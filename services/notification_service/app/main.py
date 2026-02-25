"""Notification Service — FastAPI application factory.

Consumes messages from RabbitMQ and dispatches notifications.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings
from app.core.events import lifespan
from app.routers import health

from shared.logging import setup_logging
from shared.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    setup_logging(
        log_level=settings.log_level,
        json_logs=settings.json_logs,
        service_name=settings.service_name,
    )

    application = FastAPI(
        title="SwiftTrack Notification Service",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    application.add_middleware(RequestContextMiddleware)
    application.include_router(health.router)

    return application


app = create_app()
