"""Outside services the CRM uses (Zoho Books, the email providers), and the key
it keeps its own secrets with.

The services are connected on Bishnoi One Platform, per company (Companies →
the company → Connections): nothing about them is kept on the CRM's server.
The CRM asks the platform GET /connect/services?company=<slug> with its connect
key (PLATFORM_APP_KEY), and is given each service that's switched on and filled
in, with its details. The answer is kept for as long as the platform says (5
minutes); while it can't be reached, the last answer stands for up to a day.

The CRM's own secrets (each person's mailbox sign-in, its order links) are
encrypted with the key the platform gives it with its links (dataKey,
app/platform_links.py): the same key through new connect keys. On this
computer, with no platform connected, a key of its own is kept in .data/.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import DATA_DIR, Settings

log = logging.getLogger(__name__)

GRACE = 24 * 3600  # how long the last answer stands while the platform can't be reached
RETRY = 30  # seconds between tries while it can't


@dataclass(frozen=True)
class Service:
    key: str
    name: str
    purpose: str


SERVICES: tuple[Service, ...] = (
    Service("zoho_books", "Zoho Books", "Invoices under each customer's name, for the monthly rebate, and registering the rebate back in Zoho."),
    Service("gmail", "Gmail (Google Workspace)", "Each person sends from their own Gmail address, and every email sent is kept on the customer."),
    Service("outlook", "Outlook (Microsoft 365)", "Each person sends from their own Outlook address, and every email sent is kept on the customer."),
    Service("zoho_mail", "Zoho Mail", "Each person sends from their own Zoho Mail address, and every email sent is kept on the customer."),
)
BY_KEY = {s.key: s for s in SERVICES}
MAIL_PROVIDERS = ("gmail", "outlook", "zoho_mail")


# --- the company's services, from the platform ---

_lock = threading.Lock()
# By company: (the last answer, when it was had, when to ask again)
_known: dict[str, tuple[dict | None, float, float]] = {}


def connected(settings: Settings) -> bool:
    """Whether the CRM can ask the platform at all."""
    return bool(settings.platform_app_key and settings.platform_api_url)


def _ask(settings: Settings, company: str) -> tuple[dict | None, float]:
    """(the company's services, or None when they can't be had; seconds until asking again)."""
    try:
        r = httpx.get(
            f"{settings.platform_api_url.rstrip('/')}/connect/services",
            params={"company": company},
            headers={"X-Bishnoi-App-Key": settings.platform_app_key.get_secret_value()},
            timeout=5,
        )
    except httpx.HTTPError as e:
        log.error("Services: can't reach the platform at %s (%s).", settings.platform_api_url, e.__class__.__name__)
        return None, RETRY
    if r.status_code == 401:
        log.error("Services: the platform doesn't take PLATFORM_APP_KEY. Make a new key on its Connections page.")
        return {}, 60
    if r.status_code != 200:
        log.error("Services: the platform answered %s.", r.status_code)
        return None, RETRY
    try:
        body = r.json()
        return {k: dict(v) for k, v in (body.get("services") or {}).items()}, float(body.get("askAgainIn") or 300)
    except (ValueError, AttributeError, TypeError):
        log.error("Services: the platform's answer wasn't readable.")
        return None, RETRY


def services(settings: Settings, company: str | None = None) -> dict[str, dict]:
    """The company's services that are on and filled in, by key, with their details."""
    company = company or settings.company
    if not company or not connected(settings):
        return {}
    now = time.time()
    with _lock:
        last, had_at, next_at = _known.get(company, (None, 0.0, 0.0))
    if now < next_at:
        return last if last is not None and now - had_at < GRACE else {}
    found, wait = _ask(settings, company)
    with _lock:
        if found is not None:
            _known[company] = (found, now, now + wait)
            return found
        _known[company] = (last, had_at, now + wait)
    return last if last is not None and now - had_at < GRACE else {}


def service(settings: Settings, key: str, company: str | None = None) -> dict | None:
    """One service's details, or None when it isn't on for the company."""
    return services(settings, company).get(key)


def forget() -> None:
    """Asks the platform again next time (tests; a changed connection)."""
    with _lock:
        _known.clear()


# --- the CRM's own secrets ---


class NoKey(Exception):
    """There's no key to encrypt with: online, the CRM isn't connected to the platform yet."""


def _local_key() -> Fernet | None:
    path: Path = DATA_DIR / "connections.key"
    return Fernet(path.read_bytes().strip()) if path.exists() else None


def _fernet(settings: Settings) -> MultiFernet:
    """Encrypts with the platform's data key (on this computer without one, a
    key of its own in .data/); reads what either of them encrypted."""
    from app.platform_links import answer  # here: app.platform_links reads the settings module first

    keys: list[Fernet] = []
    given = (answer(settings) or {}).get("dataKey")
    if given:
        try:
            keys.append(Fernet(given.encode()))
        except ValueError:
            log.error("Secrets: the platform's data key isn't a Fernet key.")
    local = _local_key()
    if not keys and local is None and not settings.is_production:
        path: Path = DATA_DIR / "connections.key"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Fernet.generate_key())
        local = _local_key()
    if local is not None:
        keys.append(local)
    if not keys:
        raise NoKey("Connect the CRM to Bishnoi One Platform first: set PLATFORM_APP_KEY (from the platform's Connections page) on the server.")
    return MultiFernet(keys)


def seal(settings: Settings, secrets: dict[str, str]) -> str | None:
    return _fernet(settings).encrypt(json.dumps(secrets).encode()).decode() if secrets else None


def unseal(settings: Settings, sealed: str | None) -> dict[str, str]:
    """The saved secrets; none when there are none, or when the key they were saved with is gone."""
    if not sealed:
        return {}
    try:
        return json.loads(_fernet(settings).decrypt(sealed.encode()))
    except (InvalidToken, NoKey, ValueError):
        return {}


def zoho_hosts(centre: str) -> tuple[str, str]:
    """Zoho's sign-in and API addresses for a data centre."""
    if centre == "ca":
        return "https://accounts.zohocloud.ca", "https://www.zohoapis.ca"
    return f"https://accounts.zoho.{centre}", f"https://www.zohoapis.{centre}"
