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
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.catalog.sync import sync_all_products
from app.config import settings
from app.database import AsyncSessionLocal

#: logging, não print. O stdout de um container é um pipe, e print() fica
#: bufferizado em blocos: a primeira execução do agendador rodou e o resultado
#: não apareceu no Railway até o buffer encher. Com um agendador, "não vejo
#: nada no log" é indistinguível de "não rodou" — e foi exatamente o tempo que
#: se perdeu diagnosticando. O logging do uvicorn já sai com flush.
log = logging.getLogger("catalog.sync")

#: Chave do advisory lock. Número arbitrário e fixo; só precisa não colidir com
#: outro lock consultivo do mesmo banco.
_LOCK_ID = 815_2024

#: Estado da última execução, exposto em GET /catalog/sync/status para dar
#: visibilidade sem precisar abrir o log do Railway.
ultimo_resultado: dict = {"estado": "nunca executou"}


async def _rodar_uma_vez() -> None:
    global ultimo_resultado
    inicio = datetime.now(timezone.utc)
    # Registrar o INÍCIO, não só o fim: sem esta linha, "começou e travou" e
    # "nunca começou" produzem exatamente o mesmo log — nenhum.
    log.info("iniciando sync do catálogo")
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
            log.info("sync pulado: outra instância estava sincronizando")
            return
        try:
            resumo = await sync_all_products(db)
            # `synced` traz uma linha por produto — 700 dicionários, ~80 KB por
            # execução no log do Railway. Para acompanhamento periódico o que
            # importa é o agregado; o detalhe continua no POST /catalog/sync.
            resumo = {k: v for k, v in resumo.items() if k not in ("synced", "errors")}
            ultimo_resultado = {
                "estado": "ok",
                "em": inicio.isoformat(),
                "duracao_s": round(
                    (datetime.now(timezone.utc) - inicio).total_seconds(), 1),
                **resumo,
            }
            log.info("catálogo atualizado: %s", ultimo_resultado)
        finally:
            await db.execute(text("select pg_advisory_unlock(:k)"), {"k": _LOCK_ID})
            await db.commit()


async def _loop(intervalo_s: int) -> None:
    while True:
        comeco = datetime.now(timezone.utc)
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
            log.exception("sync FALHOU: %r", exc)
        # Desconta o tempo da rodada. Dormir o intervalo cheio DEPOIS do sync
        # dava um ciclo de 64 min (4 min de sync + 60 de espera), e o atraso
        # acumulava: ~1h30 de deriva por dia. Medido em produção entre as
        # execuções de 15:12:45 e 16:16:50.
        gasto = (datetime.now(timezone.utc) - comeco).total_seconds()
        await asyncio.sleep(max(0.0, intervalo_s - gasto))


def iniciar(app) -> asyncio.Task | None:
    """Agenda o sync periódico. Retorna a task, ou None se desligado."""
    intervalo = settings.sync_intervalo_segundos
    if intervalo <= 0:
        log.info("agendador desligado (SYNC_INTERVALO_SEGUNDOS <= 0)")
        return None
    if not settings.meubess_api_key:
        log.warning("agendador desligado: MEUBESS_API_KEY não configurada")
        return None
    log.info("agendador ligado: a cada %ss", intervalo)
    return asyncio.create_task(_loop(intervalo))
