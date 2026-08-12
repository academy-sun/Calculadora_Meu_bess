from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    supabase_jwt_secret: str = ""
    api_key_ploomes: str = ""      # User-Key do Ploomes (saída) + key legada de entrada
    api_key_embed: str = ""        # key própria do embed Ploomes (entrada em /calculate e /ploomes/*)
    #: Chave do campo do USUÁRIO FINAL no Ploomes. Recebe a resposta filtrada
    #: (ver calculate/perfil.py). Separada de propósito: é ela que garante que
    #: editar o JavaScript do campo não dá acesso ao payload completo.
    api_key_embed_restrito: str = ""
    ploomes_field_map: str = ""    # JSON: nosso campo → FieldKey da conta (ver app/ploomes/context.py)
    environment: str = "development"

    # Supabase — Admin API (service role key) e origem do JWKS de autenticação
    supabase_url: str = "https://vxltorwxvxslhexaaqfs.supabase.co"
    supabase_service_role_key: str = ""

    # Plataforma MeuBess — supplier catalog API
    meubess_api_key: str = ""
    meubess_api_url: str = "https://plataforma.meubess.com.br/api/v1"

    # Feedback do usuário — notificação por e-mail (opcional).
    # Sem SMTP_HOST o feedback continua sendo gravado e aparece na caixa de
    # entrada da plataforma; o e-mail é aviso em cima do registro, não o
    # registro. Ver app/feedback/email.py.
    feedback_email_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_ssl: bool = False      # True para porta 465

    # Sync periódico do catálogo (preços). 3600 = de hora em hora.
    # 0 ou negativo desliga o agendador — usado nos testes e em dev, onde não
    # se quer bater na plataforma a cada execução.
    sync_intervalo_segundos: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
