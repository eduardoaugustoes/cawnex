"""FastAPI application factory for the stream service."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from stream import health, routes_pipe, routes_stream
from stream.sqs_poller import SqsPoller
from stream.subscribers import SubscriberRegistry

log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Spin up the SQS poller if a queue URL is configured."""
    queue_url = os.environ.get("EVENTS_QUEUE_URL", "")
    region = os.environ.get("AWS_REGION", "us-east-1")
    poller: SqsPoller | None = None
    if queue_url:
        poller = SqsPoller(
            queue_url=queue_url,
            registry=app.state.registry,
            region=region,
        )
        await poller.start()
        log.info("sqs poller started for queue %s", queue_url)
    else:
        log.info("EVENTS_QUEUE_URL not set — sqs poller disabled")
    try:
        yield
    finally:
        if poller is not None:
            await poller.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="cawnex-stream",
        docs_url=None,
        redoc_url=None,
        lifespan=_lifespan,
    )
    app.state.registry = SubscriberRegistry()
    app.include_router(health.router)
    app.include_router(routes_stream.router)
    app.include_router(routes_pipe.router)
    return app


app = create_app()
