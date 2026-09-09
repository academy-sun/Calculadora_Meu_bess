"""Transporte de e-mail (Resend) — o ponto único que fala com o provedor.

Estes testes eram de feedback/email.py. Saíram junto com o transporte quando
o convite de usuário também passou a mandar e-mail: o que eles verificam é o
provedor, não o assunto de quem chama.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app import emails


@pytest.mark.asyncio
async def test_sem_chave_nao_tenta_a_rede():
    with patch.object(emails.settings, "resend_api_key", ""), \
         patch.object(emails.settings, "feedback_email_from", "de@x.com"), \
         patch.object(emails, "_postar", AsyncMock()) as post:
        enviado, motivo = await emails.enviar("a@b.com", "assunto", "corpo")
    assert enviado is False and "RESEND_API_KEY" in motivo
    post.assert_not_called()


@pytest.mark.asyncio
async def test_sem_remetente_nao_tenta_a_rede():
    """Remetente fora do domínio verificado é recusa certa do Resend; sem ele
    configurado, nem vale a chamada."""
    with patch.object(emails.settings, "resend_api_key", "re_x"), \
         patch.object(emails.settings, "feedback_email_from", ""), \
         patch.object(emails, "_postar", AsyncMock()) as post:
        enviado, motivo = await emails.enviar("a@b.com", "assunto", "corpo")
    assert enviado is False and "FEEDBACK_EMAIL_FROM" in motivo
    post.assert_not_called()


@pytest.mark.asyncio
async def test_erro_de_rede_vira_texto_e_nao_excecao():
    """Quem chama decide a gravidade — levantar aqui derrubaria o fluxo de
    quem só queria ser avisado."""
    with patch.object(emails.settings, "resend_api_key", "re_x"), \
         patch.object(emails.settings, "feedback_email_from", "de@x.com"), \
         patch.object(emails, "_postar", AsyncMock(side_effect=TimeoutError("estourou"))):
        enviado, motivo = await emails.enviar("a@b.com", "assunto", "corpo")
    assert enviado is False and "TimeoutError" in motivo


@pytest.mark.asyncio
async def test_recusa_do_resend_chega_legivel():
    """O corpo do erro é a parte útil: "domain is not verified" diz o que
    corrigir, "400 Bad Request" não diz nada."""
    resp = httpx.Response(403, text='{"message":"The domain is not verified"}',
                          request=httpx.Request("POST", emails._URL))
    with patch.object(emails.settings, "resend_api_key", "re_x"), \
         patch.object(emails.settings, "feedback_email_from", "de@x.com"), \
         patch.object(emails, "_postar", AsyncMock(
             side_effect=httpx.HTTPStatusError("erro", request=resp.request, response=resp))):
        enviado, motivo = await emails.enviar("a@b.com", "assunto", "corpo")
    assert enviado is False
    assert "403" in motivo and "not verified" in motivo


@pytest.mark.asyncio
async def test_envia_do_remetente_verificado_para_o_destino():
    enviados = []
    with patch.object(emails.settings, "resend_api_key", "re_x"), \
         patch.object(emails.settings, "feedback_email_from", "calculadora@x.com"), \
         patch.object(emails, "_postar",
                      AsyncMock(side_effect=lambda p: enviados.append(p))):
        enviado, motivo = await emails.enviar("dest@y.com", "Convite", "corpo")
    assert (enviado, motivo) == (True, None)
    assert enviados[0]["from"] == "calculadora@x.com"
    assert enviados[0]["to"] == ["dest@y.com"]
    assert enviados[0]["subject"] == "Convite"
