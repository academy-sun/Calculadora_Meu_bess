"""Política de curadoria do catálogo — SQL exercitado contra sqlite não serve
(usa ilike e update-from), então o teste cobre a forma da política e a
integração com o sync. A verificação de efeito real foi feita em produção,
contra o banco, e está registrada no commit."""

from unittest.mock import AsyncMock, patch

import pytest

from app.catalog import curadoria


def test_politica_declara_o_modulo_unico_e_a_marca():
    """São os dois parâmetros que mudam o que o motor pode cotar."""
    assert curadoria.MODULO_UNICO_ID == "29740487"
    assert curadoria.MARCA_INVERSOR == "WEG"
    assert any("SIW300H" in t for t in curadoria.TITULOS_BLOQUEADOS)
    assert any("Luna" in t for t in curadoria.TITULOS_BLOQUEADOS)


def test_so_toca_linhas_sem_decisao_humana():
    """Quem já tem ativo_manual definido é exceção aberta de propósito."""
    assert "p.ativo_manual is null" in curadoria._SQL.lower()


def test_sql_preserva_o_modulo_escolhido():
    assert "p.meubess_id <> :modulo_id" in curadoria._SQL


@pytest.mark.asyncio
async def test_aplicar_curadoria_devolve_quantidade():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=type("R", (), {"rowcount": 13})())
    assert await curadoria.aplicar_curadoria(db) == 13


@pytest.mark.asyncio
async def test_sync_aplica_a_politica_antes_do_commit():
    """Sem isto o catálogo se repovoa: produto novo chega sempre ativo."""
    from app.catalog import sync as sync_mod

    db = AsyncMock()
    with patch.object(sync_mod, "_check_api_key"), \
         patch.object(sync_mod, "_fetch_all_products", AsyncMock(return_value=[])), \
         patch("app.catalog.curadoria.aplicar_curadoria",
               AsyncMock(return_value=7)) as politica:
        resumo = await sync_mod.sync_all_products(db)

    politica.assert_awaited_once()
    assert resumo["desativados_pela_politica"] == 7
    assert db.commit.await_count == 1
