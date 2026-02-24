import hashlib
import secrets
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import get_current_user
from app.core.auth_token import issue_auth_token
from app.core.config import get_settings
from app.core.security import verify_password
from app.db.session import get_conn

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=4096)


class UserOut(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    tenant_id: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def _log_security_event(conn, *, event_type: str, actor_email: str, tenant_id: str, details: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO security_audit_logs (event_type, actor_email, tenant_id, details)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (event_type, actor_email, tenant_id, json.dumps(details)),
        )


def _register_login_attempt(conn, *, email: str, client_ip: str, success: bool) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auth_login_attempts (email, client_ip, success)
            VALUES (LOWER(%s), %s, %s)
            """,
            (email, client_ip, success),
        )


def _is_locked(conn, *, email: str, max_failed: int, lockout_minutes: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM auth_login_attempts
            WHERE LOWER(email) = LOWER(%s)
              AND success = FALSE
              AND created_at >= NOW() - (%s || ' minutes')::interval
            """,
            (email, lockout_minutes),
        )
        failed = int(cur.fetchone()[0])
    return failed >= max_failed


def _build_tokens(*, settings, row, session_id: str):
    access_token = issue_auth_token(
        secret=settings.auth_secret_key,
        sub=str(row[0]),
        email=row[1],
        role=row[5],
        tenant_id=row[6],
        ttl_minutes=settings.auth_token_ttl_minutes,
        sid=session_id,
        token_type="access",
    )
    refresh_token = _new_refresh_token()
    return access_token, refresh_token


@router.post("/auth/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    x_mfa_code: str | None = Header(default=None, alias="X-MFA-Code"),
):
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"

    with get_conn() as conn:
        conn.autocommit = False
        try:
            if _is_locked(
                conn,
                email=str(payload.email),
                max_failed=settings.auth_max_failed_logins,
                lockout_minutes=settings.auth_lockout_minutes,
            ):
                _register_login_attempt(conn, email=str(payload.email), client_ip=client_ip, success=False)
                conn.commit()
                raise HTTPException(status_code=429, detail="Account temporarily locked. Try later.")

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, full_name, password_hash, password_salt, role, tenant_id, is_active
                    FROM app_users
                    WHERE LOWER(email) = LOWER(%s)
                    """,
                    (str(payload.email),),
                )
                row = cur.fetchone()

            if row is None or not verify_password(payload.password, row[4], row[3]):
                _register_login_attempt(conn, email=str(payload.email), client_ip=client_ip, success=False)
                _log_security_event(
                    conn,
                    event_type="AUTH_LOGIN_FAILED",
                    actor_email=str(payload.email).lower(),
                    tenant_id="",
                    details={"reason": "invalid_credentials", "ip": client_ip},
                )
                conn.commit()
                raise HTTPException(status_code=401, detail="Invalid credentials")

            if not row[7]:
                _register_login_attempt(conn, email=str(payload.email), client_ip=client_ip, success=False)
                conn.commit()
                raise HTTPException(status_code=403, detail="User is inactive")

            role = str(row[5]).strip().lower()
            if settings.auth_require_mfa_for_admin and role == "admin" and (x_mfa_code or "").strip() != "000000":
                _register_login_attempt(conn, email=str(payload.email), client_ip=client_ip, success=False)
                _log_security_event(
                    conn,
                    event_type="AUTH_LOGIN_MFA_REQUIRED",
                    actor_email=row[1],
                    tenant_id=row[6],
                    details={"ip": client_ip},
                )
                conn.commit()
                raise HTTPException(status_code=401, detail="MFA required")

            session_id = secrets.token_urlsafe(32)
            access_token, refresh_token = _build_tokens(settings=settings, row=row, session_id=session_id)
            refresh_hash = _hash_refresh(refresh_token)
            refresh_expires_at = datetime.utcnow() + timedelta(minutes=settings.auth_refresh_ttl_minutes)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth_sessions (
                      session_id, user_id, user_email, tenant_id, refresh_hash, refresh_expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (session_id, row[0], row[1], row[6], refresh_hash, refresh_expires_at),
                )

            _register_login_attempt(conn, email=str(payload.email), client_ip=client_ip, success=True)
            _log_security_event(
                conn,
                event_type="AUTH_LOGIN_SUCCESS",
                actor_email=row[1],
                tenant_id=row[6],
                details={"ip": client_ip},
            )
            conn.commit()

            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.auth_token_ttl_minutes * 60,
                user=UserOut(email=row[1], full_name=row[2], role=row[5], tenant_id=row[6]),
            )
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise


@router.post("/auth/refresh", response_model=LoginResponse)
def refresh_token(payload: RefreshRequest):
    settings = get_settings()
    refresh_hash = _hash_refresh(payload.refresh_token)
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT session_id, user_id, user_email, tenant_id, refresh_expires_at, revoked_at
                    FROM auth_sessions
                    WHERE refresh_hash = %s
                    """,
                    (refresh_hash,),
                )
                session = cur.fetchone()
            if session is None or session[5] is not None or session[4] <= datetime.utcnow():
                conn.rollback()
                raise HTTPException(status_code=401, detail="Unauthorized")

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, full_name, password_hash, password_salt, role, tenant_id, is_active
                    FROM app_users
                    WHERE id = %s
                    """,
                    (session[1],),
                )
                user = cur.fetchone()
            if user is None or not user[7]:
                conn.rollback()
                raise HTTPException(status_code=401, detail="Unauthorized")

            access_token, next_refresh = _build_tokens(settings=settings, row=user, session_id=session[0])
            next_hash = _hash_refresh(next_refresh)
            next_exp = datetime.utcnow() + timedelta(minutes=settings.auth_refresh_ttl_minutes)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE auth_sessions
                    SET refresh_hash = %s,
                        refresh_expires_at = %s
                    WHERE session_id = %s
                    """,
                    (next_hash, next_exp, session[0]),
                )
            conn.commit()
            return LoginResponse(
                access_token=access_token,
                refresh_token=next_refresh,
                expires_in=settings.auth_token_ttl_minutes * 60,
                user=UserOut(email=user[1], full_name=user[2], role=user[5], tenant_id=user[6]),
            )
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise


@router.post("/auth/logout")
def logout(current_user=Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = NOW()
                    WHERE session_id = %s
                    """,
                    (current_user.sid,),
                )
                _log_security_event(
                    conn,
                    event_type="AUTH_LOGOUT",
                    actor_email=current_user.email,
                    tenant_id=current_user.tenant_id,
                    details={},
                )
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise


@router.get("/auth/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT email, full_name, role, tenant_id, is_active
            FROM app_users
            WHERE LOWER(email) = LOWER(%s)
            """,
            (current_user.email,),
        )
        row = cur.fetchone()
    if row is None or not row[4]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return UserOut(email=row[0], full_name=row[1], role=row[2], tenant_id=row[3])
