"""ASGI middleware for request-ID and correlation-ID propagation.

Injects ``X-Request-ID`` (per-request unique) and forwards
``X-Correlation-ID`` (cross-service tracing) into structlog context vars.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_CORRELATION_HEADER = "X-Correlation-ID"
_REQUEST_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Injects request/correlation IDs into each request and structlog context."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(_REQUEST_HEADER, str(uuid.uuid4()))
        correlation_id = request.headers.get(_CORRELATION_HEADER, str(uuid.uuid4()))

        # Bind to structlog context vars so every log line includes these IDs
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
        )

        response: Response = await call_next(request)

        response.headers[_REQUEST_HEADER] = request_id
        response.headers[_CORRELATION_HEADER] = correlation_id
        return response
