"""HR records on employees (2026-11-18, step 4I, owner-approved): labelled details (SSS no., Pag-IBIG no.,
PhilHealth no., TIN, date hired, any label HR adds) and documents (contracts, NBI clearance, background checks).

Only the company's administrators (accounts.runs_company) and holders of the "Manage HR records" ability
(abilities.py, key hr.records, on their Platform role) read or change them. Nobody else, not even the employee
themself. Every change and every opening of a document is in the audit log, with labels only, never values.
They are never sent to the apps.

    GET    /identity/access/hr/people                       the employees, for HR holders who aren't administrators
    GET    /identity/access/people/{id}/hr                  details + document list
    PUT    /identity/access/people/{id}/hr                  {details: [{label, value}]}: the whole list, in order
    POST   /identity/access/people/{id}/hr/documents        multipart: file, label, expiresOn (optional, YYYY-MM-DD)
    GET    /identity/access/people/{id}/hr/documents/{doc}  the file (inline, never cached)
    DELETE /identity/access/people/{id}/hr/documents/{doc}
"""

import io
import zipfile
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.platform.accounts import account_of, runs_company
from modules.platform.api import Api, conflict, field_error, iso, not_found
from modules.platform.audit import audit
from modules.platform.deps import DB, SettingsDep
from modules.platform.models import AccessRoleAbility, HrDocument, Identity
from modules.platform import sign_in
from modules.platform.routers.identity import Signed

router = APIRouter(prefix="/identity/access", tags=["hr records"])

ABILITY = "hr.records"
# The labels offered first; HR may add any other.
SUGGESTED_DETAILS = ("SSS no.", "Pag-IBIG no.", "PhilHealth no.", "TIN", "Date hired", "Employment status", "Emergency contact")
SUGGESTED_DOCUMENTS = ("Contract", "NBI clearance", "Background check", "Medical certificate", "Diploma", "Valid ID")
MAX_DETAILS, MAX_LABEL, MAX_VALUE = 50, 60, 500
MAX_BYTES, MAX_DOCUMENTS = 10_000_000, 50
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def may_keep_hr(db: Session, person: Identity) -> bool:
    """Whether this person may read and change the company's HR records: its administrators, and anyone whose
    Platform role holds "Manage HR records"."""
    if runs_company(db, person):
        return True
    if not person.access_role_id:
        return False
    return db.get(AccessRoleAbility, (person.access_role_id, ABILITY)) is not None


def hr_keeper(signed: Signed, db: DB, settings: SettingsDep) -> Identity:
    _, me = signed
    if not may_keep_hr(db, me):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only HR and your company's administrators see HR records. Employees don't see their own.")
    # Like administrators, they change nothing until their own sign-in has two steps, where that's required.
    if sign_in.needs_two_step(settings, account_of(db, me), True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Set up two-step sign-in first: Your profile, Two-step sign-in. HR records need it.")
    return me


Keeper = Annotated[Identity, Depends(hr_keeper)]


def employee(db: Session, me: Identity, person_id: str) -> Identity:
    p = db.get(Identity, person_id)
    if p is None or p.company_id != me.company_id or p.via_operator:
        raise not_found("employee")
    return p


def document_out(d: HrDocument) -> dict:
    return {"id": d.id, "label": d.label, "fileName": d.file_name, "contentType": d.content_type, "size": d.size,
            "uploadedBy": d.uploaded_by, "uploadedAt": iso(d.uploaded_at), "expiresOn": d.expires_on.isoformat() if d.expires_on else None}


def records_out(db: Session, p: Identity) -> dict:
    docs = db.scalars(select(HrDocument).where(HrDocument.identity_id == p.id).order_by(func.lower(HrDocument.label), HrDocument.uploaded_at.desc())).all()
    return {
        "id": p.id,
        "details": [{"label": k, "value": v} for k, v in (p.hr_details or {}).items()],
        "documents": [document_out(d) for d in docs],
        "suggestedDetails": list(SUGGESTED_DETAILS),
        "suggestedDocuments": list(SUGGESTED_DOCUMENTS),
    }


@router.get("/hr/people")
def hr_people(db: DB, me: Keeper) -> dict:
    """The company's employees (not the recycle bin's), for picking whose HR records to open."""
    rows = db.scalars(select(Identity).where(Identity.company_id == me.company_id, Identity.via_operator.is_(False), Identity.deleted_at.is_(None))
                      .order_by(func.lower(Identity.full_name))).all()
    return {"people": [{"id": p.id, "fullName": p.full_name, "email": p.email, "title": p.title, "status": p.status} for p in rows]}


@router.get("/people/{person_id}/hr")
def read_records(person_id: str, db: DB, me: Keeper) -> dict:
    p = employee(db, me, person_id)
    audit(db, me.email, "hr.records_viewed", category="security", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    return records_out(db, p)


class DetailIn(Api):
    label: str | None = Field(None, max_length=200)
    value: str | None = Field(None, max_length=2000)


class DetailsIn(Api):
    details: list[DetailIn] = Field(max_length=200)


def clean(given: list[DetailIn]) -> dict[str, str]:
    out: dict[str, str] = {}
    seen: set[str] = set()
    for d in given:
        label, value = (d.label or "").strip(), (d.value or "").strip()
        if not label and not value:
            continue
        if not label:
            raise field_error("details", "Give every detail a label.")
        if len(label) > MAX_LABEL:
            raise field_error("details", f"Keep a label to {MAX_LABEL} characters.")
        if len(value) > MAX_VALUE:
            raise field_error("details", f"Keep {label} to {MAX_VALUE} characters.")
        if label.lower() in seen:
            raise field_error("details", f"{label} is there twice. Keep one.")
        seen.add(label.lower())
        if value:
            out[label] = value
    if len(out) > MAX_DETAILS:
        raise field_error("details", f"Keep at most {MAX_DETAILS} details.")
    return out


@router.put("/people/{person_id}/hr")
def save_details(person_id: str, body: DetailsIn, db: DB, me: Keeper) -> dict:
    p = employee(db, me, person_id)
    before = p.hr_details or {}
    after = clean(body.details)
    changed = sorted({k for k in set(before) | set(after) if before.get(k) != after.get(k)})
    if changed or list(before) != list(after):
        p.hr_details = after or None
        # The labels changed, never what they hold.
        audit(db, me.email, "hr.details_changed", category="security", target=p.email, target_type="identity", target_id=p.id,
              company_id=me.company_id, fields=changed or ["order"])
        db.commit()
    return records_out(db, p)


def sniff(data: bytes) -> str | None:
    """The file's real type by its first bytes; None when it's none of PDF, PNG, JPEG or a Word document."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if "word/document.xml" in z.namelist():
                    return DOCX
        except zipfile.BadZipFile:
            return None
    return None


@router.post("/people/{person_id}/hr/documents", status_code=status.HTTP_201_CREATED)
async def add_document(person_id: str, db: DB, me: Keeper, file: UploadFile = File(...), label: str = Form(""),
                       expires_on: str = Form("", alias="expiresOn")) -> dict:
    p = employee(db, me, person_id)
    label = label.strip()
    if not label:
        raise field_error("label", "Say what it is, for example Contract.")
    if len(label) > MAX_LABEL:
        raise field_error("label", f"Keep the label to {MAX_LABEL} characters.")
    expires: date | None = None
    if expires_on.strip():
        try:
            expires = date.fromisoformat(expires_on.strip())
        except ValueError:
            raise field_error("expiresOn", "Give the expiry date as a date.") from None
    if (db.scalar(select(func.count()).select_from(HrDocument).where(HrDocument.identity_id == p.id)) or 0) >= MAX_DOCUMENTS:
        raise conflict(f"{p.full_name} already has {MAX_DOCUMENTS} documents. Remove one first.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Keep a file to 10 MB.")
    if not data:
        raise field_error("file", "That file is empty.")
    kind = sniff(data)
    if kind is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use a PDF, a PNG or JPEG picture, or a Word document (.docx).")
    d = HrDocument(identity_id=p.id, label=label, file_name=(file.filename or "document")[:200], content_type=kind, data=data, size=len(data),
                   uploaded_by=me.email, expires_on=expires)
    db.add(d)
    audit(db, me.email, "hr.document_added", category="security", target=f"{p.email} · {label}", target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    return document_out(d)


def document_of(db: Session, p: Identity, doc_id: str) -> HrDocument:
    d = db.get(HrDocument, doc_id)
    if d is None or d.identity_id != p.id:
        raise not_found("document")
    return d


@router.get("/people/{person_id}/hr/documents/{doc_id}")
def open_document(person_id: str, doc_id: str, db: DB, me: Keeper) -> Response:
    p = employee(db, me, person_id)
    d = document_of(db, p, doc_id)
    audit(db, me.email, "hr.document_opened", category="security", target=f"{p.email} · {d.label}", target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    safe = d.file_name.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(d.data, media_type=d.content_type, headers={
        "Content-Disposition": f"inline; filename=\"{safe.encode('ascii', 'replace').decode()}\"; filename*=UTF-8''{quote(safe)}",
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/people/{person_id}/hr/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(person_id: str, doc_id: str, db: DB, me: Keeper) -> Response:
    p = employee(db, me, person_id)
    d = document_of(db, p, doc_id)
    audit(db, me.email, "hr.document_removed", category="security", target=f"{p.email} · {d.label}", target_type="identity", target_id=p.id, company_id=me.company_id)
    db.delete(d)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def erase_of(db: Session, p: Identity) -> None:
    """Their HR records go with them when they're deleted permanently (company_access.erase_person)."""
    for d in db.scalars(select(HrDocument).where(HrDocument.identity_id == p.id)):
        db.delete(d)
    p.hr_details = None
