"""ROS Mock REST — health-check endpoints."""

from shared.health import create_health_router

router = create_health_router()
