from datetime import datetime
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


@router.post("/external-intake", response_model=ExternalTriggerResponse)
def automation_external_intake(payload: ExternalTriggerRequest):
    priority, reason = priority_from_signal(payload.event_type, payload.severity)
    playbook = recommend_playbook(payload.event_type, payload.severity)
    event_at = payload.occurred_at or datetime.utcnow()

    with get_conn() as conn:
        conn.autocommit = False
        try:
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
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (payload.tenant_id, payload.asset_id, subject),
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
                      requester_name, requester_email,
                      machine_line, machine_station, machine_serial,
                      sla_due_at, first_response_at, resolved_at,
                      created_at, updated_at
                    )
                    VALUES (%s,%s,'OPEN', %s,%s,%s, %s,%s, %s,%s,%s, %s,NULL,NULL, %s,%s)
                    """,
                    (
                        ticket_id,
                        payload.tenant_id,
                        subject,
                        priority,
                        description,
                        f"{payload.source_system} agent",
                        f"{payload.source_system.lower()}-agent@example.com",
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
