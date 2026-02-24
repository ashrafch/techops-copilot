from datetime import datetime
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import get_current_user, require_api_key
from app.core.identity import resolve_actor
from app.core.rbac import require_admin_role
from app.core.security import generate_salt_hex, hash_password
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
            SELECT id, email, full_name, role, tenant_id, is_active, updated_at
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
            updated_at=row[6],
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
                    RETURNING id, email, full_name, role, tenant_id, is_active, updated_at
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
        updated_at=row[6],
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
                    "SELECT id, email, full_name, role, tenant_id, is_active, updated_at FROM app_users WHERE id = %s",
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
                    RETURNING id, email, full_name, role, tenant_id, is_active, updated_at
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
        updated_at=row[6],
    )


@router.patch("/admin/users/{user_id}/password")
def update_admin_user_password(
    user_id: int,
    payload: AdminPasswordUpdate,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
):
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
