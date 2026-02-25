"""Integration Service — Saga Orchestrator.

Implements the distributed transaction for order processing:
  1. Register order in CMS (SOAP)
  2. Add package to WMS (TCP)
  3. Request route optimisation from ROS (REST)

If any step fails, compensating actions undo the previous steps.

**Idempotency**: Before executing each step the saga fetches the current
order status from the order_service.  If a step has already completed
(e.g. on a message redeliver) it is skipped, preventing duplicate calls
to CMS / WMS / ROS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.services import cms_client, ros_client, wms_client

logger = structlog.get_logger()

# Status progression — index determines "how far" the saga has gone.
_STATUS_ORDER: list[str] = [
    "PENDING",
    "CMS_REGISTERED",
    "WMS_RECEIVED",
    "ROUTE_OPTIMIZED",
    "READY",
]


@dataclass
class SagaResult:
    """Result of the saga execution."""

    success: bool
    order_id: str
    cms_reference: str | None = None
    wms_reference: str | None = None
    route_id: str | None = None
    error: str | None = None
    completed_steps: list[str] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)


# ── Helpers ─────────────────────────────────────────────


async def _fetch_order_status(
    http_client: httpx.AsyncClient,
    order_service_url: str,
    order_id: str,
) -> str | None:
    """Fetch the current order status from order_service.

    Returns the status string, or None if the order cannot be found.
    """
    try:
        resp = await http_client.get(
            f"{order_service_url}/api/orders/{order_id}",
        )
        if resp.status_code == 200:
            return resp.json().get("status")
        logger.warning(
            "saga_status_fetch_failed",
            order_id=order_id,
            status_code=resp.status_code,
        )
    except Exception as exc:
        logger.warning(
            "saga_status_fetch_error",
            order_id=order_id,
            error=str(exc),
        )
    return None


def _step_already_done(current_status: str | None, step_status: str) -> bool:
    """Return True if the order has already progressed past *step_status*."""
    if current_status is None:
        return False
    try:
        current_idx = _STATUS_ORDER.index(current_status)
        step_idx = _STATUS_ORDER.index(step_status)
        return current_idx >= step_idx
    except ValueError:
        # Unknown status (e.g. FAILED) — don't skip
        return False


# ── Saga ────────────────────────────────────────────────


async def execute_order_saga(
    http_client: httpx.AsyncClient,
    *,
    cms_url: str,
    ros_url: str,
    wms_host: str,
    wms_port: int,
    order_service_url: str,
    order_id: str,
    client_id: str,
    pickup_address: str,
    delivery_address: str,
    package_details: dict[str, Any],
) -> SagaResult:
    """
    Execute the 3-step order saga with compensating actions.

    Idempotent: each step checks the current order status and skips
    if the step was already completed on a previous attempt.

    Steps: CMS Register → WMS Add Package → ROS Optimize Route
    Compensation: If step N fails, undo steps N-1, N-2, ...
    """
    result = SagaResult(success=False, order_id=order_id)

    # ── Fetch current order status for idempotency ───────
    current_status = await _fetch_order_status(
        http_client, order_service_url, order_id,
    )
    logger.info(
        "saga_idempotency_check",
        order_id=order_id,
        current_status=current_status,
    )

    # ── Step 1: Register order in CMS (SOAP) ────────────
    if _step_already_done(current_status, "CMS_REGISTERED"):
        logger.info("saga_step_1_skipped", order_id=order_id, reason="already CMS_REGISTERED")
        result.skipped_steps.append("CMS_REGISTERED")
        result.completed_steps.append("CMS_REGISTERED")
    else:
        try:
            logger.info("saga_step_1_cms", order_id=order_id)
            cms_result = await cms_client.register_order(
                http_client, cms_url,
                order_id=order_id,
                client_id=client_id,
                pickup_address=pickup_address,
                delivery_address=delivery_address,
            )
            result.cms_reference = cms_result["cms_reference"]
            result.completed_steps.append("CMS_REGISTERED")
            logger.info("saga_step_1_complete", order_id=order_id, cms_ref=result.cms_reference)
        except Exception as e:
            result.error = f"CMS registration failed: {e}"
            logger.error("saga_step_1_failed", order_id=order_id, error=str(e))
            return result

    # ── Step 2: Add package to WMS (TCP) ─────────────────
    if _step_already_done(current_status, "WMS_RECEIVED"):
        logger.info("saga_step_2_skipped", order_id=order_id, reason="already WMS_RECEIVED")
        result.skipped_steps.append("WMS_RECEIVED")
        result.completed_steps.append("WMS_RECEIVED")
    else:
        try:
            logger.info("saga_step_2_wms", order_id=order_id)
            wms_result = await wms_client.add_package(
                wms_host, wms_port,
                order_id=order_id,
                package_details=package_details,
            )
            result.wms_reference = wms_result["wms_reference"]
            result.completed_steps.append("WMS_RECEIVED")
            logger.info("saga_step_2_complete", order_id=order_id, wms_ref=result.wms_reference)
        except Exception as e:
            result.error = f"WMS add package failed: {e}"
            logger.error("saga_step_2_failed", order_id=order_id, error=str(e))

            # Compensate: cancel CMS registration
            await _compensate_cms(http_client, cms_url, order_id)
            return result

    # ── Step 3: Optimise route via ROS (REST) ────────────
    if _step_already_done(current_status, "ROUTE_OPTIMIZED"):
        logger.info("saga_step_3_skipped", order_id=order_id, reason="already ROUTE_OPTIMIZED")
        result.skipped_steps.append("ROUTE_OPTIMIZED")
        result.completed_steps.append("ROUTE_OPTIMIZED")
    else:
        try:
            logger.info("saga_step_3_ros", order_id=order_id)
            ros_result = await ros_client.optimize_route(
                http_client, ros_url,
                order_id=order_id,
                delivery_address=delivery_address,
            )
            result.route_id = ros_result.get("route_id")
            result.completed_steps.append("ROUTE_OPTIMIZED")
            logger.info("saga_step_3_complete", order_id=order_id, route_id=result.route_id)
        except Exception as e:
            result.error = f"ROS route optimisation failed: {e}"
            logger.error("saga_step_3_failed", order_id=order_id, error=str(e))

            # Compensate: cancel WMS + CMS
            await _compensate_wms(wms_host, wms_port, order_id)
            await _compensate_cms(http_client, cms_url, order_id)
            return result

    # All steps succeeded (or were already done)
    result.success = True
    logger.info(
        "saga_completed",
        order_id=order_id,
        steps=result.completed_steps,
        skipped=result.skipped_steps,
    )
    return result


async def _compensate_cms(
    http_client: httpx.AsyncClient, cms_url: str, order_id: str
) -> None:
    """Compensating action: cancel CMS registration."""
    try:
        await cms_client.cancel_order(http_client, cms_url, order_id=order_id)
        logger.info("saga_compensation_cms", order_id=order_id)
    except Exception as comp_err:
        logger.error("saga_compensation_cms_failed", order_id=order_id, error=str(comp_err))


async def _compensate_wms(wms_host: str, wms_port: int, order_id: str) -> None:
    """Compensating action: cancel WMS package."""
    try:
        await wms_client.cancel_package(wms_host, wms_port, order_id=order_id)
        logger.info("saga_compensation_wms", order_id=order_id)
    except Exception as comp_err:
        logger.error("saga_compensation_wms_failed", order_id=order_id, error=str(comp_err))
