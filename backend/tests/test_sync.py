"""
Testes para app/catalog/sync.py (réplica fiel + classificação não-destrutiva)

Cobrem:
  1. classify_product()    — cascata de sinais (técnico > categoria > título > fase)
  2. _map_to_raw()         — achatamento do produto MeuBESS em colunas
  3. _fetch_all_products() — fallback de endpoint quando /products/all retorna 5xx
"""

import pytest
import httpx
import respx

from app.catalog.sync import classify_product, _map_to_raw, _fetch_all_products
from app.config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def raw(**kwargs) -> dict:
    """Dict raw mínimo (formato já achatado) para os testes de classify."""
    base = {
        "title": "", "category_title": "", "section": "", "groups": "",
        "phase": "", "battery_inputs": None, "max_eps_power": None,
    }
    base.update(kwargs)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# 1. classify_product — bateria e módulo (por categoria/section)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyBateriaModulo:
    def test_modulo_de_bateria(self):
        tipo, conf, review = classify_product(
            raw(category_title="Módulo de Bateria", title="WEG SBW 5kWh")
        )
        assert tipo == "bateria"
        assert review is False

    def test_cabine_de_baterias(self):
        tipo, _, review = classify_product(raw(category_title="Cabine de Baterias"))
        assert tipo == "bateria"
        assert review is False

    def test_bateria_por_section(self):
        tipo, _, _ = classify_product(raw(section="bat_litio", title="Bateria Lítio"))
        assert tipo == "bateria"

    def test_modulo_por_groups(self):
        tipo, _, review = classify_product(
            raw(groups="Módulo", category_title="Módulo Fotovoltaico", title="Painel 550W")
        )
        assert tipo == "modulo_fv"
        assert review is False

    def test_modulo_por_categoria(self):
        tipo, _, _ = classify_product(raw(category_title="Painel Solar", title="JA 620Wp"))
        assert tipo == "modulo_fv"


# ─────────────────────────────────────────────────────────────────────────────
# 2. classify_product — sinal técnico é ground-truth (confiança alta)
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyTecnico:
    def test_battery_inputs_positivo_e_hibrido(self):
        tipo, conf, review = classify_product(
            raw(battery_inputs=2, category_title="Inversor Trifásico 380 V")
        )
        assert tipo == "inversor_hibrido"
        assert conf == "alta"
        # categoria diz "Trifásico" (string) mas técnico diz híbrido → divergência
        assert review is True

    def test_battery_inputs_zero_e_string(self):
        tipo, conf, review = classify_product(
            raw(battery_inputs=0, category_title="Inversor Monofásico 220 V")
        )
        assert tipo == "inversor_string"
        assert conf == "alta"
        assert review is False  # categoria concorda (string)

    def test_max_eps_power_indica_hibrido(self):
        tipo, conf, _ = classify_product(
            raw(max_eps_power=5.0, category_title="Inversor Híbrido Monofasico 220v")
        )
        assert tipo == "inversor_hibrido"
        assert conf == "alta"

    def test_tecnico_sem_contradicao_nao_revisa(self):
        tipo, conf, review = classify_product(
            raw(battery_inputs=4, category_title="Inversor Híbrido Trifásico 380v",
                title="SIW400H Híbrido", phase="hibrido")
        )
        assert tipo == "inversor_hibrido"
        assert conf == "alta"
        assert review is False  # todos os sinais concordam


# ─────────────────────────────────────────────────────────────────────────────
# 3. classify_product — sem técnico: decide por texto, sempre pede revisão
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifySemTecnico:
    def test_trifasico_220v_e_string_nao_hibrido(self):
        # Caso real que estava errado: deve sair como STRING, não híbrido.
        tipo, conf, review = classify_product(
            raw(category_title="Inversor Trifásico 220 V", groups="Inversor",
                title="WEG - 20,0KW 220V - SIW400G K020 W00 - Inversor Trifásico",
                phase="trifasico")
        )
        assert tipo == "inversor_string"
        assert conf == "media"
        assert review is True  # faltou ground-truth técnico

    def test_categoria_hibrido_sem_tecnico(self):
        tipo, conf, review = classify_product(
            raw(category_title="Inversor Híbrido Monofasico 220v",
                title="SIW200H M050 Híbrido")
        )
        assert tipo == "inversor_hibrido"
        assert conf == "media"
        assert review is True

    def test_hibrido_so_por_titulo(self):
        tipo, conf, review = classify_product(
            raw(title="Inversor Hibrido GOODWE GW6000-ES", category_title="", groups="Inversor")
        )
        assert tipo == "inversor_hibrido"
        assert conf == "baixa"
        assert review is True

    def test_hibrido_so_por_fase(self):
        tipo, conf, review = classify_product(raw(phase="hibrido", title="SIW500H T020"))
        assert tipo == "inversor_hibrido"
        assert conf == "baixa"
        assert review is True

    def test_microinversor_via_categoria_e_string(self):
        tipo, _, _ = classify_product(
            raw(category_title="Microinversor Monofásico 220 V", title="WEG SIW100G")
        )
        assert tipo == "inversor_string"

    def test_indefinido_quando_nenhum_sinal(self):
        tipo, conf, review = classify_product(raw(title="Produto genérico", groups="Outros"))
        assert tipo == "indefinido"
        assert review is True


# ─────────────────────────────────────────────────────────────────────────────
# 4. _map_to_raw — achatamento do produto MeuBESS
# ─────────────────────────────────────────────────────────────────────────────

class TestMapToRaw:
    def test_achata_objetos_aninhados(self):
        product = {
            "id": "WHS656200",
            "title": "WEG 12kW Trifásico",
            "power": "12.0",
            "active": True,
            "battery_inputs": 2,
            "category": {"id": 5, "title": "Inversor Híbrido Trifásico 380v", "section": "general"},
            "brand": {"id": 9, "title": "WEG"},
            "supplier": {"id": 1, "title": "MeuBESS"},
            "images": [{"path": "a.jpg"}],
        }
        out = _map_to_raw(product)
        assert out["meubess_id"] == "WHS656200"
        assert out["power"] == 12.0
        assert out["active"] is True
        assert out["battery_inputs"] == 2
        assert out["category_title"] == "Inversor Híbrido Trifásico 380v"
        assert out["category_section"] == "general"
        assert out["brand_title"] == "WEG"
        assert out["marca"] == "WEG"          # cai no brand.title quando marca ausente
        assert out["supplier_title"] == "MeuBESS"
        assert out["images"] == [{"path": "a.jpg"}]
        # classificação anexada
        assert out["tipo_auto"] == "inversor_hibrido"
        assert out["classificacao_confianca"] == "alta"
        assert "needs_review" in out

    def test_id_numerico_vira_string(self):
        out = _map_to_raw({"id": 1367624546, "title": "x"})
        assert out["meubess_id"] == "1367624546"
        assert isinstance(out["meubess_id"], str)

    def test_campos_ausentes_viram_none(self):
        out = _map_to_raw({"id": "1", "title": "x"})
        assert out["power"] is None
        assert out["battery_inputs"] is None
        assert out["category_title"] is None
        assert out["images"] is None

    def test_marca_direta_tem_prioridade(self):
        out = _map_to_raw({"id": "1", "marca": "WEG", "brand": {"id": 9, "title": "OUTRA"}})
        assert out["marca"] == "WEG"


# ─────────────────────────────────────────────────────────────────────────────
# 5. _fetch_all_products — fallback de endpoint
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTS_ALL_URL = f"{settings.meubess_api_url}/products/all"
PRODUCTS_URL     = f"{settings.meubess_api_url}/products"

SAMPLE_PRODUCTS = [
    {"id": "1", "title": "Bateria WEG 5kWh", "category": {"title": "Módulo de Bateria"}, "active": True},
    {"id": "2", "title": "Inversor Híbrido 10kW", "battery_inputs": 2, "active": True},
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
