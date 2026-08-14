"""Seleção do cabo CC por cor."""

from app.engines.pv_kit import _cabo_da_cor, _cabo_mc4_items
from app.engines.kit_attributes import MARGEM_VENDA


class _C:
    def __init__(self, pid, title, price):
    # As fixtures declaram o PREÇO que se espera do produto; o motor hoje
    # deriva preço de custo (preco_venda = custo / (1 - margem)). Traduzir
    # aqui mantém cada teste falando de preço, que é o que ele afirma, sem
    # espalhar a fórmula por dezenas de fixtures.
        self.meubess_id, self.title = pid, title
        self.cost = price * (1 - MARGEM_VENDA)
    def __getattr__(self, _):
        return None


PRETO = _C("p1", "A - CABO SOLAR 6MM 1,8KV PRETO", 5.0)
VERMELHO = _C("v1", "A - CABO SOLAR 6MM 1,8KV VERMELHO", 5.0)
PRETO_CARO = _C("p2", "B - Cabo Solar 6mm - Preto", 10.4)


def test_escolhe_o_produto_da_cor_certa():
    """O kit repetia o mesmo produto nas duas linhas: a linha vermelha saía com
    o código e o nome do cabo preto."""
    assert _cabo_da_cor([PRETO, VERMELHO], "Vermelho").meubess_id == "v1"
    assert _cabo_da_cor([PRETO, VERMELHO], "Preto").meubess_id == "p1"


def test_o_mais_barato_dentro_da_cor():
    assert _cabo_da_cor([PRETO_CARO, PRETO, VERMELHO], "Preto").meubess_id == "p1"


def test_sem_produto_da_cor_cai_no_mais_barato():
    """Catálogo sem cabo vermelho não pode deixar o kit sem o segundo cabo."""
    assert _cabo_da_cor([PRETO], "Vermelho").meubess_id == "p1"


def test_kit_leva_dois_cabos_com_ids_diferentes():
    itens = _cabo_mc4_items(14, [PRETO, VERMELHO], [])
    cabos = [i for i in itens if "CABO" in i["nome"].upper()]
    assert len(cabos) == 2
    assert {c["meubess_id"] for c in cabos} == {"p1", "v1"}
    assert all(c["qtd"] == 50 for c in cabos)   # ceil(28/25)*25
