from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_login_success_and_me(monkeypatch):
    monkeypatch.setenv("ENFORCE_AUTH", "true")
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test_secret_key")
    get_settings.cache_clear()
    client = TestClient(app)

    login = client.post(
        "/auth/login",
        json={"email": "operator@example.com", "password": "ChangeMe123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "operator"
    get_settings.cache_clear()


def test_login_invalid_credentials(monkeypatch):
    monkeypatch.setenv("ENFORCE_AUTH", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test_secret_key")
    get_settings.cache_clear()
    client = TestClient(app)

    login = client.post(
        "/auth/login",
        json={"email": "operator@example.com", "password": "wrong-password"},
    )
    assert login.status_code == 401
    get_settings.cache_clear()


def test_enforce_auth_blocks_business_endpoint_without_token(monkeypatch):
    monkeypatch.setenv("ENFORCE_AUTH", "true")
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test_secret_key")
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.get("/tickets", params={"tenant_id": "demo"})
    assert response.status_code == 401
    get_settings.cache_clear()
