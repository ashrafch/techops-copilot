from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _payload():
    return {
        "tenant_id": "demo",
        "source": "pytest-rbac",
        "requester": {"name": "RBAC User", "email": "rbac@example.com"},
        "subject": "RBAC test",
        "description_raw": "RBAC test payload",
        "machine": {"line": "L-RBAC", "station": "S-RBAC", "serial": "SN-RBAC-001"},
        "priority": "P3",
    }


def test_rbac_disabled_keeps_write_open(monkeypatch):
    monkeypatch.setenv("ENFORCE_RBAC", "false")
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.post("/intake", json=_payload())
    assert response.status_code == 200
    get_settings.cache_clear()


def test_rbac_blocks_write_without_operator(monkeypatch):
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    get_settings.cache_clear()
    client = TestClient(app)

    forbidden = client.post("/intake", json=_payload())
    assert forbidden.status_code == 403

    viewer = client.post("/intake", json=_payload(), headers={"X-User-Role": "viewer"})
    assert viewer.status_code == 403

    operator = client.post("/intake", json=_payload(), headers={"X-User-Role": "operator"})
    assert operator.status_code == 200
    get_settings.cache_clear()


def test_rbac_viewer_can_read_but_cannot_write(monkeypatch):
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    get_settings.cache_clear()
    client = TestClient(app)

    created = client.post("/intake", json=_payload(), headers={"X-User-Role": "operator"})
    assert created.status_code == 200
    ticket_id = created.json()["ticket_id"]

    read = client.get(f"/tickets/{ticket_id}", headers={"X-User-Role": "viewer"})
    assert read.status_code == 200

    write_forbidden = client.patch(
        f"/tickets/{ticket_id}/status",
        json={"status": "IN_PROGRESS"},
        headers={"X-User-Role": "viewer"},
    )
    assert write_forbidden.status_code == 403
    get_settings.cache_clear()


def test_rbac_only_admin_can_patch_tenant_route(monkeypatch):
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    get_settings.cache_clear()
    client = TestClient(app)

    as_operator = client.patch(
        "/tenant-routes/demo",
        json={"to_emails": ["ops@example.com"]},
        headers={"X-User-Role": "operator"},
    )
    assert as_operator.status_code == 403

    as_admin = client.patch(
        "/tenant-routes/demo",
        json={"to_emails": ["ops@example.com"]},
        headers={"X-User-Role": "admin"},
    )
    assert as_admin.status_code == 200

    sla_operator = client.patch(
        "/tenant-sla-policies/demo",
        json={"p1_minutes": 30, "p2_minutes": 120, "p3_minutes": 240, "p4_minutes": 480},
        headers={"X-User-Role": "operator"},
    )
    assert sla_operator.status_code == 403

    sla_admin = client.patch(
        "/tenant-sla-policies/demo",
        json={"p1_minutes": 30, "p2_minutes": 120, "p3_minutes": 240, "p4_minutes": 480},
        headers={"X-User-Role": "admin"},
    )
    assert sla_admin.status_code == 200
    get_settings.cache_clear()


def test_rbac_with_auth_token_role(monkeypatch):
    monkeypatch.setenv("ENFORCE_AUTH", "true")
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test_secret_key")
    get_settings.cache_clear()
    client = TestClient(app)

    op_login = client.post(
        "/auth/login",
        json={"email": "operator@example.com", "password": "ChangeMe123!"},
    )
    assert op_login.status_code == 200
    op_token = op_login.json()["access_token"]

    forbidden = client.patch(
        "/tenant-routes/demo",
        json={"to_emails": ["ops@example.com"]},
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert forbidden.status_code == 403

    admin_login = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "ChangeMe123!"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    allowed = client.patch(
        "/tenant-routes/demo",
        json={"to_emails": ["ops@example.com"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    get_settings.cache_clear()
