"""The Sales app's sales orders (feature plan step 11, agreed 2026-10-29), kept in the Operations service
beside the stock they ship from.

    CRM quote (approved, letter, Rx, credit)  ── quote.ordered ──▶  sales order: waiting for approval
    typed here, at the price list's prices    ──  submitted  ────▶  sales order: waiting for approval
    approved (sales.approve)  ──▶  confirmed: its delivery is made (a stock order, kind sale)
    the delivery issued       ──▶  delivered (delivery.done goes to Books; step 13 invoices it)

Decisions (2026-10-29): the order is its own document and today's Inventory "sales orders" are its
deliveries; Raise order in the CRM sends the event quote.ordered (no separate Order system); every order
waits for approval, from a quote or not; an order typed here takes the price list's prices only (nobody
types a price); it ships from the warehouse chosen, by default the company's first.

The CRM hears each change (sales_order.updated), so the quote shows its order's number and progress; each
step is linked in the document trail (step 9).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import business_events, documents
from app.models import Order, OrderLine, Product, SalesOrder, SalesOrderLine, User, Warehouse
from app.stock import next_number


def default_warehouse(db: Session) -> Warehouse | None:
    """The company's first warehouse that's switched on: where an order ships from unless another is chosen."""
    return db.scalar(select(Warehouse).where(Warehouse.is_active).order_by(Warehouse.no, Warehouse.code).limit(1))


def totals(order: SalesOrder) -> None:
    order.gross_centavos = sum((line.unit_price or 0) * line.quantity for line in order.lines)
    order.discount_centavos = sum(line.discount or 0 for line in order.lines)
    order.total_centavos = sum(line.total or 0 for line in order.lines)


def told(db: Session, slug: str | None, order: SalesOrder) -> None:
    """The CRM hears what became of an order from one of its quotes, with its latest delivery's shipping (step 12)."""
    if order.quote_id:
        business_events.emit(db, slug, "sales_order.updated", {
            "quoteId": order.quote_id, "id": order.id, "number": order.number, "status": order.status,
            "note": order.decision_note, "deliveredAt": order.delivered_at.isoformat() if order.delivered_at else None,
            "delivery": latest_delivery(db, order),
            # Invoiced and paid (step 13).
            "invoice": {"id": order.invoice_id, "number": order.invoice_number, "invoicedAt": order.invoiced_at.isoformat() if order.invoiced_at else None,
                        "paidAt": order.paid_at.isoformat() if order.paid_at else None} if order.invoice_id else None})


def for_invoice(order: SalesOrder) -> dict:
    """What Finance needs to invoice its delivery (step 13): the customer, the sale, the lines as sold."""
    return {
        "id": order.id, "number": order.number, "quote": {"id": order.quote_id, "number": order.quote_number} if order.quote_id else None,
        "customer": {"id": order.customer_id, "name": order.customer_name, "address": order.customer_address, "tin": order.customer_tin},
        "salesperson": {"id": order.salesperson_id, "name": order.salesperson_name} if order.salesperson_id or order.salesperson_name else None,
        "division": {"id": order.division_id, "name": order.division_name} if order.division_id else None,
        "team": {"id": order.team_id, "name": order.team_name} if order.team_id else None,
        "payer": order.payer, "currency": order.currency,
        "pricesIncludeTax": (order.tax or {}).get("pricesIncludeTax") if isinstance(order.tax, dict) else None,
        "lines": [{"sku": line.product.sku, "name": line.product.name, "quantity": line.quantity, "freeQuantity": line.free_quantity or 0,
                   "unitPriceCentavos": line.unit_price, "discountCentavos": line.discount or 0, "vatCategory": line.vat_category or "standard"}
                  for line in order.lines],
    }


def invoiced(db: Session, data: dict, slug: str | None) -> None:
    """Finance issued the invoice for one of its deliveries (invoice.issued): the order is invoiced."""
    order = db.get(SalesOrder, str(data.get("salesOrderId") or "")) if data.get("salesOrderId") else None
    if order is None:
        return
    order.invoice_id, order.invoice_number = str(data.get("id") or "")[:36] or None, str(data.get("number") or "")[:30] or None
    order.invoice_total = int(data.get("totalCentavos") or 0)
    order.invoiced_at = datetime.now(UTC)
    told(db, slug, order)


def paid(db: Session, data: dict, slug: str | None) -> None:
    """Its invoice was paid in full (invoice.paid): the chain is closed."""
    order = db.get(SalesOrder, str(data.get("salesOrderId") or "")) if data.get("salesOrderId") else None
    if order is None or order.invoice_id != str(data.get("id") or ""):
        return
    order.paid_at = datetime.fromisoformat(data["paidAt"]) if data.get("paidAt") else datetime.now(UTC)
    told(db, slug, order)


def latest_delivery(db: Session, order: SalesOrder) -> dict | None:
    """Its latest delivery that isn't cancelled: number, where it is, the courier and how to track it."""
    from app.shipping import STATE_LABELS, tracking_link

    db.flush()
    d = db.scalar(select(Order).where(Order.sales_order_id == order.id, Order.status != "cancelled").order_by(Order.created_at.desc()))
    if d is None:
        return None
    return {"id": d.id, "number": d.number, "status": d.delivery_status or d.status,
            "statusLabel": STATE_LABELS.get(d.delivery_status or "", None),
            "courier": d.courier.name if d.courier else None, "trackingNumber": d.tracking_number, "trackingUrl": tracking_link(d),
            "deliveredAt": d.delivered_at.isoformat() if d.delivered_at else None}


def shipment_changed(db: Session, slug: str | None, delivery: Order) -> None:
    """A delivery's shipping changed (courier, tracking, delivered, failed): its order's quote hears it."""
    if delivery.sales_order_id:
        order = db.get(SalesOrder, delivery.sales_order_id)
        if order is not None:
            told(db, slug, order)


def from_quote(db: Session, data: dict, slug: str | None) -> SalesOrder | None:
    """The sales order for a CRM quote (the event quote.ordered), waiting for approval; made once per quote."""
    quote = data.get("quote") or {}
    if not quote.get("id"):
        return None
    found = db.scalar(select(SalesOrder).where(SalesOrder.quote_id == str(quote["id"])))
    if found is not None:
        return found
    warehouse = default_warehouse(db)
    if warehouse is None:
        raise ValueError("This company has no warehouse switched on to ship from.")
    customer, salesperson = data.get("customer") or {}, data.get("salesperson") or {}
    team, division = data.get("team") or {}, data.get("division") or {}
    order = SalesOrder(
        number=next_number(db, "SO"), status="pending",
        customer_id=customer.get("id"), customer_name=str(customer.get("name") or "Customer")[:200],
        customer_address=(customer.get("address") or None) and str(customer["address"])[:400], customer_tin=(customer.get("tin") or None),
        quote_id=str(quote["id"]), quote_number=str(quote.get("number") or "")[:30] or None,
        salesperson_id=salesperson.get("id"), salesperson_name=salesperson.get("name"),
        team_id=team.get("id"), team_name=team.get("name"), division_id=division.get("id"), division_name=division.get("name"),
        payer=data.get("payer"), warehouse_id=warehouse.id, notes=quote.get("notes"),
        tax=data.get("tax"), currency=str(data.get("currency") or "PHP")[:3], created_by_name=(data.get("raisedBy") or {}).get("name"),
    )
    missing = []
    for i, line in enumerate(data.get("lines") or []):
        product = db.get(Product, line.get("inventoryId")) if line.get("inventoryId") else None
        if product is None and line.get("code"):
            product = db.scalar(select(Product).where(Product.sku == str(line["code"])))
        if product is None:
            missing.append(str(line.get("name") or line.get("code") or "a line"))
            continue
        order.lines.append(SalesOrderLine(position=i, product_id=product.id, quantity=max(1, int(line.get("quantity") or 0)),
                                          free_quantity=int(line.get("freeQuantity") or 0), unit_price=int(line.get("unitPriceCentavos") or 0),
                                          discount=int(line.get("discountCentavos") or 0), total=int(line.get("totalCentavos") or 0),
                                          vat_category=str(line.get("vatCategory") or "standard")[:20]))
    if missing:
        order.notes = ((order.notes + "\n") if order.notes else "") + "Not found in Inventory, left out: " + ", ".join(missing) + "."
    totals(order)
    db.add(order)
    db.flush()
    business_events.link(db, slug, business_events.ref("quote", order.quote_id, order.quote_number, app="crm"), business_events.ref("sales_order", order.id, order.number))
    told(db, slug, order)
    return order


def approve(db: Session, order: SalesOrder, me: User, slug: str | None) -> Order | None:
    """Confirmed: its delivery is made for the warehouse to reserve, pick and issue, and draft purchase orders
    for what the warehouse lacks (order-on-demand, 15b). A dropshipped order makes the vendors' purchase orders
    instead, shipping to the customer (15c); then there's no delivery."""
    from app import supply

    now = datetime.now(UTC)
    if order.dropship:
        supply.dropship(db, me, order, slug)  # refuses before anything changes when an item has no vendor
        order.status, order.decided_by_id, order.decided_at, order.decision_note = "confirmed", me.id, now, None
        told(db, slug, order)
        return None
    order.status, order.decided_by_id, order.decided_at, order.decision_note = "confirmed", me.id, now, None
    supply.on_demand(db, me, order, slug)
    delivery = Order(number=next_number(db, "DR"), kind="sale", recipient=order.customer_name[:160], warehouse_id=order.warehouse_id,
                     needed_on=order.scheduled_on, notes=order.notes, created_by_id=me.id, sales_order_id=order.id,
                     scheduled_on=order.scheduled_on, source_document=order.number)
    for i, line in enumerate(order.lines):
        delivery.lines.append(OrderLine(position=i, product_id=line.product_id, quantity=line.quantity + (line.free_quantity or 0),
                                        unit_price=line.unit_price))
    documents.apply(db, delivery, ("delivery",), None, me, order.warehouse_id, new=True)
    db.add(delivery)
    db.flush()
    business_events.link(db, slug, business_events.ref("sales_order", order.id, order.number), business_events.ref("order", delivery.id, delivery.number))
    told(db, slug, order)
    return delivery


def delivered(db: Session, delivery: Order, slug: str | None) -> None:
    """Its delivery left the warehouse: the order's lines are delivered, and the order with them."""
    if not delivery.sales_order_id:
        return
    order = db.get(SalesOrder, delivery.sales_order_id)
    if order is None or order.status != "confirmed":
        return
    for line in order.lines:
        line.delivered = line.quantity
    order.status, order.delivered_at = "delivered", delivery.issued_at or datetime.now(UTC)
    told(db, slug, order)
