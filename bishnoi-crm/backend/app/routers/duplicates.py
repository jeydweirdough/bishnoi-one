"""Possible duplicates, and merging them (Customers → Possible duplicates).

Finding them borrows record linkage's usual shape (as splink does it), kept
small enough to need no library:
- blocking: only records that share something are compared (the start of the
  name, a phone number, an email address, a website), so a few thousand
  customers aren't compared each with each;
- scoring: each pair earns points for what matches (same phone, same email,
  same or similar name, same city or company) and loses some where they clearly
  differ. Pairs above the line are offered, strongest first.

Merging keeps one record. Everything on the other one moves to it (contacts,
activities, quotes, deals, visits, balances, marketing requests); the kept record's
empty fields are filled from the other; the other is deleted, and its id is
remembered (MergedRecord) so old links and the other Bishnoi One apps still find the
one kept. Pairs someone says are different aren't offered again.
"""

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, digits, iso, not_found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Activity, Balance, Company, Contact, Deal, MergedRecord, NotDuplicate, Quote, Visit
from app.scope import reaches, within

router = APIRouter(tags=["duplicates"])

Edit = Annotated[Access, Depends(require("customers.edit"))]
View = Annotated[Access, Depends(require("customers.view"))]
Kind = Literal["company", "contact"]

# Words that don't tell two names apart: titles, and the company's legal form.
NOISE = {"dr", "dra", "doctor", "md", "mr", "mrs", "ms", "the", "inc", "corp", "corporation", "co", "company", "ltd", "llc", "opc", "and"}
# A block bigger than this (a common name start) is too broad to say anything.
BLOCK_LIMIT = 60
LINE = {"company": 50, "contact": 60}


def name_key(name: str | None) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower()).split()
    return " ".join(w for w in words if w not in NOISE)


def site_key(url: str | None) -> str | None:
    if not url:
        return None
    host = re.sub(r"^[a-z]+://", "", url.strip().lower()).split("/")[0]
    return host.removeprefix("www.") or None


def phones(record: Company | Contact) -> set[str]:
    numbers = {record.phone, getattr(record, "mobile", None)}
    return {key for n in numbers if (key := digits(n)) and len(key) >= 7}


def name_of(record: Company | Contact) -> str:
    return record.name if isinstance(record, Company) else record.full_name


def score(kind: Kind, a, b) -> tuple[int, list[str]]:
    points, why = 0, []
    if phones(a) & phones(b):
        points += 50 if kind == "company" else 60
        why.append("Same phone number")
    if a.email and b.email and a.email.lower() == b.email.lower():
        points += 50 if kind == "company" else 60
        why.append("Same email")
    na, nb = name_key(name_of(a)), name_key(name_of(b))
    if na and na == nb:
        points += 60 if kind == "company" else 40
        why.append("Same name")
    elif na and nb:
        alike = SequenceMatcher(None, na, nb).ratio()
        if alike >= 0.85:
            points += round((50 if kind == "company" else 30) * alike)
            why.append("Similar name")
    if kind == "company":
        if site_key(a.website) and site_key(a.website) == site_key(b.website):
            points += 40
            why.append("Same website")
        if a.city and b.city:
            if a.city.strip().lower() == b.city.strip().lower():
                points += 10
                why.append("Same city")
            else:
                points -= 15
    elif a.company_id and a.company_id == b.company_id:
        points += 20
        why.append("Same customer")
    return points, why


def blocks(kind: Kind, records: list) -> list[list]:
    by: dict[str, list] = defaultdict(list)
    for r in records:
        key = name_key(name_of(r)).replace(" ", "")
        if len(key) >= 3:
            by["n:" + key[:4]].append(r)
        for p in phones(r):
            by["p:" + p].append(r)
        if r.email:
            by["e:" + r.email.lower()].append(r)
        if kind == "company" and (site := site_key(r.website)):
            by["w:" + site].append(r)
    return [group for group in by.values() if 1 < len(group) <= BLOCK_LIMIT]


def summary(db: Session, kind: Kind, r) -> dict:
    if kind == "company":
        counts = {
            "contacts": db.scalar(select(func.count()).where(Contact.company_id == r.id)) or 0,
            "activities": db.scalar(select(func.count()).where(Activity.company_id == r.id)) or 0,
            "quotes": db.scalar(select(func.count()).where(Quote.company_id == r.id)) or 0,
            "deals": db.scalar(select(func.count()).where(Deal.company_id == r.id)) or 0,
            "visits": db.scalar(select(func.count()).where(Visit.company_id == r.id)) or 0,
        }
        place = ", ".join(p for p in (r.city, r.country) if p) or None
    else:
        counts = {
            "activities": db.scalar(select(func.count()).where(Activity.contact_id == r.id)) or 0,
            "quotes": db.scalar(select(func.count()).where(Quote.contact_id == r.id)) or 0,
            "deals": db.scalar(select(func.count()).where(Deal.contact_id == r.id)) or 0,
        }
        place = r.company.name if r.company else None
    return {
        "id": r.id,
        "name": name_of(r),
        "place": place,
        "email": r.email,
        "phone": r.phone or getattr(r, "mobile", None),
        "owner": {"id": r.owner.id, "name": r.owner.full_name} if r.owner else None,
        "updatedAt": iso(r.updated_at),
        "counts": counts,
    }


def pair_ids(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


@router.get("/duplicates")
def find_duplicates(access: Edit, db: DB, kind: Kind = "company", limit: int = Query(50, ge=1, le=200)) -> dict:
    """Possible duplicates among the records this person can reach, strongest first."""
    model = Company if kind == "company" else Contact
    records = list(db.scalars(within(select(model), model, access)).unique())
    dismissed = {(n.first_id, n.second_id) for n in db.scalars(select(NotDuplicate).where(NotDuplicate.kind == kind))}
    seen: set[tuple[str, str]] = set()
    found = []
    for group in blocks(kind, records):
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                ids = pair_ids(a.id, b.id)
                if a.id == b.id or ids in seen or ids in dismissed:
                    continue
                seen.add(ids)
                points, why = score(kind, a, b)
                if points >= LINE[kind]:
                    found.append((points, why, a, b))
    found.sort(key=lambda f: (-f[0], name_of(f[2]).lower()))
    return {
        "kind": kind,
        "total": len(found),
        "pairs": [
            {"score": min(100, points), "reasons": why, "a": summary(db, kind, a), "b": summary(db, kind, b)}
            for points, why, a, b in found[:limit]
        ],
    }


class PairIn(Api):
    kind: Kind
    keep_id: str = Field(max_length=36)
    merge_id: str = Field(max_length=36)


def both(db: Session, access: Access, body: PairIn) -> tuple:
    if body.keep_id == body.merge_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick two different records.")
    model = Company if body.kind == "company" else Contact
    keep, other = db.get(model, body.keep_id), db.get(model, body.merge_id)
    what = "customer" if body.kind == "company" else "contact"
    if keep is None or other is None or not reaches(keep, access) or not reaches(other, access):
        raise not_found(what)
    return keep, other


COMPANY_FILL = ("industry", "lead_source", "website", "email", "phone", "address", "city", "country", "price_group_code")
CONTACT_FILL = ("company_id", "last_name", "job_title", "email", "phone", "mobile")


def fill(keep, other, names: tuple[str, ...]) -> list[str]:
    """Copies what the kept record lacks from the other; says which it took."""
    took = []
    for name in names:
        if getattr(keep, name) in (None, "") and getattr(other, name) not in (None, ""):
            setattr(keep, name, getattr(other, name))
            took.append(name)
    extra = dict(keep.extra or {})
    for key, value in (other.extra or {}).items():
        if extra.get(key) in (None, "", []) and value not in (None, "", []):
            extra[key] = value
            took.append(key)
    keep.extra = extra
    if other.notes and other.notes.strip() not in (keep.notes or ""):
        keep.notes = f"{keep.notes}\n\n{other.notes}" if keep.notes else other.notes
        took.append("notes")
    return took


@router.post("/duplicates/merge")
def merge(access: Edit, me: CurrentUser, db: DB, body: PairIn) -> dict:
    """Keeps one record and moves everything on the other to it. Needs Delete
    as well as Edit: the other record goes."""
    access.require("customers.delete")
    keep, other = both(db, access, body)
    if body.kind == "company":
        for model in (Contact, Activity, Quote, Deal, Visit, Balance):
            db.execute(update(model).where(model.company_id == other.id).values(company_id=keep.id))
        took = fill(keep, other, COMPANY_FILL)
        if keep.latitude is None and other.latitude is not None:
            keep.latitude, keep.longitude, keep.pinned_at, keep.pinned_by_id = other.latitude, other.longitude, other.pinned_at, other.pinned_by_id
            took.append("location")
    else:
        for model in (Activity, Quote, Deal):
            db.execute(update(model).where(model.contact_id == other.id).values(contact_id=keep.id))
        took = fill(keep, other, CONTACT_FILL)
    name = name_of(other)
    # Anything merged into the other one before now leads to the one kept.
    db.execute(update(MergedRecord).where(MergedRecord.new_id == other.id).values(new_id=keep.id))
    db.add(MergedRecord(old_id=other.id, kind=body.kind, new_id=keep.id, name=name[:200], merged_by_id=me.id))
    db.execute(
        NotDuplicate.__table__.delete().where((NotDuplicate.first_id == other.id) | (NotDuplicate.second_id == other.id))
    )
    db.flush()
    db.expire_all()
    db.delete(db.get(type(keep), other.id))
    audit(db, me, f"{body.kind}.merged", target=f"{name} into {name_of(keep)}", target_type=body.kind, target_id=keep.id, fields=took)
    db.commit()
    return {"keptId": keep.id, "filled": took}


class NotDuplicateIn(Api):
    kind: Kind
    first_id: str = Field(max_length=36)
    second_id: str = Field(max_length=36)


@router.post("/duplicates/different", status_code=status.HTTP_204_NO_CONTENT)
def mark_different(access: Edit, me: CurrentUser, db: DB, body: NotDuplicateIn) -> None:
    """These two are different: don't offer them again."""
    both(db, access, PairIn(kind=body.kind, keep_id=body.first_id, merge_id=body.second_id))
    first, second = pair_ids(body.first_id, body.second_id)
    exists = db.scalar(select(NotDuplicate).where(NotDuplicate.kind == body.kind, NotDuplicate.first_id == first, NotDuplicate.second_id == second))
    if exists is None:
        db.add(NotDuplicate(kind=body.kind, first_id=first, second_id=second, decided_by_id=me.id))
        db.commit()


def merged_into(db: Session, record_id: str) -> MergedRecord | None:
    return db.get(MergedRecord, record_id)


@router.get("/merged/{record_id}")
def read_merged(_: View, db: DB, record_id: str) -> dict:
    """Where a merged customer or contact went, for an old link."""
    found = merged_into(db, record_id)
    if found is None:
        raise not_found("record")
    return {"kind": found.kind, "newId": found.new_id, "name": found.name, "mergedAt": iso(found.merged_at)}
