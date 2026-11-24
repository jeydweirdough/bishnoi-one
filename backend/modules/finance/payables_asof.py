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
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from modules.finance.models import Bill, JournalEntry, PaymentVoucher, VendorCredit, VendorCreditAllocation, VoucherLine
from modules.finance.settlements import bill_settled_map


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
    voucher_active = or_(
        PaymentVoucher.status == "released",
        and_(PaymentVoucher.status == "void", voucher_reversed.c.on > on),
    )
    paid = (
        select(VoucherLine.bill_id, func.sum(VoucherLine.amount_centavos).label("paid"))
        .join(PaymentVoucher, PaymentVoucher.id == VoucherLine.voucher_id)
        .outerjoin(voucher_reversed, voucher_reversed.c.entry_id == PaymentVoucher.entry_id)
        .where(voucher_active, PaymentVoucher.entry_id.is_not(None), PaymentVoucher.paid_on <= on)
        .group_by(VoucherLine.bill_id)
        .subquery()
    )
    paid_then = func.coalesce(paid.c.paid, 0)
    # Pre-2026 opening AP bills have no individual entry_id (their balance sits in the Dec 31 opening JE),
    # while a voided bill with no reversal entry (cancelled at source) must not stay owed forever.
    bill_active = or_(
        Bill.status == "recorded",
        and_(Bill.status == "void", bill_reversed.c.on > on),
    )
    rows = db.execute(
        select(Bill, paid_then)
        .outerjoin(paid, paid.c.bill_id == Bill.id)
        .outerjoin(bill_reversed, bill_reversed.c.entry_id == Bill.entry_id)
        .where(bill_active, Bill.bill_date <= on, paid_then < Bill.payable_centavos)
    ).all()
    after = datetime.combine(on + timedelta(days=1), time.min, UTC)
    settled_map = bill_settled_map(db, [b.id for b, _ in rows], on=on, after=after)
    out: list[OwedBill] = []
    for b, p in rows:
        settled = int(p) + settled_map.get(b.id, 0)
        if settled < b.payable_centavos:
            out.append(OwedBill(b, settled, b.payable_centavos - settled))
    return out


def _unapplied_vendor_credits_on(db: Session, on: date) -> int:
    vc_reversed = aliased(_reversed_on())
    active_vc = or_(VendorCredit.status == "recorded", and_(VendorCredit.status == "void", vc_reversed.c.on > on))
    vcs = list(
        db.scalars(
            select(VendorCredit)
            .outerjoin(vc_reversed, vc_reversed.c.entry_id == VendorCredit.entry_id)
            .where(active_vc, VendorCredit.credit_date <= on)
        )
    )
    if not vcs:
        return 0
    after = datetime.combine(on + timedelta(days=1), time.min, UTC)
    allocs = dict(
        db.execute(
            select(VendorCreditAllocation.vendor_credit_id, func.sum(VendorCreditAllocation.amount_centavos))
            .where(
                VendorCreditAllocation.vendor_credit_id.in_([v.id for v in vcs]),
                VendorCreditAllocation.applied_on <= on,
                or_(VendorCreditAllocation.removed_at.is_(None), VendorCreditAllocation.removed_at >= after),
            )
            .group_by(VendorCreditAllocation.vendor_credit_id)
        ).all()
    )
    return sum(max(0, v.credit_centavos - int(allocs.get(v.id, 0) or 0)) for v in vcs)


def total_owed_on(db: Session, on: date) -> int:
    return sum(o.owed_centavos for o in owed_on(db, on)) - _unapplied_vendor_credits_on(db, on)
