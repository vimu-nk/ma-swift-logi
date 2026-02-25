"""Order Service — Auto-assignment logic."""

from __future__ import annotations

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.order import Order, OrderStatus

logger = structlog.get_logger()


async def get_drivers_list() -> list[str]:
    """Get the list of active driver usernames from config."""
    drivers_str = settings.driver_usernames
    return [d.strip() for d in drivers_str.split(",") if d.strip()]


async def assign_driver(
    session: AsyncSession,
    order: Order,
    driver_type: str,
) -> Order:
    """Assign a driver to an order based on round-robin (fewest active assignments)."""
    driver_usernames = await get_drivers_list()

    if not driver_usernames:
        logger.warning(f"no_drivers_available_for_{driver_type}_assignment")
        return order

    # Find the driver with the fewest active assignments for the given phase
    # For pickup phase, count active pickup orders
    # For delivery phase, count active delivery orders
    
    driver_counts = {d: 0 for d in driver_usernames}
    
    if driver_type == "pickup":
        active_statuses = [
            OrderStatus.PICKUP_ASSIGNED,
            OrderStatus.PICKING_UP,
            OrderStatus.PICKED_UP,
        ]
        stmt = (
            select(Order.pickup_driver_id, func.count(Order.id))
            .where(Order.status.in_(active_statuses))
            .where(Order.pickup_driver_id.in_(driver_usernames))
            .group_by(Order.pickup_driver_id)
        )
    else:  # delivery
        active_statuses = [
            OrderStatus.OUT_FOR_DELIVERY,
            OrderStatus.DELIVERY_ATTEMPTED,
        ]
        stmt = (
            select(Order.delivery_driver_id, func.count(Order.id))
            .where(Order.status.in_(active_statuses))
            .where(Order.delivery_driver_id.in_(driver_usernames))
            .group_by(Order.delivery_driver_id)
        )

    result = await session.execute(stmt)
    counts = result.all()
    
    for driver_id, count in counts:
        if driver_id in driver_counts:
            driver_counts[driver_id] = count

    # Driver with the minimum assignments
    selected_driver = min(driver_counts.items(), key=lambda x: x[1])[0]

    if driver_type == "pickup":
        order.pickup_driver_id = selected_driver
    else:
        order.delivery_driver_id = selected_driver

    logger.info(
        f"auto_assigned_{driver_type}_driver",
        order_id=str(order.id),
        driver_id=selected_driver,
        current_load=driver_counts[selected_driver],
    )
    
    return order
