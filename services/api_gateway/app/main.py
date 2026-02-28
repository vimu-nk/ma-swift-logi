"""API Gateway — FastAPI application factory.

Central entry-point for all client requests. Proxies to downstream services.
"""

from __future__ import annotations

import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.events import lifespan
from app.routers import health
from app.routers.auth import router as auth_router
from app.routers.orders import router as orders_router
from app.routers.websocket import router as ws_router

from shared.logging import setup_logging
from shared.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    setup_logging(
        log_level=settings.log_level,
        json_logs=settings.json_logs,
        service_name=settings.service_name,
    )

    application = FastAPI(
        title="SwiftTrack API Gateway",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS for dashboard clients
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.add_middleware(RequestContextMiddleware)

    # Routers
    application.include_router(health.router)
    application.include_router(auth_router)
    application.include_router(orders_router)
    application.include_router(ws_router)

    # Static files (frontend dashboard)
    static_dir = pathlib.Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @application.get("/", include_in_schema=False)
        async def root():
            return FileResponse(str(static_dir / "landing.html"))

        @application.get("/landing", include_in_schema=False)
        async def serve_landing():
            return FileResponse(str(static_dir / "landing.html"))

        @application.get("/login", include_in_schema=False)
        async def serve_login():
            return FileResponse(str(static_dir / "login.html"))

        @application.get("/client", include_in_schema=False)
        async def serve_client():
            return FileResponse(str(static_dir / "client.html"))

        @application.get("/driver", include_in_schema=False)
        async def serve_driver():
            return FileResponse(str(static_dir / "driver.html"))

        @application.get("/pickup", include_in_schema=False)
        async def serve_pickup():
            return FileResponse(str(static_dir / "pickup.html"))

        @application.get("/delivery", include_in_schema=False)
        async def serve_delivery():
            return FileResponse(str(static_dir / "delivery.html"))

        @application.get("/admin", include_in_schema=False)
        async def serve_admin():
            return FileResponse(str(static_dir / "admin.html"))

    return application


app = create_app()
