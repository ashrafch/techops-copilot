from fastapi.testclient import TestClient
from uuid import uuid4

from app.core.config import get_settings
from app.main import app


def test_admin_user_crud_with_role_header(monkeypatch):
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    monkeypatch.setenv("ENFORCE_AUTH", "false")
    get_settings.cache_clear()
    client = TestClient(app)

    list_resp = client.get("/admin/users", headers={"X-User-Role": "admin"})
    assert list_resp.status_code == 200
    assert isinstance(list_resp.json(), list)

    unique_email = f"new.operator.{uuid4().hex[:8]}@example.com"
    create_resp = client.post(
        "/admin/users",
        headers={"X-User-Role": "admin"},
        json={
            "email": unique_email,
            "full_name": "New Operator",
            "password": "ChangeMe123!",
            "role": "operator",
            "tenant_id": "demo",
            "is_active": True,
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    user_id = created["id"]

    patch_resp = client.patch(
        f"/admin/users/{user_id}",
        headers={"X-User-Role": "admin"},
        json={"full_name": "Updated Operator", "is_active": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["full_name"] == "Updated Operator"
    assert patch_resp.json()["is_active"] is False

    pwd_resp = client.patch(
        f"/admin/users/{user_id}/password",
        headers={"X-User-Role": "admin"},
        json={"password": "NewPass123!"},
    )
    assert pwd_resp.status_code == 200
    assert pwd_resp.json()["ok"] is True

    audit_resp = client.get("/admin/audit-logs", headers={"X-User-Role": "admin"}, params={"tenant_id": "demo"})
    assert audit_resp.status_code == 200
    actions = [row["action"] for row in audit_resp.json()]
    assert "ADMIN_USER_CREATED" in actions
    assert "ADMIN_USER_UPDATED" in actions
    assert "ADMIN_USER_PASSWORD_RESET" in actions
    get_settings.cache_clear()


def test_admin_endpoints_block_non_admin(monkeypatch):
    monkeypatch.setenv("ENFORCE_RBAC", "true")
    monkeypatch.setenv("ENFORCE_AUTH", "false")
    get_settings.cache_clear()
    client = TestClient(app)

    resp = client.get("/admin/users", headers={"X-User-Role": "operator"})
    assert resp.status_code == 403
    get_settings.cache_clear()
