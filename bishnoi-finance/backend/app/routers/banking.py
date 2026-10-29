"""Banks, payments and equity (feature plan step 16, 2026-10-29).

Bank accounts and payment channels (16a)
    GET   /finance/bank-accounts                 the company's bank accounts and e-wallets, and the providers to pick from
    POST  /finance/bank-accounts                 one more (with the ledger account its money is kept in)
    PATCH /finance/bank-accounts/{id}            name, number, default, switched on or off
Exchange rates (16c)
    GET   /finance/exchange-rates?currency=      the latest rates recorded
    PUT   /finance/exchange-rates                {currency, on, rate}: the day's rate (pesos per unit)
Owner's equity and closing (16d), the period lock (16e)
    POST  /finance/equity/entries                capital put in, or drawings taken out
    GET   /finance/equity/statement?yearEnd=     the statement of changes in equity for a fiscal year
    GET   /finance/closing                        fiscal years, closed or not, and the lock
    POST  /finance/closing                        {yearEnd, lock}: close a fiscal year to retained earnings
    PUT   /finance/period-lock                    {lockedUntil}: nothing posted on or before it (null opens it)
"""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import Field
from sqlalchemy import func, select

from app import fx
from app.access import permitted
from app.audit import audit
from app.bir_reports import balances
from app.deps import DB, CurrentUser, SettingsDep
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.models import Account, BankAccount, ExchangeRate, TaxProfile, YearClosing
from app.routers.funds import today
from app.routers.tax import Api, field_error

router = APIRouter(prefix="/finance", tags=["banking"])

# The banks and e-wallets people pick from; each drawn as its initials in its colour (no logos copied).
PROVIDERS = {
    "bdo": ("bank", "BDO Unibank", "#0033a0"), "bpi": ("bank", "BPI", "#b11116"), "metrobank": ("bank", "Metrobank", "#1a3f8f"),
    "landbank": ("bank", "LANDBANK", "#007a33"), "pnb": ("bank", "PNB", "#003b71"), "unionbank": ("bank", "UnionBank", "#f47920"),
    "securitybank": ("bank", "Security Bank", "#00a0af"), "chinabank": ("bank", "China Bank", "#c8102e"), "rcbc": ("bank", "RCBC", "#00539b"),
    "eastwest": ("bank", "EastWest Bank", "#6d2077"), "dbp": ("bank", "DBP", "#00704a"), "psbank": ("bank", "PSBank", "#1d4f91"),
    "gcash": ("ewallet", "GCash", "#007dfe"), "maya": ("ewallet", "Maya", "#00b14f"), "cash": ("cash", "Cash on hand", "#5c6b73"),
    "other": ("bank", "Other bank", "#5c6b73"),
}


def provider_out(key: str) -> dict:
    kind, name, color = PROVIDERS.get(key, PROVIDERS["other"])
    return {"key": key, "kind": kind, "name": name, "color": color, "initials": "".join(w[0] for w in name.split()[:2]).upper()}


def bank_out(b: BankAccount) -> dict:
    return {"id": b.id, "kind": b.kind, "provider": provider_out(b.provider), "name": b.name, "accountName": b.account_name,
            "accountNumber": b.account_number, "currency": b.currency, "isDefault": b.is_default, "isActive": b.is_active,
            "account": {"id": b.account.id, "code": b.account.code, "name": b.account.name}}


# --- bank accounts (16a) ---------------------------------------------------------------------------------


@router.get("/bank-accounts")
def bank_accounts(_: CurrentUser, db: DB) -> dict:
    rows = db.scalars(select(BankAccount).order_by(BankAccount.is_active.desc(), BankAccount.is_default.desc(), BankAccount.name)).all()
    return {"items": [bank_out(b) for b in rows], "providers": [provider_out(k) for k in PROVIDERS]}


class BankIn(Api):
    provider: str = Field(max_length=20)
    name: str = Field(min_length=1, max_length=120)
    account_name: str | None = Field(None, max_length=160)
    account_number: str | None = Field(None, max_length=40)
    currency: str = Field("PHP", min_length=3, max_length=3)
    account_id: str = Field(max_length=36)
    is_default: bool = False


class BankPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=120)
    account_name: str | None = Field(None, max_length=160)
    account_number: str | None = Field(None, max_length=40)
    is_default: bool | None = None
    is_active: bool | None = None


def _one_default(db, b: BankAccount) -> None:
    for other in db.scalars(select(BankAccount).where(BankAccount.kind == b.kind, BankAccount.id != b.id, BankAccount.is_default)):
        other.is_default = False


@router.post("/bank-accounts", status_code=status.HTTP_201_CREATED)
def add_bank_account(user: permitted("accounts.manage"), db: DB, body: BankIn) -> dict:
    if body.provider not in PROVIDERS:
        raise field_error("provider", "Pick the bank or e-wallet.")
    a = db.get(Account, body.account_id)
    if a is None or not a.is_active or a.type != "asset":
        raise field_error("accountId", "Pick the asset account its money is kept in (e.g. Cash in bank, BDO).")
    b = BankAccount(kind=PROVIDERS[body.provider][0], provider=body.provider, name=body.name.strip(), account_name=body.account_name,
                    account_number=body.account_number, currency=body.currency.upper(), account_id=a.id, is_default=body.is_default)
    db.add(b)
    db.flush()
    if b.is_default:
        _one_default(db, b)
    audit(db, user, "bank_account.created", target=b.name, target_type="bank_account", target_id=b.id)
    db.commit()
    return bank_out(b)


@router.patch("/bank-accounts/{bank_id}")
def change_bank_account(user: permitted("accounts.manage"), db: DB, bank_id: str, body: BankPatch) -> dict:
    b = db.get(BankAccount, bank_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such bank account.")
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if getattr(b, k) != v}
    for k, v in fields.items():
        setattr(b, k, v.strip() if isinstance(v, str) else v)
    if fields.get("is_default"):
        _one_default(db, b)
    if fields:
        audit(db, user, "bank_account.updated", target=b.name, target_type="bank_account", target_id=b.id, fields=sorted(fields))
        db.commit()
    return bank_out(b)


# --- exchange rates (16c) ----------------------------------------------------------------------------------


def rate_out(r: ExchangeRate) -> dict:
    return {"currency": r.currency, "on": r.on.isoformat(), "rate": r.rate_e4 / fx.SCALE, "createdBy": r.created_by}


@router.get("/exchange-rates")
def exchange_rates(_: CurrentUser, db: DB, currency: str = "USD") -> dict:
    rows = db.scalars(select(ExchangeRate).where(ExchangeRate.currency == currency.upper()).order_by(ExchangeRate.on.desc()).limit(60)).all()
    return {"currency": currency.upper(), "items": [rate_out(r) for r in rows]}


class RateIn(Api):
    currency: str = Field(min_length=3, max_length=3)
    on: date
    rate: float = Field(gt=0, le=100000)


@router.put("/exchange-rates")
def set_rate(user: permitted("accounts.manage"), db: DB, settings: SettingsDep, body: RateIn) -> dict:
    if body.currency.upper() == fx.BASE:
        raise field_error("currency", "Pesos need no rate.")
    if body.on > today(settings):
        raise field_error("on", "A rate is recorded for a day that has come.")
    r = db.scalar(select(ExchangeRate).where(ExchangeRate.currency == body.currency.upper(), ExchangeRate.on == body.on))
    if r is None:
        r = ExchangeRate(currency=body.currency.upper(), on=body.on, rate_e4=0, created_by=user.full_name)
        db.add(r)
    r.rate_e4, r.created_by = fx.rate_e4_of(body.rate), user.full_name
    audit(db, user, "exchange_rate.set", target=f"{r.currency} {r.on.isoformat()}", target_type="exchange_rate", fields=["rate"])
    db.commit()
    return rate_out(r)


# --- owner's equity (16d) ------------------------------------------------------------------------------------


class EquityIn(Api):
    kind: Literal["capital", "drawing"]
    amount_centavos: int = Field(gt=0, le=10**13)
    on: date
    bank_account_id: str = Field(max_length=36)
    owner: str = Field(min_length=1, max_length=120)
    memo: str | None = Field(None, max_length=200)


def _equity_accounts(db) -> tuple[Account | None, Account | None, Account | None]:
    s = posting_settings(db)
    get = lambda i: db.get(Account, i) if i else None  # noqa: E731
    return get(s.capital_account_id), get(s.drawings_account_id), get(s.retained_earnings_account_id)


@router.post("/equity/entries", status_code=status.HTTP_201_CREATED)
def equity_entry(user: permitted("journal.post"), db: DB, settings: SettingsDep, body: EquityIn) -> dict:
    """Capital the owner put in (Dr the bank, Cr capital) or drawings taken out (Dr drawings, Cr the bank)."""
    if body.on > today(settings):
        raise field_error("on", "It can't be dated in the future.")
    bank = db.get(BankAccount, body.bank_account_id)
    if bank is None or not bank.is_active:
        raise field_error("bankAccountId", "Pick one of the company's active bank accounts.")
    capital, drawings, _ = _equity_accounts(db)
    other = capital if body.kind == "capital" else drawings
    if other is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Set the {'capital' if body.kind == 'capital' else 'drawings'} account under Accounting, Default accounts.")
    what = f"Capital from {body.owner}" if body.kind == "capital" else f"Drawings by {body.owner}"
    legs = [Leg(bank.account, debit=body.amount_centavos), Leg(other, credit=body.amount_centavos)] if body.kind == "capital" else \
        [Leg(other, debit=body.amount_centavos), Leg(bank.account, credit=body.amount_centavos)]
    e = post(db, body.on, f"{what}{': ' + body.memo if body.memo else ''}", legs, user.full_name, source="equity", by_id=user.id)
    audit(db, user, f"equity.{body.kind}", target=what, target_type="journal_entry", target_id=e.id)
    db.commit()
    return {"entryId": e.id, "number": e.number}


def fiscal_year(db, year_end: date) -> tuple[date, date]:
    """(first day, last day) of the fiscal year ending on `year_end` (the last day of its month)."""
    start = date(year_end.year, 1, 1) if year_end.month == 12 else date(year_end.year - 1, year_end.month + 1, 1)
    return start, year_end


def year_ends(db, settings, back: int = 4) -> list[date]:
    """The last fiscal year ends, most recent first (the fiscal year from Tax setup)."""
    from calendar import monthrange

    profile = db.get(TaxProfile, 1)
    month = profile.fiscal_month_end if profile else 12
    now = today(settings)
    year = now.year if (now.month, now.day) > (month, monthrange(now.year, month)[1]) else now.year - 1
    return [date(y, month, monthrange(y, month)[1]) for y in range(year, year - back, -1)]


def period_moves(db, start: date, end: date) -> dict[str, tuple[int, int]]:
    """By account: (debits, credits) in the period, closing entries left out (they only move income into equity)."""
    from app.models import JournalEntry, JournalLine

    q = (select(JournalLine.account_id, func.sum(JournalLine.debit_centavos), func.sum(JournalLine.credit_centavos)).join(JournalEntry)
         .where(JournalEntry.entry_date >= start, JournalEntry.entry_date <= end, JournalEntry.source != "closing").group_by(JournalLine.account_id))
    return {a: (int(d or 0), int(c or 0)) for a, d, c in db.execute(q)}


@router.get("/equity/statement")
def changes_in_equity(_: permitted("journal.view"), db: DB, settings: SettingsDep, year_end: date | None = None) -> dict:
    """Opening equity, capital put in, drawings, the year's net income, and closing equity."""
    start, end = fiscal_year(db, year_end or year_ends(db, settings, 1)[0])
    capital, drawings, _ = _equity_accounts(db)
    accounts = {a.id: a for a in db.scalars(select(Account))}

    def worth(moves: dict) -> int:
        """Equity accounts plus income less expenses not yet closed into them."""
        return sum((c - d) for aid, (d, c) in moves.items() if aid in accounts and accounts[aid].type in ("equity", "income", "expense"))

    opening = worth(balances(db, before=start))
    moves = period_moves(db, start, end)
    put_in = (lambda m: m[1] - m[0])(moves.get(capital.id, (0, 0))) if capital else 0
    taken = (lambda m: m[0] - m[1])(moves.get(drawings.id, (0, 0))) if drawings else 0
    income = sum(c - d for aid, (d, c) in moves.items() if aid in accounts and accounts[aid].type in ("income", "expense"))
    other = worth(moves) - put_in + taken - income  # anything else posted straight to equity
    closed = db.scalar(select(YearClosing).where(YearClosing.year_end == end)) is not None
    rows = [{"label": "Equity at the start of the year", "amountCentavos": opening},
            {"label": "Capital put in", "amountCentavos": put_in},
            {"label": "Drawings taken out", "amountCentavos": -taken},
            {"label": "Net income for the year", "amountCentavos": income}]
    if other:
        rows.append({"label": "Other changes to equity", "amountCentavos": other})
    rows.append({"label": "Equity at the end of the year", "amountCentavos": opening + put_in - taken + income + other})
    return {"start": start.isoformat(), "end": end.isoformat(), "closed": closed, "rows": rows}


# --- closing the year (16d) and the period lock (16e) -------------------------------------------------------


@router.get("/closing")
def closing(_: permitted("journal.view"), db: DB, settings: SettingsDep) -> dict:
    closed = {c.year_end: c for c in db.scalars(select(YearClosing))}
    s = posting_settings(db)
    return {"lockedUntil": s.locked_until.isoformat() if s.locked_until else None,
            "years": [{"yearEnd": y.isoformat(), "closed": y in closed, "closedBy": closed[y].closed_by if y in closed else None,
                       "netIncomeCentavos": closed[y].net_income_centavos if y in closed else None} for y in year_ends(db, settings)],
            "accountsSet": all(_equity_accounts(db))}


class CloseIn(Api):
    year_end: date
    lock: bool = True


@router.post("/closing")
def close_year(user: permitted("accounts.manage"), db: DB, settings: SettingsDep, body: CloseIn) -> dict:
    """The fiscal year's income and expenses moved to retained earnings, and its drawings to capital, in one entry
    dated the year's last day; then (by default) the books locked up to it."""
    if body.year_end not in year_ends(db, settings, 10):
        raise field_error("yearEnd", "Pick the last day of a fiscal year that has ended.")
    if db.scalar(select(YearClosing).where(YearClosing.year_end == body.year_end)):
        raise HTTPException(status.HTTP_409_CONFLICT, "That year is already closed.")
    capital, drawings, retained = _equity_accounts(db)
    if retained is None or (drawings is not None and capital is None):
        raise HTTPException(status.HTTP_409_CONFLICT, "Set the retained earnings, capital and drawings accounts under Accounting, Default accounts.")
    start, end = fiscal_year(db, body.year_end)
    moves = balances(db, start=start, end=end)
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_(list(moves))))}
    legs, net = [], 0
    for aid, (d, c) in moves.items():
        a = accounts.get(aid)
        if a is None or a.type not in ("income", "expense"):
            continue
        bal = c - d  # income carries credits; an expense, debits (negative here)
        if bal > 0:
            legs.append(Leg(a, debit=bal, description="Closing the year"))
        elif bal < 0:
            legs.append(Leg(a, credit=-bal, description="Closing the year"))
        net += bal
    if net > 0:
        legs.append(Leg(retained, credit=net, description="Net income for the year"))
    elif net < 0:
        legs.append(Leg(retained, debit=-net, description="Net loss for the year"))
    if drawings is not None:
        d, c = balances(db, end=end).get(drawings.id, (0, 0))
        if d - c > 0:
            legs += [Leg(capital, debit=d - c, description="Drawings closed to capital"), Leg(drawings, credit=d - c, description="Drawings closed to capital")]
    entry = post(db, end, f"Closing the fiscal year ended {end:%d %b %Y}", legs, user.full_name, source="closing", by_id=user.id) if legs else None
    db.add(YearClosing(year_end=end, entry_id=entry.id if entry else None, net_income_centavos=net, closed_by=user.full_name, closed_at=datetime.now(UTC)))
    s = posting_settings(db)
    if body.lock and (s.locked_until is None or s.locked_until < end):
        s.locked_until = end
    audit(db, user, "books.year_closed", target=end.isoformat(), target_type="year_closing", fields=["locked"] if body.lock else [])
    db.commit()
    return {"yearEnd": end.isoformat(), "netIncomeCentavos": net, "entryId": entry.id if entry else None,
            "lockedUntil": s.locked_until.isoformat() if s.locked_until else None}


class LockIn(Api):
    locked_until: date | None = None


@router.put("/period-lock")
def period_lock(user: permitted("accounts.manage"), db: DB, settings: SettingsDep, body: LockIn) -> dict:
    """Nothing is posted on or before this day (null opens the books again)."""
    if body.locked_until and body.locked_until >= today(settings):
        raise field_error("lockedUntil", "Lock up to a day that has passed.")
    s = posting_settings(db)
    before = s.locked_until
    s.locked_until = body.locked_until
    if before != body.locked_until:
        audit(db, user, "books.locked" if body.locked_until else "books.opened", target=body.locked_until.isoformat() if body.locked_until else "open",
              target_type="settings", fields=["lockedUntil"])
        db.commit()
    return {"lockedUntil": s.locked_until.isoformat() if s.locked_until else None}
