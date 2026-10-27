"""Bishnoi One accounts: the companies' people signing in once, here, for every
application they have been given.

- /identity/login, /identity/logout: their sign-in (not the console's staff).
- /identity/me: who they are, and the applications they may open.
- /identity/switch: to another company they work for (same email, one password).
- /identity/pass: a pass into one application (app/passes.py), sent back to
  that application's own address (or to Bishnoi One.exe on the same PC) only;
  for the company they're in, or another of theirs when it names one.
- /identity/password: changing their password (at every company of theirs).

Someone who works for two companies has a row at each (models.Identity), under
the same email; a sign-in is at one of them at a time.
- /pass/key: the platform's public key, for the applications to check passes.

A pass is refused, in words a person can act on, when the account or its
company is suspended, when the company doesn't have the application, or when
the person hasn't been given it.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import Api
from app.access_roles import role_for_pass
from app.audit import audit
from app import passwords
from app.deps import DB, Address, SettingsDep, as_utc, get_db
from app.models import AccessRole, Application, Company, User, CompanyApp, Identity, IdentityApp, IdentitySession
from app.passes import ISSUER, PassUnavailable, issue, key_id, public_key
from app.routers.auth import Attempts
from app.security import DUMMY_HASH, MAX_PASSWORD, check_password_rules, hash_password, new_token, token_hash, verify_password

router = APIRouter(tags=["bishnoi accounts"])

WRONG = "That email and password don't match a Bishnoi One account."
attempts = Attempts()
_bearer = HTTPBearer(auto_error=False)

# Bishnoi One.exe runs the applications on the PC itself, on these ports.
DESKTOP_PORTS = range(47300, 47400)
RETURN_PATH = "/auth/platform"


def current_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[IdentitySession, Identity]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in with your Bishnoi One account.")
    record = db.scalar(select(IdentitySession).where(IdentitySession.token_hash == token_hash(credentials.credentials)))
    if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your Bishnoi One sign-in has ended. Please sign in again.")
    person = db.get(Identity, record.identity_id)
    changed = person and person.password_changed_at and as_utc(record.created_at) < as_utc(person.password_changed_at)
    if person is None or person.status != "active" or changed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your Bishnoi One sign-in has ended. Please sign in again.")
    return record, person


Signed = Annotated[tuple[IdentitySession, Identity], Depends(current_identity)]


class LoginIn(Api):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


def same_person(db: Session, email: str) -> list[Identity]:
    """Every company's row for this email: the most recently used first."""
    return list(db.scalars(
        select(Identity).where(func.lower(Identity.email) == email.strip().lower())
        .order_by(Identity.last_active_at.desc().nulls_last(), Identity.created_at)
    ))


def usable(db: Session, rows: list[Identity]) -> list[tuple[Identity, Company]]:
    """The rows they can work in now: active, at an active company."""
    out = []
    for row in rows:
        company = db.get(Company, row.company_id)
        if row.status == "active" and company is not None and company.status == "active":
            out.append((row, company))
    return out


def open_session(db: Session, settings, person: Identity, address, action: str) -> dict:
    token = new_token()
    now = datetime.now(UTC)
    expires_in = settings.identity_session_hours * 3600
    db.add(IdentitySession(token_hash=token_hash(token), identity_id=person.id, created_at=now, expires_at=now + timedelta(seconds=expires_in)))
    person.last_active_at = now
    audit(db, person.email, action, category="security", target=person.email, target_type="identity", target_id=person.id, company_id=person.company_id, address=address)
    db.commit()
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in}


@router.post("/identity/login")
def login(body: LoginIn, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    email = body.email.strip().lower()
    window = settings.login_lockout_minutes * 60
    wait = attempts.wait_seconds(email, settings.login_attempts, window)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many wrong passwords. Try again in {max(1, wait // 60)} minute(s).",
            headers={"Retry-After": str(wait)},
        )
    rows = same_person(db, email)
    # One password for all their companies (kept the same at each row).
    person = next((r for r in rows if r.password_hash), rows[0] if rows else None)
    ok = verify_password(body.password, person.password_hash if person and person.password_hash else DUMMY_HASH)
    if person is None or not person.password_hash or not ok:
        attempts.failed(email, window)
        audit(db, email, "identity.sign_in_failed", category="security", target=email, target_type="identity", target_id=person.id if person else None, address=address)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG)
    # At the company they last worked in, of those they can work in now.
    open_rows = usable(db, rows)
    if not open_rows:
        if all(r.status != "active" for r in rows):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This Bishnoi One account is suspended. Ask your company's administrator.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your company's Bishnoi One access is suspended. Ask your company's administrator.")
    attempts.clear(email)
    response.headers["Cache-Control"] = "no-store"
    return open_session(db, settings, open_rows[0][0], address, "identity.signed_in")


@router.post("/identity/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(signed: Signed, db: DB) -> Response:
    record, person = signed
    record.revoked_at = datetime.now(UTC)
    audit(db, person.email, "identity.signed_out", category="security", target=person.email, target_type="identity", target_id=person.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def admin_grant(person: Identity, app: Application) -> IdentityApp:
    """A company administrator's standing grant to an application their company has: Administrator
    there, given or not (decided 2026-10-25). Never saved; made fresh each time it's asked for."""
    return IdentityApp(identity_id=person.id, application_id=app.id, role="Administrator", is_app_admin=True, granted_at=None)


def grant_of(db: Session, person: Identity, app: Application) -> IdentityApp | None:
    """What this person holds on an application: their grant, or a company administrator's standing one."""
    grant = db.get(IdentityApp, (person.id, app.id))
    if person.is_company_admin and (grant is None or not grant.is_app_admin):
        return admin_grant(person, app) if grant is None else IdentityApp(
            identity_id=person.id, application_id=app.id, role=grant.role or "Administrator", is_app_admin=True, granted_at=grant.granted_at)
    return grant


def granted(db: Session, person: Identity) -> list[tuple[Application, IdentityApp]]:
    """The applications this person may open: given to them, and their company has it. A company's
    administrator opens every application the company has."""
    rows = db.execute(
        select(Application, IdentityApp)
        .join(CompanyApp, (CompanyApp.application_id == Application.id) & (CompanyApp.company_id == person.company_id))
        .outerjoin(IdentityApp, (IdentityApp.application_id == Application.id) & (IdentityApp.identity_id == person.id))
        .where(Application.is_active)
        .order_by(Application.sort_order, Application.name)
    ).all()
    if person.is_company_admin:
        return [(a, grant_of(db, person, a)) for a, _ in rows]
    return [(a, g) for a, g in rows if g is not None]


@router.get("/identity/me")
def me(signed: Signed, db: DB) -> dict:
    _, person = signed
    company = db.get(Company, person.company_id)
    role = db.get(AccessRole, person.access_role_id) if person.access_role_id else None
    return {
        "id": person.id,
        "email": person.email,
        "fullName": person.full_name,
        "title": person.title,
        "isCompanyAdmin": person.is_company_admin,
        "company": {"id": company.id, "name": company.name, "slug": company.slug} if company else None,
        # Every company they work for, to switch to (this one too).
        "companies": sorted(
            ({"id": c.id, "name": c.name, "slug": c.slug, "current": c.id == person.company_id} for _, c in usable(db, same_person(db, person.email))),
            key=lambda c: c["name"].lower(),
        ),
        # Their one role at the company (app/access_roles.py), when they have one.
        "role": role.name if role else None,
        # Also Bishnoi One staff here (same email): "admin" (Platform Admin) or "member" (Support), else None.
        # The one app's Admin Console shows companies, APIs and accounts to them (app/deps.py staff_by_account).
        "staff": db.scalar(select(User.role).where(func.lower(User.email) == person.email.lower(), User.is_active)),
        "apps": [
            {"key": a.key, "name": a.name, "appUrl": a.app_url, "role": role.name if role else g.role, "isAppAdmin": g.is_app_admin or bool(role and role.is_admin),
             # When it was given to them: the first one given is where they start (the one app opens it after sign-in).
             "grantedAt": as_utc(g.granted_at).isoformat() if g.granted_at else None}
            for a, g in granted(db, person)
        ],
    }


class SwitchIn(Api):
    company: str = Field(min_length=1, max_length=60)


def at_company(db: Session, person: Identity, slug: str) -> Identity:
    """Their row at another company of theirs (by its short name), or 403."""
    for row, company in usable(db, same_person(db, person.email)):
        if company.slug == slug.strip().lower():
            return row
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't work for that company on Bishnoi One, or its access is suspended. Ask its administrator.")


@router.post("/identity/switch")
def switch(body: SwitchIn, signed: Signed, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    """To another company they work for: a new sign-in there, in place of this one."""
    record, person = signed
    there = at_company(db, person, body.company)
    record.revoked_at = datetime.now(UTC)
    response.headers["Cache-Control"] = "no-store"
    return open_session(db, settings, there, address, "identity.switched_company")


class PassIn(Api):
    app: str = Field(min_length=1, max_length=40)
    return_to: str = Field(min_length=1, max_length=500)
    # Another company of theirs (its short name); the one they're in when not given.
    company: str | None = Field(default=None, max_length=60)


def check_return(app: Application, return_to: str, settings) -> str:
    """The pass goes back only to the application's own address, or to Bishnoi One.exe on this PC."""
    try:
        target = urlsplit(return_to)
    except ValueError:
        target = None
    if target is None or target.path != RETURN_PATH or target.query or target.fragment or target.username or target.password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That return address isn't one this application uses.")
    registered = urlsplit(app.app_url) if app.app_url else None
    # The application's own host and port. The scheme may differ from what's
    # registered — an office .local address is served over http while it was
    # stored as https — so the host has to match, not the scheme.
    if registered and target.netloc and target.netloc == registered.netloc:
        return return_to
    # The one app (ONE_APP_URL): every module's screens on one site, so it is a return for each.
    one = urlsplit(settings.one_app_url) if settings.one_app_url else None
    if one and target.netloc and target.netloc == one.netloc:
        return return_to
    if target.scheme == "http" and target.hostname in ("127.0.0.1", "localhost") and target.port:
        if target.port in DESKTOP_PORTS or settings.environment != "production":
            return return_to
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "That return address isn't one this application uses.")


@router.post("/identity/pass")
def make_pass(body: PassIn, signed: Signed, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    _, person = signed
    if body.company:
        person = at_company(db, person, body.company)
    app = db.scalar(select(Application).where(Application.key == body.app, Application.is_active))
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such application.")
    return_to = check_return(app, body.return_to, settings)
    company = db.get(Company, person.company_id)
    if company is None or company.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your company's Bishnoi One access is suspended. Ask your company's administrator.")
    if db.get(CompanyApp, (company.id, app.id)) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{company.name} doesn't have {app.name}. Ask your company's administrator.")
    grant = grant_of(db, person, app)
    if grant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your Bishnoi One account doesn't include {app.name}. Ask your company's administrator for access.")
    try:
        token = issue(settings, person, company, app, grant, role_for_pass(db, person, app))
    except PassUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    person.last_active_at = datetime.now(UTC)
    audit(db, person.email, "identity.opened_app", category="security", target=app.name, target_type="application", target_id=app.id, company_id=person.company_id, application_id=app.id, address=address)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"pass": token, "returnTo": return_to}


class PasswordIn(Api):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD)
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD)


@router.post("/identity/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordIn, signed: Signed, db: DB) -> Response:
    record, person = signed
    if not verify_password(body.current_password, person.password_hash or DUMMY_HASH):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Your current password isn't right.")
    problem = check_password_rules(body.new_password)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    now = datetime.now(UTC)
    password = hash_password(body.new_password)
    # One password at every company of theirs, and in the Admin Console (app/passwords.py).
    passwords.set_for(db, person.email, password, now)
    # this sign-in carries on; every other one ends
    record.created_at = now
    audit(db, person.email, "identity.password_changed", category="security", target=person.email, target_type="identity", target_id=person.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pass/key")
def pass_key(settings: SettingsDep) -> dict:
    """What the applications check passes with. Not a secret."""
    try:
        return {"issuer": ISSUER, "alg": "EdDSA", "kid": key_id(settings), "publicKey": public_key(settings)}
    except PassUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
