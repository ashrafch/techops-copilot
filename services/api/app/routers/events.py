from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal
from datetime import datetime
import json

from app.core.auth import require_api_key
from app.core.rbac import require_operator_role
from app.db.session import get_conn

router = APIRouter(dependencies=[Depends(require_api_key)])

EventType = Literal["CREATED", "EMAIL_SENT", "CLOSED", "NOTE"]


class EventCreate(BaseModel):
    ticket_id: str = Field(min_length=1)
    event_type: EventType
    message: str = Field(default="", max_length=4000)
    meta: Dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    id: int
    ticket_id: str
    event_type: EventType
    message: str
    meta: Dict[str, Any]
    created_at: datetime


@router.post("/events")
def create_event(payload: EventCreate, _: None = Depends(require_operator_role)):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                # check ticket exists
                cur.execute("SELECT 1 FROM tickets WHERE ticket_id = %s", (payload.ticket_id,))
                if cur.fetchone() is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="Ticket not found")

                cur.execute(
                    """
                    INSERT INTO ticket_events (ticket_id, event_type, message, meta)
                    VALUES (%s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        payload.ticket_id,
                        payload.event_type,
                        payload.message or "",
                        json.dumps(payload.meta or {}),
                    ),
                )
                event_id = cur.fetchone()[0]

            conn.commit()
            return {"ok": True, "event_id": event_id}
        except Exception:
            conn.rollback()
            raise


@router.get("/tickets/{ticket_id}/events", response_model=List[EventOut])
def list_ticket_events(
    ticket_id: str,
    limit: int = Query(100, ge=1, le=500),
):
    with get_conn() as conn, conn.cursor() as cur:
        # opzionale ma utile: 404 se ticket non esiste
        cur.execute("SELECT 1 FROM tickets WHERE ticket_id = %s", (ticket_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        cur.execute(
            """
            SELECT id, ticket_id, event_type, message, meta, created_at
            FROM ticket_events
            WHERE ticket_id = %s
            ORDER BY id ASC
            LIMIT %s
            """,
            (ticket_id, limit),
        )
        rows = cur.fetchall()

    return [
        EventOut(
            id=r[0],
            ticket_id=r[1],
            event_type=r[2],
            message=r[3],
            meta=r[4] or {},
            created_at=r[5],
        )
        for r in rows
    ]
