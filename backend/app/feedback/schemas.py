from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    origem: Literal["embed", "interna"]
    tipo: Optional[Literal["dimensionamento", "melhoria", "erro"]] = None
    #: Mensagem do usuário. Limite alto de propósito — cortar o relato de quem
    #: se deu ao trabalho de escrever é perder justamente o detalhe que importa.
    mensagem: str = Field(min_length=3, max_length=5000)
    autor_nome: Optional[str] = None
    autor_email: Optional[str] = None
    #: Entradas do cálculo e kit resultante. Sem isso "o dimensionamento está
    #: errado" não tem como ser reproduzido.
    contexto: Optional[dict[str, Any]] = None
    url: Optional[str] = None


class FeedbackRead(BaseModel):
    id: str
    criado_em: datetime
    origem: str
    tipo: Optional[str] = None
    mensagem: str
    autor_nome: Optional[str] = None
    autor_email: Optional[str] = None
    contexto: Optional[dict[str, Any]] = None
    url: Optional[str] = None
    email_enviado: bool
    email_erro: Optional[str] = None
    lido: bool

    model_config = {"from_attributes": True}


class FeedbackCreated(BaseModel):
    """O que o autor recebe de volta.

    Devolve se o e-mail saiu para a tela poder dizer a verdade: "recebemos"
    vale mesmo quando a notificação falha, porque o registro está gravado.
    """
    id: str
    email_enviado: bool
