"""Fills a demo company with a small office's worth of records, so every
screen has something on it and every list runs past one page.

    uv run python -m app.tools.users --company northwind demo     # first: the demo accounts and catalogue
    uv run python -m app.tools.fill_demo --company northwind

About 150 customers (40 of them the field agents' doctors), 300 contacts, 650
activities over the last three months and the weeks ahead, 60 deals, 50
visits and 80 quotes. Quotes are made through the API, as a rep would make
them, so their prices, numbers and approvals follow the real rules.

For development only. Into a company whose every account is a demo one
(@….test); a company with real people in it (a local copy of GetMeds) only
when asked with --real, and then the records go to its own reps. Every record
made here is marked (SAMPLE, in its notes), so --remove takes them all out
again: do that before a local copy is ever copied up to the live database.

    uv run python -m app.tools.fill_demo --company getmeds --real
    uv run python -m app.tools.fill_demo --company getmeds --remove
"""

import json
import random
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Activity, Company, Contact, CustomerType, Deal, DealStage, Product, Quote, SignInSession, User, Visit
from app.security import new_token, token_hash
from app.tenants import for_tool

TOOL = "fill demo tool"
SAMPLE = "Sample data (fill_demo): remove with app.tools.fill_demo --remove."
# The customer types a sample customer is given, where the company has them; otherwise any.
PREFERRED = ("customer", "prospect", "hospital", "drugstore", "drugstore_chain", "distributor", "wholesaler", "government_hospital", "partner")

KINDS = ("Pharmacy", "Drugstore", "Clinic", "Medical Center", "Hospital", "Diagnostics", "Wellness Center")
NAMES = (
    "Mercury", "Rose", "Southstar", "Generika", "TGP", "Watsons", "St. Luke's", "Makati Med", "Asian", "Cardinal",
    "Our Lady of Lourdes", "Unciano", "Perpetual Help", "Capitol", "Medical City", "Healthway", "Hi-Precision", "Unilab",
    "Bethany", "Sacred Heart", "San Lorenzo", "Del Monte", "Mabuhay", "Bayanihan", "Sampaguita", "Narra", "Banaue",
    "Agape", "Fatima", "St. Jude", "Divine Mercy", "Holy Family", "Good Shepherd", "Emmanuel", "Grace", "Shalom",
)
CITIES = ("Makati", "Pasig", "Quezon City", "Manila", "Taguig", "Mandaluyong", "Pasay", "Parañaque", "Las Piñas", "Caloocan",
          "Marikina", "Muntinlupa", "Cebu City", "Davao City", "Iloilo City", "Bacolod", "Cagayan de Oro", "Baguio")
INDUSTRIES = ("Retail pharmacy", "Hospital", "Clinic", "Distributor", "Diagnostics", "Government")
FIRST = ("Maria", "Jose", "Ana", "Juan", "Carmela", "Miguel", "Rosa", "Paolo", "Liza", "Ramon", "Teresa", "Carlo", "Grace",
         "Antonio", "Isabel", "Mark", "Joy", "Dennis", "Kristine", "Rafael", "Angelica", "Nestor", "Bea", "Arnel", "Cecilia")
LAST = ("Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza", "Torres", "Flores", "Villanueva", "Ramos",
        "Aquino", "Castillo", "Navarro", "Dela Cruz", "Gonzales", "Lim", "Tan", "Uy", "Sy", "Domingo", "Salazar", "Pascual")
TITLES = ("Purchasing officer", "Pharmacist", "Store manager", "Medical director", "Owner", "Procurement head",
          "Head nurse", "Chief pharmacist", "Finance officer", "Clinic secretary")
SPECIALTIES = ("Internal medicine", "Pediatrics", "Cardiology", "Urology", "Dermatology", "Oncology", "Family medicine", "OB-GYN")
SOURCES = ("Referral", "Website", "Cold call", "Event", "Existing customer")
CALLS = ("Followed up on the last order", "Checked stock levels", "Introduced the new price list", "Asked about the monthly order",
         "Confirmed delivery schedule", "Discussed payment terms", "Presented a new product")
TASKS = ("Send the updated quotation", "Prepare samples for the visit", "Follow up on the payment", "Book a product presentation",
         "Call about the reorder", "Send the product brochure")
MEETINGS = ("Product presentation", "Quarterly review", "Contract renewal meeting", "Lunch meeting with the pharmacist")
LOST = ("Price", "Went with a competitor", "No budget", "No response")


def now_utc() -> datetime:
    return datetime.now(UTC).replace(second=0, microsecond=0)


def refuse_real(db: Session, real_ok: bool) -> None:
    if get_settings().is_production:
        sys.exit("Demo records are for development only (ENVIRONMENT is production; run with ENVIRONMENT=development).")
    real = db.scalar(select(func.count()).select_from(User).where(~User.email.like("%.test")))
    if real and not real_ok:
        sys.exit(f"Refused: this company has {real} account(s) that aren't demo ones. Say --real to fill it all the same (its own reps get the records).")
    if db.scalar(select(func.count()).select_from(User)) == 0:
        sys.exit("No demo accounts yet. First: uv run python -m app.tools.users --company <name> demo")


def fill(db: Session, rnd: random.Random) -> list[Company]:
    if db.scalar(select(func.count()).select_from(Deal).where(Deal.notes == SAMPLE)):
        print("Records: already filled (there are sample deals here); going on to the quotes.")
        return list(db.scalars(select(Company).where(Company.notes == SAMPLE, Company.field_tier.is_(None)).order_by(Company.created_at)))
    users = list(db.scalars(select(User).where(User.is_active)))
    role = {u.id: (u.role.name if u.role else "") for u in users}
    reps = [u for u in users if role[u.id] in ("Salesperson", "Team Lead")]
    field = [u for u in users if role[u.id] == "Field agent"]
    types = [t.code for t in db.scalars(select(CustomerType).where(CustomerType.is_active))]
    sell = [t for t in PREFERRED if t in types] or [t for t in types if t not in ("doctor", "inactive")] or types
    now = now_utc()

    def ago(days_max: int, days_min: int = 0) -> datetime:
        return now - timedelta(days=rnd.uniform(days_min, days_max), hours=rnd.randint(0, 8))

    # Customers: 110 the reps sell to, 40 doctors the field agents visit.
    companies: list[Company] = []
    taken: set[str] = set()
    while len(companies) < 110:
        name = f"{rnd.choice(NAMES)} {rnd.choice(KINDS)} {rnd.choice(CITIES)}"
        if name in taken:
            continue
        taken.add(name)
        owner = rnd.choice(reps)
        city = name.rsplit(" ", 1)[-1] if name.split()[-1] in CITIES else rnd.choice(CITIES)
        slug = "".join(ch for ch in name.lower() if ch.isalnum())[:18]
        companies.append(Company(
            name=name, status=rnd.choices(sell, weights=[5 if t == "customer" else 3 if t == "prospect" else 1 for t in sell])[0],
            industry=rnd.choice(INDUSTRIES), city=city, country="Philippines", lead_source=rnd.choice(SOURCES),
            phone=f"+63 2 8{rnd.randint(100, 999)} {rnd.randint(1000, 9999)}", email=f"orders@{slug}.test",
            owner_id=owner.id, team_id=owner.team_id, created_by_id=owner.id, created_at=ago(120, 3), notes=SAMPLE,
        ))
    doctor_type = "doctor" if "doctor" in types else sell[0]
    for i in range(40):
        owner = field[i % len(field)] if field else rnd.choice(reps)
        lat, lng = 14.55 + rnd.uniform(-0.08, 0.08), 121.02 + rnd.uniform(-0.08, 0.08)
        companies.append(Company(
            name=f"Dr. {rnd.choice(FIRST)} {rnd.choice(LAST)}", status=doctor_type, industry=rnd.choice(SPECIALTIES),
            city=rnd.choice(CITIES[:12]), country="Philippines", phone=f"+63 9{rnd.randint(10, 99)} {rnd.randint(100, 999)} {rnd.randint(1000, 9999)}",
            latitude=lat, longitude=lng, pinned_at=ago(60, 30), pinned_by_id=owner.id,
            field_tier=rnd.choice((1, 2, 2, 3, 3)), field_zone=rnd.choice(("red", "yellow", "green", "green")), zone_set_at=ago(14),
            owner_id=owner.id, team_id=owner.team_id, created_by_id=owner.id, created_at=ago(120, 30), notes=SAMPLE,
        ))
    db.add_all(companies)
    db.flush()

    # Contacts: one to four at each customer the reps sell to.
    contacts: dict[str, list[Contact]] = {}
    for c in companies[:110]:
        for _ in range(rnd.choice((1, 2, 2, 3, 3, 4))):
            first, last = rnd.choice(FIRST), rnd.choice(LAST)
            person = Contact(
                company_id=c.id, first_name=first, last_name=last, job_title=rnd.choice(TITLES),
                email=f"{first.lower()}.{last.lower().replace(' ', '')}{rnd.randint(1, 99)}@example.test",
                mobile=f"+63 9{rnd.randint(10, 99)} {rnd.randint(100, 999)} {rnd.randint(1000, 9999)}",
                owner_id=c.owner_id, team_id=c.team_id, created_by_id=c.owner_id, created_at=c.created_at + timedelta(hours=1), notes=SAMPLE,
            )
            contacts.setdefault(c.id, []).append(person)
    db.add_all([p for ps in contacts.values() for p in ps])
    db.flush()

    # Activities: three months of calls, emails, notes and meetings done; tasks and meetings ahead (a few overdue).
    activities = 0
    for _ in range(560):
        c = rnd.choice(companies[:110])
        person = rnd.choice(contacts.get(c.id) or [None])
        kind = rnd.choices(("call", "email", "note", "meeting", "task"), weights=(6, 3, 2, 2, 2))[0]
        at = ago(90)
        subject = rnd.choice(MEETINGS if kind == "meeting" else TASKS if kind == "task" else CALLS)
        db.add(Activity(
            kind=kind, subject=subject, company_id=c.id, contact_id=person.id if person else None, at=at, done_at=at,
            duration_minutes=rnd.choice((5, 10, 15, 30)) if kind in ("call", "meeting") else None,
            direction=rnd.choice(("out", "out", "in")) if kind in ("call", "email") else None,
            outcome="Agreed to place an order next week." if kind == "meeting" and rnd.random() < 0.5 else None,
            owner_id=c.owner_id, team_id=c.team_id, created_by_id=c.owner_id, created_at=at,
        ))
        activities += 1
    for _ in range(90):
        c = rnd.choice(companies[:110])
        person = rnd.choice(contacts.get(c.id) or [None])
        kind = rnd.choice(("task", "task", "meeting"))
        at = (now + timedelta(days=rnd.randint(-6, 21))).replace(hour=rnd.choice((1, 2, 3, 5, 6, 7)), minute=0)
        db.add(Activity(
            kind=kind, subject=rnd.choice(MEETINGS if kind == "meeting" else TASKS), company_id=c.id,
            contact_id=person.id if person else None, at=at, done_at=None,
            owner_id=c.owner_id, team_id=c.team_id, created_by_id=c.owner_id, created_at=now - timedelta(days=rnd.randint(1, 10)),
        ))
        activities += 1

    # Deals: open ones across the stages, and some already won or lost.
    stages = {s.code: s for s in db.scalars(select(DealStage).where(DealStage.is_active))}
    open_stages = [s for s in stages.values() if s.outcome == "open"]
    won = next((s for s in stages.values() if s.outcome == "won"), None)
    lost = next((s for s in stages.values() if s.outcome == "lost"), None)
    for i in range(60):
        c = rnd.choice(companies[:110])
        person = rnd.choice(contacts.get(c.id) or [None])
        made = ago(100, 5)
        stage = won if i % 6 == 0 and won else lost if i % 6 == 1 and lost else rnd.choice(open_stages)
        closed = stage.outcome != "open"
        closed_at = made + timedelta(days=rnd.randint(5, 40)) if closed else None
        if closed_at and closed_at > now:
            closed_at = now - timedelta(days=rnd.randint(0, 4))
        close_on = (closed_at.date() if closed_at else date.today() + timedelta(days=rnd.randint(-5, 90))).isoformat()
        db.add(Deal(
            name=f"{c.name.split(' ')[0]} {rnd.choice(('monthly supply', 'annual contract', 'new branch', 'Q4 order', 'formulary listing'))}",
            company_id=c.id, contact_id=person.id if person else None, stage_code=stage.code, probability=stage.probability,
            forecast_category=stage.forecast_category, value_centavos=rnd.randint(20, 900) * 100_000, expected_close_on=close_on,
            lead_source=c.lead_source, priority=rnd.choice((None, "low", "medium", "high", "urgent")),
            closed_at=closed_at, lost_reason=rnd.choice(LOST) if stage is lost else None, notes=SAMPLE,
            owner_id=c.owner_id, team_id=c.team_id, created_by_id=c.owner_id, created_at=made,
        ))

    # Visits: the field agents' last two months at their doctors.
    doctors = companies[110:]
    for _ in range(50):
        d = rnd.choice(doctors)
        outcome = rnd.choices(("detailed", "collected", "promised", "not_in"), weights=(5, 2, 1, 1))[0]
        at = ago(60).replace(hour=rnd.randint(0, 8))
        db.add(Visit(
            company_id=d.id, visited_at=at, outcome=outcome,
            amount_centavos=rnd.randint(5, 80) * 100_000 if outcome == "collected" else 0,
            receipt_no=f"OR-{rnd.randint(10000, 99999)}" if outcome == "collected" else None,
            latitude=d.latitude, longitude=d.longitude, accuracy_m=rnd.randint(8, 40), distance_m=rnd.randint(2, 60),
            care_group=rnd.choice((None, "enrolled", "followed_up", "not_now")),
            owner_id=d.owner_id, team_id=d.team_id, created_by_id=d.owner_id, created_at=at,
        ))
    summary = f"{len(companies)} customers, {sum(len(v) for v in contacts.values())} contacts, {activities} activities, 60 deals, 50 visits"
    audit(db, TOOL, "demo.filled", target=summary)
    db.commit()
    print(f"Made {summary}.")
    return companies[:110]


def make_quotes(company: str, db: Session, rnd: random.Random, customers: list[Company], count: int = 80) -> None:
    """Through the API, as each customer's own rep: prices, numbers and approvals as the real rules make them."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    if db.scalar(select(func.count()).select_from(Quote).where(Quote.company_id.in_([c.id for c in customers]))):
        print("Quotes: skipped, the sample customers have quotes already.")
        return
    products = [p.id for p in db.scalars(select(Product).where(Product.is_active))]
    if not products:
        print("Quotes: skipped, no products on sale.")
        return
    made = failed = 0
    # A sign-in for each rep, made here and deleted after (no one's password is used).
    tokens: dict[str, str] = {}
    sessions: list[SignInSession] = []
    for owner_id in {c.owner_id for c in customers[:count]}:
        token = f"{company}.{new_token()}"
        tokens[owner_id] = token
        sessions.append(SignInSession(token_hash=token_hash(token), user_id=owner_id, expires_at=datetime.now(UTC) + timedelta(hours=1)))
    db.add_all(sessions)
    db.commit()
    with TestClient(create_app(get_settings()), base_url="http://127.0.0.1") as client:
        for i in range(count):
            c = customers[i % len(customers)]
            lines = [{"productId": pid, "quantity": rnd.choice((1, 2, 5, 10, 20))} for pid in rnd.sample(products, k=min(len(products), rnd.randint(1, 4)))]
            body = {"priceType": rnd.choice(("PATIENT", "TRADE", "TRADE")), "lines": lines, "notes": None}
            r = client.post(f"/companies/{c.id}/quotes", data={"quote": json.dumps(body)}, headers={"Authorization": f"Bearer {tokens[c.owner_id]}"})
            if r.status_code == 201:
                made += 1
            else:
                failed += 1
                if failed <= 3:
                    print(f"  a quote was refused ({r.status_code}): {r.text[:200]}")
    for session in sessions:
        db.delete(session)
    db.commit()
    print(f"Made {made} quotes" + (f"; {failed} refused." if failed else "."))


def remove(db: Session) -> None:
    """Takes out every record this tool made: the customers marked SAMPLE, and all that hangs on them."""
    ids = list(db.scalars(select(Company.id).where(Company.notes == SAMPLE)))
    counts = {}
    for model in (Quote, Visit, Activity, Deal, Contact):
        rows = list(db.scalars(select(model).where(model.company_id.in_(ids))))
        counts[model.__tablename__.removeprefix("nbcm_")] = len(rows)
        for row in rows:
            db.delete(row)
        db.flush()
    for c in db.scalars(select(Company).where(Company.id.in_(ids))):
        db.delete(c)
    counts["companies"] = len(ids)
    summary = ", ".join(f"{n} {k}" for k, n in counts.items())
    audit(db, TOOL, "demo.removed", target=summary)
    db.commit()
    print(f"Removed {summary}.")


def history_days(rnd: random.Random, today: date) -> tuple[str, list[date]]:
    """When one customer was quoted over the last year, by the kind of customer it is.

    Retention reads only these dates (app/routers/retention.py): healthy is a
    quote within the at-risk window, at risk within the lost window, lost
    beyond it; the rate compares two lost windows back to back."""

    def every(start: date, end: date) -> list[date]:
        out, day = [], start
        while day <= end:
            out.append(day)
            day += timedelta(days=rnd.randint(18, 40))
        return out

    year_ago = today - timedelta(days=rnd.randint(300, 365))
    kind = rnd.choices(("regular", "slipping", "lost", "new", "won back", "never"), weights=(45, 15, 15, 10, 7, 8))[0]
    if kind == "regular":
        return kind, every(year_ago, today - timedelta(days=rnd.randint(0, 25)))
    if kind == "slipping":
        return kind, every(year_ago, today - timedelta(days=rnd.randint(35, 85)))
    if kind == "lost":
        return kind, every(year_ago, today - timedelta(days=rnd.randint(100, 240)))
    if kind == "new":
        return kind, every(today - timedelta(days=rnd.randint(15, 80)), today - timedelta(days=rnd.randint(0, 10)))
    if kind == "won back":
        return kind, every(year_ago, today - timedelta(days=rnd.randint(190, 230))) + every(today - timedelta(days=rnd.randint(20, 45)), today)
    return kind, []


def quote_history(company: str, db: Session, rnd: random.Random, customers: list[Company]) -> None:
    """A year of quotes for the sample customers, so Retention has a history to read.

    Each is made through the API (prices and rules as a rep's), then given its
    day: created on it, valid from it, and numbered in its own month. Replaces
    the sample customers' quotes, if they have any."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers.quotes import next_number

    ids = [c.id for c in customers]
    for q in db.scalars(select(Quote).where(Quote.company_id.in_(ids))):
        db.delete(q)
    db.commit()
    products = [p.id for p in db.scalars(select(Product).where(Product.is_active))]
    if not products:
        print("Quote history: skipped, no products on sale.")
        return
    today = date.today()
    plan = []
    kinds: dict[str, int] = {}
    for c in customers:
        kind, days = history_days(rnd, today)
        kinds[kind] = kinds.get(kind, 0) + 1
        plan += [(day, c) for day in days]
    plan.sort(key=lambda x: x[0])
    tokens: dict[str, str] = {}
    sessions: list[SignInSession] = []
    for owner_id in {c.owner_id for c in customers}:
        token = f"{company}.{new_token()}"
        tokens[owner_id] = token
        sessions.append(SignInSession(token_hash=token_hash(token), user_id=owner_id, expires_at=datetime.now(UTC) + timedelta(hours=2)))
    db.add_all(sessions)
    db.commit()
    valid_days = 30
    made = failed = 0
    with TestClient(create_app(get_settings()), base_url="http://127.0.0.1") as client:
        for n, (day, c) in enumerate(plan):
            lines = [{"productId": pid, "quantity": rnd.choice((1, 2, 5, 10, 20))} for pid in rnd.sample(products, k=min(len(products), rnd.randint(1, 4)))]
            body = {"priceType": rnd.choice(("PATIENT", "TRADE", "TRADE")), "lines": lines, "notes": None}
            r = client.post(f"/companies/{c.id}/quotes", data={"quote": json.dumps(body)}, headers={"Authorization": f"Bearer {tokens[c.owner_id]}"})
            if r.status_code != 201:
                failed += 1
                if failed <= 3:
                    print(f"  a quote was refused ({r.status_code}): {r.text[:200]}")
                continue
            q = db.get(Quote, r.json()["id"])
            db.refresh(q)
            if q.created_at.date() != day:
                at = datetime(day.year, day.month, day.day, rnd.randint(1, 9), rnd.randint(0, 59), tzinfo=UTC)
                if day.strftime("%Y%m") != today.strftime("%Y%m"):
                    q.number = next_number(db, day.isoformat())
                q.created_at = q.updated_at = at
                q.valid_until = (day + timedelta(days=valid_days)).isoformat()
                db.commit()
            made += 1
            if made % 100 == 0:
                print(f"  {made} of {len(plan)}…")
    for session in sessions:
        db.delete(session)
    db.commit()
    print(f"Quote history: {made} quotes over the last year" + (f" ({failed} refused)" if failed else "") + "; customers: " + ", ".join(f"{n} {k}" for k, n in kinds.items()) + ".")


def main() -> int:
    company, url = for_tool(sys.argv)
    print(f"Company: {company}")
    engine = make_engine(url)
    upgrade(engine)
    rnd = random.Random(7)
    with make_sessions(engine)() as db:
        if "--remove" in sys.argv:
            remove(db)
            return 0
        refuse_real(db, "--real" in sys.argv)
        if "--retention" in sys.argv:
            # Only the quote history, for customers this tool already made.
            customers = list(db.scalars(select(Company).where(Company.notes == SAMPLE, Company.field_tier.is_(None)).order_by(Company.created_at)))
            if not customers:
                sys.exit("No sample customers yet: run without --retention first.")
            quote_history(company, db, rnd, customers)
            return 0
        customers = fill(db, rnd)
        quote_history(company, db, rnd, customers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
