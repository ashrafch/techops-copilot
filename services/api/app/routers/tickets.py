from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal, List

from app.core.auth import require_api_key
from app.core.rbac import require_operator_role
from app.db.session import get_conn
from app.db.events import log_event

router = APIRouter(dependencies=[Depends(require_api_key)])

Status = Literal["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"]
Priority = Literal["P1", "P2", "P3", "P4"]

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
    created_at: datetime
    updated_at: datetime

class TicketStatusUpdate(BaseModel):
    status: Status


class TicketAssignmentUpdate(BaseModel):
    assignee_name: str = Field(default="", max_length=255)
    assignee_email: EmailStr | str = ""


@router.get("/tickets", response_model=List[TicketOut])
def list_tickets(
    tenant_id: str = Query(..., min_length=1),
    status: Optional[Status] = None,
    limit: int = Query(50, ge=1, le=200),
):
    with get_conn() as conn, conn.cursor() as cur:
        if status:
            cur.execute(
                """
                SELECT ticket_id, tenant_id, status, subject, priority, description_raw,
                       requester_name, requester_email, assignee_name, assignee_email,
                       machine_line, machine_station, machine_serial,
                       created_at, updated_at
                FROM tickets
                WHERE tenant_id = %s AND status = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (tenant_id, status, limit),
            )
        else:
            cur.execute(
                """
                SELECT ticket_id, tenant_id, status, subject, priority, description_raw,
                       requester_name, requester_email, assignee_name, assignee_email,
                       machine_line, machine_station, machine_serial,
                       created_at, updated_at
                FROM tickets
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            )
        rows = cur.fetchall()

    return [
        TicketOut(
            ticket_id=r[0], tenant_id=r[1], status=r[2],
            subject=r[3], priority=r[4], description_raw=r[5],
            requester_name=r[6], requester_email=r[7], assignee_name=r[8], assignee_email=r[9],
            machine_line=r[10], machine_station=r[11], machine_serial=r[12],
            created_at=r[13], updated_at=r[14]
        )
        for r in rows
    ]

@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticket_id, tenant_id, status, subject, priority, description_raw,
                   requester_name, requester_email, assignee_name, assignee_email,
                   machine_line, machine_station, machine_serial,
                   created_at, updated_at
            FROM tickets
            WHERE ticket_id = %s
            """,
            (ticket_id,),
        )
        r = cur.fetchone()

    if not r:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketOut(
        ticket_id=r[0], tenant_id=r[1], status=r[2],
        subject=r[3], priority=r[4], description_raw=r[5],
        requester_name=r[6], requester_email=r[7], assignee_name=r[8], assignee_email=r[9],
        machine_line=r[10], machine_station=r[11], machine_serial=r[12],
        created_at=r[13], updated_at=r[14]
    )


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
                cur.execute(
                    """
                    UPDATE tickets
                    SET status = %s, updated_at = NOW()
                    WHERE ticket_id = %s
                    RETURNING status
                    """,
                    (payload.status, ticket_id),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Ticket not found")

            log_event(
                conn,
                ticket_id=ticket_id,
                event_type="NOTE",
                message=f"Ticket status changed to {payload.status}",
                meta={"status": payload.status},
            )

            conn.commit()
            return {"ticket_id": ticket_id, "status": payload.status}
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
                    SET assignee_name = %s, assignee_email = %s, updated_at = NOW()
                    WHERE ticket_id = %s
                    RETURNING assignee_name, assignee_email
                    """,
                    (assignee_name, assignee_email, ticket_id),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Ticket not found")

            if assignee_name or assignee_email:
                message = f"Ticket assigned to {assignee_name or assignee_email}"
            else:
                message = "Ticket unassigned"

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

@router.patch("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, _: None = Depends(require_operator_role)):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM tickets WHERE ticket_id = %s", (ticket_id,))
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Ticket not found")
                if row[0] == "CLOSED":
                    conn.commit()
                    return {"ticket_id": ticket_id, "status": "CLOSED"}

                cur.execute(
                    """
                    UPDATE tickets
                    SET status = 'CLOSED', updated_at = NOW()
                    WHERE ticket_id = %s
                    """,
                    (ticket_id,),
                )

            log_event(
                conn,
                ticket_id=ticket_id,
                event_type="CLOSED",
                message="Ticket closed",
                meta={},
            )

            conn.commit()
            return {"ticket_id": ticket_id, "status": "CLOSED"}
        except Exception:
            conn.rollback()
            raise
