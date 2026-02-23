from datetime import date, datetime
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional

from app.db.session import get_conn
from app.db.events import log_event  # NEW

router = APIRouter()

Priority = Literal["P1", "P2", "P3", "P4"]

class Requester(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr

class Machine(BaseModel):
    line: str = ""
    station: str = ""
    serial: str = ""

class IntakeRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    source: Optional[str] = "webhook"
    requester: Requester
    subject: str = Field(min_length=1)
    description_raw: str = Field(min_length=1)
    machine: Machine = Machine()
    priority: Priority = "P3"

class IntakeResponse(BaseModel):
    ticket_id: str
    status: str

def _next_ticket_id(conn) -> str:
    today = date.today()
    ymd = today.strftime("%Y%m%d")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ticket_sequences (day, last_seq)
            VALUES (%s, 0)
            ON CONFLICT (day) DO NOTHING
            """,
            (today,),
        )
        cur.execute("SELECT last_seq FROM ticket_sequences WHERE day = %s FOR UPDATE", (today,))
        last = cur.fetchone()[0]
        new_seq = last + 1
        cur.execute("UPDATE ticket_sequences SET last_seq = %s WHERE day = %s", (new_seq, today))

    return f"TCK-{ymd}-{new_seq:04d}"

@router.post("/intake", response_model=IntakeResponse)
def intake(req: IntakeRequest):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            ticket_id = _next_ticket_id(conn)
            now = datetime.utcnow()

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tickets (
                      ticket_id, tenant_id, status,
                      subject, priority, description_raw,
                      requester_name, requester_email,
                      machine_line, machine_station, machine_serial,
                      created_at, updated_at
                    )
                    VALUES (%s,%s,'OPEN', %s,%s,%s, %s,%s, %s,%s,%s, %s,%s)
                    """,
                    (
                        ticket_id, req.tenant_id,
                        req.subject, req.priority, req.description_raw,
                        req.requester.name, str(req.requester.email),
                        req.machine.line, req.machine.station, req.machine.serial,
                        now, now
                    ),
                )

            # NEW: log evento "CREATED"
            log_event(
                conn=conn,
                ticket_id=ticket_id,
                event_type="CREATED",
                message="Ticket created via intake",
                meta={
                    "tenant_id": req.tenant_id,
                    "source": req.source,
                    "priority": req.priority,
                    "requester": {"name": req.requester.name, "email": str(req.requester.email)},
                    "machine": {"line": req.machine.line, "station": req.machine.station, "serial": req.machine.serial},
                },
            )

            conn.commit()
            return IntakeResponse(ticket_id=ticket_id, status="OPEN")
        except Exception:
            conn.rollback()
            raise
