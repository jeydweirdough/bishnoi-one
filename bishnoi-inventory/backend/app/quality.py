"""Quality checks on receipt (feature plan step 14a, 2026-10-29): receive → check → store.

A warehouse that checks what it receives (Warehouse.quality_check) takes a receipt's goods in on hold
(Stock.on_hold): on hand, but nobody can reserve or pick them. Its quality check lists each line; the
checker says how many passed and how many failed, and why. Passed goods are released for use; failed goods
are put aside as damaged (a "damage" movement with the reason), to be returned to the vendor or written off
the usual way. A receipt into a warehouse that doesn't check is usable at once, as before.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.api import conflict, field_error
from app.models import QUALITY_REASONS, Location, Product, QualityCheck, QualityCheckLine, Receipt, User
from app.out import product_ref
from app.stock import Ref, balance, next_number, post

REASON_LABELS = {"damaged": "Damaged", "expired": "Expired", "short_expiry": "Expiry too near", "wrong_item": "Wrong item",
                 "short": "Short (not all arrived)", "other": "Other"}


def hold(db: Session, receipt: Receipt, held: list[tuple[Product, Location, object, int]]) -> QualityCheck:
    """The receipt's goods wait for their check: on hold where they were put, and listed on its quality check."""
    check = QualityCheck(number=next_number(db, "QC"), receipt_id=receipt.id, warehouse_id=receipt.warehouse_id)
    for i, (product, location, batch, quantity) in enumerate(held):
        row = balance(db, product.id, location, batch.id if batch else None)
        row.on_hold = (row.on_hold or 0) + quantity
        check.lines.append(QualityCheckLine(position=i, product_id=product.id, location_id=location.id, batch_id=batch.id if batch else None, quantity=quantity))
    db.add(check)
    db.flush()
    return check


def done(db: Session, me: User, check: QualityCheck, results: dict[str, dict], notes: str | None) -> None:
    """Each line's result: passed released for use, failed put aside as damaged with why. Once."""
    if check.status != "waiting":
        raise conflict(f"{check.number} is already done.")
    ref = Ref("quality_check", check.id, check.number)
    for i, line in enumerate(check.lines):
        r = results.get(line.id)
        if r is None:
            raise field_error(f"lines.{i}.passed", f"Say how many of {line.product.name} passed.")
        passed, failed = int(r.get("passed") or 0), int(r.get("failed") or 0)
        if passed < 0 or failed < 0 or passed + failed != line.quantity:
            raise field_error(f"lines.{i}.passed", f"Passed and failed must add up to the {line.quantity} received.")
        reason = r.get("reason")
        if failed and reason not in QUALITY_REASONS:
            raise field_error(f"lines.{i}.reason", "Say why they failed.")
        row = balance(db, line.product_id, line.location, line.batch_id)
        if (row.on_hold or 0) < line.quantity:
            raise conflict(f"{line.product.name} isn't on hold any more: someone moved it. Count it instead.")
        row.on_hold -= line.quantity
        line.passed, line.failed = passed, failed
        line.reason = reason if failed else None
        line.note = (r.get("note") or "").strip()[:300] or None
        if failed:
            db.flush()
            post(db, me, kind="damage", product=line.product, quantity=-failed, ref=ref, location=line.location, batch=line.batch,
                 note=f"Failed its quality check: {REASON_LABELS.get(reason, reason)}" + (f" ({line.note})" if line.note else ""))
    check.status, check.checked_by_id, check.checked_at = "done", me.id, datetime.now(UTC)
    check.notes = (notes or "").strip() or None


def check_out(check: QualityCheck, *, full: bool = True) -> dict:
    lines = check.lines
    out = {
        "id": check.id, "number": check.number, "status": check.status,
        "receipt": {"id": check.receipt.id, "number": check.receipt.number},
        "supplier": {"id": check.receipt.supplier.id, "name": check.receipt.supplier.name} if check.receipt.supplier else None,
        "warehouse": {"id": check.warehouse.id, "code": check.warehouse.code, "name": check.warehouse.name},
        "receivedAt": check.receipt.received_at.isoformat() if check.receipt.received_at else None,
        "checkedBy": {"id": check.checked_by.id, "name": check.checked_by.full_name} if check.checked_by else None,
        "checkedAt": check.checked_at.isoformat() if check.checked_at else None,
        "units": sum(line.quantity for line in lines),
        "passed": sum(line.passed or 0 for line in lines),
        "failed": sum(line.failed or 0 for line in lines),
        "createdAt": check.created_at.isoformat() if check.created_at else None,
    }
    if full:
        out["notes"] = check.notes
        out["lines"] = [{
            "id": line.id, "product": product_ref(line.product),
            "location": {"id": line.location.id, "code": line.location.code, "name": line.location.name},
            "batch": {"id": line.batch.id, "batchNo": line.batch.batch_no, "expiresOn": line.batch.expires_on.isoformat() if line.batch.expires_on else None} if line.batch else None,
            "quantity": line.quantity, "passed": line.passed, "failed": line.failed, "reason": line.reason,
            "reasonLabel": REASON_LABELS.get(line.reason or "", None), "note": line.note,
        } for line in lines]
        out["reasons"] = [{"value": k, "label": v} for k, v in REASON_LABELS.items()]
    return out
