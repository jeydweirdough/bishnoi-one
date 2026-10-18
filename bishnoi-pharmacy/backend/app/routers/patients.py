"""Patients and customers: who medicines go to, with their prescriptions and
what they've been given.

A patient has prescriptions dispensed to them; a customer buys over the
counter. They're one list with a kind, because a customer who comes back
with a prescription becomes a patient without being entered twice.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select

from app.access import Can
from app.api import Api, camel, changed, check_email, conflict, day, field_error, get_or_404, iso
from app.audit import audit
from app.deps import DB
from app.models import Dispensing, Patient, Prescription, Sale, SaleLine

router = APIRouter(prefix="/patients", tags=["patients"])

Kind = Literal["patient", "customer"]


def not_born_yet(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("A birth date can't be in the future.")
    return value


class PatientIn(Api):
    kind: Kind = "patient"
    full_name: str = Field(min_length=1, max_length=160)
    birth_date: date | None = None
    sex: Literal["female", "male", "other"] | None = None
    phone: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=254)
    address: str | None = Field(None, max_length=300)
    allergies: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=4000)

    _email = field_validator("email")(check_email)
    _born = field_validator("birth_date")(not_born_yet)


class PatientPatch(Api):
    kind: Kind | None = None
    full_name: str | None = Field(None, min_length=1, max_length=160)
    birth_date: date | None = None
    sex: Literal["female", "male", "other"] | None = None
    phone: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=254)
    address: str | None = Field(None, max_length=300)
    allergies: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=4000)

    _email = field_validator("email")(check_email)
    _born = field_validator("birth_date")(not_born_yet)


def patient_out(p: Patient) -> dict:
    return {
        "id": p.id,
        "no": p.no,
        "kind": p.kind,
        "fullName": p.full_name,
        "birthDate": day(p.birth_date),
        "sex": p.sex,
        "phone": p.phone,
        "email": p.email,
        "address": p.address,
        "allergies": p.allergies,
        "notes": p.notes,
        "createdAt": iso(p.created_at),
        "updatedAt": iso(p.updated_at),
    }


def patient_brief(p: Patient | None) -> dict | None:
    if p is None:
        return None
    return {"id": p.id, "fullName": p.full_name, "birthDate": day(p.birth_date), "allergies": p.allergies, "kind": p.kind}


@router.get("")
def list_patients(
    _: Can("patients.view"),
    db: DB,
    q: str | None = Query(None, max_length=80),
    kind: Kind | Literal["all"] = "all",
    limit: int = Query(200, ge=1, le=500),
) -> list[dict]:
    query = select(Patient).order_by(func.lower(Patient.full_name)).limit(limit)
    if kind != "all":
        query = query.where(Patient.kind == kind)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Patient.full_name).like(like), Patient.phone.like(like), func.lower(Patient.email).like(like)))
    people = list(db.scalars(query))
    ids = [p.id for p in people]
    rx = dict(db.execute(select(Prescription.patient_id, func.count()).where(Prescription.patient_id.in_(ids)).group_by(Prescription.patient_id)).all()) if ids else {}
    last = dict(db.execute(select(Sale.patient_id, func.max(Sale.sold_at)).where(Sale.patient_id.in_(ids)).group_by(Sale.patient_id)).all()) if ids else {}
    return [{**patient_out(p), "prescriptionCount": rx.get(p.id, 0), "lastVisitAt": iso(last.get(p.id))} for p in people]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_patient(access: Can("patients.create"), db: DB, body: PatientIn) -> dict:
    p = Patient(**body.model_dump())
    db.add(p)
    db.flush()
    audit(db, access.user, f"{p.kind}.created", target=p.full_name, target_type=p.kind, target_id=p.id)
    db.commit()
    return patient_out(p)


@router.get("/{patient_id}")
def read_patient(_: Can("patients.view"), db: DB, patient_id: str) -> dict:
    p = get_or_404(db, Patient, patient_id, "patient")
    prescriptions = db.scalars(select(Prescription).where(Prescription.patient_id == p.id).order_by(Prescription.received_at.desc()))
    # What they've been given: every line they bought or had dispensed, newest first.
    lines = db.execute(
        select(SaleLine, Sale)
        .join(Sale, SaleLine.sale_id == Sale.id)
        .where(Sale.patient_id == p.id)
        .order_by(Sale.sold_at.desc())
        .limit(200)
    ).all()
    dispensings = dict(
        db.execute(select(Dispensing.sale_id, Dispensing.number).where(Dispensing.patient_id == p.id, Dispensing.sale_id.is_not(None))).all()
    )
    return {
        **patient_out(p),
        "prescriptions": [
            {
                "id": rx.id,
                "number": rx.number,
                "status": rx.status,
                "prescriberName": rx.prescriber_name,
                "prescribedOn": day(rx.prescribed_on),
                "receivedAt": iso(rx.received_at),
                "items": [{"writtenAs": i.written_as, "quantity": i.quantity, "qtyDispensed": i.qty_dispensed} for i in rx.items],
            }
            for rx in prescriptions
        ],
        "medications": [
            {
                "at": iso(sale.sold_at),
                "medicine": line.medicine.label,
                "medicineId": line.medicine_id,
                "rxClass": line.medicine.rx_class,
                "quantity": line.quantity - line.qty_returned,
                "unit": line.medicine.unit,
                "lotNo": line.batch.lot_no,
                "saleId": sale.id,
                "saleNumber": sale.number,
                "dispensingNumber": dispensings.get(sale.id),
            }
            for line, sale in lines
            if line.quantity > line.qty_returned
        ],
    }


@router.patch("/{patient_id}")
def update_patient(access: Can("patients.edit"), db: DB, patient_id: str, body: PatientPatch) -> dict:
    p = get_or_404(db, Patient, patient_id, "patient")
    wanted = changed(body)
    for key in ("kind", "full_name"):
        if key in wanted and wanted[key] is None:
            raise field_error(camel([key])[0], "This can't be empty.")
    fields = [k for k, v in wanted.items() if getattr(p, k) != v]
    for k in fields:
        setattr(p, k, wanted[k])
    if fields:
        audit(db, access.user, f"{p.kind}.updated", target=p.full_name, target_type=p.kind, target_id=p.id, fields=camel(fields))
        db.commit()
    return patient_out(p)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(access: Can("patients.delete"), db: DB, patient_id: str) -> Response:
    """Only someone with no prescriptions or sales: those are records the pharmacy must keep."""
    p = get_or_404(db, Patient, patient_id, "patient")
    if db.scalar(select(func.count()).select_from(Prescription).where(Prescription.patient_id == p.id)) or db.scalar(
        select(func.count()).select_from(Sale).where(Sale.patient_id == p.id)
    ):
        raise conflict(f"{p.full_name} has prescriptions or purchases on record, which the pharmacy must keep.")
    audit(db, access.user, f"{p.kind}.deleted", target=p.full_name, target_type=p.kind, target_id=p.id)
    db.delete(p)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
