import json
import base64
import hashlib
import hmac
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.mfa import current_totp_code
from app.main import app


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _sign_hs256(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def test_admin_mfa_enroll_and_login(monkeypatch):
    monkeypatch.setenv("ENFORCE_AUTH", "false")
    monkeypatch.setenv("ENFORCE_RBAC", "false")
    monkeypatch.setenv("AUTH_REQUIRE_MFA_FOR_ADMIN", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test_secret_key")
    get_settings.cache_clear()
    client = TestClient(app)

    users = client.get("/admin/users")
    assert users.status_code == 200
    admin_row = next((u for u in users.json() if u["email"] == "admin@example.com"), None)
    assert admin_row is not None
    admin_id = int(admin_row["id"])

    reset = client.patch(f"/admin/users/{admin_id}/password", json={"password": "AdminPass123!X"})
    assert reset.status_code == 200

    enroll = client.post(f"/admin/users/{admin_id}/mfa/enroll")
    assert enroll.status_code == 200
    secret = enroll.json()["mfa_secret"]
    code = current_totp_code(secret)

    login = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!X"},
        headers={"X-MFA-Code": code},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "admin"

    disable = client.post(f"/admin/users/{admin_id}/mfa/disable")
    assert disable.status_code == 200
    assert disable.json()["ok"] is True
    restore = client.patch(f"/admin/users/{admin_id}/password", json={"password": "ChangeMe123!"})
    assert restore.status_code == 200
    get_settings.cache_clear()


def test_sso_login_flow(monkeypatch):
    monkeypatch.setenv("ENFORCE_AUTH", "false")
    monkeypatch.setenv("ENFORCE_RBAC", "false")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test_secret_key")
    get_settings.cache_clear()
    client = TestClient(app)

    cfg = client.patch(
        "/admin/sso-config/demo",
        json={
            "provider": "oidc",
            "issuer": "techops-sso-demo",
            "audience": "techops-copilot",
            "client_id": "techops-demo-client",
            "sso_shared_secret": "demo_sso_secret",
            "is_enabled": True,
        },
    )
    assert cfg.status_code == 200

    claims = {
        "sub": "external-user-1",
        "email": "sso.operator@example.com",
        "name": "SSO Operator",
        "role": "operator",
        "aud": "techops-copilot",
        "iss": "techops-sso-demo",
        "exp": int((datetime.utcnow() + timedelta(minutes=10)).timestamp()),
    }
    token = _sign_hs256(claims, "demo_sso_secret")
    login = client.post("/auth/sso/login", json={"tenant_id": "demo", "id_token": token})
    assert login.status_code == 200
    assert login.json()["user"]["email"] == "sso.operator@example.com"
    get_settings.cache_clear()
