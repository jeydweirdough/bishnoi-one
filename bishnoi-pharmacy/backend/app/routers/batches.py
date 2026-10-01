"""Batches and expiry: every lot on record, what is about to expire, what
already has, and what is held back (quarantined or recalled).

A quarantined batch is held while it's looked into, and can be released. A
recalled one is withdrawn for good. Neither can be dispensed or sold; what's
left of them, and of expired batches, leaves the shelf by a stock adjustment.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import Field
from sqlalchemy import func, or_, select

from app.access import Can
from app.api import Api, conflict, day, field_error, get_or_404, iso, today
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import Batch, Medicine

router = APIRouter(prefix="/batches", tags=["batches"])


class StatusIn(Api):
    status: Literal["available", "quarantined", "recalled"]
    reason: str | None = Field(None, max_length=300)


def batch_out(b: Batch, on) -> dict:
    days = (b.expires_on - on).days
    return {
        "id": b.id,
        "medicine": {"id": b.medicine.id, "label": b.medicine.label, "code": b.medicine.code, "unit": b.medicine.unit},
        "lotNo": b.lot_no,
        "supplier": {"id": b.supplier.id, "name": b.supplier.name} if b.supplier else None,
        "receivingId": b.receiving_id,
        "manufacturedOn": day(b.manufactured_on),
        "expiresOn": day(b.expires_on),
        "daysToExpiry": days,
        "expired": days <= 0,
        "costCentavos": b.cost_centavos,
        "qtyReceived": b.qty_received,
        "qtyOnHand": b.qty_on_hand,
        "valueCentavos": b.cost_centavos * b.qty_on_hand,
        "status": b.status,
        "statusReason": b.status_reason,
        "statusChangedAt": iso(b.status_changed_at),
    }


@router.get("")
def list_batches(
    _: Can("batches.view"),
    db: DB,
    settings: SettingsDep,
    view: Literal["all", "expiring", "expired", "held"] = "all",
    q: str | None = Query(None, max_length=80),
    medicine_id: str | None = Query(None, alias="medicineId", max_length=36),
    within: int | None = Query(None, ge=1, le=3650, description="expiring: days ahead (default EXPIRY_WARNING_DAYS)"),
) -> dict:
    on = today(settings)
    query = select(Batch).join(Medicine, Batch.medicine_id == Medicine.id)
    if view == "expiring":
        days = within or settings.expiry_warning_days
        query = query.where(Batch.expires_on > on, Batch.expires_on <= on + timedelta(days=days), Batch.qty_on_hand > 0,
                            Batch.status != "recalled").order_by(Batch.expires_on)
    elif view == "expired":
        # Still on the shelf, so still to be taken off it.
        query = query.where(Batch.expires_on <= on, Batch.qty_on_hand > 0).order_by(Batch.expires_on)
    elif view == "held":
        query = query.where(Batch.status.in_(("quarantined", "recalled"))).order_by(Batch.status_changed_at.desc())
    else:
        query = query.order_by(func.lower(Medicine.generic_name), Batch.expires_on)
    if medicine_id:
        query = query.where(Batch.medicine_id == medicine_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Batch.lot_no).like(like), func.lower(Medicine.generic_name).like(like), func.lower(Medicine.code).like(like)))
    batches = list(db.scalars(query.limit(500)).unique())
    return {
        "items": [batch_out(b, on) for b in batches],
        "valueCentavos": sum(b.cost_centavos * b.qty_on_hand for b in batches),
        "withinDays": within or settings.expiry_warning_days,
    }


@router.get("/{batch_id}")
def read_batch(_: Can("batches.view"), db: DB, settings: SettingsDep, batch_id: str) -> dict:
    return batch_out(get_or_404(db, Batch, batch_id, "batch"), today(settings))


@router.post("/{batch_id}/status")
def set_status(access: Can("batches.manage"), db: DB, settings: SettingsDep, batch_id: str, body: StatusIn) -> dict:
    """Quarantines, recalls or releases a batch."""
    b = get_or_404(db, Batch, batch_id, "batch")
    if b.status == body.status:
        return batch_out(b, today(settings))
    if b.status == "recalled":
        raise conflict(f"Lot {b.lot_no} has been recalled. A recall is final.")
    if body.status != "available" and not body.reason:
        raise field_error("reason", "Say why, so whoever sees it held knows what to do.")
    b.status = body.status
    b.status_reason = body.reason if body.status != "available" else None
    b.status_changed_at = datetime.now(UTC)
    action = {"available": "batch.released", "quarantined": "batch.quarantined", "recalled": "batch.recalled"}[body.status]
    audit(db, access.user, action, target=f"{b.medicine.code} lot {b.lot_no}", target_type="batch", target_id=b.id, fields=["status"])
    db.commit()
    return batch_out(b, today(settings))
