from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Feedback(Base):
    """Relato de quem usa a calculadora. Ver migration 017."""
    __tablename__ = "feedbacks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True,
                                    server_default=func.gen_random_uuid())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                server_default=func.now())
    origem: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str | None] = mapped_column(Text)
    mensagem: Mapped[str] = mapped_column(Text)
    autor_nome: Mapped[str | None] = mapped_column(Text)
    autor_email: Mapped[str | None] = mapped_column(Text)
    contexto: Mapped[Any | None] = mapped_column(JSONB)
    url: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    email_enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    email_erro: Mapped[str | None] = mapped_column(Text)
    lido: Mapped[bool] = mapped_column(Boolean, default=False)
