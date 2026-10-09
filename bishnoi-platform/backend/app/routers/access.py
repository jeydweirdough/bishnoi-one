"""Access management: who may reach what, at each of the three levels.

- Platform Admin (staff here, role admin) runs the platform: companies,
  applications, everyone's access, settings. Support (role member) sees it
  all and works tickets and incidents.
- Company admin (a user with is_company_admin) runs their own company.
- Application admin (a grant with is_app_admin) runs one application for
  their company.

Also here: access requests (someone asks for an application; a Platform Admin
decides), the staff who sign in to this console, and their sign-in sessions.
"""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import Api, camel, changed, check_email, conflict, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, Address, AdminUser, CurrentSession, CurrentUser
from app.identity import ROLE_NAMES
from app.models import AccessRequest, Application, Company, CompanyApp, Identity, IdentityApp, SignInSession, User

router = APIRouter(prefix="/platform", tags=["access"])

# What each kind of staff may do here, as the Roles & permissions page lists it.
# The API's own checks are in app/deps.py (CurrentUser / AdminUser); this is
# those checks in words.
PERMISSIONS: tuple[tuple[str, str, bool], ...] = (
    ("Dashboard, monitoring and activity", "See", True),
    ("Companies, departments and branches", "See", True),
    ("Companies, departments and branches", "Add, change, suspend", False),
    ("Applications, deployments, integrations", "See", True),
    ("Applications, deployments, integrations", "Add, change, declare a status", False),
    ("Users and their access", "See", True),
    ("Users and their access", "Add, change, grant, withdraw", False),
    ("Access requests", "Log one for somebody", True),
    ("Access requests", "Approve or decline", False),
    ("Support tickets", "Log, assign, move along, note", True),
    ("Incidents", "Declare, update, resolve", True),
    ("Health checks", "Run now", True),
    ("Announcements and maintenance notices", "Write and publish", False),
    ("Settings and staff", "Change", False),
)


class RequestIn(Api):
    identity_id: str
    application_id: str
    role: str | None = Field(None, max_length=60)
    reason: str | None = Field(None, max_length=2000)


class DecisionIn(Api):
    approve: bool
    note: str | None = Field(None, max_length=500)


class StaffPatch(Api):
    full_name: str | None = Field(None, min_length=1, max_length=120)
    email: str | None = Field(None, max_length=254)
    role: str | None = Field(None, pattern="^(admin|member)$")
    is_active: bool | None = None


class StaffIn(Api):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254)
    role: str = Field("member", pattern="^(admin|member)$")
    # None: one is made, and shown once.
    password: str | None = Field(None, max_length=256)


class StaffPasswordIn(Api):
    # None: one is made, and shown once.
    password: str | None = Field(None, max_length=256)


def _email(value: str) -> str:
    try:
        return check_email(value.strip())
    except ValueError as e:
        raise field_error("email", str(e)) from None


def _email_taken(db: Session, email: str, but: str | None = None) -> bool:
    found = db.scalar(select(User).where(func.lower(User.email) == email))
    return found is not None and found.id != but


def _other_admins(db: Session, u: User) -> int:
    """Platform Admins still able to sign in, besides this one."""
    return db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active, User.id != u.id)) or 0


def _password(given: str | None) -> tuple[str, bool]:
    from app.security import check_password_rules

    password = given or secrets.token_urlsafe(9)
    problem = check_password_rules(password)
    if problem:
        raise field_error("password", problem)
    return password, given is None


def request_out(r: AccessRequest, person: Identity, app: Application, company: Company, company_has_app: bool) -> dict:
    return {
        "id": r.id,
        "user": {"id": person.id, "name": person.full_name, "email": person.email},
        "company": {"id": company.id, "name": company.name},
        "application": {"id": app.id, "name": app.name},
        "role": r.role,
        "reason": r.reason,
        "status": r.status,
        "createdAt": iso(r.created_at),
        "decidedAt": iso(r.decided_at),
        "decidedBy": r.decided_by,
        "decisionNote": r.decision_note,
        # Approving needs the company to have the application first.
        "companyHasApp": company_has_app,
    }


def _requests(db: Session, query) -> list[dict]:
    rows = db.execute(
        query.join(Identity, Identity.id == AccessRequest.identity_id)
        .join(Application, Application.id == AccessRequest.application_id)
        .join(Company, Company.id == Identity.company_id)
        .add_columns(Identity, Application, Company)
    ).all()
    pairs = set(db.execute(select(CompanyApp.company_id, CompanyApp.application_id)).tuples())
    return [request_out(r, person, app, company, (company.id, app.id) in pairs) for r, person, app, company in rows]


@router.get("/access/requests")
def list_requests(db: DB, _: CurrentUser, status: str | None = "pending") -> dict:
    query = select(AccessRequest).order_by(AccessRequest.created_at.desc()).limit(200)
    if status in ("pending", "approved", "declined"):
        query = query.where(AccessRequest.status == status)
    pending = db.scalar(select(func.count()).select_from(AccessRequest).where(AccessRequest.status == "pending"))
    return {"requests": _requests(db, query), "pending": pending}


@router.post("/access/requests", status_code=status.HTTP_201_CREATED)
def add_request(body: RequestIn, db: DB, me: CurrentUser) -> dict:
    """Logs a request on someone's behalf (they asked Support, or wrote in)."""
    person = db.get(Identity, body.identity_id)
    if person is None:
        raise field_error("identityId", "Pick who is asking.")
    app = db.get(Application, body.application_id)
    if app is None:
        raise field_error("applicationId", "Pick the application they want.")
    if db.get(IdentityApp, (person.id, app.id)):
        raise field_error("applicationId", f"{person.full_name} can already use {app.name}.")
    if db.scalar(select(AccessRequest).where(AccessRequest.identity_id == person.id, AccessRequest.application_id == app.id,
                                             AccessRequest.status == "pending")):
        raise conflict(f"{person.full_name} is already waiting to hear about {app.name}.")
    r = AccessRequest(identity_id=person.id, application_id=app.id, role=body.role, reason=body.reason)
    db.add(r)
    db.flush()
    audit(db, me, "access.requested", target=f"{person.email} · {app.name}", target_type="user", target_id=person.id,
          company_id=person.company_id, application_id=app.id)
    db.commit()
    return {"request": _requests(db, select(AccessRequest).where(AccessRequest.id == r.id))[0]}


@router.post("/access/requests/{request_id}/decision")
def decide(request_id: str, body: DecisionIn, db: DB, me: AdminUser) -> dict:
    r = db.get(AccessRequest, request_id)
    if r is None:
        raise not_found("request")
    if r.status != "pending":
        raise conflict(f"That request was already {r.status}.")
    person = db.get(Identity, r.identity_id)
    app = db.get(Application, r.application_id)
    if body.approve:
        if db.get(CompanyApp, (person.company_id, app.id)) is None:
            raise conflict(f"{person.full_name}'s company doesn't have {app.name}. Give it to the company first, then approve.")
        if db.get(IdentityApp, (person.id, app.id)) is None:
            db.add(IdentityApp(identity_id=person.id, application_id=app.id, role=r.role, granted_by=me.email))
    r.status = "approved" if body.approve else "declined"
    r.decided_at = datetime.now(UTC)
    r.decided_by = me.email
    r.decision_note = body.note
    audit(db, me, f"access.request_{r.status}", target=f"{person.email} · {app.name}", target_type="user", target_id=person.id,
          company_id=person.company_id, application_id=app.id)
    db.commit()
    return {"request": _requests(db, select(AccessRequest).where(AccessRequest.id == r.id))[0]}


@router.get("/access/organizations")
def organization_access(db: DB, _: CurrentUser) -> dict:
    """Every company against every application: whether it has it, and how
    many of its people use it. With each company's admins."""
    companies = db.scalars(select(Company).order_by(func.lower(Company.name))).all()
    apps = db.scalars(select(Application).where(Application.is_active).order_by(Application.sort_order, Application.name)).all()
    enabled = set(db.execute(select(CompanyApp.company_id, CompanyApp.application_id)).tuples())
    users = {
        (company_id, app_id): n
        for company_id, app_id, n in db.execute(
            select(Identity.company_id, IdentityApp.application_id, func.count())
            .join(IdentityApp, IdentityApp.identity_id == Identity.id)
            .group_by(Identity.company_id, IdentityApp.application_id)
        )
    }
    admins: dict[str, list[dict]] = {}
    for p in db.scalars(select(Identity).where(Identity.is_company_admin).order_by(Identity.full_name)):
        admins.setdefault(p.company_id, []).append({"id": p.id, "name": p.full_name})
    return {
        "applications": [{"id": a.id, "key": a.key, "name": a.name} for a in apps],
        "companies": [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "admins": admins.get(c.id, []),
                "cells": [{"applicationId": a.id, "enabled": (c.id, a.id) in enabled, "userCount": users.get((c.id, a.id), 0)} for a in apps],
            }
            for c in companies
        ],
    }


@router.get("/access/applications")
def application_access(db: DB, _: CurrentUser) -> dict:
    """Per application: the roles people hold in it, and who runs it where."""
    apps = db.scalars(select(Application).where(Application.is_active).order_by(Application.sort_order, Application.name)).all()
    roles: dict[str, dict[str, int]] = {}
    for app_id, role, n in db.execute(
        select(IdentityApp.application_id, IdentityApp.role, func.count()).group_by(IdentityApp.application_id, IdentityApp.role)
    ):
        roles.setdefault(app_id, {})[role or "No role given"] = n
    app_admins: dict[str, list[dict]] = {}
    for g, p, c in db.execute(
        select(IdentityApp, Identity, Company).join(Identity, Identity.id == IdentityApp.identity_id)
        .join(Company, Company.id == Identity.company_id).where(IdentityApp.is_app_admin).order_by(Identity.full_name)
    ):
        app_admins.setdefault(g.application_id, []).append({"id": p.id, "name": p.full_name, "companyName": c.name})
    return {
        "applications": [
            {
                "id": a.id,
                "name": a.name,
                "userCount": sum(roles.get(a.id, {}).values()),
                "roles": [{"role": r, "userCount": n} for r, n in sorted(roles.get(a.id, {}).items(), key=lambda x: (-x[1], x[0]))],
                "admins": app_admins.get(a.id, []),
            }
            for a in apps
        ]
    }


def staff_out(u: User, sessions: int = 0) -> dict:
    return {
        "id": u.id,
        "fullName": u.full_name,
        "email": u.email,
        "role": u.role,
        "roleName": ROLE_NAMES[u.role],
        "isActive": u.is_active,
        "createdAt": iso(u.created_at),
        "lastSignInAt": iso(u.last_sign_in_at),
        "activeSessions": sessions,
    }


def _live_sessions(db: Session) -> dict[str, int]:
    return dict(
        db.execute(
            select(SignInSession.user_id, func.count())
            .where(SignInSession.revoked_at.is_(None), SignInSession.expires_at > datetime.now(UTC))
            .group_by(SignInSession.user_id)
        ).all()
    )


@router.get("/access/roles")
def roles(db: DB, _: CurrentUser) -> dict:
    staff = db.scalars(select(User).order_by(User.full_name)).all()
    live = _live_sessions(db)
    return {
        "staffRoles": [
            {
                "role": role,
                "name": ROLE_NAMES[role],
                "permissions": [{"area": area, "action": action} for area, action, both in PERMISSIONS if both or role == "admin"],
                "holders": [staff_out(u, live.get(u.id, 0)) for u in staff if u.role == role],
            }
            for role in ("admin", "member")
        ],
        "permissions": [{"area": area, "action": action, "support": both} for area, action, both in PERMISSIONS],
        "levels": {
            "companyAdmins": db.scalar(select(func.count()).select_from(Identity).where(Identity.is_company_admin)),
            "applicationAdmins": db.scalar(select(func.count()).select_from(IdentityApp).where(IdentityApp.is_app_admin)),
        },
    }


@router.get("/staff")
def list_staff(db: DB, _: CurrentUser) -> dict:
    live = _live_sessions(db)
    return {"staff": [staff_out(u, live.get(u.id, 0)) for u in db.scalars(select(User).order_by(User.full_name))]}


@router.post("/staff", status_code=status.HTTP_201_CREATED)
def create_staff(body: StaffIn, db: DB, me: AdminUser, address: Address) -> dict:
    """A new staff account for this console. Its password is shown once, to hand over; they change it after."""
    from app.security import hash_password

    email = _email(body.email)
    if _email_taken(db, email):
        raise field_error("email", "There's already a staff account with this email.")
    password, made = _password(body.password)
    u = User(email=email, full_name=body.full_name.strip(), password_hash=hash_password(password), role=body.role)
    db.add(u)
    db.flush()
    audit(db, me, "staff.created", category="security", target=u.email, target_type="staff", target_id=u.id, fields=["role"], address=address)
    db.commit()
    return {"staff": staff_out(u), "password": password if made else None}


@router.patch("/staff/{staff_id}")
def update_staff(staff_id: str, body: StaffPatch, db: DB, me: AdminUser, address: Address) -> dict:
    u = db.get(User, staff_id)
    if u is None:
        raise not_found("staff account")
    if body.email is not None:
        body.email = _email(body.email)
        if _email_taken(db, body.email, but=u.id):
            raise field_error("email", "There's already a staff account with this email.")
    if body.full_name is not None:
        body.full_name = body.full_name.strip()
    fields = {k: v for k, v in changed(body).items() if v is not None and getattr(u, k) != v}
    if u.id == me.id and ({"role", "is_active"} & fields.keys()):
        # So the platform can't be left with nobody to run it by one slip.
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't change your own role or switch yourself off. Ask another Platform Admin.")
    if u.role == "admin" and (fields.get("role") == "member" or fields.get("is_active") is False) and not _other_admins(db, u):
        raise HTTPException(status.HTTP_409_CONFLICT, "This is the last Platform Admin. Make someone else a Platform Admin first.")
    for name, value in fields.items():
        setattr(u, name, value)
    if fields:
        if "role" in fields:
            action = "staff.role_changed"
        elif "is_active" in fields:
            action = f"staff.{'enabled' if u.is_active else 'disabled'}"
        else:
            action = "staff.updated"
        audit(db, me, action, category="security", target=u.email, target_type="staff", target_id=u.id, fields=camel(fields), address=address)
    db.commit()
    return {"staff": staff_out(u, _live_sessions(db).get(u.id, 0))}


@router.post("/staff/{staff_id}/password")
def reset_staff_password(staff_id: str, body: StaffPasswordIn, db: DB, me: AdminUser, address: Address) -> dict:
    """A new password for someone else's staff account, shown once. Their sign-ins end.
    Your own is changed under Account."""
    from app.security import hash_password

    u = db.get(User, staff_id)
    if u is None:
        raise not_found("staff account")
    if u.id == me.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Change your own password under Account.")
    password, made = _password(body.password)
    u.password_hash, u.password_changed_at = hash_password(password), datetime.now(UTC)
    audit(db, me, "staff.password_reset", category="security", target=u.email, target_type="staff", target_id=u.id, address=address)
    db.commit()
    return {"password": password if made else None}


@router.delete("/staff/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff(staff_id: str, db: DB, me: AdminUser, address: Address) -> Response:
    """Gone for good: their sign-ins end; tickets and incidents they had are kept, with nobody on them.
    Switching off is the way to keep the account."""
    u = db.get(User, staff_id)
    if u is None:
        raise not_found("staff account")
    if u.id == me.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't delete your own account. Ask another Platform Admin.")
    if u.role == "admin" and u.is_active and not _other_admins(db, u):
        raise HTTPException(status.HTTP_409_CONFLICT, "This is the last Platform Admin. Make someone else a Platform Admin first.")
    audit(db, me, "staff.deleted", category="security", target=u.email, target_type="staff", target_id=u.id, address=address)
    db.delete(u)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions")
def list_sessions(db: DB, record: CurrentSession, _: CurrentUser) -> dict:
    """Staff sign-ins to this console still running. Each application keeps
    its own users' sign-ins; those aren't here."""
    rows = db.execute(
        select(SignInSession, User).join(User)
        .where(SignInSession.revoked_at.is_(None), SignInSession.expires_at > datetime.now(UTC))
        .order_by(SignInSession.created_at.desc())
    ).all()
    return {
        "sessions": [
            {
                "id": s.id,
                "staff": {"id": u.id, "name": u.full_name, "email": u.email, "roleName": ROLE_NAMES[u.role]},
                "startedAt": iso(s.created_at),
                "expiresAt": iso(s.expires_at),
                "address": s.address,
                "isYours": s.id == record.id,
            }
            for s, u in rows
        ]
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_session(session_id: str, db: DB, me: CurrentUser, address: Address) -> Response:
    """Signs a session out. Your own, or anybody's if you're a Platform Admin."""
    s = db.get(SignInSession, session_id)
    if s is None or s.revoked_at is not None:
        raise not_found("session")
    if s.user_id != me.id and me.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a Platform Admin can sign somebody else out.")
    s.revoked_at = datetime.now(UTC)
    owner = db.get(User, s.user_id)
    audit(db, me, "auth.session_ended", category="security", target=owner.email if owner else "", target_type="staff",
          target_id=s.user_id, address=address)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
