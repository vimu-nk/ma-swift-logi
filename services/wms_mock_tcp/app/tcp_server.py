"""WMS Mock TCP — raw asyncio TCP server.

Simulates a warehouse management system that communicates via a
proprietary TCP-based protocol.

Protocol format:
  Request:  COMMAND|param1|param2|...
  Response: ACK|COMMAND|param1|RESULT  or  ERR|COMMAND|message

Supported commands:
  ADD_PACKAGE|<order_id>|<details_json>
  CANCEL_PACKAGE|<order_id>
  STATUS|<order_id>
"""

from __future__ import annotations

import asyncio
import json
import uuid

import structlog

log = structlog.get_logger()

# In-memory package store
_packages: dict[str, dict] = {}


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Handle a single TCP client connection."""
    addr = writer.get_extra_info("peername")
    log.info("tcp_client_connected", remote=str(addr))

    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break

            message = data.decode("utf-8", errors="replace").strip()
            log.info("tcp_message_received", message=message, remote=str(addr))

            response = _process_command(message)
            writer.write((response + "\n").encode("utf-8"))
            await writer.drain()
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("tcp_client_error", remote=str(addr))
    finally:
        writer.close()
        await writer.wait_closed()
        log.info("tcp_client_disconnected", remote=str(addr))


def _process_command(message: str) -> str:
    """Parse and execute a WMS protocol command."""
    parts = message.split("|")
    command = parts[0].upper() if parts else ""

    if command == "ADD_PACKAGE":
        return _handle_add_package(parts)
    elif command == "CANCEL_PACKAGE":
        return _handle_cancel_package(parts)
    elif command == "STATUS":
        return _handle_status(parts)
    else:
        return f"ERR|UNKNOWN|Unrecognised command: {command}"


def _handle_add_package(parts: list[str]) -> str:
    """ADD_PACKAGE|<order_id>|<details_json>"""
    if len(parts) < 2:
        return "ERR|ADD_PACKAGE|Missing order_id"

    order_id = parts[1]
    details = parts[2] if len(parts) > 2 else "{}"
    wms_ref = f"WMS-{uuid.uuid4().hex[:8].upper()}"

    try:
        details_parsed = json.loads(details)
    except json.JSONDecodeError:
        details_parsed = {"raw": details}

    _packages[order_id] = {
        "order_id": order_id,
        "wms_reference": wms_ref,
        "status": "RECEIVED",
        "details": details_parsed,
    }

    log.info("wms_package_added", order_id=order_id, wms_ref=wms_ref)
    return f"ACK|ADD_PACKAGE|{order_id}|{wms_ref}|RECEIVED"


def _handle_cancel_package(parts: list[str]) -> str:
    """CANCEL_PACKAGE|<order_id>"""
    if len(parts) < 2:
        return "ERR|CANCEL_PACKAGE|Missing order_id"

    order_id = parts[1]
    if order_id in _packages:
        _packages[order_id]["status"] = "CANCELLED"
        log.info("wms_package_cancelled", order_id=order_id)
        return f"ACK|CANCEL_PACKAGE|{order_id}|CANCELLED"
    else:
        return f"ERR|CANCEL_PACKAGE|{order_id}|Package not found"


def _handle_status(parts: list[str]) -> str:
    """STATUS|<order_id>"""
    if len(parts) < 2:
        return "ERR|STATUS|Missing order_id"

    order_id = parts[1]
    if order_id in _packages:
        pkg = _packages[order_id]
        return f"ACK|STATUS|{order_id}|{pkg['wms_reference']}|{pkg['status']}"
    else:
        return f"ERR|STATUS|{order_id}|Package not found"


async def start_tcp_server(host: str, port: int) -> asyncio.Server:
    """Start the TCP server and return the ``asyncio.Server`` handle."""
    server = await asyncio.start_server(handle_client, host, port)
    log.info("tcp_server_listening", host=host, port=port)
    return server
