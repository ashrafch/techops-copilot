from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import get_current_user, require_api_key
from app.core.identity import resolve_actor
from app.core.rbac import require_admin_role, require_viewer_role
from app.db.audit import log_admin_action
from app.db.session import get_conn

router = APIRouter(dependencies=[Depends(require_api_key)])


class TenantRouteOut(BaseModel):
    tenant_id: str
    channel: str
    to_emails: List[EmailStr]
    cc_emails: List[EmailStr]
    bcc_emails: List[EmailStr]
    reply_to: Optional[EmailStr] = None
    is_active: bool
    updated_at: datetime


class TenantRouteUpdate(BaseModel):
    to_emails: List[EmailStr] = Field(min_length=1)


class EmailHistoryItem(BaseModel):
    email: str
    last_used_at: datetime


class TenantSlaPolicyOut(BaseModel):
    tenant_id: str
    p1_minutes: int
    p2_minutes: int
    p3_minutes: int
    p4_minutes: int
    updated_at: datetime


class TenantSlaPolicyUpdate(BaseModel):
    p1_minutes: int = Field(ge=1, le=10080)
    p2_minutes: int = Field(ge=1, le=10080)
    p3_minutes: int = Field(ge=1, le=10080)
    p4_minutes: int = Field(ge=1, le=10080)


def _csv_to_list(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _list_to_csv(values: list[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip().lower()
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return ",".join(unique)


@router.get("/tenant-routes/{tenant_id}", response_model=TenantRouteOut)
def get_tenant_route(tenant_id: str, _: None = Depends(require_viewer_role)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT tenant_id, channel, to_emails, cc_emails, bcc_emails, reply_to, is_active, updated_at
            FROM tenant_routes
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Tenant route not found")

    return TenantRouteOut(
        tenant_id=row[0],
        channel=row[1],
        to_emails=_csv_to_list(row[2]),
        cc_emails=_csv_to_list(row[3] or ""),
        bcc_emails=_csv_to_list(row[4] or ""),
        reply_to=row[5] or None,
        is_active=row[6],
        updated_at=row[7],
    )


@router.patch("/tenant-routes/{tenant_id}", response_model=TenantRouteOut)
def update_tenant_route(
    tenant_id: str,
    payload: TenantRouteUpdate,
    _: None = Depends(require_admin_role),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    current_user=Depends(get_current_user),
):
    to_csv = _list_to_csv([str(item) for item in payload.to_emails])
    if not to_csv:
        raise HTTPException(status_code=422, detail="to_emails must contain at least one email")
    actor_email, actor_role = resolve_actor(x_user_role=x_user_role, current_user=current_user)

    with get_conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenant_routes (tenant_id, channel, to_emails, cc_emails, bcc_emails, reply_to, is_active)
                    VALUES (%s, 'email', %s, '', '', '', TRUE)
                    ON CONFLICT (tenant_id) DO UPDATE SET
                      to_emails = EXCLUDED.to_emails,
                      updated_at = NOW()
                    RETURNING tenant_id, channel, to_emails, cc_emails, bcc_emails, reply_to, is_active, updated_at
                    """,
                    (tenant_id, to_csv),
                )
                row = cur.fetchone()
                log_admin_action(
                    conn,
                    tenant_id=tenant_id,
                    actor_email=actor_email,
                    actor_role=actor_role,
                    action="TENANT_ROUTE_UPDATED",
                    target_type="tenant_route",
                    target_id=tenant_id,
                    details={"to_emails": _csv_to_list(row[2])},
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return TenantRouteOut(
        tenant_id=row[0],
        channel=row[1],
        to_emails=_csv_to_list(row[2]),
        cc_emails=_csv_to_list(row[3] or ""),
        bcc_emails=_csv_to_list(row[4] or ""),
        reply_to=row[5] or None,
        is_active=row[6],
        updated_at=row[7],
    )


@router.get("/tenant-email-history", response_model=List[EmailHistoryItem])
def list_tenant_email_history(
    tenant_id: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(require_viewer_role),
):
    email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH route_emails AS (
              SELECT LOWER(TRIM(x.email)) AS email, NOW() AS last_used_at
              FROM tenant_routes tr
              CROSS JOIN LATERAL regexp_split_to_table(COALESCE(tr.to_emails, ''), '\\s*,\\s*') AS x(email)
              WHERE tr.tenant_id = %s
            ),
            ticket_emails AS (
              SELECT LOWER(TRIM(requester_email)) AS email, MAX(created_at) AS last_used_at
              FROM tickets
              WHERE tenant_id = %s
              GROUP BY LOWER(TRIM(requester_email))
            ),
            merged AS (
              SELECT email, last_used_at FROM route_emails
              UNION ALL
              SELECT email, last_used_at FROM ticket_emails
            )
            SELECT email, MAX(last_used_at) AS last_used_at
            FROM merged
            WHERE email <> ''
              AND email ~ %s
            GROUP BY email
            ORDER BY last_used_at DESC, email ASC
            LIMIT %s
            """,
            (tenant_id, tenant_id, email_regex, limit),
        )
        rows = cur.fetchall()

    return [EmailHistoryItem(email=row[0], last_used_at=row[1]) for row in rows]


@router.get("/tenant-sla-policies/{tenant_id}", response_model=TenantSlaPolicyOut)
def get_tenant_sla_policy(tenant_id: str, _: None = Depends(require_viewer_role)):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT tenant_id, p1_minutes, p2_minutes, p3_minutes, p4_minutes, updated_at
            FROM tenant_sla_policies
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Tenant SLA policy not found")
    return TenantSlaPolicyOut(
        tenant_id=row[0],
        p1_minutes=row[1],
        p2_minutes=row[2],
        p3_minutes=row[3],
        p4_minutes=row[4],
        updated_at=row[5],
    )


@router.patch("/tenant-sla-policies/{tenant_id}", response_model=TenantSlaPolicyOut)
def update_tenant_sla_policy(
    tenant_id: str,
    payload: TenantSlaPolicyUpdate,
    _: None = Depends(require_admin_role),
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
                    INSERT INTO tenant_sla_policies (tenant_id, p1_minutes, p2_minutes, p3_minutes, p4_minutes)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id) DO UPDATE SET
                      p1_minutes = EXCLUDED.p1_minutes,
                      p2_minutes = EXCLUDED.p2_minutes,
                      p3_minutes = EXCLUDED.p3_minutes,
                      p4_minutes = EXCLUDED.p4_minutes,
                      updated_at = NOW()
                    RETURNING tenant_id, p1_minutes, p2_minutes, p3_minutes, p4_minutes, updated_at
                    """,
                    (
                        tenant_id,
                        payload.p1_minutes,
                        payload.p2_minutes,
                        payload.p3_minutes,
                        payload.p4_minutes,
                    ),
                )
                row = cur.fetchone()
                log_admin_action(
                    conn,
                    tenant_id=tenant_id,
                    actor_email=actor_email,
                    actor_role=actor_role,
                    action="TENANT_SLA_POLICY_UPDATED",
                    target_type="tenant_sla_policy",
                    target_id=tenant_id,
                    details={
                        "p1_minutes": row[1],
                        "p2_minutes": row[2],
                        "p3_minutes": row[3],
                        "p4_minutes": row[4],
                    },
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return TenantSlaPolicyOut(
        tenant_id=row[0],
        p1_minutes=row[1],
        p2_minutes=row[2],
        p3_minutes=row[3],
        p4_minutes=row[4],
        updated_at=row[5],
    )
