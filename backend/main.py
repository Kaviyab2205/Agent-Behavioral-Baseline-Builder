import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base
from backend.api import health, agents, scenarios, baseline, production, monitor, alerts, settings

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Agent Behavioral Baseline Builder",
    description="Backend API for establishing agent behavioral baselines prior to production.",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(agents.router, prefix="/api", tags=["Agents"])
app.include_router(scenarios.router, prefix="/api", tags=["Scenarios"])
app.include_router(baseline.router, prefix="/api", tags=["Baseline"])
app.include_router(production.router, prefix="/api", tags=["Production"])
app.include_router(monitor.router, prefix="/api", tags=["Monitor"])
app.include_router(alerts.router, prefix="/api", tags=["Alerts"])
app.include_router(settings.router, prefix="/api", tags=["Settings"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
