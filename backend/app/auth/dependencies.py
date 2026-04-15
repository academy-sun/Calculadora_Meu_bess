from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from jose import JWTError, jwt

from app.auth.schemas import UserInToken
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# Chave Pública oficial do Supabase para o projeto debiageyayshcvbpivdq (tipo ES256)
SUPABASE_JWKS = {
    "deb3cc32-0a35-49b1-8a49-55883e681ef1": {
        "alg": "ES256",
        "crv": "P-256",
        "ext": True,
        "key_ops": ["verify"],
        "kid": "deb3cc32-0a35-49b1-8a49-55883e681ef1",
        "kty": "EC",
        "use": "sig",
        "x": "eXk4KKjR4hpWDQ_36cVwCGkaFADziEp3MQhf7AEN80A",
        "y": "esUW4h5OYWDLBjyA83px9u3w9D35Ht8eOJkF_mms78c"
    }
}

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

        kid = header.get("kid")
        alg = header.get("alg")
        
        # Selecionar a chave de validação correta
        if alg == "ES256" and kid in SUPABASE_JWKS:
            key = SUPABASE_JWKS[kid]
            print(f"INFO JWT: Usando chave pública (JWK) para kid={kid}")
        else:
            key = settings.supabase_jwt_secret.strip()
            print(f"INFO JWT: Usando segredo simétrico configurado")

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
    if not api_key or api_key != settings.api_key_ploomes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key inválida")
    return api_key
