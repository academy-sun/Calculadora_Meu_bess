import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import uuid
from datetime import datetime
from app.engines.compatibility import find_compatible_kits, KitBESS
from app.engines.schemas import ProductBESSRead


def make_battery(
    marca="WEG", modelo="BAT-14", sku="W-BAT-14",
    tensao_nominal_v=51.2, capacidade_kwh=14.3, dod_percent=90.0,
    corrente_max_descarga_a=100.0, preco=18000.0,
) -> ProductBESSRead:
    return ProductBESSRead(
        id=uuid.uuid4(), marca=marca, modelo=modelo, sku=sku,
        tipo="bateria", tensao_nominal_v=tensao_nominal_v,
        capacidade_kwh=capacidade_kwh, dod_percent=dod_percent,
        corrente_max_descarga_a=corrente_max_descarga_a,
        preco=preco, disponivel=True, atualizado_em=datetime.utcnow(),
    )


def make_inverter(
    marca="WEG", modelo="INV-5K", sku="W-INV-5K",
    tensao_min_dc_v=40.0, tensao_max_dc_v=60.0,
    corrente_max_dc_a=300.0, potencia_continua_kw=5.0, preco=12000.0,
) -> ProductBESSRead:
    return ProductBESSRead(
        id=uuid.uuid4(), marca=marca, modelo=modelo, sku=sku,
        tipo="inversor_hibrido", tensao_min_dc_v=tensao_min_dc_v,
        tensao_max_dc_v=tensao_max_dc_v, corrente_max_dc_a=corrente_max_dc_a,
        potencia_continua_kw=potencia_continua_kw,
        preco=preco, disponivel=True, atualizado_em=datetime.utcnow(),
    )


class TestCompatibility(unittest.TestCase):

    def test_compatible_same_brand_only(self):
        """Bateria WEG só casa com inversor WEG"""
        bat = make_battery(marca="WEG")
        inv_weg = make_inverter(marca="WEG")
        inv_fox = make_inverter(marca="FoxESS", sku="FOX-INV-1")

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv_weg, inv_fox],
            capacidade_necessaria_kwh=14.0,
            potencia_necessaria_kw=4.0,
        )
        self.assertGreaterEqual(len(kits), 1)
        self.assertTrue(all(k.inversor.marca == "WEG" for k in kits))

    def test_different_brands_no_cross_compatibility(self):
        """WEG bat + FoxESS inverter → lista vazia"""
        bat = make_battery(marca="WEG")
        inv = make_inverter(marca="FoxESS")

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv],
            capacidade_necessaria_kwh=14.0,
            potencia_necessaria_kw=4.0,
        )
        self.assertEqual(kits, [])

    def test_voltage_incompatible_returns_empty(self):
        """Tensão da bateria fora da faixa do inversor → lista vazia"""
        bat = make_battery(tensao_nominal_v=100.0)
        inv = make_inverter(tensao_min_dc_v=40.0, tensao_max_dc_v=60.0)

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv],
            capacidade_necessaria_kwh=14.0,
            potencia_necessaria_kw=4.0,
        )
        self.assertEqual(kits, [])

    def test_kits_sorted_by_price_ascending(self):
        """Kits retornados em ordem crescente de preço total"""
        bat_cheap = make_battery(preco=10000.0, sku="B-CHEAP")
        bat_expensive = make_battery(preco=25000.0, sku="B-EXP")
        inv = make_inverter()

        kits = find_compatible_kits(
            baterias=[bat_cheap, bat_expensive],
            inversores=[inv],
            capacidade_necessaria_kwh=14.0,
            potencia_necessaria_kw=4.0,
        )
        self.assertGreaterEqual(len(kits), 2)
        prices = [k.preco_total for k in kits]
        self.assertEqual(prices, sorted(prices))

    def test_minimum_capacity_always_met(self):
        """Kit selecionado sempre atende a capacidade mínima necessária"""
        bat = make_battery(capacidade_kwh=14.3, dod_percent=90.0)
        inv = make_inverter()

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv],
            capacidade_necessaria_kwh=28.0,
            potencia_necessaria_kw=4.0,
        )
        for kit in kits:
            self.assertGreaterEqual(kit.capacidade_total_kwh, 28.0)

    def test_power_requirement_enforced(self):
        """Inversor com potência insuficiente não entra no resultado"""
        bat = make_battery()
        inv_weak = make_inverter(potencia_continua_kw=2.0, sku="INV-WEAK")
        inv_strong = make_inverter(potencia_continua_kw=10.0, sku="INV-STRONG")

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv_weak, inv_strong],
            capacidade_necessaria_kwh=14.0,
            potencia_necessaria_kw=8.0,
        )
        self.assertTrue(all(k.potencia_total_kw >= 8.0 for k in kits))
        modelos = [k.inversor.modelo for k in kits]
        self.assertNotIn("INV-WEAK", modelos)

    def test_price_calculation(self):
        """Preço total = preço bateria × quantidade + preço inversor"""
        bat = make_battery(preco=10000.0)
        inv = make_inverter(preco=5000.0)

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv],
            capacidade_necessaria_kwh=14.0,
            potencia_necessaria_kw=4.0,
        )
        self.assertGreaterEqual(len(kits), 1)
        kit = kits[0]
        expected_price = bat.preco * kit.qtd_baterias_total + inv.preco
        self.assertAlmostEqual(kit.preco_total, expected_price, places=2)


if __name__ == '__main__':
    unittest.main()
