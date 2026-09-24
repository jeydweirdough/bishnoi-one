"""Stock: what's on hand per medicine, what's running low, deliveries taken
in, corrections, and every movement behind the numbers.

Receiving makes a batch per lot (or tops up the same lot of the same
medicine). An adjustment corrects one batch by a counted difference, with a
reason: a recount, damage, expired stock taken off the shelf.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, status
from pydantic import Field
from sqlalchemy import func, or_, select

from app.access import Can
from app.api import Api, conflict, day, field_error, get_or_404, iso, next_number, person_out, today
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import MOVEMENT_KINDS, Batch, Medicine, Receiving, StockMovement, Supplier
from app.stock import move, on_hand, sellable

router = APIRouter(prefix="/stock", tags=["stock"])


class ReceiveLine(Api):
    medicine_id: str = Field(max_length=36)
    lot_no: str = Field(min_length=1, max_length=60)
    expires_on: date
    manufactured_on: date | None = None
    quantity: int = Field(ge=1, le=10_000_000)
    cost_centavos: int = Field(0, ge=0, le=100_000_000)


class ReceivingIn(Api):
    supplier_id: str | None = Field(None, max_length=36)
    reference: str | None = Field(None, max_length=80)
    received_on: date
    notes: str | None = Field(None, max_length=2000)
    lines: list[ReceiveLine] = Field(min_length=1, max_length=200)


class AdjustmentIn(Api):
    batch_id: str = Field(max_length=36)
    # The difference counted: -3 when three are missing or damaged.
    quantity: int = Field(ge=-10_000_000, le=10_000_000)
    reason: str = Field(min_length=1, max_length=300)


@router.get("")
def current(
    _: Can("stock.view"),
    db: DB,
    settings: SettingsDep,
    view: Literal["current", "low"] = "current",
    q: str | None = Query(None, max_length=80),
) -> dict:
    """Per medicine: on hand, how much of it can be given out, its value at
    cost, and the nearest expiry. Low: at or below the reorder level."""
    on = today(settings)
    query = select(Medicine).where(Medicine.status != "discontinued").order_by(func.lower(Medicine.generic_name))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Medicine.generic_name).like(like), func.lower(Medicine.code).like(like)))
    medicines = list(db.scalars(query).unique())
    ids = [m.id for m in medicines]
    total, usable = on_hand(db, ids), sellable(db, ids, on)
    value = dict(db.execute(select(Batch.medicine_id, func.sum(Batch.qty_on_hand * Batch.cost_centavos)).group_by(Batch.medicine_id)).all())
    nearest = dict(
        db.execute(
            select(Batch.medicine_id, func.min(Batch.expires_on))
            .where(Batch.qty_on_hand > 0, Batch.status == "available", Batch.expires_on > on)
            .group_by(Batch.medicine_id)
        ).all()
    )
    rows = []
    for m in medicines:
        can_give = usable.get(m.id, 0)
        low = can_give <= m.reorder_level
        if view == "low" and not (low and m.status == "active"):
            continue
        rows.append(
            {
                "medicine": {"id": m.id, "label": m.label, "code": m.code, "unit": m.unit, "status": m.status, "rxClass": m.rx_class},
                "onHand": total.get(m.id, 0),
                "available": can_give,
                "reorderLevel": m.reorder_level,
                "low": low,
                "valueCentavos": int(value.get(m.id) or 0),
                "nearestExpiry": day(nearest.get(m.id)),
            }
        )
    return {"items": rows, "valueCentavos": sum(r["valueCentavos"] for r in rows)}


def receiving_out(r: Receiving, db: DB, with_lines: bool = False) -> dict:
    batches = list(db.scalars(select(Batch).where(Batch.receiving_id == r.id))) if with_lines else []
    moved = db.execute(
        select(func.count(), func.coalesce(func.sum(StockMovement.quantity), 0)).where(StockMovement.kind == "receive", StockMovement.reference == r.number)
    ).one()
    out = {
        "id": r.id,
        "number": r.number,
        "supplier": {"id": r.supplier.id, "name": r.supplier.name} if r.supplier else None,
        "reference": r.reference,
        "receivedOn": day(r.received_on),
        "notes": r.notes,
        "receivedBy": person_out(r.received_by),
        "createdAt": iso(r.created_at),
        "lineCount": moved[0],
        "units": int(moved[1]),
    }
    if with_lines:
        lines = db.scalars(select(StockMovement).where(StockMovement.kind == "receive", StockMovement.reference == r.number))
        out["lines"] = [
            {"medicine": mv.medicine.label, "medicineId": mv.medicine_id, "lotNo": mv.batch.lot_no, "expiresOn": day(mv.batch.expires_on),
             "quantity": mv.quantity, "costCentavos": mv.batch.cost_centavos, "batchId": mv.batch_id}
            for mv in lines
        ]
        out["batchCount"] = len(batches)
    return out


@router.get("/receivings")
def list_receivings(_: Can("stock.view"), db: DB, limit: int = Query(200, ge=1, le=500)) -> list[dict]:
    return [receiving_out(r, db) for r in db.scalars(select(Receiving).order_by(Receiving.created_at.desc()).limit(limit))]


@router.get("/receivings/{receiving_id}")
def read_receiving(_: Can("stock.view"), db: DB, receiving_id: str) -> dict:
    return receiving_out(get_or_404(db, Receiving, receiving_id, "delivery"), db, with_lines=True)


@router.post("/receivings", status_code=status.HTTP_201_CREATED)
def receive(access: Can("stock.receive"), db: DB, settings: SettingsDep, body: ReceivingIn) -> dict:
    on = today(settings)
    if body.received_on > on:
        raise field_error("receivedOn", "A delivery can't be received in the future.")
    if body.supplier_id is not None and db.get(Supplier, body.supplier_id) is None:
        raise field_error("supplierId", "Pick a supplier from the list.")
    r = Receiving(
        number=next_number(db, "RC", settings),
        supplier_id=body.supplier_id,
        reference=body.reference,
        received_on=body.received_on,
        notes=body.notes,
        received_by_id=access.user.id,
    )
    db.add(r)
    db.flush()
    for n, line in enumerate(body.lines):
        m = db.get(Medicine, line.medicine_id)
        if m is None:
            raise field_error(f"lines.{n}.medicineId", "Pick a medicine from the catalogue.")
        if line.expires_on <= on:
            raise field_error(f"lines.{n}.expiresOn", "This lot has already expired. Don't take it in.")
        if line.manufactured_on is not None and line.manufactured_on >= line.expires_on:
            raise field_error(f"lines.{n}.manufacturedOn", "It must be made before it expires.")
        batch = db.scalar(select(Batch).where(Batch.medicine_id == m.id, Batch.lot_no == line.lot_no))
        if batch is None:
            batch = Batch(
                medicine_id=m.id, lot_no=line.lot_no, supplier_id=body.supplier_id, receiving_id=r.id,
                manufactured_on=line.manufactured_on, expires_on=line.expires_on, cost_centavos=line.cost_centavos,
                qty_received=0, qty_on_hand=0,
            )
            db.add(batch)
            db.flush()
        elif batch.expires_on != line.expires_on:
            raise field_error(f"lines.{n}.expiresOn", f"Lot {line.lot_no} is on record expiring {batch.expires_on.isoformat()}. Check the lot number.")
        elif batch.status == "recalled":
            raise conflict(f"Lot {line.lot_no} of {m.label} has been recalled. Don't take it in.")
        batch.qty_received += line.quantity
        move(db, batch, line.quantity, "receive", by=access.user, reference=r.number)
    audit(db, access.user, "stock.received", target=f"{r.number}{f' ({r.reference})' if r.reference else ''}", target_type="receiving", target_id=r.id)
    db.commit()
    return receiving_out(r, db, with_lines=True)


@router.post("/adjustments", status_code=status.HTTP_201_CREATED)
def adjust(access: Can("stock.adjust"), db: DB, body: AdjustmentIn) -> dict:
    if body.quantity == 0:
        raise field_error("quantity", "Enter the difference counted, e.g. -3 for three missing.")
    b = get_or_404(db, Batch, body.batch_id, "batch")
    if body.quantity > 0 and b.status == "recalled":
        raise conflict(f"Lot {b.lot_no} has been recalled; nothing goes back into it.")
    mv = move(db, b, body.quantity, "adjust", by=access.user, reason=body.reason)
    audit(db, access.user, "stock.adjusted", target=f"{b.medicine.code} lot {b.lot_no} {body.quantity:+d}", target_type="batch", target_id=b.id)
    db.commit()
    return movement_out(mv)


def movement_out(mv: StockMovement) -> dict:
    return {
        "id": mv.id,
        "at": iso(mv.at),
        "kind": mv.kind,
        "medicine": {"id": mv.medicine.id, "label": mv.medicine.label, "unit": mv.medicine.unit},
        "batch": {"id": mv.batch.id, "lotNo": mv.batch.lot_no},
        "quantity": mv.quantity,
        "balance": mv.balance,
        "reason": mv.reason,
        "reference": mv.reference,
        "by": person_out(mv.by),
    }


@router.get("/movements")
def movements(
    _: Can("stock.view"),
    db: DB,
    kind: Literal[MOVEMENT_KINDS] | None = None,  # type: ignore[valid-type]
    medicine_id: str | None = Query(None, alias="medicineId", max_length=36),
    batch_id: str | None = Query(None, alias="batchId", max_length=36),
    before: int | None = Query(None, ge=1, description="the last id of the page before"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Newest first. Pass the last one's id as `before` for the next page."""
    q = select(StockMovement).order_by(StockMovement.id.desc()).limit(limit + 1)
    if kind:
        q = q.where(StockMovement.kind == kind)
    if medicine_id:
        q = q.where(StockMovement.medicine_id == medicine_id)
    if batch_id:
        q = q.where(StockMovement.batch_id == batch_id)
    if before:
        q = q.where(StockMovement.id < before)
    rows = list(db.scalars(q).unique())
    return {"items": [movement_out(mv) for mv in rows[:limit]], "more": len(rows) > limit}
