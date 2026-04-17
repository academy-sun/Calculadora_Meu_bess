import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from app.engines.bess import calculate_backup, calculate_peak_shaving, calculate_arbitrage_economy
from app.engines.schemas import BackupInput, PeakShavingInput, ArbitrageInput, CargaItem


class TestBackup(unittest.TestCase):

    def test_single_load_capacidade(self):
        """1 carga 5 kW × 4 h/dia → Capacidade = 20 kWh"""
        inp = BackupInput(
            cargas=[CargaItem(potencia_kw=5.0, tdia_horas=4.0)],
            autonomia_horas=12.0,
            dod_percent=80.0,
            tensao_instalacao_v=220.0,
        )
        result = calculate_backup(inp)
        self.assertAlmostEqual(result.capacidade_kwh, 20.0, places=2)

    def test_single_load_energia_necessaria(self):
        """Energia = 20 × (12/24) / 0.8 / 0.9 ≈ 13.89 kWh"""
        inp = BackupInput(
            cargas=[CargaItem(potencia_kw=5.0, tdia_horas=4.0)],
            autonomia_horas=12.0,
            dod_percent=80.0,
            tensao_instalacao_v=220.0,
        )
        result = calculate_backup(inp)
        expected = 20.0 * (12.0 / 24.0) / 0.80 / 0.9
        self.assertAlmostEqual(result.energia_necessaria_kwh, expected, places=2)

    def test_multi_load_sum(self):
        """2 cargas: 3 kW×2 h + 2 kW×6 h = 6 + 12 = 18 kWh capacidade"""
        inp = BackupInput(
            cargas=[
                CargaItem(potencia_kw=3.0, tdia_horas=2.0),
                CargaItem(potencia_kw=2.0, tdia_horas=6.0),
            ],
            autonomia_horas=24.0,
            dod_percent=100.0,
            tensao_instalacao_v=220.0,
        )
        result = calculate_backup(inp)
        self.assertAlmostEqual(result.capacidade_kwh, 18.0, places=2)

    def test_dod_100_energia_equals_capacidade_over_efficiency(self):
        """DoD 100%, autonomia 24h → Energia = Capacidade / 0.9"""
        inp = BackupInput(
            cargas=[CargaItem(potencia_kw=10.0, tdia_horas=3.0)],
            autonomia_horas=24.0,
            dod_percent=100.0,
            tensao_instalacao_v=220.0,
        )
        result = calculate_backup(inp)
        self.assertAlmostEqual(result.energia_necessaria_kwh, 30.0 / 0.9, places=2)

    def test_zero_dod_raises(self):
        with self.assertRaises(ValueError):
            calculate_backup(BackupInput(
                cargas=[CargaItem(potencia_kw=5.0, tdia_horas=4.0)],
                autonomia_horas=4.0,
                dod_percent=0.0,
                tensao_instalacao_v=220.0,
            ))

    def test_empty_cargas_raises(self):
        with self.assertRaises(ValueError):
            calculate_backup(BackupInput(
                cargas=[],
                autonomia_horas=4.0,
                dod_percent=80.0,
                tensao_instalacao_v=220.0,
            ))


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
