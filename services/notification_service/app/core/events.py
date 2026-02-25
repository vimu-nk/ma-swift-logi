"""Notification Service — application lifespan (startup / shutdown hooks)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.core.config import settings
from app.services.consumer import init as init_consumer, close as close_consumer

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown resources."""
    log.info("notification_service starting up")

    await init_consumer(settings.rabbitmq_url)

    yield

    log.info("notification_service shutting down")
    await close_consumer()
