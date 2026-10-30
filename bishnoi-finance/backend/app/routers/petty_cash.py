"""Petty cash: spending from a petty cash fund, one voucher (PCV) with its receipts.

Decided 2026-10-30 by the user (Plans/Plan - Petty cash and receipts):
- its own module: people get view, add/edit (petty_cash.create: Aubrey), check and post or return
  (petty_cash.check: Cristal or Malou) and void (petty_cash.void) separately, on the Roles screen;
- no official receipt, no entry: every receipt line has its receipt number and its photo or PDF, which
  the checker sees beside the line and which prints with the voucher;
- whoever made or submitted a voucher never checks it;
- 2MG and GPI are kept apart: Finance's books are 2MG's, so a voucher here is 2MG's; GPI's stay in Zoho.

Posting (on check): Dr each line's account (before VAT) and Input VAT; Cr the fund (what was paid out of
it) and the withholding tax payable, worked out line by line exactly as bills are (app/payables.py).
The entry, and the BIR lists that read posted lines (app/bir_reports.py), are dated the voucher's date.
A posted voucher is voided with a reason, which reverses its entry on the day it's voided.

Not here yet (phase 2, after Malou confirms how it's done): refilling a fund.
"""

import re
from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field
from typing import Literal
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.access import access_of, permitted
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.models import Account, JournalEntry, JournalLine, PettyCashEvent, PettyCashLine, PettyCashVoucher, StoredFile
from app.money_accounts import money_account_ids
from app.notify import done, holders, tell
from app.payables import PURCHASE_TYPES, VAT_KINDS, WITHHOLDING, withholding_out, work_out
from app.routers.funds import today
from app.routers.payables import FileIn, peso, store_file
from app.routers.tax import Api, field_error, split_tin
from app.signatures import sign

router = APIRouter(tags=["petty cash"])

STATUS_LABELS = {"draft": "Draft", "to_check": "Waiting to be checked", "returned": "Returned for correction", "posted": "Posted", "void": "Void"}
SHOWS = ("draft", "to_check", "returned", "posted", "void")


# --- funds: the petty cash accounts under CASH ----------------------------------------------------


def fund_ids(db: DB) -> set[str]:
    """Petty cash funds: accounts under CASH named "Petty Cash" (the plan's rule until Malou names the funds in use)."""
    under_cash = money_account_ids(db)
    return {a.id for a in db.scalars(select(Account).where(Account.id.in_(under_cash))) if "petty cash" in a.name.lower()}


def balances(db: DB, account_ids: set[str]) -> dict[str, int]:
    """Each fund's balance in the books: approved entries, debits less credits."""
    if not account_ids:
        return {}
    rows = db.execute(
        select(JournalLine.account_id, func.sum(JournalLine.debit_centavos) - func.sum(JournalLine.credit_centavos))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalLine.account_id.in_(account_ids), JournalEntry.status == "approved")
        .group_by(JournalLine.account_id)
    ).all()
    return {a: int(v or 0) for a, v in rows}


def funds_out(db: DB) -> list[dict]:
    ids = fund_ids(db)
    held = balances(db, ids)
    return [{"id": a.id, "code": a.code, "name": a.name, "active": a.is_active, "balanceCentavos": held.get(a.id, 0)}
            for a in db.scalars(select(Account).where(Account.id.in_(ids)).order_by(Account.code))]


# --- reading ---------------------------------------------------------------------------------------


def preparers(v: PettyCashVoucher) -> set[str]:
    return {x for x in (v.created_by_id, v.submitted_by_id) if x}


def may(user, v: PettyCashVoucher) -> dict:
    can = access_of(user).can
    open_ = v.status in ("draft", "returned")
    mine = user.id in preparers(v)
    return {
        "canEdit": open_ and can("petty_cash.create"),
        "canSubmit": open_ and can("petty_cash.create") and bool(v.lines) and all(ln.file_ref for ln in v.lines),
        "canCheck": v.status == "to_check" and can("petty_cash.check") and not mine,
        "canReturn": v.status == "to_check" and can("petty_cash.check") and not mine,
        "canVoid": v.status == "posted" and can("petty_cash.void"),
        "canDelete": open_ and can("petty_cash.create"),
    }


def summary(v: PettyCashVoucher) -> dict:
    return {
        "id": v.id, "number": v.number, "status": v.status, "statusLabel": STATUS_LABELS[v.status],
        "voucherDate": v.voucher_date.isoformat(), "fund": {"id": v.fund.id, "code": v.fund.code, "name": v.fund.name},
        "personInCharge": v.person_in_charge, "department": v.department, "receipts": len(v.lines),
        "missingReceipts": sum(1 for ln in v.lines if not ln.file_ref),
        "totalCentavos": v.total_centavos, "paidOutCentavos": v.paid_out_centavos, "createdBy": v.created_by,
    }


def worked(db: DB, v: PettyCashVoucher):
    return work_out(db, [line_dict(ln) for ln in v.lines], v.voucher_date, v.amounts_include_vat)


def line_dict(ln: PettyCashLine) -> dict:
    return {"accountId": ln.account_id, "amountCentavos": ln.amount_centavos, "vat": ln.vat, "withholding": ln.withholding,
            "purchaseType": ln.purchase_type, "description": ln.description}


def voucher_out(db: DB, v: PettyCashVoucher, user=None) -> dict:
    # Totals are worked out whenever the voucher is saved, and again when it's submitted and posted.
    return summary(v) | (may(user, v) if user is not None else {}) | {
        "amountsIncludeVat": v.amounts_include_vat, "notes": v.notes,
        "lines": [{
            "id": ln.id, "position": ln.position, "spentOn": ln.spent_on.isoformat(), "store": ln.store, "storeTin": ln.store_tin,
            "receiptNumber": ln.receipt_number, "account": {"id": ln.account.id, "code": ln.account.code, "name": ln.account.name},
            "description": ln.description, "purchaseType": ln.purchase_type, "purchaseTypeLabel": PURCHASE_TYPES[ln.purchase_type],
            "vat": ln.vat, "vatLabel": VAT_KINDS[ln.vat], "withholding": ln.withholding,
            "withholdingRateBp": WITHHOLDING[ln.withholding][1] if ln.withholding in WITHHOLDING else None,
            "amountCentavos": ln.amount_centavos, "netCentavos": ln.net_centavos, "vatCentavos": ln.vat_centavos, "withheldCentavos": ln.withheld_centavos,
            "file": {"name": ln.file_name, "contentType": ln.file_type, "size": ln.file_size, "uploadedBy": ln.file_by,
                     "uploadedAt": ln.file_at.isoformat() if ln.file_at else None} if ln.file_ref else None,
        } for ln in v.lines],
        "netCentavos": v.net_centavos, "vatCentavos": v.vat_centavos, "withheldCentavos": v.withheld_centavos,
        "entryId": v.entry_id,
        "createdAt": v.created_at.isoformat(), "submittedAt": v.submitted_at.isoformat() if v.submitted_at else None,
        "checkedBy": v.checked_by, "checkedAt": v.checked_at.isoformat() if v.checked_at else None,
        "voidedBy": v.voided_by, "voidedAt": v.voided_at.isoformat() if v.voided_at else None, "voidReason": v.void_reason,
        "events": [{"at": e.at.isoformat(), "kind": e.kind, "who": e.who, "text": e.text} for e in v.events],
    }


def set_totals(v: PettyCashVoucher, w) -> None:
    for ln, out in zip(v.lines, w.lines):
        ln.net_centavos, ln.vat_centavos, ln.withheld_centavos = out["netCentavos"], out["vatCentavos"], out["withheldCentavos"]
    v.net_centavos, v.vat_centavos, v.withheld_centavos, v.total_centavos, v.paid_out_centavos = w.net, w.vat, w.withheld, w.total, w.payable


@router.get("/petty-cash/choices")
def choices(user: permitted("petty_cash.view"), db: DB) -> dict:
    """What a voucher's fields offer: the funds (with their balance), accounts, tax lists, and earlier PIC/department names."""
    accounts = db.scalars(select(Account).where(Account.is_active, Account.type.in_(("expense", "asset"))).order_by(Account.code))
    seen = lambda col: sorted({x for (x,) in db.execute(select(col).where(col.is_not(None)).distinct()) if x})  # noqa: E731
    return {
        "funds": funds_out(db),
        "accounts": [{"id": a.id, "code": a.code, "name": a.name, "type": a.type} for a in accounts],
        "vatKinds": [{"key": k, "label": v} for k, v in VAT_KINDS.items()],
        "purchaseTypes": [{"key": k, "label": v} for k, v in PURCHASE_TYPES.items()],
        "withholding": withholding_out(),
        "people": seen(PettyCashVoucher.person_in_charge), "departments": seen(PettyCashVoucher.department),
    }


@router.get("/petty-cash")
def list_vouchers(user: permitted("petty_cash.view"), db: DB, show: Literal["draft", "to_check", "returned", "posted", "void", "all"] | None = None,
                  q: str | None = Query(None, max_length=100)) -> dict:
    """The vouchers at one step (or all), newest first, with each step's count and what waits for this person."""
    counts = dict(db.execute(select(PettyCashVoucher.status, func.count()).group_by(PettyCashVoucher.status)).all())
    query = select(PettyCashVoucher)
    if show and show != "all":
        query = query.where(PettyCashVoucher.status == show)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(func.lower(PettyCashVoucher.number).like(like) | func.lower(func.coalesce(PettyCashVoucher.person_in_charge, "")).like(like)
                            | func.lower(func.coalesce(PettyCashVoucher.department, "")).like(like))
    rows = list(db.scalars(query.order_by(PettyCashVoucher.voucher_date.desc(), PettyCashVoucher.created_at.desc()).limit(200)))
    can = access_of(user).can
    waiting = db.scalars(select(PettyCashVoucher).where(PettyCashVoucher.status.in_(("to_check", "returned")))).all()
    return {
        "items": [summary(v) | may(user, v) for v in rows], "limited": len(rows) == 200,
        "counts": {k: counts.get(k, 0) for k in SHOWS} | {"all": sum(counts.values())},
        # "Waiting for you": vouchers to check (not your own) and your returned ones; "waiting on others": yours being checked.
        "waitingForYou": sum(1 for v in waiting if (v.status == "to_check" and can("petty_cash.check") and user.id not in preparers(v))
                             or (v.status == "returned" and user.id in preparers(v))),
        "waitingOnOthers": sum(1 for v in waiting if v.status == "to_check" and user.id in preparers(v)),
        "funds": funds_out(db),
        "may": {"create": can("petty_cash.create"), "check": can("petty_cash.check"), "void": can("petty_cash.void")},
    }


def found(db: DB, voucher_id: str) -> PettyCashVoucher:
    v = db.get(PettyCashVoucher, voucher_id)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such petty cash voucher.")
    return v


@router.get("/petty-cash/{voucher_id}")
def read(user: permitted("petty_cash.view"), db: DB, voucher_id: str) -> dict:
    return voucher_out(db, found(db, voucher_id), user)


# --- making and changing a voucher -------------------------------------------------------------------


class LineIn(Api):
    id: str | None = Field(None, max_length=36)  # an existing receipt line keeps its file
    spent_on: date
    store: str = Field(min_length=1, max_length=200)
    store_tin: str | None = Field(None, max_length=20)
    receipt_number: str = Field(min_length=1, max_length=60)
    account_id: str
    description: str | None = Field(None, max_length=200)
    purchase_type: Literal["services", "capital_goods", "other_goods", "importation"]
    vat: Literal["vat", "zero", "exempt", "none"]
    withholding: str | None = Field(None, max_length=10)
    amount_centavos: int = Field(gt=0, lt=10**11)


class VoucherIn(Api):
    number: str = Field(min_length=1, max_length=60)
    fund_account_id: str
    voucher_date: date
    person_in_charge: str | None = Field(None, max_length=120)
    department: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=500)
    amounts_include_vat: bool = True
    lines: list[LineIn] = Field(min_length=1, max_length=100)


def key_of(number: str) -> str:
    return re.sub(r"\s+", " ", number.strip()).lower()


def line_error(i: int, field: str, message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "lines", i, field], "msg": message}])


def apply(db: DB, settings, v: PettyCashVoucher, body: VoucherIn, user) -> None:
    number = re.sub(r"\s+", " ", body.number.strip())
    twin = db.scalar(select(PettyCashVoucher).where(PettyCashVoucher.number_key == key_of(number), PettyCashVoucher.status != "void",
                                                    PettyCashVoucher.id != (v.id or "")))
    if twin:
        raise field_error("number", f"Petty cash voucher {twin.number} is already here ({STATUS_LABELS[twin.status].lower()}).")
    if body.fund_account_id not in fund_ids(db) or not (fund := db.get(Account, body.fund_account_id)).is_active:
        raise field_error("fundAccountId", "Pick an active petty cash fund (an account under Cash named Petty Cash).")
    if body.voucher_date > today(settings):
        raise field_error("voucherDate", "The voucher date can't be in the future.")
    existing = {ln.id: ln for ln in v.lines}
    kept: list[PettyCashLine] = []
    for i, line in enumerate(body.lines):
        a = db.get(Account, line.account_id)
        if a is None or not a.is_active or a.type not in ("expense", "asset"):
            raise line_error(i, "accountId", "Pick an active expense or asset account.")
        if line.withholding and line.withholding not in WITHHOLDING:
            raise line_error(i, "withholding", "Pick a withholding code from the list.")
        if line.spent_on > body.voucher_date:
            raise line_error(i, "spentOn", "A receipt can't be dated after its voucher.")
        tin = None
        if line.store_tin and line.store_tin.strip():
            try:
                main, branch = split_tin(line.store_tin)
            except ValueError as problem:
                raise line_error(i, "storeTin", str(problem)) from None
            tin = f"{main}-{branch}" if branch else main
        if line.id and line.id not in existing:
            raise line_error(i, "id", "This receipt line isn't on this voucher. Reload and try again.")
        ln = existing.pop(line.id) if line.id else PettyCashLine()
        ln.position, ln.spent_on, ln.store, ln.store_tin = i + 1, line.spent_on, line.store.strip(), tin
        ln.receipt_number, ln.account_id, ln.description = line.receipt_number.strip(), a.id, (line.description or "").strip() or None
        ln.purchase_type, ln.vat, ln.withholding, ln.amount_centavos = line.purchase_type, line.vat, line.withholding or None, line.amount_centavos
        kept.append(ln)
    for gone in existing.values():  # removed receipt lines take their files with them
        if gone.file_ref and (stored := db.get(StoredFile, gone.file_ref)):
            db.delete(stored)
    v.lines = kept
    v.number, v.number_key, v.fund_account_id, v.voucher_date = number, key_of(number), fund.id, body.voucher_date
    v.person_in_charge = (body.person_in_charge or "").strip() or None
    v.department = (body.department or "").strip() or None
    v.notes, v.amounts_include_vat = (body.notes or "").strip() or None, body.amounts_include_vat
    db.add(v)
    try:
        db.flush()
    except IntegrityError:  # saved at the same moment by someone else (the database keeps a number once)
        db.rollback()
        raise field_error("number", f"Petty cash voucher {number} was just saved by someone else. Reload to see it.") from None
    db.refresh(v, ["fund"])
    set_totals(v, worked(db, v))


def editable(v: PettyCashVoucher) -> None:
    if v.status not in ("draft", "returned"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This voucher is {STATUS_LABELS[v.status].lower()}: only a draft or a returned voucher is changed. A posted one is voided and entered again.")


def event(v: PettyCashVoucher, kind: str, user, text: str | None = None) -> None:
    v.events.append(PettyCashEvent(kind=kind, who=user.full_name[:120], who_id=user.id, text=(text or None) and text[:300]))


def link(v: PettyCashVoucher) -> str:
    return f"/petty-cash/{v.id}"


def name(v: PettyCashVoucher) -> str:
    return f"petty cash voucher {v.number} ({v.fund.name}, {peso(v.total_centavos)})"


def content(v: PettyCashVoucher) -> dict:
    """What a voucher says: what each signature on it vouches for."""
    return {"number": v.number, "fund": v.fund_account_id, "date": v.voucher_date.isoformat(),
            "lines": [[ln.spent_on.isoformat(), ln.store, ln.store_tin, ln.receipt_number, ln.account_id, ln.amount_centavos, ln.vat, ln.withholding, ln.file_ref] for ln in v.lines],
            "net": v.net_centavos, "vat": v.vat_centavos, "withheld": v.withheld_centavos, "paidOut": v.paid_out_centavos}


@router.post("/petty-cash", status_code=status.HTTP_201_CREATED)
def add(user: permitted("petty_cash.create"), db: DB, settings: SettingsDep, body: VoucherIn) -> dict:
    v = PettyCashVoucher(created_by=user.full_name[:120], created_by_id=user.id)
    apply(db, settings, v, body, user)
    audit(db, user, "petty_cash.created", target=v.number, target_type="petty_cash", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


@router.put("/petty-cash/{voucher_id}")
def change(user: permitted("petty_cash.create"), db: DB, settings: SettingsDep, voucher_id: str, body: VoucherIn) -> dict:
    v = found(db, voucher_id)
    editable(v)
    apply(db, settings, v, body, user)
    audit(db, user, "petty_cash.updated", target=v.number, target_type="petty_cash", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


@router.delete("/petty-cash/{voucher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(user: permitted("petty_cash.create"), db: DB, voucher_id: str) -> Response:
    v = found(db, voucher_id)
    editable(v)
    refs = [ln.file_ref for ln in v.lines if ln.file_ref]
    audit(db, user, "petty_cash.deleted", target=v.number, target_type="petty_cash", target_id=v.id)
    done(db, "petty_cash.returned", link(v))
    db.delete(v)
    for ref in refs:
        if stored := db.get(StoredFile, ref):
            db.delete(stored)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- each receipt's photo or PDF ----------------------------------------------------------------------


def found_line(v: PettyCashVoucher, line_id: str) -> PettyCashLine:
    ln = next((x for x in v.lines if x.id == line_id), None)
    if ln is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such receipt line on this voucher.")
    return ln


@router.post("/petty-cash/{voucher_id}/lines/{line_id}/file", status_code=status.HTTP_201_CREATED)
def attach(user: permitted("petty_cash.create"), db: DB, voucher_id: str, line_id: str, body: FileIn) -> dict:
    """The receipt for one line (a photo or a PDF, up to 3 MB). Attaching again replaces it, while the voucher can still be changed."""
    v = found(db, voucher_id)
    editable(v)
    ln = found_line(v, line_id)
    old = ln.file_ref
    ref, size = store_file(db, body)
    ln.file_ref, ln.file_name, ln.file_type, ln.file_size = ref, body.name.strip()[:200], body.content_type, size
    ln.file_by, ln.file_at = user.full_name[:120], datetime.now(UTC)
    if old and (stored := db.get(StoredFile, old)):
        db.delete(stored)
    audit(db, user, "petty_cash.receipt_added", target=f"{v.number} line {ln.position}", target_type="petty_cash", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


@router.get("/petty-cash/{voucher_id}/lines/{line_id}/file")
def open_receipt(user: permitted("petty_cash.view"), db: DB, voucher_id: str, line_id: str) -> Response:
    ln = found_line(found(db, voucher_id), line_id)
    if not ln.file_ref:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This receipt line has no file yet.")
    stored = db.get(StoredFile, ln.file_ref)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The file is no longer here.")
    filename = (ln.file_name or "receipt").replace('"', "")
    return Response(stored.data, media_type=stored.content_type, headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.delete("/petty-cash/{voucher_id}/lines/{line_id}/file")
def remove_receipt(user: permitted("petty_cash.create"), db: DB, voucher_id: str, line_id: str) -> dict:
    v = found(db, voucher_id)
    editable(v)
    ln = found_line(v, line_id)
    if ln.file_ref and (stored := db.get(StoredFile, ln.file_ref)):
        db.delete(stored)
    ln.file_ref = ln.file_name = ln.file_type = ln.file_size = ln.file_by = ln.file_at = None
    audit(db, user, "petty_cash.receipt_removed", target=f"{v.number} line {ln.position}", target_type="petty_cash", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


# --- submitted, checked and posted (or returned), voided --------------------------------------------------


@router.post("/petty-cash/{voucher_id}/submit")
def submit(user: permitted("petty_cash.create"), db: DB, voucher_id: str) -> dict:
    v = found(db, voucher_id)
    editable(v)
    missing = [ln.position for ln in v.lines if not ln.file_ref]
    if missing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Attach the receipt for line {', '.join(map(str, missing))} first: every receipt is attached before submitting.")
    if not v.fund.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{v.fund.name} is switched off. Pick another fund.")
    set_totals(v, worked(db, v))
    again = v.status == "returned"
    v.status, v.submitted_by_id, v.submitted_at = "to_check", user.id, datetime.now(UTC)
    v.checked_by = v.checked_by_id = v.checked_at = None
    event(v, "resubmitted" if again else "submitted", user)
    sign(db, user, "petty_cash", v.id, "prepared", content(v))
    done(db, "petty_cash.returned", link(v))
    tell(db, [u for u in holders(db, "petty_cash.check") if u.id not in preparers(v)], "petty_cash.to_check",
         f"{user.full_name} {'resubmitted' if again else 'submitted'} {name(v)}. Waiting for you to check it.", link=link(v))
    audit(db, user, "petty_cash.submitted", target=v.number, target_type="petty_cash", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


def waiting_check(user, v: PettyCashVoucher) -> None:
    if v.status != "to_check":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This voucher is {STATUS_LABELS[v.status].lower()}: someone may have acted on it already. Reload to see where it stands.")
    if user.id in preparers(v):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You made or submitted this voucher, so someone else checks it.")


def posting(db: DB, v: PettyCashVoucher, w) -> list[Leg]:
    s = posting_settings(db)
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_({ln["accountId"] for ln in w.lines})))}
    if any(not accounts[ln["accountId"]].is_active for ln in w.lines):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account on this voucher has been switched off. Return it so it's corrected.")
    legs = [Leg(accounts[out["accountId"]], debit=out["netCentavos"], description=f"{ln.store}, receipt {ln.receipt_number}"[:200])
            for ln, out in zip(v.lines, w.lines)]
    legs.append(Leg(db.get(Account, s.input_tax_account_id) if s.input_tax_account_id else None, debit=w.vat, description="Input VAT"))
    legs.append(Leg(v.fund, credit=w.payable, description=f"Petty cash voucher {v.number}"[:200]))
    legs.append(Leg(db.get(Account, s.withholding_account_id) if s.withholding_account_id else None, credit=w.withheld, description="Tax withheld (EWT)"))
    return legs


@router.post("/petty-cash/{voucher_id}/check")
def check(user: permitted("petty_cash.check"), db: DB, voucher_id: str) -> dict:
    """Checked against its receipts and posted: Dr accounts and Input VAT, Cr the fund and tax withheld."""
    v = found(db, voucher_id)
    waiting_check(user, v)
    if not v.fund.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{v.fund.name} is switched off. Return the voucher so another fund is picked.")
    w = worked(db, v)
    set_totals(v, w)
    e = post(db, v.voucher_date, f"Petty cash voucher {v.number} ({v.fund.name})"[:300], posting(db, v, w), user.full_name,
             reference=v.number[:80], source="petty_cash", by_id=user.id)
    v.status, v.entry_id = "posted", e.id
    v.checked_by, v.checked_by_id, v.checked_at = user.full_name[:120], user.id, datetime.now(UTC)
    event(v, "posted", user)
    sign(db, user, "petty_cash", v.id, "checked", content(v))
    done(db, "petty_cash.to_check", link(v))
    tell(db, [v.submitted_by_id], "petty_cash.posted", f"{user.full_name} checked and posted {name(v)}.", link=link(v), not_to=[user.id])
    audit(db, user, "petty_cash.posted", target=v.number, target_type="petty_cash", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)


class ReasonIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/petty-cash/{voucher_id}/return")
def return_voucher(user: permitted("petty_cash.check"), db: DB, voucher_id: str, body: ReasonIn) -> dict:
    """Back to whoever submitted it, with the reason; corrected, it's submitted again."""
    v = found(db, voucher_id)
    waiting_check(user, v)
    reason = body.reason.strip()
    v.status = "returned"
    event(v, "returned", user, reason)
    done(db, "petty_cash.to_check", link(v))
    tell(db, [v.submitted_by_id], "petty_cash.returned", f"{user.full_name} returned {name(v)}: {reason}", link=link(v), not_to=[user.id])
    audit(db, user, "petty_cash.returned", target=v.number, target_type="petty_cash", target_id=v.id, fields=["reason"])
    db.commit()
    return voucher_out(db, v, user)


@router.post("/petty-cash/{voucher_id}/void")
def void(user: permitted("petty_cash.void"), db: DB, settings: SettingsDep, voucher_id: str, body: ReasonIn) -> dict:
    """A posted voucher, cancelled: its entry reversed today; the voucher, its receipts and history kept."""
    v = found(db, voucher_id)
    if v.status != "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a posted voucher is voided. A draft is deleted; one waiting to be checked is returned first.")
    reason = body.reason.strip()
    entry = db.get(JournalEntry, v.entry_id) if v.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of petty cash voucher {v.number}: {reason}"[:300], legs, user.full_name,
             reference=v.number[:80], source="petty_cash", reverses=entry, by_id=user.id)
    v.status, v.void_reason, v.voided_at, v.voided_by = "void", reason, datetime.now(UTC), user.full_name[:120]
    event(v, "voided", user, reason)
    audit(db, user, "petty_cash.voided", target=v.number, target_type="petty_cash", target_id=v.id)
    db.commit()
    return voucher_out(db, v, user)
