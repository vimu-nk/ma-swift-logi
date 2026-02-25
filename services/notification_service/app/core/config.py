"""Notification Service — environment-based configuration."""

from __future__ import annotations

from shared.config import BaseServiceSettings


class NotificationServiceSettings(BaseServiceSettings):
    """Settings specific to the Notification Service."""

    service_name: str = "notification_service"
    service_port: int = 8003


settings = NotificationServiceSettings()
