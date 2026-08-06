"""
Testes do motor de montagem de kit (R1–R9), com os modelos WEG validados.
"""

import math

from app.engines.kit_builder import build_kits


class FakeProduct:
    """Objeto leve que imita MeuBESSProduct (eff() usa getattr com default None)."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


# ── catálogo de teste (specs WEG reais) ───────────────────────────────────────

def cb100(preco=11974.0):
    return FakeProduct(
        meubess_id="cb100", title="SBW CB100 W00", marca="WEG",
        usable_capacity_kwh=10.07, max_parallel_batteries=4,
        max_continuous_current_a=27, peak_discharge_current_a=65,
        nominal_voltage_v=384, operating_voltage_min_v=348, operating_voltage_max_v=436.8,
        compatible_inverters="SIW200H; SIW400H", preco=preco,
    )

def m050():
    return FakeProduct(
        meubess_id="m050", title="W - WEG - SIW200H M050 - Inversor Híbrido", marca="WEG",
        peak_power_kw=6.0, max_eps_power=5.0, battery_inputs=1,
        battery_input_max_current_a=40, max_parallel_units=5,
        eps_output_voltage="220", split_phase=False,
        battery_voltage_min_v=80, battery_voltage_max_v=480, preco=6919.0,
    )

def s057():
    return FakeProduct(
        meubess_id="s057", title="W - WEG - SIW200H S057 - SplitPhase", marca="WEG",
        peak_power_kw=7.695, max_eps_power=5.7, battery_inputs=1,
        battery_input_max_current_a=50, max_parallel_units=4,
        eps_output_voltage="127/220", split_phase=True,
        battery_voltage_min_v=85, battery_voltage_max_v=460, preco=7560.0,
    )

def t015():
    return FakeProduct(
        meubess_id="t015", title="W - WEG - SIW400H T015 - Trifásico", marca="WEG",
        peak_power_kw=18.0, max_eps_power=15.0, battery_inputs=2,
        battery_input_max_current_a=50, max_parallel_units=4,
        eps_output_voltage="380/220", split_phase=False,
        battery_voltage_min_v=150, battery_voltage_max_v=800, preco=14715.0,
    )

def t030():
    return FakeProduct(
        meubess_id="t030", title="W - WEG - SIW400H T030 - Trifásico", marca="WEG",
        peak_power_kw=36.0, max_eps_power=30.0, battery_inputs=2,
        battery_input_max_current_a=50, max_parallel_units=4,
        eps_output_voltage="380/220", split_phase=False,
        battery_voltage_min_v=150, battery_voltage_max_v=800, preco=17932.0,
    )


# ── Residencial monofásico (mistura 127/220 → exige split-phase) ──────────────

class TestResidencial:
    def _run(self):
        return build_kits(
            [m050(), s057()], [cb100()],
            pn_kva=2.40, pp_kva=4.33, e_bat_kwh=13.5,
            fase_instalacao="monofasico", tensoes_carga={"127", "220"},
        )

    def test_split_phase_e_escolhido_e_m050_descartado(self):
        kits, skipped = self._run()
        assert kits, "deveria haver ao menos um kit viável"
        melhor = kits[0]
        assert melhor.inversor.meubess_id == "s057"  # split-phase, não o M050
        # M050 (EPS só 220) descartado por R8 (não atende 127 V)
        assert any(s.produto_id == "m050" and "127" in s.motivo for s in skipped)

    def test_duas_baterias_e_uma_caixa_de_juncao(self):
        kits, _ = self._run()
        melhor = kits[0]
        assert melhor.qtd_baterias == 2          # energia manda (13,5 kWh / 10,07)
        assert melhor.qtd_inversores == 1
        assert melhor.distribuicao_baterias == [2]
        assert melhor.n_caixas_juncao == 1
        assert melhor.pico_entregavel_kw >= 4.33


# ── Comercial trifásico ───────────────────────────────────────────────────────

class TestComercial:
    def _run(self):
        return build_kits(
            [t015(), t030()], [cb100()],
            pn_kva=8.67, pp_kva=22.4, e_bat_kwh=22.2,
            fase_instalacao="trifasico", tensoes_carga={"220", "380"},
        )

    def test_t030_single_3_baterias_distribuidas_2_1(self):
        kits, _ = self._run()
        kit_t030 = next(k for k in kits if k.inversor.meubess_id == "t030")
        assert kit_t030.qtd_inversores == 1
        assert kit_t030.qtd_baterias == 3              # energia (22,2 / 10,07)
        assert kit_t030.distribuicao_baterias == [2, 1]  # 2 numa entrada, 1 na outra
        assert kit_t030.n_caixas_juncao == 1            # só a entrada com 2 baterias
        assert kit_t030.pico_entregavel_kw >= 22.4

    def test_t015_escala_para_2_inversores_no_pico(self):
        kits, _ = self._run()
        kit_t015 = next((k for k in kits if k.inversor.meubess_id == "t015"), None)
        assert kit_t015 is not None
        # pico 22,4 > 18 kVA de um T015 → precisa de 2 em paralelo (R4)
        assert kit_t015.qtd_inversores == 2


# ── Restrições de dado / tensão ───────────────────────────────────────────────

class TestRestricoes:
    def test_inversor_sem_pico_e_descartado_com_motivo(self):
        inv_incompleto = FakeProduct(
            meubess_id="x", title="Inversor sem specs", marca="WEG",
            battery_inputs=1, battery_input_max_current_a=50, max_eps_power=5,
        )  # falta peak_power_kw
        kits, skipped = build_kits(
            [inv_incompleto], [cb100()],
            pn_kva=2.0, pp_kva=3.0, e_bat_kwh=10.0,
        )
        assert kits == []
        assert any(s.produto_id == "x" and "peak_power_kw" in s.motivo for s in skipped)

    def test_r8_bloqueia_carga_127_em_inversor_220(self):
        kits, skipped = build_kits(
            [m050()], [cb100()],
            pn_kva=2.0, pp_kva=3.0, e_bat_kwh=10.0,
            tensoes_carga={"127"},
        )
        assert kits == []
        assert any(s.produto_id == "m050" for s in skipped)

    def test_sem_tensao_carga_nao_bloqueia_por_r8(self):
        # Sem tensões de carga informadas, R8 não filtra (pendência, não erro).
        kits, _ = build_kits(
            [m050()], [cb100()],
            pn_kva=2.0, pp_kva=3.0, e_bat_kwh=10.0,
        )
        assert kits, "sem tensão de carga, M050 deve montar kit normalmente"


class TestR7Rede:
    def test_inversor_tri_em_unidade_mono_gera_alerta(self):
        kits, _ = build_kits(
            [t030()], [cb100()],
            pn_kva=8.0, pp_kva=20.0, e_bat_kwh=20.0,
            fase_instalacao="monofasico", padrao_entrada="mono_220",
        )
        assert kits
        assert any("trifásico em unidade monofásica" in a.lower() or "monofásica" in a
                   for a in kits[0].alertas)

    def test_autotransformador_127_220_com_inversor_380(self):
        kits, _ = build_kits(
            [t030()], [cb100()],
            pn_kva=8.0, pp_kva=20.0, e_bat_kwh=20.0,
            fase_instalacao="trifasico", padrao_entrada="tri_127_220",
        )
        assert kits
        assert any("autotransformador" in a.lower() for a in kits[0].alertas)

    def test_tri_em_unidade_tri_380_sem_alerta_de_rede(self):
        kits, _ = build_kits(
            [t030()], [cb100()],
            pn_kva=8.0, pp_kva=20.0, e_bat_kwh=20.0,
            fase_instalacao="trifasico", padrao_entrada="tri_220_380",
        )
        assert kits
        assert not any("autotransformador" in a.lower() or "monofásica" in a
                       for a in kits[0].alertas)


# ── teto de potencia CC do inversor ───────────────────────────────────────────
# Reportado em campo: kit com inversor hibrido de 7,5 kW recebendo 17,05 kWp de
# FV (DC/AC 2,3). dc_capacity_modules validava so tensao/corrente, nunca a
# potencia que o inversor consegue processar.

from app.engines.pv_kit import ModuloAttrs, OVERSIZE_DC_AC, dc_capacity_modules


class _Inv:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _modulo_550():
    return ModuloAttrs(produto=None, voc_v=50.0, imp_a=13.0, isc_a=13.8, wp=550.0, preco=457.52)


def _siw200h_m075():
    """Valores reais do catalogo: 7,5 kW, 3 MPPT, 1 entrada/MPPT, Voc max 600 V."""
    return _Inv(power=7.5, qty_mppt=3, qty_inputs_per_mppt=1,
                voc_max_voltage=600.0, short_circuit_current_inverter=20.0)


def test_capacidade_cc_limitada_pela_potencia_e_nao_so_pela_tensao():
    inv, mod = _siw200h_m075(), _modulo_550()
    # eletricamente caberiam 12 em serie x 1 x 3 MPPT = 36 modulos (19,8 kWp)
    assert math.floor(600 / 50) * 1 * 3 == 36
    cap = dc_capacity_modules(inv, 1, mod)
    # 7,5 kW x 1,5 = 11,25 kWp -> 20 modulos de 550 Wp
    assert cap == 20
    assert cap * mod.wp / 1000 <= 7.5 * OVERSIZE_DC_AC


def test_capacidade_cc_nao_permite_o_caso_reportado_de_17kwp():
    """31 modulos de 550 Wp = 17,05 kWp num inversor de 7,5 kW."""
    assert dc_capacity_modules(_siw200h_m075(), 1, _modulo_550()) < 31


def test_teto_de_potencia_escala_com_a_quantidade_de_inversores():
    inv, mod = _siw200h_m075(), _modulo_550()
    assert dc_capacity_modules(inv, 2, mod) == 40   # 15 kW x 1,5 = 22,5 kWp
    # com 3 unidades o limite volta a ser o eletrico (36 x 3 = 108 < 61 x ...)
    assert dc_capacity_modules(inv, 3, mod) == 61


def test_limite_eletrico_continua_valendo_quando_e_o_mais_restritivo():
    """Inversor potente mas com pouca tensao de entrada: quem manda e a tensao."""
    inv = _Inv(power=50.0, qty_mppt=1, qty_inputs_per_mppt=1,
               voc_max_voltage=300.0, short_circuit_current_inverter=20.0)
    # 6 em serie x 1 x 1 = 6 modulos, bem abaixo do teto de potencia
    assert dc_capacity_modules(inv, 1, _modulo_550()) == 6


def test_sem_potencia_cadastrada_mantem_so_o_limite_eletrico():
    """Nao inventa teto quando o produto nao tem potencia — sinaliza a lacuna
    deixando passar, como manda a skill, em vez de bloquear silenciosamente."""
    inv = _Inv(qty_mppt=3, qty_inputs_per_mppt=1, voc_max_voltage=600.0,
               short_circuit_current_inverter=20.0)
    assert dc_capacity_modules(inv, 1, _modulo_550()) == 36


def test_isc_incompativel_continua_bloqueando():
    inv = _siw200h_m075()
    inv.short_circuit_current_inverter = 10.0    # menor que a Isc do modulo
    assert dc_capacity_modules(inv, 1, _modulo_550()) == 0


# ── R8, lado FASE: carga trifasica x inversor monofasico ──────────────────────
# Reportado em campo: ar condicionado TRIFASICO 220 V retornou inversor
# MONOfasico 220 V. A checagem de tensao sozinha aceitava, porque toda carga
# trifasica do catalogo e 220 V e o inversor mono "atende 220 V".
#
# Usa os mesmos fixtures WEG do resto do arquivo: m050 = mono 220,
# s057 = split-phase 127/220, t015 = trifasico 380/220.

def _montar_por_fase(inversores, fases, tensoes={"220"}):
    return build_kits(
        inversores, [cb100()],
        pn_kva=2.5, pp_kva=5.0, e_bat_kwh=10.0,
        fase_instalacao="trifasico", tensoes_carga=set(tensoes),
        fases_carga=(set(fases) if fases is not None else None),
        padrao_entrada="tri_220_380",
    )


def test_carga_trifasica_descarta_inversor_monofasico():
    """O caso reportado: nenhum kit mono pode sobrar."""
    kits, skipped = _montar_por_fase([m050()], {"trifasico"})
    assert kits == []
    assert any("trifásica exige inversor trifásico" in s.motivo for s in skipped)


def test_carga_trifasica_aceita_inversor_trifasico():
    kits, _ = _montar_por_fase([t015()], {"trifasico"})
    assert len(kits) == 1
    assert kits[0].inversor.meubess_id == "t015"


def test_carga_trifasica_escolhe_o_tri_mesmo_sendo_mais_caro():
    kits, _ = _montar_por_fase([m050(), t015()], {"trifasico"})
    assert [k.inversor.meubess_id for k in kits] == ["t015"]


def test_split_phase_nao_serve_carga_trifasica():
    """Split-phase tem duas fases, nao tres."""
    kits, skipped = _montar_por_fase([s057()], {"trifasico"})
    assert kits == []
    assert any("trifásica" in s.motivo for s in skipped)


def test_carga_monofasica_continua_aceitando_inversor_mono():
    """A regra nova nao pode estreitar o que ja funcionava."""
    kits, _ = _montar_por_fase([m050()], {"monofasico"})
    assert len(kits) == 1


def test_mistura_mono_e_trifasica_exige_o_trifasico():
    kits, _ = _montar_por_fase([m050(), t015()], {"monofasico", "trifasico"})
    assert [k.inversor.meubess_id for k in kits] == ["t015"]


def test_sem_fase_informada_o_motor_nao_bloqueia_nada():
    """Cotacao antiga, sem fase nas cargas: comportamento anterior preservado."""
    kits, _ = _montar_por_fase([m050()], None)
    assert len(kits) == 1


def test_fase_com_acento_e_maiuscula_e_normalizada_no_service():
    from app.calculate.service import _normalizar_fase
    assert _normalizar_fase("Trifásico") == "trifasico"
    assert _normalizar_fase("TRIFASICO") == "trifasico"
    assert _normalizar_fase("Bifásico") == "bifasico"
    assert _normalizar_fase(None) == ""


# ── carga bifasica ────────────────────────────────────────────────────────────

def test_carga_bifasica_nao_bloqueia_mas_alerta_em_saida_mono():
    kits, _ = _montar_por_fase([m050()], {"bifasico"})
    assert len(kits) == 1
    assert any("bifásica" in a for a in (kits[0].alertas or []))


def test_carga_bifasica_em_split_phase_nao_alerta():
    kits, _ = _montar_por_fase([s057()], {"bifasico"})
    assert len(kits) == 1
    assert not any("bifásica" in a for a in (kits[0].alertas or []))


def test_carga_bifasica_em_trifasico_nao_alerta():
    kits, _ = _montar_por_fase([t015()], {"bifasico"})
    assert len(kits) == 1
    assert not any("bifásica" in a for a in (kits[0].alertas or []))
