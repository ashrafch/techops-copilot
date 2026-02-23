from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import DatabaseConnectionError, DatabaseNotConfiguredError
from app.routers.events import router as events_router
from app.routers.health import router as health_router
from app.routers.intake import router as intake_router
from app.routers.tickets import router as tickets_router

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)


@app.exception_handler(DatabaseNotConfiguredError)
def handle_db_not_configured(_: Request, exc: DatabaseNotConfiguredError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(DatabaseConnectionError)
def handle_db_unavailable(_: Request, exc: DatabaseConnectionError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(intake_router)
app.include_router(tickets_router)
app.include_router(events_router)
app.include_router(health_router)
