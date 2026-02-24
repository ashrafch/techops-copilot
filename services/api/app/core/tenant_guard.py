from fastapi import HTTPException

from app.core.auth_token import AuthTokenClaims
from app.core.config import get_settings


def enforce_tenant_access(*, requested_tenant_id: str, current_user: AuthTokenClaims | None) -> None:
    settings = get_settings()
    if not settings.enforce_auth or not settings.enforce_tenant_isolation:
        return
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    role = (current_user.role or "").strip().lower()
    if role == "admin":
        return
    if requested_tenant_id.strip() != (current_user.tenant_id or "").strip():
        raise HTTPException(status_code=403, detail="Forbidden: cross-tenant access denied")
