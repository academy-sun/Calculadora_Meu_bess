import numpy as np

from app.engines.schemas import (
    ArbitrageInput, ArbitrageResult,
    BackupInput, BackupResult,
    PeakShavingInput, PeakShavingResult,
)


def calculate_backup(data: BackupInput, dod_percent: float) -> BackupResult:
    """Capacidade necessária = potência × autonomia ÷ DoD"""
    if dod_percent <= 0:
        raise ValueError("dod_percent deve ser maior que zero")
    dod = dod_percent / 100.0
    capacidade_kwh = data.potencia_critica_kw * data.autonomia_horas / dod
    return BackupResult(
        capacidade_necessaria_kwh=round(capacidade_kwh, 2),
        potencia_necessaria_kw=data.potencia_critica_kw,
        observacoes=f"Autonomia de {data.autonomia_horas}h com DoD {dod_percent}%",
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


def calculate_arbitrage(data: ArbitrageInput) -> ArbitrageResult:
    """
    Carrega na fora-de-ponta, descarrega na ponta.
    Capacidade ótima = energia consumida durante a janela de ponta.
    """
    curva = np.array(data.curva_carga_kw)
    horas = len(curva)

    indices_ponta = [
        i for i in range(horas)
        if data.horario_ponta_inicio <= (i % 24) < data.horario_ponta_fim
    ]

    if not indices_ponta:
        return ArbitrageResult(
            capacidade_otima_kwh=0.0,
            ciclos_dia=0.0,
            economia_anual_estimada_rs=0.0,
            payback_meses=None,
        )

    energia_ponta_dia = float(curva[indices_ponta].sum()) / (horas / 24)
    delta_tarifa = data.tarifa_ponta_rs_kwh - data.tarifa_fora_ponta_rs_kwh
    economia_diaria = energia_ponta_dia * delta_tarifa
    economia_anual = economia_diaria * 365
    ciclos_dia = 1.0
    capacidade_kwh = energia_ponta_dia / ciclos_dia

    return ArbitrageResult(
        capacidade_otima_kwh=round(capacidade_kwh, 2),
        ciclos_dia=ciclos_dia,
        economia_anual_estimada_rs=round(economia_anual, 2),
        payback_meses=None,
    )
