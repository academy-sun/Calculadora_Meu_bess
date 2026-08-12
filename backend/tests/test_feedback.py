"""Feedback: gravar sempre, notificar se der."""

from unittest.mock import AsyncMock, patch

import pytest

from app.feedback import email as email_mod
from app.feedback import service
from app.feedback.schemas import FeedbackCreate


def _dados(**kw):
    base = dict(origem="embed", tipo="dimensionamento",
                mensagem="O kit veio com bateria demais para a carga informada.")
    return FeedbackCreate(**{**base, **kw})


def _db():
    db = AsyncMock()
    db.add = lambda o: None
    return db


async def test_grava_antes_de_tentar_o_email():
    """Ordem importa: e-mail que falha não pode levar o relato junto."""
    chamadas = []
    db = _db()
    db.commit = AsyncMock(side_effect=lambda: chamadas.append("commit"))
    with patch.object(email_mod, "enviar",
                      AsyncMock(side_effect=lambda fb: (chamadas.append("email"), (True, None))[1])):
        await service.registrar(db, _dados(), "UA")
    assert chamadas[0] == "commit", chamadas
    assert "email" in chamadas


async def test_falha_de_email_nao_derruba_o_registro():
    """Exceção aqui devolveria 500 depois de gravar, e o autor reenviaria
    achando que não foi."""
    db = _db()
    with patch.object(email_mod, "enviar",
                      AsyncMock(return_value=(False, "SMTPAuthenticationError: 535"))):
        fb = await service.registrar(db, _dados(), "UA")
    assert fb.email_enviado is False
    assert "535" in (fb.email_erro or "")


async def test_mensagem_e_normalizada():
    db = _db()
    with patch.object(email_mod, "enviar", AsyncMock(return_value=(False, None))):
        fb = await service.registrar(db, _dados(mensagem="   texto com espaços   "), None)
    assert fb.mensagem == "texto com espaços"


async def test_sem_smtp_configurado_nao_e_erro_e_sim_estado():
    """Feedback continua valendo sem e-mail — a caixa de entrada é a fonte."""
    with patch.object(email_mod.settings, "feedback_email_to", "a@b.com"), \
         patch.object(email_mod.settings, "smtp_host", ""):
        enviado, motivo = await email_mod.enviar(type("F", (), {
            "origem": "embed", "tipo": None, "autor_nome": None, "autor_email": None,
            "criado_em": None, "url": None, "mensagem": "x", "contexto": None})())
    assert enviado is False
    assert "SMTP_HOST" in motivo


async def test_erro_de_rede_no_smtp_vira_texto_e_nao_excecao():
    with patch.object(email_mod.settings, "feedback_email_to", "a@b.com"), \
         patch.object(email_mod.settings, "smtp_host", "smtp.exemplo"), \
         patch.object(email_mod, "_enviar_sincrono",
                      side_effect=TimeoutError("estourou")):
        enviado, motivo = await email_mod.enviar(type("F", (), {
            "origem": "embed", "tipo": None, "autor_nome": None, "autor_email": None,
            "criado_em": None, "url": None, "mensagem": "x", "contexto": None})())
    assert enviado is False
    assert "TimeoutError" in motivo


def test_mensagem_vazia_e_recusada_no_schema():
    with pytest.raises(Exception):
        FeedbackCreate(origem="embed", mensagem="")


def test_corpo_do_email_leva_o_contexto():
    """É o contexto que permite reproduzir o caso; sem ele o relato é
    irrespondível."""
    corpo = email_mod._corpo(type("F", (), {
        "origem": "embed", "tipo": "dimensionamento", "autor_nome": "Luiz",
        "autor_email": "l@x.com", "criado_em": None, "url": "http://x",
        "mensagem": "kit errado",
        "contexto": {"powerpeak_kwp": 8.5, "kit": "SIW200H M050"}})())
    assert "kit errado" in corpo
    assert "powerpeak_kwp" in corpo and "8.5" in corpo
