from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "FlagDrop"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./flagdrop.db"

    # JWT
    secret_key: str = "change-me-in-production-use-a-real-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_prefix": "FLAGDROP_", "env_file": ".env"}


settings = Settings()
