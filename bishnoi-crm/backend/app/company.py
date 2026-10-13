"""Whether a company may use the CRM: registered on Bishnoi One Platform, active
there, and given the CRM.

A company is registered on the platform first; only then can it use the CRM.
For each company (its short name, the slug), the CRM holds a signed company
pass from the platform, which it checks with the platform's public key
(PLATFORM_PUBLIC_KEY), as it checks sign-in passes. No secret is shared.

The pass lasts 30 days and is kept in the CRM's own database (the table the
connect key is in, app/platform_connect.py), so a restart costs nothing and
nobody waits for the platform:
- a pass under an hour old is used as it is;
- an older one is still used, and a fresh one fetched in the background;
- with none (a company never seen here, or its pass run out) the platform is
  asked there and then.
While the platform can't be reached, the kept pass stands until it runs out.

The platform also sends a fresh pass the moment a company changes there
(suspended, paused, given or refused the CRM, deleted): POST
/platform/company, below. Only a pass signed by the platform, for the CRM,
newer than the one kept, is taken; anything else is answered as if the
address didn't exist.

The platform not set up (no PLATFORM_API_URL): on this computer, the
companies in DEV_COMPANIES are allowed; in production, none is.
"""

import base64
import json
import logging
import threading
import time
from dataclasses import dataclass, replace

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Request, Response

from app import platform_pass
from app.config import Settings
from app.platform_pass import ISSUERS, LEEWAY, _b64

APP_KEY = "crm"
WORD = "the CRM"  # how this application is named in what people read
REFRESH = 3600  # a kept pass older than this is renewed, in the background
RETRY = 30  # seconds between tries while the platform can't be reached


log = logging.getLogger(__name__)

# What a person is told when the server isn't set up or can't reach the
# platform: it's not theirs to fix, so the details go to the server's log.
UNAVAILABLE = "Signing in isn't available right now. Try again in a few minutes; if it keeps happening, tell your administrator."
UNREACHABLE = "Signing in isn't available right now. Try again in a moment."


def unavailable(detail: str, until: float = 0.0, message: str = UNAVAILABLE) -> "Standing":
    """A setup problem: logged for whoever runs the server, a plain line for the person."""
    log.error("Company check: %s", detail)
    return Standing(False, message, until=until, outage=True)


@dataclass(frozen=True)
class Standing:
    ok: bool
    # Why not, for the person; or the company's name when ok.
    message: str
    company_id: str | None = None
    name: str | None = None
    until: float = 0.0  # when to ask the platform again
    # Not a no: the platform couldn't be asked (out of reach, or the server not
    # set up to ask it). Answered as "not available right now", not "not allowed".
    outage: bool = False
    expires: float = 0.0  # when the pass it came from runs out (0: none)
    issued: float = 0.0  # when the platform signed that pass


_lock = threading.Lock()
_last: dict[str, Standing] = {}  # by company: the answer in hand
_renewing: set[str] = set()  # companies being renewed in the background


def _read(token: str, public_key: str, slug: str | None = None) -> dict:
    """The pass's claims, once its signature, audience and dates are checked. Any doubt raises ValueError."""
    head_b64, body_b64, sig_b64 = token.split(".")
    head, body = json.loads(_b64(head_b64)), json.loads(_b64(body_b64))
    if head.get("alg") != "EdDSA":
        raise ValueError("alg")
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(_b64(sig_b64), f"{head_b64}.{body_b64}".encode())
    if body.get("iss") not in ISSUERS or body.get("aud") != APP_KEY or body.get("kind") != "company" or not body.get("slug"):
        raise ValueError("not a company pass for this application")
    if slug is not None and body.get("slug") != slug:
        raise ValueError("not this company's pass")
    if not isinstance(body.get("exp"), int) or body["exp"] + LEEWAY < time.time():
        raise ValueError("expired")
    return body


def _checked(settings: Settings, token: str, slug: str | None = None) -> dict:
    """_read with the platform's key, fetched again once if it may have been replaced."""
    try:
        return _read(token, platform_pass.public_key(settings), slug)
    except (InvalidSignature, TypeError):
        return _read(token, platform_pass.public_key(settings, again=True), slug)


def _standing_of(claims: dict, checked_at: float) -> Standing:
    """What a checked pass says, to be asked again an hour after it was had."""
    name, company_id = claims.get("companyName") or claims["slug"], claims.get("company")
    common = {"company_id": company_id, "name": name, "until": checked_at + REFRESH, "expires": float(claims["exp"]), "issued": float(claims.get("iat") or 0)}
    if claims.get("status") == "deleted":
        return Standing(False, f"The company \"{claims['slug']}\" isn't registered on Bishnoi One Platform any more. Ask your Bishnoi One administrator.", **common)
    if claims.get("status") == "paused":
        return Standing(False, f"{name}'s Bishnoi One access is paused until {claims.get('pausedUntil') or 'later'}. It comes back by itself then.", **common)
    if claims.get("status") != "active":
        return Standing(False, f"{name} is suspended on Bishnoi One Platform, so {WORD} can't be used. Ask your Bishnoi One administrator.", **common)
    if not claims.get("granted"):
        return Standing(False, f"{name} isn't set up to use {WORD} on Bishnoi One Platform yet. Ask your Bishnoi One administrator to give it {WORD}.", **common)
    return Standing(True, name, **common)


# --- kept in this application's own database -------------------------------------------------


def _kept_name(slug: str) -> str:
    return f"company_pass:{slug}"


def _load(settings: Settings, slug: str) -> Standing | None:
    """The pass kept for this company, checked again (it may have run out, or the key been replaced)."""
    from app import platform_connect

    raw = platform_connect.read_value(settings, _kept_name(slug))
    if not raw:
        return None
    try:
        kept = json.loads(raw)
        return _standing_of(_checked(settings, kept["pass"], slug), float(kept["at"]))
    except (ValueError, KeyError, TypeError, InvalidSignature, json.JSONDecodeError):
        log.warning("Company check: the pass kept for %r no longer checks out; asking the platform.", slug)
        return None


def _keep(settings: Settings, slug: str, token: str, at: float) -> None:
    from app import platform_connect

    try:
        platform_connect.write_value(settings, _kept_name(slug), json.dumps({"pass": token, "at": at}))
    except Exception:  # noqa: BLE001 (it's a speed-up: without it, the platform is asked again)
        log.exception("Company check: couldn't keep the pass for %r.", slug)


# --- asking the platform ---------------------------------------------------------------------


def _ask(settings: Settings, slug: str) -> Standing:
    """The platform's answer, checked, and kept when it's a pass."""
    try:
        r = httpx.get(f"{settings.platform_api_url.rstrip('/')}/public/company-pass", params={"app": APP_KEY, "company": slug}, timeout=10)
    except httpx.HTTPError:
        raise ConnectionError from None
    now = time.time()
    if r.status_code == 404:
        return Standing(False, f"The company \"{slug}\" isn't registered on Bishnoi One Platform yet. Ask your Bishnoi One administrator to register it.", until=now + 300)
    if r.status_code != 200:
        raise ConnectionError
    try:
        token = r.json()["pass"]
        claims = _checked(settings, token, slug)
    except (ValueError, KeyError, InvalidSignature, TypeError, json.JSONDecodeError):
        return unavailable(f"the Platform's pass for {slug!r} didn't verify: is PLATFORM_PUBLIC_KEY (if set) the Platform's current key?", until=now + 300)
    _keep(settings, slug, token, now)
    return _standing_of(claims, now)


def _usable(found: Standing | None, now: float) -> bool:
    """A pass's answer that hasn't run out: good to act on while a fresh one is fetched."""
    return found is not None and not found.outage and found.expires > now


def _remember(slug: str, found: Standing) -> Standing:
    with _lock:
        _last[slug] = found
    return found


def _renew_later(settings: Settings, slug: str) -> None:
    """Fetches a fresh pass without anyone waiting for it."""
    with _lock:
        if slug in _renewing:
            return
        _renewing.add(slug)

    def run() -> None:
        try:
            _remember(slug, _ask(settings, slug))
        except ConnectionError:
            with _lock:
                held = _last.get(slug)
                if held is not None:
                    # Out of reach: keep what's in hand, and try again shortly.
                    _last[slug] = replace(held, until=time.time() + RETRY)
        except Exception:  # noqa: BLE001
            log.exception("Company check: renewing %r failed.", slug)
        finally:
            with _lock:
                _renewing.discard(slug)

    threading.Thread(target=run, name=f"company-pass-{slug}", daemon=True).start()


def standing(settings: Settings, slug: str) -> Standing:
    """Whether this company may use the CRM now."""
    if not settings.platform_api_url:
        if settings.is_production:
            return unavailable("PLATFORM_API_URL isn't set on the server (ENVIRONMENT is production, so no company is allowed without it).")
        if slug in {c.strip().lower() for c in settings.dev_companies}:
            return Standing(True, slug, None, slug, until=float("inf"))
        return Standing(False, f"There's no company \"{slug}\" on this computer. Try one of: {', '.join(settings.dev_companies)}.")
    now = time.time()
    with _lock:
        known = _last.get(slug)
    if known is None:
        # Not in memory (a restart): the pass kept in the database, if any.
        loaded = _load(settings, slug)
        if loaded is not None:
            known = _remember(slug, loaded)
    if known is not None and known.until > now and (not known.expires or known.expires > now):
        return known
    if _usable(known, now):
        # Over an hour old but not run out: use it, and fetch a fresh one meanwhile.
        _renew_later(settings, slug)
        return known
    try:
        found = _ask(settings, slug)
    except ConnectionError:
        found = unavailable(f"can't reach the Platform at {settings.platform_api_url}.", until=now + RETRY, message=UNREACHABLE)
    return _remember(slug, found)


# --- the platform telling us a company changed ------------------------------------------------

router = APIRouter()
_NOWHERE = {"detail": "Not Found"}  # what any unknown address answers


def take_pass(settings: Settings, token: str) -> bool:
    """A pass the platform sent: kept if it's genuine, for this application, and
    newer than the one kept. False otherwise, saying nothing about why."""
    try:
        claims = _checked(settings, token)
    except (ValueError, KeyError, TypeError, InvalidSignature, json.JSONDecodeError):
        return False
    slug = claims["slug"]
    issued = float(claims.get("iat") or 0)
    with _lock:
        held = _last.get(slug)
    held = held or _load(settings, slug)
    if held is not None and held.issued and issued <= held.issued:
        return False  # an older pass sent again: what's kept is newer
    now = time.time()
    _keep(settings, slug, token, now)
    _remember(slug, _standing_of(claims, now))
    log.info("Company check: the platform sent a fresh pass for %r (%s).", slug, claims.get("status"))
    return True


@router.api_route("/platform/company", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"], include_in_schema=False)
async def company_changed(request: Request) -> Response:
    """Hidden: not in the API's map, and anything but the platform's signed pass
    gets exactly what an address that doesn't exist gets."""
    from fastapi.responses import JSONResponse

    settings: Settings = request.app.state.settings
    nowhere = JSONResponse(_NOWHERE, status_code=404)
    if request.method != "POST" or not settings.platform_api_url:
        return nowhere
    try:
        raw = await request.body()
        token = json.loads(raw)["pass"] if len(raw) <= 4000 else None
    except (ValueError, KeyError, TypeError):
        return nowhere
    if not isinstance(token, str) or token.count(".") != 2:
        return nowhere
    import anyio

    taken = await anyio.to_thread.run_sync(take_pass, settings, token)
    return Response(status_code=204) if taken else nowhere


def forget(kept: bool = False, settings: Settings | None = None) -> None:
    """Asks the platform again next time (tests; a changed setting). With kept,
    the passes in the database go too."""
    with _lock:
        slugs = list(_last)
        _last.clear()
        _renewing.clear()
    if kept and settings is not None:
        from app import platform_connect

        for slug in slugs:
            platform_connect.write_value(settings, _kept_name(slug), None)
