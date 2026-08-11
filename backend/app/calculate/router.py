from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import verify_api_key
from app.calculate import perfil as perfil_mod
from app.calculate.schemas import CalculateRequest, CalculateResponse
from app.calculate.service import run_calculation
from app.database import get_db

router = APIRouter(tags=["calculate"])


@router.post("/calculate", response_model=CalculateResponse)
async def calculate(
    req: CalculateRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Endpoint principal de cálculo. Autenticado via API Key (X-API-Key header).
    Aceita requisições do Ploomes ou da interface interna.

    A resposta é filtrada pelo perfil de quem chamou (ver calculate/perfil.py):
    o campo do usuário final no Ploomes usa uma chave própria e recebe a versão
    sem valores unitários, sem frete detalhado e sem diagnóstico. O filtro é
    aqui e não na tela — na tela, os valores continuariam na resposta HTTP.
    """
    resp = await run_calculation(db, req)
    return perfil_mod.aplicar(resp, perfil_mod.resolver(api_key))
