"""Atualização periódica do catálogo a partir da plataforma MeuBESS.

O preço é o dado que mais muda e o único que o consultor não consegue conferir
sozinho na hora da proposta. Rodar o sync de hora em hora mantém a cotação
alinhada com a plataforma sem depender de alguém lembrar de apertar o botão.

O sync já é idempotente e preserva a camada de decisão humana
(`_PRESERVE_ON_CONFLICT` em sync.py): tipo_manual, ativo_manual,
overrides_tecnicos, validado_por/em. Ou seja, a curadoria do catálogo — os
produtos desativados, as potências da linha K, as reclassificações — não é
desfeita por esta rotina. É por isso que ela pode rodar sozinha.

Roda dentro do processo da API, não como serviço separado: é uma chamada HTTP
a cada hora, não justifica um container. Com mais de uma réplica, o lock
consultivo do Postgres garante que só uma execute.
"""

import asyncio
import traceback
from datetime import datetime, timezone

from sqlalchemy import text

from app.catalog.sync import sync_all_products
from app.config import settings
from app.database import AsyncSessionLocal

#: Chave do advisory lock. Número arbitrário e fixo; só precisa não colidir com
#: outro lock consultivo do mesmo banco.
_LOCK_ID = 815_2024

#: Estado da última execução, exposto em GET /catalog/sync/status para dar
#: visibilidade sem precisar abrir o log do Railway.
ultimo_resultado: dict = {"estado": "nunca executou"}


async def _rodar_uma_vez() -> None:
    global ultimo_resultado
    inicio = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        # pg_try_advisory_lock não bloqueia: se outra réplica está sincronizando,
        # esta simplesmente pula a rodada em vez de enfileirar.
        obteve = (await db.execute(
            text("select pg_try_advisory_lock(:k)"), {"k": _LOCK_ID}
        )).scalar()
        if not obteve:
            ultimo_resultado = {
                "estado": "pulado",
                "motivo": "outra instância estava sincronizando",
                "em": inicio.isoformat(),
            }
            return
        try:
            resumo = await sync_all_products(db)
            ultimo_resultado = {
                "estado": "ok",
                "em": inicio.isoformat(),
                "duracao_s": round(
                    (datetime.now(timezone.utc) - inicio).total_seconds(), 1),
                **resumo,
            }
            print(f"[sync] catálogo atualizado: {resumo}")
        finally:
            await db.execute(text("select pg_advisory_unlock(:k)"), {"k": _LOCK_ID})
            await db.commit()


async def _loop(intervalo_s: int) -> None:
    while True:
        try:
            await _rodar_uma_vez()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Uma falha de rede na plataforma não pode derrubar o agendador —
            # senão o primeiro timeout às 3h da manhã encerra o sync até o
            # próximo deploy. Registra e tenta de novo no ciclo seguinte.
            global ultimo_resultado
            ultimo_resultado = {
                "estado": "erro",
                "erro": repr(exc),
                "em": datetime.now(timezone.utc).isoformat(),
            }
            print(f"[sync] FALHOU: {exc!r}")
            traceback.print_exc()
        await asyncio.sleep(intervalo_s)


def iniciar(app) -> asyncio.Task | None:
    """Agenda o sync periódico. Retorna a task, ou None se desligado."""
    intervalo = settings.sync_intervalo_segundos
    if intervalo <= 0:
        print("[sync] agendador desligado (SYNC_INTERVALO_SEGUNDOS <= 0)")
        return None
    if not settings.meubess_api_key:
        print("[sync] agendador desligado: MEUBESS_API_KEY não configurada")
        return None
    print(f"[sync] agendador ligado: a cada {intervalo}s")
    return asyncio.create_task(_loop(intervalo))
