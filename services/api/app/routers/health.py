from fastapi import APIRouter, HTTPException

from app.db.session import (
    DatabaseConnectionError,
    DatabaseNotConfiguredError,
    get_conn,
)

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except (DatabaseNotConfiguredError, DatabaseConnectionError):
        raise HTTPException(status_code=503, detail="Database not ready")

    return {"status": "ready"}
