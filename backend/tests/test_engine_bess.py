import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from app.engines.bess import calculate_backup, calculate_peak_shaving, calculate_arbitrage
from app.engines.schemas import BackupInput, PeakShavingInput, ArbitrageInput


class TestBackup(unittest.TestCase):

    def test_backup_basic(self):
        """5 kW crítico, 4h autonomia, DoD 90% → capacidade = 5*4/0.9 ≈ 22.22 kWh"""
        result = calculate_backup(BackupInput(
            potencia_critica_kw=5.0,
            autonomia_horas=4.0,
            tensao_instalacao_v=220.0,
        ), dod_percent=90.0)
        self.assertAlmostEqual(result.capacidade_necessaria_kwh, 22.22, places=1)
        self.assertEqual(result.potencia_necessaria_kw, 5.0)

    def test_backup_full_dod(self):
        """DoD 100% → capacidade = potência × autonomia"""
        result = calculate_backup(BackupInput(
            potencia_critica_kw=10.0,
            autonomia_horas=2.0,
            tensao_instalacao_v=220.0,
        ), dod_percent=100.0)
        self.assertAlmostEqual(result.capacidade_necessaria_kwh, 20.0, places=2)

    def test_backup_zero_dod_raises(self):
        with self.assertRaises(ValueError):
            calculate_backup(BackupInput(
                potencia_critica_kw=5.0,
                autonomia_horas=4.0,
                tensao_instalacao_v=220.0,
            ), dod_percent=0.0)

    def test_backup_observacoes_contains_autonomia(self):
        result = calculate_backup(BackupInput(
            potencia_critica_kw=5.0,
            autonomia_horas=8.0,
            tensao_instalacao_v=220.0,
        ), dod_percent=80.0)
        self.assertIn("8.0", result.observacoes)


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


class TestArbitrage(unittest.TestCase):

    def test_arbitrage_basic(self):
        """Tarifa ponta 3× fora-de-ponta → economia positiva"""
        curva = [10.0] * 24
        result = calculate_arbitrage(ArbitrageInput(
            curva_carga_kw=curva,
            horario_ponta_inicio=18,
            horario_ponta_fim=21,
            tarifa_ponta_rs_kwh=0.90,
            tarifa_fora_ponta_rs_kwh=0.30,
        ))
        self.assertGreater(result.economia_anual_estimada_rs, 0)
        self.assertGreater(result.capacidade_otima_kwh, 0)
        self.assertEqual(result.ciclos_dia, 1.0)

    def test_arbitrage_equal_tariffs(self):
        """Tarifas iguais → economia = 0"""
        curva = [10.0] * 24
        result = calculate_arbitrage(ArbitrageInput(
            curva_carga_kw=curva,
            horario_ponta_inicio=18,
            horario_ponta_fim=21,
            tarifa_ponta_rs_kwh=0.50,
            tarifa_fora_ponta_rs_kwh=0.50,
        ))
        self.assertEqual(result.economia_anual_estimada_rs, 0.0)

    def test_arbitrage_3h_window(self):
        """Janela de ponta de 3h (18-21), 10 kW → energia ponta = 30 kWh/dia"""
        curva = [10.0] * 24
        result = calculate_arbitrage(ArbitrageInput(
            curva_carga_kw=curva,
            horario_ponta_inicio=18,
            horario_ponta_fim=21,
            tarifa_ponta_rs_kwh=1.0,
            tarifa_fora_ponta_rs_kwh=0.3,
        ))
        # 3 horas × 10 kW = 30 kWh de energia na ponta por dia
        self.assertAlmostEqual(result.capacidade_otima_kwh, 30.0, delta=1.0)


if __name__ == '__main__':
    unittest.main()
