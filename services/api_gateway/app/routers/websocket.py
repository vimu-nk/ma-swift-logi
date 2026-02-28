"""API Gateway — WebSocket endpoint for real-time order tracking."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from shared.rabbitmq import RabbitMQClient

router = APIRouter(tags=["WebSocket Tracking"])
logger = structlog.get_logger()

# Connected WebSocket clients: client_id -> list[WebSocket]
_connections: dict[str, list[WebSocket]] = {}


@router.websocket("/ws/tracking/{client_id}")
async def tracking_websocket(websocket: WebSocket, client_id: str) -> None:
    """
    WebSocket for real-time order tracking.

    Clients connect with their client_id and receive live status updates
    for their orders.
    """
    await websocket.accept()
    logger.info("websocket_connected", client_id=client_id)

    # Register connection
    if client_id not in _connections:
        _connections[client_id] = []
    _connections[client_id].append(websocket)

    try:
        # Keep connection alive — wait for client messages (or disconnect)
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=45.0)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                else:
                    await websocket.send_json({"type": "ack", "data": data})
            except TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info("websocket_disconnected", client_id=client_id)
    finally:
        _connections[client_id].remove(websocket)
        if not _connections[client_id]:
            del _connections[client_id]


async def broadcast_to_client(client_id: str, message: dict[str, Any]) -> None:
    """Send a message to all WebSocket connections for a given client_id."""
    if client_id not in _connections:
        return

    dead_connections = []
    for ws in _connections[client_id]:
        try:
            await ws.send_json(message)
        except Exception:
            dead_connections.append(ws)

    for ws in dead_connections:
        _connections[client_id].remove(ws)


async def broadcast_to_all(message: dict[str, Any]) -> None:
    """Send a message to ALL connected WebSocket clients."""
    for client_id in list(_connections.keys()):
        await broadcast_to_client(client_id, message)


# ── RabbitMQ → WebSocket bridge ──────────────

_ws_mq_client: RabbitMQClient | None = None


async def init_ws_consumer(rmq_url: str) -> None:
    """Start consuming notification events for WebSocket push."""
    global _ws_mq_client
    _ws_mq_client = RabbitMQClient(rmq_url, service_name="api_gateway_ws")
    await _ws_mq_client.connect()

    queue_name = f"api_gateway.ws_notifications.{os.getpid()}"

    await _ws_mq_client.consume(
        queue_name=queue_name,
        routing_keys=[
            "notification.order_update",
            "notification.status_changed",
        ],
        handler=_handle_ws_event,
        durable=False,
        auto_delete=True,
    )


async def close_ws_consumer() -> None:
    """Disconnect cleanly."""
    global _ws_mq_client
    if _ws_mq_client:
        await _ws_mq_client.close()
        _ws_mq_client = None


async def _handle_ws_event(body: dict[str, Any]) -> None:
    """Push RabbitMQ events to connected WebSocket clients."""
    order_id = body.get("order_id", "")
    message = body.get("message", "")
    event = body.get("event", "")

    ws_message = {
        "type": "order_update",
        "order_id": order_id,
        "event": event,
        "status": body.get("status", ""),
        "message": message,
    }

    # Broadcast to all (in production, map order_id → client_id via DB)
    await broadcast_to_all(ws_message)
    logger.info("ws_broadcast", event_type=event, order_id=order_id)
