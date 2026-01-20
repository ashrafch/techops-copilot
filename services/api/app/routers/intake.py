from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
import re

router = APIRouter()

class Requester(BaseModel):
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None

class Machine(BaseModel):
    line: Optional[str] = None
    station: Optional[str] = None
    serial: Optional[str] = None

class IntakeIn(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    source: str = Field(default="webhook")
    requester: Requester
    subject: str = Field(..., min_length=1)
    description_raw: str = Field(..., min_length=1)
    machine: Optional[Machine] = None
    priority: Literal["P1", "P2", "P3", "P4"] = "P3"

class IntakeOut(BaseModel):
    ticket_id: str
    status: str

_counter = 0

def _slug(s: str) -> str:
    s = s.strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "-", s)
    return s.strip("-")[:32] or "TICKET"

@router.post("/intake", response_model=IntakeOut)
def intake(payload: IntakeIn):
    # MVP: genera un ticket id deterministico (poi lo mettiamo su Postgres)
    global _counter
    _counter += 1

    date_part = datetime.utcnow().strftime("%Y%m%d")
    ticket_id = f"TCK-{date_part}-{_counter:04d}"

    return IntakeOut(ticket_id=ticket_id, status="OPEN")
