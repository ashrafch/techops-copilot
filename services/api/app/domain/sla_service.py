from datetime import datetime, timedelta
from typing import Literal


Priority = Literal["P1", "P2", "P3", "P4"]
SlaState = Literal["ON_TIME", "AT_RISK", "BREACHED", "NO_SLA", "CLOSED"]


def get_sla_minutes_for_priority(conn, tenant_id: str, priority: Priority) -> int:
    defaults = {"P1": 60, "P2": 240, "P3": 480, "P4": 1440}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p1_minutes, p2_minutes, p3_minutes, p4_minutes
            FROM tenant_sla_policies
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        row = cur.fetchone()

    if not row:
        return defaults[priority]

    tenant_map = {"P1": int(row[0]), "P2": int(row[1]), "P3": int(row[2]), "P4": int(row[3])}
    return tenant_map.get(priority, defaults[priority])


def compute_sla_due_at(now: datetime, sla_minutes: int) -> datetime:
    return now + timedelta(minutes=sla_minutes)


def compute_sla_state(status: str, sla_due_at: datetime | None, now: datetime | None = None) -> SlaState:
    if status == "CLOSED":
        return "CLOSED"
    if sla_due_at is None:
        return "NO_SLA"

    tnow = now or datetime.utcnow()
    if tnow >= sla_due_at:
        return "BREACHED"

    total_seconds_left = (sla_due_at - tnow).total_seconds()
    if total_seconds_left <= 3600:
        return "AT_RISK"

    return "ON_TIME"
