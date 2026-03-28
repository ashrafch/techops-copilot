from datetime import datetime

from app.db.events import log_event
from app.db.session import get_conn


def run_sla_monitor_for_tenant(tenant_id: str, limit: int = 500) -> dict[str, int]:
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(at_risk_lead_minutes, 60)
                    FROM tenant_automation_policies
                    WHERE tenant_id = %s
                    """,
                    (tenant_id,),
                )
                row = cur.fetchone()
                at_risk_lead_minutes = int(row[0]) if row else 60

                cur.execute(
                    """
                    SELECT ticket_id, status, sla_due_at
                    FROM tickets
                    WHERE tenant_id = %s
                      AND status <> 'CLOSED'
                      AND sla_due_at IS NOT NULL
                    ORDER BY sla_due_at ASC
                    LIMIT %s
                    """,
                    (tenant_id, limit),
                )
                rows = cur.fetchall()

            now = datetime.utcnow()
            at_risk_alerted = 0
            breached_alerted = 0

            for ticket_id, status, sla_due_at in rows:
                if status == "CLOSED" or sla_due_at is None:
                    continue
                seconds_left = (sla_due_at - now).total_seconds()
                alert_type = None
                if seconds_left <= 0:
                    alert_type = "BREACHED"
                elif seconds_left <= at_risk_lead_minutes * 60:
                    alert_type = "AT_RISK"
                if alert_type is None:
                    continue

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ticket_sla_alerts (ticket_id, alert_type)
                        VALUES (%s, %s)
                        ON CONFLICT (ticket_id, alert_type) DO NOTHING
                        RETURNING id
                        """,
                        (ticket_id, alert_type),
                    )
                    inserted = cur.fetchone()
                if inserted is None:
                    continue

                log_event(
                    conn,
                    ticket_id=ticket_id,
                    event_type="NOTE",
                    message=f"SLA alert {alert_type}: action required",
                    meta={"source": "scheduler-sla-monitor", "alert_type": alert_type},
                )
                if alert_type == "AT_RISK":
                    at_risk_alerted += 1
                else:
                    breached_alerted += 1

            conn.commit()
            return {
                "scanned": len(rows),
                "at_risk_alerted": at_risk_alerted,
                "breached_alerted": breached_alerted,
            }
        except Exception:
            conn.rollback()
            raise


def list_tenants_for_scheduler() -> list[str]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT tenant_id FROM tenant_automation_policies ORDER BY tenant_id ASC")
        rows = cur.fetchall()
    return [str(r[0]) for r in rows]
