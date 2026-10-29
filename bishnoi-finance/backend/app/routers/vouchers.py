"""Payment vouchers: paying suppliers' bills once they're approved (Aubrey's steps 4-6).

- Prepared (vouchers.prepare: Cristal, Aubrey) for one supplier: which of their bills ready to
  pay it pays and how much of each (part of a bill allowed), how it's paid (bank transfer,
  check, cash), from which account (one under CASH in the chart), and the same payment's
  Oojeema PV number and Zoho reference. Submitted, it's ready to release.
- Released (vouchers.release: Cristal), which posts it: Dr each bill's payables account, Cr the
  account it's paid from. No other OK in the Hub: the bills were approved (and checked, with tax
  withheld) before they could be paid (Aubrey's flow, 2026-10-23; Plans/Plan - Bill approval
  flow). Whoever prepared it may release it.
- Returned with a reason before release by someone else who may release it: back to whoever
  prepared it, who corrects it and submits it again. Every step is kept in its history.
  Cancelled before release (nothing posted); voided after (vouchers.void: the entry reversed,
  the bills owed again). What open vouchers hold of a bill is set aside, so nothing is paid twice.

Decided 2026-10-23 (Plans/Plan - Payment vouchers; checks moved to the bill the same day).
Included in Finance's own router (app/routers/finance.py), so main.py is untouched.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import func, or_, select

from app import fx
from app.access import access_of, permitted
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.models import BankAccount, OPEN_VOUCHERS, Account, Bill, JournalEntry, PaymentVoucher, StoredFile, Supplier, User, VoucherEvent, VoucherFile, VoucherLine
from app.notify import done, holders, tell
from app.routers.funds import today
from app.routers.payables import FileIn, files_out, found_file, file_response, set_aside, store_file
from app.routers.tax import Api, field_error
from app.signatures import sign

router = APIRouter(prefix="/vouchers", tags=["vouchers"])

STATUS_LABELS = {
    "draft": "Draft", "returned": "Returned", "to_check": "To check", "to_approve": "To approve",
    "to_release": "To release", "released": "Released", "cancelled": "Cancelled", "void": "Void",
}
METHOD_LABELS = {"bank": "Bank transfer", "check": "Check", "cash": "Cash"}
MAX_FILES = 10


# --- amounts in words, as a voucher or a check prints them --------------------------------------

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _words(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return ONES[n // 100] + " hundred" + (" " + _words(n % 100) if n % 100 else "")
    for size, name in ((10**9, "billion"), (10**6, "million"), (10**3, "thousand")):
        if n >= size:
            return _words(n // size) + " " + name + (" " + _words(n % size) if n % size else "")
    return str(n)


def in_words(centavos: int) -> str:
    """₱11,100.50 → "Eleven thousand one hundred pesos and 50/100"."""
    pesos, cents = divmod(centavos, 100)
    text = _words(pesos) + (" peso" if pesos == 1 else " pesos") + f" and {cents:02d}/100"
    return text[0].upper() + text[1:]


# --- what a voucher pays from ---------------------------------------------------------------------


def paying_accounts(db: DB) -> list[Account]:
    """The accounts a voucher is paid from: those under the chart's CASH account (Oojeema's
    chart groups the banks, petty cash funds and e-wallets there), plus the money accounts set
    under Default accounts. A chart with nothing under CASH offers every asset account.
    Decided 2026-10-23 (you weren't sure; Cristal would know best: decision 5)."""
    cash = [a.id for a in db.scalars(select(Account).where(func.upper(func.trim(Account.name)) == "CASH"))]
    under = list(db.scalars(select(Account).where(Account.parent_id.in_(cash), Account.is_active))) if cash else []
    if not under:
        return list(db.scalars(select(Account).where(Account.type == "asset", Account.is_active).order_by(Account.code)))
    s = posting_settings(db)
    ids = {a.id for a in under} | {x for x in (s.cash_account_id, s.bank_account_id, s.ewallet_account_id, s.check_account_id) if x}
    return list(db.scalars(select(Account).where(Account.id.in_(ids), Account.is_active).order_by(Account.code)))


def bill_payables(db: DB, b: Bill) -> Account | None:
    """The account the bill's owed amount sits in: the one it posted to when recorded."""
    for account_id in (b.payables_account_id, b.supplier.payables_account_id, posting_settings(db).payables_account_id):
        a = db.get(Account, account_id) if account_id else None
        if a is not None:
            return a
    return None


# --- as the screens see it ------------------------------------------------------------------------


def account_brief(a: Account | None) -> dict | None:
    return {"id": a.id, "code": a.code, "name": a.name} if a else None


def voucher_summary(v: PaymentVoucher) -> dict:
    return {
        "id": v.id, "no": v.no, "number": v.number, "status": v.status, "statusLabel": STATUS_LABELS[v.status],
        "supplier": {"id": v.supplier.id, "name": v.supplier.name}, "method": v.method, "methodLabel": METHOD_LABELS[v.method],
        "totalCentavos": v.total_centavos, "bills": len(v.lines), "preparedBy": v.prepared_by, "oojeemaRef": v.oojeema_ref,
        "paidOn": v.paid_on.isoformat() if v.paid_on else None, "updatedAt": v.updated_at.isoformat() if v.updated_at else None,
    }


def may(user: User, v: PaymentVoucher) -> dict:
    """What this person may do to this voucher now. Whoever prepared it may release it (Cristal
    handles the payment end to end); returning is for someone else."""
    can = access_of(user).can
    mine = v.prepared_by_id == user.id
    open_ = v.status in OPEN_VOUCHERS
    return {
        "canEdit": v.status in ("draft", "returned") and can("vouchers.prepare"),
        "canSubmit": v.status in ("draft", "returned") and can("vouchers.prepare"),
        "canRelease": v.status == "to_release" and can("vouchers.release"),
        "canReturn": v.status == "to_release" and can("vouchers.release") and not mine,
        "canCancel": open_ and (can("vouchers.release") or (v.status in ("draft", "returned") and can("vouchers.prepare"))),
        "canVoid": v.status == "released" and can("vouchers.void"),
        "canAttach": v.status not in ("cancelled", "void") and (can("vouchers.prepare") or can("vouchers.release")),
    }


def voucher_out(db: DB, v: PaymentVoucher, user: User) -> dict:
    held = set_aside(db, [ln.bill_id for ln in v.lines], exclude_voucher=v.id)
    lines = []
    for ln in v.lines:
        b = ln.bill
        # Paid before this voucher: once it's released, its own amount is in the bill's paid.
        before = b.paid_centavos - (ln.amount_centavos if v.status == "released" else 0)
        lines.append({
            "billId": b.id, "billNo": b.no, "billNumber": b.bill_number, "billDate": b.bill_date.isoformat(), "dueDate": b.due_date.isoformat(),
            "payableCentavos": b.payable_centavos, "paidBeforeCentavos": max(before, 0), "setAsideElsewhereCentavos": held.get(b.id, 0),
            "amountCentavos": ln.amount_centavos, "leftAfterCentavos": max(b.payable_centavos - max(before, 0) - ln.amount_centavos, 0),
            "partial": max(before, 0) + ln.amount_centavos < b.payable_centavos,
            "documentMissing": not b.files, "files": files_out(b.files),
            "approvedBy": b.approved_by, "checkedBy": b.checked_by, "withheldCentavos": b.withheld_centavos,
        })
    s = v.supplier
    return voucher_summary(v) | may(user, v) | {
        "supplier": {"id": s.id, "name": s.name, "companyName": s.company_name, "tin": s.tin, "branchCode": s.branch_code, "address": s.address,
                     "bankName": s.bank_name, "bankAccountName": s.bank_account_name, "bankAccountNumber": s.bank_account_number},
        "paidFrom": account_brief(db.get(Account, v.paid_from_id) if v.paid_from_id else None),
        "lines": lines, "amountInWords": in_words(v.total_centavos),
        "zohoRef": v.zoho_ref, "notes": v.notes,
        "releasedBy": v.released_by,
        "bankReference": v.bank_reference, "checkNumber": v.check_number, "checkDate": v.check_date.isoformat() if v.check_date else None,
        "entryId": v.entry_id,
        "events": [{"at": e.at.isoformat(), "kind": e.kind, "who": e.who, "text": e.text} for e in v.events],
        "files": files_out(v.files),
    }


def found(db: DB, voucher_id: str) -> PaymentVoucher:
    v = db.get(PaymentVoucher, voucher_id)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such payment voucher.")
    return v


def link(v: PaymentVoucher) -> str:
    return f"/vouchers/{v.id}"


def event(v: PaymentVoucher, kind: str, user: User, text: str | None = None) -> None:
    v.events.append(VoucherEvent(kind=kind, who=user.full_name[:120], who_id=user.id, text=(text or None) and text[:300]))


def content(v: PaymentVoucher) -> dict:
    """What a voucher says: what each signature on it vouches for."""
    return {
        "number": v.number, "supplier": v.supplier.name, "method": v.method, "paidFrom": v.paid_from_id, "total": v.total_centavos,
        "lines": [[ln.bill.no, ln.bill.bill_number, ln.amount_centavos] for ln in v.lines], "oojeema": v.oojeema_ref, "zoho": v.zoho_ref,
    }


def peso(centavos: int) -> str:
    return f"₱{centavos / 100:,.2f}"


def next_number(db: DB, on: date) -> str:
    prefix = f"PV-{on:%Y%m}-"
    last = db.scalar(select(func.max(PaymentVoucher.number)).where(PaymentVoucher.number.like(f"{prefix}%")))
    return f"{prefix}{(int(last.rsplit('-', 1)[1]) + 1 if last else 1):04d}"


def expect(v: PaymentVoucher, *states: str) -> None:
    if v.status not in states:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This voucher is {STATUS_LABELS[v.status].lower()}: someone may have acted on it already. Reload to see where it stands.")


# --- the lists ------------------------------------------------------------------------------------


@router.get("")
def list_vouchers(user: permitted("vouchers.view"), db: DB, show: str | None = Query(None, max_length=20), q: str | None = Query(None, max_length=100)) -> dict:
    query = select(PaymentVoucher).join(Supplier, Supplier.id == PaymentVoucher.supplier_id)
    if show in STATUS_LABELS:
        query = query.where(PaymentVoucher.status == show)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(
            func.lower(PaymentVoucher.number).like(like), func.lower(Supplier.name).like(like),
            func.lower(func.coalesce(PaymentVoucher.oojeema_ref, "")).like(like), func.lower(func.coalesce(PaymentVoucher.zoho_ref, "")).like(like),
            func.lower(func.coalesce(PaymentVoucher.bank_reference, "")).like(like), func.lower(func.coalesce(PaymentVoucher.check_number, "")).like(like),
        ))
    items = db.scalars(query.order_by(PaymentVoucher.updated_at.desc()).limit(300)).all()
    counts = dict(db.execute(select(PaymentVoucher.status, func.count()).group_by(PaymentVoucher.status)).all())
    can = access_of(user).can
    return {"items": [voucher_summary(v) for v in items], "counts": {k: counts.get(k, 0) for k in STATUS_LABELS}, "canPrepare": can("vouchers.prepare")}


@router.get("/choices")
def voucher_choices(user: permitted("vouchers.view"), db: DB, settings: SettingsDep, supplier: str | None = Query(None, max_length=36),
                    voucher: str | None = Query(None, max_length=36)) -> dict:
    """Suppliers with bills left to pay; for one supplier, those bills with what's paid, what
    other open vouchers set aside and what's left; the accounts a voucher pays from."""
    open_bills = db.scalars(select(Bill).where(Bill.status == "recorded", Bill.paid_centavos < Bill.payable_centavos)).all()
    held = set_aside(db, [b.id for b in open_bills], exclude_voucher=voucher)
    per_supplier: dict[str, int] = {}
    for b in open_bills:
        left = b.payable_centavos - b.paid_centavos - held.get(b.id, 0)
        if left > 0:
            per_supplier[b.supplier_id] = per_supplier.get(b.supplier_id, 0) + left
    suppliers = db.scalars(select(Supplier).where(Supplier.id.in_(list(per_supplier))).order_by(func.lower(Supplier.name))).all()
    bills = []
    if supplier:
        for b in sorted((b for b in open_bills if b.supplier_id == supplier), key=lambda x: (x.due_date, x.no or 0)):
            bills.append({
                "id": b.id, "no": b.no, "billNumber": b.bill_number, "billDate": b.bill_date.isoformat(), "dueDate": b.due_date.isoformat(),
                "payableCentavos": b.payable_centavos, "paidCentavos": b.paid_centavos, "setAsideCentavos": held.get(b.id, 0),
                "availableCentavos": max(b.payable_centavos - b.paid_centavos - held.get(b.id, 0), 0), "documentMissing": not b.files,
            })
    picked = db.get(Supplier, supplier) if supplier else None
    return {
        "suppliers": [{"id": s.id, "name": s.name, "owedCentavos": per_supplier.get(s.id, 0)} for s in suppliers],
        "supplier": {"id": picked.id, "name": picked.name, "bankName": picked.bank_name, "bankAccountName": picked.bank_account_name,
                     "bankAccountNumber": picked.bank_account_number} if picked else None,
        "bills": bills,
        "accounts": [account_brief(a) for a in paying_accounts(db)],
        "methods": [{"key": k, "label": v} for k, v in METHOD_LABELS.items()],
        "today": today(settings).isoformat(),
    }


# --- preparing ------------------------------------------------------------------------------------


class LineIn(Api):
    bill_id: str
    amount_centavos: int = Field(gt=0, lt=10**11)


class VoucherIn(Api):
    supplier_id: str
    method: Literal["bank", "check", "cash"] = "bank"
    paid_from_id: str | None = None
    oojeema_ref: str | None = Field(None, max_length=60)
    zoho_ref: str | None = Field(None, max_length=60)
    notes: str | None = Field(None, max_length=500)
    lines: list[LineIn] = Field(min_length=1, max_length=100)


def line_error(i: int, field: str, message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "lines", i, field], "msg": message}])


def check_amounts(db: DB, v: PaymentVoucher, pairs: list[tuple[Bill, int]]) -> None:
    """Each bill recorded, the supplier's, once, and no more than what's left of it after what
    it's been paid and what other open vouchers set aside (so nothing is paid twice)."""
    held = set_aside(db, [b.id for b, _ in pairs], exclude_voucher=v.id)
    seen = set()
    for i, (b, amount) in enumerate(pairs):
        if b.supplier_id != v.supplier_id or b.status != "recorded":
            raise line_error(i, "billId", "Pick a bill of this supplier that's ready to pay (approved and posted).")
        if b.id in seen:
            raise line_error(i, "billId", "This bill is on the voucher twice.")
        seen.add(b.id)
        left = b.payable_centavos - b.paid_centavos - held.get(b.id, 0)
        if amount > left:
            others = f" ({peso(held[b.id])} is set aside in another voucher)" if held.get(b.id) else ""
            raise line_error(i, "amountCentavos", f"Bill {b.no} has {peso(max(left, 0))} left to pay{others}.")


def apply(db: DB, v: PaymentVoucher, body: VoucherIn) -> None:
    supplier = db.get(Supplier, body.supplier_id)
    if supplier is None:
        raise field_error("supplierId", "Pick a supplier.")
    if body.paid_from_id and body.paid_from_id not in {a.id for a in paying_accounts(db)}:
        raise field_error("paidFromId", "Pick one of the accounts money is paid from.")
    v.supplier_id, v.method, v.paid_from_id = supplier.id, body.method, body.paid_from_id
    v.oojeema_ref, v.zoho_ref, v.notes = body.oojeema_ref, body.zoho_ref, body.notes
    pairs = []
    for i, line in enumerate(body.lines):
        b = db.get(Bill, line.bill_id)
        if b is None:
            raise line_error(i, "billId", "There's no such bill.")
        pairs.append((b, line.amount_centavos))
    check_amounts(db, v, pairs)
    v.lines = [VoucherLine(bill_id=b.id, position=i, amount_centavos=amount) for i, (b, amount) in enumerate(pairs)]
    v.total_centavos = sum(amount for _, amount in pairs)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_voucher(user: permitted("vouchers.prepare"), db: DB, settings: SettingsDep, body: VoucherIn) -> dict:
    v = PaymentVoucher(number=next_number(db, today(settings)), prepared_by=user.full_name[:120], prepared_by_id=user.id, status="draft")
    with db.no_autoflush:  # filled in first: the checks below read the database, which would save it half-made
        apply(db, v, body)
    db.add(v)
    event(v, "created", user)
    db.flush()
    audit(db, user, "voucher.created", target=v.number, target_type="voucher", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


@router.get("/{voucher_id}")
def read_voucher(user: permitted("vouchers.view"), db: DB, voucher_id: str) -> dict:
    return voucher_out(db, found(db, voucher_id), user)


@router.put("/{voucher_id}")
def change_voucher(user: permitted("vouchers.prepare"), db: DB, voucher_id: str, body: VoucherIn) -> dict:
    v = found(db, voucher_id)
    expect(v, "draft", "returned")
    apply(db, v, body)
    audit(db, user, "voucher.updated", target=v.number, target_type="voucher", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


@router.post("/{voucher_id}/submit")
def submit(user: permitted("vouchers.prepare"), db: DB, voucher_id: str) -> dict:
    v = found(db, voucher_id)
    expect(v, "draft", "returned")
    if not v.lines:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add the bills it pays first.")
    if not v.paid_from_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pick the account it's paid from first.")
    check_amounts(db, v, [(ln.bill, ln.amount_centavos) for ln in v.lines])
    again = v.status == "returned"
    v.status = "to_release"
    event(v, "resubmitted" if again else "submitted", user)
    sign(db, user, "payment_voucher", v.id, "prepared", content(v))
    done(db, "voucher.returned", link(v))
    tell(db, holders(db, "vouchers.release"), "voucher.to_release",
         f"{user.full_name} {'resubmitted' if again else 'submitted'} {v.number}, {peso(v.total_centavos)} to {v.supplier.name}. Ready to release.",
         link=link(v), not_to=[user.id])
    audit(db, user, "voucher.submitted", target=v.number, target_type="voucher", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


# --- the steps after: return, release -------------------------------------------------------------


class ReasonIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/{voucher_id}/return")
def send_back(user: CurrentUser, db: DB, voucher_id: str, body: ReasonIn) -> dict:
    """Back to whoever prepared it, with the reason (Cristal Q4: errors go back to Aubrey)."""
    v = found(db, voucher_id)
    if not may(user, v)["canReturn"]:
        expect(v, "to_release")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow returning this voucher, or you prepared it (cancel it, or release it).")
    v.status = "returned"
    reason = body.reason.strip()
    event(v, "returned", user, reason)
    done(db, "voucher.to_release", link(v))
    tell(db, [v.prepared_by_id], "voucher.returned", f"{user.full_name} returned {v.number}: {reason}", link=link(v), not_to=[user.id])
    audit(db, user, "voucher.returned", target=v.number, target_type="voucher", target_id=v.id, fields=["reason"])
    db.commit()
    return voucher_out(db, v, user)


class ReleaseIn(Api):
    paid_on: date
    bank_reference: str | None = Field(None, max_length=80)
    check_number: str | None = Field(None, max_length=40)
    check_date: date | None = None
    note: str | None = Field(None, max_length=300)
    # The company bank account it went out of (step 16a); the rate on the day paid, for a foreign bill (16c).
    bank_account_id: str | None = Field(None, max_length=36)
    rate: float | None = Field(None, gt=0, le=100000)


@router.post("/{voucher_id}/release")
def release(user: permitted("vouchers.release"), db: DB, settings: SettingsDep, voucher_id: str, body: ReleaseIn) -> dict:
    """Paid: posts Dr each bill's payables account, Cr the account it's paid from (counts at once,
    like the other automatic entries), and each bill's paid amount goes up."""
    v = found(db, voucher_id)
    expect(v, "to_release")
    if body.paid_on > today(settings):
        raise field_error("paidOn", "The payment date can't be in the future.")
    if v.method == "check" and not (body.check_number or "").strip():
        raise field_error("checkNumber", "Enter the check number.")
    paid_from = db.get(Account, v.paid_from_id) if v.paid_from_id else None
    if body.bank_account_id:
        bank = db.get(BankAccount, body.bank_account_id)
        if bank is None or not bank.is_active:
            raise field_error("bankAccountId", "Pick one of the company's active bank accounts.")
        paid_from, v.bank_account_id, v.paid_from_id = bank.account, bank.id, bank.account_id
    if paid_from is None or not paid_from.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "The account it's paid from isn't set or is switched off. Return it to be corrected.")
    for i, ln in enumerate(v.lines):
        if ln.amount_centavos > ln.bill.payable_centavos - ln.bill.paid_centavos or ln.bill.status != "recorded":
            raise line_error(i, "amountCentavos", f"Bill {ln.bill.no} no longer has {peso(ln.amount_centavos)} left to pay. Return the voucher to be corrected.")
    legs = [Leg(bill_payables(db, ln.bill), debit=ln.amount_centavos, description=f"Bill {ln.bill.no} ({ln.bill.bill_number})"[:200]) for ln in v.lines]
    # A foreign bill is paid in its currency at the day's rate (step 16c): the pesos that go out differ from what it
    # was booked at; the difference is an exchange gain (fewer pesos) or loss (more).
    paid, rate_e4 = 0, None
    for ln in v.lines:
        b = ln.bill
        if b.currency and b.currency != fx.BASE and b.foreign_payable:
            rate_e4 = rate_e4 or fx.need_rate(db, b.currency, body.paid_on, body.rate, "rate")
            foreign = round(b.foreign_payable * ln.amount_centavos / b.payable_centavos) if b.payable_centavos else 0
            paid += fx.to_pesos(foreign, rate_e4)
        else:
            paid += ln.amount_centavos
    exchange = v.total_centavos - paid
    legs.append(Leg(paid_from, credit=paid, description=f"{METHOD_LABELS[v.method]} to {v.supplier.name}"[:200]))
    if exchange:
        s = posting_settings(db)
        gain = db.get(Account, s.fx_gain_account_id) if s.fx_gain_account_id else None
        loss = db.get(Account, s.fx_loss_account_id) if s.fx_loss_account_id else None
        if (exchange > 0 and gain is None) or (exchange < 0 and loss is None):
            raise HTTPException(status.HTTP_409_CONFLICT, "Set the exchange gain and loss accounts under Accounting, Default accounts, then release it.")
        legs.append(Leg(gain, credit=exchange, description="Exchange gain") if exchange > 0 else Leg(loss, debit=-exchange, description="Exchange loss"))
    v.rate_e4, v.exchange_centavos = rate_e4, exchange or None
    reference = (body.check_number if v.method == "check" else body.bank_reference) or v.oojeema_ref
    e = post(db, body.paid_on, f"{v.number}: payment to {v.supplier.name}", legs, user.full_name, reference=(reference or v.number)[:80], source="voucher", by_id=user.id)
    for ln in v.lines:
        ln.bill.paid_centavos += ln.amount_centavos
    v.status, v.released_by, v.released_by_id, v.paid_on, v.entry_id = "released", user.full_name[:120], user.id, body.paid_on, e.id
    v.bank_reference, v.check_number, v.check_date = (body.bank_reference or "").strip() or None, (body.check_number or "").strip() or None, body.check_date
    event(v, "released", user, (body.note or "").strip() or None)
    sign(db, user, "payment_voucher", v.id, "released", content(v))
    done(db, "voucher.to_release", link(v))
    tell(db, [v.prepared_by_id], "voucher.released", f"{user.full_name} released {v.number}: {peso(v.total_centavos)} paid to {v.supplier.name}.", link=link(v), not_to=[user.id])
    audit(db, user, "voucher.released", target=v.number, target_type="voucher", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


@router.post("/{voucher_id}/cancel")
def cancel(user: CurrentUser, db: DB, voucher_id: str, body: ReasonIn) -> dict:
    """Not released yet: nothing was posted, so it's simply cancelled (kept, with the reason)."""
    v = found(db, voucher_id)
    expect(v, *OPEN_VOUCHERS)
    if not may(user, v)["canCancel"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow cancelling this voucher.")
    v.status = "cancelled"
    event(v, "cancelled", user, body.reason.strip())
    for kind in ("voucher.to_release", "voucher.returned"):
        done(db, kind, link(v))
    audit(db, user, "voucher.cancelled", target=v.number, target_type="voucher", target_id=v.id, fields=["reason"])
    db.commit()
    return voucher_out(db, v, user)


@router.post("/{voucher_id}/void")
def void(user: permitted("vouchers.void"), db: DB, settings: SettingsDep, voucher_id: str, body: ReasonIn) -> dict:
    """Released, then undone: its entry reversed today, the bills owed again (decision 7: Malou)."""
    v = found(db, voucher_id)
    expect(v, "released")
    reason = body.reason.strip()
    entry = db.get(JournalEntry, v.entry_id) if v.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of {v.number}: {reason}"[:300], legs, user.full_name, reference=v.number, source="voucher", reverses=entry, by_id=user.id)
    for ln in v.lines:
        ln.bill.paid_centavos = max(ln.bill.paid_centavos - ln.amount_centavos, 0)
    v.status = "void"
    event(v, "voided", user, reason)
    tell(db, [v.prepared_by_id, v.released_by_id], "voucher.voided", f"{user.full_name} voided {v.number}: {reason}", link=link(v), not_to=[user.id])
    audit(db, user, "voucher.voided", target=v.number, target_type="voucher", target_id=v.id, fields=["reason"])
    db.commit()
    return voucher_out(db, v, user)


# --- proof of payment, attached -------------------------------------------------------------------


def may_attach(user: User, v: PaymentVoucher) -> None:
    if not may(user, v)["canAttach"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow attaching files to this voucher, or it's cancelled or void.")


@router.post("/{voucher_id}/files", status_code=status.HTTP_201_CREATED)
def attach(user: CurrentUser, db: DB, voucher_id: str, body: FileIn) -> dict:
    v = found(db, voucher_id)
    may_attach(user, v)
    if len(v.files) >= MAX_FILES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A voucher keeps up to {MAX_FILES} files. Remove one first.")
    ref, size = store_file(db, body)
    v.files.append(VoucherFile(ref=ref, name=body.name.strip(), content_type=body.content_type, size=size, uploaded_by=user.full_name))
    audit(db, user, "voucher.file_added", target=v.number, target_type="voucher", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


@router.get("/{voucher_id}/files/{file_id}")
def open_file(user: permitted("vouchers.view"), db: DB, voucher_id: str, file_id: str) -> Response:
    return file_response(db, found_file(found(db, voucher_id).files, file_id))


@router.delete("/{voucher_id}/files/{file_id}")
def remove_file(user: CurrentUser, db: DB, voucher_id: str, file_id: str) -> dict:
    v = found(db, voucher_id)
    may_attach(user, v)
    f = found_file(v.files, file_id)
    if stored := db.get(StoredFile, f.ref):
        db.delete(stored)
    v.files.remove(f)
    audit(db, user, "voucher.file_removed", target=v.number, target_type="voucher", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


