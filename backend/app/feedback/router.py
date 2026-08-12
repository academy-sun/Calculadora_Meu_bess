from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_user_or_api_key
from app.database import get_db
from app.feedback import service
from app.feedback.schemas import FeedbackCreate, FeedbackCreated, FeedbackRead

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackCreated)
async def criar_feedback(
    dados: FeedbackCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_user_or_api_key),
):
    """Recebe o relato de quem usa a calculadora.

    Aceita sessão (calculadora interna) OU API key (embed do Ploomes), que é o
    mesmo nível de confiança do /calculate — o embed não tem usuário logado.
    """
    fb = await service.registrar(db, dados, request.headers.get("user-agent"))
    return FeedbackCreated(id=str(fb.id), email_enviado=fb.email_enviado)


@router.get("", response_model=list[FeedbackRead])
async def listar_feedbacks(
    apenas_nao_lidos: bool = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Caixa de entrada. Admin: o relato pode conter preço e nome de cliente."""
    return await service.listar(db, apenas_nao_lidos=apenas_nao_lidos)


@router.patch("/{feedback_id}/lido", response_model=FeedbackRead)
async def marcar_lido(
    feedback_id: str,
    lido: bool = True,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    fb = await service.marcar_lido(db, feedback_id, lido)
    if fb is None:
        raise HTTPException(status_code=404, detail="Feedback não encontrado")
    return fb
