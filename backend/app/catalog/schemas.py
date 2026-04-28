import uuid
from datetime import datetime
from typing import Optional
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
