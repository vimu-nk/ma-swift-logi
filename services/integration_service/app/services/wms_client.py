"""Integration Service — WMS TCP client."""

from __future__ import annotations

import asyncio
import json

import structlog

logger = structlog.get_logger()


async def add_package(
    wms_host: str,
    wms_port: int,
    *,
    order_id: str,
    package_details: dict,
) -> dict:
    """Send ADD_PACKAGE command to WMS via TCP."""
    details_json = json.dumps(package_details)
    command = f"ADD_PACKAGE|{order_id}|{details_json}"

    response = await _send_tcp_command(wms_host, wms_port, command)
    parts = response.split("|")

    if parts[0] == "ACK" and len(parts) >= 4:
        wms_ref = parts[3]
        logger.info("wms_package_added", order_id=order_id, wms_reference=wms_ref)
        return {"wms_reference": wms_ref, "status": parts[4] if len(parts) > 4 else "RECEIVED"}
    else:
        raise RuntimeError(f"WMS ADD_PACKAGE failed: {response}")


async def cancel_package(
    wms_host: str,
    wms_port: int,
    *,
    order_id: str,
) -> dict:
    """Send CANCEL_PACKAGE command to WMS (compensating action)."""
    command = f"CANCEL_PACKAGE|{order_id}"

    response = await _send_tcp_command(wms_host, wms_port, command)
    parts = response.split("|")

    if parts[0] == "ACK":
        logger.info("wms_package_cancelled", order_id=order_id)
        return {"status": "CANCELLED"}
    else:
        raise RuntimeError(f"WMS CANCEL_PACKAGE failed: {response}")


async def _send_tcp_command(host: str, port: int, command: str) -> str:
    """Open a TCP connection, send a command, read the response, and close."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write((command + "\n").encode("utf-8"))
        await writer.drain()

        data = await asyncio.wait_for(reader.readline(), timeout=10.0)
        return data.decode("utf-8").strip()
    finally:
        writer.close()
        await writer.wait_closed()
