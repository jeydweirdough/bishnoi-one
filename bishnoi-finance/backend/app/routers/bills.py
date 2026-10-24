"""Supplier bills: drafted against one of Inventory's suppliers (or from a
delivery received there), recorded in the books, paid, and voided (never
edited) once recorded. Decided 2026-10-24, BIR features from Oojeema; app/bills.py
works out what each comes to.
"""

import re
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access import permitted
from app.audit import audit
from app.bills import KINDS, work_out
from app.deps import DB, SettingsDep
from app.funds import RELEASE_METHODS as METHODS
from app.inventory import InventoryUnavailable, find_suppliers, read_supplier, supplier_deliveries
from app.ledger import Leg, account, money_account, post
from app.ledger import settings as posting_settings
from app.models import Account, BillPayment, JournalEntry, SupplierBill
from app.routers.funds import today
from app.routers.tax import Api, field_error
from app.tax.packs.ph import EWT_ATCS

router = APIRouter(prefix="/finance/bills", tags=["bills"])

ATC_PATTERN = re.compile(r"W[A-Z]\d{3}[A-Z]?")


def unavailable(e: InventoryUnavailable) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


# --- what a bill can be made of ---------------------------------------------------------------


@router.get("/setup")
def setup(_: permitted("bills.view"), db: DB) -> dict:
    accounts = db.scalars(select(Account).where(Account.is_active, Account.type.in_(("expense", "asset"))).order_by(Account.code)).all()
    return {
        "kinds": [{"key": k, "label": v} for k, v in KINDS.items()],
        "atcs": [{"code": a.code, "nature": a.nature, "rateBp": a.rate_bp} for a in EWT_ATCS.values()],
        "accounts": [{"id": a.id, "code": a.code, "name": a.name, "type": a.type} for a in accounts],
        "methods": [{"key": k, "label": v} for k, v in METHODS.items()],
    }


@router.get("/suppliers")
def suppliers(_: permitted("bills.view"), settings: SettingsDep, q: str | None = Query(None, max_length=80)) -> dict:
    try:
        return {"items": find_suppliers(settings, q)}
    except InventoryUnavailable as e:
        raise unavailable(e) from None


@router.get("/suppliers/{supplier_id}/deliveries")
def deliveries(_: permitted("bills.view"), settings: SettingsDep, supplier_id: str) -> dict:
    try:
        return {"items": supplier_deliveries(settings, supplier_id)}
    except InventoryUnavailable as e:
        raise unavailable(e) from None


# --- bills ------------------------------------------------------------------------------------


class LineIn(Api):
    description: str = Field(min_length=1, max_length=200)
    account_id: str = Field(max_length=36)
    kind: str = "vatable"
    amount_centavos: int = Field(ge=0)
    withheld: bool = True


class BillIn(Api):
    supplier_id: str = Field(min_length=1, max_length=36)
    supplier_invoice_no: str = Field(min_length=1, max_length=60)
    bill_date: date
    terms_days: int = Field(30, ge=0, le=365)
    delivery_ref: str | None = Field(None, max_length=60)
    notes: str | None = Field(None, max_length=500)
    amounts_include_vat: bool = True
    lines: list[LineIn] = Field(min_length=1, max_length=100)
    atc: str | None = Field(None, max_length=8)
    ewt_rate_bp: int | None = Field(None, ge=0, le=3000)

    @field_validator("atc")
    @classmethod
    def _atc(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        atc = value.strip().upper()
        if not ATC_PATTERN.fullmatch(atc):
            raise ValueError("An ATC looks like WC158 or WI160, as on the BIR's list.")
        return atc


def found(db: Session, bill_id: str) -> SupplierBill:
    bill = db.get(SupplierBill, bill_id)
    if bill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such bill.")
    return bill


def must_be_draft(bill: SupplierBill) -> None:
    if bill.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "A recorded bill isn't changed: void it and record it again.")


def computed_for(db: Session, bill: SupplierBill) -> dict:
    return work_out(db, bill.bill_date, bill.lines, include_vat=bill.amounts_include_vat, atc=bill.atc, rate_bp=bill.ewt_rate_bp)


def bill_out(db: Session, bill: SupplierBill, *, full: bool = True) -> dict:
    c = bill.computed if bill.status != "draft" and bill.computed else computed_for(db, bill)
    due = bill.bill_date + timedelta(days=bill.terms_days)
    payable = c["payableCentavos"]
    out = {
        "id": bill.id, "no": bill.no, "status": bill.status,
        "supplier": {"id": bill.supplier_id, "name": bill.supplier_name, "tin": bill.supplier_tin, "address": bill.supplier_address, "vatStatus": bill.supplier_vat_status},
        "supplierInvoiceNo": bill.supplier_invoice_no, "billDate": bill.bill_date.isoformat(), "termsDays": bill.terms_days, "dueDate": due.isoformat(),
        "deliveryRef": bill.delivery_ref, "notes": bill.notes, "amountsIncludeVat": bill.amounts_include_vat,
        "atc": bill.atc, "ewtRateBp": bill.ewt_rate_bp,
        "totalCentavos": c["totalCentavos"], "inputTaxCentavos": c["inputTaxCentavos"], "ewtCentavos": c["ewtCentavos"], "payableCentavos": payable,
        "paidCentavos": bill.paid_centavos, "balanceCentavos": payable - bill.paid_centavos if bill.status == "posted" else 0,
        "createdBy": bill.created_by, "postedBy": bill.posted_by, "voidedBy": bill.voided_by, "voidReason": bill.void_reason,
    }
    if full:
        accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_({ln.get("accountId") for ln in bill.lines})))}
        out["computed"] = {**c, "lines": [{**ln, "account": ({"code": accounts[ln["accountId"]].code, "name": accounts[ln["accountId"]].name} if ln.get("accountId") in accounts else None)} for ln in c["lines"]]}
        out["payments"] = [payment_out(p) for p in bill.payments]
        out["methods"] = [{"key": k, "label": v} for k, v in METHODS.items()]
    return out


def apply(db: Session, settings, bill: SupplierBill, body: BillIn, *, supplier_changed: bool) -> None:
    if body.bill_date > today(settings):
        raise field_error("billDate", "A bill can't be dated in the future.")
    if supplier_changed:
        try:
            s = read_supplier(settings, body.supplier_id)
        except InventoryUnavailable as e:
            raise unavailable(e) from None
        bill.supplier_id, bill.supplier_name = s["id"], s["name"]
        bill.supplier_tin, bill.supplier_address = s.get("tin"), s.get("address")
        bill.supplier_vat_status = s.get("vatStatus") or "vat"
    taken = db.scalar(select(SupplierBill.id).where(
        SupplierBill.supplier_id == bill.supplier_id, func.lower(SupplierBill.supplier_invoice_no) == body.supplier_invoice_no.strip().lower(),
        SupplierBill.status != "void", SupplierBill.id != (bill.id or ""),
    ))
    if taken:
        raise field_error("supplierInvoiceNo", "This supplier invoice is already recorded.")
    for i, ln in enumerate(body.lines):
        if ln.kind not in KINDS:
            raise field_error(f"lines.{i}.kind", "Pick the line's VAT kind.")
        if bill.supplier_vat_status == "non_vat" and ln.kind == "vatable":
            raise field_error(f"lines.{i}.kind", f"{bill.supplier_name} isn't VAT-registered: its bills carry no input VAT.")
        a = db.get(Account, ln.account_id)
        if a is None or not a.is_active or a.type not in ("expense", "asset"):
            raise field_error(f"lines.{i}.accountId", "Charge it to an active expense or asset account.")
    rate = body.ewt_rate_bp if body.ewt_rate_bp is not None else (EWT_ATCS[body.atc].rate_bp if body.atc in EWT_ATCS else None)
    if body.atc and rate is None:
        raise field_error("ewtRateBp", "Give the rate for this ATC.")
    bill.supplier_invoice_no = body.supplier_invoice_no.strip()
    bill.bill_date, bill.terms_days = body.bill_date, body.terms_days
    bill.delivery_ref, bill.notes = body.delivery_ref, body.notes
    bill.amounts_include_vat = body.amounts_include_vat
    bill.lines = [{"description": ln.description, "accountId": ln.account_id, "kind": ln.kind, "amountCentavos": ln.amount_centavos, "withheld": ln.withheld} for ln in body.lines]
    bill.atc, bill.ewt_rate_bp = body.atc, (rate or 0) if body.atc else 0


@router.get("")
def list_bills(_: permitted("bills.view"), db: DB, state: str | None = Query(None, alias="status"), q: str | None = Query(None, max_length=80)) -> dict:
    query = select(SupplierBill)
    if state in ("draft", "posted", "void"):
        query = query.where(SupplierBill.status == state)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(SupplierBill.supplier_name).like(like), func.lower(SupplierBill.supplier_invoice_no).like(like)))
    bills = db.scalars(query.order_by(SupplierBill.bill_date.desc(), SupplierBill.no.desc()).limit(300)).all()
    counts = dict(db.execute(select(SupplierBill.status, func.count()).group_by(SupplierBill.status)).all())
    return {"items": [bill_out(db, b, full=False) for b in bills], "counts": {k: counts.get(k, 0) for k in ("draft", "posted", "void")}}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_bill(user: permitted("bills.create"), db: DB, settings: SettingsDep, body: BillIn) -> dict:
    bill = SupplierBill(created_by=user.full_name, supplier_id=body.supplier_id, supplier_name="", lines=[])
    apply(db, settings, bill, body, supplier_changed=True)
    db.add(bill)
    db.flush()
    audit(db, user, "bill.created", target=f"{bill.supplier_name} {bill.supplier_invoice_no}", target_type="bill", target_id=bill.id)
    db.commit()
    return bill_out(db, bill)


@router.get("/payables")
def payables(_: permitted("bills.view"), db: DB, settings: SettingsDep) -> dict:
    """What's owed to each supplier on recorded bills, by how late it is."""
    on = today(settings)
    buckets = (("current", "Not yet due", None, 0), ("1_30", "1 to 30 days", 1, 30), ("31_60", "31 to 60 days", 31, 60), ("61_90", "61 to 90 days", 61, 90), ("over_90", "Over 90 days", 91, None))
    rows: dict[str, dict] = {}
    for b in db.scalars(select(SupplierBill).where(SupplierBill.status == "posted")):
        owed = b.payable_centavos - b.paid_centavos
        if owed <= 0:
            continue
        late = (on - (b.bill_date + timedelta(days=b.terms_days))).days
        key = next(k for k, _, lo, hi in buckets if (lo is None or late >= lo) and (hi is None or late <= hi))
        row = rows.setdefault(b.supplier_id, {"supplier": {"id": b.supplier_id, "name": b.supplier_name}, "owedCentavos": 0, **{k: 0 for k, *_ in buckets}})
        row[key] += owed
        row["owedCentavos"] += owed
    items = sorted(rows.values(), key=lambda r: -r["owedCentavos"])
    return {
        "asOf": on.isoformat(), "buckets": [{"key": k, "label": label} for k, label, *_ in buckets], "items": items,
        "totals": {k: sum(r[k] for r in items) for k, *_ in buckets} | {"owedCentavos": sum(r["owedCentavos"] for r in items)},
    }


@router.get("/{bill_id}")
def read_bill(_: permitted("bills.view"), db: DB, bill_id: str) -> dict:
    return bill_out(db, found(db, bill_id))


@router.put("/{bill_id}")
def update_bill(user: permitted("bills.create"), db: DB, settings: SettingsDep, bill_id: str, body: BillIn) -> dict:
    bill = found(db, bill_id)
    must_be_draft(bill)
    apply(db, settings, bill, body, supplier_changed=body.supplier_id != bill.supplier_id)
    audit(db, user, "bill.updated", target=f"{bill.supplier_name} {bill.supplier_invoice_no}", target_type="bill", target_id=bill.id)
    db.commit()
    return bill_out(db, bill)


@router.delete("/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(user: permitted("bills.create"), db: DB, bill_id: str) -> Response:
    bill = found(db, bill_id)
    must_be_draft(bill)
    audit(db, user, "bill.deleted", target=f"{bill.supplier_name} {bill.supplier_invoice_no}", target_type="bill", target_id=bill.id)
    db.delete(bill)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{bill_id}/record")
def record_bill(user: permitted("bills.record"), db: DB, bill_id: str) -> dict:
    """In the books: the purchase, its input VAT, what the supplier is owed and the tax withheld for the BIR."""
    bill = found(db, bill_id)
    must_be_draft(bill)
    c = computed_for(db, bill)
    if c["totalCentavos"] <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "The bill comes to nothing: add its amounts first.")
    ledger = posting_settings(db)
    by_account: dict[str, int] = {}
    for ln in c["lines"]:
        by_account[ln["accountId"]] = by_account.get(ln["accountId"], 0) + ln["netCentavos"]
    entry = post(db, bill.bill_date, f"Bill {bill.supplier_invoice_no} from {bill.supplier_name}", [
        *[Leg(account(db, a), debit=amount) for a, amount in by_account.items()],
        Leg(account(db, ledger.input_tax_account_id), debit=c["inputTaxCentavos"], description="Input VAT"),
        Leg(account(db, ledger.payables_account_id), credit=c["payableCentavos"]),
        Leg(account(db, ledger.ewt_payable_account_id), credit=c["ewtCentavos"], description=f"Withheld ({bill.atc})" if bill.atc else None),
    ], user.full_name, reference=bill.supplier_invoice_no, source="bill")
    bill.computed = c
    bill.total_centavos, bill.input_tax_centavos, bill.ewt_centavos, bill.payable_centavos = c["totalCentavos"], c["inputTaxCentavos"], c["ewtCentavos"], c["payableCentavos"]
    bill.status, bill.entry_id = "posted", entry.id
    bill.posted_at, bill.posted_by = datetime.now(UTC), user.full_name
    audit(db, user, "bill.recorded", target=f"{bill.supplier_name} {bill.supplier_invoice_no}", target_type="bill", target_id=bill.id)
    db.commit()
    return bill_out(db, bill)


class VoidIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/{bill_id}/void")
def void_bill(user: permitted("bills.void"), db: DB, settings: SettingsDep, bill_id: str, body: VoidIn) -> dict:
    bill = found(db, bill_id)
    if bill.status != "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a recorded bill is voided. A draft is simply deleted.")
    if bill.paid_centavos:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payments are recorded against this bill: take them off first.")
    entry = db.get(JournalEntry, bill.entry_id) if bill.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of bill {bill.supplier_invoice_no}: {body.reason}", legs, user.full_name, reference=bill.supplier_invoice_no, source="bill", reverses=entry)
    bill.status, bill.void_reason = "void", body.reason
    bill.voided_at, bill.voided_by = datetime.now(UTC), user.full_name
    audit(db, user, "bill.voided", target=f"{bill.supplier_name} {bill.supplier_invoice_no}", target_type="bill", target_id=bill.id)
    db.commit()
    return bill_out(db, bill)


# --- payments ---------------------------------------------------------------------------------


def payment_out(p: BillPayment) -> dict:
    return {
        "id": p.id, "paidOn": p.paid_on.isoformat(), "amountCentavos": p.amount_centavos, "method": p.method,
        "methodLabel": METHODS.get(p.method, p.method), "reference": p.reference, "recordedBy": p.recorded_by,
        "removedBy": p.removed_by, "removedAt": p.removed_at.isoformat() if p.removed_at else None,
    }


class PaymentIn(Api):
    paid_on: date
    amount_centavos: int = Field(ge=1)
    method: str = Field(max_length=10)
    reference: str | None = Field(None, max_length=80)


@router.post("/{bill_id}/payments", status_code=status.HTTP_201_CREATED)
def pay(user: permitted("bills.pay"), db: DB, settings: SettingsDep, bill_id: str, body: PaymentIn) -> dict:
    """Money paid to the supplier: what's owed down, money out."""
    bill = found(db, bill_id)
    if bill.status != "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Payments are recorded against a recorded bill.")
    if body.method not in METHODS:
        raise field_error("method", "Pick how it was paid.")
    if body.paid_on > today(settings):
        raise field_error("paidOn", "A payment can't be dated in the future.")
    owed = bill.payable_centavos - bill.paid_centavos
    if body.amount_centavos > owed:
        raise field_error("amountCentavos", f"That's more than is owed on this bill ({owed / 100:,.2f}).")
    p = BillPayment(bill=bill, paid_on=body.paid_on, amount_centavos=body.amount_centavos, method=body.method, reference=body.reference, recorded_by=user.full_name)
    how = METHODS[body.method] + (f" ({body.reference})" if body.reference else "")
    entry = post(db, body.paid_on, f"Payment to {bill.supplier_name} for bill {bill.supplier_invoice_no}, {how}", [
        Leg(account(db, posting_settings(db).payables_account_id), debit=body.amount_centavos),
        Leg(money_account(db, body.method), credit=body.amount_centavos),
    ], user.full_name, reference=body.reference or bill.supplier_invoice_no, source="bill")
    p.entry_id = entry.id
    bill.paid_centavos += body.amount_centavos
    db.add(p)
    db.flush()
    audit(db, user, "bill.paid", target=f"{bill.supplier_name} {bill.supplier_invoice_no}", target_type="bill", target_id=bill.id)
    db.commit()
    return bill_out(db, bill)


@router.delete("/{bill_id}/payments/{payment_id}")
def remove_payment(user: permitted("bills.void"), db: DB, settings: SettingsDep, bill_id: str, payment_id: str) -> dict:
    bill = found(db, bill_id)
    p = db.get(BillPayment, payment_id)
    if p is None or p.bill_id != bill.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such payment.")
    if p.removed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "This payment was already taken off.")
    entry = db.get(JournalEntry, p.entry_id) if p.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Payment for bill {bill.supplier_invoice_no} taken off", legs, user.full_name, reference=entry.reference, source="bill", reverses=entry)
    p.removed_at, p.removed_by = datetime.now(UTC), user.full_name
    bill.paid_centavos -= p.amount_centavos
    audit(db, user, "bill.payment_removed", target=f"{bill.supplier_name} {bill.supplier_invoice_no}", target_type="bill", target_id=bill.id)
    db.commit()
    return bill_out(db, bill)
