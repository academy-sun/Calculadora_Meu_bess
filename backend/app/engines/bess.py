import numpy as np

from app.engines.schemas import (
    ArbitrageInput, ArbitrageKitEconomy,
    BackupInput, BackupResult,
    PeakShavingInput, PeakShavingResult,
)

_EFICIENCIA_SISTEMA = 0.9   # round-trip + inversor
_HORAS_PONTA = 3.0          # 18h–21h
_DIAS_UTEIS_MES = 22


def calculate_backup(data: BackupInput) -> BackupResult:
    """
    Capacidade (kWh)      = Σ(Pp_i × TDIA_i)
    Energia Necessária    = Capacidade × (Autonomia / 24) / DoD / 0.9
    """
    if data.dod_percent <= 0:
        raise ValueError("dod_percent deve ser maior que zero")
    if not data.cargas:
        raise ValueError("cargas não pode ser vazia")

    dod = data.dod_percent / 100.0
    capacidade_kwh = sum(c.potencia_kw * c.tdia_horas for c in data.cargas)
    energia_necessaria_kwh = (
        capacidade_kwh * (data.autonomia_horas / 24.0) / dod / _EFICIENCIA_SISTEMA
    )

    return BackupResult(
        capacidade_kwh=round(capacidade_kwh, 2),
        energia_necessaria_kwh=round(energia_necessaria_kwh, 2),
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
