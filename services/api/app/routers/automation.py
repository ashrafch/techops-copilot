import json
from datetime import datetime, timedelta
from typing import Literal
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import require_api_key
from app.db.events import log_event
from app.db.session import get_conn
from app.db.ticket_id import next_ticket_id
from app.domain.agent_service import priority_from_signal, recommend_playbook
from app.domain.sla_service import compute_sla_due_at, compute_sla_state, get_sla_minutes_for_priority

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
    confidence: float
    memory_hint: str
    playbook: dict[str, str]


class SlaMonitorRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    limit: int = Field(default=200, ge=1, le=2000)


class SlaMonitorResponse(BaseModel):
    tenant_id: str
    scanned: int
    at_risk_alerted: int
    breached_alerted: int
    ticket_ids: list[str]


class DecisionLogOut(BaseModel):
    id: int
    tenant_id: str
    ticket_id: str
    source_system: str
    event_id: str
    event_type: str
    severity: str
    decision: str
    priority: str
    reason: str
    confidence: float
    memory_hint: str
    playbook: dict[str, str]
    created_at: datetime


class ActionRunOut(BaseModel):
    id: int
    tenant_id: str
    ticket_id: str
    action_name: str
    status: str
    detail: str
    request_payload: dict
    response_payload: dict
    created_at: datetime


class MemoryFeedbackIn(BaseModel):
    tenant_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(min_length=1, max_length=128)
    asset_id: str = Field(min_length=1, max_length=255)
    outcome_score: int = Field(ge=1, le=5)
    resolution_note: str = Field(default="", max_length=4000)


class MemorySuggestionOut(BaseModel):
    ticket_id: str
    outcome_score: int
    resolution_note: str
    created_at: datetime


class ProactiveActionOut(BaseModel):
    ticket_id: str
    priority: str
    sla_state: str
    recommendation: str


class ProactiveSummaryOut(BaseModel):
    tenant_id: str
    predicted_breach_2h: int
    unassigned_open: int
    next_best_actions: list[ProactiveActionOut]


def _subject(event_type: str, summary: str) -> str:
    return f"[{event_type.strip().upper()}] {summary.strip()}"


def _load_automation_policy(conn, tenant_id: str) -> dict[str, str | int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT correlation_window_minutes, at_risk_lead_minutes,
                   auto_assign_name, auto_assign_email,
                   action_webhook_url, action_webhook_token
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
            "action_webhook_url": "",
            "action_webhook_token": "",
        }
    return {
        "correlation_window_minutes": int(row[0]),
        "at_risk_lead_minutes": int(row[1]),
        "auto_assign_name": row[2] or "",
        "auto_assign_email": (row[3] or "").strip().lower(),
        "action_webhook_url": row[4] or "",
        "action_webhook_token": row[5] or "",
    }


def _lookup_memory_hint(conn, tenant_id: str, event_type: str, asset_id: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT resolution_note
            FROM agent_memory_feedback
            WHERE tenant_id = %s
              AND event_type = %s
              AND (asset_id = %s OR asset_id = '')
            ORDER BY outcome_score DESC, created_at DESC
            LIMIT 1
            """,
            (tenant_id, event_type.strip().upper(), asset_id),
        )
        row = cur.fetchone()
    if row is None:
        return ""
    return (row[0] or "").strip()


def _estimate_confidence(event_type: str, severity: str, decision: Decision, memory_hint: str) -> float:
    base = 0.65
    severity_boost = {"critical": 0.2, "high": 0.14, "medium": 0.07, "low": 0.03}.get(severity, 0.05)
    decision_boost = {"CREATED": 0.05, "CORRELATED": 0.1, "DUPLICATE": 0.12}[decision]
    event_boost = 0.08 if event_type.strip().upper() in {"CONVEYOR_JAM", "ROBOT_STALL", "SAFETY_STOP"} else 0.02
    memory_boost = 0.08 if memory_hint else 0
    return max(0.5, min(0.99, round(base + severity_boost + decision_boost + event_boost + memory_boost, 4)))


def _insert_decision_log(
    conn,
    *,
    tenant_id: str,
    ticket_id: str,
    source_system: str,
    event_id: str,
    event_type: str,
    severity: str,
    decision: Decision,
    priority: str,
    reason: str,
    confidence: float,
    memory_hint: str,
    playbook: dict[str, str],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_decision_logs (
              tenant_id, ticket_id, source_system, event_id, event_type, severity,
              decision, priority, reason, confidence, playbook, memory_hint
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            """,
            (
                tenant_id,
                ticket_id,
                source_system,
                event_id,
                event_type,
                severity,
                decision,
                priority,
                reason,
                confidence,
                json.dumps(playbook),
                memory_hint,
            ),
        )


def _insert_action_log(
    conn,
    *,
    tenant_id: str,
    ticket_id: str,
    action_name: str,
    status: str,
    detail: str,
    request_payload: dict,
    response_payload: dict,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_action_runs (
              tenant_id, ticket_id, action_name, status, detail, request_payload, response_payload
            )
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
            """,
            (
                tenant_id,
                ticket_id,
                action_name,
                status,
                detail,
                json.dumps(request_payload),
                json.dumps(response_payload),
            ),
        )


def _execute_action_webhook(
    conn,
    *,
    tenant_id: str,
    ticket_id: str,
    decision: Decision,
    priority: str,
    reason: str,
    confidence: float,
    playbook: dict[str, str],
    policy: dict[str, str | int],
) -> None:
    webhook_url = str(policy["action_webhook_url"]).strip()
    webhook_token = str(policy["action_webhook_token"]).strip()
    payload = {
        "tenant_id": tenant_id,
        "ticket_id": ticket_id,
        "decision": decision,
        "priority": priority,
        "reason": reason,
        "confidence": confidence,
        "playbook": playbook,
        "ts": datetime.utcnow().isoformat(),
    }

    if not webhook_url:
        _insert_action_log(
            conn,
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            action_name="external_orchestration",
            status="SKIPPED",
            detail="No action webhook configured for tenant",
            request_payload=payload,
            response_payload={},
        )
        return

    headers = {"Content-Type": "application/json"}
    if webhook_token:
        headers["Authorization"] = f"Bearer {webhook_token}"

    req = urllib_request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=6) as response:
            body = response.read().decode("utf-8", errors="ignore")
            _insert_action_log(
                conn,
                tenant_id=tenant_id,
                ticket_id=ticket_id,
                action_name="external_orchestration",
                status="SUCCESS",
                detail=f"HTTP {response.status}",
                request_payload=payload,
                response_payload={"status": response.status, "body": body[:1000]},
            )
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        _insert_action_log(
            conn,
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            action_name="external_orchestration",
            status="FAILED",
            detail=f"HTTP {exc.code}",
            request_payload=payload,
            response_payload={"status": exc.code, "body": body[:1000]},
        )
    except Exception as exc:
        _insert_action_log(
            conn,
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            action_name="external_orchestration",
            status="FAILED",
            detail=str(exc),
            request_payload=payload,
            response_payload={},
        )


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
            memory_hint = _lookup_memory_hint(conn, payload.tenant_id, payload.event_type, payload.asset_id)
            if memory_hint:
                playbook = {**playbook, "memory_hint": memory_hint}

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
                    confidence = _estimate_confidence(payload.event_type, payload.severity, "DUPLICATE", memory_hint)
                    _insert_decision_log(
                        conn,
                        tenant_id=payload.tenant_id,
                        ticket_id=existing[0],
                        source_system=payload.source_system,
                        event_id=payload.event_id,
                        event_type=payload.event_type,
                        severity=payload.severity,
                        decision="DUPLICATE",
                        priority=priority,
                        reason=reason,
                        confidence=confidence,
                        memory_hint=memory_hint,
                        playbook=playbook,
                    )
                    conn.commit()
                    return ExternalTriggerResponse(
                        ticket_id=existing[0],
                        status="OPEN",
                        decision="DUPLICATE",
                        priority=priority,
                        reason=reason,
                        confidence=confidence,
                        memory_hint=memory_hint,
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
                    confidence = _estimate_confidence(payload.event_type, payload.severity, "CORRELATED", memory_hint)
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
                    _insert_decision_log(
                        conn,
                        tenant_id=payload.tenant_id,
                        ticket_id=ticket_id,
                        source_system=payload.source_system,
                        event_id=payload.event_id,
                        event_type=payload.event_type,
                        severity=payload.severity,
                        decision="CORRELATED",
                        priority=priority,
                        reason=reason,
                        confidence=confidence,
                        memory_hint=memory_hint,
                        playbook=playbook,
                    )
                    _execute_action_webhook(
                        conn,
                        tenant_id=payload.tenant_id,
                        ticket_id=ticket_id,
                        decision="CORRELATED",
                        priority=priority,
                        reason=reason,
                        confidence=confidence,
                        playbook=playbook,
                        policy=policy,
                    )
                    conn.commit()
                    return ExternalTriggerResponse(
                        ticket_id=ticket_id,
                        status=correlated[1],
                        decision="CORRELATED",
                        priority=priority,
                        reason=reason,
                        confidence=confidence,
                        memory_hint=memory_hint,
                        playbook=playbook,
                    )

                ticket_id = next_ticket_id(conn)
                confidence = _estimate_confidence(payload.event_type, payload.severity, "CREATED", memory_hint)
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
                        "confidence": confidence,
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
                _insert_decision_log(
                    conn,
                    tenant_id=payload.tenant_id,
                    ticket_id=ticket_id,
                    source_system=payload.source_system,
                    event_id=payload.event_id,
                    event_type=payload.event_type,
                    severity=payload.severity,
                    decision="CREATED",
                    priority=priority,
                    reason=reason,
                    confidence=confidence,
                    memory_hint=memory_hint,
                    playbook=playbook,
                )
                _execute_action_webhook(
                    conn,
                    tenant_id=payload.tenant_id,
                    ticket_id=ticket_id,
                    decision="CREATED",
                    priority=priority,
                    reason=reason,
                    confidence=confidence,
                    playbook=playbook,
                    policy=policy,
                )

            conn.commit()
            return ExternalTriggerResponse(
                ticket_id=ticket_id,
                status="OPEN",
                decision="CREATED",
                priority=priority,
                reason=reason,
                confidence=confidence,
                memory_hint=memory_hint,
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


@router.get("/decisions", response_model=list[DecisionLogOut])
def list_decisions(
    tenant_id: str = Query(..., min_length=1),
    ticket_id: str = Query("", min_length=0),
    limit: int = Query(100, ge=1, le=500),
):
    where = ["tenant_id = %s"]
    params: list[object] = [tenant_id]
    if ticket_id.strip():
        where.append("ticket_id = %s")
        params.append(ticket_id.strip())
    params.append(limit)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, tenant_id, ticket_id, source_system, event_id, event_type, severity,
                   decision, priority, reason, confidence, playbook, memory_hint, created_at
            FROM agent_decision_logs
            WHERE {" AND ".join(where)}
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        rows = cur.fetchall()

    return [
        DecisionLogOut(
            id=row[0],
            tenant_id=row[1],
            ticket_id=row[2],
            source_system=row[3],
            event_id=row[4],
            event_type=row[5],
            severity=row[6],
            decision=row[7],
            priority=row[8],
            reason=row[9],
            confidence=float(row[10]),
            playbook=row[11] or {},
            memory_hint=row[12] or "",
            created_at=row[13],
        )
        for row in rows
    ]


@router.get("/actions", response_model=list[ActionRunOut])
def list_actions(
    tenant_id: str = Query(..., min_length=1),
    ticket_id: str = Query("", min_length=0),
    limit: int = Query(100, ge=1, le=500),
):
    where = ["tenant_id = %s"]
    params: list[object] = [tenant_id]
    if ticket_id.strip():
        where.append("ticket_id = %s")
        params.append(ticket_id.strip())
    params.append(limit)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, tenant_id, ticket_id, action_name, status, detail, request_payload, response_payload, created_at
            FROM agent_action_runs
            WHERE {" AND ".join(where)}
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        rows = cur.fetchall()
    return [
        ActionRunOut(
            id=row[0],
            tenant_id=row[1],
            ticket_id=row[2],
            action_name=row[3],
            status=row[4],
            detail=row[5] or "",
            request_payload=row[6] or {},
            response_payload=row[7] or {},
            created_at=row[8],
        )
        for row in rows
    ]


@router.post("/memory/feedback")
def create_memory_feedback(payload: MemoryFeedbackIn):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_memory_feedback (
                      tenant_id, ticket_id, event_type, asset_id, outcome_score, resolution_note
                    )
                    VALUES (%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        payload.tenant_id,
                        payload.ticket_id,
                        payload.event_type.strip().upper(),
                        payload.asset_id.strip(),
                        payload.outcome_score,
                        payload.resolution_note.strip(),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return {"ok": True, "id": row[0]}
        except Exception:
            conn.rollback()
            raise


@router.get("/memory/suggestions", response_model=list[MemorySuggestionOut])
def memory_suggestions(
    tenant_id: str = Query(..., min_length=1),
    event_type: str = Query(..., min_length=1),
    asset_id: str = Query("", min_length=0),
    limit: int = Query(10, ge=1, le=50),
):
    with get_conn() as conn, conn.cursor() as cur:
        if asset_id.strip():
            cur.execute(
                """
                SELECT ticket_id, outcome_score, resolution_note, created_at
                FROM agent_memory_feedback
                WHERE tenant_id = %s
                  AND event_type = %s
                  AND (asset_id = %s OR asset_id = '')
                ORDER BY outcome_score DESC, created_at DESC
                LIMIT %s
                """,
                (tenant_id, event_type.strip().upper(), asset_id.strip(), limit),
            )
        else:
            cur.execute(
                """
                SELECT ticket_id, outcome_score, resolution_note, created_at
                FROM agent_memory_feedback
                WHERE tenant_id = %s
                  AND event_type = %s
                ORDER BY outcome_score DESC, created_at DESC
                LIMIT %s
                """,
                (tenant_id, event_type.strip().upper(), limit),
            )
        rows = cur.fetchall()
    return [
        MemorySuggestionOut(ticket_id=row[0], outcome_score=row[1], resolution_note=row[2] or "", created_at=row[3])
        for row in rows
    ]


@router.get("/proactive-summary", response_model=ProactiveSummaryOut)
def proactive_summary(
    tenant_id: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticket_id, status, priority, sla_due_at, assignee_email
            FROM tickets
            WHERE tenant_id = %s
              AND status <> 'CLOSED'
            ORDER BY created_at DESC
            """,
            (tenant_id,),
        )
        rows = cur.fetchall()

    now = datetime.utcnow()
    predicted_breach_2h = 0
    unassigned_open = 0
    actions: list[ProactiveActionOut] = []
    urgency_rows: list[tuple[float, ProactiveActionOut]] = []

    for row in rows:
        ticket_id, status, priority, sla_due_at, assignee_email = row
        if not (assignee_email or "").strip():
            unassigned_open += 1
        if sla_due_at is not None and sla_due_at <= now + timedelta(hours=2):
            predicted_breach_2h += 1

        sla_state = compute_sla_state(status=status, sla_due_at=sla_due_at, now=now)
        if sla_state == "BREACHED":
            recommendation = "Escalate now and assign owner immediately"
        elif sla_state == "AT_RISK":
            recommendation = "Prioritize this ticket in next dispatch cycle"
        elif not (assignee_email or "").strip():
            recommendation = "Assign an owner to start handling"
        else:
            recommendation = "Monitor progression and update status"

        due_seconds = (sla_due_at - now).total_seconds() if sla_due_at is not None else 999999
        urgency_rows.append(
            (
                due_seconds,
                ProactiveActionOut(
                    ticket_id=ticket_id,
                    priority=priority,
                    sla_state=sla_state,
                    recommendation=recommendation,
                ),
            )
        )

    for _, action in sorted(urgency_rows, key=lambda item: item[0])[:limit]:
        actions.append(action)

    return ProactiveSummaryOut(
        tenant_id=tenant_id,
        predicted_breach_2h=predicted_breach_2h,
        unassigned_open=unassigned_open,
        next_best_actions=actions,
    )
