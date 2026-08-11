"""Perfil de visualização — o filtro que separa admin de usuário final.

O ponto destes testes é que o filtro é de SERVIDOR: o que o perfil restrito
não pode ver não sai na resposta. Se um dia alguém "otimizar" isso escondendo
só na tela, estes testes caem.
"""

from unittest.mock import patch

import pytest

from app.calculate import perfil as perfil_mod
from app.calculate.schemas import (
    CalculateResponse, Diagnostico, KitInfo, KitItem, ProdutoDescartado,
    SolarDimensionamento,
)


def _resposta_completa() -> CalculateResponse:
    item = KitItem(nome="Bateria X", tipo="bateria", qtd=2,
                   preco_unitario=5987.03, preco_total=11974.06)
    kit = KitInfo(
        marca="WEG", bateria_modelo="CB050", inversor_modelo="M050",
        qtd_baterias=2, capacidade_total_kwh=10.0, potencia_total_kw=6.0,
        preco_total=25989.37, frete_valor=7900.0, total_com_frete=33889.37,
        cobertura_energia=0.97, itens=[item], rotulo_caminho="split",
        alertas=["Carga bifásica atendida por saída monofásica"],
        economia_mensal_rs=1200.0, payback_anos=3.5,
    )
    alt = kit.model_copy(deep=True)
    alt.rotulo = "Alternativa — mais econômica"
    return CalculateResponse(
        tipo_calculo="backup", origem="ploomes", negocio_id="1",
        solicitado_em="2026-01-01T00:00:00Z", calculado_em="2026-01-01T00:00:00Z",
        capacidade_kwh=10.0, potencia_kw=6.0,
        kit_selecionado=kit, alternativas=[alt],
        economia_mensal_rs=1200.0, economia_anual_rs=14400.0, payback_meses=42.0,
        frete={"uf": "AC", "tipo": "cif", "valor": 7900.0,
               "percentual": 8.0, "valor_minimo": 7900.0},
        diagnostico=Diagnostico(
            avisos=["8 inversores híbridos sem dados de entrada FV"],
            descartados=[ProdutoDescartado(
                produto_id="1", titulo="Concorrente Y", motivo="sem spec",
                marca="OUTRA", tipo="dado_ausente")],
        ),
        solar_dimensionamento=SolarDimensionamento(
            modulo_marca="WEG", modulo_modelo="Longi", modulo_wp=635.0,
            qty_modulos=10, n_serie=10, n_paralelo=1, mppt_qty=2,
            kwp_instalado=6.35, cobertura_pct=100.0, preco_modulos_total=6000.0),
    )


class TestResolucaoDoPerfil:
    def test_chave_restrita_da_perfil_restrito(self):
        with patch.object(perfil_mod.settings, "api_key_embed_restrito", "K-REST"), \
             patch.object(perfil_mod.settings, "api_key_embed", "K-ADMIN"):
            assert perfil_mod.resolver("K-REST") == "restrito"

    def test_chaves_de_admin_dao_perfil_completo(self):
        with patch.object(perfil_mod.settings, "api_key_embed_restrito", "K-REST"), \
             patch.object(perfil_mod.settings, "api_key_embed", "K-ADMIN"), \
             patch.object(perfil_mod.settings, "api_key_ploomes", "K-PLOOMES"):
            assert perfil_mod.resolver("K-ADMIN") == "completo"
            assert perfil_mod.resolver("K-PLOOMES") == "completo"

    def test_chave_desconhecida_fecha_em_restrito(self):
        """Variável esquecida no deploy não pode virar acesso completo."""
        with patch.object(perfil_mod.settings, "api_key_embed_restrito", "K-REST"), \
             patch.object(perfil_mod.settings, "api_key_embed", "K-ADMIN"):
            assert perfil_mod.resolver("outra-coisa") == "restrito"
            assert perfil_mod.resolver(None) == "restrito"


class TestPerfilCompleto:
    def test_passa_intacta(self):
        r = perfil_mod.aplicar(_resposta_completa(), "completo")
        assert r.kit_selecionado.itens[0].preco_unitario == 5987.03
        assert r.frete["percentual"] == 8.0
        assert r.diagnostico is not None
        assert r.kit_selecionado.alertas


class TestPerfilRestrito:
    @pytest.fixture
    def r(self):
        return perfil_mod.aplicar(_resposta_completa(), "restrito")

    def test_nao_sai_preco_por_item(self, r):
        it = r.kit_selecionado.itens[0]
        assert (it.preco_unitario, it.preco_total) == (0.0, 0.0)

    def test_nao_sai_preco_do_kit_nem_frete_isolado(self, r):
        assert r.kit_selecionado.preco_total == 0.0
        assert r.kit_selecionado.frete_valor is None

    def test_o_total_com_frete_permanece(self, r):
        """É o único valor em reais que o usuário final precisa ver."""
        assert r.kit_selecionado.total_com_frete == 33889.37

    def test_alternativa_tambem_e_filtrada_e_mantem_total(self, r):
        alt = r.alternativas[0]
        assert alt.preco_total == 0.0
        assert alt.itens[0].preco_unitario == 0.0
        assert alt.total_com_frete == 33889.37

    def test_cobertura_permanece_para_o_alerta(self, r):
        """Sem ela não dá para avisar que o kit cobre menos que o pedido."""
        assert r.alternativas[0].cobertura_energia == 0.97

    def test_frete_perde_valor_percentual_e_minimo(self, r):
        assert set(r.frete) <= {"uf", "tipo", "modalidade"}
        assert "percentual" not in r.frete
        assert "valor" not in r.frete

    def test_diagnostico_nao_sai(self, r):
        assert r.diagnostico is None

    def test_alertas_e_rotulo_interno_nao_saem(self, r):
        assert r.kit_selecionado.alertas is None
        assert r.kit_selecionado.rotulo_caminho is None

    def test_economia_e_payback_nao_saem(self, r):
        assert (r.economia_mensal_rs, r.economia_anual_rs, r.payback_meses) == (None, None, None)
        assert r.kit_selecionado.economia_mensal_rs is None

    def test_preco_dos_modulos_nao_sai(self, r):
        assert r.solar_dimensionamento.preco_modulos_total == 0.0

    def test_nenhum_valor_confidencial_sobra_no_json(self, r):
        """Varredura no JSON serializado — é ele que trafega.

        Um teste campo a campo passa se alguém adicionar um campo novo com
        valor; este pega, porque procura os números no corpo inteiro.
        """
        corpo = r.model_dump_json()
        for confidencial in ("5987.03", "11974.06", "25989.37", "7900.0", "6000.0"):
            assert confidencial not in corpo, f"{confidencial} vazou: {corpo[:400]}"
        assert "33889.37" in corpo, "o total com frete deveria permanecer"
