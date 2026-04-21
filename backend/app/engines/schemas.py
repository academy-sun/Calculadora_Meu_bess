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


class LoadRow:
    """Uma linha da tabela de cargas do formulário Backup."""
    def __init__(
        self,
        qtd: int,
        pnom_w: float,
        fp: float,     # fator de potência
        fd: float,     # fator de demanda
        ip_in: float,  # relação corrente de partida / nominal
        tdia_h: float, # horas de uso por dia (Backup scenario)
    ):
        self.qtd = qtd
        self.pnom_w = pnom_w
        self.fp = fp
        self.fd = fd
        self.ip_in = ip_in
        self.tdia_h = tdia_h


class LoadRowResult:
    """Resultado calculado para uma linha da tabela de cargas."""
    def __init__(
        self,
        pn_kva: float,
        dmn_kva: float,
        pp_kva: float,
        dmp_kva: float,
        e_eps_kwh: float,
    ):
        self.pn_kva = pn_kva
        self.dmn_kva = dmn_kva
        self.pp_kva = pp_kva
        self.dmp_kva = dmp_kva
        self.e_eps_kwh = e_eps_kwh


class BackupInput:
    def __init__(
        self,
        cargas: list,               # list[LoadRow]
        tipo_instalacao: str,       # "monofasico" | "trifasico"
        autonomia_h: float = 4.0,   # for record; not used in E_EPS formula
        dod_percent: float = 90.0,  # 0-100; used in kit selection
        eficiencia_roundtrip: float = 90.0,  # for record
    ):
        self.cargas = cargas
        self.tipo_instalacao = tipo_instalacao
        self.autonomia_h = autonomia_h
        self.dod_percent = dod_percent
        self.eficiencia_roundtrip = eficiencia_roundtrip


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
    def __init__(
        self,
        rows: list,           # list[LoadRowResult]
        total_pn: float,
        total_dmn: float,
        total_pp: float,
        total_dmp: float,
        total_e_eps: float,
    ):
        self.rows = rows
        self.total_pn = total_pn
        self.total_dmn = total_dmn
        self.total_pp = total_pp
        self.total_dmp = total_dmp
        self.total_e_eps = total_e_eps


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


class ArbitrageInputV2:
    """
    Input para o novo motor de Arbitragem (baseado na planilha CALCULADORA ARBITRAGEM.xlsx).
    Substitui ArbitrageInput (tarifa-baseada) para o fluxo de Arbitragem Tarifária.
    """
    def __init__(
        self,
        consumo_ponta_kwh: list,      # 12 valores mensais (E4:E15)
        demanda_ponta_kw: list,        # 12 valores mensais (F4:F15)
        tarifa_ponta_kwh: float,       # I4
        tarifa_fora_ponta_kwh: float,  # I3
        bess_capacidade_kwh: float,    # capacidade nominal do BESS comercial
        bess_dod: float,               # DoD em 0-100, e.g. 90
        bess_preco: float,             # preço unitário R$
    ):
        if len(consumo_ponta_kwh) != 12:
            raise ValueError("consumo_ponta_kwh deve ter 12 valores")
        if len(demanda_ponta_kw) != 12:
            raise ValueError("demanda_ponta_kw deve ter 12 valores")
        self.consumo_ponta_kwh = consumo_ponta_kwh
        self.demanda_ponta_kw = demanda_ponta_kw
        self.tarifa_ponta_kwh = tarifa_ponta_kwh
        self.tarifa_fora_ponta_kwh = tarifa_fora_ponta_kwh
        self.bess_capacidade_kwh = bess_capacidade_kwh
        self.bess_dod = bess_dod
        self.bess_preco = bess_preco


class ArbitrageResult:
    def __init__(
        self,
        qty_bess: int,
        qty_consumo: int,
        qty_potencia: int,
        avg_consumo_ponta: float,
        max_demanda_ponta: float,
        economia_mensal: float,
        custo_total: float,
        payback_meses,
    ):
        self.qty_bess = qty_bess
        self.qty_consumo = qty_consumo
        self.qty_potencia = qty_potencia
        self.avg_consumo_ponta = avg_consumo_ponta
        self.max_demanda_ponta = max_demanda_ponta
        self.economia_mensal = economia_mensal
        self.custo_total = custo_total
        self.payback_meses = payback_meses
