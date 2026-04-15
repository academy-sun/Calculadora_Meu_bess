from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from jose import JWTError, jwt

from app.auth.schemas import UserInToken
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserInToken:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token não fornecido")
    token = credentials.credentials
    try:
        # Diagnostic log
        header = jwt.get_unverified_header(token)
        print(f"DEBUG JWT: Header={header}")

        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret.strip(),
            algorithms=["HS256", "RS256", "HS384", "HS512"],
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
    if not api_key or api_key != settings.api_key_ploomes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key inválida")
    return api_key
