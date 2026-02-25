"""Order service — CRUD operations and event publishing."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderStatus, OrderStatusHistory

logger = structlog.get_logger()


async def create_order(
    session: AsyncSession,
    *,
    client_id: str,
    pickup_address: str,
    delivery_address: str,
    package_details: dict,
) -> Order:
    """Create a new order in PENDING status."""
    order = Order(
        id=uuid.uuid4(),
        client_id=client_id,
        status=OrderStatus.PENDING,
        pickup_address=pickup_address,
        delivery_address=delivery_address,
        package_details=package_details,
    )

    # Initial status history entry
    history = OrderStatusHistory(
        id=uuid.uuid4(),
        order_id=order.id,
        old_status=None,
        new_status=OrderStatus.PENDING,
        details="Order created",
    )

    session.add(order)
    session.add(history)
    await session.commit()
    await session.refresh(order, ["status_history"])

    logger.info("order_created", order_id=str(order.id), client_id=client_id)
    return order


async def update_order_status(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    new_status: str,
    details: str | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> Order | None:
    """Transition order to a new status with audit trail."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.status_history))
    )
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if order is None:
        return None

    old_status = order.status
    order.status = OrderStatus(new_status)

    # Apply extra fields (e.g., cms_reference, route_id)
    if extra_fields:
        for key, value in extra_fields.items():
            if hasattr(order, key):
                setattr(order, key, value)

    history = OrderStatusHistory(
        id=uuid.uuid4(),
        order_id=order.id,
        old_status=old_status,
        new_status=OrderStatus(new_status),
        details=details,
    )
    session.add(history)

    await session.commit()
    await session.refresh(order)

    logger.info(
        "order_status_updated",
        order_id=str(order_id),
        old_status=old_status.value,
        new_status=new_status,
    )
    return order


async def get_order(
    session: AsyncSession, order_id: uuid.UUID
) -> Order | None:
    """Fetch a single order with status history."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.status_history))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_orders(
    session: AsyncSession,
    *,
    client_id: str | None = None,
    pickup_driver_id: str | None = None,
    delivery_driver_id: str | None = None,
    driver_id_any: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Order], int]:
    """List orders with optional filters, returning (orders, total_count)."""
    base = select(Order).options(selectinload(Order.status_history))
    count_base = select(func.count(Order.id))

    if client_id:
        base = base.where(Order.client_id == client_id)
        count_base = count_base.where(Order.client_id == client_id)
    if pickup_driver_id:
        base = base.where(Order.pickup_driver_id == pickup_driver_id)
        count_base = count_base.where(Order.pickup_driver_id == pickup_driver_id)
    if delivery_driver_id:
        base = base.where(Order.delivery_driver_id == delivery_driver_id)
        count_base = count_base.where(Order.delivery_driver_id == delivery_driver_id)
    if driver_id_any:
        driver_condition = or_(
            Order.pickup_driver_id == driver_id_any,
            Order.delivery_driver_id == driver_id_any,
        )
        base = base.where(driver_condition)
        count_base = count_base.where(driver_condition)
    if status:
        base = base.where(Order.status == OrderStatus(status))
        count_base = count_base.where(Order.status == OrderStatus(status))

    base = base.order_by(Order.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(base)
    orders = list(result.scalars().all())

    count_result = await session.execute(count_base)
    total = count_result.scalar() or 0

    return orders, total
