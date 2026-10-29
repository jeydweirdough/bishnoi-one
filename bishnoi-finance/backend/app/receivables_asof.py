"""What each customer owed at the end of a given day, rebuilt from dated events.

An invoice's `paid_centavos` and `status` say where it stands now; a later
payment, a payment taken off, or a void would change a past day's figure if
those were used. So a past day is rebuilt from the same dates the ledger posts
(app/routers/invoices.py):

- the sale, on the invoice date (issue);
- each payment, money and withholding, on its paid-on date (record_payment);
- a payment taken off, on the day it was taken off (remove_payment: its
  reversal is dated that day, and `removed_at` records it);
- a void, on the day it was voided (void: its reversal is dated that day, and
  `voided_at` records it).

So at the end of a day an invoice is owed if it's dated on or before it, wasn't
yet voided, and its payments made by then (less those already taken off) don't
cover it. Drafts never reached the ledger and never count. Today's figure is the
same as the current one, since payments can't be dated in the future.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Invoice, InvoicePayment


@dataclass(frozen=True)
class Owed:
    invoice: Invoice
    paid_centavos: int  # paid by the end of the day, withholding included
    owed_centavos: int


def end_of(day: date, zone: ZoneInfo) -> datetime:
    """The first instant after the day, where the organisation is, in UTC: what
    `voided_at` and `removed_at` (saved in UTC) are compared with."""
    return datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)


def owed_on(db: Session, on: date, zone: ZoneInfo) -> list[Owed]:
    after = end_of(on, zone)
    paid = (
        select(InvoicePayment.invoice_id, func.sum(InvoicePayment.amount_centavos + InvoicePayment.cwt_centavos).label("paid"))
        .where(InvoicePayment.paid_on <= on, or_(InvoicePayment.removed_at.is_(None), InvoicePayment.removed_at >= after))
        .group_by(InvoicePayment.invoice_id)
        .subquery()
    )
    issued_then = or_(Invoice.status == "issued", and_(Invoice.status == "void", Invoice.voided_at >= after))
    rows = db.execute(
        select(Invoice, func.coalesce(paid.c.paid, 0))
        .outerjoin(paid, paid.c.invoice_id == Invoice.id)
        .where(issued_then, Invoice.invoice_date <= on, func.coalesce(paid.c.paid, 0) < Invoice.total_centavos)
    ).all()
    return [Owed(inv, int(p), inv.total_centavos - int(p)) for inv, p in rows]


def total_owed_on(db: Session, on: date, zone: ZoneInfo) -> int:
    return sum(o.owed_centavos for o in owed_on(db, on, zone))
