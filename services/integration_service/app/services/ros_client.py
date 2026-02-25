"""Integration Service — ROS REST client."""

from __future__ import annotations

import structlog
import httpx

logger = structlog.get_logger()


async def optimize_route(
    http_client: httpx.AsyncClient,
    ros_url: str,
    *,
    order_id: str,
    delivery_address: str,
) -> dict:
    """Request route optimisation from ROS (REST/JSON)."""
    payload = {
        "delivery_points": [
            {
                "order_id": order_id,
                "address": delivery_address,
                "priority": "normal",
            },
        ],
        "vehicle_id": "VH-001",
        "depot_address": "SwiftLogistics Warehouse, Colombo 10",
    }

    response = await http_client.post(
        f"{ros_url}/api/routes/optimize",
        json=payload,
    )
    response.raise_for_status()

    data = response.json()
    route_id = data.get("route_id", "UNKNOWN")

    logger.info("ros_route_optimized", order_id=order_id, route_id=route_id)
    return data
