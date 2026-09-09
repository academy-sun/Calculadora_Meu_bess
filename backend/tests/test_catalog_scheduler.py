"""Agendador do sync periódico do catálogo."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.catalog import scheduler


def test_desligado_quando_intervalo_zero():
    with patch.object(scheduler.settings, "sync_intervalo_segundos", 0):
        assert scheduler.iniciar(None) is None


def test_desligado_sem_api_key():
    """Sem credencial o sync falharia em toda rodada — melhor nem agendar."""
    with patch.object(scheduler.settings, "sync_intervalo_segundos", 3600), \
         patch.object(scheduler.settings, "meubess_api_key", ""):
        assert scheduler.iniciar(None) is None


def _duplas_falsas(obteve_lock=True):
    """Devolve (engine, conexao_do_lock, sessao_do_sync).

    Separadas de propósito: o teste que importa é que o lock NÃO encoste na
    sessão do sync. Enquanto os dois compartilhavam a conexão, o commit de
    dentro do sync devolvia a conexão ao pool e o unlock saía em outra.
    """
    def _ctx(valor):
        alvo = AsyncMock()
        resultado = AsyncMock()
        resultado.scalar = lambda: valor
        alvo.execute = AsyncMock(return_value=resultado)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=alvo)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx, alvo

    ctx_lock, conexao = _ctx(obteve_lock)
    ctx_sync, sessao = _ctx(None)
    engine = AsyncMock()
    engine.connect = lambda: ctx_lock
    return engine, conexao, ctx_sync, sessao


def _sqls(alvo):
    return [str(c.args[0]) for c in alvo.execute.call_args_list]


def test_pula_quando_outra_instancia_tem_o_lock():
    """Duas réplicas não podem sincronizar o mesmo catálogo ao mesmo tempo."""
    engine, _, ctx_sync, _ = _duplas_falsas(obteve_lock=False)
    with patch.object(scheduler, "engine", engine),          patch.object(scheduler, "AsyncSessionLocal", return_value=ctx_sync),          patch.object(scheduler, "sync_all_products", AsyncMock()) as sync:
        asyncio.run(scheduler._rodar_uma_vez())
    sync.assert_not_called()
    assert scheduler.ultimo_resultado["estado"] == "pulado"


def test_libera_o_lock_mesmo_se_o_sync_falhar():
    """Lock preso deixaria o sync parado até o próximo deploy."""
    engine, conexao, ctx_sync, _ = _duplas_falsas()
    with patch.object(scheduler, "engine", engine),          patch.object(scheduler, "AsyncSessionLocal", return_value=ctx_sync),          patch.object(scheduler, "sync_all_products",
                      AsyncMock(side_effect=ValueError("plataforma fora do ar"))):
        with pytest.raises(ValueError):
            asyncio.run(scheduler._rodar_uma_vez())
    assert any("pg_advisory_unlock" in x for x in _sqls(conexao)), _sqls(conexao)


def test_trava_e_destrava_na_MESMA_conexao_dedicada():
    """O bug que isto trava, medido em produção.

    O lock é de SESSÃO do Postgres, e sessão é a CONEXÃO. Ele era pego e solto
    na AsyncSession do sync — mas sync_all_products dá commit lá dentro, e
    commit devolve a conexão ao pool. O unlock saía numa conexão diferente da
    que travou: não fazia nada, e a original voltava ao pool ainda segurando o
    lock.

    O efeito é intermitente, que é o pior tipo: a rodada seguinte funciona se
    o pool devolver a mesma conexão e é pulada se devolver outra. Quatro
    rodadas ok e a quinta pulada, com um lock concedido a uma conexão 'idle'
    há 41 minutos no pg_locks.
    """
    engine, conexao, ctx_sync, sessao = _duplas_falsas()
    with patch.object(scheduler, "engine", engine),          patch.object(scheduler, "AsyncSessionLocal", return_value=ctx_sync),          patch.object(scheduler, "sync_all_products",
                      AsyncMock(return_value={"total": 700})):
        asyncio.run(scheduler._rodar_uma_vez())

    da_conexao = _sqls(conexao)
    da_sessao = _sqls(sessao)
    assert any("pg_try_advisory_lock" in x for x in da_conexao)
    assert any("pg_advisory_unlock" in x for x in da_conexao)
    # E o ponto: a sessão do sync não vê o lock em momento nenhum.
    assert not any("advisory" in x for x in da_sessao), da_sessao


def test_registra_resumo_quando_da_certo():
    engine, _, ctx_sync, _ = _duplas_falsas()
    with patch.object(scheduler, "engine", engine),          patch.object(scheduler, "AsyncSessionLocal", return_value=ctx_sync),          patch.object(scheduler, "sync_all_products",
                      AsyncMock(return_value={"total": 700, "criados": 2})):
        asyncio.run(scheduler._rodar_uma_vez())
    assert scheduler.ultimo_resultado["estado"] == "ok"
    assert scheduler.ultimo_resultado["total"] == 700
