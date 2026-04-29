import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserInToken
from app.database import get_db
from app.projects import service
from app.projects.schemas import BulkDeleteRequest, BulkDeleteResponse, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    origem: str | None = None,
    negocio_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    user_filter = None if current_user.role == "admin" else current_user.sub
    return await service.list_projects(
        db, origem=origem, negocio_id=negocio_id, limit=limit, user_id_filter=user_filter
    )


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    project = await service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    project = await service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    if current_user.role != "admin" and project.solicitante_id != current_user.sub:
        raise HTTPException(status_code=403, detail="Sem permissão para excluir este projeto")
    await service.delete_project(db, project_id)


@router.delete("", response_model=BulkDeleteResponse)
async def bulk_delete_projects(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    deleted, forbidden = await service.bulk_delete_projects(
        db,
        request.ids,
        current_user.sub,
        current_user.role == "admin",
    )
    return BulkDeleteResponse(deleted=deleted, forbidden=forbidden)
