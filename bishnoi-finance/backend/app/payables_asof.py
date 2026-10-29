"""What was owed to each supplier at the end of a given day, rebuilt from dated events
(as app/receivables_asof.py does for customers; built 2026-10-29).

A bill's `paid_centavos` and `status` say where it stands now; a later payment or a
void would change a past day's figure if those were used. So a past day is rebuilt
from the same dates the ledger posts:

- the bill, on its bill date (routers/payables.py clear, or an import);
- each payment, on the voucher's paid-on date (routers/vouchers.py release);
- a void of either, on the date of the entry that reverses it (both voids post a
  reversal pointing at the original entry, dated the day they were voided).

So at the end of a day a bill is owed if it's dated on or before it, its entry wasn't
reversed by then, and the payments made by then (less those already reversed) don't
cover it. Drafts never reached the ledger and never count. Today's figure equals the
current one, since bills and payments can't be dated in the future.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import Bill, JournalEntry, PaymentVoucher, VoucherLine


@dataclass(frozen=True)
class OwedBill:
    bill: Bill
    paid_centavos: int  # paid by the end of the day
    owed_centavos: int


def _reversed_on():
    """Each reversed entry and the date it was reversed (its earliest reversal)."""
    return (select(JournalEntry.reverses_id.label("entry_id"), func.min(JournalEntry.entry_date).label("on"))
            .where(JournalEntry.reverses_id.is_not(None)).group_by(JournalEntry.reverses_id).subquery())


def owed_on(db: Session, on: date) -> list[OwedBill]:
    voucher_reversed, bill_reversed = aliased(_reversed_on()), aliased(_reversed_on())
    paid = (
        select(VoucherLine.bill_id, func.sum(VoucherLine.amount_centavos).label("paid"))
        .join(PaymentVoucher, PaymentVoucher.id == VoucherLine.voucher_id)
        .outerjoin(voucher_reversed, voucher_reversed.c.entry_id == PaymentVoucher.entry_id)
        .where(PaymentVoucher.status.in_(("released", "void")), PaymentVoucher.entry_id.is_not(None), PaymentVoucher.paid_on <= on,
               or_(voucher_reversed.c.on.is_(None), voucher_reversed.c.on > on))
        .group_by(VoucherLine.bill_id)
        .subquery()
    )
    paid_then = func.coalesce(paid.c.paid, 0)
    rows = db.execute(
        select(Bill, paid_then)
        .outerjoin(paid, paid.c.bill_id == Bill.id)
        .outerjoin(bill_reversed, bill_reversed.c.entry_id == Bill.entry_id)
        .where(Bill.status.in_(("recorded", "void")), Bill.entry_id.is_not(None), Bill.bill_date <= on,
               or_(bill_reversed.c.on.is_(None), bill_reversed.c.on > on), paid_then < Bill.payable_centavos)
    ).all()
    return [OwedBill(b, int(p), b.payable_centavos - int(p)) for b, p in rows]


def total_owed_on(db: Session, on: date) -> int:
    return sum(o.owed_centavos for o in owed_on(db, on))
