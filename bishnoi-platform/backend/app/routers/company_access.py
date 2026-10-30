"""Access for a company's own administrators, signed in with their Bishnoi One
account: the one place their company's roles are made and people given them,
for every module (decided 2026-10-23; app/access_roles.py says how the
modules are told). The one app's /platform/access screens use these.

- GET    /identity/access: the modules (what each declares), roles, people, and
  who is still to be given a role.
- POST   /identity/access/roles, PATCH and DELETE /identity/access/roles/{id}.
- PUT    /identity/access/people/{id}/role: their one role.
- PUT / DELETE /identity/access/people/{id}/apps/{key}: the modules they may open.
- POST   /identity/access/import: the roles each module has today, once.

Only a company administrator (Identity.is_company_admin) may; every change is
in the audit log (names of what changed, never values) and sent to the modules.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import abilities as ab
from app import access_roles
from app.access_roles import ADMINISTRATOR
from app.api import Api, changed, check_email, conflict, field_error, not_found
from app.audit import audit
from app import passwords
from app.deps import DB, SettingsDep
from app.models import AccessRole, Application, Company, CompanyApp, Identity, IdentityApp, IdentitySession
from app import email_rules, sign_in
from app.accounts import account_of, memberships, runs_company
from app.routers.identity import Signed

router = APIRouter(prefix="/identity/access", tags=["company access"])


def company_admin(signed: Signed, db: DB, settings: SettingsDep) -> Identity:
    _, person = signed
    if not runs_company(db, person):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only your company's administrators manage access.")
    # Administrators change nothing until their own sign-in has two steps, where that's required (2026-10-30).
    if sign_in.needs_two_step(settings, account_of(db, person), True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Set up two-step sign-in first: Your profile, Two-step sign-in. Administrators need it.")
    return person


Admin = Annotated[Identity, Depends(company_admin)]


def told(request: Request, settings, company_id: str) -> None:
    access_roles.push(request.app.state.sessions, settings, company_id)


# ---- What the screens read ------------------------------------------------------------------


def module_out(app: Application) -> dict:
    found = access_roles.catalog(app)
    return {
        "key": app.key,
        "name": app.name,
        "reachable": found is not None,
        "areas": found.get("areas", []) if found else [],
        "scopes": found.get("scopes") or [] if found else [],
    }


def role_out(db: Session, role: AccessRole, holders: int = 0) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "isAdmin": role.is_admin,
        "permissions": access_roles.grants_of(db, role),
        "scopes": access_roles.scopes_of(db, role),
        "people": holders,
        # Step 6: its abilities (with limits) and the job role it was copied from.
        "abilities": access_roles.abilities_of(db, role),
        "jobRole": role.job_role,
    }


def holders_of(db: Session, company_id: str) -> dict[str, int]:
    return dict(db.execute(
        select(Identity.access_role_id, func.count()).where(Identity.company_id == company_id, Identity.access_role_id.is_not(None)).group_by(Identity.access_role_id)
    ).all())


@router.get("")
def overview(db: DB, me: Admin) -> dict:
    apps = access_roles.modules_of(db, me.company_id)
    by_id = {a.id: a for a in apps}
    holders = holders_of(db, me.company_id)
    roles = db.scalars(select(AccessRole).where(AccessRole.company_id == me.company_id).order_by(AccessRole.is_admin.desc(), func.lower(AccessRole.name))).all()
    people, to_choose = [], []
    for p in db.scalars(select(Identity).where(Identity.company_id == me.company_id, Identity.via_operator.is_(False), Identity.deleted_at.is_(None))
                        .order_by(func.lower(Identity.full_name))):
        grants = db.scalars(select(IdentityApp).where(IdentityApp.identity_id == p.id)).all()
        given = [{"key": by_id[g.application_id].key, "role": access_roles.legacy_role(g)} for g in grants if g.application_id in by_id]
        people.append({
            "id": p.id,
            "fullName": p.full_name,
            "email": p.email,
            "title": p.title,
            "status": p.status,
            "isCompanyAdmin": p.is_company_admin,
            "roleId": p.access_role_id,
            "apps": given,
            "appDetails": p.app_details or {},
        })
        if p.access_role_id is None and any(g["role"] for g in given):
            to_choose.append(p.id)
    company = db.get(Company, me.company_id)
    return {
        "company": {"id": company.id, "name": company.name},
        "modules": [module_out(a) for a in apps],
        "roles": [role_out(db, r, holders.get(r.id, 0)) for r in roles],
        "people": people,
        # Without a role here yet, with one in an application: each still goes by that one until given one here.
        "toChoose": to_choose,
        "meId": me.id,
        "inBin": db.scalar(select(func.count()).select_from(Identity).where(Identity.company_id == me.company_id, Identity.deleted_at.is_not(None),
                                                                             Identity.via_operator.is_(False))) or 0,
    }


# ---- Roles ----------------------------------------------------------------------------------


class RoleIn(Api):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    is_admin: bool = False
    # By module key: its permissions ("customers.edit"), and its scope where it has scopes.
    permissions: dict[str, list[str]] = Field(default_factory=dict)
    scopes: dict[str, str] = Field(default_factory=dict)


class RolePatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    is_admin: bool | None = None
    permissions: dict[str, list[str]] | None = None
    scopes: dict[str, str] | None = None


def name_taken(db: Session, company_id: str, name: str, but: str | None = None) -> bool:
    q = select(AccessRole.id).where(AccessRole.company_id == company_id, func.lower(AccessRole.name) == name.lower())
    if but:
        q = q.where(AccessRole.id != but)
    return db.scalar(q) is not None


def check_modules(db: Session, company_id: str, permissions: dict[str, list[str]], scopes: dict[str, str]) -> dict[str, tuple[list[str], str | None]]:
    """Each module named: its permissions and scope, checked against what it declares."""
    apps = {a.key: a for a in access_roles.modules_of(db, company_id)}
    out = {}
    for key in set(permissions) | set(scopes):
        app = apps.get(key)
        if app is None:
            raise field_error("permissions", f"Your company doesn't have {key}.")
        found = access_roles.catalog(app)
        if found is None:
            raise field_error("permissions", f"{app.name} can't be reached right now, so its permissions can't be changed. Try again in a moment.")
        unknown = sorted(set(permissions.get(key, [])) - access_roles.permissions_in(found))
        if unknown:
            raise field_error("permissions", f"{app.name} has no permission {', '.join(unknown)}.")
        offered = access_roles.scopes_in(found)
        scope = scopes.get(key) or None
        if scope and scope not in offered:
            raise field_error("scopes", f"{app.name} has no scope {scope}.")
        if offered and not scope:
            scope = offered[0]  # the narrowest: their own records
        out[key] = (permissions.get(key, []), scope)
    return out


def check_name(name: str, is_admin: bool) -> None:
    if name.strip().lower() == ADMINISTRATOR.lower() and not is_admin:
        raise field_error("name", "Administrator is the role with everything. Name this one something else.")


def get_role(db: Session, me: Identity, role_id: str) -> AccessRole:
    role = db.get(AccessRole, role_id)
    if role is None or role.company_id != me.company_id:
        raise not_found("role")
    return role


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(body: RoleIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    check_name(body.name, body.is_admin)
    if name_taken(db, me.company_id, body.name):
        raise field_error("name", "There's already a role with that name.")
    modules = {} if body.is_admin else check_modules(db, me.company_id, body.permissions, body.scopes)
    role = AccessRole(company_id=me.company_id, name=body.name, description=body.description, is_admin=body.is_admin)
    db.add(role)
    db.flush()
    for key, (perms, scope) in modules.items():
        access_roles.set_module(db, role, key, perms, scope)
    audit(db, me.email, "access.role_created", target=role.name, target_type="access_role", target_id=role.id, company_id=me.company_id)
    db.commit()
    told(request, settings, me.company_id)
    return role_out(db, role)


@router.patch("/roles/{role_id}")
def update_role(role_id: str, body: RolePatch, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    role = get_role(db, me, role_id)
    wanted = changed(body)
    is_admin = wanted["is_admin"] if wanted.get("is_admin") is not None else role.is_admin
    name = wanted.get("name") or role.name
    check_name(name, is_admin)
    if "name" in wanted and wanted["name"] is None:
        raise field_error("name", "Give the role a name.")
    if wanted.get("name") and name_taken(db, me.company_id, wanted["name"], but=role.id):
        raise field_error("name", "There's already a role with that name.")
    if role.is_admin and not is_admin and holders_of(db, me.company_id).get(role.id) and not other_admins(db, me.company_id, but_role=role.id):
        raise conflict("Someone must always have everything, or nobody could fix a mistake in access. Give another role everything first.")
    fields = []
    for key in ("name", "description", "is_admin"):
        if key in wanted and (wanted[key] is not None or key == "description") and getattr(role, key) != wanted[key]:
            setattr(role, key, wanted[key])
            fields.append(key)
    if not role.is_admin and (body.permissions is not None or body.scopes is not None):
        modules = check_modules(db, me.company_id, body.permissions or {}, body.scopes or {})
        keep = access_roles.grants_of(db, role), access_roles.scopes_of(db, role)
        for key, (perms, scope) in modules.items():
            if body.permissions is None:
                perms = keep[0].get(key, [])
            if body.scopes is None or key not in (body.scopes or {}):
                scope = keep[1].get(key, scope)
            access_roles.set_module(db, role, key, perms, scope)
        db.flush()
        if (access_roles.grants_of(db, role), access_roles.scopes_of(db, role)) != keep:
            fields.append("permissions")
    if fields:
        from datetime import UTC, datetime

        role.updated_at = datetime.now(UTC)
        audit(db, me.email, "access.role_updated", target=role.name, target_type="access_role", target_id=role.id, company_id=me.company_id, fields=fields)
        db.commit()
        told(request, settings, me.company_id)
    return role_out(db, role, holders_of(db, me.company_id).get(role.id, 0))


# ---- Abilities and job roles (feature plan step 6): in plain words, defined by Bishnoi One ----------


@router.get("/abilities")
def abilities(_: Admin) -> dict:
    """What a role can hold, as abilities in business words, and the ready-made job roles to copy."""
    return {
        "groups": [{"name": g, "abilities": [{"key": a.key, "label": a.label, "limit": a.limit, "apps": sorted(a.grants)} for a in ab.ABILITIES if a.group == g]}
                   for g in ab.GROUPS],
        "jobRoles": [{"key": j.key, "name": j.name, "sees": j.sees, "abilities": list(j.abilities), "scopes": j.scopes, "limits": j.limits, "admin": j.admin}
                     for j in ab.JOB_ROLES],
    }


class FromJobIn(Api):
    job_role: str = Field(max_length=40)
    name: str | None = Field(None, min_length=1, max_length=80)


@router.post("/roles/from-job", status_code=status.HTTP_201_CREATED)
def role_from_job(body: FromJobIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    """A copy of one of Bishnoi One's job roles, for the company to adjust (decision 23)."""
    job = ab.JOB.get(body.job_role)
    if job is None:
        raise field_error("job_role", "There's no such job role.")
    name = (body.name or job.name).strip()
    check_name(name, job.admin)
    if name_taken(db, me.company_id, name):
        raise field_error("name", "There's already a role with that name. Give the copy another name.")
    role = AccessRole(company_id=me.company_id, name=name, description=f"Who sees: {job.sees.lower()}.", is_admin=job.admin, job_role=job.key)
    db.add(role)
    db.flush()
    if not job.admin:
        access_roles.set_abilities(db, role, [{"key": k, "limit": job.limits.get(k)} for k in job.abilities], job.scopes)
    audit(db, me.email, "access.role_created", target=role.name, target_type="access_role", target_id=role.id, company_id=me.company_id, fields=["from a job role"])
    db.commit()
    told(request, settings, me.company_id)
    return role_out(db, role)


class AbilityIn(Api):
    key: str = Field(max_length=60)
    limit: int | None = Field(None, ge=0, le=10**12)


class AbilitiesIn(Api):
    abilities: list[AbilityIn] = Field(max_length=100)
    # By module: whose records the role reaches there (its scopes), when changing them too.
    scopes: dict[str, str] = Field(default_factory=dict)


@router.put("/roles/{role_id}/abilities")
def set_role_abilities(role_id: str, body: AbilitiesIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    """The role's abilities, switched on or off in plain words (decision 22); its permissions follow."""
    role = get_role(db, me, role_id)
    if role.is_admin:
        raise conflict("This role has everything; there's nothing to switch.")
    unknown = sorted({a.key for a in body.abilities} - set(ab.ABILITY))
    if unknown:
        raise field_error("abilities", f"There's no ability {', '.join(unknown)}.")
    apps = {a.key: a for a in access_roles.modules_of(db, me.company_id)}
    for key, scope in body.scopes.items():
        found = access_roles.catalog(apps[key]) if key in apps else None
        if key not in apps or (found is not None and scope not in access_roles.scopes_in(found)):
            raise field_error("scopes", f"{key} has no scope {scope}.")
    before = (access_roles.abilities_of(db, role), access_roles.scopes_of(db, role))
    access_roles.set_abilities(db, role, [a.model_dump() for a in body.abilities], body.scopes)
    db.flush()
    if (access_roles.abilities_of(db, role), access_roles.scopes_of(db, role)) != before:
        from datetime import UTC, datetime

        role.updated_at = datetime.now(UTC)
        audit(db, me.email, "access.role_updated", target=role.name, target_type="access_role", target_id=role.id, company_id=me.company_id, fields=["abilities"])
        db.commit()
        told(request, settings, me.company_id)
    return role_out(db, role, holders_of(db, me.company_id).get(role.id, 0))


def other_admins(db: Session, company_id: str, but_role: str) -> int:
    """People holding a role with everything, other than this role."""
    return db.scalar(
        select(func.count()).select_from(Identity).join(AccessRole, AccessRole.id == Identity.access_role_id)
        .where(Identity.company_id == company_id, AccessRole.is_admin, AccessRole.id != but_role, Identity.status == "active")
    ) or 0


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: str, request: Request, db: DB, me: Admin, settings: SettingsDep) -> Response:
    role = get_role(db, me, role_id)
    holders = holders_of(db, me.company_id).get(role.id, 0)
    if holders:
        raise conflict(f"{holders} {'person has' if holders == 1 else 'people have'} this role. Give them another one first.")
    audit(db, me.email, "access.role_deleted", target=role.name, target_type="access_role", target_id=role.id, company_id=me.company_id)
    db.delete(role)
    db.commit()
    told(request, settings, me.company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- People ---------------------------------------------------------------------------------


class PersonRoleIn(Api):
    role_id: str | None = None


def get_person(db: Session, me: Identity, person_id: str) -> Identity:
    p = db.get(Identity, person_id)
    # An operator's let-in membership isn't one of the company's people (2026-10-28).
    if p is None or p.company_id != me.company_id or p.via_operator:
        raise not_found("person")
    return p


@router.put("/people/{person_id}/role")
def set_role(person_id: str, body: PersonRoleIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    p = get_person(db, me, person_id)
    role = get_role(db, me, body.role_id) if body.role_id else None
    was = db.get(AccessRole, p.access_role_id) if p.access_role_id else None
    if was and was.is_admin and not (role and role.is_admin) and not other_admins_people(db, me.company_id, but=p.id):
        raise conflict("Someone must always have everything, or nobody could fix a mistake in access. Give it to someone else first.")
    if p.access_role_id != (role.id if role else None):
        p.access_role_id = role.id if role else None
        audit(db, me.email, "access.role_given", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id, fields=["role"])
        db.commit()
        told(request, settings, me.company_id)
    return {"id": p.id, "roleId": p.access_role_id}


# ---- People: the company's own administrators add and keep them (R2, decided 2026-10-26) --------
# One list of people for every module: added here once, with the modules they may open and
# their role; switched off here, they're off everywhere. Each module keeps only what is its own
# about a person (an e-signature, a licence number, an employee ID).


class PersonIn(Api):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254)
    title: str | None = Field(None, max_length=120)
    role_id: str | None = None
    apps: list[str] = []

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return check_email(value)


# What each app keeps of its own about a person, edited here (2026-10-30): the app, then its fields.
APP_DETAILS = {"crm": {"employeeId": str}, "pharmacy": {"licenseNo": str}, "finance": {"calendarOn": bool}}


def clean_details(given: dict | None, before: dict | None) -> dict:
    out = {k: dict(v) for k, v in (before or {}).items()}
    for app, fields in (given or {}).items():
        allowed = APP_DETAILS.get(app)
        if allowed is None or not isinstance(fields, dict):
            raise field_error("appDetails", f"Nothing of {app}'s is kept here.")
        for name, value in fields.items():
            kind = allowed.get(name)
            if kind is None:
                raise field_error("appDetails", f"{app} keeps no {name}.")
            if value in (None, ""):
                out.setdefault(app, {}).pop(name, None)
            elif kind is bool:
                out.setdefault(app, {})[name] = bool(value)
            else:
                text = str(value).strip()
                if len(text) > 40:
                    raise field_error("appDetails", "Use at most 40 characters.")
                out.setdefault(app, {})[name] = text
    return {k: v for k, v in out.items() if v}


class PersonPatch(Api):
    full_name: str | None = Field(None, min_length=2, max_length=120)
    title: str | None = Field(None, max_length=120)
    app_details: dict[str, dict] | None = None
    # Their sign-in email, at the company's domain (app/email_rules.py, decided 2026-10-29).
    email: str | None = Field(None, max_length=254)
    status: Literal["active", "suspended"] | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value) if value else None


class PasswordIn(Api):
    password: str | None = Field(None, max_length=200)


def person_out(p: Identity) -> dict:
    return {"id": p.id, "fullName": p.full_name, "email": p.email, "title": p.title, "status": p.status, "isCompanyAdmin": p.is_company_admin, "roleId": p.access_role_id,
            "appDetails": p.app_details or {}}


@router.post("/people", status_code=status.HTTP_201_CREATED)
def add_person(body: PersonIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    """Someone new at the company: their account, their role and the modules they may open, in one go."""
    same = db.scalar(select(Identity).where(Identity.company_id == me.company_id, func.lower(Identity.email) == body.email.lower()))
    if same is not None:
        raise field_error("email", "That person is in the recycle bin: restore them instead." if same.deleted_at else "Somebody here already has that email.")
    email_rules.check_company_email(db.get(Company, me.company_id), body.email)
    email_rules.check_available(db, body.email, me.company_id)
    role = get_role(db, me, body.role_id) if body.role_id else None
    apps = [company_module(db, me, key) for key in dict.fromkeys(body.apps)]
    p = Identity(company_id=me.company_id, full_name=body.full_name.strip(), email=body.email, title=(body.title or "").strip() or None, access_role_id=role.id if role else None)
    # Already at another company: the same person, with the password they have.
    elsewhere = db.scalar(select(Identity).where(func.lower(Identity.email) == body.email.lower(), Identity.password_hash.is_not(None)))
    if elsewhere is not None:
        p.password_hash, p.password_changed_at = elsewhere.password_hash, elsewhere.password_changed_at
    db.add(p)
    db.flush()
    for app in apps:
        db.add(IdentityApp(identity_id=p.id, application_id=app.id, granted_by=me.email))
    audit(db, me.email, "access.person_added", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    told(request, settings, me.company_id)
    return {"person": person_out(p), "hasPassword": p.password_hash is not None}


@router.patch("/people/{person_id}")
def change_person(person_id: str, body: PersonPatch, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    """Their name or title, or switching them off (and on again): off, they can't sign in to any module."""
    p = get_person(db, me, person_id)
    if p.deleted_at is not None:
        raise conflict(f"{p.full_name} is in the recycle bin. Restore them first.")
    fields = {k: v for k, v in changed(body).items() if v is not None and k != "app_details" and getattr(p, k) != v}
    if body.app_details is not None:
        details = clean_details(body.app_details, p.app_details)
        if details != (p.app_details or {}):
            p.app_details = details or None
            fields["app_details"] = details
    if "email" in fields:
        new = fields.pop("email")
        change_email(db, me, p, new)
        audit(db, me.email, "access.email_changed", category="security", target=new, target_type="identity", target_id=p.id, company_id=me.company_id, fields=["email"])
        if not fields:
            db.commit()
            told(request, settings, me.company_id)
            return {"person": person_out(p)}
    if fields.get("status") == "suspended":
        if p.id == me.id:
            raise conflict("You can't switch yourself off. Ask another administrator.")
        role = db.get(AccessRole, p.access_role_id) if p.access_role_id else None
        if role and role.is_admin and not other_admins_people(db, me.company_id, but=p.id):
            raise conflict("Someone must always have everything, or nobody could fix a mistake in access. Give it to someone else first.")
        if p.is_company_admin and not db.scalar(
                select(func.count()).select_from(Identity).where(Identity.company_id == me.company_id, Identity.is_company_admin, Identity.id != p.id,
                                                                 Identity.status == "active", Identity.via_operator.is_(False))):
            raise conflict(f"{p.full_name} is the company's only administrator. Make someone else one first (Company profile).")
    for name, value in fields.items():
        if name == "app_details":
            continue
        setattr(p, name, value.strip() if isinstance(value, str) and name != "status" else value)
    if fields:
        action = {"suspended": "access.person_suspended", "active": "access.person_reactivated"}.get(fields.get("status"), "access.person_changed")
        audit(db, me.email, action, target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id, fields=sorted(fields))
        db.commit()
        told(request, settings, me.company_id)
    return {"person": person_out(p)}


def change_email(db: Session, me: Identity, p: Identity, new: str) -> None:
    """A person's sign-in email, changed by their company's administrator: at the company's domain, and
    nobody else's anywhere. Their account keeps its password and history; they sign in with the new one."""
    if db.scalar(select(Identity).where(Identity.company_id == me.company_id, func.lower(Identity.email) == new, Identity.id != p.id)):
        raise field_error("email", "Somebody here already has that email.")
    email_rules.check_company_email(db.get(Company, me.company_id), new)
    account = account_of(db, p)
    email_rules.check_available(db, new, me.company_id, but_account=account.id if account else None)
    if account is not None and (account.is_operator or any(
            m.company_id != me.company_id and not m.via_operator and m.status == "active" for m in memberships(db, account))):
        raise conflict(f"{p.email} is also used outside {db.get(Company, me.company_id).name}. Ask Bishnoi One's operators to separate it first.")
    email_rules.change_email(db, p, new)


@router.post("/people/{person_id}/password")
def set_person_password(person_id: str, body: PasswordIn, db: DB, me: Admin) -> dict:
    """A first (or replacement) password for their Bishnoi One account; made up when none is typed,
    and shown once. Their other sign-ins end; they change it themselves afterwards."""
    from datetime import UTC, datetime
    import secrets

    from app.security import check_password_rules, hash_password

    p = get_person(db, me, person_id)
    made = body.password is None
    password = body.password or secrets.token_urlsafe(9)
    problem = check_password_rules(password)
    if problem:
        raise field_error("password", problem)
    hashed, now = hash_password(password), datetime.now(UTC)
    # One password at every company of theirs, and in the Admin Console (app/passwords.py).
    passwords.set_for(db, p.email, hashed, now)
    # Handed over: they choose their own at the first sign-in (2026-10-30).
    account = account_of(db, p)
    if account is not None and p.id != me.id:
        account.must_change_password = True
    audit(db, me.email, "access.password_set", category="security", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    return {"password": password if made else None}


def other_admins_people(db: Session, company_id: str, but: str) -> int:
    return db.scalar(
        select(func.count()).select_from(Identity).join(AccessRole, AccessRole.id == Identity.access_role_id)
        .where(Identity.company_id == company_id, AccessRole.is_admin, Identity.id != but, Identity.status == "active")
    ) or 0


def company_module(db: Session, me: Identity, key: str) -> Application:
    app = db.scalar(
        select(Application).join(CompanyApp, (CompanyApp.application_id == Application.id) & (CompanyApp.company_id == me.company_id))
        .where(Application.key == key, Application.is_active)
    )
    if app is None:
        raise not_found("module")
    return app


@router.put("/people/{person_id}/apps/{key}")
def give_module(person_id: str, key: str, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    p = get_person(db, me, person_id)
    app = company_module(db, me, key)
    if db.get(IdentityApp, (p.id, app.id)) is None:
        db.add(IdentityApp(identity_id=p.id, application_id=app.id, granted_by=me.email))
        audit(db, me.email, "access.granted", target=f"{p.email} · {app.name}", target_type="identity", target_id=p.id, company_id=me.company_id, application_id=app.id)
        db.commit()
        told(request, settings, me.company_id)
    return {"id": p.id, "app": app.key}


@router.delete("/people/{person_id}/apps/{key}", status_code=status.HTTP_204_NO_CONTENT)
def take_module(person_id: str, key: str, db: DB, me: Admin) -> Response:
    p = get_person(db, me, person_id)
    app = company_module(db, me, key)
    g = db.get(IdentityApp, (p.id, app.id))
    if g is not None:
        audit(db, me.email, "access.withdrawn", target=f"{p.email} · {app.name}", target_type="identity", target_id=p.id, company_id=me.company_id, application_id=app.id)
        db.delete(g)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/import")
def import_roles(request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    company = db.get(Company, me.company_id)
    report = access_roles.import_roles(db, settings, company, me.email)
    told(request, settings, me.company_id)
    return report


# ---- The recycle bin (2026-10-30) ---------------------------------------------------------------
# Deleting a person puts them in the recycle bin: switched off, out of People and every list, their
# sign-ins ended, no longer an administrator. Nothing is erased (what they did keeps pointing at them),
# so they can be restored: back on People, still switched off until someone switches them on.


@router.delete("/people/{person_id}")
def delete_person(person_id: str, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    p = get_person(db, me, person_id)
    if p.deleted_at is not None:
        return {"person": person_out(p)}
    if p.id == me.id:
        raise conflict("You can't delete yourself. Ask another administrator.")
    if p.is_company_admin and not db.scalar(
            select(func.count()).select_from(Identity).where(Identity.company_id == me.company_id, Identity.is_company_admin, Identity.id != p.id,
                                                             Identity.status == "active", Identity.via_operator.is_(False))):
        raise conflict(f"{p.full_name} is the company's only administrator. Make someone else one first (Company profile).")
    role = db.get(AccessRole, p.access_role_id) if p.access_role_id else None
    if role and role.is_admin and p.status == "active" and not other_admins_people(db, me.company_id, but=p.id):
        raise conflict("Someone must always have everything, or nobody could fix a mistake in access. Give it to someone else first.")
    now = datetime.now(UTC)
    p.status, p.is_company_admin, p.deleted_at, p.deleted_by = "suspended", False, now, me.email
    for s in db.scalars(select(IdentitySession).where(IdentitySession.identity_id == p.id, IdentitySession.revoked_at.is_(None))):
        s.revoked_at = now
    audit(db, me.email, "access.person_deleted", category="security", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    told(request, settings, me.company_id)
    return {"person": person_out(p)}


@router.get("/bin")
def recycle_bin(db: DB, me: Admin) -> dict:
    rows = db.scalars(select(Identity).where(Identity.company_id == me.company_id, Identity.deleted_at.is_not(None), Identity.via_operator.is_(False))
                      .order_by(Identity.deleted_at.desc())).all()
    return {"people": [{**person_out(p), "deletedAt": p.deleted_at.isoformat(), "deletedBy": p.deleted_by} for p in rows]}


@router.post("/people/{person_id}/restore")
def restore_person(person_id: str, db: DB, me: Admin) -> dict:
    p = get_person(db, me, person_id)
    if p.deleted_at is None:
        return {"person": person_out(p)}
    p.deleted_at, p.deleted_by = None, None
    audit(db, me.email, "access.person_restored", category="security", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    return {"person": person_out(p)}


# ---- Invitations, two-step resets, import (2026-10-30, app/sign_in.py) ---------------------------------


def invite(db: Session, settings, me: Identity, p: Identity) -> dict:
    """A link for them to set their own password (a week), emailed when the company sends email; the
    link is also given back, for the administrator to pass on another way."""
    account = account_of(db, p)
    if account is None:
        raise conflict(f"{p.full_name} has no Bishnoi One account yet.")
    token = sign_in.make_link(db, account, "invite", settings.invite_link_hours, made_by=me.email)
    url = sign_in.site(db, settings) + sign_in.link_path("invite", token)
    company = db.get(Company, me.company_id)
    emailed = sign_in.send(db, settings, me.company_id, p.email, f"You're invited to {company.name} on Bishnoi One",
                           f"Hello {p.full_name},\n\n{me.full_name} added you to {company.name} on Bishnoi One. "
                           f"Choose your password here (the link works for {settings.invite_link_hours // 24} days, once):\n\n{url}\n\n"
                           f"Then sign in with {p.email}.\n\nBishnoi One")
    audit(db, me.email, "access.person_invited" if emailed else "access.invite_link_made", category="security", target=p.email,
          target_type="identity", target_id=p.id, company_id=me.company_id)
    return {"link": url, "emailed": emailed}


@router.post("/people/{person_id}/invite")
def invite_person(person_id: str, db: DB, me: Admin, settings: SettingsDep) -> dict:
    p = get_person(db, me, person_id)
    if p.deleted_at is not None or p.status != "active":
        raise conflict(f"{p.full_name} is switched off. Switch them on first.")
    out = invite(db, settings, me, p)
    db.commit()
    return out


@router.post("/people/{person_id}/two-step/reset")
def reset_two_step(person_id: str, db: DB, me: Admin) -> dict:
    """Their authenticator app lost (a new phone): two-step sign-in off, to set up again at their next sign-in."""
    p = get_person(db, me, person_id)
    if p.id == me.id:
        raise conflict("Turn yours off in Your profile, or ask another administrator.")
    account = account_of(db, p)
    if account is None or not sign_in.two_step_on(account):
        return {"reset": False}
    account.two_step_secret, account.two_step_on_at, account.recovery_codes = None, None, None
    now = datetime.now(UTC)
    for s in db.scalars(select(IdentitySession).where(IdentitySession.identity_id == p.id, IdentitySession.revoked_at.is_(None))):
        s.revoked_at = now
    audit(db, me.email, "access.two_step_reset", category="security", target=p.email, target_type="identity", target_id=p.id, company_id=me.company_id)
    db.commit()
    return {"reset": True}


class ImportRow(Api):
    full_name: str = Field("", max_length=200)
    email: str = Field("", max_length=254)
    title: str | None = Field(None, max_length=200)
    role: str | None = Field(None, max_length=120)
    apps: list[str] = []


class ImportIn(Api):
    rows: list[ImportRow] = Field(max_length=2000)
    apply: bool = False
    invite: bool = False


@router.post("/people/import")
def import_people(body: ImportIn, request: Request, db: DB, me: Admin, settings: SettingsDep) -> dict:
    """People from a file (already read and mapped in the browser): each row checked first (new,
    already here, or a problem with why); with apply, every new one added at once, or none."""
    company = db.get(Company, me.company_id)
    roles = {r.name.strip().lower(): r for r in db.scalars(select(AccessRole).where(AccessRole.company_id == me.company_id))}
    apps = {a.key: a for a in access_roles.modules_of(db, me.company_id)}
    by_name = {a.name.strip().lower(): a for a in apps.values()} | {k: a for k, a in apps.items()}
    here = {e.lower() for e in db.scalars(select(Identity.email).where(Identity.company_id == me.company_id))}
    seen: set[str] = set()
    out = []
    for n, row in enumerate(body.rows, start=1):
        reasons: list[str] = []
        name = " ".join(row.full_name.split())
        email = row.email.strip().lower()
        if len(name) < 2:
            reasons.append("No name.")
        try:
            email = check_email(email)
        except ValueError:
            reasons.append("Not an email address.")
        outcome = "new"
        if email and email in seen:
            reasons.append("This email is in the file twice.")
        seen.add(email)
        if not reasons and email in here:
            outcome = "already"
        elif not reasons:
            for check in (lambda: email_rules.check_company_email(company, email), lambda: email_rules.check_available(db, email, me.company_id)):
                try:
                    check()
                except HTTPException as e:
                    reasons.append(e.detail if isinstance(e.detail, str) else str(e.detail[0].get("msg", "Not allowed.")))
        role = roles.get((row.role or "").strip().lower()) if row.role and row.role.strip() else None
        if row.role and row.role.strip() and role is None:
            reasons.append(f"No role called \"{row.role.strip()}\" here.")
        picked = []
        for a in row.apps:
            found = by_name.get(a.strip().lower())
            if a.strip() and found is None:
                reasons.append(f"No app called \"{a.strip()}\" here.")
            elif found is not None and found not in picked:
                picked.append(found)
        out.append({"n": n, "fullName": name, "email": email, "title": (row.title or "").strip() or None, "role": role.name if role else None,
                    "apps": [a.key for a in picked], "outcome": "problem" if reasons else outcome, "reasons": reasons, "_role": role, "_apps": picked})
    counts = {k: sum(1 for r in out if r["outcome"] == k) for k in ("new", "already", "problem")}
    result = {"rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in out], "counts": counts}
    if not body.apply:
        return result
    if counts["problem"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Fix or untick the rows with problems first: nothing was added.")
    made, invited, emailed = [], 0, 0
    for r in out:
        if r["outcome"] != "new":
            continue
        p = Identity(company_id=me.company_id, full_name=r["fullName"], email=r["email"], title=r["title"], access_role_id=r["_role"].id if r["_role"] else None)
        db.add(p)
        db.flush()
        for app in r["_apps"]:
            db.add(IdentityApp(identity_id=p.id, application_id=app.id, granted_by=me.email))
        made.append(p)
    db.flush()
    audit(db, me.email, "access.people_imported", target=f"{len(made)} people", target_type="identity", company_id=me.company_id)
    if body.invite:
        for p in made:
            sent = invite(db, settings, me, p)
            invited += 1
            emailed += 1 if sent["emailed"] else 0
    db.commit()
    told(request, settings, me.company_id)
    return {**result, "added": len(made), "invited": invited, "emailed": emailed}
