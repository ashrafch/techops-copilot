from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _intake_payload():
    return {
        "tenant_id": "demo",
        "source": "pytest-auth",
        "requester": {"name": "Auth User", "email": "auth@example.com"},
        "subject": "Auth test",
        "description_raw": "Auth gate validation",
        "machine": {"line": "L-A", "station": "S-A", "serial": "SN-A-001"},
        "priority": "P3",
    }


def test_no_api_key_config_keeps_endpoints_open(monkeypatch):
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.post("/intake", json=_intake_payload())
    assert response.status_code == 200
    get_settings.cache_clear()


def test_api_key_required_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "super-secret")
    get_settings.cache_clear()
    client = TestClient(app)

    no_header = client.post("/intake", json=_intake_payload())
    assert no_header.status_code == 401
    assert no_header.json()["detail"] == "Unauthorized"

    bad_header = client.post(
        "/intake",
        json=_intake_payload(),
        headers={"X-API-Key": "wrong"},
    )
    assert bad_header.status_code == 401
    assert bad_header.json()["detail"] == "Unauthorized"

    ok_header = client.post(
        "/intake",
        json=_intake_payload(),
        headers={"X-API-Key": "super-secret"},
    )
    assert ok_header.status_code == 200
    get_settings.cache_clear()


def test_health_stays_public_with_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "super-secret")
    get_settings.cache_clear()
    client = TestClient(app)

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert ready.status_code == 200
    get_settings.cache_clear()
