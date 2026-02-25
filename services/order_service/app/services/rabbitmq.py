"""Order service — RabbitMQ event publisher and consumer."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from shared.rabbitmq import RabbitMQClient
from app.core.database import async_session_factory
from app.services import order_service as order_svc
from app.services.auto_assign import assign_driver

logger = structlog.get_logger()

# Module-level client (initialised during lifespan)
mq_client: RabbitMQClient | None = None


async def init_rabbitmq(url: str) -> None:
    """Connect to RabbitMQ and start consuming status updates."""
    global mq_client
    mq_client = RabbitMQClient(url, service_name="order_service")
    await mq_client.connect()

    # Consume status updates from integration_service
    await mq_client.consume(
        queue_name="order_service.status_updates",
        routing_keys=[
            "order.cms_registered",
            "order.wms_received",
            "order.route_optimized",
            "order.saga_failed",
        ],
        handler=_handle_status_update,
    )


async def close_rabbitmq() -> None:
    """Disconnect cleanly."""
    global mq_client
    if mq_client:
        await mq_client.close()
        mq_client = None


async def publish_order_created(order_id: uuid.UUID, order_data: dict[str, Any]) -> None:
    """Publish order.created event to trigger the integration saga."""
    if not mq_client:
        logger.warning("rabbitmq_not_connected", event="order.created")
        return

    await mq_client.publish_event(
        routing_key="order.created",
        body={
            "event": "order.created",
            "order_id": str(order_id),
            **order_data,
        },
    )


async def publish_order_status(
    order_id: uuid.UUID,
    status: str,
    details: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """Publish a generic order status change event."""
    if not mq_client:
        return

    await mq_client.publish_event(
        routing_key="notification.status_changed",
        body={
            "event": "notification.status_changed",
            "order_id": str(order_id),
            "status": status,
            "details": details,
        },
        correlation_id=correlation_id,
    )


async def _handle_status_update(body: dict[str, Any]) -> None:
    """
    Process status updates arriving from integration_service.
    Updates the order in DB and publishes downstream events.
    """
    event = body.get("event", "")
    order_id_str = body.get("order_id")

    if not order_id_str:
        logger.warning("missing_order_id", event=event)
        return

    order_id = uuid.UUID(order_id_str)

    status_map = {
        "order.cms_registered": ("CMS_REGISTERED", "cms_reference"),
        "order.wms_received": ("WMS_RECEIVED", "wms_reference"),
        "order.route_optimized": ("ROUTE_OPTIMIZED", "route_id"),
        "order.saga_failed": ("FAILED", None),
    }

    if event not in status_map:
        logger.warning("unknown_event", event=event)
        return

    new_status, ref_field = status_map[event]

    extra_fields = {}
    if ref_field and ref_field in body:
        extra_fields[ref_field] = body[ref_field]

    # If route_optimized, also set status to READY
    is_ready = False
    if event == "order.route_optimized":
        new_status = "READY"
        is_ready = True
        if "route_id" in body:
            extra_fields["route_id"] = body["route_id"]

    async with async_session_factory() as session:
        order = await order_svc.update_order_status(
            session,
            order_id=order_id,
            new_status=new_status,
            details=body.get("details", f"Updated via {event}"),
            extra_fields=extra_fields if extra_fields else None,
        )
        if order:
            logger.info(
                "order_status_updated_via_mq",
                order_id=str(order_id),
                new_status=new_status,
            )
            # Publish downstream for notification_service
            correlation_id = body.get("_correlation_id")
            await publish_order_status(
                order_id, new_status, correlation_id=correlation_id,
            )

            # --- Auto Assignment Trigger ---
            if is_ready:
                # Assign a pickup driver immediately
                assigned_order = await assign_driver(session, order, "pickup")
                if assigned_order.pickup_driver_id:
                    # Update status to PICKUP_ASSIGNED
                    order = await order_svc.update_order_status(
                        session,
                        order_id=order_id,
                        new_status="PICKUP_ASSIGNED",
                        details="System auto-assigned pickup driver",
                        extra_fields={"pickup_driver_id": assigned_order.pickup_driver_id},
                    )
                    logger.info(
                        "auto_assigned_pickup_driver",
                        order_id=str(order_id),
                        driver=assigned_order.pickup_driver_id,
                    )
                    await publish_order_status(
                        order_id, "PICKUP_ASSIGNED", correlation_id=correlation_id,
                    )
