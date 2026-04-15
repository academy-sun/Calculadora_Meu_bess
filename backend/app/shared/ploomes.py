import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

async def create_ploomes_interaction(deal_id: str, content: str):
    """
    Cria uma interação (comentário) no negócio do Ploomes.
    """
    if not settings.api_key_ploomes:
        logger.warning("Ploomes API Key não configurada. Pulando registro de interação.")
        return False

    # O Ploomes espera DealId como inteiro em muitos endpoints, mas aqui é string vinda da req
    try:
        deal_id_int = int(deal_id)
    except (ValueError, TypeError):
        logger.error(f"ID do Negócio inválido para o Ploomes: {deal_id}")
        return False

    url = "https://api2.ploomes.com/Interactions"
    headers = {
        "User-Key": settings.api_key_ploomes,
        "Content-Type": "application/json"
    }
    
    payload = {
        "Content": content,
        "DealId": deal_id_int
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            
            if response.status_code in (200, 201):
                logger.info(f"Interação criada no Ploomes para o Negócio {deal_id}")
                return True
            else:
                logger.error(f"Erro ao criar interação no Ploomes: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Exceção ao integrar com Ploomes: {str(e)}")
        return False
