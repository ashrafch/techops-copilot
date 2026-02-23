from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Literal, List

from app.db.session import get_conn
from app.db.events import log_event

router = APIRouter()

Status = Literal["OPEN", "CLOSED"]
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
    machine_line: str
    machine_station: str
    machine_serial: str
    created_at: datetime
    updated_at: datetime

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
                       requester_name, requester_email,
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
                       requester_name, requester_email,
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
            requester_name=r[6], requester_email=r[7],
            machine_line=r[8], machine_station=r[9], machine_serial=r[10],
            created_at=r[11], updated_at=r[12]
        )
        for r in rows
    ]

@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticket_id, tenant_id, status, subject, priority, description_raw,
                   requester_name, requester_email,
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
        requester_name=r[6], requester_email=r[7],
        machine_line=r[8], machine_station=r[9], machine_serial=r[10],
        created_at=r[11], updated_at=r[12]
    )

@router.patch("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tickets
                    SET status = 'CLOSED', updated_at = NOW()
                    WHERE ticket_id = %s
                    """,
                    (ticket_id,),
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Ticket not found")

            # log evento CLOSED nella stessa transaction
            log_event(
                conn,
                ticket_id=ticket_id,
                event_type="CLOSED",
                message="Ticket closed",
                meta={},
            )

            conn.commit()
            return {"ticket_id": ticket_id, "status": "CLOSED"}
        except:
            conn.rollback()
            raise
