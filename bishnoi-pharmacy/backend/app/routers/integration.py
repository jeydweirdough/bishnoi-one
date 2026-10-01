"""Orders other Bishnoi One apps send here for the pharmacist's check, and the
verdict they read back. Only for an app holding one of INTEGRATION_KEYS, sent
in the X-Bishnoi-Key header (the same way the CRM reads Inventory and asks
Finance).

    the app sends an order ──> it lands in Prescriptions (received)
                                  │  the pharmacist checks it, as any other
                                  ▼
    the app asks for the verdict: verified, needs clarification, or rejected

The shape is not about medicine: an order goes in, a verdict comes back. Any
app that needs a pharmacist to pass its order uses the same two endpoints.

Sending the same order again (same app, same sourceId) updates it rather than
making a second one: its details are replaced and, if it was waiting for
clarification, it goes back to the inbox to be checked again. A verified or
rejected one is left as it was: the verdict stands.
"""

import hmac
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import Field, field_validator
from sqlalchemy import func, select

from app.api import Api, check_email, iso, next_number, not_found, today
from app.audit import audit
from app.config import Settings
from app.deps import DB, SettingsDep
from app.models import CHECKS, Medicine, Patient, Prescription, PrescriptionItem
from app.routers.prescriptions import flags
from app.stock import sellable


def calling_app(
    settings: SettingsDep,
    x_bishnoi_key: Annotated[str | None, Header()] = None,
    # The header's name before the rename to Bishnoi One: still taken until every app is redeployed.
    x_nabhi_key: Annotated[str | None, Header()] = None,
) -> str:
    """The name of the app whose key came with the request."""
    x_bishnoi_key = x_bishnoi_key or x_nabhi_key
    if x_bishnoi_key:
        for key in settings.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if hmac.compare_digest(secret.encode(), x_bishnoi_key.encode()):
                return name
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This needs a Bishnoi One app's key (X-Bishnoi-Key).")


Caller = Annotated[str, Depends(calling_app)]
router = APIRouter(prefix="/integration/checks", tags=["integration"])

# The verdict as the sending app should read it. "received" and "pending" are
# both "with the pharmacist" from outside.
OUTCOME = {
    "received": "waiting",
    "pending": "waiting",
    "verified": "verified",
    "needs_clarification": "needs_clarification",
    "rejected": "rejected",
}
# Once here, the verdict stands: sending the order again changes nothing.
SETTLED = ("verified", "rejected")


class CustomerIn(Api):
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=254)
    address: str | None = Field(None, max_length=300)

    _email = field_validator("email")(check_email)


class PrescriptionDetails(Api):
    prescriber_name: str = Field(min_length=1, max_length=120)
    prescriber_license: str | None = Field(None, max_length=40)
    prescriber_clinic: str | None = Field(None, max_length=160)
    prescribed_on: date
    notes: str | None = Field(None, max_length=4000)


class LineIn(Api):
    # The sending app's product code: matched to a medicine here when a medicine has the same code.
    code: str | None = Field(None, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    quantity: int = Field(ge=1, le=100_000)
    unit: str | None = Field(None, max_length=30)
    directions: str | None = Field(None, max_length=300)


class CheckIn(Api):
    # The sending app's own id for the order: sending it again finds this check.
    source_id: str = Field(min_length=1, max_length=64)
    # What people call it there: a quote or order number.
    reference: str = Field(min_length=1, max_length=40)
    customer: CustomerIn
    prescription: PrescriptionDetails
    lines: list[LineIn] = Field(min_length=1, max_length=30)
    # Who sent it, as the sending app knows them.
    sent_by: str = Field(min_length=1, max_length=120)


def check_out(db: DB, rx: Prescription, settings: Settings) -> dict:
    ids = [i.medicine_id for i in rx.items if i.medicine_id]
    blocking = [f["message"] for f in flags(rx, settings, sellable(db, ids, today(settings))) if f["level"] == "block"]
    return {
        "id": rx.id,
        "number": rx.number,
        "sourceId": rx.source_id,
        "reference": rx.source_ref,
        # waiting, verified, needs_clarification or rejected.
        "outcome": OUTCOME[rx.status],
        "status": rx.status,
        # The pharmacist's note: why it needs clarification or was rejected.
        "note": rx.verification_notes,
        "checkedBy": rx.checked_by.full_name if rx.checked_by else None,
        "checkedByLicense": rx.checked_by.license_no if rx.checked_by else None,
        "checkedAt": iso(rx.checked_at),
        "receivedAt": iso(rx.received_at),
        "checks": [{"key": k, "label": label, "done": bool((rx.checks or {}).get(k))} for k, label in CHECKS],
        "lines": [
            {"writtenAs": i.written_as, "quantity": i.quantity, "matchedTo": i.medicine.label if i.medicine else None}
            for i in rx.items
        ],
        # What stands in the way of verifying it, as the pharmacist sees it.
        "blocking": blocking if rx.status not in SETTLED else [],
    }


def find(db: DB, app: str, source_id: str) -> Prescription | None:
    return db.scalar(select(Prescription).where(Prescription.source == app, Prescription.source_id == source_id))


def items_from(db: DB, lines: list[LineIn]) -> list[PrescriptionItem]:
    """Each line as written, matched to a medicine when one has the same code."""
    out = []
    for n, line in enumerate(lines):
        medicine = None
        if line.code:
            medicine = db.scalar(select(Medicine).where(func.lower(Medicine.code) == line.code.lower()))
        written = f"{line.name} ({line.code})" if line.code else line.name
        if line.unit:
            written = f"{written}, {line.unit}"
        out.append(PrescriptionItem(position=n, written_as=written[:200], medicine_id=medicine.id if medicine else None, quantity=line.quantity, directions=line.directions))
    return out


def patient_for(db: DB, customer: CustomerIn, app: str) -> Patient:
    """The customer as a patient on record: the one with the same name, or a new one."""
    found = db.scalar(select(Patient).where(func.lower(Patient.full_name) == customer.name.lower()).order_by(Patient.created_at))
    if found is not None:
        for field in ("phone", "email", "address"):
            if getattr(found, field) is None and getattr(customer, field):
                setattr(found, field, getattr(customer, field))
        if found.kind == "customer":
            found.kind = "patient"
        return found
    patient = Patient(kind="patient", full_name=customer.name, phone=customer.phone, email=customer.email, address=customer.address,
                      notes=f"First sent by {app.upper()} for a check.")
    db.add(patient)
    db.flush()
    return patient


@router.post("")
def send(app: Caller, db: DB, settings: SettingsDep, body: CheckIn) -> dict:
    """An order, for the pharmacist to check. Sending it again updates it."""
    rx = find(db, app, body.source_id)
    who = f"{app}: {body.sent_by}"
    if rx is not None and rx.status in SETTLED:
        # The pharmacist has decided; the verdict stands.
        return check_out(db, rx, settings)
    details = body.prescription
    if rx is None:
        rx = Prescription(
            number=next_number(db, "RX", settings),
            patient_id=patient_for(db, body.customer, app).id,
            status="received",
            checks={},
            source=app,
            source_id=body.source_id,
        )
        db.add(rx)
        action = "prescription.received"
    else:
        rx.patient_id = patient_for(db, body.customer, app).id
        # Asked, and answered: back in the inbox to be checked again.
        if rx.status == "needs_clarification":
            rx.status = "received"
        action = "prescription.resent"
    rx.source_ref = body.reference
    rx.source_by = body.sent_by
    rx.prescriber_name = details.prescriber_name
    rx.prescriber_license = details.prescriber_license
    rx.prescriber_clinic = details.prescriber_clinic
    rx.prescribed_on = details.prescribed_on
    rx.notes = details.notes
    rx.items = items_from(db, body.lines)
    db.flush()
    audit(db, who, action, target=f"{rx.number} {body.reference}", target_type="prescription", target_id=rx.id)
    db.commit()
    db.refresh(rx)
    return check_out(db, rx, settings)


@router.get("/{source_id}")
def read(app: Caller, db: DB, settings: SettingsDep, source_id: str) -> dict:
    """Where the pharmacist is with it, and the verdict once there is one."""
    rx = find(db, app, source_id)
    if rx is None:
        raise not_found("check")
    return check_out(db, rx, settings)

