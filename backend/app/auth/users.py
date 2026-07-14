import httpx
from app.config import settings


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": "application/json",
    }


def _admin_url(path: str) -> str:
    return f"{settings.supabase_url}/auth/v1/admin{path}"


async def list_auth_users() -> list[dict]:
    async with httpx.AsyncClient() as client:
        r = await client.get(_admin_url("/users?per_page=200"), headers=_headers())
        r.raise_for_status()
        data = r.json()
        return data.get("users", data) if isinstance(data, dict) else data


async def invite_auth_user(email: str, nome: str, role: str, redirect_to: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _admin_url("/invite"),
            headers=_headers(),
            json={"email": email, "data": {"nome": nome, "role": role}, "redirect_to": redirect_to},
        )
        r.raise_for_status()
        return r.json()


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
