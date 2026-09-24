"""Sales: every transaction, whether over the counter or made by a dispensing,
and what's brought back on them.

At the counter only over-the-counter medicines are sold, taken from the
batches that expire soonest. A prescription medicine goes out only through a
verified prescription (routers/dispensing.py), which records its sale here.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Query, status
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access import Can
from app.api import Api, conflict, day_start, field_error, get_or_404, iso, next_number, person_out, today
from app.audit import audit
from app.config import Settings
from app.deps import DB, SettingsDep
from app.models import Batch, Dispensing, Medicine, Patient, Sale, SaleLine, SaleReturn, User
from app.routers.patients import patient_brief
from app.stock import allocate, move, take

router = APIRouter(prefix="/sales", tags=["sales"])

PaymentMethod = Literal["cash", "card", "ewallet", "other"]


@dataclass
class SaleItem:
    medicine: Medicine
    batch: Batch
    quantity: int


def record_sale(
    db: Session,
    settings: Settings,
    by: User,
    items: list[SaleItem],
    *,
    source: str,
    patient_id: str | None,
    payment_method: str,
    discount_centavos: int,
    notes: str | None,
) -> Sale:
    """Writes the sale for stock already taken off its batches, at each medicine's price."""
    lines = [
        SaleLine(
            medicine_id=i.medicine.id,
            batch_id=i.batch.id,
            quantity=i.quantity,
            unit_price_centavos=i.medicine.price_centavos,
            line_total_centavos=i.medicine.price_centavos * i.quantity,
        )
        for i in items
    ]
    subtotal = sum(line.line_total_centavos for line in lines)
    if discount_centavos > subtotal:
        raise field_error("discountCentavos", "The discount can't be more than the sale.")
    sale = Sale(
        number=next_number(db, "SI", settings),
        source=source,
        patient_id=patient_id,
        sold_by_id=by.id,
        subtotal_centavos=subtotal,
        discount_centavos=discount_centavos,
        total_centavos=subtotal - discount_centavos,
        payment_method=payment_method,
        notes=notes,
        lines=lines,
    )
    db.add(sale)
    db.flush()
    return sale


class CounterLine(Api):
    medicine_id: str = Field(max_length=36)
    quantity: int = Field(ge=1, le=100_000)


class CounterSaleIn(Api):
    patient_id: str | None = Field(None, max_length=36)
    lines: list[CounterLine] = Field(min_length=1, max_length=100)
    payment_method: PaymentMethod = "cash"
    discount_centavos: int = Field(0, ge=0)
    notes: str | None = Field(None, max_length=2000)


class ReturnLine(Api):
    sale_line_id: str = Field(max_length=36)
    quantity: int = Field(ge=1, le=100_000)


class ReturnIn(Api):
    lines: list[ReturnLine] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=300)
    restock: bool = False
    refund_centavos: int = Field(0, ge=0)
    refund_method: PaymentMethod | None = None


def sale_out(s: Sale, dispensing: Dispensing | None = None) -> dict:
    return {
        "id": s.id,
        "number": s.number,
        "source": s.source,
        "patient": patient_brief(s.patient),
        "soldBy": person_out(s.sold_by),
        "soldAt": iso(s.sold_at),
        "subtotalCentavos": s.subtotal_centavos,
        "discountCentavos": s.discount_centavos,
        "totalCentavos": s.total_centavos,
        "refundedCentavos": s.refunded_centavos,
        "paymentMethod": s.payment_method,
        "notes": s.notes,
        "dispensing": {"id": dispensing.id, "number": dispensing.number, "prescriptionId": dispensing.prescription_id} if dispensing else None,
        "lines": [
            {
                "id": line.id,
                "medicine": line.medicine.label,
                "medicineId": line.medicine_id,
                "unit": line.medicine.unit,
                "lotNo": line.batch.lot_no,
                "quantity": line.quantity,
                "qtyReturned": line.qty_returned,
                "unitPriceCentavos": line.unit_price_centavos,
                "lineTotalCentavos": line.line_total_centavos,
            }
            for line in s.lines
        ],
    }


def return_out(r: SaleReturn) -> dict:
    return {
        "id": r.id,
        "number": r.number,
        "sale": {"id": r.sale.id, "number": r.sale.number},
        "patient": patient_brief(r.sale.patient),
        "reason": r.reason,
        "restocked": r.restocked,
        "refundCentavos": r.refund_centavos,
        "refundMethod": r.refund_method,
        "by": person_out(r.by),
        "at": iso(r.at),
        "units": sum(line["quantity"] for line in r.lines or []),
    }


@router.get("")
def list_sales(
    _: Can("sales.view"),
    db: DB,
    settings: SettingsDep,
    view: Literal["today", "history"] = "today",
    source: Literal["counter", "dispensing"] | None = None,
    q: str | None = Query(None, max_length=80),
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
    limit: int = Query(300, ge=1, le=1000),
) -> dict:
    query = select(Sale).outerjoin(Patient, Sale.patient_id == Patient.id).order_by(Sale.sold_at.desc()).limit(limit)
    if view == "today":
        since = until = today(settings)
    if since:
        query = query.where(Sale.sold_at >= day_start(since, settings))
    if until:
        query = query.where(Sale.sold_at < day_start(until + timedelta(days=1), settings))
    if source:
        query = query.where(Sale.source == source)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Sale.number).like(like), func.lower(Patient.full_name).like(like)))
    sales = list(db.scalars(query).unique())
    return {
        "items": [sale_out(s) for s in sales],
        "count": len(sales),
        "totalCentavos": sum(s.total_centavos for s in sales),
        "refundedCentavos": sum(s.refunded_centavos for s in sales),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def counter_sale(access: Can("sales.create"), db: DB, settings: SettingsDep, body: CounterSaleIn) -> dict:
    if body.patient_id is not None:
        get_or_404(db, Patient, body.patient_id, "customer")
    on = today(settings)
    wanted: dict[str, int] = {}
    for n, line in enumerate(body.lines):
        m = db.get(Medicine, line.medicine_id)
        if m is None:
            raise field_error(f"lines.{n}.medicineId", "Pick a medicine from the catalogue.")
        if m.rx_class != "otc":
            raise conflict(f"{m.label} needs a verified prescription. Take the prescription in and dispense it instead.")
        if m.status == "inactive":
            raise conflict(f"{m.label} is marked inactive in the catalogue.")
        wanted[m.id] = wanted.get(m.id, 0) + line.quantity
    items: list[SaleItem] = []
    for medicine_id, qty in wanted.items():
        m = db.get(Medicine, medicine_id)
        for batch, n in allocate(db, m, qty, on):
            items.append(SaleItem(medicine=m, batch=batch, quantity=n))
    sale = record_sale(
        db, settings, access.user, items, source="counter", patient_id=body.patient_id,
        payment_method=body.payment_method, discount_centavos=body.discount_centavos, notes=body.notes,
    )
    for item in items:
        take(db, item.batch, item.quantity, "sale", on=on, by=access.user, reference=sale.number)
    audit(db, access.user, "sale.made", target=f"{sale.number} at the counter", target_type="sale", target_id=sale.id)
    db.commit()
    db.refresh(sale)
    return sale_out(sale)


@router.get("/returns")
def list_returns(
    _: Can("sales.view"),
    db: DB,
    view: Literal["returns", "refunds"] = "returns",
    limit: int = Query(300, ge=1, le=1000),
) -> list[dict]:
    query = select(SaleReturn).order_by(SaleReturn.at.desc()).limit(limit)
    if view == "refunds":
        query = query.where(SaleReturn.refund_centavos > 0)
    return [return_out(r) for r in db.scalars(query)]


@router.get("/{sale_id}")
def read_sale(_: Can("sales.view"), db: DB, sale_id: str) -> dict:
    s = get_or_404(db, Sale, sale_id, "sale")
    dispensing = db.scalar(select(Dispensing).where(Dispensing.sale_id == s.id))
    returns = db.scalars(select(SaleReturn).where(SaleReturn.sale_id == s.id).order_by(SaleReturn.at))
    return {**sale_out(s, dispensing), "returns": [return_out(r) for r in returns]}


@router.post("/{sale_id}/returns", status_code=status.HTTP_201_CREATED)
def make_return(access: Can("sales.refund"), db: DB, settings: SettingsDep, sale_id: str, body: ReturnIn) -> dict:
    """Takes medicines back on a sale. Back on the shelf only when `restock`
    (sealed and undamaged); a refund is optional, as for an exchange."""
    s = get_or_404(db, Sale, sale_id, "sale")
    lines = {line.id: line for line in s.lines}
    value = 0
    for n, ret in enumerate(body.lines):
        line = lines.get(ret.sale_line_id)
        if line is None:
            raise field_error(f"lines.{n}.saleLineId", "That line isn't on this sale.")
        left = line.quantity - line.qty_returned
        if ret.quantity > left:
            raise conflict(f"{line.medicine.label}: {left} can still be returned on this sale, {ret.quantity} asked.")
        value += ret.quantity * line.unit_price_centavos
    if body.refund_centavos > min(value, s.total_centavos - s.refunded_centavos):
        raise field_error("refundCentavos", "The refund can't be more than what's being returned, or than what's left paid on the sale.")
    if body.refund_centavos and body.refund_method is None:
        raise field_error("refundMethod", "Say how the money is paid back.")

    r = SaleReturn(
        number=next_number(db, "RT", settings),
        sale_id=s.id,
        reason=body.reason,
        restocked=body.restock,
        refund_centavos=body.refund_centavos,
        refund_method=body.refund_method if body.refund_centavos else None,
        by_id=access.user.id,
        lines=[{"saleLineId": ret.sale_line_id, "quantity": ret.quantity} for ret in body.lines],
    )
    db.add(r)
    for ret in body.lines:
        line = lines[ret.sale_line_id]
        line.qty_returned += ret.quantity
        if body.restock:
            if line.batch.status == "recalled":
                raise conflict(f"Lot {line.batch.lot_no} has been recalled, so it can't go back on the shelf.")
            move(db, line.batch, ret.quantity, "return", by=access.user, reference=r.number, reason=body.reason)
    s.refunded_centavos += body.refund_centavos
    audit(db, access.user, "sale.refunded" if body.refund_centavos else "sale.returned", target=f"{r.number} on {s.number}",
          target_type="return", target_id=r.id)
    db.commit()
    return read_sale(access, db, s.id)
