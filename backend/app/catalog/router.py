import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.catalog import service
from app.catalog.schemas import (
    ProductBESSCreate, ProductBESSRead,
    ProductSolarCreate, ProductSolarRead,
    StandardLoadCreate, StandardLoadRead,
)
from app.database import get_db

router = APIRouter(prefix="/catalog", tags=["catalog"])


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
