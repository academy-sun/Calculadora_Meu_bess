from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    supabase_jwt_secret: str = ""
    api_key_ploomes: str = ""
    environment: str = "development"

    # Plataforma MeuBess — supplier catalog API
    meubess_api_key: str = ""
    meubess_api_url: str = "https://plataforma.meubess.com.br/api/v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
