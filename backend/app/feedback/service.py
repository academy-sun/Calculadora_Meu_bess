from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feedback import email as email_mod
from app.feedback.models import Feedback
from app.feedback.schemas import FeedbackCreate


async def registrar(db: AsyncSession, dados: FeedbackCreate,
                    user_agent: str | None) -> Feedback:
    """Grava e tenta notificar, NESTA ordem.

    Gravar primeiro é o ponto: se o e-mail falhar, o relato continua existindo.
    O contrário — mandar e-mail e só depois gravar — perde o feedback quando o
    banco recusa, e quem escreveu não fica sabendo.
    """
    fb = Feedback(
        origem=dados.origem,
        tipo=dados.tipo,
        mensagem=dados.mensagem.strip(),
        autor_nome=dados.autor_nome,
        autor_email=dados.autor_email,
        contexto=dados.contexto,
        url=dados.url,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    enviado, erro = await email_mod.enviar(fb)
    fb.email_enviado = enviado
    fb.email_erro = erro
    await db.commit()
    await db.refresh(fb)
    return fb


async def listar(db: AsyncSession, apenas_nao_lidos: bool = False,
                 limit: int = 200) -> list[Feedback]:
    stmt = select(Feedback).order_by(Feedback.criado_em.desc()).limit(limit)
    if apenas_nao_lidos:
        stmt = stmt.where(Feedback.lido.is_(False))
    return list((await db.execute(stmt)).scalars().all())


async def marcar_lido(db: AsyncSession, feedback_id: str, lido: bool) -> Feedback | None:
    fb = await db.get(Feedback, feedback_id)
    if fb is None:
        return None
    fb.lido = lido
    await db.commit()
    await db.refresh(fb)
    return fb
