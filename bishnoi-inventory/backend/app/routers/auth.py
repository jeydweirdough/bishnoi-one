"""Signing in and out of this app.

Its own accounts, in its own database: an account here signs in to this app
only. Accounts are made with the users tool (see README.md).
"""

import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import Depends, APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app import platform_pass, platform_roles
from app.audit import audit
from app.demo import DEMO_ACCOUNTS, DEMO_PASSWORD
from app.deps import DB, CurrentSession, CurrentTenant, CurrentUser, SettingsDep, open_company
from app.company import standing as company_standing
from app.config import Settings
from app.tenants import clean, company_of
from app.identity import me_out
from app.models import PlatformPass, Role, SignInSession, User
from app.permissions import ADMINISTRATOR
from app.security import DUMMY_HASH, MAX_PASSWORD, hash_password, new_token, token_hash, verify_password

router = APIRouter(prefix="/auth", tags=["sign-in"])

WRONG = "That email and password don't match an account here."


class Api(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid", str_strip_whitespace=True)


class LoginIn(Api):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


class Attempts:
    """Wrong passwords per email, in memory. Enough to stop guessing; a restart forgets."""

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def wait_seconds(self, email: str, limit: int, window: float) -> int:
        with self._lock:
            recent = self._prune(email, window)
            return int(window - (time.monotonic() - recent[0])) + 1 if len(recent) >= limit else 0

    def failed(self, email: str, window: float) -> None:
        with self._lock:
            self._prune(email, window).append(time.monotonic())

    def clear(self, email: str | None = None) -> None:
        with self._lock:
            self._failures.pop(email, None) if email else self._failures.clear()

    def _prune(self, email: str, window: float) -> deque[float]:
        recent = self._failures[email]
        while recent and time.monotonic() - recent[0] > window:
            recent.popleft()
        return recent


attempts = Attempts()


@router.post("/login", dependencies=[Depends(platform_roles.signs_in_here)])
def login(body: LoginIn, db: DB, settings: SettingsDep, tenant: CurrentTenant, response: Response) -> dict:
    """At the company the sign-in page names (X-Bishnoi-Company), which must be
    registered on the platform (CurrentTenant refuses it otherwise)."""
    email = body.email.lower()
    window = settings.login_lockout_minutes * 60
    wait = attempts.wait_seconds(email, settings.login_attempts, window)
    if wait:
        # A long Retry-After, so the screens don't quietly try again.
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many wrong passwords. Try again in {max(1, wait // 60)} minute(s).",
            headers={"Retry-After": str(wait)},
        )
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not ok or not user.is_active:
        attempts.failed(email, window)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG)
    attempts.clear(email)

    token = f"{tenant.slug}.{new_token()}"
    now = datetime.now(UTC)
    expires_in = settings.session_hours * 3600
    db.add(SignInSession(token_hash=token_hash(token), user_id=user.id, created_at=now, expires_at=now + timedelta(seconds=expires_in)))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in}


# --- signing in with a Bishnoi One account (the platform) -----------------------------------

APP_KEY = "inventory"  # this application's key on the platform


class PlatformIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    token: str = Field(alias="pass", min_length=20, max_length=8000)


@router.post("/platform")
def sign_in_with_platform(body: PlatformIn, request: Request, response: Response) -> dict:
    """Takes a pass from the platform (app/platform_pass.py) and opens a session
    here, as /auth/login does, at the company the pass is for. The person is
    found by their Bishnoi One account, or by email the first time; someone new
    is added with their role from the platform. The platform decides who may
    open this application; this only refuses someone switched off here."""
    base: Settings = request.app.state.settings
    try:
        claims = platform_pass.check_for(base, body.token, APP_KEY)
    except platform_pass.PassRefused as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from None
    slug = clean(claims.get("companySlug"))
    if slug is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This sign-in link doesn't say which company it's for. Sign in again from Bishnoi One.")
    tenant = open_company(request, slug)
    found = company_standing(base, slug)
    if found.company_id and claims.get("company") != found.company_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This sign-in link isn't for this company. Sign in again from Bishnoi One.")
    with tenant.sessions() as db:
        return _open_platform_session(db, base, tenant.slug, claims, response)


def _open_platform_session(db, settings: Settings, slug: str, claims: dict, response: Response) -> dict:
    now = datetime.now(UTC)
    db.execute(delete(PlatformPass).where(PlatformPass.expires_at < now))
    db.add(PlatformPass(jti=str(claims["jti"])[:64], expires_at=platform_pass.expires(claims)))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This sign-in link was already used. Sign in again from the start.") from None

    email = str(claims["email"]).strip().lower()
    # Their role as the Platform keeps it (app/platform_roles.py), kept here before it is matched by name.
    if isinstance(claims.get("roleDef"), dict):
        platform_roles.keep(db, claims["roleDef"])
    wanted = ADMINISTRATOR if claims.get("appAdmin") else (claims.get("role") or "")
    role = db.scalar(select(Role).where(func.lower(Role.name) == wanted.lower())) if wanted else None
    user = db.scalar(select(User).where(User.platform_identity_id == claims["sub"]))
    if user is None:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        # Linked to an account that's gone (it was deleted and added again): the Platform vouches
        # for this email, which is one person at one company there, so it's re-linked below
        # rather than refused (decided 2026-10-27, when ai4 was locked out that way).
    if user is None:
        if role is None:
            what = f" ({wanted})" if wanted else ""
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your role here{what} isn't set up in this application. Ask your administrator to set your role on the platform.")
        user = User(
            email=email,
            full_name=str(claims.get("name") or email)[:120],
            # never used: they sign in with their Bishnoi One account
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role_id=role.id,
            platform_identity_id=claims["sub"],
            # the session opened below starts at the same moment, so it counts
            password_changed_at=now,
        )
        db.add(user)
        db.flush()
        audit(db, email, "user.created", target=email, target_type="user", target_id=user.id, fields=["from the platform"])
    else:
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account in this application is switched off. Ask your administrator.")
        changed = []
        if user.platform_identity_id != claims["sub"]:
            user.platform_identity_id = claims["sub"]
            changed.append("platformIdentity")
        if claims.get("name") and user.full_name != claims["name"]:
            user.full_name = str(claims["name"])[:120]
            changed.append("fullName")
        if user.email != email and db.scalar(select(User.id).where(func.lower(User.email) == email)) is None:
            user.email = email
            changed.append("email")
        # the platform decides the role; one this app doesn't have leaves theirs as it is
        if role is not None and user.role_id != role.id:
            user.role_id = role.id
            changed.append("role")
        if changed:
            audit(db, email, "user.updated", target=email, target_type="user", target_id=user.id, fields=changed)

    token = f"{slug}.{new_token()}"
    expires_in = settings.session_hours * 3600
    db.add(SignInSession(token_hash=token_hash(token), user_id=user.id, created_at=now, expires_at=now + timedelta(seconds=expires_in)))
    audit(db, user, "auth.signed_in", target=user.email, target_type="user", target_id=user.id, fields=["with a Bishnoi One account"])
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(record: CurrentSession, db: DB) -> Response:
    record.revoked_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser, settings: SettingsDep) -> dict:
    return me_out(user, settings)


@router.get("/demo-accounts")
def demo_accounts(request: Request) -> dict:
    """The demo accounts that exist at the company, for the sign-in page. Development only."""
    if request.app.state.settings.is_production:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    emails = [d.email for d in DEMO_ACCOUNTS]
    with open_company(request, company_of(request)).sessions() as db:
        active = set(db.scalars(select(User.email).where(User.email.in_(emails), User.is_active)))
    return {
        "password": DEMO_PASSWORD,
        "items": [{"group": d.group, "email": d.email, "who": d.name, "role": d.role} for d in DEMO_ACCOUNTS if d.email in active],
    }


@router.post("/switch-org")
@router.post("/leave")
def not_here() -> None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "This app has one company and its own accounts, so there's nothing to switch to.")


@router.get("/company")
def company_status(request: Request) -> dict:
    """For the sign-in page: whether the company it names (X-Bishnoi-Company) may
    use Inventory, and why not; or, signed in, the company of the session."""
    slug = company_of(request)
    found = company_standing(request.app.state.settings, slug)
    return {"ok": found.ok, "message": found.message, "name": found.name, "slug": slug}


# ---- View as (app/platform_roles.py says how) --------------------------------------------------


@router.get("/view-as")
def view_as_people(user: CurrentUser, db: DB) -> dict:
    """Whom an administrator may view as: everyone switched on, by role, most permissions first."""
    if not platform_roles.may_view_as(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can view as someone else.")
    return {"roles": platform_roles.people_by_role(db)}


@router.post("/view-as")
def start_view_as(body: dict, user: CurrentUser, db: DB) -> dict:
    """Starting to view as someone: checked, and kept in the activity log (who, as whom)."""
    if not platform_roles.may_view_as(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can view as someone else.")
    other = db.get(User, str(body.get("userId") or ""))
    if other is None or not other.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That person isn't here, or is switched off.")
    audit(db, user, "auth.viewed_as", target=other.email, target_type="user", target_id=other.id)
    db.commit()
    return {"id": other.id, "fullName": other.full_name, "role": other.role.name}
