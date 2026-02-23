from fastapi import Header, HTTPException

from app.core.config import get_settings


def require_operator_role(x_user_role: str | None = Header(default=None, alias="X-User-Role")) -> None:
    settings = get_settings()
    if not settings.enforce_rbac:
        return

    role = (x_user_role or "").strip().lower()
    if role not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Forbidden: operator role required")
