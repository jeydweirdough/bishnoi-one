"""How much there is and what has happened to it: the stock overview, the
movement trail, batches and their expiry, and serial numbers."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from sqlalchemy import and_, case, func, or_, select

from app.access import allowed
from app.api import iso
from app.deps import DB, SettingsDep
from app.levels import by_product, by_warehouse, levels_by_product, levels_by_warehouse, state, state_sql
from app.models import Batch, Category, Location, Movement, Product, Serial, Stock, Warehouse
from app.out import batch_ref, day, location_ref, product_ref, today, warehouse_ref
from app.paging import Limit, Offset, cut, total

router = APIRouter(prefix="/inventory", tags=["stock"])

View = allowed("stock.view")


def in_category(db: DB, category_id: str) -> set[str]:
    """A category and every one inside it."""
    wanted, frontier = {category_id}, [category_id]
    while frontier:
        frontier = list(db.scalars(select(Category.id).where(Category.parent_id.in_(frontier))))
        wanted.update(frontier)
    return wanted


@router.get("/stock")
def stock_overview(
    _: View,
    db: DB,
    warehouse: str | None = Query(None, max_length=36),
    q: str | None = Query(None, max_length=100),
    category: str | None = Query(None, max_length=36),
    state_: str | None = Query(None, alias="state", max_length=8, description="low, out, over, ok"),
    limit: int | None = Limit(),
    offset: int = Offset(),
) -> dict:
    """One row per product per warehouse it's in, with every quantity.

    With `limit`, one page of the rows: `count` is how many rows match in all,
    and `total` still sums every matching row, not just this page."""
    if limit is not None:
        return stock_page(db, warehouse, q, category, state_, limit, offset)
    query = select(Product).where(Product.product_type != "service")
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Product.name).like(like), func.lower(Product.sku).like(like), func.lower(Product.barcode).like(like)))
    if category:
        query = query.where(Product.category_id.in_(in_category(db, category)))
    products = {p.id: p for p in db.scalars(query)}
    levels = by_warehouse(db, list(products), warehouse)
    # Low and over are judged on the product as a whole, as the reorder point
    # is; a warehouse row is flagged out on its own when nothing is free there.
    overall = by_product(db, list(products))
    warehouses = {w.id: w for w in db.scalars(select(Warehouse))}
    rows = []
    for (pid, wid), level in levels.items():
        p = products.get(pid)
        if p is None or wid not in warehouses:
            continue
        row_state = "out" if level["available"] <= 0 and state(p, level) is not None else state(p, overall[pid])
        if state_ and row_state != state_:
            continue
        rows.append({"product": product_ref(p), "warehouse": warehouse_ref(warehouses[wid]), **level, "reorderPoint": p.reorder_point, "state": row_state, "value": level["onHand"] * p.cost_price})
    rows.sort(key=lambda r: (r["product"]["name"].lower(), r["warehouse"]["code"]))
    total = {k: sum(r[k] for r in rows) for k in ("onHand", "damaged", "reserved", "allocated", "available", "inTransit", "value")}
    return {"items": rows, "total": total}


QUANTITIES = ("onHand", "damaged", "reserved", "allocated", "available", "inTransit")


def stock_page(db: DB, warehouse: str | None, q: str | None, category: str | None, state_: str | None, limit: int, offset: int) -> dict:
    """stock_overview's rows, filtered, sorted, summed and cut into a page by the database."""
    lv = levels_by_warehouse(warehouse)
    overall = levels_by_product()
    # As stock_overview: a warehouse row is out on its own when nothing is free
    # there; otherwise low and over are judged on the product as a whole.
    row_state = case(
        (and_(lv.c.available <= 0, Product.variant_count == 0), "out"),
        else_=state_sql(func.coalesce(overall.c.available, 0), func.coalesce(overall.c.on_hand, 0)),
    )
    rows = (
        select(
            Product.id.label("product_id"),
            Warehouse.id.label("warehouse_id"),
            func.lower(Product.name).label("name"),
            Warehouse.code.label("code"),
            lv.c.on_hand,
            lv.c.damaged,
            lv.c.reserved,
            lv.c.allocated,
            lv.c.available,
            lv.c.in_transit,
            (lv.c.on_hand * Product.cost_price).label("value"),
            row_state.label("state"),
        )
        .select_from(lv)
        .join(Product, Product.id == lv.c.product_id)
        .join(Warehouse, Warehouse.id == lv.c.warehouse_id)
        .outerjoin(overall, overall.c.product_id == lv.c.product_id)
        .where(Product.product_type != "service")
    )
    if q:
        like = f"%{q.lower()}%"
        rows = rows.where(or_(func.lower(Product.name).like(like), func.lower(Product.sku).like(like), func.lower(Product.barcode).like(like)))
    if category:
        rows = rows.where(Product.category_id.in_(in_category(db, category)))
    rows = rows.subquery()
    matching = select(rows)
    if state_:
        matching = matching.where(rows.c.state == state_)
    matching = matching.subquery()
    sums = db.execute(
        select(*(func.coalesce(func.sum(matching.c[c]), 0) for c in ("on_hand", "damaged", "reserved", "allocated", "available", "in_transit", "value")), func.count())
    ).one()
    page = db.execute(cut(select(matching).order_by(matching.c.name, matching.c.code, matching.c.product_id), limit, offset)).all()
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_({r.product_id for r in page})))}
    warehouses = {w.id: w for w in db.scalars(select(Warehouse).where(Warehouse.id.in_({r.warehouse_id for r in page})))}
    items = []
    for r in page:
        p = products[r.product_id]
        level = dict(zip(QUANTITIES, (int(r.on_hand or 0), int(r.damaged or 0), int(r.reserved or 0), int(r.allocated or 0), int(r.available or 0), int(r.in_transit or 0)), strict=True))
        items.append({"product": product_ref(p), "warehouse": warehouse_ref(warehouses[r.warehouse_id]), **level, "reorderPoint": p.reorder_point, "state": r.state, "value": level["onHand"] * p.cost_price})
    return {"items": items, "total": {k: int(v) for k, v in zip((*QUANTITIES, "value"), sums[:7], strict=True)}, "count": int(sums[7])}


def available(_: View, db: DB) -> dict[str, int]:
    """What's free per product per warehouse ("product:warehouse"), for the order
    and transfer forms. Read through GraphQL: the overview's rows without the rest."""
    products = list(db.scalars(select(Product.id).where(Product.product_type != "service")))
    return {f"{pid}:{wid}": level["available"] for (pid, wid), level in by_warehouse(db, products).items()}


def movement_out(m: Movement) -> dict:
    return {
        "id": m.id,
        "at": iso(m.at),
        "kind": m.kind,
        "product": product_ref(m.product),
        "warehouse": warehouse_ref(m.warehouse),
        "location": location_ref(m.location),
        "batch": {"id": m.batch.id, "batchNo": m.batch.batch_no, "expiresOn": day(m.batch.expires_on)} if m.batch else None,
        "quantity": m.quantity,
        "onHandChange": m.on_hand_change,
        "onHandAfter": m.on_hand_after,
        "unitCost": m.unit_cost,
        "reference": m.reference,
        "referenceType": m.reference_type,
        "referenceId": m.reference_id,
        "note": m.note,
        "serials": m.serials or [],
        "user": m.user_name,
    }


def day_start(d: date, zone: str) -> datetime:
    """The start of the company's day, as a moment."""
    return datetime.combine(d, time.min, ZoneInfo(zone)).astimezone(UTC)


@router.get("/movements")
def movements(
    _: View,
    db: DB,
    settings: SettingsDep,
    product: str | None = Query(None, max_length=36),
    warehouse: str | None = Query(None, max_length=36),
    kind: str | None = Query(None, max_length=16, description="a kind, or several: receive,issue"),
    reference: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=100),
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    before: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Newest first. Pass the last one's id as `before` for the next page."""
    query = select(Movement).order_by(Movement.id.desc()).limit(limit + 1)
    if product:
        query = query.where(Movement.product_id == product)
    if warehouse:
        query = query.where(Movement.warehouse_id == warehouse)
    if kind:
        query = query.where(Movement.kind.in_(kind.split(",")))
    if reference:
        query = query.where(Movement.reference_id == reference)
    if q:
        like = f"%{q.lower()}%"
        query = query.join(Product).where(or_(func.lower(Product.name).like(like), func.lower(Product.sku).like(like), func.lower(Movement.reference).like(like)))
    if start:
        query = query.where(Movement.at >= day_start(start, settings.org_timezone))
    if end:
        query = query.where(Movement.at < day_start(end + timedelta(days=1), settings.org_timezone))
    if before:
        query = query.where(Movement.id < before)
    found = db.scalars(query).all()
    return {"items": [movement_out(m) for m in found[:limit]], "more": len(found) > limit}


@router.get("/batches")
def batches(
    _: View,
    db: DB,
    settings: SettingsDep,
    q: str | None = Query(None, max_length=100),
    product: str | None = Query(None, max_length=36),
    warehouse: str | None = Query(None, max_length=36),
    expiry: str | None = Query(None, max_length=10, description="expired, expiring, ok"),
    empty: bool = Query(False, description="also batches with nothing left"),
    limit: int | None = Limit(),
    offset: int = Offset(),
) -> list[dict] | dict:
    """Batches, soonest to expire first: the order FEFO takes them in."""
    warn = settings.expiry_warning_days
    held = select(Stock.batch_id, func.sum(Stock.on_hand).label("on_hand"), func.sum(Stock.damaged).label("damaged")).where(Stock.batch_id.is_not(None))
    if warehouse:
        held = held.where(Stock.warehouse_id == warehouse)
    held = held.group_by(Stock.batch_id).subquery()
    query = (
        select(Batch, func.coalesce(held.c.on_hand, 0), func.coalesce(held.c.damaged, 0))
        .outerjoin(held, held.c.batch_id == Batch.id)
        .join(Product, Batch.product_id == Product.id)
        .order_by(Batch.expires_on.is_(None), Batch.expires_on, Batch.received_at)
    )
    if not empty:
        query = query.where(held.c.on_hand > 0)
    if product:
        query = query.where(Batch.product_id == product)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Batch.batch_no).like(like), func.lower(Product.name).like(like), func.lower(Product.sku).like(like)))
    today_ = today()
    if expiry == "expired":
        query = query.where(Batch.expires_on < today_)
    elif expiry == "expiring":
        query = query.where(Batch.expires_on >= today_, Batch.expires_on <= today_ + timedelta(days=warn))
    elif expiry == "ok":
        query = query.where(or_(Batch.expires_on.is_(None), Batch.expires_on > today_ + timedelta(days=warn)))
    found = db.execute(cut(query.order_by(Batch.id), limit, offset) if limit is not None else query)
    rows = []
    for batch, on_hand, damaged in found:
        where = db.execute(
            select(Warehouse.code, func.sum(Stock.on_hand)).join(Warehouse, Stock.warehouse_id == Warehouse.id).where(Stock.batch_id == batch.id, Stock.on_hand > 0).group_by(Warehouse.code)
        ).all()
        rows.append(
            {
                **batch_ref(batch, warn),
                "product": product_ref(batch.product),
                "onHand": int(on_hand),
                "damaged": int(damaged),
                "daysLeft": (batch.expires_on - today_).days if batch.expires_on else None,
                "value": int(on_hand) * batch.product.cost_price,
                "warehouses": [{"code": code, "onHand": int(n)} for code, n in where],
            }
        )
    if limit is not None:
        return {"items": rows, "total": total(db, query)}
    return rows


@router.get("/serials")
def serials(_: View, db: DB, q: str = Query(min_length=1, max_length=80), limit: int | None = Limit(), offset: int = Offset()) -> list[dict] | dict:
    """Where a serial-numbered unit is, and where it has been. Without `limit`,
    the first 50 found; with it, one page and the total."""
    like = f"%{q.lower()}%"
    query = select(Serial).where(func.lower(Serial.serial_no).like(like)).order_by(Serial.serial_no, Serial.id)
    units = db.scalars(cut(query, limit, offset) if limit is not None else query.limit(50)).all()
    out = []
    for s in units:
        p = db.get(Product, s.product_id)
        loc = db.get(Location, s.location_id) if s.location_id else None
        # The trail of this product's serial-numbered movements, read for this one number.
        trail = db.scalars(select(Movement).where(Movement.product_id == s.product_id, Movement.kind.not_in(("reserve", "release"))).order_by(Movement.id.desc()).limit(1000))
        history = [m for m in trail if s.serial_no in (m.serials or [])][:20]
        out.append(
            {
                "id": s.id,
                "serialNo": s.serial_no,
                "status": s.status,
                "product": product_ref(p),
                "warehouse": warehouse_ref(loc.warehouse) if loc else None,
                "location": location_ref(loc),
                "batch": batch_ref(db.get(Batch, s.batch_id)) if s.batch_id else None,
                "history": [movement_out(m) for m in history],
            }
        )
    if limit is not None:
        return {"items": out, "total": total(db, query)}
    return out

