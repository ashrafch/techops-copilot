from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import require_api_key
from app.core.rbac import require_operator_role, require_viewer_role
from app.db.events import log_event
from app.db.session import get_conn
from app.domain.sla_service import compute_sla_state

router = APIRouter(dependencies=[Depends(require_api_key)])

Status = Literal["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"]
Priority = Literal["P1", "P2", "P3", "P4"]
SlaStateFilter = Literal["ALL", "ON_TIME", "AT_RISK", "BREACHED"]
SlaState = Literal["ON_TIME", "AT_RISK", "BREACHED", "NO_SLA", "CLOSED"]


class TicketOut(BaseModel):
    ticket_id: str
    tenant_id: str
    status: Status
    subject: str
    priority: Priority
    description_raw: str
    requester_name: str
    requester_email: str
    assignee_name: str
    assignee_email: str
    machine_line: str
    machine_station: str
    machine_serial: str
    sla_due_at: datetime | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    sla_state: SlaState
    created_at: datetime
    updated_at: datetime


class TicketStatusUpdate(BaseModel):
    status: Status


class TicketAssignmentUpdate(BaseModel):
    assignee_name: str = Field(default="", max_length=255)
    assignee_email: EmailStr | str = ""


class TicketNoteCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class QueueSummaryOut(BaseModel):
    open_total: int
    unassigned_total: int
    my_total: int
    at_risk_total: int
    breached_total: int


class TicketMetricsOut(BaseModel):
    open_total: int
    in_progress_total: int
    waiting_total: int
    resolved_total: int
    closed_total: int
    created_last_24h: int
    closed_last_24h: int
    avg_resolution_minutes: float
    at_risk_open_total: int
    breached_open_total: int


def _row_to_ticket(row, now: datetime) -> TicketOut:
    sla_due_at = row[13]
    status = row[2]
    sla_state = compute_sla_state(status=status, sla_due_at=sla_due_at, now=now)
    return TicketOut(
        ticket_id=row[0],
        tenant_id=row[1],
        status=status,
        subject=row[3],
        priority=row[4],
        description_raw=row[5],
        requester_name=row[6],
        requester_email=row[7],
        assignee_name=row[8],
        assignee_email=row[9],
        machine_line=row[10],
        machine_station=row[11],
        machine_serial=row[12],
        sla_due_at=sla_due_at,
        first_response_at=row[14],
        resolved_at=row[15],
        sla_state=sla_state,
        created_at=row[16],
        updated_at=row[17],
    )


@router.get("/tickets", response_model=List[TicketOut])
def list_tickets(
    tenant_id: str = Query(..., min_length=1),
    status: Optional[Status] = None,
    assignee_email: Optional[str] = None,
    only_unassigned: bool = False,
    sla_state: SlaStateFilter = "ALL",
    limit: int = Query(50, ge=1, le=500),
    _: None = Depends(require_viewer_role),
):
    where_clauses = ["tenant_id = %s"]
    params: list[object] = [tenant_id]

    if status:
        where_clauses.append("status = %s")
        params.append(status)
    if assignee_email:
        where_clauses.append("LOWER(assignee_email) = %s")
        params.append(assignee_email.strip().lower())
    if only_unassigned:
        where_clauses.append("COALESCE(assignee_email, '') = ''")

    sql = f"""
        SELECT ticket_id, tenant_id, status, subject, priority, description_raw,
               requester_name, requester_email, assignee_name, assignee_email,
               machine_line, machine_station, machine_serial,
               sla_due_at, first_response_at, resolved_at,
               created_at, updated_at
        FROM tickets
        WHERE {" AND ".join(where_clauses)}
        ORDER BY created_at DESC
        LIMIT %s
    """
    params.append(limit)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    now = datetime.utcnow()
    tickets = [_row_to_ticket(r, now) for r in rows]
    if sla_state != "ALL":
        tickets = [t for t in tickets if t.sla_state == sla_state]
    return tickets


@router.get("/tickets/queue-summary", response_model=QueueSummaryOut)
def queue_summary(
    tenant_id: str = Query(..., min_length=1),
    assignee_email: str = Query("", min_length=0),
    _: None = Depends(require_viewer_role),
):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, assignee_email, sla_due_at
            FROM tickets
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        rows = cur.fetchall()

    now = datetime.utcnow()
    assignee_lower = assignee_email.strip().lower()
    open_total = 0
    unassigned_total = 0
    my_total = 0
    at_risk_total = 0
    breached_total = 0

    for row in rows:
        status = row[0]
        assigned = (row[1] or "").strip().lower()
        sla_due_at = row[2]
        if status != "CLOSED":
            open_total += 1
        if status != "CLOSED" and not assigned:
            unassigned_total += 1
        if status != "CLOSED" and assignee_lower and assigned == assignee_lower:
            my_total += 1

        sla_state = compute_sla_state(status=status, sla_due_at=sla_due_at, now=now)
        if sla_state == "AT_RISK":
            at_risk_total += 1
        if sla_state == "BREACHED":
            breached_total += 1

    return QueueSummaryOut(
        open_total=open_total,
        unassigned_total=unassigned_total,
        my_total=my_total,
        at_risk_total=at_risk_total,
        breached_total=breached_total,
    )


@router.get("/tickets/metrics", response_model=TicketMetricsOut)
def ticket_metrics(
    tenant_id: str = Query(..., min_length=1),
    _: None = Depends(require_viewer_role),
):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, created_at, resolved_at, sla_due_at
            FROM tickets
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        rows = cur.fetchall()

    now = datetime.utcnow()
    open_total = 0
    in_progress_total = 0
    waiting_total = 0
    resolved_total = 0
    closed_total = 0
    created_last_24h = 0
    closed_last_24h = 0
    resolution_minutes: list[float] = []
    at_risk_open_total = 0
    breached_open_total = 0

    for status, created_at, resolved_at, sla_due_at in rows:
        if status == "OPEN":
            open_total += 1
        elif status == "IN_PROGRESS":
            in_progress_total += 1
        elif status == "WAITING":
            waiting_total += 1
        elif status == "RESOLVED":
            resolved_total += 1
        elif status == "CLOSED":
            closed_total += 1

        if (now - created_at).total_seconds() <= 86400:
            created_last_24h += 1

        if resolved_at is not None:
            if (now - resolved_at).total_seconds() <= 86400:
                closed_last_24h += 1
            resolution_minutes.append((resolved_at - created_at).total_seconds() / 60.0)

        sla_state = compute_sla_state(status=status, sla_due_at=sla_due_at, now=now)
        if sla_state == "AT_RISK":
            at_risk_open_total += 1
        elif sla_state == "BREACHED":
            breached_open_total += 1

    avg_resolution = round(sum(resolution_minutes) / len(resolution_minutes), 2) if resolution_minutes else 0.0
    return TicketMetricsOut(
        open_total=open_total,
        in_progress_total=in_progress_total,
        waiting_total=waiting_total,
        resolved_total=resolved_total,
        closed_total=closed_total,
        created_last_24h=created_last_24h,
        closed_last_24h=closed_last_24h,
        avg_resolution_minutes=avg_resolution,
        at_risk_open_total=at_risk_open_total,
        breached_open_total=breached_open_total,
    )


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, _: None = Depends(require_viewer_role)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticket_id, tenant_id, status, subject, priority, description_raw,
                   requester_name, requester_email, assignee_name, assignee_email,
                   machine_line, machine_station, machine_serial,
                   sla_due_at, first_response_at, resolved_at,
                   created_at, updated_at
            FROM tickets
            WHERE ticket_id = %s
            """,
            (ticket_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return _row_to_ticket(row, datetime.utcnow())


@router.patch("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdate,
    _: None = Depends(require_operator_role),
):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM tickets WHERE ticket_id = %s", (ticket_id,))
                existing = cur.fetchone()
                if existing is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Ticket not found")

                cur.execute(
                    """
                    UPDATE tickets
                    SET status = %s,
                        first_response_at = CASE
                          WHEN first_response_at IS NULL AND %s IN ('IN_PROGRESS','WAITING','RESOLVED','CLOSED')
                          THEN NOW()
                          ELSE first_response_at
                        END,
                        resolved_at = CASE
                          WHEN %s IN ('RESOLVED','CLOSED') THEN COALESCE(resolved_at, NOW())
                          ELSE NULL
                        END,
                        updated_at = NOW()
                    WHERE ticket_id = %s
                    RETURNING status
                    """,
                    (payload.status, payload.status, payload.status, ticket_id),
                )
                row = cur.fetchone()

            log_event(
                conn,
                ticket_id=ticket_id,
                event_type="NOTE",
                message=f"Ticket status changed to {payload.status}",
                meta={"status": payload.status},
            )

            if payload.status == "CLOSED" and existing[0] != "CLOSED":
                log_event(
                    conn,
                    ticket_id=ticket_id,
                    event_type="CLOSED",
                    message="Ticket closed",
                    meta={},
                )

            conn.commit()
            return {"ticket_id": ticket_id, "status": row[0]}
        except Exception:
            conn.rollback()
            raise


@router.patch("/tickets/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str,
    payload: TicketAssignmentUpdate,
    _: None = Depends(require_operator_role),
):
    assignee_name = payload.assignee_name.strip()
    assignee_email = str(payload.assignee_email).strip().lower()

    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tickets
                    SET assignee_name = %s,
                        assignee_email = %s,
                        first_response_at = CASE
                          WHEN first_response_at IS NULL AND %s <> '' THEN NOW()
                          ELSE first_response_at
                        END,
                        updated_at = NOW()
                    WHERE ticket_id = %s
                    RETURNING assignee_name, assignee_email
                    """,
                    (assignee_name, assignee_email, assignee_email, ticket_id),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Ticket not found")

            message = f"Ticket assigned to {assignee_name or assignee_email}" if (assignee_name or assignee_email) else "Ticket unassigned"
            log_event(
                conn,
                ticket_id=ticket_id,
                event_type="NOTE",
                message=message,
                meta={"assignee_name": row[0], "assignee_email": row[1]},
            )

            conn.commit()
            return {"ticket_id": ticket_id, "assignee_name": row[0], "assignee_email": row[1]}
        except Exception:
            conn.rollback()
            raise


@router.post("/tickets/{ticket_id}/notes")
def add_ticket_note(
    ticket_id: str,
    payload: TicketNoteCreate,
    _: None = Depends(require_operator_role),
):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM tickets WHERE ticket_id = %s", (ticket_id,))
                if cur.fetchone() is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Ticket not found")

            log_event(
                conn,
                ticket_id=ticket_id,
                event_type="NOTE",
                message=payload.message.strip(),
                meta={"source": "manual_note"},
            )
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise


@router.patch("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, _: None = Depends(require_operator_role)):
    # keep backward compatibility endpoint
    return update_ticket_status(ticket_id=ticket_id, payload=TicketStatusUpdate(status="CLOSED"))
