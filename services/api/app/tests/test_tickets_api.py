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


def test_update_ticket_status_and_assignment():
    client = TestClient(app)
    ticket_id = _intake(client, subject="Lifecycle and assignment")

    status_update = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "IN_PROGRESS"},
    )
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "IN_PROGRESS"

    assign = client.patch(
        f"/tickets/{ticket_id}/assign",
        json={"assignee_name": "Ops User", "assignee_email": "ops.user@example.com"},
    )
    assert assign.status_code == 200
    assert assign.json()["assignee_email"] == "ops.user@example.com"

    ticket = client.get(f"/tickets/{ticket_id}")
    assert ticket.status_code == 200
    payload = ticket.json()
    assert payload["status"] == "IN_PROGRESS"
    assert payload["assignee_name"] == "Ops User"
    assert payload["assignee_email"] == "ops.user@example.com"
    assert payload["first_response_at"] is not None


def test_add_note_and_queue_summary():
    client = TestClient(app)
    ticket_id = _intake(client, subject="Queue summary and notes")

    note = client.post(f"/tickets/{ticket_id}/notes", json={"message": "Investigating root cause"})
    assert note.status_code == 200
    assert note.json()["ok"] is True

    summary = client.get("/tickets/queue-summary", params={"tenant_id": "demo"})
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["open_total"] >= 1
    assert "at_risk_total" in payload
    assert "breached_total" in payload


def test_ticket_metrics_endpoint_returns_operational_snapshot():
    client = TestClient(app)
    ticket_id = _intake(client, subject="Metrics endpoint ticket")

    close_resp = client.patch(f"/tickets/{ticket_id}/close")
    assert close_resp.status_code == 200

    metrics = client.get("/tickets/metrics", params={"tenant_id": "demo"})
    assert metrics.status_code == 200
    payload = metrics.json()
    assert payload["closed_total"] >= 1
    assert payload["created_last_24h"] >= 1
    assert "avg_resolution_minutes" in payload
    assert "breached_open_total" in payload


def test_ticket_executive_report_returns_business_snapshot():
    client = TestClient(app)
    ticket_id = _intake(client, subject="Executive report ticket")
    close_resp = client.patch(f"/tickets/{ticket_id}/close")
    assert close_resp.status_code == 200

    report = client.get("/tickets/executive-report", params={"tenant_id": "demo", "days": 30})
    assert report.status_code == 200
    payload = report.json()
    assert payload["tenant_id"] == "demo"
    assert payload["window_days"] == 30
    assert "sla_attainment_pct" in payload
    assert "mttr_minutes" in payload
    assert "estimated_cost_impact" in payload
    assert isinstance(payload["trend"], list)
