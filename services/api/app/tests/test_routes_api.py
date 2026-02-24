import os

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://techops:techops@postgres_app:5432/techops")

from app.main import app


def _intake(client: TestClient, email: str) -> str:
    payload = {
        "tenant_id": "demo",
        "source": "pytest-routes",
        "requester": {"name": "Routes User", "email": email},
        "subject": "Routes test",
        "description_raw": "Routes endpoint test",
        "machine": {"line": "L-R", "station": "S-R", "serial": "SN-R-001"},
        "priority": "P3",
    }
    response = client.post("/intake", json=payload)
    assert response.status_code == 200
    return response.json()["ticket_id"]


def test_get_tenant_route_returns_route():
    client = TestClient(app)
    response = client.get("/tenant-routes/demo")
    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "demo"
    assert isinstance(payload["to_emails"], list)
    assert len(payload["to_emails"]) >= 1


def test_patch_tenant_route_updates_to_emails():
    client = TestClient(app)
    response = client.patch(
        "/tenant-routes/demo",
        json={"to_emails": ["ops1@example.com", "ops2@example.com"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["to_emails"] == ["ops1@example.com", "ops2@example.com"]


def test_tenant_email_history_contains_recent_requester_email():
    client = TestClient(app)
    email = "history-check@example.com"
    _intake(client, email=email)

    response = client.get("/tenant-email-history", params={"tenant_id": "demo", "limit": 50})
    assert response.status_code == 200
    emails = [item["email"] for item in response.json()]
    assert email in emails


def test_get_and_patch_tenant_sla_policy():
    client = TestClient(app)
    read = client.get("/tenant-sla-policies/demo")
    assert read.status_code == 200
    assert read.json()["tenant_id"] == "demo"

    patch = client.patch(
        "/tenant-sla-policies/demo",
        json={"p1_minutes": 45, "p2_minutes": 180, "p3_minutes": 360, "p4_minutes": 720},
    )
    assert patch.status_code == 200
    payload = patch.json()
    assert payload["p1_minutes"] == 45
    assert payload["p4_minutes"] == 720
