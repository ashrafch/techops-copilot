import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


class TokenError(ValueError):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@dataclass
class AuthTokenClaims:
    sub: str
    email: str
    role: str
    tenant_id: str
    exp: int
    sid: str
    typ: str


def issue_auth_token(
    *,
    secret: str,
    sub: str,
    email: str,
    role: str,
    tenant_id: str,
    ttl_minutes: int,
    sid: str,
    token_type: str = "access",
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    exp = int(time.time()) + (ttl_minutes * 60)
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "exp": exp,
        "sid": sid,
        "typ": token_type,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_auth_token(token: str, secret: str) -> AuthTokenClaims:
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("Invalid token format")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    provided_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise TokenError("Invalid token signature")

    payload_raw = _b64url_decode(payload_b64)
    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:  # pragma: no cover
        raise TokenError("Invalid token payload") from exc

    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise TokenError("Token expired")

    return AuthTokenClaims(
        sub=str(payload.get("sub", "")),
        email=str(payload.get("email", "")),
        role=str(payload.get("role", "")),
        tenant_id=str(payload.get("tenant_id", "")),
        exp=exp,
        sid=str(payload.get("sid", "")),
        typ=str(payload.get("typ", "access")),
    )
