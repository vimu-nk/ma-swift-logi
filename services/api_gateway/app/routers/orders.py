"""API Gateway — Order proxy routes (forwards to order_service)."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.auth import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/api/orders", tags=["Orders (Gateway)"])
logger = structlog.get_logger()


async def _proxy(method: str, path: str, **kwargs: Any) -> dict:
    """Forward a request to the order_service."""
    url = f"{settings.order_service_url}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, **kwargs)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else response.text,
        )
    return response.json()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_order(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    """Create order — proxied to order_service (auth required)."""
    body = await request.json()
    # Auto-fill client_id from JWT if not provided
    if "client_id" not in body:
        body["client_id"] = user["username"]

    logger.info("gateway_create_order", user=user["username"], client_id=body.get("client_id"))
    return await _proxy("POST", "/api/orders", json=body)


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Get order by ID — proxied (auth required)."""
    return await _proxy("GET", f"/api/orders/{order_id}")


@router.get("")
async def list_orders(
    client_id: str | None = Query(None),
    driver_id: str | None = Query(None),
    driver_id_any: str | None = Query(None),
    order_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
) -> dict:
    """List orders — proxied (auth required). Clients see only their own orders."""
    # Clients can only see their own orders
    if user["role"] == "client":
        client_id = user["username"]
    if user["role"] == "driver":
        driver_id_any = user["username"]

    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if client_id:
        params["client_id"] = client_id
    if driver_id:
        params["driver_id"] = driver_id
    if driver_id_any:
        params["driver_id_any"] = driver_id_any
    if order_status:
        params["status"] = order_status

    return await _proxy("GET", "/api/orders", params=params)


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    """Update order status — proxied (drivers only)."""
    if user["role"] not in ("driver", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can update order status",
        )

    body = await request.json()
    return await _proxy("PATCH", f"/api/orders/{order_id}/status", json=body)
