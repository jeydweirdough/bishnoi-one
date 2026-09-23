"""Signing in and out of this app.

Its own accounts, in its own database: an account here signs in to this app
only. Accounts are made with the users tool (see README.md).
"""

import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import func, select

from app.deps import DB, CurrentSession, CurrentUser, SettingsDep
from app.identity import me_out
from app.models import SignInSession, User
from app.security import DUMMY_HASH, MAX_PASSWORD, new_token, token_hash, verify_password

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
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG)
    attempts.clear(email)

    token = new_token()
    now = datetime.now(UTC)
    expires_in = settings.session_hours * 3600
    db.add(SignInSession(token_hash=token_hash(token), user_id=user.id, created_at=now, expires_at=now + timedelta(seconds=expires_in)))
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


@router.post("/switch-org")
@router.post("/view-as")
@router.post("/leave")
def not_here() -> None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "This app has one company and its own accounts, so there's nothing to switch to.")
