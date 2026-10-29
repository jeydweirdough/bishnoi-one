"""The journal: posting balanced entries, and the entries each fund step makes.

What a marketing request posts, with the accounts from nbfi_ledger_settings:

    released          Dr Advances to employees      Cr Cash / Bank / E-wallet
    reviewed          Dr each category's expense    Cr Advances (up to what was released)
                                                    Cr Due to employees (anything over)
    unused funds back        Dr Cash / Bank / E-wallet     Cr Advances
    reimbursed        Dr Due to employees           Cr Cash / Bank / E-wallet

Only covered receipts are expensed. What was spent on the person's own, or
refused, stays in Advances until it comes back as unused funds, so once a request
is closed its Advances balance is zero.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.locks import lock_series
from app.models import Account, FundRequest, JournalEntry, JournalLine, LedgerSettings


@dataclass
class Leg:
    account: Account | None
    debit: int = 0
    credit: int = 0
    description: str | None = None


def next_number(db: Session, on: date) -> str:
    prefix = f"JE-{on:%Y%m}-"
    lock_series(db, prefix)  # two entries saved at once never read the same "highest so far"
    last = db.scalar(select(func.max(JournalEntry.number)).where(JournalEntry.number.like(f"{prefix}%")))
    return f"{prefix}{(int(last.rsplit('-', 1)[1]) + 1 if last else 1):04d}"


def post(db: Session, on: date, memo: str, legs: list[Leg], who: str, *, reference: str | None = None, source: str = "manual",
         fund: FundRequest | None = None, reverses: JournalEntry | None = None, waits: bool = False, by_id: str | None = None) -> JournalEntry:
    """A balanced entry, posted. Legs of zero are left out; a leg with no
    account (a posting account nobody set) refuses the whole entry, so the
    step it belongs to doesn't happen either. `waits`: typed by hand, so it
    counts only once someone else approves it (app/routers/ledger.py)."""
    # The books closed up to a day (step 16e): nothing is posted on or before it, not even a reversal.
    lock = settings(db).locked_until
    if lock is not None and on <= lock:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The books are closed up to {lock:%d %b %Y}. Date it after that, or ask the Finance Head to open the period.")
    legs = [leg for leg in legs if leg.debit or leg.credit]
    missing = [leg for leg in legs if leg.account is None]
    if missing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A default account is not set. Set it under Accounting → Default accounts, then try again.")
    debits, credits = sum(leg.debit for leg in legs), sum(leg.credit for leg in legs)
    if not legs or debits != credits:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Total debits must equal total credits, and both must be greater than zero.")
    entry = JournalEntry(
        number=next_number(db, on), entry_date=on, memo=memo[:300], reference=reference, source=source,
        fund_request_id=fund.id if fund else None, reverses_id=reverses.id if reverses else None, posted_by=who[:120],
        status="waiting" if waits else "approved", posted_by_id=by_id,
    )
    for i, leg in enumerate(legs):
        entry.lines.append(JournalLine(position=i, account_id=leg.account.id, debit_centavos=leg.debit, credit_centavos=leg.credit, description=leg.description))
    db.add(entry)
    db.flush()
    if reverses is not None:
        reverses.reversed_by_id = entry.id
    if fund is not None:
        # Its list of entries was read before this one existed.
        db.expire(fund, ["entries"])
    return entry


def settings(db: Session) -> LedgerSettings:
    found = db.get(LedgerSettings, 1)
    if found is None:  # made by the migration; this is only a safety net
        found = LedgerSettings(id=1)
        db.add(found)
        db.flush()
    return found


def account(db: Session, account_id: str | None) -> Account | None:
    return db.get(Account, account_id) if account_id else None


def money_account(db: Session, method: str) -> Account | None:
    s = settings(db)
    return account(db, {"cash": s.cash_account_id, "bank": s.bank_account_id, "ewallet": s.ewallet_account_id, "check": s.check_account_id}.get(method))


# --- what each fund step posts -----------------------------------------------------------------


def post_release(db: Session, r: FundRequest, on: date, who: str) -> JournalEntry:
    advances = account(db, settings(db).advances_account_id)
    amount = r.released_centavos or 0
    return post(db, on, f"{r.number}: cash advance to {r.requester_name} ({r.purpose})", [
        Leg(advances, debit=amount),
        Leg(money_account(db, r.release_method or "cash"), credit=amount),
    ], who, reference=r.release_reference, source="fund", fund=r)


def post_check(db: Session, r: FundRequest, on: date, who: str) -> JournalEntry | None:
    """The covered receipts, expensed to their categories' accounts."""
    by_account: dict[str, int] = defaultdict(int)
    names: dict[str, str] = {}
    details: dict[str, set[str]] = defaultdict(set)
    for e in r.expenses:
        if e.accepted is not False and e.category is not None and e.category.covered:
            top = e.category.top
            if top.account_id is None:
                raise HTTPException(status.HTTP_409_CONFLICT, f"The expense category {top.name} has no account. Assign one under Accounting → Expense categories.")
            by_account[top.account_id] += e.amount_centavos
            names[top.account_id] = top.name
            # The sub-categories, as the line's detail: Food's Dining, Snacks.
            details[top.account_id].add(e.category.name if e.category.parent_id else f"{top.name} (general)")
    covered = sum(by_account.values())
    if covered == 0:
        return None
    s = settings(db)
    released = r.released_centavos or 0
    legs = [Leg(account(db, a), debit=amount, description=", ".join(sorted(details[a]))[:200]) for a, amount in sorted(by_account.items(), key=lambda x: names[x[0]])]
    legs.append(Leg(account(db, s.advances_account_id), credit=min(covered, released)))
    legs.append(Leg(account(db, s.due_to_employees_account_id), credit=max(covered - released, 0), description=f"Owed to {r.requester_name}"))
    return post(db, on, f"{r.number}: liquidation of cash advance ({r.requester_name})", legs, who, source="fund", fund=r)


def post_returned(db: Session, r: FundRequest, amount: int, method: str, reference: str | None, on: date, who: str) -> JournalEntry:
    return post(db, on, f"{r.number}: refund of excess cash advance ({r.requester_name})", [
        Leg(money_account(db, method), debit=amount),
        Leg(account(db, settings(db).advances_account_id), credit=amount),
    ], who, reference=reference, source="fund", fund=r)


def post_reimbursed(db: Session, r: FundRequest, amount: int, method: str, reference: str | None, on: date, who: str) -> JournalEntry:
    return post(db, on, f"{r.number}: reimbursement to {r.requester_name}", [
        Leg(account(db, settings(db).due_to_employees_account_id), debit=amount),
        Leg(money_account(db, method), credit=amount),
    ], who, reference=reference, source="fund", fund=r)


# --- as the screens see it ---------------------------------------------------------------------


def account_out(a: Account) -> dict:
    from app.management import term_of  # here: app.management reads the models first

    shown = term_of(a)[0] if a.type in ("asset", "liability") else None
    return {"id": a.id, "code": a.code, "name": a.name, "type": a.type, "description": a.description, "isActive": a.is_active, "parentId": a.parent_id,
            "term": a.term, "termShown": shown, "costBehaviour": a.cost_behaviour, "reportTag": a.report_tag}


def entry_out(e: JournalEntry) -> dict:
    return {
        "id": e.id,
        "number": e.number,
        "date": e.entry_date.isoformat(),
        "memo": e.memo,
        "reference": e.reference,
        "source": e.source,
        "fundRequestId": e.fund_request_id,
        "reversesId": e.reverses_id,
        "reversedById": e.reversed_by_id,
        "postedBy": e.posted_by,
        "status": e.status,
        "decidedBy": e.decided_by,
        "decidedAt": e.decided_at.isoformat() if e.decided_at else None,
        "rejectedReason": e.rejected_reason,
        "lines": [
            {
                "account": {"id": ln.account.id, "code": ln.account.code, "name": ln.account.name},
                "debitCentavos": ln.debit_centavos,
                "creditCentavos": ln.credit_centavos,
                "description": ln.description,
            }
            for ln in e.lines
        ],
        "totalCentavos": sum(ln.debit_centavos for ln in e.lines),
    }
