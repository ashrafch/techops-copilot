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
    auth_signing_keys: list[str]
    auth_token_ttl_minutes: int
    auth_refresh_ttl_minutes: int
    auth_require_mfa_for_admin: bool
    auth_mfa_bootstrap_code: str
    auth_max_failed_logins: int
    auth_lockout_minutes: int
    password_min_length: int
    password_require_upper: bool
    password_require_lower: bool
    password_require_digit: bool
    password_require_symbol: bool
    security_log_retention_days: int
    enforce_tenant_isolation: bool
    sla_monitor_scheduler_enabled: bool
    sla_monitor_scheduler_interval_seconds: int
    sso_default_audience: str
    sso_default_issuer: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    require_api_key_raw = os.getenv("REQUIRE_API_KEY", "false").strip().lower()
    cors_allowed_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    cors_allowed_origins = [
        origin.strip() for origin in cors_allowed_origins_raw.split(",") if origin.strip()
    ]
    enforce_rbac_raw = os.getenv("ENFORCE_RBAC", "false").strip().lower()
    enforce_auth_raw = os.getenv("ENFORCE_AUTH", "false").strip().lower()
    auth_require_mfa_for_admin_raw = os.getenv("AUTH_REQUIRE_MFA_FOR_ADMIN", "false").strip().lower()
    auth_secret_key = os.getenv("AUTH_SECRET_KEY", "dev_auth_secret_change_me")
    auth_secret_keys_raw = os.getenv("AUTH_SECRET_KEYS", "")
    parsed_keys = [k.strip() for k in auth_secret_keys_raw.split(",") if k.strip()]
    auth_signing_keys = [auth_secret_key] + [k for k in parsed_keys if k != auth_secret_key]
    enforce_tenant_isolation_raw = os.getenv("ENFORCE_TENANT_ISOLATION", "true").strip().lower()
    scheduler_enabled_raw = os.getenv("SLA_MONITOR_SCHEDULER_ENABLED", "false").strip().lower()
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
        auth_secret_key=auth_secret_key,
        auth_signing_keys=auth_signing_keys,
        auth_token_ttl_minutes=int(os.getenv("AUTH_TOKEN_TTL_MINUTES", "480")),
        auth_refresh_ttl_minutes=int(os.getenv("AUTH_REFRESH_TTL_MINUTES", "10080")),
        auth_require_mfa_for_admin=auth_require_mfa_for_admin_raw in {"1", "true", "yes", "on"},
        auth_mfa_bootstrap_code=os.getenv("AUTH_MFA_BOOTSTRAP_CODE", "000000").strip(),
        auth_max_failed_logins=int(os.getenv("AUTH_MAX_FAILED_LOGINS", "5")),
        auth_lockout_minutes=int(os.getenv("AUTH_LOCKOUT_MINUTES", "15")),
        password_min_length=int(os.getenv("PASSWORD_MIN_LENGTH", "12")),
        password_require_upper=os.getenv("PASSWORD_REQUIRE_UPPER", "true").strip().lower() in {"1", "true", "yes", "on"},
        password_require_lower=os.getenv("PASSWORD_REQUIRE_LOWER", "true").strip().lower() in {"1", "true", "yes", "on"},
        password_require_digit=os.getenv("PASSWORD_REQUIRE_DIGIT", "true").strip().lower() in {"1", "true", "yes", "on"},
        password_require_symbol=os.getenv("PASSWORD_REQUIRE_SYMBOL", "true").strip().lower() in {"1", "true", "yes", "on"},
        security_log_retention_days=int(os.getenv("SECURITY_LOG_RETENTION_DAYS", "90")),
        enforce_tenant_isolation=enforce_tenant_isolation_raw in {"1", "true", "yes", "on"},
        sla_monitor_scheduler_enabled=scheduler_enabled_raw in {"1", "true", "yes", "on"},
        sla_monitor_scheduler_interval_seconds=int(os.getenv("SLA_MONITOR_SCHEDULER_INTERVAL_SECONDS", "300")),
        sso_default_audience=os.getenv("SSO_DEFAULT_AUDIENCE", "techops-copilot"),
        sso_default_issuer=os.getenv("SSO_DEFAULT_ISSUER", "techops-sso"),
    )
