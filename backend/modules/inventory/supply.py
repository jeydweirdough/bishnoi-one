"""Order-on-demand (feature plan step 15b, 2026-10-29): what a sales order sets off on the buying side when it
is approved.

Order-on-demand (our make-to-order: a distributor buys what it sells): approving a sales order whose lines the
warehouse can't fill raises a draft purchase order for the shortfall, per usual vendor, at its price, tied to
the order (PurchaseOrder.sales_order_id). Its delivery is still made; it waits for the stock to come in. Switched
by the replenishment settings (order_on_demand, on by default).

Dropshipping (15c) was removed on 2026-11-17 (owner's decision): every sale leaves from our warehouse.
"""

from sqlalchemy.orm import Session

from modules.inventory import business_events
from modules.inventory.models import Product, PurchaseOrder, PurchaseOrderLine, SalesOrder, SupplierProduct, User
from modules.inventory.replenishment import settings_of
from modules.inventory.stock import available, next_number


def _price(db: Session, product: Product) -> int:
    terms = db.get(SupplierProduct, (product.supplier_id, product.id)) if product.supplier_id else None
    return terms.price if terms and terms.price else product.cost_price


def _po(db: Session, me: User, order: SalesOrder, supplier_id: str, lines: list[tuple[Product, int]], slug: str | None) -> PurchaseOrder:
    po = PurchaseOrder(number=next_number(db, "PO"), supplier_id=supplier_id, warehouse_id=order.warehouse_id, created_by_id=me.id,
                       sales_order_id=order.id, reason=on_demand_reason(order, lines))
    po.lines = [PurchaseOrderLine(position=i, product_id=p.id, quantity=q, unit_cost=_price(db, p)) for i, (p, q) in enumerate(lines)]
    db.add(po)
    db.flush()
    business_events.link(db, slug, business_events.ref("sales_order", order.id, order.number), business_events.ref("purchase_order", po.id, po.number))
    return po


def on_demand_reason(order: SalesOrder, lines: list[tuple[Product, int]]) -> str:
    """Why an order-on-demand purchase order was made, in plain words (2026-11-18)."""
    short = ", ".join(f"{p.name} ×{q:,}" for p, q in lines)
    when = f" It's due to the customer on {order.scheduled_on:%d %b %Y}." if order.scheduled_on else ""
    return f"Made when sales order {order.number} for {order.customer_name} was approved: the warehouse is short of {short}.{when}"


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
    made = [_po(db, me, order, supplier_id, lines, slug) for supplier_id, lines in groups.items()]
    if missing:
        order.notes = ((order.notes + "\n") if order.notes else "") + "Not enough stock, and no usual vendor to order from: " + ", ".join(p.name for p in missing) + "."
    return made

