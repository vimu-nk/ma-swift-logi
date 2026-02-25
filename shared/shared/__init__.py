"""SwiftTrack shared utilities package."""

from shared.logging import setup_logging
from shared.config import BaseServiceSettings

# Lazy import — RabbitMQClient requires aio-pika which not all services install
def __getattr__(name: str):
    if name == "RabbitMQClient":
        from shared.rabbitmq import RabbitMQClient
        return RabbitMQClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["setup_logging", "BaseServiceSettings", "RabbitMQClient"]
