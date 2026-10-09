"""Signing in and out of this app.

Its own accounts, in its own database: an account here signs in to this app
only. Accounts are made with the users tool (see README.md).
"""

import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.audit import audit
from app.demo import DEMO_ACCOUNTS, DEMO_PASSWORD
from app.deps import DB, CurrentSession, CurrentUser, SettingsDep
from app.identity import me_out
from app import platform_pass
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


@router.post("/login")
def login(body: LoginIn, db: DB, settings: SettingsDep, response: Response) -> dict:
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
        audit(db, email, "auth.sign_in_failed", target=email, target_type="user", target_id=user.id if user else None)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG)
    attempts.clear(email)

    token = new_token()
    now = datetime.now(UTC)
    expires_in = settings.session_hours * 3600
    db.add(SignInSession(token_hash=token_hash(token), user_id=user.id, created_at=now, expires_at=now + timedelta(seconds=expires_in)))
    audit(db, user, "auth.signed_in", target=user.email, target_type="user", target_id=user.id)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in}


# --- signing in with a Bishnoi One account (the platform) -----------------------------------

APP_KEY = "pharmacy"  # this application's key on the platform


class PlatformIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    token: str = Field(alias="pass", min_length=20, max_length=8000)


@router.post("/platform")
def sign_in_with_platform(body: PlatformIn, db: DB, settings: SettingsDep, response: Response) -> dict:
    """Takes a pass from the platform (app/platform_pass.py) and opens a session
    here, as /auth/login does. The person is found by their Bishnoi One account, or
    by email the first time; someone new is added with their role from the
    platform. The platform decides who may open this application; this only
    refuses someone switched off here."""
    try:
        claims = platform_pass.check_for(settings, body.token, APP_KEY)
    except platform_pass.PassRefused as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from None
    now = datetime.now(UTC)
    db.execute(delete(PlatformPass).where(PlatformPass.expires_at < now))
    db.add(PlatformPass(jti=str(claims["jti"])[:64], expires_at=platform_pass.expires(claims)))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This sign-in link was already used. Sign in again from the start.") from None

    email = str(claims["email"]).strip().lower()
    wanted = ADMINISTRATOR if claims.get("appAdmin") else (claims.get("role") or "")
    role = db.scalar(select(Role).where(func.lower(Role.name) == wanted.lower())) if wanted else None
    user = db.scalar(select(User).where(User.platform_identity_id == claims["sub"]))
    if user is None:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is not None and user.platform_identity_id not in (None, claims["sub"]):
            raise HTTPException(status.HTTP_409_CONFLICT, "This email is already linked to another Bishnoi One account here. Ask your administrator.")
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

    token = new_token()
    expires_in = settings.session_hours * 3600
    db.add(SignInSession(token_hash=token_hash(token), user_id=user.id, created_at=now, expires_at=now + timedelta(seconds=expires_in)))
    audit(db, user, "auth.signed_in", target=user.email, target_type="user", target_id=user.id, fields=["with a Bishnoi One account"])
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(record: CurrentSession, user: CurrentUser, db: DB) -> Response:
    record.revoked_at = datetime.now(UTC)
    audit(db, user, "auth.signed_out", target=user.email, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser, settings: SettingsDep) -> dict:
    return me_out(user, settings)


@router.get("/demo-accounts")
def demo_accounts(db: DB, settings: SettingsDep) -> dict:
    """The demo accounts that exist here, for the sign-in page. Development only."""
    if settings.is_production:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    emails = [d.email for d in DEMO_ACCOUNTS]
    active = set(db.scalars(select(User.email).where(User.email.in_(emails), User.is_active)))
    return {
        "password": DEMO_PASSWORD,
        "items": [{"group": d.group, "email": d.email, "who": d.name, "role": d.role} for d in DEMO_ACCOUNTS if d.email in active],
    }


@router.post("/switch-org")
@router.post("/view-as")
@router.post("/leave")
def not_here() -> None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "This app has one company and its own accounts, so there's nothing to switch to.")
