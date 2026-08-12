"""Reprecifica um kit editado na tela, no servidor.

Por que no servidor: no perfil restrito o preço unitário NÃO chega ao
navegador — `perfil._limpar_kit` zera item.preco_unitario justamente para o
valor não trafegar na resposta HTTP. Logo o cliente não tem como recalcular
nada depois que o vendedor muda uma quantidade ou acrescenta um item. Sem este
endpoint, o total exibido congelaria no valor do kit original e iria assim para
a proposta — errado, e silenciosamente.

O cliente manda só o que ele sabe: id do produto e quantidade. O preço vem
daqui, do catálogo, e a resposta passa pelo mesmo filtro de perfil do
/calculate.
"""

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculate.schemas import KitItem
from app.catalog.models import MeuBESSProduct
from app.engines.kit_attributes import eff, eff_float
from app.engines.shipping import calcular_frete, calcular_frete_fob


class ItemEditado(BaseModel):
    meubess_id: str
    qtd: int = Field(ge=1)


class ReprecificarRequest(BaseModel):
    itens: list[ItemEditado]
    tipo_frete: str | None = None      # "cif" | "fob"
    uf_entrega: str | None = None


class ReprecificarResponse(BaseModel):
    itens: list[KitItem]
    preco_total: float
    frete_valor: float | None = None
    total_com_frete: float


async def reprecificar(db: AsyncSession, req: ReprecificarRequest) -> ReprecificarResponse:
    """Preços e totais do kit editado. Ignora id que não existe mais no catálogo.

    Um id ausente não vira erro: o produto pode ter sido desativado entre a
    cotação e a edição, e derrubar a tela inteira por causa de um item seria
    pior do que devolver o kit sem ele — a diferença fica visível no total.
    """
    ids = [i.meubess_id for i in req.itens if i.meubess_id]
    encontrados: dict[str, MeuBESSProduct] = {}
    if ids:
        linhas = (await db.execute(
            select(MeuBESSProduct).where(MeuBESSProduct.meubess_id.in_(ids))
        )).scalars().all()
        encontrados = {p.meubess_id: p for p in linhas}

    itens: list[KitItem] = []
    for pedido in req.itens:
        prod = encontrados.get(pedido.meubess_id)
        if prod is None:
            continue
        preco = eff_float(prod, "price") or 0.0
        itens.append(KitItem(
            meubess_id=pedido.meubess_id,
            nome=str(eff(prod, "title") or ""),
            tipo=str(prod.tipo_manual or prod.tipo_auto or "acessorio"),
            qtd=pedido.qtd,
            preco_unitario=round(preco, 2),
            preco_total=round(preco * pedido.qtd, 2),
            # Atributos que a tela usa para recalcular energia, potência de
            # partida e de inversão ao vivo. Sem eles as métricas do card
            # zerariam a cada edição.
            energia_unit_kwh=eff_float(prod, "usable_capacity_kwh"),
            corrente_pico_a=eff_float(prod, "peak_discharge_current_a"),
            tensao_v=eff_float(prod, "nominal_voltage_v"),
            potencia_inversao_kw=eff_float(prod, "max_eps_power") or eff_float(prod, "power"),
            potencia_pico_kw=eff_float(prod, "peak_power_kw"),
            corrente_entrada_a=eff_float(prod, "battery_input_max_current_a"),
            entradas_bateria=(int(v) if (v := eff_float(prod, "battery_inputs")) else None),
            # `power` do módulo vem em kW no cadastro; a tela e a proposta
            # trabalham em Wp.
            potencia_wp=(round(pw * 1000, 1)
                         if (pw := eff_float(prod, "power")) and
                            str(prod.tipo_manual or prod.tipo_auto or "") == "modulo_fv"
                         else None),
        ))

    preco_total = round(sum(i.preco_total for i in itens), 2)

    # Mesma regra do /calculate: o frete CIF é percentual por faixa de preço,
    # então mudar o kit pode mudar a faixa. Recalcular sobre o total novo é o
    # ponto — reaplicar o percentual antigo erraria na virada de faixa.
    frete = None
    if req.tipo_frete == "fob":
        frete = calcular_frete_fob(preco_total)
    elif req.tipo_frete == "cif" and req.uf_entrega:
        frete = calcular_frete(req.uf_entrega, preco_total)

    frete_valor = float(frete["valor"]) if frete else None
    return ReprecificarResponse(
        itens=itens,
        preco_total=preco_total,
        frete_valor=frete_valor,
        total_com_frete=round(preco_total + (frete_valor or 0.0), 2),
    )


def limpar_para_restrito(resp: ReprecificarResponse) -> ReprecificarResponse:
    """Mesma barreira do /calculate: no restrito só o total com frete sobrevive.

    Sem isto o endpoint viraria a porta dos fundos do filtro de perfil — bastaria
    mandar os ids do kit para receber os preços unitários que a resposta do
    cálculo esconde.
    """
    for item in resp.itens:
        item.preco_unitario = 0.0
        item.preco_total = 0.0
    resp.preco_total = 0.0
    resp.frete_valor = None
    return resp
