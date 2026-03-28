import base64
import hashlib
import hmac
import os
import struct
import time
from urllib.parse import quote


def generate_mfa_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode("utf-8").rstrip("=")


def _hotp(secret: str, counter: int, digits: int = 6) -> str:
    normalized = secret.upper().strip()
    padding = "=" * (-len(normalized) % 8)
    key = base64.b32decode(normalized + padding, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    otp = binary % (10**digits)
    return str(otp).zfill(digits)


def verify_totp(secret: str, code: str, *, step_seconds: int = 30, window: int = 1) -> bool:
    if not secret.strip() or not code.strip().isdigit():
        return False
    now_counter = int(time.time()) // step_seconds
    cleaned = code.strip()
    for offset in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret, now_counter + offset), cleaned):
            return True
    return False


def current_totp_code(secret: str, *, step_seconds: int = 30) -> str:
    counter = int(time.time()) // step_seconds
    return _hotp(secret, counter)


def provisioning_uri(secret: str, email: str, issuer: str = "TechOps Copilot") -> str:
    label = quote(f"{issuer}:{email}")
    issuer_q = quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_q}&algorithm=SHA1&digits=6&period=30"
