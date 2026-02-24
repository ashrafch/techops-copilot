import json
from typing import Any


def log_admin_action(
    conn,
    *,
    tenant_id: str,
    actor_email: str,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    payload = details or {}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO admin_audit_logs (
              tenant_id,
              actor_email,
              actor_role,
              action,
              target_type,
              target_id,
              details
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                tenant_id.strip(),
                actor_email.strip().lower(),
                actor_role.strip().lower(),
                action.strip(),
                target_type.strip(),
                target_id.strip(),
                json.dumps(payload),
            ),
        )
