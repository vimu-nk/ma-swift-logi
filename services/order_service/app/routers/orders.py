"""Order API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.order import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
)
from app.services import order_service as order_svc
from app.services.auto_assign import assign_driver
from app.services.rabbitmq import publish_order_created, publish_order_status

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Submit a new order — returns 202 and triggers async processing."""
    order = await order_svc.create_order(
        session,
        client_id=payload.client_id,
        pickup_address=payload.pickup_address,
        delivery_address=payload.delivery_address,
        package_details=payload.package_details,
    )

    # Publish event to RabbitMQ (triggers integration saga)
    await publish_order_created(
        order.id,
        {
            "client_id": payload.client_id,
            "pickup_address": payload.pickup_address,
            "delivery_address": payload.delivery_address,
            "package_details": payload.package_details,
        },
    )

    return OrderResponse.model_validate(order)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Get a single order by ID."""
    order = await order_svc.get_order(session, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )
    return OrderResponse.model_validate(order)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    client_id: str | None = Query(None),
    pickup_driver_id: str | None = Query(None),
    delivery_driver_id: str | None = Query(None),
    driver_id_any: str | None = Query(None),
    order_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> OrderListResponse:
    """List orders with optional filters."""
    orders, total = await order_svc.list_orders(
        session,
        client_id=client_id,
        pickup_driver_id=pickup_driver_id,
        delivery_driver_id=delivery_driver_id,
        driver_id_any=driver_id_any,
        status=order_status,
        limit=limit,
        offset=offset,
    )
    return OrderListResponse(
        orders=[OrderResponse.model_validate(o) for o in orders],
        total=total,
    )


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Update order status (e.g., driver marks as DELIVERED/FAILED)."""
    allowed = {
        "PICKING_UP", "PICKED_UP", "AT_WAREHOUSE", 
        "OUT_FOR_DELIVERY", "DELIVERY_ATTEMPTED",
        "DELIVERED", "FAILED"
    }
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status must be one of: {allowed}",
        )

    order = await order_svc.get_order(session, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )

    extra_fields = {}
    if payload.delivery_notes:
        extra_fields["delivery_notes"] = payload.delivery_notes
    if payload.proof_of_delivery:
        extra_fields["proof_of_delivery"] = payload.proof_of_delivery
    if payload.pickup_driver_id:
        extra_fields["pickup_driver_id"] = payload.pickup_driver_id
    if payload.delivery_driver_id:
        extra_fields["delivery_driver_id"] = payload.delivery_driver_id

    target_status = payload.status
    
    if target_status == "AT_WAREHOUSE":
        # System auto-assigns delivery driver but STAYS at AT_WAREHOUSE
        # Driver will manually transition to OUT_FOR_DELIVERY
        assigned_order = await assign_driver(session, order, "delivery")
        if assigned_order.delivery_driver_id:
            extra_fields["delivery_driver_id"] = assigned_order.delivery_driver_id
        
    elif target_status == "DELIVERY_ATTEMPTED":
        new_attempts = order.delivery_attempts + 1
        extra_fields["delivery_attempts"] = new_attempts
        if new_attempts < order.max_delivery_attempts:
            # Keep the same driver and allow them to retry later
            # Moving back to AT_WAREHOUSE means the driver has to start delivery again,
            # or it can just stay as DELIVERY_ATTEMPTED and they can attempt again.
            # Keeping it as DELIVERY_ATTEMPTED makes the most sense.
            pass
        else:
            target_status = "FAILED"

    updated_order = await order_svc.update_order_status(
        session,
        order_id=order_id,
        new_status=target_status,
        details=f"Driver update: {payload.status}",
        extra_fields=extra_fields if extra_fields else None,
    )

    if not updated_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )

    # Publish status change for notifications
    await publish_order_status(order_id, target_status)

    return OrderResponse.model_validate(updated_order)
