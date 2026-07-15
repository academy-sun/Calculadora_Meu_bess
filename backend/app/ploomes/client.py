"""
Cliente HTTP da API Ploomes (https://api2.ploomes.com), autenticado por User-Key.

Substitui o antigo app/shared/ploomes.py: além do comentário (interaction),
expõe GET/POST/PATCH genéricos usados por context.py e pushback.py.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api2.ploomes.com"
TIMEOUT = 15.0


class PloomesError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Ploomes API {status_code}: {detail}")


def _headers() -> dict[str, str]:
    return {
        "User-Key": settings.api_key_ploomes,
        "Content-Type": "application/json",
    }


def _check_configured() -> None:
    if not settings.api_key_ploomes:
        raise PloomesError(503, "API_KEY_PLOOMES não configurada no backend")


async def get(path: str, params: dict | None = None) -> dict:
    _check_configured()
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}{path}", params=params, headers=_headers(), timeout=TIMEOUT)
    if resp.status_code != 200:
        raise PloomesError(resp.status_code, resp.text[:500])
    return resp.json()


async def post(path: str, json: dict) -> dict:
    _check_configured()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}{path}", json=json, headers=_headers(), timeout=TIMEOUT)
    if resp.status_code not in (200, 201):
        raise PloomesError(resp.status_code, resp.text[:500])
    return resp.json() if resp.text else {}


async def patch(path: str, json: dict) -> dict:
    _check_configured()
    async with httpx.AsyncClient() as client:
        resp = await client.patch(f"{BASE_URL}{path}", json=json, headers=_headers(), timeout=TIMEOUT)
    if resp.status_code not in (200, 204):
        raise PloomesError(resp.status_code, resp.text[:500])
    return resp.json() if resp.text else {}


async def create_ploomes_interaction(deal_id: str, content: str) -> bool:
    """Cria uma interação (comentário) no negócio. Fire-and-forget: nunca levanta."""
    if not settings.api_key_ploomes:
        logger.warning("Ploomes API Key não configurada. Pulando registro de interação.")
        return False
    try:
        deal_id_int = int(deal_id)
    except (ValueError, TypeError):
        logger.error(f"ID do Negócio inválido para o Ploomes: {deal_id}")
        return False
    try:
        await post("/Interactions", {"Content": content, "DealId": deal_id_int})
        logger.info(f"Interação criada no Ploomes para o Negócio {deal_id}")
        return True
    except Exception as e:
        logger.error(f"Exceção ao integrar com Ploomes: {e}")
        return False
