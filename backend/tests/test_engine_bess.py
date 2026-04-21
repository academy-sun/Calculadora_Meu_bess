import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import unittest
try:
    import pytest
except ImportError:
    pytest = None  # type: ignore

from app.engines.bess import (
    calculate_backup, calculate_peak_shaving, calculate_arbitrage_economy, calculate_arbitrage_v2,
)
from app.engines.schemas import BackupInput, LoadRow, PeakShavingInput, ArbitrageInput, ArbitrageInputV2


# Minimal approx helper for when pytest is not installed
class _Approx:
    def __init__(self, expected, abs=1e-3):
        self.expected = expected
        self.abs = abs
    def __eq__(self, actual):
        return abs(actual - self.expected) <= self.abs

def _approx(expected, abs=1e-3):
    return _Approx(expected, abs)


class TestBackup(unittest.TestCase):
    """Tests verified against CALCULADORA BACKUP.xlsx formulas."""

    def _make_input(self, cargas, tipo="monofasico"):
        return BackupInput(cargas=cargas, tipo_instalacao=tipo, dod_percent=90)

    def test_single_load_ar_condicionado(self):
        """AR CONDICIONADO BTU 7500: qty=1, PNOM=800W, FP=0.75, FD=1, IP/IN=6, TDIA=6h"""
        cargas = [LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=6.0, tdia_h=6.0)]
        result = calculate_backup(self._make_input(cargas))

        self.assertAlmostEqual(result.rows[0].pn_kva, 1.067, places=3)
        self.assertAlmostEqual(result.rows[0].dmn_kva, 1.067, places=3)
        self.assertAlmostEqual(result.rows[0].pp_kva, 6.402, places=3)
        self.assertAlmostEqual(result.rows[0].dmp_kva, 6.402, places=3)
        self.assertAlmostEqual(result.rows[0].e_eps_kwh, 6.402, places=3)

    def test_single_load_abajur(self):
        """ABAJUR 45W INCAND: qty=2, PNOM=45W, FP=1.0, FD=0.9, IP/IN=1.0, TDIA=5h"""
        cargas = [LoadRow(qtd=2, pnom_w=45, fp=1.0, fd=0.9, ip_in=1.0, tdia_h=5.0)]
        result = calculate_backup(self._make_input(cargas))

        self.assertAlmostEqual(result.rows[0].pn_kva, 0.09, places=3)
        self.assertAlmostEqual(result.rows[0].dmn_kva, 0.081, places=3)
        self.assertAlmostEqual(result.rows[0].pp_kva, 0.09, places=3)
        self.assertAlmostEqual(result.rows[0].dmp_kva, 0.081, places=3)
        self.assertAlmostEqual(result.rows[0].e_eps_kwh, 0.45, places=3)

    def test_multiple_loads_totals(self):
        """Two loads: verify SUBTOTAL sums."""
        cargas = [
            LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=6.0, tdia_h=6.0),
            LoadRow(qtd=2, pnom_w=45,  fp=1.0,  fd=0.9, ip_in=1.0, tdia_h=5.0),
        ]
        result = calculate_backup(self._make_input(cargas))

        self.assertEqual(len(result.rows), 2)
        self.assertAlmostEqual(result.total_pn, 1.157, places=3)
        self.assertAlmostEqual(result.total_dmn, 1.148, places=3)
        self.assertAlmostEqual(result.total_pp, 6.492, places=3)
        self.assertAlmostEqual(result.total_dmp, 6.483, places=3)
        self.assertAlmostEqual(result.total_e_eps, 6.852, places=3)

    def test_roundup_behavior(self):
        """ROUNDUP is ceil for positive: ceil(800/0.75) = ceil(1066.67) = 1067"""
        cargas = [LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=1.0, tdia_h=1.0)]
        result = calculate_backup(self._make_input(cargas))
        self.assertAlmostEqual(result.rows[0].pn_kva, 1.067, places=3)

    def test_raises_on_empty_cargas(self):
        with self.assertRaises(ValueError):
            calculate_backup(BackupInput(cargas=[], tipo_instalacao="monofasico"))


class TestPeakShaving(unittest.TestCase):

    def test_peak_shaving_basic(self):
        """Curva com pico de 100 kW, alvo 80 kW → redução de 20 kW"""
        curva = [50.0] * 23 + [100.0]
        result = calculate_peak_shaving(PeakShavingInput(
            curva_carga_kw=curva,
            demanda_alvo_kw=80.0,
            tarifa_demanda_rs_kw=50.0,
        ))
        self.assertAlmostEqual(result.reducao_demanda_kw, 20.0, places=1)
        self.assertGreater(result.capacidade_necessaria_kwh, 0)
        self.assertEqual(result.economia_mensal_estimada_rs, 20.0 * 50.0)

    def test_peak_shaving_no_reduction_needed(self):
        """Pico já abaixo do alvo → redução = 0"""
        curva = [50.0] * 24
        result = calculate_peak_shaving(PeakShavingInput(
            curva_carga_kw=curva,
            demanda_alvo_kw=80.0,
            tarifa_demanda_rs_kw=50.0,
        ))
        self.assertEqual(result.reducao_demanda_kw, 0.0)
        self.assertEqual(result.capacidade_necessaria_kwh, 0.0)
        self.assertEqual(result.economia_mensal_estimada_rs, 0.0)

    def test_peak_shaving_multiple_peaks(self):
        """Múltiplos picos — capacidade = maior excedente em uma hora"""
        curva = [90.0] * 3 + [50.0] * 21
        result = calculate_peak_shaving(PeakShavingInput(
            curva_carga_kw=curva,
            demanda_alvo_kw=80.0,
            tarifa_demanda_rs_kw=30.0,
        ))
        self.assertAlmostEqual(result.reducao_demanda_kw, 10.0, places=1)
        self.assertAlmostEqual(result.capacidade_necessaria_kwh, 10.0, places=1)


class TestArbitrageEconomy(unittest.TestCase):

    def _azul_input(self):
        return ArbitrageInput(
            modalidade="azul",
            tarifa_ponta_kwh=0.90,
            tarifa_fora_ponta_kwh=0.30,
            demanda_medida_ponta_kw=50.0,
            demanda_medida_fora_ponta_kw=30.0,
            demanda_contratada_ponta_kw=60.0,
            demanda_contratada_fora_ponta_kw=40.0,
            tarifa_demanda_ponta_kw=45.0,
            tarifa_demanda_fora_ponta_kw=15.0,
            tarifa_demanda_unica_kw=None,
            dod_percent=80.0,
            tensao_instalacao_v=220.0,
        )

    def test_energia_arbitrada(self):
        """2 baterias × 10 kWh × 0.80 DoD = 16 kWh/dia"""
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        self.assertAlmostEqual(eco.energia_arbitrada_dia_kwh, 16.0, places=2)

    def test_potencia_descarga(self):
        """16 kWh / 3h = 5.33 kW"""
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        self.assertAlmostEqual(eco.potencia_descarga_kw, 16.0 / 3.0, places=2)

    def test_economia_energia_mensal(self):
        """16 kWh × (0.90 - 0.30) × 22 dias = 211.20 R$/mês"""
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        self.assertAlmostEqual(eco.economia_energia_mensal, 16.0 * 0.60 * 22, places=1)

    def test_economia_demanda_azul(self):
        """Redução = min(16/3, 50) = 5.33 kW; economia = 5.33 × 45 ≈ 240 R$"""
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        expected = min(16.0 / 3.0, 50.0) * 45.0
        self.assertAlmostEqual(eco.economia_demanda_mensal, expected, places=1)

    def test_economia_demanda_verde_zero(self):
        """Tarifa Verde: economia de demanda = 0"""
        verde = ArbitrageInput(
            modalidade="verde",
            tarifa_ponta_kwh=0.90,
            tarifa_fora_ponta_kwh=0.30,
            demanda_medida_ponta_kw=50.0,
            demanda_medida_fora_ponta_kw=30.0,
            demanda_contratada_ponta_kw=60.0,
            demanda_contratada_fora_ponta_kw=40.0,
            tarifa_demanda_ponta_kw=None,
            tarifa_demanda_fora_ponta_kw=None,
            tarifa_demanda_unica_kw=35.0,
            dod_percent=80.0,
            tensao_instalacao_v=220.0,
        )
        eco = calculate_arbitrage_economy(verde, n_baterias=2, cap_bateria_kwh=10.0)
        self.assertEqual(eco.economia_demanda_mensal, 0.0)

    def test_economia_total_is_sum(self):
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        self.assertAlmostEqual(
            eco.economia_total_mensal,
            eco.economia_energia_mensal + eco.economia_demanda_mensal,
            places=2,
        )


class TestArbitrageV2(unittest.TestCase):
    """Tests verified against CALCULADORA ARBITRAGEM.xlsx formulas."""

    BESS_CAP   = 215.0
    BESS_DOD   = 90.0
    BESS_PRECO = 550_000.0

    def _make_input(self, consumo, demanda, tp=2.5, tfp=0.3):
        return ArbitrageInputV2(
            consumo_ponta_kwh=consumo,
            demanda_ponta_kw=demanda,
            tarifa_ponta_kwh=tp,
            tarifa_fora_ponta_kwh=tfp,
            bess_capacidade_kwh=self.BESS_CAP,
            bess_dod=self.BESS_DOD,
            bess_preco=self.BESS_PRECO,
        )

    def test_qty_driven_by_consumption(self):
        consumo = [10000.0] * 12
        demanda = [250.0] * 12
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda))

        self.assertEqual(result.qty_consumo, 3)
        self.assertEqual(result.qty_potencia, 3)
        self.assertEqual(result.qty_bess, 3)
        self.assertAlmostEqual(result.avg_consumo_ponta, 10000.0, places=2)

    def test_qty_driven_by_power(self):
        consumo = [500.0] * 12
        demanda = [300.0] * 11 + [450.0]
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda))

        self.assertEqual(result.qty_consumo, 1)
        self.assertEqual(result.qty_potencia, 5)
        self.assertEqual(result.qty_bess, 5)
        self.assertAlmostEqual(result.max_demanda_ponta, 450.0, places=2)

    def test_economia_mensal(self):
        """economia = avg_consumo × (tarifa_ponta - tarifa_fora_ponta)"""
        consumo = [10000.0] * 12
        demanda = [250.0] * 12
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda, tp=2.5, tfp=0.3))
        self.assertAlmostEqual(result.economia_mensal, 22000.0, places=2)

    def test_payback_meses(self):
        consumo = [10000.0] * 12
        demanda = [250.0] * 12
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda, tp=2.5, tfp=0.3))
        self.assertAlmostEqual(result.custo_total, 1_650_000.0, places=1)
        self.assertAlmostEqual(result.payback_meses, 75.0, places=1)

    def test_raises_on_wrong_length(self):
        with self.assertRaises(ValueError):
            ArbitrageInputV2(
                consumo_ponta_kwh=[100.0] * 11,
                demanda_ponta_kw=[100.0] * 12,
                tarifa_ponta_kwh=2.5,
                tarifa_fora_ponta_kwh=0.3,
                bess_capacidade_kwh=215, bess_dod=90, bess_preco=550000,
            )

    def test_payback_none_when_no_economia(self):
        """When tarifa_ponta <= tarifa_fora_ponta, economia <= 0, payback = None."""
        consumo = [1000.0] * 12
        demanda = [100.0] * 12
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda, tp=0.3, tfp=0.5))
        self.assertIsNone(result.payback_meses)


if __name__ == '__main__':
    unittest.main()
