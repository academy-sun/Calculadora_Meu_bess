import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.calculate.schemas import CalculateRequest, CalculateResponse, KitInfo, LoadItem, OrigemInfo
from app.calculate.service import _build_load_curve, _kits_to_response
from app.engines.kit_builder import KitBESS
import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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

class _FakeProd:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def make_kit(marca="WEG", preco=30000.0) -> KitBESS:
    bat = _FakeProd(meubess_id="bat", marca=marca, title="BAT")
    inv = _FakeProd(meubess_id="inv", marca=marca, title="INV")
    return KitBESS(
        inversor=inv, bateria=bat,
        qtd_inversores=1, qtd_baterias=1,
        distribuicao_baterias=[1], n_caixas_juncao=0,
        capacidade_total_kwh=14.3, pico_entregavel_kw=5.0,
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_origem_info(**kwargs):
    defaults = dict(
        origem="ploomes",
        negocio_id="123",
        negocio_nome="Empresa Teste",
        solicitante_id="user-1",
        solicitante_nome="João",
        solicitado_em=datetime.now(timezone.utc),
    )
    return OrigemInfo(**{**defaults, **kwargs})


# ── backup_direto schema ───────────────────────────────────────────────────────

def test_backup_direto_schema_accepts_new_tipo():
    """tipo_calculo='backup_direto' deve ser aceito pelo schema."""
    req = CalculateRequest(
        origem_info=_make_origem_info(),
        tipo_calculo="backup_direto",
        tipo_instalacao="monofasico",
        total_pp_kva=28.8,
        total_e_eps_kwh=4.8,
    )
    assert req.tipo_calculo == "backup_direto"
    assert req.total_pp_kva == 28.8
    assert req.total_e_eps_kwh == 4.8


def test_backup_direto_schema_fields_optional_by_default():
    """total_pp_kva e total_e_eps_kwh são None quando não fornecidos."""
    req = CalculateRequest(
        origem_info=_make_origem_info(),
        tipo_calculo="backup",
    )
    assert req.total_pp_kva is None
    assert req.total_e_eps_kwh is None


def test_backup_direto_schema_rejects_unknown_tipo():
    """tipo_calculo inválido deve lançar ValidationError."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CalculateRequest(
            origem_info=_make_origem_info(),
            tipo_calculo="tipo_inexistente",
        )


# ── backup_direto service validation ──────────────────────────────────────────

import asyncio

def _run(coro):
    """Helper para rodar coroutines em testes síncronos."""
    return asyncio.run(coro)


def _make_backup_direto_req(**kwargs):
    defaults = dict(
        origem_info=_make_origem_info(),
        tipo_calculo="backup_direto",
        tipo_instalacao="monofasico",
        total_pp_kva=28.8,
        total_e_eps_kwh=4.8,
    )
    return CalculateRequest(**{**defaults, **kwargs})


def _mock_db_and_catalog(mock_project=None):
    """Retorna (db_mock, patches) para usar em testes de service."""
    if mock_project is None:
        mock_project = MagicMock()
        mock_project.parametros = {}
        mock_project.id = uuid.uuid4()

    db = AsyncMock()
    patches = [
        patch("app.calculate.service.create_project", new=AsyncMock(return_value=mock_project)),
        patch("app.calculate.service.mark_project_done", new=AsyncMock()),
        patch("app.calculate.service.mark_project_error", new=AsyncMock()),
        patch("app.calculate.service.list_kit_products", new=AsyncMock(return_value=([], []))),
        patch("app.calculate.service.list_products", new=AsyncMock(return_value=[])),
    ]
    return db, patches


def test_backup_direto_missing_total_pp_kva_raises():
    """Sem total_pp_kva deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_pp_kva=None)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with pytest.raises(ValueError, match="total_pp_kva"):
            _run(run_calculation(db, req))


def test_backup_direto_missing_total_e_eps_kwh_raises():
    """Sem total_e_eps_kwh deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_e_eps_kwh=None)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with pytest.raises(ValueError, match="total_e_eps_kwh"):
            _run(run_calculation(db, req))


def test_backup_direto_zero_e_eps_raises():
    """total_e_eps_kwh=0 deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_e_eps_kwh=0.0)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with pytest.raises(ValueError, match="maior que zero"):
            _run(run_calculation(db, req))


def test_backup_direto_valid_returns_response():
    """Com totais válidos e catálogo vazio deve retornar kit_selecionado=None sem erro."""
    from app.calculate.service import run_calculation
    from app.calculate.schemas import CalculateResponse

    req = _make_backup_direto_req()
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = _run(run_calculation(db, req))

    assert isinstance(result, CalculateResponse)
    assert result.tipo_calculo == "backup_direto"
    assert result.capacidade_kwh == 4.8
    assert result.potencia_kw == 28.8
    assert result.kit_selecionado is None   # catálogo vazio → sem kit
    assert result.backup_rows is None


def test_existing_backup_tipo_still_works():
    """tipo_calculo='backup' continua validando e roteando corretamente."""
    req = CalculateRequest(
        origem_info=_make_origem_info(),
        tipo_calculo="backup",
        tipo_instalacao="monofasico",
        cargas_backup=[],
    )
    assert req.tipo_calculo == "backup"
    assert req.total_pp_kva is None
