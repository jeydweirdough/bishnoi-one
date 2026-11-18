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

from modules.inventory import business_events, documents
from modules.inventory.models import Order, OrderLine, Product, SalesOrder, SalesOrderLine, User, Warehouse
from modules.inventory.packs import sold_as
from modules.inventory.stock import next_number


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
            "quoteId": order.quote_id, "id": order.id, "number": order.number, "status": order.status, "statusLabel": status_label(order),
            "note": order.decision_note, "deliveredAt": order.delivered_at.isoformat() if order.delivered_at else None,
            "delivery": latest_delivery(db, order),
            # Invoiced and paid (step 13), with the invoice's figures (Step 4D): the quote shows what was invoiced.
            "invoice": invoice_out(order)})


STATUS_LABELS = {"draft": "Draft", "pending": "Waiting for approval", "confirmed": "Confirmed", "delivered": "Delivered",
                 "rejected": "Rejected", "cancelled": "Cancelled"}


def is_invoiced(order: SalesOrder) -> bool:
    """An invoice stands for it (issued or paid): its amounts follow the invoice and nothing on it changes."""
    return order.invoice_state in ("issued", "paid")


def status_label(order: SalesOrder) -> str:
    """What the order shows: the invoice's state once invoiced (Step 4D), else its own."""
    if order.invoice_state == "paid":
        return "Paid"
    if order.invoice_state == "issued":
        return "Invoiced"
    if order.invoice_state == "voided":
        return "Invoice voided — waiting for reissue"
    return STATUS_LABELS[order.status]


def figures(order: SalesOrder) -> dict:
    """The order's amounts: the invoice's once invoiced, the order's own otherwise (or while its invoice is voided)."""
    if is_invoiced(order):
        return {"source": "invoice", "invoiceNumber": order.invoice_number,
                "grossCentavos": order.invoice_gross if order.invoice_gross is not None else order.gross_centavos,
                "discountCentavos": order.invoice_discount if order.invoice_discount is not None else order.discount_centavos,
                "taxCentavos": order.invoice_tax, "totalCentavos": order.invoice_total if order.invoice_total is not None else order.total_centavos}
    return {"source": "order", "invoiceNumber": None, "grossCentavos": order.gross_centavos, "discountCentavos": order.discount_centavos,
            "taxCentavos": None, "totalCentavos": order.total_centavos}


def value_of(order: SalesOrder) -> int:
    """What the order comes to in reports: the invoice's total once invoiced, the order's own otherwise."""
    return figures(order)["totalCentavos"] or 0


def invoice_out(order: SalesOrder) -> dict | None:
    if not order.invoice_id:
        return None
    return {"id": order.invoice_id, "number": order.invoice_number, "state": order.invoice_state,
            "invoicedAt": order.invoiced_at.isoformat() if order.invoiced_at else None,
            "paidAt": order.paid_at.isoformat() if order.paid_at else None,
            "grossCentavos": order.invoice_gross, "discountCentavos": order.invoice_discount, "taxCentavos": order.invoice_tax,
            "totalCentavos": order.invoice_total, "lines": order.invoice_lines, "voidReason": order.invoice_note}


def invoiced_message(order: SalesOrder) -> str | None:
    """Why an invoiced order can't change, or None when it can (Step 4D)."""
    if is_invoiced(order):
        return (f"This order is invoiced ({order.invoice_number}): its amounts follow the invoice. "
                "Ask Finance to void and reissue it to change them.")
    if order.invoice_state == "voided":
        return (f"This order's invoice ({order.invoice_number}) was voided and waits for its reissue in Finance: "
                "the reissued invoice sets its amounts.")
    return None


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
                   "unitPriceCentavos": line.unit_price, "discountCentavos": line.discount or 0, "vatCategory": line.vat_category or "standard",
                   # The unit sold (step 4A), words only: "2 Boxes of 10"; quantity and price stay per base unit.
                   "soldAs": sold_as(line.quantity, line.unit_name, line.per)}
                  for line in order.lines],
    }


def _order_of_invoice(db: Session, data: dict) -> SalesOrder | None:
    """The sales order an invoice event is about: by the order Finance names, else the order whose invoice it replaces
    (a reissued invoice doesn't carry the order), else the order holding that invoice."""
    if data.get("salesOrderId"):
        order = db.get(SalesOrder, str(data["salesOrderId"]))
        if order is not None:
            return order
    for invoice_id in (data.get("replacesId"), data.get("id")):
        if invoice_id:
            order = db.scalar(select(SalesOrder).where(SalesOrder.invoice_id == str(invoice_id)[:36]))
            if order is not None:
                return order
    return None


def _cents(value) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def invoiced(db: Session, data: dict, slug: str | None) -> None:
    """Finance issued the invoice for one of its deliveries, or its reissue (invoice.issued): the order takes the
    invoice's figures and follows them from now on (Step 4D)."""
    order = _order_of_invoice(db, data)
    if order is None:
        return
    order.invoice_id, order.invoice_number = str(data.get("id") or "")[:36] or None, str(data.get("number") or "")[:30] or None
    order.invoice_total = int(data.get("totalCentavos") or 0)
    order.invoice_tax = _cents(data.get("taxCentavos"))
    order.invoice_gross, order.invoice_discount = _cents(data.get("grossCentavos")), _cents(data.get("discountCentavos"))
    lines = data.get("lines")
    order.invoice_lines = [{"ref": line.get("ref"), "description": str(line.get("description") or "")[:200], "quantity": _cents(line.get("quantity")) or 0,
                            "unitPriceCentavos": _cents(line.get("unitPriceCentavos")) or 0, "discountCentavos": _cents(line.get("discountCentavos")) or 0,
                            "taxCentavos": _cents(line.get("taxCentavos")) or 0, "totalCentavos": _cents(line.get("totalCentavos")) or 0}
                           for line in lines[:500] if isinstance(line, dict)] if isinstance(lines, list) else None
    order.invoice_state, order.invoice_note, order.paid_at = "issued", None, None
    order.invoiced_at = datetime.now(UTC)
    told(db, slug, order)


def voided(db: Session, data: dict, slug: str | None) -> None:
    """Its invoice was voided (invoice.voided): the order's own amounts show again, marked as waiting for the reissue."""
    invoice_id = str(data.get("id") or "")[:36]
    order = db.scalar(select(SalesOrder).where(SalesOrder.invoice_id == invoice_id)) if invoice_id else None
    if order is None or order.invoice_state == "voided":
        return
    order.invoice_state, order.invoice_note = "voided", (str(data.get("reason") or "")[:300] or None)
    order.invoice_total = order.invoice_tax = order.invoice_gross = order.invoice_discount = None
    order.invoice_lines, order.paid_at = None, None
    told(db, slug, order)


def paid(db: Session, data: dict, slug: str | None) -> None:
    """Its invoice was paid in full (invoice.paid): the chain is closed."""
    order = _order_of_invoice(db, {"salesOrderId": data.get("salesOrderId"), "id": data.get("id")})
    if order is None or order.invoice_id != str(data.get("id") or "") or order.invoice_state == "voided":
        return
    order.paid_at = datetime.fromisoformat(data["paidAt"]) if data.get("paidAt") else datetime.now(UTC)
    order.invoice_state = "paid"
    told(db, slug, order)


def latest_delivery(db: Session, order: SalesOrder) -> dict | None:
    """Its latest delivery that isn't cancelled: number, where it is, the courier and how to track it."""
    from modules.inventory.shipping import STATE_LABELS, tracking_link

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


def approve(db: Session, order: SalesOrder, me: User, slug: str | None) -> Order:
    """Confirmed: its delivery is made for the warehouse to reserve, pick and issue, and draft purchase orders
    for what the warehouse lacks (order-on-demand, 15b). This is the only way a sale delivery (kind "sale") is
    made: the Inventory API refuses one typed directly (2026-11-17)."""
    from modules.inventory import supply

    now = datetime.now(UTC)
    order.status, order.decided_by_id, order.decided_at, order.decision_note = "confirmed", me.id, now, None
    supply.on_demand(db, me, order, slug)
    delivery = Order(number=next_number(db, "DR"), kind="sale", recipient=order.customer_name[:160], warehouse_id=order.warehouse_id,
                     needed_on=order.scheduled_on, notes=order.notes, created_by_id=me.id, sales_order_id=order.id,
                     scheduled_on=order.scheduled_on, source_document=order.number)
    for i, line in enumerate(order.lines):
        delivery.lines.append(OrderLine(position=i, product_id=line.product_id, quantity=line.quantity + (line.free_quantity or 0),
                                        unit_price=line.unit_price, sold_as=sold_as(line.quantity + (line.free_quantity or 0), line.unit_name, line.per)))
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
