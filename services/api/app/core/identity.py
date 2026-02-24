from app.core.config import get_settings


def resolve_actor(
    *,
    x_user_role: str | None,
    current_user,
) -> tuple[str, str]:
    settings = get_settings()

    if settings.enforce_auth and current_user is not None:
        return (current_user.email or "unknown@local").strip().lower(), (current_user.role or "unknown").strip().lower()

    role = (x_user_role or "").strip().lower() or "system"
    email = (getattr(current_user, "email", "") or "").strip().lower() or "system@local"
    return email, role
