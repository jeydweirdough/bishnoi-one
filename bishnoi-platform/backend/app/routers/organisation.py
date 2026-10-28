"""The company's org chart and branches, kept by its own administrators (feature plan step 4,
agreed 2026-10-28): one chart for the whole company, edited here only (the CRM's teams follow it).
The one app's /platform/organisation screen uses these.

- GET   /identity/organisation: units, branches, and where each person sits.
- POST  /identity/organisation/units, PATCH …/units/{id}: divisions, departments, teams
  (switched off, never deleted).
- POST  /identity/organisation/branches, PATCH …/branches/{id}.
- PUT   /identity/organisation/people/{id}: a person's main unit, other units and branch.

Every change is in the audit log (names of what changed, never values).
"""

from typing import Literal

from fastapi import APIRouter, Request, status
from pydantic import Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api import Api, changed, conflict, field_error, not_found
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import Branch, Identity, MembershipUnit, Unit
from app.routers.company_access import Admin, get_person
from app import org_push

router = APIRouter(prefix="/identity/organisation", tags=["organisation"])

Kind = Literal["division", "department", "team"]


def unit_out(u: Unit, people: int = 0) -> dict:
    return {"id": u.id, "kind": u.kind, "name": u.name, "parentId": u.parent_id, "managerId": u.manager_id,
            "areas": u.areas or [], "isActive": u.is_active, "people": people}


def branch_out(b: Branch, people: int = 0) -> dict:
    return {"id": b.id, "name": b.name, "address": b.address, "isActive": b.is_active, "people": people}


@router.get("")
def overview(db: DB, me: Admin) -> dict:
    members = db.scalars(select(Identity).where(Identity.company_id == me.company_id, Identity.via_operator.is_(False))
                         .order_by(func.lower(Identity.full_name))).all()
    others: dict[str, list[str]] = {}
    for m in db.scalars(select(MembershipUnit).join(Identity, Identity.id == MembershipUnit.membership_id).where(Identity.company_id == me.company_id)):
        others.setdefault(m.membership_id, []).append(m.unit_id)
    in_unit: dict[str, int] = {}
    in_branch: dict[str, int] = {}
    for p in members:
        if p.status == "active":
            if p.main_unit_id:
                in_unit[p.main_unit_id] = in_unit.get(p.main_unit_id, 0) + 1
            if p.branch_id:
                in_branch[p.branch_id] = in_branch.get(p.branch_id, 0) + 1
    units = db.scalars(select(Unit).where(Unit.company_id == me.company_id).order_by(func.lower(Unit.name))).all()
    branches = db.scalars(select(Branch).where(Branch.company_id == me.company_id).order_by(func.lower(Branch.name))).all()
    return {
        "units": [unit_out(u, in_unit.get(u.id, 0)) for u in units],
        "branches": [branch_out(b, in_branch.get(b.id, 0)) for b in branches],
        "people": [{"id": p.id, "fullName": p.full_name, "email": p.email, "title": p.title, "status": p.status,
                    "mainUnitId": p.main_unit_id, "otherUnitIds": others.get(p.id, []), "branchId": p.branch_id} for p in members],
        "notPlaced": sum(1 for p in members if p.status == "active" and not p.main_unit_id),
    }


# ---- Units --------------------------------------------------------------------------------------


class UnitIn(Api):
    kind: Kind
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None
    manager_id: str | None = None
    areas: list[str] = Field(default_factory=list, max_length=100)


class UnitPatch(Api):
    kind: Kind | None = None
    name: str | None = Field(None, min_length=1, max_length=120)
    parent_id: str | None = None
    manager_id: str | None = None
    areas: list[str] | None = Field(None, max_length=100)
    is_active: bool | None = None


def get_unit(db: Session, me: Identity, unit_id: str) -> Unit:
    u = db.get(Unit, unit_id)
    if u is None or u.company_id != me.company_id:
        raise not_found("unit")
    return u


def check_parent(db: Session, me: Identity, unit_id: str | None, parent_id: str | None) -> None:
    """The unit above must be the company's, and never the unit itself or one under it."""
    seen = set()
    at = parent_id
    while at:
        if at == unit_id or at in seen:
            raise field_error("parent_id", "A unit can't sit under itself or under one of its own units.")
        seen.add(at)
        at = get_unit(db, me, at).parent_id


def check_name(db: Session, me: Identity, name: str, parent_id: str | None, other_than: str | None = None) -> None:
    query = select(Unit.id).where(Unit.company_id == me.company_id, func.lower(Unit.name) == name.lower(),
                                  Unit.parent_id.is_(None) if parent_id is None else Unit.parent_id == parent_id)
    if other_than:
        query = query.where(Unit.id != other_than)
    if db.scalar(query):
        raise field_error("name", "There's already a unit with that name here.")


def check_manager(db: Session, me: Identity, manager_id: str | None) -> None:
    if manager_id:
        get_person(db, me, manager_id)


def clean(areas: list[str]) -> list[str]:
    return list(dict.fromkeys(a.strip() for a in areas if a and a.strip()))


@router.post("/units", status_code=status.HTTP_201_CREATED)
def add_unit(body: UnitIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    name = body.name.strip()
    check_parent(db, me, None, body.parent_id)
    check_name(db, me, name, body.parent_id)
    check_manager(db, me, body.manager_id)
    u = Unit(company_id=me.company_id, kind=body.kind, name=name, parent_id=body.parent_id, manager_id=body.manager_id, areas=clean(body.areas))
    db.add(u)
    db.flush()
    audit(db, me.email, "organisation.unit_added", target=u.name, target_type="unit", target_id=u.id, company_id=me.company_id)
    db.commit()
    org_push.push(request.app.state.sessions, settings, me.company_id)
    return {"unit": unit_out(u)}


@router.patch("/units/{unit_id}")
def change_unit(unit_id: str, body: UnitPatch, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    u = get_unit(db, me, unit_id)
    fields = changed(body)
    if "parent_id" in fields:
        check_parent(db, me, u.id, fields["parent_id"])
    if "name" in fields or "parent_id" in fields:
        check_name(db, me, (fields.get("name") or u.name).strip(), fields.get("parent_id", u.parent_id), other_than=u.id)
    if "manager_id" in fields:
        check_manager(db, me, fields["manager_id"])
    if fields.get("is_active") is False and db.scalar(select(func.count()).select_from(Unit).where(Unit.parent_id == u.id, Unit.is_active)):
        raise conflict("Units still sit under this one. Move or switch them off first.")
    for name, value in fields.items():
        if name in ("kind", "name", "is_active") and value is None:
            continue
        setattr(u, name, clean(value) if name == "areas" else value.strip() if name == "name" else value)
    if fields:
        audit(db, me.email, "organisation.unit_changed", target=u.name, target_type="unit", target_id=u.id, company_id=me.company_id, fields=sorted(fields))
        db.commit()
        org_push.push(request.app.state.sessions, settings, me.company_id)
    return {"unit": unit_out(u)}


# ---- Branches -----------------------------------------------------------------------------------


class BranchIn(Api):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(None, max_length=200)


class BranchPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=120)
    address: str | None = Field(None, max_length=200)
    is_active: bool | None = None


def get_branch(db: Session, me: Identity, branch_id: str) -> Branch:
    b = db.get(Branch, branch_id)
    if b is None or b.company_id != me.company_id:
        raise not_found("branch")
    return b


def branch_name_taken(db: Session, me: Identity, name: str, other_than: str | None = None) -> bool:
    query = select(Branch.id).where(Branch.company_id == me.company_id, func.lower(Branch.name) == name.lower())
    return bool(db.scalar(query.where(Branch.id != other_than) if other_than else query))


@router.post("/branches", status_code=status.HTTP_201_CREATED)
def add_branch(body: BranchIn, db: DB, me: Admin) -> dict:
    name = body.name.strip()
    if branch_name_taken(db, me, name):
        raise field_error("name", "There's already a branch with that name.")
    b = Branch(company_id=me.company_id, name=name, address=(body.address or "").strip() or None)
    db.add(b)
    db.flush()
    audit(db, me.email, "organisation.branch_added", target=b.name, target_type="branch", target_id=b.id, company_id=me.company_id)
    db.commit()
    return {"branch": branch_out(b)}


@router.patch("/branches/{branch_id}")
def change_branch(branch_id: str, body: BranchPatch, db: DB, me: Admin) -> dict:
    b = get_branch(db, me, branch_id)
    fields = {k: v for k, v in changed(body).items() if not (k in ("name", "is_active") and v is None)}
    if "name" in fields and branch_name_taken(db, me, fields["name"].strip(), other_than=b.id):
        raise field_error("name", "There's already a branch with that name.")
    for name, value in fields.items():
        setattr(b, name, value.strip() or None if isinstance(value, str) else value)
    if fields:
        audit(db, me.email, "organisation.branch_changed", target=b.name, target_type="branch", target_id=b.id, company_id=me.company_id, fields=sorted(fields))
        db.commit()
    return {"branch": branch_out(b)}


# ---- Where people sit ---------------------------------------------------------------------------


class PlacementIn(Api):
    main_unit_id: str | None = None
    other_unit_ids: list[str] = Field(default_factory=list, max_length=50)
    branch_id: str | None = None


@router.put("/people/{person_id}")
def place_person(person_id: str, body: PlacementIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    p = get_person(db, me, person_id)
    for unit_id in [body.main_unit_id, *body.other_unit_ids]:
        if unit_id and not get_unit(db, me, unit_id).is_active:
            raise field_error("main_unit_id" if unit_id == body.main_unit_id else "other_unit_ids", "That unit is switched off.")
    if body.branch_id:
        get_branch(db, me, body.branch_id)
    others = [u for u in dict.fromkeys(body.other_unit_ids) if u != body.main_unit_id]
    p.main_unit_id, p.branch_id = body.main_unit_id, body.branch_id
    db.execute(delete(MembershipUnit).where(MembershipUnit.membership_id == p.id))
    for unit_id in others:
        db.add(MembershipUnit(membership_id=p.id, unit_id=unit_id))
    audit(db, me.email, "organisation.person_placed", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id,
          fields=["mainUnit", "otherUnits", "branch"])
    db.commit()
    org_push.push(request.app.state.sessions, settings, me.company_id)
    return {"id": p.id, "mainUnitId": p.main_unit_id, "otherUnitIds": others, "branchId": p.branch_id}
