"""Access in one place: a company's roles for every module, kept here.

Decided 2026-10-23 (benchmarks/decisions.md, step R1). Each person has one role
at their company; a role holds any module's permissions, with a scope per
module where the module has scopes (the CRM: own, team, managed, all). Each
module's API still declares its permissions in code and enforces every
request; what changes is where roles are made and given:

- catalog(app): what a module's API declares (GET <api>/platform/catalog),
  kept for five minutes, so the roles screen offers exactly that.
- spec(db, role, app): the role as one module keeps it.
- push(...): sends each application the company has its roles and who holds
  them, signed with the platform's key (kind "roles"), to the API address
  registered for it: POST <api>/platform/roles. The application keeps them in
  its own role tables, so it enforces them as it always has. Sent in the
  background on every change; an application out of reach catches up when the
  next change is sent, and each person's sign-in pass carries their role too
  (app/passes.py), so nobody waits on it.
- import_roles(...): the first time, the roles each application has today,
  matched by name across applications, and each person's role, matched by
  their email; someone with different roles in different applications is left
  for the administrator to choose (until then each application goes by the
  role on their grant, as before).
"""

import logging
import secrets
import threading
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AccessRole, AccessRolePermission, AccessRoleScope, Application, Company, CompanyApp, Identity, IdentityApp

log = logging.getLogger(__name__)

ADMINISTRATOR = "Administrator"  # every module's system role: everything
KEEP = 300  # seconds a module's catalog is kept
MISSING = 60  # seconds before asking again a module that didn't answer
PUSH_LIFETIME = 600  # seconds a roles note may be taken
ASK_LIFETIME = 120

_catalogs: dict[str, tuple[dict | None, float]] = {}  # by API address: (what it answered, when)


def forget() -> None:
    """Asks every module again next time (tests)."""
    _catalogs.clear()


def catalog(app: Application) -> dict | None:
    """What the module declares: {"areas": [{key, name, group, actions: [{key, label, permission}]}],
    "scopes": [{key, label}]}; None when it has no API here or doesn't answer."""
    if not app.api_url:
        return None
    url = app.api_url.rstrip("/")
    known = _catalogs.get(url)
    if known and time.monotonic() - known[1] < (KEEP if known[0] else MISSING):
        return known[0]
    try:
        r = httpx.get(f"{url}/platform/catalog", timeout=3)
        found = r.json() if r.status_code == 200 else None
        if not isinstance(found, dict) or not isinstance(found.get("areas"), list):
            found = None
    except (httpx.HTTPError, ValueError):
        found = None
    if found is None and known and known[0]:
        found = known[0]  # out of reach for now: what it said last stands
    _catalogs[url] = (found, time.monotonic())
    return found


def permissions_in(found: dict) -> set[str]:
    return {a["permission"] for area in found.get("areas", []) for a in area.get("actions", [])}


def scopes_in(found: dict) -> list[str]:
    return [s["key"] for s in found.get("scopes") or []]


def modules_of(db: Session, company_id: str) -> list[Application]:
    """The company's applications that keep roles (every one but the platform itself), in their order."""
    return list(db.scalars(
        select(Application)
        .join(CompanyApp, (CompanyApp.application_id == Application.id) & (CompanyApp.company_id == company_id))
        .where(Application.is_active, Application.key != "platform")
        .order_by(Application.sort_order, Application.name)
    ))


def grants_of(db: Session, role: AccessRole) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for app_key, permission in db.execute(
        select(AccessRolePermission.app_key, AccessRolePermission.permission).where(AccessRolePermission.role_id == role.id).order_by(AccessRolePermission.permission)
    ):
        out.setdefault(app_key, []).append(permission)
    return out


def scopes_of(db: Session, role: AccessRole) -> dict[str, str]:
    return dict(db.execute(select(AccessRoleScope.app_key, AccessRoleScope.scope).where(AccessRoleScope.role_id == role.id)).all())


def set_module(db: Session, role: AccessRole, app_key: str, permissions: list[str], scope: str | None) -> None:
    """What the role holds in one module, in place of what it held."""
    db.execute(delete(AccessRolePermission).where(AccessRolePermission.role_id == role.id, AccessRolePermission.app_key == app_key))
    db.execute(delete(AccessRoleScope).where(AccessRoleScope.role_id == role.id, AccessRoleScope.app_key == app_key))
    for p in sorted(set(permissions)):
        db.add(AccessRolePermission(role_id=role.id, app_key=app_key, permission=p))
    if scope:
        db.add(AccessRoleScope(role_id=role.id, app_key=app_key, scope=scope))


def spec(db: Session, role: AccessRole, app_key: str) -> dict:
    """The role as one module keeps it."""
    perms = sorted(db.scalars(select(AccessRolePermission.permission).where(AccessRolePermission.role_id == role.id, AccessRolePermission.app_key == app_key)))
    scope = db.scalar(select(AccessRoleScope.scope).where(AccessRoleScope.role_id == role.id, AccessRoleScope.app_key == app_key))
    return {"name": role.name, "description": role.description, "scope": scope, "permissions": perms, "admin": role.is_admin}


def role_for_pass(db: Session, person: Identity, app: Application) -> dict | None:
    """Their one role, as this application keeps it, for their sign-in pass; None without one."""
    if not person.access_role_id:
        return None
    role = db.get(AccessRole, person.access_role_id)
    return spec(db, role, app.key) if role else None


# ---- Telling the modules -------------------------------------------------------------------


def roles_note(db: Session, settings: Settings, company: Company, app: Application) -> str:
    """Signed: every role of the company as this module keeps it, and who holds which."""
    from app.passes import ISSUER, sign

    roles = db.scalars(select(AccessRole).where(AccessRole.company_id == company.id).order_by(AccessRole.name)).all()
    by_id = {r.id: r for r in roles}
    # Everyone who may open this module: their role (when they have one here) and, since R2, whether
    # they're switched on, so switching someone off on the Platform switches them off in the module.
    people = db.execute(
        select(Identity.email, Identity.access_role_id, Identity.status)
        .join(IdentityApp, (IdentityApp.identity_id == Identity.id) & (IdentityApp.application_id == app.id))
        .where(Identity.company_id == company.id)
        .order_by(Identity.email)
    ).all()
    now = int(time.time())
    return sign(settings, {
        "iss": ISSUER,
        "aud": app.key,
        "kind": "roles",
        "company": company.id,
        "slug": company.slug,
        "roles": [spec(db, r, app.key) for r in roles],
        "people": [
            {"email": e.lower(), "role": by_id[rid].name if rid in by_id else None, "admin": bool(rid in by_id and by_id[rid].is_admin), "active": st == "active"}
            for e, rid, st in people
        ],
        "iat": now,
        "exp": now + PUSH_LIFETIME,
        "jti": secrets.token_urlsafe(12),
    })


def _send(sessions, settings: Settings, company_id: str) -> None:
    with sessions() as db:
        company = db.get(Company, company_id)
        if company is None:
            return
        for app in modules_of(db, company_id):
            if not app.api_url:
                continue
            url = app.api_url.rstrip("/") + "/platform/roles"
            try:
                r = httpx.post(url, json={"pass": roles_note(db, settings, company, app)}, timeout=10)
                answer = "taken" if r.status_code == 204 else f"answered {r.status_code}"
            except httpx.HTTPError as e:
                answer = f"out of reach ({e.__class__.__name__})"
            if answer != "taken":
                log.warning("Roles push: %s for %r: %s.", app.key, company.slug, answer)


def push(sessions, settings: Settings, company_id: str) -> None:
    """Sends every module the company has its roles, in the background."""

    def run() -> None:
        try:
            _send(sessions, settings, company_id)
        except Exception:  # noqa: BLE001 (each sign-in carries the person's role too)
            log.exception("Roles push: couldn't tell the applications about %s.", company_id)

    threading.Thread(target=run, name="roles-push", daemon=True).start()


# ---- The first time: the roles each module has today -----------------------------------------


def read_roles(settings: Settings, app: Application, slug: str) -> list[dict] | None:
    """The roles a module has today for this company: [{name, description, scope, permissions, isSystem}]."""
    from app.passes import ISSUER, sign

    if not app.api_url:
        return None
    now = int(time.time())
    ask = sign(settings, {"iss": ISSUER, "aud": app.key, "kind": "roles-ask", "slug": slug, "iat": now, "exp": now + ASK_LIFETIME, "jti": secrets.token_urlsafe(12)})
    try:
        r = httpx.post(app.api_url.rstrip("/") + "/platform/roles/export", json={"pass": ask}, timeout=10)
        found = r.json().get("roles") if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError, AttributeError):
        found = None
    return found if isinstance(found, list) else None


def legacy_role(grant: IdentityApp) -> str | None:
    """The role an application gives someone today, from their grant."""
    return ADMINISTRATOR if grant.is_app_admin else (grant.role or None)


def legacy_roles(db: Session, person: Identity, apps: list[Application]) -> dict[str, str]:
    """By application key: the role each of these applications gives them today."""
    by_id = {a.id: a for a in apps}
    out = {}
    for grant in db.scalars(select(IdentityApp).where(IdentityApp.identity_id == person.id, IdentityApp.application_id.in_(by_id))):
        name = legacy_role(grant)
        if name:
            out[by_id[grant.application_id].key] = name
    return out


def import_roles(db: Session, settings: Settings, company: Company, actor: str) -> dict:
    """Brings in the roles each module has today and gives each person theirs (see the top)."""
    apps = modules_of(db, company.id)
    roles: dict[str, AccessRole] = {r.name.lower(): r for r in db.scalars(select(AccessRole).where(AccessRole.company_id == company.id))}
    read, unreachable, made = [], [], 0
    for app in apps:
        found = read_roles(settings, app, company.slug)
        if found is None:
            unreachable.append(app.name)
            continue
        read.append(app)
        for r in found:
            name = str(r.get("name") or "").strip()[:80]
            if not name:
                continue
            admin = bool(r.get("isSystem")) or name.lower() == ADMINISTRATOR.lower()
            role = roles.get(name.lower())
            if role is None:
                role = AccessRole(company_id=company.id, name=ADMINISTRATOR if admin else name, description=r.get("description"), is_admin=admin)
                db.add(role)
                db.flush()
                roles[name.lower()] = role
                made += 1
            if not role.is_admin:
                set_module(db, role, app.key, [p for p in r.get("permissions") or [] if isinstance(p, str)], r.get("scope"))
            role.updated_at = datetime.now(UTC)
    assigned, conflicts = 0, []
    for person in db.scalars(select(Identity).where(Identity.company_id == company.id, Identity.access_role_id.is_(None)).order_by(Identity.full_name)):
        given = legacy_roles(db, person, read)
        names = {n.lower() for n in given.values()}
        if len(names) == 1 and next(iter(names)) in roles:
            person.access_role_id = roles[next(iter(names))].id
            assigned += 1
        elif given:
            conflicts.append(person.email)
    from app.audit import audit

    audit(db, actor, "access.roles_imported", target=company.name, target_type="company", target_id=company.id, company_id=company.id,
          fields=[a.key for a in read])
    db.commit()
    return {"rolesMade": made, "peopleGiven": assigned, "toChoose": len(conflicts), "unreachable": unreachable}
