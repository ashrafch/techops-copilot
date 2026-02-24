from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _trigger_payload(event_id: str, event_type: str, severity: str, asset_id: str):
    return {
        "tenant_id": "demo",
        "source_system": "wms",
        "event_id": event_id,
        "event_type": event_type,
        "severity": severity,
        "asset_id": asset_id,
        "location": "DC-NORTH-LINE-1",
        "summary": "Automated signal from logistics stack",
        "details": "Telemetry threshold crossed.",
    }


def test_external_trigger_creates_ticket_with_ai_decision():
    client = TestClient(app)
    payload = _trigger_payload(
        event_id=f"evt-{uuid4().hex[:8]}",
        event_type="CONVEYOR_JAM",
        severity="high",
        asset_id=f"CONV-{uuid4().hex[:6]}",
    )
    resp = client.post("/automation/external-intake", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "CREATED"
    assert body["priority"] == "P1"
    assert body["ticket_id"].startswith("TCK-")

    ticket = client.get(f"/tickets/{body['ticket_id']}")
    assert ticket.status_code == 200
    assert ticket.json()["priority"] == "P1"


def test_external_trigger_duplicate_event_id_returns_duplicate():
    client = TestClient(app)
    event_id = f"evt-{uuid4().hex[:8]}"
    payload = _trigger_payload(
        event_id=event_id,
        event_type="FORKLIFT_BATTERY_LOW",
        severity="medium",
        asset_id="FL-02",
    )
    first = client.post("/automation/external-intake", json=payload)
    assert first.status_code == 200
    second = client.post("/automation/external-intake", json=payload)
    assert second.status_code == 200
    assert second.json()["decision"] == "DUPLICATE"
    assert second.json()["ticket_id"] == first.json()["ticket_id"]


def test_external_trigger_correlates_open_ticket_for_same_asset_and_event_type():
    client = TestClient(app)
    asset = "RB-99"
    first = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="ROBOT_STALL",
            severity="critical",
            asset_id=asset,
        ),
    )
    assert first.status_code == 200

    second = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="ROBOT_STALL",
            severity="critical",
            asset_id=asset,
        ),
    )
    assert second.status_code == 200
    assert second.json()["decision"] == "CORRELATED"
    assert second.json()["ticket_id"] == first.json()["ticket_id"]


def test_external_trigger_endpoint_works_with_rbac_enabled_without_user_role(monkeypatch):
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    monkeypatch.setenv("ENFORCE_AUTH", "false")
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="CONVEYOR_JAM",
            severity="high",
            asset_id="CONV-02",
        ),
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] in {"CREATED", "CORRELATED"}
    get_settings.cache_clear()
