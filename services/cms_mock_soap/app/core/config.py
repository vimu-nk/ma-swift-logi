"""CMS Mock SOAP — configuration."""

from __future__ import annotations

from shared.config import BaseServiceSettings


class CmsMockSettings(BaseServiceSettings):
    service_name: str = "cms_mock_soap"
    service_port: int = 8004


settings = CmsMockSettings()
