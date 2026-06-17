import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.catalog import service
from app.catalog import sync as sync_svc
from app.catalog.schemas import (
    MeuBESSProductRead, MeuBESSProductUpdate,
    ProductBESSCreate, ProductBESSRead,
    ProductSolarCreate, ProductSolarRead,
    StandardLoadCreate, StandardLoadRead,
)
from app.database import get_db

router = APIRouter(prefix="/catalog", tags=["catalog"])


# ── Sync from supplier platform ──────────────────────────────────────────────


@router.get("/sync/preview", tags=["catalog"])
async def sync_preview(
    limit: int = 5,
    _=Depends(require_admin),
) -> list[dict]:
    """Admin-only: fetch first N raw products from supplier API (no DB insert). For debugging field structure."""
    try:
        return await sync_svc.preview_raw_products(limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/sync/status", tags=["catalog"])
async def sync_status(_=Depends(require_admin)) -> dict:
    """Admin-only: check sync configuration without making external requests."""
    from app.config import settings
    key = settings.meubess_api_key
    return {
        "api_key_configured": bool(key),
        "api_key_preview": f"{key[:8]}…" if key else None,
        "api_url": settings.meubess_api_url,
    }


@router.post("/sync", tags=["catalog"])
async def sync_catalog(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    """
    Admin-only: fetch ALL products from plataforma.meubess.com.br (paginated)
    and upsert them into products_bess or products_solar based on their type.
    """
    try:
        return await sync_svc.sync_all_products(db)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ── Réplica MeuBESS (tabela única meubess_products) ──────────────────────────


@router.get("/products", response_model=list[MeuBESSProductRead], tags=["catalog"])
async def get_products(
    tipo: str | None = Query(None, description="tipo efetivo: bateria/inversor_hibrido/inversor_string/modulo_fv/indefinido"),
    marca: str | None = None,
    app: str | None = None,
    needs_review: bool | None = None,
    titulo: str | None = None,
    potencia_min: float | None = Query(None, description="potência mínima em kW (sozinha = 'maior que')"),
    potencia_max: float | None = Query(None, description="potência máxima em kW (sozinha = 'menor que')"),
    active: bool | None = Query(None, description="situação: true=ativo, false=inativo"),
    synced_from: datetime | None = None,
    synced_to: datetime | None = None,
    seen_from: datetime | None = None,
    seen_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Lista a réplica fiel do catálogo MeuBESS com filtros (substitui /bess e /solar)."""
    return await service.list_products(
        db,
        tipo=tipo, marca=marca, app=app, needs_review=needs_review, titulo=titulo,
        potencia_min=potencia_min, potencia_max=potencia_max, active=active,
        synced_from=synced_from, synced_to=synced_to,
        seen_from=seen_from, seen_to=seen_to,
    )


@router.patch("/products/{meubess_id}", response_model=MeuBESSProductRead, tags=["catalog"])
async def patch_product(
    meubess_id: str,
    data: MeuBESSProductUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Edição manual / validação de um produto (tipo_manual, overrides técnicos, marcar validado)."""
    product = await service.update_product(db, meubess_id, data)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product


@router.get("/bess", response_model=list[ProductBESSRead])
async def get_bess(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    return await service.list_bess(db)


@router.post("/bess", response_model=ProductBESSRead, status_code=201)
async def add_bess(
    data: ProductBESSCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    return await service.create_bess(db, data)


@router.put("/bess/{product_id}", response_model=ProductBESSRead)
async def update_bess(
    product_id: uuid.UUID,
    data: ProductBESSCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    product = await service.update_bess(db, product_id, data)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product


@router.delete("/bess/{product_id}", status_code=204)
async def delete_bess(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    deleted = await service.delete_bess(db, product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Produto não encontrado")


@router.get("/solar", response_model=list[ProductSolarRead])
async def get_solar(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    return await service.list_solar(db)


@router.post("/solar", response_model=ProductSolarRead, status_code=201)
async def add_solar(
    data: ProductSolarCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    return await service.create_solar(db, data)


@router.put("/solar/{product_id}", response_model=ProductSolarRead)
async def update_solar(
    product_id: uuid.UUID,
    data: ProductSolarCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    product = await service.update_solar(db, product_id, data)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product


@router.delete("/solar/{product_id}", status_code=204)
async def delete_solar(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    deleted = await service.delete_solar(db, product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Produto não encontrado")


@router.get("/loads", response_model=list[StandardLoadRead])
async def get_loads(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    return await service.list_loads(db)


@router.post("/loads", response_model=StandardLoadRead, status_code=201)
async def add_load(
    data: StandardLoadCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    return await service.create_load(db, data)


@router.put("/loads/{load_id}", response_model=StandardLoadRead)
async def update_load(
    load_id: uuid.UUID,
    data: StandardLoadCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    load = await service.update_load(db, load_id, data)
    if not load:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
    return load


@router.delete("/loads/{load_id}", status_code=204)
async def delete_load(
    load_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    deleted = await service.delete_load(db, load_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
