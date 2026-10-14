"""Government assistance applications (PAP, Rx playbook KPI 3) a field agent
files for a doctor's patient on a GetMeds product.

Every approved application is a point for the month it was approved; a denied
one counts for nothing, but one sent again and approved counts then. So an
approval needs its confirmation receipt, and the month it falls in is the day
it was approved. Pending ones are followed up weekly until they're decided.

- GET /assistance?status=&month=: the applications within reach, the month's
  counts, and the products and programs to pick from.
- POST /assistance: one filed (visits.create): the doctor must be one's own.
- PATCH /assistance/{id}: approved (with the receipt), denied, or sent again.
- DELETE /assistance/{id}: one filed by mistake, while still pending.
- POST /assistance/{id}/files: the patient's IDs, or other documents (the
  form, the prescription...), several at a time; GET and DELETE
  /assistance/{id}/files/{n}: one of them. PDF, JPG or PNG, up to 10 MB each.

visits.view / create / edit, within the person's reach.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import Field
from sqlalchemy import func, select

from app.access import Access, require
from app.api import Api, field_error, iso, not_found, person_out
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import AssistanceApplication, Company, Product, StoredFile
from app.routers.field import local_day, month_or_now, this_month
from app.scope import reaches, within

router = APIRouter(prefix="/assistance", tags=["field work"])

View = Annotated[Access, Depends(require("visits.view"))]
Create = Annotated[Access, Depends(require("visits.create"))]
Edit = Annotated[Access, Depends(require("visits.edit"))]

Program = Literal["dswd", "pcso", "ovp", "yakap"]
Status = Literal["pending", "approved", "denied"]

# The four programs, as the playbook teaches them: what each gives, and how long it takes.
PROGRAMS = [
    {"key": "dswd", "name": "DSWD Medical Assistance (AICS)", "gives": "₱50,000 to ₱100,000 an application", "days": "7 to 14 working days"},
    {"key": "pcso", "name": "PCSO Individual Medical Assistance (IMAP)", "gives": "Up to ₱300,000 a year a patient", "days": "7 to 14 days"},
    {"key": "ovp", "name": "Office of the Vice President", "gives": "Varies by case", "days": "Varies"},
    {"key": "yakap", "name": "YAKAP / DOH", "gives": "25% to 50% of the cost", "days": "Same day to 3 days"},
]


def out(a: AssistanceApplication) -> dict:
    return {
        "id": a.id,
        "program": a.program,
        "patientName": a.patient_name,
        "doctor": {"id": a.company.id, "name": a.company.name},
        "products": a.products or [],
        "submittedOn": a.submitted_on,
        "status": a.status,
        "decidedOn": a.decided_on,
        "receiptNo": a.receipt_no,
        "notes": a.notes,
        "attachments": [{"n": n, "kind": f["kind"], "name": f["name"], "contentType": f["contentType"], "size": f["size"]} for n, f in enumerate(a.attachments or [])],
        "owner": person_out(a.owner),
        "updatedAt": iso(a.updated_at),
    }


def today_of(settings) -> date:
    """Today, the company's own."""
    return date.fromisoformat(local_day(datetime.now(UTC), settings))


def mine(db, access: Access, application_id: str) -> AssistanceApplication:
    a = db.get(AssistanceApplication, application_id)
    if a is None or not reaches(a, access):
        raise not_found("application")
    return a


@router.get("")
def list_applications(
    access: View,
    db: DB,
    settings: SettingsDep,
    status_: Status | None = Query(None, alias="status"),
    month: str | None = Query(None, max_length=7),
) -> dict:
    month = month_or_now(month, settings)
    query = within(select(AssistanceApplication), AssistanceApplication, access)
    every = db.scalars(query).unique().all()
    shown = [a for a in every if not status_ or a.status == status_]
    # Pending first, oldest first (they need following up), then the decided, newest first.
    pending = sorted((a for a in shown if a.status == "pending"), key=lambda a: a.submitted_on)
    decided = sorted((a for a in shown if a.status != "pending"), key=lambda a: a.decided_on or a.submitted_on, reverse=True)
    shown = pending + decided
    products = db.scalars(select(Product).where(Product.is_active).order_by(func.lower(Product.name)))
    return {
        "month": month,
        "thisMonth": this_month(settings),
        "items": [out(a) for a in shown],
        "counts": {
            "pending": sum(1 for a in every if a.status == "pending"),
            # The month's points: approved in it.
            "approved": sum(1 for a in every if a.status == "approved" and (a.decided_on or "").startswith(month)),
            "denied": sum(1 for a in every if a.status == "denied" and (a.decided_on or "").startswith(month)),
            "submitted": sum(1 for a in every if a.submitted_on.startswith(month)),
        },
        "programs": PROGRAMS,
        "products": [{"id": p.id, "name": p.name, "strength": p.strength} for p in products],
        "can": {"file": access.can("visits.create"), "edit": access.can("visits.edit")},
    }


class ApplicationIn(Api):
    program: Program
    patient_name: str = Field(min_length=2, max_length=120)
    company_id: str = Field(max_length=36)
    # The products it's for, at least one.
    product_ids: list[str] = Field(min_length=1, max_length=10)
    submitted_on: date
    notes: str | None = Field(None, max_length=2000)


@router.post("", status_code=status.HTTP_201_CREATED)
def file_application(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, body: ApplicationIn) -> dict:
    doctor = db.get(Company, body.company_id)
    if doctor is None or not reaches(doctor, access):
        raise field_error("companyId", "Pick one of your doctors.")
    products = []
    for n, pid in enumerate(dict.fromkeys(body.product_ids)):
        product = db.get(Product, pid)
        if product is None:
            raise field_error(f"productIds.{n}", "Pick GetMeds products from the list.")
        products.append({"id": product.id, "name": product.name})
    if body.submitted_on > today_of(settings):
        raise field_error("submittedOn", "Log it once it's been handed in.")
    a = AssistanceApplication(
        program=body.program,
        patient_name=" ".join(body.patient_name.split()),
        company_id=doctor.id,
        products=products,
        submitted_on=body.submitted_on.isoformat(),
        notes=(body.notes or "").strip() or None,
        owner_id=me.id,
        team_id=me.team_id,
        created_by_id=me.id,
    )
    db.add(a)
    db.flush()
    audit(db, me, "assistance.filed", target=doctor.name, target_type="assistance", target_id=a.id)
    db.commit()
    db.refresh(a)
    return out(a)


class DecisionIn(Api):
    status: Status
    # On an approval: the confirmation receipt (it's what scores the point), and the day.
    receipt_no: str | None = Field(None, max_length=60)
    decided_on: date | None = None
    # Sent again after a denial: when.
    submitted_on: date | None = None
    notes: str | None = Field(None, max_length=2000)


@router.patch("/{application_id}")
def decide(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, application_id: str, body: DecisionIn) -> dict:
    a = mine(db, access, application_id)
    today = today_of(settings)
    if body.decided_on and body.decided_on > today:
        raise field_error("decidedOn", "That day hasn't come yet.")
    if body.status == "approved":
        receipt = (body.receipt_no or "").strip()
        if not receipt:
            raise field_error("receiptNo", "Enter the confirmation receipt number: the approval counts with it.")
        a.status, a.receipt_no, a.decided_on = "approved", receipt, (body.decided_on or today).isoformat()
    elif body.status == "denied":
        a.status, a.receipt_no, a.decided_on = "denied", None, (body.decided_on or today).isoformat()
    else:
        # Pending again: sent again after a denial (or a decision undone).
        a.status, a.receipt_no, a.decided_on = "pending", None, None
        if body.submitted_on:
            a.submitted_on = body.submitted_on.isoformat()
    if body.notes is not None:
        a.notes = body.notes.strip() or None
    audit(db, me, f"assistance.{a.status}", target=a.company.name, target_type="assistance", target_id=a.id)
    db.commit()
    db.refresh(a)
    return out(a)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw(access: Edit, me: CurrentUser, db: DB, application_id: str) -> Response:
    a = mine(db, access, application_id)
    if a.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a pending application can be taken back: a decided one is the record.")
    audit(db, me, "assistance.withdrawn", target=a.company.name, target_type="assistance", target_id=a.id)
    for f in a.attachments or []:
        if f.get("store") == "db" and (stored := db.get(StoredFile, f["ref"])):
            db.delete(stored)
    db.delete(a)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


MAX_FILES = 12


@router.post("/{application_id}/files")
def attach(
    access: Edit,
    me: CurrentUser,
    db: DB,
    application_id: str,
    kind: Annotated[Literal["id", "document"], Form()],
    files: Annotated[list[UploadFile], File()],
) -> dict:
    """Files on the application: the patient's IDs, or other documents. Each
    must really be a PDF or a photo (told by its first bytes), up to 10 MB."""
    from app.routers.quote_links import kept_upload

    a = mine(db, access, application_id)
    kept = list(a.attachments or [])
    if len(kept) + len(files) > MAX_FILES:
        raise field_error("files", f"An application keeps up to {MAX_FILES} files.")
    for upload in files:
        entry, data = kept_upload(upload, "files")
        db.add(StoredFile(ref=entry["ref"], content_type=entry["contentType"], data=data))
        kept.append({"kind": kind, **entry})
    a.attachments = kept
    audit(db, me, "assistance.files_added", target=a.company.name, target_type="assistance", target_id=a.id)
    db.commit()
    db.refresh(a)
    return out(a)


@router.get("/{application_id}/files/{n}")
def read_file(access: View, db: DB, settings: SettingsDep, application_id: str, n: int) -> Response:
    from app.routers.quotes import file_response

    files = mine(db, access, application_id).attachments or []
    return file_response(db, settings, files[n] if 0 <= n < len(files) else None, "This application has no such file.")


@router.delete("/{application_id}/files/{n}")
def remove_file(access: Edit, me: CurrentUser, db: DB, application_id: str, n: int) -> dict:
    a = mine(db, access, application_id)
    files = list(a.attachments or [])
    if not 0 <= n < len(files):
        raise not_found("file")
    gone = files.pop(n)
    if gone.get("store") == "db" and (stored := db.get(StoredFile, gone["ref"])):
        db.delete(stored)
    a.attachments = files
    audit(db, me, "assistance.file_removed", target=a.company.name, target_type="assistance", target_id=a.id)
    db.commit()
    db.refresh(a)
    return out(a)
