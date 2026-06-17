"""
Synchronisation with plataforma.meubess.com.br supplier API.

Routing rules — uses `category.title` (Portuguese) as primary signal,
falls back to `groups` for English-format catalogs:

  category.title contains "Módulo de Bateria"/"Cabine de Baterias"
                                           → products_bess  /  tipo = "bateria"
  category.title contains "Híbrido"       → products_bess  /  tipo = "inversor_hibrido"
  category.title contains "SplitPhase"
    + app contains "bess"                 → products_bess  /  tipo = "inversor_hibrido"
  category.title contains "Microinversor"
    OR title keywords                     → products_solar /  tipo = "inversor_solar"
  category.title contains "bomba"         → SKIPPED
  groups == "Inversor" (other categories) → products_solar /  tipo = "inversor_solar"
  groups == "Módulo" / "panel" variants   → products_solar /  tipo = "modulo_fv"
  groups == "battery" variants (English)  → products_bess  /  tipo = "bateria"
  groups == "inverter" / "hybrid" (Eng.)  → products_bess  /  tipo = "inversor_hibrido"
  groups == "string_inverter" (English)   → products_solar /  tipo = "inversor_solar"
  app == "solar"                          → products_solar /  tipo = "modulo_fv"
  anything else (cables, structures…)    → SKIPPED

Valid DB values:
  products_bess.tipo  ∈ { 'bateria', 'inversor_hibrido' }
  products_solar.tipo ∈ { 'modulo_fv', 'inversor_solar' }

Unit assumptions:
  • power for inverters  → potencia_continua_kw (kW)
  • power for batteries  → capacidade_kwh (kWh)
  • power for panels     → potencia_pico_wp (Wp) — API sends kW, multiply × 1 000
  • power for inversor_solar → potencia_nominal_kw (kW)
"""

import uuid
from datetime import datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import ProductBESS, ProductSolar
from app.config import settings


# ── helpers ─────────────────────────────────────────────────────────────────


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


def _safe_price(product: dict) -> float:
    """Return best available price (price → price_sale → 0). Never raises."""
    for key in ("price", "price_sale"):
        f = _safe_float(product.get(key))
        if f is not None and f > 0:
            return f
    return 0.0


def _safe_brand(product: dict) -> str:
    """Extract brand title safely; returns 'Desconhecida' if missing/null."""
    brand = product.get("brand")
    if isinstance(brand, dict):
        return brand.get("title") or "Desconhecida"
    return str(brand) if brand else "Desconhecida"


def _extract_modelo(title: str) -> str:
    """
    Input:  "W - WEG - 15,0KW 380V - SIW400G T015 W1 - Inversor Trifásico"
    Output: "15,0KW 380V - SIW400G T015 W1"
    """
    parts = [p.strip() for p in title.split(" - ")]
    if len(parts) >= 4:
        return " - ".join(parts[2:-1])
    if len(parts) == 3:
        return parts[1]
    return title


def _enrich_modelo(modelo: str, power: float | None, tipo: str) -> str:
    """
    Appends the power rating to the model name when it is missing.

    Prevents all variants of the same product line from showing the same
    generic model (e.g. four OUROLUX "SOFAR" inverters at 4/5/7.5/10 kW
    all appearing as "SOFAR").
    """
    import re
    if not power or tipo == "bateria":
        return modelo
    # Already has a power indicator — leave it alone
    if re.search(r"\d[\d,.]*\s*k?[wva]", modelo, re.IGNORECASE):
        return modelo
    kw_str = f"{power:g}".replace(".", ",") + "kW"
    return f"{modelo} {kw_str}"


_SKIP_TITLE_KEYWORDS: tuple[str, ...] = (
    # Cabos
    "cabo solar", "cabo ", " cabo",
    # Conectores
    "conector", " mc4", "mc4 ",
    # Estruturas de fixação / suporte
    "estrutura", "carport", "abrigo de inversor",
    # Hardware (parafusos, fixadores, trilhos)
    "fixador", "grampo", "parafuso", "porca ", " porca", "borracha",
    "trilho", "perfil ", " perfil", "haste", "emenda u",
    # Monitoramento / dataloggers
    "monitoramento", "gateway",
)

_MICROINVERTER_KEYWORDS: tuple[str, ...] = (
    "microinversor", "micro inversor", "micro-inversor",
)


def _classify(product: dict) -> tuple[str, str] | tuple[None, None]:
    """
    Returns (table: 'bess' | 'solar', tipo: str) or (None, None) to skip.

    Uses category.title as primary signal for the MeuBESS Portuguese catalog.
    Falls back to English group names for other catalog formats.
    """
    title     = (product.get("title")  or "").lower()
    groups    = (product.get("groups") or "").strip().lower()
    app       = (product.get("app")    or "").lower()
    cat_obj   = product.get("category") or {}
    cat_raw   = cat_obj.get("title") if isinstance(cat_obj, dict) else None
    cat_title = (cat_raw or "").lower()

    # ── Rejeição antecipada por palavras no título ────────────────────────────
    if any(kw in title for kw in _SKIP_TITLE_KEYWORDS):
        return None, None

    # ── Kit bundles (e.g. "Kit Gerador") → sempre ignorar ────────────────────
    if "kit" in groups and "gerador" in groups:
        return None, None

    # ── category.title routing (MeuBESS Portuguese catalog) ──────────────────
    if cat_title:
        # Batteries: Grupo="Acessórios", Categoria="Módulo de Bateria" / "Cabine de Baterias"
        if "módulo de bateria" in cat_title or "cabine de bateria" in cat_title:
            return "bess", "bateria"

        if groups in ("inversor", "inversores"):
            # Pump inverters → skip
            if "bomba" in cat_title:
                return None, None
            # Micro-inverters → solar
            if "microinversor" in cat_title or any(kw in title for kw in _MICROINVERTER_KEYWORDS):
                return "solar", "inversor_solar"
            # Explicit hybrid category → BESS
            if "híbrido" in cat_title or "hibrido" in cat_title:
                return "bess", "inversor_hibrido"
            # SplitPhase with bess app → these are battery-compatible (e.g. WEG SIW200H SplitPhase)
            if "splitphase" in cat_title.replace(" ", "").replace("-", ""):
                if "bess" in app:
                    return "bess", "inversor_hibrido"
                return "solar", "inversor_solar"
            # All other inverter categories (Monofásico, Trifásico, etc.) → string inverter
            return "solar", "inversor_solar"

        if groups in ("módulo", "módulos", "modulo"):
            return "solar", "modulo_fv"

    # ── English group names (legacy / other catalog formats) ─────────────────

    # batteries
    if groups in ("battery", "battery_storage", "storage", "bateria"):
        return "bess", "bateria"

    # hybrid / off-grid inverters
    if groups in ("inverter", "hybrid", "hibrido", "off_grid", "offgrid"):
        if any(kw in title for kw in _MICROINVERTER_KEYWORDS):
            return "solar", "inversor_solar"
        return "bess", "inversor_hibrido"

    # solar panels
    if groups in ("panel", "solar_panel", "module", "modulo", "painel", "placa"):
        return "solar", "modulo_fv"

    # string / on-grid solar inverters
    if groups in ("string_inverter", "inverter_string", "on_grid", "ongrid",
                  "inversor_solar", "solar_inverter"):
        return "solar", "inversor_solar"

    # app-level fallback for solar
    if app == "solar":
        return "solar", "modulo_fv"

    # skip everything else
    return None, None


def _map_to_bess(product: dict, tipo: str) -> dict:
    power = _safe_float(product.get("power"))
    modelo = _enrich_modelo(
        _extract_modelo(product.get("title") or str(product["id"])),
        power,
        tipo,
    )
    return {
        "sku": str(product["id"]),
        "marca": _safe_brand(product),
        "modelo": modelo,
        "tipo": tipo,
        "fase": product.get("phase") or None,
        "potencia_continua_kw": power if tipo != "bateria" else None,
        "capacidade_kwh":       power if tipo == "bateria" else None,
        "preco": _safe_price(product),
        "disponivel": bool(product.get("active", True)),
    }


def _map_to_solar(product: dict, tipo: str = "modulo_fv") -> dict:
    power = _safe_float(product.get("power"))
    # API sends power in kW for all products.
    # Solar panels: field expects Wp  → multiply by 1000  (e.g. 0.55 kW → 550 Wp)
    # String inverters: field expects kW → keep as-is
    potencia_pico_wp   = power * 1000 if power and tipo == "modulo_fv"      else None
    potencia_nominal_kw = power        if power and tipo == "inversor_solar" else None
    return {
        "sku": str(product["id"]),
        "marca": _safe_brand(product),
        "modelo": _extract_modelo(product.get("title") or str(product["id"])),
        "tipo": tipo,
        "potencia_pico_wp":   potencia_pico_wp,
        "potencia_nominal_kw": potencia_nominal_kw,
        "fase": product.get("phase") or None,
        "preco": _safe_price(product),
        "disponivel": bool(product.get("active", True)),
    }


# ── upsert ───────────────────────────────────────────────────────────────────


async def _upsert_bess(db: AsyncSession, data: dict) -> None:
    stmt = pg_insert(ProductBESS).values(
        id=uuid.uuid4(), atualizado_em=datetime.utcnow(), **data
    )
    update_set = {k: stmt.excluded[k] for k in data if k != "sku"}
    update_set["atualizado_em"] = datetime.utcnow()
    stmt = stmt.on_conflict_do_update(index_elements=["sku"], set_=update_set)
    await db.execute(stmt)


async def _upsert_solar(db: AsyncSession, data: dict) -> None:
    stmt = pg_insert(ProductSolar).values(id=uuid.uuid4(), **data)
    update_set = {k: stmt.excluded[k] for k in data if k != "sku"}
    stmt = stmt.on_conflict_do_update(index_elements=["sku"], set_=update_set)
    await db.execute(stmt)


# ── fetch all (with pagination) ───────────────────────────────────────────────


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
            # "links" pode ser um dict {"next": url} (Resource) ou lista (flat)
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
    returns a 5xx error, falls back to GET /products. This handles temporary
    bugs in the supplier's backend without failing the whole sync.
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
                # Erro no servidor do fornecedor neste endpoint — tenta o próximo
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
        self.skipped: list[str] = []

    def to_dict(self) -> dict:
        return {
            "synced": self.synced,
            "errors": self.errors,
            "total_synced": len(self.synced),
            "total_errors": len(self.errors),
            "total_skipped": len(self.skipped),
        }


async def _process_product(db: AsyncSession, product: dict, result: SyncResult) -> None:
    pid = str(product.get("id", "?"))
    try:
        table, tipo = _classify(product)
        if table is None:
            # Not a catalogable product (accessory, cable, structure, etc.) — skip silently
            result.skipped.append(pid)
            return
        if table == "bess":
            data = _map_to_bess(product, tipo)
            await _upsert_bess(db, data)
        else:
            data = _map_to_solar(product, tipo)
            await _upsert_solar(db, data)

        result.synced.append({
            "id": pid,
            "table": table,
            "tipo": tipo,
            "marca": data["marca"],
            "modelo": data["modelo"],
            "preco": data["preco"],
        })
    except Exception as exc:  # noqa: BLE001
        # Roll back the aborted transaction so the next product can proceed normally.
        # Without this, a CheckViolationError (or any DB error) leaves the SQLAlchemy
        # session in a failed-transaction state and every subsequent execute() raises
        # InFailedSQLTransactionError.
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
    Fetch ALL products from the supplier API (paginated) and upsert into
    products_bess / products_solar based on their type.
    """
    _check_api_key()
    result = SyncResult()

    # connect=10s evita travar quando Railway não alcança a API do fornecedor
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

        for product in products:
            await _process_product(db, product, result)

    await db.commit()
    return result.to_dict()


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
    Fetch specific product IDs from the supplier API and upsert them.
    Kept for potential future use (e.g. webhook-triggered single-product refresh).
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
