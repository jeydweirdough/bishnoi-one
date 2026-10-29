"""Shipping with couriers (feature plan step 12, 2026-10-29): a delivery goes by courier (LBC, J&T,
Lalamove…), our own delivery or customer pick-up; it carries the courier's tracking number and the
shipping fee (charged to the customer or not, for the invoice in step 13). Once issued it is out for
delivery, then delivered (the customer's signature on screen, or the courier's proof-of-delivery
photo) or failed (with why), and a failed one can go out again.

    issued ──▶ out ──▶ delivered
                │  ▲
                ▼  │ sent again
              failed

No own-fleet transport management; booking and tracking through the couriers' own systems come later
(decision 4). The sales order's CRM quote hears each change (sales_order.updated).
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app import documents, sales
from app.api import iso
from app.models import Courier, Order

METHOD_LABELS = {"courier": "Courier", "own": "Our delivery", "pickup": "Customer pick-up"}
STATE_LABELS = {"out": "Out for delivery", "delivered": "Delivered", "failed": "Failed delivery"}


def courier_out(c: Courier) -> dict:
    return {"id": c.id, "code": c.code, "name": c.name, "trackingUrl": c.tracking_url, "sortOrder": c.sort_order, "isActive": c.is_active}


def tracking_link(o: Order) -> str | None:
    if o.courier is None or not o.courier.tracking_url or not o.tracking_number:
        return None
    return o.courier.tracking_url.replace("{number}", o.tracking_number)


def on_time(o: Order) -> bool | None:
    """Delivered by the day it was promised (its scheduled date, else the date needed); None when nothing was promised."""
    promised = o.scheduled_on or o.needed_on
    day = o.delivered_on or (o.delivered_at.astimezone(documents.zone()).date() if o.delivered_at else None)
    if promised is None or day is None:
        return None
    return day <= promised


def shipping_out(o: Order) -> dict:
    return {
        "method": o.delivery_method,
        "methodLabel": METHOD_LABELS.get(o.delivery_method or "", None),
        "courier": {"id": o.courier.id, "name": o.courier.name} if o.courier else None,
        "trackingNumber": o.tracking_number,
        "trackingUrl": tracking_link(o),
        "fee": o.shipping_fee or 0,
        "feeCharged": bool(o.fee_charged),
        "status": o.delivery_status,
        "statusLabel": STATE_LABELS.get(o.delivery_status or "", None),
        "deliveredAt": iso(o.delivered_at),
        "onTime": on_time(o),
        "failedReason": o.failed_reason,
        "attempts": o.attempts or 0,
        "hasPhoto": o.received_photo_type is not None,
    }


def sent_out(o: Order) -> None:
    """Issued: a customer's delivery is on its way (an issue to a department or project isn't shipped)."""
    if o.kind == "sale":
        o.delivery_status, o.attempts = "out", max(1, o.attempts or 0)
        o.delivery_method = o.delivery_method or "courier"


def delivered(db: Session, o: Order, slug: str | None, when: datetime | None = None) -> None:
    o.delivery_status = "delivered"
    o.delivered_at = when or datetime.now(UTC)
    o.delivered_on = o.delivered_at.astimezone(documents.zone()).date()
    o.failed_reason = None
    sales.shipment_changed(db, slug, o)


def failed(db: Session, o: Order, slug: str | None, reason: str) -> None:
    o.delivery_status, o.failed_reason = "failed", reason
    sales.shipment_changed(db, slug, o)


def sent_again(db: Session, o: Order, slug: str | None) -> None:
    o.delivery_status, o.attempts = "out", (o.attempts or 1) + 1
    sales.shipment_changed(db, slug, o)
