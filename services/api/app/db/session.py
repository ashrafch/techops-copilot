import psycopg
from contextlib import contextmanager

from app.core.config import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    pass


class DatabaseConnectionError(RuntimeError):
    pass


@contextmanager
def get_conn():
    settings = get_settings()
    if not settings.database_url:
        raise DatabaseNotConfiguredError("DATABASE_URL not set")

    try:
        conn = psycopg.connect(
            settings.database_url,
            connect_timeout=settings.db_connect_timeout_seconds,
        )
    except psycopg.Error as exc:
        raise DatabaseConnectionError("Database unavailable") from exc

    try:
        yield conn
    finally:
        conn.close()
