from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limit_state
from app.main import app


def test_rate_limit_blocks_after_threshold(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_RPM", "2")
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("REQUIRE_API_KEY", "false")
    get_settings.cache_clear()
    reset_rate_limit_state()

    client = TestClient(app)
    params = {"tenant_id": "demo", "limit": 1}

    r1 = client.get("/tickets", params=params)
    r2 = client.get("/tickets", params=params)
    r3 = client.get("/tickets", params=params)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["detail"] == "Rate limit exceeded"
    assert r3.headers.get("Retry-After") == "60"
    assert r3.headers.get("X-Request-ID")

    reset_rate_limit_state()
    get_settings.cache_clear()


def test_rate_limit_does_not_apply_to_health(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_RPM", "1")
    get_settings.cache_clear()
    reset_rate_limit_state()

    client = TestClient(app)
    h1 = client.get("/health")
    h2 = client.get("/health")

    assert h1.status_code == 200
    assert h2.status_code == 200

    reset_rate_limit_state()
    get_settings.cache_clear()
