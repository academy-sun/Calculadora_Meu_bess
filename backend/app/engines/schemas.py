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
                 atualizado_em=None):
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


class BackupInput:
    def __init__(self, potencia_critica_kw: float, autonomia_horas: float, tensao_instalacao_v: float):
        self.potencia_critica_kw = potencia_critica_kw
        self.autonomia_horas = autonomia_horas
        self.tensao_instalacao_v = tensao_instalacao_v


class PeakShavingInput:
    def __init__(self, curva_carga_kw: list[float], demanda_alvo_kw: float, tarifa_demanda_rs_kw: float):
        self.curva_carga_kw = curva_carga_kw
        self.demanda_alvo_kw = demanda_alvo_kw
        self.tarifa_demanda_rs_kw = tarifa_demanda_rs_kw


class ArbitrageInput:
    def __init__(self, curva_carga_kw: list[float], horario_ponta_inicio: int, horario_ponta_fim: int,
                 tarifa_ponta_rs_kwh: float, tarifa_fora_ponta_rs_kwh: float):
        self.curva_carga_kw = curva_carga_kw
        self.horario_ponta_inicio = horario_ponta_inicio
        self.horario_ponta_fim = horario_ponta_fim
        self.tarifa_ponta_rs_kwh = tarifa_ponta_rs_kwh
        self.tarifa_fora_ponta_rs_kwh = tarifa_fora_ponta_rs_kwh


class SolarInput:
    def __init__(self, consumo_medio_mensal_kwh: float, irradiacao_kwh_m2_dia: float, area_disponivel_m2: float):
        self.consumo_medio_mensal_kwh = consumo_medio_mensal_kwh
        self.irradiacao_kwh_m2_dia = irradiacao_kwh_m2_dia
        self.area_disponivel_m2 = area_disponivel_m2


# ── Outputs ──────────────────────────────────────────────────────────────────

class BackupResult:
    def __init__(self, capacidade_necessaria_kwh: float, potencia_necessaria_kw: float, observacoes: str):
        self.capacidade_necessaria_kwh = capacidade_necessaria_kwh
        self.potencia_necessaria_kw = potencia_necessaria_kw
        self.observacoes = observacoes


class PeakShavingResult:
    def __init__(self, capacidade_necessaria_kwh: float, potencia_necessaria_kw: float, reducao_demanda_kw: float,
                 economia_mensal_estimada_rs: float, payback_meses: Optional[float]):
        self.capacidade_necessaria_kwh = capacidade_necessaria_kwh
        self.potencia_necessaria_kw = potencia_necessaria_kw
        self.reducao_demanda_kw = reducao_demanda_kw
        self.economia_mensal_estimada_rs = economia_mensal_estimada_rs
        self.payback_meses = payback_meses


class ArbitrageResult:
    def __init__(self, capacidade_otima_kwh: float, ciclos_dia: float, economia_anual_estimada_rs: float,
                 payback_meses: Optional[float]):
        self.capacidade_otima_kwh = capacidade_otima_kwh
        self.ciclos_dia = ciclos_dia
        self.economia_anual_estimada_rs = economia_anual_estimada_rs
        self.payback_meses = payback_meses


class SolarResult:
    def __init__(self, potencia_pico_kwp: float, quantidade_modulos: int, potencia_inversor_kw: float,
                 geracao_anual_estimada_kwh: float):
        self.potencia_pico_kwp = potencia_pico_kwp
        self.quantidade_modulos = quantidade_modulos
        self.potencia_inversor_kw = potencia_inversor_kw
        self.geracao_anual_estimada_kwh = geracao_anual_estimada_kwh
