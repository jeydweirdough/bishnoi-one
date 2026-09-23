import logging
import threading
import time
from collections import defaultdict

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access, active_member, owns_company
from app.config import Settings
from app.deps import DB, CurrentAccess, CurrentClaims, CurrentOrg, CurrentUser, SettingsDep
from app.models import (
    LocalCredential,
    Membership,
    Organization,
    PlatformSession,
    Profile,
    ProfilePhoto,
    SessionRecord,
    Subdivision,
    utcnow,
)
from app.catalogue import app_urls, catalogue
from app.fields import fields_out
from app.lists import lists_out
from app.modules import ORDERS, Kind, Module
from app.platform import company, every_company, is_developer_admin
from app.routers.photos import when as photo_when
from app.schemas import LoginIn, SwitchOrgIn, ViewAsIn
from app.security import DUMMY_HASH, issue_token, verify_password
from app.audit import audit
from app.tenancy import all_companies, company_of, set_company

log = logging.getLogger("crm.auth")

router = APIRouter(tags=["sign-in"])

# Sign-in attempts per email. In memory, so per process; enough to slow down
# guessing until Supabase Auth (which has its own limits) takes over. An attempt
# is counted before the password is checked, so parallel requests can't slip
# past the limit, and cleared when sign-in succeeds.
WINDOW_SECONDS = 15 * 60
MAX_ATTEMPTS = 5
_attempts: dict[str, list[float]] = defaultdict(list)
_attempts_lock = threading.Lock()


def _reserve_attempt(email: str) -> int | None:
    """Counts an attempt and returns None, or returns the minutes to wait if over the limit."""
    now = time.monotonic()
    with _attempts_lock:
        recent = [t for t in _attempts.get(email, []) if t > now - WINDOW_SECONDS]
        if len(recent) >= MAX_ATTEMPTS:
            _attempts[email] = recent
            return int(WINDOW_SECONDS - (now - recent[0])) // 60 + 1
        _attempts[email] = [*recent, now]
        # Keep the table from growing with every address ever tried.
        for key in [k for k, times in _attempts.items() if times and times[-1] <= now - WINDOW_SECONDS]:
            del _attempts[key]
        return None


def _clear_attempts(email: str) -> None:
    with _attempts_lock:
        _attempts.pop(email, None)


def companies_of(db: Session, user_id: str) -> list[tuple[Membership, Organization]]:
    """The companies a person can work in now: the one they used last first, then the one they joined first."""
    with all_companies(db):
        rows = db.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.org_id)
            .where(Membership.user_id == user_id, Membership.status == "active", Organization.status == "active")
        ).all()

    def order(row: tuple[Membership, Organization]) -> tuple:
        # SQLite hands back naive datetimes and Postgres aware ones; compare them as naive UTC.
        used, joined = (d.replace(tzinfo=None) if d else None for d in (row[0].last_used_at, row[0].created_at))
        return (used is None, -used.timestamp() if used else 0.0, joined)

    return sorted(((m, o) for m, o in rows), key=order)


def start_session(
    db: Session, settings: Settings, user: Profile, membership: Membership | None, org_id: str | None = None
) -> dict:
    """A new sign-in session in a company, and the web app's token for it.

    Normally that company is the one the membership is in. A Developer Admin
    opening a company they do not work in has no membership there, so the
    company is named directly (app/platform.py)."""
    now = utcnow()
    org = membership.org_id if membership is not None else org_id
    if org is None:
        raise ValueError("a session needs a company")
    with all_companies(db):
        record = SessionRecord(org_id=org, user_id=user.id, expires_at=now + timedelta(hours=settings.session_hours))
        db.add(record)
        if membership is not None:
            membership.last_used_at = now
        db.commit()
    token, expires_in = issue_token(settings, user, org, record.id, expires_at=record.expires_at)
    return {"accessToken": token, "expiresIn": expires_in}


def start_platform_session(db: Session, settings: Settings, user: Profile) -> dict:
    """A session in no company: the platform itself. Only a Developer Admin has one."""
    now = utcnow()
    record = PlatformSession(user_id=user.id, expires_at=now + timedelta(hours=settings.session_hours))
    db.add(record)
    db.commit()
    token, expires_in = issue_token(settings, user, None, record.id, expires_at=record.expires_at)
    return {"accessToken": token, "expiresIn": expires_in}


def end_session(db: Session, session_id: str) -> None:
    """Ends whichever kind of session that id names.

    Read across companies on purpose: a session is ended from wherever the
    person happens to be, including the platform, where there is no company to
    look inside."""
    with all_companies(db):
        for record in (db.get(SessionRecord, session_id), db.get(PlatformSession, session_id)):
            if record is not None and record.revoked_at is None:
                record.revoked_at = utcnow()
                db.commit()


def photo_at(db: Session, user_id: str) -> str | None:
    """When their picture last changed; None means they have none, so initials are drawn."""
    row = db.get(ProfilePhoto, user_id)
    return photo_when(row.updated_at) if row else None


def org_out(org: Organization) -> dict:
    return {
        "id": org.id,
        "slug": org.slug,
        "name": org.name,
        "brandName": org.brand_name,
        "currency": org.currency,
        # How many decimals this money has: two for a peso, none for a yen.
        "minorUnits": org.minor_units,
        "locale": org.locale,
        "timezone": org.timezone,
    }


@router.post("/auth/login")
def login(body: LoginIn, db: DB, settings: SettingsDep) -> dict:
    email = body.email.lower()
    wait = _reserve_attempt(email)
    if wait is not None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many tries. Try again in {wait} minutes.")

    user = db.scalar(select(Profile).where(Profile.email == email))
    credential = db.get(LocalCredential, user.id) if user else None
    matched = verify_password(body.password, credential.password_hash if credential else DUMMY_HASH)
    if not (user and credential and matched):
        log.info("sign-in failed for %s", email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That email and password don't match.")
    # A Developer Admin signs in to the platform, not to a company. Landing them
    # in whichever company came first is how you end up looking at one company's
    # settings when your job is all of them.
    if user.is_active and is_developer_admin(db, user.id):
        _clear_attempts(email)
        log.info("signed in to the platform: %s", email)
        return start_platform_session(db, settings, user)

    companies = companies_of(db, user.id) if user.is_active else []
    if not companies:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is switched off. Ask your admin.")

    _clear_attempts(email)
    log.info("signed in: %s", email)
    return start_session(db, settings, user, companies[0][0])


@router.get("/auth/orgs")
def my_companies(claims: CurrentClaims, user: CurrentUser, db: DB) -> dict:
    """The companies this person can open. For a Developer Admin that is every
    company on the platform, switched-off ones included, since a company that
    has been suspended is exactly the sort that needs looking at."""
    if is_developer_admin(db, user.id):
        mine = {o.id for _, o in companies_of(db, user.id)}
        return {
            "current": claims.org_id,
            "everyCompany": True,
            "items": [{**org_out(o), "status": o.status, "isMine": o.id in mine} for o in every_company(db)],
        }
    return {
        "current": claims.org_id,
        "everyCompany": False,
        "items": [{**org_out(o), "status": "active", "isMine": True} for _, o in companies_of(db, user.id)],
    }


@router.post("/auth/switch-org")
def switch_company(body: SwitchOrgIn, claims: CurrentClaims, user: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    """A new session in another company. Same answer for "not yours" and "no such
    company", so nobody can map the platform by guessing ids.

    A Developer Admin may open any company that is switched on, member or not:
    reaching a company to put it right is the whole of the job."""
    membership = next((m for m, _ in companies_of(db, user.id) if m.org_id == body.org_id), None)
    if membership is None:
        target = company(db, body.org_id) if is_developer_admin(db, user.id) else None
        if target is None or target.status != "active":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "You're not in that company.")
        end_session(db, claims.session_id)
        log.info("developer admin opened company %s: %s", target.slug, user.email)
        return start_session(db, settings, user, None, org_id=target.id)
    end_session(db, claims.session_id)
    log.info("switched company: %s", user.email)
    return start_session(db, settings, user, membership)


@router.post("/auth/view-as")
def view_as(body: ViewAsIn, claims: CurrentClaims, user: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    """Look through somebody's eyes, in their company.

    Only a Developer Admin, and only to look: the session resolves as that
    person -- their teams, their scopes, their screens, which is the only honest
    way to see what they see -- but every change through it is refused
    (app/deps.py), and the audit log names who was really at the keyboard.

    Not another Developer Admin: the tier is nobody's to borrow."""
    if not is_developer_admin(db, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for developer admins.")
    target_org = company(db, body.org_id)
    if target_org is None or target_org.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such company.")

    set_company(db, target_org.id)
    with all_companies(db):
        person = db.get(Profile, body.user_id)
    membership = active_member(db, body.user_id) if person else None
    if person is None or membership is None or not person.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nobody like that in this company.")
    if is_developer_admin(db, person.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A developer admin isn't somebody to look through.")

    end_session(db, claims.session_id)
    now = utcnow()
    with all_companies(db):
        record = SessionRecord(
            org_id=target_org.id,
            user_id=person.id,
            expires_at=now + timedelta(hours=settings.session_hours),
            viewed_by_id=user.id,
        )
        db.add(record)
        db.commit()
    audit(db, user, "viewed.as", f"{person.email} in {target_org.slug}")
    log.info("viewing as %s in %s: %s", person.email, target_org.slug, user.email)
    token, expires_in = issue_token(
        settings, person, target_org.id, record.id, expires_at=record.expires_at, viewed_by=user.id
    )
    return {"accessToken": token, "expiresIn": expires_in}


@router.post("/auth/leave")
def leave_company(claims: CurrentClaims, user: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    """Back to the platform, from a company or from looking through somebody.

    Whoever is really at the keyboard comes back as themselves: `viewed_by` when
    looking through somebody, and the signed-in person otherwise."""
    with all_companies(db):
        me = db.get(Profile, claims.viewed_by) if claims.viewed_by else user
    if me is None or not is_developer_admin(db, me.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for developer admins.")
    end_session(db, claims.session_id)
    log.info("back to the platform: %s", me.email)
    return start_platform_session(db, settings, me)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(claims: CurrentClaims, user: CurrentUser, db: DB) -> Response:
    """Ends the session here and in every app it was handed to."""
    end_session(db, claims.session_id)
    log.info("signed out: %s", user.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def modules_for(
    access: Access,
    modules: tuple[Module, ...],
    team_names: dict[tuple[str, str], str],
    app_urls: dict[str, str | None] | None = None,
) -> list[dict]:
    out = []
    for m in modules:
        actions = [a for a in m.actions if access.can(m.key, a)]
        if not actions:
            continue
        teams: dict[str, list[str]] = defaultdict(list)
        for action in actions:
            for scope in access.scopes(m.key, action):
                if scope.division == m.key:
                    teams[scope.subdivision].append(action)
        out.append(
            {
                "key": m.key,
                "name": m.name,
                "kind": m.kind.value,
                "built": m.built,
                # Where a module that's another app lives (None until it's set up).
                **({"url": (app_urls or {}).get(m.key)} if m.kind is Kind.APP else {}),
                "actions": actions,
                # The module's own teams this person works in, and what they may do in each.
                "teams": sorted(
                    (
                        {"code": code, "name": team_names.get((m.key, code), code), "actions": acts}
                        for code, acts in teams.items()
                    ),
                    key=lambda t: t["name"].casefold(),
                ),
            }
        )
    return out


@router.get("/auth/me")
def me(claims: CurrentClaims, user: CurrentUser, access: CurrentAccess, db: DB, settings: SettingsDep) -> dict:
    """Who is signed in, and what they can see.

    In a platform session there is no company yet, so `org` is null and there is
    nothing company-shaped to send: no modules, no lists, no fields. The screens
    read `org === null` as "you are on the platform, pick a company"."""
    if claims.org_id is None:
        return {
            "user": {"id": user.id, "email": user.email, "fullName": user.full_name, "photoAt": photo_at(db, user.id)},
            "org": None,
            # Nobody is being looked through: the platform is nobody's screens.
            "viewedBy": None,
            "canManageSettings": False,
            "canRecover": True,
            # No company open, so there is no department to run one of.
            "manageDepartments": [],
            "isDeveloperAdmin": True,
            "isOwner": False,
            "modules": [],
            "lists": {},
            "customerFields": [],
        }

    org = db.get(Organization, company_of(db))
    team_names = {(d, c): n for d, c, n in db.execute(select(Subdivision.division_code, Subdivision.code, Subdivision.name))}
    # Who is really at the keyboard, when it is not the person named above. The
    # screens say so on every page: a session nobody can tell is borrowed is a
    # session that will be mistaken for the person's own.
    with all_companies(db):
        driver = db.get(Profile, claims.viewed_by) if claims.viewed_by else None
    return {
        "viewedBy": {"email": driver.email, "fullName": driver.full_name} if driver else None,
        "user": {"id": user.id, "email": user.email, "fullName": user.full_name, "photoAt": photo_at(db, user.id)},
        "org": org_out(org),
        "canManageSettings": access.manage_settings,
        # The recovery key itself, not "can reach the recovery screens" -- the
        # screens' own rules combine the two, and the company record is reachable
        # by this key and the owner but not by a plain Admin.
        "canRecover": access.recover_settings,
        # The departments this person runs without running the company. Empty for
        # a company-wide admin too: `canManageSettings` already covers every
        # department, so the two never have to be read together.
        "manageDepartments": sorted(access.manage_departments),
        # The tier above every company. Never a role, so a company's own
        # admins can't grant it (app/platform.py).
        "isDeveloperAdmin": is_developer_admin(db, user.id),
        # The company's own decisions, which its admins cannot grant themselves.
        "isOwner": owns_company(db, user.id),
        # Where each application lives is this company's to set, in
        # Settings -> Apps, not a deployment setting (app/catalogue.py).
        "modules": modules_for(access, catalogue(db), team_names, app_urls(db)),
        # The company's own pick-lists and its own customer fields, so the
        # screens name things the way it does. Reps need these and are not
        # admins, so they ride along with the sign-in rather than a settings call.
        # Switched-off choices come too, carrying `isActive`: a record filed
        # under one still has to show the name its company gave it, so the
        # screens offer only the active ones but can name them all.
        "lists": lists_out(db, active_only=False),
        "customerFields": fields_out(db, "customer", active_only=True),
    }
