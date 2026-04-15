import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_calculo: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(Text, default="calculando")
    versao: Mapped[int] = mapped_column(Integer, default=1)
    parametros: Mapped[dict | None] = mapped_column(JSONB)
    origem: Mapped[str] = mapped_column(Text, nullable=False)
    negocio_id: Mapped[str | None] = mapped_column(Text)
    negocio_nome: Mapped[str | None] = mapped_column(Text)
    solicitante_id: Mapped[str] = mapped_column(Text, nullable=False)
    solicitante_nome: Mapped[str] = mapped_column(Text, nullable=False)
    solicitado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    load_curve: Mapped["LoadCurve | None"] = relationship(back_populates="project", uselist=False)
    project_loads: Mapped[list["ProjectLoad"]] = relationship(back_populates="project")
    results: Mapped[list["CalculationResult"]] = relationship(back_populates="project")


class LoadCurve(Base):
    __tablename__ = "load_curves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    origem: Mapped[str] = mapped_column(Text, nullable=False)
    dados: Mapped[list] = mapped_column(JSONB, nullable=False)
    unidade: Mapped[str] = mapped_column(Text, default="kW")
    resolucao: Mapped[str] = mapped_column(Text, default="1h")

    project: Mapped["Project"] = relationship(back_populates="load_curve")


class ProjectLoad(Base):
    __tablename__ = "project_loads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    standard_load_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("standard_loads.id"))
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    potencia_w: Mapped[float] = mapped_column(Numeric, nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, default=1)
    horas_uso_dia: Mapped[float] = mapped_column(Numeric, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="project_loads")


class CalculationResult(Base):
    __tablename__ = "calculation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    engine: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    outputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="results")
