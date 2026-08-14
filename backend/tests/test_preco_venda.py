"""Preço de venda derivado do custo."""

import pytest

from app.engines.kit_attributes import MARGEM_VENDA, preco_venda
from app.engines.kit_builder import build_kits


class _P:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
    def __getattr__(self, _):
        return None


def test_formula_bate_com_o_caso_conferido_na_plataforma():
    """LONGI 635: custo 546,10 na MeuBESS → venda 717,14.

    É margem sobre o PREÇO, não markup sobre o custo: custo × 1,2385 daria
    676,35, que não é o número da plataforma.
    """
    assert preco_venda(_P(cost=546.10)) == 717.14
    assert round(546.10 * (1 + MARGEM_VENDA), 2) != 717.14


def test_price_da_plataforma_e_ignorado():
    """`price` é o 'Preço de Venda Fixo', preenchido à mão e fora da fórmula —
    no LONGI ele traz 600,00 quando o correto são 717,14."""
    assert preco_venda(_P(cost=546.10, price=600.00)) == 717.14


def test_sem_custo_nao_ha_preco():
    assert preco_venda(_P()) is None
    assert preco_venda(_P(cost=None, price=600.00)) is None
    assert preco_venda(_P(cost=0)) is None


def test_override_de_custo_vale_sobre_o_da_plataforma():
    """A camada de decisão humana continua valendo para o custo também."""
    p = _P(cost=546.10, overrides_tecnicos={"cost": 400.0})
    assert preco_venda(p) == round(400.0 / (1 - MARGEM_VENDA), 2)


def _inv(pid, **kw):
    base = dict(meubess_id=pid, title=pid, marca="WEG", peak_power_kw=6.0,
                max_eps_power=5.0, battery_inputs=1, battery_input_max_current_a=40,
                max_parallel_units=5, eps_output_voltage="220", voltage="220",
                battery_voltage_min_v=80, battery_voltage_max_v=480)
    return _P(**{**base, **kw})


def _bat(pid, **kw):
    base = dict(meubess_id=pid, title=pid, marca="WEG", usable_capacity_kwh=10.07,
                max_parallel_batteries=4, max_continuous_current_a=27,
                peak_discharge_current_a=65, nominal_voltage_v=384,
                operating_voltage_min_v=348, operating_voltage_max_v=436.8)
    # sem compatible_inverters: a compatibilidade cai na faixa de tensão
    # (R5), que é o que estes fixtures querem exercitar
    return _P(**{**base, **kw})


def test_produto_sem_custo_e_recusado_com_motivo():
    """Cotar com preço zero seria pior que recusar: o item entraria como o mais
    barato de todos e sumiria do total sem ninguém notar."""
    kits, skipped = build_kits(
        [_inv("sem_custo")], [_bat("b1", cost=1000.0)],
        pn_kva=2.0, pp_kva=4.0, e_bat_kwh=10.0)
    assert kits == []
    assert any("preco" in s.motivo for s in skipped), [s.motivo for s in skipped]


def test_bateria_sem_custo_tambem_e_recusada():
    kits, skipped = build_kits(
        [_inv("i1", cost=5000.0)], [_bat("sem_custo")],
        pn_kva=2.0, pp_kva=4.0, e_bat_kwh=10.0)
    assert kits == []
    assert any("preco" in s.motivo for s in skipped), [s.motivo for s in skipped]


def test_kit_com_custo_cota_pelo_preco_derivado():
    kits, _ = build_kits(
        [_inv("i1", cost=5000.0)], [_bat("b1", cost=1000.0)],
        pn_kva=2.0, pp_kva=4.0, e_bat_kwh=10.0)
    assert kits
    esperado = round(5000 / (1 - MARGEM_VENDA), 2) + round(1000 / (1 - MARGEM_VENDA), 2)
    assert kits[0].preco_total == pytest.approx(esperado, abs=0.02)
