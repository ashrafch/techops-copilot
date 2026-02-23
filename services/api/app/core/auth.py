import hmac
import logging

from fastapi import Header, HTTPException

from app.core.config import get_settings

logger = logging.getLogger("app.auth")


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    api_key_required = settings.require_api_key or bool(settings.api_key)

    if not api_key_required:
        return

    if not settings.api_key:
        logger.error("API key required but API_KEY is not configured")
        raise HTTPException(status_code=503, detail="API auth not configured")

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        logger.warning("Unauthorized API request blocked")
        raise HTTPException(status_code=401, detail="Unauthorized")
