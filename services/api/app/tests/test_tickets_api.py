import os

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://techops:techops@postgres_app:5432/techops")

from app.main import app


def _intake(client: TestClient, subject: str, priority: str = "P3") -> str:
    payload = {
        "tenant_id": "demo",
        "source": "pytest-tickets",
        "requester": {"name": "Tickets User", "email": "tickets@example.com"},
        "subject": subject,
        "description_raw": "Tickets endpoint test",
        "machine": {"line": "L-TK", "station": "S-TK", "serial": "SN-TK-001"},
        "priority": priority,
    }
    response = client.post("/intake", json=payload)
    assert response.status_code == 200
    return response.json()["ticket_id"]


def test_close_missing_ticket_returns_404():
    client = TestClient(app)
    response = client.patch("/tickets/TCK-20990101-9999/close")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"


def test_list_tickets_filter_by_status():
    client = TestClient(app)
    ticket_id = _intake(client, subject="List status filter")

    close_response = client.patch(f"/tickets/{ticket_id}/close")
    assert close_response.status_code == 200

    open_list = client.get("/tickets", params={"tenant_id": "demo", "status": "OPEN", "limit": 200})
    assert open_list.status_code == 200
    open_ids = [item["ticket_id"] for item in open_list.json()]
    assert ticket_id not in open_ids

    closed_list = client.get("/tickets", params={"tenant_id": "demo", "status": "CLOSED", "limit": 200})
    assert closed_list.status_code == 200
    closed_ids = [item["ticket_id"] for item in closed_list.json()]
    assert ticket_id in closed_ids


def test_intake_rejects_invalid_priority():
    client = TestClient(app)
    payload = {
        "tenant_id": "demo",
        "source": "pytest-tickets",
        "requester": {"name": "Tickets User", "email": "tickets@example.com"},
        "subject": "Invalid priority",
        "description_raw": "Priority validation test",
        "machine": {"line": "L-TK", "station": "S-TK", "serial": "SN-TK-002"},
        "priority": "P5",
    }

    response = client.post("/intake", json=payload)
    assert response.status_code == 422
