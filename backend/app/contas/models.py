import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Conta(Base):
    """Conta do Ploomes autorizada a chamar a calculadora. Ver migration 019."""
    __tablename__ = "contas"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True,
                                    server_default=func.gen_random_uuid())
    nome: Mapped[str] = mapped_column(Text)
    #: SHA-256 da chave. A chave em claro não existe aqui — ver service.hash_da_chave.
    api_key_hash: Mapped[str] = mapped_column(Text, unique=True)
    perfil: Mapped[str] = mapped_column(Text)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    observacao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                    server_default=func.now())
