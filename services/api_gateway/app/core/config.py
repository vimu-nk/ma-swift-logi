"""API Gateway — environment-based configuration."""

from __future__ import annotations

from shared.config import BaseServiceSettings


class ApiGatewaySettings(BaseServiceSettings):
    """Settings specific to the API Gateway."""

    service_name: str = "api_gateway"
    service_port: int = 8000

    # JWT
    jwt_secret_key: str = "swifttrack-dev-secret-key-change-in-production"

    # Downstream service URLs (resolved via Docker network)
    order_service_url: str = "http://order_service:8001"
    integration_service_url: str = "http://integration_service:8002"
    notification_service_url: str = "http://notification_service:8003"


settings = ApiGatewaySettings()
