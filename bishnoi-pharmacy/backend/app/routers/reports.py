"""Reports and the dashboard: read-only questions about a stretch of days.

Days are the pharmacy's own (ORG_TIMEZONE), so "sold on the 3rd" means the
3rd at the counter, not on the server's clock.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from zoneinfo import ZoneInfo

from app.access import Can
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


@router.get("/reports/{name}")
def report(
    _: Can("reports.view"),
    db: DB,
    settings: SettingsDep,
    name: Literal["prescriptions", "dispensing", "sales", "usage", "expiry", "stock"],
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
) -> dict:
    start, end = _range(settings, since, until)
    lo, hi = day_start(start, settings), day_start(end + timedelta(days=1), settings)
    out: dict = {"name": name, "from": day(start), "to": day(end)}

    if name == "prescriptions":
        rows = list(db.scalars(select(Prescription).where(Prescription.received_at >= lo, Prescription.received_at < hi)).unique())
        by_status: dict[str, int] = defaultdict(int)
        per_day: dict[str, int] = defaultdict(int)
        prescribers: dict[str, int] = defaultdict(int)
        hours = []
        for rx in rows:
            by_status[rx.status] += 1
            per_day[_local_day(rx.received_at, settings)] += 1
            prescribers[rx.prescriber_name] += 1
            if rx.status == "verified" and rx.checked_at:
                hours.append((as_utc(rx.checked_at) - as_utc(rx.received_at)).total_seconds() / 3600)
        checkers = db.execute(
            select(User.full_name, Prescription.status, func.count())
            .join(User, Prescription.checked_by_id == User.id)
            .where(Prescription.checked_at >= lo, Prescription.checked_at < hi)
            .group_by(User.full_name, Prescription.status)
        ).all()
        by_checker: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for who, st, n in checkers:
            by_checker[who][st] += n
        out |= {
            "received": len(rows),
            "byStatus": dict(by_status),
            "averageHoursToVerify": round(sum(hours) / len(hours), 1) if hours else None,
            "perDay": [{"day": d, "count": per_day.get(d, 0)} for d in _days(start, end)],
            "byChecker": [{"name": who, **counts} for who, counts in sorted(by_checker.items())],
            "topPrescribers": [{"name": n, "count": c} for n, c in sorted(prescribers.items(), key=lambda x: -x[1])[:10]],
        }
    elif name == "dispensing":
        rows = list(db.scalars(select(Dispensing).where(Dispensing.dispensed_at >= lo, Dispensing.dispensed_at < hi)).unique())
        per_day: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        by_pharmacist: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for d in rows:
            units = sum(line.quantity for line in d.lines)
            key = _local_day(d.dispensed_at, settings)
            per_day[key][0] += 1
            per_day[key][1] += units
            who = d.dispensed_by.full_name if d.dispensed_by else "(no longer here)"
            by_pharmacist[who][0] += 1
            by_pharmacist[who][1] += units
        out |= {
            "dispensings": len(rows),
            "units": sum(v[1] for v in per_day.values()),
            "prescriptions": len({d.prescription_id for d in rows}),
            "perDay": [{"day": d, "count": per_day[d][0], "units": per_day[d][1]} for d in _days(start, end)],
            "byPharmacist": [{"name": n, "count": v[0], "units": v[1]} for n, v in sorted(by_pharmacist.items())],
        }
    elif name == "sales":
        sales = list(db.scalars(select(Sale).where(Sale.sold_at >= lo, Sale.sold_at < hi)).unique())
        refunds = db.scalar(select(func.coalesce(func.sum(SaleReturn.refund_centavos), 0)).where(SaleReturn.at >= lo, SaleReturn.at < hi)) or 0
        per_day: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        by_method: dict[str, int] = defaultdict(int)
        by_source: dict[str, int] = defaultdict(int)
        for s in sales:
            key = _local_day(s.sold_at, settings)
            per_day[key][0] += 1
            per_day[key][1] += s.total_centavos
            by_method[s.payment_method] += s.total_centavos
            by_source[s.source] += s.total_centavos
        gross = sum(s.subtotal_centavos for s in sales)
        discounts = sum(s.discount_centavos for s in sales)
        out |= {
            "count": len(sales),
            "grossCentavos": gross,
            "discountCentavos": discounts,
            "refundCentavos": int(refunds),
            "netCentavos": gross - discounts - int(refunds),
            "byPaymentMethod": dict(by_method),
            "bySource": dict(by_source),
            "perDay": [{"day": d, "count": per_day[d][0], "totalCentavos": per_day[d][1]} for d in _days(start, end)],
        }
    elif name == "usage":
        # What went out, net of what came back, per medicine.
        rows = db.execute(
            select(
                SaleLine.medicine_id,
                Sale.source,
                func.sum(SaleLine.quantity - SaleLine.qty_returned),
                func.sum((SaleLine.quantity - SaleLine.qty_returned) * SaleLine.unit_price_centavos),
            )
            .join(Sale, SaleLine.sale_id == Sale.id)
            .where(Sale.sold_at >= lo, Sale.sold_at < hi)
            .group_by(SaleLine.medicine_id, Sale.source)
        ).all()
        usage: dict[str, dict] = {}
        for medicine_id, source, units, value in rows:
            u = usage.setdefault(medicine_id, {"dispensed": 0, "counter": 0, "valueCentavos": 0})
            u["dispensed" if source == "dispensing" else "counter"] += int(units or 0)
            u["valueCentavos"] += int(value or 0)
        medicines = {m.id: m for m in db.scalars(select(Medicine).where(Medicine.id.in_(list(usage)))).unique()} if usage else {}
        items = [
            {"medicine": {"id": mid, "label": medicines[mid].label, "unit": medicines[mid].unit}, **u, "units": u["dispensed"] + u["counter"]}
            for mid, u in usage.items()
        ]
        items.sort(key=lambda x: -x["units"])
        out |= {"items": items}
    elif name == "expiry":
        on = today(settings)
        # Everything still on the shelf that has expired, or will by the day
        # asked for: the warning window ahead, unless another day is chosen.
        window_end = max(until, on) if until else on + timedelta(days=settings.expiry_warning_days)
        batches = list(
            db.scalars(
                select(Batch).where(Batch.qty_on_hand > 0, Batch.expires_on <= window_end).order_by(Batch.expires_on)
            ).unique()
        )
        items = [
            {
                "batchId": b.id,
                "medicine": {"id": b.medicine.id, "label": b.medicine.label, "unit": b.medicine.unit},
                "lotNo": b.lot_no,
                "expiresOn": day(b.expires_on),
                "expired": b.expires_on <= on,
                "qtyOnHand": b.qty_on_hand,
                "valueCentavos": b.qty_on_hand * b.cost_centavos,
                "status": b.status,
            }
            for b in batches
        ]
        out |= {
            "to": day(window_end),
            "items": items,
            "expiredValueCentavos": sum(i["valueCentavos"] for i in items if i["expired"]),
            "expiringValueCentavos": sum(i["valueCentavos"] for i in items if not i["expired"]),
        }
    else:  # stock
        on = today(settings)
        medicines = list(db.scalars(select(Medicine).where(Medicine.status != "discontinued").order_by(func.lower(Medicine.generic_name))).unique())
        ids = [m.id for m in medicines]
        total, usable = on_hand(db, ids), sellable(db, ids, on)
        value = dict(db.execute(select(Batch.medicine_id, func.sum(Batch.qty_on_hand * Batch.cost_centavos)).group_by(Batch.medicine_id)).all())
        moved = dict(
            db.execute(
                select(SaleLine.medicine_id, func.sum(SaleLine.quantity))
                .join(Sale, SaleLine.sale_id == Sale.id)
                .where(Sale.sold_at >= lo, Sale.sold_at < hi)
                .group_by(SaleLine.medicine_id)
            ).all()
        )
        items = [
            {
                "medicine": {"id": m.id, "label": m.label, "unit": m.unit, "code": m.code},
                "onHand": total.get(m.id, 0),
                "available": usable.get(m.id, 0),
                "reorderLevel": m.reorder_level,
                "low": usable.get(m.id, 0) <= m.reorder_level,
                "valueCentavos": int(value.get(m.id) or 0),
                "unitsOut": int(moved.get(m.id) or 0),
            }
            for m in medicines
        ]
        out |= {"items": items, "valueCentavos": sum(i["valueCentavos"] for i in items), "lowCount": sum(1 for i in items if i["low"])}
    return out


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
