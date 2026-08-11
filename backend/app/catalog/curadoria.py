"""Política de quais produtos o motor pode usar.

Isto NÃO é um script de limpeza que roda uma vez. A migration 014 desativou o
catálogo de uma vez, e o primeiro sync automático trouxe 13 produtos novos —
7 inversores LIVOLTEK, 1 DEYE e 5 módulos de outras linhas — todos ativos,
porque produto novo chega sem decisão nossa. Sem aplicar a política a cada
sync, o catálogo se repovoa sozinho de hora em hora.

A regra é do time comercial: o motor cota o que a MX3 vende, que hoje é
inversor WEG e um módulo específico.

Só toca linhas com `ativo_manual IS NULL`, ou seja, sem decisão humana
registrada. Quem for marcado explicitamente (true ou false) fica como está —
a política não sobrescreve exceção que alguém tenha aberto de propósito.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Único módulo FV que o motor pode cotar. Escolhido entre os dois Longi 635 W
#: do catálogo (o outro é o N-Type, id 19993196, a R$ 708,82 contra R$ 600,00).
MODULO_UNICO_ID = "29740487"

#: Marca aceita para inversores (híbrido e string).
MARCA_INVERSOR = "WEG"

#: Linhas retiradas por decisão comercial, casadas por trecho do título.
TITULOS_BLOQUEADOS = ("%SIW300H%", "%SBW300%Luna%")

_SQL = """
with tipo as (
  select meubess_id,
         coalesce(tipo_manual, tipo_auto) as t,
         coalesce(marca, '')              as m,
         coalesce(title, '')              as titulo
    from meubess_products
)
update meubess_products p
   set ativo_manual = false,
       validado_por = 'politica/curadoria-catalogo',
       validado_em  = now()
  from tipo
 where tipo.meubess_id = p.meubess_id
   and p.ativo_manual is null
   and (
        (tipo.t like 'inversor%' and tipo.m not ilike :marca_inversor)
     or (tipo.t = 'modulo_fv' and p.meubess_id <> :modulo_id)
     or tipo.titulo ilike :bloq_0
     or tipo.titulo ilike :bloq_1
   )
"""


async def aplicar_curadoria(db: AsyncSession) -> int:
    """Desativa o que a política exclui. Devolve quantos produtos foram tocados.

    Idempotente: quem já está com ativo_manual definido não é considerado, e
    numa rodada sem produto novo o retorno é 0.
    """
    resultado = await db.execute(
        text(_SQL),
        {
            "marca_inversor": f"%{MARCA_INVERSOR}%",
            "modulo_id": MODULO_UNICO_ID,
            "bloq_0": TITULOS_BLOQUEADOS[0],
            "bloq_1": TITULOS_BLOQUEADOS[1],
        },
    )
    return resultado.rowcount or 0
