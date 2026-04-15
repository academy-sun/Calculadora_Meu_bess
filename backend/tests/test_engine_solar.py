import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import math
from app.engines.solar import calculate_solar, POTENCIA_MODULO_WP, AREA_MODULO_M2
from app.engines.schemas import SolarInput


class TestSolar(unittest.TestCase):

    def test_solar_basic(self):
        """
        500 kWh/mês, irradiação 5.0 kWh/m²/dia, eficiência 80%
        Geração diária = 500/30 ≈ 16.67 kWh
        Potência pico = 16.67 / (5.0 * 0.80) ≈ 4.17 kWp
        """
        result = calculate_solar(SolarInput(
            consumo_medio_mensal_kwh=500.0,
            irradiacao_kwh_m2_dia=5.0,
            area_disponivel_m2=100.0,
        ))
        self.assertGreaterEqual(result.potencia_pico_kwp, 4.0)
        self.assertLessEqual(result.potencia_pico_kwp, 4.5)
        self.assertGreater(result.quantidade_modulos, 0)
        self.assertGreater(result.geracao_anual_estimada_kwh, 0)
        self.assertGreater(result.potencia_inversor_kw, 0)

    def test_solar_high_irradiation_needs_less_panels(self):
        """Maior irradiação → menos potência necessária"""
        result_low = calculate_solar(SolarInput(
            consumo_medio_mensal_kwh=1000.0,
            irradiacao_kwh_m2_dia=3.0,
            area_disponivel_m2=200.0,
        ))
        result_high = calculate_solar(SolarInput(
            consumo_medio_mensal_kwh=1000.0,
            irradiacao_kwh_m2_dia=6.0,
            area_disponivel_m2=200.0,
        ))
        self.assertLess(result_high.potencia_pico_kwp, result_low.potencia_pico_kwp)
        self.assertLess(result_high.quantidade_modulos, result_low.quantidade_modulos)

    def test_solar_area_constrains_modules(self):
        """Área pequena limita a quantidade de módulos"""
        # Com área de 20 m² e módulo de 2.2 m², máximo 9 módulos
        max_modulos = math.floor(20.0 / AREA_MODULO_M2)
        result = calculate_solar(SolarInput(
            consumo_medio_mensal_kwh=5000.0,
            irradiacao_kwh_m2_dia=5.0,
            area_disponivel_m2=20.0,
        ))
        self.assertLessEqual(result.quantidade_modulos, max_modulos)

    def test_solar_generation_proportional_to_irradiation(self):
        """Geração anual proporcional à irradiação"""
        r1 = calculate_solar(SolarInput(
            consumo_medio_mensal_kwh=300.0,
            irradiacao_kwh_m2_dia=4.0,
            area_disponivel_m2=50.0,
        ))
        r2 = calculate_solar(SolarInput(
            consumo_medio_mensal_kwh=300.0,
            irradiacao_kwh_m2_dia=8.0,
            area_disponivel_m2=50.0,
        ))
        # Com área menor, área pode ser constraint — só verificar que geração aumenta com irradiação
        self.assertGreaterEqual(r2.geracao_anual_estimada_kwh, r1.geracao_anual_estimada_kwh)

    def test_solar_inverter_power_is_90pct_of_peak(self):
        """Potência do inversor = 90% da potência de pico FV"""
        result = calculate_solar(SolarInput(
            consumo_medio_mensal_kwh=500.0,
            irradiacao_kwh_m2_dia=5.0,
            area_disponivel_m2=100.0,
        ))
        expected_inverter = round(result.potencia_pico_kwp * 0.9, 1)
        self.assertAlmostEqual(result.potencia_inversor_kw, expected_inverter, places=2)


if __name__ == '__main__':
    unittest.main()
