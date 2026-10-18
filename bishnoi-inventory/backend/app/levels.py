"""How much there is: every quantity the screens show, per product, overall
or per warehouse.

- on hand:    physically there (good and damaged)
- damaged:    on hand, set aside as damaged
- reserved:   held for confirmed orders
- allocated:  held for orders being picked
- available:  on hand − damaged − reserved − allocated
- in transit: on its way here on a transfer
"""

from collections import defaultdict

from sqlalchemy import Integer, case, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.models import Order, OrderLine, Product, Stock, Transfer, TransferLine
from app.stock import held, in_transit

ZERO = {"onHand": 0, "damaged": 0, "reserved": 0, "allocated": 0, "available": 0, "inTransit": 0}


def by_warehouse(db: Session, product_ids: list[str] | None = None, warehouse_id: str | None = None) -> dict[tuple[str, str], dict[str, int]]:
    """Every quantity, per (product, warehouse) that has any."""
    q = select(Stock.product_id, Stock.warehouse_id, func.sum(Stock.on_hand), func.sum(Stock.damaged)).group_by(Stock.product_id, Stock.warehouse_id)
    if product_ids is not None:
        q = q.where(Stock.product_id.in_(product_ids))
    if warehouse_id:
        q = q.where(Stock.warehouse_id == warehouse_id)
    out: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: dict(ZERO))
    for product_id, wh, on_hand, damaged in db.execute(q):
        row = out[(product_id, wh)]
        row["onHand"], row["damaged"] = int(on_hand or 0), int(damaged or 0)
    for key, hold in held(db, product_ids=product_ids, warehouse_id=warehouse_id).items():
        out[key]["reserved"], out[key]["allocated"] = hold["reserved"], hold["allocated"]
    for key, qty in in_transit(db, product_ids=product_ids).items():
        if warehouse_id is None or key[1] == warehouse_id:
            out[key]["inTransit"] = qty
    for row in out.values():
        row["available"] = row["onHand"] - row["damaged"] - row["reserved"] - row["allocated"]
    return out


def by_product(db: Session, product_ids: list[str] | None = None, warehouse_id: str | None = None) -> dict[str, dict[str, int]]:
    """Every quantity, per product, summed over the warehouses (or in one)."""
    out: dict[str, dict[str, int]] = defaultdict(lambda: dict(ZERO))
    for (product_id, _), row in by_warehouse(db, product_ids, warehouse_id).items():
        for k, v in row.items():
            out[product_id][k] += v
    return out


def state(product: Product, level: dict[str, int]) -> str | None:
    """out (nothing available), low (at or below the reorder point, or under
    the minimum), over (above the maximum), ok. None for a service, and for
    a product that only groups its variants."""
    if product.product_type == "service" or product.variant_count:
        return None
    available = level["available"]
    if available <= 0:
        return "out"
    if available <= product.reorder_point or available < product.min_stock:
        return "low"
    if product.max_stock is not None and level["onHand"] > product.max_stock:
        return "over"
    return "ok"


def suggested_order(product: Product, level: dict[str, int]) -> int:
    """How many to order to get back to the maximum (or reorder point plus the
    reorder quantity), counting what's already on its way."""
    target = product.max_stock if product.max_stock is not None else product.reorder_point + max(product.reorder_qty, 1)
    return max(0, target - level["available"] - level["inTransit"])


# --- the same quantities as SQL, for lists the database pages ---------------------------
#
# by_warehouse() and state() above add the quantities up in Python, which is
# right for a few products. A paged list has to filter on the state and sort
# before it cuts the page, so the database works them out instead: the same
# sums (stock, what orders hold, what's on its way) and the same rules.


def _zero():
    return literal(0, Integer)


def _parts(warehouse_id: str | None = None):
    """Stock, holds and transfers on their way as one set of rows, per (product, warehouse)."""
    on = select(
        Stock.product_id.label("product_id"),
        Stock.warehouse_id.label("warehouse_id"),
        Stock.on_hand.label("on_hand"),
        Stock.damaged.label("damaged"),
        _zero().label("reserved"),
        _zero().label("allocated"),
        _zero().label("in_transit"),
    )
    hold = (
        select(
            OrderLine.product_id,
            Order.warehouse_id,
            _zero(),
            _zero(),
            case((Order.status == "confirmed", OrderLine.quantity), else_=0),
            case((Order.status == "picking", OrderLine.quantity), else_=0),
            _zero(),
        )
        .select_from(OrderLine)
        .join(Order, OrderLine.order_id == Order.id)
        .where(Order.status.in_(("confirmed", "picking")))
    )
    coming = (
        select(TransferLine.product_id, Transfer.to_warehouse_id, _zero(), _zero(), _zero(), _zero(), TransferLine.quantity)
        .select_from(TransferLine)
        .join(Transfer, TransferLine.transfer_id == Transfer.id)
        .where(Transfer.status == "in_transit")
    )
    if warehouse_id:
        on = on.where(Stock.warehouse_id == warehouse_id)
        hold = hold.where(Order.warehouse_id == warehouse_id)
        coming = coming.where(Transfer.to_warehouse_id == warehouse_id)
    return union_all(on, hold, coming).subquery()


def _summed(parts, *keys):
    on_hand, damaged = func.sum(parts.c.on_hand), func.sum(parts.c.damaged)
    reserved, allocated = func.sum(parts.c.reserved), func.sum(parts.c.allocated)
    return (
        select(
            *keys,
            on_hand.label("on_hand"),
            damaged.label("damaged"),
            reserved.label("reserved"),
            allocated.label("allocated"),
            (on_hand - damaged - reserved - allocated).label("available"),
            func.sum(parts.c.in_transit).label("in_transit"),
        )
        .group_by(*keys)
        .subquery()
    )


def levels_by_warehouse(warehouse_id: str | None = None):
    """by_warehouse() as a subquery: product_id, warehouse_id and every quantity."""
    parts = _parts(warehouse_id)
    return _summed(parts, parts.c.product_id, parts.c.warehouse_id)


def levels_by_product(warehouse_id: str | None = None):
    """by_product() as a subquery: product_id and every quantity, summed over the warehouses."""
    parts = _parts(warehouse_id)
    return _summed(parts, parts.c.product_id)


def state_sql(available, on_hand):
    """state() as SQL, for a product's available and on-hand quantities."""
    return case(
        ((Product.product_type == "service") | (Product.variant_count != 0), None),
        (available <= 0, "out"),
        ((available <= Product.reorder_point) | (available < Product.min_stock), "low"),
        (Product.max_stock.is_not(None) & (on_hand > Product.max_stock), "over"),
        else_="ok",
    )
