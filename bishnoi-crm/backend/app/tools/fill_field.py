"""Fills a company's field work, so every field screen has a real-looking
two months on it: each field agent's doctors (pinned, tiered, zoned), their
days on the road (visits with detailing, collections and Patient Care Group
follow-ups, and the GPS trail between clinics), monthly field goals, the
balances accounting uploaded, doctors updated, the week plans their coach
went over, and patient assistance applications. Sales reps get revenue
targets too, so Home and Performance measure against something.

    uv run python -m app.tools.fill_field --company getmeds --real
    uv run python -m app.tools.fill_field --company getmeds --remove

Run after app.tools.fill_demo. For development only; a company with real
people in it only with --real. Everything made is listed in
.data/fill_field-<company>.json, so --remove takes out exactly that, and the
doctors are marked like fill_demo's (their notes). Remove it before a local
copy is ever copied up to the live database.
"""

import json
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import (
    AssistanceApplication,
    AuditEntry,
    Balance,
    Company,
    CustomerType,
    Kpi,
    KpiTarget,
    PlanStop,
    Product,
    RouteDay,
    TrailBatch,
    User,
    Visit,
    WeekPlan,
)
from app.tenants import for_tool
from app.tools.fill_demo import FIRST, LAST, SAMPLE, SPECIALTIES, refuse_real
from app.trail import Point, encode, metres, path_metres

TOOL = "fill field tool"
DAYS_BACK = 60
# Where an agent's doctors are: a part of the city each, about 4 km across.
AREAS = (
    ("Makati", 14.5547, 121.0244), ("Pasig", 14.5764, 121.0851), ("Quezon City", 14.6760, 121.0437), ("Manila", 14.5995, 120.9842),
    ("Taguig", 14.5176, 121.0509), ("Mandaluyong", 14.5794, 121.0359), ("Pasay", 14.5378, 121.0014), ("Parañaque", 14.4793, 121.0198),
    ("Marikina", 14.6507, 121.1029), ("Caloocan", 14.6488, 120.9830), ("Las Piñas", 14.4445, 120.9939), ("Muntinlupa", 14.4081, 121.0415),
)
MESSAGES = ("Efficacy against the leading brand", "Dosing and pack sizes", "Price per course of treatment", "Safety profile", "Availability at nearby drugstores")
REACTIONS = ("will_prescribe", "already_prescribes", "interested", "interested", "neutral", "concerns", "not_interested")
OBJECTIVES = ("Follow up on the samples left", "Collect the remaining balance", "Present the new pack size", "Ask about patients for the care group", "Confirm the prescription switch")
PROGRAMS = ("dswd", "pcso", "ovp", "yakap")


def sidecar(company: str) -> Path:
    url = get_settings().database_url
    folder = Path(url.removeprefix("sqlite:///")).parent if url.startswith("sqlite:///") else Path(".data")
    return folder / f"fill_field-{company}.json"


def working_days(today: date) -> list[date]:
    return [today - timedelta(days=n) for n in range(DAYS_BACK, -1, -1) if (today - timedelta(days=n)).weekday() < 5]


def fill(db: Session, rnd: random.Random, company: str) -> dict[str, list]:
    settings = get_settings()
    zone = ZoneInfo(settings.org_timezone)
    today = datetime.now(zone).date()
    made: dict[str, list] = {"route_days": [], "trail_batches": [], "week_plans": [], "kpi_targets": [], "audit": []}
    users = list(db.scalars(select(User).where(User.is_active)))
    role = {u.id: u.role.name if u.role else "" for u in users}
    agents = [u for u in users if role[u.id] == "Field agent"]
    if not agents:
        sys.exit("No field agents in this company.")
    coaches = [u for u in users if role[u.id] in ("Team Lead", "Manager")]
    products = [(p.id, p.name) for p in db.scalars(select(Product).where(Product.is_active))]
    doctor_type = "doctor" if db.get(CustomerType, "doctor") else None

    def local(day: date, hour: int, minute: int = 0) -> datetime:
        return datetime.combine(day, time(hour, minute), zone).astimezone(UTC)

    # Each agent's doctors: the ones fill_demo gave them, and more around their area, up to about 15.
    doctors: dict[str, list[Company]] = {}
    areas: dict[str, tuple[str, float, float]] = {}
    for n, agent in enumerate(agents):
        area, lat0, lng0 = areas[agent.id] = AREAS[n % len(AREAS)]
        mine = list(db.scalars(select(Company).where(Company.owner_id == agent.id, Company.field_tier.is_not(None))))
        for _ in range(max(0, rnd.randint(13, 18) - len(mine))):
            c = Company(
                name=f"Dr. {rnd.choice(FIRST)} {rnd.choice(LAST)}", status=doctor_type or "customer", industry=rnd.choice(SPECIALTIES),
                city=area, country="Philippines", phone=f"+63 9{rnd.randint(10, 99)} {rnd.randint(100, 999)} {rnd.randint(1000, 9999)}",
                field_tier=rnd.choice((1, 2, 2, 3, 3)), field_zone=rnd.choice(("red", "yellow", "yellow", "green", "green")),
                zone_set_at=datetime.now(UTC) - timedelta(days=rnd.randint(1, 20)),
                owner_id=agent.id, team_id=agent.team_id, created_by_id=agent.id, created_at=datetime.now(UTC) - timedelta(days=rnd.randint(70, 200)), notes=SAMPLE,
            )
            db.add(c)
            mine.append(c)
        for c in mine:
            # Pinned near the agent's area (a few without a pin yet, as in life).
            if rnd.random() < 0.9:
                c.latitude, c.longitude = lat0 + rnd.uniform(-0.02, 0.02), lng0 + rnd.uniform(-0.02, 0.02)
                c.pinned_at, c.pinned_by_id = datetime.now(UTC) - timedelta(days=rnd.randint(30, 90)), agent.id
            else:
                c.latitude = c.longitude = c.pinned_at = c.pinned_by_id = None
        doctors[agent.id] = mine
    db.flush()
    # The visits fill_demo made at random give way to these days on the road.
    db.execute(delete(Visit).where(Visit.company_id.in_([c.id for cs in doctors.values() for c in cs])))

    # Days on the road: red doctors in the morning, yellow midday, green in the afternoon; a trail between them.
    days = working_days(today)
    visits = 0
    visited_on: dict[tuple[str, date], list[Company]] = {}
    for agent in agents:
        area = areas[agent.id]
        home = (area[1] + rnd.uniform(-0.03, 0.03), area[2] + rnd.uniform(-0.03, 0.03))
        for day in days:
            if day == today and datetime.now(zone).hour < 10:
                continue
            if rnd.random() < 0.08:  # a day off, or in the office
                continue
            pinned = [c for c in doctors[agent.id] if c.latitude is not None]
            if not pinned:
                continue
            order = {"red": 0, "yellow": 1, "green": 2}
            todays = sorted(rnd.sample(pinned, k=min(len(pinned), rnd.randint(4, 7))), key=lambda c: order.get(c.field_zone or "green", 2))
            if day == today:
                todays = todays[: max(1, (datetime.now(zone).hour - 8) // 2)]
            visited_on[(agent.id, day)] = todays
            moment = local(day, 8, rnd.randint(0, 40))
            points: list[Point] = []
            here = home

            def walk(to: tuple[float, float], start: datetime) -> datetime:
                """Points every two minutes or so from here to there, at city speed."""
                nonlocal here
                gone = metres(here[0], here[1], to[0], to[1])
                steps = max(2, int(gone / 400))
                at = start
                for s in range(1, steps + 1):
                    f = s / steps
                    at = at + timedelta(seconds=rnd.randint(90, 150))
                    points.append(Point(here[0] + (to[0] - here[0]) * f + rnd.uniform(-0.0002, 0.0002), here[1] + (to[1] - here[1]) * f + rnd.uniform(-0.0002, 0.0002), rnd.randint(6, 30), at))
                here = to
                return at

            points.append(Point(home[0], home[1], rnd.randint(8, 25), moment))
            for d in todays:
                moment = walk((d.latitude, d.longitude), moment)
                outcome = rnd.choices(("detailed", "collected", "promised", "not_in", "updated"), weights=(6, 3, 1, 1, 1))[0]
                detailing = []
                if outcome in ("detailed", "collected") and products:
                    for pid, pname in rnd.sample(products, k=min(len(products), rnd.randint(1, 3))):
                        detailing.append({"productId": pid, "productName": pname, "message": rnd.choice(MESSAGES), "reaction": rnd.choice(REACTIONS)})
                care = rnd.choices((None, "enrolled", "followed_up", "not_now"), weights=(5, 1, 2, 2))[0] if outcome != "not_in" else None
                db.add(Visit(
                    company_id=d.id, visited_at=moment, outcome=outcome,
                    amount_centavos=rnd.randint(5, 60) * 100_000 if outcome == "collected" else 0,
                    receipt_no=f"OR-{rnd.randint(100000, 999999)}" if outcome == "collected" else None,
                    latitude=d.latitude + rnd.uniform(-0.0002, 0.0002), longitude=d.longitude + rnd.uniform(-0.0002, 0.0002),
                    accuracy_m=rnd.randint(6, 35), distance_m=rnd.randint(3, 45), detailing=detailing,
                    next_objective=rnd.choice(OBJECTIVES) if rnd.random() < 0.6 else None, care_group=care,
                    owner_id=agent.id, team_id=agent.team_id, created_by_id=agent.id, created_at=moment,
                ))
                if care == "enrolled" and d.care_group_at is None:
                    d.care_group_at = moment
                visits += 1
                # Time at the clinic, then on to the next.
                stay = moment + timedelta(minutes=rnd.randint(20, 45))
                points.append(Point(d.latitude, d.longitude, rnd.randint(6, 20), stay))
                moment = stay + timedelta(minutes=rnd.randint(10, 40))
            moment = walk(home, moment)
            batch = TrailBatch(
                user_id=agent.id, day=day.isoformat(), started_at=points[0].at, ended_at=points[-1].at, count=len(points),
                points=encode(points, points[0].at), min_lat=min(p.lat for p in points), max_lat=max(p.lat for p in points),
                min_lng=min(p.lng for p in points), max_lng=max(p.lng for p in points),
            )
            summary = RouteDay(user_id=agent.id, day=day.isoformat(), distance_m=round(path_metres(points)), points=len(points),
                               first_at=points[0].at, last_at=points[-1].at, last_lat=points[-1].lat, last_lng=points[-1].lng)
            db.add_all([batch, summary])
            db.flush()
            made["trail_batches"].append(batch.id)
            made["route_days"].append(summary.id)

    # Balances, as accounting uploaded them at the end of last month.
    as_of = (today.replace(day=1) - timedelta(days=1)).isoformat()
    uploader = next((u for u in users if role[u.id] in ("Administrator", "Finance")), None)
    balances = 0
    for agent in agents:
        for d in doctors[agent.id]:
            if rnd.random() < 0.65:
                db.add(Balance(company_id=d.id, as_of=as_of, amount_centavos=rnd.randint(8, 180) * 100_000, note=SAMPLE, uploaded_by_id=uploader.id if uploader else None))
                balances += 1

    # Doctors updated (a goal): the activity log says who changed which doctor.
    for agent in agents:
        for d in rnd.sample(doctors[agent.id], k=min(len(doctors[agent.id]), rnd.randint(3, 9))):
            at = datetime.now(UTC) - timedelta(days=rnd.randint(0, 45), hours=rnd.randint(0, 8))
            entry = AuditEntry(at=at, actor_id=agent.id, actor=agent.email, action="company.updated", target_type="company", target_id=d.id, target=d.name,
                               fields=rnd.choice((["phone"], ["fieldZone"], ["address"], ["fieldTier", "fieldZone"])))
            db.add(entry)
            db.flush()
            made["audit"].append(entry.id)

    # Monthly targets: the four field goals for each agent; revenue for each salesperson and team lead.
    kpis = {k.code: k for k in db.scalars(select(Kpi))}
    first = today.replace(day=1)
    months = [(first.replace(year=first.year - (first.month - 1 - n < 0), month=(first.month - 1 - n) % 12 + 1)).strftime("%Y-%m") for n in (2, 1, 0)]

    def target(code: str, user: User, month: str, value: int) -> None:
        k = kpis.get(code)
        if k is None or db.scalar(select(KpiTarget.id).where(KpiTarget.kpi_id == k.id, KpiTarget.month == month, KpiTarget.user_id == user.id)):
            return
        t = KpiTarget(kpi_id=k.id, month=month, user_id=user.id, value=value)
        db.add(t)
        db.flush()
        made["kpi_targets"].append(t.id)

    for month in months:
        for agent in agents:
            n = len(doctors[agent.id])
            target("doctors_visited", agent, month, max(5, round(n * rnd.uniform(0.8, 1.0))))
            target("doctors_updated", agent, month, rnd.randint(4, 8))
            target("amount_collected", agent, month, rnd.randint(15, 40) * 1_000_000)
            target("collection_visits", agent, month, rnd.randint(8, 16))
        for rep in (u for u in users if role[u.id] in ("Salesperson", "Team Lead")):
            target("revenue_won", rep, month, rnd.randint(5, 25) * 10_000_000)

    # Week plans: the last three weeks sent and gone over by the coach; this week sent, the days ahead planned.
    monday = today - timedelta(days=today.weekday())
    plans = stops = 0
    for agent in agents:
        coach = next((c for c in coaches if c.team_id == agent.team_id), None) or (rnd.choice(coaches) if coaches else None)
        for back in (3, 2, 1, 0):
            week = monday - timedelta(weeks=back)
            sent = local(week, 7, rnd.randint(0, 50))
            plan = WeekPlan(user_id=agent.id, week=week.isoformat(), submitted_at=sent,
                            reviewed_at=sent + timedelta(hours=rnd.randint(2, 30)) if back or rnd.random() < 0.5 else None,
                            note=SAMPLE)
            if plan.reviewed_at and coach:
                plan.reviewed_by_id = coach.id
            db.add(plan)
            db.flush()
            made["week_plans"].append(plan.id)
            plans += 1
            for i in range(5):
                day = week + timedelta(days=i)
                if (agent.id, day) in visited_on:
                    chosen = list(visited_on[(agent.id, day)])
                    # Most of the plan was visited; a stop or two wasn't.
                    extra = [c for c in doctors[agent.id] if c not in chosen]
                    chosen += rnd.sample(extra, k=min(len(extra), rnd.randint(0, 2)))
                elif day >= today:
                    # Today (not on the road yet) and the days ahead: the plan, nothing visited yet.
                    chosen = rnd.sample(doctors[agent.id], k=min(len(doctors[agent.id]), 8))
                else:
                    continue
                for c in chosen:
                    slot = {"red": "morning", "yellow": "midday"}.get(c.field_zone or "green", "afternoon")
                    db.add(PlanStop(user_id=agent.id, company_id=c.id, day=day.isoformat(), slot=slot))
                    stops += 1

    # Patient assistance applications: older ones decided, newer ones pending (a few past a week, to follow up).
    applications = 0
    for agent in agents:
        for _ in range(rnd.randint(2, 6)):
            d = rnd.choice(doctors[agent.id])
            submitted = today - timedelta(days=rnd.randint(1, 55))
            status = "pending" if (today - submitted).days < 12 or rnd.random() < 0.25 else rnd.choice(("approved", "approved", "denied"))
            decided = (submitted + timedelta(days=rnd.randint(5, 14))) if status != "pending" else None
            if decided and decided > today:
                decided = today
            db.add(AssistanceApplication(
                program=rnd.choice(PROGRAMS), patient_name=f"{rnd.choice(FIRST)} {rnd.choice(LAST)}", company_id=d.id,
                products=[{"id": pid, "name": pname} for pid, pname in rnd.sample(products, k=min(len(products), rnd.randint(1, 2)))],
                submitted_on=submitted.isoformat(), status=status, decided_on=decided.isoformat() if decided else None,
                receipt_no=f"{rnd.choice(('DSWD', 'PCSO', 'OVP', 'YAKAP'))}-{rnd.randint(100000, 999999)}" if status == "approved" else None,
                notes=SAMPLE, owner_id=agent.id, team_id=agent.team_id, created_by_id=agent.id,
                created_at=datetime.combine(submitted, time(9), zone).astimezone(UTC),
            ))
            applications += 1

    total_doctors = sum(len(v) for v in doctors.values())
    summary = (f"{len(agents)} field agents, {total_doctors} doctors, {visits} visits on {len(made['route_days'])} days on the road, "
               f"{balances} balances, {len(made['audit'])} doctors updated, {len(made['kpi_targets'])} targets, {plans} week plans ({stops} stops), {applications} assistance applications")
    audit(db, TOOL, "demo.field_filled", target=summary[:200])
    db.commit()
    print(f"Made {summary}.")
    return made


def remove(db: Session, company: str) -> None:
    path = sidecar(company)
    made = json.loads(path.read_text()) if path.exists() else {}
    for model, key in ((RouteDay, "route_days"), (TrailBatch, "trail_batches"), (WeekPlan, "week_plans"), (KpiTarget, "kpi_targets"), (AuditEntry, "audit")):
        ids = made.get(key, [])
        for i in range(0, len(ids), 500):
            db.execute(delete(model).where(model.id.in_(ids[i:i + 500])))
    doctors = list(db.scalars(select(Company.id).where(Company.notes == SAMPLE, Company.field_tier.is_not(None))))
    for model in (PlanStop, Balance, AssistanceApplication, Visit):
        db.execute(delete(model).where(model.company_id.in_(doctors)))
    db.commit()
    path.unlink(missing_ok=True)
    print(f"Removed the field work made by this tool ({sum(len(v) for v in made.values())} listed rows, and what hung on {len(doctors)} sample doctors). "
          "The doctors themselves go with app.tools.fill_demo --remove.")


def main() -> int:
    company, url = for_tool(sys.argv)
    print(f"Company: {company}")
    engine = make_engine(url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        if "--remove" in sys.argv:
            remove(db, company)
            return 0
        refuse_real(db, "--real" in sys.argv)
        if sidecar(company).exists():
            sys.exit(f"Already filled ({sidecar(company)}). Run with --remove first to fill it again.")
        made = fill(db, random.Random(11), company)
        sidecar(company).write_text(json.dumps(made))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
