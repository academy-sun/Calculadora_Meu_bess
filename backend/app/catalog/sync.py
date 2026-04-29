"""
Synchronisation with plataforma.meubess.com.br supplier API.

Rules for routing API products to our catalog tables:

  groups == "inverter"                    → products_bess  /  tipo = "inversor_hibrido"
  groups == "battery"                     → products_bess  /  tipo = "bateria"
  groups == "panel" | app == "solar"      → products_solar /  tipo = "modulo_fotovoltaico"
  groups == "string_inverter"             → products_solar /  tipo = "inversor_string"
  anything else                           → products_bess  /  tipo = "inversor_hibrido"

Notes on unit assumptions:
  • power for inverters  → potencia_continua_kw (kW)
  • power for batteries  → capacidade_kwh (kWh)
  • power for panels     → potencia_pico_wp (Wp — assumes the API sends Wp, e.g. 550.0)
"""

import uuid
from datetime import datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import ProductBESS, ProductSolar
from app.config import settings


# ── helpers ─────────────────────────────────────────────────────────────────


def _extract_modelo(title: str) -> str:
    """
    Extracts the model string from a supplier title.

    Input:  "W - WEG - 15,0KW 380V - SIW400G T015 W1 - Inversor Trifásico"
    Output: "15,0KW 380V - SIW400G T015 W1"
    """
    parts = [p.strip() for p in title.split(" - ")]
    if len(parts) >= 4:
        # keep everything between brand (index 1) and category (last index)
        return " - ".join(parts[2:-1])
    elif len(parts) == 3:
        return parts[1]
    return title


def _map_to_bess(product: dict, tipo: str) -> dict:
    power = float(product["power"]) if product.get("power") else None
    return {
        "sku": str(product["id"]),
        "marca": product["brand"]["title"],
        "modelo": _extract_modelo(product["title"]),
        "tipo": tipo,
        "fase": product.get("phase"),        # "monofasico" | "trifasico" | None
        "potencia_continua_kw": power if tipo != "bateria" else None,
        "capacidade_kwh": power if tipo == "bateria" else None,
        "preco": float(product["price"]),
        "disponivel": bool(product.get("active", True)),
    }


def _map_to_solar(product: dict, tipo: str = "modulo_fotovoltaico") -> dict:
    power = float(product["power"]) if product.get("power") else None
    return {
        "sku": str(product["id"]),
        "marca": product["brand"]["title"],
        "modelo": _extract_modelo(product["title"]),
        "tipo": tipo,
        "potencia_pico_wp": power,      # API sends Wp for panels (e.g. 550.0)
        "potencia_nominal_kw": power / 1000 if power and tipo == "inversor_string" else None,
        "fase": product.get("phase"),
        "preco": float(product["price"]),
        "disponivel": bool(product.get("active", True)),
    }


def _classify(product: dict) -> tuple[str, str]:
    """Returns (table: 'bess' | 'solar', tipo: str)."""
    groups = (product.get("groups") or "").lower()
    app = (product.get("app") or "").lower()

    if groups == "battery":
        return "bess", "bateria"
    if groups in ("panel", "solar_panel", "module"):
        return "solar", "modulo_fotovoltaico"
    if groups == "string_inverter":
        return "solar", "inversor_string"
    if app == "solar":
        return "solar", "modulo_fotovoltaico"
    # default: inverter
    return "bess", "inversor_hibrido"


# ── upsert ───────────────────────────────────────────────────────────────────


async def _upsert_bess(db: AsyncSession, data: dict) -> None:
    stmt = pg_insert(ProductBESS).values(
        id=uuid.uuid4(),
        atualizado_em=datetime.utcnow(),
        **data,
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


# ── public API ───────────────────────────────────────────────────────────────


class SyncResult:
    def __init__(self) -> None:
        self.synced: list[dict] = []
        self.errors: list[dict] = []

    def to_dict(self) -> dict:
        return {"synced": self.synced, "errors": self.errors}


async def sync_products(db: AsyncSession, product_ids: list[str]) -> dict:
    """
    Fetch each product ID from the supplier API, map it, and upsert into
    products_bess or products_solar. Returns a summary dict.
    """
    if not settings.meubess_api_key:
        raise ValueError(
            "MEUBESS_API_KEY não configurada. "
            "Adicione a variável de ambiente no Railway."
        )

    result = SyncResult()

    async with httpx.AsyncClient(timeout=15.0) as client:
        for pid in product_ids:
            pid = pid.strip()
            if not pid:
                continue
            try:
                resp = await client.get(
                    f"{settings.meubess_api_url}/products/{pid}",
                    headers={
                        "Authorization": f"Bearer {settings.meubess_api_key}",
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                product = resp.json()

                table, tipo = _classify(product)

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

            except httpx.HTTPStatusError as exc:
                result.errors.append({
                    "id": pid,
                    "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                })
            except Exception as exc:  # noqa: BLE001
                result.errors.append({"id": pid, "error": str(exc)})

    await db.commit()
    return result.to_dict()
