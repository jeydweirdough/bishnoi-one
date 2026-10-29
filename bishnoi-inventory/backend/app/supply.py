"""Order-on-demand and dropshipping (feature plan steps 15b and 15c, 2026-10-29): what a sales order sets off on
the buying side when it is approved.

Order-on-demand (our make-to-order: a distributor buys what it sells): approving a sales order whose lines the
warehouse can't fill raises a draft purchase order for the shortfall, per usual vendor, at its price, tied to
the order (PurchaseOrder.sales_order_id). Its delivery is still made; it waits for the stock to come in. Switched
by the replenishment settings (order_on_demand, on by default).

Dropshipping: a sales order marked dropship goes from the vendor straight to the customer. Approving it raises a
purchase order with the customer as ship-to, instead of a delivery from our warehouse; when the vendor says it
was delivered, the order is delivered (no stock passes through us) and Finance invoices it (delivery.done).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import business_events
from app.api import conflict
from app.models import Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SupplierProduct, User
from app.replenishment import settings_of
from app.stock import available, next_number


def _price(db: Session, product: Product) -> int:
    terms = db.get(SupplierProduct, (product.supplier_id, product.id)) if product.supplier_id else None
    return terms.price if terms and terms.price else product.cost_price


def _po(db: Session, me: User, order: SalesOrder, supplier_id: str, lines: list[tuple[Product, int]], slug: str | None, *, dropship: bool) -> PurchaseOrder:
    po = PurchaseOrder(number=next_number(db, "PO"), supplier_id=supplier_id, warehouse_id=order.warehouse_id, created_by_id=me.id,
                       sales_order_id=order.id, dropship=dropship,
                       ship_to_name=order.customer_name if dropship else None, ship_to_address=order.customer_address if dropship else None,
                       notes=(f"Dropship: deliver straight to {order.customer_name}" + (f", {order.customer_address}" if order.customer_address else "") if dropship
                              else f"Order-on-demand for {order.number}: what the warehouse can't fill") + f" ({order.number}).")
    po.lines = [PurchaseOrderLine(position=i, product_id=p.id, quantity=q, unit_cost=_price(db, p)) for i, (p, q) in enumerate(lines)]
    db.add(po)
    db.flush()
    business_events.link(db, slug, business_events.ref("sales_order", order.id, order.number), business_events.ref("purchase_order", po.id, po.number))
    return po


def by_vendor(db: Session, wanted: list[tuple[Product, int]]) -> tuple[dict[str, list[tuple[Product, int]]], list[Product]]:
    out: dict[str, list[tuple[Product, int]]] = {}
    missing = []
    for product, quantity in wanted:
        if product.supplier_id is None:
            missing.append(product)
        else:
            out.setdefault(product.supplier_id, []).append((product, quantity))
    return out, missing


def on_demand(db: Session, me: User, order: SalesOrder, slug: str | None) -> list[PurchaseOrder]:
    """Draft purchase orders for what the warehouse lacks for this order; none when it has it all (or it's switched off)."""
    if not settings_of(db).order_on_demand:
        return []
    need: dict[str, int] = {}
    for line in order.lines:
        need[line.product_id] = need.get(line.product_id, 0) + line.quantity + (line.free_quantity or 0)
    short = []
    for pid, quantity in need.items():
        free = available(db, pid, order.warehouse_id)
        if quantity > max(free, 0):
            short.append((db.get(Product, pid), quantity - max(free, 0)))
    groups, missing = by_vendor(db, short)
    made = [_po(db, me, order, supplier_id, lines, slug, dropship=False) for supplier_id, lines in groups.items()]
    if missing:
        order.notes = ((order.notes + "\n") if order.notes else "") + "Not enough stock, and no usual vendor to order from: " + ", ".join(p.name for p in missing) + "."
    return made


def dropship(db: Session, me: User, order: SalesOrder, slug: str | None) -> list[PurchaseOrder]:
    """The vendor's purchase orders for a dropshipped order, shipping to the customer. Every item needs a usual vendor."""
    wanted = [(line.product, line.quantity + (line.free_quantity or 0)) for line in order.lines]
    groups, missing = by_vendor(db, wanted)
    if missing:
        raise conflict(f"Set a usual vendor on {', '.join(p.name for p in missing)} to dropship it.")
    return [_po(db, me, order, supplier_id, lines, slug, dropship=True) for supplier_id, lines in groups.items()]


def dropship_delivered(db: Session, me: User, po: PurchaseOrder, slug: str | None) -> SalesOrder:
    """The vendor delivered to the customer: the purchase order is received (no stock), the sales order delivered
    when all its vendors have, and Finance is told so it invoices (delivery.done)."""
    from app import sales

    if not po.dropship or not po.sales_order_id:
        raise conflict(f"{po.number} isn't a dropship order.")
    if po.status not in ("ordered", "partial"):
        raise conflict(f"Place {po.number} with the vendor first." if po.status == "draft" else f"{po.number} is {po.status}.")
    order = db.get(SalesOrder, po.sales_order_id)
    for line in po.lines:
        line.received = line.quantity
    po.status = "received"
    others = db.scalars(select(PurchaseOrder).where(PurchaseOrder.sales_order_id == order.id, PurchaseOrder.dropship, PurchaseOrder.id != po.id)).all()
    if all(o.status == "received" for o in others) and order.status == "confirmed":
        for line in order.lines:
            line.delivered = line.quantity
        order.status, order.delivered_at = "delivered", datetime.now(UTC)
        sales.told(db, slug, order)
    business_events.emit(db, slug, "delivery.done", {
        "orderId": po.id, "number": po.number, "salesOrderId": order.id, "recipient": order.customer_name, "warehouseId": po.warehouse_id,
        "issuedAt": datetime.now(UTC).isoformat(), "dropship": True,
        "lines": [{"sku": line.product.sku, "productId": line.product_id, "quantity": line.quantity, "unitPrice": 0, "picks": []} for line in po.lines],
        "shipping": None,
        # Only this vendor's part of the sale.
        "salesOrder": {**sales.for_invoice(order), "lines": [x for x in sales.for_invoice(order)["lines"] if x["sku"] in {line.product.sku for line in po.lines}]},
    })
    return order
