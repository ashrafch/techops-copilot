from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_conn
from app.main import app


def test_refresh_and_logout_flow(monkeypatch):
    monkeypatch.setenv("ENFORCE_AUTH", "true")
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test_secret_key")
    get_settings.cache_clear()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM auth_login_attempts WHERE LOWER(email) = LOWER(%s)", ("operator@example.com",))
        conn.commit()

    client = TestClient(app)
    login = client.post("/auth/login", json={"email": "operator@example.com", "password": "ChangeMe123!"})
    assert login.status_code == 200
    body = login.json()
    assert body["refresh_token"]

    refreshed = client.post("/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]

    me_ok = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me_ok.status_code == 200

    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {new_access}"})
    assert logout.status_code == 200

    me_after = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me_after.status_code == 401
    get_settings.cache_clear()


def test_login_lockout(monkeypatch):
    monkeypatch.setenv("ENFORCE_AUTH", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test_secret_key")
    monkeypatch.setenv("AUTH_MAX_FAILED_LOGINS", "2")
    monkeypatch.setenv("AUTH_LOCKOUT_MINUTES", "60")
    get_settings.cache_clear()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM auth_login_attempts WHERE LOWER(email) = LOWER(%s)", ("operator@example.com",))
        conn.commit()

    client = TestClient(app)
    bad1 = client.post("/auth/login", json={"email": "operator@example.com", "password": "bad-pass"})
    assert bad1.status_code == 401
    bad2 = client.post("/auth/login", json={"email": "operator@example.com", "password": "bad-pass"})
    assert bad2.status_code in {401, 429}
    lock = client.post("/auth/login", json={"email": "operator@example.com", "password": "bad-pass"})
    assert lock.status_code == 429
    get_settings.cache_clear()
