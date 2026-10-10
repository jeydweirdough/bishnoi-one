"""What the CRM is linked to, from Bishnoi One Platform (its Connections page).

With PLATFORM_APP_KEY set (made on the platform's Connections page), the CRM
asks the platform GET /connect/links and is told:

- for each application it uses (Inventory, Finance, Pharmacy): where its API
  is, where its screens are, and the key to call it with;
- for each application that uses it (Finance): the key that caller sends;
- where its own screens are (for sign-in with Gmail, Outlook and Zoho Mail);
- the key it encrypts its own secrets with (app/connections.py).

Those are laid over the settings on every request (app/deps.py), so the code
that calls Inventory reads settings.inventory_api_url as before, whichever
way it was set. While connected, the platform's answer is the whole truth: a
link switched off there is off here, whatever .env says. Without a connect
key, .env is used as before.

The answer is kept for as long as the platform says (5 minutes). While the
platform can't be reached, the last answer stands for up to a day, so a short
outage changes nothing; after that, the links are dropped until it answers.
"""

import logging
import threading
import time

import httpx
from pydantic import SecretStr

from app.config import Settings

log = logging.getLogger(__name__)

GRACE = 24 * 3600  # how long the last answer stands while the platform can't be reached
RETRY = 30  # seconds between tries while it can't

# Each application this one uses: its key on the platform -> (API setting, key setting, screens setting).
USES: dict[str, tuple[str, str, str | None]] = {
    "inventory": ("inventory_api_url", "inventory_api_key", "inventory_app_url"),
    "finance": ("finance_api_url", "finance_api_key", None),
    "pharmacy": ("pharmacy_api_url", "pharmacy_api_key", None),
}
# Where this application's own screens are, when the platform knows.
OWN_APP_URL = "crm_app_url"

_lock = threading.Lock()
# By connect key: (the last answer, when it was had, when to ask again)
_known: dict[str, tuple[dict | None, float, float]] = {}

NOTHING = {"uses": {}, "usedBy": {}}


def _ask(settings: Settings, key: str) -> tuple[dict | None, float]:
    """(the platform's answer or None when it can't be had, seconds until asking again)."""
    try:
        r = httpx.get(f"{settings.platform_api_url.rstrip('/')}/connect/links", headers={"X-Bishnoi-App-Key": key}, timeout=5)
    except httpx.HTTPError as e:
        log.error("Links: can't reach the platform at %s (%s).", settings.platform_api_url, e.__class__.__name__)
        return None, RETRY
    if r.status_code == 401:
        # Replaced or disconnected on the platform: no links until a new key is set here.
        log.error("Links: the platform doesn't take PLATFORM_APP_KEY (it was replaced, or the CRM was disconnected). Make a new key on its Connections page.")
        from app.platform_connect import replaced

        replaced(settings)
        return dict(NOTHING), 60
    if r.status_code != 200:
        log.error("Links: the platform answered %s.", r.status_code)
        return None, RETRY
    try:
        body = r.json()
        found = {"uses": dict(body.get("uses") or {}), "usedBy": dict(body.get("usedBy") or {}), "appUrl": body.get("appUrl"), "dataKey": body.get("dataKey")}
        return found, float(body.get("askAgainIn") or 300)
    except ValueError:
        log.error("Links: the platform's answer wasn't readable.")
        return None, RETRY


def answer(settings: Settings) -> dict | None:
    """The platform's word on this application's links; None when not connected."""
    from app.platform_connect import connect_key  # here: it reads the settings module first

    key = connect_key(settings)
    if not key or not settings.platform_api_url:
        return None
    now = time.time()
    with _lock:
        last, had_at, next_at = _known.get(key, (None, 0.0, 0.0))
    if now < next_at:
        return last if last is not None and now - had_at < GRACE else (dict(NOTHING) if last is not None else None)
    found, wait = _ask(settings, key)
    with _lock:
        if found is not None:
            _known[key] = (found, now, now + wait)
            return found
        _known[key] = (last, had_at, now + wait)
    if last is not None and now - had_at < GRACE:
        return last
    return dict(NOTHING) if last is not None else None


def overrides(settings: Settings) -> dict:
    """What to lay over the settings: every link as the platform says, or nothing when not connected."""
    found = answer(settings)
    if found is None:
        return {}
    out: dict = {}
    for name, (url, key, screens) in USES.items():
        link = found["uses"].get(name)
        out[url] = link.get("apiUrl") if link else None
        out[key] = SecretStr(link["key"]) if link and link.get("key") else None
        if screens:
            out[screens] = link.get("appUrl") if link else None
    out["integration_keys"] = [SecretStr(f"{name}:{secret}") for name, secret in found["usedBy"].items()]
    if found.get("appUrl"):
        out[OWN_APP_URL] = found["appUrl"]
    return out


def effective(settings: Settings) -> Settings:
    """The settings with the platform's links laid over them."""
    over = overrides(settings)
    return settings.model_copy(update=over) if over else settings


def forget() -> None:
    """Asks the platform again next time (tests; a changed key)."""
    with _lock:
        _known.clear()
