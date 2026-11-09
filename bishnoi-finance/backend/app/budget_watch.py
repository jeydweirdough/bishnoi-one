"""Over-budget warnings for spending that isn't posted yet (Sir Mel, recording 12, 2026-11-04: "the
system should prompt when spending goes over budget").

A warning, never a block: the budget is a plan, and Malou decides. For each account a bill or
petty cash voucher spends on, in the month it will post (a bill's date; a voucher's date, the
same dates `ledger.post` uses), it adds what the books already show for that account and month
to what this document adds, and compares that with the month's budget (every division's line for
the account together, as the Budget against actual report does, `routers/reports.py`).

Only drafts and documents waiting for a step are checked: once posted, the books already hold
them. Payment vouchers aren't: they pay bills whose spending was counted when the bill posted.
Accounts with no budget for the year give no warning.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session


def fiscal_place(db: Session):
    """For a day: (its fiscal year's last day, the month's place in that year, 0 to 11)."""
    from app.models import TaxProfile

    profile = db.get(TaxProfile, 1)
    end_month = profile.fiscal_month_end if profile else 12

    def where(d: date) -> tuple[date, int]:
        year = d.year if d.month <= end_month else d.year + 1
        index = (d.month - end_month - 1) % 12
        return date(year, end_month, monthrange(year, end_month)[1]), index

    return where


def over_budget(db: Session, on: date, spend: dict[str, int]) -> list[dict]:
    """`spend`: centavos this document adds, by account id. Returns one row per account that would go over its
    budget for `on`'s month, with the budget, what's already posted, this document's part and how far over."""
    from app.bir_reports import balances
    from app.models import Account, Budget

    spend = {k: v for k, v in spend.items() if k and v}
    if not spend:
        return []
    year_end, i = fiscal_place(db)(on)
    budgeted: dict[str, int] = {}
    for b in db.scalars(select(Budget).where(Budget.year_end == year_end, Budget.account_id.in_(list(spend)))):
        budgeted[b.account_id] = budgeted.get(b.account_id, 0) + (b.months[i] if i < len(b.months) else 0)
    if not budgeted:
        return []
    first = on.replace(day=1)
    last = on.replace(day=monthrange(on.year, on.month)[1])
    moves = balances(db, start=first, end=last)
    out = []
    for a in db.scalars(select(Account).where(Account.id.in_(list(budgeted))).order_by(Account.code)):
        d, cr = moves.get(a.id, (0, 0))
        posted = cr - d if a.type == "income" else d - cr
        after = posted + spend[a.id]
        if after > budgeted[a.id]:
            out.append({"accountId": a.id, "code": a.code, "account": a.name, "month": first.isoformat()[:7],
                        "budgetCentavos": budgeted[a.id], "postedCentavos": posted, "thisCentavos": spend[a.id],
                        "overCentavos": after - budgeted[a.id]})
    return out
