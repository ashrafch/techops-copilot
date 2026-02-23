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
