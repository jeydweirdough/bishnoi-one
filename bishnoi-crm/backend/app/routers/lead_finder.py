"""Find leads with AI (decided 2026-10-19): the screens write a prompt for the
person's own chatbot (ChatGPT, Claude, DeepSeek), the chatbot searches the web
and answers in a fixed format, and what's pasted back is checked and saved here.

- GET  /leads/finder  what the prompt needs: the customer types offered to the
  person's team, and their team's name.
- POST /leads/check   each pasted lead, checked: what's missing, whether its type
  is one on offer, and the customers already in the CRM it looks like (the
  duplicate check's own scoring; a division that hides its customers is named
  only as "another division").
- POST /leads/save    the ones the person ticked, as their customers in their
  team, each with where it was found and a call to make in two days.

Nothing reaches the CRM without the person's review. The chatbot's answer is
data, never instructions: only the known fields are read.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from typing import Annotated

from app.access import Access, require
from app.api import Api
from app.audit import audit
from app.deps import DB, CurrentUser
from app.extra import applies, check_required
from app.models import Activity, Company, CustomerType
from app.routers.customer_types import first_type
from app.routers.duplicates import LINE, score
from app.routers.sharing import shown_to

router = APIRouter(prefix="/leads", tags=["leads"])

Create = Annotated[Access, Depends(require("customers.create"))]
MAX_LEADS = 100
FOLLOW_UP_DAYS = 2
FOUND_WITH = "Found with AI search"


class LeadIn(Api):
    name: str = Field(min_length=1, max_length=160)
    type: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=80)
    region: str | None = Field(None, max_length=80)
    phone: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=254)
    website: str | None = Field(None, max_length=200)
    source: str | None = Field(None, max_length=500)
    why: str | None = Field(None, max_length=1000)


class LeadsIn(Api):
    leads: list[LeadIn] = Field(min_length=1, max_length=MAX_LEADS)


def offered_types(db, team_id) -> list[CustomerType]:
    return [t for t in db.scalars(select(CustomerType).where(CustomerType.is_active).order_by(CustomerType.sort_order, CustomerType.name)) if applies(t, team_id)]


def type_of(lead: LeadIn, offered: list[CustomerType]) -> str | None:
    """The lead's type as one on offer: by code or by name, any case."""
    want = (lead.type or "").strip().lower().replace(" ", "_")
    for t in offered:
        if want in (t.code.lower(), t.name.lower().replace(" ", "_")):
            return t.code
    return None


def looks_like(lead: LeadIn) -> Company:
    """The lead as a customer that isn't saved, for the duplicate check's scoring."""
    return Company(name=lead.name, phone=lead.phone, email=lead.email, website=lead.website, city=lead.city)


@router.get("/finder")
def finder(access: Create, me: CurrentUser, db: DB) -> dict:
    offered = offered_types(db, me.team_id)
    return {
        "team": me.team.name if me.team else None,
        "types": [{"code": t.code, "name": t.name} for t in offered],
        "maxLeads": MAX_LEADS,
    }


@router.post("/check")
def check(access: Create, me: CurrentUser, db: DB, body: LeadsIn) -> dict:
    offered = offered_types(db, me.team_id)
    everyone = list(db.scalars(select(Company)).unique())
    out = []
    for n, lead in enumerate(body.leads):
        probe = looks_like(lead)
        matches = []
        for c in everyone:
            points, why = score("company", probe, c)
            if points >= LINE["company"]:
                named = shown_to(c, access)
                matches.append({
                    "id": c.id if named else None,
                    "name": c.name if named else "A customer of another division",
                    "teamName": (c.team.name if c.team else None) if named else None,
                    "why": why,
                    "points": points,
                })
        matches.sort(key=lambda m: -m["points"])
        problems = []
        if not (lead.city or lead.address):
            problems.append("No city or address")
        if not (lead.phone or lead.email or lead.website):
            problems.append("No phone, email or website")
        if not lead.source:
            problems.append("No source link: check it before saving")
        kind = type_of(lead, offered)
        if lead.type and kind is None:
            problems.append(f"Type “{lead.type}” isn't one of yours; pick one")
        out.append({"index": n, "type": kind, "problems": problems, "matches": matches[:3]})
    return {"items": out}


@router.post("/save")
def save(access: Create, me: CurrentUser, db: DB, body: LeadsIn) -> dict:
    """Each lead as the person's customer in their team. One that fails (a field
    their form requires is empty) is skipped with why; the rest are saved."""
    offered = offered_types(db, me.team_id)
    if not offered:
        raise HTTPException(409, "Your team has no customer types: an administrator adds them in Settings.")
    default = first_type(db, team_id=me.team_id)
    saved, skipped = [], []
    now = datetime.now(UTC)
    for n, lead in enumerate(body.leads):
        notes = "\n".join(x for x in (f"{FOUND_WITH}.", lead.why and f"Why: {lead.why}", lead.source and f"Source: {lead.source}", lead.region and f"Region: {lead.region}") if x)
        company = Company(
            name=lead.name.strip(), status=type_of(lead, offered) or default, address=lead.address, city=lead.city, country="Philippines",
            phone=lead.phone, email=(lead.email or None), website=lead.website, notes=notes, extra={},
            owner_id=me.id, team_id=me.team_id, created_by_id=me.id,
        )
        try:
            check_required(db, "company", company, team_id=me.team_id, kind=company.status)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else "; ".join(str(x.get("msg")) for x in e.detail if isinstance(x, dict))
            skipped.append({"index": n, "name": lead.name, "why": detail})
            continue
        db.add(company)
        db.flush()
        db.add(Activity(
            kind="task", subject=f"Call new lead: {company.name}", company_id=company.id,
            at=(now + timedelta(days=FOLLOW_UP_DAYS)).replace(hour=1, minute=0, second=0, microsecond=0),
            owner_id=me.id, team_id=me.team_id, created_by_id=me.id,
        ))
        audit(db, me, "company.created", target=company.name, target_type="company", target_id=company.id)
        saved.append({"index": n, "id": company.id, "name": company.name})
    db.commit()
    return {"saved": saved, "skipped": skipped}

