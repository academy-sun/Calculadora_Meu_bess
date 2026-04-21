import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import pytest
import unittest
from app.engines.bess import calculate_backup, calculate_peak_shaving, calculate_arbitrage_economy
from app.engines.schemas import BackupInput, LoadRow, PeakShavingInput, ArbitrageInput


class TestBackup:
    """Tests verified against CALCULADORA BACKUP.xlsx formulas."""

    def _make_input(self, cargas, tipo="monofasico"):
        return BackupInput(cargas=cargas, tipo_instalacao=tipo, dod_percent=90)

    def test_single_load_ar_condicionado(self):
        """AR CONDICIONADO BTU 7500: qty=1, PNOM=800W, FP=0.75, FD=1, IP/IN=6, TDIA=6h"""
        # Pn = ceil(1 * 800/0.75) / 1000 = ceil(1066.67) / 1000 = 1067/1000 = 1.067
        cargas = [LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=6.0, tdia_h=6.0)]
        result = calculate_backup(self._make_input(cargas))

        assert result.rows[0].pn_kva == pytest.approx(1.067, abs=0.001)
        assert result.rows[0].dmn_kva == pytest.approx(1.067, abs=0.001)   # 1.067 * 1.0
        assert result.rows[0].pp_kva == pytest.approx(6.402, abs=0.001)    # 1.067 * 6
        assert result.rows[0].dmp_kva == pytest.approx(6.402, abs=0.001)   # 1.067 * 6
        assert result.rows[0].e_eps_kwh == pytest.approx(6.402, abs=0.001) # 1.067 * 6

    def test_single_load_abajur(self):
        """ABAJUR 45W INCAND: qty=2, PNOM=45W, FP=1.0, FD=0.9, IP/IN=1.0, TDIA=5h"""
        # Pn = ceil(2 * 45/1.0) / 1000 = 90 / 1000 = 0.09
        cargas = [LoadRow(qtd=2, pnom_w=45, fp=1.0, fd=0.9, ip_in=1.0, tdia_h=5.0)]
        result = calculate_backup(self._make_input(cargas))

        assert result.rows[0].pn_kva == pytest.approx(0.09, abs=0.001)
        assert result.rows[0].dmn_kva == pytest.approx(0.081, abs=0.001)   # 0.09 * 0.9
        assert result.rows[0].pp_kva == pytest.approx(0.09, abs=0.001)     # 0.09 * 1.0
        assert result.rows[0].dmp_kva == pytest.approx(0.081, abs=0.001)   # 0.081 * 1.0
        assert result.rows[0].e_eps_kwh == pytest.approx(0.45, abs=0.001)  # 0.09 * 5

    def test_multiple_loads_totals(self):
        """Two loads: verify SUBTOTAL sums."""
        cargas = [
            LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=6.0, tdia_h=6.0),  # Pn=1.067
            LoadRow(qtd=2, pnom_w=45,  fp=1.0,  fd=0.9, ip_in=1.0, tdia_h=5.0),  # Pn=0.090
        ]
        result = calculate_backup(self._make_input(cargas))

        assert len(result.rows) == 2
        assert result.total_pn    == pytest.approx(1.157, abs=0.001)   # 1.067 + 0.09
        assert result.total_dmn   == pytest.approx(1.148, abs=0.001)   # 1.067 + 0.081
        assert result.total_pp    == pytest.approx(6.492, abs=0.001)   # 6.402 + 0.09
        assert result.total_dmp   == pytest.approx(6.483, abs=0.001)   # 6.402 + 0.081
        assert result.total_e_eps == pytest.approx(6.852, abs=0.001)   # 6.402 + 0.45

    def test_roundup_behavior(self):
        """ROUNDUP is ceil for positive: ceil(800/0.75) = ceil(1066.67) = 1067"""
        cargas = [LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=1.0, tdia_h=1.0)]
        result = calculate_backup(self._make_input(cargas))
        # 1067 / 1000 = 1.067 (not 1.066)
        assert result.rows[0].pn_kva == pytest.approx(1.067, abs=0.0001)

    def test_raises_on_empty_cargas(self):
        with pytest.raises(ValueError, match="cargas"):
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


if __name__ == '__main__':
    unittest.main()
