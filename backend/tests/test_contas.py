"""Contas: quem pode chamar a calculadora, e como se corta o acesso de uma.

A tabela substitui a comparação contra variáveis de ambiente. A diferença que
importa é operacional — saber de quem é a requisição e revogar UMA conta sem
derrubar as outras.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.contas import service as svc


def test_a_chave_nao_e_guardada_em_claro():
    """Se o banco vazar, as chaves não vazam junto."""
    chave = svc.gerar_chave()
    h = svc.hash_da_chave(chave)
    assert chave not in h
    assert len(h) == 64 and int(h, 16) >= 0     # sha256 hex


def test_hash_e_estavel_entre_chamadas():
    """A busca depende disso: hash instável não acharia a conta nunca."""
    assert svc.hash_da_chave("abc") == svc.hash_da_chave("abc")
    assert svc.hash_da_chave("abc") != svc.hash_da_chave("abd")


def test_chave_gerada_nao_se_repete():
    assert len({svc.gerar_chave() for _ in range(50)}) == 50


def test_chave_tem_entropia_de_sobra_para_dispensar_kdf():
    """32 bytes aleatórios em hex. É o que justifica sha256 puro no lugar de
    um KDF lento: não há dicionário para atacar, e o caminho é quente."""
    assert len(svc.gerar_chave()) == 64


@pytest.mark.asyncio
async def test_chave_vazia_nao_consulta_o_banco():
    """Requisição sem header não pode virar consulta — é o caso mais comum
    de todos (qualquer varredura na URL pública)."""
    db = AsyncMock()
    assert await svc.buscar_por_chave(db, "") is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_semeadura_e_idempotente():
    """Roda a cada boot. Se criasse de novo o que já existe, o deploy
    duplicaria conta a cada reinício."""
    db = AsyncMock()
    db.scalar = AsyncMock(return_value="ja-existe")
    with patch.object(svc.settings, "api_key_embed", "K-ADMIN"), \
         patch.object(svc.settings, "api_key_embed_restrito", "K-REST"):
        assert await svc.semear_do_ambiente(db) == 0
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_semeadura_registra_o_que_falta_com_o_perfil_certo():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    with patch.object(svc.settings, "api_key_embed", "K-ADMIN"), \
         patch.object(svc.settings, "api_key_embed_restrito", "K-REST"):
        assert await svc.semear_do_ambiente(db) == 2
    perfis = {c.args[0].perfil for c in db.add.call_args_list}
    assert perfis == {"completo", "restrito"}
    # O hash é que vai para o banco, nunca a chave.
    hashes = {c.args[0].api_key_hash for c in db.add.call_args_list}
    assert hashes == {svc.hash_da_chave("K-ADMIN"), svc.hash_da_chave("K-REST")}


@pytest.mark.asyncio
async def test_sem_env_nao_semeia_nada():
    """Quando as envs saírem, a semeadura vira inofensiva sozinha."""
    db = AsyncMock()
    with patch.object(svc.settings, "api_key_embed", ""), \
         patch.object(svc.settings, "api_key_embed_restrito", ""):
        assert await svc.semear_do_ambiente(db) == 0


@pytest.mark.asyncio
async def test_criar_devolve_a_chave_uma_vez_e_guarda_so_o_hash():
    db = AsyncMock()
    conta, chave = await svc.criar(db, "Cliente X", "restrito")
    assert conta.api_key_hash == svc.hash_da_chave(chave)
    assert conta.perfil == "restrito"
    assert getattr(conta, "chave", None) is None   # não sobra em lugar nenhum


class TestTodasAsPortasUsamATabela:
    """A migração para a tabela precisa valer em TODAS as rotas, não só no
    /calculate.

    Ficou pela metade uma vez: /calculate passou a resolver na tabela e
    /catalog/loads + /feedback continuaram comparando com as variáveis de
    ambiente. Efeito em campo: a conta do primeiro cliente — que só existe na
    tabela, como toda conta de cliente — levava 401 nas duas. O catálogo de
    cargas apareceu vazio no embed dele, e o botão de feedback parou sem
    reclamar.
    """
    import pytest

    @staticmethod
    def _conta():
        return type("C", (), {"perfil": "restrito", "nome": "Cliente X"})()

    @pytest.mark.asyncio
    async def test_chave_de_conta_abre_catalogo_e_feedback(self):
        from app.auth import dependencies as deps
        with patch.object(deps.contas_svc, "buscar_por_chave",
                          AsyncMock(return_value=self._conta())):
            assert await deps.require_user_or_api_key(None, "K-CLIENTE", None) is None

    @pytest.mark.asyncio
    async def test_chave_fora_da_tabela_e_401(self):
        from fastapi import HTTPException
        from app.auth import dependencies as deps
        with patch.object(deps.contas_svc, "buscar_por_chave",
                          AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as e:
                await deps.require_user_or_api_key(None, "K-QUALQUER", None)
        assert e.value.status_code == 401

    @pytest.mark.asyncio
    async def test_sessao_do_app_interno_continua_valendo(self):
        from fastapi.security import HTTPAuthorizationCredentials
        from app.auth import dependencies as deps
        cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")
        with patch.object(deps, "get_current_user", lambda c: object()):
            assert await deps.require_user_or_api_key(cred, None, None) is None

    @pytest.mark.asyncio
    async def test_sem_nada_e_401(self):
        from fastapi import HTTPException
        from app.auth import dependencies as deps
        with pytest.raises(HTTPException) as e:
            await deps.require_user_or_api_key(None, None, None)
        assert e.value.status_code == 401
