"""Payables: suppliers, and their bills, with the supplier's invoice attached.

- /finance/suppliers: who the company buys from (suppliers.view, .add, .edit, .deactivate: each a
  tick on the Roles screen, 2026-10-23), with their papers attached.
- /finance/bills: supplier bills. A draft is made, changed, deleted and has files attached
  by whoever may make drafts (bills.create); recording posts it to the books at once, like
  an issued invoice (bills.record; the checkers come at the payment voucher, later); a
  recorded bill is voided with a reason (bills.void), which posts the reversal, and never
  changed. Each a tick on the Roles screen (split 2026-10-23, migration 0018).
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
from sqlalchemy import func, or_, select

from app.access import access_of, permitted
from app.audit import audit
from app.deps import DB, SettingsDep
from app.funds import RECEIPT_TYPES, decode
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.models import Account, Bill, BillFile, JournalEntry, StoredFile, Supplier, SupplierFile
from app.payables import VAT_KINDS, WITHHOLDING, withholding_out, work_out
from app.routers.funds import today
from app.routers.tax import Api, field_error, split_tin

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
    """What's owed each supplier: their recorded bills (payments come with the vouchers, later)."""
    return dict(db.execute(select(Bill.supplier_id, func.sum(Bill.payable_centavos)).where(Bill.status == "recorded").group_by(Bill.supplier_id)).all())


def supplier_out(db: DB, s: Supplier, owed: int | None = None) -> dict:
    code = s.withholding
    return {
        "id": s.id, "no": s.no, "name": s.name, "companyName": s.company_name,
        "salutation": s.salutation, "firstName": s.first_name, "lastName": s.last_name,
        "tin": s.tin, "branchCode": s.branch_code, "address": s.address,
        "vatRegistered": s.vat_registered,
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


class SupplierRowIn(Api):
    name: str | None = Field(None, max_length=300)
    company_name: str | None = Field(None, max_length=300)
    salutation: str | None = Field(None, max_length=40)
    first_name: str | None = Field(None, max_length=200)
    last_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=400)
    phone: str | None = Field(None, max_length=100)
    mobile: str | None = Field(None, max_length=100)
    tin: str | None = Field(None, max_length=100)
    company_id: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=600)
    terms: str | None = Field(None, max_length=60)
    notes: str | None = Field(None, max_length=2000)
    status: str | None = Field(None, max_length=40)
    currency: str | None = Field(None, max_length=10)


class SupplierImportCheckIn(Api):
    rows: list[SupplierRowIn] = Field(min_length=1, max_length=3000)


def terms_days(text: str | None) -> int:
    """Zoho's payment terms as days: "Net 30" or "30" is 30; "Due on receipt" is 0; none: 30."""
    if not text:
        return 30
    digits = re.search(r"\d+", text)
    if digits:
        return min(int(digits.group()), 365)
    return 0 if "receipt" in text.lower() else 30


def cut(value: str | None, size: int) -> str | None:
    value = (value or "").strip()
    return value[:size] or None


def clean_supplier_row(r: SupplierRowIn) -> tuple[dict, list[str], list[str]]:
    """The row as a supplier would be saved, what was noted on the way, and what stops it."""
    notes, problems = [], []
    name = (r.name or "").strip() or (r.company_name or "").strip()
    if not name:
        problems.append("No name.")
    elif len(name) > 200:
        problems.append("The name is over 200 characters.")
    tin = branch = None
    for given in (r.tin, r.company_id):
        if given and given.strip() and tin is None:
            try:
                tin, in_tin = split_tin(given)
                branch = in_tin or "00000"
            except ValueError:
                notes.append(f"Company ID in Zoho: {given.strip()} (not a TIN).")
    if r.currency and r.currency.strip().upper() not in ("PHP", "₱"):
        notes.append(f"Billed in {r.currency.strip().upper()} in Zoho: Finance keeps pesos only for now.")
    remarks = "\n".join(x for x in [(r.notes or "").strip(), *notes] if x)[:500] or None
    return {
        "name": name[:200], "companyName": cut(r.company_name, 200), "salutation": cut(r.salutation, 10),
        "firstName": cut(r.first_name, 80), "lastName": cut(r.last_name, 80), "email": cut(r.email, 254),
        "phone": cut(r.phone, 40), "mobile": cut(r.mobile, 40), "tin": tin, "branchCode": branch if tin else None,
        "address": cut(r.address, 300), "termsDays": terms_days(r.terms), "notes": remarks,
        "isActive": (r.status or "").strip().lower() not in ("inactive", "disabled"),
    }, notes, problems


@router.post("/suppliers/import/check")
def check_supplier_import(user: permitted("suppliers.add"), db: DB, body: SupplierImportCheckIn) -> dict:
    here = list(db.scalars(select(Supplier)))
    by_name = {s.name.strip().lower(): s for s in here}
    by_tin = {(s.tin, s.branch_code): s for s in here if s.tin}
    seen_name: dict[str, int] = {}
    seen_tin: dict[tuple, int] = {}
    out = []
    for i, r in enumerate(body.rows):
        supplier, notes, problems = clean_supplier_row(r)
        key, tin_key = supplier["name"].lower(), (supplier["tin"], supplier["branchCode"])
        twin = by_name.get(key) or (by_tin.get(tin_key) if supplier["tin"] else None)
        earlier = seen_name.get(key) or (seen_tin.get(tin_key) if supplier["tin"] else None)
        if earlier and not problems:
            problems.append(f"The same supplier as line {earlier} (same name or TIN).")
        if supplier["name"]:
            seen_name.setdefault(key, i + 1)
        if supplier["tin"]:
            seen_tin.setdefault(tin_key, i + 1)
        status_ = "here" if twin else "problem" if problems else "new"
        note = f"Already in Finance as {twin.name}." if twin else " ".join(problems + notes) or None
        if status_ == "new" and not supplier["isActive"]:
            note = " ".join(x for x in ["Inactive in Zoho: imported switched off.", note] if x)
        out.append({"line": i + 1, "status": status_, "note": note, "supplier": supplier})
    counts = {k: sum(1 for x in out if x["status"] == k) for k in ("new", "here", "problem")}
    return {"rows": out, "counts": counts}


class SupplierImportRowIn(SupplierIn):
    is_active: bool = True


class SupplierImportIn(Api):
    suppliers: list[SupplierImportRowIn] = Field(min_length=1, max_length=3000)


def first_message(detail) -> str:
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        return str(detail[0].get("msg", "")).replace("Value error, ", "")
    return str(detail)


@router.post("/suppliers/import", status_code=status.HTTP_201_CREATED)
def run_supplier_import(user: permitted("suppliers.add"), db: DB, body: SupplierImportIn) -> dict:
    """Adds the chosen suppliers, all or none: a supplier already here (same name, or TIN and
    branch) refuses the lot, naming its line. VAT-registered and nothing withheld unless the
    row says otherwise: Zoho's export doesn't carry them in the BIR's terms."""
    added = 0
    for i, row in enumerate(body.suppliers):
        s = Supplier(created_by=user.full_name, is_active=row.is_active)
        try:
            apply_supplier(db, s, SupplierIn.model_validate(row.model_dump(exclude={"is_active"})))
        except HTTPException as refused:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, f"Line {i + 1} ({row.name}): {first_message(refused.detail)} Nothing was imported.") from None
        db.add(s)
        db.flush()  # so a later row with the same name or TIN is caught
        added += 1
    audit(db, user, "suppliers.imported", target=f"{added} suppliers", target_type="supplier")
    db.commit()
    return {"added": added}


def found_supplier(db: DB, supplier_id: str) -> Supplier:
    s = db.get(Supplier, supplier_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such supplier.")
    return s


@router.get("/suppliers/{supplier_id}")
def read_supplier(user: permitted("suppliers.view"), db: DB, supplier_id: str) -> dict:
    s = found_supplier(db, supplier_id)
    bills = db.scalars(select(Bill).where(Bill.supplier_id == s.id).order_by(Bill.bill_date.desc(), Bill.no.desc()).limit(50)).all()
    return supplier_out(db, s) | {"bills": [bill_summary(b) for b in bills], "withholdingChoices": withholding_out(),
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


def bill_summary(b: Bill) -> dict:
    return {
        "id": b.id, "no": b.no, "status": b.status, "statusLabel": STATUS_LABELS[b.status],
        "supplier": {"id": b.supplier.id, "name": b.supplier.name},
        "billNumber": b.bill_number, "billDate": b.bill_date.isoformat(), "dueDate": b.due_date.isoformat(),
        "totalCentavos": b.total_centavos, "payableCentavos": b.payable_centavos,
        "documentMissing": not b.files, "createdBy": b.created_by,
    }


def bill_out(db: DB, b: Bill) -> dict:
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
    return bill_summary(b) | {
        "supplier": supplier_out(db, b.supplier),
        "poNumber": b.po_number, "drNumber": b.dr_number, "checkedPo": b.checked_po, "checkedDr": b.checked_dr,
        "amountsIncludeVat": b.amounts_include_vat, "zohoRef": b.zoho_ref, "oojeemaRef": b.oojeema_ref, "notes": b.notes,
        "lines": [
            ln | {
                "account": {"id": a.id, "code": a.code, "name": a.name} if (a := accounts.get(ln["accountId"])) else None,
                "vatLabel": VAT_KINDS.get(ln["vat"], ln["vat"]),
                "withholdingRateBp": WITHHOLDING[ln["withholding"]][1] if ln.get("withholding") in WITHHOLDING else None,
            }
            for ln in lines
        ],
        "netCentavos": totals[0], "vatCentavos": totals[1], "withheldCentavos": totals[2], "totalCentavos": totals[3], "payableCentavos": totals[4],
        "problem": problem,
        "files": [
            {"id": f.id, "name": f.name, "contentType": f.content_type, "size": f.size, "uploadedBy": f.uploaded_by, "uploadedAt": f.uploaded_at.isoformat()}
            for f in b.files
        ],
        "entryId": b.entry_id,
        "recordedBy": b.recorded_by, "recordedAt": b.recorded_at.isoformat() if b.recorded_at else None,
        "voidedBy": b.voided_by, "voidedAt": b.voided_at.isoformat() if b.voided_at else None, "voidReason": b.void_reason,
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
        "withholding": withholding_out(),
        "today": today(settings).isoformat(),
    }


@router.get("/bills")
def list_bills(
    user: permitted("bills.view"),
    db: DB,
    state: Literal["draft", "recorded", "void"] | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=100),
    missing: bool = False,
) -> dict:
    query = select(Bill).join(Supplier, Supplier.id == Bill.supplier_id)
    if state:
        query = query.where(Bill.status == state)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(
            func.lower(Supplier.name).like(like), func.lower(Bill.bill_number).like(like), func.lower(func.coalesce(Bill.po_number, "")).like(like),
            func.lower(func.coalesce(Bill.zoho_ref, "")).like(like), func.lower(func.coalesce(Bill.oojeema_ref, "")).like(like),
        ))
    if missing:
        query = query.where(Bill.status != "void", ~select(BillFile.id).where(BillFile.bill_id == Bill.id).exists())
    items = db.scalars(query.order_by(Bill.bill_date.desc(), Bill.no.desc()).limit(300)).all()
    counts = dict(db.execute(select(Bill.status, func.count()).group_by(Bill.status)).all())
    without = db.scalar(select(func.count()).select_from(Bill).where(Bill.status != "void", ~select(BillFile.id).where(BillFile.bill_id == Bill.id).exists())) or 0
    return {"items": [bill_summary(b) for b in items], "counts": {k: counts.get(k, 0) for k in STATUS_LABELS} | {"missing": without}}


class BillLineIn(Api):
    account_id: str
    description: str | None = Field(None, max_length=200)
    amount_centavos: int = Field(gt=0, lt=10**11)
    vat: Literal["vat", "zero", "exempt", "none"] = "vat"
    withholding: str | None = Field(None, max_length=10)


class BillIn(Api):
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


def apply_bill(db: DB, settings, b: Bill, body: BillIn) -> None:
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
        raise field_error("billNumber", f"This invoice from {supplier.name} is already here: bill {twin.no} ({STATUS_LABELS[twin.status].lower()}).")
    lines = []
    for i, line in enumerate(body.lines):
        a = db.get(Account, line.account_id)
        if a is None or not a.is_active or a.type not in ("expense", "asset"):
            raise line_error(i, "accountId", "Pick an active expense or asset account.")
        if line.withholding and line.withholding not in WITHHOLDING:
            raise line_error(i, "withholding", "Pick a withholding code from the list.")
        lines.append({"accountId": a.id, "description": line.description, "amountCentavos": line.amount_centavos, "vat": line.vat, "withholding": line.withholding})
    b.supplier_id, b.bill_number, b.bill_date, b.due_date = supplier.id, number, body.bill_date, due
    b.po_number, b.dr_number, b.checked_po, b.checked_dr = body.po_number, body.dr_number, body.checked_po, body.checked_dr
    b.amounts_include_vat, b.zoho_ref, b.oojeema_ref, b.notes, b.lines = body.amounts_include_vat, body.zoho_ref, body.oojeema_ref, body.notes, lines
    # Worked out now, so a draft's list shows its total; recording works it out again.
    w = work_out(db, lines, body.bill_date, body.amounts_include_vat)
    b.net_centavos, b.vat_centavos, b.withheld_centavos, b.total_centavos, b.payable_centavos = w.net, w.vat, w.withheld, w.total, w.payable


def found_bill(db: DB, bill_id: str) -> Bill:
    b = db.get(Bill, bill_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such bill.")
    return b


@router.post("/bills", status_code=status.HTTP_201_CREATED)
def add_bill(user: permitted("bills.create"), db: DB, settings: SettingsDep, body: BillIn) -> dict:
    b = Bill(created_by=user.full_name)
    apply_bill(db, settings, b, body)
    db.add(b)
    db.flush()
    audit(db, user, "bill.created", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b)


@router.get("/bills/{bill_id}")
def read_bill(user: permitted("bills.view"), db: DB, bill_id: str) -> dict:
    return bill_out(db, found_bill(db, bill_id))


@router.put("/bills/{bill_id}")
def change_bill(user: permitted("bills.create"), db: DB, settings: SettingsDep, bill_id: str, body: BillIn) -> dict:
    b = found_bill(db, bill_id)
    if b.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft is changed. A recorded bill is voided and entered again.")
    apply_bill(db, settings, b, body)
    audit(db, user, "bill.updated", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b)


@router.delete("/bills/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(user: permitted("bills.create"), db: DB, bill_id: str) -> Response:
    b = found_bill(db, bill_id)
    if b.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft is deleted. A recorded bill is voided.")
    refs = [f.ref for f in b.files]
    audit(db, user, "bill.deleted", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.delete(b)
    for ref in refs:
        if stored := db.get(StoredFile, ref):
            db.delete(stored)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bills/{bill_id}/record")
def record_bill(user: permitted("bills.record"), db: DB, settings: SettingsDep, bill_id: str) -> dict:
    """Posts the bill: Dr each line's account (before VAT) and Input VAT; Cr Accounts
    payable (what's paid the supplier) and the withholding tax payable (Reconciler rule 3).
    Counts at once, like an issued invoice: the checks come at the payment voucher."""
    b = found_bill(db, bill_id)
    if b.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "This bill is already recorded or void.")
    if not b.supplier.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{b.supplier.name} is switched off. Switch the supplier back on, or pick another.")
    w = work_out(db, b.lines, b.bill_date, b.amounts_include_vat)
    s = posting_settings(db)
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_({ln["accountId"] for ln in w.lines})))}
    if any(not (a := accounts.get(ln["accountId"])) or not a.is_active for ln in w.lines):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account on this bill has been switched off. Edit the bill and pick another.")
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
    b.status, b.entry_id, b.recorded_at, b.recorded_by = "recorded", e.id, datetime.now(UTC), user.full_name
    audit(db, user, "bill.recorded", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b)


class VoidIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/bills/{bill_id}/void")
def void_bill(user: permitted("bills.void"), db: DB, settings: SettingsDep, bill_id: str, body: VoidIn) -> dict:
    """A recorded bill, cancelled: its entry reversed today, the bill kept and marked void."""
    b = found_bill(db, bill_id)
    if b.status != "recorded":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a recorded bill is voided. A draft is simply deleted.")
    reason = body.reason.strip()
    entry = db.get(JournalEntry, b.entry_id) if b.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of bill {b.no} ({b.supplier.name}, invoice {b.bill_number}): {reason}"[:300], legs, user.full_name,
             reference=b.bill_number[:80], source="bill", reverses=entry, by_id=user.id)
    b.status, b.void_reason, b.voided_at, b.voided_by = "void", reason, datetime.now(UTC), user.full_name
    audit(db, user, "bill.voided", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b)


# --- the supplier's invoice, attached ----------------------------------------------------------


@router.post("/bills/{bill_id}/files", status_code=status.HTTP_201_CREATED)
def attach(user: permitted("bills.create"), db: DB, bill_id: str, body: FileIn) -> dict:
    """Attached to a draft or a recorded bill (the document often comes later); not a void one."""
    b = found_bill(db, bill_id)
    if b.status == "void":
        raise HTTPException(status.HTTP_409_CONFLICT, "This bill is void: nothing more is attached to it.")
    if len(b.files) >= MAX_FILES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A bill keeps up to {MAX_FILES} files. Remove one first.")
    ref, size = store_file(db, body)
    b.files.append(BillFile(ref=ref, name=body.name.strip(), content_type=body.content_type, size=size, uploaded_by=user.full_name))
    audit(db, user, "bill.file_added", target=f"{b.supplier.name} {b.bill_number}", target_type="bill", target_id=b.id)
    db.commit()
    return bill_out(db, b)


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
    return bill_out(db, b)
