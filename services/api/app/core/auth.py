import hmac

from fastapi import Header, HTTPException

from app.core.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()

    # Backward-compatible mode: if API_KEY is empty, auth is disabled.
    if not settings.api_key:
        return

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
