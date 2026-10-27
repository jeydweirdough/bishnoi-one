"""Payables: suppliers, and their bills, with the supplier's invoice attached.

- /finance/suppliers: who the company buys from (suppliers.view, .add, .edit, .deactivate: each a
  tick on the Roles screen, 2026-10-23), with their papers attached.
- /finance/bills: supplier bills, in Aubrey's flow (2026-10-23, migration 0020). A draft is
  made, changed, deleted, has files attached and is submitted by whoever may make drafts
  (bills.create: Aubrey); approved or returned (bills.approve: Malou, told first with
  bills.first; Cristal backup); if it has tax withheld, checked or returned (bills.check: Mel).
  Only then is it posted to the books, and it's ready to pay (a payment voucher). Returned, it
  goes back to whoever submitted it and, corrected, to approval again. A posted bill is voided
  with a reason (bills.void), which posts the reversal, and never changed.
- /finance/bills/{id}/files: the supplier's invoice, a photo or a PDF (Aubrey Q6, Q20:
  missing documents are what goes wrong most). A bill without one says so.

Built 2026-10-23 from Aubrey's answers (Plans/Plan - Suppliers, bills and chart import).
Included in Finance's own router (app/routers/finance.py), so main.py is untouched.
"""

import re
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import case, func, or_, select, text

from app.access import access_of, permissions_of, permitted
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.funds import RECEIPT_TYPES, decode
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.models import OPEN_VOUCHERS, Account, Bill, BillEvent, BillFile, JournalEntry, PaymentVoucher, StoredFile, Supplier, SupplierFile, VoucherLine
from app.payables import PURCHASE_TYPES, VAT_KINDS, WITHHOLDING, withholding_out, work_out
from app.notify import done, holders, tell
from app.routers.funds import today
from app.routers.tax import Api, field_error, split_tin
from app.signatures import sign
from app.supplier_import import SupplierImportCheckIn, SupplierImportIn, clean_supplier_row
from app.supplier_directory import classify_directory

router = APIRouter(tags=["payables"])

MAX_FILE_BYTES = 3 * 1024 * 1024
MAX_FILES = 10


# --- files: a bill's invoice, a supplier's papers -------------------------------------------------


class FileIn(Api):
    name: str = Field(min_length=1, max_length=200)
    content_type: str = Field(max_length=100)
    # The file, base64.
    data: str


def store_file(db: DB, body: FileIn) -> tuple[str, int]:
    """A photo or a PDF, up to 3 MB, kept in the database like receipts are. Answers its ref and size."""
    if body.content_type not in RECEIPT_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Attach a photo (JPG, PNG, WebP, HEIC) or a PDF.")
    data = decode(body.data)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file is over 3 MB: scan or photograph it at a lower size.")
    ref = secrets.token_hex(16)
    db.add(StoredFile(ref=ref, content_type=body.content_type, data=data))
    return ref, len(data)


def found_file(files, file_id: str):
    f = next((x for x in files if x.id == file_id), None)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such file here.")
    return f


def file_response(db: DB, f) -> Response:
    stored = db.get(StoredFile, f.ref)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The file is no longer here.")
    name = f.name.replace('"', '')
    return Response(stored.data, media_type=stored.content_type, headers={"Content-Disposition": f'inline; filename="{name}"'})


# --- suppliers ---------------------------------------------------------------------------------


def account_brief(db: DB, account_id: str | None) -> dict | None:
    a = db.get(Account, account_id) if account_id else None
    return {"id": a.id, "code": a.code, "name": a.name} if a else None


def files_out(files) -> list[dict]:
    return [{"id": f.id, "name": f.name, "contentType": f.content_type, "size": f.size, "uploadedBy": f.uploaded_by, "uploadedAt": f.uploaded_at.isoformat()} for f in files]


def owed_by_supplier(db: DB) -> dict[str, int]:
    """What's owed each supplier: their recorded bills, less what released vouchers have paid."""
    return dict(db.execute(
        select(Bill.supplier_id, func.sum(Bill.payable_centavos - Bill.paid_centavos)).where(Bill.status == "recorded").group_by(Bill.supplier_id)
    ).all())


def set_aside(db: DB, bill_ids, exclude_voucher: str | None = None) -> dict[str, int]:
    """What open payment vouchers (not yet released or cancelled) hold of each bill, so it isn't paid twice."""
    ids = list(bill_ids)
    if not ids:
        return {}
    query = (
        select(VoucherLine.bill_id, func.sum(VoucherLine.amount_centavos))
        .join(PaymentVoucher, PaymentVoucher.id == VoucherLine.voucher_id)
        .where(VoucherLine.bill_id.in_(ids), PaymentVoucher.status.in_(OPEN_VOUCHERS))
    )
    if exclude_voucher:
        query = query.where(PaymentVoucher.id != exclude_voucher)
    return dict(db.execute(query.group_by(VoucherLine.bill_id)).all())


PAYMENT_LABELS = {"unpaid": "Unpaid", "partly_paid": "Partly paid", "paid": "Paid"}


def payment_state(b: Bill) -> str:
    if b.status != "recorded" or b.paid_centavos <= 0:
        return "unpaid"
    return "paid" if b.paid_centavos >= b.payable_centavos else "partly_paid"


def supplier_out(db: DB, s: Supplier, owed: int | None = None) -> dict:
    code = s.withholding
    return {
        "id": s.id, "no": s.no, "name": s.name, "companyName": s.company_name,
        "salutation": s.salutation, "firstName": s.first_name, "lastName": s.last_name,
        "tin": s.tin, "branchCode": s.branch_code, "address": s.address,
        "vatRegistered": s.vat_registered,
        "taxDefaultsConfirmed": s.tax_defaults_confirmed, "importDetails": s.import_details,
        "withholding": {"code": code, "name": WITHHOLDING[code][0], "rateBp": WITHHOLDING[code][1]} if code in WITHHOLDING else None,
        "termsDays": s.terms_days, "email": s.email, "phone": s.phone, "mobile": s.mobile,
        "payablesAccount": account_brief(db, s.payables_account_id),
        "contacts": s.contacts or [],
        "bankName": s.bank_name, "bankAccountName": s.bank_account_name, "bankAccountNumber": s.bank_account_number,
        "notes": s.notes, "isActive": s.is_active, "createdBy": s.created_by,
        "files": files_out(s.files),
        "owedCentavos": owed if owed is not None else owed_by_supplier(db).get(s.id, 0),
    }


def may_do(user) -> dict:
    can = access_of(user).can
    return {"canAdd": can("suppliers.add"), "canEdit": can("suppliers.edit"), "canDeactivate": can("suppliers.deactivate")}


def payables_accounts(db: DB) -> list[dict]:
    """The accounts a supplier's bills may post to instead of the default: active liabilities."""
    return [{"id": a.id, "code": a.code, "name": a.name} for a in db.scalars(select(Account).where(Account.is_active, Account.type == "liability").order_by(Account.code))]


@router.get("/suppliers")
def list_suppliers(user: permitted("suppliers.view"), db: DB, q: str | None = Query(None, max_length=100), active: bool | None = None) -> dict:
    query = select(Supplier)
    if active is not None:
        query = query.where(Supplier.is_active == active)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Supplier.name).like(like), func.lower(func.coalesce(Supplier.company_name, "")).like(like),
                                func.coalesce(Supplier.tin, "").like(like)))
    items = db.scalars(query.order_by(func.lower(Supplier.name)).limit(500)).all()
    owed = owed_by_supplier(db)
    return {"items": [supplier_out(db, s, owed.get(s.id, 0)) for s in items], "withholding": withholding_out(),
            "payablesAccounts": payables_accounts(db)} | may_do(user)


class ContactIn(Api):
    salutation: str | None = Field(None, max_length=10)
    first_name: str | None = Field(None, max_length=80)
    last_name: str | None = Field(None, max_length=80)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=40)
    mobile: str | None = Field(None, max_length=40)
    designation: str | None = Field(None, max_length=80)


class SupplierIn(Api):
    tax_defaults_confirmed: bool = False
    name: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(None, max_length=200)
    salutation: str | None = Field(None, max_length=10)
    first_name: str | None = Field(None, max_length=80)
    last_name: str | None = Field(None, max_length=80)
    tin: str | None = Field(None, max_length=20)
    branch_code: str | None = Field(None, max_length=5)
    address: str | None = Field(None, max_length=300)
    vat_registered: bool = True
    withholding: str | None = Field(None, max_length=10)
    terms_days: int = Field(30, ge=0, le=365)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=40)
    mobile: str | None = Field(None, max_length=40)
    payables_account_id: str | None = None
    contacts: list[ContactIn] = Field(default_factory=list, max_length=20)
    bank_name: str | None = Field(None, max_length=80)
    bank_account_name: str | None = Field(None, max_length=120)
    bank_account_number: str | None = Field(None, max_length=40)
    notes: str | None = Field(None, max_length=500)

    @field_validator("branch_code")
    @classmethod
    def _branch(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"\d{3}|\d{5}", value):
            raise ValueError("A branch code is 3 or 5 digits: 00000 for the head office.")
        return value

    @field_validator("withholding")
    @classmethod
    def _withholding(cls, value: str | None) -> str | None:
        if value is not None and value not in WITHHOLDING:
            raise ValueError("Pick a withholding code from the list.")
        return value


def apply_supplier(db: DB, s: Supplier, body: SupplierIn) -> list[str]:
    """The supplier's details from the form; refused if another supplier has the same TIN
    and branch, or the same name. Answers the names of what changed. Switching a supplier
    off or on is its own step (suppliers.deactivate), not part of the form."""
    tin, branch = None, body.branch_code
    if body.tin:
        try:
            tin, in_tin = split_tin(body.tin)
        except ValueError as problem:
            raise field_error("tin", str(problem)) from None
        branch = branch or in_tin or "00000"
    others = select(Supplier).where(Supplier.id != s.id) if s.id else select(Supplier)
    if tin and (twin := db.scalar(others.where(Supplier.tin == tin, Supplier.branch_code == branch))):
        raise field_error("tin", f"{twin.name} already has this TIN and branch code.")
    if twin := db.scalar(others.where(func.lower(Supplier.name) == body.name.strip().lower())):
        raise field_error("name", f"There's already a supplier called {twin.name}.")
    if body.payables_account_id:
        a = db.get(Account, body.payables_account_id)
        if a is None or not a.is_active or a.type != "liability":
            raise field_error("payablesAccountId", "Pick an active liability account, or leave it to the default.")
    contacts = [c.model_dump(by_alias=True) for c in body.contacts if any(v for v in c.model_dump().values())]
    values = body.model_dump(exclude={"contacts"}) | {"tin": tin, "branch_code": branch if tin else body.branch_code, "contacts": contacts}
    changed = [k for k, v in values.items() if getattr(s, k) != v]
    for k, v in values.items():
        setattr(s, k, v)
    return changed


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def add_supplier(user: permitted("suppliers.add"), db: DB, body: SupplierIn) -> dict:
    s = Supplier(created_by=user.full_name, is_active=True)
    apply_supplier(db, s, body)
    db.add(s)
    db.flush()
    audit(db, user, "supplier.created", target=s.name, target_type="supplier", target_id=s.id)
    db.commit()
    return supplier_out(db, s, 0)


# --- importing suppliers (Zoho's vendor export, as CSV) -------------------------------------------
#
# The screen reads the file in the browser and sends its rows by field; nothing of the file is
# kept. /import/check answers what would happen to each row, cleaned as it would be saved;
# /import adds the chosen ones, all or none. Decided 2026-10-23 (Plans/Plan - Suppliers like
# Zoho's vendors: decision 1; Zoho's Company ID is the TIN, decision 3; pesos only, decision 4).


def supplier_import_preview(db, body):
    here = list(db.scalars(select(Supplier)))
    if body.mode == "directory":
        return classify_directory(body.rows, here)
    by_name = {s.name.strip().lower(): s for s in here}
    by_tin = {(s.tin, s.branch_code): s for s in here if s.tin}
    accounts = payables_accounts(db)
    account_ids = {a["id"] for a in accounts}
    seen_name, seen_tin, out = {}, {}, []
    for i, row in enumerate(body.rows):
        value, notes, errors, reviews = clean_supplier_row(row)
        key, tin_key = value["name"].strip().lower(), (value["tin"], value["branchCode"])
        twin = by_name.get(key) or (by_tin.get(tin_key) if value["tin"] else None)
        earlier = seen_name.get(key) or (seen_tin.get(tin_key) if value["tin"] else None)
        related = [s for s in here if value["tin"] and s.tin == value["tin"] and s.branch_code != value["branchCode"]]
        related += [s for s in out if value["tin"] and s["supplier"]["tin"] == value["tin"] and s["supplier"]["branchCode"] != value["branchCode"]]
        if related and not row.review.branch_confirmed:
            reviews.append("Same TIN with another branch: confirm this is a separate supplier branch.")
        account_source = row.accounts_payable
        matches = [a for a in accounts if account_source and account_source.casefold() in (a["code"].casefold(), a["name"].casefold(), f'{a["code"]} - {a["name"]}'.casefold())]
        if (account_source or value["payablesAccountId"]) and not row.review.account_confirmed:
            reviews.append("Confirm the source Accounts Payable account or explicitly use the default.")
        if value["payablesAccountId"] and value["payablesAccountId"] not in account_ids:
            errors.append("Pick an active liability account.")
        # Validate all destination limits without silently truncating any source value.
        try:
            validation_value = {k: v for k, v in value.items() if k != "isActive"}
            validation_value["vatRegistered"] = value["vatRegistered"] if value["vatRegistered"] is not None else True
            SupplierIn.model_validate(validation_value)
        except ValueError as problem:
            errors.extend(f'{".".join(str(p) for p in e["loc"])}: {e["msg"]}' for e in problem.errors(include_input=False))
        if key:
            seen_name.setdefault(key, row.record or i + 1)
        if value["tin"]:
            seen_tin.setdefault(tin_key, row.record or i + 1)
        state = "here" if twin else "duplicate" if earlier else "problem" if errors else "review" if reviews else "new"
        message = f"Already in Finance as {twin.name}; left unchanged." if twin else f"Same supplier as record {earlier} (name or TIN and branch)." if earlier else " ".join(errors + reviews + notes) or None
        out.append({"line": i + 1, "record": row.record or i + 1, "status": state, "note": message, "errors": errors, "reviews": reviews, "warnings": notes, "supplier": value,
                    "accountMatches": matches})
    return {"rows": out, "counts": {k: sum(r["status"] == k for r in out) for k in ("new", "review", "here", "duplicate", "problem")}, "payablesAccounts": accounts, "withholding": withholding_out()}


@router.post("/suppliers/import/check")
def check_supplier_import(user: permitted("suppliers.add"), db: DB, body: SupplierImportCheckIn) -> dict:
    return supplier_import_preview(db, body)


def lock_supplier_writes(db):
    # No row changes: acquire a writer lock before checking supplier identities.
    # PostgreSQL table lock also serialises inserts into an otherwise empty table.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("LOCK TABLE nbfi_suppliers IN SHARE ROW EXCLUSIVE MODE"))
    else:
        db.execute(text("UPDATE nbfi_suppliers SET name = name WHERE 1 = 0"))


@router.post("/suppliers/import", status_code=status.HTTP_201_CREATED)
def run_supplier_import(user: permitted("suppliers.add"), db: DB, body: SupplierImportIn) -> dict:
    if not body.confirmed:
        raise HTTPException(422, "Confirm the selected suppliers before importing. Nothing was imported.")
    try:
        lock_supplier_writes(db)
        checked = supplier_import_preview(db, body)
        refused = next((r for r in checked["rows"] if r["status"] != "new"), None) if body.mode == "review" else None
        if refused:
            raise HTTPException(409, f'Record {refused["record"]}: {refused["note"]} Nothing was imported.')
        for row in checked["rows"]:
            if row["status"] != "new":
                continue
            value = dict(row["supplier"])
            supplier = Supplier(created_by=user.full_name, is_active=value.pop("isActive"), import_details=row.get("importDetails", {}))
            value["taxDefaultsConfirmed"] = body.mode == "review"
            if value["vatRegistered"] is None:
                value["vatRegistered"] = True  # storage compatibility only; flag prevents auto-fill
            apply_supplier(db, supplier, SupplierIn.model_validate(value))
            db.add(supplier)
            db.flush()
        added = checked["counts"]["new"]
        audit(db, user, "suppliers.imported", target=f'{added} suppliers', target_type="supplier")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"added": added, "counts": checked["counts"]} if body.mode == "directory" else {"added": added}

def found_supplier(db: DB, supplier_id: str) -> Supplier:
    s = db.get(Supplier, supplier_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such supplier.")
    return s


@router.get("/suppliers/{supplier_id}")
def read_supplier(user: permitted("suppliers.view"), db: DB, supplier_id: str) -> dict:
    s = found_supplier(db, supplier_id)
    bills = db.scalars(select(Bill).where(Bill.supplier_id == s.id).order_by(Bill.bill_date.desc(), Bill.no.desc()).limit(50)).all()
    held = set_aside(db, [b.id for b in bills])
    return supplier_out(db, s) | {"bills": [bill_summary(b, held.get(b.id, 0)) for b in bills], "withholdingChoices": withholding_out(),
                                  "payablesAccounts": payables_accounts(db)} | may_do(user)


@router.put("/suppliers/{supplier_id}")
def change_supplier(user: permitted("suppliers.edit"), db: DB, supplier_id: str, body: SupplierIn) -> dict:
    s = found_supplier(db, supplier_id)
    changed = apply_supplier(db, s, body)
    audit(db, user, "supplier.updated", target=s.name, target_type="supplier", target_id=s.id, fields=changed)
    db.commit()
    return supplier_out(db, s)


class ActiveIn(Api):
    is_active: bool


@router.post("/suppliers/{supplier_id}/active")
def switch_supplier(user: permitted("suppliers.deactivate"), db: DB, supplier_id: str, body: ActiveIn) -> dict:
    """Switched off: not offered on new bills; their bills stay as they are. Never deleted."""
    s = found_supplier(db, supplier_id)
    if s.is_active != body.is_active:
        s.is_active = body.is_active
        audit(db, user, "supplier.switched_on" if body.is_active else "supplier.switched_off", target=s.name, target_type="supplier", target_id=s.id)
        db.commit()
    return supplier_out(db, s)


@router.post("/suppliers/{supplier_id}/files", status_code=status.HTTP_201_CREATED)
def attach_to_supplier(user: permitted("suppliers.edit"), db: DB, supplier_id: str, body: FileIn) -> dict:
    """The supplier's papers: their BIR 2303, accreditation, a contract."""
    s = found_supplier(db, supplier_id)
    if len(s.files) >= MAX_FILES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A supplier keeps up to {MAX_FILES} files. Remove one first.")
    ref, size = store_file(db, body)
    s.files.append(SupplierFile(ref=ref, name=body.name.strip(), content_type=body.content_type, size=size, uploaded_by=user.full_name))
    audit(db, user, "supplier.file_added", target=s.name, target_type="supplier", target_id=s.id)
    db.commit()
    return supplier_out(db, s)


@router.get("/suppliers/{supplier_id}/files/{file_id}")
def open_supplier_file(user: permitted("suppliers.view"), db: DB, supplier_id: str, file_id: str) -> Response:
    return file_response(db, found_file(found_supplier(db, supplier_id).files, file_id))


@router.delete("/suppliers/{supplier_id}/files/{file_id}")
def remove_supplier_file(user: permitted("suppliers.edit"), db: DB, supplier_id: str, file_id: str) -> dict:
    s = found_supplier(db, supplier_id)
    f = found_file(s.files, file_id)
    if stored := db.get(StoredFile, f.ref):
        db.delete(stored)
    s.files.remove(f)
    audit(db, user, "supplier.file_removed", target=s.name, target_type="supplier", target_id=s.id)
    db.commit()
    return supplier_out(db, s)


# --- bills --------------------------------------------------------------------------------------

STATUS_LABELS = {"draft": "Draft", "recorded": "Recorded", "void": "Void"}
# Where a bill stands, as the lists and tabs show it (Aubrey's flow, 2026-10-23): made, approved,
# checked if tax is withheld; posted when it clears and then ready to pay.
STATE_LABELS = {
    "draft": "Draft", "returned": "Returned", "to_approve": "To approve", "to_check": "To check",
    "ready": "Ready to pay", "partly_paid": "Partly paid", "paid": "Paid", "void": "Void",
}
STATE = case(
    (Bill.status == "void", "void"),
    (Bill.status == "recorded", case((Bill.paid_centavos <= 0, "ready"), (Bill.paid_centavos >= Bill.payable_centavos, "paid"), else_="partly_paid")),
    else_=func.coalesce(Bill.stage, "draft"),
)


def bill_state(b: Bill) -> str:
    if b.status == "void":
        return "void"
    if b.status == "recorded":
        return {"unpaid": "ready"}.get(payment_state(b), payment_state(b))
    return b.stage or "draft"


def bill_summary(b: Bill, held: int = 0) -> dict:
    """`held`: what open payment vouchers set aside of it. Paid and left are always shown, not
    behind a click (you, 2026-10-23: part-payments must be seen)."""
    state = payment_state(b)
    where = bill_state(b)
    return {
        "id": b.id, "no": b.no, "status": b.status, "statusLabel": STATUS_LABELS[b.status], "state": where, "stateLabel": STATE_LABELS[where],
        "supplier": {"id": b.supplier.id, "name": b.supplier.name},
        "billNumber": b.bill_number, "billDate": b.bill_date.isoformat(), "dueDate": b.due_date.isoformat(),
        "totalCentavos": b.total_centavos, "payableCentavos": b.payable_centavos, "withheldCentavos": b.withheld_centavos,
        "paidCentavos": b.paid_centavos, "leftCentavos": max(b.payable_centavos - b.paid_centavos, 0) if b.status == "recorded" else 0,
        "setAsideCentavos": held, "paymentState": state, "paymentLabel": PAYMENT_LABELS[state],
        "documentMissing": not b.files, "createdBy": b.created_by,
    }


def may_bill(user, b: Bill) -> dict:
    """What this person may do to this bill now. Whoever submitted it does no later step (Malou
    Q10); whoever approved it doesn't also check it."""
    can = access_of(user).can
    mine = b.submitted_by_id == user.id
    open_ = b.status == "draft" and b.stage in (None, "returned")
    return {
        "canEdit": open_ and can("bills.create"),
        "canSubmit": open_ and can("bills.create") and b.tax_reviewed,
        "canApprove": b.status == "draft" and b.stage == "to_approve" and can("bills.approve") and not mine,
        "canCheck": b.status == "draft" and b.stage == "to_check" and can("bills.check") and not mine and b.approved_by_id != user.id,
        "canReturn": b.status == "draft" and not mine and (
            (b.stage == "to_approve" and can("bills.approve"))
            or (b.stage == "to_check" and can("bills.check") and b.approved_by_id != user.id)
        ),
        "canVoid": b.status == "recorded" and can("bills.void"),
        "canAttach": b.status != "void" and can("bills.create"),
        "canPay": b.status == "recorded" and b.paid_centavos < b.payable_centavos and can("vouchers.prepare"),
    }


def bill_out(db: DB, b: Bill, user=None) -> dict:
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_({ln["accountId"] for ln in b.lines})))} if b.lines else {}
    worked, problem = None, None
    if b.status == "draft" and b.lines:
        try:
            w = work_out(db, b.lines, b.bill_date, b.amounts_include_vat)
            worked = (w.lines, w.net, w.vat, w.withheld, w.total, w.payable)
        except HTTPException as refused:
            problem = refused.detail
    lines = worked[0] if worked else b.lines
    totals = worked[1:] if worked else (b.net_centavos, b.vat_centavos, b.withheld_centavos, b.total_centavos, b.payable_centavos)
    return bill_summary(b, set_aside(db, [b.id]).get(b.id, 0)) | (may_bill(user, b) if user is not None else {}) | {
        "supplier": supplier_out(db, b.supplier), "taxReviewed": b.tax_reviewed,
        "poNumber": b.po_number, "drNumber": b.dr_number, "checkedPo": b.checked_po, "checkedDr": b.checked_dr,
        "amountsIncludeVat": b.amounts_include_vat, "zohoRef": b.zoho_ref, "oojeemaRef": b.oojeema_ref, "notes": b.notes,
        "lines": [
            ln | {
                "account": {"id": a.id, "code": a.code, "name": a.name} if (a := accounts.get(ln["accountId"])) else None,
                "vatLabel": VAT_KINDS.get(ln["vat"], ln["vat"]),
                "purchaseType": ln.get("purchaseType", "other_goods"),
                "purchaseTypeLabel": PURCHASE_TYPES[ln.get("purchaseType", "other_goods")],
                "withholdingRateBp": WITHHOLDING[ln["withholding"]][1] if ln.get("withholding") in WITHHOLDING else None,
            }
            for ln in lines
        ],
        "netCentavos": totals[0], "vatCentavos": totals[1], "withheldCentavos": totals[2], "totalCentavos": totals[3], "payableCentavos": totals[4],
        # Bills with tax withheld are checked after approval (Mel); the others skip it.
        "needsCheck": totals[2] > 0,
        "problem": problem,
        "files": files_out(b.files),
        "entryId": b.entry_id,
        "vouchers": [
            {"id": v.id, "number": v.number, "status": v.status, "amountCentavos": ln.amount_centavos}
            for ln, v in db.execute(
                select(VoucherLine, PaymentVoucher).join(PaymentVoucher, PaymentVoucher.id == VoucherLine.voucher_id)
                .where(VoucherLine.bill_id == b.id, PaymentVoucher.status.notin_(("cancelled",))).order_by(PaymentVoucher.created_at)
            ).all()
        ],
        "approvedBy": b.approved_by, "approvedAt": b.approved_at.isoformat() if b.approved_at else None,
        "checkedBy": b.checked_by, "checkedAt": b.checked_at.isoformat() if b.checked_at else None,
        "recordedBy": b.recorded_by, "recordedAt": b.recorded_at.isoformat() if b.recorded_at else None,
        "voidedBy": b.voided_by, "voidedAt": b.voided_at.isoformat() if b.voided_at else None, "voidReason": b.void_reason,
        "events": [{"at": e.at.isoformat(), "kind": e.kind, "who": e.who, "text": e.text} for e in b.events],
    }


@router.get("/bills/choices")
def bill_choices(user: permitted("bills.view"), db: DB, settings: SettingsDep) -> dict:
    """What the bill form offers: active suppliers, the accounts a line can go to (expenses
    and assets), the VAT kinds and the withholding codes."""
    suppliers = db.scalars(select(Supplier).where(Supplier.is_active).order_by(func.lower(Supplier.name))).all()
    accounts = db.scalars(select(Account).where(Account.is_active, Account.type.in_(("expense", "asset"))).order_by(Account.code)).all()
    return {
        "suppliers": [supplier_out(db, s, 0) for s in suppliers],
        "accounts": [{"id": a.id, "code": a.code, "name": a.name, "type": a.type} for a in accounts],
        "vatKinds": [{"key": k, "label": v} for k, v in VAT_KINDS.items()],
        "purchaseTypes": [{"key": k, "label": v} for k, v in PURCHASE_TYPES.items()],
        "withholding": withholding_out(), "canEditSuppliers": access_of(user).can("suppliers.edit"),
        "today": today(settings).isoformat(),
    }


@router.get("/bills")
def list_bills(
    user: permitted("bills.view"),
    db: DB,
    settings: SettingsDep,
    show: str | None = Query(None, max_length=20),
    q: str | None = Query(None, max_length=100),
    missing: bool = False,
    queue: str | None = Query(None, max_length=30),
    supplier_id: str | None = Query(None, alias="supplierId", max_length=36),
    bucket: str | None = Query(None, max_length=12),
) -> dict:
    from app.payables_work import BILL_QUEUES, event_note, filter_bills
    from app.routers.receivables import BUCKETS

    if queue and queue not in BILL_QUEUES:
        raise field_error("queue", "Pick a listed Payables work queue.")
    if bucket and bucket not in {k for k, _, _ in BUCKETS}:
        raise field_error("bucket", "Pick a listed aging bucket.")
    query = select(Bill).join(Supplier, Supplier.id == Bill.supplier_id)
    if show in STATE_LABELS:
        query = query.where(STATE == show)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(
            func.lower(Supplier.name).like(like), func.lower(Bill.bill_number).like(like), func.lower(func.coalesce(Bill.po_number, "")).like(like),
            func.lower(func.coalesce(Bill.zoho_ref, "")).like(like), func.lower(func.coalesce(Bill.oojeema_ref, "")).like(like),
        ))
    if missing:
        query = query.where(Bill.status != "void", ~select(BillFile.id).where(BillFile.bill_id == Bill.id).exists())
    items = db.scalars(query.order_by(Bill.bill_date.desc(), Bill.no.desc())).all()
    held = set_aside(db, [b.id for b in items])
    items = filter_bills(items, user, today(settings), held, queue, supplier_id, bucket)
    counts = dict(db.execute(select(STATE, func.count()).select_from(Bill).group_by(STATE)).all())
    without = db.scalar(select(func.count()).select_from(Bill).where(Bill.status != "void", ~select(BillFile.id).where(BillFile.bill_id == Bill.id).exists())) or 0
    can = access_of(user).can
    return {
        "items": [bill_summary(b, held.get(b.id, 0)) | {"queueNote": event_note(b, today(settings), bool(queue and queue.startswith("sent_"))) if queue else None} for b in items],
        "counts": {k: counts.get(k, 0) for k in STATE_LABELS} | {"missing": without},
        "canCreate": can("bills.create"),
        "queueLabel": BILL_QUEUES[queue][0] if queue else None,
    }


class BillLineIn(Api):
    purchase_type: Literal["services", "capital_goods", "other_goods", "importation"] = "other_goods"
    account_id: str
    description: str | None = Field(None, max_length=200)
    amount_centavos: int = Field(gt=0, lt=10**11)
    vat: Literal["vat", "zero", "exempt", "none"] = "vat"
    withholding: str | None = Field(None, max_length=10)


class BillIn(Api):
    tax_reviewed: bool = False
    save_supplier_defaults: bool = False
    supplier_vat_registered: bool | None = None
    supplier_withholding: str | None = None
    supplier_id: str
    bill_number: str = Field(min_length=1, max_length=60)
    bill_date: date
    due_date: date | None = None
    po_number: str | None = Field(None, max_length=60)
    dr_number: str | None = Field(None, max_length=60)
    checked_po: bool = False
    checked_dr: bool = False
    amounts_include_vat: bool = True
    zoho_ref: str | None = Field(None, max_length=60)
    oojeema_ref: str | None = Field(None, max_length=60)
    notes: str | None = Field(None, max_length=500)
    lines: list[BillLineIn] = Field(min_length=1, max_length=100)


def line_error(i: int, field: str, message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "lines", i, field], "msg": message}])


def apply_bill(db: DB, settings, b: Bill, body: BillIn, user) -> None:
    supplier = db.get(Supplier, body.supplier_id)
    if supplier is None or not supplier.is_active:
        raise field_error("supplierId", "Pick an active supplier.")
    if body.bill_date > today(settings):
        raise field_error("billDate", "The bill date can't be in the future.")
    due = body.due_date or body.bill_date + timedelta(days=supplier.terms_days)
    if due < body.bill_date:
        raise field_error("dueDate", "The due date can't be before the bill date.")
    number = body.bill_number.strip()
    twin = db.scalar(select(Bill).where(
        Bill.supplier_id == supplier.id, func.lower(Bill.bill_number) == number.lower(), Bill.status != "void", Bill.id != (b.id or ""),
    ))
    if twin:
        raise field_error("billNumber", f"This invoice from {supplier.name} is already here: bill {twin.no} ({STATE_LABELS[bill_state(twin)].lower()}).")
    lines = []
    for i, line in enumerate(body.lines):
        a = db.get(Account, line.account_id)
        if a is None or not a.is_active or a.type not in ("expense", "asset"):
            raise line_error(i, "accountId", "Pick an active expense or asset account.")
        if line.withholding and line.withholding not in WITHHOLDING:
            raise line_error(i, "withholding", "Pick a withholding code from the list.")
        lines.append({"accountId": a.id, "description": line.description, "amountCentavos": line.amount_centavos, "vat": line.vat, "withholding": line.withholding, "purchaseType": line.purchase_type})
    b.tax_reviewed = body.tax_reviewed and all("vat" in line.model_fields_set and "withholding" in line.model_fields_set for line in body.lines)
    b.supplier_id, b.bill_number, b.bill_date, b.due_date = supplier.id, number, body.bill_date, due
    b.po_number, b.dr_number, b.checked_po, b.checked_dr = body.po_number, body.dr_number, body.checked_po, body.checked_dr
    b.amounts_include_vat, b.zoho_ref, b.oojeema_ref, b.notes, b.lines = body.amounts_include_vat, body.zoho_ref, body.oojeema_ref, body.notes, lines
    # Worked out now, so a draft's list shows its total; clearing works it out again.
    w = work_out(db, lines, body.bill_date, body.amounts_include_vat)
    b.net_centavos, b.vat_centavos, b.withheld_centavos, b.total_centavos, b.payable_centavos = w.net, w.vat, w.withheld, w.total, w.payable
    if body.save_supplier_defaults:
        if not access_of(user).can("suppliers.edit"):
            raise HTTPException(403, "You may review this bill, but changing supplier defaults requires Edit suppliers.")
        if not b.tax_reviewed or body.supplier_vat_registered is None or "supplier_withholding" not in body.model_fields_set:
            raise HTTPException(422, "Explicitly confirm supplier VAT registration and withholding before saving defaults.")
        if body.supplier_withholding and body.supplier_withholding not in WITHHOLDING:
            raise HTTPException(422, "Choose a valid supplier withholding code.")
        supplier.vat_registered, supplier.withholding, supplier.tax_defaults_confirmed = body.supplier_vat_registered, body.supplier_withholding, True
        audit(db, user, "supplier.tax_defaults_confirmed", target=supplier.name, target_type="supplier", target_id=supplier.id, fields=["vat_registered", "withholding", "tax_defaults_confirmed"])
    if b.tax_reviewed:
        bill_event(b, "tax_reviewed", user)


def found_bill(db: DB, bill_id: str) -> Bill:
    b = db.get(Bill, bill_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such bill.")
    return b


def editable(b: Bill) -> None:
    if b.status != "draft" or b.stage not in (None, "returned"):
        where = STATE_LABELS[bill_state(b)].lower()
        raise HTTPException(status.HTTP_409_CONFLICT, f"This bill is {where}: only a draft or a returned bill is changed. A posted bill is voided and entered again.")


@router.post("/bills", status_code=status.HTTP_201_CREATED)
def add_bill(user: permitted("bills.create"), db: DB, settings: SettingsDep, body: BillIn) -> dict:
    b = Bill(created_by=user.full_name)
    apply_bill(db, settings, b, body, user)
    db.add(b)
    db.flush()
    audit(db, user, "bill.created", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b, user)


@router.get("/bills/{bill_id}")
def read_bill(user: permitted("bills.view"), db: DB, bill_id: str) -> dict:
    return bill_out(db, found_bill(db, bill_id), user)


@router.put("/bills/{bill_id}")
def change_bill(user: permitted("bills.create"), db: DB, settings: SettingsDep, bill_id: str, body: BillIn) -> dict:
    b = found_bill(db, bill_id)
    editable(b)
    apply_bill(db, settings, b, body, user)
    audit(db, user, "bill.updated", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b, user)


@router.delete("/bills/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(user: permitted("bills.create"), db: DB, bill_id: str) -> Response:
    b = found_bill(db, bill_id)
    editable(b)
    refs = [f.ref for f in b.files]
    audit(db, user, "bill.deleted", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    done(db, "bill.returned", bill_link(b))
    db.delete(b)
    for ref in refs:
        if stored := db.get(StoredFile, ref):
            db.delete(stored)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the bill's approval: submitted, approved, checked if tax is withheld, then posted ---------


def bill_link(b: Bill) -> str:
    return f"/bills/{b.id}"


def bill_name(b: Bill) -> str:
    return f"bill {b.no} ({b.supplier.name}, invoice {b.bill_number}, {peso(b.payable_centavos)})"


def peso(centavos: int) -> str:
    return f"₱{centavos / 100:,.2f}"


def bill_event(b: Bill, kind: str, user, text: str | None = None) -> None:
    b.events.append(BillEvent(kind=kind, who=user.full_name[:120], who_id=user.id, text=(text or None) and text[:300]))


def bill_content(b: Bill) -> dict:
    """What a bill says: what each signature on it vouches for."""
    return {
        "supplier": b.supplier.name, "number": b.bill_number, "date": b.bill_date.isoformat(), "due": b.due_date.isoformat(),
        "lines": [[ln["accountId"], ln["amountCentavos"], ln["vat"], ln.get("withholding")] for ln in b.lines],
        "net": b.net_centavos, "vat": b.vat_centavos, "withheld": b.withheld_centavos, "payable": b.payable_centavos,
    }


def at_stage(b: Bill, stage: str) -> None:
    if b.status != "draft" or b.stage != stage:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This bill is {STATE_LABELS[bill_state(b)].lower()}: someone may have acted on it already. Reload to see where it stands.")


def not_submitter(user, b: Bill) -> None:
    if b.submitted_by_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You submitted this bill, so someone else approves and checks it.")


@router.post("/bills/{bill_id}/submit")
def submit_bill(user: permitted("bills.create"), db: DB, bill_id: str) -> dict:
    """For approval: Malou is told first (bills.first); the other approvers are backup (Cristal)."""
    b = found_bill(db, bill_id)
    editable(b)
    if not b.tax_reviewed:
        raise HTTPException(409, "Open this draft and confirm its VAT and withholding choices before submitting.")
    if not b.supplier.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{b.supplier.name} is switched off. Switch the supplier back on, or pick another.")
    w = work_out(db, b.lines, b.bill_date, b.amounts_include_vat)
    b.net_centavos, b.vat_centavos, b.withheld_centavos, b.total_centavos, b.payable_centavos = w.net, w.vat, w.withheld, w.total, w.payable
    again = b.stage == "returned"
    b.stage, b.submitted_by_id = "to_approve", user.id
    b.approved_by = b.approved_by_id = b.approved_at = b.checked_by = b.checked_by_id = b.checked_at = None
    bill_event(b, "resubmitted" if again else "submitted", user)
    sign(db, user, "bill", b.id, "prepared", bill_content(b))
    done(db, "bill.returned", bill_link(b))
    approvers = [u for u in holders(db, "bills.approve") if u.id != user.id]
    first = [u for u in approvers if not u.role.is_system and "bills.first" in permissions_of(u.role)]
    tell(db, first or approvers, "bill.to_approve",
         f"{user.full_name} {'resubmitted' if again else 'submitted'} {bill_name(b)}. Waiting for your approval.", link=bill_link(b))
    audit(db, user, "bill.submitted", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b, user)


def clear(db: DB, user, b: Bill) -> None:
    """Approved (and checked, if tax is withheld): posted to the books. Dr each line's account
    (before VAT) and Input VAT; Cr Accounts payable (what's paid the supplier) and the
    withholding tax payable (Reconciler rule 3). Then ready to pay: Cristal is told."""
    if not b.supplier.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{b.supplier.name} is switched off. Switch the supplier back on, or return the bill.")
    w = work_out(db, b.lines, b.bill_date, b.amounts_include_vat)
    s = posting_settings(db)
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_({ln["accountId"] for ln in w.lines})))}
    if any(not (a := accounts.get(ln["accountId"])) or not a.is_active for ln in w.lines):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account on this bill has been switched off. Return the bill so it's corrected.")
    legs = [Leg(accounts[ln["accountId"]], debit=ln["netCentavos"], description=(ln.get("description") or None)) for ln in w.lines]
    legs.append(Leg(db.get(Account, s.input_tax_account_id) if s.input_tax_account_id else None, debit=w.vat, description="Input VAT"))
    # The supplier's own payables account (e.g. AP - Trade), if it's set and still active; else the default.
    own = db.get(Account, b.supplier.payables_account_id) if b.supplier.payables_account_id else None
    payables = own if own is not None and own.is_active else (db.get(Account, s.payables_account_id) if s.payables_account_id else None)
    legs.append(Leg(payables, credit=w.payable, description=b.supplier.name[:200]))
    legs.append(Leg(db.get(Account, s.withholding_account_id) if s.withholding_account_id else None, credit=w.withheld, description="Tax withheld (EWT)"))
    e = post(db, b.bill_date, f"Bill from {b.supplier.name}, invoice {b.bill_number}", legs, user.full_name, reference=b.bill_number[:80], source="bill", by_id=user.id)
    b.lines = w.lines
    b.net_centavos, b.vat_centavos, b.withheld_centavos, b.total_centavos, b.payable_centavos = w.net, w.vat, w.withheld, w.total, w.payable
    b.status, b.stage, b.entry_id, b.recorded_at, b.recorded_by = "recorded", None, e.id, datetime.now(UTC), user.full_name
    b.payables_account_id = payables.id if payables else None  # payment vouchers take it off this same account
    bill_event(b, "cleared", user)
    tell(db, holders(db, "vouchers.release"), "bill.ready", f"{bill_name(b)} is approved and posted. Ready to pay, due {b.due_date:%d %b %Y}.",
         link=bill_link(b), not_to=[user.id])
    audit(db, user, "bill.recorded", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)


@router.post("/bills/{bill_id}/approve")
def approve_bill(user: permitted("bills.approve"), db: DB, bill_id: str) -> dict:
    """Malou (Cristal backup). With tax withheld, it goes to be checked (Mel); else it clears."""
    b = found_bill(db, bill_id)
    at_stage(b, "to_approve")
    not_submitter(user, b)
    b.approved_by, b.approved_by_id, b.approved_at = user.full_name[:120], user.id, datetime.now(UTC)
    bill_event(b, "approved", user)
    sign(db, user, "bill", b.id, "approved", bill_content(b))
    done(db, "bill.to_approve", bill_link(b))
    if b.withheld_centavos > 0:
        b.stage = "to_check"
        tell(db, holders(db, "bills.check"), "bill.to_check", f"{user.full_name} approved {bill_name(b)}. It has tax withheld: waiting for you to check it.",
             link=bill_link(b), not_to=[b.submitted_by_id, user.id])
    else:
        clear(db, user, b)
    audit(db, user, "bill.approved", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b, user)


@router.post("/bills/{bill_id}/check")
def check_bill(user: permitted("bills.check"), db: DB, bill_id: str) -> dict:
    """Mel checks the tax withheld (the BIR code and rate); then it clears."""
    b = found_bill(db, bill_id)
    at_stage(b, "to_check")
    not_submitter(user, b)
    if b.approved_by_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You approved this bill, so someone else checks it.")
    b.checked_by, b.checked_by_id, b.checked_at = user.full_name[:120], user.id, datetime.now(UTC)
    bill_event(b, "checked", user)
    sign(db, user, "bill", b.id, "checked", bill_content(b))
    done(db, "bill.to_check", bill_link(b))
    clear(db, user, b)
    audit(db, user, "bill.checked", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b, user)


class ReasonIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/bills/{bill_id}/return")
def return_bill(user: CurrentUser, db: DB, bill_id: str, body: ReasonIn) -> dict:
    """Back to whoever submitted it, with the reason; corrected, it goes to approval again."""
    b = found_bill(db, bill_id)
    if not may_bill(user, b)["canReturn"]:
        if b.status != "draft" or b.stage not in ("to_approve", "to_check"):
            at_stage(b, "to_approve")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow returning this bill at this step, or you submitted or approved it.")
    was = b.stage
    reason = body.reason.strip()
    b.stage = "returned"
    b.approved_by = b.approved_by_id = b.approved_at = b.checked_by = b.checked_by_id = b.checked_at = None
    bill_event(b, "returned", user, reason)
    for kind in ("bill.to_approve", "bill.to_check"):
        done(db, kind, bill_link(b))
    tell(db, [b.submitted_by_id], "bill.returned", f"{user.full_name} returned {bill_name(b)} ({STATE_LABELS[was].lower()}): {reason}", link=bill_link(b), not_to=[user.id])
    audit(db, user, "bill.returned", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id, fields=["reason"])
    db.commit()
    return bill_out(db, b, user)


class VoidIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/bills/{bill_id}/void")
def void_bill(user: permitted("bills.void"), db: DB, settings: SettingsDep, bill_id: str, body: VoidIn) -> dict:
    """A posted bill, cancelled: its entry reversed today, the bill kept and marked void."""
    b = found_bill(db, bill_id)
    if b.status != "recorded":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a posted bill is voided. A draft is simply deleted; one waiting for approval is returned first.")
    paying = db.scalars(
        select(PaymentVoucher.number).join(VoucherLine, VoucherLine.voucher_id == PaymentVoucher.id)
        .where(VoucherLine.bill_id == b.id, PaymentVoucher.status.notin_(("cancelled", "void")))
    ).all()
    if paying:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Payment voucher {', '.join(sorted(set(paying)))} pays this bill: cancel or void it first.")
    reason = body.reason.strip()
    entry = db.get(JournalEntry, b.entry_id) if b.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of bill {b.no} ({b.supplier.name}, invoice {b.bill_number}): {reason}"[:300], legs, user.full_name,
             reference=b.bill_number[:80], source="bill", reverses=entry, by_id=user.id)
    b.status, b.void_reason, b.voided_at, b.voided_by = "void", reason, datetime.now(UTC), user.full_name
    bill_event(b, "voided", user, reason)
    done(db, "bill.ready", bill_link(b))
    audit(db, user, "bill.voided", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b, user)


# --- the supplier's invoice, attached ----------------------------------------------------------


@router.post("/bills/{bill_id}/files", status_code=status.HTTP_201_CREATED)
def attach(user: permitted("bills.create"), db: DB, bill_id: str, body: FileIn) -> dict:
    """Attached at any step before void (the document often comes later)."""
    b = found_bill(db, bill_id)
    if b.status == "void":
        raise HTTPException(status.HTTP_409_CONFLICT, "This bill is void: nothing more is attached to it.")
    if len(b.files) >= MAX_FILES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A bill keeps up to {MAX_FILES} files. Remove one first.")
    ref, size = store_file(db, body)
    b.files.append(BillFile(ref=ref, name=body.name.strip(), content_type=body.content_type, size=size, uploaded_by=user.full_name))
    audit(db, user, "bill.file_added", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b, user)


@router.get("/bills/{bill_id}/files/{file_id}")
def open_file(user: permitted("bills.view"), db: DB, bill_id: str, file_id: str) -> Response:
    return file_response(db, found_file(found_bill(db, bill_id).files, file_id))


@router.delete("/bills/{bill_id}/files/{file_id}")
def remove_file(user: permitted("bills.create"), db: DB, bill_id: str, file_id: str) -> dict:
    b = found_bill(db, bill_id)
    if b.status == "void":
        raise HTTPException(status.HTTP_409_CONFLICT, "This bill is void: its files stay as they are.")
    f = found_file(b.files, file_id)
    if stored := db.get(StoredFile, f.ref):
        db.delete(stored)
    b.files.remove(f)
    audit(db, user, "bill.file_removed", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b, user)
