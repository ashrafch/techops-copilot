from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_ready_returns_ready_when_db_is_available():
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database not ready"
    get_settings.cache_clear()


def test_db_endpoint_returns_503_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.get("/tickets", params={"tenant_id": "demo"})
    assert response.status_code == 503
    assert response.json()["detail"] == "DATABASE_URL not set"
    get_settings.cache_clear()
