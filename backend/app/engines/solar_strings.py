# backend/app/engines/solar_strings.py
import math
from typing import Optional

from app.engines.schemas import SolarStringsInput, SolarStringsResult

EFICIENCIA_SISTEMA = 0.8
DIAS_MES = 30


def _kwp_necessario(consumo_mensal: float, hsp: float) -> float:
    return consumo_mensal / (hsp * EFICIENCIA_SISTEMA * DIAS_MES)


def _size_module(inversor, modulo, kwp_necessario: float) -> Optional[SolarStringsResult]:
    mppt_v_min = getattr(inversor, 'mppt_v_min', None)
    mppt_v_max = getattr(inversor, 'mppt_v_max', None)
    mppt_i_max_a = getattr(inversor, 'mppt_i_max_a', None)
    mppt_qty = getattr(inversor, 'mppt_qty', None)
    voc_v = getattr(modulo, 'voc_v', None)
    vmp_v = getattr(modulo, 'vmp_v', None)
    imp_a = getattr(modulo, 'imp_a', None)
    wp = getattr(modulo, 'potencia_pico_wp', None)

    if any(v is None for v in [mppt_v_min, mppt_v_max, mppt_i_max_a, mppt_qty,
                                voc_v, vmp_v, imp_a, wp]):
        return None

    mppt_v_min = float(mppt_v_min)
    mppt_v_max = float(mppt_v_max)
    mppt_i_max_a = float(mppt_i_max_a)
    mppt_qty = int(mppt_qty)
    voc_v = float(voc_v)
    vmp_v = float(vmp_v)
    imp_a = float(imp_a)
    wp = float(wp)

    if vmp_v <= 0 or voc_v <= 0 or imp_a <= 0 or wp <= 0:
        return None

    n_serie_min = math.ceil(mppt_v_min / vmp_v)
    n_serie_max = math.floor(mppt_v_max / voc_v)

    if n_serie_min > n_serie_max or n_serie_max < 1:
        return None

    n_serie = n_serie_max
    n_paralelo_max = math.floor(mppt_i_max_a / imp_a)
    if n_paralelo_max < 1:
        return None

    n_strings_necessarias = math.ceil(kwp_necessario * 1000 / (n_serie * wp))
    n_paralelo = math.ceil(n_strings_necessarias / mppt_qty)
    n_paralelo = min(n_paralelo, n_paralelo_max)

    qty_modulos = n_serie * n_paralelo * mppt_qty
    kwp_instalado = round(qty_modulos * wp / 1000, 3)
    cobertura_pct = round(min(kwp_instalado / kwp_necessario * 100, 999.9), 1)

    return SolarStringsResult(
        modulo_marca=str(modulo.marca),
        modulo_modelo=str(modulo.modelo),
        modulo_wp=wp,
        qty_modulos=qty_modulos,
        n_serie=n_serie,
        n_paralelo=n_paralelo,
        mppt_qty=mppt_qty,
        kwp_instalado=kwp_instalado,
        cobertura_pct=cobertura_pct,
    )


def size_solar_strings(
    inversor,
    modulos: list,
    solar_input: SolarStringsInput,
) -> Optional[SolarStringsResult]:
    """
    Seleciona o melhor módulo FV e retorna configuração ótima de strings.
    Retorna None se nenhum módulo for compatível ou inversor sem dados MPPT.
    """
    kwp_nec = _kwp_necessario(
        solar_input.consumo_medio_mensal_kwh,
        solar_input.hsp_media,
    )

    candidatos = []
    for modulo in modulos:
        if not getattr(modulo, 'disponivel', True):
            continue
        result = _size_module(inversor, modulo, kwp_nec)
        if result is not None:
            candidatos.append((modulo, result))

    if not candidatos:
        return None

    def score(item):
        modulo, r = item
        penalty = 0 if r.kwp_instalado <= kwp_nec * 1.2 else 1000
        distance = abs(r.kwp_instalado - kwp_nec)
        preco_total = float(modulo.preco) * r.qty_modulos if modulo.preco else float('inf')
        return (penalty, distance, preco_total)

    candidatos.sort(key=score)
    return candidatos[0][1]
