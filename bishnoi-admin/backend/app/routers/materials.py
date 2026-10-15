"""Promotional materials, from design to giving them out.

    the marketing assistant adds the material and uploads its design
        │  Submit for review: the design goes to Pharmacy (app/linked.py)
        ▼
    the pharmacist approves it, returns it for changes, or rejects it
        │  returned: a new version is uploaded and submitted again; each keeps its comments
        ▼
    the executive office produces it: a print run ordered, then received into stock
        │
        ▼
    the marketing assistant asks to give some to a CRM team (or one person in it)
        │  the team's manager approves or rejects it in the CRM
        ▼
    given out: the stock goes down

    /admin/materials                                   list, add
    /admin/materials/{id}                              one (asks Pharmacy and the CRM again), change, delete
    /admin/materials/{id}/design                       upload the design (a new version once one was sent)
    /admin/materials/{id}/versions/{n}/file            a version's design
    /admin/materials/{id}/submit                       send the latest design to the pharmacist
    /admin/materials/{id}/productions[/{pid}/...]      a print run; received (with a photo as proof) or cancelled
    /admin/materials/{id}/distributions[/{did}/...]    a request to give some out; distributed (with proof) or cancelled
    /admin/materials/{id}/proofs/{ref}                 a proof photo
    /admin/materials/teams                             the CRM's teams and their people

Permissions: materials.view, .create, .edit (the design and submitting it),
.produce (print runs), .distribute (asking to give out, and recording it), .delete.
"""

import base64
import logging
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from urllib.parse import quote as url_quote

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import linked
from app.access import access_of, permitted
from app.api import Api, field_error
from app.audit import audit
from app.config import Settings
from app.deps import DB, SettingsDep
from app.executive import today_in_org, urgency_tier
from app.models import PromoDistribution, PromoMaterial, PromoProduction, PromoVersion, RecordEvent, StoredFile, utcnow
from app.routers.operations import event, history

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/materials", tags=["promotional materials"])

PATH = "materials"  # its history's record type
KINDS = ("Leaflet", "Brochure", "Poster", "Standee", "Tarpaulin", "Calendar", "Notepad", "Giveaway", "Other")
# Up to 3 MB: sent on to Pharmacy as text, it must still fit a request there.
MAX_BYTES = 3 * 1024 * 1024
FILE_KINDS = {b"%PDF": "application/pdf", b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg"}
PROOF_KINDS = FILE_KINDS  # a photo of the delivery or hand-over, or a scanned receipt
# How long another app's last answer stands before it's asked again.
FRESH_FOR = timedelta(seconds=30)
# Only these can have their design changed and sent.
DESIGNING = ("draft", "returned")
# These can be produced.
PRODUCIBLE = ("approved", "in_production", "available")
# A distribution in these still holds its quantity.
HOLDING = ("for_approval", "approved")
DISTRIBUTION_SETTLED = ("distributed", "cancelled", "rejected")


# --- how each is shown ---------------------------------------------------------------------


def _iso(moment: datetime | date | None) -> str | None:
    if moment is None:
        return None
    if isinstance(moment, datetime) and moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.isoformat()


def reserved(db: Session, material: PromoMaterial) -> int:
    """What open requests hold: asked for or approved, not yet given out."""
    rows = db.scalars(select(PromoDistribution.quantity).where(PromoDistribution.material_id == material.id, PromoDistribution.status.in_(HOLDING)))
    return sum(rows)


def version_out(v: PromoVersion) -> dict:
    return {
        "number": v.number, "fileName": v.file_name, "hasFile": bool(v.file_ref), "notes": v.notes, "review": v.review,
        "sentAt": _iso(v.sent_at), "sentBy": v.sent_by_name, "pharmacyNumber": v.pharmacy_number,
        "comments": v.comments, "reviewedBy": v.reviewed_by, "reviewedAt": _iso(v.reviewed_at),
        "syncedAt": _iso(v.synced_at), "syncError": v.sync_error,
    }


def production_out(p: PromoProduction) -> dict:
    return {
        "id": p.id, "versionNumber": p.version_number, "quantity": p.quantity, "supplier": p.supplier, "cost": p.cost,
        "orderedOn": _iso(p.ordered_on), "expectedOn": _iso(p.expected_on), "receivedOn": _iso(p.received_on),
        "status": p.status, "notes": p.notes, "by": p.by_name,
        "proof": {"ref": p.proof_ref, "name": p.proof_name} if p.proof_ref else None,
    }


def distribution_out(d: PromoDistribution) -> dict:
    return {
        "id": d.id, "no": d.no, "teamId": d.team_id, "teamName": d.team_name, "recipientId": d.recipient_id, "recipientName": d.recipient_name,
        "quantity": d.quantity, "purpose": d.purpose, "status": d.status, "requestedBy": d.requested_by_name,
        "managerName": d.manager_name, "decisionNote": d.decision_note, "decidedAt": _iso(d.decided_at),
        "distributedOn": _iso(d.distributed_on), "requestedAt": _iso(d.created_at), "syncedAt": _iso(d.synced_at), "syncError": d.sync_error,
        "proof": {"ref": d.proof_ref, "name": d.proof_name} if d.proof_ref else None,
    }


# --- how urgent it is: real dates and real stock only, never a made-up deadline ---------

# Waiting this long on someone (the pharmacist, a manager) is worth a nudge.
WAIT_NUDGE_DAYS = 3
# Low stock: this share of all that was received, or this many, whichever is more.
LOW_STOCK_SHARE, LOW_STOCK_FLOOR = 0.1, 10
# Still to come before it's in hand: the date needed counts down until it's in stock.
NOT_IN_HAND = ("draft", "pharmacy_review", "returned", "approved", "in_production")


def _days_since(moment: datetime | None, today: date) -> int | None:
    if moment is None:
        return None
    return (today - (moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment).date()).days


def urgency(db: Session, m: PromoMaterial, today: date, held: int | None = None) -> dict:
    """What makes this material pressing now, from its own dates and stock:
    the days until it's needed (while it isn't in stock yet), how long it has
    waited on the pharmacist or a manager, and whether stock is running low.
    `next` says the step that moves it on, in plain words with its timing."""
    held = reserved(db, m) if held is None else held
    latest = m.versions[-1] if m.versions else None
    needed_in = (m.needed_by - today).days if m.needed_by and m.status in NOT_IN_HAND else None

    waiting = None
    if m.status == "pharmacy_review" and latest is not None:
        days = _days_since(latest.sent_at, today)
        if days is not None:
            waiting = {"on": "pharmacist", "days": days}
    else:
        oldest = db.scalar(select(PromoDistribution.created_at).where(PromoDistribution.material_id == m.id, PromoDistribution.status == "for_approval").order_by(PromoDistribution.created_at))
        days = _days_since(oldest, today)
        if days is not None:
            waiting = {"on": "manager", "days": days}

    received = sum(db.scalars(select(PromoProduction.quantity).where(PromoProduction.material_id == m.id, PromoProduction.status == "received")))
    free = max(m.stock - held, 0)
    low = m.status == "available" and received > 0 and free <= max(LOW_STOCK_FLOOR, round(received * LOW_STOCK_SHARE))

    timing = ""
    if needed_in is not None:
        timing = f" It's needed {'today' if needed_in == 0 else 'tomorrow' if needed_in == 1 else f'in {needed_in} days'}." if needed_in >= 0 else f" It was needed {-needed_in} day{'s' if needed_in != -1 else ''} ago."
    soon = needed_in is not None and needed_in <= 15
    step = {
        "draft": ("Upload the design and submit it for review" + (" today." if soon else ".")) if not latest or latest.review == "draft" else "Submit the design for review" + (" today." if soon else "."),
        "returned": "Correct the design as the pharmacist asked and submit it again" + (" today." if soon else "."),
        "pharmacy_review": "With the pharmacist." + (f" Waiting {waiting['days']} days: follow it up in Pharmacy." if waiting and waiting["days"] >= WAIT_NUDGE_DAYS else ""),
        "approved": "Order its production" + (" now." if soon else "."),
        "in_production": "Mark it received as soon as it arrives.",
        "available": (f"Only {free:,} free to give out: order more before it runs out." if low else "In stock: request distribution to the teams who need it.") if free > 0 else "None left to give out: order more, or retire it.",
    }.get(m.status)
    tier = urgency_tier(needed_in) if needed_in is not None else ("urgent" if low or (waiting and waiting["days"] >= WAIT_NUDGE_DAYS) else "none")
    told = step + timing if step and m.status in NOT_IN_HAND else step
    # "step" alone where the timing is shown beside it (the overview's countdown).
    return {"neededIn": needed_in, "tier": tier, "waiting": waiting, "lowStock": low, "next": told, "step": step}


def material_out(db: Session, m: PromoMaterial, today: date | None = None) -> dict:
    latest = m.versions[-1] if m.versions else None
    held = reserved(db, m)
    today = today or date.today()
    return {
        "id": m.id, "no": m.no, "title": m.title, "kind": m.kind, "product": m.product, "description": m.description,
        "quantity": m.quantity, "specs": m.specs, "neededBy": _iso(m.needed_by), "budget": m.budget,
        "status": m.status, "stock": m.stock, "reserved": held, "available": max(m.stock - held, 0),
        "version": latest.number if latest else None, "review": latest.review if latest else None,
        "createdBy": m.created_by_name, "createdAt": _iso(m.created_at), "updatedAt": _iso(m.updated_at),
        "urgency": urgency(db, m, today, held),
    }


def _get(db: Session, material_id: str) -> PromoMaterial:
    m = db.get(PromoMaterial, material_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That promotional material isn't here any more.")
    return m


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def _unavailable(e: Exception) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


# --- keeping up with Pharmacy and the CRM --------------------------------------------------


def _stale(synced: datetime | None) -> bool:
    if synced is None:
        return True
    synced = synced.replace(tzinfo=UTC) if synced.tzinfo is None else synced
    return datetime.now(UTC) - synced >= FRESH_FOR


def _moment(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def take_review(db: Session, m: PromoMaterial, v: PromoVersion, answer: dict) -> None:
    """Pharmacy's answer on a version, and what it makes of the material."""
    outcome = answer.get("outcome")
    v.synced_at = utcnow()
    v.sync_error = None
    v.pharmacy_number = answer.get("number") or v.pharmacy_number
    if outcome not in ("waiting", "approved", "returned", "rejected") or outcome == v.review:
        return
    v.review = outcome
    v.comments = (answer.get("comments") or None) and str(answer["comments"])[:2000]
    v.reviewed_by = (answer.get("reviewedBy") or None) and str(answer["reviewedBy"])[:140]
    v.reviewed_at = _moment(answer.get("reviewedAt"))
    if outcome != "waiting" and m.status == "pharmacy_review" and v is m.versions[-1]:
        m.status = outcome  # approved, returned or rejected
        words = {"approved": "Design approved by the pharmacist", "returned": "Design returned for changes by the pharmacist", "rejected": "Design rejected by the pharmacist"}[outcome]
        by = f" ({v.reviewed_by})" if v.reviewed_by else ""
        event(db, PATH, m.id, f"review_{outcome}", words + by + (f" · {v.comments}" if v.comments else ""), None)
        audit(db, f"Pharmacy ({v.reviewed_by})" if v.reviewed_by else "Pharmacy", f"materials.review_{outcome}", target=m.title, target_type=PATH, target_id=m.id)


DISTRIBUTION_OUTCOMES = {"waiting": "for_approval", "approved": "approved", "rejected": "rejected"}


def take_decision(db: Session, m: PromoMaterial, d: PromoDistribution, answer: dict) -> None:
    """The CRM manager's answer on a distribution."""
    d.synced_at = utcnow()
    d.sync_error = None
    wanted = DISTRIBUTION_OUTCOMES.get(answer.get("outcome"))
    if wanted is None or d.status != "for_approval" or wanted == d.status:
        return
    d.status = wanted
    d.manager_name = (answer.get("decidedBy") or None) and str(answer["decidedBy"])[:140]
    d.decision_note = (answer.get("note") or None) and str(answer["note"])[:500]
    d.decided_at = _moment(answer.get("decidedAt")) or utcnow()
    who = d.recipient_name or d.team_name
    words = f"{d.quantity} for {who} {'approved' if wanted == 'approved' else 'rejected'} by {d.manager_name or 'the manager'}"
    event(db, PATH, m.id, f"distribution_{wanted}", words + (f" · {d.decision_note}" if d.decision_note else ""), None)
    audit(db, f"CRM ({d.manager_name})" if d.manager_name else "CRM", f"materials.distribution_{wanted}", target=m.title, target_type=PATH, target_id=m.id)


def refresh(db: Session, settings: Settings, m: PromoMaterial, *, now: bool = False) -> bool:
    """Asks Pharmacy about a design with the pharmacist, and the CRM about
    requests with a manager, when their last answer is out of date. A failure
    is kept, not raised: the material still opens. True when anything was asked."""
    asked = False
    latest = m.versions[-1] if m.versions else None
    if latest and latest.review == "waiting" and linked.linked(settings, "pharmacy") and (now or _stale(latest.synced_at)):
        asked = True
        try:
            take_review(db, m, latest, linked.call(settings, "pharmacy", "GET", f"/integration/materials/{url_quote(latest.id)}"))
        except (linked.Unavailable, linked.Refused) as e:
            latest.synced_at, latest.sync_error = utcnow(), str(e)[:300]
    waiting = db.scalars(select(PromoDistribution).where(PromoDistribution.material_id == m.id, PromoDistribution.status == "for_approval")).all()
    if waiting and linked.linked(settings, "crm"):
        for d in waiting:
            if not (now or _stale(d.synced_at)):
                continue
            asked = True
            try:
                take_decision(db, m, d, linked.call(settings, "crm", "GET", f"/integration/material-requests/{url_quote(d.id)}"))
            except (linked.Unavailable, linked.Refused) as e:
                d.synced_at, d.sync_error = utcnow(), str(e)[:300]
    if asked:
        db.commit()
    return asked


# --- the list and one material --------------------------------------------------------------


class MaterialIn(Api):
    title: str = Field(min_length=2, max_length=160)
    kind: str = Field(min_length=2, max_length=40)
    product: str | None = Field(None, max_length=160)
    description: str | None = Field(None, max_length=1000)
    quantity: int | None = Field(None, ge=1, le=10_000_000)  # how many are planned
    specs: str | None = Field(None, max_length=300)  # size, paper, colours
    needed_by: date | None = None
    budget: float | None = Field(None, ge=0, le=1_000_000_000)


def _check_kind(body: MaterialIn) -> None:
    if body.kind not in KINDS:
        raise field_error("kind", "Pick a type from the list.")


def highlights(db: Session, today: date) -> list[dict]:
    """For the overview's "Needs your attention": materials needed within 15 days (or late) that aren't in stock yet."""
    out = []
    for m in db.scalars(select(PromoMaterial).where(PromoMaterial.needed_by.is_not(None), PromoMaterial.status.in_(NOT_IN_HAND))):
        days = (m.needed_by - today).days
        if days <= 15:
            out.append({
                "entityType": "material", "entityId": m.id, "title": m.title,
                "subtitle": urgency(db, m, today)["step"] or "", "reference": f"PM-{m.no}" if m.no else m.kind,
                "dueDate": m.needed_by.isoformat(), "daysRemaining": days, "urgencyTier": urgency_tier(days),
                "actionPath": f"/materials/{m.id}",
            })
    return out


@router.get("")
def list_materials(user: permitted("materials.view"), db: DB, settings: SettingsDep) -> dict:
    today = today_in_org(settings)
    items = [material_out(db, m, today) for m in db.scalars(select(PromoMaterial).order_by(PromoMaterial.updated_at.desc()))]
    rank = {"overdue": 0, "urgent": 1, "approaching": 2, "upcoming": 3}
    items.sort(key=lambda i: (rank.get(i["urgency"]["tier"], 4), i["urgency"]["neededIn"] if i["urgency"]["neededIn"] is not None else 10**6))
    return {
        "items": items,
        "kinds": list(KINDS),
        "linked": {"pharmacy": linked.linked(settings, "pharmacy"), "crm": linked.linked(settings, "crm")},
    }


def _steps(m: PromoMaterial, user, db: Session) -> dict:
    """What can be done with it now, by this person."""
    access = access_of(user)
    latest = m.versions[-1] if m.versions else None
    design = m.status in DESIGNING
    return {
        "edit": access.can("materials.edit") and design,
        "upload": access.can("materials.edit") and design,
        "submit": access.can("materials.edit") and design and bool(latest and latest.review == "draft" and latest.file_ref),
        "produce": access.can("materials.produce") and m.status in PRODUCIBLE,
        "distribute": access.can("materials.distribute") and m.status == "available" and m.stock - reserved(db, m) > 0,
        "recordDistribution": access.can("materials.distribute"),
        "retire": access.can("materials.edit") and m.status == "available",
        "delete": access.can("materials.delete") and m.status in ("draft", "returned", "rejected"),
    }


def one_out(db: Session, settings: Settings, m: PromoMaterial, user) -> dict:
    productions = db.scalars(select(PromoProduction).where(PromoProduction.material_id == m.id).order_by(PromoProduction.created_at.desc())).all()
    distributions = db.scalars(select(PromoDistribution).where(PromoDistribution.material_id == m.id).order_by(PromoDistribution.created_at.desc())).all()
    return {
        "material": material_out(db, m, today_in_org(settings)),
        "versions": [version_out(v) for v in reversed(m.versions)],
        "productions": [production_out(p) for p in productions],
        "distributions": [distribution_out(d) for d in distributions],
        "history": history(db, PATH, m.id),
        "can": _steps(m, user, db),
        "kinds": list(KINDS),
        "linked": {"pharmacy": linked.linked(settings, "pharmacy"), "crm": linked.linked(settings, "crm")},
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def add_material(user: permitted("materials.create"), body: MaterialIn, db: DB, settings: SettingsDep) -> dict:
    _check_kind(body)
    m = PromoMaterial(**body.model_dump(), created_by_name=user.full_name)
    db.add(m)
    db.flush()
    event(db, PATH, m.id, "added", "Added", user)
    audit(db, user, "materials.added", target=m.title, target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


@router.get("/teams")
def crm_teams(user: permitted("materials.view"), settings: SettingsDep) -> dict:
    """The CRM's teams, each with its manager and people, to give materials to."""
    try:
        answer = linked.call(settings, "crm", "GET", "/integration/teams")
    except (linked.Unavailable, linked.Refused) as e:
        raise _unavailable(e) from None
    return {"teams": answer.get("teams") or []}


@router.get("/{material_id}")
def one_material(material_id: str, user: permitted("materials.view"), db: DB, settings: SettingsDep) -> dict:
    m = _get(db, material_id)
    refresh(db, settings, m)
    return one_out(db, settings, m, user)


@router.post("/{material_id}/refresh")
def refresh_now(material_id: str, user: permitted("materials.view"), db: DB, settings: SettingsDep) -> dict:
    """Asks Pharmacy and the CRM again now, whatever their last answer's age."""
    m = _get(db, material_id)
    refresh(db, settings, m, now=True)
    return one_out(db, settings, m, user)


@router.patch("/{material_id}")
def change_material(material_id: str, user: permitted("materials.edit"), body: MaterialIn, db: DB, settings: SettingsDep) -> dict:
    _check_kind(body)
    m = _get(db, material_id)
    if m.status not in DESIGNING:
        raise _conflict("Its details can be changed only while it's a draft or returned for changes.")
    changed = [k for k, v in body.model_dump().items() if getattr(m, k) != v]
    for k in changed:
        setattr(m, k, getattr(body, k))
    if changed:
        m.updated_at = utcnow()
        event(db, PATH, m.id, "changed", "Changed " + ", ".join(changed), user)
        audit(db, user, "materials.changed", target=m.title, target_type=PATH, target_id=m.id, fields=changed)
        db.commit()
    return one_out(db, settings, m, user)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(material_id: str, user: permitted("materials.delete"), db: DB) -> Response:
    m = _get(db, material_id)
    if m.status not in ("draft", "returned", "rejected"):
        raise _conflict("An approved material can't be deleted. Retire it instead, so its records stay.")
    refs = [v.file_ref for v in m.versions if v.file_ref]
    refs += [r for r in db.scalars(select(PromoProduction.proof_ref).where(PromoProduction.material_id == m.id)) if r]
    audit(db, user, "materials.deleted", target=m.title, target_type=PATH, target_id=m.id)
    if refs:
        db.execute(delete(StoredFile).where(StoredFile.ref.in_(refs)))
    db.execute(delete(RecordEvent).where(RecordEvent.record_type == PATH, RecordEvent.record_id == m.id))
    db.delete(m)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{material_id}/retire")
def retire_material(material_id: str, user: permitted("materials.edit"), db: DB, settings: SettingsDep) -> dict:
    m = _get(db, material_id)
    if m.status != "available":
        raise _conflict("Only a material in stock can be retired.")
    if reserved(db, m):
        raise _conflict("Some of it is still asked for or approved to give out. Record or cancel those first.")
    m.status = "retired"
    event(db, PATH, m.id, "retired", "Retired: no longer given out", user)
    audit(db, user, "materials.retired", target=m.title, target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


# --- the design ----------------------------------------------------------------------------


async def read_upload(file: UploadFile, field: str, kinds: dict[bytes, str], words: str) -> tuple[bytes, str]:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise field_error(field, "The file is over 3 MB. Save a smaller PDF or picture.")
    kind = next((v for magic, v in kinds.items() if data.startswith(magic)), None)
    if kind is None:
        raise field_error(field, words)
    return data, kind


def keep_proof(db: Session, record, data: bytes, kind: str, name: str | None) -> None:
    """Keeps the proof on a production run or distribution, in place of any before it."""
    if record.proof_ref:
        old = db.get(StoredFile, record.proof_ref)
        if old is not None:
            db.delete(old)
    record.proof_ref = secrets.token_hex(16)
    record.proof_name = (name or "proof")[:200]
    db.add(StoredFile(ref=record.proof_ref, content_type=kind, data=data))


@router.put("/{material_id}/design")
async def upload_design(
    material_id: str,
    user: permitted("materials.edit"),
    db: DB,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    notes: Annotated[str | None, Form(max_length=1000)] = None,
) -> dict:
    """The design's file: replaces a draft version's, or starts the next version once one was sent."""
    m = _get(db, material_id)
    if m.status not in DESIGNING:
        raise _conflict("A new design can be uploaded only while it's a draft or returned for changes.")
    data, kind = await read_upload(file, "file", FILE_KINDS, "Upload the design as a PDF or a picture (PNG or JPG).")
    latest = m.versions[-1] if m.versions else None
    if latest is None or latest.review != "draft":
        latest = PromoVersion(material=m, number=(latest.number + 1) if latest else 1)
        db.add(latest)
    elif latest.file_ref:
        old = db.get(StoredFile, latest.file_ref)
        if old is not None:
            db.delete(old)
    ref = secrets.token_hex(16)
    db.add(StoredFile(ref=ref, content_type=kind, data=data))
    latest.file_ref = ref
    latest.file_name = (file.filename or "design")[:200]
    latest.notes = (notes or "").strip()[:1000] or None
    m.updated_at = utcnow()
    db.flush()
    event(db, PATH, m.id, "design_uploaded", f"Design uploaded (version {latest.number}): {latest.file_name}", user)
    audit(db, user, "materials.design_uploaded", target=f"{m.title} v{latest.number}", target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


@router.get("/{material_id}/versions/{number}/file")
def design_file(material_id: str, number: int, user: permitted("materials.view"), db: DB) -> Response:
    m = _get(db, material_id)
    v = next((v for v in m.versions if v.number == number), None)
    stored = db.get(StoredFile, v.file_ref) if v and v.file_ref else None
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That version has no design file.")
    return Response(stored.data, media_type=stored.content_type, headers={"Content-Disposition": f"inline; filename*=utf-8''{url_quote(v.file_name or 'design')}"})


@router.get("/{material_id}/proofs/{ref}")
def proof_file(material_id: str, ref: str, user: permitted("materials.view"), db: DB) -> Response:
    """A proof photo, only through the material it belongs to."""
    m = _get(db, material_id)
    owner = db.scalar(select(PromoProduction).where(PromoProduction.material_id == m.id, PromoProduction.proof_ref == ref)) or db.scalar(
        select(PromoDistribution).where(PromoDistribution.material_id == m.id, PromoDistribution.proof_ref == ref)
    )
    stored = db.get(StoredFile, ref) if owner else None
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That proof isn't here any more.")
    return Response(stored.data, media_type=stored.content_type, headers={"Content-Disposition": f"inline; filename*=utf-8''{url_quote(owner.proof_name or 'proof')}"})


@router.post("/{material_id}/submit")
def submit_for_review(material_id: str, user: permitted("materials.edit"), db: DB, settings: SettingsDep) -> dict:
    """Sends the latest design to the pharmacist in Pharmacy."""
    m = _get(db, material_id)
    latest = m.versions[-1] if m.versions else None
    if m.status not in DESIGNING or latest is None or latest.review != "draft":
        raise _conflict("Upload a new design first: there is nothing new to send.")
    stored = db.get(StoredFile, latest.file_ref) if latest.file_ref else None
    if stored is None:
        raise field_error("file", "Upload the design before submitting it.")
    body = {
        "sourceId": latest.id,
        "reference": f"PM-{m.no}" if m.no else m.id[:8],
        "version": latest.number,
        "title": m.title,
        "kind": m.kind,
        "product": m.product,
        "description": m.description,
        "notes": latest.notes,
        "file": {"name": latest.file_name, "contentType": stored.content_type, "data": base64.b64encode(stored.data).decode()},
        "sentBy": user.full_name,
    }
    try:
        answer = linked.call(settings, "pharmacy", "POST", "/integration/materials", body)
    except linked.Refused as e:
        raise _conflict(str(e)) from None
    except linked.Unavailable as e:
        raise _unavailable(e) from None
    latest.review = "waiting"
    latest.sent_at = utcnow()
    latest.sent_by_name = user.full_name
    m.status = "pharmacy_review"
    m.updated_at = utcnow()
    take_review(db, m, latest, answer)
    event(db, PATH, m.id, "submitted", f"Version {latest.number} submitted for the pharmacist's review" + (f" ({latest.pharmacy_number})" if latest.pharmacy_number else ""), user)
    audit(db, user, "materials.submitted", target=f"{m.title} v{latest.number}", target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


# --- production ----------------------------------------------------------------------------


class ProductionIn(Api):
    quantity: int = Field(ge=1, le=10_000_000)
    supplier: str | None = Field(None, max_length=160)
    cost: float | None = Field(None, ge=0, le=1_000_000_000)
    ordered_on: date | None = None
    expected_on: date | None = None
    notes: str | None = Field(None, max_length=500)


def _production(db: Session, m: PromoMaterial, production_id: str) -> PromoProduction:
    p = db.get(PromoProduction, production_id)
    if p is None or p.material_id != m.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That production run isn't here any more.")
    if p.status != "ordered":
        raise _conflict("That production run is already closed.")
    return p


@router.post("/{material_id}/productions", status_code=status.HTTP_201_CREATED)
def add_production(material_id: str, user: permitted("materials.produce"), body: ProductionIn, db: DB, settings: SettingsDep) -> dict:
    m = _get(db, material_id)
    if m.status not in PRODUCIBLE:
        raise _conflict("Only a design the pharmacist approved can be produced.")
    approved = next((v for v in reversed(m.versions) if v.review == "approved"), None)
    p = PromoProduction(material_id=m.id, version_number=approved.number if approved else 1, by_name=user.full_name, **body.model_dump())
    p.ordered_on = p.ordered_on or today_in_org(settings)
    db.add(p)
    if m.status == "approved":
        m.status = "in_production"
    m.updated_at = utcnow()
    event(db, PATH, m.id, "production_ordered", f"Production of {p.quantity:,} ordered" + (f" from {p.supplier}" if p.supplier else ""), user)
    audit(db, user, "materials.production_ordered", target=m.title, target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


@router.post("/{material_id}/productions/{production_id}/received")
async def production_received(
    material_id: str,
    production_id: str,
    user: permitted("materials.produce"),
    db: DB,
    settings: SettingsDep,
    received_on: Annotated[date | None, Form(alias="receivedOn")] = None,
    proof: Annotated[UploadFile | None, File()] = None,
) -> dict:
    """Received into stock, on a day; with a photo of the delivery as proof, when there is one."""
    m = _get(db, material_id)
    p = _production(db, m, production_id)
    if proof is not None and proof.filename:
        data, kind = await read_upload(proof, "proof", PROOF_KINDS, "Attach the proof as a picture (PNG or JPG) or a PDF.")
        keep_proof(db, p, data, kind, proof.filename)
    p.status = "received"
    p.received_on = received_on or today_in_org(settings)
    m.stock += p.quantity
    if m.status in ("approved", "in_production"):
        m.status = "available"
    m.updated_at = utcnow()
    event(db, PATH, m.id, "production_received", f"{p.quantity:,} received into stock · {m.stock:,} in stock" + (" · proof attached" if p.proof_ref else ""), user)
    audit(db, user, "materials.production_received", target=m.title, target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


@router.post("/{material_id}/productions/{production_id}/cancel")
def production_cancelled(material_id: str, production_id: str, user: permitted("materials.produce"), db: DB, settings: SettingsDep) -> dict:
    m = _get(db, material_id)
    p = _production(db, m, production_id)
    p.status = "cancelled"
    still = db.scalar(select(PromoProduction.id).where(PromoProduction.material_id == m.id, PromoProduction.status == "ordered", PromoProduction.id != p.id))
    if m.status == "in_production" and not still:
        m.status = "available" if m.stock else "approved"
    m.updated_at = utcnow()
    event(db, PATH, m.id, "production_cancelled", f"Production of {p.quantity:,} cancelled", user)
    audit(db, user, "materials.production_cancelled", target=m.title, target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


# --- giving it out -------------------------------------------------------------------------


class DistributionIn(Api):
    team_id: str = Field(min_length=1, max_length=36)
    recipient_id: str | None = Field(None, max_length=36)
    quantity: int = Field(ge=1, le=10_000_000)
    purpose: str | None = Field(None, max_length=500)


def _crm_body(m: PromoMaterial, d: PromoDistribution, state: str) -> dict:
    return {
        "sourceId": d.id,
        "reference": f"PD-{d.no}" if d.no else d.id[:8],
        "material": {"no": m.no, "title": m.title, "kind": m.kind, "product": m.product},
        "teamId": d.team_id,
        "recipientId": d.recipient_id,
        "quantity": d.quantity,
        "purpose": d.purpose,
        "requestedBy": d.requested_by_name,
        "state": state,  # requested, distributed or cancelled
        "distributedOn": _iso(d.distributed_on),
    }


def _tell_crm(settings: Settings, m: PromoMaterial, d: PromoDistribution, state: str) -> None:
    """Lets the CRM know a request was given out or cancelled. A failure is kept on it, not raised."""
    try:
        linked.call(settings, "crm", "POST", "/integration/material-requests", _crm_body(m, d, state))
        d.synced_at, d.sync_error = utcnow(), None
    except (linked.Unavailable, linked.Refused) as e:
        log.warning("Distribution %s not passed to the CRM: %s", d.id, e)
        d.synced_at, d.sync_error = utcnow(), str(e)[:300]


def _distribution(db: Session, m: PromoMaterial, distribution_id: str) -> PromoDistribution:
    d = db.get(PromoDistribution, distribution_id)
    if d is None or d.material_id != m.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That distribution isn't here any more.")
    return d


@router.post("/{material_id}/distributions", status_code=status.HTTP_201_CREATED)
def ask_to_distribute(material_id: str, user: permitted("materials.distribute"), body: DistributionIn, db: DB, settings: SettingsDep) -> dict:
    """Asks the team's manager in the CRM to approve giving some out."""
    m = _get(db, material_id)
    if m.status != "available":
        raise _conflict("Only a material in stock can be given out.")
    left = m.stock - reserved(db, m)
    if body.quantity > left:
        raise field_error("quantity", f"Only {left:,} can be asked for: the rest is given out or already asked for.")
    try:
        teams = linked.call(settings, "crm", "GET", "/integration/teams").get("teams") or []
    except (linked.Unavailable, linked.Refused) as e:
        raise _unavailable(e) from None
    team = next((t for t in teams if t.get("id") == body.team_id), None)
    if team is None:
        raise field_error("teamId", "Pick a team from the list.")
    person = None
    if body.recipient_id:
        person = next((p for p in team.get("people") or [] if p.get("id") == body.recipient_id), None)
        if person is None:
            raise field_error("recipientId", "Pick someone in that team.")
    d = PromoDistribution(
        material_id=m.id, team_id=team["id"], team_name=str(team.get("name") or "Team")[:140],
        recipient_id=person["id"] if person else None, recipient_name=str(person.get("name"))[:140] if person else None,
        quantity=body.quantity, purpose=body.purpose, requested_by_name=user.full_name,
    )
    db.add(d)
    db.flush()
    try:
        answer = linked.call(settings, "crm", "POST", "/integration/material-requests", _crm_body(m, d, "requested"))
    except linked.Refused as e:
        db.rollback()
        raise _conflict(str(e)) from None
    except linked.Unavailable as e:
        db.rollback()
        raise _unavailable(e) from None
    take_decision(db, m, d, answer)
    manager = (team.get("manager") or {}).get("name")
    event(db, PATH, m.id, "distribution_requested", f"{d.quantity:,} asked for {d.recipient_name or d.team_name}" + (f" · for {manager}'s approval" if manager else ""), user)
    audit(db, user, "materials.distribution_requested", target=m.title, target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


@router.post("/{material_id}/distributions/{distribution_id}/distributed")
async def record_distributed(
    material_id: str,
    distribution_id: str,
    user: permitted("materials.distribute"),
    db: DB,
    settings: SettingsDep,
    distributed_on: Annotated[date | None, Form(alias="distributedOn")] = None,
    proof: Annotated[UploadFile | None, File()] = None,
) -> dict:
    """Given out, on a day; with a photo of the hand-over or the signed receipt as proof, when there is one."""
    m = _get(db, material_id)
    d = _distribution(db, m, distribution_id)
    if d.status != "approved":
        raise _conflict("Only a distribution the manager approved can be recorded as given out.")
    if d.quantity > m.stock:
        raise _conflict(f"Only {m.stock:,} are in stock.")
    if proof is not None and proof.filename:
        data, kind = await read_upload(proof, "proof", PROOF_KINDS, "Attach the proof as a picture (PNG or JPG) or a PDF.")
        keep_proof(db, d, data, kind, proof.filename)
    d.status = "distributed"
    d.distributed_on = distributed_on or today_in_org(settings)
    m.stock -= d.quantity
    m.updated_at = utcnow()
    _tell_crm(settings, m, d, "distributed")
    event(db, PATH, m.id, "distributed", f"{d.quantity:,} given to {d.recipient_name or d.team_name} · {m.stock:,} left in stock" + (" · proof attached" if d.proof_ref else ""), user)
    audit(db, user, "materials.distributed", target=m.title, target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)


@router.post("/{material_id}/distributions/{distribution_id}/cancel")
def cancel_distribution(material_id: str, distribution_id: str, user: permitted("materials.distribute"), db: DB, settings: SettingsDep) -> dict:
    m = _get(db, material_id)
    d = _distribution(db, m, distribution_id)
    if d.status not in HOLDING:
        raise _conflict("That distribution is already closed.")
    d.status = "cancelled"
    m.updated_at = utcnow()
    _tell_crm(settings, m, d, "cancelled")
    event(db, PATH, m.id, "distribution_cancelled", f"Request for {d.quantity:,} for {d.recipient_name or d.team_name} cancelled", user)
    audit(db, user, "materials.distribution_cancelled", target=m.title, target_type=PATH, target_id=m.id)
    db.commit()
    return one_out(db, settings, m, user)
