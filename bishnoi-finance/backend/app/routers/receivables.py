"""What customers owe, and for how long (benchmarks E5, a main screen as Marg
has it): every issued invoice not yet paid in full, by customer, in ageing
buckets by how far past its due date it is on the day asked.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.access import permitted
from app.deps import DB, SettingsDep
from app.models import Invoice
from app.routers.funds import today

router = APIRouter(prefix="/finance/receivables", tags=["invoices"])

# (key, label, the most days past due it holds; None: no limit)
BUCKETS = (
    ("current", "Not yet due", 0),
    ("d1_30", "1 to 30 days late", 30),
    ("d31_60", "31 to 60 days late", 60),
    ("d61_90", "61 to 90 days late", 90),
    ("over_90", "Over 90 days late", None),
)


def bucket_of(days_late: int) -> str:
    return next(key for key, _, most in BUCKETS if most is None or days_late <= most)


@router.get("")
def ageing(_: permitted("invoices.view"), db: DB, settings: SettingsDep, on: date | None = Query(None)) -> dict:
    """As of a day (today unless asked): each customer's open invoices, what's
    still owed on each, and how late it is."""
    on = on or today(settings)
    rows = db.scalars(select(Invoice).where(Invoice.status == "issued", Invoice.paid_centavos < Invoice.total_centavos, Invoice.invoice_date <= on)).all()
    customers: dict[str, dict] = {}
    totals = {key: 0 for key, _, _ in BUCKETS}
    for inv in rows:
        due = inv.invoice_date + timedelta(days=inv.terms_days)
        late = max(0, (on - due).days)
        owed = inv.total_centavos - inv.paid_centavos
        key = bucket_of(late)
        c = customers.setdefault(inv.customer_id or f"name:{inv.customer_name.lower()}", {
            "customerId": inv.customer_id, "name": inv.customer_name, "totalCentavos": 0,
            "buckets": {k: 0 for k, _, _ in BUCKETS}, "oldestDaysLate": 0, "invoices": [],
        })
        c["totalCentavos"] += owed
        c["buckets"][key] += owed
        c["oldestDaysLate"] = max(c["oldestDaysLate"], late)
        c["invoices"].append({"id": inv.id, "number": inv.number, "date": inv.invoice_date.isoformat(), "dueDate": due.isoformat(),
                              "daysLate": late, "bucket": key, "totalCentavos": inv.total_centavos, "owedCentavos": owed})
        totals[key] += owed
    ordered = sorted(customers.values(), key=lambda c: (-c["oldestDaysLate"], -c["totalCentavos"]))
    for c in ordered:
        c["invoices"].sort(key=lambda i: -i["daysLate"])
    return {
        "on": on.isoformat(),
        "buckets": [{"key": k, "label": label, "amountCentavos": totals[k]} for k, label, _ in BUCKETS],
        "totalCentavos": sum(totals.values()),
        "customers": ordered,
    }
