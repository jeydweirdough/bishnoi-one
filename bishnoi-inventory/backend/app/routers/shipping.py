"""Shipping with couriers (feature plan step 12, app/shipping.py).

    GET   /inventory/couriers                    the company's couriers
    POST  /inventory/couriers                    one of its own
    PATCH /inventory/couriers/{id}               name, tracking page, order, switched on or off
    PUT   /inventory/orders/{id}/shipping        how it goes, courier, tracking number, fee (until delivered)
    POST  /inventory/orders/{id}/delivered       delivered, with who received it and the courier's photo (optional)
    POST  /inventory/orders/{id}/failed          not delivered, with why
    POST  /inventory/orders/{id}/send-again      a failed delivery goes out again
    GET   /inventory/orders/{id}/delivery-photo  the courier's proof-of-delivery photo
"""

import base64
from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import Field
from sqlalchemy import func, select

from app import shipping
from app.access import CurrentAccess, allowed, settings_allowed
from app.api import Api, changed, conflict, field_error, found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Courier, Order

router = APIRouter(prefix="/inventory", tags=["shipping"])

# Couriers, warehouses and locations: changed by the company administrators (2026-10-31).
Manage = settings_allowed("warehouses.manage")
Issue = allowed("orders.issue")

PHOTO_TYPES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
MAX_PHOTO = 3_000_000


# --- couriers ----------------------------------------------------------------------------


class CourierIn(Api):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    tracking_url: str | None = Field(None, max_length=300)


class CourierPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    tracking_url: str | None = Field(None, max_length=300)
    sort_order: int | None = Field(None, ge=0, le=999)
    is_active: bool | None = None


def check_url(value: str | None) -> str | None:
    value = (value or "").strip() or None
    if value and not value.startswith(("https://", "http://")):
        raise field_error("trackingUrl", "Give the tracking page's address, starting with https://, with {number} where the tracking number goes.")
    return value


@router.get("/couriers")
def couriers(_: CurrentUser, db: DB) -> list[dict]:
    return [shipping.courier_out(c) for c in db.scalars(select(Courier).order_by(Courier.sort_order, func.lower(Courier.name)))]


@router.post("/couriers", status_code=status.HTTP_201_CREATED)
def add_courier(_: Manage, me: CurrentUser, db: DB, body: CourierIn) -> dict:
    code = body.code.strip().upper()
    if db.scalar(select(Courier.id).where(func.upper(Courier.code) == code)):
        raise field_error("code", "There's already a courier with that code.")
    last = db.scalar(select(func.max(Courier.sort_order))) or 0
    c = Courier(code=code, name=body.name.strip(), tracking_url=check_url(body.tracking_url), sort_order=last + 1)
    db.add(c)
    db.flush()
    audit(db, me, "courier.created", target=c.name, target_type="courier", target_id=c.id)
    db.commit()
    return shipping.courier_out(c)


@router.patch("/couriers/{courier_id}")
def change_courier(_: Manage, me: CurrentUser, db: DB, courier_id: str, body: CourierPatch) -> dict:
    c = found(db, Courier, courier_id, "courier")
    fields = changed(body)
    if "tracking_url" in fields:
        fields["tracking_url"] = check_url(fields["tracking_url"])
    fields = {k: v for k, v in fields.items() if (v is not None or k == "tracking_url") and getattr(c, k) != v}
    for k, v in fields.items():
        setattr(c, k, v.strip() if isinstance(v, str) else v)
    if fields:
        audit(db, me, "courier.updated", target=c.name, target_type="courier", target_id=c.id, fields=sorted(fields))
        db.commit()
    return shipping.courier_out(c)


# --- a delivery's shipping ---------------------------------------------------------------


class ShippingIn(Api):
    method: Literal["courier", "own", "pickup"]
    courier_id: str | None = Field(None, max_length=36)
    tracking_number: str | None = Field(None, max_length=60)
    # In centavos.
    fee: int = Field(0, ge=0, le=10**10)
    fee_charged: bool = False


def slug_of(request: Request) -> str | None:
    return getattr(request.state, "company", None)


def a_delivery(db: DB, order_id: str) -> Order:
    o = found(db, Order, order_id, "order")
    if o.kind != "sale":
        raise conflict("Only a customer's delivery is shipped; an issue to a department or project isn't.")
    return o


@router.put("/orders/{order_id}/shipping")
def set_shipping(access: CurrentAccess, me: CurrentUser, db: DB, order_id: str, body: ShippingIn, request: Request) -> dict:
    """How it goes: set while it's prepared, or when it's handed to the courier; not once delivered."""
    o = a_delivery(db, order_id)
    access.require("orders.issue" if o.status == "issued" else "orders.edit")
    if o.status == "cancelled" or o.delivery_status == "delivered":
        raise conflict(f"This delivery is already {'cancelled' if o.status == 'cancelled' else 'delivered'}.")
    courier = None
    if body.method == "courier" and body.courier_id:
        courier = found(db, Courier, body.courier_id, "courier")
        if not courier.is_active and courier.id != o.courier_id:
            raise field_error("courierId", f"{courier.name} is switched off. Pick another courier.")
    if body.method == "courier" and courier is None and o.status == "issued":
        raise field_error("courierId", "Pick the courier it went with.")
    before = (o.delivery_method, o.courier_id, o.tracking_number, o.shipping_fee, o.fee_charged)
    o.delivery_method = body.method
    o.courier_id = courier.id if courier else None
    o.courier = courier
    o.tracking_number = (body.tracking_number or "").strip() or None if body.method == "courier" else None
    o.shipping_fee, o.fee_charged = body.fee, body.fee_charged and body.fee > 0
    after = (o.delivery_method, o.courier_id, o.tracking_number, o.shipping_fee, o.fee_charged)
    if before != after:
        names = ("deliveryMethod", "courier", "trackingNumber", "shippingFee", "feeCharged")
        audit(db, me, "order.shipping_set", target=o.number, target_type="order", target_id=o.id,
              fields=[n for n, a, b in zip(names, before, after, strict=True) if a != b])
        if o.status == "issued":
            shipping.sales.shipment_changed(db, slug_of(request), o)
        db.commit()
    return shipping.shipping_out(o)


class DeliveredIn(Api):
    received_by: str = Field(min_length=2, max_length=120)
    # The courier's proof-of-delivery photo (PNG or JPEG as a data URL), when there is one.
    photo: str | None = Field(None, max_length=4_200_000)


def photo_of(value: str) -> tuple[bytes, str]:
    raw = value.split(",", 1)[1] if value.startswith("data:") else value
    try:
        image = base64.b64decode(raw, validate=True)
    except ValueError:
        raise field_error("photo", "That isn't an image.") from None
    if len(image) > MAX_PHOTO:
        raise field_error("photo", "The photo is too large: keep it under 3 MB.")
    kind = next((k for head, k in PHOTO_TYPES.items() if image.startswith(head)), None)
    if kind is None:
        raise field_error("photo", "The photo must be a PNG or JPEG image.")
    return image, kind


def out_now(o: Order) -> None:
    if o.status != "issued":
        raise conflict("Issue the delivery first: only what left the warehouse is delivered.")
    if o.delivery_status == "delivered":
        raise conflict("This delivery is already delivered.")


@router.post("/orders/{order_id}/delivered")
def mark_delivered(_: Issue, me: CurrentUser, db: DB, order_id: str, body: DeliveredIn, request: Request) -> dict:
    """Delivered, by the courier's word: who received it, and their proof-of-delivery photo when there is one.
    (When the customer signs on our screen, POST /orders/{id}/received records it as delivered.)"""
    o = a_delivery(db, order_id)
    out_now(o)
    if body.photo:
        o.received_photo, o.received_photo_type = photo_of(body.photo)
    o.received_by_name = o.received_by_name or body.received_by.strip()
    shipping.delivered(db, o, slug_of(request))
    audit(db, me, "order.delivered", target=o.number, target_type="order", target_id=o.id, fields=["receivedBy", *(["photo"] if body.photo else [])])
    db.commit()
    return shipping.shipping_out(o)


class FailedIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/orders/{order_id}/failed")
def mark_failed(_: Issue, me: CurrentUser, db: DB, order_id: str, body: FailedIn, request: Request) -> dict:
    """Not delivered (nobody there, refused, wrong address): why, for the customer and the reports."""
    o = a_delivery(db, order_id)
    out_now(o)
    if o.delivery_status == "failed":
        raise conflict("This delivery is already marked failed. Send it again, or mark it delivered.")
    shipping.failed(db, o, slug_of(request), body.reason.strip())
    audit(db, me, "order.delivery_failed", target=o.number, target_type="order", target_id=o.id, fields=["failedReason"])
    db.commit()
    return shipping.shipping_out(o)


class AgainIn(Api):
    tracking_number: str | None = Field(None, max_length=60)


@router.post("/orders/{order_id}/send-again")
def send_again(_: Issue, me: CurrentUser, db: DB, order_id: str, body: AgainIn, request: Request) -> dict:
    o = a_delivery(db, order_id)
    if o.delivery_status != "failed":
        raise conflict("Only a failed delivery is sent again.")
    if body.tracking_number and body.tracking_number.strip():
        o.tracking_number = body.tracking_number.strip()
    shipping.sent_again(db, o, slug_of(request))
    audit(db, me, "order.sent_again", target=o.number, target_type="order", target_id=o.id, fields=["attempts"])
    db.commit()
    return shipping.shipping_out(o)


@router.get("/orders/{order_id}/delivery-photo")
def delivery_photo(_: allowed("orders.view"), db: DB, order_id: str) -> Response:
    o = found(db, Order, order_id, "order")
    if not o.received_photo:
        raise conflict("This delivery has no photo.")
    return Response(o.received_photo, media_type=o.received_photo_type or "image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
