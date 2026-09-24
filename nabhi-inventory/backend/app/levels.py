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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, Stock
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
    the minimum), over (above the maximum), ok. None for a service."""
    if product.product_type == "service":
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
