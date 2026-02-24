from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import require_api_key
from app.db.events import log_event
from app.db.session import get_conn
from app.db.ticket_id import next_ticket_id
from app.domain.agent_service import priority_from_signal, recommend_playbook
from app.domain.sla_service import compute_sla_due_at, get_sla_minutes_for_priority

router = APIRouter(prefix="/automation", tags=["automation"], dependencies=[Depends(require_api_key)])

Severity = Literal["critical", "high", "medium", "low"]
Decision = Literal["CREATED", "CORRELATED", "DUPLICATE"]


class ExternalTriggerRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    source_system: str = Field(min_length=1, max_length=128)
    event_id: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=128)
    severity: Severity = "medium"
    asset_id: str = Field(min_length=1, max_length=255)
    location: str = Field(default="", max_length=255)
    summary: str = Field(min_length=1, max_length=300)
    details: str = Field(default="", max_length=4000)
    occurred_at: datetime | None = None


class ExternalTriggerResponse(BaseModel):
    ticket_id: str
    status: str
    decision: Decision
    priority: str
    reason: str
    playbook: dict[str, str]


def _subject(event_type: str, summary: str) -> str:
    return f"[{event_type.strip().upper()}] {summary.strip()}"


def _load_automation_policy(conn, tenant_id: str) -> dict[str, str | int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT correlation_window_minutes, at_risk_lead_minutes, auto_assign_name, auto_assign_email
            FROM tenant_automation_policies
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        row = cur.fetchone()
    if row is None:
        return {
            "correlation_window_minutes": 1440,
            "at_risk_lead_minutes": 60,
            "auto_assign_name": "",
            "auto_assign_email": "",
        }
    return {
        "correlation_window_minutes": int(row[0]),
        "at_risk_lead_minutes": int(row[1]),
        "auto_assign_name": row[2] or "",
        "auto_assign_email": (row[3] or "").strip().lower(),
    }


class SlaMonitorRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    limit: int = Field(default=200, ge=1, le=2000)


class SlaMonitorResponse(BaseModel):
    tenant_id: str
    scanned: int
    at_risk_alerted: int
    breached_alerted: int
    ticket_ids: list[str]


@router.post("/external-intake", response_model=ExternalTriggerResponse)
def automation_external_intake(payload: ExternalTriggerRequest):
    priority, reason = priority_from_signal(payload.event_type, payload.severity)
    playbook = recommend_playbook(payload.event_type, payload.severity)
    event_at = payload.occurred_at or datetime.utcnow()

    with get_conn() as conn:
        conn.autocommit = False
        try:
            policy = _load_automation_policy(conn, payload.tenant_id)
            correlation_window_minutes = int(policy["correlation_window_minutes"])
            correlation_from = datetime.utcnow() - timedelta(minutes=correlation_window_minutes)
            auto_assign_name = str(policy["auto_assign_name"])
            auto_assign_email = str(policy["auto_assign_email"])

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticket_id
                    FROM external_trigger_events
                    WHERE tenant_id = %s AND source_system = %s AND event_id = %s
                    """,
                    (payload.tenant_id, payload.source_system, payload.event_id),
                )
                existing = cur.fetchone()
                if existing is not None:
                    conn.rollback()
                    return ExternalTriggerResponse(
                        ticket_id=existing[0],
                        status="OPEN",
                        decision="DUPLICATE",
                        priority=priority,
                        reason=reason,
                        playbook=playbook,
                    )

                subject = _subject(payload.event_type, payload.summary)
                cur.execute(
                    """
                    SELECT ticket_id, status
                    FROM tickets
                    WHERE tenant_id = %s
                      AND machine_serial = %s
                      AND status <> 'CLOSED'
                      AND subject = %s
                      AND created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (payload.tenant_id, payload.asset_id, subject, correlation_from),
                )
                correlated = cur.fetchone()
                if correlated is not None:
                    ticket_id = correlated[0]
                    log_event(
                        conn=conn,
                        ticket_id=ticket_id,
                        event_type="NOTE",
                        message=f"External trigger correlated: {payload.event_type}",
                        meta={
                            "source_system": payload.source_system,
                            "event_id": payload.event_id,
                            "severity": payload.severity,
                            "playbook": playbook,
                            "correlation_window_minutes": correlation_window_minutes,
                        },
                    )
                    cur.execute(
                        """
                        INSERT INTO external_trigger_events (
                          tenant_id, source_system, event_id, event_type, ticket_id, decision, payload
                        )
                        VALUES (%s, %s, %s, %s, %s, 'CORRELATED', %s::jsonb)
                        """,
                        (
                            payload.tenant_id,
                            payload.source_system,
                            payload.event_id,
                            payload.event_type,
                            ticket_id,
                            payload.model_dump_json(),
                        ),
                    )
                    conn.commit()
                    return ExternalTriggerResponse(
                        ticket_id=ticket_id,
                        status=correlated[1],
                        decision="CORRELATED",
                        priority=priority,
                        reason=reason,
                        playbook=playbook,
                    )

                ticket_id = next_ticket_id(conn)
                sla_minutes = get_sla_minutes_for_priority(conn, payload.tenant_id, priority)
                sla_due_at = compute_sla_due_at(event_at, sla_minutes)
                description = payload.details.strip() or payload.summary.strip()

                cur.execute(
                    """
                    INSERT INTO tickets (
                      ticket_id, tenant_id, status,
                      subject, priority, description_raw,
                      requester_name, requester_email, assignee_name, assignee_email,
                      machine_line, machine_station, machine_serial,
                      sla_due_at, first_response_at, resolved_at,
                      created_at, updated_at
                    )
                    VALUES (%s,%s,'OPEN', %s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,NULL,NULL, %s,%s)
                    """,
                    (
                        ticket_id,
                        payload.tenant_id,
                        subject,
                        priority,
                        description,
                        f"{payload.source_system} agent",
                        f"{payload.source_system.lower()}-agent@example.com",
                        auto_assign_name,
                        auto_assign_email,
                        payload.location,
                        payload.event_type,
                        payload.asset_id,
                        sla_due_at,
                        event_at,
                        event_at,
                    ),
                )
                log_event(
                    conn=conn,
                    ticket_id=ticket_id,
                    event_type="CREATED",
                    message="Ticket created by AI automation agent",
                    meta={
                        "source": "automation-external-intake",
                        "event_id": payload.event_id,
                        "event_type": payload.event_type,
                        "severity": payload.severity,
                        "priority_reason": reason,
                        "playbook": playbook,
                        "correlation_window_minutes": correlation_window_minutes,
                        "auto_assign_email": auto_assign_email or None,
                    },
                )
                cur.execute(
                    """
                    INSERT INTO external_trigger_events (
                      tenant_id, source_system, event_id, event_type, ticket_id, decision, payload
                    )
                    VALUES (%s, %s, %s, %s, %s, 'CREATED', %s::jsonb)
                    """,
                    (
                        payload.tenant_id,
                        payload.source_system,
                        payload.event_id,
                        payload.event_type,
                        ticket_id,
                        payload.model_dump_json(),
                    ),
                )

            conn.commit()
            return ExternalTriggerResponse(
                ticket_id=ticket_id,
                status="OPEN",
                decision="CREATED",
                priority=priority,
                reason=reason,
                playbook=playbook,
            )
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise


@router.post("/sla-monitor", response_model=SlaMonitorResponse)
def automation_sla_monitor(payload: SlaMonitorRequest):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            policy = _load_automation_policy(conn, payload.tenant_id)
            at_risk_lead_minutes = int(policy["at_risk_lead_minutes"])
            with conn.cursor() as cur:
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
                    (payload.tenant_id, payload.limit),
                )
                rows = cur.fetchall()

            now = datetime.utcnow()
            at_risk_alerted = 0
            breached_alerted = 0
            alerted_ticket_ids: list[str] = []

            for ticket_id, status, sla_due_at in rows:
                if status == "CLOSED" or sla_due_at is None:
                    continue
                seconds_left = (sla_due_at - now).total_seconds()
                alert_type: str | None = None
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
                    conn=conn,
                    ticket_id=ticket_id,
                    event_type="NOTE",
                    message=f"SLA alert {alert_type}: action required",
                    meta={
                        "source": "automation-sla-monitor",
                        "alert_type": alert_type,
                        "at_risk_lead_minutes": at_risk_lead_minutes,
                    },
                )
                alerted_ticket_ids.append(ticket_id)
                if alert_type == "AT_RISK":
                    at_risk_alerted += 1
                else:
                    breached_alerted += 1

            conn.commit()
            return SlaMonitorResponse(
                tenant_id=payload.tenant_id,
                scanned=len(rows),
                at_risk_alerted=at_risk_alerted,
                breached_alerted=breached_alerted,
                ticket_ids=alerted_ticket_ids,
            )
        except Exception:
            conn.rollback()
            raise
