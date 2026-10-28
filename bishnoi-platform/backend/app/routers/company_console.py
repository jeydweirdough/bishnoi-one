"""The company console (feature plan step 5, 2026-10-28): what a company's own administrators
keep about their company in the Admin Console, signed in with their Bishnoi One account. People,
roles and the org chart are in company_access.py and organisation.py; this is the rest.

- GET/PATCH /identity/company: the company's profile (name, contact email, time zone, currency).
- GET  /identity/company/apps: the apps the company has, and how many people may open each.
- GET  /identity/company/services, PUT …/services/{key}, POST …/services/{key}/check: its outside
  services (email sending, Zoho Books, lead channels), the same as Bishnoi One's operators keep.
- GET  /identity/company/activity: the company's activity log, newest first.
- GET  /identity/company/security, POST …/security/people/{id}/sign-out: who has a password,
  when each last signed in, open sign-ins, and ending a person's sign-ins.

Every change is in the audit log (names of what changed, never values).
"""

from datetime import UTC, datetime
from zoneinfo import available_timezones

from fastapi import APIRouter, Request
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select

from app import abilities as ab
from app import catalogue as catalogue_on
from app import services as svc
from app.access_roles import modules_of
from app.accounts import account_of
from app.api import Api, changed, check_email, conflict, field_error, iso, not_found
from app.audit import audit
from app.company_push import apps_of, push as push_company
from app.deps import DB, SettingsDep, as_utc
from app.models import Application, AuditEntry, Company, CompanyApp, CompanySwitch, Identity, IdentityApp, IdentitySession
from app.routers import services as service_routes
from app.routers.activity import entry_out
from app.routers.company_access import Admin, get_person

router = APIRouter(prefix="/identity/company", tags=["company console"])

PAGE = 50


def company_out(c: Company) -> dict:
    return {"id": c.id, "no": c.no, "name": c.name, "slug": c.slug, "status": c.status, "currency": c.currency,
            "timezone": c.timezone, "contactEmail": c.contact_email, "createdAt": iso(c.created_at)}


@router.get("")
def profile(db: DB, me: Admin) -> dict:
    return {"company": company_out(db.get(Company, me.company_id))}


class CompanyPatch(Api):
    name: str | None = Field(None, min_length=2, max_length=120)
    contact_email: str | None = Field(None, max_length=254)
    timezone: str | None = Field(None, max_length=64)
    currency: str | None = Field(None, min_length=3, max_length=3)

    @field_validator("contact_email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value) if value else None


@router.patch("")
def change_profile(body: CompanyPatch, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    c = db.get(Company, me.company_id)
    fields = changed(body)
    if "name" in fields and not fields["name"]:
        raise field_error("name", "Give the company a name.")
    if fields.get("timezone") and fields["timezone"] not in available_timezones():
        raise field_error("timezone", "Pick a time zone from the list, such as Asia/Manila.")
    if "currency" in fields:
        fields["currency"] = (fields["currency"] or c.currency).upper()
    fields = {k: (v.strip() if isinstance(v, str) else v) for k, v in fields.items() if getattr(c, k) != v and not (k != "contact_email" and v is None)}
    for k, v in fields.items():
        setattr(c, k, v)
    if fields:
        audit(db, me.email, "company.updated", target=c.name, target_type="company", target_id=c.id, company_id=c.id, fields=sorted(fields))
        db.commit()
        # Each app keeps its company's name and settings from the company pass.
        push_company(request.app.state.sessions, settings, c.id, apps_of(db, c.id))
    return {"company": company_out(c)}


@router.get("/apps")
def apps(db: DB, me: Admin) -> dict:
    people = dict(db.execute(
        select(IdentityApp.application_id, func.count()).join(Identity, Identity.id == IdentityApp.identity_id)
        .where(Identity.company_id == me.company_id, Identity.status == "active").group_by(IdentityApp.application_id)
    ).all())
    admins = db.scalar(select(func.count()).select_from(Identity).where(Identity.company_id == me.company_id, Identity.status == "active", Identity.is_company_admin,
                                                                         Identity.via_operator.is_(False))) or 0
    return {"apps": [{"key": a.key, "name": a.name, "description": a.description, "appUrl": a.app_url,
                      # Company administrators open every app the company has.
                      "people": people.get(a.id, 0), "administrators": admins} for a in modules_of(db, me.company_id)]}


# ---- The app catalogue (feature plan step 6): apps to turn on, and features inside each ------------


@router.get("/catalogue")
def catalogue(db: DB, me: Admin) -> dict:
    on = catalogue_on.switches(db, me.company_id)
    services = catalogue_on.services_of(db, me.company_id)
    offered = {a.key for a in db.scalars(select(Application).where(Application.is_active))}
    return {"apps": [{
        "key": a.key, "name": a.name, "job": a.job, "service": a.service, "later": a.later,
        "on": on[ab.app_switch(a.key)],
        # The service it runs in: the company has it, or it can be added (registered and running), or not yet.
        "available": a.service in services or a.service in offered,
        "switches": [{"key": s.key, "label": s.label, "hint": s.hint, "later": s.later, "on": on[s.key]} for s in a.switches],
    } for a in ab.CATALOGUE]}


class SwitchIn(Api):
    on: bool


@router.put("/catalogue/{key}")
def switch(key: str, body: SwitchIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    """Turns a catalogue app (its key) or a feature ("inventory.batches") on or off. Turning on an app
    whose service the company doesn't have yet adds the service, as an operator would."""
    if key in ab.APPS:
        app, feature, stored = ab.APPS[key], None, ab.app_switch(key)
    elif key in ab.SWITCHES:
        app, feature = ab.SWITCHES[key]
        stored = key
    else:
        raise not_found("app or feature")
    if body.on and (app.later or (feature and feature.later)):
        raise conflict(f"{feature.label if feature else app.name} isn't ready yet. It's on the plan.")
    services = catalogue_on.services_of(db, me.company_id)
    if body.on and app.service not in services:
        if feature:
            raise conflict(f"Turn {app.name} on first.")
        service = db.scalar(select(Application).where(Application.key == app.service, Application.is_active))
        if service is None:
            raise conflict(f"{app.name} isn't available yet. Ask Bishnoi One's operators.")
        db.add(CompanyApp(company_id=me.company_id, application_id=service.id))
    row = db.get(CompanySwitch, (me.company_id, stored))
    if row is None:
        row = CompanySwitch(company_id=me.company_id, key=stored, is_on=body.on, updated_by=me.email)
        db.add(row)
    row.is_on, row.updated_by, row.updated_at = body.on, me.email, datetime.now(UTC)
    audit(db, me.email, "catalogue.switched_on" if body.on else "catalogue.switched_off", target=feature.label if feature else app.name,
          target_type="company", target_id=me.company_id, company_id=me.company_id, fields=[stored])
    db.commit()
    # Each app hears at once (its company pass carries its switches).
    push_company(request.app.state.sessions, settings, me.company_id, apps_of(db, me.company_id))
    return catalogue(db, me)


# ---- Integrations: the company's outside services ------------------------------------------------


@router.get("/services")
def services(db: DB, me: Admin, settings: SettingsDep) -> dict:
    company = db.get(Company, me.company_id)
    return {"services": [service_routes._out(db, settings, s, service_routes.row_of(db, company, s.key)) for s in svc.SERVICES]}


@router.put("/services/{key}")
def save_service(key: str, body: service_routes.ServiceIn, db: DB, me: Admin, settings: SettingsDep) -> dict:
    return service_routes.save(db, settings, db.get(Company, me.company_id), key, body, me.email, None)


@router.post("/services/{key}/check")
def check_service(key: str, db: DB, me: Admin, settings: SettingsDep) -> dict:
    return service_routes.check(db, settings, db.get(Company, me.company_id), key, me.email)


# ---- Activity log ---------------------------------------------------------------------------------


@router.get("/activity")
def activity(db: DB, me: Admin, q: str | None = None, category: str | None = None, before: datetime | None = None) -> dict:
    """A page of the company's log. `before` (the last one's `at`) gets the next page. Bishnoi One's own
    system entries (health checks, connections) aren't the company's and aren't shown."""
    query = select(AuditEntry).where(AuditEntry.company_id == me.company_id).order_by(AuditEntry.created_at.desc())
    if category in ("admin", "security"):
        query = query.where(AuditEntry.category == category)
    else:
        query = query.where(AuditEntry.category.in_(("admin", "security", "support")))
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(AuditEntry.actor).like(like), func.lower(AuditEntry.target).like(like), func.lower(AuditEntry.action).like(like)))
    if before:
        query = query.where(AuditEntry.created_at < before)
    rows = db.scalars(query.limit(PAGE + 1)).all()
    return {"entries": [entry_out(e) for e in rows[:PAGE]], "more": len(rows) > PAGE}


# ---- Security -------------------------------------------------------------------------------------


@router.get("/security")
def security(db: DB, me: Admin) -> dict:
    now = datetime.now(UTC)
    people = db.scalars(select(Identity).where(Identity.company_id == me.company_id, Identity.via_operator.is_(False))
                        .order_by(func.lower(Identity.full_name))).all()
    open_by: dict[str, int] = {}
    for s in db.scalars(select(IdentitySession).join(Identity, Identity.id == IdentitySession.identity_id)
                        .where(Identity.company_id == me.company_id, IdentitySession.revoked_at.is_(None))):
        if as_utc(s.expires_at) > now:
            open_by[s.identity_id] = open_by.get(s.identity_id, 0) + 1
    out = []
    for p in people:
        account = account_of(db, p)
        out.append({
            "id": p.id, "fullName": p.full_name, "email": p.email, "status": p.status, "isCompanyAdmin": p.is_company_admin,
            "hasPassword": bool(account and account.password_hash),
            "passwordChangedAt": iso(account.password_changed_at) if account else None,
            "lastActiveAt": iso(p.last_active_at),
            "openSignIns": open_by.get(p.id, 0),
        })
    return {
        "people": out,
        "withoutPassword": sum(1 for p in out if p["status"] == "active" and not p["hasPassword"]),
        "administrators": sum(1 for p in out if p["status"] == "active" and p["isCompanyAdmin"]),
        "openSignIns": sum(open_by.values()),
    }


@router.post("/security/people/{person_id}/sign-out")
def sign_out(person_id: str, db: DB, me: Admin) -> dict:
    """Ends every open sign-in of this person at the company (their next step asks them to sign in again)."""
    p = get_person(db, me, person_id)
    now, ended = datetime.now(UTC), 0
    for s in db.scalars(select(IdentitySession).where(IdentitySession.identity_id == p.id, IdentitySession.revoked_at.is_(None))):
        s.revoked_at, ended = now, ended + 1
    audit(db, me.email, "security.signed_out_person", category="security", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    return {"ended": ended}

