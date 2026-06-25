import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import MeuBESSProduct, ProductBESS, ProductSolar, StandardLoad
from app.catalog.schemas import (
    DIMENSIONAMENTO_FIELDS, MeuBESSProductUpdate,
    ProductBESSCreate, ProductSolarCreate, StandardLoadCreate,
)


# ── meubess_products (réplica fiel) ──────────────────────────────────────────


async def list_products(
    db: AsyncSession,
    *,
    tipo: str | None = None,
    marca: str | None = None,
    app: str | None = None,
    needs_review: bool | None = None,
    titulo: str | None = None,
    potencia_min: float | None = None,
    potencia_max: float | None = None,
    active: bool | None = None,
    synced_from: datetime | None = None,
    synced_to: datetime | None = None,
    seen_from: datetime | None = None,
    seen_to: datetime | None = None,
    limit: int = 2000,
) -> list[MeuBESSProduct]:
    """
    Lista produtos da réplica MeuBESS com filtros opcionais.

    `tipo` filtra pelo tipo efetivo = coalesce(tipo_manual, tipo_auto).
    Potência: só `potencia_min` = "maior que"; só `potencia_max` = "menor que"; ambos = faixa.
    """
    stmt = select(MeuBESSProduct)

    if tipo:
        tipo_efetivo = func.coalesce(MeuBESSProduct.tipo_manual, MeuBESSProduct.tipo_auto)
        stmt = stmt.where(tipo_efetivo == tipo)
    if marca:
        stmt = stmt.where(func.lower(MeuBESSProduct.marca).like(f"%{marca.lower()}%"))
    if app:
        stmt = stmt.where(MeuBESSProduct.app.like(f"%{app}%"))
    if needs_review is not None:
        stmt = stmt.where(MeuBESSProduct.needs_review == needs_review)
    if titulo:
        stmt = stmt.where(func.lower(MeuBESSProduct.title).like(f"%{titulo.lower()}%"))
    if potencia_min is not None:
        stmt = stmt.where(MeuBESSProduct.power >= potencia_min)
    if potencia_max is not None:
        stmt = stmt.where(MeuBESSProduct.power <= potencia_max)
    if active is not None:
        stmt = stmt.where(MeuBESSProduct.active == active)
    if synced_from is not None:
        stmt = stmt.where(MeuBESSProduct.last_synced_at >= synced_from)
    if synced_to is not None:
        stmt = stmt.where(MeuBESSProduct.last_synced_at <= synced_to)
    if seen_from is not None:
        stmt = stmt.where(MeuBESSProduct.first_seen_at >= seen_from)
    if seen_to is not None:
        stmt = stmt.where(MeuBESSProduct.first_seen_at <= seen_to)

    stmt = stmt.order_by(MeuBESSProduct.title).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_kit_products(
    db: AsyncSession,
) -> tuple[list[MeuBESSProduct], list[MeuBESSProduct]]:
    """
    Retorna (inversores_hibridos, baterias) ativos da réplica para montar kit,
    pelo tipo efetivo = coalesce(tipo_manual, tipo_auto).
    """
    inversores = await list_products(db, tipo="inversor_hibrido", active=True)
    baterias = await list_products(db, tipo="bateria", active=True)
    return inversores, baterias


async def get_product(db: AsyncSession, meubess_id: str) -> MeuBESSProduct | None:
    result = await db.execute(
        select(MeuBESSProduct).where(MeuBESSProduct.meubess_id == meubess_id)
    )
    return result.scalar_one_or_none()


async def update_product(
    db: AsyncSession, meubess_id: str, data: MeuBESSProductUpdate
) -> MeuBESSProduct | None:
    """Aplica edição manual / validação, preservando os campos não informados."""
    product = await get_product(db, meubess_id)
    if not product:
        return None

    # Só aplica campos efetivamente enviados (exclude_unset) — permite zerar via null.
    provided = data.model_dump(exclude_unset=True)

    if "tipo_manual" in provided:
        product.tipo_manual = data.tipo_manual
    if "overrides_tecnicos" in provided:
        product.overrides_tecnicos = data.overrides_tecnicos
    if "validado_por" in provided:
        product.validado_por = data.validado_por

    # Campos de dimensionamento (datasheet)
    for field in DIMENSIONAMENTO_FIELDS:
        if field in provided:
            setattr(product, field, provided[field])

    if data.marcar_validado:
        product.needs_review = False
        product.validado_em = datetime.utcnow()

    await db.commit()
    await db.refresh(product)
    return product


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


async def update_solar(db: AsyncSession, product_id: uuid.UUID, data: ProductSolarCreate) -> ProductSolar | None:
    result = await db.execute(select(ProductSolar).where(ProductSolar.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return None
    for key, value in data.model_dump().items():
        setattr(product, key, value)
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


async def update_load(db: AsyncSession, load_id: uuid.UUID, data: StandardLoadCreate) -> StandardLoad | None:
    result = await db.execute(select(StandardLoad).where(StandardLoad.id == load_id))
    load = result.scalar_one_or_none()
    if not load:
        return None
    for key, value in data.model_dump().items():
        setattr(load, key, value)
    await db.commit()
    await db.refresh(load)
    return load


async def delete_bess(db: AsyncSession, product_id: uuid.UUID) -> bool:
    product = await get_bess_by_id(db, product_id)
    if not product:
        return False
    await db.delete(product)
    await db.commit()
    return True


async def delete_solar(db: AsyncSession, product_id: uuid.UUID) -> bool:
    result = await db.execute(select(ProductSolar).where(ProductSolar.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return False
    await db.delete(product)
    await db.commit()
    return True


async def delete_load(db: AsyncSession, load_id: uuid.UUID) -> bool:
    result = await db.execute(select(StandardLoad).where(StandardLoad.id == load_id))
    load = result.scalar_one_or_none()
    if not load:
        return False
    await db.delete(load)
    await db.commit()
    return True


async def get_bess_comercial(db: AsyncSession) -> MeuBESSProduct | None:
    """
    Unidade BESS comercial usada pela Arbitragem, da réplica (origem='manual',
    tipo efetivo='bess_comercial'). Retorna None se nenhuma estiver cadastrada.
    """
    tipo_efetivo = func.coalesce(MeuBESSProduct.tipo_manual, MeuBESSProduct.tipo_auto)
    result = await db.execute(
        select(MeuBESSProduct).where(tipo_efetivo == "bess_comercial").limit(1)
    )
    return result.scalar_one_or_none()
