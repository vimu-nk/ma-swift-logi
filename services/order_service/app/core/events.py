"""Order Service — application lifespan (startup / shutdown hooks)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import engine
from app.services.rabbitmq import init_rabbitmq, close_rabbitmq

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown resources."""
    log.info("order_service starting up", db_url=settings.database_url.split("@")[-1])

    # Initialise RabbitMQ connection and consumers
    await init_rabbitmq(settings.rabbitmq_url)

    yield

    # Shutdown
    log.info("order_service shutting down")
    await close_rabbitmq()
    await engine.dispose()
