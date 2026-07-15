from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import verify_api_key
from app.ploomes import context, pushback
from app.ploomes.client import PloomesError
from app.ploomes.schemas import PushbackRequest

router = APIRouter(prefix="/ploomes", tags=["ploomes"], dependencies=[Depends(verify_api_key)])


@router.get("/context/{deal_id}")
async def get_context(deal_id: int) -> dict:
    """Prefill do embed: kWp, cidade/UF, estrutura e campos crus do negócio."""
    try:
        return await context.get_deal_context(deal_id)
    except PloomesError as e:
        raise HTTPException(status_code=e.status_code if e.status_code >= 400 else 502,
                            detail=e.detail)


@router.get("/fields")
async def get_fields(entity_id: int | None = None) -> list[dict]:
    """Descoberta de FieldKeys da conta para montar o PLOOMES_FIELD_MAP."""
    try:
        return await context.list_fields(entity_id)
    except PloomesError as e:
        raise HTTPException(status_code=502, detail=e.detail)


@router.post("/pushback")
async def post_pushback(req: PushbackRequest) -> dict:
    """Grava o resultado do dimensionamento no Ploomes (campos + itens + comentário)."""
    try:
        return await pushback.push_result(req)
    except PloomesError as e:
        raise HTTPException(status_code=502, detail=e.detail)
