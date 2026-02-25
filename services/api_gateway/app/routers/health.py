"""API Gateway — health-check endpoints."""

from __future__ import annotations

from shared.health import create_health_router

# No readiness checks for the gateway itself (stateless proxy);
# downstream connectivity is checked per-request.
router = create_health_router()
