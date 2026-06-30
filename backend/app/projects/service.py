import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculate.schemas import SaveQuoteRequest
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


def _build_quote_parametros(body: SaveQuoteRequest) -> dict:
    """`parametros` guarda o request original (cargas, autonomia_dias, etc — usado para
    "Editar cotação") mesclado com o resultado computado (kit_selecionado já é o kit
    escolhido, possivelmente com itens editados pelo usuário)."""
    return {
        **body.calculo.model_dump(mode="json", exclude={"origem_info"}),
        **body.resultado.model_dump(mode="json", exclude={"projeto_id"}),
        "titulo": body.titulo,
    }


async def create_quote_project(
    db: AsyncSession, body: SaveQuoteRequest, user_id: uuid.UUID | None = None
) -> Project:
    """Persiste a cotação só agora, quando o usuário escolheu um kit (não em toda busca)."""
    origem_info = body.calculo.origem_info
    project = Project(
        tipo_calculo=body.calculo.tipo_calculo,
        estado="concluido",
        versao=1,
        parametros=_build_quote_parametros(body),
        origem=origem_info.origem,
        negocio_id=origem_info.negocio_id,
        negocio_nome=origem_info.negocio_nome,
        solicitante_id=origem_info.solicitante_id,
        solicitante_nome=origem_info.solicitante_nome,
        solicitado_em=origem_info.solicitado_em,
        calculado_em=datetime.now(timezone.utc),
        user_id=user_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def update_quote_project(
    db: AsyncSession, project_id: uuid.UUID, body: SaveQuoteRequest
) -> Project | None:
    """
    Salva uma cotação editada como NOVA VERSÃO da mesma cotação (não cria um projeto
    novo) — usado pelo fluxo "Editar cotação" → "Escolher este kit" novamente.
    """
    project = await get_project(db, project_id)
    if not project:
        return None
    origem_info = body.calculo.origem_info
    project.tipo_calculo = body.calculo.tipo_calculo
    project.parametros = _build_quote_parametros(body)
    project.origem = origem_info.origem
    project.negocio_id = origem_info.negocio_id
    project.negocio_nome = origem_info.negocio_nome
    project.solicitante_id = origem_info.solicitante_id
    project.solicitante_nome = origem_info.solicitante_nome
    project.estado = "concluido"
    project.versao = (project.versao or 1) + 1
    project.calculado_em = datetime.now(timezone.utc)
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
