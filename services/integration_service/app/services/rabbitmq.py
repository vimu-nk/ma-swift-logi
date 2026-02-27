"""Integration Service — RabbitMQ consumer and publisher."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from shared.rabbitmq import RabbitMQClient
from app.core.config import settings
from app.services.saga import execute_order_saga

logger = structlog.get_logger()

# Module-level state
mq_client: RabbitMQClient | None = None
http_client: httpx.AsyncClient | None = None


async def init(rmq_url: str) -> None:
    """Connect to RabbitMQ and start consuming order.created events."""
    global mq_client, http_client

    http_client = httpx.AsyncClient(timeout=30.0)

    mq_client = RabbitMQClient(rmq_url, service_name="integration_service")
    await mq_client.connect()

    await mq_client.consume_with_retry(
        queue_name="integration_service.order_created",
        routing_keys=["order.created"],
        handler=_handle_order_created,
        max_retries=3,
        retry_ttl=30_000,  # 30 seconds
    )


async def close() -> None:
    """Disconnect cleanly."""
    global mq_client, http_client
    if http_client:
        await http_client.aclose()
        http_client = None
    if mq_client:
        await mq_client.close()
        mq_client = None


async def _handle_order_created(body: dict[str, Any]) -> None:
    """Consume order.created → execute saga → publish results."""
    order_id = body.get("order_id", "unknown")
    correlation_id = body.get("_correlation_id")
    logger.info("saga_triggered", order_id=order_id, correlation_id=correlation_id)

    if not http_client or not mq_client:
        logger.error("clients_not_initialised")
        return

    result = await execute_order_saga(
        http_client,
        cms_url=settings.cms_url,
        ros_url=settings.ros_url,
        wms_host=settings.wms_host,
        wms_port=settings.wms_port,
        order_service_url=settings.order_service_url,
        order_id=order_id,
        client_id=body.get("client_id", ""),
        pickup_address=body.get("pickup_address", ""),
        delivery_address=body.get("delivery_address", ""),
        package_details=body.get("package_details", {}),
    )

    # Publish intermediate events for each completed step
    for step in result.completed_steps:
        event_data: dict[str, Any] = {
            "event": f"order.{step.lower()}",
            "order_id": order_id,
        }
        if step == "CMS_REGISTERED" and result.cms_reference:
            event_data["cms_reference"] = result.cms_reference
        elif step == "WMS_RECEIVED" and result.wms_reference:
            event_data["wms_reference"] = result.wms_reference
        elif step == "ROUTE_OPTIMIZED" and result.route_id:
            event_data["route_id"] = result.route_id

        await mq_client.publish_event(
            routing_key=f"order.{step.lower()}",
            body=event_data,
            correlation_id=correlation_id,
        )

    # If saga failed, publish failure event
    if not result.success:
        await mq_client.publish_event(
            routing_key="order.saga_failed",
            body={
                "event": "order.saga_failed",
                "order_id": order_id,
                "error": result.error,
                "completed_steps": result.completed_steps,
            },
            correlation_id=correlation_id,
        )
        logger.error("saga_failed", order_id=order_id, error=result.error)
    else:
        logger.info("saga_success", order_id=order_id)
