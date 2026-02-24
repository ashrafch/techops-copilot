import os

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://techops:techops@postgres_app:5432/techops")

from app.core.config import get_settings
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


def test_get_and_patch_tenant_automation_policy():
    client = TestClient(app)
    read = client.get("/tenant-automation-policies/demo")
    assert read.status_code == 200
    assert read.json()["tenant_id"] == "demo"
    assert "action_webhook_url" in read.json()

    patch = client.patch(
        "/tenant-automation-policies/demo",
        json={
            "correlation_window_minutes": 120,
            "at_risk_lead_minutes": 30,
            "auto_assign_name": "Automation Dispatcher",
            "auto_assign_email": "dispatch@example.com",
            "action_webhook_url": "https://example.com/agent-hook",
            "action_webhook_token": "temp-token",
        },
    )
    assert patch.status_code == 200
    payload = patch.json()
    assert payload["correlation_window_minutes"] == 120
    assert payload["at_risk_lead_minutes"] == 30
    assert payload["auto_assign_email"] == "dispatch@example.com"
    assert payload["action_webhook_url"] == "https://example.com/agent-hook"


def test_admin_audit_logs_include_route_and_sla_updates(monkeypatch):
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    monkeypatch.setenv("ENFORCE_AUTH", "false")
    get_settings.cache_clear()
    client = TestClient(app)

    sla_patch = client.patch(
        "/tenant-sla-policies/demo",
        json={"p1_minutes": 30, "p2_minutes": 120, "p3_minutes": 240, "p4_minutes": 480},
        headers={"X-User-Role": "admin"},
    )
    assert sla_patch.status_code == 200

    route_patch = client.patch(
        "/tenant-routes/demo",
        json={"to_emails": ["ops1@example.com", "ops2@example.com"]},
        headers={"X-User-Role": "admin"},
    )
    assert route_patch.status_code == 200
    automation_patch = client.patch(
        "/tenant-automation-policies/demo",
        json={
            "correlation_window_minutes": 240,
            "at_risk_lead_minutes": 45,
            "auto_assign_name": "Automation Dispatcher",
            "auto_assign_email": "dispatch@example.com",
            "action_webhook_url": "",
            "action_webhook_token": "",
        },
        headers={"X-User-Role": "admin"},
    )
    assert automation_patch.status_code == 200

    audit = client.get("/admin/audit-logs", params={"tenant_id": "demo"}, headers={"X-User-Role": "admin"})
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()]
    assert "TENANT_SLA_POLICY_UPDATED" in actions
    assert "TENANT_ROUTE_UPDATED" in actions
    assert "TENANT_AUTOMATION_POLICY_UPDATED" in actions
    get_settings.cache_clear()
