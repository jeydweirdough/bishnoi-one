"""Document Auto-Scan & Receipt OCR Inbox (migration 0042).

Uploads PDFs or photos, extracts text cleanly (server `pypdf` for PDFs; browser `tesseract.js` text for photos),
parses against real `nbfi_suppliers`, and converts to a draft Bill with the file already attached.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import select

from modules.finance import company_scope
from modules.finance.access import permitted
from modules.finance.audit import audit
from modules.finance.deps import DB, SettingsDep
from modules.finance.funds import decode
from modules.finance.models import Account, Bill, BillFile, DocumentScan, StoredFile, Supplier
from modules.finance.payables import VAT_KINDS, work_out as bill_work_out
from modules.finance.receipt_scan import extract_pdf_text, parse_receipt
from modules.finance.routers.funds import today
from modules.finance.routers.payables import FileIn, store_file
from modules.finance.routers.tax import Api, field_error, iso

router = APIRouter(prefix="/scans", tags=["scans"])


class ScanUploadIn(FileIn):
    ocr_text: str | None = Field(None, max_length=100_000)


class ConvertScanIn(Api):
    supplier_id: str = Field(min_length=1, max_length=36)
    account_id: str = Field(min_length=1, max_length=36)
    bill_number: str = Field(min_length=1, max_length=60)
    bill_date: date
    amount_centavos: int = Field(gt=0)
    vat: Literal["vat", "zero", "exempt", "none"] = "vat"
    description: str | None = Field(None, max_length=200)
    amounts_include_vat: bool = True


def _scan_out(s: DocumentScan) -> dict:
    return {
        "id": s.id,
        "fileName": s.file_name,
        "contentType": s.file_type,
        "size": s.file_size,
        "status": s.status,
        "rawText": s.raw_text,
        "parsed": s.parsed,
        "linkedBillId": s.linked_bill_id,
        "createdBy": s.created_by,
        "createdAt": iso(s.created_at),
    }


@router.get("")
def list_scans(_: permitted("bills.view"), db: DB) -> dict:
    scans = [_scan_out(s) for s in db.scalars(select(DocumentScan).order_by(DocumentScan.created_at.desc()).limit(100))]
    sup_q = select(Supplier).where(Supplier.is_active).order_by(Supplier.name)
    if company_scope.configured(db, "supplier"):
        sup_q = sup_q.where(company_scope.usable_clause("supplier", Supplier.id))
    acct_q = select(Account).where(Account.is_active, Account.type.in_(("expense", "asset"))).order_by(Account.code)
    if company_scope.configured(db, "account"):
        acct_q = acct_q.where(company_scope.usable_clause("account", Account.id))
    suppliers = [{"id": s.id, "name": s.name, "tin": s.tin} for s in db.scalars(sup_q)]
    accounts = [{"id": a.id, "code": a.code, "name": a.name} for a in db.scalars(acct_q)]
    return {"items": scans, "suppliers": suppliers, "accounts": accounts, "vatKinds": [{"key": k, "label": v} for k, v in VAT_KINDS.items()]}


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_scan(user: permitted("bills.create"), db: DB, body: ScanUploadIn) -> dict:
    ref, size = store_file(db, body)
    raw_bytes = decode(body.data)
    text = (body.ocr_text or "").strip()
    if not text and body.content_type == "application/pdf":
        text = extract_pdf_text(raw_bytes)
    parsed = parse_receipt(db, text)
    scan = DocumentScan(
        file_ref=ref, file_name=body.name.strip()[:200], file_type=body.content_type, file_size=size,
        status="ready", raw_text=text, parsed=parsed, created_by=user.full_name,
    )
    db.add(scan)
    db.flush()
    audit(db, user, "scan.uploaded", target=scan.file_name, target_type="scan", target_id=scan.id)
    db.commit()
    return _scan_out(scan)


@router.get("/{scan_id}/file")
def open_scan_file(_: permitted("bills.view"), db: DB, scan_id: str) -> Response:
    scan = db.get(DocumentScan, scan_id)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such scanned document.")
    stored = db.get(StoredFile, scan.file_ref)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File bytes are missing.")
    safe_name = scan.file_name.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(stored.data, media_type=stored.content_type, headers={"Content-Disposition": f'inline; filename="{safe_name}"'})


@router.post("/{scan_id}/convert-to-bill")
def convert_to_bill(user: permitted("bills.create"), db: DB, settings: SettingsDep, scan_id: str, body: ConvertScanIn) -> dict:
    scan = db.get(DocumentScan, scan_id)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such scanned document.")
    if scan.linked_bill_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This scan has already been converted to a draft bill.")
    if company_scope.configured(db, "supplier"):
        company_scope.require_ids(db, "supplier", [body.supplier_id], status_code=422)
    if company_scope.configured(db, "account"):
        company_scope.require_ids(db, "account", [body.account_id], status_code=422)
    sup = db.get(Supplier, body.supplier_id)
    if sup is None or not sup.is_active:
        raise field_error("supplierId", "Pick an active supplier.")
    acc = db.get(Account, body.account_id)
    if acc is None or not acc.is_active or acc.type not in ("expense", "asset"):
        raise field_error("accountId", "Pick an active expense or asset account.")
    if body.bill_date > today(settings):
        raise field_error("billDate", "Bill date can't be in the future.")
    line = {"accountId": acc.id, "description": body.description or f"From scan: {scan.file_name}", "amountCentavos": body.amount_centavos, "vat": body.vat, "withholding": None, "purchaseType": "other_goods"}
    w = bill_work_out(db, [line], body.bill_date, body.amounts_include_vat)
    b = Bill(
        supplier_id=sup.id,
        bill_number=body.bill_number.strip(),
        bill_date=body.bill_date,
        due_date=body.bill_date + timedelta(days=int(sup.terms_days or 30)),
        amounts_include_vat=body.amounts_include_vat,
        notes=f"Created from Document Scan ({scan.file_name}). Please verify VAT & withholding before submitting.",
        lines=[line],
        tax_reviewed=False,
        net_centavos=w.net, vat_centavos=w.vat, withheld_centavos=w.withheld,
        total_centavos=w.total, payable_centavos=w.payable,
        created_by=user.full_name,
    )
    b.files.append(BillFile(ref=scan.file_ref, name=scan.file_name, content_type=scan.file_type, size=scan.file_size, uploaded_by=user.full_name))
    db.add(b)
    db.flush()
    scan.status = "linked"
    scan.linked_bill_id = b.id
    audit(db, user, "scan.converted_to_bill", target=f"{scan.file_name} -> {b.bill_number}", target_type="scan", target_id=scan.id)
    db.commit()
    return {"scanId": scan.id, "billId": b.id, "billNo": b.no, "href": f"/bills/{b.id}?edit=1"}


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(user: permitted("bills.create"), db: DB, scan_id: str) -> None:
    scan = db.get(DocumentScan, scan_id)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such scanned document.")
    if not scan.linked_bill_id:
        if stored := db.get(StoredFile, scan.file_ref):
            db.delete(stored)
    db.delete(scan)
    db.commit()
