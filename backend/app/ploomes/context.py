"""
Leitura do contexto de um negócio no Ploomes para prefill do embed.

O mapeamento FieldKey → nosso campo é específico da conta e vem da env
PLOOMES_FIELD_MAP (JSON). Exemplo:

    PLOOMES_FIELD_MAP={"powerpeak_kwp":"deal_A1B2...","cidade":"deal_C3D4...",
                       "uf":"deal_E5F6...","fixing_type":"deal_G7H8...",
                       "kit_preco":"deal_I9J0...","kit_descricao":"deal_K1L2...",
                       "frete_valor":"deal_M3N4...","total_geral":"deal_O5P6..."}

Chaves de ENTRADA (context): powerpeak_kwp, cidade, uf, fixing_type
Chaves de SAÍDA (pushback):  kit_preco, kit_descricao, frete_valor, frete_descricao, total_geral
"""

import json

from app.config import settings
from app.ploomes import client


def field_map() -> dict[str, str]:
    if not settings.ploomes_field_map:
        return {}
    try:
        return json.loads(settings.ploomes_field_map)
    except json.JSONDecodeError:
        return {}


def _other_properties_dict(deal: dict) -> dict[str, object]:
    """OtherProperties do Ploomes → {FieldKey: valor} (pega o primeiro valor não-nulo)."""
    out: dict[str, object] = {}
    for prop in deal.get("OtherProperties") or []:
        key = prop.get("FieldKey")
        if not key:
            continue
        for vk in ("StringValue", "BigStringValue", "DecimalValue", "IntegerValue",
                   "BoolValue", "DateTimeValue", "ObjectValueName"):
            v = prop.get(vk)
            if v is not None:
                out[key] = v
                break
    return out


async def get_deal_context(deal_id: int) -> dict:
    """Busca o negócio com campos custom e cidade, e devolve o prefill mapeado
    + os campos crus (raw_fields) para diagnóstico/descoberta."""
    data = await client.get(
        f"/Deals?$filter=Id+eq+{deal_id}"
        "&$expand=OtherProperties,City($select=Name,Short;$expand=State($select=Short))"
    )
    deals = data.get("value") or []
    if not deals:
        raise client.PloomesError(404, f"Negócio {deal_id} não encontrado")
    deal = deals[0]

    props = _other_properties_dict(deal)
    fmap = field_map()

    def mapped(key: str):
        fk = fmap.get(key)
        return props.get(fk) if fk else None

    # cidade/UF: prioridade para o City nativo do negócio; fallback nos campos custom
    city = deal.get("City") or {}
    state = city.get("State") or {}
    cidade = city.get("Name") or mapped("cidade")
    uf = state.get("Short") or city.get("Short") or mapped("uf")

    powerpeak_raw = mapped("powerpeak_kwp")
    try:
        powerpeak_kwp = float(powerpeak_raw) if powerpeak_raw is not None else None
    except (TypeError, ValueError):
        powerpeak_kwp = None

    return {
        "deal_id": deal_id,
        "titulo": deal.get("Title"),
        "powerpeak_kwp": powerpeak_kwp,
        "cidade": cidade,
        "uf": uf,
        "fixing_type": mapped("fixing_type"),
        "field_map_configurado": bool(fmap),
        "raw_fields": [
            {"field_key": k, "valor": v} for k, v in sorted(props.items())
        ],
    }


async def list_fields(entity_id: int | None = None) -> list[dict]:
    """Descoberta: lista campos custom da conta (Key, Name, Type) para montar o
    PLOOMES_FIELD_MAP. entity_id opcional filtra por entidade (ex.: Deals)."""
    path = "/Fields?$select=Id,Key,Name,EntityId,TypeId&$top=300"
    if entity_id is not None:
        path += f"&$filter=EntityId+eq+{entity_id}"
    data = await client.get(path)
    return [
        {
            "id": f.get("Id"),
            "key": f.get("Key"),
            "name": f.get("Name"),
            "entity_id": f.get("EntityId"),
            "type_id": f.get("TypeId"),
        }
        for f in data.get("value") or []
    ]
