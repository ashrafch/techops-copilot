import logging
import time
import uuid
import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import is_rate_limited
from app.db.session import DatabaseConnectionError, DatabaseNotConfiguredError
from app.domain.sla_monitor_job import list_tenants_for_scheduler, run_sla_monitor_for_tenant
from app.routers.admin import router as admin_router
from app.routers.automation import router as automation_router
from app.routers.auth_router import router as auth_router
from app.routers.events import router as events_router
from app.routers.health import router as health_router
from app.routers.intake import router as intake_router
from app.routers.routes import router as routes_router
from app.routers.tickets import router as tickets_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("app.request")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


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
app.include_router(routes_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(automation_router)

# Versioned API aliases for enterprise integrations.
app.include_router(intake_router, prefix="/v1")
app.include_router(tickets_router, prefix="/v1")
app.include_router(events_router, prefix="/v1")
app.include_router(routes_router, prefix="/v1")
app.include_router(health_router, prefix="/v1")
app.include_router(auth_router, prefix="/v1")
app.include_router(admin_router, prefix="/v1")
app.include_router(automation_router, prefix="/v1")


@app.on_event("startup")
async def startup_scheduler():
    settings = get_settings()
    if not settings.sla_monitor_scheduler_enabled:
        return

    async def _runner():
        while True:
            try:
                tenants = list_tenants_for_scheduler()
                for tenant_id in tenants:
                    result = run_sla_monitor_for_tenant(tenant_id=tenant_id, limit=500)
                    logger.info(
                        "scheduler=sla_monitor tenant_id=%s scanned=%s at_risk=%s breached=%s",
                        tenant_id,
                        result["scanned"],
                        result["at_risk_alerted"],
                        result["breached_alerted"],
                    )
            except Exception:
                logger.exception("scheduler=sla_monitor_failed")
            await asyncio.sleep(max(30, settings.sla_monitor_scheduler_interval_seconds))

    app.state.sla_scheduler_task = asyncio.create_task(_runner())


@app.on_event("shutdown")
async def shutdown_scheduler():
    task = getattr(app.state, "sla_scheduler_task", None)
    if task is not None:
        task.cancel()
