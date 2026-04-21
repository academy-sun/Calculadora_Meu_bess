import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import uuid
from datetime import datetime
from app.engines.compatibility import find_compatible_kits, KitBESS
from app.engines.schemas import ProductBESSRead


def _bat(marca="Intelbras", modelo="SBW CB050", sku="SBW-CB050",
         cap=5.02, dod=90, preco=3000):
    b = ProductBESSRead(
        id=uuid.uuid4(), marca=marca, modelo=modelo, sku=sku,
        tipo='bateria', capacidade_kwh=cap, dod_percent=dod,
        preco=preco, disponivel=True, atualizado_em=datetime.utcnow(),
    )
    return b


def _inv(marca="Intelbras", modelo="INV", sku="INV-1",
         eps_kva=10.0, fase='monofasico', pot_kw=5.0, preco=6000):
    inv = ProductBESSRead(
        id=uuid.uuid4(), marca=marca, modelo=modelo, sku=sku,
        tipo='inversor_hibrido', potencia_continua_kw=pot_kw,
        preco=preco, disponivel=True, atualizado_em=datetime.utcnow(),
    )
    inv.pot_ca_max_eps_kva = eps_kva
    inv.fase = fase
    return inv


class TestKitSelectionV2(unittest.TestCase):
    """Updated tests for Backup kit selection using P_max EPS and fase."""

    def test_selects_inverter_by_eps_not_nominal(self):
        """Inverter with P_max EPS 10 kVA qualifies when total_pp = 8 kVA."""
        bat = _bat()
        inv_small = _inv(eps_kva=6.0, preco=5000, sku="INV-6")   # 6 < 8 → excluded
        inv_large = _inv(eps_kva=10.0, preco=7000, sku="INV-10")  # 10 >= 8 → included

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv_small, inv_large],
            total_pp_kva=8.0,
            total_e_eps_kwh=4.518,   # exactly 1 × (5.02 × 0.9)
            tipo_instalacao='monofasico',
        )

        self.assertEqual(len(kits), 1)
        self.assertEqual(kits[0].inversor.modelo, 'INV')

    def test_filters_by_fase(self):
        """Monofásico inversor excluded when trifásico installation."""
        bat = _bat()
        inv_mono = _inv(eps_kva=10.0, fase='monofasico', preco=5000, sku="INV-MONO")
        inv_tri  = _inv(eps_kva=10.0, fase='trifasico',  preco=8000, sku="INV-TRI", modelo="INV-TRI")

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv_mono, inv_tri],
            total_pp_kva=8.0,
            total_e_eps_kwh=4.518,
            tipo_instalacao='trifasico',
        )

        self.assertEqual(len(kits), 1)
        self.assertEqual(kits[0].inversor.fase, 'trifasico')

    def test_battery_quantity_formula(self):
        """qty = ceil(E_EPS / (cap × dod/100))"""
        # 5.02 kWh bat, 90% DoD → usable = 4.518 kWh
        # E_EPS = 9.5 → ceil(9.5 / 4.518) = ceil(2.10) = 3
        bat = _bat(cap=5.02, dod=90)
        inv = _inv(eps_kva=20.0)

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv],
            total_pp_kva=5.0,
            total_e_eps_kwh=9.5,
            tipo_instalacao='monofasico',
        )

        self.assertEqual(len(kits), 1)
        self.assertEqual(kits[0].qtd_baterias, 3)

    def test_returns_cheapest_first(self):
        bat = _bat()
        inv_cheap = _inv(eps_kva=10.0, preco=5000, sku="INV-CHEAP")
        inv_pricey = _inv(eps_kva=10.0, preco=9000, sku="INV-PRICEY")

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv_cheap, inv_pricey],
            total_pp_kva=8.0,
            total_e_eps_kwh=4.518,
            tipo_instalacao='monofasico',
        )

        self.assertGreaterEqual(len(kits), 2)
        self.assertLessEqual(kits[0].preco_total, kits[-1].preco_total)

    def test_returns_empty_when_no_eligible_inverter(self):
        bat = _bat()
        inv = _inv(eps_kva=4.0)   # 4 < 8 → excluded

        kits = find_compatible_kits(
            baterias=[bat], inversores=[inv],
            total_pp_kva=8.0, total_e_eps_kwh=4.518,
            tipo_instalacao='monofasico',
        )

        self.assertEqual(kits, [])

    def test_different_brands_excluded(self):
        """WEG bat + Intelbras inverter → empty"""
        bat = _bat(marca="WEG")
        inv = _inv(marca="Intelbras")

        kits = find_compatible_kits(
            baterias=[bat], inversores=[inv],
            total_pp_kva=5.0, total_e_eps_kwh=4.0,
            tipo_instalacao='monofasico',
        )
        self.assertEqual(kits, [])

    def test_price_calculation(self):
        """preco_total = bat.preco × qtd_baterias + inv.preco"""
        bat = _bat(cap=5.02, dod=90, preco=3000)
        inv = _inv(eps_kva=20.0, preco=6000)

        kits = find_compatible_kits(
            baterias=[bat], inversores=[inv],
            total_pp_kva=5.0, total_e_eps_kwh=4.518,  # 1 bat needed
            tipo_instalacao='monofasico',
        )

        self.assertEqual(len(kits), 1)
        kit = kits[0]
        expected = 3000 * kit.qtd_baterias + 6000
        self.assertAlmostEqual(kit.preco_total, expected, places=2)


if __name__ == '__main__':
    unittest.main()
