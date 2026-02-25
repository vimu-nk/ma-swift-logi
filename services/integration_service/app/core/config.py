"""Integration Service — environment-based configuration."""

from __future__ import annotations

from shared.config import BaseServiceSettings


class IntegrationServiceSettings(BaseServiceSettings):
    """Settings specific to the Integration Service."""

    service_name: str = "integration_service"
    service_port: int = 8002

    # External system endpoints (match docker-compose service names)
    cms_url: str = "http://cms_mock_soap:8004"
    ros_url: str = "http://ros_mock_rest:8005"
    wms_host: str = "wms_mock_tcp"
    wms_port: int = 9000

    # Internal services
    order_service_url: str = "http://order_service:8001"


settings = IntegrationServiceSettings()
