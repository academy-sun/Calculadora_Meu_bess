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


def _cliente_falso():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"id": "u1"})
    cli = AsyncMock()
    cli.post = AsyncMock(return_value=resp)
    cli.put = AsyncMock(return_value=resp)
    cli.get = AsyncMock(return_value=resp)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=cli)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, cli


@pytest.mark.asyncio
async def test_convite_nao_vai_para_baixo_de_admin():
    """Medido contra o projeto real: POST /auth/v1/admin/invite devolve 404 e
    POST /auth/v1/invite devolve 400 (existe, recusou o corpo vazio)."""
    ctx, cli = _cliente_falso()
    with patch.object(users.httpx, "AsyncClient", return_value=ctx):
        await users.invite_auth_user("a@b.com", "Fulano", "admin", "https://x/y")
    url = cli.post.call_args.args[0]
    assert url.endswith("/auth/v1/invite"), url
    assert "/admin/" not in url, url


@pytest.mark.asyncio
async def test_redirect_to_vai_na_query_e_nao_no_corpo():
    """No corpo o GoTrue ignora em silêncio, e o convidado cai na URL padrão
    do projeto em vez da tela de definir senha."""
    ctx, cli = _cliente_falso()
    with patch.object(users.httpx, "AsyncClient", return_value=ctx):
        await users.invite_auth_user("a@b.com", "Fulano", "admin", "https://x/set-password")
    assert cli.post.call_args.kwargs["params"] == {"redirect_to": "https://x/set-password"}
    assert "redirect_to" not in cli.post.call_args.kwargs["json"]


@pytest.mark.asyncio
async def test_nome_e_papel_viajam_em_data():
    """É de `data` que sai o user_metadata, e é do user_metadata que o backend
    lê o papel (ver auth/dependencies.get_current_user)."""
    ctx, cli = _cliente_falso()
    with patch.object(users.httpx, "AsyncClient", return_value=ctx):
        await users.invite_auth_user("a@b.com", "Thais", "admin", "")
    corpo = cli.post.call_args.kwargs["json"]
    assert corpo["email"] == "a@b.com"
    assert corpo["data"] == {"nome": "Thais", "role": "admin"}


@pytest.mark.asyncio
async def test_as_rotas_de_usuario_continuam_sob_admin():
    """Contraprova: só o convite saiu do /admin."""
    ctx, cli = _cliente_falso()
    with patch.object(users.httpx, "AsyncClient", return_value=ctx):
        await users.update_auth_user("u1", "engineer")
    assert "/auth/v1/admin/users/u1" in cli.put.call_args.args[0]
