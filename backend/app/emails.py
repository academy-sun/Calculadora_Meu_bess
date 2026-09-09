"""Envio de e-mail transacional pelo Resend.

Ponto ÚNICO que fala com o provedor. Antes isso morava dentro de
feedback/email.py, e quando o convite de usuário também precisou de e-mail a
escolha era duplicar o transporte ou compartilhá-lo. Duplicar significaria
duas chaves, dois timeouts e dois tratamentos de erro para manter em dia.

Desligado por padrão. Sem RESEND_API_KEY, `enviar` devolve (False, motivo) e
quem chamou decide o que fazer — para o feedback isso é aceitável (o registro
no banco é a fonte da verdade); para o convite, não é, e o chamador precisa
dizer isso a quem clicou.
"""

import httpx

from app.config import settings

_URL = "https://api.resend.com/emails"

#: Nenhum e-mail nosso é transação: se o Resend estiver lento, quem paga a
#: espera é a pessoa que clicou.
_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


async def _postar(payload: dict) -> None:
    """POST no Resend. Levanta em erro de rede ou status != 2xx."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        )
        resp.raise_for_status()


async def enviar(destino: str, assunto: str, texto: str) -> tuple[bool, str | None]:
    """(enviado, erro). NUNCA levanta — quem chama decide a gravidade."""
    if not destino:
        return False, "destinatário vazio"
    if not settings.resend_api_key:
        return False, "RESEND_API_KEY não configurada"
    if not settings.feedback_email_from:
        return False, "FEEDBACK_EMAIL_FROM não configurado"
    try:
        await _postar({
            "from": settings.feedback_email_from,
            "to": [destino],
            "subject": assunto,
            "text": texto,
        })
        return True, None
    except httpx.HTTPStatusError as exc:
        # O corpo do erro do Resend é a parte útil ("domain is not verified",
        # "invalid from address"). Sem ele sobra "400 Bad Request".
        return False, f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"[:500]
