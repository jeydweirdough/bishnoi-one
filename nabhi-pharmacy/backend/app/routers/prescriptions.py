"""Prescriptions: taken in, checked, and verified before anything is dispensed.

    received ──check──> pending ──> verified ──> dispensing queue
                           │
                           ├──> needs_clarification ──(asked, answered)──> checked again
                           └──> rejected (closed)

Checking is its own step, apart from dispensing. The pharmacist ticks each
check (models.CHECKS), matches every medicine as written to one in the
catalogue, and gives a verdict. Verified needs every tick, every medicine
matched, and nothing blocking (flags below). Needs clarification and rejected
need a note saying why. Only a verified prescription can be dispensed.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select

from app.access import Can
from app.api import Api, camel, changed, conflict, day, field_error, get_or_404, iso, next_number, person_out, today
from app.audit import audit
from app.config import Settings
from app.deps import DB, SettingsDep
from app.models import CHECK_KEYS, CHECKS, Dispensing, Medicine, Patient, Prescription, PrescriptionItem
from app.routers.patients import PatientIn, patient_brief
from app.stock import sellable

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])

# Where each list on the Prescriptions page draws from.
VIEWS: dict[str, tuple[str, ...]] = {
    "inbox": ("received",),
    "pending": ("pending",),
    "verified": ("verified",),
    "attention": ("needs_clarification", "rejected"),
}
# Checking can't start again once it is closed.
CLOSED = ("rejected",)
Verdict = Literal["pending", "verified", "needs_clarification", "rejected"]


class ItemIn(Api):
    written_as: str = Field(min_length=1, max_length=200)
    medicine_id: str | None = Field(None, max_length=36)
    quantity: int = Field(ge=1, le=100_000)
    directions: str | None = Field(None, max_length=300)


class PrescriptionIn(Api):
    patient_id: str | None = Field(None, max_length=36)
    # A patient seen for the first time, entered with the prescription.
    new_patient: PatientIn | None = None
    prescriber_name: str = Field(min_length=1, max_length=120)
    prescriber_license: str | None = Field(None, max_length=40)
    prescriber_clinic: str | None = Field(None, max_length=160)
    prescribed_on: date
    notes: str | None = Field(None, max_length=4000)
    items: list[ItemIn] = Field(min_length=1, max_length=30)


class PrescriptionPatch(Api):
    prescriber_name: str | None = Field(None, min_length=1, max_length=120)
    prescriber_license: str | None = Field(None, max_length=40)
    prescriber_clinic: str | None = Field(None, max_length=160)
    prescribed_on: date | None = None
    notes: str | None = Field(None, max_length=4000)
    items: list[ItemIn] | None = Field(None, min_length=1, max_length=30)


class Match(Api):
    item_id: str = Field(max_length=36)
    medicine_id: str | None = Field(None, max_length=36)


class CheckIn(Api):
    checks: dict[str, bool] = Field(default_factory=dict)
    matches: list[Match] = Field(default_factory=list, max_length=30)
    status: Verdict
    notes: str | None = Field(None, max_length=4000)

    @field_validator("checks")
    @classmethod
    def _known(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = sorted(set(value) - set(CHECK_KEYS))
        if unknown:
            raise ValueError(f"Unknown check: {', '.join(unknown)}.")
        return {k: bool(value.get(k)) for k in CHECK_KEYS}


# --- what the screens are shown ---------------------------------------------------------------


def flags(rx: Prescription, settings: Settings, available: dict[str, int]) -> list[dict]:
    """What the pharmacist should know before verifying. "block" stops a
    verification; "warn" is for them to weigh."""
    on = today(settings)
    out: list[dict] = []

    def add(level: str, check: str, message: str) -> None:
        out.append({"level": level, "check": check, "message": message})

    if rx.prescribed_on > on:
        add("block", "date", "The prescription is dated in the future.")
    elif rx.prescribed_on < on - timedelta(days=settings.prescription_valid_days):
        add("block", "date", f"The prescription is more than {settings.prescription_valid_days} days old.")
    if rx.patient.allergies:
        add("warn", "patient", f"Allergies on record: {rx.patient.allergies}")
    for item in rx.items:
        m = item.medicine
        if m is None:
            add("block", "medicine", f"“{item.written_as}” isn't matched to a medicine in the catalogue yet.")
            continue
        if m.status == "inactive":
            add("block", "medicine", f"{m.label} is marked inactive in the catalogue.")
        if m.rx_class == "dangerous" and not rx.prescriber_license:
            add("block", "required", f"{m.label} is a dangerous drug: the prescriber's licence number is required.")
        if m.rx_class == "otc":
            add("warn", "medicine", f"{m.label} is sold over the counter; it doesn't need a prescription.")
        have = available.get(m.id, 0)
        # A check sent by another app is filled by that app's order, not from the counter's stock.
        if item.remaining and have < item.remaining and rx.source is None:
            add("warn", "availability", f"Only {have} {m.unit}(s) of {m.label} can be given out today; {item.remaining} prescribed.")
    return out


def item_out(item: PrescriptionItem, available: dict[str, int]) -> dict:
    m = item.medicine
    return {
        "id": item.id,
        "writtenAs": item.written_as,
        "medicine": None
        if m is None
        else {"id": m.id, "label": m.label, "unit": m.unit, "rxClass": m.rx_class, "status": m.status, "priceCentavos": m.price_centavos},
        "quantity": item.quantity,
        "directions": item.directions,
        "qtyDispensed": item.qty_dispensed,
        "remaining": item.remaining,
        "available": available.get(m.id, 0) if m else None,
    }


def dispense_state(rx: Prescription) -> str:
    """none, partial or full: how much of it has been handed over."""
    given = sum(i.qty_dispensed for i in rx.items)
    if given == 0:
        return "none"
    return "full" if all(i.remaining == 0 for i in rx.items) else "partial"


def summary_out(rx: Prescription) -> dict:
    return {
        "id": rx.id,
        "number": rx.number,
        "status": rx.status,
        "dispensed": dispense_state(rx),
        "patient": patient_brief(rx.patient),
        "prescriberName": rx.prescriber_name,
        "prescribedOn": day(rx.prescribed_on),
        "receivedAt": iso(rx.received_at),
        "checkedAt": iso(rx.checked_at),
        "checkedBy": person_out(rx.checked_by),
        "itemCount": len(rx.items),
        # Sent by another app for checking, or None when taken in here.
        "source": {"app": rx.source, "reference": rx.source_ref, "sentBy": rx.source_by} if rx.source else None,
        "items": [{"writtenAs": i.written_as, "quantity": i.quantity, "remaining": i.remaining} for i in rx.items],
    }


def detail_out(db: DB, rx: Prescription, settings: Settings) -> dict:
    ids = [i.medicine_id for i in rx.items if i.medicine_id]
    available = sellable(db, ids, today(settings))
    dispensings = db.scalars(select(Dispensing).where(Dispensing.prescription_id == rx.id).order_by(Dispensing.dispensed_at))
    return {
        **summary_out(rx),
        "prescriberLicense": rx.prescriber_license,
        "prescriberClinic": rx.prescriber_clinic,
        "notes": rx.notes,
        "receivedBy": person_out(rx.received_by),
        "verificationNotes": rx.verification_notes,
        "checks": [{"key": k, "label": label, "done": bool((rx.checks or {}).get(k))} for k, label in CHECKS],
        "items": [item_out(i, available) for i in rx.items],
        "flags": flags(rx, settings, available),
        "editable": rx.status != "verified" and rx.status not in CLOSED,
        "dispensings": [
            {"id": d.id, "number": d.number, "dispensedAt": iso(d.dispensed_at), "dispensedBy": person_out(d.dispensed_by),
             "units": sum(line.quantity for line in d.lines)}
            for d in dispensings
        ],
    }


# --- endpoints ----------------------------------------------------------------------------------


def _items(db: DB, items: list[ItemIn]) -> list[PrescriptionItem]:
    out = []
    for n, item in enumerate(items):
        if item.medicine_id is not None and db.get(Medicine, item.medicine_id) is None:
            raise field_error(f"items.{n}.medicineId", "Pick a medicine from the catalogue.")
        out.append(PrescriptionItem(position=n, **item.model_dump()))
    return out


@router.get("/counts")
def counts(_: Can("prescriptions.view"), db: DB) -> dict:
    by_status = dict(db.execute(select(Prescription.status, func.count()).group_by(Prescription.status)).all())
    return {view: sum(by_status.get(s, 0) for s in statuses) for view, statuses in VIEWS.items()}


@router.get("")
def list_prescriptions(
    _: Can("prescriptions.view"),
    db: DB,
    view: Literal["inbox", "pending", "verified", "attention", "history"] = "inbox",
    q: str | None = Query(None, max_length=80),
    limit: int = Query(200, ge=1, le=500),
) -> list[dict]:
    query = select(Prescription).join(Patient, Prescription.patient_id == Patient.id)
    if view in VIEWS:
        query = query.where(Prescription.status.in_(VIEWS[view]))
    # The inbox is worked oldest first; everything else reads newest first.
    query = query.order_by(Prescription.received_at if view in ("inbox", "pending") else Prescription.received_at.desc()).limit(limit)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            or_(func.lower(Prescription.number).like(like), func.lower(Patient.full_name).like(like), func.lower(Prescription.prescriber_name).like(like))
        )
    return [summary_out(rx) for rx in db.scalars(query).unique()]


@router.post("", status_code=status.HTTP_201_CREATED)
def receive(access: Can("prescriptions.create"), db: DB, settings: SettingsDep, body: PrescriptionIn) -> dict:
    """Takes a prescription in. It lands in the inbox, waiting to be checked."""
    if (body.patient_id is None) == (body.new_patient is None):
        raise field_error("patientId", "Pick the patient, or enter a new one.")
    if body.patient_id is not None:
        patient = get_or_404(db, Patient, body.patient_id, "patient")
        if patient.kind == "customer":
            # Someone who used to buy over the counter, now with a prescription.
            patient.kind = "patient"
    else:
        if not access.can("patients.create"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role can't add patients. Pick one already on record.")
        patient = Patient(**{**body.new_patient.model_dump(), "kind": "patient"})
        db.add(patient)
        db.flush()
        audit(db, access.user, "patient.created", target=patient.full_name, target_type="patient", target_id=patient.id)
    rx = Prescription(
        number=next_number(db, "RX", settings),
        patient_id=patient.id,
        prescriber_name=body.prescriber_name,
        prescriber_license=body.prescriber_license,
        prescriber_clinic=body.prescriber_clinic,
        prescribed_on=body.prescribed_on,
        notes=body.notes,
        status="received",
        checks={},
        received_by_id=access.user.id,
        items=_items(db, body.items),
    )
    db.add(rx)
    db.flush()
    audit(db, access.user, "prescription.received", target=f"{rx.number} {patient.full_name}", target_type="prescription", target_id=rx.id)
    db.commit()
    db.refresh(rx)
    return detail_out(db, rx, settings)


@router.get("/{prescription_id}")
def read(_: Can("prescriptions.view"), db: DB, settings: SettingsDep, prescription_id: str) -> dict:
    return detail_out(db, get_or_404(db, Prescription, prescription_id, "prescription"), settings)


@router.patch("/{prescription_id}")
def update(access: Can("prescriptions.edit"), db: DB, settings: SettingsDep, prescription_id: str, body: PrescriptionPatch) -> dict:
    """Corrects what was entered, before it is verified. Once verified it is
    what was checked, and stays as it is."""
    rx = get_or_404(db, Prescription, prescription_id, "prescription")
    if rx.status == "verified":
        raise conflict("This prescription is verified. Send it back for checking before changing it.")
    if rx.status in CLOSED:
        raise conflict("This prescription was rejected, so it's closed.")
    wanted = changed(body)
    if "prescriber_name" in wanted and wanted["prescriber_name"] is None:
        raise field_error("prescriberName", "This can't be empty.")
    if "prescribed_on" in wanted and wanted["prescribed_on"] is None:
        raise field_error("prescribedOn", "This can't be empty.")
    fields = [k for k, v in wanted.items() if k != "items" and getattr(rx, k) != v]
    for k in fields:
        setattr(rx, k, wanted[k])
    if body.items is not None:
        rx.items = _items(db, body.items)
        fields.append("items")
    if fields:
        audit(db, access.user, "prescription.updated", target=rx.number, target_type="prescription", target_id=rx.id, fields=camel(fields))
        db.commit()
        db.refresh(rx)
    return detail_out(db, rx, settings)


@router.post("/{prescription_id}/check")
def check(access: Can("prescriptions.verify"), db: DB, settings: SettingsDep, prescription_id: str, body: CheckIn) -> dict:
    """The pharmacist's check: the ticks, the matches, and the verdict."""
    rx = get_or_404(db, Prescription, prescription_id, "prescription")
    if rx.status in CLOSED:
        raise conflict("This prescription was rejected, so it's closed.")
    if rx.status == "verified" and dispense_state(rx) != "none":
        raise conflict("Medicines have been dispensed on this prescription, so its verification stands.")

    items = {i.id: i for i in rx.items}
    for n, match in enumerate(body.matches):
        item = items.get(match.item_id)
        if item is None:
            raise field_error(f"matches.{n}.itemId", "That medicine isn't on this prescription.")
        if match.medicine_id is not None and db.get(Medicine, match.medicine_id) is None:
            raise field_error(f"matches.{n}.medicineId", "Pick a medicine from the catalogue.")
        item.medicine_id = match.medicine_id
    db.flush()
    # A new medicine_id doesn't reload the medicine it names by itself.
    for item in rx.items:
        db.refresh(item)

    if body.status in ("needs_clarification", "rejected") and not body.notes:
        raise field_error("notes", "Say what's wrong, so whoever picks it up next knows what to ask.")
    if body.status == "verified":
        missing = [label for key, label in CHECKS if not body.checks.get(key)]
        if missing:
            raise field_error("checks", f"Tick every check before verifying. Still open: {', '.join(missing)}.")
        ids = [i.medicine_id for i in rx.items if i.medicine_id]
        blockers = [f["message"] for f in flags(rx, settings, sellable(db, ids, today(settings))) if f["level"] == "block"]
        if blockers:
            raise conflict(" ".join(blockers))

    before = rx.status
    rx.checks = body.checks
    rx.status = body.status
    rx.verification_notes = body.notes
    rx.checked_by_id = access.user.id
    rx.checked_at = datetime.now(UTC)
    action = {"pending": "prescription.checked", "verified": "prescription.verified",
              "needs_clarification": "prescription.needs_clarification", "rejected": "prescription.rejected"}[body.status]
    audit(db, access.user, action, target=f"{rx.number} {rx.patient.full_name}", target_type="prescription", target_id=rx.id,
          fields=["status"] if before != rx.status else [])
    db.commit()
    db.refresh(rx)
    return detail_out(db, rx, settings)
