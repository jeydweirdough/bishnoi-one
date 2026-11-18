"""One sign-in for the whole system (stage M3, second part, 2026-11-18).

The one app sends every module the Bishnoi One account's own session token (its `bishnoi_account`
cookie) instead of a session of the module's own. A module of the one backend doesn't know that
token, so it asks the Platform, in-process, who it is:

    GET <PLATFORM_API_URL>/internal/session?app=<the module's Platform key>
    Authorization: Bearer <the account token>

The Platform answers only a module of the one backend (the in-process mark, modules/inprocess.py:
a request from outside never carries it) and only about the module asking. It answers what a pass
for that module would say (who, the company, the role there with its permissions and scope, the
place on the org chart, company administrator) and refuses exactly as it refuses a pass: the
sign-in ended or revoked, the account or company suspended, the module not the company's or not
given to the person, a handed-over password still to change, two-step sign-in still owed.

The module then finds or adds the person the way its pass sign-in (/auth/platform) does, and keeps
a session row of its own for the token (hashed with ACCOUNT_PREFIX, so it never matches a token of
the module's own), so its records, "last signed in" and sign-out work as before.

An answer is kept for TTL seconds per module and token, so a page doesn't ask the Platform on every
request. Signing out, or moving to another company, drops it at once (the Platform calls forget());
anything else the Platform refuses (a suspension, a role taken away) is seen within TTL. A refusal
is never kept.

Outside the one backend (a module's own tests, a module run alone) none of this applies: enabled()
is False and the module takes only its own sessions and passes, as before.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from typing import Any

from modules import inprocess

PATH = "/internal/session"
# Seconds an answer is kept (2026-11-19: 60 -> 15). Sign-out forgets it at once in this process; with several
# worker processes the others keep it until it runs out, so it's short. ONE_SESSION_CACHE_SECONDS changes it.
try:
    TTL = max(0, int(os.environ.get("ONE_SESSION_CACHE_SECONDS", "15")))
except ValueError:
    TTL = 15
ACCOUNT_PREFIX = "account:"  # a module's session row for an account token is kept under hash(ACCOUNT_PREFIX + token)
MOST = 5000  # answers kept at most; the expired ones go first

_lock = threading.Lock()
_kept: dict[tuple[str, str], tuple[float, dict]] = {}  # (module key, hash of the token) -> (until, answer)


class Refused(Exception):
    """The Platform won't vouch for this token here: `status` (401, 403 or 503) and words for the person."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def hashed(token: str) -> str:
    """The token as every module and the Platform keep it (security.token_hash)."""
    return hashlib.sha256(token.encode()).hexdigest()


def row_hash(token: str) -> str:
    """What a module's own session row for an account token is kept under."""
    return hashed(ACCOUNT_PREFIX + token)


def _platform(settings: Any) -> str | None:
    url = getattr(settings, "platform_api_url", None)
    return url.rstrip("/") if url else None


def enabled(settings: Any) -> bool:
    """The module runs in the one backend with the Platform beside it: it takes the account's token."""
    url = _platform(settings)
    return bool(url) and inprocess.serves(f"{url}{PATH}")


def who(settings: Any, app_key: str, token: str) -> tuple[dict, bool]:
    """What the Platform says about this account token for this module, and whether it was just asked
    (False: kept from less than TTL seconds ago). Raises Refused."""
    key = (app_key, hashed(token))
    now = time.monotonic()
    with _lock:
        kept = _kept.get(key)
    if kept is not None and kept[0] > now:
        return kept[1], False
    url = _platform(settings)
    if not url:
        raise Refused(503, "Bishnoi One can't be asked just now. Try again in a minute.")
    try:
        r = inprocess.get(app_key, f"{url}{PATH}", params={"app": app_key}, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    except Exception:  # noqa: BLE001 (never in-process; only an address of its own could fail this way)
        raise Refused(503, "Bishnoi One can't be asked just now. Try again in a minute.") from None
    if r.status_code == 200:
        answer = r.json()
        with _lock:
            if len(_kept) >= MOST:
                for k in [k for k, (until, _) in _kept.items() if until <= now] or list(_kept)[: MOST // 10]:
                    _kept.pop(k, None)
            _kept[key] = (now + TTL, answer)
        return answer, True
    with _lock:
        _kept.pop(key, None)
    try:
        detail = r.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if r.status_code in (401, 403):
        default = "Your Bishnoi One sign-in has ended. Please sign in again." if r.status_code == 401 else "Your Bishnoi One account doesn't include this part."
        raise Refused(r.status_code, detail if isinstance(detail, str) and detail else default)
    raise Refused(503, "Bishnoi One can't be asked just now. Try again in a minute.")


def forget(token_hash: str) -> None:
    """Every module's answer for this token (its hash, as the Platform keeps it) dropped: it asks again."""
    with _lock:
        for k in [k for k in _kept if k[1] == token_hash]:
            _kept.pop(k, None)


def forget_all() -> None:
    """Every answer dropped (a password changed, tests)."""
    with _lock:
        _kept.clear()


# --- what each module's deps.py uses -------------------------------------------------------------

SIGNED_OUT = "Your session has ended. Please sign in again."


def answer(request: Any, app_key: str, token: str) -> tuple[dict, bool] | None:
    """who(), once per request (CRM and Inventory ask it for the company first, then for the session);
    None when the module isn't in the one backend. A refusal is an HTTPException in the Platform's words."""
    from fastapi import HTTPException

    settings = request.app.state.settings
    if not enabled(settings):
        return None
    memo = getattr(request.state, "one_session", None)
    if memo is not None and memo[0] == token:
        return memo[1], memo[2]
    try:
        found, fresh = who(settings, app_key, token)
    except Refused as e:
        raise HTTPException(e.status, e.message, headers={"Retry-After": "30"} if e.status == 503 else None) from None
    request.state.one_session = (token, found, fresh)
    return found, fresh


def _moment(value: Any, default):
    from datetime import UTC, datetime

    try:
        moment = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return default
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def session_row(db: Any, model: Any, token: str, found: dict, fresh: bool, provision: Any, opened: Any) -> Any:
    """The module's own session row for an account token: made the first time (`provision(now)` finds or
    adds the person exactly as the module's pass sign-in does, `opened(user)` notes the sign-in), and the
    person brought in step again whenever the Platform was just asked. A row signed out of here stays out."""
    from datetime import UTC, datetime, timedelta

    from fastapi import HTTPException
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    key = row_hash(token)
    for attempt in range(2):
        row = db.scalar(select(model).where(model.token_hash == key))
        if row is not None and row.revoked_at is not None:
            raise HTTPException(401, SIGNED_OUT)
        if row is not None and not fresh:
            return row
        now = datetime.now(UTC)
        try:
            user = provision(now)
        except HTTPException:
            db.rollback()
            raise
        signed_in_at = _moment(found.get("signedInAt"), now)
        expires_at = _moment(found.get("expiresAt"), now + timedelta(hours=12))
        if row is None:
            row = model(token_hash=key, user_id=user.id, created_at=signed_in_at, expires_at=expires_at)
            db.add(row)
            opened(user)
        else:
            row.user_id, row.created_at, row.expires_at = user.id, signed_in_at, expires_at
        try:
            db.commit()
            return row
        except IntegrityError:
            # Two first requests at once: the other one made the row (or the person); take theirs.
            db.rollback()
            fresh = False
    raise HTTPException(503, "Signing in didn't finish just now. Try again in a moment.")
