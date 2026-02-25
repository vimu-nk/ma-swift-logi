"""WMS Mock TCP — configuration."""

from __future__ import annotations

from shared.config import BaseServiceSettings


class WmsMockSettings(BaseServiceSettings):
    service_name: str = "wms_mock_tcp"
    tcp_port: int = 9000
    health_port: int = 9001


settings = WmsMockSettings()
