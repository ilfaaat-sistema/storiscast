from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "media"
    FERNET_KEY: str
    DEFAULT_TENANT_ID: str = "00000000-0000-0000-0000-000000000001"

    # Phase 6 — multi-tenancy auth
    SUPABASE_JWT_SECRET: str = ""  # Supabase → Settings → API → JWT Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Phase 1 — VK
    VK_ACCESS_TOKEN: str = ""

    # Phase 2 — Telegram
    TG_API_ID: int = 0
    TG_API_HASH: str = ""
    TG_SESSION_STRING: str = ""

    # Phase 3 — Instagram
    IG_ACCESS_TOKEN: str = ""
    IG_USER_ID: str = ""
    IG_GRAPH_API_VERSION: str = "v21.0"

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")


settings = Settings()
