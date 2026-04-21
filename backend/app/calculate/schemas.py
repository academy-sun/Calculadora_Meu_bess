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


# ── Backup load row ───────────────────────────────────────────────────────────

class BackupLoadRow(BaseModel):
    """One row from the backup load table (pre-filled from catalog, user-editable)."""
    nome: str
    qtd: int = 1
    pnom_w: float
    fp: float = 1.0
    fd: float = 1.0
    ip_in: float = 1.0
    tdia_h: float = 4.0


class BackupRowResult(BaseModel):
    nome: str
    pn_kva: float
    dmn_kva: float
    pp_kva: float
    dmp_kva: float
    e_eps_kwh: float


# ── Legacy load item (kept for peak shaving) ─────────────────────────────────

class LoadItem(BaseModel):
    nome: str
    potencia_w: float
    quantidade: int = 1
    horas_uso_dia: float


# ── Request ───────────────────────────────────────────────────────────────────

class CalculateRequest(BaseModel):
    origem_info: OrigemInfo
    tipo_calculo: Literal["backup", "peak_shaving", "arbitragem", "solar", "solar_storage"]

    # ── Backup ────────────────────────────────────────────────────────────────
    cargas_backup: Optional[list[BackupLoadRow]] = None
    tipo_instalacao: Optional[Literal["monofasico", "trifasico"]] = None
    autonomia_horas: Optional[float] = None
    dod_percent: Optional[float] = None
    eficiencia_roundtrip: Optional[float] = None
    tensao_instalacao_v: Optional[float] = None

    # ── Arbitragem ────────────────────────────────────────────────────────────
    consumo_ponta_kwh: Optional[list[float]] = None   # 12 values
    demanda_ponta_kw: Optional[list[float]] = None    # 12 values
    tarifa_ponta_rs_kwh: Optional[float] = None
    tarifa_fora_ponta_rs_kwh: Optional[float] = None

    # ── Peak Shaving ──────────────────────────────────────────────────────────
    curva_carga_kw: Optional[list[float]] = None
    cargas: Optional[list[LoadItem]] = None
    demanda_alvo_kw: Optional[float] = None
    tarifa_demanda_rs_kw: Optional[float] = None

    # ── Solar ─────────────────────────────────────────────────────────────────
    irradiacao_kwh_m2_dia: Optional[float] = None
    area_disponivel_m2: Optional[float] = None


# ── Kit info ──────────────────────────────────────────────────────────────────

class KitInfo(BaseModel):
    marca: str
    bateria_modelo: str
    inversor_modelo: str
    qtd_baterias: int
    qtd_inversores: int = 1
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    economia_mensal_rs: Optional[float] = None
    payback_anos: Optional[float] = None


# ── Response ─────────────────────────────────────────────────────────────────

class CalculateResponse(BaseModel):
    projeto_id: str
    tipo_calculo: str
    origem: str
    negocio_id: Optional[str]
    solicitado_em: datetime
    calculado_em: datetime

    capacidade_kwh: float
    potencia_kw: float

    # Backup-specific
    backup_rows: Optional[list[BackupRowResult]] = None
    total_pn_kva: Optional[float] = None
    total_dmn_kva: Optional[float] = None
    total_pp_kva: Optional[float] = None
    total_dmp_kva: Optional[float] = None

    # Arbitragem-specific
    qty_bess: Optional[int] = None
    qty_consumo: Optional[int] = None
    qty_potencia: Optional[int] = None
    avg_consumo_ponta: Optional[float] = None
    max_demanda_ponta: Optional[float] = None

    kit_selecionado: Optional[KitInfo] = None
    economia_mensal_rs: Optional[float] = None
    economia_anual_rs: Optional[float] = None
    payback_meses: Optional[float] = None
    alternativas: list[KitInfo] = []
