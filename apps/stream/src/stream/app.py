"""FastAPI application factory for the stream service."""

from __future__ import annotations

from fastapi import FastAPI

from stream import health, routes_pipe, routes_stream
from stream.subscribers import SubscriberRegistry


def create_app() -> FastAPI:
    app = FastAPI(title="cawnex-stream", docs_url=None, redoc_url=None)
    app.state.registry = SubscriberRegistry()
    app.include_router(health.router)
    app.include_router(routes_stream.router)
    app.include_router(routes_pipe.router)
    return app


app = create_app()
