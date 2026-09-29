"""Nabhi accounts: the companies' people signing in once, here, for every
application they have been given.

- /identity/login, /identity/logout: their sign-in (not the console's staff).
- /identity/me: who they are, and the applications they may open.
- /identity/pass: a pass into one application (app/passes.py), sent back to
  that application's own address (or to Nabhi.exe on the same PC) only.
- /identity/password: changing their password.
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
from app.audit import audit
from app.deps import DB, Address, SettingsDep, as_utc, get_db
from app.models import Application, Company, CompanyApp, Identity, IdentityApp, IdentitySession
from app.passes import ISSUER, PassUnavailable, issue, key_id, public_key
from app.routers.auth import Attempts
from app.security import DUMMY_HASH, MAX_PASSWORD, check_password_rules, hash_password, new_token, token_hash, verify_password

router = APIRouter(tags=["nabhi accounts"])

WRONG = "That email and password don't match a Nabhi account."
attempts = Attempts()
_bearer = HTTPBearer(auto_error=False)

# Nabhi.exe runs the applications on the PC itself, on these ports.
DESKTOP_PORTS = range(47300, 47400)
RETURN_PATH = "/auth/platform"


def current_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[IdentitySession, Identity]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in with your Nabhi account.")
    record = db.scalar(select(IdentitySession).where(IdentitySession.token_hash == token_hash(credentials.credentials)))
    if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your Nabhi sign-in has ended. Please sign in again.")
    person = db.get(Identity, record.identity_id)
    changed = person and person.password_changed_at and as_utc(record.created_at) < as_utc(person.password_changed_at)
    if person is None or person.status != "active" or changed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your Nabhi sign-in has ended. Please sign in again.")
    return record, person


Signed = Annotated[tuple[IdentitySession, Identity], Depends(current_identity)]


class LoginIn(Api):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


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
    person = db.scalar(select(Identity).where(func.lower(Identity.email) == email))
    ok = verify_password(body.password, person.password_hash if person and person.password_hash else DUMMY_HASH)
    if person is None or not person.password_hash or not ok:
        attempts.failed(email, window)
        audit(db, email, "identity.sign_in_failed", category="security", target=email, target_type="identity", target_id=person.id if person else None, address=address)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG)
    company = db.get(Company, person.company_id)
    if person.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This Nabhi account is suspended. Ask your company's administrator.")
    if company is None or company.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your company's Nabhi access is suspended. Ask your company's administrator.")
    attempts.clear(email)
    token = new_token()
    now = datetime.now(UTC)
    expires_in = settings.identity_session_hours * 3600
    db.add(IdentitySession(token_hash=token_hash(token), identity_id=person.id, created_at=now, expires_at=now + timedelta(seconds=expires_in)))
    person.last_active_at = now
    audit(db, person.email, "identity.signed_in", category="security", target=person.email, target_type="identity", target_id=person.id, company_id=person.company_id, address=address)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in}


@router.post("/identity/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(signed: Signed, db: DB) -> Response:
    record, person = signed
    record.revoked_at = datetime.now(UTC)
    audit(db, person.email, "identity.signed_out", category="security", target=person.email, target_type="identity", target_id=person.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def granted(db: Session, person: Identity) -> list[tuple[Application, IdentityApp]]:
    """The applications this person may open: given to them, and their company has it."""
    rows = db.execute(
        select(Application, IdentityApp)
        .join(IdentityApp, IdentityApp.application_id == Application.id)
        .join(CompanyApp, (CompanyApp.application_id == Application.id) & (CompanyApp.company_id == person.company_id))
        .where(IdentityApp.identity_id == person.id, Application.is_active)
        .order_by(Application.sort_order, Application.name)
    ).all()
    return [(a, g) for a, g in rows]


@router.get("/identity/me")
def me(signed: Signed, db: DB) -> dict:
    _, person = signed
    company = db.get(Company, person.company_id)
    return {
        "id": person.id,
        "email": person.email,
        "fullName": person.full_name,
        "title": person.title,
        "isCompanyAdmin": person.is_company_admin,
        "company": {"id": company.id, "name": company.name, "slug": company.slug} if company else None,
        "apps": [
            {"key": a.key, "name": a.name, "appUrl": a.app_url, "role": g.role, "isAppAdmin": g.is_app_admin}
            for a, g in granted(db, person)
        ],
    }


class PassIn(Api):
    app: str = Field(min_length=1, max_length=40)
    return_to: str = Field(min_length=1, max_length=500)


def check_return(app: Application, return_to: str, settings) -> str:
    """The pass goes back only to the application's own address, or to Nabhi.exe on this PC."""
    try:
        target = urlsplit(return_to)
    except ValueError:
        target = None
    if target is None or target.path != RETURN_PATH or target.query or target.fragment or target.username or target.password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That return address isn't one this application uses.")
    origin = f"{target.scheme}://{target.netloc}"
    registered = urlsplit(app.app_url) if app.app_url else None
    if registered and origin == f"{registered.scheme}://{registered.netloc}":
        return return_to
    if target.scheme == "http" and target.hostname in ("127.0.0.1", "localhost") and target.port:
        if target.port in DESKTOP_PORTS or settings.environment != "production":
            return return_to
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "That return address isn't one this application uses.")


@router.post("/identity/pass")
def make_pass(body: PassIn, signed: Signed, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    _, person = signed
    app = db.scalar(select(Application).where(Application.key == body.app, Application.is_active))
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such application.")
    return_to = check_return(app, body.return_to, settings)
    company = db.get(Company, person.company_id)
    if company is None or company.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your company's Nabhi access is suspended. Ask your company's administrator.")
    if db.get(CompanyApp, (company.id, app.id)) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{company.name} doesn't have {app.name}. Ask your company's administrator.")
    grant = db.get(IdentityApp, (person.id, app.id))
    if grant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your Nabhi account doesn't include {app.name}. Ask your company's administrator for access.")
    try:
        token = issue(settings, person, company, app, grant)
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
    person.password_hash = hash_password(body.new_password)
    person.password_changed_at = now
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
