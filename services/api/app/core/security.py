import hashlib
import hmac
import secrets


PBKDF2_ITERATIONS = 200_000


def generate_salt_hex() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    candidate = hash_password(password, salt_hex)
    return hmac.compare_digest(candidate, expected_hash_hex)


def validate_password_policy(
    password: str,
    *,
    min_length: int,
    require_upper: bool,
    require_lower: bool,
    require_digit: bool,
    require_symbol: bool,
) -> tuple[bool, str]:
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"
    if require_upper and not any(ch.isupper() for ch in password):
        return False, "Password must include at least one uppercase letter"
    if require_lower and not any(ch.islower() for ch in password):
        return False, "Password must include at least one lowercase letter"
    if require_digit and not any(ch.isdigit() for ch in password):
        return False, "Password must include at least one digit"
    if require_symbol and not any(not ch.isalnum() for ch in password):
        return False, "Password must include at least one symbol"
    return True, ""
