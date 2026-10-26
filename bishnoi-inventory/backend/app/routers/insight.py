"""What needs attention and what's happening: the dashboard, the alerts, and
the reports.

Every report is one shape, columns and rows, so the screens show any of
them the same way and export any of them to CSV.
"""

import csv
import io
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app import cpr
from app.access import CurrentAccess, allowed
from app.api import iso
from app.config import Settings
from app.deps import DB, SettingsDep
from app.levels import ZERO, by_product, by_warehouse, state, suggested_order
from app.models import (
    Adjustment,
    AdjustmentLine,
    Batch,
    Count,
    Movement,
    Order,
    Product,
    PurchaseOrder,
    Receipt,
    Stock,
    Supplier,
    Transfer,
    Warehouse,
)
from app.out import day, today, warehouse_ref
from app.routers.adjustments import REASON_LABELS
from app.routers.catalog import category_path
from app.routers.orders import order_brief
from app.routers.purchasing import performance, po_brief, receipt_brief
from app.routers.stock import movement_out

router = APIRouter(prefix="/inventory", tags=["insight"])


def since(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


# --- alerts ---------------------------------------------------------------------------


def alerts(db: DB, settings: Settings, access: CurrentAccess) -> list[dict]:
    """What needs someone: each with how many, the worst few, and where to look."""
    products = db.scalars(select(Product).where(Product.status == "active", Product.product_type != "service")).all()
    levels = by_product(db, [p.id for p in products])
    rated = [(p, levels.get(p.id, dict(ZERO))) for p in products]
    out_of_stock = [(p, lv) for p, lv in rated if state(p, lv) == "out"]
    low = [(p, lv) for p, lv in rated if state(p, lv) == "low"]
    warn = today() + timedelta(days=settings.expiry_warning_days)
    held = select(Stock.batch_id, func.sum(Stock.on_hand).label("n")).where(Stock.batch_id.is_not(None), Stock.on_hand > 0).group_by(Stock.batch_id).subquery()
    expiring = db.execute(select(Batch, held.c.n).join(held, held.c.batch_id == Batch.id).where(Batch.expires_on.is_not(None), Batch.expires_on <= warn).order_by(Batch.expires_on)).all()
    expired = [(b, n) for b, n in expiring if b.expires_on < today()]
    soon = [(b, n) for b, n in expiring if b.expires_on >= today()]
    items: list[dict] = []

    def add(key: str, tone: str, title: str, count: int, href: str, examples: list[str], permission: str) -> None:
        if count and access.can(permission):
            items.append({"key": key, "tone": tone, "title": title, "count": count, "href": href, "examples": examples[:5]})

    add("out", "critical", "Out of stock", len(out_of_stock), "/stock?state=out", [f"{p.name} ({lv['reserved'] + lv['allocated']} held for orders)" if lv["reserved"] + lv["allocated"] else p.name for p, lv in out_of_stock], "stock.view")
    add("low", "warning", "Low stock", len(low), "/stock?state=low", [f"{p.name}: {lv['available']} left, reorder at {p.reorder_point}" for p, lv in low], "stock.view")
    add("expired", "critical", "Expired stock on hand", len(expired), "/batches?expiry=expired", [f"{b.product.name} · {b.batch_no}: {n} expired {b.expires_on:%d %b %Y}" for b, n in expired], "stock.view")
    add("expiring", "warning", f"Expiring within {settings.expiry_warning_days} days", len(soon), "/batches?expiry=expiring", [f"{b.product.name} · {b.batch_no}: {n} on {b.expires_on:%d %b %Y}" for b, n in soon], "stock.view")
    pending_po = db.scalars(select(PurchaseOrder).where(PurchaseOrder.status.in_(("ordered", "partial"))).order_by(PurchaseOrder.expected_on)).all()
    late = [po for po in pending_po if po.expected_on and po.expected_on < today()]
    # Product registrations (app/cpr.py): selling without a valid CPR isn't allowed.
    registrations = [(x, cpr.state(x, today(), settings.expiry_warning_days)) for x in db.scalars(select(Product).where(cpr.state_sql(today(), settings.expiry_warning_days).in_(cpr.ATTENTION)).order_by(Product.cpr_valid_until, Product.name))]
    lapsed = [x for x, s in registrations if s == "expired"]
    renew = [x for x, s in registrations if s == "expiring"]
    unregistered = [x for x, s in registrations if s in ("missing", "no_date")]
    add("cpr_expired", "critical", "CPR expired", len(lapsed), "/products?cpr=expired", [f"{x.name} · {x.cpr_number}: expired {x.cpr_valid_until:%d %b %Y}" for x in lapsed], "products.view")
    add("cpr_expiring", "warning", f"CPR expiring within {settings.expiry_warning_days} days", len(renew), "/products?cpr=expiring", [f"{x.name} · {x.cpr_number}: {x.cpr_valid_until:%d %b %Y}" for x in renew], "products.view")
    add("cpr_missing", "warning", "Products without a complete CPR", len(unregistered), "/products?cpr=missing", [f"{x.name}: " + ("no CPR number" if not x.cpr_number else "no validity date") for x in unregistered], "products.view")
    add("receiving", "info", "Purchase orders to receive", len(pending_po), "/purchase-orders?status=ordered,partial", [f"{po.number} · {po.supplier.name}" + (" (late)" if po in late else "") for po in pending_po], "purchasing.view")
    add("drafts", "info", "Purchase orders to approve", db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status == "draft")) or 0, "/purchase-orders?status=draft", [], "purchasing.approve")
    transit = db.scalars(select(Transfer).where(Transfer.status == "in_transit")).all()
    add("transit", "info", "Transfers awaiting receipt", len(transit), "/transfers?status=in_transit", [f"{t.number}: {t.from_warehouse.code} → {t.to_warehouse.code}" for t in transit], "transfers.view")
    asked = db.scalars(select(Transfer).where(Transfer.status == "requested")).all()
    add("transfer_requests", "info", "Transfers to approve", len(asked), "/transfers?status=requested", [f"{t.number}: {t.from_warehouse.code} → {t.to_warehouse.code}" for t in asked], "transfers.approve")
    approved = db.scalars(select(Transfer).where(Transfer.status == "approved")).all()
    add("dispatch", "info", "Transfers to dispatch", len(approved), "/transfers?status=approved", [f"{t.number}: {t.from_warehouse.code} → {t.to_warehouse.code}" for t in approved], "transfers.dispatch")
    waiting = db.scalars(select(Adjustment).where(Adjustment.status == "pending")).all()
    add("adjustments", "info", "Adjustments to approve", len(waiting), "/adjustments?status=pending", [f"{a.number} · {REASON_LABELS[a.reason]}" for a in waiting], "adjustments.approve")
    counts = db.scalars(select(Count).where(Count.status == "submitted")).all()
    add("counts", "info", "Counts to approve", len(counts), "/counts?status=submitted", [f"{c.number} · {c.warehouse.name}" for c in counts], "counts.approve")
    to_issue = db.scalars(select(Order).where(Order.status.in_(("confirmed", "picking"))).order_by(Order.needed_on)).all()
    add("issue", "info", "Orders to issue", len(to_issue), "/orders?status=confirmed,picking", [f"{o.number} · {o.recipient}" for o in to_issue], "orders.issue")
    return items


@router.get("/alerts")
def list_alerts(access: CurrentAccess, db: DB, settings: SettingsDep) -> list[dict]:
    return alerts(db, settings, access)


# --- the dashboard --------------------------------------------------------------------


@router.get("/dashboard")
def dashboard(_: allowed("dashboard.view"), access: CurrentAccess, db: DB, settings: SettingsDep) -> dict:
    products = db.scalars(select(Product).where(Product.product_type != "service")).all()
    levels = by_product(db, [p.id for p in products])
    active = [p for p in products if p.status == "active"]
    states = defaultdict(int)
    for p in active:
        states[state(p, levels.get(p.id, dict(ZERO)))] += 1
    warn = today() + timedelta(days=settings.expiry_warning_days)
    held = select(Stock.batch_id, func.sum(Stock.on_hand).label("n")).where(Stock.batch_id.is_not(None), Stock.on_hand > 0).group_by(Stock.batch_id).subquery()
    expiring = db.scalar(select(func.count()).select_from(Batch).join(held, held.c.batch_id == Batch.id).where(Batch.expires_on.is_not(None), Batch.expires_on <= warn)) or 0
    warehouses = db.scalars(select(Warehouse).where(Warehouse.is_active).order_by(Warehouse.code)).all()
    per_wh = by_warehouse(db)
    cost = {p.id: p.cost_price for p in products}
    by_wh: dict[str, dict] = {w.id: {"units": 0, "value": 0, "available": 0, "products": 0} for w in warehouses}
    for (pid, wid), lv in per_wh.items():
        if wid in by_wh:
            by_wh[wid]["units"] += lv["onHand"]
            by_wh[wid]["value"] += lv["onHand"] * cost.get(pid, 0)
            by_wh[wid]["available"] += lv["available"]
            by_wh[wid]["products"] += 1 if lv["onHand"] else 0
    total_units = sum(lv["onHand"] for lv in levels.values())
    total_value = sum(lv["onHand"] * cost.get(pid, 0) for pid, lv in levels.items())
    see = access.can
    return {
        "totals": {
            "products": len(active),
            "units": total_units,
            "value": total_value,
            "low": states["low"],
            "out": states["out"],
            "expiring": expiring,
            "reserved": sum(lv["reserved"] + lv["allocated"] for lv in levels.values()),
            "inTransit": sum(lv["inTransit"] for lv in levels.values()),
        },
        "warehouses": [{**warehouse_ref(w), **by_wh[w.id]} for w in warehouses],
        "alerts": alerts(db, settings, access),
        "recentMovements": [movement_out(m) for m in db.scalars(select(Movement).where(Movement.kind.not_in(("reserve", "release"))).order_by(Movement.id.desc()).limit(10))] if see("stock.view") else [],
        "recentReceipts": [receipt_brief(r) for r in db.scalars(select(Receipt).order_by(Receipt.received_at.desc()).limit(5))] if see("receiving.view") else [],
        "recentIssues": [order_brief(o) for o in db.scalars(select(Order).where(Order.status == "issued").order_by(Order.issued_at.desc()).limit(5))] if see("orders.view") else [],
        "openOrders": db.scalar(select(func.count()).select_from(Order).where(Order.status.in_(("confirmed", "picking")))) or 0 if see("orders.view") else 0,
        "trend": monthly(db, settings),
        "upcoming": [purchase_brief(po) for po in db.scalars(
            select(PurchaseOrder).where(PurchaseOrder.status.in_(("ordered", "partial"))).order_by(PurchaseOrder.expected_on.is_(None), PurchaseOrder.expected_on).limit(6)
        )] if see("purchasing.view") else [],
        "recentPurchases": [purchase_brief(po) for po in db.scalars(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).limit(5))] if see("purchasing.view") else [],
    }


MONTHS = 12


def monthly(db: DB, settings: Settings) -> list[dict]:
    """The last twelve months, the company's own months: units received and units
    issued, and how many orders were made. For the home page's chart and trends."""
    zone = ZoneInfo(settings.org_timezone)
    now = datetime.now(zone)
    keys: list[str] = []
    y, m = now.year, now.month
    for _ in range(MONTHS):
        keys.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    keys.reverse()
    first = datetime(int(keys[0][:4]), int(keys[0][5:]), 1, tzinfo=zone)
    rows = {k: {"month": k, "received": 0, "issued": 0, "orders": 0} for k in keys}
    for at, kind, change in db.execute(
        select(Movement.at, Movement.kind, Movement.on_hand_change).where(Movement.kind.in_(("receive", "issue")), Movement.at >= first)
    ):
        key = (at if at.tzinfo else at.replace(tzinfo=UTC)).astimezone(zone).strftime("%Y-%m")
        if key in rows:
            rows[key]["received" if kind == "receive" else "issued"] += abs(change)
    for (created,) in db.execute(select(Order.created_at).where(Order.created_at >= first)):
        key = (created if created.tzinfo else created.replace(tzinfo=UTC)).astimezone(zone).strftime("%Y-%m")
        if key in rows:
            rows[key]["orders"] += 1
    return list(rows.values())


def purchase_brief(po: PurchaseOrder) -> dict:
    """A purchase order as the home page lists it: its first product, and how many more."""
    first = po.lines[0].product if po.lines else None
    return {**po_brief(po), "firstItem": first.name if first else None, "moreItems": max(0, len(po.lines) - 1)}


# --- reports ---------------------------------------------------------------------------


class Report:
    """One report. `chart`: how the one app charts it ({kind: bar|line, x: column, series: [columns]})."""

    def __init__(self, key: str, title: str, group: str, about: str, build: Callable, *, dated: bool = False, by_warehouse: bool = True, chart: dict | None = None, fixed: bool = False):
        self.key, self.title, self.group, self.about, self.build = key, title, group, about, build
        self.dated, self.by_warehouse, self.chart, self.fixed = dated, by_warehouse, chart, fixed


def bar(x: str, *series: str) -> dict:
    return {"kind": "bar", "x": x, "series": list(series)}


def figure(label: str, value, kind: str = "number", tone: str | None = None) -> dict:
    return {"label": label, "value": value, "kind": kind, **({"tone": tone} if tone else {})}


def total(rows: list[dict], key: str) -> int:
    return sum(int(r.get(key) or 0) for r in rows)


# The headline figures over a report's rows, beside its table (the shared report kit shows them).
SUMMARY: dict[str, Callable[[list[dict]], list[dict]]] = {
    "current": lambda rows: [figure("Products", len({r["sku"] for r in rows})), figure("On hand", total(rows, "onHand")), figure("Available", total(rows, "available"))],
    "valuation": lambda rows: [figure("Value at cost", total(rows, "value"), "money"), figure("Value at selling price", total(rows, "retail"), "money"), figure("Margin on hand", total(rows, "retail") - total(rows, "value"), "money", "good"), figure("Products", len(rows))],
    "aging": lambda rows: [figure("Value", total(rows, "value"), "money"), figure("Products", len(rows))],
    "low": lambda rows: [figure("Products low", len(rows), tone="warn" if rows else None), figure("Suggested to order", total(rows, "suggested"))],
    "out": lambda rows: [figure("Products out", len(rows), tone="bad" if rows else None), figure("Suggested to order", total(rows, "suggested"))],
    "expiring": lambda rows: [figure("Batches", len(rows), tone="warn" if rows else None), figure("Units", total(rows, "onHand")), figure("Value at risk", total(rows, "value"), "money", "bad" if rows else None), figure("Already expired", sum(1 for r in rows if (r.get("daysLeft") or 0) < 0), tone="bad")],
    "registrations": lambda rows: [figure("Need attention", sum(1 for r in rows if r["state"] != "CPR valid"), tone="bad"), figure("Expired", sum(1 for r in rows if r["state"] == "CPR expired"), tone="bad"), figure("Expiring", sum(1 for r in rows if r["state"] == "CPR expiring"), tone="warn"), figure("Valid", sum(1 for r in rows if r["state"] == "CPR valid"), tone="good")],
    "dead": lambda rows: [figure("Products", len(rows), tone="warn" if rows else None), figure("Value tied up", total(rows, "value"), "money", "bad" if rows else None)],
    "purchases": lambda rows: [figure("Lines received", len(rows)), figure("Units", total(rows, "quantity")), figure("Value", total(rows, "total"), "money")],
    "issuance": lambda rows: [figure("Lines issued", len(rows)), figure("Units", total(rows, "quantity")), figure("Value", total(rows, "total"), "money")],
    "adjustments": lambda rows: [figure("Lines", len(rows)), figure("Net units", total(rows, "quantity")), figure("Net value", total(rows, "value"), "money")],
    "fast": lambda rows: [figure("Units issued", total(rows, "issued")), figure("Orders", total(rows, "orders"))],
}


def col(key: str, label: str, kind: str = "text") -> dict:
    """kind: text, number, money, date, datetime, percent."""
    return {"key": key, "label": label, "kind": kind}


class Params:
    def __init__(self, db: DB, settings: Settings, warehouse: str | None, start: date, end: date):
        self.db, self.settings, self.warehouse, self.start, self.end = db, settings, warehouse, start, end
        zone = ZoneInfo(settings.org_timezone)
        # The company's days, as moments: from the start of `start` to the end of `end`.
        self.after = datetime.combine(start, time.min, zone).astimezone(UTC)
        self.before = datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(UTC)


def stocked(db: DB) -> list[Product]:
    return db.scalars(select(Product).where(Product.product_type != "service").order_by(func.lower(Product.name))).all()


def current_inventory(p: Params) -> tuple[list[dict], list[dict]]:
    products = {x.id: x for x in stocked(p.db)}
    whs = {w.id: w for w in p.db.scalars(select(Warehouse))}
    rows = []
    for (pid, wid), lv in sorted(by_warehouse(p.db, list(products), p.warehouse).items(), key=lambda kv: (products[kv[0][0]].name.lower() if kv[0][0] in products else "", whs[kv[0][1]].code if kv[0][1] in whs else "")):
        if pid not in products or wid not in whs:
            continue
        x = products[pid]
        rows.append({"sku": x.sku, "product": x.name, "warehouse": whs[wid].code, "onHand": lv["onHand"], "damaged": lv["damaged"], "reserved": lv["reserved"], "allocated": lv["allocated"], "available": lv["available"], "inTransit": lv["inTransit"], "unit": x.unit_code, "state": state(x, lv)})
    return [col("sku", "SKU"), col("product", "Product"), col("warehouse", "Warehouse"), col("onHand", "On hand", "number"), col("damaged", "Damaged", "number"), col("reserved", "Reserved", "number"), col("allocated", "Allocated", "number"), col("available", "Available", "number"), col("inTransit", "In transit", "number"), col("unit", "Unit"), col("state", "Stock")], rows


def valuation(p: Params):
    products = {x.id: x for x in stocked(p.db)}
    rows = []
    for pid, lv in by_product(p.db, list(products), p.warehouse).items():
        x = products.get(pid)
        if x is None or not lv["onHand"]:
            continue
        rows.append({"sku": x.sku, "product": x.name, "category": category_path(x.category) or "—", "onHand": lv["onHand"], "unitCost": x.cost_price, "value": lv["onHand"] * x.cost_price, "retail": lv["onHand"] * x.selling_price})
    rows.sort(key=lambda r: -r["value"])
    return [col("sku", "SKU"), col("product", "Product"), col("category", "Category"), col("onHand", "On hand", "number"), col("unitCost", "Unit cost", "money"), col("value", "Value at cost", "money"), col("retail", "Value at selling price", "money")], rows


KIND_LABELS = {
    "receive": "Stock in", "issue": "Stock out", "transfer_out": "Transfer out", "transfer_in": "Transfer in", "adjust": "Adjustment",
    "return_in": "Customer return", "return_out": "Returned to supplier", "damage": "Damaged", "write_off": "Written off",
    "expired": "Expired", "lost": "Lost", "reserve": "Reserved", "release": "Released",
}


def movement_rows(p: Params, kinds: tuple[str, ...] | None = None):
    q = select(Movement).where(Movement.at >= p.after, Movement.at < p.before).order_by(Movement.id.desc()).limit(5000)
    if p.warehouse:
        q = q.where(Movement.warehouse_id == p.warehouse)
    if kinds:
        q = q.where(Movement.kind.in_(kinds))
    return [
        {"at": iso(m.at), "kind": KIND_LABELS[m.kind], "sku": m.product.sku, "product": m.product.name, "warehouse": m.warehouse.code, "batch": m.batch.batch_no if m.batch else "", "quantity": m.quantity, "reference": m.reference or "", "user": m.user_name, "note": m.note or ""}
        for m in p.db.scalars(q)
    ]


MOVEMENT_COLUMNS = [col("at", "When", "datetime"), col("kind", "Action"), col("sku", "SKU"), col("product", "Product"), col("warehouse", "Warehouse"), col("batch", "Batch"), col("quantity", "Quantity", "number"), col("reference", "Reference"), col("user", "By"), col("note", "Note")]


def stock_movement(p: Params):
    return MOVEMENT_COLUMNS, movement_rows(p, tuple(k for k in KIND_LABELS if k not in ("reserve", "release")))


def stock_aging(p: Params):
    """How long stock has sat, by when its batch first came in. Unbatched
    stock is aged from the last time it was received."""
    q = select(Stock).where(Stock.on_hand > 0)
    if p.warehouse:
        q = q.where(Stock.warehouse_id == p.warehouse)
    buckets = ("0–30 days", "31–90 days", "91–180 days", "181–365 days", "Over a year")
    rows: dict[str, dict] = {}
    now = datetime.now(UTC)
    for s in p.db.scalars(q):
        if s.batch:
            since_ = s.batch.received_at
        else:
            since_ = p.db.scalar(select(func.max(Movement.at)).where(Movement.product_id == s.product_id, Movement.location_id == s.location_id, Movement.batch_id.is_(None), Movement.on_hand_change > 0)) or now
        age = (now - (since_.replace(tzinfo=UTC) if since_.tzinfo is None else since_)).days
        bucket = buckets[0 if age <= 30 else 1 if age <= 90 else 2 if age <= 180 else 3 if age <= 365 else 4]
        row = rows.setdefault(s.product_id, {"sku": s.product.sku, "product": s.product.name, **{b: 0 for b in buckets}, "oldestDays": 0, "value": 0})
        row[bucket] += s.on_hand
        row["oldestDays"] = max(row["oldestDays"], age)
        row["value"] += s.on_hand * s.product.cost_price
    out = sorted(rows.values(), key=lambda r: -r["oldestDays"])
    return [col("sku", "SKU"), col("product", "Product"), *(col(b, b, "number") for b in buckets), col("oldestDays", "Oldest (days)", "number"), col("value", "Value", "money")], out


def by_state(wanted: str):
    def build(p: Params):
        products = [x for x in stocked(p.db) if x.status == "active"]
        levels = by_product(p.db, [x.id for x in products], p.warehouse)
        rows = []
        for x in products:
            lv = levels.get(x.id, dict(ZERO))
            if state(x, lv) != wanted:
                continue
            rows.append({"sku": x.sku, "product": x.name, "supplier": x.supplier.name if x.supplier else "—", "onHand": lv["onHand"], "held": lv["reserved"] + lv["allocated"], "available": lv["available"], "inTransit": lv["inTransit"], "reorderPoint": x.reorder_point, "suggested": suggested_order(x, lv)})
        return [col("sku", "SKU"), col("product", "Product"), col("supplier", "Usual supplier"), col("onHand", "On hand", "number"), col("held", "Held for orders", "number"), col("available", "Available", "number"), col("inTransit", "In transit", "number"), col("reorderPoint", "Reorder point", "number"), col("suggested", "Suggested order", "number")], rows

    return build


def expiring(p: Params):
    warn = today() + timedelta(days=p.settings.expiry_warning_days)
    q = select(Stock).join(Batch, Stock.batch_id == Batch.id).where(Stock.on_hand > 0, Batch.expires_on.is_not(None), Batch.expires_on <= warn).order_by(Batch.expires_on)
    if p.warehouse:
        q = q.where(Stock.warehouse_id == p.warehouse)
    rows = [
        {"sku": s.product.sku, "product": s.product.name, "batch": s.batch.batch_no, "expiresOn": day(s.batch.expires_on), "daysLeft": (s.batch.expires_on - today()).days, "warehouse": s.location.warehouse.code, "location": s.location.code, "onHand": s.on_hand, "value": s.on_hand * s.product.cost_price}
        for s in p.db.scalars(q)
    ]
    return [col("sku", "SKU"), col("product", "Product"), col("batch", "Batch"), col("expiresOn", "Expires", "date"), col("daysLeft", "Days left", "number"), col("warehouse", "Warehouse"), col("location", "Location"), col("onHand", "On hand", "number"), col("value", "Value", "money")], rows


def registrations(p: Params):
    """Every product that needs a CPR, or has one: its number, validity and state, the ones needing someone first."""
    warn = p.settings.expiry_warning_days
    order = {s: i for i, s in enumerate(cpr.STATES)}
    products = [x for x in p.db.scalars(select(Product).order_by(Product.name)) if cpr.needs_one(x) or x.cpr_number]
    rows = []
    for x in sorted(products, key=lambda x: (order[cpr.state(x, today(), warn)], x.cpr_valid_until or date.max, x.name.lower())):
        c = cpr.out(x, today(), warn)
        rows.append({"sku": x.sku, "product": x.name, "brand": x.brand.name if x.brand else "", "cprNumber": c["number"] or "", "validUntil": c["validUntil"], "daysLeft": c["daysLeft"], "state": c["label"]})
    return [col("sku", "SKU"), col("product", "Product"), col("brand", "Brand"), col("cprNumber", "CPR number"), col("validUntil", "Valid until", "date"), col("daysLeft", "Days left", "number"), col("state", "State")], rows


def purchase_history(p: Params):
    q = select(Receipt).where(Receipt.received_at >= p.after, Receipt.received_at < p.before).order_by(Receipt.received_at.desc())
    if p.warehouse:
        q = q.where(Receipt.warehouse_id == p.warehouse)
    rows = []
    for r in p.db.scalars(q):
        for line in r.lines:
            rows.append({"at": iso(r.received_at), "receipt": r.number, "order": r.order.number if r.order else "", "supplier": r.supplier.name if r.supplier else "", "sku": line.product.sku, "product": line.product.name, "batch": line.batch.batch_no if line.batch else "", "quantity": line.quantity, "unitCost": line.unit_cost, "total": line.quantity * line.unit_cost, "warehouse": r.warehouse.code})
    return [col("at", "Received", "datetime"), col("receipt", "Receipt"), col("order", "PO"), col("supplier", "Supplier"), col("sku", "SKU"), col("product", "Product"), col("batch", "Batch"), col("quantity", "Quantity", "number"), col("unitCost", "Unit cost", "money"), col("total", "Total", "money"), col("warehouse", "Warehouse")], rows


def issuance_history(p: Params):
    q = select(Order).where(Order.status == "issued", Order.issued_at >= p.after, Order.issued_at < p.before).order_by(Order.issued_at.desc())
    if p.warehouse:
        q = q.where(Order.warehouse_id == p.warehouse)
    rows = []
    for o in p.db.scalars(q):
        for line in o.lines:
            rows.append({"at": iso(o.issued_at), "order": o.number, "kind": o.kind.title(), "recipient": o.recipient, "sku": line.product.sku, "product": line.product.name, "batches": ", ".join(f"{x['batchNo']} ×{x['quantity']}" for x in line.picks or [] if x.get("batchNo")), "quantity": line.quantity, "total": line.quantity * line.unit_price, "warehouse": o.warehouse.code})
    return [col("at", "Issued", "datetime"), col("order", "Order"), col("kind", "Kind"), col("recipient", "For"), col("sku", "SKU"), col("product", "Product"), col("batches", "Batches"), col("quantity", "Quantity", "number"), col("total", "Value", "money"), col("warehouse", "Warehouse")], rows


def warehouse_inventory(p: Params):
    whs = p.db.scalars(select(Warehouse).order_by(Warehouse.code)).all()
    products = {x.id: x for x in stocked(p.db)}
    totals: dict[str, dict] = {w.id: {"warehouse": f"{w.code} · {w.name}", "products": 0, "onHand": 0, "damaged": 0, "held": 0, "available": 0, "inTransit": 0, "value": 0, "low": 0} for w in whs}
    for (pid, wid), lv in by_warehouse(p.db, list(products)).items():
        row = totals.get(wid)
        if row is None or pid not in products:
            continue
        row["products"] += 1 if lv["onHand"] else 0
        row["onHand"] += lv["onHand"]
        row["damaged"] += lv["damaged"]
        row["held"] += lv["reserved"] + lv["allocated"]
        row["available"] += lv["available"]
        row["inTransit"] += lv["inTransit"]
        row["value"] += lv["onHand"] * products[pid].cost_price
        row["low"] += 1 if state(products[pid], lv) in ("low", "out") else 0
    return [col("warehouse", "Warehouse"), col("products", "Products", "number"), col("onHand", "On hand", "number"), col("damaged", "Damaged", "number"), col("held", "Held for orders", "number"), col("available", "Available", "number"), col("inTransit", "Coming in", "number"), col("value", "Value", "money"), col("low", "Low or out here", "number")], list(totals.values())


def adjustments_report(p: Params):
    q = select(AdjustmentLine, Adjustment).join(Adjustment).where(Adjustment.status == "posted", Adjustment.decided_at >= p.after, Adjustment.decided_at < p.before).order_by(Adjustment.decided_at.desc())
    if p.warehouse:
        q = q.where(Adjustment.warehouse_id == p.warehouse)
    rows = [
        {"at": iso(a.decided_at), "number": a.number, "reason": REASON_LABELS[a.reason], "sku": line.product.sku, "product": line.product.name, "batch": line.batch.batch_no if line.batch else "", "quantity": line.quantity, "value": line.quantity * line.product.cost_price, "warehouse": a.warehouse.code, "by": a.created_by.full_name if a.created_by else "", "approvedBy": a.decided_by.full_name if a.decided_by else "", "notes": a.notes or ""}
        for line, a in p.db.execute(q)
    ]
    return [col("at", "Posted", "datetime"), col("number", "Adjustment"), col("reason", "Reason"), col("sku", "SKU"), col("product", "Product"), col("batch", "Batch"), col("quantity", "Quantity", "number"), col("value", "Value", "money"), col("warehouse", "Warehouse"), col("by", "Written by"), col("approvedBy", "Approved by"), col("notes", "Notes")], rows


def variance(p: Params):
    q = select(Count).where(Count.status == "approved", Count.approved_at >= p.after, Count.approved_at < p.before).order_by(Count.approved_at.desc())
    if p.warehouse:
        q = q.where(Count.warehouse_id == p.warehouse)
    rows = []
    for c in p.db.scalars(q):
        for line in c.lines:
            if line.counted is None or line.counted == line.expected:
                continue
            rows.append({"count": c.number, "at": iso(c.approved_at), "warehouse": c.warehouse.code, "sku": line.product.sku, "product": line.product.name, "location": line.location.code, "batch": line.batch.batch_no if line.batch else "", "expected": line.expected, "counted": line.counted, "difference": line.counted - line.expected, "value": (line.counted - line.expected) * line.product.cost_price})
    return [col("count", "Count"), col("at", "Approved", "datetime"), col("warehouse", "Warehouse"), col("sku", "SKU"), col("product", "Product"), col("location", "Location"), col("batch", "Batch"), col("expected", "Expected", "number"), col("counted", "Counted", "number"), col("difference", "Difference", "number"), col("value", "Value", "money")], rows


def product_movement(p: Params):
    q = select(Movement.product_id, Movement.kind, func.sum(Movement.quantity)).where(Movement.at >= p.after, Movement.at < p.before, Movement.kind.not_in(("reserve", "release", "damage"))).group_by(Movement.product_id, Movement.kind)
    if p.warehouse:
        q = q.where(Movement.warehouse_id == p.warehouse)
    agg: dict[str, dict] = defaultdict(lambda: {"in": 0, "out": 0, "transfers": 0, "adjusted": 0})
    for pid, kind, n in p.db.execute(q):
        n = int(n or 0)
        if kind in ("transfer_in", "transfer_out"):
            agg[pid]["transfers"] += n
        elif kind == "adjust":
            agg[pid]["adjusted"] += n
        elif n > 0:
            agg[pid]["in"] += n
        else:
            agg[pid]["out"] += -n
    products = {x.id: x for x in p.db.scalars(select(Product).where(Product.id.in_(list(agg))))}
    levels = by_product(p.db, list(agg), p.warehouse)
    rows = [
        {"sku": products[pid].sku, "product": products[pid].name, "in": a["in"], "out": a["out"], "transfers": a["transfers"], "adjusted": a["adjusted"], "net": a["in"] - a["out"] + a["transfers"] + a["adjusted"], "onHand": levels.get(pid, ZERO)["onHand"]}
        for pid, a in agg.items()
        if pid in products
    ]
    rows.sort(key=lambda r: -(r["in"] + r["out"]))
    return [col("sku", "SKU"), col("product", "Product"), col("in", "In", "number"), col("out", "Out", "number"), col("transfers", "Transfers (net)", "number"), col("adjusted", "Adjusted (net)", "number"), col("net", "Net change", "number"), col("onHand", "On hand now", "number")], rows


def supplier_performance(p: Params):
    suppliers = {s.id: s for s in p.db.scalars(select(Supplier))}
    rows = []
    for sid, perf in performance(p.db).items():
        s = suppliers.get(sid)
        if s is None:
            continue
        rows.append({"supplier": s.name, "orders": perf["orders"], "ordered": perf["ordered"], "received": perf["received"], "fillRate": perf["fillRate"], "onTimeRate": perf["onTimeRate"], "lead": perf["averageLeadDays"], "promised": s.lead_time_days, "spend": perf["spend"]})
    rows.sort(key=lambda r: -r["spend"])
    return [col("supplier", "Supplier"), col("orders", "Orders", "number"), col("ordered", "Units ordered", "number"), col("received", "Units received", "number"), col("fillRate", "Fill rate", "percent"), col("onTimeRate", "On time", "percent"), col("lead", "Average lead time (days)", "number"), col("promised", "Promised lead time (days)", "number"), col("spend", "Received value", "money")], rows


def dead_stock(p: Params):
    """On hand, with nothing going out in the dead-stock window."""
    cutoff = since(p.settings.dead_stock_days)
    last_out = dict(p.db.execute(select(Movement.product_id, func.max(Movement.at)).where(Movement.kind.in_(("issue", "transfer_out"))).group_by(Movement.product_id)).all())
    products = {x.id: x for x in stocked(p.db)}
    rows = []
    for pid, lv in by_product(p.db, list(products), p.warehouse).items():
        if not lv["onHand"] or pid not in products:
            continue
        last = last_out.get(pid)
        last_aware = last.replace(tzinfo=UTC) if last is not None and last.tzinfo is None else last
        if last_aware is not None and last_aware >= cutoff:
            continue
        x = products[pid]
        rows.append({"sku": x.sku, "product": x.name, "onHand": lv["onHand"], "value": lv["onHand"] * x.cost_price, "lastOut": iso(last_aware) if last_aware else "", "days": (datetime.now(UTC) - last_aware).days if last_aware else None})
    rows.sort(key=lambda r: -r["value"])
    return [col("sku", "SKU"), col("product", "Product"), col("onHand", "On hand", "number"), col("value", "Value tied up", "money"), col("lastOut", "Last went out", "datetime"), col("days", "Days since", "number")], rows


def fast_moving(p: Params):
    q = select(Movement.product_id, func.sum(-Movement.quantity), func.count(func.distinct(Movement.reference_id))).where(Movement.kind == "issue", Movement.at >= p.after, Movement.at < p.before).group_by(Movement.product_id)
    if p.warehouse:
        q = q.where(Movement.warehouse_id == p.warehouse)
    days = max(1, (p.end - p.start).days + 1)
    products = {x.id: x for x in stocked(p.db)}
    levels = by_product(p.db, list(products), p.warehouse)
    rows = []
    for pid, units, orders in p.db.execute(q):
        x = products.get(pid)
        if x is None:
            continue
        per_day = int(units or 0) / days
        available = levels.get(pid, ZERO)["available"]
        rows.append({"sku": x.sku, "product": x.name, "issued": int(units or 0), "orders": int(orders or 0), "perDay": round(per_day, 1), "available": available, "cover": round(available / per_day) if per_day else None})
    rows.sort(key=lambda r: -r["issued"])
    return [col("sku", "SKU"), col("product", "Product"), col("issued", "Units issued", "number"), col("orders", "Orders", "number"), col("perDay", "Per day", "number"), col("available", "Available", "number"), col("cover", "Days of cover", "number")], rows[:100]


# --- Zoho-style aggregated reports ----------------------------------------------------------------
# These match what Zoho Inventory offers (Sales by Customer, Sales by Item, etc.): each row is a
# grouping dimension (customer, product, salesperson, vendor) and every other column is a pre-computed
# aggregate — count, total quantity, total value — ready to read without further customization.


def sales_by_customer(p: Params):
    """Like Zoho's 'Sales by Customer': each recipient's order count, quantity, value, and share."""
    q = select(Order).where(Order.status == "issued", Order.issued_at >= p.after, Order.issued_at < p.before)
    if p.warehouse:
        q = q.where(Order.warehouse_id == p.warehouse)
    by: dict[str, dict] = {}
    for o in p.db.scalars(q):
        r = by.setdefault(o.recipient, {"customer": o.recipient, "orders": 0, "items": 0, "quantity": 0, "value": 0})
        r["orders"] += 1
        for line in o.lines:
            r["items"] += 1
            r["quantity"] += line.quantity
            r["value"] += line.quantity * line.unit_price
    rows = sorted(by.values(), key=lambda r: -r["value"])
    grand = sum(r["value"] for r in rows) or 1
    for r in rows:
        r["share"] = round(r["value"] / grand, 4)
    return [col("customer", "Customer"), col("orders", "Order count", "number"), col("items", "Line items", "number"), col("quantity", "Total quantity", "number"), col("value", "Total value", "money"), col("share", "Share of total", "percent")], rows


def sales_by_item(p: Params):
    """Like Zoho's 'Sales by Item': each product issued — quantity, value, average price, share."""
    q = select(Order).where(Order.status == "issued", Order.issued_at >= p.after, Order.issued_at < p.before)
    if p.warehouse:
        q = q.where(Order.warehouse_id == p.warehouse)
    by: dict[str, dict] = {}
    for o in p.db.scalars(q):
        for line in o.lines:
            r = by.setdefault(line.product_id, {"sku": line.product.sku, "product": line.product.name, "orders": 0, "quantity": 0, "value": 0})
            r["orders"] += 1
            r["quantity"] += line.quantity
            r["value"] += line.quantity * line.unit_price
    rows = sorted(by.values(), key=lambda r: -r["value"])
    grand = sum(r["value"] for r in rows) or 1
    for r in rows:
        r["avgPrice"] = round(r["value"] / r["quantity"]) if r["quantity"] else 0
        r["share"] = round(r["value"] / grand, 4)
    return [col("sku", "SKU"), col("product", "Product"), col("orders", "Times ordered", "number"), col("quantity", "Total quantity", "number"), col("avgPrice", "Avg unit price", "money"), col("value", "Total value", "money"), col("share", "Share of total", "percent")], rows


def sales_by_salesperson(p: Params):
    """Like Zoho's 'Sales by Salesperson': each person who issued orders — count, quantity, value."""
    q = select(Order).where(Order.status == "issued", Order.issued_at >= p.after, Order.issued_at < p.before)
    if p.warehouse:
        q = q.where(Order.warehouse_id == p.warehouse)
    by: dict[str, dict] = {}
    for o in p.db.scalars(q):
        name = o.issued_by.full_name if o.issued_by else (o.created_by.full_name if o.created_by else "Unknown")
        uid = o.issued_by_id or o.created_by_id or ""
        r = by.setdefault(uid, {"salesperson": name, "orderCount": 0, "items": 0, "quantity": 0, "value": 0})
        r["orderCount"] += 1
        for line in o.lines:
            r["items"] += 1
            r["quantity"] += line.quantity
            r["value"] += line.quantity * line.unit_price
    rows = sorted(by.values(), key=lambda r: -r["value"])
    return [col("salesperson", "Name"), col("orderCount", "Order count", "number"), col("items", "Line items", "number"), col("quantity", "Total quantity", "number"), col("value", "Total value", "money")], rows


def purchases_by_vendor(p: Params):
    """Like Zoho's 'Purchases by Vendor': each supplier's receipt count, quantity, spend."""
    q = select(Receipt).where(Receipt.received_at >= p.after, Receipt.received_at < p.before)
    if p.warehouse:
        q = q.where(Receipt.warehouse_id == p.warehouse)
    by: dict[str, dict] = {}
    for r in p.db.scalars(q):
        name = r.supplier.name if r.supplier else "No supplier"
        sid = r.supplier_id or ""
        row = by.setdefault(sid, {"vendor": name, "receipts": 0, "purchaseOrders": 0, "items": 0, "quantity": 0, "spend": 0})
        row["receipts"] += 1
        if r.order_id:
            row["purchaseOrders"] += 1  # counts per receipt; duplicates possible but close enough
        for line in r.lines:
            row["items"] += 1
            row["quantity"] += line.quantity
            row["spend"] += line.quantity * line.unit_cost
    rows = sorted(by.values(), key=lambda r: -r["spend"])
    grand = sum(r["spend"] for r in rows) or 1
    for r in rows:
        r["share"] = round(r["spend"] / grand, 4)
    return [col("vendor", "Vendor"), col("receipts", "Receipts", "number"), col("items", "Line items", "number"), col("quantity", "Total quantity", "number"), col("spend", "Total spend", "money"), col("share", "Share of total", "percent")], rows


def purchases_by_item(p: Params):
    """Like Zoho's 'Purchases by Item': each product received — quantity, cost, avg unit cost."""
    q = select(Receipt).where(Receipt.received_at >= p.after, Receipt.received_at < p.before)
    if p.warehouse:
        q = q.where(Receipt.warehouse_id == p.warehouse)
    by: dict[str, dict] = {}
    for rec in p.db.scalars(q):
        for line in rec.lines:
            r = by.setdefault(line.product_id, {"sku": line.product.sku, "product": line.product.name, "receipts": 0, "quantity": 0, "spend": 0})
            r["receipts"] += 1
            r["quantity"] += line.quantity
            r["spend"] += line.quantity * line.unit_cost
    rows = sorted(by.values(), key=lambda r: -r["spend"])
    for r in rows:
        r["avgCost"] = round(r["spend"] / r["quantity"]) if r["quantity"] else 0
    return [col("sku", "SKU"), col("product", "Product"), col("receipts", "Times received", "number"), col("quantity", "Total quantity", "number"), col("avgCost", "Avg unit cost", "money"), col("spend", "Total cost", "money")], rows


def inventory_summary(p: Params):
    """Like Zoho's 'Inventory Summary': each product's opening stock, received, issued, adjusted, closing, and value.
    Opening = closing − received + issued − adjusted, where closing is the current on-hand."""
    products = {x.id: x for x in stocked(p.db)}
    levels = by_product(p.db, list(products), p.warehouse)
    q = select(Movement.product_id, Movement.kind, func.sum(Movement.quantity)).where(
        Movement.at >= p.after, Movement.at < p.before,
        Movement.kind.not_in(("reserve", "release")),
    ).group_by(Movement.product_id, Movement.kind)
    if p.warehouse:
        q = q.where(Movement.warehouse_id == p.warehouse)
    moves: dict[str, dict] = defaultdict(lambda: {"received": 0, "issued": 0, "adjusted": 0, "transferred": 0})
    for pid, kind, n in p.db.execute(q):
        n = int(n or 0)
        if kind == "receive":
            moves[pid]["received"] += n
        elif kind == "issue":
            moves[pid]["issued"] += abs(n)
        elif kind == "adjust":
            moves[pid]["adjusted"] += n
        elif kind in ("transfer_in", "transfer_out"):
            moves[pid]["transferred"] += n
        elif kind in ("damage", "write_off", "lost", "expired", "return_in", "return_out"):
            moves[pid]["adjusted"] += n
    rows = []
    for pid, x in products.items():
        closing = levels.get(pid, ZERO)["onHand"]
        m = moves.get(pid, {"received": 0, "issued": 0, "adjusted": 0, "transferred": 0})
        opening = closing - m["received"] + m["issued"] - m["adjusted"] - m["transferred"]
        if not (opening or closing or m["received"] or m["issued"]):
            continue
        rows.append({"sku": x.sku, "product": x.name, "opening": opening, "received": m["received"], "issued": m["issued"], "adjusted": m["adjusted"], "closing": closing, "value": closing * x.cost_price})
    rows.sort(key=lambda r: r["product"].lower())
    return [col("sku", "SKU"), col("product", "Product"), col("opening", "Opening stock", "number"), col("received", "Received", "number"), col("issued", "Issued", "number"), col("adjusted", "Adjusted", "number"), col("closing", "Closing stock", "number"), col("value", "Closing value", "money")], rows


def committed_stock(p: Params):
    """Like Zoho's 'Committed Stock Details': products with stock committed to open orders — reserved, allocated, by whom."""
    q = select(Order).where(Order.status.in_(("confirmed", "picking")))
    if p.warehouse:
        q = q.where(Order.warehouse_id == p.warehouse)
    by: dict[str, dict] = {}
    for o in p.db.scalars(q):
        for line in o.lines:
            r = by.setdefault(line.product_id, {"sku": line.product.sku, "product": line.product.name, "orders": 0, "committed": 0, "value": 0, "customers": set()})
            r["orders"] += 1
            r["committed"] += line.quantity
            r["value"] += line.quantity * line.unit_price
            r["customers"].add(o.recipient)
    products_map = {x.id: x for x in stocked(p.db)}
    product_levels = by_product(p.db, list(by), p.warehouse)
    rows = []
    for pid, r in by.items():
        lv = product_levels.get(pid, ZERO)
        rows.append({"sku": r["sku"], "product": r["product"], "orders": r["orders"], "customers": len(r["customers"]), "committed": r["committed"], "available": lv["available"], "onHand": lv["onHand"], "value": r["value"]})
    rows.sort(key=lambda r: -r["committed"])
    return [col("sku", "SKU"), col("product", "Product"), col("orders", "Open orders", "number"), col("customers", "Customers", "number"), col("committed", "Committed qty", "number"), col("onHand", "On hand", "number"), col("available", "Available", "number"), col("value", "Committed value", "money")], rows


def batch_summary(p: Params):
    """Like Zoho's 'Batch Details': each batch with its product, manufacturing/expiry dates, status, and stock."""
    q = select(Stock).join(Batch, Stock.batch_id == Batch.id).where(Stock.on_hand > 0)
    if p.warehouse:
        q = q.where(Stock.warehouse_id == p.warehouse)
    by: dict[str, dict] = {}
    for s in p.db.scalars(q):
        b = s.batch
        r = by.setdefault(b.id, {"sku": s.product.sku, "product": s.product.name, "batch": b.batch_no, "manufactured": day(b.manufactured_on) if b.manufactured_on else "", "expires": day(b.expires_on) if b.expires_on else "", "status": "Expired" if b.expires_on and b.expires_on < today() else ("Expiring" if b.expires_on and (b.expires_on - today()).days <= p.settings.expiry_warning_days else "Active"), "warehouses": set(), "onHand": 0, "value": 0})
        r["onHand"] += s.on_hand
        r["value"] += s.on_hand * s.product.cost_price
        r["warehouses"].add(s.location.warehouse.code)
    rows = []
    for r in by.values():
        rows.append({**r, "warehouses": ", ".join(sorted(r["warehouses"]))})
    rows.sort(key=lambda r: (r["status"] != "Expired", r["status"] != "Expiring", r["product"].lower()))
    return [col("sku", "SKU"), col("product", "Product"), col("batch", "Batch"), col("manufactured", "Manufactured", "date"), col("expires", "Expires", "date"), col("status", "Status"), col("warehouses", "Warehouses"), col("onHand", "On hand", "number"), col("value", "Value", "money")], rows


# Summary figures for the new aggregated reports.
SUMMARY.update({
    "sales-by-customer": lambda rows: [figure("Customers", len(rows)), figure("Orders", sum(r["orders"] for r in rows)), figure("Total value", sum(r["value"] for r in rows), "money")],
    "sales-by-item": lambda rows: [figure("Products", len(rows)), figure("Total quantity", sum(r["quantity"] for r in rows)), figure("Total value", sum(r["value"] for r in rows), "money")],
    "sales-by-salesperson": lambda rows: [figure("People", len(rows)), figure("Orders", sum(r["orderCount"] for r in rows)), figure("Total value", sum(r["value"] for r in rows), "money")],
    "purchases-by-vendor": lambda rows: [figure("Vendors", len(rows)), figure("Receipts", sum(r["receipts"] for r in rows)), figure("Total spend", sum(r["spend"] for r in rows), "money")],
    "purchases-by-item": lambda rows: [figure("Products", len(rows)), figure("Total quantity", sum(r["quantity"] for r in rows)), figure("Total spend", sum(r["spend"] for r in rows), "money")],
    "inventory-summary": lambda rows: [figure("Products", len(rows)), figure("Opening", sum(r["opening"] for r in rows)), figure("Received", sum(r["received"] for r in rows)), figure("Issued", sum(r["issued"] for r in rows)), figure("Closing", sum(r["closing"] for r in rows)), figure("Closing value", sum(r["value"] for r in rows), "money")],
    "committed": lambda rows: [figure("Products committed", len(rows)), figure("Committed units", sum(r["committed"] for r in rows)), figure("Committed value", sum(r["value"] for r in rows), "money")],
    "batch-summary": lambda rows: [figure("Batches", len(rows)), figure("Units", sum(r["onHand"] for r in rows)), figure("Value", sum(r["value"] for r in rows), "money"), figure("Expired", sum(1 for r in rows if r["status"] == "Expired"), tone="bad"), figure("Expiring", sum(1 for r in rows if r["status"] == "Expiring"), tone="warn")],
})


REPORTS: tuple[Report, ...] = (
    Report("current", "Current inventory", "Stock", "Every product in every warehouse, with each quantity.", current_inventory),
    Report("valuation", "Inventory valuation", "Stock", "What the stock on hand is worth, at cost and at selling price.", valuation, chart=bar("product", "value", "retail"), fixed=True),
    Report("warehouses", "Warehouse inventory", "Stock", "Each warehouse's totals side by side.", warehouse_inventory, by_warehouse=False, chart=bar("warehouse", "onHand", "available")),
    Report("aging", "Stock aging", "Stock", "How long stock has been sitting, by when it came in.", stock_aging),
    Report("inventory-summary", "Inventory summary", "Stock", "Each product's opening stock, received, issued, adjusted and closing stock for the period.", inventory_summary, dated=True, chart=bar("product", "received", "issued")),
    Report("committed", "Committed stock", "Stock", "Products with stock committed to open orders that haven't shipped.", committed_stock, by_warehouse=True),
    Report("batch-summary", "Batch details", "Stock", "Every batch on hand: product, expiry, status and which warehouses hold it.", batch_summary),
    Report("low", "Low stock", "Attention", "Available at or below the reorder point, with how many to order.", by_state("low")),
    Report("out", "Out of stock", "Attention", "Nothing available, with how many to order.", by_state("out")),
    Report("expiring", "Expiring products", "Attention", "Batches on hand that have expired or expire within the warning window.", expiring, fixed=True),
    Report("registrations", "Product registrations (CPR)", "Attention", "Each product's FDA registration: missing, without a date, expired or expiring first.", registrations, by_warehouse=False, fixed=True),
    Report("dead", "Dead stock", "Attention", "On hand, with nothing issued or transferred out in the dead-stock window.", dead_stock, chart=bar("product", "value")),
    Report("movements", "Stock movement", "Activity", "Every movement in the period.", stock_movement, dated=True, fixed=True),
    Report("product-movement", "Product movement", "Activity", "Each product's ins and outs over the period.", product_movement, dated=True, chart=bar("product", "in", "out")),
    Report("fast", "Fast-moving products", "Activity", "What's issued the most, and how long what's left will last.", fast_moving, dated=True, chart=bar("product", "issued")),
    Report("sales-by-customer", "Sales by customer", "Sales", "Each customer's order count, quantity and value — like Zoho's 'Sales by Customer'.", sales_by_customer, dated=True, chart=bar("customer", "value")),
    Report("sales-by-item", "Sales by item", "Sales", "Each product issued: quantity, average price, value and share of total.", sales_by_item, dated=True, chart=bar("product", "value")),
    Report("sales-by-salesperson", "Sales by salesperson", "Sales", "Each person who issued orders: count, quantity and value.", sales_by_salesperson, dated=True, by_warehouse=False, chart=bar("salesperson", "value")),
    Report("purchases", "Purchase history", "Purchasing", "Everything received in the period.", purchase_history, dated=True),
    Report("purchases-by-vendor", "Purchases by vendor", "Purchasing", "Each supplier's receipt count, quantity and spend — like Zoho's 'Purchases by Vendor'.", purchases_by_vendor, dated=True, chart=bar("vendor", "spend")),
    Report("purchases-by-item", "Purchases by item", "Purchasing", "Each product received: quantity, average cost and total spend.", purchases_by_item, dated=True, chart=bar("product", "spend")),
    Report("suppliers", "Supplier performance", "Purchasing", "Fill rate, on-time deliveries and lead time, per supplier.", supplier_performance, by_warehouse=False, chart=bar("supplier", "fillRate", "onTimeRate")),
    Report("issuance", "Sales and issuance history", "Orders", "Everything issued in the period.", issuance_history, dated=True),
    Report("adjustments", "Inventory adjustments", "Control", "Every posted adjustment in the period, with its reason.", adjustments_report, dated=True, fixed=True),
    Report("variance", "Inventory variance", "Control", "Differences found by counts approved in the period.", variance, dated=True),
)
BY_KEY = {r.key: r for r in REPORTS}


@router.get("/reports")
def list_reports(_: allowed("reports.view")) -> list[dict]:
    return [{"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "byWarehouse": r.by_warehouse, "fixed": r.fixed} for r in REPORTS]


def run(db: DB, settings: Settings, key: str, warehouse: str | None, start: date | None, end: date | None) -> tuple[Report, list[dict], list[dict], Params]:
    report = BY_KEY.get(key)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such report.")
    end = end or today()
    start = start or end - timedelta(days=29)
    if start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The period starts after it ends.")
    params = Params(db, settings, warehouse if report.by_warehouse else None, start, end)
    columns, rows = report.build(params)
    return report, columns, rows, params


@router.get("/reports/{key}")
def read_report(
    _: allowed("reports.view"),
    db: DB,
    settings: SettingsDep,
    key: str,
    warehouse: str | None = Query(None, max_length=36),
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
) -> dict:
    report, columns, rows, params = run(db, settings, key, warehouse, start, end)
    return {
        "key": report.key, "title": report.title, "group": report.group, "about": report.about, "dated": report.dated, "byWarehouse": report.by_warehouse, "fixed": report.fixed,
        "from": day(params.start), "to": day(params.end), "columns": columns, "rows": rows,
        "summary": SUMMARY[report.key](rows) if report.key in SUMMARY else [], "chart": report.chart,
    }


@router.get("/reports/{key}/csv")
def export_report(
    _: allowed("reports.export"),
    db: DB,
    settings: SettingsDep,
    key: str,
    warehouse: str | None = Query(None, max_length=36),
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
) -> Response:
    report, columns, rows, params = run(db, settings, key, warehouse, start, end)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([c["label"] for c in columns])
    for row in rows:
        out = []
        for c in columns:
            value = row.get(c["key"])
            if c["kind"] == "money" and value is not None:
                value = f"{value / 10**settings.org_minor_units:.{settings.org_minor_units}f}"
            elif c["kind"] == "percent" and value is not None:
                value = f"{value * 100:.1f}%"
            # A cell starting with = + - @ would be run as a formula by a spreadsheet.
            if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
                value = "'" + value
            out.append("" if value is None else value)
        writer.writerow(out)
    name = f"{report.key}-{params.start}-{params.end}.csv" if report.dated else f"{report.key}-{params.end}.csv"
    return Response("﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}"'})

