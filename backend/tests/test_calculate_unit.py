import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.calculate.schemas import CalculateRequest, CalculateResponse, KitInfo, LoadItem, OrigemInfo
from app.calculate.service import _build_load_curve, _kits_to_response
from app.engines.compatibility import KitBESS
from app.catalog.schemas import ProductBESSRead
import uuid
from datetime import datetime


# ── _build_load_curve ─────────────────────────────────────────────────────────

def test_build_load_curve_single_load():
    """1000W, 1 unit, 8h → 8 horas com 1.0 kW"""
    cargas = [LoadItem(nome="AC", potencia_w=1000.0, quantidade=1, horas_uso_dia=8.0)]
    curva = _build_load_curve(cargas)
    assert len(curva) == 24
    assert sum(1 for v in curva[:8] if v == 1.0) == 8
    assert all(v == 0.0 for v in curva[8:])


def test_build_load_curve_multiple_loads():
    """Duas cargas: 500W + 500W ambas por 4h → 1.0 kW por 4h"""
    cargas = [
        LoadItem(nome="L1", potencia_w=500.0, quantidade=1, horas_uso_dia=4.0),
        LoadItem(nome="L2", potencia_w=500.0, quantidade=1, horas_uso_dia=4.0),
    ]
    curva = _build_load_curve(cargas)
    assert abs(curva[0] - 1.0) < 0.001
    assert abs(curva[3] - 1.0) < 0.001


def test_build_load_curve_quantity():
    """3 unidades de 1000W → 3.0 kW"""
    cargas = [LoadItem(nome="AC", potencia_w=1000.0, quantidade=3, horas_uso_dia=2.0)]
    curva = _build_load_curve(cargas)
    assert abs(curva[0] - 3.0) < 0.001
    assert abs(curva[1] - 3.0) < 0.001
    assert curva[2] == 0.0


def test_build_load_curve_returns_24_points():
    """Sempre retorna 24 pontos"""
    curva = _build_load_curve([])
    assert len(curva) == 24


# ── _kits_to_response ──────────────────────────────────────────────────────────

def make_kit(marca="WEG", preco=30000.0) -> KitBESS:
    bat = ProductBESSRead(
        id=uuid.uuid4(), marca=marca, modelo="BAT", sku=f"B-{marca}",
        tipo="bateria", preco=18000.0, disponivel=True,
        atualizado_em=datetime.utcnow(),
    )
    inv = ProductBESSRead(
        id=uuid.uuid4(), marca=marca, modelo="INV", sku=f"I-{marca}",
        tipo="inversor_hibrido", preco=12000.0, disponivel=True,
        atualizado_em=datetime.utcnow(),
    )
    return KitBESS(
        bateria=bat, inversor=inv,
        qtd_baterias_serie=1, qtd_strings_paralelo=1,
        qtd_baterias_total=1,
        capacidade_total_kwh=14.3, potencia_total_kw=5.0,
        preco_total=preco,
    )


def test_kits_to_response_empty():
    kit, alts = _kits_to_response([])
    assert kit is None
    assert alts == []


def test_kits_to_response_single_kit():
    k = make_kit()
    kit, alts = _kits_to_response([k])
    assert kit is not None
    assert kit.marca == "WEG"
    assert alts == []


def test_kits_to_response_multiple_kits():
    k1 = make_kit(preco=25000.0)
    k2 = make_kit(marca="FoxESS", preco=30000.0)
    kit, alts = _kits_to_response([k1, k2])
    assert kit.preco_total == 25000.0
    assert len(alts) == 1
    assert alts[0].preco_total == 30000.0
