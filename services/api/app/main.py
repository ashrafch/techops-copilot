from fastapi import FastAPI
from app.routers.intake import router as intake_router
from app.routers.tickets import router as tickets_router
from app.routers.events import router as events_router

app = FastAPI(title="TechOps Copilot API")

app.include_router(intake_router)
app.include_router(tickets_router)
app.include_router(events_router)

@app.get("/health")
def health():
    return {"status": "ok"}
