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

import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, or_, select, update

from app.access import access_of, permissions_of, permitted
from app.audit import audit
from app.config import Settings
from app.deps import DB, SettingsDep
from app.ledger import Leg, account_out, entry_out, post
from app.ledger import settings as posting_settings
from app.models import ACCOUNT_TYPES, Account, JournalEntry, JournalLine, Notification, User
from app.notify import done, holders, tell
from app.routers.funds import today
from app.signatures import journal_content, sign
from app.routers.tax import Api, field_error
from app.workdays import one_workday_later

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
    # The account it sits under (migration 0017); none: at the top.
    parent_id: str | None = None


def check_parent(db: DB, account_id: str | None, parent_id: str | None) -> None:
    """A parent that exists, and isn't the account itself or one of the accounts under it."""
    if parent_id is None:
        return
    seen = {account_id}
    at = db.get(Account, parent_id)
    if at is None:
        raise field_error("parentId", "There's no such account to put it under.")
    while at is not None:
        if at.id in seen:
            raise field_error("parentId", "An account can't sit under itself or under an account that sits under it.")
        seen.add(at.id)
        at = db.get(Account, at.parent_id) if at.parent_id else None


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def add_account(user: permitted("accounts.manage"), db: DB, body: AccountIn) -> dict:
    if db.scalar(select(Account.id).where(func.upper(Account.code) == body.code.upper())):
        raise field_error("code", "This account code is already in use.")
    check_parent(db, None, body.parent_id)
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
    check_parent(db, a.id, body.parent_id)
    changes = [k for k, v in body.model_dump().items() if getattr(a, k) != v]
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    audit(db, user, "account.updated", target=f"{a.code} {a.name}", target_type="account", target_id=a.id, fields=changes)
    db.commit()
    return account_out(a)


# --- importing a chart (Oojeema's or Zoho's, as CSV) ---------------------------------------------
#
# The screen reads the file in the browser and sends its rows; nothing of the file is kept.
# /check answers what would happen to each row; /import adds the chosen ones, all or none.
# Existing accounts, entries and default accounts are never changed. Decided 2026-10-23
# (Plans/Plan - Suppliers, bills and chart import; Plans/Plan - Import chart of accounts).

# A chart's class (Oojeema's "Class", Zoho's "Account Type"), as one of Finance's five types.
CLASS_TYPES = {
    **dict.fromkeys(("cash", "bank", "current assets", "current asset", "other current asset", "other current assets", "prepaid and other current assets",
                     "inventory", "stock", "input vat", "accounts receivable", "fixed assets", "fixed asset", "noncurrent assets", "non-current assets",
                     "other asset", "other assets", "payment clearing"), "asset"),
    **dict.fromkeys(("current liabilities", "current liability", "noncurrent liabilities", "non-current liabilities", "accounts payable",
                     "credit card", "other current liability", "other liability", "long term liability", "long-term liabilities"), "liability"),
    **dict.fromkeys(("equity",), "equity"),
    **dict.fromkeys(("revenue", "income", "other income", "sales"), "income"),
    **dict.fromkeys(("cost of sales", "cost of goods sold", "operating expenses", "other expenses", "other expense", "expense", "expenses"), "expense"),
}
CODE = re.compile(r"^[A-Za-z0-9.\-]+$")


def type_of(kind: str | None, nature: str | None, statement: str | None) -> str | None:
    """The class, as a type; failing that, an income-statement account by its normal side."""
    found = CLASS_TYPES.get((kind or "").strip().lower())
    if found:
        return found
    if (statement or "").strip().lower() == "income statement":
        side = (nature or "").strip().lower()
        return "income" if side == "credit" else "expense" if side == "debit" else None
    return None


class ImportRowIn(Api):
    code: str | None = Field(None, max_length=60)
    name: str | None = Field(None, max_length=300)
    kind: str | None = Field(None, max_length=80)
    nature: str | None = Field(None, max_length=20)
    statement: str | None = Field(None, max_length=40)
    parent: str | None = Field(None, max_length=300)
    description: str | None = Field(None, max_length=500)


class ImportCheckIn(Api):
    rows: list[ImportRowIn] = Field(min_length=1, max_length=3000)


@router.post("/accounts/import/check")
def check_import(user: permitted("accounts.manage"), db: DB, body: ImportCheckIn) -> dict:
    existing = {a.code.upper(): a for a in db.scalars(select(Account))}
    names_here = {a.name.strip().lower() for a in existing.values()}
    codes_in_file: dict[str, int] = {}
    for r in body.rows:
        if r.code:
            codes_in_file[r.code.strip().upper()] = codes_in_file.get(r.code.strip().upper(), 0) + 1
    names_in_file = {(r.name or "").strip().lower() for r in body.rows if r.name}
    out = []
    for i, r in enumerate(body.rows):
        code, name = (r.code or "").strip(), (r.name or "").strip()
        kind = (r.kind or "").strip() or None
        type_ = type_of(kind, r.nature, r.statement)
        parent = (r.parent or "").strip() or None
        where = "file" if parent and parent.lower() in names_in_file else "chart" if parent and parent.lower() in names_here else None
        # (which field, what's wrong): only a missing type can be put right on the screen.
        problems: list[tuple[str, str]] = []
        if not code:
            problems.append(("code", "No code."))
        elif not CODE.match(code) or len(code) > 20:
            problems.append(("code", "The code has spaces or symbols, or is over 20 characters."))
        elif codes_in_file.get(code.upper(), 0) > 1:
            problems.append(("code", "This code is in the file more than once."))
        if not name:
            problems.append(("name", "No name."))
        elif len(name) > 120:
            problems.append(("name", "The name is over 120 characters."))
        if type_ is None:
            problems.append(("type", f"Finance can't tell the type from “{kind}”: pick one." if kind else "No class: pick a type."))
        here = existing.get(code.upper()) if code else None
        status_ = "here" if here else "problem" if problems else "new"
        note = (f"Already in Finance as {here.code} · {here.name}." if here else " ".join(m for _, m in problems)) or None
        if status_ == "new" and parent and where is None:
            note = f"Its parent “{parent}” isn't in the file or the chart: imported without one."
        out.append({
            "line": i + 1, "code": code, "name": name, "kind": kind, "type": type_, "parent": parent, "parentFound": where,
            "description": (r.description or "").strip() or None, "status": status_, "note": note, "problems": [f for f, _ in problems],
        })
    counts = {k: sum(1 for x in out if x["status"] == k) for k in ("new", "here", "problem")}
    return {"rows": out, "counts": counts, "types": [{"key": k, "label": v} for k, v in TYPE_LABELS.items()]}


class ImportAccountIn(Api):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$")
    name: str = Field(min_length=1, max_length=120)
    type: Literal["asset", "liability", "equity", "income", "expense"]
    description: str | None = Field(None, max_length=300)
    parent: str | None = Field(None, max_length=300)


class ImportIn(Api):
    accounts: list[ImportAccountIn] = Field(min_length=1, max_length=3000)


@router.post("/accounts/import", status_code=status.HTTP_201_CREATED)
def run_import(user: permitted("accounts.manage"), db: DB, body: ImportIn) -> dict:
    """Adds the chosen accounts, all or none: any code already used refuses the lot,
    naming it. Parents are matched by name, to an account in this import or already here."""
    existing = {a.code.upper() for a in db.scalars(select(Account))}
    seen: set[str] = set()
    for i, row in enumerate(body.accounts):
        key = row.code.upper()
        if key in existing or key in seen:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Line {i + 1}: the code {row.code} is already used. Nothing was imported.")
        seen.add(key)
    made = []
    for row in body.accounts:
        a = Account(code=row.code, name=row.name, type=row.type, description=row.description, is_active=True)
        db.add(a)
        made.append((a, row.parent))
    db.flush()
    everything = {a.id: a for a in db.scalars(select(Account))}
    by_name: dict[str, Account] = {}
    for a in everything.values():
        by_name.setdefault(a.name.strip().lower(), a)
    for a, _ in made:  # this import's own names come first
        by_name[a.name.strip().lower()] = a

    def above(p: Account, a: Account) -> bool:
        """Whether a is p, or sits above p: then a can't go under p."""
        at, steps = p, 0
        while at is not None and steps < 50:
            if at.id == a.id:
                return True
            at, steps = everything.get(at.parent_id) if at.parent_id else None, steps + 1
        return steps >= 50

    linked = 0
    for a, parent in made:
        p = by_name.get((parent or "").strip().lower()) if parent else None
        if p is not None and not above(p, a):
            a.parent_id = p.id
            linked += 1
    audit(db, user, "accounts.imported", target=f"{len(made)} accounts", target_type="account")
    db.commit()
    return {"added": len(made), "withParent": linked}


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
    # Supplier bills (2026-10-23): what's owed suppliers, the VAT on purchases, the tax withheld for the BIR.
    "payables_account_id": ("liability", "What's owed suppliers on bills"),
    "input_tax_account_id": ("asset", "VAT on bills (input VAT)"),
    "withholding_account_id": ("liability", "Tax withheld from suppliers (EWT payable)"),
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
    source: Literal["manual", "fund", "invoice", "bill"] | None = None,
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
    # Where each reversal stands, so an entry whose reversal still waits isn't shown as reversed.
    reversals = [e.reversed_by_id for e in items if e.reversed_by_id]
    standing = dict(db.execute(select(JournalEntry.id, JournalEntry.status).where(JournalEntry.id.in_(reversals))).all()) if reversals else {}
    return {"items": [entry_for(user, e, standing.get(e.reversed_by_id)) for e in items]}


def entry_for(user: User, e: JournalEntry, reversal_status: str | None = None) -> dict:
    """The entry, whether this person may approve or reject it now, and where its reversal stands."""
    may = e.status == "waiting" and e.posted_by_id != user.id and access_of(user).can("journal.approve")
    return entry_out(e) | {"canDecide": may, "reversalStatus": reversal_status}


@router.get("/entries/{entry_id}")
def read_entry(user: permitted("journal.view"), db: DB, entry_id: str) -> dict:
    e = db.get(JournalEntry, entry_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such entry.")
    reversal = db.get(JournalEntry, e.reversed_by_id) if e.reversed_by_id else None
    return entry_for(user, e, reversal.status if reversal else None)


def peso(centavos: int) -> str:
    return f"₱{centavos / 100:,.2f}"


def waiting_text(e: JournalEntry, who: str, late: bool = False) -> str:
    total = sum(ln.debit_centavos for ln in e.lines)
    still = " Still waiting after a working day:" if late else ""
    return f"{still} {who} posted {e.number}, {peso(total)}: {e.memo}. Waiting for your approval.".strip()


def waiting_for_approval(db: DB, e: JournalEntry, user: User) -> None:
    """Tell whoever approves first (decided 2026-10-22: the Finance Head, by the
    journal.first tick), not whoever posted it. If that leaves nobody (none hold
    the tick, or the one who does posted it), every approver is told, so nothing
    goes unseen. The other approvers are backup: remind_backup tells them once an
    entry has waited a working day."""
    approvers = [u for u in holders(db, "journal.approve") if u.id != user.id]
    # Ticked on the role itself: the Administrator holds every permission without ticks, and isn't anyone's first approver.
    first = [u for u in approvers if not u.role.is_system and "journal.first" in permissions_of(u.role)]
    tell(db, first or approvers, "entry.waiting", waiting_text(e, user.full_name), link=entry_link(e))


def remind_backup(db: DB, user: User, settings: Settings) -> None:
    """For a backup approver (may approve, isn't told first), when they open a page:
    entries still waiting one working day after they were posted (Monday to
    Saturday, not counting Philippine holidays: app/workdays.py), that they weren't
    told of yet. Finance has no timers, so this is where the waiting time is checked."""
    can = permissions_of(user.role)
    # The Administrator (IT) holds every permission but isn't a backup approver to remind.
    if "journal.approve" not in can or "journal.first" in can or user.role.is_system:
        return
    now = datetime.now(UTC)
    # A working day is never shorter than a day: only those can be due.
    due = db.scalars(
        select(JournalEntry).where(
            JournalEntry.status == "waiting",
            JournalEntry.created_at <= now - timedelta(days=1),
            or_(JournalEntry.posted_by_id.is_(None), JournalEntry.posted_by_id != user.id),
        )
    ).all()
    if not due:
        return
    told = set(db.scalars(select(Notification.link).where(Notification.user_id == user.id, Notification.kind == "entry.waiting")))
    for e in due:
        posted = e.created_at if e.created_at.tzinfo else e.created_at.replace(tzinfo=UTC)
        if entry_link(e) not in told and one_workday_later(posted, settings.org_timezone) <= now:
            tell(db, [user], "entry.waiting", waiting_text(e, e.posted_by, late=True), link=entry_link(e))
    db.commit()


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
    sign(db, user, "journal_entry", e.id, "prepared", journal_content(e))
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
    sign(db, user, "journal_entry", back.id, "prepared", journal_content(back))
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
    if to == "approved":
        # The approver's signature, on what they approved (decided 2026-10-22: placed by their own step).
        sign(db, user, "journal_entry", e.id, "approved", journal_content(e))
    audit(db, user, f"entry.{to}", target=e.number, target_type="journal_entry", target_id=e.id, fields=["reason"] if reason else ())
    said = f"{user.full_name} approved {e.number}: it now counts in the books." if to == "approved" else f"{user.full_name} rejected {e.number}: {reason}"
    tell(db, [e.posted_by_id], f"entry.{to}", said, link=entry_link(e), not_to=[user.id])
    # Decided: nobody else needs to be asked about it any more.
    done(db, "entry.waiting", entry_link(e))
    db.commit()
    return e


class ManyIn(Api):
    ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/entries/approve")
def approve_many(user: permitted("journal.approve"), db: DB, settings: SettingsDep, body: ManyIn) -> dict:
    """Approves several waiting entries (decided 2026-10-22). Each goes through the
    same check as one at a time: still waiting when saved, and never this person's
    own. Any that couldn't be approved are named, with why."""
    approved, skipped = [], []
    for entry_id in dict.fromkeys(body.ids):
        try:
            approved.append(decide(db, settings, user, entry_id, "approved").number)
        except HTTPException as refused:
            found = db.get(JournalEntry, entry_id)
            skipped.append({"number": found.number if found else None, "reason": refused.detail})
    return {"approved": approved, "skipped": skipped}


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
