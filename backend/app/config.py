from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    supabase_jwt_secret: str = ""
    #: Chave do campo de ADMIN no Ploomes. Recebe a resposta completa.
    #: A calculadora interna NÃO usa chave — ela exige login e manda a sessão
    #: do Supabase. Ter uma chave no build significava publicá-la: variável
    #: VITE_* é compilada dentro do JavaScript, que é servido a qualquer um.
    api_key_embed: str = ""
    #: Chave do campo do USUÁRIO FINAL no Ploomes. Recebe a resposta filtrada
    #: (ver calculate/perfil.py). Separada de propósito: é ela que garante que
    #: editar o JavaScript do campo não dá acesso ao payload completo.
    api_key_embed_restrito: str = ""
    environment: str = "development"

    # Supabase — Admin API (service role key) e origem do JWKS de autenticação
    supabase_url: str = "https://vxltorwxvxslhexaaqfs.supabase.co"
    supabase_service_role_key: str = ""

    # Plataforma MeuBess — supplier catalog API
    meubess_api_key: str = ""
    meubess_api_url: str = "https://plataforma.meubess.com.br/api/v1"

    #: Aponta um produto (id ou trecho do título) para o sync despejar o JSON
    #: cru dele no log. Vazio = desligado. Serve para mostrar à MeuBESS o que a
    #: API deles devolve de fato — a plataforma só é alcançável de dentro do
    #: container, então não dá para consultar da máquina de quem desenvolve.
    sync_debug_produto: str = ""

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
