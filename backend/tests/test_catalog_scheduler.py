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


def _sessao_falsa(obteve_lock=True):
    sessao = AsyncMock()
    resultado = AsyncMock()
    resultado.scalar = lambda: obteve_lock
    sessao.execute = AsyncMock(return_value=resultado)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=sessao)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, sessao


def test_pula_quando_outra_instancia_tem_o_lock():
    """Duas réplicas não podem sincronizar o mesmo catálogo ao mesmo tempo."""
    ctx, _ = _sessao_falsa(obteve_lock=False)
    with patch.object(scheduler, "AsyncSessionLocal", return_value=ctx), \
         patch.object(scheduler, "sync_all_products", AsyncMock()) as sync:
        asyncio.run(scheduler._rodar_uma_vez())
    sync.assert_not_called()
    assert scheduler.ultimo_resultado["estado"] == "pulado"


def test_libera_o_lock_mesmo_se_o_sync_falhar():
    """Lock preso deixaria o sync parado até o próximo deploy."""
    ctx, sessao = _sessao_falsa(obteve_lock=True)
    with patch.object(scheduler, "AsyncSessionLocal", return_value=ctx), \
         patch.object(scheduler, "sync_all_products",
                      AsyncMock(side_effect=ValueError("plataforma fora do ar"))):
        with pytest.raises(ValueError):
            asyncio.run(scheduler._rodar_uma_vez())
    sqls = [str(c.args[0]) for c in sessao.execute.call_args_list]
    assert any("pg_advisory_unlock" in s for s in sqls), sqls


def test_registra_resumo_quando_da_certo():
    ctx, _ = _sessao_falsa(obteve_lock=True)
    with patch.object(scheduler, "AsyncSessionLocal", return_value=ctx), \
         patch.object(scheduler, "sync_all_products",
                      AsyncMock(return_value={"total": 700, "criados": 2})):
        asyncio.run(scheduler._rodar_uma_vez())
    assert scheduler.ultimo_resultado["estado"] == "ok"
    assert scheduler.ultimo_resultado["total"] == 700
