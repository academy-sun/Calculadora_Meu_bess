import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import Project


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def list_projects(
    db: AsyncSession,
    origem: str | None = None,
    negocio_id: str | None = None,
    limit: int = 50,
) -> list[Project]:
    stmt = select(Project).order_by(Project.solicitado_em.desc()).limit(limit)
    if origem:
        stmt = stmt.where(Project.origem == origem)
    if negocio_id:
        stmt = stmt.where(Project.negocio_id == negocio_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_project(db: AsyncSession, data: dict) -> Project:
    project = Project(**data)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def mark_project_done(
    db: AsyncSession, project: Project, calculado_em: datetime
) -> Project:
    project.estado = "concluido"
    project.calculado_em = calculado_em
    await db.commit()
    await db.refresh(project)
    return project


async def mark_project_error(db: AsyncSession, project: Project) -> Project:
    project.estado = "erro"
    await db.commit()
    await db.refresh(project)
    return project
