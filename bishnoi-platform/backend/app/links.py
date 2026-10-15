"""The platform as the applications' switchboard.

Each application keeps three settings: the platform's address, its public key,
and its own connect key (PLATFORM_APP_KEY), made here. With the connect key it
asks GET /connect/links what it's linked to, and gets:

- for each application it uses: that application's API address, its screens'
  address, and the key to call it with;
- for each application that uses it: the key that caller will send.

So addresses and keys between applications are set here, once, not on every
server. Only the links the code knows (KNOWN) can be made: a link the
applications don't understand would do nothing.

The keys between applications are kept encrypted with a key worked out from
the platform's signing key, so the database alone doesn't give them away.
A connect key is kept only as its hash; it's shown once, when it's made.
"""

import base64
import logging
import hashlib
import secrets
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import passes
from app.api import as_utc
from app.config import Settings
from app.models import AppLink, Application, utcnow

# How often an application asks again (seconds). A link switched off stops
# working within this long; one switched on starts within it.
ASK_AGAIN = 300

# The links the applications' code understands: (who uses, who's used) -> what it does.
KNOWN: dict[tuple[str, str], str] = {
    ("crm", "inventory"): "The CRM's products, prices and stock come from Inventory.",
    ("crm", "finance"): "Finance works out the tax on the CRM's quotes.",
    ("crm", "pharmacy"): "The pharmacist checks the CRM's Rx quotes in Pharmacy.",
    ("finance", "crm"): "Finance reads the CRM's customers to invoice them.",
    ("exec", "pharmacy"): "The pharmacist approves Admin's promotional material designs in Pharmacy.",
    ("exec", "crm"): "Admin reads the CRM's teams and asks their manager to approve promotional materials going out.",
}


def _box(settings: Settings) -> Fernet:
    raw = passes._raw_private(passes.signing_key(settings))
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"bishnoi-app-links:" + raw).digest()))


def seal(settings: Settings, secret: str) -> str:
    return _box(settings).encrypt(secret.encode()).decode()


def unseal(settings: Settings, sealed: str) -> str | None:
    """The key, or None when it was sealed with another signing key (the platform's key changed)."""
    try:
        return _box(settings).decrypt(sealed.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def new_link_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def make_connect_key(app: Application, settings: Settings | None = None) -> str:
    """A new connect key for this application; the old one stops working."""
    key = f"bpk.{app.key}.{secrets.token_urlsafe(32)}"
    if settings is not None:
        app.connect_key_sealed = seal(settings, key)
    app.connect_key_hash = hash_key(key)
    app.connect_key_hint = key[-6:]
    app.connect_key_made_at = utcnow()
    return key


def app_of_key(db: Session, key: str | None) -> Application | None:
    if not key or not key.startswith("bpk."):
        return None
    found = db.scalar(select(Application).where(Application.connect_key_hash == hash_key(key.strip())))
    return found if found is not None and found.is_active else None


def links_for(db: Session, settings: Settings, app: Application) -> dict:
    """What an application is told: what it uses, and who uses it."""
    apps = {a.id: a for a in db.scalars(select(Application).where(Application.is_active))}
    uses: dict[str, dict] = {}
    used_by: dict[str, str] = {}
    for link in db.scalars(select(AppLink).where(AppLink.is_on, (AppLink.from_app_id == app.id) | (AppLink.to_app_id == app.id))):
        caller, target = apps.get(link.from_app_id), apps.get(link.to_app_id)
        secret = unseal(settings, link.secret)
        if caller is None or target is None or secret is None or (caller.key, target.key) not in KNOWN:
            continue
        if caller.id == app.id and target.api_url:
            uses[target.key] = {"apiUrl": target.api_url, "appUrl": target.app_url, "key": secret}
        if target.id == app.id:
            used_by[caller.key] = secret
    return {"app": app.key, "appUrl": app.app_url, "uses": uses, "usedBy": used_by, "dataKey": data_key(settings, app), "askAgainIn": ASK_AGAIN}


def data_key(settings: Settings, app: Application) -> str | None:
    """The key the application encrypts its own secrets with: made the first
    time it's asked for, then the same. None when it can't be read (the
    platform's signing key changed): the application keeps the one it had."""
    if app.data_key is None:
        app.data_key = seal(settings, Fernet.generate_key().decode())
    return unseal(settings, app.data_key)


def link_state(link: AppLink, caller: Application, target: Application, health: dict[str, str]) -> tuple[str, str]:
    """(state, what it means), for the screens: on and working, or what's in the way."""
    if not link.is_on:
        return "off", "Switched off."
    if not target.api_url:
        return "waiting", f"Add {target.name}'s API address, so {caller.name} knows where to call."
    for a in (caller, target):
        if not a.connect_key_hash:
            return "waiting", f"{a.name} isn't connected to the platform yet: make its connect key."
        if not a.connected_at:
            return "waiting", f"Waiting for {a.name} to connect: put its connect key on its server."
    changed = as_utc(link.changed_at)
    for a in (caller, target):
        if as_utc(a.connected_at) < changed:
            return "waiting", f"Waiting for {a.name} to pick the change up (within {ASK_AGAIN // 60} minutes)."
    if health.get(target.id) == "down":
        return "problem", f"{target.name} isn't answering, so {caller.name} can't use it."
    return "working", KNOWN.get((caller.key, target.key), "")


def seen(app: Application, when: datetime | None = None) -> None:
    app.connected_at = when or utcnow()


# --- delivering the connect key to the application's own address ---

log = logging.getLogger("platform.links")
_asked: dict[str, float] = {}  # by application key: when it last asked (a hello)
ASK_EVERY = 30  # seconds between deliveries an application can ask for


def deliver(sessions, settings: Settings, app_id: str) -> str:
    """Sends the application its connect key, signed, to the API address
    registered for it (Applications): only whoever runs that address gets it.
    Makes the key the first time. Returns what happened, in words."""
    import httpx

    from app.passes import connect_pass

    with sessions() as db:
        app = db.get(Application, app_id)
        if app is None or not app.is_active or not app.api_url:
            return "No API address registered for it."
        key = unseal(settings, app.connect_key_sealed) if app.connect_key_sealed else None
        if key is None or hash_key(key) != app.connect_key_hash:
            key = make_connect_key(app, settings)
            db.commit()
        token = connect_pass(settings, app, key)
        url = app.api_url.rstrip("/") + "/platform/connect"
    try:
        r = httpx.post(url, json={"token": token}, timeout=10)
    except httpx.HTTPError as e:
        log.warning("Links: couldn't deliver the connect key to %s (%s).", url, e.__class__.__name__)
        return f"Couldn't reach {url}."
    if r.status_code >= 300:
        log.warning("Links: %s answered %s to the connect key.", url, r.status_code)
        return f"{url} answered {r.status_code}."
    return "Delivered."


def deliver_later(sessions, settings: Settings, app_id: str) -> None:
    """deliver(), without making the caller wait (the application may be the one asking)."""
    import threading

    threading.Thread(target=deliver, args=(sessions, settings, app_id), name="deliver-connect-key", daemon=True).start()


def may_ask(app_key: str) -> bool:
    """At most one delivery every ASK_EVERY seconds per application."""
    import time

    now = time.monotonic()
    if now - _asked.get(app_key, -ASK_EVERY) < ASK_EVERY:
        return False
    _asked[app_key] = now
    return True
