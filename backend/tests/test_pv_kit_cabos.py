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


# O caso real: A.DIAS e WEG com o MESMO custo (4,21) no catálogo.
ADIAS_PRETO = _C("adias", "A - CABO SOLAR 6MM 1,8KV PRETO", 5.68)
ADIAS_PRETO.marca = "A.DIAS"
WEG_PRETO = _C("weg", "W - Unipolar flexível NH 6 mm² Preto", 5.68)
WEG_PRETO.marca = "WEG"
WEG_PRETO_DUP = _C("weg2", "W - (WEG) Unipolar flexível NH 6 mm² Preto", 5.68)
WEG_PRETO_DUP.marca = "WEG"
BEL_PRETO = _C("bel", "B - Cabo Solar 6mm - Preto", 7.01)
BEL_PRETO.marca = "BEL ENERGY"


def test_no_empate_de_preco_ganha_a_marca_que_vendemos():
    """Saiu cabo A.DIAS num kit inteiramente WEG, e não havia critério nenhum
    dizendo isso: os dois custam 4,21, o `min` devolve o primeiro da lista, e
    a lista vem ordenada por título — 'A - CABO SOLAR' antes de
    'W - Unipolar flexível'. O desempate era a ordem alfabética."""
    assert _cabo_da_cor([ADIAS_PRETO, WEG_PRETO], "Preto").meubess_id == "weg"
    # e a ordem de entrada não pode mudar a resposta
    assert _cabo_da_cor([WEG_PRETO, ADIAS_PRETO], "Preto").meubess_id == "weg"


def test_preco_ainda_manda_sobre_a_marca():
    """A preferência é DESEMPATE, não regra: cabo mais barato continua
    ganhando, senão isto viraria uma trava de fornecedor escondida."""
    barato = _C("outro", "X - Cabo 6mm Preto", 4.00)
    barato.marca = "OUTRA"
    assert _cabo_da_cor([barato, WEG_PRETO], "Preto").meubess_id == "outro"


def test_escolha_e_estavel_entre_duplicatas_da_mesma_marca():
    """A plataforma tem o mesmo cabo WEG cadastrado duas vezes, com títulos
    quase iguais e custo idêntico. Sem um terceiro critério, qual entra na
    proposta mudaria conforme a ordem que o banco devolvesse."""
    a = _cabo_da_cor([WEG_PRETO, WEG_PRETO_DUP], "Preto").meubess_id
    b = _cabo_da_cor([WEG_PRETO_DUP, WEG_PRETO], "Preto").meubess_id
    assert a == b


def test_marca_ausente_nao_quebra_a_escolha():
    """Acessório sem marca cadastrada é comum; ele só perde o desempate."""
    sem_marca = _C("s1", "Z - Cabo 6mm Preto", 5.68)
    assert _cabo_da_cor([sem_marca, WEG_PRETO], "Preto").meubess_id == "weg"
    assert _cabo_da_cor([sem_marca], "Preto").meubess_id == "s1"
