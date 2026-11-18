"""The Sales app's sales orders (feature plan step 11; app/sales.py says how one moves).

    GET  /inventory/sales-orders                 newest first; status, q, paging
    GET  /inventory/sales-orders/{id}            one, with its lines and its deliveries
    POST /inventory/sales-orders                 typed here: a draft at the price list's prices
    PUT  /inventory/sales-orders/{id}            a draft changed
    POST /inventory/sales-orders/{id}/submit     the draft goes for approval: on its approval slip (Step 4C)
    POST /inventory/sales-orders/{id}/approve    confirmed, and its delivery made (sales.approve); while connected to
                                                 Bishnoi One, only an administrator (the slip is withdrawn); others
                                                 sign the slip, whose end comes back as approval.decided
    POST /inventory/sales-orders/{id}/reject     back to the rep, with the reason (sales.approve; the same rule)
    POST /inventory/sales-orders/{id}/cancel     while nothing has left the warehouse
"""

from datetime import date

from fastapi import APIRouter, Query, Request
from pydantic import Field
from sqlalchemy import func, or_, select

from modules.inventory import shipping, sales
from modules.inventory.access import allowed
from modules.inventory.api import Api, conflict, field_error, found, iso
from modules.inventory.audit import audit
from modules.inventory.deps import DB, CurrentUser
from modules.inventory.models import Order, Packaging, Product, PurchaseOrder, SalesOrder, SalesOrderLine, Warehouse
from modules.inventory.packs import pack_price, plural, sold_as
from modules.inventory.out import person, product_ref, warehouse_ref
from modules.inventory.paging import Limit, Offset, cut, total
from modules.inventory.stock import next_number

router = APIRouter(prefix="/inventory", tags=["sales"])

View = allowed("sales.view")
STATUS_LABELS = sales.STATUS_LABELS


def company_of(request: Request) -> str | None:
    return getattr(request.state, "company", None)


def brief(o: SalesOrder) -> dict:
    return {
        "id": o.id, "number": o.number, "status": o.status, "statusLabel": sales.status_label(o),
        # Once invoiced, the invoice's state and total (Step 4D): the invoice is the order's source of truth.
        "invoiceState": o.invoice_state, "amountsFrom": sales.figures(o)["source"],
        "customer": {"id": o.customer_id, "name": o.customer_name, "address": o.customer_address, "tin": o.customer_tin},
        "quote": {"id": o.quote_id, "number": o.quote_number} if o.quote_id else None,
        "salesperson": {"id": o.salesperson_id, "name": o.salesperson_name} if o.salesperson_name else None,
        "division": o.division_name, "team": o.team_name,
        "warehouse": warehouse_ref(o.warehouse), "scheduledOn": o.scheduled_on.isoformat() if o.scheduled_on else None,
        "totalCentavos": sales.value_of(o), "currency": o.currency, "units": sum(line.quantity for line in o.lines),
        "createdAt": iso(o.created_at), "createdBy": o.created_by_name,
    }


def out(db: DB, o: SalesOrder) -> dict:
    deliveries = db.scalars(select(Order).where(Order.sales_order_id == o.id).order_by(Order.created_at)).all()
    return {
        **brief(o),
        "payer": o.payer, "notes": o.notes, "tax": o.tax,
        "grossCentavos": (shown := sales.figures(o))["grossCentavos"], "discountCentavos": shown["discountCentavos"], "taxCentavos": shown["taxCentavos"],
        # The order's own amounts, as ordered: the invoice's take their place once invoiced.
        "ordered": {"grossCentavos": o.gross_centavos, "discountCentavos": o.discount_centavos, "totalCentavos": o.total_centavos},
        "decidedBy": person(o.decided_by), "decidedAt": iso(o.decided_at), "decisionNote": o.decision_note, "deliveredAt": iso(o.delivered_at),
        "lines": [{"id": line.id, "product": product_ref(line.product), "quantity": line.quantity, "freeQuantity": line.free_quantity,
                   "unitPrice": line.unit_price, "discount": line.discount, "total": line.total, "delivered": line.delivered,
                   "unit": line_unit(line)} for line in o.lines],
        "purchaseOrders": purchase_orders_of(db, o),
        "deliveries": [{"id": d.id, "number": d.number, "status": d.status, "issuedAt": iso(d.issued_at), "shipping": shipping.shipping_out(d)} for d in deliveries],
        # Invoiced from its delivery, and paid (step 13).
        "invoice": {**sales.invoice_out(o), "invoicedAt": iso(o.invoiced_at), "paidAt": iso(o.paid_at), "total": o.invoice_total} if o.invoice_id else None,
    }


@router.get("/sales-orders")
def list_orders(_: View, db: DB, status_: str | None = Query(None, alias="status", max_length=80), q: str | None = Query(None, max_length=100),
                limit: int | None = Limit(), offset: int = Offset()) -> list[dict] | dict:
    """Newest first. Without `limit`, the latest 500 (the board's columns)."""
    query = select(SalesOrder).order_by(SalesOrder.created_at.desc())
    if status_:
        query = query.where(SalesOrder.status.in_(status_.split(",")))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(SalesOrder.number).like(like), func.lower(SalesOrder.customer_name).like(like), func.lower(SalesOrder.quote_number).like(like)))
    if limit is not None:
        return {"items": [brief(o) for o in db.scalars(cut(query.order_by(SalesOrder.id), limit, offset))], "total": total(db, query)}
    return [brief(o) for o in db.scalars(query.limit(500))]


@router.get("/sales-orders/{order_id}")
def read_order(_: View, db: DB, order_id: str) -> dict:
    return out(db, found(db, SalesOrder, order_id, "sales order"))


class LineIn(Api):
    product_id: str = Field(max_length=36)
    # Always in the base unit; with a pack (step 4A), a whole number of that pack.
    quantity: int = Field(gt=0, le=10**9)
    packaging_id: str | None = Field(None, max_length=36)


class OrderIn(Api):
    customer_name: str = Field(min_length=1, max_length=200)
    customer_id: str | None = Field(None, max_length=36)
    customer_address: str | None = Field(None, max_length=400)
    customer_tin: str | None = Field(None, max_length=30)
    warehouse_id: str | None = Field(None, max_length=36)
    scheduled_on: date | None = None
    notes: str | None = Field(None, max_length=4000)
    lines: list[LineIn] = Field(min_length=1, max_length=200)


def fill(db: DB, o: SalesOrder, body: OrderIn) -> None:
    """A typed order, at the price list's prices: nobody types a price (decided 2026-10-29)."""
    warehouse = db.get(Warehouse, body.warehouse_id) if body.warehouse_id else sales.default_warehouse(db)
    if warehouse is None or not warehouse.is_active:
        raise field_error("warehouseId", "Pick a warehouse that's switched on.")
    o.customer_name, o.customer_id = body.customer_name.strip(), body.customer_id
    o.customer_address, o.customer_tin = body.customer_address, body.customer_tin
    o.warehouse_id, o.scheduled_on, o.notes = warehouse.id, body.scheduled_on, body.notes
    o.lines.clear()
    for i, line in enumerate(body.lines):
        product = db.get(Product, line.product_id)
        if product is None or product.status != "active" or product.product_type == "service":
            raise field_error(f"lines.{i}.productId", "Pick a stocked product that's on sale.")
        o.lines.append(sold_line(db, i, product, line))
    sales.totals(o)


def sold_line(db: DB, i: int, product: Product, line: LineIn) -> SalesOrderLine:
    """A typed line in the unit chosen (step 4A): the base unit, or one of the item's packs that may be sold, at
    that pack's price when it has one. The quantity and price stay per base unit."""
    if not line.packaging_id:
        if not product.base_sellable:
            raise field_error(f"lines.{i}.packagingId", f"{product.name} isn't sold by the {product.unit.name}: pick one of its packs.")
        return SalesOrderLine(position=i, product_id=product.id, quantity=line.quantity, unit_price=product.selling_price,
                              total=product.selling_price * line.quantity)
    pack = db.get(Packaging, line.packaging_id)
    if pack is None or pack.product_id != product.id:
        raise field_error(f"lines.{i}.packagingId", f"That pack isn't one of {product.name}'s.")
    if not pack.sellable:
        raise field_error(f"lines.{i}.packagingId", f"{product.name} isn't sold by the {pack.name}.")
    if line.quantity % pack.quantity:
        raise field_error(f"lines.{i}.quantity", f"Sell whole {plural(pack.name, 2)} of {pack.quantity:,}.")
    each = pack_price(product, pack) // pack.quantity
    return SalesOrderLine(position=i, product_id=product.id, quantity=line.quantity, unit_price=each, total=each * line.quantity,
                          packaging_id=pack.id, unit_name=pack.name, per=pack.quantity)


def line_unit(line: SalesOrderLine) -> dict:
    """The unit a line was sold in: a pack ("Box", per 10) or the base unit."""
    return {"packagingId": line.packaging_id, "name": line.unit_name or line.product.unit.name, "per": line.per or 1,
            "soldAs": sold_as(line.quantity, line.unit_name, line.per)}


@router.post("/sales-orders", status_code=201)
def create_order(_: allowed("sales.create"), me: CurrentUser, db: DB, body: OrderIn) -> dict:
    o = SalesOrder(number=next_number(db, "SO"), status="draft", created_by_id=me.id, created_by_name=me.full_name, warehouse_id="")
    fill(db, o, body)
    db.add(o)
    db.flush()
    audit(db, me, "sales_order.created", target=o.number, target_type="sales_order", target_id=o.id)
    db.commit()
    return {"id": o.id, "number": o.number}


@router.put("/sales-orders/{order_id}")
def update_order(_: allowed("sales.edit"), me: CurrentUser, db: DB, order_id: str, body: OrderIn) -> dict:
    o = found(db, SalesOrder, order_id, "sales order")
    if (why := sales.invoiced_message(o)) is not None:
        raise conflict(why)
    if o.status not in ("draft", "rejected") or o.quote_id:
        raise conflict("Only a draft typed here can be changed; an order from a quote changes in the CRM, as a new quote.")
    fill(db, o, body)
    o.status = "draft"
    audit(db, me, "sales_order.updated", target=o.number, target_type="sales_order", target_id=o.id)
    db.commit()
    return {"id": o.id}


@router.post("/sales-orders/{order_id}/submit")
def submit_order(_: allowed("sales.create"), me: CurrentUser, db: DB, order_id: str, request: Request) -> dict:
    o = found(db, SalesOrder, order_id, "sales order")
    if o.status not in ("draft", "rejected"):
        raise conflict("Only a draft goes for approval.")
    o.status, o.decision_note = "pending", None
    # On its approval slip (Step 4C): signed up the chart on the Platform, which tells us the end.
    sales.ask_for_approval(db, company_of(request), o, sales.requester_of(me))
    audit(db, me, "sales_order.submitted", target=o.number, target_type="sales_order", target_id=o.id)
    db.commit()
    return {"id": o.id, "status": o.status}


def on_slip(request: Request) -> bool:
    """Connected to Bishnoi One: orders are approved on their approval slip (Step 4C), not here."""
    return bool(getattr(request.app.state.settings, "platform_api_url", None))


def decided_here(request: Request, db: DB, me, o: SalesOrder, what: str) -> None:
    """While connected, only an administrator decides an order here, and its waiting slip is withdrawn."""
    if not on_slip(request):
        return
    if not me.role.is_system:
        raise conflict(f"This order is {what} on its approval slip: open Approvals, or the slip on this order.")
    sales.withdraw_approval(db, company_of(request), o, f"Decided in Inventory by {me.full_name} (administrator).", me.email)


@router.post("/sales-orders/{order_id}/approve")
def approve_order(_: allowed("sales.approve"), me: CurrentUser, db: DB, order_id: str, request: Request) -> dict:
    o = found(db, SalesOrder, order_id, "sales order")
    if o.status != "pending":
        raise conflict("Only an order waiting for approval can be approved.")
    if not o.lines:
        raise conflict("This order has no lines to deliver.")
    decided_here(request, db, me, o, "approved")
    delivery = sales.approve(db, o, me, company_of(request))
    audit(db, me, "sales_order.approved", target=o.number, target_type="sales_order", target_id=o.id, fields=[delivery.number])
    db.commit()
    return {"id": o.id, "status": o.status, "delivery": {"id": delivery.id, "number": delivery.number},
            "purchaseOrders": purchase_orders_of(db, o)}


def purchase_orders_of(db: DB, o: SalesOrder) -> list[dict]:
    """The purchase orders it raised: order-on-demand (15b)."""
    return [{"id": po.id, "number": po.number, "status": po.status, "supplier": po.supplier.name if po.supplier else None}
            for po in db.scalars(select(PurchaseOrder).where(PurchaseOrder.sales_order_id == o.id).order_by(PurchaseOrder.number))]


class RejectIn(Api):
    note: str = Field(min_length=3, max_length=500)


@router.post("/sales-orders/{order_id}/reject")
def reject_order(_: allowed("sales.approve"), me: CurrentUser, db: DB, order_id: str, body: RejectIn, request: Request) -> dict:
    """Not approved, with the reason; an order typed here goes back to its maker to change and send again."""
    o = found(db, SalesOrder, order_id, "sales order")
    if o.status != "pending":
        raise conflict("Only an order waiting for approval can be rejected.")
    decided_here(request, db, me, o, "returned")
    from datetime import UTC, datetime

    o.status, o.decided_by_id, o.decided_at, o.decision_note = "rejected", me.id, datetime.now(UTC), body.note.strip()
    sales.told(db, company_of(request), o)
    audit(db, me, "sales_order.rejected", target=o.number, target_type="sales_order", target_id=o.id)
    db.commit()
    return {"id": o.id, "status": o.status}


@router.post("/sales-orders/{order_id}/cancel")
def cancel_order(_: allowed("sales.edit"), me: CurrentUser, db: DB, order_id: str, request: Request) -> dict:
    o = found(db, SalesOrder, order_id, "sales order")
    if sales.is_invoiced(o):
        raise conflict(f"This order is invoiced ({o.invoice_number}): it can't be cancelled. Ask Finance to void the invoice first.")
    if (why := sales.invoiced_message(o)) is not None:
        raise conflict(why)
    if o.status in ("delivered", "cancelled"):
        raise conflict(f"This order is already {o.status}.")
    deliveries = db.scalars(select(Order).where(Order.sales_order_id == o.id, Order.status != "cancelled")).all()
    if any(d.status != "draft" for d in deliveries):
        raise conflict("The warehouse has already reserved or issued its delivery: cancel the delivery first.")
    for d in deliveries:
        d.status = "cancelled"
    if o.status == "pending":
        sales.withdraw_approval(db, company_of(request), o, f"The order was cancelled by {me.full_name}.", me.email)
    o.status = "cancelled"
    sales.told(db, company_of(request), o)
    audit(db, me, "sales_order.cancelled", target=o.number, target_type="sales_order", target_id=o.id)
    db.commit()
    return {"id": o.id, "status": o.status}
