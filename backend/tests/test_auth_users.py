"""Chamadas ao GoTrue do Supabase para administrar usuários.

O que estes testes protegem é a FORMA DA URL, não a lógica — porque foi
exatamente aí que quebrou. `/auth/v1/admin/invite` não existe: o convite mora
em `/auth/v1/invite`, sem o `/admin`. As outras rotas de usuário ficam sob
`/admin` mesmo, então a montagem "prefixo + caminho" parecia coerente e
estava errada só para uma delas.

Erro de URL não aparece em revisão nem em type check. Aparece quando alguém
clica em "Enviar convite" e leva um 404 na cara — que foi como este apareceu.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth import users


def _cliente_falso(payload=None):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload or {"id": "u1"})
    cli = AsyncMock()
    cli.post = AsyncMock(return_value=resp)
    cli.put = AsyncMock(return_value=resp)
    cli.get = AsyncMock(return_value=resp)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=cli)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, cli


@pytest.mark.asyncio
async def test_convite_gera_o_link_e_manda_pelo_resend():
    """POST /auth/v1/invite cria E envia — mas quem entrega é o mailer
    embutido do Supabase, que é para desenvolvimento: poucos e-mails por hora
    e entrega ruim para domínio externo. O primeiro convite de verdade deste
    projeto não chegou, sem erro em lugar nenhum.

    generate_link devolve o link e NÃO envia; o envio sai pelo Resend, que é
    o mesmo caminho do feedback e já está provado em produção.
    """
    ctx, cli = _cliente_falso({"action_link": "https://sb/verify?token=abc"})
    with patch.object(users.httpx, "AsyncClient", return_value=ctx),          patch.object(users.emails, "enviar",
                      AsyncMock(return_value=(True, None))) as env:
        r = await users.invite_auth_user("a@b.com", "Thais", "admin", "https://x/set")

    url = cli.post.call_args.args[0]
    assert url.endswith("/auth/v1/admin/generate_link"), url
    assert cli.post.call_args.kwargs["json"]["type"] == "invite"
    # o link tem de chegar ao convidado, e no e-mail dele
    destino, _assunto, corpo = env.call_args.args
    assert destino == "a@b.com"
    assert "https://sb/verify?token=abc" in corpo
    assert r["email_enviado"] is True


@pytest.mark.asyncio
async def test_falha_de_envio_do_convite_e_erro_e_nao_estado():
    """Diferente do feedback: sem o e-mail o convite não serve para nada, e
    quem clicou precisa saber. Não pode virar sucesso silencioso."""
    ctx, _ = _cliente_falso({"action_link": "https://sb/x"})
    with patch.object(users.httpx, "AsyncClient", return_value=ctx),          patch.object(users.emails, "enviar",
                      AsyncMock(return_value=(False, "HTTP 403: not verified"))):
        r = await users.invite_auth_user("a@b.com", "Thais", "admin", "")
    assert r["email_enviado"] is False
    assert "not verified" in r["erro"]


@pytest.mark.asyncio
async def test_redirect_to_vai_para_o_generate_link():
    """É ele que define onde o convidado cai ao clicar — sem isso, a URL
    padrão do projeto em vez da tela de definir senha."""
    ctx, cli = _cliente_falso({"action_link": "https://sb/x"})
    with patch.object(users.httpx, "AsyncClient", return_value=ctx),          patch.object(users.emails, "enviar", AsyncMock(return_value=(True, None))):
        await users.invite_auth_user("a@b.com", "Thais", "admin", "https://x/set-password")
    assert cli.post.call_args.kwargs["json"]["redirect_to"] == "https://x/set-password"


@pytest.mark.asyncio
async def test_nome_e_papel_viajam_em_data():
    """É de `data` que sai o user_metadata, e é do user_metadata que o backend
    lê o papel (ver auth/dependencies.get_current_user)."""
    ctx, cli = _cliente_falso({"action_link": "https://sb/x"})
    with patch.object(users.httpx, "AsyncClient", return_value=ctx),          patch.object(users.emails, "enviar", AsyncMock(return_value=(True, None))):
        await users.invite_auth_user("a@b.com", "Thais", "admin", "")
    assert cli.post.call_args.kwargs["json"]["data"] == {"nome": "Thais", "role": "admin"}


@pytest.mark.asyncio
async def test_as_rotas_de_usuario_continuam_sob_admin():
    """Contraprova: só o convite saiu do /admin."""
    ctx, cli = _cliente_falso()
    with patch.object(users.httpx, "AsyncClient", return_value=ctx):
        await users.update_auth_user("u1", "engineer")
    assert "/auth/v1/admin/users/u1" in cli.put.call_args.args[0]
