import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import ProductBESS, ProductSolar, StandardLoad
from app.catalog.schemas import ProductBESSCreate, ProductSolarCreate, StandardLoadCreate


async def list_bess(db: AsyncSession, disponivel_only: bool = True) -> list[ProductBESS]:
    stmt = select(ProductBESS)
    if disponivel_only:
        stmt = stmt.where(ProductBESS.disponivel == True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_bess_by_id(db: AsyncSession, product_id: uuid.UUID) -> ProductBESS | None:
    result = await db.execute(select(ProductBESS).where(ProductBESS.id == product_id))
    return result.scalar_one_or_none()


async def create_bess(db: AsyncSession, data: ProductBESSCreate) -> ProductBESS:
    product = ProductBESS(**data.model_dump(), atualizado_em=datetime.utcnow())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def update_bess(db: AsyncSession, product_id: uuid.UUID, data: ProductBESSCreate) -> ProductBESS | None:
    product = await get_bess_by_id(db, product_id)
    if not product:
        return None
    for key, value in data.model_dump().items():
        setattr(product, key, value)
    product.atualizado_em = datetime.utcnow()
    await db.commit()
    await db.refresh(product)
    return product


async def list_solar(db: AsyncSession, disponivel_only: bool = True) -> list[ProductSolar]:
    stmt = select(ProductSolar)
    if disponivel_only:
        stmt = stmt.where(ProductSolar.disponivel == True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_solar(db: AsyncSession, data: ProductSolarCreate) -> ProductSolar:
    product = ProductSolar(**data.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def list_loads(db: AsyncSession, ativo_only: bool = True) -> list[StandardLoad]:
    stmt = select(StandardLoad)
    if ativo_only:
        stmt = stmt.where(StandardLoad.ativo == True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_load(db: AsyncSession, data: StandardLoadCreate) -> StandardLoad:
    load = StandardLoad(**data.model_dump())
    db.add(load)
    await db.commit()
    await db.refresh(load)
    return load
