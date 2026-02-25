"""CMS Mock SOAP — FastAPI application factory.

Simulates a SOAP-based Content Management System by returning XML responses.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings
from app.core.events import lifespan
from app.routers import health
from app.routers.soap import router as soap_router

from shared.logging import setup_logging
from shared.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    setup_logging(
        log_level=settings.log_level,
        json_logs=settings.json_logs,
        service_name=settings.service_name,
    )

    application = FastAPI(
        title="SwiftTrack CMS Mock (SOAP)",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    application.add_middleware(RequestContextMiddleware)
    application.include_router(health.router)
    application.include_router(soap_router)

    return application


app = create_app()
