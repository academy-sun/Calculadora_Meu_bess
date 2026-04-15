import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductBESS(Base):
    __tablename__ = "products_bess"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    marca: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    fase: Mapped[str | None] = mapped_column(Text)
    tensao_nominal_v: Mapped[float | None] = mapped_column(Numeric)
    tensao_min_dc_v: Mapped[float | None] = mapped_column(Numeric)
    tensao_max_dc_v: Mapped[float | None] = mapped_column(Numeric)
    corrente_max_carga_a: Mapped[float | None] = mapped_column(Numeric)
    corrente_max_descarga_a: Mapped[float | None] = mapped_column(Numeric)
    corrente_max_dc_a: Mapped[float | None] = mapped_column(Numeric)
    capacidade_kwh: Mapped[float | None] = mapped_column(Numeric)
    dod_percent: Mapped[float | None] = mapped_column(Numeric)
    potencia_continua_kw: Mapped[float | None] = mapped_column(Numeric)
    preco: Mapped[float] = mapped_column(Numeric, nullable=False)
    disponivel: Mapped[bool] = mapped_column(Boolean, default=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ProductSolar(Base):
    __tablename__ = "products_solar"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    marca: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    potencia_pico_wp: Mapped[float | None] = mapped_column(Numeric)
    eficiencia_pct: Mapped[float | None] = mapped_column(Numeric)
    potencia_nominal_kw: Mapped[float | None] = mapped_column(Numeric)
    mppt_min_v: Mapped[float | None] = mapped_column(Numeric)
    mppt_max_v: Mapped[float | None] = mapped_column(Numeric)
    fase: Mapped[str | None] = mapped_column(Text)
    preco: Mapped[float] = mapped_column(Numeric, nullable=False)
    disponivel: Mapped[bool] = mapped_column(Boolean, default=True)


class StandardLoad(Base):
    __tablename__ = "standard_loads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(Text, nullable=False)
    potencia_w: Mapped[float] = mapped_column(Numeric, nullable=False)
    fator_potencia: Mapped[float] = mapped_column(Numeric, default=1.0)
    tensao: Mapped[str] = mapped_column(Text, nullable=False)
    fase: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
