# backend/app/engines/solar_strings.py
import math
from typing import Optional

from app.engines.kit_attributes import eff, eff_float, preco_venda
from app.engines.schemas import SolarStringsInput, SolarStringsResult

EFICIENCIA_SISTEMA = 0.8
DIAS_MES = 30


def _kwp_necessario(consumo_mensal: float, hsp: float) -> float:
    return consumo_mensal / (hsp * EFICIENCIA_SISTEMA * DIAS_MES)


def _size_module(inversor, modulo, kwp_necessario: float) -> Optional[SolarStringsResult]:
    # Atributos lidos da réplica meubess_products (via valor efetivo):
    #   inversor: tensão máx PV (voc_max_voltage), corrente de string, nº MPPT
    #   módulo:   Voc, Imp, potência (kW → Wp)
    # Vmp do módulo não existe na réplica → restrição de tensão mínima é opcional.
    mppt_v_min   = eff_float(inversor, 'mppt_min_voltage')
    mppt_v_max   = eff_float(inversor, 'voc_max_voltage')
    mppt_i_max_a = eff_float(inversor, 'string_current')
    mppt_qty     = eff(inversor, 'qty_mppt')
    voc_v = eff_float(modulo, 'voc_max_voltage')
    vmp_v = eff_float(modulo, 'vmp_v')  # opcional (ausente na réplica)
    imp_a = eff_float(modulo, 'max_power_current')
    power_kw = eff_float(modulo, 'power')
    wp = power_kw * 1000 if power_kw else None

    # Obrigatórios (Vmp e mppt_v_min são opcionais → restrição mín. relaxada)
    if any(v is None for v in [mppt_v_max, mppt_i_max_a, mppt_qty, voc_v, imp_a, wp]):
        return None

    mppt_v_max = float(mppt_v_max)
    mppt_i_max_a = float(mppt_i_max_a)
    mppt_qty = int(mppt_qty)
    voc_v = float(voc_v)
    imp_a = float(imp_a)
    wp = float(wp)

    if voc_v <= 0 or imp_a <= 0 or wp <= 0:
        return None

    n_serie_max = math.floor(mppt_v_max / voc_v)
    if n_serie_max < 1:
        return None

    # Restrição de tensão mínima só quando há mppt_v_min E Vmp do módulo.
    n_serie_min = math.ceil(mppt_v_min / vmp_v) if (mppt_v_min and vmp_v) else 1
    if n_serie_min > n_serie_max:
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

    # Mesmo preço do resto do motor: derivado do custo, não o 'price' do
    # cadastro (ver kit_attributes.preco_venda).
    preco_mod = preco_venda(modulo)
    preco_modulos_total = round(preco_mod * qty_modulos, 2) if preco_mod else 0.0

    return SolarStringsResult(
        modulo_marca=str(eff(modulo, 'marca') or '—'),
        modulo_modelo=str(eff(modulo, 'title') or eff(modulo, 'meubess_id') or ''),
        modulo_wp=wp,
        qty_modulos=qty_modulos,
        n_serie=n_serie,
        n_paralelo=n_paralelo,
        mppt_qty=mppt_qty,
        kwp_instalado=kwp_instalado,
        cobertura_pct=cobertura_pct,
        preco_modulos_total=preco_modulos_total,
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
        if eff(modulo, 'active') is False:
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
        preco_mod = preco_venda(modulo)
        preco_total = preco_mod * r.qty_modulos if preco_mod else float('inf')
        return (penalty, distance, preco_total)

    candidatos.sort(key=score)
    return candidatos[0][1]
