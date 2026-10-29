"""Replenishment (feature plan step 15a, 2026-10-29): when to order and how many, from use and lead time.

For each stocked item in a warehouse:

    daily use      what was issued over the last `history_days`, a day on average
    lead time      the vendor's for this item (vendor prices), else the vendor's, else the default; plus safety days
    position       available + coming by transfer + still to come on purchase orders (drafts included, so a
                   draft already made isn't made twice)
    order point    the most of: its reorder point, its minimum, and use during the lead time
    order          when the position is at or below the order point: up to its maximum when it has one, else
                   the order point plus its reorder quantity (at least one)

Draft purchase orders are made per usual vendor, at that vendor's price for the item (else its cost). Items with
no usual vendor are listed as needing one. Made by hand from the Replenishment page, or each night when the
company switches that on (the Platform's nightly check, app/business_events.py).
"""

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import documents
from app.levels import by_product
from app.models import Movement, Product, PurchaseOrder, PurchaseOrderLine, ReplenishmentSettings, SupplierProduct, User, Warehouse
from app.out import product_ref, supplier_ref, warehouse_ref
from app.stock import next_number


def settings_of(db: Session) -> ReplenishmentSettings:
    s = db.get(ReplenishmentSettings, 1)
    if s is None:
        s = ReplenishmentSettings(id=1)
        db.add(s)
        db.flush()
    return s


def incoming(db: Session, warehouse_id: str) -> dict[str, int]:
    """Still to come on purchase orders to this warehouse (drafts included)."""
    q = (select(PurchaseOrderLine.product_id, func.sum(PurchaseOrderLine.quantity - PurchaseOrderLine.received))
         .join(PurchaseOrder, PurchaseOrderLine.order_id == PurchaseOrder.id)
         .where(PurchaseOrder.warehouse_id == warehouse_id, PurchaseOrder.status.in_(("draft", "ordered", "partial")))
         .group_by(PurchaseOrderLine.product_id))
    return {pid: max(0, int(n or 0)) for pid, n in db.execute(q)}


def used(db: Session, warehouse_id: str, days: int) -> dict[str, int]:
    """What left the warehouse to customers and departments in the last `days`."""
    since = datetime.now(UTC) - timedelta(days=days)
    q = (select(Movement.product_id, func.sum(-Movement.quantity))
         .where(Movement.warehouse_id == warehouse_id, Movement.kind == "issue", Movement.at >= since)
         .group_by(Movement.product_id))
    return {pid: int(n or 0) for pid, n in db.execute(q)}


def plan(db: Session, warehouse: Warehouse, *, everything: bool = False) -> list[dict]:
    """Each item's refill: only those to order now, unless `everything`."""
    s = settings_of(db)
    products = db.scalars(select(Product).where(Product.product_type != "service", Product.variant_count == 0, Product.status == "active")
                          .order_by(func.lower(Product.name))).all()
    ids = [p.id for p in products]
    levels = by_product(db, ids, warehouse.id)
    coming, use = incoming(db, warehouse.id), used(db, warehouse.id, s.history_days)
    vendor_terms = {(sp.supplier_id, sp.product_id): sp for sp in db.scalars(select(SupplierProduct).where(SupplierProduct.product_id.in_(ids)))}
    rows = []
    for p in products:
        lv = levels.get(p.id) or {"available": 0, "inTransit": 0, "onHand": 0}
        terms = vendor_terms.get((p.supplier_id, p.id)) if p.supplier_id else None
        lead = (terms.lead_time_days if terms and terms.lead_time_days is not None else None)
        if lead is None and p.supplier is not None and p.supplier.lead_time_days is not None:
            lead = p.supplier.lead_time_days
        lead = s.default_lead_days if lead is None else lead
        daily = use.get(p.id, 0) / s.history_days if s.history_days else 0
        cover = math.ceil(daily * (lead + s.safety_days))
        point = max(p.reorder_point, p.min_stock, cover)
        position = lv["available"] + lv["inTransit"] + coming.get(p.id, 0)
        due = point > 0 and position <= point
        target = p.max_stock if p.max_stock is not None and p.max_stock > point else point + max(p.reorder_qty, 1)
        quantity = max(0, target - position) if due else 0
        if not due and not everything:
            continue
        rows.append({
            "product": product_ref(p), "supplier": supplier_ref(p.supplier), "available": lv["available"], "inTransit": lv["inTransit"],
            "onOrder": coming.get(p.id, 0), "dailyUse": round(daily, 2), "leadDays": lead, "safetyDays": s.safety_days,
            "orderPoint": point, "position": position, "suggested": quantity,
            "daysLeft": math.floor(lv["available"] / daily) if daily > 0 else None,
            "unitCost": terms.price if terms and terms.price else p.cost_price,
        })
    rows.sort(key=lambda r: (r["suggested"] == 0, r["daysLeft"] if r["daysLeft"] is not None else 10**6, r["product"]["name"].lower()))
    return rows


def make_drafts(db: Session, me: User | None, warehouse: Warehouse, product_ids: list[str] | None = None) -> tuple[list[PurchaseOrder], list[dict]]:
    """Draft purchase orders for what is due, one per usual vendor; and the items left out for want of a vendor."""
    rows = [r for r in plan(db, warehouse) if r["suggested"] > 0 and (product_ids is None or r["product"]["id"] in product_ids)]
    by_vendor: dict[str, list[dict]] = {}
    no_vendor = []
    for r in rows:
        if r["supplier"] is None:
            no_vendor.append(r)
        else:
            by_vendor.setdefault(r["supplier"]["id"], []).append(r)
    made = []
    for supplier_id, lines in by_vendor.items():
        po = PurchaseOrder(number=next_number(db, "PO"), supplier_id=supplier_id, warehouse_id=warehouse.id, created_by_id=me.id if me else None,
                           replenishment=True, notes="Made by replenishment: what's due from use and lead time. Check it, then place it.",
                           expected_on=documents.today() + timedelta(days=max(r["leadDays"] for r in lines)))
        po.lines = [PurchaseOrderLine(position=i, product_id=r["product"]["id"], quantity=r["suggested"], unit_cost=r["unitCost"]) for i, r in enumerate(lines)]
        db.add(po)
        made.append(po)
    db.flush()
    settings_of(db).last_run_at = datetime.now(UTC)
    return made, no_vendor


def nightly(db: Session) -> int:
    """Each night, when the company switched it on: drafts for every warehouse. Returns how many were made."""
    if not settings_of(db).automatic:
        return 0
    made = 0
    for w in db.scalars(select(Warehouse).where(Warehouse.is_active)):
        made += len(make_drafts(db, None, w)[0])
    db.commit()
    return made


def settings_out(s: ReplenishmentSettings) -> dict:
    return {"safetyDays": s.safety_days, "defaultLeadDays": s.default_lead_days, "historyDays": s.history_days, "automatic": s.automatic,
            "lastRunAt": s.last_run_at.isoformat() if s.last_run_at else None}


def warehouse_of(db: Session, warehouse_id: str | None) -> Warehouse | None:
    if warehouse_id:
        return db.get(Warehouse, warehouse_id)
    return db.scalar(select(Warehouse).where(Warehouse.is_active).order_by(Warehouse.code))


__all__ = ["make_drafts", "nightly", "plan", "settings_of", "settings_out", "warehouse_of", "warehouse_ref"]
