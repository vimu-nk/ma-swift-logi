"""Order SQLAlchemy models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class OrderStatus(str, enum.Enum):
    """Order lifecycle states."""

    PENDING = "PENDING"
    CMS_REGISTERED = "CMS_REGISTERED"
    WMS_RECEIVED = "WMS_RECEIVED"
    ROUTE_OPTIMIZED = "ROUTE_OPTIMIZED"
    READY = "READY"
    PICKUP_ASSIGNED = "PICKUP_ASSIGNED"
    PICKING_UP = "PICKING_UP"
    PICKED_UP = "PICKED_UP"
    AT_WAREHOUSE = "AT_WAREHOUSE"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERY_ATTEMPTED = "DELIVERY_ATTEMPTED"
    DELIVERY_FAILED = (
        "FAILED"  # Keeping enum value as FAILED for backward compatibility but conceptual failure
    )
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Order(Base):
    """Core order entity."""

    __tablename__ = "orders"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: str = Column(String(100), nullable=False, index=True)
    status: OrderStatus = Column(
        Enum(OrderStatus, name="order_status"),
        nullable=False,
        default=OrderStatus.PENDING,
    )

    # Addresses
    pickup_address: str = Column(Text, nullable=False)
    delivery_address: str = Column(Text, nullable=False)

    # Package details (flexible JSON)
    package_details: dict = Column(JSONB, nullable=False, default=dict)

    # External system references (populated by saga)
    cms_reference: str | None = Column(String(100), nullable=True)
    wms_reference: str | None = Column(String(100), nullable=True)
    route_id: str | None = Column(String(100), nullable=True)

    # Driver Assignment & Delivery info
    pickup_driver_id: str | None = Column(String(100), nullable=True)
    delivery_driver_id: str | None = Column(String(100), nullable=True)
    delivery_notes: str | None = Column(Text, nullable=True)
    proof_of_delivery: dict | None = Column(JSONB, nullable=True)

    # Retry logic
    delivery_attempts: int = Column(Integer, nullable=False, default=0)
    max_delivery_attempts: int = Column(Integer, nullable=False, default=3)

    # Timestamps
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    status_history = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.created_at",
    )

    __table_args__ = (
        Index("ix_orders_status", "status"),
        Index("ix_orders_created_at", "created_at"),
    )


class OrderStatusHistory(Base):
    """Audit trail for order status changes."""

    __tablename__ = "order_status_history"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: OrderStatus | None = Column(Enum(OrderStatus, name="order_status"), nullable=True)
    new_status: OrderStatus = Column(Enum(OrderStatus, name="order_status"), nullable=False)
    details: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    order = relationship("Order", back_populates="status_history")
