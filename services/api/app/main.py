import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import is_rate_limited
from app.db.session import DatabaseConnectionError, DatabaseNotConfiguredError
from app.routers.events import router as events_router
from app.routers.health import router as health_router
from app.routers.intake import router as intake_router
from app.routers.tickets import router as tickets_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("app.request")

app = FastAPI(title=settings.app_name)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    settings = get_settings()
    skip_rate_limit = request.url.path in {"/health", "/ready", "/docs", "/openapi.json"}
    if not skip_rate_limit and settings.rate_limit_requests_per_minute > 0:
        client_ip = "unknown"
        if request.client and request.client.host:
            client_ip = request.client.host
        limited = is_rate_limited(
            key=f"{client_ip}:{request.url.path}",
            max_requests=settings.rate_limit_requests_per_minute,
        )
        if limited:
            response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            response.headers["X-Request-ID"] = request_id
            response.headers["Retry-After"] = "60"
            logger.warning(
                "request_id=%s method=%s path=%s status=%s reason=rate_limited",
                request_id,
                request.method,
                request.url.path,
                429,
            )
            return response

    started_at = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(DatabaseNotConfiguredError)
def handle_db_not_configured(request: Request, exc: DatabaseNotConfiguredError):
    request_id = getattr(request.state, "request_id", "")
    response = JSONResponse(status_code=503, content={"detail": str(exc)})
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(DatabaseConnectionError)
def handle_db_unavailable(request: Request, exc: DatabaseConnectionError):
    request_id = getattr(request.state, "request_id", "")
    response = JSONResponse(status_code=503, content={"detail": str(exc)})
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


app.include_router(intake_router)
app.include_router(tickets_router)
app.include_router(events_router)
app.include_router(health_router)
