import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    pot_ca_max_eps_kva: Mapped[float | None] = mapped_column(Numeric)
    mppt_v_min: Mapped[float | None] = mapped_column(Numeric)
    mppt_v_max: Mapped[float | None] = mapped_column(Numeric)
    mppt_i_max_a: Mapped[float | None] = mapped_column(Numeric)
    mppt_qty: Mapped[int | None] = mapped_column(Integer)
    max_baterias: Mapped[int | None] = mapped_column(Integer)
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
    voc_v: Mapped[float | None] = mapped_column(Numeric)
    vmp_v: Mapped[float | None] = mapped_column(Numeric)
    isc_a: Mapped[float | None] = mapped_column(Numeric)
    imp_a: Mapped[float | None] = mapped_column(Numeric)
    potencia_nominal_kw: Mapped[float | None] = mapped_column(Numeric)
    mppt_min_v: Mapped[float | None] = mapped_column(Numeric)
    mppt_max_v: Mapped[float | None] = mapped_column(Numeric)
    fase: Mapped[str | None] = mapped_column(Text)
    preco: Mapped[float] = mapped_column(Numeric, nullable=False)
    disponivel: Mapped[bool] = mapped_column(Boolean, default=True)


class MeuBESSProduct(Base):
    """
    Réplica fiel do produto MeuBESS (tabela única raw).

    O sync espelha todos os campos relevantes sem classificar/descartar.
    A classificação é anotação não-destrutiva (tipo_auto + needs_review),
    com override manual (tipo_manual / overrides_tecnicos) preservado entre syncs.
    Datas de compliance (first_seen_at / last_synced_at) são geradas no Supabase.
    """
    __tablename__ = "meubess_products"

    # ── chave (id do produto na MeuBESS; alfanumérico) ──────────────────────
    meubess_id: Mapped[str] = mapped_column(Text, primary_key=True)

    # ── identidade / comercial ──────────────────────────────────────────────
    enterprise_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    original_title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    sku: Mapped[str | None] = mapped_column(Text)
    suplier_cod: Mapped[str | None] = mapped_column(Text)
    marca: Mapped[str | None] = mapped_column(Text)
    brand_id: Mapped[str | None] = mapped_column(Text)
    brand_title: Mapped[str | None] = mapped_column(Text)
    supplier_id: Mapped[str | None] = mapped_column(Text)
    supplier_title: Mapped[str | None] = mapped_column(Text)
    app: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool | None] = mapped_column(Boolean)
    view: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    groups: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str | None] = mapped_column(Text)

    # ── categoria ───────────────────────────────────────────────────────────
    category_id: Mapped[str | None] = mapped_column(Text)
    category_title: Mapped[str | None] = mapped_column(Text)
    category_section: Mapped[str | None] = mapped_column(Text)

    # ── elétricos / técnicos ────────────────────────────────────────────────
    power: Mapped[float | None] = mapped_column(Numeric)
    voltage: Mapped[str | None] = mapped_column(Text)
    phase: Mapped[str | None] = mapped_column(Text)
    breaker: Mapped[str | None] = mapped_column(Text)
    battery_inputs: Mapped[int | None] = mapped_column(Integer)
    max_eps_power: Mapped[float | None] = mapped_column(Numeric)
    max_output_power: Mapped[float | None] = mapped_column(Numeric)
    qty_mppt: Mapped[int | None] = mapped_column(Integer)
    qty_inputs_per_mppt: Mapped[int | None] = mapped_column(Integer)
    voc_max_voltage: Mapped[float | None] = mapped_column(Numeric)
    mppt_min_voltage: Mapped[float | None] = mapped_column(Numeric)
    output_voltage: Mapped[float | None] = mapped_column(Numeric)
    string_current: Mapped[float | None] = mapped_column(Numeric)
    short_circuit_current_inverter: Mapped[float | None] = mapped_column(Numeric)
    short_circuit_current_module: Mapped[float | None] = mapped_column(Numeric)
    max_power_current: Mapped[float | None] = mapped_column(Numeric)

    # ── preço / fiscal / dimensão ───────────────────────────────────────────
    price: Mapped[float | None] = mapped_column(Numeric)
    price_sale: Mapped[float | None] = mapped_column(Numeric)
    price_sale_until: Mapped[str | None] = mapped_column(Text)
    ncm: Mapped[str | None] = mapped_column(Text)
    unt_measure: Mapped[str | None] = mapped_column(Text)
    unt_multiples: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float | None] = mapped_column(Numeric)
    width: Mapped[float | None] = mapped_column(Numeric)
    height: Mapped[float | None] = mapped_column(Numeric)
    length: Mapped[float | None] = mapped_column(Numeric)
    volumes: Mapped[float | None] = mapped_column(Numeric)
    fixing_type: Mapped[str | None] = mapped_column(Text)
    fixing_capacity: Mapped[int | None] = mapped_column(Integer)

    # ── mídia ───────────────────────────────────────────────────────────────
    images: Mapped[Any | None] = mapped_column(JSONB)

    # ── classificação automática (anotação, não filtro) ────────────────────
    tipo_auto: Mapped[str | None] = mapped_column(Text)
    classificacao_confianca: Mapped[str | None] = mapped_column(Text)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── override manual (preservado no upsert) ──────────────────────────────
    tipo_manual: Mapped[str | None] = mapped_column(Text)
    overrides_tecnicos: Mapped[Any | None] = mapped_column(JSONB)
    validado_por: Mapped[str | None] = mapped_column(Text)
    validado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── origem / compliance ─────────────────────────────────────────────────
    origem: Mapped[str] = mapped_column(Text, default="meubess")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class StandardLoad(Base):
    __tablename__ = "standard_loads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(Text, nullable=False)
    potencia_w: Mapped[float] = mapped_column(Numeric, nullable=False)
    fator_potencia: Mapped[float] = mapped_column(Numeric, default=1.0)
    tdia_horas: Mapped[float | None] = mapped_column(Numeric)
    fator_demanda: Mapped[float | None] = mapped_column(Numeric)
    ip_in: Mapped[float | None] = mapped_column(Numeric)
    tensao: Mapped[str] = mapped_column(Text, nullable=False)
    fase: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
