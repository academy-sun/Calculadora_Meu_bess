"""Notificação por e-mail do feedback recebido, via Resend.

Antes era SMTP da caixa da MX3. O domínio está no Microsoft 365, que desliga
SMTP autenticado por padrão desde 2022 — liberar exige mexer em política de
tenant, e o resultado dependeria de uma senha de caixa guardada no servidor.
O Resend troca isso por uma chave de API revogável e um domínio verificado.

Desligado por padrão. Sem RESEND_API_KEY, `enviar` devolve (False, motivo) e
o feedback fica só na caixa de entrada da plataforma — que é o comportamento
correto, não uma falha: o registro no banco é a fonte da verdade, o e-mail é
aviso em cima dele.
"""

import httpx

from app.config import settings

_URL = "https://api.resend.com/emails"

#: O feedback é aviso, não transação. Se o Resend estiver lento, quem paga a
#: espera é a pessoa que clicou em enviar — e ela já teve o relato gravado.
_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


def _corpo(fb) -> str:
    linhas = [
        f"Origem:  {fb.origem}",
        f"Tipo:    {fb.tipo or '—'}",
        f"Autor:   {fb.autor_nome or '—'} {f'<{fb.autor_email}>' if fb.autor_email else ''}".strip(),
        f"Quando:  {fb.criado_em:%d/%m/%Y %H:%M} UTC" if fb.criado_em else "",
        f"URL:     {fb.url or '—'}",
        "",
        "─" * 60,
        fb.mensagem,
        "─" * 60,
    ]
    if fb.contexto:
        import json
        # O contexto vai inteiro e legível: é com ele que se reproduz o caso,
        # e resumir aqui obrigaria a abrir a plataforma para ver o que falta.
        linhas += ["", "Contexto do cálculo:", json.dumps(fb.contexto, indent=2,
                                                          ensure_ascii=False)[:4000]]
    return "\n".join(l for l in linhas if l != "")


async def _postar(payload: dict) -> None:
    """POST no Resend. Levanta em erro de rede ou status != 2xx."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        )
        resp.raise_for_status()


async def enviar(fb) -> tuple[bool, str | None]:
    """(enviado, erro). Nunca levanta — o feedback já está gravado.

    Deixar uma exceção subir aqui faria o POST devolver 500 depois de gravar,
    e o autor reenviaria achando que não foi. Falha de e-mail vira registro em
    `email_erro`, visível na caixa de entrada.
    """
    destino = settings.feedback_email_to
    if not destino:
        return False, "FEEDBACK_EMAIL_TO não configurado"
    if not settings.resend_api_key:
        return False, "RESEND_API_KEY não configurada"
    if not settings.feedback_email_from:
        return False, "FEEDBACK_EMAIL_FROM não configurado"

    assunto = f"[Calculadora BESS] {fb.tipo or 'feedback'} — {fb.autor_nome or fb.origem}"
    try:
        await _postar({
            "from": settings.feedback_email_from,
            "to": [destino],
            "subject": assunto,
            "text": _corpo(fb),
        })
        return True, None
    except httpx.HTTPStatusError as exc:
        # O corpo do erro do Resend é a parte útil ("domain is not verified",
        # "invalid from address"). Sem ele sobra "400 Bad Request", que não
        # diz o que corrigir.
        return False, f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"[:500]
