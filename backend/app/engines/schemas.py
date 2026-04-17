# Minimal schemas without pydantic dependency
from typing import Optional
import uuid
from datetime import datetime


# ProductBESSRead for compatibility (simple version)
class ProductBESSRead:
    def __init__(self, id=None, marca=None, modelo=None, sku=None, tipo=None,
                 tensao_nominal_v=None, capacidade_kwh=None, dod_percent=None,
                 corrente_max_descarga_a=None, tensao_min_dc_v=None,
                 tensao_max_dc_v=None, corrente_max_dc_a=None,
                 potencia_continua_kw=None, preco=0.0, disponivel=True,
                 atualizado_em=None, max_baterias=None):
        self.id = id or uuid.uuid4()
        self.marca = marca
        self.modelo = modelo
        self.sku = sku
        self.tipo = tipo
        self.tensao_nominal_v = tensao_nominal_v
        self.capacidade_kwh = capacidade_kwh
        self.dod_percent = dod_percent
        self.corrente_max_descarga_a = corrente_max_descarga_a
        self.tensao_min_dc_v = tensao_min_dc_v
        self.tensao_max_dc_v = tensao_max_dc_v
        self.corrente_max_dc_a = corrente_max_dc_a
        self.potencia_continua_kw = potencia_continua_kw
        self.preco = preco
        self.disponivel = disponivel
        self.atualizado_em = atualizado_em or datetime.utcnow()
        self.max_baterias = max_baterias


class CargaItem:
    """Uma carga crítica com potência (kW) e tempo de uso diário (h/dia)."""
    def __init__(self, potencia_kw: float, tdia_horas: float):
        self.potencia_kw = potencia_kw
        self.tdia_horas = tdia_horas


class BackupInput:
    def __init__(
        self,
        cargas: list,             # list[CargaItem]
        autonomia_horas: float,   # duração do backup desejada (h)
        dod_percent: float,       # ex: 80 → usado como 0.80
        tensao_instalacao_v: float,
    ):
        self.cargas = cargas
        self.autonomia_horas = autonomia_horas
        self.dod_percent = dod_percent
        self.tensao_instalacao_v = tensao_instalacao_v


class PeakShavingInput:
    def __init__(self, curva_carga_kw: list[float], demanda_alvo_kw: float, tarifa_demanda_rs_kw: float):
        self.curva_carga_kw = curva_carga_kw
        self.demanda_alvo_kw = demanda_alvo_kw
        self.tarifa_demanda_rs_kw = tarifa_demanda_rs_kw


class ArbitrageInput:
    def __init__(
        self,
        modalidade: str,                          # "verde" ou "azul"
        tarifa_ponta_kwh: float,                  # R$/kWh
        tarifa_fora_ponta_kwh: float,             # R$/kWh
        demanda_medida_ponta_kw: float,           # kW medido hoje na ponta
        demanda_medida_fora_ponta_kw: float,
        demanda_contratada_ponta_kw: float,
        demanda_contratada_fora_ponta_kw: float,
        tarifa_demanda_ponta_kw,                  # R$/kW (Azul) ou None
        tarifa_demanda_fora_ponta_kw,             # R$/kW (Azul) ou None
        tarifa_demanda_unica_kw,                  # R$/kW (Verde) ou None
        dod_percent: float,
        tensao_instalacao_v: float,
    ):
        self.modalidade = modalidade.lower()
        self.tarifa_ponta_kwh = tarifa_ponta_kwh
        self.tarifa_fora_ponta_kwh = tarifa_fora_ponta_kwh
        self.demanda_medida_ponta_kw = demanda_medida_ponta_kw
        self.demanda_medida_fora_ponta_kw = demanda_medida_fora_ponta_kw
        self.demanda_contratada_ponta_kw = demanda_contratada_ponta_kw
        self.demanda_contratada_fora_ponta_kw = demanda_contratada_fora_ponta_kw
        self.tarifa_demanda_ponta_kw = tarifa_demanda_ponta_kw
        self.tarifa_demanda_fora_ponta_kw = tarifa_demanda_fora_ponta_kw
        self.tarifa_demanda_unica_kw = tarifa_demanda_unica_kw
        self.dod_percent = dod_percent
        self.tensao_instalacao_v = tensao_instalacao_v


class SolarInput:
    def __init__(self, consumo_medio_mensal_kwh: float, irradiacao_kwh_m2_dia: float, area_disponivel_m2: float):
        self.consumo_medio_mensal_kwh = consumo_medio_mensal_kwh
        self.irradiacao_kwh_m2_dia = irradiacao_kwh_m2_dia
        self.area_disponivel_m2 = area_disponivel_m2


# ── Outputs ──────────────────────────────────────────────────────────────────

class BackupResult:
    def __init__(self, capacidade_kwh: float, energia_necessaria_kwh: float):
        # capacidade_kwh     = Σ(Pp_i × TDIA_i)
        # energia_necessaria = capacidade × (autonomia/24) / DoD / 0.9
        self.capacidade_kwh = capacidade_kwh
        self.energia_necessaria_kwh = energia_necessaria_kwh


class PeakShavingResult:
    def __init__(self, capacidade_necessaria_kwh: float, potencia_necessaria_kw: float, reducao_demanda_kw: float,
                 economia_mensal_estimada_rs: float, payback_meses: Optional[float]):
        self.capacidade_necessaria_kwh = capacidade_necessaria_kwh
        self.potencia_necessaria_kw = potencia_necessaria_kw
        self.reducao_demanda_kw = reducao_demanda_kw
        self.economia_mensal_estimada_rs = economia_mensal_estimada_rs
        self.payback_meses = payback_meses


class ArbitrageKitEconomy:
    """Resultado econômico para uma combinação específica (bateria, n_baterias)."""
    def __init__(
        self,
        energia_arbitrada_dia_kwh: float,
        potencia_descarga_kw: float,
        economia_energia_mensal: float,
        economia_demanda_mensal: float,
        economia_total_mensal: float,
    ):
        self.energia_arbitrada_dia_kwh = energia_arbitrada_dia_kwh
        self.potencia_descarga_kw = potencia_descarga_kw
        self.economia_energia_mensal = economia_energia_mensal
        self.economia_demanda_mensal = economia_demanda_mensal
        self.economia_total_mensal = economia_total_mensal


class SolarResult:
    def __init__(self, potencia_pico_kwp: float, quantidade_modulos: int, potencia_inversor_kw: float,
                 geracao_anual_estimada_kwh: float):
        self.potencia_pico_kwp = potencia_pico_kwp
        self.quantidade_modulos = quantidade_modulos
        self.potencia_inversor_kw = potencia_inversor_kw
        self.geracao_anual_estimada_kwh = geracao_anual_estimada_kwh
