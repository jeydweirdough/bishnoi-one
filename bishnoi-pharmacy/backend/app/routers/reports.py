"""Reports and the dashboard: read-only questions about a stretch of days.

Days are the pharmacy's own (ORG_TIMEZONE), so "sold on the 3rd" means the
3rd at the counter, not on the server's clock.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.access import Access, Can, CurrentAccess
from app.api import as_utc, day, day_start, field_error, today
from app.config import Settings
from app.deps import DB, SettingsDep
from app.models import Batch, Dispensing, DispensingLine, Medicine, Prescription, Sale, SaleLine, SaleReturn, User
from app.stock import on_hand, sellable

router = APIRouter(tags=["reports"])


def _range(settings: Settings, since: date | None, until: date | None) -> tuple[date, date]:
    end = until or today(settings)
    start = since or end - timedelta(days=29)
    if start > end:
        raise field_error("from", "The first day comes after the last.")
    if (end - start).days > 366:
        raise field_error("from", "Ask for a year at most.")
    return start, end


def _local_day(moment, settings: Settings) -> str:
    return as_utc(moment).astimezone(ZoneInfo(settings.org_timezone)).date().isoformat()


def _days(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=n)).isoformat() for n in range((end - start).days + 1)]


# --- reports (decided 2026-10-25, benchmarks/surpass.md §11) ------------------------------------
# One registry, each report in a group (Prescriptions, Dispensing, Sales, Inventory) and needing
# Reports plus the permission for its data, drawn by the one app's shared report kit
# (src/platform/reports/):
# - GET /reports: the reports this person may open.
# - GET /reports/{key}?from&to: one report: columns, rows, headline figures, chart.

STATUSES = {"received": "Received", "pending": "Checking", "verified": "Verified", "needs_clarification": "Needs clarification", "rejected": "Rejected"}
METHODS = {"cash": "Cash", "card": "Card", "ewallet": "E-wallet", "other": "Other"}
SOURCES = {"counter": "Counter sale", "dispensing": "Dispensed prescription"}


def col(key: str, label: str, kind: str = "text") -> dict:
    return {"key": key, "label": label, "kind": kind}


def fig(label: str, value, kind: str = "number", tone: str | None = None) -> dict:
    return {"label": label, "value": value, "kind": kind, **({"tone": tone} if tone else {})}


def bar(x: str, *series: str) -> dict:
    return {"kind": "bar", "x": x, "series": list(series)}


@dataclass
class Ctx:
    db: Session
    settings: Settings
    first: date
    last: date
    lo: datetime
    hi: datetime


@dataclass
class Report:
    key: str
    title: str
    group: str
    about: str
    build: Callable[[Ctx], tuple]
    needs: str
    dated: bool = True
    fixed: bool = False


def _received(c: Ctx) -> list[Prescription]:
    return list(c.db.scalars(select(Prescription).where(Prescription.received_at >= c.lo, Prescription.received_at < c.hi)).unique())


def prescriptions_received(c: Ctx):
    rows = _received(c)
    per_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hours = []
    for rx in rows:
        d = per_day[_local_day(rx.received_at, c.settings)]
        d["received"] += 1
        d[rx.status if rx.status in ("verified", "rejected") else "open"] += 1
        if rx.status == "verified" and rx.checked_at:
            hours.append((as_utc(rx.checked_at) - as_utc(rx.received_at)).total_seconds() / 3600)
    out = [{"day": d, "received": per_day[d]["received"], "verified": per_day[d]["verified"], "rejected": per_day[d]["rejected"], "open": per_day[d]["open"]} for d in _days(c.first, c.last)]
    still = sum(r["open"] for r in out)
    return (
        [col("day", "Day", "date"), col("received", "Received", "number"), col("verified", "Verified", "number"), col("rejected", "Rejected", "number"), col("open", "Still open", "number")],
        out,
        [fig("Received", len(rows)), fig("Verified", sum(r["verified"] for r in out), tone="good"), fig("Still open", still, tone="warn" if still else None),
         fig("Average hours to verify", round(sum(hours) / len(hours), 1) if hours else None)],
        bar("day", "received", "verified"),
    )


def prescriptions_by_status(c: Ctx):
    counts: dict[str, int] = defaultdict(int)
    for rx in _received(c):
        counts[rx.status] += 1
    total = sum(counts.values())
    rows = [{"status": label, "count": counts.get(s, 0), "share": counts.get(s, 0) / total if total else 0} for s, label in STATUSES.items()]
    return ([col("status", "Status"), col("count", "Prescriptions", "number"), col("share", "Share", "percent")], rows, [fig("Received", total)], bar("status", "count"))


def prescriptions_by_checker(c: Ctx):
    found = c.db.execute(
        select(User.full_name, Prescription.status, func.count())
        .join(User, Prescription.checked_by_id == User.id)
        .where(Prescription.checked_at >= c.lo, Prescription.checked_at < c.hi)
        .group_by(User.full_name, Prescription.status)
    ).all()
    by: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for who, st, n in found:
        by[who][st] += n
    rows = [{"pharmacist": who, "verified": v["verified"], "clarify": v["needs_clarification"], "rejected": v["rejected"], "checked": sum(v.values())} for who, v in sorted(by.items())]
    return (
        [col("pharmacist", "Pharmacist"), col("checked", "Checked", "number"), col("verified", "Verified", "number"), col("clarify", "Needs clarification", "number"), col("rejected", "Rejected", "number")],
        rows,
        [fig("Checked", sum(r["checked"] for r in rows)), fig("Pharmacists", len(rows))],
        bar("pharmacist", "verified", "rejected"),
    )


def top_prescribers(c: Ctx):
    by: dict[tuple[str, str], int] = defaultdict(int)
    for rx in _received(c):
        by[(rx.prescriber_name, rx.prescriber_clinic or "")] += 1
    rows = [{"prescriber": n, "clinic": cl, "count": k} for (n, cl), k in sorted(by.items(), key=lambda x: (-x[1], x[0][0]))]
    return ([col("prescriber", "Prescriber"), col("clinic", "Clinic"), col("count", "Prescriptions", "number")], rows, [fig("Prescribers", len(rows)), fig("Prescriptions", sum(by.values()))], bar("prescriber", "count") if rows else None)


def _dispensings(c: Ctx) -> list[Dispensing]:
    return list(c.db.scalars(select(Dispensing).where(Dispensing.dispensed_at >= c.lo, Dispensing.dispensed_at < c.hi)).unique())


def dispensing_per_day(c: Ctx):
    rows = _dispensings(c)
    per_day: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for d in rows:
        k = per_day[_local_day(d.dispensed_at, c.settings)]
        k[0] += 1
        k[1] += sum(line.quantity for line in d.lines)
    out = [{"day": d, "count": per_day[d][0], "units": per_day[d][1]} for d in _days(c.first, c.last)]
    return (
        [col("day", "Day", "date"), col("count", "Dispensings", "number"), col("units", "Units", "number")],
        out,
        [fig("Dispensings", len(rows)), fig("Units", sum(r["units"] for r in out)), fig("Prescriptions", len({d.prescription_id for d in rows}))],
        bar("day", "count"),
    )


def dispensing_by_pharmacist(c: Ctx):
    by: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for d in _dispensings(c):
        who = by[d.dispensed_by.full_name if d.dispensed_by else "(no longer here)"]
        who[0] += 1
        who[1] += sum(line.quantity for line in d.lines)
    rows = [{"pharmacist": n, "count": v[0], "units": v[1]} for n, v in sorted(by.items())]
    return ([col("pharmacist", "Pharmacist"), col("count", "Dispensings", "number"), col("units", "Units", "number")], rows, [fig("Dispensings", sum(r["count"] for r in rows)), fig("Pharmacists", len(rows))], bar("pharmacist", "count"))


def _sales(c: Ctx) -> list[Sale]:
    return list(c.db.scalars(select(Sale).where(Sale.sold_at >= c.lo, Sale.sold_at < c.hi)).unique())


def _refunds(c: Ctx) -> int:
    return int(c.db.scalar(select(func.coalesce(func.sum(SaleReturn.refund_centavos), 0)).where(SaleReturn.at >= c.lo, SaleReturn.at < c.hi)) or 0)


def sales_per_day(c: Ctx):
    sales = _sales(c)
    per_day: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for s in sales:
        k = per_day[_local_day(s.sold_at, c.settings)]
        k[0] += 1
        k[1] += s.subtotal_centavos
        k[2] += s.discount_centavos
    out = [{"day": d, "count": per_day[d][0], "gross": per_day[d][1], "discount": per_day[d][2], "total": per_day[d][1] - per_day[d][2]} for d in _days(c.first, c.last)]
    gross, discounts, refunds = sum(r["gross"] for r in out), sum(r["discount"] for r in out), _refunds(c)
    return (
        [col("day", "Day", "date"), col("count", "Sales", "number"), col("gross", "Gross", "money"), col("discount", "Discounts", "money"), col("total", "Total", "money")],
        out,
        [fig("Sales", len(sales)), fig("Gross", gross, "money"), fig("Refunds", refunds, "money", "warn" if refunds else None), fig("Net sales", gross - discounts - refunds, "money", "good")],
        bar("day", "total"),
    )


def _sales_by(attr: str, label: str, words: dict[str, str]):
    def build(c: Ctx):
        by: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for s in _sales(c):
            k = by[getattr(s, attr)]
            k[0] += 1
            k[1] += s.total_centavos
        total = sum(v[1] for v in by.values())
        rows = [{"name": words.get(k, k.title()), "count": v[0], "total": v[1], "share": v[1] / total if total else 0} for k, v in sorted(by.items(), key=lambda x: -x[1][1])]
        return ([col("name", label), col("count", "Sales", "number"), col("total", "Total", "money"), col("share", "Share", "percent")], rows, [fig("Total", total, "money")], bar("name", "total") if rows else None)

    return build


def returns(c: Ctx):
    found = list(c.db.scalars(select(SaleReturn).where(SaleReturn.at >= c.lo, SaleReturn.at < c.hi).order_by(SaleReturn.at)).unique())
    sales = {s.id: s.number for s in c.db.scalars(select(Sale).where(Sale.id.in_([r.sale_id for r in found])))} if found else {}
    rows = [{"date": as_utc(r.at).isoformat(), "number": r.number, "sale": sales.get(r.sale_id, ""), "reason": r.reason, "restocked": "Yes" if r.restocked else "No",
             "method": METHODS.get(r.refund_method or "", ""), "refund": r.refund_centavos} for r in found]
    return (
        [col("date", "When", "datetime"), col("number", "Return"), col("sale", "Sale"), col("reason", "Reason"), col("restocked", "Back on the shelf"), col("method", "Refunded by"), col("refund", "Refund", "money")],
        rows,
        [fig("Returns", len(rows)), fig("Refunded", sum(r["refund"] for r in rows), "money", "warn" if rows else None)],
        None,
    )


def medicine_usage(c: Ctx):
    found = c.db.execute(
        select(SaleLine.medicine_id, Sale.source, func.sum(SaleLine.quantity - SaleLine.qty_returned), func.sum((SaleLine.quantity - SaleLine.qty_returned) * SaleLine.unit_price_centavos))
        .join(Sale, SaleLine.sale_id == Sale.id)
        .where(Sale.sold_at >= c.lo, Sale.sold_at < c.hi)
        .group_by(SaleLine.medicine_id, Sale.source)
    ).all()
    usage: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for mid, source, units, value in found:
        u = usage[mid]
        u[0 if source == "dispensing" else 1] += int(units or 0)
        u[2] += int(value or 0)
    meds = {m.id: m for m in c.db.scalars(select(Medicine).where(Medicine.id.in_(list(usage)))).unique()} if usage else {}
    rows = [{"code": meds[mid].code, "medicine": meds[mid].label, "unit": meds[mid].unit, "dispensed": u[0], "counter": u[1], "units": u[0] + u[1], "value": u[2]} for mid, u in usage.items()]
    rows.sort(key=lambda r: -r["units"])
    return (
        [col("code", "Code"), col("medicine", "Medicine"), col("unit", "Unit"), col("dispensed", "Dispensed", "number"), col("counter", "Over the counter", "number"), col("units", "Units out", "number"), col("value", "Value", "money")],
        rows,
        [fig("Medicines moved", len(rows)), fig("Units out", sum(r["units"] for r in rows)), fig("Value", sum(r["value"] for r in rows), "money")],
        bar("medicine", "units") if rows else None,
    )


def expiry(c: Ctx):
    on = today(c.settings)
    # Still on the shelf and expired, or expiring by the period's last day (the warning window
    # ahead when no later day is asked for).
    until = max(c.last, on + timedelta(days=c.settings.expiry_warning_days))
    batches = list(c.db.scalars(select(Batch).where(Batch.qty_on_hand > 0, Batch.expires_on <= until).order_by(Batch.expires_on)).unique())
    rows = [{"code": b.medicine.code, "medicine": b.medicine.label, "lot": b.lot_no, "expires": day(b.expires_on), "state": "Expired" if b.expires_on <= on else "Expiring",
             "days": (b.expires_on - on).days, "qty": b.qty_on_hand, "value": b.qty_on_hand * b.cost_centavos} for b in batches]
    expired = sum(r["value"] for r in rows if r["state"] == "Expired")
    return (
        [col("code", "Code"), col("medicine", "Medicine"), col("lot", "Lot"), col("expires", "Expires", "date"), col("days", "Days left", "number"), col("state", "State"), col("qty", "On hand", "number"), col("value", "Value at cost", "money")],
        rows,
        [fig("Batches", len(rows)), fig("Expired value", expired, "money", "bad" if expired else None), fig("Expiring value", sum(r["value"] for r in rows) - expired, "money", "warn")],
        None,
    )


def _stock_rows(c: Ctx) -> list[dict]:
    on = today(c.settings)
    meds = list(c.db.scalars(select(Medicine).where(Medicine.status != "discontinued").order_by(func.lower(Medicine.generic_name))).unique())
    ids = [m.id for m in meds]
    total, usable = on_hand(c.db, ids), sellable(c.db, ids, on)
    value = dict(c.db.execute(select(Batch.medicine_id, func.sum(Batch.qty_on_hand * Batch.cost_centavos)).group_by(Batch.medicine_id)).all())
    moved = dict(c.db.execute(select(SaleLine.medicine_id, func.sum(SaleLine.quantity)).join(Sale, SaleLine.sale_id == Sale.id).where(Sale.sold_at >= c.lo, Sale.sold_at < c.hi).group_by(SaleLine.medicine_id)).all())
    return [{"code": m.code, "medicine": m.label, "unit": m.unit, "onHand": total.get(m.id, 0), "available": usable.get(m.id, 0), "reorder": m.reorder_level,
             "short": max(m.reorder_level - usable.get(m.id, 0), 0), "out": int(moved.get(m.id) or 0), "value": int(value.get(m.id) or 0), "low": usable.get(m.id, 0) <= m.reorder_level} for m in meds]


STOCK_COLUMNS = [col("code", "Code"), col("medicine", "Medicine"), col("unit", "Unit"), col("onHand", "On hand", "number"), col("available", "Available", "number"), col("reorder", "Reorder level", "number")]


def stock_on_hand(c: Ctx):
    rows = _stock_rows(c)
    low = sum(1 for r in rows if r["low"])
    return (
        [*STOCK_COLUMNS, col("out", "Units out in the period", "number"), col("value", "Value at cost", "money")],
        [{k: v for k, v in r.items() if k not in ("low", "short")} for r in rows],
        [fig("Medicines", len(rows)), fig("Value at cost", sum(r["value"] for r in rows), "money"), fig("At or below reorder level", low, tone="warn" if low else "good")],
        None,
    )


def low_stock(c: Ctx):
    rows = [{k: v for k, v in r.items() if k not in ("low", "value", "out")} for r in _stock_rows(c) if r["low"]]
    return ([*STOCK_COLUMNS, col("short", "Short by", "number")], rows, [fig("To reorder", len(rows), tone="warn" if rows else "good")], None)


REPORTS: tuple[Report, ...] = (
    Report("prescriptions-received", "Prescriptions received", "Prescriptions", "Prescriptions taken in each day, how many were verified, and how long checking took.", prescriptions_received, "prescriptions.view"),
    Report("prescriptions-by-status", "Prescriptions by status", "Prescriptions", "Prescriptions taken in during the period, where each stands now.", prescriptions_by_status, "prescriptions.view"),
    Report("prescriptions-by-pharmacist", "Prescriptions checked by pharmacist", "Prescriptions", "Who checked the prescriptions in the period, and what they decided.", prescriptions_by_checker, "prescriptions.view"),
    Report("top-prescribers", "Prescriptions by prescriber", "Prescriptions", "The doctors whose prescriptions came in during the period, most first.", top_prescribers, "prescriptions.view"),
    Report("dispensing-per-day", "Dispensing summary", "Dispensing", "Dispensings and units released each day.", dispensing_per_day, "dispensing.view"),
    Report("dispensing-by-pharmacist", "Dispensing by pharmacist", "Dispensing", "Who released the medicines in the period, and how much.", dispensing_by_pharmacist, "dispensing.view"),
    Report("sales-summary", "Sales summary", "Sales", "Sales each day: gross, discounts and total, with the period's refunds and net sales.", sales_per_day, "sales.view"),
    Report("sales-by-payment-method", "Sales by payment method", "Sales", "How customers paid in the period.", _sales_by("payment_method", "Payment method", METHODS), "sales.view"),
    Report("sales-by-source", "Sales by source", "Sales", "Counter sales against dispensed prescriptions.", _sales_by("source", "Source", SOURCES), "sales.view"),
    Report("returns", "Sales returns", "Sales", "Medicines brought back in the period, why, and what was refunded.", returns, "sales.view"),
    Report("medicine-usage", "Medicine usage", "Inventory", "What went out per medicine, net of returns: dispensed and over the counter.", medicine_usage, "stock.view"),
    Report("stock-on-hand", "Stock summary", "Inventory", "Every medicine's stock, what's sellable, and its value at cost.", stock_on_hand, "stock.view", dated=False),
    Report("low-stock", "Medicines to reorder", "Inventory", "Medicines at or below their reorder level, and by how much.", low_stock, "stock.view", dated=False),
    Report("expiry", "Expiring batches", "Inventory", "Batches still on the shelf that have expired, or will within the warning window or by the period's last day.", expiry, "batches.view", dated=False, fixed=True),
)
BY_KEY = {r.key: r for r in REPORTS}


def allowed(r: Report, access: Access) -> bool:
    return access.can("reports.view") and access.can(r.needs)


@router.get("/reports")
def list_reports(access: CurrentAccess) -> list[dict]:
    return [{"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "fixed": r.fixed} for r in REPORTS if allowed(r, access)]


@router.get("/reports/{key}")
def read_report(
    access: CurrentAccess,
    db: DB,
    settings: SettingsDep,
    key: str,
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
) -> dict:
    access.require("reports.view")
    r = BY_KEY.get(key)
    if r is None or not allowed(r, access):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such report.")
    start, end = _range(settings, since, until)
    c = Ctx(db=db, settings=settings, first=start, last=end, lo=day_start(start, settings), hi=day_start(end + timedelta(days=1), settings))
    columns, rows, summary, chart = r.build(c)
    return {"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "fixed": r.fixed, "from": day(start), "to": day(end),
            "filters": [], "columns": columns, "rows": rows, "summary": summary, "chart": chart}


@router.get("/dashboard")
def dashboard(_: Can("dashboard.view"), db: DB, settings: SettingsDep) -> dict:
    """What needs doing now, and how today is going."""
    on = today(settings)
    lo, hi = day_start(on, settings), day_start(on + timedelta(days=1), settings)
    by_status = dict(db.execute(select(Prescription.status, func.count()).group_by(Prescription.status)).all())
    verified = list(db.scalars(select(Prescription).where(Prescription.status == "verified")).unique())
    queue = sum(1 for rx in verified if all(i.qty_dispensed == 0 for i in rx.items))
    partial = sum(1 for rx in verified if any(i.qty_dispensed for i in rx.items) and any(i.remaining for i in rx.items))

    medicines = list(db.scalars(select(Medicine).where(Medicine.status == "active")).unique())
    usable = sellable(db, [m.id for m in medicines], on)
    low = [m for m in medicines if usable.get(m.id, 0) <= m.reorder_level]
    expiring = db.scalar(
        select(func.count()).select_from(Batch).where(
            Batch.qty_on_hand > 0, Batch.status != "recalled", Batch.expires_on > on,
            Batch.expires_on <= on + timedelta(days=settings.expiry_warning_days),
        )
    )
    expired = db.scalar(select(func.count()).select_from(Batch).where(Batch.qty_on_hand > 0, Batch.expires_on <= on))
    held = db.scalar(select(func.count()).select_from(Batch).where(Batch.status == "quarantined"))
    sales_today = db.execute(select(func.count(), func.coalesce(func.sum(Sale.total_centavos), 0)).where(Sale.sold_at >= lo, Sale.sold_at < hi)).one()
    dispensed_today = db.scalar(select(func.count()).select_from(Dispensing).where(Dispensing.dispensed_at >= lo, Dispensing.dispensed_at < hi))
    units_today = db.scalar(
        select(func.coalesce(func.sum(DispensingLine.quantity), 0))
        .join(Dispensing, DispensingLine.dispensing_id == Dispensing.id)
        .where(Dispensing.dispensed_at >= lo, Dispensing.dispensed_at < hi)
    )
    return {
        "today": day(on),
        "prescriptions": {
            "inbox": by_status.get("received", 0),
            "pending": by_status.get("pending", 0),
            "needsClarification": by_status.get("needs_clarification", 0),
        },
        "dispensing": {"queue": queue, "partial": partial, "today": dispensed_today or 0, "unitsToday": int(units_today or 0)},
        "stock": {
            "low": len(low),
            "expiring": expiring or 0,
            "expired": expired or 0,
            "quarantined": held or 0,
            "lowItems": [
                {"id": m.id, "label": m.label, "available": usable.get(m.id, 0), "reorderLevel": m.reorder_level, "unit": m.unit}
                for m in sorted(low, key=lambda m: usable.get(m.id, 0) - m.reorder_level)[:6]
            ],
        },
        "sales": {"count": sales_today[0], "totalCentavos": int(sales_today[1])},
        "expiryWarningDays": settings.expiry_warning_days,
    }
