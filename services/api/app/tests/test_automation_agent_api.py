from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_conn
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
    assert isinstance(body["confidence"], float)
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


def test_external_trigger_uses_tenant_automation_auto_assign():
    client = TestClient(app)
    policy = client.patch(
        "/tenant-automation-policies/demo",
        json={
            "correlation_window_minutes": 1440,
            "at_risk_lead_minutes": 60,
            "auto_assign_name": "Automation Dispatcher",
            "auto_assign_email": "dispatch@example.com",
            "action_webhook_url": "",
            "action_webhook_token": "",
        },
    )
    assert policy.status_code == 200

    resp = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="CONVEYOR_JAM",
            severity="high",
            asset_id=f"CONV-{uuid4().hex[:6]}",
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    ticket = client.get(f"/tickets/{body['ticket_id']}")
    assert ticket.status_code == 200
    assert ticket.json()["assignee_name"] == "Automation Dispatcher"
    assert ticket.json()["assignee_email"] == "dispatch@example.com"


def test_external_trigger_respects_correlation_window():
    client = TestClient(app)
    update = client.patch(
        "/tenant-automation-policies/demo",
        json={
            "correlation_window_minutes": 1,
            "at_risk_lead_minutes": 1,
            "auto_assign_name": "Automation Dispatcher",
            "auto_assign_email": "dispatch@example.com",
            "action_webhook_url": "",
            "action_webhook_token": "",
        },
    )
    assert update.status_code == 200

    first = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="ROBOT_STALL",
            severity="critical",
            asset_id="RB-WINDOW-01",
        ),
    )
    assert first.status_code == 200
    first_ticket_id = first.json()["ticket_id"]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE tickets SET created_at = NOW() - INTERVAL '3 minutes' WHERE ticket_id = %s",
            (first_ticket_id,),
        )
        conn.commit()

    second = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="ROBOT_STALL",
            severity="critical",
            asset_id="RB-WINDOW-01",
        ),
    )
    assert second.status_code == 200
    assert second.json()["decision"] == "CREATED"
    assert second.json()["ticket_id"] != first_ticket_id


def test_sla_monitor_creates_breach_alert_once():
    client = TestClient(app)
    create = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="ROBOT_STALL",
            severity="critical",
            asset_id=f"RB-SLA-{uuid4().hex[:4]}",
        ),
    )
    assert create.status_code == 200
    ticket_id = create.json()["ticket_id"]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE tickets SET sla_due_at = NOW() - INTERVAL '5 minutes' WHERE ticket_id = %s", (ticket_id,))
        conn.commit()

    first = client.post("/automation/sla-monitor", json={"tenant_id": "demo", "limit": 200})
    assert first.status_code == 200
    assert first.json()["breached_alerted"] >= 1
    assert ticket_id in first.json()["ticket_ids"]

    second = client.post("/automation/sla-monitor", json={"tenant_id": "demo", "limit": 200})
    assert second.status_code == 200
    assert second.json()["breached_alerted"] == 0


def test_decision_and_action_logs_available_after_external_trigger():
    client = TestClient(app)
    create = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="CONVEYOR_JAM",
            severity="high",
            asset_id=f"CONV-DL-{uuid4().hex[:4]}",
        ),
    )
    assert create.status_code == 200
    ticket_id = create.json()["ticket_id"]

    decisions = client.get("/automation/decisions", params={"tenant_id": "demo", "ticket_id": ticket_id, "limit": 20})
    assert decisions.status_code == 200
    assert len(decisions.json()) >= 1

    actions = client.get("/automation/actions", params={"tenant_id": "demo", "ticket_id": ticket_id, "limit": 20})
    assert actions.status_code == 200
    assert len(actions.json()) >= 1


def test_memory_feedback_and_suggestions():
    client = TestClient(app)
    create = client.post(
        "/automation/external-intake",
        json=_trigger_payload(
            event_id=f"evt-{uuid4().hex[:8]}",
            event_type="ROBOT_STALL",
            severity="critical",
            asset_id="RB-MEM-01",
        ),
    )
    assert create.status_code == 200
    ticket_id = create.json()["ticket_id"]

    feedback = client.post(
        "/automation/memory/feedback",
        json={
            "tenant_id": "demo",
            "ticket_id": ticket_id,
            "event_type": "ROBOT_STALL",
            "asset_id": "RB-MEM-01",
            "outcome_score": 5,
            "resolution_note": "Power cycle robot cell before full recalibration.",
        },
    )
    assert feedback.status_code == 200

    suggestions = client.get(
        "/automation/memory/suggestions",
        params={"tenant_id": "demo", "event_type": "ROBOT_STALL", "asset_id": "RB-MEM-01", "limit": 10},
    )
    assert suggestions.status_code == 200
    assert len(suggestions.json()) >= 1


def test_proactive_summary_returns_recommendations():
    client = TestClient(app)
    resp = client.get("/automation/proactive-summary", params={"tenant_id": "demo", "limit": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert "predicted_breach_2h" in body
    assert "next_best_actions" in body
