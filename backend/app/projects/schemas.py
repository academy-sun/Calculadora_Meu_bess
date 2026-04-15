import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProjectRead(BaseModel):
    id: uuid.UUID
    tipo_calculo: str
    estado: str
    versao: int
    origem: str
    negocio_id: Optional[str]
    negocio_nome: Optional[str]
    solicitante_id: str
    solicitante_nome: str
    solicitado_em: datetime
    calculado_em: Optional[datetime]
    parametros: Optional[dict]

    model_config = {"from_attributes": True}
