import hmac
import logging

from fastapi import Header, HTTPException

from app.core.auth_token import AuthTokenClaims, TokenError, verify_auth_token_with_secrets
from app.core.config import get_settings
from app.db.session import get_conn

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


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthTokenClaims | None:
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        if settings.enforce_auth:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return None

    token = authorization[len("Bearer ") :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        claims = verify_auth_token_with_secrets(token=token, secrets_list=settings.auth_signing_keys)
    except TokenError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if claims.typ != "access":
        raise HTTPException(status_code=401, detail="Unauthorized")
    if settings.enforce_auth:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT revoked_at
                FROM auth_sessions
                WHERE session_id = %s
                """,
                (claims.sid,),
            )
            row = cur.fetchone()
        if row is None or row[0] is not None:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return claims
