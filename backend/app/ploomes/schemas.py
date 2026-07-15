from typing import Optional

from pydantic import BaseModel


class PushbackItem(BaseModel):
    nome: str
    sku: Optional[str] = None
    qtd: int = 1
    preco_unitario: float


class PushbackRequest(BaseModel):
    deal_id: int
    kit_descricao: str
    kit_preco: float
    frete_valor: Optional[float] = None
    frete_descricao: Optional[str] = None   # ex.: "CIF — SP" | "FOB — Retirada no CD"
    total_geral: Optional[float] = None
    itens: list[PushbackItem] = []
    incluir_produtos: bool = True
