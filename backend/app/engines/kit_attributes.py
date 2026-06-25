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
