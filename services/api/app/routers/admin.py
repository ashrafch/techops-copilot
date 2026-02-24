from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import require_api_key
from app.core.rbac import require_admin_role
from app.core.security import generate_salt_hex, hash_password
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


@router.post("/admin/users", response_model=AdminUserOut)
def create_admin_user(payload: AdminUserCreate):
    salt = generate_salt_hex()
    pwd_hash = hash_password(payload.password, salt)

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
def update_admin_user(user_id: int, payload: AdminUserUpdate):
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
def update_admin_user_password(user_id: int, payload: AdminPasswordUpdate):
    salt = generate_salt_hex()
    pwd_hash = hash_password(payload.password, salt)

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
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"ok": True}
