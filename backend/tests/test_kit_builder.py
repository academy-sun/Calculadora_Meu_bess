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

from app.engines.pv_kit import (
    MAX_MATRIZ_DC_AC_HIBRIDO, ModuloAttrs, dc_capacity_modules,
)


class _Inv:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _modulo_550():
    return ModuloAttrs(produto=None, voc_v=50.0, imp_a=13.0, isc_a=13.8, wp=550.0, preco=457.52)


def _siw200h_m075():
    """Hibrido real do catalogo: 7,5 kW CA, 3 MPPT, Voc max 600 V, 1 entrada de
    bateria (e o que marca o produto como hibrido para o teto de matriz)."""
    return FakeProduct(power=7.5, qty_mppt=3, qty_inputs_per_mppt=1,
                       voc_max_voltage=600.0, short_circuit_current_inverter=20.0,
                       battery_inputs=1)


def _string_6kw():
    """Inversor string: sem entrada de bateria."""
    return FakeProduct(power=6.0, qty_mppt=3, qty_inputs_per_mppt=1,
                       voc_max_voltage=600.0, short_circuit_current_inverter=20.0)


def test_teto_de_matriz_do_hibrido_e_o_dobro_da_potencia_ca():
    """Datasheet WEG, "Maxima Potencia da Matriz": M050 5 kW -> 10.000 Wp,
    S075 7,5 kW -> 15.000 Wp. Aqui: 7,5 kW -> 15.000 Wp / 550 = 27 modulos."""
    cap = dc_capacity_modules(_siw200h_m075(), 1, _modulo_550())
    assert cap == 27
    assert cap * 550 / 1000 <= 7.5 * MAX_MATRIZ_DC_AC_HIBRIDO


def test_teto_eletrico_ainda_limita_quando_e_menor():
    """36 modulos cabem eletricamente (12 serie x 3 MPPT), mas a matriz para em 27."""
    assert math.floor(600 / 50) * 1 * 3 == 36
    assert dc_capacity_modules(_siw200h_m075(), 1, _modulo_550()) == 27


def test_caso_reportado_de_17kwp_continua_bloqueado():
    """31 modulos = 17,05 kWp num hibrido de 7,5 kW (matriz max 15 kWp)."""
    assert dc_capacity_modules(_siw200h_m075(), 1, _modulo_550()) < 31


def test_inversor_string_usa_a_razao_menor():
    """String nao tem entrada de bateria: 1,5x, nao 2,0x. 6 kW -> 9 kWp -> 16 modulos."""
    assert dc_capacity_modules(_string_6kw(), 1, _modulo_550()) == 16


def test_dado_do_produto_tem_prioridade_sobre_a_razao():
    """Quando max_pv_power_w existir no cadastro, manda nele."""
    inv = _siw200h_m075()
    inv.max_pv_power_w = 11000.0        # datasheet hipotetico, menor que 2x
    assert dc_capacity_modules(inv, 1, _modulo_550()) == 20   # 11000/550


def test_teto_escala_com_a_quantidade_de_inversores():
    inv, mod = _siw200h_m075(), _modulo_550()
    assert dc_capacity_modules(inv, 2, mod) == 54    # 30 kWp
    # com 3 unidades quem limita volta a ser o eletrico: 36 x 3 = 108 < 81
    assert dc_capacity_modules(inv, 3, mod) == 81


def test_limite_eletrico_continua_valendo_quando_e_o_mais_restritivo():
    """Inversor potente mas com pouca tensao de entrada: quem manda e a tensao."""
    inv = FakeProduct(power=50.0, qty_mppt=1, qty_inputs_per_mppt=1,
                      voc_max_voltage=300.0, short_circuit_current_inverter=20.0,
                      battery_inputs=1)
    assert dc_capacity_modules(inv, 1, _modulo_550()) == 6


def test_sem_potencia_cadastrada_mantem_so_o_limite_eletrico():
    """Nao inventa teto quando o produto nao tem potencia — deixa passar e a
    lacuna fica visivel, como manda a skill."""
    inv = FakeProduct(qty_mppt=3, qty_inputs_per_mppt=1, voc_max_voltage=600.0,
                      short_circuit_current_inverter=20.0, battery_inputs=1)
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


# ═══ AUDITORIA R1–R9 ═════════════════════════════════════════════════════════
# Cada regra da skill com um teste que a PROVA. As duas falhas encontradas em
# campo (R8 so de tensao; R8 contornada no caminho combinado) existiam porque
# ninguem tinha conferido que a regra escrita estava inteira no motor.
# Referencia: .claude/skills/dimensionamento-kit-bess-hibrido/reference/
#             restricoes-composicao-kit.md

class TestR1TetoDeBaterias:
    """total_baterias <= inversor.entradas_bateria x bateria.max_em_paralelo"""

    def test_energia_alem_do_teto_descarta_o_inversor(self):
        # M050: 1 entrada; CB100: 4 em paralelo -> teto 4 baterias (~40 kWh).
        # 45 kWh exigem 5 -> inviavel nesse arranjo.
        kits, skipped = build_kits(
            [m050()], [cb100()], pn_kva=2.0, pp_kva=3.0, e_bat_kwh=45.0)
        assert kits == []
        assert any("energia exige 5 baterias" in s.motivo and "máx 4" in s.motivo
                   for s in skipped)

    def test_no_limite_do_teto_ainda_monta(self):
        kits, _ = build_kits(
            [m050()], [cb100()], pn_kva=2.0, pp_kva=3.0, e_bat_kwh=40.0)
        assert len(kits) == 1
        assert kits[0].qtd_baterias == 4          # exatamente o teto
        assert kits[0].distribuicao_baterias == [4]

    def test_inversor_com_2_entradas_dobra_o_teto(self):
        """T030 tem 2 entradas -> 8 baterias, onde o M050 so aceita 4."""
        kits, _ = build_kits(
            [t030()], [cb100()], pn_kva=2.0, pp_kva=3.0, e_bat_kwh=70.0)
        assert len(kits) == 1
        assert kits[0].qtd_baterias == 7


class TestR2PotenciaPorEntrada:
    """A corrente soma dentro da entrada, mas trunca no teto DELA. Distribuir
    entre entradas entrega mais potencia do que concentrar."""

    def test_potencia_pode_exigir_mais_baterias_que_a_energia(self):
        # Energia pede 1 bateria (10 kWh / 10,07). Mas o pico de 30 kVA nao cabe
        # em 1: dist [1,0] -> min(65,50)=50 A x 384 V = 19,2 kW < 30.
        # Com 2, dist [1,1] -> 100 A = 38,4 kW, limitado ao pico do T030 (36 kW).
        kits, _ = build_kits(
            [t030()], [cb100()], pn_kva=5.0, pp_kva=30.0, e_bat_kwh=10.0)
        assert len(kits) == 1
        assert kits[0].qtd_baterias == 2, "potencia deve mandar quando exige mais que a energia"
        assert kits[0].distribuicao_baterias == [1, 1]
        assert kits[0].pico_entregavel_kw >= 30.0

    def test_distribuir_entrega_mais_potencia_que_concentrar(self):
        """O exemplo do treinamento, verificado pelo motor: 3 baterias em 2
        entradas saem como 2+1, nao 3+0."""
        from app.engines.kit_builder import _distribuir, _pico_dc_kw

        i_entrada, i_pico_bat, tensao = 50.0, 65.0, 384.0
        concentrado = _pico_dc_kw([3, 0], i_entrada, i_pico_bat, tensao)
        distribuido = _pico_dc_kw(_distribuir(3, 2), i_entrada, i_pico_bat, tensao)

        assert _distribuir(3, 2) == [2, 1]
        assert distribuido > concentrado
        assert concentrado == 50.0 * tensao / 1000        # uma entrada saturada
        assert distribuido == 100.0 * tensao / 1000       # duas entradas saturadas

    def test_bateria_extra_na_entrada_saturada_so_agrega_energia(self):
        from app.engines.kit_builder import _pico_dc_kw
        uma = _pico_dc_kw([1], 50.0, 65.0, 384.0)
        duas = _pico_dc_kw([2], 50.0, 65.0, 384.0)
        assert uma == duas, "2a bateria na MESMA entrada nao acrescenta potencia"


class TestR4TetoDeParalelismo:
    """qtd_inversores <= inversor.max_paralelo"""

    def test_pico_alem_do_paralelismo_descarta(self):
        # T015: pico 18 kVA, max 4 unidades -> teto 72 kVA. 100 kVA nao cabe.
        kits, skipped = build_kits(
            [t015()], [cb100()], pn_kva=40.0, pp_kva=100.0, e_bat_kwh=20.0)
        assert kits == []
        assert any("máx paralelo" in s.motivo for s in skipped)

    def test_no_limite_do_paralelismo_ainda_monta(self):
        kits, _ = build_kits(
            [t015()], [cb100()], pn_kva=40.0, pp_kva=72.0, e_bat_kwh=20.0)
        assert kits and kits[0].qtd_inversores == 4


class TestR5CompatibilidadeInversorBateria:
    """A lista do datasheet da bateria e autoritativa; sem ela, faixa de tensao."""

    def test_lista_do_datasheet_bloqueia_inversor_fora_dela(self):
        bat = cb100()
        bat.compatible_inverters = "SIW500X"        # nao inclui SIW200H
        kits, skipped = build_kits(
            [m050()], [bat], pn_kva=2.0, pp_kva=3.0, e_bat_kwh=10.0)
        assert kits == []
        assert any(s.produto_id in ("m050", "cb100") for s in skipped)

    def test_mesma_marca_nao_basta(self):
        """A skill e explicita: nao assumir que mesma marca = compativel."""
        bat = cb100()
        bat.compatible_inverters = "SIW400H"        # so o trifasico
        kits, _ = build_kits([m050(), t015()], [bat],
                             pn_kva=2.0, pp_kva=3.0, e_bat_kwh=10.0)
        assert [k.inversor.meubess_id for k in kits] == ["t015"]

    def test_sem_lista_vale_a_faixa_de_tensao(self):
        bat = cb100()
        bat.compatible_inverters = None
        bat.operating_voltage_min_v = 700           # fora da janela do M050 (80-480)
        bat.operating_voltage_max_v = 900
        kits, skipped = build_kits(
            [m050()], [bat], pn_kva=2.0, pp_kva=3.0, e_bat_kwh=10.0)
        assert kits == []


class TestR6CargaMonoEmTrifasico:
    """Advisory, nao bloqueante — e so quando ha carga mono de verdade."""

    def test_gera_alerta_sem_bloquear(self):
        kits, _ = build_kits(
            [t015()], [cb100()], pn_kva=5.0, pp_kva=10.0, e_bat_kwh=10.0,
            fase_instalacao="trifasico", tensoes_carga={"220"},
            fases_carga={"monofasico", "trifasico"})
        assert kits, "R6 nao pode bloquear"
        assert any("1/3 da potência" in a for a in (kits[0].alertas or []))

    def test_projeto_so_com_carga_trifasica_nao_gera_o_alerta(self):
        """Antes disparava em qualquer projeto trifasico, mesmo sem nenhuma
        carga mono — alerta sem motivo se aprende a ignorar."""
        kits, _ = build_kits(
            [t015()], [cb100()], pn_kva=5.0, pp_kva=10.0, e_bat_kwh=10.0,
            fase_instalacao="trifasico", tensoes_carga={"220"},
            fases_carga={"trifasico"})
        assert kits
        assert not any("1/3 da potência" in a for a in (kits[0].alertas or []))

    def test_carga_bifasica_em_tri_tambem_alerta(self):
        kits, _ = build_kits(
            [t015()], [cb100()], pn_kva=5.0, pp_kva=10.0, e_bat_kwh=10.0,
            fase_instalacao="trifasico", tensoes_carga={"220"},
            fases_carga={"bifasico"})
        assert any("1/3 da potência" in a for a in (kits[0].alertas or []))

    def test_instalacao_mono_nao_gera_o_alerta(self):
        kits, _ = build_kits(
            [m050()], [cb100()], pn_kva=2.0, pp_kva=3.0, e_bat_kwh=10.0,
            fase_instalacao="monofasico", tensoes_carga={"220"})
        assert not any("1/3 da potência" in a for a in (kits[0].alertas or []))


class TestR9CaixaDeJuncao:
    """n_jbw = numero de ENTRADAS com >= 2 baterias em paralelo."""

    def test_uma_bateria_por_entrada_nao_usa_caixa(self):
        kits, _ = build_kits(
            [t030()], [cb100()], pn_kva=5.0, pp_kva=30.0, e_bat_kwh=15.0)
        kit = kits[0]
        assert kit.distribuicao_baterias == [1, 1]
        assert kit.n_caixas_juncao == 0, "1+1 sao ligacoes diretas"

    def test_conta_por_entrada_com_duas_ou_mais(self):
        kits, _ = build_kits(
            [t030()], [cb100()], pn_kva=5.0, pp_kva=30.0, e_bat_kwh=40.0)
        kit = kits[0]
        assert kit.distribuicao_baterias == [2, 2]
        assert kit.n_caixas_juncao == 2


class TestDesempateEntreKits:
    """No catalogo WEG a CB100 custa exatamente o dobro da CB050, entao
    4xCB050 e 2xCB100 empatam no preco. O desempate era a ordem da lista."""

    def _cb050(self, preco=5987.03):
        return FakeProduct(
            meubess_id="cb050", title="SBW CB050 W00", marca="WEG",
            usable_capacity_kwh=5.02, max_parallel_batteries=4,
            max_continuous_current_a=27, peak_discharge_current_a=65,
            nominal_voltage_v=192, operating_voltage_min_v=174,
            operating_voltage_max_v=218, compatible_inverters="SIW200H; SIW400H",
            preco=preco)

    def test_empate_de_preco_prefere_menos_componentes(self):
        # a CB100 real custa exatamente 2x a CB050 (11.974,06 = 2 x 5.987,03)
        kits, _ = build_kits(
            [m050()], [self._cb050(), cb100(preco=2 * 5987.03)],
            pn_kva=2.0, pp_kva=4.5, e_bat_kwh=15.6)
        precos = {k.bateria.meubess_id: k.preco_total for k in kits}
        assert abs(precos["cb050"] - precos["cb100"]) < 0.01, "premissa: empatam"
        assert kits[0].bateria.meubess_id == "cb100"
        assert kits[0].qtd_baterias == 2, "2 modulos em vez de 4, pelo mesmo preco"

    def test_preco_ainda_manda_sobre_a_contagem(self):
        """Menos componentes so desempata; nao inverte uma diferenca de preco."""
        kits, _ = build_kits(
            [m050()], [self._cb050(preco=4000.0), cb100()],
            pn_kva=2.0, pp_kva=4.5, e_bat_kwh=15.6)
        assert kits[0].bateria.meubess_id == "cb050"   # 4x4000 < 2x11974

    def test_ordenacao_e_deterministica(self):
        """Mesma entrada, mesma saida — independente da ordem da lista."""
        a, _ = build_kits([m050()], [self._cb050(), cb100(preco=2 * 5987.03)],
                          pn_kva=2.0, pp_kva=4.5, e_bat_kwh=15.6)
        b, _ = build_kits([m050()], [cb100(preco=2 * 5987.03), self._cb050()],
                          pn_kva=2.0, pp_kva=4.5, e_bat_kwh=15.6)
        assert [k.bateria.meubess_id for k in a] == [k.bateria.meubess_id for k in b]


# ── R8, tensão ENTRE FASES (achado do engenheiro na validação) ────────────────

def k017():
    """SIW400H K017: saída SELECIONÁVEL 380/220 ou 220/127.

    Diferente do T015/T030, ele consegue entregar 220 V entre fases — é o que
    a segunda configuração significa.
    """
    return FakeProduct(
        meubess_id="k017", title="W - WEG - SIW400H K017 - Trifásico", marca="WEG",
        peak_power_kw=19.0, max_eps_power=17.3, battery_inputs=2,
        battery_input_max_current_a=50, max_parallel_units=4, phase="trifasico",
        eps_output_voltage="380/220;220/127", split_phase=False,
        battery_voltage_min_v=150, battery_voltage_max_v=800, preco=15474.38,
    )


class TestTensaoEntreFases:
    """Carga trifásica 220 V não pode receber inversor 380/220.

    '380/220' = 380 V entre fases, 220 V entre fase e neutro. A carga
    trifásica 220 V precisa de 220 V entre fases; esse inversor entrega 380 V
    ali. Antes o par era achatado num conjunto e o '220' fazia a regra passar.
    """
    def _run(self, inversores):
        return build_kits(
            inversores, [cb100()],
            pn_kva=4.0, pp_kva=12.0, e_bat_kwh=32.0,
            fase_instalacao="trifasico", tensoes_carga={"220"},
            fases_carga={"trifasico"}, tensoes_trifasicas={"220"},
        )

    def test_t015_recusado_para_carga_trifasica_220(self):
        kits, skipped = self._run([t015()])
        assert kits == []
        assert any("entre fases" in s.motivo for s in skipped), \
            [s.motivo for s in skipped]

    def test_k017_aceito_para_carga_trifasica_220(self):
        kits, _ = self._run([k017()])
        assert [k.inversor.meubess_id for k in kits] == ["k017"]

    def test_t015_continua_valendo_para_carga_trifasica_380(self):
        """Contraprova: o bloqueio é da tensão, não do modelo."""
        kits, _ = build_kits(
            [t015()], [cb100()],
            pn_kva=4.0, pp_kva=12.0, e_bat_kwh=32.0,
            fase_instalacao="trifasico", tensoes_carga={"380"},
            fases_carga={"trifasico"}, tensoes_trifasicas={"380"},
        )
        assert [k.inversor.meubess_id for k in kits] == ["t015"]

    def test_carga_mono_220_ainda_aceita_saida_380_220(self):
        """Fase-neutro 220 V o 380/220 entrega — só a trifásica é que não."""
        kits, _ = build_kits(
            [t015()], [cb100()],
            pn_kva=4.0, pp_kva=12.0, e_bat_kwh=32.0,
            fase_instalacao="trifasico", tensoes_carga={"220"},
            fases_carga={"monofasico"}, tensoes_trifasicas=None,
        )
        assert [k.inversor.meubess_id for k in kits] == ["t015"]

    def test_entre_fases_ignora_ordem_do_par(self):
        from app.engines.kit_builder import _tensoes_entre_fases
        assert _tensoes_entre_fases("380/220") == {"380"}
        assert _tensoes_entre_fases("380/220;220/127") == {"380", "220"}
        assert _tensoes_entre_fases("127/220") == {"220"}   # ordem invertida
        assert _tensoes_entre_fases("220") == {"220"}
        assert _tensoes_entre_fases(None) == set()
