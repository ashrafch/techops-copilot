from fastapi import APIRouter, Depends, HTTPException
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


class UserOut(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    tenant_id: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, email, full_name, password_hash, password_salt, role, tenant_id, is_active
            FROM app_users
            WHERE LOWER(email) = LOWER(%s)
            """,
            (str(payload.email),),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not row[7]:
        raise HTTPException(status_code=403, detail="User is inactive")

    if not verify_password(payload.password, row[4], row[3]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    settings = get_settings()
    token = issue_auth_token(
        secret=settings.auth_secret_key,
        sub=str(row[0]),
        email=row[1],
        role=row[5],
        tenant_id=row[6],
        ttl_minutes=settings.auth_token_ttl_minutes,
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.auth_token_ttl_minutes * 60,
        user=UserOut(email=row[1], full_name=row[2], role=row[5], tenant_id=row[6]),
    )


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
