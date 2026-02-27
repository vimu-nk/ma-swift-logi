"""ROS Mock — REST/JSON endpoints simulating a Route Optimisation System."""

from fastapi import APIRouter
from pydantic import BaseModel
import uuid
import random
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/routes", tags=["ROS REST Mock"])

# ── In-memory store ──────────────────────────
_routes: dict[str, dict] = {}


# ── Schemas ──────────────────────────────────


class DeliveryPoint(BaseModel):
    order_id: str
    address: str
    priority: str = "normal"


class OptimizeRequest(BaseModel):
    delivery_points: list[DeliveryPoint]
    vehicle_id: str = "VH-001"
    depot_address: str = "SwiftLogistics Warehouse, Colombo 10"


class RouteStop(BaseModel):
    sequence: int
    order_id: str
    address: str
    eta: str
    distance_km: float


class OptimizeResponse(BaseModel):
    route_id: str
    vehicle_id: str
    total_distance_km: float
    estimated_duration_min: int
    stops: list[RouteStop]
    optimized_at: str


# ── Endpoints ────────────────────────────────


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_route(request: OptimizeRequest) -> OptimizeResponse:
    """Generate a mock-optimised route for the given delivery points."""
    route_id = f"RT-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    stops = []
    total_distance = 0.0
    for i, point in enumerate(request.delivery_points, start=1):
        dist = round(random.uniform(1.5, 15.0), 1)
        total_distance += dist
        eta = (now + timedelta(minutes=20 * i)).isoformat()
        stops.append(
            RouteStop(
                sequence=i,
                order_id=point.order_id,
                address=point.address,
                eta=eta,
                distance_km=dist,
            )
        )

    route = OptimizeResponse(
        route_id=route_id,
        vehicle_id=request.vehicle_id,
        total_distance_km=round(total_distance, 1),
        estimated_duration_min=20 * len(stops),
        stops=stops,
        optimized_at=now.isoformat(),
    )

    # Store for GET retrieval
    _routes[route_id] = route.model_dump()
    return route


@router.get("/{route_id}")
async def get_route(route_id: str) -> dict:
    """Retrieve a previously optimised route."""
    if route_id in _routes:
        return _routes[route_id]
    return {"error": "Route not found", "route_id": route_id}
