"""
Resolução de atributos de produto para a lógica de kit.

Regra única: o **valor efetivo** de um campo é o override manual
(`overrides_tecnicos[campo]`) quando presente; caso contrário, a coluna nativa.

Isso permite corrigir dados que vêm errados/nulos da MeuBESS sem que o sync
reescreva por cima (o sync só escreve as colunas nativas; o override vence na
leitura). As colunas de dimensionamento da migration 010 não vêm da MeuBESS e
são lidas direto — mas passam pela mesma regra, então também aceitam override.
"""

from typing import Any


def eff(product: Any, field: str, default: Any = None) -> Any:
    """Valor efetivo do campo: override manual vence a coluna nativa."""
    overrides = getattr(product, "overrides_tecnicos", None) or {}
    val = overrides.get(field)
    if val is None:
        val = getattr(product, field, None)
    return default if val is None else val


def eff_float(product: Any, field: str) -> float | None:
    val = eff(product, field)
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def eff_int(product: Any, field: str) -> int | None:
    val = eff(product, field)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def eff_bool(product: Any, field: str) -> bool | None:
    val = eff(product, field)
    if val is None:
        return None
    return bool(val)


#: Margem que a plataforma MeuBESS aplica sobre o custo do material para chegar
#: ao preço de venda: venda = custo / (1 - margem).
#:
#: Não é markup sobre o custo (que daria custo × 1,2585): é margem sobre o
#: PREÇO, então o divisor. No LONGI 635: 546,10 / (1 - 0,2585) = 736,48.
#:
#: Era 0,2385 — dois pontos abaixo — e ficou assim desde que a fórmula entrou.
#: Nenhum teste pegaria: eles conferem que a CONTA está certa, e a conta
#: estava. O que estava errado era o número, e número de negócio só se
#: confere contra a origem. Foi uma comparação item a item entre uma cotação
#: nossa e a mesma cotação na plataforma que mostrou: os sete custos batiam
#: centavo a centavo e as sete vendas estavam todas 2% baixas.
#:
#: Se a MeuBESS mudar a margem de novo, o sintoma volta a ser este — preço
#: coerente, plausível e errado. A conferência é comparar um kit nos dois
#: lados, não ler o código.
MARGEM_VENDA = 0.2585


def preco_venda(produto: Any) -> float | None:
    """Preço de venda do produto, a partir do custo.

    Ponto ÚNICO onde o preço é decidido — o cálculo estava espalhado por quatro
    lugares que liam `price` direto, e `price` é o "Preço de Venda Fixo" da
    plataforma: preenchido à mão lá e sem seguir a fórmula. No módulo LONGI 635
    ele traz R$ 600,00 quando o correto são R$ 736,48.

    Devolve None quando não há custo. O chamador precisa tratar isso como
    "produto não cotável" e não como preço zero: um item a R$ 0,00 entra no kit
    como o mais barato de todos e some do total sem ninguém notar.
    """
    custo = eff_float(produto, "cost")
    if custo is None or custo <= 0:
        return None
    return round(custo / (1 - MARGEM_VENDA), 2)
