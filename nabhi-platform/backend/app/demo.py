"""This app's demo accounts and sample records, for development.

`uv run python -m app.tools.users demo` makes the accounts (password
demo1234) and, into a platform with no companies yet, a few sample companies,
people, tickets and an incident, so every screen has something on it. The
sign-in page lists the demo accounts that exist here. None of it works in
production.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.numbers import TICKET_PREFIXES
from app.security import hash_password
from app.models import (
    Announcement,
    Application,
    Company,
    CompanyApp,
    Identity,
    IdentityApp,
    Incident,
    IncidentCompany,
    IncidentUpdate,
    OrgUnit,
    AccessRequest,
    Ticket,
    TicketNote,
    User,
)

DEMO_PASSWORD = "demo1234"


@dataclass(frozen=True)
class Demo:
    group: str
    email: str
    name: str
    role: str
    admin: bool = False


DEMO_ACCOUNTS: tuple[Demo, ...] = (
    Demo("Platform", "jun@pharmacrm.test", "Jun Espino", "Platform Admin · everything", admin=True),
    Demo("Platform", "lea@pharmacrm.test", "Lea Santos", "Support · tickets and incidents"),
)

# name, slug, status, apps, departments, branches
COMPANIES = (
    ("GetMeds", "getmeds", "active", ("crm", "inventory", "pharmacy", "exec", "finance"), ("Sales", "Pharmacy", "Finance"), ("Makati", "Cebu")),
    ("Northwind Pharma", "northwind", "active", ("crm", "inventory"), ("Sales", "Warehouse"), ("Pasig",)),
    ("Bayside Clinics", "bayside", "suspended", ("pharmacy",), ("Dispensary",), ("Iloilo",)),
)

# name, email, company slug, title, company admin, {app: role}
PEOPLE = (
    ("Maria Santos", "maria@getmeds.test", "getmeds", "Pharmacist", False, {"pharmacy": "Pharmacist", "inventory": "Viewer"}),
    ("Jade Madigal", "jade@getmeds.test", "getmeds", "Operations lead", True, {"crm": "Administrator", "inventory": "Manager", "pharmacy": "Supervisor"}),
    ("Paolo Reyes", "paolo@getmeds.test", "getmeds", "Sales rep", False, {"crm": "Salesperson"}),
    ("Ana Lim", "ana@northwind.test", "northwind", "Managing director", True, {"crm": "Administrator", "inventory": "Manager"}),
    ("Rico Tan", "rico@northwind.test", "northwind", "Warehouse clerk", False, {"inventory": "Clerk"}),
    ("Grace Uy", "grace@bayside.test", "bayside", "Head pharmacist", True, {"pharmacy": "Administrator"}),
)


def seed_sample(db: Session, by: str) -> bool:
    """Sample records, into a platform with no companies. False if it had some."""
    if db.scalar(select(func.count()).select_from(Company)):
        return False
    now = datetime.now(UTC)
    apps = {a.key: a for a in db.scalars(select(Application))}
    companies: dict[str, Company] = {}
    for name, slug, status, keys, departments, branches in COMPANIES:
        c = Company(name=name, slug=slug, status=status, contact_email=f"it@{slug}.test", suspended_at=now if status == "suspended" else None)
        db.add(c)
        db.flush()
        companies[slug] = c
        for key in keys:
            if key in apps:
                db.add(CompanyApp(company_id=c.id, application_id=apps[key].id))
        for d in departments:
            db.add(OrgUnit(company_id=c.id, kind="department", name=d))
        for b in branches:
            db.add(OrgUnit(company_id=c.id, kind="branch", name=b, location=f"{b} City"))
    people: dict[str, Identity] = {}
    for name, email, slug, title, admin, roles in PEOPLE:
        person = Identity(company_id=companies[slug].id, full_name=name, email=email, title=title, is_company_admin=admin,
                          last_active_at=now - timedelta(hours=len(people) * 5), password_hash=hash_password(DEMO_PASSWORD))
        db.add(person)
        db.flush()
        people[email] = person
        for key, role in roles.items():
            db.add(IdentityApp(identity_id=person.id, application_id=apps[key].id, role=role, is_app_admin=role == "Administrator", granted_by=by))
    db.add(AccessRequest(identity_id=people["paolo@getmeds.test"].id, application_id=apps["inventory"].id, role="Viewer",
                         reason="To check stock before quoting."))

    lead = db.scalar(select(User).where(User.role == "admin"))
    incident = Incident(number=f"INC-{now.year}-0001", title="Pharmacy dispensing is slow for some companies", kind="performance",
                        severity="major", status="identified", application_id=apps["pharmacy"].id, lead_id=lead.id if lead else None,
                        summary="Dispensing pages take over ten seconds to open.", started_at=now - timedelta(hours=3), created_by=by)
    db.add(incident)
    db.flush()
    db.add(IncidentCompany(incident_id=incident.id, company_id=companies["getmeds"].id))
    db.add(IncidentUpdate(incident_id=incident.id, status="investigating", body="Reports of slow dispensing pages. Looking into it.",
                          author="Jun Espino", created_at=now - timedelta(hours=3)))
    db.add(IncidentUpdate(incident_id=incident.id, status="identified", body="A missing index on batches. A fix is being tested.",
                          author="Jun Espino", created_at=now - timedelta(hours=1)))

    tickets = (
        ("bug", "Dispensing page does not load", "high", "investigating", "pharmacy", "getmeds", "maria@getmeds.test", incident.id, 26),
        ("bug", "Quote PDF shows the wrong currency", "critical", "reported", "crm", "northwind", "ana@northwind.test", None, 40),
        ("complaint", "Sign-in takes too long in the mornings", "medium", "triaged", "crm", "getmeds", "paolo@getmeds.test", None, None),
        ("feature", "Export stock counts to Excel", "low", "reported", "inventory", "northwind", "rico@northwind.test", None, None),
        ("support", "How do I add a branch?", "low", "resolved", None, "getmeds", "jade@getmeds.test", None, None),
        ("issue", "Nightly price sync ran twice", "medium", "fixing", "inventory", "getmeds", "jade@getmeds.test", None, None),
    )
    counts: dict[str, int] = {}
    for kind, title, severity, status, app, slug, email, incident_id, affected in tickets:
        counts[kind] = counts.get(kind, 0) + 1
        person = people[email]
        t = Ticket(number=f"{TICKET_PREFIXES[kind]}-{now.year}-{counts[kind]:05d}", kind=kind, title=title, severity=severity, status=status,
                   application_id=apps[app].id if app else None, company_id=companies[slug].id, identity_id=person.id,
                   reporter_name=person.full_name, reporter_email=person.email, incident_id=incident_id, affected_users=affected,
                   assignee_id=lead.id if lead and status not in ("reported", "triaged") else None,
                   created_at=now - timedelta(hours=6 * counts[kind] + 2), updated_at=now,
                   resolved_at=now if status == "resolved" else None)
        db.add(t)
        db.flush()
        db.add(TicketNote(ticket_id=t.id, author=person.full_name, body=f"Reported by {person.full_name}.", status_to="reported",
                          created_at=t.created_at))
    db.add(Announcement(kind="maintenance", level="warning", title="Database upgrade on Saturday night",
                        body="Every application is read-only for about 20 minutes while the database is upgraded.",
                        starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=2, minutes=30), published_at=now, created_by=by))
    return True

