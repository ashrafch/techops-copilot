import os

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://techops:techops@postgres_app:5432/techops")

from app.main import app


def test_ticket_flow_and_close_idempotency():
    client = TestClient(app)

    payload = {
        "tenant_id": "demo",
        "source": "pytest",
        "requester": {"name": "PyTest User", "email": "pytest@example.com"},
        "subject": "Pytest flow",
        "description_raw": "End-to-end API flow test",
        "machine": {"line": "L-PY", "station": "S-PY", "serial": "SN-PY-001"},
        "priority": "P3",
    }

    intake = client.post("/intake", json=payload)
    assert intake.status_code == 200
    intake_json = intake.json()
    assert intake_json["status"] == "OPEN"
    ticket_id = intake_json["ticket_id"]
    assert ticket_id

    ticket = client.get(f"/tickets/{ticket_id}")
    assert ticket.status_code == 200
    assert ticket.json()["status"] == "OPEN"

    events_before_close = client.get(f"/tickets/{ticket_id}/events")
    assert events_before_close.status_code == 200
    before = events_before_close.json()
    created_events = [e for e in before if e["event_type"] == "CREATED"]
    assert len(created_events) >= 1

    close_1 = client.patch(f"/tickets/{ticket_id}/close")
    assert close_1.status_code == 200
    assert close_1.json()["status"] == "CLOSED"

    events_after_first_close = client.get(f"/tickets/{ticket_id}/events")
    assert events_after_first_close.status_code == 200
    after_first = events_after_first_close.json()
    closed_count_first = len([e for e in after_first if e["event_type"] == "CLOSED"])
    assert closed_count_first == 1

    close_2 = client.patch(f"/tickets/{ticket_id}/close")
    assert close_2.status_code == 200
    assert close_2.json()["status"] == "CLOSED"

    events_after_second_close = client.get(f"/tickets/{ticket_id}/events")
    assert events_after_second_close.status_code == 200
    after_second = events_after_second_close.json()
    closed_count_second = len([e for e in after_second if e["event_type"] == "CLOSED"])
    assert closed_count_second == closed_count_first
