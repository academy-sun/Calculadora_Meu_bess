"""Notificação por e-mail do feedback recebido.

SMTP da stdlib, e não um serviço de e-mail transacional, por uma razão
prática: a MX3 já tem caixa em domínio próprio, então dá para ligar isto com
uma senha de app e nenhuma conta nova. Trocar por Resend/SendGrid depois é
substituir só `_enviar_sincrono`.

Desligado por padrão. Sem SMTP_HOST configurado, `enviar` devolve
(False, motivo) e o feedback fica só na caixa de entrada da plataforma — que
é o comportamento correto, não uma falha: o registro no banco é a fonte da
verdade, o e-mail é aviso em cima dele.
"""

import asyncio
import smtplib
from email.message import EmailMessage

from app.config import settings


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


def _enviar_sincrono(destinatario: str, assunto: str, corpo: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = destinatario
    msg.set_content(corpo)

    if settings.smtp_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)


async def enviar(fb) -> tuple[bool, str | None]:
    """(enviado, erro). Nunca levanta — o feedback já está gravado.

    Deixar uma exceção subir aqui faria o POST devolver 500 depois de gravar,
    e o autor reenviaria achando que não foi. Falha de e-mail vira registro em
    `email_erro`, visível na caixa de entrada.
    """
    destino = settings.feedback_email_to
    if not destino:
        return False, "FEEDBACK_EMAIL_TO não configurado"
    if not settings.smtp_host:
        return False, "SMTP_HOST não configurado"

    assunto = f"[Calculadora BESS] {fb.tipo or 'feedback'} — {fb.autor_nome or fb.origem}"
    try:
        # smtplib é bloqueante; numa rota async isso seguraria o event loop
        # inteiro pelo tempo do handshake TLS.
        await asyncio.to_thread(_enviar_sincrono, destino, assunto, _corpo(fb))
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"[:500]
