"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cawnex_api.config import settings
from cawnex_api.deps.redis import close_redis
from cawnex_api.routers import health, tenants, repos, tasks, agents, workflows, webhooks, stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cawnex API",
        description="Coordinated Intelligence — Multi-agent orchestration platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    prefix = "/api/v1"
    app.include_router(health.router)  # /health (no prefix)
    app.include_router(tenants.router, prefix=prefix)
    app.include_router(repos.router, prefix=prefix)
    app.include_router(tasks.router, prefix=prefix)
    app.include_router(agents.router, prefix=prefix)
    app.include_router(workflows.router, prefix=prefix)
    app.include_router(webhooks.router, prefix=prefix)
    app.include_router(stream.router, prefix=prefix)

    return app


app = create_app()
