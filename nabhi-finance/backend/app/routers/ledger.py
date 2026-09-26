"""The ledger: the chart of accounts, the journal, and what they add up to.

- /finance/ledger/accounts: the chart. Admins add and change accounts; an
  account with entries keeps its type.
- /finance/ledger/posting: which accounts the fund steps post to (admins).
- /finance/ledger/entries: the journal, newest first. Anyone in Finance
  writes a manual journal (debits = credits) or reverses an entry; nobody
  edits or deletes one.
- /finance/ledger/accounts/{id}: one account's lines with a running balance.
- /finance/ledger/trial-balance: every account's debits, credits and balance
  up to a day.

Balances are on each type's normal side: assets and expenses grow with
debits; liabilities, equity and income with credits.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, or_, select

from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.ledger import Leg, account_out, entry_out, post, settings as posting_settings
from app.models import ACCOUNT_TYPES, Account, JournalEntry, JournalLine
from app.routers.funds import today
from app.routers.tax import Api, field_error

router = APIRouter(prefix="/finance/ledger", tags=["ledger"])

DEBIT_NORMAL = {"asset", "expense"}
TYPE_LABELS = {"asset": "Asset", "liability": "Liability", "equity": "Equity", "income": "Income", "expense": "Expense"}


def balance(type_: str, debit: int, credit: int) -> int:
    return debit - credit if type_ in DEBIT_NORMAL else credit - debit


# --- the chart ---------------------------------------------------------------------------------


@router.get("/accounts")
def list_accounts(user: CurrentUser, db: DB) -> dict:
    items = db.scalars(select(Account).order_by(Account.code)).all()
    return {"items": [account_out(a) for a in items], "types": [{"key": k, "label": v} for k, v in TYPE_LABELS.items()], "canEdit": user.role == "admin"}


class AccountIn(Api):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$")
    name: str = Field(min_length=1, max_length=120)
    type: Literal["asset", "liability", "equity", "income", "expense"]
    description: str | None = Field(None, max_length=300)
    is_active: bool = True


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def add_account(user: AdminUser, db: DB, body: AccountIn) -> dict:
    if db.scalar(select(Account.id).where(func.upper(Account.code) == body.code.upper())):
        raise field_error("code", "This account code is already in use.")
    a = Account(**body.model_dump())
    db.add(a)
    db.commit()
    return account_out(a)


@router.put("/accounts/{account_id}")
def change_account(user: AdminUser, db: DB, account_id: str, body: AccountIn) -> dict:
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such account.")
    if db.scalar(select(Account.id).where(func.upper(Account.code) == body.code.upper(), Account.id != a.id)):
        raise field_error("code", "This account code is already in use.")
    if body.type != a.type and db.scalar(select(JournalLine.id).where(JournalLine.account_id == a.id).limit(1)):
        raise field_error("type", "This account has journal entries, so its type cannot change. Create a new account instead.")
    for k, v in body.model_dump().items():
        setattr(a, k, v)
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
def read_posting(user: CurrentUser, db: DB) -> dict:
    return posting_out(db, user.role == "admin")


class PostingIn(Api):
    accounts: dict[str, str | None]


@router.put("/posting")
def change_posting(user: AdminUser, db: DB, body: PostingIn) -> dict:
    s = posting_settings(db)
    for key, account_id in body.accounts.items():
        if key not in POSTING:
            raise field_error("accounts", f"Unknown default account: {key}.")
        a = db.get(Account, account_id) if account_id else None
        if account_id and (a is None or a.type != POSTING[key][0] or not a.is_active):
            raise field_error(key, f"Select an active {POSTING[key][0]} account.")
        setattr(s, key, account_id)
    db.commit()
    return posting_out(db, True)


# --- the journal -------------------------------------------------------------------------------


@router.get("/entries")
def list_entries(
    user: CurrentUser,
    db: DB,
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
    source: Literal["manual", "fund"] | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    query = select(JournalEntry)
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
    return {"items": [entry_out(e) for e in items]}


@router.get("/entries/{entry_id}")
def read_entry(user: CurrentUser, db: DB, entry_id: str) -> dict:
    e = db.get(JournalEntry, entry_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such entry.")
    return entry_out(e)


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
def add_entry(user: CurrentUser, db: DB, settings: SettingsDep, body: EntryIn) -> dict:
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
    e = post(db, body.entry_date, body.memo, legs, user.full_name, reference=body.reference)
    db.commit()
    return entry_out(e)


class ReverseIn(Api):
    entry_date: date | None = Field(None, alias="date")


@router.post("/entries/{entry_id}/reverse", status_code=status.HTTP_201_CREATED)
def reverse(user: CurrentUser, db: DB, settings: SettingsDep, entry_id: str, body: ReverseIn) -> dict:
    """Undoes an entry with its mirror: the same lines, the sides swapped."""
    e = db.get(JournalEntry, entry_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such entry.")
    if e.reversed_by_id or e.reverses_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This entry has already been reversed, or is itself a reversal.")
    on = body.entry_date or today(settings)
    legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in e.lines]
    back = post(db, on, f"Reversal of {e.number}: {e.memo}", legs, user.full_name, reference=e.reference, source=e.source, reverses=e)
    back.fund_request_id = e.fund_request_id
    db.commit()
    return entry_out(back)


# --- what it adds up to ------------------------------------------------------------------------


@router.get("/accounts/{account_id}")
def account_ledger(
    user: CurrentUser,
    db: DB,
    account_id: str,
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
) -> dict:
    """One account's lines, oldest first, each with the balance after it."""
    a = db.get(Account, account_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such account.")
    lines = select(JournalLine, JournalEntry).join(JournalEntry, JournalEntry.id == JournalLine.entry_id).where(JournalLine.account_id == a.id)
    opening = 0
    if since:
        debit, credit = db.execute(
            select(func.coalesce(func.sum(JournalLine.debit_centavos), 0), func.coalesce(func.sum(JournalLine.credit_centavos), 0))
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalLine.account_id == a.id, JournalEntry.entry_date < since)
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
def trial_balance(user: CurrentUser, db: DB, settings: SettingsDep, until: date | None = Query(None, alias="to")) -> dict:
    on = until or today(settings)
    sums = {
        account_id: (debit, credit)
        for account_id, debit, credit in db.execute(
            select(JournalLine.account_id, func.sum(JournalLine.debit_centavos), func.sum(JournalLine.credit_centavos))
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalEntry.entry_date <= on)
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
    return {
        "to": on.isoformat(),
        "rows": rows,
        "debitCentavos": sum(r["debitCentavos"] for r in rows),
        "creditCentavos": sum(r["creditCentavos"] for r in rows),
        "types": ACCOUNT_TYPES,
    }
