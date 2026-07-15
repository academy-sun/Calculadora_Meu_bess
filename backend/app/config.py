from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    supabase_jwt_secret: str = ""
    api_key_ploomes: str = ""      # User-Key do Ploomes (saída) + key legada de entrada
    api_key_embed: str = ""        # key própria do embed Ploomes (entrada em /calculate e /ploomes/*)
    ploomes_field_map: str = ""    # JSON: nosso campo → FieldKey da conta (ver app/ploomes/context.py)
    environment: str = "development"

    # Supabase — Admin API (service role key)
    supabase_url: str = "https://debiageyayshcvbpivdq.supabase.co"
    supabase_service_role_key: str = ""

    # Plataforma MeuBess — supplier catalog API
    meubess_api_key: str = ""
    meubess_api_url: str = "https://plataforma.meubess.com.br/api/v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
