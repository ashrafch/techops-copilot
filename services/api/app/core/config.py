import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str
    log_level: str
    app_env: str
    database_url: str
    db_connect_timeout_seconds: int
    api_key: str
    require_api_key: bool
    rate_limit_requests_per_minute: int
    cors_allowed_origins: list[str]
    enforce_rbac: bool
    enforce_auth: bool
    auth_secret_key: str
    auth_token_ttl_minutes: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    require_api_key_raw = os.getenv("REQUIRE_API_KEY", "false").strip().lower()
    cors_allowed_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    cors_allowed_origins = [
        origin.strip() for origin in cors_allowed_origins_raw.split(",") if origin.strip()
    ]
    enforce_rbac_raw = os.getenv("ENFORCE_RBAC", "false").strip().lower()
    enforce_auth_raw = os.getenv("ENFORCE_AUTH", "false").strip().lower()
    return Settings(
        app_name=os.getenv("APP_NAME", "TechOps Copilot API"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        app_env=os.getenv("APP_ENV", "dev"),
        database_url=os.getenv("DATABASE_URL", ""),
        db_connect_timeout_seconds=int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
        api_key=os.getenv("API_KEY", ""),
        require_api_key=require_api_key_raw in {"1", "true", "yes", "on"},
        rate_limit_requests_per_minute=int(os.getenv("RATE_LIMIT_RPM", "0")),
        cors_allowed_origins=cors_allowed_origins,
        enforce_rbac=enforce_rbac_raw in {"1", "true", "yes", "on"},
        enforce_auth=enforce_auth_raw in {"1", "true", "yes", "on"},
        auth_secret_key=os.getenv("AUTH_SECRET_KEY", "dev_auth_secret_change_me"),
        auth_token_ttl_minutes=int(os.getenv("AUTH_TOKEN_TTL_MINUTES", "480")),
    )
