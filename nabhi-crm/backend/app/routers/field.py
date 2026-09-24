"""Field work: visits to doctors, what they owe, and each agent's month against
their goals.

- /visits: a visit and what came of it. A collection needs its amount (and
  takes a receipt number); other outcomes collect nothing. visits.view /
  create / edit / delete, within the person's reach, and the doctor too.
- /field/doctors: doctors within reach and what each owes now: the newest
  uploaded balance, less what visits collected after its date.
- /field/performance: each person's month: doctors visited, doctors updated
  (their details changed), amount collected, visits that collected. Everyone
  sees their own; goals.view shows everyone within reach.
- /field/goals: the month's goals per person (goals.manage).

Months are the company's own (its timezone), written YYYY-MM.
"""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access import Access, CurrentAccess, permissions_of, require
from app.api import Api, field_error, iso, not_found, person_out, team_out
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app.models import AuditEntry, Balance, Company, FieldGoal, User, Visit
from app.scope import reachable_people, reaches, within

router = APIRouter(tags=["field work"])

View = Annotated[Access, Depends(require("visits.view"))]
Create = Annotated[Access, Depends(require("visits.create"))]
Edit = Annotated[Access, Depends(require("visits.edit"))]
Delete = Annotated[Access, Depends(require("visits.delete"))]
Manage = Annotated[Access, Depends(require("goals.manage"))]

Outcome = Literal["collected", "promised", "not_in", "updated", "other"]
MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
DOCTOR = "doctor"


# --- months ----------------------------------------------------------------------------------


def this_month(settings: Settings) -> str:
    return datetime.now(ZoneInfo(settings.org_timezone)).strftime("%Y-%m")


def month_or_now(month: str | None, settings: Settings) -> str:
    if month is None:
        return this_month(settings)
    if not MONTH.fullmatch(month):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Write the month as YYYY-MM, e.g. 2026-09.")
    return month


def month_bounds(month: str, settings: Settings) -> tuple[datetime, datetime]:
    """The month's first moment and the next month's, in UTC."""
    zone = ZoneInfo(settings.org_timezone)
    year, mon = int(month[:4]), int(month[5:])
    start = datetime(year, mon, 1, tzinfo=zone)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


# --- visits ----------------------------------------------------------------------------------


class VisitFields(Api):
    visited_at: datetime | None = None
    amount_centavos: int | None = Field(None, ge=0, le=10**12)
    receipt_no: str | None = Field(None, max_length=40)
    notes: str | None = Field(None, max_length=5000)


class VisitIn(VisitFields):
    company_id: str = Field(max_length=36)
    outcome: Outcome


class VisitPatch(VisitFields):
    outcome: Outcome | None = None


def visit_out(visit: Visit, access: Access) -> dict:
    inside = reaches(visit, access)
    return {
        "id": visit.id,
        "company": {"id": visit.company.id, "name": visit.company.name},
        "visitedAt": iso(visit.visited_at),
        "outcome": visit.outcome,
        "amountCentavos": visit.amount_centavos,
        "receiptNo": visit.receipt_no,
        "notes": visit.notes,
        "owner": person_out(visit.owner),
        "createdAt": iso(visit.created_at),
        "can": {"edit": inside and access.can("visits.edit"), "delete": inside and access.can("visits.delete")},
    }


def to_utc(moment: datetime, settings: Settings) -> datetime:
    """A time with no zone is the company's own local time (what a form sends)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo(settings.org_timezone))
    return moment.astimezone(UTC)


def check_collection(outcome: str, amount: int, receipt: str | None) -> None:
    if outcome == "collected" and amount <= 0:
        raise field_error("amountCentavos", "Enter how much was collected.")
    if outcome != "collected" and amount:
        raise field_error("amountCentavos", "Only a collection has an amount. Pick “Collected” or clear the amount.")
    if outcome != "collected" and receipt:
        raise field_error("receiptNo", "Only a collection has a receipt.")


def get_visit(db: Session, access: Access, visit_id: str) -> Visit:
    visit = db.get(Visit, visit_id)
    if visit is None or not reaches(visit, access):
        raise not_found("visit")
    return visit


@router.get("/visits")
def list_visits(
    access: View,
    db: DB,
    settings: SettingsDep,
    company: str | None = Query(None, max_length=36),
    person: str | None = Query(None, max_length=36),
    month: str | None = Query(None, max_length=7),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    query = within(select(Visit), Visit, access)
    if company:
        query = query.where(Visit.company_id == company)
    if person:
        query = query.where(Visit.owner_id == person)
    if month:
        start, end = month_bounds(month_or_now(month, settings), settings)
        query = query.where(Visit.visited_at >= start, Visit.visited_at < end)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    visits = db.scalars(query.order_by(Visit.visited_at.desc()).limit(limit).offset(offset)).unique().all()
    return {"items": [visit_out(v, access) for v in visits], "total": total}


@router.post("/visits", status_code=status.HTTP_201_CREATED)
def create_visit(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, body: VisitIn) -> dict:
    doctor = db.get(Company, body.company_id)
    if doctor is None or not reaches(doctor, access):
        raise field_error("companyId", "Pick a doctor you can see.")
    visited_at = to_utc(body.visited_at, settings) if body.visited_at else datetime.now(UTC)
    if visited_at > datetime.now(UTC) + timedelta(minutes=5):
        raise field_error("visitedAt", "A visit is logged once it's happened, so not in the future.")
    amount = body.amount_centavos or 0
    receipt = (body.receipt_no or "").strip() or None
    check_collection(body.outcome, amount, receipt)
    visit = Visit(
        company_id=doctor.id,
        visited_at=visited_at,
        outcome=body.outcome,
        amount_centavos=amount,
        receipt_no=receipt,
        notes=(body.notes or "").strip() or None,
        owner_id=me.id,
        team_id=me.team_id,
        created_by_id=me.id,
    )
    db.add(visit)
    db.flush()
    audit(db, me, "visit.created", target=doctor.name, target_type="visit", target_id=visit.id)
    db.commit()
    db.refresh(visit)
    return visit_out(visit, access)


@router.patch("/visits/{visit_id}")
def update_visit(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, visit_id: str, body: VisitPatch) -> dict:
    visit = get_visit(db, access, visit_id)
    sent = body.model_fields_set
    if "visited_at" in sent and body.visited_at:
        visit.visited_at = to_utc(body.visited_at, settings)
    if body.outcome is not None:
        visit.outcome = body.outcome
    if "amount_centavos" in sent:
        visit.amount_centavos = body.amount_centavos or 0
    if "receipt_no" in sent:
        visit.receipt_no = (body.receipt_no or "").strip() or None
    if "notes" in sent:
        visit.notes = (body.notes or "").strip() or None
    if visit.outcome != "collected":
        visit.amount_centavos, visit.receipt_no = 0, None
    check_collection(visit.outcome, visit.amount_centavos, visit.receipt_no)
    audit(db, me, "visit.updated", target=visit.company.name, target_type="visit", target_id=visit.id)
    db.commit()
    db.refresh(visit)
    return visit_out(visit, access)


@router.delete("/visits/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_visit(access: Delete, me: CurrentUser, db: DB, visit_id: str) -> Response:
    visit = get_visit(db, access, visit_id)
    audit(db, me, "visit.deleted", target=visit.company.name, target_type="visit", target_id=visit.id)
    db.delete(visit)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- what doctors owe --------------------------------------------------------------------------


def owed_of(db: Session, company_ids: list[str], settings: Settings) -> dict[str, dict]:
    """For each doctor with a balance on file: the newest one, what visits
    collected after its date, and what that leaves owed."""
    if not company_ids:
        return {}
    newest: dict[str, Balance] = {}
    for b in db.scalars(
        select(Balance).where(Balance.company_id.in_(company_ids)).order_by(Balance.as_of, Balance.created_at)
    ):
        newest[b.company_id] = b  # ordered, so the last one seen is the newest
    zone = ZoneInfo(settings.org_timezone)
    out = {}
    for company_id, b in newest.items():
        # The balance counts everything paid up to the end of its date.
        after = datetime.combine(date.fromisoformat(b.as_of) + timedelta(days=1), datetime.min.time(), zone).astimezone(UTC)
        collected = db.scalar(
            select(func.coalesce(func.sum(Visit.amount_centavos), 0)).where(
                Visit.company_id == company_id, Visit.outcome == "collected", Visit.visited_at >= after
            )
        ) or 0
        out[company_id] = {
            "asOf": b.as_of,
            "balanceCentavos": b.amount_centavos,
            "collectedSinceCentavos": collected,
            "owedCentavos": max(b.amount_centavos - collected, 0),
        }
    return out


def last_visits(db: Session, company_ids: list[str]) -> dict[str, datetime]:
    if not company_ids:
        return {}
    rows = db.execute(
        select(Visit.company_id, func.max(Visit.visited_at)).where(Visit.company_id.in_(company_ids)).group_by(Visit.company_id)
    )
    return {company_id: at for company_id, at in rows}


@router.get("/field/doctors")
def list_doctors(
    access: View,
    db: DB,
    settings: SettingsDep,
    search: str | None = Query(None, max_length=100),
    owed: bool = False,
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Doctors within reach (the Doctor type, or anyone with a balance on file),
    most owed first."""
    with_balance = select(Balance.company_id)
    query = within(select(Company), Company, access).where(or_(Company.status == DOCTOR, Company.id.in_(with_balance)))
    if search:
        query = query.where(func.lower(Company.name).contains(search.strip().lower()))
    doctors = db.scalars(query.order_by(Company.name)).unique().all()
    ids = [d.id for d in doctors]
    balances, seen = owed_of(db, ids, settings), last_visits(db, ids)
    rows = []
    for d in doctors:
        b = balances.get(d.id)
        if owed and not (b and b["owedCentavos"] > 0):
            continue
        rows.append({
            "id": d.id,
            "name": d.name,
            "city": d.city,
            "owner": person_out(d.owner),
            "balance": b,
            "lastVisitAt": iso(seen.get(d.id)),
        })
    rows.sort(key=lambda r: (-(r["balance"] or {}).get("owedCentavos", 0), r["name"].lower()))
    return {"items": rows[:limit], "total": len(rows), "owedCentavos": sum((r["balance"] or {}).get("owedCentavos", 0) for r in rows)}


@router.get("/field/doctors/{company_id}")
def read_doctor_balance(access: View, db: DB, settings: SettingsDep, company_id: str) -> dict:
    """One doctor's balance now, and the balances uploaded for them before."""
    doctor = db.get(Company, company_id)
    if doctor is None or not reaches(doctor, access):
        raise not_found("customer")
    history = db.scalars(select(Balance).where(Balance.company_id == doctor.id).order_by(Balance.as_of.desc(), Balance.created_at.desc()).limit(24))
    return {
        "balance": owed_of(db, [doctor.id], settings).get(doctor.id),
        "history": [{"asOf": b.as_of, "balanceCentavos": b.amount_centavos, "note": b.note} for b in history],
    }


# --- the month against its goals ---------------------------------------------------------------


def is_field_person(user: User) -> bool:
    """Someone whose job is visiting: they log visits, and don't watch others'."""
    granted = permissions_of(user.role)
    return not user.role.is_system and "visits.create" in granted and "goals.view" not in granted


def goal_out(goal: FieldGoal | None) -> dict | None:
    if goal is None:
        return None
    return {
        "doctorsVisited": goal.doctors_visited,
        "doctorsUpdated": goal.doctors_updated,
        "amountCentavos": goal.amount_centavos,
        "collectionVisits": goal.collection_visits,
    }


def actuals(db: Session, user_ids: list[str], start: datetime, end: datetime) -> dict[str, dict]:
    out = {u: {"doctorsVisited": 0, "doctorsUpdated": 0, "amountCentavos": 0, "collectionVisits": 0} for u in user_ids}
    if not user_ids:
        return out
    in_month = (Visit.owner_id.in_(user_ids), Visit.visited_at >= start, Visit.visited_at < end)
    for owner, doctors in db.execute(select(Visit.owner_id, func.count(func.distinct(Visit.company_id))).where(*in_month).group_by(Visit.owner_id)):
        out[owner]["doctorsVisited"] = doctors
    collected = select(Visit.owner_id, func.count(), func.sum(Visit.amount_centavos)).where(*in_month, Visit.outcome == "collected")
    for owner, visits, amount in db.execute(collected.group_by(Visit.owner_id)):
        out[owner]["collectionVisits"], out[owner]["amountCentavos"] = visits, amount or 0
    # A doctor updated: one whose details they changed this month (the audit
    # log says who changed which customer), counted once however often.
    updated = (
        select(AuditEntry.actor_id, func.count(func.distinct(AuditEntry.target_id)))
        .where(
            AuditEntry.actor_id.in_(user_ids),
            AuditEntry.action == "company.updated",
            AuditEntry.at >= start,
            AuditEntry.at < end,
        )
        .group_by(AuditEntry.actor_id)
    )
    for actor, doctors in db.execute(updated):
        out[actor]["doctorsUpdated"] = doctors
    return out


@router.get("/field/performance")
def performance(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, month: str | None = Query(None, max_length=7)) -> dict:
    month = month_or_now(month, settings)
    start, end = month_bounds(month, settings)
    goals = {g.user_id: g for g in db.scalars(select(FieldGoal).where(FieldGoal.month == month))}
    if access.can("goals.view"):
        people = [u for u in reachable_people(db, access) if is_field_person(u) or u.id in goals]
    else:
        people = [me]
    done = actuals(db, [p.id for p in people], start, end)
    rows = [
        {"person": person_out(p), "team": team_out(p.team), "goal": goal_out(goals.get(p.id)), "actual": done[p.id]}
        for p in sorted(people, key=lambda u: u.full_name.lower())
    ]
    totals = {k: sum(r["actual"][k] for r in rows) for k in ("doctorsVisited", "doctorsUpdated", "amountCentavos", "collectionVisits")}
    return {"month": month, "thisMonth": this_month(settings), "people": rows, "totals": totals, "canSetGoals": access.can("goals.manage")}


class GoalIn(Api):
    user_id: str = Field(max_length=36)
    doctors_visited: int = Field(0, ge=0, le=100000)
    doctors_updated: int = Field(0, ge=0, le=100000)
    amount_centavos: int = Field(0, ge=0, le=10**13)
    collection_visits: int = Field(0, ge=0, le=100000)


class GoalsIn(Api):
    goals: list[GoalIn] = Field(max_length=1000)


@router.get("/field/goals")
def read_goals(access: Manage, db: DB, settings: SettingsDep, month: str | None = Query(None, max_length=7)) -> dict:
    """Everyone who can be given goals (field people, and anyone already given
    some that month), with the month's goals."""
    month = month_or_now(month, settings)
    goals = {g.user_id: g for g in db.scalars(select(FieldGoal).where(FieldGoal.month == month))}
    people = [u for u in db.scalars(select(User).where(User.is_active).order_by(User.full_name)) if is_field_person(u) or u.id in goals]
    return {
        "month": month,
        "people": [{"person": person_out(p), "team": team_out(p.team), "goal": goal_out(goals.get(p.id))} for p in people],
    }


@router.put("/field/goals")
def set_goals(access: Manage, me: CurrentUser, db: DB, settings: SettingsDep, body: GoalsIn, month: str | None = Query(None, max_length=7)) -> dict:
    month = month_or_now(month, settings)
    users = set(db.scalars(select(User.id).where(User.id.in_([g.user_id for g in body.goals]))))
    if missing := [g.user_id for g in body.goals if g.user_id not in users]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"No such person: {missing[0]}.")
    existing = {g.user_id: g for g in db.scalars(select(FieldGoal).where(FieldGoal.month == month))}
    for g in body.goals:
        goal = existing.get(g.user_id) or FieldGoal(user_id=g.user_id, month=month)
        goal.doctors_visited, goal.doctors_updated = g.doctors_visited, g.doctors_updated
        goal.amount_centavos, goal.collection_visits = g.amount_centavos, g.collection_visits
        db.add(goal)
    audit(db, me, "goals.updated", target=f"Goals for {month} ({len(body.goals)} people)", target_type="goals")
    db.commit()
    return read_goals(access, db, settings, month)
