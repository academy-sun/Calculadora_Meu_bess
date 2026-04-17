from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class OrigemInfo(BaseModel):
    origem: Literal["ploomes", "interno"]
    negocio_id: Optional[str] = None
    negocio_nome: Optional[str] = None
    solicitante_id: str
    solicitante_nome: str
    solicitado_em: datetime


class LoadItem(BaseModel):
    nome: str
    potencia_w: float
    quantidade: int = 1
    horas_uso_dia: float


class CalculateRequest(BaseModel):
    origem_info: OrigemInfo
    tipo_calculo: Literal["backup", "peak_shaving", "arbitragem", "solar", "solar_storage"]

    curva_carga_kw: Optional[list[float]] = None
    cargas: Optional[list[LoadItem]] = None

    potencia_critica_kw: Optional[float] = None
    autonomia_horas: Optional[float] = None
    tensao_instalacao_v: Optional[float] = None
    demanda_alvo_kw: Optional[float] = None
    tarifa_demanda_rs_kw: Optional[float] = None
    horario_ponta_inicio: Optional[int] = None
    horario_ponta_fim: Optional[int] = None
    tarifa_ponta_rs_kwh: Optional[float] = None
    tarifa_fora_ponta_rs_kwh: Optional[float] = None
    irradiacao_kwh_m2_dia: Optional[float] = None
    area_disponivel_m2: Optional[float] = None

    # Backup — DoD informado pelo engenheiro (antes era lido do catálogo)
    dod_percent: Optional[float] = None

    # Arbitragem Tarifária — tarifas e demandas
    modalidade_tarifaria: Optional[Literal["verde", "azul"]] = None
    demanda_medida_ponta_kw: Optional[float] = None
    demanda_medida_fora_ponta_kw: Optional[float] = None
    demanda_contratada_ponta_kw: Optional[float] = None
    demanda_contratada_fora_ponta_kw: Optional[float] = None
    tarifa_demanda_ponta_rs_kw: Optional[float] = None
    tarifa_demanda_fora_ponta_rs_kw: Optional[float] = None
    tarifa_demanda_unica_rs_kw: Optional[float] = None


class KitInfo(BaseModel):
    marca: str
    bateria_modelo: str
    inversor_modelo: str
    qtd_baterias: int
    qtd_inversores: int = 1
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    economia_mensal_rs: Optional[float] = None    # valor econômico (arbitragem)
    payback_anos: Optional[float] = None          # payback em anos (arbitragem)


class CalculateResponse(BaseModel):
    projeto_id: str
    tipo_calculo: str
    origem: str
    negocio_id: Optional[str]
    solicitado_em: datetime
    calculado_em: datetime

    capacidade_kwh: float
    potencia_kw: float

    kit_selecionado: Optional[KitInfo]

    economia_mensal_rs: Optional[float] = None
    economia_anual_rs: Optional[float] = None
    payback_meses: Optional[float] = None

    alternativas: list[KitInfo] = []
