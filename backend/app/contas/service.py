"""Quem pode chamar a calculadora, e com qual perfil.

Substitui a comparação contra duas variáveis de ambiente. A diferença que
importa não é técnica, é operacional: com a calculadora indo para contas de
clientes, é preciso saber de quem é cada requisição e conseguir cortar UMA
conta sem derrubar as outras. Chave em env não permite nem uma coisa nem outra.
"""

import hashlib
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.contas.models import Conta

log = logging.getLogger("contas")


def hash_da_chave(chave: str) -> str:
    """SHA-256 hex da chave.

    Sem sal e sem KDF lento, de propósito: a chave é gerada por nós com 256
    bits de aleatoriedade, não escolhida por uma pessoa. Não há dicionário
    para atacar, então bcrypt/argon2 só encareceriam o caminho quente de toda
    requisição sem fechar buraco nenhum.
    """
    return hashlib.sha256(chave.encode()).hexdigest()


def gerar_chave() -> str:
    """Chave nova, em claro. Só quem chamou vê — não guardamos o valor."""
    return secrets.token_hex(32)


async def buscar_por_chave(db: AsyncSession, chave: str) -> Conta | None:
    """Conta ATIVA dona dessa chave, ou None.

    Conta inativa devolve None junto com chave inexistente, e é intencional:
    quem foi revogado recebe a mesma resposta de quem nunca existiu.
    """
    if not chave:
        return None
    res = await db.execute(
        select(Conta).where(Conta.api_key_hash == hash_da_chave(chave),
                            Conta.ativa.is_(True))
    )
    return res.scalars().first()


async def criar(db: AsyncSession, nome: str, perfil: str,
                observacao: str | None = None) -> tuple[Conta, str]:
    """Cria a conta e devolve (conta, chave em claro).

    A chave em claro sai daqui uma vez e nunca mais: quem cria precisa
    guardá-la na hora. Perder significa criar outra, não recuperar esta.
    """
    chave = gerar_chave()
    conta = Conta(nome=nome, api_key_hash=hash_da_chave(chave), perfil=perfil,
                  observacao=observacao)
    db.add(conta)
    await db.flush()
    return conta, chave


#: Chaves que já existiam como variável de ambiente, com o nome e o perfil de
#: cada uma. Some daqui à medida que as contas passem a nascer pela tabela.
_SEMENTES = (
    ("api_key_embed",          "MX3 — campo de admin",           "completo"),
    ("api_key_embed_restrito", "MX3 — campo do usuário final",   "restrito"),
)


async def semear_do_ambiente(db: AsyncSession) -> int:
    """Registra as chaves de ambiente que ainda não estão na tabela.

    Roda no boot, idempotente. Existe para a virada não ter passo manual: no
    primeiro deploy com a tabela nova, as chaves já em uso continuam valendo
    sem ninguém precisar cadastrá-las antes. Quando as envs saírem, esta
    função deixa de encontrar o que semear e vira inofensiva.
    """
    criadas = 0
    for env, nome, perfil in _SEMENTES:
        chave = getattr(settings, env, "")
        if not chave:
            continue
        existe = await db.scalar(
            select(Conta.id).where(Conta.api_key_hash == hash_da_chave(chave))
        )
        if existe:
            continue
        db.add(Conta(nome=nome, api_key_hash=hash_da_chave(chave), perfil=perfil,
                     observacao=f"semeada de {env.upper()} no boot"))
        criadas += 1
        log.info("conta semeada do ambiente: %s (%s)", nome, perfil)
    if criadas:
        await db.commit()
    return criadas
