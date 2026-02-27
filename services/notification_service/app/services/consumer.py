"""Notification Service — RabbitMQ event consumer."""

from __future__ import annotations

from typing import Any

import structlog

from shared.rabbitmq import RabbitMQClient

logger = structlog.get_logger()

mq_client: RabbitMQClient | None = None


async def init(rmq_url: str) -> None:
    """Connect to RabbitMQ and start consuming all order events."""
    global mq_client
    mq_client = RabbitMQClient(rmq_url, service_name="notification_service")
    await mq_client.connect()

    await mq_client.consume(
        queue_name="notification_service.all_events",
        routing_keys=[
            "order.created",
            "order.cms_registered",
            "order.wms_received",
            "order.route_optimized",
            "order.saga_failed",
            "notification.status_changed",
        ],
        handler=_handle_event,
    )


async def close() -> None:
    """Disconnect cleanly."""
    global mq_client
    if mq_client:
        await mq_client.close()
        mq_client = None


async def _handle_event(body: dict[str, Any]) -> None:
    """
    Process order events — stub notification logic.
    In production, this would send emails, SMS, push notifications, etc.
    """
    event = body.get("event", "unknown")
    order_id = body.get("order_id", "unknown")
    status = body.get("status", "")

    # Stub: log what notification would be sent
    notification_map = {
        "order.created": ("email", "Order {order_id} received — processing started."),
        "order.cms_registered": ("internal", "Order {order_id} registered in CMS."),
        "order.wms_received": ("internal", "Order {order_id} received at warehouse."),
        "order.route_optimized": ("email", "Order {order_id} — delivery route optimised."),
        "notification.status_changed": ("push", "Order {order_id} status → {status}."),
        "order.saga_failed": ("alert", "Order {order_id} processing failed — requires attention."),
    }

    channel, message_tpl = notification_map.get(
        event, ("log", "Unknown event {event} for order {order_id}")
    )
    message = message_tpl.format(order_id=order_id, event=event, status=status)

    logger.info(
        "notification_sent",
        event=event,
        order_id=order_id,
        channel=channel,
        message=message,
    )

    # Publish to a notification-specific exchange for WebSocket consumers
    if mq_client:
        await mq_client.publish_event(
            routing_key="notification.order_update",
            body={
                "event": event,
                "order_id": order_id,
                "status": status,
                "message": message,
                "channel": channel,
            },
        )
