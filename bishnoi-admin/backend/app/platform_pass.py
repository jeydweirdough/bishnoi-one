"""Signing in with a Bishnoi One account: checking the pass the platform gives.

The platform (bishnoi-platform, app/passes.py) signs a two-minute pass saying who
the person is, their company, this application, and their role here. This
application holds only the platform's public key (fetched from the platform, below), so
it can check a pass but never make one. A pass is taken once: its id is kept until
it would have expired anyway.

This file is the same in every Bishnoi One application; only the app's key differs.
"""

import base64
import json
import time
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ISSUER = "bishnoi-platform"
# Passes the platform signed before the rename to Bishnoi One, until it's redeployed.
ISSUERS = {ISSUER, "nabhi-platform"}
LEEWAY = 30  # seconds of clock difference allowed between the platform and this PC


class PassRefused(Exception):
    """Why a pass can't be taken, in words for the person."""


def _b64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def check(token: str, public_key: str | None, app_key: str, now: float | None = None) -> dict:
    """The pass's claims, once its signature, issuer, application and time are right."""
    if not public_key:
        raise PassRefused("Signing in with a Bishnoi One account isn't set up for this application.")
    now = time.time() if now is None else now
    try:
        head_b64, body_b64, sig_b64 = token.split(".")
        head = json.loads(_b64(head_b64))
        body = json.loads(_b64(body_b64))
        if head.get("alg") != "EdDSA":
            raise ValueError("alg")
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(_b64(sig_b64), f"{head_b64}.{body_b64}".encode())
    except (ValueError, InvalidSignature, json.JSONDecodeError, TypeError):
        raise PassRefused("This sign-in link isn't valid. Sign in again from the start.") from None
    if body.get("iss") not in ISSUERS or body.get("aud") != app_key:
        raise PassRefused("This sign-in link is for another application. Sign in again from the start.")
    if not isinstance(body.get("exp"), int) or body["exp"] + LEEWAY < now:
        raise PassRefused("This sign-in link has expired. Sign in again from the start.")
    if not body.get("sub") or not body.get("email") or not body.get("jti"):
        raise PassRefused("This sign-in link isn't valid. Sign in again from the start.")
    return body


def expires(claims: dict) -> datetime:
    return datetime.fromtimestamp(claims["exp"], UTC) + timedelta(seconds=LEEWAY)


# --- the platform's public key ---------------------------------------------------------------
# Not a secret, so it isn't copied onto every server: with PLATFORM_API_URL set,
# it's fetched from the platform (GET /pass/key) the first time it's needed,
# and again when a pass doesn't verify with it (the platform's key was
# replaced), at most once a minute. PLATFORM_PUBLIC_KEY, when set, is used instead.

_fetched: dict[str, tuple[str, float]] = {}  # by the platform's address: (its key, when it was fetched)
AGAIN = 60


def public_key(settings, again: bool = False) -> str | None:
    """The key passes are checked with: PLATFORM_PUBLIC_KEY, or the platform's own."""
    given = getattr(settings, "platform_public_key", None)
    if given:
        return given
    url = getattr(settings, "platform_api_url", None)
    if not url:
        return None
    known = _fetched.get(url)
    if known and not (again and time.time() - known[1] > AGAIN):
        return known[0]
    import httpx  # here: only an application that asks the platform needs it

    try:
        r = httpx.get(f"{url.rstrip('/')}/pass/key", timeout=5)
        key = r.json().get("publicKey") if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError, AttributeError):
        key = None
    if key:
        _fetched[url] = (key, time.time())
        return key
    return known[0] if known else None


def check_for(settings, token: str, app_key: str) -> dict:
    """check(), with the platform's key; once more with a fresh one when it doesn't verify."""
    key = public_key(settings)
    try:
        return check(token, key, app_key)
    except PassRefused:
        fresh = public_key(settings, again=True)
        if fresh and fresh != key:
            return check(token, fresh, app_key)
        raise


def forget_key() -> None:
    """Fetches the key again next time (tests)."""
    _fetched.clear()
