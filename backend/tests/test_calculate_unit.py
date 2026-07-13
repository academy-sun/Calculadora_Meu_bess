import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.calculate.schemas import CalculateRequest, CalculateResponse, KitInfo, LoadItem, OrigemInfo
from app.calculate.service import _build_load_curve, _select_kits
from app.engines.kit_builder import KitBESS, _montar_kit, _attrs_inversor, _attrs_bateria
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


# ── _select_kits ──────────────────────────────────────────────────────────────

class _FakeProd:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def make_kit(marca="WEG", preco=30000.0, capacidade_total_kwh=14.3) -> KitBESS:
    bat = _FakeProd(meubess_id="bat", marca=marca, title="BAT")
    inv = _FakeProd(meubess_id="inv", marca=marca, title="INV")
    return KitBESS(
        inversor=inv, bateria=bat,
        qtd_inversores=1, qtd_baterias=1,
        distribuicao_baterias=[1], n_caixas_juncao=0,
        capacidade_total_kwh=capacidade_total_kwh, pico_entregavel_kw=5.0,
        preco_total=preco,
    )


def test_select_kits_empty():
    kit, alts = _select_kits([], 10.0)
    assert kit is None
    assert alts == []


def test_select_kits_single_kit():
    k = make_kit()
    kit, alts = _select_kits([k], k.capacidade_total_kwh)
    assert kit is not None
    assert kit.marca == "WEG"
    assert kit.rotulo == "Kit sugerido"
    assert alts == []


def test_select_kits_multiple_kits_picks_cheapest_as_sugerido_and_next_as_alternativa():
    k1 = make_kit(preco=25000.0)
    k2 = make_kit(marca="FoxESS", preco=30000.0)
    kit, alts = _select_kits([k1, k2], k1.capacidade_total_kwh)
    assert kit.preco_total == 25000.0
    assert kit.rotulo == "Kit sugerido"
    assert len(alts) == 1
    assert alts[0].preco_total == 30000.0
    assert alts[0].rotulo == "Alternativa — outra composição"


def _make_full_kit(qtd_baterias=4, preco_inv=10000.0, preco_bat=3000.0, usable_kwh=5.0) -> KitBESS:
    """Kit com produtos cujos atributos completos permitem economic_undershoot_kit
    recalcular variantes com menos baterias (precisa de peak_power_kw, battery_inputs,
    usable_capacity_kwh etc. — não só marca/título como o `make_kit` simples)."""
    inv = _FakeProd(
        meubess_id="inv", marca="WEG", title="INV",
        peak_power_kw=20.0, max_eps_power=15.0, battery_inputs=2,
        battery_input_max_current_a=100.0, max_parallel_units=1, price=preco_inv,
    )
    bat = _FakeProd(
        meubess_id="bat", marca="WEG", title="BAT",
        usable_capacity_kwh=usable_kwh, max_parallel_batteries=4,
        max_continuous_current_a=50.0, peak_discharge_current_a=50.0,
        nominal_voltage_v=51.2, price=preco_bat,
    )
    return KitBESS(
        inversor=inv, bateria=bat,
        qtd_inversores=1, qtd_baterias=qtd_baterias,
        distribuicao_baterias=[qtd_baterias // 2, qtd_baterias - qtd_baterias // 2],
        n_caixas_juncao=0,
        capacidade_total_kwh=usable_kwh * qtd_baterias,
        pico_entregavel_kw=20.0,
        preco_total=preco_inv + preco_bat * qtd_baterias,
    )


def test_select_kits_picks_cheapest_under_100pct_coverage_as_economic_alternative():
    """
    A montagem normal sempre escolhe o menor n suficiente (cobertura ≥ 100% por
    construção). A "alternativa mais econômica" é sintetizada com MENOS baterias —
    a que mais se aproxima de 100% de cobertura sem atingir.
    """
    sugerido = make_kit(preco=25000.0, capacidade_total_kwh=10.0)
    composicao = make_kit(marca="FoxESS", preco=30000.0, capacidade_total_kwh=10.0)
    # usable_kwh=5 × 4 baterias = 20kWh ≥ e_bat_kwh=18 (sugerido pelo motor); variantes
    # com 1/2/3 baterias (5/10/15 kWh) ficam abaixo — a de 3 (15kWh = 83%) é a mais próxima.
    kit_completo = _make_full_kit(qtd_baterias=4, preco_inv=10000.0, preco_bat=3000.0, usable_kwh=5.0)
    kits = [sugerido, composicao, kit_completo]

    kit, alts = _select_kits(kits, e_bat_kwh=18.0)

    assert kit.preco_total == 25000.0
    assert len(alts) == 2
    assert alts[0].preco_total == 30000.0
    rotulos = [a.rotulo for a in alts]
    assert "Alternativa — mais econômica" in rotulos
    economica = next(a for a in alts if a.rotulo == "Alternativa — mais econômica")
    assert economica.qtd_baterias == 3
    assert economica.capacidade_total_kwh == 15.0
    assert economica.preco_total == 10000.0 + 3000.0 * 3


# ── Preço real da caixa de junção (JBW) ────────────────────────────────────────

def test_montar_kit_uses_real_jbw_price_when_available():
    """
    Regressão: a JBW aparecia sempre com preço R$ 0 (hardcoded) mesmo havendo produto
    real cadastrado no catálogo (ex.: 'Caixa de Junção - JBW 41DC 50A W0', R$1108,71).
    _montar_kit agora busca o preço real por marca; sem produto cadastrado, mantém
    0 mas sinaliza via alerta em vez de aparentar que é gratuita.
    """
    inv = _FakeProd(
        meubess_id="inv", marca="WEG", title="INV",
        peak_power_kw=20.0, max_eps_power=15.0, battery_inputs=1,
        battery_input_max_current_a=100.0, max_parallel_units=1, price=10000.0,
    )
    bat = _FakeProd(
        meubess_id="bat", marca="WEG", title="BAT",
        usable_capacity_kwh=5.0, max_parallel_batteries=4,
        max_continuous_current_a=50.0, peak_discharge_current_a=50.0,
        nominal_voltage_v=51.2, price=3000.0,
    )
    ia, _ = _attrs_inversor(inv)
    ba, _ = _attrs_bateria(bat)
    # n=2 numa única entrada (battery_inputs=1) → distribuição [2] → n_jbw=1
    n_entradas = ia["battery_inputs"]

    jbw_weg = _FakeProd(meubess_id="jbw", marca="WEG", title="Caixa de Junção - JBW 41DC 50A W0", price=1108.71)
    jbw_outra_marca = _FakeProd(meubess_id="jbw2", marca="FoxESS", title="Junction Box", price=50.0)

    # Com produto real cadastrado da mesma marca: usa o preço real, não zero.
    kit_com_preco = _montar_kit(inv, bat, 1, 2, ia, ba, n_entradas, [], lambda p: str(p.title), [jbw_weg, jbw_outra_marca])
    jbw_item = next(it for it in kit_com_preco.itens if it["tipo"] == "acessorio")
    assert jbw_item["preco_unitario"] == 1108.71
    assert jbw_item["preco_total"] == 1108.71
    assert kit_com_preco.preco_total == 10000.0 + 3000.0 * 2 + 1108.71
    assert not any("sem preço cadastrado" in a for a in kit_com_preco.alertas)

    # Sem nenhuma JBW cadastrada: mantém 0, mas alerta explicitamente (não esconde o gap).
    kit_sem_preco = _montar_kit(inv, bat, 1, 2, ia, ba, n_entradas, [], lambda p: str(p.title), [])
    jbw_item_zero = next(it for it in kit_sem_preco.itens if it["tipo"] == "acessorio")
    assert jbw_item_zero["preco_unitario"] == 0.0
    assert any("sem preço cadastrado" in a for a in kit_sem_preco.alertas)


# ── FV combinado (pv_kit) ──────────────────────────────────────────────────────

def _hybrid_with_mppt() -> object:
    """Híbrido tipo SIW200H M105 W10: dados de bateria + dados de MPPT (lado PV)."""
    return _FakeProd(
        meubess_id="hyb", marca="WEG", title="SIW200H M105 W10",
        peak_power_kw=12.0, max_eps_power=10.5, battery_inputs=1,
        battery_input_max_current_a=50.0, max_parallel_units=3, price=11000.0,
        # lado PV
        voc_max_voltage=600, mppt_min_voltage=80, string_current=16,
        qty_mppt=4, qty_inputs_per_mppt=1, short_circuit_current_inverter=20,
    )


def _battery() -> object:
    return _FakeProd(
        meubess_id="bat", marca="WEG", title="SBW CB050",
        usable_capacity_kwh=5.0, max_parallel_batteries=4,
        max_continuous_current_a=50.0, peak_discharge_current_a=65.0,
        nominal_voltage_v=51.2, price=6000.0,
    )


def _module_jam() -> object:
    """Módulo JAM66D46-700: Imp 17.3A > 16A (clipping, não bloqueia); Isc 18.4 < 20 (OK)."""
    return _FakeProd(
        meubess_id="mod", marca="JA Solar", title="JAM66D46-700/LB",
        voc_max_voltage=48.2, max_power_current=17.32, short_circuit_current_module=18.43,
        power=0.700, price=700.0,
    )


def test_combined_kit_includes_pv_items_when_module_fits_hybrid_dc():
    """Regressão do bug: Imp>string_current zerava a capacidade CC e o FV sumia.
    Agora a série cabe na tensão e a Isc do módulo (18.4) < Isc máx da entrada (20),
    então o híbrido absorve os módulos no DC e o kit combinado traz itens de módulo."""
    from app.engines.kit_builder import _montar_kit, _attrs_inversor, _attrs_bateria
    from app.engines.pv_kit import build_combined_pv_storage, dc_capacity_modules, _attrs_modulo

    hyb, bat = _hybrid_with_mppt(), _battery()
    ia, _ = _attrs_inversor(hyb)
    ba, _ = _attrs_bateria(bat)
    base = _montar_kit(hyb, bat, 1, 2, ia, ba, ia["battery_inputs"], [], lambda p: str(p.title))

    mod_attrs = _attrs_modulo(_module_jam())
    # capacidade CC: floor(600/48.2)=12 série × 1 entrada × 4 MPPT × 1 inv = 48 módulos
    assert dc_capacity_modules(hyb, 1, mod_attrs) == 48

    sugerido, alts = build_combined_pv_storage(
        kits_storage=[base],
        e_bat_kwh=10.0,
        kwp_alvo=3.5,   # ~5 módulos de 700W → cabe nos 48 do DC
        modulos=[_module_jam()],
        fixing_type="tile_ceramic",
        cabos=[_FakeProd(meubess_id="cabo", title="Cabo CC 6mm", category_title="Cabo CC", price=5.0)],
        mc4s=[_FakeProd(meubess_id="mc4", title="Conector MC4", category_title="Conector MC4", price=8.5)],
        estruturas=[_FakeProd(meubess_id="est", title="Estrutura telha cerâmica",
                              groups="structure", fixing_type="tile_ceramic", fixing_capacity=4, price=300.0)],
        inversores_string=[],
        inversores_hibridos=[hyb],
        voltage="220", phase="monofasico",
    )
    assert sugerido is not None
    assert sugerido.rotulo_caminho == "dc"
    merged = sugerido.to_merged_kit()
    tipos = {it["tipo"] for it in merged.itens}
    assert "modulo_fv" in tipos      # o FV aparece no kit combinado
    assert "bateria" in tipos        # e a bateria também
    assert any(it["tipo"] == "acessorio" for it in merged.itens)  # cabos/mc4/estrutura


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


_EMPTY_PV = dict(modulos=[], inversores_string=[], cabos=[], mc4s=[], estruturas=[])


def _mock_db_and_catalog():
    """Retorna (db_mock, patches) para usar em testes de service."""
    db = AsyncMock()
    patches = [
        patch("app.calculate.service.list_kit_products", new=AsyncMock(return_value=([], [], []))),
        patch("app.calculate.service.list_products", new=AsyncMock(return_value=[])),
        patch("app.calculate.service.list_pv_products", new=AsyncMock(return_value=_EMPTY_PV)),
    ]
    return db, patches


def test_backup_direto_missing_total_pp_kva_raises():
    """Sem total_pp_kva deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_pp_kva=None)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2]:
        with pytest.raises(ValueError, match="total_pp_kva"):
            _run(run_calculation(db, req))


def test_backup_direto_missing_total_e_eps_kwh_raises():
    """Sem total_e_eps_kwh deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_e_eps_kwh=None)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2]:
        with pytest.raises(ValueError, match="total_e_eps_kwh"):
            _run(run_calculation(db, req))


def test_backup_direto_zero_e_eps_raises():
    """total_e_eps_kwh=0 deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_e_eps_kwh=0.0)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2]:
        with pytest.raises(ValueError, match="maior que zero"):
            _run(run_calculation(db, req))


def test_backup_direto_valid_returns_response():
    """Com totais válidos e catálogo vazio deve retornar kit_selecionado=None sem erro."""
    from app.calculate.service import run_calculation
    from app.calculate.schemas import CalculateResponse

    req = _make_backup_direto_req()
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2]:
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
