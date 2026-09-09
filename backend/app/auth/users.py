import httpx

from app import emails
from app.config import settings


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": "application/json",
    }


def _auth_url(path: str) -> str:
    """Endpoint do GoTrue FORA do /admin."""
    return f"{settings.supabase_url}/auth/v1{path}"


def _admin_url(path: str) -> str:
    """Endpoint do GoTrue sob /admin — users, e só.

    O convite NÃO mora aqui. Ele é /auth/v1/invite, sem o /admin, e chamá-lo
    sob /admin devolve 404: a rota simplesmente não existe. Convidar usuário
    ficou quebrado até alguém tentar, porque o erro só aparece na hora do
    clique — não há como um 404 de URL montada errada aparecer antes disso.
    """
    return f"{settings.supabase_url}/auth/v1/admin{path}"


async def list_auth_users() -> list[dict]:
    async with httpx.AsyncClient() as client:
        r = await client.get(_admin_url("/users?per_page=200"), headers=_headers())
        r.raise_for_status()
        data = r.json()
        return data.get("users", data) if isinstance(data, dict) else data


def _corpo_do_convite(nome: str, link: str) -> str:
    return "\n".join([
        f"Olá, {nome}.",
        "",
        "Você foi convidado para a Calculadora MeuBESS.",
        "Use o link abaixo para definir sua senha e entrar:",
        "",
        link,
        "",
        "Se você não esperava este convite, ignore este e-mail.",
    ])


async def invite_auth_user(email: str, nome: str, role: str, redirect_to: str) -> dict:
    """Cria o convite e MANDA o e-mail por conta própria.

    O caminho óbvio seria POST /auth/v1/invite, que cria e envia. Ele funciona
    — o usuário nasce com invited_at preenchido — mas quem entrega é o mailer
    embutido do Supabase, que é para desenvolvimento: limite de poucos e-mails
    por hora e entrega ruim para domínio externo. O primeiro convite de
    verdade deste projeto simplesmente não chegou, sem erro em lugar nenhum.

    Então usamos /admin/generate_link, que devolve o link e NÃO envia nada, e
    o envio sai pelo Resend — domínio verificado, o mesmo caminho do feedback,
    que já está provado em produção.

    Diferente do feedback, aqui a falha de envio É o erro: sem o e-mail o
    convite não serve para nada. Por isso ela volta no retorno em vez de virar
    só um registro.
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _admin_url("/generate_link"),
            headers=_headers(),
            json={
                "type": "invite",
                "email": email,
                "data": {"nome": nome, "role": role},
                **({"redirect_to": redirect_to} if redirect_to else {}),
            },
        )
        r.raise_for_status()
        dados = r.json()

    link = dados.get("action_link") or (dados.get("properties") or {}).get("action_link")
    if not link:
        return {"email": email, "email_enviado": False,
                "erro": "Supabase não devolveu o link do convite"}

    enviado, erro = await emails.enviar(
        email, "Convite para a Calculadora MeuBESS", _corpo_do_convite(nome, link))
    return {"email": email, "email_enviado": enviado, "erro": erro}


async def update_auth_user(user_id: str, role: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.put(
            _admin_url(f"/users/{user_id}"),
            headers=_headers(),
            json={"user_metadata": {"role": role}},
        )
        r.raise_for_status()
        return r.json()


async def delete_auth_user(user_id: str) -> None:
    async with httpx.AsyncClient() as client:
        r = await client.delete(_admin_url(f"/users/{user_id}"), headers=_headers())
        r.raise_for_status()
