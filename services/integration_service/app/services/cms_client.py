"""Integration Service — CMS SOAP client."""

from __future__ import annotations

import structlog
import httpx

logger = structlog.get_logger()

REGISTER_XML_TPL = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:cms="http://swiftlogistics.lk/cms">
  <soap:Body>
    <cms:RegisterOrderRequest>
      <cms:OrderId>{order_id}</cms:OrderId>
      <cms:ClientId>{client_id}</cms:ClientId>
      <cms:PickupAddress>{pickup_address}</cms:PickupAddress>
      <cms:DeliveryAddress>{delivery_address}</cms:DeliveryAddress>
    </cms:RegisterOrderRequest>
  </soap:Body>
</soap:Envelope>"""

CANCEL_XML_TPL = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:cms="http://swiftlogistics.lk/cms">
  <soap:Body>
    <cms:CancelOrderRequest>
      <cms:OrderId>{order_id}</cms:OrderId>
    </cms:CancelOrderRequest>
  </soap:Body>
</soap:Envelope>"""


async def register_order(
    http_client: httpx.AsyncClient,
    cms_url: str,
    *,
    order_id: str,
    client_id: str,
    pickup_address: str,
    delivery_address: str,
) -> dict:
    """Register an order in CMS via SOAP XML."""
    xml_body = REGISTER_XML_TPL.format(
        order_id=order_id,
        client_id=client_id,
        pickup_address=pickup_address,
        delivery_address=delivery_address,
    )

    response = await http_client.post(
        f"{cms_url}/soap/orders",
        content=xml_body,
        headers={"Content-Type": "application/xml"},
    )
    response.raise_for_status()

    # Extract CMS reference from XML response
    import re

    body = response.text
    cms_ref_match = re.search(r"<(?:\w+:)?CmsReference>(.*?)</(?:\w+:)?CmsReference>", body)
    cms_ref = cms_ref_match.group(1) if cms_ref_match else "UNKNOWN"

    logger.info("cms_order_registered", order_id=order_id, cms_ref=cms_ref)
    return {"cms_reference": cms_ref, "status": "SUCCESS"}


async def cancel_order(
    http_client: httpx.AsyncClient,
    cms_url: str,
    *,
    order_id: str,
) -> dict:
    """Cancel an order in CMS (compensating action)."""
    xml_body = CANCEL_XML_TPL.format(order_id=order_id)

    response = await http_client.post(
        f"{cms_url}/soap/orders/cancel",
        content=xml_body,
        headers={"Content-Type": "application/xml"},
    )
    response.raise_for_status()

    logger.info("cms_order_cancelled", order_id=order_id)
    return {"status": "CANCELLED"}
