import os

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://techops:techops@postgres_app:5432/techops")

from app.main import app


def _create_ticket(client: TestClient) -> str:
    payload = {
        "tenant_id": "demo",
        "source": "pytest-events",
        "requester": {"name": "Events User", "email": "events@example.com"},
        "subject": "Events flow",
        "description_raw": "Events endpoint test",
        "machine": {"line": "L-EV", "station": "S-EV", "serial": "SN-EV-001"},
        "priority": "P3",
    }
    intake = client.post("/intake", json=payload)
    assert intake.status_code == 200
    return intake.json()["ticket_id"]


def test_create_and_list_note_event():
    client = TestClient(app)
    ticket_id = _create_ticket(client)

    create_event_payload = {
        "ticket_id": ticket_id,
        "event_type": "NOTE",
        "message": "Manual note",
        "meta": {"author": "pytest"},
    }
    created = client.post("/events", json=create_event_payload)
    assert created.status_code == 200
    created_json = created.json()
    assert created_json["ok"] is True
    assert created_json["event_id"] > 0

    events = client.get(f"/tickets/{ticket_id}/events")
    assert events.status_code == 200
    note_events = [e for e in events.json() if e["event_type"] == "NOTE"]
    assert len(note_events) >= 1
    assert note_events[-1]["message"] == "Manual note"
    assert note_events[-1]["meta"]["author"] == "pytest"


def test_create_event_returns_404_for_missing_ticket():
    client = TestClient(app)
    payload = {
        "ticket_id": "TCK-20990101-9999",
        "event_type": "NOTE",
        "message": "Should fail",
        "meta": {},
    }

    response = client.post("/events", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"


def test_list_events_returns_404_for_missing_ticket():
    client = TestClient(app)

    response = client.get("/tickets/TCK-20990101-9999/events")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"


def test_create_event_rejects_invalid_event_type():
    client = TestClient(app)
    ticket_id = _create_ticket(client)

    payload = {
        "ticket_id": ticket_id,
        "event_type": "INVALID_EVENT",
        "message": "Invalid type",
        "meta": {},
    }

    response = client.post("/events", json=payload)
    assert response.status_code == 422
