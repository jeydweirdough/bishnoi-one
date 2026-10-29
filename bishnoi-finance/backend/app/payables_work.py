"""Current Payables work and balances. Read-only; posting rules stay in the routers."""

from calendar import monthrange
from datetime import UTC, date
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import Bill, PaymentVoucher
from app.routers.receivables import BUCKETS, bucket_of


def bill_rows(db):
    return list(db.scalars(select(Bill).order_by(Bill.due_date, Bill.no)))


def balance(b, held):
    owed = max(b.payable_centavos - b.paid_centavos, 0) if b.status == "recorded" else 0
    reserved = held.get(b.id, 0) if owed else 0
    return {"owedCentavos": owed, "reservedCentavos": reserved, "availableCentavos": max(owed - reserved, 0)}


def aging(db, on: date, supplier_id=None, bucket=None, current: bool = True):
    """As of the end of `on`, rebuilt from dated bills, payments and voids (app/payables_asof.py).
    Money set aside in unreleased vouchers is today's state, so it shows only for today (`current`)."""
    from app.payables_asof import owed_on
    from app.routers.payables import set_aside

    owed = sorted(owed_on(db, on), key=lambda o: (o.bill.due_date, o.bill.no or 0))
    bills = [o.bill for o in owed]
    held = set_aside(db, [b.id for b in bills]) if current else {}
    suppliers = {}
    for o in owed:
        b = o.bill
        late = max((on - b.due_date).days, 0)
        key = bucket_of(late)
        if (supplier_id and b.supplier_id != supplier_id) or (bucket and key != bucket):
            continue
        reserved = min(held.get(b.id, 0), o.owed_centavos)
        amounts = {"owedCentavos": o.owed_centavos, "reservedCentavos": reserved, "availableCentavos": o.owed_centavos - reserved}
        row = suppliers.setdefault(b.supplier_id, {
            "id": b.supplier_id, "name": b.supplier.company_name or b.supplier.name,
            "owedCentavos": 0, "reservedCentavos": 0, "availableCentavos": 0,
            "buckets": {k: 0 for k, _, _ in BUCKETS}, "oldestDaysLate": 0, "bills": [],
        })
        for field, value in amounts.items():
            row[field] += value
        row["buckets"][key] += amounts["owedCentavos"]
        row["oldestDaysLate"] = max(row["oldestDaysLate"], late)
        row["bills"].append({"id": b.id, "no": b.no, "invoice": b.bill_number, "dueDate": b.due_date.isoformat(),
                             "bucket": key, "daysLate": late, **amounts})
    rows = sorted(suppliers.values(), key=lambda r: (-r["oldestDaysLate"], r["name"].lower()))
    totals = {f: sum(r[f] for r in rows) for f in ("owedCentavos", "reservedCentavos", "availableCentavos")}
    return {"on": on.isoformat(), "suppliers": rows, "totals": totals,
            "billCount": sum(len(r["bills"]) for r in rows),
            "buckets": [{"key": k, "label": label, "amountCentavos": sum(r["buckets"][k] for r in rows)} for k, label, _ in BUCKETS]}


BILL_QUEUES = {
    "outstanding": ("Unpaid posted bills", "Balances"),
    "drafts": ("Draft bills", "Waiting for me"), "returned": ("Bills returned to me", "Waiting for me"),
    "approve": ("Bills I can approve", "Waiting for me"), "check": ("Bills I can check", "Waiting for me"),
    "prepare": ("Bills with money available to prepare", "Waiting for me"),
    "sent_approve": ("My bills waiting for approval", "Sent, waiting on others"),
    "sent_check": ("My bills waiting for the tax check", "Sent, waiting on others"),
    "overdue": ("Overdue", "Due to pay"), "by_15": ("Due today through the 15th", "Due to pay"),
    "month_end": ("Due through month-end", "Due to pay"), "missing": ("Bills missing an invoice attachment", "Documents"),
}
VOUCHER_QUEUES = {"drafts": "My draft vouchers", "returned": "Vouchers returned to me", "release": "Vouchers I can release"}


def filter_bills(rows, user, on, held, queue=None, supplier_id=None, bucket=None):
    from app.access import access_of
    from app.routers.payables import may_bill

    can = access_of(user).can
    out = []
    end = on.replace(day=monthrange(on.year, on.month)[1])
    for b in rows:
        amounts = balance(b, held)
        owing = amounts["owedCentavos"] > 0
        mine = b.submitted_by_id == user.id
        allowed = may_bill(user, b)
        tests = {
            "outstanding": owing,
            "drafts": can("bills.create") and b.status == "draft" and b.stage is None,
            "returned": can("bills.create") and b.status == "draft" and b.stage == "returned" and mine,
            "approve": allowed["canApprove"], "check": allowed["canCheck"],
            "prepare": can("vouchers.view") and can("vouchers.prepare") and amounts["availableCentavos"] > 0,
            "sent_approve": mine and b.status == "draft" and b.stage == "to_approve",
            "sent_check": mine and b.status == "draft" and b.stage == "to_check",
            "overdue": owing and b.due_date < on,
            "by_15": owing and on.day <= 15 and on <= b.due_date <= on.replace(day=15),
            "month_end": owing and max(on, on.replace(day=16)) <= b.due_date <= end,
            "missing": b.status != "void" and not b.files,
        }
        if queue and not tests.get(queue, False):
            continue
        if supplier_id and b.supplier_id != supplier_id:
            continue
        if bucket and (not owing or bucket_of(max((on - b.due_date).days, 0)) != bucket):
            continue
        out.append(b)
    return out


def filter_vouchers(rows, user, queue):
    from app.access import access_of
    from app.routers.vouchers import may as may_voucher

    can = access_of(user).can
    return [v for v in rows if {
        "drafts": can("vouchers.prepare") and v.prepared_by_id == user.id and v.status == "draft",
        "returned": can("vouchers.prepare") and v.prepared_by_id == user.id and v.status == "returned",
        "release": may_voucher(user, v)["canRelease"],
    }.get(queue, False)]


def event_note(record, on, waiting=False):
    kinds = {"submitted", "resubmitted", "approved"} if waiting else {"returned"}
    event = next((e for e in reversed(record.events) if e.kind in kinds), None)
    if not event:
        return None
    days = max((on - event.at.replace(tzinfo=UTC).astimezone(ZoneInfo("Asia/Manila")).date()).days, 0)
    return f"Waiting {days} calendar day(s)" if waiting else f"{event.who}: {event.text or 'Returned for correction'}"


def work(db, user, on):
    from app.access import access_of
    from app.routers.payables import set_aside

    can = access_of(user).can
    sections = []
    report = None
    if can("bills.view"):
        rows = bill_rows(db)
        held = set_aside(db, [b.id for b in rows])
        report = aging(db, on)
        for key, (label, group) in BILL_QUEUES.items():
            if key == "outstanding":
                continue
            found = filter_bills(rows, user, on, held, queue=key)
            if not found:
                continue
            if key == "month_end":
                label = "Due 16th through month-end" if on.day <= 15 else "Due today through month-end"
            sections.append({"key": f"bills_{key}", "label": label, "group": group, "unit": "bills",
                             "count": len(found), "href": f"/finance/bills?queue={key}",
                             "amountCentavos": sum(balance(b, held)["owedCentavos"] if b.status == "recorded" else b.payable_centavos for b in found),
                             "reservedCentavos": sum(balance(b, held)["reservedCentavos"] for b in found),
                             "availableCentavos": sum(balance(b, held)["availableCentavos"] for b in found),
                             "details": [{"id": b.id, "label": f"Bill {b.no}", "href": f"/finance/bills/{b.id}",
                                          "note": event_note(b, on, key.startswith("sent_"))} for b in sorted(found, key=lambda b: b.events[-1].at if b.events else b.created_at)[:5]]})
    if can("vouchers.view"):
        rows = list(db.scalars(select(PaymentVoucher).order_by(PaymentVoucher.updated_at)))
        for key, label in VOUCHER_QUEUES.items():
            found = filter_vouchers(rows, user, key)
            if found:
                sections.append({"key": f"vouchers_{key}", "label": label, "group": "Waiting for me", "unit": "vouchers",
                                 "count": len(found), "href": f"/finance/vouchers?queue={key}",
                                 "amountCentavos": sum(v.total_centavos for v in found), "reservedCentavos": 0, "availableCentavos": 0,
                                 "details": [{"id": v.id, "label": v.number, "href": f"/finance/vouchers/{v.id}",
                                              "note": event_note(v, on)} for v in found[:5]]})
    return {"on": on.isoformat(), "queues": sections, "aging": report}
