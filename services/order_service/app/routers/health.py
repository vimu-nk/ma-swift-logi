"""Order Service — health-check endpoints with database readiness probe."""

from __future__ import annotations

from sqlalchemy import text

from app.core.database import engine
from shared.health import create_health_router


async def check_database() -> bool:
    """Return True if the database is reachable."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


router = create_health_router(readiness_checks=[check_database])
