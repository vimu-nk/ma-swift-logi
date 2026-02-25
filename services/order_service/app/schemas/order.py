"""Pydantic schemas for Order API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Request Schemas ───────────────────────────


class OrderCreate(BaseModel):
    """Payload for creating a new order."""

    client_id: str = Field(..., min_length=1, max_length=100)
    pickup_address: str = Field(..., min_length=1)
    delivery_address: str = Field(..., min_length=1)
    package_details: dict = Field(
        default_factory=dict,
        examples=[{"weight_kg": 2.5, "description": "Electronics"}],
    )


class OrderStatusUpdate(BaseModel):
    """Payload for driver status updates."""

    status: str = Field(..., description="New status")
    pickup_driver_id: str | None = None
    delivery_driver_id: str | None = None
    delivery_notes: str | None = None
    proof_of_delivery: dict | None = Field(
        default=None,
        examples=[{"type": "signature", "data": "base64..."}],
    )


# ── Response Schemas ──────────────────────────


class StatusHistoryItem(BaseModel):
    """Single entry in order status history."""

    old_status: str | None
    new_status: str
    details: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Full order detail response."""

    id: uuid.UUID
    client_id: str
    status: str
    pickup_address: str
    delivery_address: str
    package_details: dict
    cms_reference: str | None = None
    wms_reference: str | None = None
    route_id: str | None = None
    pickup_driver_id: str | None = None
    delivery_driver_id: str | None = None
    delivery_attempts: int = 0
    max_delivery_attempts: int = 3
    delivery_notes: str | None = None
    proof_of_delivery: dict | None = None
    created_at: datetime
    updated_at: datetime
    status_history: list[StatusHistoryItem] = []

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    """Paginated order list."""

    orders: list[OrderResponse]
    total: int
