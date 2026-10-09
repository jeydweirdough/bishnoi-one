"""Whether a company may use Inventory: registered on Bishnoi One Platform, active
there, and given Inventory.

A company is registered on the platform first; only then can it use Inventory.
For each company (its short name, the slug), Inventory asks the platform for a
signed company pass (GET /public/company-pass), which it checks with the
platform's public key (PLATFORM_PUBLIC_KEY), as it checks sign-in passes. No
secret is shared between the two.

The answer is kept for as long as the pass lasts (an hour). While the
platform can't be reached, the last good answer is used for up to a day,
so a short outage doesn't lock everyone out; after that Inventory refuses.

The platform not set up (no PLATFORM_API_URL): on this computer, the
companies in DEV_COMPANIES are allowed; in production, none is.
"""

import base64
import json
import logging
import threading
import time
from dataclasses import dataclass

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app import platform_pass
from app.config import Settings
from app.platform_pass import ISSUERS, LEEWAY, _b64

APP_KEY = "inventory"
GRACE = 24 * 3600  # how long a last good answer stands while the platform can't be reached


log = logging.getLogger(__name__)

# What a person is told when the server isn't set up or can't reach the
# platform: it's not theirs to fix, so the details go to the server's log.
UNAVAILABLE = "Signing in isn't available right now. Try again in a few minutes; if it keeps happening, tell your administrator."
UNREACHABLE = "Signing in isn't available right now. Try again in a moment."


def unavailable(detail: str, until: float = 0.0, message: str = UNAVAILABLE) -> "Standing":
    """A setup problem: logged for whoever runs the server, a plain line for the person."""
    log.error("Company check: %s", detail)
    return Standing(False, message, until=until)


@dataclass(frozen=True)
class Standing:
    ok: bool
    # Why not, for the person; or the company's name when ok.
    message: str
    company_id: str | None = None
    name: str | None = None
    until: float = 0.0  # when to ask the platform again


_lock = threading.Lock()
_last: dict[str, Standing] = {}  # by company
_good: dict[str, tuple[Standing, float]] = {}  # the last good answer, and when it was had


def _read(token: str, public_key: str, slug: str) -> dict:
    head_b64, body_b64, sig_b64 = token.split(".")
    head, body = json.loads(_b64(head_b64)), json.loads(_b64(body_b64))
    if head.get("alg") != "EdDSA":
        raise ValueError("alg")
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(_b64(sig_b64), f"{head_b64}.{body_b64}".encode())
    if body.get("iss") not in ISSUERS or body.get("aud") != APP_KEY or body.get("kind") != "company" or body.get("slug") != slug:
        raise ValueError("not this company's pass")
    if not isinstance(body.get("exp"), int) or body["exp"] + LEEWAY < time.time():
        raise ValueError("expired")
    return body


def _ask(settings: Settings, slug: str) -> Standing:
    """The platform's answer, checked."""
    if not settings.platform_api_url:
        return unavailable("PLATFORM_API_URL isn't set on the server.", until=time.time() + 60)
    try:
        r = httpx.get(f"{settings.platform_api_url.rstrip('/')}/public/company-pass", params={"app": APP_KEY, "company": slug}, timeout=10)
    except httpx.HTTPError:
        raise ConnectionError from None
    if r.status_code == 404:
        return Standing(False, f"The company \"{slug}\" isn't registered on Bishnoi One Platform yet. Ask your Bishnoi One administrator to register it.", until=time.time() + 300)
    if r.status_code != 200:
        raise ConnectionError
    try:
        token = r.json()["pass"]
        try:
            claims = _read(token, platform_pass.public_key(settings), slug)
        except (InvalidSignature, TypeError):
            # The platform's key may have been replaced: fetch it again, once.
            claims = _read(token, platform_pass.public_key(settings, again=True), slug)
    except (ValueError, KeyError, InvalidSignature, TypeError, json.JSONDecodeError):
        return unavailable(f"the Platform's pass for {slug!r} didn't verify: is PLATFORM_PUBLIC_KEY (if set) the Platform's current key?", until=time.time() + 300)
    name, company_id, until = claims.get("companyName") or slug, claims.get("company"), float(claims["exp"])
    if claims.get("status") != "active":
        return Standing(False, f"{name} is suspended on Bishnoi One Platform, so Inventory can't be used. Ask your Bishnoi One administrator.", company_id, name, until)
    if not claims.get("granted"):
        return Standing(False, f"{name} isn't set up to use Inventory on Bishnoi One Platform yet. Ask your Bishnoi One administrator to give it Inventory.", company_id, name, until)
    return Standing(True, name, company_id, name, until)


def standing(settings: Settings, slug: str) -> Standing:
    """Whether this company may use Inventory now."""
    if not settings.platform_api_url:
        if settings.is_production:
            return unavailable("PLATFORM_API_URL isn't set on the server (ENVIRONMENT is production, so no company is allowed without it).")
        if slug in {c.strip().lower() for c in settings.dev_companies}:
            return Standing(True, slug, None, slug, until=float("inf"))
        return Standing(False, f"There's no company \"{slug}\" on this computer. Try one of: {', '.join(settings.dev_companies)}.")
    now = time.time()
    with _lock:
        known = _last.get(slug)
        if known and known.until > now:
            return known
    try:
        found = _ask(settings, slug)
    except ConnectionError:
        good = _good.get(slug)
        if good and now - good[1] < GRACE:
            return good[0]
        found = unavailable(f"can't reach the Platform at {settings.platform_api_url}.", until=now + 30, message=UNREACHABLE)
    with _lock:
        _last[slug] = found
        if found.ok:
            _good[slug] = (found, now)
    return found


def forget() -> None:
    """Asks the platform again next time (tests; a changed setting)."""
    with _lock:
        _last.clear()
        _good.clear()
