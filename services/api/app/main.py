from fastapi import FastAPI
from app.routers.health import router as health_router
from app.routers.intake import router as intake_router

app = FastAPI(title="TechOps Copilot API", version="0.1.0")

app.include_router(health_router)
app.include_router(intake_router)
