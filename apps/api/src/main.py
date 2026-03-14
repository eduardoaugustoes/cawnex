"""
Cawnex API — FastAPI application.

Multi-tenant API serving the iOS and web clients.
All routes (except /health) require a valid Cognito JWT.
Tenant context is extracted from the JWT and available on every request.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import health

app = FastAPI(
    title="Cawnex API",
    version="0.1.0",
    docs_url="/docs" if __import__("os").environ.get("STAGE") != "prod" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # API GW handles CORS, this is a fallback
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
