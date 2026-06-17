"""
Testes para app/catalog/sync.py

Cobrem três comportamentos:
  1. _classify()      — classificação correta de produtos por groups/title
  2. _enrich_modelo() — enriquecimento do nome do modelo com potência
  3. _fetch_all_products() — fallback de endpoint quando /products/all retorna 5xx
"""

import pytest
import httpx
import respx

from app.catalog.sync import _classify, _enrich_modelo, _fetch_all_products
from app.config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def product(groups="", app="", title="", active=True):
    """Constrói um dict mínimo de produto para os testes."""
    return {"id": "1", "groups": groups, "app": app, "title": title, "active": active}


# ─────────────────────────────────────────────────────────────────────────────
# 1. _classify — produtos que DEVEM ser classificados
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyBateria:
    def test_battery_group(self):
        assert _classify(product(groups="battery")) == ("bess", "bateria")

    def test_battery_storage_group(self):
        assert _classify(product(groups="battery_storage")) == ("bess", "bateria")

    def test_storage_group(self):
        assert _classify(product(groups="storage")) == ("bess", "bateria")

    def test_bateria_pt(self):
        assert _classify(product(groups="bateria")) == ("bess", "bateria")


class TestClassifyInversorHibrido:
    def test_inverter_group(self):
        assert _classify(product(groups="inverter", title="WEG SIW400H T030 Inversor Hibrido")) == ("bess", "inversor_hibrido")

    def test_hybrid_group(self):
        assert _classify(product(groups="hybrid", title="Inversor Hibrido 5kW")) == ("bess", "inversor_hibrido")

    def test_off_grid_group(self):
        assert _classify(product(groups="off_grid", title="Inversor Off-Grid 10kW")) == ("bess", "inversor_hibrido")

    def test_hibrido_pt(self):
        assert _classify(product(groups="hibrido", title="Sofar 10kW Hibrido")) == ("bess", "inversor_hibrido")


class TestClassifyInversorSolar:
    def test_string_inverter_group(self):
        assert _classify(product(groups="string_inverter", title="Sungrow 10kW")) == ("solar", "inversor_solar")

    def test_on_grid_group(self):
        assert _classify(product(groups="on_grid", title="Deye 5kW")) == ("solar", "inversor_solar")

    def test_microinversor_dentro_de_inverter_group(self):
        # Micro-inversor com groups="inverter" deve ir para solar, não bess
        assert _classify(product(groups="inverter", title="Microinversor 600W")) == ("solar", "inversor_solar")

    def test_micro_inversor_com_espaco(self):
        assert _classify(product(groups="inverter", title="Micro Inversor 2,5kW 220V")) == ("solar", "inversor_solar")


class TestClassifyModuloFV:
    def test_panel_group(self):
        assert _classify(product(groups="panel", title="Painel Solar 550W")) == ("solar", "modulo_fv")

    def test_module_group(self):
        assert _classify(product(groups="module", title="Módulo FV 400W")) == ("solar", "modulo_fv")

    def test_app_solar_fallback(self):
        assert _classify(product(groups="", app="solar", title="Painel 400W")) == ("solar", "modulo_fv")


# ─────────────────────────────────────────────────────────────────────────────
# 2. _classify — produtos que DEVEM ser ignorados (skip)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifySkip:
    @pytest.mark.parametrize("title", [
        "Cabo Solar 6mm",
        "Cabo Solar 4mm Preto",
        "Conector MC4 6 mm²",
        " MC4 fêmea 4mm",
        "Estrutura de Solo para 8 Módulos",
        "Estrutura Carport Galvanizada a Fogo",
        "CCM - Estruturas Metálicas",
        "Fixador Final Alumínio",
        "Grampo Intermediário Telhado",
        "P - Parafuso Auto Brocante INOX 5,5x25",
        "Porca Serrilhada M8",
        "Trilho H Alumínio 4,2m",
        "Perfil Mini Trilho Alto Alumínio 32cm",
        "Haste Fibromadeira INOX 250mm",
        "Monitoramento IED202",
        "Gateway WEG ED100 Trifásico",
        "Emenda U para Trilho H Completa",
        "Abrigo de Inversor Metálico",
    ])
    def test_acessorio_ignorado(self, title):
        # Mesmo que groups seja "inverter", itens de acessório devem ser ignorados
        result = _classify(product(groups="inverter", title=title))
        assert result == (None, None), f"Deveria ser ignorado: '{title}'"

    def test_groups_desconhecido_sem_app(self):
        assert _classify(product(groups="accessory", title="Cabo DC")) == (None, None)

    def test_groups_vazio_sem_app(self):
        assert _classify(product(groups="", app="")) == (None, None)


def product_meubess(groups="Inversor", app="bess", title="", cat_title="", active=True):
    """Constrói produto no formato real da API MeuBESS (com category object)."""
    return {
        "id": "1",
        "groups": groups,
        "app": app,
        "title": title,
        "active": active,
        "category": {"title": cat_title} if cat_title else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2b. _classify — formato MeuBESS português (category.title)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyMeuBESSPortugues:
    """Testa roteamento usando category.title — formato real da API MeuBESS."""

    # Baterias
    def test_modulo_de_bateria(self):
        p = product_meubess(groups="Acessórios", cat_title="Módulo de Bateria",
                            title="WEG SBW 5kWh")
        assert _classify(p) == ("bess", "bateria")

    def test_cabine_de_baterias(self):
        p = product_meubess(groups="Acessórios", cat_title="Cabine de Baterias",
                            title="WEG CB100")
        assert _classify(p) == ("bess", "bateria")

    # Inversores híbridos (categoria explícita)
    def test_inversor_hibrido_monofasico(self):
        p = product_meubess(groups="Inversor", cat_title="Inversor Híbrido Monofasico 220v",
                            title="W - WEG - 5,0KW 220V - SIW200H M050 W00 - Inversor Híbrido")
        assert _classify(p) == ("bess", "inversor_hibrido")

    def test_inversor_hibrido_trifasico_220v(self):
        p = product_meubess(groups="Inversor", cat_title="Inversor Híbrido Trifásico 220v",
                            title="W - WEG - SIW400H K017 T030 W20")
        assert _classify(p) == ("bess", "inversor_hibrido")

    def test_inversor_hibrido_trifasico_380v(self):
        p = product_meubess(groups="Inversor", cat_title="Inversor Híbrido Trifásico 380v",
                            title="W - WEG - 15,0KW 380V - SIW400H T015 W10 - Inversor Híbrido Trifásico")
        assert _classify(p) == ("bess", "inversor_hibrido")

    # SplitPhase com app=bess → híbrido (ex: WEG SIW200H SplitPhase)
    def test_splitphase_bess_app_classifica_como_hibrido(self):
        p = product_meubess(groups="Inversor", app="bess",
                            cat_title="Inversor SplitPhase 127/220V",
                            title="W - WEG SIW200H S075 W20 - Inversor Monofásico 127/220V")
        assert _classify(p) == ("bess", "inversor_hibrido")

    def test_splitphase_sem_bess_app_classifica_como_solar(self):
        p = product_meubess(groups="Inversor", app="sunhub",
                            cat_title="Inversor SplitPhase 127/220V",
                            title="SIW100G SplitPhase")
        assert _classify(p) == ("solar", "inversor_solar")

    # Inversores string (Monofásico/Trifásico sem Híbrido) → solar
    def test_inversor_monofasico_220v_e_string(self):
        p = product_meubess(groups="Inversor", cat_title="Inversor Monofásico 220 V",
                            title="W - WEG - 5,0KW 220V - SIW300 M050 - Inversor Monofásico")
        assert _classify(p) == ("solar", "inversor_solar")

    def test_inversor_trifasico_380v_e_string(self):
        p = product_meubess(groups="Inversor", cat_title="Inversor Trifásico 380 V",
                            title="Huawei SUN2000 15KTL")
        assert _classify(p) == ("solar", "inversor_solar")

    def test_inversor_bomba_ignorado(self):
        p = product_meubess(groups="Inversor", cat_title="Inversor p/ bomba trifásica",
                            title="Sungrow SG15RT-V112")
        assert _classify(p) == (None, None)

    def test_microinversor_via_categoria(self):
        p = product_meubess(groups="Inversor", cat_title="Microinversor Monofásico 220 V",
                            title="W - WEG - 2,4KW 220V - SIW100G M024 W10 - Microinversor")
        assert _classify(p) == ("solar", "inversor_solar")

    # Módulos FV
    def test_modulo_fv_grupo_modulo(self):
        p = product_meubess(groups="Módulo", cat_title="Módulo Fotovoltaico",
                            title="Painel Solar 550W Bifacial")
        assert _classify(p) == ("solar", "modulo_fv")

    # Acessórios sem categoria de bateria → ignorar
    def test_acessorio_sem_categoria_bateria_ignorado(self):
        p = product_meubess(groups="Acessórios", cat_title="String Box",
                            title="String Box 4E/2S 1000VCC")
        assert _classify(p) == (None, None)


# ─────────────────────────────────────────────────────────────────────────────
# 3. _enrich_modelo — enriquecimento do modelo com potência
# ─────────────────────────────────────────────────────────────────────────────

class TestEnrichModelo:
    def test_adiciona_potencia_quando_ausente(self):
        result = _enrich_modelo("SOFAR", 10.0, "inversor_hibrido")
        assert "10kW" in result or "10" in result

    def test_nao_duplica_potencia_ja_presente(self):
        result = _enrich_modelo("SOFAR 10kW", 10.0, "inversor_hibrido")
        # Não deve virar "SOFAR 10kW 10kW"
        assert result.count("10") == 1

    def test_nao_altera_bateria(self):
        # Baterias não precisam de potência no modelo
        result = _enrich_modelo("SBW CB050", 5.0, "bateria")
        assert result == "SBW CB050"

    def test_nao_altera_quando_power_none(self):
        result = _enrich_modelo("SIW400H T030", None, "inversor_hibrido")
        assert result == "SIW400H T030"

    def test_nao_altera_modelo_com_kva(self):
        result = _enrich_modelo("25,0KW 220V", 25.0, "inversor_hibrido")
        # Já contém indicador de potência, não altera
        assert result == "25,0KW 220V"

    def test_formatos_variados_de_potencia(self):
        # Cada variante deve ter a potência adicionada e ser distinta entre si
        resultados = set()
        for power, modelo_base in [(4.0, "SOFAR"), (7.5, "SOFAR"), (10.0, "SOFAR")]:
            result = _enrich_modelo(modelo_base, power, "inversor_hibrido")
            assert result != modelo_base, f"Potência não adicionada para {power}kW"
            assert "kW" in result or "kw" in result.lower(), f"Unidade kW não encontrada em '{result}'"
            resultados.add(result)
        # Os três modelos enriquecidos devem ser distintos entre si
        assert len(resultados) == 3, "Inversores com potências diferentes geraram nomes idênticos"


# ─────────────────────────────────────────────────────────────────────────────
# 4. _fetch_all_products — fallback de endpoint
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTS_ALL_URL = f"{settings.meubess_api_url}/products/all"
PRODUCTS_URL     = f"{settings.meubess_api_url}/products"

SAMPLE_PRODUCTS = [
    {"id": "1", "title": "Bateria WEG 5kWh", "groups": "battery", "power": 5.0, "active": True},
    {"id": "2", "title": "Inversor Hibrido 10kW", "groups": "inverter", "power": 10.0, "active": True},
]


@pytest.mark.asyncio
class TestFetchAllProductsFallback:
    async def test_usa_products_all_quando_funciona(self):
        with respx.mock:
            respx.get(PRODUCTS_ALL_URL).mock(
                return_value=httpx.Response(200, json=SAMPLE_PRODUCTS)
            )
            async with httpx.AsyncClient() as client:
                result = await _fetch_all_products(client)
        assert len(result) == 2

    async def test_fallback_para_products_quando_all_retorna_500(self):
        with respx.mock:
            respx.get(PRODUCTS_ALL_URL).mock(
                return_value=httpx.Response(500, json={"message": "Server Error"})
            )
            respx.get(PRODUCTS_URL).mock(
                return_value=httpx.Response(200, json=SAMPLE_PRODUCTS)
            )
            async with httpx.AsyncClient() as client:
                result = await _fetch_all_products(client)
        assert len(result) == 2

    async def test_nao_silencia_erro_401_em_products_all(self):
        """Um 401 (chave inválida) não deve tentar o próximo endpoint — deve propagar."""
        with respx.mock:
            respx.get(PRODUCTS_ALL_URL).mock(
                return_value=httpx.Response(401, json={"message": "Unauthenticated."})
            )
            async with httpx.AsyncClient() as client:
                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    await _fetch_all_products(client)
        assert exc_info.value.response.status_code == 401

    async def test_levanta_erro_quando_ambos_endpoints_falham(self):
        with respx.mock:
            respx.get(PRODUCTS_ALL_URL).mock(
                return_value=httpx.Response(500, json={"message": "Server Error"})
            )
            respx.get(PRODUCTS_URL).mock(
                return_value=httpx.Response(503, json={"message": "Service Unavailable"})
            )
            async with httpx.AsyncClient() as client:
                with pytest.raises(ValueError, match="Nenhum endpoint"):
                    await _fetch_all_products(client)
