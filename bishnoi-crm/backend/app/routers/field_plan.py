"""A field agent's week, planned by zone (the Rx CHC playbook's routing map).

Monday to Friday (Saturday is for admin, not visits), each day in three parts
by zone: red doctors in the morning, yellow midday, green in the afternoon,
8 calls a day. The agent plans it, sends it to their coach, and the coach goes
over it (every Monday morning in the playbook), taking off any visit that's
there because the clinic is easy to reach rather than because it's due.

- GET /field/plan?week=&person=: the week, each day's stops, and whether each
  was visited that day.
- POST /field/plan/stops, DELETE /field/plan/stops/{id}: a doctor on or off a day.
- POST /field/plan/fill: fills the week from the zones: red and yellow first,
  those short of their tier's visits, up to 8 a day.
- POST /field/plan/send, POST /field/plan/review: to the coach, and back.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import select

from app.access import CurrentAccess
from app.api import Api, field_error, iso, not_found, person_out
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Company, PlanStop, User, Visit, WeekPlan
from app.routers.field import TIER_VISITS, ZONES, Create, doctors_in_reach, local_day, month_bounds, route_person, visits_in
from app.scope import reaches

router = APIRouter(tags=["field work"])

Slot = Literal["morning", "midday", "afternoon"]
SLOT_OF_ZONE = {"red": "morning", "yellow": "midday", "green": "afternoon"}
SLOTS = ("morning", "midday", "afternoon")
# The playbook's daily standard, and as many as a day will take.
CALLS_A_DAY = 8
MOST_A_DAY = 12
WORK_DAYS = 5


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_of(week: str | None, today: date) -> date:
    if not week:
        return monday_of(today)
    try:
        return monday_of(date.fromisoformat(week))
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Write the week as YYYY-MM-DD.") from None


def today_of(settings) -> date:
    return date.fromisoformat(local_day(datetime.now(UTC), settings))


def week_days(monday: date) -> list[str]:
    return [(monday + timedelta(days=i)).isoformat() for i in range(WORK_DAYS)]


def record_of(db, user_id: str, monday: date, make: bool = False) -> WeekPlan | None:
    record = db.scalar(select(WeekPlan).where(WeekPlan.user_id == user_id, WeekPlan.week == monday.isoformat()))
    if record is None and make:
        record = WeekPlan(user_id=user_id, week=monday.isoformat())
        db.add(record)
    return record


def changed(db, user_id: str, monday: date) -> None:
    """A change after it was sent: the coach sees it changed since they looked."""
    record = record_of(db, user_id, monday)
    if record is not None and record.submitted_at:
        record.changed_at = datetime.now(UTC)


def visited_on(db, settings, user_id: str, days: list[str]) -> set[tuple[str, str]]:
    """(doctor, day) pairs the person visited, in the company's own days."""
    zone = ZoneInfo(settings.org_timezone)
    start = datetime.combine(date.fromisoformat(days[0]), datetime.min.time(), zone).astimezone(UTC)
    end = datetime.combine(date.fromisoformat(days[-1]) + timedelta(days=1), datetime.min.time(), zone).astimezone(UTC)
    rows = db.execute(select(Visit.company_id, Visit.visited_at).where(Visit.owner_id == user_id, Visit.visited_at >= start, Visit.visited_at < end)).all()
    return {(company_id, local_day(at if at.tzinfo else at.replace(tzinfo=UTC), settings)) for company_id, at in rows}


def stop_out(stop: PlanStop, visited: set[tuple[str, str]]) -> dict:
    c = stop.company
    return {
        "id": stop.id,
        "day": stop.day,
        "slot": stop.slot,
        "doctor": {"id": c.id, "name": c.name, "city": c.city, "tier": c.field_tier, "zone": c.field_zone},
        "visited": (c.id, stop.day) in visited,
    }


@router.get("/field/plan")
def read_plan(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, week: str | None = Query(None, max_length=10), person: str | None = Query(None, max_length=36)) -> dict:
    if not (access.can("visits.create") or access.can("goals.view")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow that.")
    user = route_person(db, access, me, person)
    today = today_of(settings)
    monday = week_of(week, today)
    days = week_days(monday)
    stops = db.scalars(select(PlanStop).where(PlanStop.user_id == user.id, PlanStop.day.in_(days)).order_by(PlanStop.created_at)).unique().all()
    visited = visited_on(db, settings, user.id, days)
    record = record_of(db, user.id, monday)
    order = {s: i for i, s in enumerate(SLOTS)}
    own = user.id == me.id
    return {
        "person": person_out(user),
        "week": monday.isoformat(),
        "thisWeek": monday_of(today).isoformat(),
        "today": today.isoformat(),
        "callsADay": CALLS_A_DAY,
        "days": [
            {"day": d, "stops": [stop_out(s, visited) for s in sorted((s for s in stops if s.day == d), key=lambda s: order[s.slot])]}
            for d in days
        ],
        "status": {
            "sentAt": iso(record.submitted_at) if record else None,
            "changedAt": iso(record.changed_at) if record else None,
            "reviewedAt": iso(record.reviewed_at) if record else None,
            "reviewedBy": person_out(record.reviewed_by) if record and record.reviewed_by else None,
            "note": record.note if record else None,
        },
        "can": {"plan": own and access.can("visits.create"), "review": not own and access.can("goals.view")},
    }


class StopIn(Api):
    company_id: str = Field(max_length=36)
    day: date
    slot: Slot | None = None


@router.post("/field/plan/stops", status_code=status.HTTP_201_CREATED)
def add_stop(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, body: StopIn) -> dict:
    """A doctor on one of the agent's own days; the part of the day follows their zone unless given."""
    doctor = db.get(Company, body.company_id)
    if doctor is None or not reaches(doctor, access):
        raise field_error("companyId", "Pick one of your doctors.")
    if body.day.weekday() >= WORK_DAYS:
        raise field_error("day", "Plan Monday to Friday: Saturday is for admin, not visits.")
    if body.day < today_of(settings):
        raise field_error("day", "That day has passed.")
    day = body.day.isoformat()
    if db.scalar(select(PlanStop.id).where(PlanStop.user_id == me.id, PlanStop.company_id == doctor.id, PlanStop.day == day)):
        raise field_error("companyId", f"{doctor.name} is already on that day.")
    planned = db.scalars(select(PlanStop.id).where(PlanStop.user_id == me.id, PlanStop.day == day)).all()
    if len(planned) >= MOST_A_DAY:
        raise field_error("day", f"That day already has {MOST_A_DAY} visits.")
    stop = PlanStop(user_id=me.id, company_id=doctor.id, day=day, slot=body.slot or SLOT_OF_ZONE.get(doctor.field_zone or "", "afternoon"))
    db.add(stop)
    changed(db, me.id, monday_of(body.day))
    db.commit()
    db.refresh(stop)
    return stop_out(stop, set())


@router.delete("/field/plan/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_stop(access: CurrentAccess, me: CurrentUser, db: DB, stop_id: str) -> Response:
    """Off the plan: by the agent, or by their coach going over it."""
    stop = db.get(PlanStop, stop_id)
    if stop is None:
        raise not_found("visit on the plan")
    if stop.user_id != me.id:
        route_person(db, access, me, stop.user_id)  # their coach, or not at all
        audit(db, me, "plan.stop_removed", target=stop.company.name, target_type="company", target_id=stop.company_id)
    else:
        changed(db, me.id, monday_of(date.fromisoformat(stop.day)))
    db.delete(stop)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/field/plan/fill")
def fill(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, week: str | None = Query(None, max_length=10)) -> dict:
    """The week filled from the zones, around what's already on it: red doctors
    first, then yellow, then green, each as often as their tier still needs
    this month (once if they have no tier), spread over the days left, up to 8 a day."""
    today = today_of(settings)
    monday = week_of(week, today)
    days = [d for d in week_days(monday) if d >= today.isoformat()]
    if not days:
        raise field_error("week", "That week has passed.")
    doctors = [d for d in db.scalars(doctors_in_reach(access, settings)).unique().all() if d.field_zone]
    month_start, month_end = month_bounds(monday.isoformat()[:7], settings)
    done = visits_in(db, [d.id for d in doctors], month_start, month_end)
    existing = db.scalars(select(PlanStop).where(PlanStop.user_id == me.id, PlanStop.day.in_(days))).all()
    load = {d: sum(1 for s in existing if s.day == d) for d in days}
    taken = {(s.company_id, s.day) for s in existing}
    rank = {z: i for i, z in enumerate(ZONES)}
    added = 0
    for doctor in sorted(doctors, key=lambda d: (rank[d.field_zone], d.field_tier or 4, d.name.lower())):
        wanted = max(0, (TIER_VISITS.get(doctor.field_tier or 0, 1)) - done.get(doctor.id, 0) - sum(1 for s in existing if s.company_id == doctor.id))
        # At most once a day; on the least busy days first.
        for day in sorted(days, key=lambda d: (load[d], d)):
            if wanted <= 0:
                break
            if load[day] >= CALLS_A_DAY or (doctor.id, day) in taken:
                continue
            db.add(PlanStop(user_id=me.id, company_id=doctor.id, day=day, slot=SLOT_OF_ZONE[doctor.field_zone]))
            taken.add((doctor.id, day))
            load[day] += 1
            wanted -= 1
            added += 1
    if added:
        changed(db, me.id, monday)
    db.commit()
    return {"added": added}


@router.post("/field/plan/send")
def send(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, week: str | None = Query(None, max_length=10)) -> dict:
    """The week to the coach. Sent again after changes, the coach looks again."""
    monday = week_of(week, today_of(settings))
    if not db.scalar(select(PlanStop.id).where(PlanStop.user_id == me.id, PlanStop.day.in_(week_days(monday)))):
        raise field_error("week", "Put some visits on the week first.")
    record = record_of(db, me.id, monday, make=True)
    record.submitted_at, record.changed_at = datetime.now(UTC), None
    record.reviewed_at = record.reviewed_by_id = None
    audit(db, me, "plan.sent", target=f"Week of {monday.isoformat()}", target_type="plan")
    db.commit()
    return {"sentAt": iso(record.submitted_at)}


class ReviewIn(Api):
    person: str = Field(max_length=36)
    week: date
    note: str | None = Field(None, max_length=1000)


@router.post("/field/plan/review")
def review(access: CurrentAccess, me: CurrentUser, db: DB, body: ReviewIn) -> dict:
    """The coach has gone over the week (taking off what didn't belong), with a word if they like."""
    if not access.can("goals.view"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow that.")
    user: User = route_person(db, access, me, body.person)
    if user.id == me.id:
        raise field_error("person", "Your own week is your coach's to review.")
    monday = monday_of(body.week)
    record = record_of(db, user.id, monday)
    if record is None or not record.submitted_at:
        raise field_error("week", f"{user.full_name} hasn't sent this week yet.")
    record.reviewed_at, record.reviewed_by_id, record.note, record.changed_at = datetime.now(UTC), me.id, (body.note or "").strip() or None, None
    audit(db, me, "plan.reviewed", target=f"{user.full_name}, week of {monday.isoformat()}", target_type="plan")
    db.commit()
    return {"reviewedAt": iso(record.reviewed_at)}
