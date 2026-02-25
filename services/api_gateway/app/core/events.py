"""API Gateway — application lifespan (startup / shutdown hooks)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.core.config import settings
from app.routers.websocket import init_ws_consumer, close_ws_consumer

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown resources."""
    log.info("api_gateway starting up")

    # Start WebSocket → RabbitMQ bridge consumer
    await init_ws_consumer(settings.rabbitmq_url)

    yield

    log.info("api_gateway shutting down")
    await close_ws_consumer()
