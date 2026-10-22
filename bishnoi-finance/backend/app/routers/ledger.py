"""The ledger: the chart of accounts, the journal, and what they add up to.

- /finance/ledger/accounts: the chart. Admins add and change accounts; an
  account with entries keeps its type.
- /finance/ledger/posting: which accounts the fund steps post to (admins).
- /finance/ledger/entries: the journal, newest first. Anyone in Finance
  writes a manual journal (debits = credits) or reverses an entry; nobody
  edits or deletes one. One typed by hand (a journal or a reversal) waits
  until someone who may approve entries, not whoever posted it, approves or
  rejects it; only approved entries count below (decided 2026-10-22).
- /finance/ledger/accounts/{id}: one account's lines with a running balance.
- /finance/ledger/trial-balance: every account's debits, credits and balance
  up to a day.

Balances are on each type's normal side: assets and expenses grow with
debits; liabilities, equity and income with credits.
"""

from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, or_, select, update

from app.access import access_of, permitted
from app.audit import audit
from app.config import Settings
from app.deps import DB, SettingsDep
from app.ledger import Leg, account_out, entry_out, post
from app.ledger import settings as posting_settings
from app.models import ACCOUNT_TYPES, Account, JournalEntry, JournalLine, User
from app.notify import tell, tell_holders
from app.routers.funds import today
from app.routers.tax import Api, field_error

router = APIRouter(prefix="/finance/ledger", tags=["ledger"])

DEBIT_NORMAL = {"asset", "expense"}
TYPE_LABELS = {"asset": "Asset", "liability": "Liability", "equity": "Equity", "income": "Income", "expense": "Expense"}


def balance(type_: str, debit: int, credit: int) -> int:
    return debit - credit if type_ in DEBIT_NORMAL else credit - debit


# --- the chart ---------------------------------------------------------------------------------


@router.get("/accounts")
def list_accounts(user: permitted("accounts.view"), db: DB) -> dict:
    items = db.scalars(select(Account).order_by(Account.code)).all()
    return {"items": [account_out(a) for a in items], "types": [{"key": k, "label": v} for k, v in TYPE_LABELS.items()], "canEdit": access_of(user).can("accounts.manage")}


class AccountIn(Api):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$")
    name: str = Field(min_length=1, max_length=120)
    type: Literal["asset", "liability", "equity", "income", "expense"]
    description: str | None = Field(None, max_length=300)
    is_active: bool = True


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def add_account(user: permitted("accounts.manage"), db: DB, body: AccountIn) -> dict:
    if db.scalar(select(Account.id).where(func.upper(Account.code) == body.code.upper())):
        raise field_error("code", "This account code is already in use.")
    a = Account(**body.model_dump())
    db.add(a)
    db.flush()
    audit(db, user, "account.created", target=f"{a.code} {a.name}", target_type="account", target_id=a.id)
    db.commit()
    return account_out(a)


@router.put("/accounts/{account_id}")
def change_account(user: permitted("accounts.manage"), db: DB, account_id: str, body: AccountIn) -> dict:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such account.")
    if db.scalar(select(Account.id).where(func.upper(Account.code) == body.code.upper(), Account.id != a.id)):
        raise field_error("code", "This account code is already in use.")
    if body.type != a.type and db.scalar(select(JournalLine.id).where(JournalLine.account_id == a.id).limit(1)):
        raise field_error("type", "This account has journal entries, so its type cannot change. Create a new account instead.")
    changes = [k for k, v in body.model_dump().items() if getattr(a, k) != v]
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    audit(db, user, "account.updated", target=f"{a.code} {a.name}", target_type="account", target_id=a.id, fields=changes)
    db.commit()
    return account_out(a)


# --- posting accounts --------------------------------------------------------------------------

POSTING = {
    "advances_account_id": ("asset", "Cash advances to employees"),
    "due_to_employees_account_id": ("liability", "Reimbursements payable to employees"),
    "cash_account_id": ("asset", "Paid in cash"),
    "bank_account_id": ("asset", "Paid by bank transfer"),
    "ewallet_account_id": ("asset", "Paid by e-wallet"),
    "check_account_id": ("asset", "Paid by check"),
    "receivables_account_id": ("asset", "What customers owe on invoices"),
    "sales_account_id": ("income", "Sales on invoices"),
    "output_tax_account_id": ("liability", "Tax on invoices (output VAT)"),
}


def posting_out(db: DB, can_edit: bool) -> dict:
    s = posting_settings(db)
    return {
        "items": [
            {"key": key, "label": label, "type": type_, "account": account_out(a) if (a := db.get(Account, getattr(s, key)) if getattr(s, key) else None) else None}
            for key, (type_, label) in POSTING.items()
        ],
        "canEdit": can_edit,
    }


@router.get("/posting")
def read_posting(user: permitted("accounts.view"), db: DB) -> dict:
    return posting_out(db, access_of(user).can("accounts.manage"))


class PostingIn(Api):
    accounts: dict[str, str | None]


@router.put("/posting")
def change_posting(user: permitted("accounts.manage"), db: DB, body: PostingIn) -> dict:
    s = posting_settings(db)
    for key, account_id in body.accounts.items():
        if key not in POSTING:
            raise field_error("accounts", f"Unknown default account: {key}.")
        a = db.get(Account, account_id) if account_id else None
        if account_id and (a is None or a.type != POSTING[key][0] or not a.is_active):
            raise field_error(key, f"Select an active {POSTING[key][0]} account.")
        setattr(s, key, account_id)
    audit(db, user, "posting.updated", target="Default accounts", target_type="settings", fields=body.accounts.keys())
    db.commit()
    return posting_out(db, True)


# --- the journal -------------------------------------------------------------------------------


@router.get("/entries")
def list_entries(
    user: permitted("journal.view"),
    db: DB,
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
    source: Literal["manual", "fund", "invoice"] | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=500),
    state: Literal["waiting", "approved", "rejected"] | None = Query(None, alias="status"),
) -> dict:
    query = select(JournalEntry)
    if state:
        query = query.where(JournalEntry.status == state)
    if since:
        query = query.where(JournalEntry.entry_date >= since)
    if until:
        query = query.where(JournalEntry.entry_date <= until)
    if source:
        query = query.where(JournalEntry.source == source)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(JournalEntry.number).like(like), func.lower(JournalEntry.memo).like(like), func.lower(JournalEntry.reference).like(like)))
    items = db.scalars(query.order_by(JournalEntry.entry_date.desc(), JournalEntry.number.desc()).limit(limit)).all()
    return {"items": [entry_for(user, e) for e in items]}


def entry_for(user: User, e: JournalEntry) -> dict:
    """The entry, and whether this person may approve or reject it now."""
    may = e.status == "waiting" and e.posted_by_id != user.id and access_of(user).can("journal.approve")
    return entry_out(e) | {"canDecide": may}


@router.get("/entries/{entry_id}")
def read_entry(user: permitted("journal.view"), db: DB, entry_id: str) -> dict:
    e = db.get(JournalEntry, entry_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such entry.")
    return entry_for(user, e)


def peso(centavos: int) -> str:
    return f"₱{centavos / 100:,.2f}"


def waiting_for_approval(db: DB, e: JournalEntry, user: User) -> None:
    """Tell everyone who may approve it, except whoever posted it."""
    total = sum(ln.debit_centavos for ln in e.lines)
    tell_holders(db, "journal.approve", "entry.waiting", f"{user.full_name} posted {e.number}, {peso(total)}: {e.memo}. Waiting for your approval.",
                 link=entry_link(e), not_to=[user.id])


def entry_link(e: JournalEntry) -> str:
    return f"/ledger?q={e.number}#{e.number}"


class LineIn(Api):
    account_id: str
    debit_centavos: int = Field(0, ge=0, lt=10**12)
    credit_centavos: int = Field(0, ge=0, lt=10**12)
    description: str | None = Field(None, max_length=200)


class EntryIn(Api):
    entry_date: date = Field(alias="date")
    memo: str = Field(min_length=1, max_length=300)
    reference: str | None = Field(None, max_length=80)
    lines: list[LineIn] = Field(min_length=2, max_length=100)


@router.post("/entries", status_code=status.HTTP_201_CREATED)
def add_entry(user: permitted("journal.post"), db: DB, settings: SettingsDep, body: EntryIn) -> dict:
    """A manual journal."""
    if body.entry_date > today(settings):
        raise field_error("date", "The entry date cannot be in the future.")
    legs = []
    for i, line in enumerate(body.lines):
        if (line.debit_centavos > 0) == (line.credit_centavos > 0):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "lines", i, "debitCentavos"], "msg": "Enter either a debit or a credit on each line."}])
        a = db.get(Account, line.account_id)
        if a is None or not a.is_active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "lines", i, "accountId"], "msg": "Select an active account."}])
        legs.append(Leg(a, debit=line.debit_centavos, credit=line.credit_centavos, description=line.description))
    e = post(db, body.entry_date, body.memo, legs, user.full_name, reference=body.reference, waits=True, by_id=user.id)
    audit(db, user, "entry.posted", target=e.number, target_type="journal_entry", target_id=e.id)
    waiting_for_approval(db, e, user)
    db.commit()
    return entry_for(user, e)


class ReverseIn(Api):
    entry_date: date | None = Field(None, alias="date")


@router.post("/entries/{entry_id}/reverse", status_code=status.HTTP_201_CREATED)
def reverse(user: permitted("journal.reverse"), db: DB, settings: SettingsDep, entry_id: str, body: ReverseIn) -> dict:
    """Undoes an entry with its mirror: the same lines, the sides swapped."""
    e = db.get(JournalEntry, entry_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such entry.")
    if e.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an approved entry can be reversed. One waiting for approval is rejected instead.")
    if e.reversed_by_id or e.reverses_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This entry has already been reversed, or is itself a reversal.")
    on = body.entry_date or today(settings)
    legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in e.lines]
    # A reversal typed in the journal is a correction by hand: it waits too.
    back = post(db, on, f"Reversal of {e.number}: {e.memo}", legs, user.full_name, reference=e.reference, source=e.source, reverses=e,
                waits=True, by_id=user.id)
    back.fund_request_id = e.fund_request_id
    audit(db, user, "entry.reversed", target=e.number, target_type="journal_entry", target_id=e.id, fields=[back.number])
    waiting_for_approval(db, back, user)
    db.commit()
    return entry_for(user, back)


# --- approving -----------------------------------------------------------------------------------


class RejectIn(Api):
    reason: str = Field(min_length=1, max_length=300)


def at(settings: Settings, moment: datetime) -> str:
    """A time of day as the company reads it, e.g. 10:02 AM."""
    local = (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(ZoneInfo(settings.org_timezone))
    return f"{local:%I:%M %p}".lstrip("0")


def decide(db: DB, settings: Settings, user: User, entry_id: str, to: Literal["approved", "rejected"], reason: str | None = None) -> JournalEntry:
    """Approve or reject an entry still waiting. Two people may click at nearly the
    same moment (Ms. Malou and Ms. Cristal both approve, decided 2026-10-22): the
    change is made only if the entry is still waiting when it's saved, checked in
    the save itself, so the first decision wins and the second is told plainly."""
    e = db.get(JournalEntry, entry_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such entry.")
    if e.status == "waiting" and e.posted_by_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You posted this entry, so someone else approves it.")
    changed = db.execute(
        update(JournalEntry)
        .where(JournalEntry.id == e.id, JournalEntry.status == "waiting", or_(JournalEntry.posted_by_id.is_(None), JournalEntry.posted_by_id != user.id))
        .values(status=to, decided_by=user.full_name[:120], decided_by_id=user.id, decided_at=datetime.now(UTC), rejected_reason=reason)
        .execution_options(synchronize_session=False)
    ).rowcount
    if not changed:
        db.rollback()
        db.refresh(e)
        if e.status == "waiting":  # still waiting, so it was this person's own
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You posted this entry, so someone else approves it.")
        who = "You" if e.decided_by_id == user.id else (e.decided_by or "Someone")
        when = f" at {at(settings, e.decided_at)}" if e.decided_at else ""
        raise HTTPException(status.HTTP_409_CONFLICT, f"{who} already {e.status} this entry{when}. Nothing else was changed.")
    db.refresh(e)
    if to == "rejected" and e.reverses_id:
        # A rejected reversal never happened: the entry it was for can be reversed again.
        original = db.get(JournalEntry, e.reverses_id)
        if original is not None and original.reversed_by_id == e.id:
            original.reversed_by_id = None
    audit(db, user, f"entry.{to}", target=e.number, target_type="journal_entry", target_id=e.id, fields=["reason"] if reason else ())
    said = f"{user.full_name} approved {e.number}: it now counts in the books." if to == "approved" else f"{user.full_name} rejected {e.number}: {reason}"
    tell(db, [e.posted_by_id], f"entry.{to}", said, link=entry_link(e), not_to=[user.id])
    db.commit()
    return e


@router.post("/entries/{entry_id}/approve")
def approve_entry(user: permitted("journal.approve"), db: DB, settings: SettingsDep, entry_id: str) -> dict:
    return entry_for(user, decide(db, settings, user, entry_id, "approved"))


@router.post("/entries/{entry_id}/reject")
def reject_entry(user: permitted("journal.approve"), db: DB, settings: SettingsDep, entry_id: str, body: RejectIn) -> dict:
    if not body.reason.strip():
        raise field_error("reason", "Enter the reason for rejection.")
    return entry_for(user, decide(db, settings, user, entry_id, "rejected", body.reason.strip()))


# --- what it adds up to ------------------------------------------------------------------------


@router.get("/accounts/{account_id}")
def account_ledger(
    user: permitted("journal.view"),
    db: DB,
    account_id: str,
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
) -> dict:
    """One account's lines, oldest first, each with the balance after it."""
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such account.")
    lines = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalLine.account_id == a.id, JournalEntry.status == "approved")
    )
    opening = 0
    if since:
        debit, credit = db.execute(
            select(func.coalesce(func.sum(JournalLine.debit_centavos), 0), func.coalesce(func.sum(JournalLine.credit_centavos), 0))
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalLine.account_id == a.id, JournalEntry.status == "approved", JournalEntry.entry_date < since)
        ).one()
        opening = balance(a.type, debit, credit)
        lines = lines.where(JournalEntry.entry_date >= since)
    if until:
        lines = lines.where(JournalEntry.entry_date <= until)
    running, rows = opening, []
    for ln, e in db.execute(lines.order_by(JournalEntry.entry_date, JournalEntry.number, JournalLine.position)):
        running += balance(a.type, ln.debit_centavos, ln.credit_centavos)
        rows.append({
            "entryId": e.id, "number": e.number, "date": e.entry_date.isoformat(), "memo": e.memo, "description": ln.description,
            "debitCentavos": ln.debit_centavos, "creditCentavos": ln.credit_centavos, "balanceCentavos": running,
        })
    return {"account": account_out(a), "openingCentavos": opening, "lines": rows, "closingCentavos": running}


@router.get("/trial-balance")
def trial_balance(user: permitted("journal.view"), db: DB, settings: SettingsDep, until: date | None = Query(None, alias="to")) -> dict:
    on = until or today(settings)
    sums = {
        account_id: (debit, credit)
        for account_id, debit, credit in db.execute(
            select(JournalLine.account_id, func.sum(JournalLine.debit_centavos), func.sum(JournalLine.credit_centavos))
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalEntry.status == "approved", JournalEntry.entry_date <= on)
            .group_by(JournalLine.account_id)
        )
    }
    rows = []
    for a in db.scalars(select(Account).order_by(Account.code)):
        debit, credit = sums.get(a.id, (0, 0))
        if not debit and not credit:
            continue
        net = debit - credit
        rows.append({"account": account_out(a), "debitCentavos": max(net, 0), "creditCentavos": max(-net, 0), "balanceCentavos": balance(a.type, debit, credit)})
    waiting = db.scalar(select(func.count()).where(JournalEntry.status == "waiting", JournalEntry.entry_date <= on)) or 0
    return {
        "to": on.isoformat(),
        # Entries up to that day still waiting for approval: not in these figures yet.
        "waiting": waiting,
        "rows": rows,
        "debitCentavos": sum(r["debitCentavos"] for r in rows),
        "creditCentavos": sum(r["creditCentavos"] for r in rows),
        "types": ACCOUNT_TYPES,
    }
