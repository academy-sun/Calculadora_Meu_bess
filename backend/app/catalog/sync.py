"""
Réplica fiel do catálogo da plataforma plataforma.meubess.com.br.

O sync NÃO classifica nem descarta produtos: ele espelha todos os campos
relevantes do produto MeuBESS na tabela única `meubess_products`. A
classificação é uma anotação não-destrutiva (tipo_auto + needs_review),
calculada por cascata de sinais, e pode ser sobrescrita manualmente
(tipo_manual / overrides_tecnicos) sem ser perdida no próximo sync.

Datas de compliance são geradas no Supabase, não na MeuBESS:
  • first_seen_at  → gravada só no primeiro INSERT (entrada no banco)
  • last_synced_at → atualizada em todo sync

IMPORTANTE: a MeuBESS é somente-leitura. Toda interação é GET na API.
"""

from datetime import datetime

import logging
import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import MeuBESSProduct
from app.config import settings


# ── helpers ─────────────────────────────────────────────────────────────────


log = logging.getLogger("catalog.sync")


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.meubess_api_key}",
        "Accept": "application/json",
    }


def _safe_float(val: object) -> float | None:
    """Convert to float, returning None on null/empty/invalid."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val: object) -> int | None:
    """Convert to int, returning None on null/empty/invalid."""
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_bool(val: object) -> bool | None:
    """Convert to bool. Accepts 1/0, '1'/'0', true/false; None stays None."""
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    s = str(val).strip().lower()
    if s in ("1", "true", "t", "yes", "s", "sim"):
        return True
    if s in ("0", "false", "f", "no", "n", "nao", "não"):
        return False
    return None


def _safe_str(val: object) -> str | None:
    """Stringify scalars; collapse empty to None. Lists/dicts → None (handled separately)."""
    if val is None or val == "":
        return None
    if isinstance(val, (dict, list)):
        return None
    return str(val)


def _nested(obj: dict, key: str, field: str) -> str | None:
    """Extract `obj[key][field]` safely as string. Returns None if missing."""
    sub = obj.get(key)
    if isinstance(sub, dict):
        return _safe_str(sub.get(field))
    return None


# ── classification cascade (annotation only — never filters/discards) ─────────

_BATTERY    = "bateria"
_HYBRID     = "inversor_hibrido"
_STRING     = "inversor_string"
_MODULE     = "modulo_fv"
_ACESSORIO  = "acessorio"
_UNKNOWN    = "indefinido"

_HYBRID_TITLE_TOKENS = ("híbrido", "hibrido", "hybrid")
_MODULE_TOKENS       = ("módulo", "modulo", "module", "painel", "fotovolt", "placa")
_INVERTER_GROUPS     = ("inversor", "inverter", "inversores")


def classify_product(raw: dict) -> tuple[str, str, bool]:
    """
    Classificação por cascata de sinais. Retorna (tipo_auto, confianca, needs_review).

    Ordem:
      1. Bateria   — category contém "bateria"/"cabine de bateria" ou section "bat_litio".
      2. Módulo FV — groups "módulo" ou category/título indicam módulo fotovoltaico.
      3. É inversor? — só entra na lógica híbrido/string quem é de fato inversor
         (groups inversor, OU tem battery_inputs/max_eps, OU category contém "inversor").
         Caso contrário → acessório (estrutura, disjuntor, medidor, cabo…), sem revisão.
         Isso evita falsos positivos como "Trilho Híbrido" ou "Medidor compatível com Híbrido".
      4. Inversor → híbrido vs string, na sub-ordem técnico → categoria → título → fase.

    confianca: 'alta' (sinal técnico), 'media' (bateria/módulo/acessório/categoria),
               'baixa' (título/fase).
    needs_review:
      • técnico presente → revisa só se um sinal textual o contradiz (divergência);
      • sem técnico e classificado HÍBRIDO → revisa (alto custo de erro, falta ground-truth);
      • sem técnico e classificado STRING por categoria → revisa só se há sinal de híbrido divergente;
      • bateria/módulo/acessório → não revisa.
    """
    title   = (raw.get("title") or "").lower()
    cat     = (raw.get("category_title") or "").lower()
    section = (raw.get("section") or "").lower()
    groups  = (raw.get("groups") or "").lower()
    phase   = (raw.get("phase") or "").lower()
    battery_inputs = raw.get("battery_inputs")
    eps_val        = _safe_float(raw.get("max_eps_power"))

    # 1. Bateria (categoria/section confiáveis)
    if "bateria" in cat or "cabine de bateria" in cat or section == "bat_litio":
        return _BATTERY, "media", False

    # 2. Módulo FV (antes de inversor; "Módulo de Bateria" já tratado acima)
    if groups in _MODULE_TOKENS or any(tok in cat for tok in _MODULE_TOKENS):
        return _MODULE, "media", False

    # 3. É realmente um inversor?
    is_inverter = (
        groups in _INVERTER_GROUPS
        or battery_inputs is not None
        or (eps_val is not None and eps_val > 0)
        or "inversor" in cat
        or phase == "hibrido"  # fase híbrida só existe em inversor
    )
    if not is_inverter:
        # Acessório / estrutura / medidor / cabo — não é candidato a kit.
        return _ACESSORIO, "media", False

    # ── 4. Inversor: distinguir híbrido vs string ────────────────────────────

    # técnico (ground-truth quando preenchido)
    tecnico: str | None = None
    if battery_inputs is not None:
        tecnico = _HYBRID if battery_inputs > 0 else _STRING
    elif eps_val is not None and eps_val > 0:
        tecnico = _HYBRID

    # categoria
    if any(tok in cat for tok in _HYBRID_TITLE_TOKENS):
        cat_sig: str | None = _HYBRID
    elif "inversor" in cat:  # inclui microinversor, monofásico/trifásico
        cat_sig = _STRING
    else:
        cat_sig = None

    # título / fase
    tit_sig  = _HYBRID if any(tok in title for tok in _HYBRID_TITLE_TOKENS) else None
    fase_sig = _HYBRID if phase == "hibrido" else None

    # ── Decisão ──────────────────────────────────────────────────────────────
    if tecnico is not None:
        contradiz = any(s is not None and s != tecnico for s in (cat_sig, tit_sig, fase_sig))
        return tecnico, "alta", contradiz

    algum_sinal_hibrido = _HYBRID in (cat_sig, tit_sig, fase_sig)

    # Sem técnico: decide por texto.
    if cat_sig == _HYBRID:
        return _HYBRID, "media", True
    if cat_sig == _STRING:
        # String por categoria clara — só revisa se outra fonte aponta híbrido.
        return _STRING, "media", algum_sinal_hibrido
    if tit_sig == _HYBRID or fase_sig == _HYBRID:
        return _HYBRID, "baixa", True

    # É inversor, mas sem pista de híbrido/string → assume string, pede revisão.
    return _STRING, "baixa", True


# ── mapeamento raw (espelha o produto MeuBESS em colunas) ─────────────────────


#: Chaves do payload da plataforma que o sync JÁ consome, direto ou aninhado.
#: Serve só para o aviso abaixo — não é validação.
_CHAVES_CONHECIDAS: set[str] = set()


def _avisar_campos_ignorados(produtos: list[dict]) -> None:
    """Registra campos que a plataforma manda e o sync descarta.

    Não é diagnóstico de erro: é como se descobre que a origem passou a expor
    um dado que interessa. Custou caro descobrir tarde que o preço de custo
    existia na API e não estava sendo importado — a calculadora cotou com o
    "preço de venda fixo" da plataforma, que é preenchido à mão e não segue a
    fórmula de margem. Um aviso por sync evita a próxima.
    """
    if not produtos:
        return
    global _CHAVES_CONHECIDAS
    if not _CHAVES_CONHECIDAS:
        import inspect
        import re
        fonte = inspect.getsource(_map_to_raw)
        _CHAVES_CONHECIDAS = set(re.findall(r'\.get\("([a-zA-Z_]+)"', fonte)) | {"id"}

    vistas: set[str] = set()
    for prod in produtos[:50]:      # amostra basta; o payload é homogêneo
        vistas |= {k for k, v in prod.items() if v is not None}
    ignoradas = sorted(vistas - _CHAVES_CONHECIDAS)
    if ignoradas:
        log.info("campos da plataforma que o sync ignora: %s", ", ".join(ignoradas))


def _map_to_raw(product: dict) -> dict:
    """Achata o JSON do produto MeuBESS no formato das colunas de meubess_products."""
    raw = {
        "meubess_id": str(product["id"]),

        # identidade / comercial
        "enterprise_id": _safe_str(product.get("enterprise_id")),
        "title": _safe_str(product.get("title")),
        "original_title": _safe_str(product.get("original_title")),
        "description": _safe_str(product.get("description")),
        "sku": _safe_str(product.get("sku")),
        "suplier_cod": _safe_str(product.get("suplier_cod")),
        "marca": _safe_str(product.get("marca")) or _nested(product, "brand", "title"),
        "brand_id": _safe_str(product.get("brand_id")) or _nested(product, "brand", "id"),
        "brand_title": _nested(product, "brand", "title"),
        "supplier_id": _safe_str(product.get("supplier_id")) or _nested(product, "supplier", "id"),
        "supplier_title": _nested(product, "supplier", "title"),
        "app": _safe_str(product.get("app")),
        "active": _safe_bool(product.get("active")),
        "view": _safe_str(product.get("view")),
        "section": _safe_str(product.get("section")),
        "type": _safe_str(product.get("type")),
        "groups": _safe_str(product.get("groups")),
        "availability": _safe_str(product.get("availability")),

        # categoria
        "category_id": _safe_str(product.get("category_id")) or _nested(product, "category", "id"),
        "category_title": _nested(product, "category", "title"),
        "category_section": _nested(product, "category", "section"),

        # elétricos / técnicos
        "power": _safe_float(product.get("power")),
        "voltage": _safe_str(product.get("voltage")),
        "phase": _safe_str(product.get("phase")),
        "breaker": _safe_str(product.get("breaker")),
        "battery_inputs": _safe_int(product.get("battery_inputs")),
        "max_eps_power": _safe_float(product.get("max_eps_power")),
        "max_output_power": _safe_float(product.get("max_output_power")),
        "qty_mppt": _safe_int(product.get("qty_mppt")),
        "qty_inputs_per_mppt": _safe_int(product.get("qty_inputs_per_mppt")),
        "voc_max_voltage": _safe_float(product.get("voc_max_voltage")),
        "mppt_min_voltage": _safe_float(product.get("mppt_min_voltage")),
        "output_voltage": _safe_float(product.get("output_voltage")),
        "string_current": _safe_float(product.get("string_current")),
        "short_circuit_current_inverter": _safe_float(product.get("short_circuit_current_inverter")),
        "short_circuit_current_module": _safe_float(product.get("short_circuit_current_module")),
        "max_power_current": _safe_float(product.get("max_power_current")),

        # preço / fiscal / dimensão
        "price": _safe_float(product.get("price")),
        "price_sale": _safe_float(product.get("price_sale")),
        "price_sale_until": _safe_str(product.get("price_sale_until")),
        "ncm": _safe_str(product.get("ncm")),
        "unt_measure": _safe_str(product.get("unt_measure")),
        "unt_multiples": _safe_str(product.get("unt_multiples")),
        "weight": _safe_float(product.get("weight")),
        "width": _safe_float(product.get("width")),
        "height": _safe_float(product.get("height")),
        "length": _safe_float(product.get("length")),
        "volumes": _safe_float(product.get("volumes")),
        "fixing_type": _safe_str(product.get("fixing_type")),
        "fixing_capacity": _safe_int(product.get("fixing_capacity")),

        # mídia (lista de imagens → JSONB)
        "images": product.get("images") if isinstance(product.get("images"), list) else None,
    }

    tipo_auto, confianca, needs_review = classify_product(raw)
    raw["tipo_auto"] = tipo_auto
    raw["classificacao_confianca"] = confianca
    raw["needs_review"] = needs_review
    return raw


# ── upsert (preserva first_seen_at e decisão humana) ──────────────────────────

# Colunas que NÃO devem ser sobrescritas num re-sync:
#   first_seen_at        → data de entrada no banco (só no primeiro INSERT)
#   tipo_manual / ...    → decisão humana de validação/override
_PRESERVE_ON_CONFLICT = {
    "first_seen_at",
    "tipo_manual",
    "ativo_manual",
    "overrides_tecnicos",
    "validado_por",
    "validado_em",
}


async def _upsert_raw(db: AsyncSession, data: dict) -> None:
    now = datetime.utcnow()
    values = {**data, "last_synced_at": now, "first_seen_at": now}
    stmt = pg_insert(MeuBESSProduct).values(**values)
    # No conflito: atualiza tudo MENOS as colunas preservadas; refresca last_synced_at.
    update_set = {
        k: stmt.excluded[k]
        for k in data
        if k not in _PRESERVE_ON_CONFLICT and k != "meubess_id"
    }
    update_set["last_synced_at"] = now
    stmt = stmt.on_conflict_do_update(index_elements=["meubess_id"], set_=update_set)
    await db.execute(stmt)


# ── fetch all (paginado) ──────────────────────────────────────────────────────


async def _fetch_from_endpoint(client: httpx.AsyncClient, base_url: str) -> list[dict]:
    """Pagina todos os produtos de um endpoint específico."""
    products: list[dict] = []
    page = 1

    while True:
        resp = await client.get(
            base_url,
            headers=_auth_headers(),
            params={"per_page": 100, "page": page},
        )
        resp.raise_for_status()
        body = resp.json()

        # Plain array — entire result in one shot
        if isinstance(body, list):
            products.extend(body)
            break

        # Paginated envelope: { "data": [...], "links": {...}, "meta": {...} }
        if isinstance(body, dict) and "data" in body:
            page_data: list[dict] = body["data"]
            products.extend(page_data)

            if not page_data:
                break  # empty page → done

            meta = body.get("meta") or {}
            # Laravel pode retornar last_page dentro de "meta" (Resource format)
            # ou no nível raiz da resposta (flat paginator format)
            last_page = meta.get("last_page") or body.get("last_page")
            links = body.get("links")
            next_url = (
                links.get("next") if isinstance(links, dict)
                else body.get("next_page_url")
            )

            if last_page is not None and page >= last_page:
                break
            if next_url is None and last_page is None:
                break

            page += 1
            continue

        # Fallback: treat whole body as a single product
        if isinstance(body, dict) and "id" in body:
            products.append(body)
        break

    return products


async def _fetch_all_products(client: httpx.AsyncClient) -> list[dict]:
    """
    Fetch every product from the supplier API.

    Tries GET /products/all first (paginated bulk endpoint). If the server
    returns a 5xx error, falls back to GET /products.
    """
    endpoints = [
        f"{settings.meubess_api_url}/products/all",
        f"{settings.meubess_api_url}/products",
    ]
    last_exc: httpx.HTTPStatusError | None = None

    for url in endpoints:
        try:
            return await _fetch_from_endpoint(client, url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                last_exc = exc
                continue
            raise  # 4xx (auth, not found) não deve ser silenciado

    raise ValueError(
        f"Nenhum endpoint de produtos disponível na API do fornecedor. "
        f"Último erro: HTTP {last_exc.response.status_code} — "
        f"{last_exc.response.text[:200]}"
    ) from last_exc


# ── per-product processing ────────────────────────────────────────────────────


class SyncResult:
    def __init__(self) -> None:
        self.synced: list[dict] = []
        self.errors: list[dict] = []
        self.por_tipo: dict[str, int] = {}
        self.needs_review_count = 0

    def record(self, raw: dict) -> None:
        tipo = raw.get("tipo_auto") or "indefinido"
        self.por_tipo[tipo] = self.por_tipo.get(tipo, 0) + 1
        if raw.get("needs_review"):
            self.needs_review_count += 1
        self.synced.append({
            "id": raw["meubess_id"],
            "tipo_auto": tipo,
            "confianca": raw.get("classificacao_confianca"),
            "needs_review": raw.get("needs_review"),
            "marca": raw.get("marca"),
            "title": raw.get("title"),
        })

    def to_dict(self) -> dict:
        return {
            "synced": self.synced,
            "errors": self.errors,
            "total_synced": len(self.synced),
            "total_errors": len(self.errors),
            "por_tipo": self.por_tipo,
            "needs_review_count": self.needs_review_count,
        }


async def _process_product(db: AsyncSession, product: dict, result: SyncResult) -> None:
    pid = str(product.get("id", "?"))
    try:
        data = _map_to_raw(product)
        await _upsert_raw(db, data)
        result.record(data)
    except Exception as exc:  # noqa: BLE001
        # Roll back para a sessão não ficar em estado de transação abortada.
        await db.rollback()
        result.errors.append({"id": pid, "error": str(exc)})


# ── public API ────────────────────────────────────────────────────────────────


def _check_api_key() -> None:
    if not settings.meubess_api_key:
        raise ValueError(
            "MEUBESS_API_KEY não configurada. "
            "Adicione a variável de ambiente no Railway."
        )


async def sync_all_products(db: AsyncSession) -> dict:
    """
    Replica TODOS os produtos da API do fornecedor (paginado) na tabela
    única `meubess_products`, sem classificar/descartar — apenas anotando
    o tipo sugerido (tipo_auto) e a flag de revisão (needs_review).
    """
    _check_api_key()
    result = SyncResult()

    _timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=_timeout) as client:
        try:
            products = await _fetch_all_products(client)
        except httpx.HTTPStatusError as exc:
            raise ValueError(
                f"Falha ao listar produtos: HTTP {exc.response.status_code} — "
                f"{exc.response.text[:300]}"
            ) from exc
        except httpx.ConnectError as exc:
            raise ValueError(
                f"Não foi possível conectar à plataforma meubess.com.br: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ValueError(
                f"Timeout ao conectar com a plataforma meubess.com.br: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise ValueError(
                f"Erro de rede ao acessar plataforma meubess.com.br: {exc}"
            ) from exc

        _avisar_campos_ignorados(products)

        for product in products:
            await _process_product(db, product, result)

    # Produto novo chega da plataforma sempre ativo, sem decisão nossa. Sem
    # este passo o catálogo se repovoa a cada sync: na primeira execução
    # automática entraram 13 produtos que a curadoria já tinha excluído.
    from app.catalog.curadoria import aplicar_curadoria
    curados = await aplicar_curadoria(db)

    await db.commit()
    return {**result.to_dict(), "desativados_pela_politica": curados}


async def preview_raw_products(limit: int = 5) -> list[dict]:
    """
    Fetch the first `limit` raw products from the supplier API without inserting anything.
    Used for debugging field names / structure.
    """
    _check_api_key()
    _timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=_timeout) as client:
        products = await _fetch_all_products(client)
    return products[:limit]


async def sync_products_by_ids(db: AsyncSession, product_ids: list[str]) -> dict:
    """
    Fetch specific product IDs from the supplier API and upsert them into
    `meubess_products`. Útil para refresh pontual (ex.: webhook).
    """
    _check_api_key()
    result = SyncResult()

    async with httpx.AsyncClient(timeout=15.0) as client:
        for pid in product_ids:
            pid = pid.strip()
            if not pid:
                continue
            try:
                resp = await client.get(
                    f"{settings.meubess_api_url}/products/{pid}",
                    headers=_auth_headers(),
                )
                resp.raise_for_status()
                product = resp.json()
                await _process_product(db, product, result)
            except httpx.HTTPStatusError as exc:
                result.errors.append({
                    "id": pid,
                    "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                })
            except Exception as exc:  # noqa: BLE001
                result.errors.append({"id": pid, "error": str(exc)})

    await db.commit()
    return result.to_dict()
