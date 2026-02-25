"""WMS Mock TCP — main entry point.

Runs two concurrent servers:
  1. Raw asyncio TCP server on TCP_PORT (simulates WMS protocol)
  2. Tiny FastAPI HTTP server on HEALTH_PORT (health checks only)
"""

from __future__ import annotations

import asyncio
import os
import signal

import structlog
import uvicorn

from app.tcp_server import start_tcp_server
from app.health_app import health_app

from shared.logging import setup_logging

log = structlog.get_logger()

TCP_PORT = int(os.getenv("TCP_PORT", "9000"))
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "9001"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


async def main() -> None:
    """Launch TCP server and HTTP health sidecar concurrently."""
    setup_logging(
        log_level=LOG_LEVEL,
        json_logs=ENVIRONMENT.lower() == "production",
        service_name="wms_mock_tcp",
    )

    log.info("wms_mock_tcp starting", tcp_port=TCP_PORT, health_port=HEALTH_PORT)

    # TCP server
    tcp_server = await start_tcp_server("0.0.0.0", TCP_PORT)

    # HTTP health sidecar (uvicorn)
    config = uvicorn.Config(
        health_app,
        host="0.0.0.0",
        port=HEALTH_PORT,
        log_level=LOG_LEVEL.lower(),
    )
    http_server = uvicorn.Server(config)

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown(tcp_server, http_server)))
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler

    await http_server.serve()

    # If HTTP server exits, close TCP server
    tcp_server.close()
    await tcp_server.wait_closed()
    log.info("wms_mock_tcp shut down")


async def _shutdown(tcp_server: asyncio.Server, http_server: uvicorn.Server) -> None:
    log.info("wms_mock_tcp received shutdown signal")
    http_server.should_exit = True
    tcp_server.close()


if __name__ == "__main__":
    asyncio.run(main())
