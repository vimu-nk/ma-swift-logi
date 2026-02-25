"""WMS Mock TCP — HTTP health-check sidecar.

A minimal FastAPI app exposing only health endpoints so Docker
and orchestrators can probe the service.
"""

from __future__ import annotations

from fastapi import FastAPI

from shared.health import create_health_router

health_app = FastAPI(
    title="WMS Mock TCP Health Sidecar",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

health_app.include_router(create_health_router())
