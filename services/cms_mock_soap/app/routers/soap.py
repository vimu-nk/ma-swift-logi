"""CMS Mock — SOAP/XML endpoints simulating a legacy Client Management System."""

from fastapi import APIRouter, Request, Response
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/soap", tags=["CMS SOAP Mock"])

# ── Register Order (SOAP-style) ──────────────

REGISTER_RESPONSE_TPL = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:cms="http://swiftlogistics.lk/cms">
  <soap:Body>
    <cms:RegisterOrderResponse>
      <cms:Status>SUCCESS</cms:Status>
      <cms:CmsReference>{cms_ref}</cms:CmsReference>
      <cms:OrderId>{order_id}</cms:OrderId>
      <cms:Timestamp>{timestamp}</cms:Timestamp>
      <cms:Message>Order registered in CMS successfully.</cms:Message>
    </cms:RegisterOrderResponse>
  </soap:Body>
</soap:Envelope>"""

CANCEL_RESPONSE_TPL = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:cms="http://swiftlogistics.lk/cms">
  <soap:Body>
    <cms:CancelOrderResponse>
      <cms:Status>SUCCESS</cms:Status>
      <cms:OrderId>{order_id}</cms:OrderId>
      <cms:Timestamp>{timestamp}</cms:Timestamp>
      <cms:Message>Order cancelled in CMS successfully.</cms:Message>
    </cms:CancelOrderResponse>
  </soap:Body>
</soap:Envelope>"""

ERROR_RESPONSE_TPL = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:cms="http://swiftlogistics.lk/cms">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Client</faultcode>
      <faultstring>{message}</faultstring>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""


@router.post("/orders", response_class=Response)
async def register_order(request: Request) -> Response:
    """Accept SOAP XML order registration and return XML acknowledgement."""
    body = await request.body()
    body_str = body.decode("utf-8", errors="replace")

    # Extract order_id from XML body (simple parsing for mock)
    order_id = _extract_xml_value(body_str, "OrderId") or "unknown"

    cms_ref = f"CMS-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    xml_response = REGISTER_RESPONSE_TPL.format(
        cms_ref=cms_ref,
        order_id=order_id,
        timestamp=timestamp,
    )
    return Response(
        content=xml_response,
        media_type="application/xml",
        status_code=200,
    )


@router.post("/orders/cancel", response_class=Response)
async def cancel_order(request: Request) -> Response:
    """Accept SOAP XML order cancellation."""
    body = await request.body()
    body_str = body.decode("utf-8", errors="replace")

    order_id = _extract_xml_value(body_str, "OrderId") or "unknown"
    timestamp = datetime.now(timezone.utc).isoformat()

    xml_response = CANCEL_RESPONSE_TPL.format(
        order_id=order_id,
        timestamp=timestamp,
    )
    return Response(
        content=xml_response,
        media_type="application/xml",
        status_code=200,
    )


def _extract_xml_value(xml_str: str, tag: str) -> str | None:
    """Simple XML value extractor (no external dependency)."""
    import re

    # Match <ns:Tag>value</ns:Tag> or <Tag>value</Tag>
    pattern = rf"<(?:\w+:)?{tag}>(.*?)</(?:\w+:)?{tag}>"
    match = re.search(pattern, xml_str)
    return match.group(1) if match else None
