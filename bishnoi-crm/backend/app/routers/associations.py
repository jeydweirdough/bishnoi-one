"""Associations (HubSpot's idea, P13): any customer, contact or deal linked to
another, with a label read from each side. A doctor "Works at" a hospital,
whose page lists them under "People here".

A record's page lists its associations by label. Linking needs the right to
edit the record one starts from; the record at the other end is named, and
opened only by those who reach it (as with the look-alikes). A customer field
that points at another customer (a doctor's hospital) shows in the same list,
under the label it stands for.
"""

import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import func, or_, select

from app.access import Access, CurrentAccess, require
from app.api import Api, field_error, not_found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import ASSOCIATED, Association, AssociationLabel, Company, Contact, Deal
from app.scope import reaches, within

router = APIRouter(tags=["associations"])
Manage = Annotated[Access, Depends(require("admin.settings"))]
Kind = Literal["company", "contact", "deal"]
MODELS = {"company": Company, "contact": Contact, "deal": Deal}
EDIT = {"company": "customers.edit", "contact": "customers.edit", "deal": "deals.edit"}
# A customer field that points at another customer, and the label it stands for.
FIELD_LABELS = {"x_hospital": "works_at"}


def name_of(record) -> str:
    return record.name if hasattr(record, "name") else record.full_name


def find(db, kind: str, record_id: str):
    return db.get(MODELS[kind], record_id) if kind in MODELS else None


def reachable(db, access: Access, kind: str, record_id: str):
    record = find(db, kind, record_id)
    if record is None or not reaches(record, access):
        raise not_found("record")
    return record


def other_out(db, access: Access, kind: str, record_id: str, **more) -> dict | None:
    record = find(db, kind, record_id)
    if record is None:
        return None
    return {"type": kind, "id": record.id, "name": name_of(record), "canOpen": reaches(record, access), **more}


@router.get("/associations")
def list_associations(access: CurrentAccess, db: DB, kind: Kind = Query(alias="type"), record_id: str = Query(alias="id", max_length=36)) -> dict:
    """A record's associations, grouped by label as read from its side, and the labels it can take."""
    record = reachable(db, access, kind, record_id)
    labels = {l.code: l for l in db.scalars(select(AssociationLabel).order_by(AssociationLabel.sort_order))}
    groups: dict[tuple[str, str], dict] = {}

    def group(code: str, side: str) -> dict:
        label = labels[code]
        return groups.setdefault((code, side), {"label": code, "side": side, "name": label.name if side == "from" else label.inverse_name, "items": []})

    may_edit = access.can(EDIT[kind])
    for a in db.scalars(select(Association).where(or_(Association.from_id == record.id, Association.to_id == record.id))):
        if a.label_code not in labels:
            continue
        side = "from" if a.from_id == record.id else "to"
        found = other_out(db, access, a.to_type if side == "from" else a.from_type, a.to_id if side == "from" else a.from_id, associationId=a.id, canRemove=may_edit)
        if found:
            group(a.label_code, side)["items"].append(found)

    # A customer field pointing at another customer counts as its label, both ways.
    if kind == "company":
        for key, code in FIELD_LABELS.items():
            if code not in labels:
                continue
            target = (record.extra or {}).get(key)
            if target and (found := other_out(db, access, "company", str(target), fromField=True, canRemove=False)):
                items = group(code, "from")["items"]
                if not any(i["id"] == found["id"] for i in items):
                    items.append(found)
            for other in db.scalars(within(select(Company), Company, access).where(Company.id != record.id)).unique():
                if (other.extra or {}).get(key) == record.id:
                    items = group(code, "to")["items"]
                    if not any(i["id"] == other.id for i in items):
                        items.append({"type": "company", "id": other.id, "name": other.name, "canOpen": True, "fromField": True, "canRemove": False})

    offered = [
        {"label": l.code, "side": side, "name": l.name if side == "from" else l.inverse_name, "otherType": l.to_type if side == "from" else l.from_type}
        for l in labels.values()
        if l.is_active
        for side in ("from", "to")
        if (l.from_type if side == "from" else l.to_type) == kind
    ]
    ordered = sorted(groups.values(), key=lambda g: (labels[g["label"]].sort_order, g["side"]))
    return {"groups": [g for g in ordered if g["items"]], "labels": offered if may_edit else []}


class AssociationIn(Api):
    label: str = Field(max_length=40)
    # Which end this record is: "from" (the doctor, who works at) or "to" (the hospital).
    side: Literal["from", "to"]
    kind: Kind = Field(alias="type")
    record_id: str = Field(alias="id", max_length=36)
    other_id: str = Field(max_length=36)


@router.post("/associations", status_code=status.HTTP_201_CREATED)
def add_association(access: CurrentAccess, me: CurrentUser, db: DB, body: AssociationIn) -> dict:
    access.require(EDIT[body.kind])
    record = reachable(db, access, body.kind, body.record_id)
    label = db.get(AssociationLabel, body.label)
    if label is None or not label.is_active or (label.from_type if body.side == "from" else label.to_type) != body.kind:
        raise field_error("label", "Pick how they're linked from the list.")
    other_kind = label.to_type if body.side == "from" else label.from_type
    other = find(db, other_kind, body.other_id)
    # Customers are named across divisions; contacts and deals only within reach.
    if other is None or other.id == record.id or (other_kind != "company" and not reaches(other, access)):
        raise field_error("otherId", "Pick a record from the list.")
    ends = (record, other) if body.side == "from" else (other, record)
    kinds = (body.kind, other_kind) if body.side == "from" else (other_kind, body.kind)
    found = db.scalar(select(Association).where(Association.label_code == label.code, Association.from_id == ends[0].id, Association.to_id == ends[1].id))
    if found is None:
        found = Association(label_code=label.code, from_type=kinds[0], from_id=ends[0].id, to_type=kinds[1], to_id=ends[1].id, created_by_id=me.id)
        db.add(found)
        db.flush()
        audit(db, me, "association.added", target=f"{name_of(ends[0])} {label.name.lower()} {name_of(ends[1])}", target_type="association", target_id=found.id)
        db.commit()
    return {"id": found.id}


@router.delete("/associations/{association_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_association(access: CurrentAccess, me: CurrentUser, db: DB, association_id: str) -> Response:
    a = db.get(Association, association_id)
    if a is None:
        raise not_found("link")
    ends = [(a.from_type, a.from_id), (a.to_type, a.to_id)]
    if not any((r := find(db, k, i)) is not None and reaches(r, access) and access.can(EDIT[k]) for k, i in ends):
        raise not_found("link")
    label = db.get(AssociationLabel, a.label_code)
    audit(db, me, "association.removed", target=label.name if label else a.label_code, target_type="association", target_id=a.id)
    db.delete(a)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/associations/targets")
def targets(access: CurrentAccess, db: DB, kind: Kind = Query(alias="type"), q: str = Query("", max_length=100)) -> list[dict]:
    """What can be picked at the other end: any customer by name; contacts and deals in reach."""
    like = f"%{q.strip().lower()}%"
    if kind == "company":
        rows = db.scalars(select(Company).where(func.lower(Company.name).like(like)).order_by(func.lower(Company.name)).limit(10)).unique()
        return [{"id": c.id, "name": c.name, "hint": c.team.name if c.team else None} for c in rows]
    if kind == "contact":
        rows = db.scalars(
            within(select(Contact), Contact, access).where(func.lower(Contact.first_name + " " + func.coalesce(Contact.last_name, "")).like(like)).limit(10)
        ).unique()
        return [{"id": c.id, "name": c.full_name, "hint": c.company.name if c.company else None} for c in rows]
    rows = db.scalars(within(select(Deal), Deal, access).where(func.lower(Deal.name).like(like)).order_by(Deal.expected_close_on.desc()).limit(10)).unique()
    return [{"id": d.id, "name": d.name, "hint": d.company.name if d.company else None} for d in rows]


# --- Settings → Associations: the labels -------------------------------------------------------


def label_out(l: AssociationLabel, used: int = 0) -> dict:
    return {"code": l.code, "fromType": l.from_type, "toType": l.to_type, "name": l.name, "inverseName": l.inverse_name, "isActive": l.is_active, "used": used}


@router.get("/admin/association-labels")
def read_labels(_: Manage, db: DB) -> list[dict]:
    used = dict(db.execute(select(Association.label_code, func.count()).group_by(Association.label_code)).all())
    return [label_out(l, used.get(l.code, 0)) for l in db.scalars(select(AssociationLabel).order_by(AssociationLabel.sort_order))]


class LabelIn(Api):
    from_type: Kind
    to_type: Kind
    name: str = Field(min_length=1, max_length=60)
    inverse_name: str = Field(min_length=1, max_length=60)


class LabelPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=60)
    inverse_name: str | None = Field(None, min_length=1, max_length=60)
    is_active: bool | None = None


@router.post("/admin/association-labels", status_code=status.HTTP_201_CREATED)
def add_label(access: Manage, me: CurrentUser, db: DB, body: LabelIn) -> list[dict]:
    base = re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_")[:30] or "label"
    code, n = base, 2
    while db.get(AssociationLabel, code):
        code, n = f"{base}_{n}", n + 1
    last = db.scalar(select(func.max(AssociationLabel.sort_order))) or 0
    db.add(AssociationLabel(code=code, from_type=body.from_type, to_type=body.to_type, name=body.name.strip(), inverse_name=body.inverse_name.strip(), sort_order=last + 1, is_active=True))
    audit(db, me, "association_label.added", target=body.name, target_type="settings")
    db.commit()
    return read_labels(access, db)


@router.patch("/admin/association-labels/{code}")
def change_label(access: Manage, me: CurrentUser, db: DB, code: str, body: LabelPatch) -> list[dict]:
    label = db.get(AssociationLabel, code)
    if label is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such label.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(label, key, value.strip() if isinstance(value, str) else value)
    audit(db, me, "association_label.changed", target=label.name, target_type="settings")
    db.commit()
    return read_labels(access, db)
