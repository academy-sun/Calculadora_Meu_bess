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
    user_id_filter: str | None = None,
) -> list[Project]:
    stmt = select(Project).order_by(Project.solicitado_em.desc()).limit(limit)
    if origem:
        stmt = stmt.where(Project.origem == origem)
    if negocio_id:
        stmt = stmt.where(Project.negocio_id == negocio_id)
    if user_id_filter:
        stmt = stmt.where(Project.solicitante_id == user_id_filter)
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


async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> bool:
    project = await get_project(db, project_id)
    if not project:
        return False
    await db.delete(project)
    await db.commit()
    return True


async def bulk_delete_projects(
    db: AsyncSession,
    project_ids: list[uuid.UUID],
    user_sub: str,
    is_admin: bool,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Returns (deleted_ids, forbidden_ids)."""
    deleted: list[uuid.UUID] = []
    forbidden: list[uuid.UUID] = []
    for pid in project_ids:
        project = await get_project(db, pid)
        if not project:
            continue
        if not is_admin and project.solicitante_id != user_sub:
            forbidden.append(pid)
            continue
        await db.delete(project)
        deleted.append(pid)
    await db.commit()
    return deleted, forbidden
