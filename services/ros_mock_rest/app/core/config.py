"""ROS Mock REST — configuration."""

from __future__ import annotations

from shared.config import BaseServiceSettings


class RosMockSettings(BaseServiceSettings):
    service_name: str = "ros_mock_rest"
    service_port: int = 8005


settings = RosMockSettings()
