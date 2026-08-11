import threading

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from jose import JWTError, jwt

from app.auth.schemas import UserInToken
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# Chaves públicas (JWKS) do projeto Supabase, buscadas sob demanda e mantidas em
# memória. Antes ficavam hardcoded aqui, o que quebrava a autenticação inteira ao
# trocar de projeto — cada projeto assina com um kid diferente.
_jwks_cache: dict[str, dict] = {}
_jwks_lock = threading.Lock()


def _jwks_url() -> str:
    return f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


def get_signing_key(kid: str) -> dict | None:
    """Chave pública para o `kid` do token. Rebusca o JWKS quando o kid é
    desconhecido (rotação de chave / troca de projeto)."""
    with _jwks_lock:
        cached = _jwks_cache.get(kid)
    if cached:
        return cached

    try:
        resp = httpx.get(_jwks_url(), timeout=5.0)
        resp.raise_for_status()
        keys = {k["kid"]: k for k in resp.json().get("keys", []) if k.get("kid")}
    except Exception as e:  # rede/JSON inválido — cai no segredo simétrico
        print(f"ERRO JWKS: falha ao buscar {_jwks_url()}: {e}")
        return None

    with _jwks_lock:
        _jwks_cache.update(keys)
        return _jwks_cache.get(kid)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserInToken:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token não fornecido")
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        alg = header.get("alg")

        # Selecionar a chave de validação correta
        jwk = get_signing_key(kid) if (alg == "ES256" and kid) else None
        if jwk:
            key = jwk
            print(f"INFO JWT: Usando chave pública (JWK) para kid={kid}")
        else:
            key = settings.supabase_jwt_secret.strip()
            print("INFO JWT: Usando segredo simétrico configurado")

        payload = jwt.decode(
            token,
            key,
            algorithms=["HS256", "RS256", "ES256", "HS384", "HS512"],
            options={"verify_aud": False},
        )
        user_metadata = payload.get("user_metadata", {})
        return UserInToken(
            sub=payload["sub"],
            email=payload.get("email", ""),
            role=user_metadata.get("role", "engineer"),
        )
    except JWTError as e:
        print(f"ERRO JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"Token inválido ou expirado: {str(e)}"
        )


def require_admin(user: UserInToken = Depends(get_current_user)) -> UserInToken:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a admins")
    return user


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    valid_keys = {k for k in (settings.api_key_ploomes, settings.api_key_embed,
                              settings.api_key_embed_restrito) if k}
    if not api_key or api_key not in valid_keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key inválida")
    return api_key


def require_user_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Security(api_key_header),
) -> None:
    """Endpoints de leitura só-catálogo: aceita sessão Supabase (app interno) OU
    a API key do embed Ploomes (sem login) — mesmo nível de confiança do /calculate."""
    valid_keys = {k for k in (settings.api_key_ploomes, settings.api_key_embed,
                              settings.api_key_embed_restrito) if k}
    if api_key and api_key in valid_keys:
        return
    if credentials:
        get_current_user(credentials)
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária")
