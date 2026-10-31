"""Customer types: what kind of customer a company is (Prospect, Customer,
Partner...). Anyone signed in reads the list; changing it needs admin.types.

A type in use can't be deleted, only switched off: the companies that have it
keep it, but it isn't offered for new ones.
"""

import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import Access, require, settings_change
from app.api import Api, camel, changed, field_error, not_found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.extra import ANY_TEAM, applies
from app.models import Company, CustomerType, Team

router = APIRouter(tags=["customer types"])

Manage = Annotated[Access, Depends(settings_change("admin.types"))]
Color = Literal["gray", "brand", "green", "blue", "amber", "red", "purple", "muted"]  # app.models.CUSTOMER_COLORS


def type_out(t: CustomerType, used: int = 0) -> dict:
    return {
        "code": t.code,
        "name": t.name,
        "color": t.color,
        "sortOrder": t.sort_order,
        "isActive": t.is_active,
        "companies": used,
        "onlyTeams": t.only_teams or [],
        "exceptTeams": t.except_teams or [],
    }


def all_types(db: Session) -> list[dict]:
    used = dict(db.execute(select(Company.status, func.count()).group_by(Company.status)).all())
    return [type_out(t, used.get(t.code, 0)) for t in db.scalars(select(CustomerType).order_by(CustomerType.sort_order, CustomerType.name))]


def check_type(db: Session, code: str | None, *, team_id=ANY_TEAM) -> str:
    """The type a company is being given, if it's one on offer to its team."""
    found = db.get(CustomerType, code or "")
    if found is None or not found.is_active or not applies(found, team_id):
        raise field_error("status", "Pick a type from the list.")
    return found.code


def first_type(db: Session, *, team_id=ANY_TEAM) -> str:
    """What a new company is when nobody says: the first type on its team's list."""
    offered = db.scalars(select(CustomerType).where(CustomerType.is_active).order_by(CustomerType.sort_order, CustomerType.name))
    code = next((t.code for t in offered if applies(t, team_id)), None)
    if code is None:
        raise field_error("status", "There are no customer types. An administrator adds them in Administration → Settings → Customer types.")
    return code


@router.get("/customer-types")
def list_types(me: CurrentUser, db: DB) -> list[dict]:
    return all_types(db)


class TypeFields(Api):
    name: str | None = Field(None, min_length=1, max_length=60)
    color: Color | None = None
    sort_order: int | None = Field(None, ge=0, le=999)
    is_active: bool | None = None
    # Which teams are offered it: only these, or everyone but these.
    only_teams: list[Annotated[str, Field(max_length=36)]] | None = Field(None, max_length=50)
    except_teams: list[Annotated[str, Field(max_length=36)]] | None = Field(None, max_length=50)


def check_teams(db: Session, ids: list[str] | None, field: str) -> list[str] | None:
    if ids is None:
        return None
    known = set(db.scalars(select(Team.id)))
    if any(i not in known for i in ids):
        raise field_error(field, "Pick teams from the list.")
    return list(dict.fromkeys(ids))


class TypeIn(TypeFields):
    name: str = Field(min_length=1, max_length=60)


def name_taken(db: Session, name: str, not_code: str | None = None) -> bool:
    query = select(CustomerType.code).where(func.lower(CustomerType.name) == name.lower())
    if not_code:
        query = query.where(CustomerType.code != not_code)
    return db.scalar(query) is not None


@router.post("/admin/customer-types", status_code=status.HTTP_201_CREATED)
def create_type(access: Manage, me: CurrentUser, db: DB, body: TypeIn) -> list[dict]:
    if name_taken(db, body.name):
        raise field_error("name", "There's a type with this name already.")
    # The code is what companies store; made from the name once, and never changed.
    base = re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_")[:30] or "type"
    code, n = base, 2
    while db.get(CustomerType, code):
        code, n = f"{base}_{n}", n + 1
    last = db.scalar(select(func.max(CustomerType.sort_order))) or 0
    db.add(
        CustomerType(
            code=code,
            name=body.name,
            color=body.color or "gray",
            sort_order=body.sort_order if body.sort_order is not None else last + 1,
            is_active=body.is_active is not False,
            only_teams=check_teams(db, body.only_teams, "onlyTeams") or [],
            except_teams=check_teams(db, body.except_teams, "exceptTeams") or [],
        )
    )
    audit(db, me, "customer_type.created", target=body.name, target_type="customer_type", target_id=code)
    db.commit()
    return all_types(db)


@router.patch("/admin/customer-types/{code}")
def update_type(access: Manage, me: CurrentUser, db: DB, code: str, body: TypeFields) -> list[dict]:
    kind = db.get(CustomerType, code)
    if kind is None:
        raise not_found("customer type")
    wanted = {k: v for k, v in changed(body).items() if v is not None}
    for key, field in (("only_teams", "onlyTeams"), ("except_teams", "exceptTeams")):
        if key in wanted:
            wanted[key] = check_teams(db, wanted[key], field)
    if "name" in wanted and name_taken(db, wanted["name"], code):
        raise field_error("name", "There's a type with this name already.")
    if wanted.get("is_active") is False and kind.is_active:
        others = db.scalar(select(func.count()).select_from(CustomerType).where(CustomerType.is_active, CustomerType.code != code)) or 0
        if not others:
            raise HTTPException(status.HTTP_409_CONFLICT, "Keep at least one type switched on, or customers couldn't be added.")
    fields = [k for k, v in wanted.items() if getattr(kind, k) != v]
    for k in fields:
        setattr(kind, k, wanted[k])
    if fields:
        audit(db, me, "customer_type.updated", target=kind.name, target_type="customer_type", target_id=code, fields=camel(fields))
        db.commit()
    return all_types(db)


@router.delete("/admin/customer-types/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_type(access: Manage, me: CurrentUser, db: DB, code: str) -> Response:
    kind = db.get(CustomerType, code)
    if kind is None:
        raise not_found("customer type")
    used = db.scalar(select(func.count()).select_from(Company).where(Company.status == code)) or 0
    if used:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{used} {'customer is' if used == 1 else 'customers are'} this type. Switch it off instead, or change them first.")
    if kind.is_active and not db.scalar(select(func.count()).select_from(CustomerType).where(CustomerType.is_active, CustomerType.code != code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Keep at least one type switched on, or customers couldn't be added.")
    audit(db, me, "customer_type.deleted", target=kind.name, target_type="customer_type", target_id=code)
    db.delete(kind)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
