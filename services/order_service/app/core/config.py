"""Order Service — environment-based configuration."""

from __future__ import annotations

from shared.config import BaseServiceSettings


class OrderServiceSettings(BaseServiceSettings):
    """Settings specific to the Order Service."""

    service_name: str = "order_service"
    service_port: int = 8001

    # Database
    database_url: str = (
        "postgresql+asyncpg://swifttrack:swifttrack_secret@postgres:5432/swifttrack"
    )

    # Connection pool
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # Auto Assignment Drivers
    driver_usernames: str = "driver1,driver2,driver3"


settings = OrderServiceSettings()
