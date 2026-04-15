from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import verify_api_key
from app.calculate.schemas import CalculateRequest, CalculateResponse
from app.calculate.service import run_calculation
from app.database import get_db

router = APIRouter(tags=["calculate"])


@router.post("/calculate", response_model=CalculateResponse)
async def calculate(
    req: CalculateRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Endpoint principal de cálculo. Autenticado via API Key (X-API-Key header).
    Aceita requisições do Ploomes ou da interface interna.
    """
    return await run_calculation(db, req)
