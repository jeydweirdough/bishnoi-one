"""Saved reports, for every module (decided 2026-10-26): a report someone built from one of a
module's reports, kept here once rather than in each module. Only the choices are kept (columns,
filters, grouping, sorting, chart), never data; the one app runs the module's report with the
viewer's own access and applies them, so a shared report never shows anyone more than they may see.

- GET    /identity/reports?app=crm: mine, and those shared at my company, for one module.
- POST   /identity/reports: save one.
- PATCH  /identity/reports/{id}: change it (its owner).
- DELETE /identity/reports/{id}: remove it (its owner, or a company administrator).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import or_, select

from app.api import Api, changed, not_found
from app.audit import audit
from app.deps import DB
from app.models import Identity, SavedReport
from app.routers.identity import Signed

router = APIRouter(prefix="/identity/reports", tags=["saved reports"])

MAX_DEFINITION = 20_000  # characters of choices: far more than any report needs


class ReportIn(Api):
    app: str = Field(min_length=1, max_length=40)
    base_key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    definition: dict = {}
    shared: bool = False


class ReportPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=120)
    definition: dict | None = None
    shared: bool | None = None


def out(r: SavedReport, me: Identity, owners: dict[str, str]) -> dict:
    return {
        "id": r.id, "app": r.app_key, "baseKey": r.base_key, "name": r.name, "definition": r.definition or {}, "shared": r.shared,
        "mine": r.owner_id == me.id, "owner": owners.get(r.owner_id, "Someone"), "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
    }


def checked(definition: dict) -> dict:
    import json

    if len(json.dumps(definition)) > MAX_DEFINITION:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That report has too many choices to keep.")
    return definition


@router.get("")
def list_reports(signed: Signed, db: DB, app: str = Query(..., max_length=40)) -> list[dict]:
    _, me = signed
    rows = db.scalars(
        select(SavedReport)
        .where(SavedReport.company_id == me.company_id, SavedReport.app_key == app, or_(SavedReport.owner_id == me.id, SavedReport.shared))
        .order_by(SavedReport.name)
    ).all()
    owners = {i.id: i.full_name for i in db.scalars(select(Identity).where(Identity.id.in_({r.owner_id for r in rows})))} if rows else {}
    return [out(r, me, owners) for r in rows]


@router.get("/{report_id}")
def read_report(report_id: str, signed: Signed, db: DB) -> dict:
    _, me = signed
    r = db.get(SavedReport, report_id)
    if r is None or r.company_id != me.company_id or not (r.shared or r.owner_id == me.id):
        raise not_found("report")
    owner = db.get(Identity, r.owner_id)
    return out(r, me, {r.owner_id: owner.full_name if owner else "Someone"})


@router.post("", status_code=status.HTTP_201_CREATED)
def save_report(body: ReportIn, signed: Signed, db: DB) -> dict:
    _, me = signed
    r = SavedReport(company_id=me.company_id, owner_id=me.id, app_key=body.app, base_key=body.base_key, name=body.name.strip(), definition=checked(body.definition), shared=body.shared)
    db.add(r)
    db.flush()
    audit(db, me.email, "report.saved", target=r.name, target_type="saved_report", target_id=r.id, company_id=me.company_id)
    db.commit()
    return out(r, me, {me.id: me.full_name})


@router.patch("/{report_id}")
def change_report(report_id: str, body: ReportPatch, signed: Signed, db: DB) -> dict:
    _, me = signed
    r = db.get(SavedReport, report_id)
    if r is None or r.company_id != me.company_id or r.owner_id != me.id:
        raise not_found("report")
    fields = {k: v for k, v in changed(body).items() if v is not None}
    if "definition" in fields:
        r.definition = checked(fields["definition"])
    if "name" in fields:
        r.name = fields["name"].strip()
    if "shared" in fields:
        r.shared = fields["shared"]
    if fields:
        r.updated_at = datetime.now(UTC)
        audit(db, me.email, "report.changed", target=r.name, target_type="saved_report", target_id=r.id, company_id=me.company_id, fields=sorted(fields))
        db.commit()
    return out(r, me, {me.id: me.full_name})


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: str, signed: Signed, db: DB) -> Response:
    _, me = signed
    r = db.get(SavedReport, report_id)
    if r is None or r.company_id != me.company_id or not (r.owner_id == me.id or me.is_company_admin):
        raise not_found("report")
    audit(db, me.email, "report.deleted", target=r.name, target_type="saved_report", target_id=r.id, company_id=me.company_id)
    db.delete(r)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
