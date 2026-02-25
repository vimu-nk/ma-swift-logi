"""ROS Mock REST — FastAPI application factory.

Simulates a REST-based Routing & Optimization System.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings
from app.core.events import lifespan
from app.routers import health
from app.routers.routes import router as routes_router

from shared.logging import setup_logging
from shared.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    setup_logging(
        log_level=settings.log_level,
        json_logs=settings.json_logs,
        service_name=settings.service_name,
    )

    application = FastAPI(
        title="SwiftTrack ROS Mock (REST)",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    application.add_middleware(RequestContextMiddleware)
    application.include_router(health.router)
    application.include_router(routes_router)

    return application


app = create_app()
