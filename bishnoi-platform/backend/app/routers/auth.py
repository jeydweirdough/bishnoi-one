"""Signing in and out of this app.

Its own accounts, in its own database: an account here signs in to this app
only. Accounts are made with the users tool (see README.md). How long a
sign-in lasts and how many wrong passwords it takes are Settings > Security.

Every sign-in, every wrong password and every sign-out is a security event in
the audit log, with the address it came from.
"""

import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import func, select

from app import platform_settings
from app.api import Api
from app.audit import audit
from app.demo import DEMO_ACCOUNTS, DEMO_PASSWORD
from app.deps import DB, Address, CurrentSession, CurrentUser, SettingsDep
from app.identity import me_out
from app.models import SignInSession, User
from app.security import DUMMY_HASH, MAX_PASSWORD, check_password_rules, hash_password, new_token, token_hash, verify_password

router = APIRouter(prefix="/auth", tags=["sign-in"])

WRONG = "That email and password don't match an account here."


class LoginIn(Api):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


class PasswordIn(Api):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD)
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD)


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
def login(body: LoginIn, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    rules = platform_settings.security(db, settings)
    email = body.email.lower()
    window = rules.lockout_minutes * 60
    wait = attempts.wait_seconds(email, rules.login_attempts, window)
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
        reason = "no such account" if user is None else "switched off" if ok else "wrong password"
        audit(db, email, "auth.sign_in_failed", category="security", target=reason, target_type="staff",
              target_id=user.id if user else None, address=address)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG)
    attempts.clear(email)

    token = new_token()
    now = datetime.now(UTC)
    expires_in = rules.session_hours * 3600
    db.add(SignInSession(token_hash=token_hash(token), user_id=user.id, created_at=now,
                         expires_at=now + timedelta(seconds=expires_in), address=address))
    user.last_sign_in_at = now
    audit(db, user, "auth.signed_in", category="security", target=user.email, target_type="staff", target_id=user.id, address=address)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(record: CurrentSession, db: DB, address: Address) -> Response:
    record.revoked_at = datetime.now(UTC)
    user = db.get(User, record.user_id)
    if user is not None:
        audit(db, user, "auth.signed_out", category="security", target=user.email, target_type="staff", target_id=user.id, address=address)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser, settings: SettingsDep) -> dict:
    return me_out(user, settings)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordIn, user: CurrentUser, record: CurrentSession, db: DB, address: Address) -> Response:
    """Changes your own password. Every other session of yours ends; this one carries on."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [{"type": "value_error", "loc": ["body", "currentPassword"], "msg": "That isn't your current password."}],
        )
    problem = check_password_rules(body.new_password)
    if problem:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "newPassword"], "msg": problem}]
        )
    now = datetime.now(UTC)
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = now
    # This session was made before the change; move it past it so it survives.
    record.created_at = now
    audit(db, user, "auth.password_changed", category="security", target=user.email, target_type="staff", target_id=user.id, address=address)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    raise HTTPException(status.HTTP_404_NOT_FOUND, "The platform sits above every company, so there's nothing to switch to.")
