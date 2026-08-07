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


# ── frete do kit on-grid puro (sem cargas) ────────────────────────────────────
# Regressao: o ramo "backup sem cargas" retorna cedo, antes do bloco que
# calculava o frete. Kit on-grid saia sempre sem frete, mesmo com CIF e UF
# preenchidos — reproduzido em campo com CIF no Acre.

from contextlib import ExitStack

# 7000.00 + 4402.55 = 11402.55, o mesmo valor do kit visto no teste real
_ONGRID_ITENS = [
    {"nome": "Modulo 635W", "tipo": "modulo", "qtd": 14,
     "preco_unitario": 500.0, "preco_total": 7000.0},
    {"nome": "Inversor string 8kW", "tipo": "inversor_string", "qtd": 1,
     "preco_unitario": 4402.55, "preco_total": 4402.55},
]
_ONGRID_PRECO = 11402.55


def _make_ongrid_req(**kwargs):
    defaults = dict(
        origem_info=_make_origem_info(),
        tipo_calculo="backup",
        powerpeak_kwp=8.5,
        tipo_instalacao="monofasico",
        padrao_entrada="mono_220",
    )
    return CalculateRequest(**{**defaults, **kwargs})


def _ongrid_detalhe():
    """Modulo de 635 Wp x14 e inversor com 2 MPPT e 600 V de tensao maxima."""
    from app.engines.pv_kit import ModuloAttrs, OngridPVDetail

    modulo = ModuloAttrs(
        produto=_FakeProd(marca="WEG", title="Modulo 635W", price=500.0),
        voc_v=50.0, imp_a=13.0, isc_a=13.8, wp=635.0, preco=500.0,
    )
    inversor = _FakeProd(title="Inversor string 8kW", voc_max_voltage=600.0,
                         qty_mppt=2, power=8.0, price=4402.55)
    return OngridPVDetail(modulo=modulo, qty_modulos=14,
                          inversor=inversor, qtd_inversores=1)


def _run_ongrid(req, detalhe=None):
    """Catalogo BESS vazio, mas o kit on-grid devolve itens: isola o caminho."""
    from app.calculate.service import run_calculation

    db, patches = _mock_db_and_catalog()
    patches.append(patch(
        "app.calculate.service.build_ongrid_kit_detalhado",
        return_value=(list(_ONGRID_ITENS),
                      _ongrid_detalhe() if detalhe is None else detalhe),
    ))
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return _run(run_calculation(db, req))


def test_ongrid_puro_monta_kit_sem_bateria():
    result = _run_ongrid(_make_ongrid_req())
    assert result.kit_selecionado is not None
    assert result.kit_selecionado.qtd_baterias == 0
    assert result.kit_selecionado.preco_total == _ONGRID_PRECO


def test_ongrid_puro_calcula_frete_cif():
    """CIF no Acre: 8% de 11402.55 = 912.20, abaixo do minimo de 7900."""
    result = _run_ongrid(_make_ongrid_req(tipo_frete="cif", uf_entrega="AC"))
    assert result.frete is not None, "kit on-grid voltou sem frete"
    assert result.frete["tipo"] == "cif"
    assert result.frete["uf"] == "AC"
    assert result.frete["valor"] == 7900.0


def test_ongrid_puro_calcula_frete_fob():
    result = _run_ongrid(_make_ongrid_req(tipo_frete="fob"))
    assert result.frete is not None
    assert result.frete["tipo"] == "fob"
    assert result.frete["valor"] == round(_ONGRID_PRECO * 0.01, 2)


def test_ongrid_puro_sem_frete_quando_nao_informado():
    assert _run_ongrid(_make_ongrid_req()).frete is None


def test_ongrid_puro_cif_sem_uf_nao_calcula():
    """CIF sem UF nao deve inventar frete."""
    assert _run_ongrid(_make_ongrid_req(tipo_frete="cif")).frete is None


def test_ongrid_puro_preenche_solar_dimensionamento():
    """O retorno antecipado do on-grid tambem descreve o FV, com os mesmos
    numeros do kit cotado (14 modulos de 635 Wp = 8.89 kWp)."""
    result = _run_ongrid(_make_ongrid_req())
    sd = result.solar_dimensionamento
    assert sd is not None, "on-grid voltou sem solar_dimensionamento"
    assert sd.qty_modulos == 14
    assert sd.modulo_wp == 635.0
    assert sd.modulo_marca == "WEG"
    assert sd.kwp_instalado == 8.89
    assert sd.preco_modulos_total == 7000.0
    # 600 V / 50 V por modulo = 12 em serie; 2 MPPT cobrem os 14 modulos em 1 paralelo
    assert (sd.n_serie, sd.n_paralelo, sd.mppt_qty) == (12, 1, 2)
    # 8.89 instalado sobre 8.5 alvo
    assert sd.cobertura_pct == 104.6


def test_ongrid_solar_dimensionamento_bate_com_kwp_do_kit():
    """kwp_instalado da ficha e o kwp_instalado do kit sao o mesmo numero."""
    result = _run_ongrid(_make_ongrid_req())
    assert result.solar_dimensionamento.kwp_instalado == result.kit_selecionado.kwp_instalado


def test_ongrid_sem_dados_de_mppt_nao_inventa_dimensionamento():
    """Inversor sem qty_mppt/tensao maxima: sem ficha, em vez de numero chutado."""
    from app.engines.pv_kit import OngridPVDetail

    base = _ongrid_detalhe()
    mudo = OngridPVDetail(modulo=base.modulo, qty_modulos=14,
                          inversor=_FakeProd(title="Inversor sem specs"),
                          qtd_inversores=1)
    result = _run_ongrid(_make_ongrid_req(), detalhe=mudo)
    assert result.solar_dimensionamento is None
    assert result.kit_selecionado is not None   # o kit continua saindo


# ── caminho combinado: cargas + FV ────────────────────────────────────────────
# Regressao: este ramo nao tinha cobertura nenhuma, e um import removido
# (select_module) so aparecia em producao — como 500, que o navegador mostrava
# como "failed to fetch" porque o handler global responde sem cabecalho CORS.

class _FakeCombinedOption:
    """Minimo que _option_to_info consome de um CombinedOption."""
    def __init__(self, kit, rotulo_caminho="dc"):
        self._kit = kit
        self.rotulo_caminho = rotulo_caminho

    def to_merged_kit(self):
        return self._kit


def _run_combinado(req, sugerido=None, alternativas=()):
    from app.calculate.service import run_calculation

    kit = make_kit(preco=30000.0, capacidade_total_kwh=10.0)
    opt = _FakeCombinedOption(kit) if sugerido is None else sugerido
    db, patches = _mock_db_and_catalog()
    patches.append(patch("app.calculate.service.build_kits", return_value=([kit], [])))
    patches.append(patch("app.calculate.service.build_combined_pv_storage",
                         return_value=(opt, list(alternativas))))
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return _run(run_calculation(db, req))


def _make_combinado_req(**kwargs):
    defaults = dict(
        origem_info=_make_origem_info(),
        tipo_calculo="backup",
        powerpeak_kwp=8.5,
        tipo_instalacao="monofasico",
        padrao_entrada="mono_220",
        autonomia_dias=1,
        dod_percent=90,
        cargas_backup=[{
            "nome": "Carga teste", "qtd": 1, "pnom_w": 3000.0,
            "fp": 1.0, "fd": 1.0, "ip_in": 1.0, "tdia_h": 4.0, "tensao": "220",
        }],
    )
    return CalculateRequest(**{**defaults, **kwargs})


def test_combinado_cargas_mais_fv_responde():
    """Exercita o ramo tem_pv and kits — onde vivia o select_module orfao."""
    result = _run_combinado(_make_combinado_req())
    assert isinstance(result, CalculateResponse)
    assert result.kit_selecionado is not None
    assert result.kit_selecionado.preco_total == 30000.0


def test_combinado_calcula_frete():
    result = _run_combinado(_make_combinado_req(tipo_frete="cif", uf_entrega="PR"))
    assert result.frete is not None
    assert result.frete["uf"] == "PR"


def test_combinado_leva_alternativas():
    kit_alt = make_kit(marca="FoxESS", preco=35000.0, capacidade_total_kwh=12.0)
    result = _run_combinado(_make_combinado_req(),
                            alternativas=[_FakeCombinedOption(kit_alt, "split")])
    assert len(result.alternativas) == 1
    assert result.alternativas[0].preco_total == 35000.0


# ── R8 no caminho COMBINADO (FV + armazenamento) ──────────────────────────────
# Reportado em campo: abajur TRIFASICO com FV no projeto voltou com inversor
# MONOfasico. A R8 filtrava kits_storage, mas o caminho "hibrido ampliado"
# SUBSTITUI o inversor depois disso, sem reaplicar a regra.

def test_combinado_nao_oferece_hibrido_incompativel_com_a_fase():
    from app.engines.kit_builder import compativel_com_cargas

    mono = _FakeProd(meubess_id="m075", title="SIW200H M075 mono 220",
                     eps_output_voltage="220", split_phase=False, phase="monofasico")
    tri = _FakeProd(meubess_id="t015", title="SIW400H T015 tri 380/220",
                    eps_output_voltage="380/220", split_phase=False, phase="trifasico")

    ok_mono, motivo = compativel_com_cargas(mono, {"220"}, {"trifasico"})
    ok_tri, _ = compativel_com_cargas(tri, {"220"}, {"trifasico"})

    assert not ok_mono and "trifásica" in motivo
    assert ok_tri


def test_compativel_com_cargas_sem_restricao_aceita_tudo():
    """Cotacao sem tensao nem fase informadas nao pode filtrar nada."""
    from app.engines.kit_builder import compativel_com_cargas
    qualquer = _FakeProd(meubess_id="x", title="X", eps_output_voltage="220")
    assert compativel_com_cargas(qualquer, None, None)[0]


def test_compativel_com_cargas_ainda_valida_tensao():
    from app.engines.kit_builder import compativel_com_cargas
    so_220 = _FakeProd(meubess_id="m", title="M", eps_output_voltage="220",
                       split_phase=False, phase="monofasico")
    ok, motivo = compativel_com_cargas(so_220, {"127"}, {"monofasico"})
    assert not ok and "127" in motivo


# ── diagnostico: o motor passa a contar o que descartou ───────────────────────
# Os tres bugs encontrados em campo tinham em comum serem SILENCIOSOS. O motor
# ja produzia SkipReason e o servico jogava fora com `kits, _skipped`.

class _Skip:
    def __init__(self, produto_id, titulo, motivo, marca=""):
        self.produto_id, self.titulo, self.motivo = produto_id, titulo, motivo
        self.marca = marca


def _req_com_cargas(**kw):
    carga = {"nome": "Carga", "qtd": 1, "pnom_w": 1000.0, "fp": 1.0, "fd": 1.0,
             "ip_in": 1.0, "tdia_h": 4.0}
    carga.update(kw.pop("carga", {}))
    return CalculateRequest(origem_info=_make_origem_info(), tipo_calculo="backup",
                            cargas_backup=[carga], **kw)


def test_diagnostico_separa_dado_ausente_de_incompatibilidade():
    from app.calculate.service import _montar_diagnostico

    d = _montar_diagnostico(
        [_Skip("a", "Inversor A", "faltam dados do inversor: peak_power_kw"),
         _Skip("b", "Inversor B", "tensão de saída EPS não cadastrada"),
         _Skip("c", "Inversor C", "carga trifásica exige inversor trifásico"),
         _Skip("d", "Inversor D", "saída EPS não atende carga(s) ['127'] V")],
        _req_com_cargas(carga={"tensao": "220", "fase": "monofasico"}), [], False)

    tipos = {x.titulo: x.tipo for x in d.descartados}
    assert tipos["Inversor A"] == "dado_ausente"
    assert tipos["Inversor B"] == "dado_ausente"
    assert tipos["Inversor C"] == "incompativel"
    assert tipos["Inversor D"] == "incompativel"


def test_diagnostico_avisa_quando_a_regra_nao_pode_ser_verificada():
    """Carga sem tensao/fase: a R8 nao roda. Silencio aqui foi o bug da demo."""
    from app.calculate.service import _montar_diagnostico

    d = _montar_diagnostico([], _req_com_cargas(), [], False)
    texto = " ".join(d.avisos)
    assert "sem tensão informada" in texto and "NÃO foi verificada" in texto
    assert "sem fase informada" in texto


def test_diagnostico_nao_avisa_quando_a_regra_rodou():
    from app.calculate.service import _montar_diagnostico

    d = _montar_diagnostico(
        [], _req_com_cargas(carga={"tensao": "220", "fase": "trifasico"}), [], False)
    texto = " ".join(d.avisos)
    assert "sem tensão informada" not in texto
    assert "sem fase informada" not in texto


def test_volume_de_cadastro_incompleto_nao_vira_alerta():
    """Medido em producao: 128 descartes por dado ausente em TODA cotacao, 110
    deles da propria marca do kit — "Cabine de Baterias" e afins classificados
    como bateria. Alerta que sempre aparece faz ignorar o painel inteiro."""
    from app.calculate.service import _montar_diagnostico

    ruido = [_Skip(str(i), f"Cabine de Baterias {i}",
                   "faltam dados da bateria: usable_kwh", "WEG")
             for i in range(110)]
    d = _montar_diagnostico(
        ruido, _req_com_cargas(carga={"tensao": "220", "fase": "monofasico"}),
        [], False, marca_kit="WEG")

    assert d.avisos == []                      # nada de alarme
    assert len(d.descartados) == 110           # mas a lista continua disponivel
    assert all(x.tipo == "dado_ausente" for x in d.descartados)


def test_diagnostico_avisa_inversor_sem_dados_de_entrada_fv():
    """O caso concreto: 8 hibridos sem voc_max/qty_mppt eram tratados como
    incapazes de receber modulos, empurrando FV para um string superdimensionado."""
    from app.calculate.service import _montar_diagnostico

    completo = _FakeProd(title="Com dado", voc_max_voltage=600.0, qty_mppt=3)
    sem = _FakeProd(title="SIW400H T015", voc_max_voltage=None, qty_mppt=None)

    com_pv = _montar_diagnostico([], _req_com_cargas(), [completo, sem], True)
    assert any("sem dados de entrada FV" in a and "SIW400H T015" in a
               for a in com_pv.avisos)

    # sem FV no projeto o aviso nao faz sentido e nao deve poluir
    sem_pv = _montar_diagnostico([], _req_com_cargas(), [completo, sem], False)
    assert not any("entrada FV" in a for a in sem_pv.avisos)


def test_diagnostico_limpo_quando_esta_tudo_certo():
    from app.calculate.service import _montar_diagnostico

    completo = _FakeProd(title="OK", voc_max_voltage=600.0, qty_mppt=3)
    d = _montar_diagnostico(
        [], _req_com_cargas(carga={"tensao": "220", "fase": "monofasico"}),
        [completo], True)
    assert d.avisos == []
    assert d.descartados == []
