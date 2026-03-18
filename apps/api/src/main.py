"""
Cawnex API — FastAPI application.

Multi-tenant API serving the iOS and web clients.
All routes (except /health) require a valid Cognito JWT.
Tenant context is extracted from the JWT and available on every request.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import (
    ai,
    autopilot,
    config,
    documents,
    goals,
    health,
    hub,
    human_tasks,
    milestones,
    mvi,
    projects,
    vault,
    waves,
)

app = FastAPI(
    title="Cawnex API",
    version="0.2.0",
    docs_url="/docs" if __import__("os").environ.get("STAGE") != "prod" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # API GW handles CORS, this is a fallback
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(config.router)
app.include_router(ai.router)
app.include_router(autopilot.router)
app.include_router(projects.router)
app.include_router(waves.router)
app.include_router(mvi.router)
app.include_router(hub.router)
app.include_router(milestones.router)
app.include_router(goals.router)
app.include_router(documents.router)
app.include_router(human_tasks.router)
app.include_router(vault.router)
