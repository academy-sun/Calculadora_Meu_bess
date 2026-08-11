"""Reprecificação de kit editado — e a barreira de perfil no caminho novo."""

from unittest.mock import AsyncMock, patch

from app.calculate.reprecificar import (
    ItemEditado, ReprecificarRequest, limpar_para_restrito, reprecificar,
)


class _Prod:
    def __init__(self, pid, title, price, tipo="bateria", **kw):
        self.meubess_id = pid
        self.title = title
        self.price = price
        self.tipo_manual = None
        self.tipo_auto = tipo
        self.overrides_tecnicos = None
        for k, v in kw.items():
            setattr(self, k, v)
    def __getattr__(self, _):
        return None


def _db(produtos):
    db = AsyncMock()
    res = AsyncMock()
    res.scalars = lambda: type("S", (), {"all": lambda self=None: produtos})()
    db.execute = AsyncMock(return_value=res)
    return db


async def test_soma_pelo_preco_do_catalogo_nao_pelo_que_o_cliente_manda():
    """O cliente manda id e quantidade. O preço é do servidor — é essa a
    razão de o endpoint existir."""
    db = _db([_Prod("b1", "Bateria CB100", 1000.0)])
    r = await reprecificar(db, ReprecificarRequest(
        itens=[ItemEditado(meubess_id="b1", qtd=3)]))
    assert r.preco_total == 3000.0
    assert r.itens[0].preco_unitario == 1000.0


async def test_frete_cif_recalculado_sobre_o_total_novo():
    """O CIF é percentual por FAIXA de preço: editar o kit pode mudar a faixa,
    então reaplicar o percentual antigo erraria na virada."""
    db = _db([_Prod("b1", "Bateria", 10000.0)])
    r = await reprecificar(db, ReprecificarRequest(
        itens=[ItemEditado(meubess_id="b1", qtd=5)],
        tipo_frete="cif", uf_entrega="AC"))
    assert r.preco_total == 50000.0
    assert r.frete_valor and r.frete_valor > 0
    assert r.total_com_frete == round(50000.0 + r.frete_valor, 2)


async def test_id_que_sumiu_do_catalogo_nao_derruba_a_tela(caplog):
    """Produto desativado entre a cotação e a edição sai do kit; o resto
    continua. Derrubar tudo por causa de um item seria pior."""
    db = _db([_Prod("b1", "Bateria", 1000.0)])
    r = await reprecificar(db, ReprecificarRequest(itens=[
        ItemEditado(meubess_id="b1", qtd=1),
        ItemEditado(meubess_id="sumiu", qtd=2),
    ]))
    assert [i.meubess_id for i in r.itens] == ["b1"]
    assert r.preco_total == 1000.0


async def test_restrito_nao_recebe_preco_por_esta_porta():
    """Sem isto o endpoint seria a porta dos fundos do filtro de perfil:
    bastaria mandar os ids do kit para receber os unitários que o /calculate
    esconde."""
    db = _db([_Prod("b1", "Bateria", 1000.0)])
    r = limpar_para_restrito(await reprecificar(db, ReprecificarRequest(
        itens=[ItemEditado(meubess_id="b1", qtd=3)],
        tipo_frete="cif", uf_entrega="AC")))
    assert r.preco_total == 0.0
    assert r.frete_valor is None
    assert all(i.preco_unitario == 0.0 and i.preco_total == 0.0 for i in r.itens)
    # O único valor que sobrevive, e é o que a tela mostra.
    assert r.total_com_frete > 0


async def test_restrito_mantem_os_atributos_de_engenharia():
    """Energia e potência continuam vindo: é com eles que o card recalcula
    cobertura e potência de partida ao vivo."""
    db = _db([_Prod("b1", "Bateria", 1000.0, usable_capacity_kwh=10.07)])
    r = limpar_para_restrito(await reprecificar(db, ReprecificarRequest(
        itens=[ItemEditado(meubess_id="b1", qtd=2)])))
    assert r.itens[0].energia_unit_kwh == 10.07
