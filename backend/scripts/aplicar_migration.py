"""Aplica um arquivo .sql de migrations/ no banco apontado por DATABASE_URL.

Uso, sem nunca digitar a credencial:

    railway run python scripts/aplicar_migration.py migrations/019_x.sql

`railway run` injeta as variáveis do serviço no processo filho, então a URL do
banco vem do ambiente e não da linha de comando — não entra no histórico do
shell nem em log nenhum.

As 18 primeiras migrations foram aplicadas à mão, uma a uma. Isso funciona até
alguém aplicar fora de ordem, ou aplicar duas vezes, ou achar que aplicou. Os
arquivos aqui são idempotentes por convenção (`if not exists`), e este script
confirma o que rodou em vez de deixar a confirmação por conta da memória.
"""

import asyncio
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _url_asyncpg(url: str) -> str:
    """SQLAlchemy usa 'postgresql+asyncpg://'; o asyncpg cru não entende o '+'."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def main() -> int:
    if len(sys.argv) < 2:
        print("uso: python scripts/aplicar_migration.py <arquivo.sql>", file=sys.stderr)
        return 2
    caminho = Path(sys.argv[1])
    if not caminho.exists():
        print(f"arquivo não encontrado: {caminho}", file=sys.stderr)
        return 2

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL ausente — rode via 'railway run'", file=sys.stderr)
        return 2

    import asyncpg
    sql = caminho.read_text(encoding="utf-8")
    conn = await asyncpg.connect(_url_asyncpg(url))
    try:
        # asyncpg executa o script inteiro quando não há parâmetros, então o
        # begin/commit de dentro do arquivo continua valendo.
        await conn.execute(sql)
    finally:
        await conn.close()
    print(f"aplicada: {caminho.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
