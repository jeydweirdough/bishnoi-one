"""Stock going out: customer orders, and issues to departments and projects.

    draft → confirmed (reserved) → picking (allocated) → issued → stock goes down
                    └──────────── cancelled (released) ┘

A customer's delivery, once issued, is shipped: out for delivery, then delivered or failed
(step 12, app/shipping.py and app/routers/shipping.py).

Confirming checks the stock is there and holds it, so nobody else can take
it. Issuing takes it out first expired, first out, unless a line names its
batch.
"""

import base64
import hashlib
import json
from datetime import UTC, date, datetime

from fastapi import APIRouter, Query, Request, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select

from app import business_events, documents, sales, shipping
from app.access import CurrentAccess, allowed
from app.api import Api, conflict, field_error, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import ORDER_KINDS, Order, OrderLine, Product, SalesOrder, Warehouse
from app.out import day, person, product_ref, warehouse_ref
from app.paging import Limit, Offset, cut, total
from app.signature_image import BadImage, checked_png
from app.stock import Ref, available, clean_serials, next_number, pick_out, post, serials_out

router = APIRouter(prefix="/inventory", tags=["orders"])

View = allowed("orders.view")


class OrderLineIn(Api):
    product_id: str = Field(max_length=36)
    quantity: int = Field(gt=0, le=10**9)
    unit_price: int | None = Field(None, ge=0, le=10**12)


class OrderIn(documents.HeaderIn):
    kind: str = "sale"
    recipient: str = Field(min_length=1, max_length=160)
    warehouse_id: str = Field(max_length=36)
    needed_on: date | None = None
    notes: str | None = Field(None, max_length=4000)
    lines: list[OrderLineIn] = Field(min_length=1, max_length=200)

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in ORDER_KINDS:
            raise ValueError("Pick what kind of order it is.")
        return v


class IssueLineIn(Api):
    line_id: str = Field(max_length=36)
    # Take it from this batch rather than first-expired-first-out.
    batch_id: str | None = Field(None, max_length=36)
    serials: list[str] = Field(default_factory=list, max_length=10000)


class IssueIn(Api):
    lines: list[IssueLineIn] = Field(default_factory=list, max_length=200)


def order_brief(o: Order) -> dict:
    return {
        "id": o.id,
        "number": o.number,
        "kind": o.kind,
        "recipient": o.recipient,
        "header": documents.header_out(o),
        "status": o.status,
        "warehouse": warehouse_ref(o.warehouse),
        "neededOn": day(o.needed_on),
        "lineCount": len(o.lines),
        "units": sum(line.quantity for line in o.lines),
        "total": sum(line.quantity * line.unit_price for line in o.lines),
        # Its lines, short, for a list row that opens in place (2026-10-25).
        "items": [{"sku": line.product.sku, "product": line.product.name, "quantity": line.quantity, "unitPrice": line.unit_price} for line in o.lines],
        "createdAt": iso(o.created_at),
        "confirmedAt": iso(o.confirmed_at),
        "issuedAt": iso(o.issued_at),
        # The wave it's picked in (step 14d).
        "waveId": o.wave_id,
        # How it goes and where it is (step 12): courier, tracking, fee; out for delivery, delivered or failed.
        "shipping": shipping.shipping_out(o) if o.kind == "sale" else None,
    }


def order_out(db: DB, o: Order) -> dict:
    open_ = o.status in ("draft", "confirmed", "picking")
    return {
        **order_brief(o),
        "notes": o.notes,
        "createdBy": person(o.created_by),
        "confirmedBy": person(o.confirmed_by),
        "issuedBy": person(o.issued_by),
        # Proof of delivery: who signed for it, and their signature (step 10).
        "received": {"name": o.received_by_name, "signedAt": iso(o.received_signed_at),
                     "signature": "data:image/png;base64," + base64.b64encode(o.received_signature).decode() if o.received_signature else None,
                     "fingerprint": o.received_fingerprint} if o.received_signed_at else None,
        "lines": [
            {
                "id": line.id,
                "product": product_ref(line.product),
                "quantity": line.quantity,
                "unitPrice": line.unit_price,
                "total": line.quantity * line.unit_price,
                # What's free to take, besides what this order already holds.
                "available": available(db, line.product_id, o.warehouse_id, exclude_order=o.id) if open_ else None,
                "picks": line.picks or [],
                "serials": line.serials or [],
            }
            for line in o.lines
        ],
    }


def check_order(db: DB, body: OrderIn) -> None:
    warehouse = db.get(Warehouse, body.warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise field_error("warehouseId", "Pick a warehouse that's switched on.")
    seen = set()
    for i, line in enumerate(body.lines):
        product = db.get(Product, line.product_id)
        if product is None or product.product_type == "service":
            raise field_error(f"lines.{i}.productId", "Pick a stocked product.")
        if product.status != "active":
            raise field_error(f"lines.{i}.productId", f"{product.name} is {product.status}.")
        if line.product_id in seen:
            raise field_error(f"lines.{i}.productId", f"{product.name} is on the order twice. Put it on one line.")
        seen.add(line.product_id)


def set_lines(db: DB, o: Order, body: OrderIn) -> None:
    o.lines = [
        OrderLine(position=i, product_id=line.product_id, quantity=line.quantity, unit_price=line.unit_price if line.unit_price is not None else db.get(Product, line.product_id).selling_price)
        for i, line in enumerate(body.lines)
    ]


def kinds_of(order_kind: str) -> tuple[str, ...]:
    """The operation types an order may have: a sale is a delivery; the rest are issues."""
    return ("delivery", "return") if order_kind == "sale" else ("issue", "delivery")


def ref(o: Order) -> Ref:
    return Ref("order", o.id, o.number)


@router.get("/orders")
def list_orders(
    _: View,
    db: DB,
    status_: str | None = Query(None, alias="status", max_length=60),
    kind: str | None = Query(None, max_length=16),
    warehouse: str | None = Query(None, max_length=36),
    q: str | None = Query(None, max_length=100),
    operation_type: str | None = Query(None, alias="operationType", max_length=36),
    timing: str | None = Query(None, max_length=10),
    delivery: str | None = Query(None, max_length=40, description="out, delivered, failed (comma-separated)"),
    courier: str | None = Query(None, max_length=36),
    limit: int | None = Limit(),
    offset: int = Offset(),
) -> list[dict] | dict:
    """Newest first. Without `limit`, the latest 500 (the board's columns)."""
    query = documents.narrow(select(Order).order_by(Order.created_at.desc()), Order, operation_type, timing)
    if delivery:
        query = query.where(Order.delivery_status.in_(delivery.split(",")))
    if courier:
        query = query.where(Order.courier_id == courier)
    if status_:
        query = query.where(Order.status.in_(status_.split(",")))
    if kind:
        query = query.where(Order.kind == kind)
    if warehouse:
        query = query.where(Order.warehouse_id == warehouse)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Order.number).like(like), func.lower(Order.recipient).like(like)))
    if limit is not None:
        return {"items": [order_brief(o) for o in db.scalars(cut(query.order_by(Order.id), limit, offset))], "total": total(db, query)}
    return [order_brief(o) for o in db.scalars(query.limit(500))]


@router.get("/order-figures")
def order_figures(_: View, db: DB, kind: str | None = Query(None, max_length=16)) -> dict:
    """The list's headline figures: orders still open, and the value issued this month and last (of this kind, when one is picked)."""
    from app.routers.purchasing import month_starts

    before, first, after = month_starts()
    base = select(Order)
    if kind:
        base = base.where(Order.kind == kind)
    open_ = len(db.scalars(base.where(Order.status.in_(("draft", "confirmed", "picking")))).all())

    def issued(start: datetime, end: datetime) -> int:
        rows = db.scalars(base.where(Order.status == "issued", Order.issued_at >= start, Order.issued_at < end)).all()
        return sum(line.quantity * line.unit_price for o in rows for line in o.lines)

    return {"openCount": open_, "issuedThisMonth": issued(first, after), "issuedLastMonth": issued(before, first)}


@router.get("/reservations")
def reservations(_: View, db: DB, warehouse: str | None = Query(None, max_length=36), limit: int | None = Limit(), offset: int = Offset()) -> list[dict] | dict:
    """Every unit held for an open order: reserved (confirmed) or allocated (being picked)."""
    query = select(OrderLine, Order).join(Order).where(Order.status.in_(("confirmed", "picking"))).order_by(Order.needed_on.is_(None), Order.needed_on, Order.number)
    if warehouse:
        query = query.where(Order.warehouse_id == warehouse)
    rows = db.execute(cut(query.order_by(OrderLine.position, OrderLine.id), limit, offset) if limit is not None else query)
    out = [
        {
            "order": {"id": o.id, "number": o.number, "status": o.status, "recipient": o.recipient, "neededOn": day(o.needed_on)},
            "warehouse": warehouse_ref(o.warehouse),
            "product": product_ref(line.product),
            "quantity": line.quantity,
            "state": "reserved" if o.status == "confirmed" else "allocated",
        }
        for line, o in rows
    ]
    return {"items": out, "total": total(db, query)} if limit is not None else out


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def create_order(_: allowed("orders.create"), me: CurrentUser, db: DB, body: OrderIn) -> dict:
    check_order(db, body)
    # A delivery (step 11: sales orders are the Sales app's own, SO-…): DR-…; an issue: IS-….
    o = Order(number=next_number(db, "DR" if body.kind == "sale" else "IS"), kind=body.kind, recipient=body.recipient, warehouse_id=body.warehouse_id, needed_on=body.needed_on, notes=body.notes, created_by_id=me.id)
    set_lines(db, o, body)
    # Its header (step 8): scheduled for the day it's needed, unless another is given.
    o.scheduled_on = body.needed_on
    documents.apply(db, o, kinds_of(o.kind), body, me, o.warehouse_id, new=True)
    db.add(o)
    db.flush()
    audit(db, me, "order.created", target=o.number, target_type="order", target_id=o.id)
    db.commit()
    return {"id": o.id, "number": o.number}


@router.get("/orders/{order_id}")
def read_order(_: View, db: DB, order_id: str) -> dict:
    return order_out(db, found(db, Order, order_id, "order"))


@router.put("/orders/{order_id}")
def update_order(_: allowed("orders.edit"), me: CurrentUser, db: DB, order_id: str, body: OrderIn) -> dict:
    o = found(db, Order, order_id, "order")
    if o.status != "draft":
        raise conflict("Only a draft can be changed. Cancel it and write it again, or issue it as it is.")
    check_order(db, body)
    o.kind, o.recipient, o.warehouse_id, o.needed_on, o.notes = body.kind, body.recipient, body.warehouse_id, body.needed_on, body.notes
    set_lines(db, o, body)
    if "scheduled_on" not in body.model_fields_set:
        o.scheduled_on = body.needed_on
    documents.apply(db, o, kinds_of(o.kind), body, me, o.warehouse_id, new=False)
    audit(db, me, "order.updated", target=o.number, target_type="order", target_id=o.id)
    db.commit()
    return {"id": o.id}


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(_: allowed("orders.edit"), me: CurrentUser, db: DB, order_id: str) -> Response:
    o = found(db, Order, order_id, "order")
    if o.status != "draft":
        raise conflict("Only a draft can be deleted. Cancel it instead.")
    audit(db, me, "order.deleted", target=o.number, target_type="order", target_id=o.id)
    db.delete(o)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/orders/{order_id}/confirm")
def confirm_order(_: allowed("orders.approve"), me: CurrentUser, db: DB, order_id: str) -> dict:
    """Holds the stock for this order. Refused if it isn't all there."""
    o = found(db, Order, order_id, "order")
    if o.status != "draft":
        raise conflict(f"This order is already {o.status}.")
    short = []
    for line in o.lines:
        free = available(db, line.product_id, o.warehouse_id, exclude_order=o.id)
        if free < line.quantity:
            short.append(f"{line.product.name}: {max(free, 0)} of {line.quantity}")
    if short:
        raise conflict(f"Not enough in {o.warehouse.name} to reserve: {'; '.join(short)}.")
    for line in o.lines:
        post(db, me, kind="reserve", product=line.product, quantity=-line.quantity, ref=ref(o), warehouse_id=o.warehouse_id, note=f"For {o.recipient}")
    o.status, o.confirmed_by_id, o.confirmed_at = "confirmed", me.id, datetime.now(UTC)
    audit(db, me, "order.confirmed", target=o.number, target_type="order", target_id=o.id)
    db.commit()
    return {"id": o.id, "status": o.status}


@router.post("/orders/{order_id}/pick")
def start_picking(access: CurrentAccess, me: CurrentUser, db: DB, order_id: str) -> dict:
    """The warehouse starts picking: reserved stock becomes allocated."""
    if not (access.can("orders.issue") or access.can("orders.approve")):
        access.require("orders.issue")
    o = found(db, Order, order_id, "order")
    if o.status != "confirmed":
        raise conflict("Only a confirmed order can be picked.")
    o.status = "picking"
    audit(db, me, "order.picking", target=o.number, target_type="order", target_id=o.id)
    db.commit()
    return {"id": o.id, "status": o.status}


@router.post("/orders/{order_id}/issue")
def issue_order(_: allowed("orders.issue"), me: CurrentUser, db: DB, order_id: str, body: IssueIn, request: Request) -> dict:
    """Takes the order's stock out: its hold is let go, and each line leaves
    first expired, first out (or from the batch it names)."""
    o = found(db, Order, order_id, "order")
    if o.status not in ("confirmed", "picking"):
        raise conflict("Confirm the order first, so its stock is held.")
    chosen = {line.line_id: line for line in body.lines}
    unknown = set(chosen) - {line.id for line in o.lines}
    if unknown:
        raise field_error("lines", "A line given isn't on this order.")
    for line in o.lines:
        post(db, me, kind="release", product=line.product, quantity=line.quantity, ref=ref(o), warehouse_id=o.warehouse_id, note="Issued")
    db.flush()
    for i, line in enumerate(o.lines):
        pick = chosen.get(line.id)
        serials = clean_serials(line.product, pick.serials if pick else [], line.quantity)
        serials_out(db, line.product, serials, o.warehouse_id, "issued")
        line.picks = pick_out(db, me, kind="issue", product=line.product, warehouse_id=o.warehouse_id, quantity=line.quantity, ref=ref(o), batch_id=pick.batch_id if pick else None, note=f"To {o.recipient}", serials=serials)
        line.serials = serials
    o.status, o.issued_by_id, o.issued_at = "issued", me.id, datetime.now(UTC)
    documents.done(o, o.issued_at)
    shipping.sent_out(o)
    audit(db, me, "order.issued", target=o.number, target_type="order", target_id=o.id)
    # Its sales order is delivered (step 11).
    sales.delivered(db, o, getattr(request.state, "company", None))
    # Told to the other apps (step 7): Finance makes the invoice from it in Stage 4.
    if o.kind == "sale":
        business_events.emit(db, getattr(request.state, "company", None), "delivery.done", {
            "orderId": o.id, "number": o.number, "salesOrderId": o.sales_order_id, "recipient": o.recipient, "warehouseId": o.warehouse_id, "issuedAt": o.issued_at.isoformat(),
            # Shipping (step 12): a fee charged to the customer is a line on the invoice (step 13).
            "shipping": {"method": o.delivery_method, "courier": o.courier.name if o.courier else None, "trackingNumber": o.tracking_number,
                         "fee": o.shipping_fee or 0, "feeCharged": bool(o.fee_charged)},
            # The sale it delivers, as sold, for Finance to invoice it (step 13).
            "salesOrder": sales.for_invoice(db.get(SalesOrder, o.sales_order_id)) if o.sales_order_id and db.get(SalesOrder, o.sales_order_id) else None,
            "lines": [{"sku": line.product.sku, "productId": line.product_id, "quantity": line.quantity, "unitPrice": line.unit_price, "picks": line.picks}
                      for line in o.lines]})
    db.commit()
    return {"id": o.id, "status": o.status}


class ReceivedIn(Api):
    name: str = Field(min_length=2, max_length=120)
    # Drawn by the customer on the device, cleaned in the browser: a PNG as a data URL.
    signature: str = Field(min_length=20, max_length=500_000)


def delivered_content(o: Order) -> dict:
    """What the customer's signature vouches for: the order, its lines, batches and serials as issued."""
    return {"number": o.number, "recipient": o.recipient, "issuedAt": iso(o.issued_at),
            "lines": [[line.product.sku, line.quantity, line.picks or [], line.serials or []] for line in o.lines]}


@router.post("/orders/{order_id}/received")
def sign_for_delivery(_: allowed("orders.issue"), me: CurrentUser, db: DB, order_id: str, body: ReceivedIn, request: Request) -> dict:
    """The customer signs for what they received (proof of delivery). Once signed, it stays as signed."""
    o = found(db, Order, order_id, "order")
    if o.status != "issued":
        raise conflict("Issue the order first: the customer signs for what left the warehouse.")
    if o.received_signed_at is not None:
        raise conflict(f"{o.received_by_name} already signed for this delivery.")
    try:
        image = checked_png(body.signature)
    except BadImage as e:
        raise field_error("signature", str(e)) from None
    content = json.dumps(delivered_content(o), sort_keys=True, separators=(",", ":"), default=str).encode()
    o.received_by_name, o.received_signature = body.name.strip(), image
    o.received_signed_at, o.received_fingerprint = datetime.now(UTC), hashlib.sha256(content).hexdigest()
    # Signed for: delivered (step 12).
    if o.kind == "sale" and o.delivery_status != "delivered":
        shipping.delivered(db, o, getattr(request.state, "company", None), o.received_signed_at)
    audit(db, me, "order.received", target=o.number, target_type="order", target_id=o.id, fields=["receivedByName", "signature"])
    db.commit()
    return {"id": o.id, "receivedBy": o.received_by_name, "signedAt": iso(o.received_signed_at)}


@router.post("/orders/{order_id}/cancel")
def cancel_order(access: CurrentAccess, me: CurrentUser, db: DB, order_id: str) -> dict:
    """Cancels it, letting go of whatever it held."""
    o = found(db, Order, order_id, "order")
    access.require("orders.edit" if o.status == "draft" else "orders.approve")
    if o.status in ("issued", "cancelled"):
        raise conflict(f"This order is already {o.status}.")
    if o.status in ("confirmed", "picking"):
        for line in o.lines:
            post(db, me, kind="release", product=line.product, quantity=line.quantity, ref=ref(o), warehouse_id=o.warehouse_id, note="Order cancelled")
    o.status = "cancelled"
    audit(db, me, "order.cancelled", target=o.number, target_type="order", target_id=o.id)
    db.commit()
    return {"id": o.id, "status": o.status}
