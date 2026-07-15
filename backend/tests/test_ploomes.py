"""Testes do módulo app/ploomes (context + pushback) com API Ploomes mockada."""

import json

import httpx
import pytest
import respx

from app.config import settings
from app.ploomes import client, context, pushback
from app.ploomes.schemas import PushbackItem, PushbackRequest

BASE = client.BASE_URL

FIELD_MAP = {
    "powerpeak_kwp": "deal_KWP",
    "fixing_type": "deal_FIX",
    "kit_preco": "deal_PRECO",
    "kit_descricao": "deal_DESC",
    "frete_valor": "deal_FRETE",
    "total_geral": "deal_TOTAL",
}


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(settings, "api_key_ploomes", "test-user-key")
    monkeypatch.setattr(settings, "ploomes_field_map", json.dumps(FIELD_MAP))


def _deal_payload():
    return {
        "value": [{
            "Id": 123,
            "Title": "Negócio Teste",
            "City": {"Name": "Londrina", "State": {"Short": "PR"}},
            "OtherProperties": [
                {"FieldKey": "deal_KWP", "DecimalValue": 8.5},
                {"FieldKey": "deal_FIX", "StringValue": "tile_ceramic"},
                {"FieldKey": "deal_OUTRO", "StringValue": "irrelevante"},
            ],
        }]
    }


class TestContext:
    @respx.mock
    async def test_get_deal_context_mapeia_campos(self):
        respx.get(url__regex=rf"{BASE}/Deals.*").mock(
            return_value=httpx.Response(200, json=_deal_payload())
        )
        ctx = await context.get_deal_context(123)
        assert ctx["deal_id"] == 123
        assert ctx["titulo"] == "Negócio Teste"
        assert ctx["powerpeak_kwp"] == 8.5
        assert ctx["cidade"] == "Londrina"
        assert ctx["uf"] == "PR"
        assert ctx["fixing_type"] == "tile_ceramic"
        assert ctx["field_map_configurado"] is True
        assert {"field_key": "deal_OUTRO", "valor": "irrelevante"} in ctx["raw_fields"]

    @respx.mock
    async def test_deal_inexistente_levanta_404(self):
        respx.get(url__regex=rf"{BASE}/Deals.*").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        with pytest.raises(client.PloomesError) as exc:
            await context.get_deal_context(999)
        assert exc.value.status_code == 404

    @respx.mock
    async def test_sem_field_map_usa_city_nativo(self, monkeypatch):
        monkeypatch.setattr(settings, "ploomes_field_map", "")
        respx.get(url__regex=rf"{BASE}/Deals.*").mock(
            return_value=httpx.Response(200, json=_deal_payload())
        )
        ctx = await context.get_deal_context(123)
        assert ctx["powerpeak_kwp"] is None    # sem mapa não lê custom
        assert ctx["uf"] == "PR"               # mas cidade nativa funciona
        assert ctx["field_map_configurado"] is False


class TestPushback:
    def _req(self, **overrides):
        base = dict(
            deal_id=123,
            kit_descricao="WEG SIW200H + 4× SBW CB100",
            kit_preco=69191.0,
            frete_valor=3100.0,
            frete_descricao="CIF — PR",
            total_geral=72291.0,
            itens=[PushbackItem(nome="Inversor SIW200H", sku="SIW200H", qtd=1, preco_unitario=8654.16)],
        )
        base.update(overrides)
        return PushbackRequest(**base)

    @respx.mock
    async def test_pushback_completo(self):
        patch_deal = respx.patch(f"{BASE}/Deals(123)").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.get(url__regex=rf"{BASE}/Quotes.*").mock(
            return_value=httpx.Response(200, json={"value": [{"Id": 777}]})
        )
        respx.get(url__regex=rf"{BASE}/Products.*").mock(
            return_value=httpx.Response(200, json={"value": [{"Id": 55}]})
        )
        add_quote_product = respx.post(f"{BASE}/Quotes(777)/Products").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.post(f"{BASE}/Interactions").mock(
            return_value=httpx.Response(200, json={})
        )

        report = await pushback.push_result(self._req())

        assert report["campos"]["ok"] is True
        assert report["produtos"]["ok"] is True
        assert report["comentario"]["ok"] is True
        assert add_quote_product.called

        # PATCH levou exatamente os campos mapeados (frete_descricao não está no mapa)
        body = json.loads(patch_deal.calls[0].request.content)
        keys = {p["FieldKey"] for p in body["OtherProperties"]}
        assert keys == {"deal_PRECO", "deal_DESC", "deal_FRETE", "deal_TOTAL"}

    @respx.mock
    async def test_produto_inexistente_e_criado(self):
        respx.patch(f"{BASE}/Deals(123)").mock(return_value=httpx.Response(200, json={}))
        respx.get(url__regex=rf"{BASE}/Quotes.*").mock(
            return_value=httpx.Response(200, json={"value": [{"Id": 777}]})
        )
        respx.get(url__regex=rf"{BASE}/Products.*").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        create_product = respx.post(f"{BASE}/Products").mock(
            return_value=httpx.Response(201, json={"value": [{"Id": 88}]})
        )
        add_qp = respx.post(f"{BASE}/Quotes(777)/Products").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.post(f"{BASE}/Interactions").mock(return_value=httpx.Response(200, json={}))

        report = await pushback.push_result(self._req())

        assert create_product.called
        body = json.loads(add_qp.calls[0].request.content)
        assert body["ProductId"] == 88
        assert report["produtos"]["ok"] is True

    @respx.mock
    async def test_negocio_sem_orcamento_nao_quebra(self):
        respx.patch(f"{BASE}/Deals(123)").mock(return_value=httpx.Response(200, json={}))
        respx.get(url__regex=rf"{BASE}/Quotes.*").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        respx.post(f"{BASE}/Interactions").mock(return_value=httpx.Response(200, json={}))

        report = await pushback.push_result(self._req())

        assert report["campos"]["ok"] is True
        assert report["produtos"]["ok"] is False
        assert "sem orçamento" in report["produtos"]["detalhe"]

    @respx.mock
    async def test_incluir_produtos_false_pula_orcamento(self):
        respx.patch(f"{BASE}/Deals(123)").mock(return_value=httpx.Response(200, json={}))
        respx.post(f"{BASE}/Interactions").mock(return_value=httpx.Response(200, json={}))

        report = await pushback.push_result(self._req(incluir_produtos=False))

        assert report["campos"]["ok"] is True
        assert report["produtos"]["itens"] == []
