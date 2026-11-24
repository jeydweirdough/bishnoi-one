"""Customer credit notes and supplier vendor credits (migration 0042).

- Customer credit notes: draft -> issued (reverses Sales/VAT and credits AR) -> apply to unpaid invoices, or void.
- Supplier vendor credits: draft -> recorded (debits AP and reverses Expense/Input VAT/EWT) -> apply to unpaid bills, or void.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.finance import company_scope
from modules.finance.access import permitted
from modules.finance.audit import audit
from modules.finance.deps import DB, SettingsDep
from modules.finance.ledger import Leg, account, post
from modules.finance.ledger import settings as posting_settings
from modules.finance.locks import locked
from modules.finance.models import (
    Account,
    Bill,
    CreditAllocation,
    CreditNote,
    Invoice,
    JournalEntry,
    Supplier,
    VendorCredit,
    VendorCreditAllocation,
)
from modules.finance.payables import PURCHASE_TYPES, VAT_KINDS, WITHHOLDING, withholding_decision, work_out as bill_work_out
from modules.finance.routers.funds import today
from modules.finance.routers.invoices import InvoiceLineBody, _validate_line_accounts, tax_of
from modules.finance.routers.tax import Api, BuyerBody, LineBody, SaleBody, field_error, iso, work_out as sale_work_out
from modules.finance.settlements import bill_settled, bill_settled_map, invoice_settled, invoice_settled_map

router = APIRouter(tags=["credits"])


def _next_seq(db: Session, model, prefix: str, on: date) -> str:
    stem = f"{prefix}-{on:%Y%m}-"
    existing = db.scalars(select(model.number).where(model.number.like(f"{stem}%"))).all()
    top = 0
    for num in existing:
        tail = str(num or "").removeprefix(stem)
        if tail.isdigit():
            top = max(top, int(tail))
    return f"{stem}{top + 1:04d}"


def _invoice_credit_applied(db: Session, invoice_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(CreditAllocation.amount_centavos), 0))
            .where(CreditAllocation.invoice_id == invoice_id, CreditAllocation.removed_at.is_(None))
        )
        or 0
    )


def _bill_credit_applied(db: Session, bill_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(VendorCreditAllocation.amount_centavos), 0))
            .where(VendorCreditAllocation.bill_id == bill_id, VendorCreditAllocation.removed_at.is_(None))
        )
        or 0
    )


# --- Customer Credit Notes ---------------------------------------------------------------------


class CreditNoteIn(Api):
    invoice_id: str | None = Field(None, max_length=36)
    customer_id: str | None = Field(None, max_length=36)
    customer_name: str = Field(min_length=1, max_length=200)
    customer_tin: str | None = Field(None, max_length=20)
    customer_address: str | None = Field(None, max_length=300)
    treatment: str = Field("regular", max_length=20)
    buyer_id_number: str | None = Field(None, max_length=40)
    credit_date: date
    reference: str | None = Field(None, max_length=80)
    reason: str | None = Field(None, max_length=500)
    prices_include_tax: bool | None = None
    lines: list[InvoiceLineBody] = Field(min_length=1, max_length=200)


class CreditApplyIn(Api):
    invoice_id: str = Field(min_length=1, max_length=36)
    applied_on: date
    amount_centavos: int = Field(gt=0)


class VoidNoteIn(Api):
    reason: str = Field(min_length=3, max_length=300)


def _sale_of_cn(cn: CreditNote) -> SaleBody:
    return SaleBody(
        treatment=cn.treatment,
        on=cn.credit_date,
        prices_include_tax=cn.prices_include_tax,
        buyer=BuyerBody(name=cn.customer_name, tin=cn.customer_tin, address=cn.customer_address, id_number=cn.buyer_id_number),
        lines=[LineBody(**{k: v for k, v in ln.items() if k != "accountId"}) for ln in cn.lines],
    )


def _cn_out(cn: CreditNote) -> dict:
    return {
        "id": cn.id,
        "status": cn.status,
        "number": cn.number,
        "invoiceId": cn.invoice_id,
        "customer": {"id": cn.customer_id, "name": cn.customer_name, "tin": cn.customer_tin, "address": cn.customer_address},
        "treatment": cn.treatment,
        "buyerIdNumber": cn.buyer_id_number,
        "date": cn.credit_date.isoformat(),
        "reference": cn.reference,
        "reason": cn.reason,
        "pricesIncludeTax": cn.prices_include_tax,
        "lines": cn.lines,
        "computed": cn.computed,
        "totalCentavos": cn.total_centavos,
        "taxCentavos": cn.tax_centavos,
        "appliedCentavos": cn.applied_centavos,
        "remainingCentavos": max(0, cn.total_centavos - cn.applied_centavos) if cn.status == "issued" else 0,
        "entryId": cn.entry_id,
        "createdBy": cn.created_by,
        "createdAt": iso(cn.created_at),
        "issuedBy": cn.issued_by,
        "issuedAt": iso(cn.issued_at),
        "voidedBy": cn.voided_by,
        "voidedAt": iso(cn.voided_at),
        "voidReason": cn.void_reason,
        "allocations": [
            {
                "id": a.id,
                "invoiceId": a.invoice_id,
                "appliedOn": a.applied_on.isoformat(),
                "amountCentavos": a.amount_centavos,
                "removedAt": iso(a.removed_at),
                "removedBy": a.removed_by,
            }
            for a in cn.allocations
        ],
    }


def _found_cn(db: Session, cn_id: str) -> CreditNote:
    cn = db.get(CreditNote, cn_id)
    if cn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such credit note.")
    return cn


def _fill_cn(db: Session, cn: CreditNote, body: CreditNoteIn, settings) -> None:
    if body.credit_date > today(settings):
        raise field_error("creditDate", "A credit note can't be dated in the future.")
    if body.invoice_id:
        inv = db.get(Invoice, body.invoice_id)
        if inv is None or inv.status != "issued":
            raise field_error("invoiceId", "Link to an issued invoice.")
    _validate_line_accounts(db, [ln.account_id for ln in body.lines])
    for k, v in body.model_dump(exclude={"lines"}).items():
        setattr(cn, k, v)
    cn.lines = [
        {k: v for k, v in ln.model_dump(mode="json", by_alias=True).items() if k != "accountId" or v is not None}
        for ln in body.lines
    ]
    computed = sale_work_out(db, settings, _sale_of_cn(cn))
    cn.computed = computed
    cn.total_centavos = computed["totalDueCentavos"]
    cn.tax_centavos = tax_of(computed)


@router.get("/credit-notes")
def list_credit_notes(_: permitted("invoices.view"), db: DB, status_: str | None = Query(None, alias="status")) -> dict:
    q = select(CreditNote).order_by(CreditNote.credit_date.desc(), CreditNote.created_at.desc())
    if status_ in ("draft", "issued", "void"):
        q = q.where(CreditNote.status == status_)
    rows = list(db.scalars(q))
    inv_rows = list(db.scalars(select(Invoice).where(Invoice.status == "issued").order_by(Invoice.invoice_date.desc()).limit(200)))
    settled_map = invoice_settled_map(db, [inv.id for inv in inv_rows])
    invoices = [
        {"id": inv.id, "number": inv.number, "customerName": inv.customer_name, "customerTin": inv.customer_tin, "balanceCentavos": max(0, inv.total_centavos - inv.paid_centavos - settled_map.get(inv.id, 0))}
        for inv in inv_rows
    ]
    acct_q = select(Account).where(Account.is_active, Account.type == "income").order_by(Account.code)
    if company_scope.configured(db, "account"):
        acct_q = acct_q.where(company_scope.usable_clause("account", Account.id))
    income_accounts = [{"id": a.id, "code": a.code, "name": a.name} for a in db.scalars(acct_q)]
    return {
        "items": [_cn_out(c) for c in rows],
        "invoices": invoices,
        "incomeAccounts": income_accounts,
    }


@router.post("/credit-notes", status_code=status.HTTP_201_CREATED)
def add_credit_note(user: permitted("invoices.create"), db: DB, settings: SettingsDep, body: CreditNoteIn) -> dict:
    cn = CreditNote(created_by=user.full_name, lines=[])
    _fill_cn(db, cn, body, settings)
    db.add(cn)
    db.flush()
    audit(db, user, "credit_note.drafted", target=cn.customer_name, target_type="credit_note", target_id=cn.id)
    db.commit()
    return _cn_out(cn)


@router.put("/credit-notes/{cn_id}")
def update_credit_note(user: permitted("invoices.create"), db: DB, settings: SettingsDep, cn_id: str, body: CreditNoteIn) -> dict:
    cn = _found_cn(db, cn_id)
    if cn.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft credit note can be edited.")
    _fill_cn(db, cn, body, settings)
    audit(db, user, "credit_note.updated", target=cn.customer_name, target_type="credit_note", target_id=cn.id)
    db.commit()
    return _cn_out(cn)


@router.delete("/credit-notes/{cn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credit_note(user: permitted("invoices.create"), db: DB, cn_id: str) -> None:
    cn = _found_cn(db, cn_id)
    if cn.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft credit note can be deleted.")
    audit(db, user, "credit_note.deleted", target=cn.customer_name, target_type="credit_note", target_id=cn.id)
    db.delete(cn)
    db.commit()


@router.post("/credit-notes/{cn_id}/issue")
def issue_credit_note(user: permitted("invoices.issue"), db: DB, settings: SettingsDep, cn_id: str) -> dict:
    cn = _found_cn(db, cn_id)
    if cn.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft credit note can be issued.")
    _validate_line_accounts(db, [ln.get("accountId") for ln in (cn.lines or [])])
    computed = sale_work_out(db, settings, _sale_of_cn(cn))
    cn.computed = computed
    cn.total_centavos = computed["totalDueCentavos"]
    cn.tax_centavos = tax_of(computed)
    cn.number = _next_seq(db, CreditNote, "CN", cn.credit_date)
    ledger = posting_settings(db)
    by_sales_acct: dict[str, int] = {}
    for raw, done in zip(cn.lines or [], computed.get("lines") or []):
        net_line = int(done["totalCentavos"]) - int(done["taxCentavos"])
        acct_id = raw.get("accountId") or ledger.sales_account_id
        by_sales_acct[acct_id] = by_sales_acct.get(acct_id, 0) + net_line
    sales_legs = [Leg(account(db, aid), debit=amt, description="Credit note return/adjustment") for aid, amt in by_sales_acct.items() if amt]
    if not sales_legs:
        sales_legs = [Leg(account(db, ledger.sales_account_id), debit=cn.total_centavos - cn.tax_centavos)]
    legs = [
        *sales_legs,
        Leg(account(db, ledger.output_tax_account_id), debit=cn.tax_centavos, description="Output VAT credit adjustment"),
        Leg(account(db, ledger.receivables_account_id), credit=cn.total_centavos),
    ]
    entry = post(db, cn.credit_date, f"{cn.number}: credit note for {cn.customer_name}", legs, user.full_name, reference=cn.number, source="credit_note", by_id=user.id)
    cn.entry_id = entry.id
    cn.status = "issued"
    cn.issued_at, cn.issued_by = datetime.now(UTC), user.full_name
    # Auto-apply to linked invoice up to remaining balance so aging stays tight.
    if cn.invoice_id:
        inv = db.get(Invoice, cn.invoice_id)
        if inv and inv.status == "issued":
            already = inv.paid_centavos + invoice_settled(db, inv.id)
            rem_inv = max(0, inv.total_centavos - already)
            to_apply = min(cn.total_centavos, rem_inv)
            if to_apply > 0:
                db.add(CreditAllocation(credit_note_id=cn.id, invoice_id=inv.id, applied_on=cn.credit_date, amount_centavos=to_apply, created_by=user.full_name))
                cn.applied_centavos = to_apply
    audit(db, user, "credit_note.issued", target=f"{cn.number} {cn.customer_name}", target_type="credit_note", target_id=cn.id)
    db.commit()
    db.refresh(cn)
    return _cn_out(cn)


@router.post("/credit-notes/{cn_id}/apply")
def apply_credit_note(user: permitted("invoices.collect"), db: DB, settings: SettingsDep, cn_id: str, body: CreditApplyIn) -> dict:
    cn = _found_cn(db, cn_id)
    if cn.status != "issued":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an issued credit note can be applied.")
    if body.applied_on > today(settings):
        raise field_error("appliedOn", "Application date can't be in the future.")
    remaining_cn = cn.total_centavos - cn.applied_centavos
    if body.amount_centavos > remaining_cn:
        raise field_error("amountCentavos", "Amount exceeds the credit note's remaining balance.")
    inv = db.get(Invoice, body.invoice_id)
    if inv is None or inv.status != "issued":
        raise field_error("invoiceId", "Pick an issued invoice.")
    [inv] = locked(db, Invoice, [inv.id])
    inv_rem = max(0, inv.total_centavos - inv.paid_centavos - invoice_settled(db, inv.id))
    if body.amount_centavos > inv_rem:
        raise field_error("amountCentavos", "Amount exceeds what the customer still owes on this invoice.")
    db.add(CreditAllocation(credit_note_id=cn.id, invoice_id=inv.id, applied_on=body.applied_on, amount_centavos=body.amount_centavos, created_by=user.full_name))
    cn.applied_centavos += body.amount_centavos
    audit(db, user, "credit_note.applied", target=f"{cn.number} -> {inv.number}", target_type="credit_note", target_id=cn.id)
    db.commit()
    db.refresh(cn)
    return _cn_out(cn)


@router.delete("/credit-notes/{cn_id}/allocations/{alloc_id}")
def remove_credit_allocation(user: permitted("invoices.void"), db: DB, cn_id: str, alloc_id: str) -> dict:
    cn = _found_cn(db, cn_id)
    alloc = next((a for a in cn.allocations if a.id == alloc_id), None)
    if alloc is None or alloc.removed_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no active allocation here.")
    alloc.removed_at, alloc.removed_by = datetime.now(UTC), user.full_name
    cn.applied_centavos = max(0, cn.applied_centavos - alloc.amount_centavos)
    db.commit()
    db.refresh(cn)
    return _cn_out(cn)


@router.post("/credit-notes/{cn_id}/void")
def void_credit_note(user: permitted("invoices.void"), db: DB, settings: SettingsDep, cn_id: str, body: VoidNoteIn) -> dict:
    cn = _found_cn(db, cn_id)
    if cn.status != "issued":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an issued credit note can be voided.")
    if cn.applied_centavos > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Remove credit allocations from invoices before voiding.")
    entry = db.get(JournalEntry, cn.entry_id) if cn.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of {cn.number}: {body.reason.strip()}"[:300], legs, user.full_name, reference=cn.number, source="credit_note", reverses=entry, by_id=user.id)
    cn.status, cn.void_reason = "void", body.reason.strip()
    cn.voided_at, cn.voided_by = datetime.now(UTC), user.full_name
    audit(db, user, "credit_note.voided", target=f"{cn.number} {cn.customer_name}", target_type="credit_note", target_id=cn.id)
    db.commit()
    return _cn_out(cn)


# --- Supplier Vendor Credits -------------------------------------------------------------------


class VendorCreditLineIn(Api):
    account_id: str = Field(min_length=1, max_length=36)
    description: str | None = Field(None, max_length=200)
    amount_centavos: int = Field(gt=0)
    vat: Literal["vat", "zero", "exempt", "none"] = "vat"
    purchase_type: Literal["services", "capital_goods", "other_goods", "importation"] = "other_goods"
    withholding: str | None = Field(None, max_length=10)
    no_withholding_reason: str | None = Field(None, max_length=20)
    no_withholding_note: str | None = Field(None, max_length=200)


class VendorCreditIn(Api):
    bill_id: str | None = Field(None, max_length=36)
    supplier_id: str = Field(min_length=1, max_length=36)
    credit_date: date
    reference: str = Field(min_length=1, max_length=60)
    reason: str | None = Field(None, max_length=500)
    amounts_include_vat: bool = True
    lines: list[VendorCreditLineIn] = Field(min_length=1, max_length=100)


class VendorApplyIn(Api):
    bill_id: str = Field(min_length=1, max_length=36)
    applied_on: date
    amount_centavos: int = Field(gt=0)


def _vc_out(vc: VendorCredit) -> dict:
    return {
        "id": vc.id,
        "status": vc.status,
        "number": vc.number,
        "billId": vc.bill_id,
        "supplier": {"id": vc.supplier.id, "name": vc.supplier.name, "tin": vc.supplier.tin},
        "date": vc.credit_date.isoformat(),
        "reference": vc.reference,
        "reason": vc.reason,
        "amountsIncludeVat": vc.amounts_include_vat,
        "lines": vc.lines,
        "netCentavos": vc.net_centavos,
        "vatCentavos": vc.vat_centavos,
        "withheldCentavos": vc.withheld_centavos,
        "totalCentavos": vc.total_centavos,
        "creditCentavos": vc.credit_centavos,
        "appliedCentavos": vc.applied_centavos,
        "remainingCentavos": max(0, vc.credit_centavos - vc.applied_centavos) if vc.status == "recorded" else 0,
        "entryId": vc.entry_id,
        "createdBy": vc.created_by,
        "createdAt": iso(vc.created_at),
        "recordedBy": vc.recorded_by,
        "recordedAt": iso(vc.recorded_at),
        "voidedBy": vc.voided_by,
        "voidedAt": iso(vc.voided_at),
        "voidReason": vc.void_reason,
        "allocations": [
            {
                "id": a.id,
                "billId": a.bill_id,
                "appliedOn": a.applied_on.isoformat(),
                "amountCentavos": a.amount_centavos,
                "removedAt": iso(a.removed_at),
                "removedBy": a.removed_by,
            }
            for a in vc.allocations
        ],
    }


def _found_vc(db: Session, vc_id: str) -> VendorCredit:
    vc = db.get(VendorCredit, vc_id)
    if vc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such vendor credit.")
    return vc


def _fill_vc(db: Session, vc: VendorCredit, body: VendorCreditIn, settings) -> None:
    if body.credit_date > today(settings):
        raise field_error("creditDate", "A vendor credit can't be dated in the future.")
    supplier = db.get(Supplier, body.supplier_id)
    if supplier is None or not supplier.is_active:
        raise field_error("supplierId", "Pick an active supplier.")
    if company_scope.configured(db, "supplier"):
        company_scope.require_ids(db, "supplier", [supplier.id], status_code=422)
    if body.bill_id:
        b = db.get(Bill, body.bill_id)
        if b is None or b.status != "recorded" or b.supplier_id != supplier.id:
            raise field_error("billId", "Link to a recorded bill for this supplier.")
    lines = []
    for i, ln in enumerate(body.lines):
        if company_scope.configured(db, "account"):
            company_scope.require_ids(db, "account", [ln.account_id], status_code=422)
        acc = db.get(Account, ln.account_id)
        if acc is None or not acc.is_active or acc.type not in ("expense", "asset"):
            raise field_error(f"lines.{i}.accountId", "Pick an active expense or asset account.")
        if ln.withholding and ln.withholding not in WITHHOLDING:
            raise field_error(f"lines.{i}.withholding", "Pick a valid withholding code.")
        try:
            code, reason, note = withholding_decision(supplier.origin, ln.withholding, ln.no_withholding_reason, ln.no_withholding_note, complete=True)
        except ValueError as err:
            raise field_error(f"lines.{i}.withholding", str(err)) from None
        item = {"accountId": acc.id, "description": ln.description, "amountCentavos": ln.amount_centavos, "vat": ln.vat, "withholding": code, "purchaseType": ln.purchase_type}
        if reason:
            item["noWithholding"] = reason
        if note:
            item["noWithholdingNote"] = note
        lines.append(item)
    w = bill_work_out(db, lines, body.credit_date, body.amounts_include_vat)
    vc.supplier_id = supplier.id
    vc.bill_id = body.bill_id
    vc.credit_date = body.credit_date
    vc.reference = body.reference.strip()
    vc.reason = body.reason
    vc.amounts_include_vat = body.amounts_include_vat
    vc.lines = lines
    vc.net_centavos, vc.vat_centavos, vc.withheld_centavos = w.net, w.vat, w.withheld
    vc.total_centavos, vc.credit_centavos = w.total, w.payable


@router.get("/vendor-credits")
def list_vendor_credits(_: permitted("bills.view"), db: DB, status_: str | None = Query(None, alias="status")) -> dict:
    q = select(VendorCredit).order_by(VendorCredit.credit_date.desc(), VendorCredit.created_at.desc())
    if status_ in ("draft", "recorded", "void"):
        q = q.where(VendorCredit.status == status_)
    rows = list(db.scalars(q))
    bill_rows = list(db.scalars(select(Bill).where(Bill.status == "recorded").order_by(Bill.bill_date.desc()).limit(200)))
    settled_map = bill_settled_map(db, [b.id for b in bill_rows])
    bills = [
        {
            "id": b.id, "no": b.no, "billNumber": b.bill_number, "supplierId": b.supplier_id, "supplierName": b.supplier.name,
            "owedCentavos": max(0, b.payable_centavos - b.paid_centavos - settled_map.get(b.id, 0)),
        }
        for b in bill_rows
    ]
    sup_q = select(Supplier).where(Supplier.is_active).order_by(func.lower(Supplier.name))
    if company_scope.configured(db, "supplier"):
        sup_q = sup_q.where(company_scope.usable_clause("supplier", Supplier.id))
    acct_q = select(Account).where(Account.is_active, Account.type.in_(("expense", "asset"))).order_by(Account.code)
    if company_scope.configured(db, "account"):
        acct_q = acct_q.where(company_scope.usable_clause("account", Account.id))
    suppliers = [{"id": s.id, "name": s.name, "tin": s.tin} for s in db.scalars(sup_q)]
    accounts = [{"id": a.id, "code": a.code, "name": a.name} for a in db.scalars(acct_q)]
    return {"items": [_vc_out(v) for v in rows], "bills": bills, "suppliers": suppliers, "accounts": accounts}


@router.post("/vendor-credits", status_code=status.HTTP_201_CREATED)
def add_vendor_credit(user: permitted("bills.create"), db: DB, settings: SettingsDep, body: VendorCreditIn) -> dict:
    vc = VendorCredit(created_by=user.full_name, supplier_id=body.supplier_id, credit_date=body.credit_date, reference=body.reference, lines=[])
    _fill_vc(db, vc, body, settings)
    db.add(vc)
    db.flush()
    audit(db, user, "vendor_credit.drafted", target=vc.reference, target_type="vendor_credit", target_id=vc.id)
    db.commit()
    db.refresh(vc)
    return _vc_out(vc)


@router.put("/vendor-credits/{vc_id}")
def update_vendor_credit(user: permitted("bills.create"), db: DB, settings: SettingsDep, vc_id: str, body: VendorCreditIn) -> dict:
    vc = _found_vc(db, vc_id)
    if vc.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft vendor credit can be edited.")
    _fill_vc(db, vc, body, settings)
    db.commit()
    db.refresh(vc)
    return _vc_out(vc)


@router.delete("/vendor-credits/{vc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor_credit(user: permitted("bills.create"), db: DB, vc_id: str) -> None:
    vc = _found_vc(db, vc_id)
    if vc.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft vendor credit can be deleted.")
    db.delete(vc)
    db.commit()


@router.post("/vendor-credits/{vc_id}/record")
def record_vendor_credit(user: permitted("bills.approve"), db: DB, settings: SettingsDep, vc_id: str) -> dict:
    vc = _found_vc(db, vc_id)
    if vc.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft vendor credit can be recorded.")
    if company_scope.configured(db, "supplier"):
        company_scope.require_ids(db, "supplier", [vc.supplier_id])
    if company_scope.configured(db, "account"):
        company_scope.require_ids(db, "account", [ln.get("accountId") for ln in (vc.lines or [])])
    w = bill_work_out(db, vc.lines, vc.credit_date, vc.amounts_include_vat)
    s = posting_settings(db)
    own = db.get(Account, vc.supplier.payables_account_id) if vc.supplier.payables_account_id else None
    payables = own if own is not None and own.is_active else account(db, s.payables_account_id)
    accts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_({ln["accountId"] for ln in w.lines})))}
    vc.number = _next_seq(db, VendorCredit, "VC", vc.credit_date)
    legs = [
        Leg(payables, debit=w.payable, description=vc.supplier.name[:200]),
        Leg(account(db, s.withholding_account_id), debit=w.withheld, description="EWT reversal (vendor credit)"),
        *[Leg(accts[ln["accountId"]], credit=ln["netCentavos"], description=(ln.get("description") or "Vendor credit")) for ln in w.lines if ln["netCentavos"]],
        Leg(account(db, s.input_tax_account_id), credit=w.vat, description="Input VAT credit reversal"),
    ]
    entry = post(db, vc.credit_date, f"{vc.number}: vendor credit from {vc.supplier.name} ({vc.reference})", legs, user.full_name, reference=vc.reference, source="vendor_credit", by_id=user.id)
    vc.entry_id = entry.id
    vc.payables_account_id = payables.id if payables else None
    vc.status = "recorded"
    vc.recorded_at, vc.recorded_by = datetime.now(UTC), user.full_name
    if vc.bill_id:
        b = db.get(Bill, vc.bill_id)
        if b and b.status == "recorded":
            rem_b = max(0, b.payable_centavos - b.paid_centavos - bill_settled(db, b.id))
            to_apply = min(vc.credit_centavos, rem_b)
            if to_apply > 0:
                db.add(VendorCreditAllocation(vendor_credit_id=vc.id, bill_id=b.id, applied_on=vc.credit_date, amount_centavos=to_apply, created_by=user.full_name))
                vc.applied_centavos = to_apply
    audit(db, user, "vendor_credit.recorded", target=f"{vc.number} {vc.supplier.name}", target_type="vendor_credit", target_id=vc.id)
    db.commit()
    db.refresh(vc)
    return _vc_out(vc)


@router.post("/vendor-credits/{vc_id}/apply")
def apply_vendor_credit(user: permitted("vouchers.prepare"), db: DB, settings: SettingsDep, vc_id: str, body: VendorApplyIn) -> dict:
    vc = _found_vc(db, vc_id)
    if vc.status != "recorded":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a recorded vendor credit can be applied.")
    if body.applied_on > today(settings):
        raise field_error("appliedOn", "Application date can't be in the future.")
    rem_vc = vc.credit_centavos - vc.applied_centavos
    if body.amount_centavos > rem_vc:
        raise field_error("amountCentavos", "Amount exceeds remaining vendor credit.")
    b = db.get(Bill, body.bill_id)
    if b is None or b.status != "recorded" or b.supplier_id != vc.supplier_id:
        raise field_error("billId", "Pick a recorded bill from the same supplier.")
    [b] = locked(db, Bill, [b.id])
    rem_b = max(0, b.payable_centavos - b.paid_centavos - bill_settled(db, b.id))
    if body.amount_centavos > rem_b:
        raise field_error("amountCentavos", "Amount exceeds what is still owed on this bill.")
    db.add(VendorCreditAllocation(vendor_credit_id=vc.id, bill_id=b.id, applied_on=body.applied_on, amount_centavos=body.amount_centavos, created_by=user.full_name))
    vc.applied_centavos += body.amount_centavos
    db.commit()
    db.refresh(vc)
    return _vc_out(vc)


@router.delete("/vendor-credits/{vc_id}/allocations/{alloc_id}")
def remove_vendor_allocation(user: permitted("bills.void"), db: DB, vc_id: str, alloc_id: str) -> dict:
    vc = _found_vc(db, vc_id)
    alloc = next((a for a in vc.allocations if a.id == alloc_id), None)
    if alloc is None or alloc.removed_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no active allocation here.")
    alloc.removed_at, alloc.removed_by = datetime.now(UTC), user.full_name
    vc.applied_centavos = max(0, vc.applied_centavos - alloc.amount_centavos)
    db.commit()
    db.refresh(vc)
    return _vc_out(vc)


@router.post("/vendor-credits/{vc_id}/void")
def void_vendor_credit(user: permitted("bills.void"), db: DB, settings: SettingsDep, vc_id: str, body: VoidNoteIn) -> dict:
    vc = _found_vc(db, vc_id)
    if vc.status != "recorded":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a recorded vendor credit can be voided.")
    if vc.applied_centavos > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Remove bill allocations before voiding.")
    entry = db.get(JournalEntry, vc.entry_id) if vc.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of {vc.number}: {body.reason.strip()}"[:300], legs, user.full_name, reference=vc.reference, source="vendor_credit", reverses=entry, by_id=user.id)
    vc.status, vc.void_reason = "void", body.reason.strip()
    vc.voided_at, vc.voided_by = datetime.now(UTC), user.full_name
    audit(db, user, "vendor_credit.voided", target=f"{vc.number} {vc.supplier.name}", target_type="vendor_credit", target_id=vc.id)
    db.commit()
    return _vc_out(vc)
