"""Dispensing: handing over what a verified prescription lists.

    verified -> dispensing queue -> pharmacist picks an eligible batch per medicine
             -> medicine dispensed -> sale recorded

Only a verified prescription reaches the queue, and only an eligible batch
(available, unexpired, with stock; see app/stock.py) can be picked. What
isn't in stock can be left for later: the prescription is then partially
dispensed, and waits in its own list until the rest is handed over.
"""

from typing import Literal

from fastapi import APIRouter, Query, status
from pydantic import Field
from sqlalchemy import func, or_, select

from app.access import Can
from app.api import Api, conflict, day, field_error, get_or_404, iso, next_number, person_out, today
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import Batch, Dispensing, DispensingLine, Patient, Prescription
from app.routers.patients import patient_brief
from app.routers.prescriptions import dispense_state, summary_out
from app.routers.sales import PaymentMethod, SaleItem, record_sale
from app.stock import eligible_batches, sellable, take

router = APIRouter(prefix="/dispensing", tags=["dispensing"])


class LineIn(Api):
    item_id: str = Field(max_length=36)
    batch_id: str = Field(max_length=36)
    quantity: int = Field(ge=1, le=100_000)


class DispenseIn(Api):
    prescription_id: str = Field(max_length=36)
    lines: list[LineIn] = Field(min_length=1, max_length=100)
    payment_method: PaymentMethod = "cash"
    discount_centavos: int = Field(0, ge=0)
    notes: str | None = Field(None, max_length=2000)


def dispensing_out(d: Dispensing) -> dict:
    return {
        "id": d.id,
        "number": d.number,
        "prescription": {"id": d.prescription.id, "number": d.prescription.number},
        "patient": patient_brief(d.patient),
        "dispensedBy": person_out(d.dispensed_by),
        "dispensedAt": iso(d.dispensed_at),
        "notes": d.notes,
        "saleId": d.sale_id,
        "lines": [
            {"medicine": line.medicine.label, "medicineId": line.medicine_id, "unit": line.medicine.unit,
             "lotNo": line.batch.lot_no, "expiresOn": day(line.batch.expires_on), "quantity": line.quantity}
            for line in d.lines
        ],
        "units": sum(line.quantity for line in d.lines),
    }


@router.get("/queue")
def queue(
    _: Can("dispensing.view"),
    db: DB,
    settings: SettingsDep,
    view: Literal["queue", "partial", "dispensed"] = "queue",
    q: str | None = Query(None, max_length=80),
) -> list[dict]:
    """Verified prescriptions by how much of them has been handed over:
    none yet (the queue), some (partial), or all (dispensed)."""
    query = select(Prescription).join(Patient, Prescription.patient_id == Patient.id).where(Prescription.status == "verified")
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Prescription.number).like(like), func.lower(Patient.full_name).like(like)))
    wanted = {"queue": "none", "partial": "partial", "dispensed": "full"}[view]
    # First verified, first served.
    rows = [rx for rx in db.scalars(query.order_by(Prescription.checked_at)).unique() if dispense_state(rx) == wanted]
    if view == "dispensed":
        rows.reverse()
    ids = list({i.medicine_id for rx in rows for i in rx.items if i.medicine_id})
    available = sellable(db, ids, today(settings))
    return [
        {
            **summary_out(rx),
            # Whether everything still owed could be handed over right now.
            "ready": all(available.get(i.medicine_id, 0) >= i.remaining for i in rx.items if i.remaining),
        }
        for rx in rows[:300]
    ]


@router.get("/prepare/{prescription_id}")
def prepare(_: Can("dispensing.view"), db: DB, settings: SettingsDep, prescription_id: str) -> dict:
    """What New Dispensing shows: each medicine still owed, and the batches it can come from."""
    rx = get_or_404(db, Prescription, prescription_id, "prescription")
    if rx.status != "verified":
        raise conflict(f"{rx.number} isn't verified, so nothing can be dispensed on it yet. Check it first.")
    on = today(settings)
    return {
        **summary_out(rx),
        "items": [
            {
                "id": item.id,
                "writtenAs": item.written_as,
                "directions": item.directions,
                "quantity": item.quantity,
                "qtyDispensed": item.qty_dispensed,
                "remaining": item.remaining,
                "medicine": {"id": item.medicine.id, "label": item.medicine.label, "unit": item.medicine.unit,
                             "priceCentavos": item.medicine.price_centavos},
                "batches": [
                    {"id": b.id, "lotNo": b.lot_no, "expiresOn": day(b.expires_on), "qtyOnHand": b.qty_on_hand}
                    for b in eligible_batches(db, item.medicine_id, on)
                ],
            }
            for item in rx.items
            if item.medicine is not None
        ],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def dispense(access: Can("dispensing.create"), db: DB, settings: SettingsDep, body: DispenseIn) -> dict:
    rx = get_or_404(db, Prescription, body.prescription_id, "prescription")
    if rx.status != "verified":
        raise conflict(f"{rx.number} isn't verified, so nothing can be dispensed on it. Check it first.")
    on = today(settings)
    items = {i.id: i for i in rx.items}
    asked: dict[str, int] = {}
    for n, line in enumerate(body.lines):
        item = items.get(line.item_id)
        if item is None:
            raise field_error(f"lines.{n}.itemId", "That medicine isn't on this prescription.")
        batch = db.get(Batch, line.batch_id)
        if batch is None or batch.medicine_id != item.medicine_id:
            raise field_error(f"lines.{n}.batchId", f"Pick a batch of {item.medicine.label if item.medicine else item.written_as}.")
        asked[item.id] = asked.get(item.id, 0) + line.quantity
    for item_id, qty in asked.items():
        item = items[item_id]
        if qty > item.remaining:
            raise conflict(f"{item.medicine.label}: {item.remaining} still owed on this prescription, {qty} picked.")

    d = Dispensing(
        number=next_number(db, "DS", settings),
        prescription_id=rx.id,
        patient_id=rx.patient_id,
        dispensed_by_id=access.user.id,
        notes=body.notes,
    )
    db.add(d)
    sale_items: list[SaleItem] = []
    for line in body.lines:
        item = items[line.item_id]
        batch = db.get(Batch, line.batch_id)
        take(db, batch, line.quantity, "dispense", on=on, by=access.user, reference=d.number)
        item.qty_dispensed += line.quantity
        d.lines.append(DispensingLine(item_id=item.id, medicine_id=item.medicine_id, batch_id=batch.id, quantity=line.quantity))
        sale_items.append(SaleItem(medicine=item.medicine, batch=batch, quantity=line.quantity))
    db.flush()
    sale = record_sale(
        db, settings, access.user, sale_items, source="dispensing", patient_id=rx.patient_id,
        payment_method=body.payment_method, discount_centavos=body.discount_centavos, notes=f"{d.number} on {rx.number}",
    )
    d.sale_id = sale.id
    state = dispense_state(rx)
    audit(db, access.user, "prescription.dispensed" if state == "full" else "prescription.partly_dispensed",
          target=f"{d.number} on {rx.number}", target_type="dispensing", target_id=d.id)
    db.commit()
    db.refresh(d)
    return dispensing_out(d)


@router.get("")
def history(
    _: Can("dispensing.view"),
    db: DB,
    q: str | None = Query(None, max_length=80),
    limit: int = Query(200, ge=1, le=500),
) -> list[dict]:
    query = select(Dispensing).join(Patient, Dispensing.patient_id == Patient.id).order_by(Dispensing.dispensed_at.desc()).limit(limit)
    if q:
        like = f"%{q.lower()}%"
        query = query.join(Prescription, Dispensing.prescription_id == Prescription.id).where(
            or_(func.lower(Dispensing.number).like(like), func.lower(Prescription.number).like(like), func.lower(Patient.full_name).like(like))
        )
    return [dispensing_out(d) for d in db.scalars(query).unique()]


@router.get("/{dispensing_id}")
def read(_: Can("dispensing.view"), db: DB, dispensing_id: str) -> dict:
    return dispensing_out(get_or_404(db, Dispensing, dispensing_id, "dispensing record"))
