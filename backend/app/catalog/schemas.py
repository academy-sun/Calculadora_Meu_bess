import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ProductBESSCreate(BaseModel):
    marca: str
    modelo: str
    sku: str
    tipo: str
    fase: Optional[str] = None
    tensao_nominal_v: Optional[float] = None
    tensao_min_dc_v: Optional[float] = None
    tensao_max_dc_v: Optional[float] = None
    corrente_max_carga_a: Optional[float] = None
    corrente_max_descarga_a: Optional[float] = None
    corrente_max_dc_a: Optional[float] = None
    capacidade_kwh: Optional[float] = None
    dod_percent: Optional[float] = None
    potencia_continua_kw: Optional[float] = None
    pot_ca_max_eps_kva: Optional[float] = None
    mppt_v_min: Optional[float] = None
    mppt_v_max: Optional[float] = None
    mppt_i_max_a: Optional[float] = None
    mppt_qty: Optional[int] = None
    max_baterias: Optional[int] = None
    preco: float
    disponivel: bool = True


class ProductBESSRead(ProductBESSCreate):
    id: uuid.UUID
    atualizado_em: datetime

    model_config = {"from_attributes": True}


class ProductSolarCreate(BaseModel):
    marca: str
    modelo: str
    sku: str
    tipo: str
    potencia_pico_wp: Optional[float] = None
    eficiencia_pct: Optional[float] = None
    voc_v: Optional[float] = None
    vmp_v: Optional[float] = None
    isc_a: Optional[float] = None
    imp_a: Optional[float] = None
    potencia_nominal_kw: Optional[float] = None
    mppt_min_v: Optional[float] = None
    mppt_max_v: Optional[float] = None
    fase: Optional[str] = None
    preco: float
    disponivel: bool = True


class ProductSolarRead(ProductSolarCreate):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class MeuBESSProductRead(BaseModel):
    """Produto da réplica fiel MeuBESS (tabela meubess_products)."""
    meubess_id: str

    # identidade / comercial
    enterprise_id: Optional[str] = None
    title: Optional[str] = None
    original_title: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    suplier_cod: Optional[str] = None
    marca: Optional[str] = None
    brand_id: Optional[str] = None
    brand_title: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_title: Optional[str] = None
    app: Optional[str] = None
    active: Optional[bool] = None
    view: Optional[str] = None
    section: Optional[str] = None
    type: Optional[str] = None
    groups: Optional[str] = None
    availability: Optional[str] = None

    # categoria
    category_id: Optional[str] = None
    category_title: Optional[str] = None
    category_section: Optional[str] = None

    # elétricos / técnicos
    power: Optional[float] = None
    voltage: Optional[str] = None
    phase: Optional[str] = None
    breaker: Optional[str] = None
    battery_inputs: Optional[int] = None
    max_eps_power: Optional[float] = None
    max_output_power: Optional[float] = None
    qty_mppt: Optional[int] = None
    qty_inputs_per_mppt: Optional[int] = None
    voc_max_voltage: Optional[float] = None
    mppt_min_voltage: Optional[float] = None
    output_voltage: Optional[float] = None
    string_current: Optional[float] = None
    short_circuit_current_inverter: Optional[float] = None
    short_circuit_current_module: Optional[float] = None
    max_power_current: Optional[float] = None

    # preço / fiscal / dimensão
    price: Optional[float] = None
    price_sale: Optional[float] = None
    price_sale_until: Optional[str] = None
    ncm: Optional[str] = None
    unt_measure: Optional[str] = None
    unt_multiples: Optional[str] = None
    weight: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    length: Optional[float] = None
    volumes: Optional[float] = None
    fixing_type: Optional[str] = None
    fixing_capacity: Optional[int] = None

    # mídia
    images: Optional[Any] = None

    # dimensionamento de kit (datasheet)
    peak_power_kw: Optional[float] = None
    peak_power_duration_s: Optional[int] = None
    battery_input_max_current_a: Optional[float] = None
    battery_voltage_min_v: Optional[float] = None
    battery_voltage_max_v: Optional[float] = None
    eps_output_voltage: Optional[str] = None
    split_phase: Optional[bool] = None
    max_parallel_units: Optional[int] = None
    usable_capacity_kwh: Optional[float] = None
    nominal_capacity_kwh: Optional[float] = None
    dod_percent: Optional[float] = None
    max_parallel_batteries: Optional[int] = None
    max_continuous_current_a: Optional[float] = None
    peak_discharge_current_a: Optional[float] = None
    nominal_voltage_v: Optional[float] = None
    operating_voltage_min_v: Optional[float] = None
    operating_voltage_max_v: Optional[float] = None
    chemistry: Optional[str] = None
    compatible_inverters: Optional[str] = None

    # classificação / validação
    tipo_auto: Optional[str] = None
    classificacao_confianca: Optional[str] = None
    needs_review: bool = False
    tipo_manual: Optional[str] = None
    overrides_tecnicos: Optional[Any] = None
    validado_por: Optional[str] = None
    validado_em: Optional[datetime] = None

    # origem / compliance
    origem: str = "meubess"
    first_seen_at: datetime
    last_synced_at: datetime

    model_config = {"from_attributes": True}


class MeuBESSProductUpdate(BaseModel):
    """Edição manual / validação de um produto da réplica."""
    tipo_manual: Optional[str] = None
    overrides_tecnicos: Optional[dict] = None
    validado_por: Optional[str] = None
    marcar_validado: bool = True  # se True, limpa needs_review e carimba validado_em

    # dimensionamento de kit (preenchível via datasheet pelo frontend)
    peak_power_kw: Optional[float] = None
    peak_power_duration_s: Optional[int] = None
    battery_input_max_current_a: Optional[float] = None
    battery_voltage_min_v: Optional[float] = None
    battery_voltage_max_v: Optional[float] = None
    eps_output_voltage: Optional[str] = None
    split_phase: Optional[bool] = None
    max_parallel_units: Optional[int] = None
    usable_capacity_kwh: Optional[float] = None
    nominal_capacity_kwh: Optional[float] = None
    dod_percent: Optional[float] = None
    max_parallel_batteries: Optional[int] = None
    max_continuous_current_a: Optional[float] = None
    peak_discharge_current_a: Optional[float] = None
    nominal_voltage_v: Optional[float] = None
    operating_voltage_min_v: Optional[float] = None
    operating_voltage_max_v: Optional[float] = None
    chemistry: Optional[str] = None
    compatible_inverters: Optional[str] = None


# Campos de dimensionamento editáveis (whitelist usada no update)
DIMENSIONAMENTO_FIELDS = (
    "peak_power_kw", "peak_power_duration_s", "battery_input_max_current_a",
    "battery_voltage_min_v", "battery_voltage_max_v", "eps_output_voltage",
    "split_phase", "max_parallel_units", "usable_capacity_kwh", "nominal_capacity_kwh",
    "dod_percent", "max_parallel_batteries", "max_continuous_current_a",
    "peak_discharge_current_a", "nominal_voltage_v", "operating_voltage_min_v",
    "operating_voltage_max_v", "chemistry", "compatible_inverters",
)


class StandardLoadCreate(BaseModel):
    nome: str
    categoria: str
    potencia_w: float
    fator_potencia: float = 1.0
    tdia_horas: Optional[float] = None
    fator_demanda: Optional[float] = None
    ip_in: Optional[float] = None
    tensao: str
    fase: str
    ativo: bool = True


class StandardLoadRead(StandardLoadCreate):
    id: uuid.UUID

    model_config = {"from_attributes": True}
