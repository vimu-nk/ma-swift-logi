"""Reusable health-check router.

Provides ``/health/live`` (liveness) and ``/health/ready`` (readiness) endpoints.
The readiness probe accepts optional async callables that must all succeed.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Response, status

HealthCheck = Callable[[], Awaitable[bool]]


def create_health_router(
    readiness_checks: list[HealthCheck] | None = None,
) -> APIRouter:
    """Build a health router with optional readiness probes.

    Args:
        readiness_checks: List of async callables returning True if healthy.

    Returns:
        A FastAPI ``APIRouter`` with ``/health/live`` and ``/health/ready``.
    """
    router = APIRouter(prefix="/health", tags=["health"])
    checks = readiness_checks or []

    @router.get("/live", summary="Liveness probe")
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @router.get("/ready", summary="Readiness probe")
    async def readiness(response: Response) -> dict[str, Any]:
        results: dict[str, str] = {}
        all_ok = True

        for check in checks:
            name = getattr(check, "__name__", str(check))
            try:
                ok = await check()
                results[name] = "ok" if ok else "failing"
                if not ok:
                    all_ok = False
            except Exception as exc:
                results[name] = f"error: {exc}"
                all_ok = False

        if not all_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {"status": "ready" if all_ok else "unavailable", "checks": results}

    return router
