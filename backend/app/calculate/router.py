from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import verify_api_key
from pydantic import BaseModel

from app.calculate import perfil as perfil_mod
from app.calculate import reprecificar as reprecificar_mod
from app.calculate.reprecificar import ReprecificarRequest, ReprecificarResponse
from app.calculate.schemas import CalculateRequest, CalculateResponse
from app.calculate.service import run_calculation
from app.catalog import service as catalog_service
from app.database import get_db


#: Tipos que podem entrar num kit. Fora daqui não é produto cotável: os 51
#: 'indefinido' são os inversores de frequência CFW500, tirados do motor na
#: migration 012 — mas o picker os listava, porque estavam ativos e com
#: preço. Reclassificar sem filtrar aqui deixava a porta aberta pela tela.
TIPOS_COTAVEIS = (
    "inversor_hibrido", "inversor_string", "bateria", "modulo_fv", "acessorio",
)


class ProdutoParaKit(BaseModel):
    """Produto do catálogo para o picker do embed.

    `price` vem None no perfil restrito — a barreira é a mesma do
    /calculate: o valor não sai do servidor, em vez de sair e a tela
    esconder."""
    meubess_id: str
    title: str
    marca: str
    tipo: str
    price: float | None = None

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


@router.post("/calculate/reprecificar", response_model=ReprecificarResponse)
async def reprecificar_kit(
    req: ReprecificarRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """Totais de um kit editado na tela.

    Existe porque o perfil restrito não recebe preço unitário (ver
    calculate/perfil.py) e portanto não consegue somar nada no cliente. Recebe
    id + quantidade, devolve os totais que o perfil permite ver.
    """
    resp = await reprecificar_mod.reprecificar(db, req)
    if perfil_mod.resolver(api_key) == "restrito":
        return reprecificar_mod.limpar_para_restrito(resp)
    return resp


@router.get("/calculate/produtos", response_model=list[ProdutoParaKit])
async def produtos_para_kit(
    q: str | None = None,
    tipo: str | None = None,
    marca: str | None = None,
    potencia_min: float | None = None,
    potencia_max: float | None = None,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """Catálogo ativo para acrescentar item ao kit, autenticado por API KEY.

    O picker da calculadora interna usa GET /catalog/products, que exige JWT —
    o embed não tem usuário logado, só chave. Daí este endpoint próprio, com a
    mesma barreira de perfil: no restrito o preço não vem.
    """
    perfil = perfil_mod.resolver(api_key)
    produtos = await catalog_service.list_products(
        db, tipo=tipo, titulo=q, marca=marca,
        potencia_min=potencia_min, potencia_max=potencia_max,
        active=True, limit=800)
    restrito = perfil == "restrito"
    return [
        ProdutoParaKit(
            meubess_id=p.meubess_id,
            title=str(p.title or ""),
            marca=str(p.marca or ""),
            tipo=str(p.tipo_manual or p.tipo_auto or ""),
            price=None if restrito else (float(p.price) if p.price is not None else None),
        )
        for p in produtos
        if p.price is not None and float(p.price) > 0
        and str(p.tipo_manual or p.tipo_auto or "") in TIPOS_COTAVEIS
    ]
