import math
from statistics import mean as _mean

import numpy as np

from app.engines.schemas import (
    ArbitrageInput, ArbitrageKitEconomy,
    ArbitrageInputV2, ArbitrageResult,
    BackupInput, BackupResult, LoadRowResult,
    PeakShavingInput, PeakShavingResult,
)

_EFICIENCIA_SISTEMA = 0.9   # round-trip + inversor
_HORAS_PONTA = 3.0          # 18h–21h
_DIAS_UTEIS_MES = 22


def calculate_backup(data: BackupInput) -> BackupResult:
    """
    Replicates CALCULADORA BACKUP.xlsx formulas exactly:
      Pn (kVA)  = ROUNDUP(qtd × (PNOM / FP), 0) / 1000
      Dmn (kVA) = Pn × FD
      Pp (kVA)  = Pn × IP/IN
      DMp (kVA) = Dmn × IP/IN
      E_EPS (kWh) = Pn × TDIA
    Totals via SUBTOTAL (= SUM of non-zero rows).
    """
    if not data.cargas:
        raise ValueError("cargas não pode ser vazia")

    row_results = []
    for row in data.cargas:
        if row.fp <= 0:
            raise ValueError(f"FP inválido para carga: {row.fp}")
        pn_kva   = math.ceil(row.qtd * (row.pnom_w / row.fp)) / 1000
        dmn_kva  = round(pn_kva * row.fd, 4)
        pp_kva   = round(pn_kva * row.ip_in, 4)
        dmp_kva  = round(dmn_kva * row.ip_in, 4)
        e_eps_kwh = round(pn_kva * row.tdia_h, 4)
        row_results.append(LoadRowResult(
            pn_kva=round(pn_kva, 3),
            dmn_kva=round(dmn_kva, 3),
            pp_kva=round(pp_kva, 3),
            dmp_kva=round(dmp_kva, 3),
            e_eps_kwh=round(e_eps_kwh, 3),
        ))

    return BackupResult(
        rows=row_results,
        total_pn=round(sum(r.pn_kva for r in row_results), 3),
        total_dmn=round(sum(r.dmn_kva for r in row_results), 3),
        total_pp=round(sum(r.pp_kva for r in row_results), 3),
        total_dmp=round(sum(r.dmp_kva for r in row_results), 3),
        total_e_eps=round(sum(r.e_eps_kwh for r in row_results), 3),
    )


def calculate_peak_shaving(data: PeakShavingInput) -> PeakShavingResult:
    """
    Calcula energia necessária para cortar o pico até demanda_alvo_kw.
    Estratégia: descarga durante todos os períodos acima do alvo.
    """
    curva = np.array(data.curva_carga_kw)
    pico_atual = float(curva.max())

    if pico_atual <= data.demanda_alvo_kw:
        return PeakShavingResult(
            capacidade_necessaria_kwh=0.0,
            potencia_necessaria_kw=0.0,
            reducao_demanda_kw=0.0,
            economia_mensal_estimada_rs=0.0,
            payback_meses=None,
        )

    reducao_kw = pico_atual - data.demanda_alvo_kw
    excedentes = np.maximum(curva - data.demanda_alvo_kw, 0)
    capacidade_kwh = float(excedentes.max())
    potencia_necessaria_kw = reducao_kw
    economia_mensal = reducao_kw * data.tarifa_demanda_rs_kw

    return PeakShavingResult(
        capacidade_necessaria_kwh=round(capacidade_kwh, 2),
        potencia_necessaria_kw=round(potencia_necessaria_kw, 2),
        reducao_demanda_kw=round(reducao_kw, 2),
        economia_mensal_estimada_rs=round(economia_mensal, 2),
        payback_meses=None,
    )


def calculate_arbitrage_economy(
    data: ArbitrageInput,
    n_baterias: int,
    cap_bateria_kwh: float,
) -> ArbitrageKitEconomy:
    """
    Calcula economia mensal para uma combinação específica de baterias.
    Parâmetros fixos: ponta = 18h–21h (3h), 22 dias úteis/mês.

    Args:
        data:             Dados tarifários e de demanda do cliente.
        n_baterias:       Quantidade de baterias nesta combinação.
        cap_bateria_kwh:  Capacidade nominal de cada bateria (kWh, sem DoD).
    """
    dod = data.dod_percent / 100.0
    energia_arbitrada_dia = n_baterias * cap_bateria_kwh * dod
    potencia_descarga_kw = energia_arbitrada_dia / _HORAS_PONTA

    economia_energia = (
        energia_arbitrada_dia
        * (data.tarifa_ponta_kwh - data.tarifa_fora_ponta_kwh)
        * _DIAS_UTEIS_MES
    )

    economia_demanda = 0.0
    if data.modalidade == "azul" and data.tarifa_demanda_ponta_kw:
        reducao_demanda = min(potencia_descarga_kw, data.demanda_medida_ponta_kw)
        economia_demanda = reducao_demanda * data.tarifa_demanda_ponta_kw

    return ArbitrageKitEconomy(
        energia_arbitrada_dia_kwh=round(energia_arbitrada_dia, 2),
        potencia_descarga_kw=round(potencia_descarga_kw, 2),
        economia_energia_mensal=round(economia_energia, 2),
        economia_demanda_mensal=round(economia_demanda, 2),
        economia_total_mensal=round(economia_energia + economia_demanda, 2),
    )


def calculate_arbitrage_v2(data: ArbitrageInputV2) -> ArbitrageResult:
    """
    Replicates CALCULADORA ARBITRAGEM.xlsx formulas exactly:
      E16 = AVERAGE(E4:E15)  → avg_consumo_ponta
      fator = 22 × cap × (DoD/100) × 0.9
      qty_consumo  = ROUNDUP(E16/22/(cap×dod×0.9), 0) = ceil(avg / fator)
      qty_potencia = ROUNDUP(LARGE(F4:F15, 1) / 100, 0)
      qty_bess     = MAX(qty_consumo, qty_potencia)
      economia     = E16 × (tarifa_ponta - tarifa_fora_ponta)   [I14]
      custo        = qty × preco                                 [I13]
      payback_meses = custo / economia                           [I15]
    """
    avg_consumo = round(_mean(data.consumo_ponta_kwh), 4)
    max_demanda = max(data.demanda_ponta_kw)

    fator = 22.0 * data.bess_capacidade_kwh * (data.bess_dod / 100.0) * 0.9
    qty_consumo  = math.ceil(avg_consumo / fator)
    qty_potencia = math.ceil(max_demanda / 100.0)
    qty_bess     = max(qty_consumo, qty_potencia)

    diff_tarifa     = data.tarifa_ponta_kwh - data.tarifa_fora_ponta_kwh
    economia_mensal = round(avg_consumo * diff_tarifa, 2)
    custo_total     = round(qty_bess * data.bess_preco, 2)

    if economia_mensal > 0:
        payback_meses = round(custo_total / economia_mensal, 1)
    else:
        payback_meses = None

    return ArbitrageResult(
        qty_bess=qty_bess,
        qty_consumo=qty_consumo,
        qty_potencia=qty_potencia,
        avg_consumo_ponta=round(avg_consumo, 2),
        max_demanda_ponta=round(max_demanda, 2),
        economia_mensal=economia_mensal,
        custo_total=custo_total,
        payback_meses=payback_meses,
    )
