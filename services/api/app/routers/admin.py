from datetime import datetime
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import get_current_user, require_api_key
from app.core.config import get_settings
from app.core.identity import resolve_actor
from app.core.mfa import generate_mfa_secret, provisioning_uri
from app.core.rbac import require_admin_role
from app.core.security import generate_salt_hex, hash_password, validate_password_policy
from app.db.audit import log_admin_action
from app.db.session import get_conn

router = APIRouter(
    dependencies=[Depends(require_api_key), Depends(require_admin_role)],
)

UserRole = Literal["admin", "operator", "viewer"]


class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    tenant_id: str
    is_active: bool
    mfa_enabled: bool
    updated_at: datetime


class AdminUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=1024)
    role: UserRole
    tenant_id: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[UserRole] = None
    tenant_id: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class AdminPasswordUpdate(BaseModel):
    password: str = Field(min_length=8, max_length=1024)


class AdminAuditLogOut(BaseModel):
    id: int
    tenant_id: str
    actor_email: str
    actor_role: str
    action: str
    target_type: str
    target_id: str
    details: dict[str, Any]
    created_at: datetime


class GdprExportOut(BaseModel):
    tenant_id: str
    tickets: list[dict[str, Any]]
    events: list[dict[str, Any]]
    admin_audit: list[dict[str, Any]]


class SecurityCleanupOut(BaseModel):
    deleted_security_logs: int
    deleted_login_attempts: int


class AdminMfaEnrollOut(BaseModel):
    user_id: int
    email: str
    mfa_enabled: bool
    mfa_secret: str
    otp_uri: str


class TenantSsoConfigOut(BaseModel):
    tenant_id: str
    provider: str
    issuer: str
    audience: str
    client_id: str
    is_enabled: bool
    updated_at: datetime


class TenantSsoConfigUpdate(BaseModel):
    provider: str = Field(default="oidc", max_length=32)
    issuer: str = Field(default="", max_length=255)
    audience: str = Field(default="", max_length=255)
    client_id: str = Field(default="", max_length=255)
    sso_shared_secret: str = Field(default="", max_length=2048)
    is_enabled: bool = False


@router.get("/admin/users", response_model=List[AdminUserOut])
def list_admin_users(
    tenant_id: str = Query("", min_length=0),
):
    where = ""
    params: tuple[object, ...] = ()
    if tenant_id.strip():
        where = "WHERE tenant_id = %s"
        params = (tenant_id.strip(),)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, email, full_name, role, tenant_id, is_active, mfa_enabled, updated_at
            FROM app_users
            {where}
            ORDER BY tenant_id ASC, role ASC, email ASC
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        AdminUserOut(
            id=row[0],
            email=row[1],
            full_name=row[2],
            role=row[3],
            tenant_id=row[4],
            is_active=row[5],
            mfa_enabled=row[6],
            updated_at=row[7],
        )
        for row in rows
    ]


@router.get("/admin/audit-logs", response_model=List[AdminAuditLogOut])
def list_admin_audit_logs(
    tenant_id: str = Query("", min_length=0),
    limit: int = Query(100, ge=1, le=500),
):
    where = ""
    params: tuple[object, ...]
    if tenant_id.strip():
        where = "WHERE tenant_id = %s"
        params = (tenant_id.strip(), limit)
    else:
        params = (limit,)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, tenant_id, actor_email, actor_role, action, target_type, target_id, details, created_at
            FROM admin_audit_logs
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        AdminAuditLogOut(
            id=row[0],
            tenant_id=row[1],
            actor_email=row[2],
            actor_role=row[3],
            action=row[4],
            target_type=row[5],
            target_id=row[6],
            details=row[7] or {},
            created_at=row[8],
        )
        for row in rows
    ]


@router.post("/admin/users", response_model=AdminUserOut)
def create_admin_user(
    payload: AdminUserCreate,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
):
    settings = get_settings()
    ok, msg = validate_password_policy(
        payload.password,
        min_length=settings.password_min_length,
        require_upper=settings.password_require_upper,
        require_lower=settings.password_require_lower,
        require_digit=settings.password_require_digit,
        require_symbol=settings.password_require_symbol,
    )
    if not ok:
        raise HTTPException(status_code=422, detail=msg)
    salt = generate_salt_hex()
    pwd_hash = hash_password(payload.password, salt)
    actor_email, actor_role = resolve_actor(x_user_role=x_user_role, current_user=current_user)

    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_users (email, full_name, password_hash, password_salt, role, tenant_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, email, full_name, role, tenant_id, is_active, mfa_enabled, updated_at
                    """,
                    (
                        str(payload.email).strip().lower(),
                        payload.full_name.strip(),
                        pwd_hash,
                        salt,
                        payload.role,
                        payload.tenant_id.strip(),
                        payload.is_active,
                    ),
                )
                row = cur.fetchone()
                log_admin_action(
                    conn,
                    tenant_id=str(row[4]),
                    actor_email=actor_email,
                    actor_role=actor_role,
                    action="ADMIN_USER_CREATED",
                    target_type="app_user",
                    target_id=str(row[0]),
                    details={"email": row[1], "role": row[3], "is_active": row[5]},
                )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key value violates unique constraint" in str(exc):
                raise HTTPException(status_code=409, detail="User already exists")
            raise

    return AdminUserOut(
        id=row[0],
        email=row[1],
        full_name=row[2],
        role=row[3],
        tenant_id=row[4],
        is_active=row[5],
        mfa_enabled=row[6],
        updated_at=row[7],
    )


@router.patch("/admin/users/{user_id}", response_model=AdminUserOut)
def update_admin_user(
    user_id: int,
    payload: AdminUserUpdate,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
):
    actor_email, actor_role = resolve_actor(x_user_role=x_user_role, current_user=current_user)
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, full_name, role, tenant_id, is_active, mfa_enabled, updated_at FROM app_users WHERE id = %s",
                    (user_id,),
                )
                existing = cur.fetchone()
                if existing is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="User not found")

                new_full_name = payload.full_name.strip() if payload.full_name is not None else existing[2]
                new_role = payload.role if payload.role is not None else existing[3]
                new_tenant = payload.tenant_id.strip() if payload.tenant_id is not None else existing[4]
                new_active = payload.is_active if payload.is_active is not None else existing[5]

                cur.execute(
                    """
                    UPDATE app_users
                    SET full_name = %s,
                        role = %s,
                        tenant_id = %s,
                        is_active = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, email, full_name, role, tenant_id, is_active, mfa_enabled, updated_at
                    """,
                    (new_full_name, new_role, new_tenant, new_active, user_id),
                )
                row = cur.fetchone()
                log_admin_action(
                    conn,
                    tenant_id=str(row[4]),
                    actor_email=actor_email,
                    actor_role=actor_role,
                    action="ADMIN_USER_UPDATED",
                    target_type="app_user",
                    target_id=str(user_id),
                    details={
                        "full_name": row[2],
                        "role": row[3],
                        "tenant_id": row[4],
                        "is_active": row[5],
                    },
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return AdminUserOut(
        id=row[0],
        email=row[1],
        full_name=row[2],
        role=row[3],
        tenant_id=row[4],
        is_active=row[5],
        mfa_enabled=row[6],
        updated_at=row[7],
    )


@router.patch("/admin/users/{user_id}/password")
def update_admin_user_password(
    user_id: int,
    payload: AdminPasswordUpdate,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
):
    settings = get_settings()
    ok, msg = validate_password_policy(
        payload.password,
        min_length=settings.password_min_length,
        require_upper=settings.password_require_upper,
        require_lower=settings.password_require_lower,
        require_digit=settings.password_require_digit,
        require_symbol=settings.password_require_symbol,
    )
    if not ok:
        raise HTTPException(status_code=422, detail=msg)
    salt = generate_salt_hex()
    pwd_hash = hash_password(payload.password, salt)
    actor_email, actor_role = resolve_actor(x_user_role=x_user_role, current_user=current_user)

    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE app_users
                    SET password_hash = %s,
                        password_salt = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                    """,
                    (pwd_hash, salt, user_id),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    raise HTTPException(status_code=404, detail="User not found")
                cur.execute("SELECT tenant_id FROM app_users WHERE id = %s", (user_id,))
                tenant_row = cur.fetchone()
                tenant_id = str(tenant_row[0]) if tenant_row else "unknown"
                log_admin_action(
                    conn,
                    tenant_id=tenant_id,
                    actor_email=actor_email,
                    actor_role=actor_role,
                    action="ADMIN_USER_PASSWORD_RESET",
                    target_type="app_user",
                    target_id=str(user_id),
                    details={},
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"ok": True}


@router.get("/admin/gdpr/export", response_model=GdprExportOut)
def gdpr_export(
    tenant_id: str = Query(..., min_length=1),
):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticket_id, status, subject, priority, requester_name, requester_email, created_at
            FROM tickets
            WHERE tenant_id = %s
            ORDER BY created_at DESC
            LIMIT 5000
            """,
            (tenant_id,),
        )
        tickets_rows = cur.fetchall()
        cur.execute(
            """
            SELECT te.ticket_id, te.event_type, te.message, te.meta, te.created_at
            FROM ticket_events te
            JOIN tickets t ON t.ticket_id = te.ticket_id
            WHERE t.tenant_id = %s
            ORDER BY te.created_at DESC
            LIMIT 10000
            """,
            (tenant_id,),
        )
        events_rows = cur.fetchall()
        cur.execute(
            """
            SELECT action, target_type, target_id, details, created_at
            FROM admin_audit_logs
            WHERE tenant_id = %s
            ORDER BY created_at DESC
            LIMIT 5000
            """,
            (tenant_id,),
        )
        audit_rows = cur.fetchall()
    return GdprExportOut(
        tenant_id=tenant_id,
        tickets=[
            {
                "ticket_id": r[0],
                "status": r[1],
                "subject": r[2],
                "priority": r[3],
                "requester_name": r[4],
                "requester_email": r[5],
                "created_at": r[6],
            }
            for r in tickets_rows
        ],
        events=[
            {"ticket_id": r[0], "event_type": r[1], "message": r[2], "meta": r[3] or {}, "created_at": r[4]}
            for r in events_rows
        ],
        admin_audit=[
            {"action": r[0], "target_type": r[1], "target_id": r[2], "details": r[3] or {}, "created_at": r[4]}
            for r in audit_rows
        ],
    )


@router.delete("/admin/gdpr/purge")
def gdpr_purge(
    tenant_id: str = Query(..., min_length=1),
    before_days: int = Query(365, ge=1, le=3650),
):
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM tickets
                    WHERE tenant_id = %s
                      AND created_at < NOW() - (%s || ' days')::interval
                    RETURNING ticket_id
                    """,
                    (tenant_id, before_days),
                )
                deleted = [r[0] for r in cur.fetchall()]
            conn.commit()
            return {"ok": True, "deleted_tickets": len(deleted)}
        except Exception:
            conn.rollback()
            raise


@router.post("/admin/security/cleanup", response_model=SecurityCleanupOut)
def security_cleanup():
    settings = get_settings()
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM security_audit_logs
                    WHERE created_at < NOW() - (%s || ' days')::interval
                    RETURNING id
                    """,
                    (settings.security_log_retention_days,),
                )
                deleted_security = len(cur.fetchall())
                cur.execute(
                    """
                    DELETE FROM auth_login_attempts
                    WHERE created_at < NOW() - (%s || ' days')::interval
                    RETURNING id
                    """,
                    (settings.security_log_retention_days,),
                )
                deleted_attempts = len(cur.fetchall())
            conn.commit()
            return SecurityCleanupOut(
                deleted_security_logs=deleted_security,
                deleted_login_attempts=deleted_attempts,
            )
        except Exception:
            conn.rollback()
            raise


@router.post("/admin/users/{user_id}/mfa/enroll", response_model=AdminMfaEnrollOut)
def enroll_user_mfa(
    user_id: int,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
):
    actor_email, actor_role = resolve_actor(x_user_role=x_user_role, current_user=current_user)
    secret = generate_mfa_secret()
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE app_users
                    SET mfa_enabled = TRUE,
                        mfa_secret = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, email, tenant_id
                    """,
                    (secret, user_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="User not found")
                otp_uri = provisioning_uri(secret=secret, email=row[1])
                log_admin_action(
                    conn,
                    tenant_id=str(row[2]),
                    actor_email=actor_email,
                    actor_role=actor_role,
                    action="ADMIN_USER_MFA_ENROLLED",
                    target_type="app_user",
                    target_id=str(user_id),
                    details={},
                )
            conn.commit()
            return AdminMfaEnrollOut(
                user_id=row[0],
                email=row[1],
                mfa_enabled=True,
                mfa_secret=secret,
                otp_uri=otp_uri,
            )
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise


@router.post("/admin/users/{user_id}/mfa/disable")
def disable_user_mfa(
    user_id: int,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
):
    actor_email, actor_role = resolve_actor(x_user_role=x_user_role, current_user=current_user)
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE app_users
                    SET mfa_enabled = FALSE,
                        mfa_secret = '',
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, email, tenant_id
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="User not found")
                log_admin_action(
                    conn,
                    tenant_id=str(row[2]),
                    actor_email=actor_email,
                    actor_role=actor_role,
                    action="ADMIN_USER_MFA_DISABLED",
                    target_type="app_user",
                    target_id=str(user_id),
                    details={},
                )
            conn.commit()
            return {"ok": True}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise


@router.get("/admin/sso-config/{tenant_id}", response_model=TenantSsoConfigOut)
def get_tenant_sso_config(tenant_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT tenant_id, provider, issuer, audience, client_id, is_enabled, updated_at
            FROM tenant_sso_configs
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="SSO config not found")
    return TenantSsoConfigOut(
        tenant_id=row[0],
        provider=row[1],
        issuer=row[2],
        audience=row[3],
        client_id=row[4],
        is_enabled=row[5],
        updated_at=row[6],
    )


@router.patch("/admin/sso-config/{tenant_id}", response_model=TenantSsoConfigOut)
def update_tenant_sso_config(
    tenant_id: str,
    payload: TenantSsoConfigUpdate,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
):
    actor_email, actor_role = resolve_actor(x_user_role=x_user_role, current_user=current_user)
    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_sso_configs (tenant_id, provider, issuer, audience, client_id, sso_shared_secret, is_enabled)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (tenant_id) DO UPDATE SET
                      provider = EXCLUDED.provider,
                      issuer = EXCLUDED.issuer,
                      audience = EXCLUDED.audience,
                      client_id = EXCLUDED.client_id,
                      sso_shared_secret = CASE WHEN EXCLUDED.sso_shared_secret <> '' THEN EXCLUDED.sso_shared_secret ELSE tenant_sso_configs.sso_shared_secret END,
                      is_enabled = EXCLUDED.is_enabled,
                      updated_at = NOW()
                    RETURNING tenant_id, provider, issuer, audience, client_id, is_enabled, updated_at
                    """,
                    (
                        tenant_id.strip(),
                        payload.provider.strip().lower() or "oidc",
                        payload.issuer.strip(),
                        payload.audience.strip(),
                        payload.client_id.strip(),
                        payload.sso_shared_secret.strip(),
                        payload.is_enabled,
                    ),
                )
                row = cur.fetchone()
                log_admin_action(
                    conn,
                    tenant_id=tenant_id.strip(),
                    actor_email=actor_email,
                    actor_role=actor_role,
                    action="TENANT_SSO_CONFIG_UPDATED",
                    target_type="tenant_sso_config",
                    target_id=tenant_id.strip(),
                    details={"provider": row[1], "issuer": row[2], "audience": row[3], "client_id": row[4], "is_enabled": row[5]},
                )
            conn.commit()
            return TenantSsoConfigOut(
                tenant_id=row[0],
                provider=row[1],
                issuer=row[2],
                audience=row[3],
                client_id=row[4],
                is_enabled=row[5],
                updated_at=row[6],
            )
        except Exception:
            conn.rollback()
            raise
