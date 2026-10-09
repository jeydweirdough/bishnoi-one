"""Fleet, travel and devices: the executive assistant's trackers.

    /admin/vehicles      the company's cars: registration, insurance and maintenance due
    /admin/fleet-cards   the sales team's fuel cards
    /admin/travel        doctors' hotel and flight sponsorships
    /admin/devices       laptops, phones and SIMs handed out, and who signed

Each takes GET (the list), GET /{id} (one, with its history), POST (add),
PATCH /{id} (change), POST /{id}/log (a quick step: renewed, PMS done, booked,
blocked, a note...) and DELETE /{id},
with the area's permission (vehicles.*, travel.*, devices.*: fuel cards go with
vehicles). A vehicle's dates and a sponsorship's start count down like a
permit's, and feed the overview and the renewal alerts (app/executive.py).
Every change is in the activity log.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.access import permitted
from app.api import Api
from app.audit import audit
from app.config import Settings
from app.deps import DB, SettingsDep
from app.executive import sync_notifications, today_in_org, urgency_tier
from app.models import DeviceIssue, FleetCard, Notification, RecordEvent, TravelSponsorship, Vehicle, utcnow

router = APIRouter(prefix="/admin", tags=["fleet, travel and devices"])

FLEET_STATUSES = ("processing", "handed_over", "with_hr", "returned")
TRAVEL_STATUSES = ("for_approval", "for_processing", "approved", "booked", "cancelled")
# A vehicle's dates, in the order they're shown.
VEHICLE_DUES = (("registration_due", "registration", "Registration"), ("insurance_due", "insurance", "Insurance"), ("pms_due", "pms", "Maintenance (PMS)"))


# --- what each list takes ------------------------------------------------------------------


class VehicleIn(Api):
    name: str = Field(min_length=2, max_length=140)
    plate: str | None = Field(None, max_length=20)
    year_model: int | None = Field(None, ge=1950, le=2100)
    color: str | None = Field(None, max_length=60)
    owner_name: str | None = Field(None, max_length=200)
    registration_due: date | None = None
    insurance_due: date | None = None
    pms_due: date | None = None
    fleet_card: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=500)


class FleetCardIn(Api):
    requested_on: date | None = None
    holder_name: str = Field(min_length=2, max_length=140)
    company_name: str | None = Field(None, max_length=140)
    monthly_allowance: float | None = Field(None, ge=0, le=10_000_000)
    allowance_note: str | None = Field(None, max_length=80)
    fuel_type: str | None = Field(None, max_length=60)
    plate: str | None = Field(None, max_length=20)
    conduction_sticker: str | None = Field(None, max_length=30)
    vehicle_unit: str | None = Field(None, max_length=140)
    status: Literal["processing", "handed_over", "with_hr", "returned"] = "processing"
    card_state: Literal["active", "blocked"] = "active"
    notes: str | None = Field(None, max_length=500)


class TravelIn(Api):
    requested_on: date | None = None
    rep_name: str = Field(min_length=2, max_length=140)
    doctor_name: str = Field(min_length=2, max_length=140)
    doctor_birthdate: date | None = None
    kind: Literal["hotel", "flight"] = "hotel"
    travel_dates: str | None = Field(None, max_length=140)
    starts_on: date | None = None
    hotel_or_flight: str | None = Field(None, max_length=200)
    status: Literal["for_approval", "for_processing", "approved", "booked", "cancelled"] = "for_approval"
    approved_on: date | None = None
    next_step: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=500)


class DeviceIn(Api):
    issued_on: date | None = None
    issued_to: str = Field(min_length=2, max_length=200)
    laptop: str | None = Field(None, max_length=140)
    phone: str | None = Field(None, max_length=140)
    sim: str | None = Field(None, max_length=60)
    condition: Literal["brand_new", "repaired", "used"] = "brand_new"
    signed_by: str | None = Field(None, max_length=140)
    notes: str | None = Field(None, max_length=500)


# --- how each is shown ---------------------------------------------------------------------


def _d(value: date | None) -> str | None:
    return value.isoformat() if value else None


def countdown(due: date | None, today: date) -> dict:
    days = (due - today).days if due else None
    return {"daysRemaining": days, "urgencyTier": urgency_tier(days)}


def vehicle_dues(v: Vehicle, today: date) -> list[dict]:
    """Each date set on the car, soonest first."""
    out = [{"what": what, "label": label, "date": _d(getattr(v, attr)), **countdown(getattr(v, attr), today)} for attr, what, label in VEHICLE_DUES if getattr(v, attr)]
    return sorted(out, key=lambda d: d["daysRemaining"])


def vehicle_out(v: Vehicle, today: date) -> dict:
    dues = vehicle_dues(v, today)
    nearest = dues[0] if dues else None
    return {
        "id": v.id, "name": v.name, "plate": v.plate, "yearModel": v.year_model, "color": v.color, "ownerName": v.owner_name,
        "registrationDue": _d(v.registration_due), "insuranceDue": _d(v.insurance_due), "pmsDue": _d(v.pms_due),
        "fleetCard": v.fleet_card, "notes": v.notes, "dues": dues,
        "nextDue": nearest["label"] if nearest else None,
        "daysRemaining": nearest["daysRemaining"] if nearest else None,
        "urgencyTier": nearest["urgencyTier"] if nearest else "none",
        "updatedAt": v.updated_at.isoformat(),
    }


def fleet_card_out(c: FleetCard, today: date) -> dict:
    return {
        "id": c.id, "requestedOn": _d(c.requested_on), "holderName": c.holder_name, "companyName": c.company_name,
        "monthlyAllowance": c.monthly_allowance, "allowanceNote": c.allowance_note, "fuelType": c.fuel_type,
        "plate": c.plate, "conductionSticker": c.conduction_sticker, "vehicleUnit": c.vehicle_unit, "status": c.status, "cardState": c.card_state, "notes": c.notes,
        "updatedAt": c.updated_at.isoformat(),
    }


def travel_out(t: TravelSponsorship, today: date) -> dict:
    ahead = t.starts_on if t.status != "cancelled" else None
    return {
        "id": t.id, "requestedOn": _d(t.requested_on), "repName": t.rep_name, "doctorName": t.doctor_name, "doctorBirthdate": _d(t.doctor_birthdate), "kind": t.kind,
        "travelDates": t.travel_dates, "startsOn": _d(t.starts_on), "hotelOrFlight": t.hotel_or_flight, "status": t.status,
        "approvedOn": _d(t.approved_on), "nextStep": t.next_step, "notes": t.notes, **countdown(ahead, today), "updatedAt": t.updated_at.isoformat(),
    }


def device_out(d: DeviceIssue, today: date) -> dict:
    return {
        "id": d.id, "issuedOn": _d(d.issued_on), "issuedTo": d.issued_to, "laptop": d.laptop, "phone": d.phone, "sim": d.sim,
        "condition": d.condition, "signedBy": d.signed_by, "notes": d.notes, "updatedAt": d.updated_at.isoformat(),
    }


@dataclass(frozen=True)
class Kind:
    path: str
    area: str
    model: type
    payload: type[Api]
    out: Callable[[Any, date], dict]
    name: Callable[[Any], str]  # how the activity log names a record
    order: tuple
    what: str  # "vehicle", for messages
    check: Callable[[Any], None] = lambda body: None


def _check_device(body: DeviceIn) -> None:
    if not (body.laptop or body.phone or body.sim):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, [{"type": "value_error", "loc": ["body", "laptop"], "msg": "Say what was handed over: a laptop, a phone or a SIM."}])


KINDS = (
    Kind("vehicles", "vehicles", Vehicle, VehicleIn, vehicle_out, lambda v: " ".join(x for x in (v.name, v.plate) if x), (Vehicle.name,), "vehicle"),
    Kind("fleet-cards", "vehicles", FleetCard, FleetCardIn, fleet_card_out, lambda c: c.holder_name, (FleetCard.holder_name,), "fuel card"),
    Kind("travel", "travel", TravelSponsorship, TravelIn, travel_out, lambda t: f"{t.doctor_name} ({t.kind})", (TravelSponsorship.requested_on.desc(),), "sponsorship"),
    Kind("devices", "devices", DeviceIssue, DeviceIn, device_out, lambda d: d.issued_to, (DeviceIssue.issued_on.desc(),), "device issue", _check_device),
)


# --- quick steps and history ---------------------------------------------------------------


def _plus_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 February
        return d.replace(year=d.year + 1, day=28)


def _year_on(due: date | None, today: date) -> date:
    """The next due date a year on: from the old one (renewed on time keeps its day), never in the past."""
    nxt = _plus_year(due or today)
    while nxt <= today:
        nxt = _plus_year(nxt)
    return nxt


def _months_on(today: date, months: int) -> date:
    y, m = divmod(today.month - 1 + months, 12)
    year, month = today.year + y, m + 1
    for day in (today.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return date(year, month, 28)


def _fmt(d: date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"


def _renew(attr: str, label: str):
    def step(v: Vehicle, today: date) -> str:
        new = _year_on(getattr(v, attr), today)
        setattr(v, attr, new)
        return f"{label} renewed · next due {_fmt(new)}"
    return step


def _pms_done(v: Vehicle, today: date) -> str:
    v.pms_due = _months_on(today, 6)
    return f"PMS done · next one {_fmt(v.pms_due)}"


def _set(attr: str, value: str, words: str, also: Callable[[Any, date], None] | None = None):
    def step(record: Any, today: date) -> str:
        setattr(record, attr, value)
        if also:
            also(record, today)
        return words
    return step


def _approved(t: TravelSponsorship, today: date) -> None:
    t.approved_on = t.approved_on or today


# Per list: the quick steps a record takes, each changing it and saying what it did.
STEPS: dict[str, dict[str, Callable[[Any, date], str]]] = {
    "vehicles": {"registration_renewed": _renew("registration_due", "Registration"), "insurance_renewed": _renew("insurance_due", "Insurance"), "pms_done": _pms_done},
    "fleet-cards": {
        "blocked": _set("card_state", "blocked", "Card blocked"), "unblocked": _set("card_state", "active", "Card working again"),
        "handed_over": _set("status", "handed_over", "Handed over"), "with_hr": _set("status", "with_hr", "Handed to HR"), "returned": _set("status", "returned", "Card returned"),
    },
    "travel": {
        "approved": _set("status", "approved", "Approved", _approved), "booked": _set("status", "booked", "Booked", _approved),
        "for_processing": _set("status", "for_processing", "Sent for processing"), "cancelled": _set("status", "cancelled", "Cancelled"),
    },
    "devices": {},
}


def event(db: Session, path: str, record_id: str, kind: str, text: str, user) -> None:
    db.add(RecordEvent(record_type=path, record_id=record_id, kind=kind, text=text[:500], by_name=getattr(user, "full_name", None)))


def history(db: Session, path: str, record_id: str) -> list[dict]:
    rows = db.scalars(select(RecordEvent).where(RecordEvent.record_type == path, RecordEvent.record_id == record_id).order_by(RecordEvent.at.desc())).all()
    return [{"id": e.id, "kind": e.kind, "text": e.text, "by": e.by_name, "at": e.at.isoformat()} for e in rows]


class StepIn(Api):
    action: str = Field(min_length=2, max_length=30)
    note: str | None = Field(None, max_length=500)


FIELD_WORDS = {
    "registration_due": "registration date", "insurance_due": "insurance date", "pms_due": "PMS date", "monthly_allowance": "allowance",
    "card_state": "card", "starts_on": "first day", "travel_dates": "dates", "hotel_or_flight": "hotel or airline", "issued_to": "who has it",
}


def _apply(record: Any, body: Api) -> list[str]:
    """Sets what was sent; returns the fields that changed, for the activity log."""
    changed = []
    for key, value in body.model_dump().items():
        if getattr(record, key) != value:
            setattr(record, key, value)
            changed.append(key)
    return changed


def _get(db: Session, kind: Kind, record_id: str):
    record = db.get(kind.model, record_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"That {kind.what} isn't here any more.")
    return record


# Each kind's list and record reads, by path.
READS: dict[str, tuple[Callable[..., list[dict]], Callable[..., dict]]] = {}


def _routes(kind: Kind) -> None:
    def list_all(user: permitted(f"{kind.area}.view"), db: DB, settings: SettingsDep) -> list[dict]:
        today = today_in_org(settings)
        return [kind.out(r, today) for r in db.scalars(select(kind.model).order_by(*kind.order))]

    def add(user: permitted(f"{kind.area}.create"), body: kind.payload, db: DB, settings: SettingsDep) -> dict:  # type: ignore[valid-type]
        kind.check(body)
        record = kind.model()
        _apply(record, body)
        db.add(record)
        db.flush()
        event(db, kind.path, record.id, "added", "Added", user)
        audit(db, user, f"{kind.path}.added", target=kind.name(record), target_type=kind.path, target_id=record.id)
        db.commit()
        sync_notifications(db, settings)
        return kind.out(record, today_in_org(settings))

    def change(record_id: str, user: permitted(f"{kind.area}.edit"), body: kind.payload, db: DB, settings: SettingsDep) -> dict:  # type: ignore[valid-type]
        kind.check(body)
        record = _get(db, kind, record_id)
        fields = _apply(record, body)
        if fields:
            record.updated_at = utcnow()
            event(db, kind.path, record.id, "changed", "Changed " + ", ".join(FIELD_WORDS.get(f, f.replace("_", " ")) for f in fields), user)
            audit(db, user, f"{kind.path}.changed", target=kind.name(record), target_type=kind.path, target_id=record.id, fields=fields)
            db.commit()
            sync_notifications(db, settings)
        return kind.out(record, today_in_org(settings))

    def remove(record_id: str, user: permitted(f"{kind.area}.delete"), db: DB) -> Response:
        record = _get(db, kind, record_id)
        audit(db, user, f"{kind.path}.deleted", target=kind.name(record), target_type=kind.path, target_id=record.id)
        # Its renewal alerts go with it.
        db.execute(delete(Notification).where(Notification.entity_id == record.id))
        db.execute(delete(RecordEvent).where(RecordEvent.record_id == record.id))
        db.delete(record)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def one(record_id: str, user: permitted(f"{kind.area}.view"), db: DB, settings: SettingsDep) -> dict:
        record = _get(db, kind, record_id)
        return {"record": kind.out(record, today_in_org(settings)), "history": history(db, kind.path, record.id), "steps": list(STEPS[kind.path])}

    def log(record_id: str, user: permitted(f"{kind.area}.edit"), body: StepIn, db: DB, settings: SettingsDep) -> dict:
        record = _get(db, kind, record_id)
        if body.action == "note":
            if not body.note:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, [{"type": "value_error", "loc": ["body", "note"], "msg": "Write the note."}])
            event(db, kind.path, record.id, "note", body.note, user)
        else:
            step = STEPS[kind.path].get(body.action)
            if step is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"A {kind.what} can't be marked {body.action.replace('_', ' ')}.")
            words = step(record, today_in_org(settings))
            record.updated_at = utcnow()
            event(db, kind.path, record.id, body.action, words + (f" · {body.note}" if body.note else ""), user)
            audit(db, user, f"{kind.path}.{body.action}", target=kind.name(record), target_type=kind.path, target_id=record.id)
        db.commit()
        sync_notifications(db, settings)
        return one(record_id, user, db, settings)

    READS[kind.path] = (list_all, one)  # for GraphQL (app/graphql_api.py)
    router.add_api_route(f"/{kind.path}", list_all, methods=["GET"], name=f"list {kind.path}")
    router.add_api_route(f"/{kind.path}/{{record_id}}", one, methods=["GET"], name=f"one of {kind.path}")
    router.add_api_route(f"/{kind.path}/{{record_id}}/log", log, methods=["POST"], name=f"log on {kind.path}")
    router.add_api_route(f"/{kind.path}", add, methods=["POST"], status_code=status.HTTP_201_CREATED, name=f"add to {kind.path}")
    router.add_api_route(f"/{kind.path}/{{record_id}}", change, methods=["PATCH"], name=f"change in {kind.path}")
    router.add_api_route(f"/{kind.path}/{{record_id}}", remove, methods=["DELETE"], status_code=status.HTTP_204_NO_CONTENT, name=f"delete from {kind.path}")


for _kind in KINDS:
    _routes(_kind)


def summary(db: Session, settings: Settings) -> dict:
    """For the overview: what's due on the cars, which trips are close and not booked, and the cards and devices out."""
    today = today_in_org(settings)
    vehicles = db.scalars(select(Vehicle)).all()
    trips = db.scalars(select(TravelSponsorship).where(TravelSponsorship.status != "cancelled")).all()
    cards = db.scalars(select(FleetCard)).all()
    return {
        "vehicles": vehicles,
        "trips": trips,
        "today": today,
        "stats": {
            "vehicles": {"total": len(vehicles), "dueSoon": sum(1 for v in vehicles if any(0 <= d["daysRemaining"] <= 30 for d in vehicle_dues(v, today))), "overdue": sum(1 for v in vehicles if any(d["daysRemaining"] < 0 for d in vehicle_dues(v, today)))},
            "fleetCards": {"active": sum(1 for c in cards if c.card_state == "active"), "blocked": sum(1 for c in cards if c.card_state == "blocked"), "processing": sum(1 for c in cards if c.status == "processing")},
            "travel": {"upcoming": sum(1 for t in trips if t.starts_on and 0 <= (t.starts_on - today).days <= 30), "waiting": sum(1 for t in trips if t.status in ("for_approval", "for_processing"))},
            "devices": {"issued": db.query(DeviceIssue).count()},
        },
    }
