"""Integration Service — application lifespan (startup / shutdown hooks)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.core.config import settings
from app.services.rabbitmq import init as init_rabbitmq, close as close_rabbitmq

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown resources."""
    log.info(
        "integration_service starting up",
        cms_url=settings.cms_url,
        ros_url=settings.ros_url,
        wms_host=settings.wms_host,
    )

    await init_rabbitmq(settings.rabbitmq_url)

    yield

    log.info("integration_service shutting down")
    await close_rabbitmq()
