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
- GET  /identity/company/overview: the Admin Console's Home (2026-10-30): people, sign-ins, security
  and access by app, counted for the company (user control; finance figures are in Reports).
- GET  /identity/company/administrators, PUT …/administrators/{id} {on}: who runs the company in
  Bishnoi One, made or unmade by another administrator (2026-10-30). Never yourself off, never the
  last one; someone unmade signs in again (their sign-ins end) and opens the console no more.

Every change is in the audit log (names of what changed, never values).
"""

from datetime import UTC, datetime
from zoneinfo import available_timezones

from fastapi import APIRouter, Request
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select

import base64

from app import abilities as ab
from app import email_rules, signatures
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
from app.routers.identity import Signed

router = APIRouter(prefix="/identity/company", tags=["company console"])

PAGE = 50


def company_out(c: Company) -> dict:
    return {"id": c.id, "no": c.no, "name": c.name, "slug": c.slug, "status": c.status, "currency": c.currency,
            "timezone": c.timezone, "contactEmail": c.contact_email, "emailDomain": c.email_domain, "createdAt": iso(c.created_at),
            # The letterhead (step 10).
            "legalName": c.legal_name, "address": c.address, "tin": c.tin, "phone": c.phone, "documentFooter": c.document_footer,
            "logo": signatures.data_url(c.logo, c.logo_type or "image/png") if c.logo else None}


LOGO_TYPES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
MAX_LOGO = 400_000


def logo_of(value: str) -> tuple[bytes, str]:
    """A PNG or JPEG logo from a data URL, checked."""
    raw = value.split(",", 1)[1] if value.startswith("data:") else value
    try:
        image = base64.b64decode(raw, validate=True)
    except ValueError:
        raise field_error("logo", "That isn't an image.") from None
    if len(image) > MAX_LOGO:
        raise field_error("logo", "The logo is too large: keep it under 400 KB.")
    kind = next((k for head, k in LOGO_TYPES.items() if image.startswith(head)), None)
    if kind is None:
        raise field_error("logo", "The logo must be a PNG or JPEG image.")
    return image, kind


@router.get("/letterhead")
def letterhead(signed: Signed, db: DB) -> dict:
    """The company's letterhead, for printing any of its documents (any of its people may read it)."""
    _, person = signed
    c = db.get(Company, person.company_id)
    return {"name": c.name, "legalName": c.legal_name or c.name, "address": c.address, "tin": c.tin, "phone": c.phone, "email": c.contact_email,
            "footer": c.document_footer, "logo": signatures.data_url(c.logo, c.logo_type or "image/png") if c.logo else None}


def off_domain(db, c: Company) -> list[dict]:
    """Its people whose email isn't at its domain: they can't sign in until it's changed."""
    if not c.email_domain:
        return []
    people = db.scalars(select(Identity).where(Identity.company_id == c.id, Identity.via_operator.is_(False), Identity.status == "active")
                        .order_by(Identity.full_name)).all()
    return [{"id": p.id, "fullName": p.full_name, "email": p.email} for p in people if email_rules.domain_of(p.email) != c.email_domain]


@router.get("")
def profile(db: DB, me: Admin) -> dict:
    c = db.get(Company, me.company_id)
    return {"company": company_out(c), "offDomain": off_domain(db, c)}


class CompanyPatch(Api):
    name: str | None = Field(None, min_length=2, max_length=120)
    contact_email: str | None = Field(None, max_length=254)
    timezone: str | None = Field(None, max_length=64)
    currency: str | None = Field(None, min_length=3, max_length=3)
    legal_name: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=400)
    tin: str | None = Field(None, max_length=30)
    phone: str | None = Field(None, max_length=40)
    document_footer: str | None = Field(None, max_length=400)
    # Its people's email domain (getmeds.ph); "" clears it (app/email_rules.py).
    email_domain: str | None = Field(None, max_length=254)
    # A PNG or JPEG as a data URL; "" removes it.
    logo: str | None = Field(None, max_length=600_000)

    @field_validator("contact_email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value) if value else None


@router.patch("")
def change_profile(body: CompanyPatch, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    c = db.get(Company, me.company_id)
    fields = changed(body)
    logo_changed = "logo" in fields
    if "logo" in fields:
        logo = fields.pop("logo")
        if logo:
            c.logo, c.logo_type = logo_of(logo)
        else:
            c.logo, c.logo_type = None, None
        audit(db, me.email, "company.updated", target=c.name, target_type="company", target_id=c.id, company_id=c.id, fields=["logo"])
    LETTER = ("legal_name", "address", "tin", "phone", "document_footer")
    if "name" in fields and not fields["name"]:
        raise field_error("name", "Give the company a name.")
    if fields.get("timezone") and fields["timezone"] not in available_timezones():
        raise field_error("timezone", "Pick a time zone from the list, such as Asia/Manila.")
    if "currency" in fields:
        fields["currency"] = (fields["currency"] or c.currency).upper()
    if "email_domain" in fields:
        fields["email_domain"] = email_rules.check_domain(db, c, fields["email_domain"]) or ""
    fields = {k: ((v.strip() or None) if k in LETTER and isinstance(v, str) else v.strip() if isinstance(v, str) else v)
              for k, v in fields.items() if getattr(c, k) != v and not (k not in ("contact_email", *LETTER) and v is None)}
    if fields.get("email_domain") == "":
        fields["email_domain"] = None
    if "email_domain" in fields and getattr(c, "email_domain") == fields["email_domain"]:
        del fields["email_domain"]
    for k, v in fields.items():
        setattr(c, k, v)
    if fields or logo_changed:
        if fields:
            audit(db, me.email, "company.updated", target=c.name, target_type="company", target_id=c.id, company_id=c.id, fields=sorted(fields))
        db.commit()
        # Each app keeps its company's name and settings from the company pass.
        push_company(request.app.state.sessions, settings, c.id, apps_of(db, c.id))
    return {"company": company_out(c), "offDomain": off_domain(db, c)}


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



# ---- Company administrators (2026-10-30) --------------------------------------------------------


def _admins(db, company_id: str) -> list[Identity]:
    return db.scalars(select(Identity).where(Identity.company_id == company_id, Identity.is_company_admin, Identity.status == "active",
                                             Identity.via_operator.is_(False)).order_by(Identity.full_name)).all()


@router.get("/administrators")
def administrators(db: DB, me: Admin) -> dict:
    people = db.scalars(select(Identity).where(Identity.company_id == me.company_id, Identity.status == "active",
                                               Identity.via_operator.is_(False)).order_by(Identity.full_name)).all()
    out = lambda p: {"id": p.id, "fullName": p.full_name, "email": p.email, "title": p.title, "isMe": p.id == me.id}  # noqa: E731
    return {"administrators": [out(p) for p in people if p.is_company_admin], "others": [out(p) for p in people if not p.is_company_admin]}


class AdministratorIn(Api):
    on: bool


@router.put("/administrators/{person_id}")
def set_administrator(person_id: str, body: AdministratorIn, db: DB, me: Admin) -> dict:
    p = get_person(db, me, person_id)
    if p.is_company_admin == body.on:
        return administrators(db, me)
    if body.on and p.status != "active":
        raise conflict(f"{p.full_name} is switched off. Switch them on first on People.")
    if not body.on:
        if p.id == me.id:
            raise conflict("You can't remove yourself. Another administrator can.")
        if not [a for a in _admins(db, me.company_id) if a.id != p.id]:
            raise conflict(f"{p.full_name} is the company's only administrator. Make someone else one first.")
    p.is_company_admin = body.on
    if not body.on:
        # Their console is closed at once: they sign in again, without it.
        now = datetime.now(UTC)
        for s in db.scalars(select(IdentitySession).where(IdentitySession.identity_id == p.id, IdentitySession.revoked_at.is_(None))):
            s.revoked_at = now
    audit(db, me.email, "company.administrator_added" if body.on else "company.administrator_removed", category="security",
          target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    return administrators(db, me)


# ---- The Admin Console's Home (2026-10-30): user control at a glance --------------------------------


@router.get("/overview")
def overview(db: DB, me: Admin, settings: SettingsDep) -> dict:
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from app import sign_in
    from app.models import AccessRole, SignInFailure, SignInLink

    company = db.get(Company, me.company_id)
    everyone = db.scalars(select(Identity).where(Identity.company_id == me.company_id, Identity.via_operator.is_(False))).all()
    active = [p for p in everyone if p.status == "active" and p.deleted_at is None]
    accounts = {p.id: account_of(db, p) for p in active}
    granted = {i for (i,) in db.execute(select(IdentityApp.identity_id).join(Identity, Identity.id == IdentityApp.identity_id)
                                        .where(Identity.company_id == me.company_id)).all()}
    now = datetime.now(UTC)
    zone = ZoneInfo(company.timezone or "Asia/Manila")
    midnight = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    seen = {pid: as_utc(a.last_sign_in_at) for pid, a in accounts.items() if a is not None and a.last_sign_in_at}
    admins = [p for p in active if p.is_company_admin]
    on = lambda people: sum(1 for p in people if accounts.get(p.id) is not None and sign_in.two_step_on(accounts[p.id]))  # noqa: E731
    emails = [p.email.lower() for p in everyone]
    account_ids = [a.id for a in accounts.values() if a is not None]
    window = now - timedelta(minutes=settings.login_lockout_minutes)
    locked = db.execute(select(SignInFailure.email).where(SignInFailure.email.in_(emails), SignInFailure.at > window)
                        .group_by(SignInFailure.email).having(func.count() >= settings.login_attempts)).all() if emails else []
    failed = db.scalar(select(func.count()).select_from(AuditEntry).where(AuditEntry.action == "identity.sign_in_failed", AuditEntry.target.in_(emails),
                                                                         AuditEntry.created_at > now - timedelta(days=7))) if emails else 0
    invites = db.scalar(select(func.count()).select_from(SignInLink).where(SignInLink.account_id.in_(account_ids), SignInLink.kind == "invite",
                                                                          SignInLink.used_at.is_(None), SignInLink.expires_at > now)) if account_ids else 0
    apps = []
    for a in modules_of(db, me.company_id):
        given = db.scalar(select(func.count()).select_from(IdentityApp).join(Identity, Identity.id == IdentityApp.identity_id)
                          .where(IdentityApp.application_id == a.id, Identity.company_id == me.company_id, Identity.status == "active",
                                 Identity.deleted_at.is_(None), Identity.via_operator.is_(False), Identity.is_company_admin.is_(False))) or 0
        apps.append({"key": a.key, "name": a.name, "people": given + len(admins)})
    holders: dict[str, int] = {}
    for p in active:
        if p.access_role_id:
            holders[p.access_role_id] = holders.get(p.access_role_id, 0) + 1
    roles = [{"id": r.id, "name": r.name, "people": holders.get(r.id, 0)}
             for r in db.scalars(select(AccessRole).where(AccessRole.company_id == me.company_id).order_by(AccessRole.is_admin.desc(), func.lower(AccessRole.name)))]
    recent = db.scalars(select(AuditEntry).where(AuditEntry.company_id == me.company_id, AuditEntry.category == "security")
                        .order_by(AuditEntry.created_at.desc()).limit(8)).all()
    return {
        "people": {
            "active": len(active),
            "off": sum(1 for p in everyone if p.status != "active" and p.deleted_at is None),
            "inBin": sum(1 for p in everyone if p.deleted_at is not None),
            "administrators": len(admins),
            "noRole": sum(1 for p in active if not p.access_role_id and not p.is_company_admin),
            "noApps": sum(1 for p in active if p.id not in granted and not p.is_company_admin),
        },
        "signIns": {
            "today": sum(1 for t in seen.values() if t >= midnight),
            "week": sum(1 for t in seen.values() if t >= now - timedelta(days=7)),
            "month": sum(1 for t in seen.values() if t >= now - timedelta(days=30)),
            "never": sum(1 for p in active if p.id not in seen),
            "invitesPending": invites or 0,
            "passwordsToChange": sum(1 for a in accounts.values() if a is not None and a.must_change_password),
        },
        "security": {
            "twoStepAdministrators": {"on": on(admins), "of": len(admins)},
            "twoStepEveryone": {"on": on(active), "of": len(active)},
            "required": settings.two_step_required,
            "failedThisWeek": failed or 0,
            "lockedNow": len(locked),
            "offDomain": sum(1 for p in active if email_rules.off_domain(db, p)),
        },
        "apps": apps,
        "roles": roles,
        "recent": [entry_out(e) for e in recent],
    }
