from fastapi import Depends, Header, HTTPException

from app.core.auth import get_current_user
from app.core.config import get_settings


def _resolve_role(
    x_user_role: str | None,
    current_user,
) -> str:
    settings = get_settings()
    if settings.enforce_auth:
        if current_user is None:
            return ""
        return (current_user.role or "").strip().lower()
    return (x_user_role or "").strip().lower()


def require_operator_role(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
) -> None:
    settings = get_settings()
    if not settings.enforce_rbac:
        return

    role = _resolve_role(x_user_role=x_user_role, current_user=current_user)
    if role not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Forbidden: operator role required")


def require_admin_role(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
) -> None:
    settings = get_settings()
    if not settings.enforce_rbac:
        return

    role = _resolve_role(x_user_role=x_user_role, current_user=current_user)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: admin role required")


def require_viewer_role(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
) -> None:
    settings = get_settings()
    if not settings.enforce_rbac:
        return

    role = _resolve_role(x_user_role=x_user_role, current_user=current_user)
    if role not in {"admin", "operator", "viewer"}:
        raise HTTPException(status_code=403, detail="Forbidden: viewer role required")
