"""Supplier prepayments (1401-000) and customer deposits / retainers (2205-000) (migration 0042).

- Posting an advance records cash out/in against an Advance Asset or Deposit Liability (without double-counting VAT).
- Applying an advance to a Bill or Invoice transfers the balance cleanly from Advance/Deposit into AP/AR.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.finance import company_scope
from modules.finance.access import CurrentAccess, permitted
from modules.finance.audit import audit
from modules.finance.deps import DB, SettingsDep
from modules.finance.ledger import Leg, account, money_account, post
from modules.finance.ledger import settings as posting_settings
from modules.finance.locks import locked
from modules.finance.models import Account, Advance, AdvanceApplication, BankAccount, Bill, Invoice, JournalEntry, Supplier
from modules.finance.routers.credits import VoidNoteIn, _next_seq
from modules.finance.routers.funds import today
from modules.finance.routers.tax import Api, field_error, iso
from modules.finance.settlements import bill_settled, bill_settled_map, invoice_settled, invoice_settled_map

router = APIRouter(prefix="/advances", tags=["advances"])


def _default_advance_account(db: Session, kind: str) -> Account:
    s = posting_settings(db)
    if kind == "supplier":
        acc = (
            db.scalar(select(Account).where(Account.is_active, Account.code == "1401-000"))
            or db.scalar(select(Account).where(Account.is_active, Account.type == "asset", func.lower(Account.name).like("%advance%supplier%")))
            or account(db, s.advances_account_id)
        )
        if acc is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "No active supplier advances account (1401-000) is set.")
        return acc
    acc = (
        db.scalar(select(Account).where(Account.is_active, Account.code == "2205-000"))
        or db.scalar(select(Account).where(Account.is_active, Account.type == "liability", func.lower(Account.name).like("%customer deposit%")))
        or db.scalar(select(Account).where(Account.is_active, Account.type == "liability", or_(func.lower(Account.name).like("%deposit%"), func.lower(Account.name).like("%unearned%"))))
    )
    if acc is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create or activate a Customer Deposits liability account (e.g. 2205-000) first.")
    return acc


def _money_gl(db: Session, method: str, bank_account_id: str | None) -> Account:
    s = posting_settings(db)
    if bank_account_id:
        ba = db.get(BankAccount, bank_account_id)
        if ba is None or not ba.is_active:
            raise field_error("bankAccountId", "Pick an active bank or cash account.")
        acc = account(db, ba.account_id)
        if acc is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "That bank account has no ledger account.")
        return acc
    acc = money_account(db, method)
    if acc is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Set default cash/bank accounts under Accounting first.")
    return acc


def _applied_total(db: Session, target_kind: str, target_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(AdvanceApplication.amount_centavos), 0))
            .where(AdvanceApplication.target_kind == target_kind, AdvanceApplication.target_id == target_id, AdvanceApplication.removed_at.is_(None))
        )
        or 0
    )


class AdvanceIn(Api):
    kind: Literal["supplier", "customer"]
    party_id: str | None = Field(None, max_length=36)
    party_name: str = Field(min_length=1, max_length=200)
    advance_date: date
    method: Literal["cash", "bank", "ewallet", "check"] = "bank"
    bank_account_id: str | None = Field(None, max_length=36)
    advance_account_id: str | None = Field(None, max_length=36)
    reference: str | None = Field(None, max_length=80)
    notes: str | None = Field(None, max_length=500)
    amount_centavos: int = Field(gt=0)


class AdvanceApplyIn(Api):
    target_id: str = Field(min_length=1, max_length=36)
    applied_on: date
    amount_centavos: int = Field(gt=0)


def _advance_out(adv: Advance) -> dict:
    return {
        "id": adv.id,
        "kind": adv.kind,
        "status": adv.status,
        "number": adv.number,
        "partyId": adv.party_id,
        "partyName": adv.party_name,
        "date": adv.advance_date.isoformat(),
        "method": adv.method,
        "bankAccountId": adv.bank_account_id,
        "advanceAccountId": adv.advance_account_id,
        "reference": adv.reference,
        "notes": adv.notes,
        "amountCentavos": adv.amount_centavos,
        "appliedCentavos": adv.applied_centavos,
        "remainingCentavos": max(0, adv.amount_centavos - adv.applied_centavos) if adv.status == "posted" else 0,
        "entryId": adv.entry_id,
        "createdBy": adv.created_by,
        "createdAt": iso(adv.created_at),
        "voidedBy": adv.voided_by,
        "voidedAt": iso(adv.voided_at),
        "voidReason": adv.void_reason,
        "applications": [
            {
                "id": app.id,
                "targetKind": app.target_kind,
                "targetId": app.target_id,
                "appliedOn": app.applied_on.isoformat(),
                "amountCentavos": app.amount_centavos,
                "entryId": app.entry_id,
                "removedAt": iso(app.removed_at),
                "removedBy": app.removed_by,
            }
            for app in adv.applications
        ],
    }


@router.get("")
def list_advances(access: CurrentAccess, db: DB, kind: Literal["supplier", "customer"] | None = Query(None)) -> dict:
    if not (access.can("invoices.view") or access.can("bills.view") or access.can("vouchers.view")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow that.")
    q = select(Advance).order_by(Advance.advance_date.desc(), Advance.created_at.desc())
    if kind:
        q = q.where(Advance.kind == kind)
    items = [_advance_out(a) for a in db.scalars(q)]
    banks = [{"id": b.id, "name": b.name, "kind": b.kind} for b in db.scalars(select(BankAccount).where(BankAccount.is_active).order_by(BankAccount.name))]
    sup_q = select(Supplier).where(Supplier.is_active).order_by(func.lower(Supplier.name))
    if company_scope.configured(db, "supplier"):
        sup_q = sup_q.where(company_scope.usable_clause("supplier", Supplier.id))
    suppliers = [{"id": s.id, "name": s.name} for s in db.scalars(sup_q)]
    bill_rows = list(db.scalars(select(Bill).where(Bill.status == "recorded").order_by(Bill.bill_date.desc()).limit(200)))
    b_settled = bill_settled_map(db, [b.id for b in bill_rows])
    open_bills = [
        {"id": b.id, "no": b.no, "billNumber": b.bill_number, "supplierId": b.supplier_id, "supplierName": b.supplier.name,
         "owedCentavos": max(0, b.payable_centavos - b.paid_centavos - b_settled.get(b.id, 0))}
        for b in bill_rows
    ]
    inv_rows = list(db.scalars(select(Invoice).where(Invoice.status == "issued").order_by(Invoice.invoice_date.desc()).limit(200)))
    i_settled = invoice_settled_map(db, [i.id for i in inv_rows])
    open_invoices = [
        {"id": i.id, "number": i.number, "customerName": i.customer_name,
         "owedCentavos": max(0, i.total_centavos - i.paid_centavos - i_settled.get(i.id, 0))}
        for i in inv_rows
    ]
    return {"items": items, "banks": banks, "suppliers": suppliers, "bills": open_bills, "invoices": open_invoices}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_advance(user: permitted("vouchers.prepare"), db: DB, settings: SettingsDep, body: AdvanceIn) -> dict:
    if body.advance_date > today(settings):
        raise field_error("advanceDate", "Date can't be in the future.")
    party_name = body.party_name.strip()
    if body.kind == "supplier" and body.party_id:
        sup = db.get(Supplier, body.party_id)
        if sup is None or not sup.is_active:
            raise field_error("partyId", "Pick an active supplier.")
        party_name = sup.name
    adv_acc = account(db, body.advance_account_id) if body.advance_account_id else _default_advance_account(db, body.kind)
    if adv_acc is None or not adv_acc.is_active:
        raise field_error("advanceAccountId", "Pick an active advance/deposit account.")
    cash_acc = _money_gl(db, body.method, body.bank_account_id)
    number = _next_seq(db, Advance, "ADV" if body.kind == "supplier" else "DEP", body.advance_date)
    if body.kind == "supplier":
        legs = [Leg(adv_acc, debit=body.amount_centavos, description=party_name), Leg(cash_acc, credit=body.amount_centavos)]
        memo = f"{number}: prepayment to {party_name}"
    else:
        legs = [Leg(cash_acc, debit=body.amount_centavos), Leg(adv_acc, credit=body.amount_centavos, description=party_name)]
        memo = f"{number}: customer deposit from {party_name}"
    entry = post(db, body.advance_date, memo[:300], legs, user.full_name, reference=body.reference or number, source="advance", by_id=user.id)
    adv = Advance(
        kind=body.kind, status="posted", number=number, party_id=body.party_id, party_name=party_name,
        advance_date=body.advance_date, method=body.method, bank_account_id=body.bank_account_id,
        advance_account_id=adv_acc.id, reference=body.reference, notes=body.notes,
        amount_centavos=body.amount_centavos, entry_id=entry.id, created_by=user.full_name,
    )
    db.add(adv)
    db.flush()
    audit(db, user, "advance.posted", target=f"{number} {party_name}", target_type="advance", target_id=adv.id)
    db.commit()
    db.refresh(adv)
    return _advance_out(adv)


@router.post("/{advance_id}/apply")
def apply_advance(user: permitted("vouchers.prepare"), db: DB, settings: SettingsDep, advance_id: str, body: AdvanceApplyIn) -> dict:
    adv = db.get(Advance, advance_id)
    if adv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such advance.")
    if adv.status != "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an active posted advance can be applied.")
    if body.applied_on > today(settings):
        raise field_error("appliedOn", "Application date can't be in the future.")
    rem = adv.amount_centavos - adv.applied_centavos
    if body.amount_centavos > rem:
        raise field_error("amountCentavos", "Amount exceeds remaining unapplied advance.")
    s = posting_settings(db)
    adv_acc = account(db, adv.advance_account_id)
    if adv.kind == "supplier":
        b = db.get(Bill, body.target_id)
        if b is None or b.status != "recorded":
            raise field_error("targetId", "Pick a recorded bill.")
        [b] = locked(db, Bill, [b.id])
        owed = max(0, b.payable_centavos - b.paid_centavos - bill_settled(db, b.id))
        if body.amount_centavos > owed:
            raise field_error("amountCentavos", "Amount exceeds the bill's remaining payable.")
        ap_acc = account(db, b.payables_account_id or s.payables_account_id)
        legs = [Leg(ap_acc, debit=body.amount_centavos, description=b.bill_number), Leg(adv_acc, credit=body.amount_centavos)]
        entry = post(db, body.applied_on, f"Apply {adv.number} to bill {b.bill_number}", legs, user.full_name, reference=adv.number, source="advance", by_id=user.id)
        target_kind = "bill"
    else:
        inv = db.get(Invoice, body.target_id)
        if inv is None or inv.status != "issued":
            raise field_error("targetId", "Pick an issued invoice.")
        [inv] = locked(db, Invoice, [inv.id])
        owed = max(0, inv.total_centavos - inv.paid_centavos - invoice_settled(db, inv.id))
        if body.amount_centavos > owed:
            raise field_error("amountCentavos", "Amount exceeds the invoice's remaining balance.")
        ar_acc = account(db, s.receivables_account_id)
        legs = [Leg(adv_acc, debit=body.amount_centavos), Leg(ar_acc, credit=body.amount_centavos, description=inv.number)]
        entry = post(db, body.applied_on, f"Apply {adv.number} to invoice {inv.number}", legs, user.full_name, reference=adv.number, source="advance", by_id=user.id)
        target_kind = "invoice"
    db.add(AdvanceApplication(
        advance_id=adv.id, target_kind=target_kind, target_id=body.target_id,
        applied_on=body.applied_on, amount_centavos=body.amount_centavos, entry_id=entry.id, created_by=user.full_name,
    ))
    adv.applied_centavos += body.amount_centavos
    db.commit()
    db.refresh(adv)
    return _advance_out(adv)


@router.delete("/{advance_id}/applications/{app_id}")
def remove_application(user: permitted("bills.void"), db: DB, settings: SettingsDep, advance_id: str, app_id: str) -> dict:
    adv = db.get(Advance, advance_id)
    if adv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such advance.")
    app = next((x for x in adv.applications if x.id == app_id), None)
    if app is None or app.removed_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no active application here.")
    entry = db.get(JournalEntry, app.entry_id) if app.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Unapply {adv.number}", legs, user.full_name, reference=adv.number, source="advance", reverses=entry, by_id=user.id)
    app.removed_at, app.removed_by = datetime.now(UTC), user.full_name
    adv.applied_centavos = max(0, adv.applied_centavos - app.amount_centavos)
    db.commit()
    db.refresh(adv)
    return _advance_out(adv)


@router.post("/{advance_id}/void")
def void_advance(user: permitted("bills.void"), db: DB, settings: SettingsDep, advance_id: str, body: VoidNoteIn) -> dict:
    adv = db.get(Advance, advance_id)
    if adv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such advance.")
    if adv.status != "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an active advance can be voided.")
    if adv.applied_centavos > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Remove bill/invoice applications before voiding.")
    entry = db.get(JournalEntry, adv.entry_id) if adv.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of {adv.number}: {body.reason.strip()}"[:300], legs, user.full_name, reference=adv.number, source="advance", reverses=entry, by_id=user.id)
    adv.status, adv.void_reason = "void", body.reason.strip()
    adv.voided_at, adv.voided_by = datetime.now(UTC), user.full_name
    db.commit()
    db.refresh(adv)
    return _advance_out(adv)
