"""This application's connect key: delivered by Bishnoi One Platform to the
address registered for it (Platform > Applications), not copied onto the
server. The Platform signs it; this checks the signature with the Platform's
public key (app/platform_pass.py) and keeps the key in the database
(DATABASE_URL's own, not a company's). Without one, the application says hello
to the Platform, which sends it to the registered address: only whoever runs
that address receives it. PLATFORM_APP_KEY, when set, is used instead.
"""

import base64
import json
import logging
import threading
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, MetaData, String, Table, Text, delete, insert, select, update

from app import platform_pass
from app.config import Settings

APP = "inventory"
log = logging.getLogger(__name__)

_meta = MetaData()
_table = Table("nbin_platform_connection", _meta, Column("name", String(40), primary_key=True), Column("value", Text, nullable=False))
_lock = threading.Lock()
_engines: dict = {}
_cached: dict[str, tuple[str | None, float]] = {}  # by database: (the key, when it was read)
_hello_at = -60.0
KEEP = 60  # seconds a read key is kept in memory


def _engine(settings: Settings):
    from app.db import make_engine

    with _lock:
        engine = _engines.get(settings.database_url)
        if engine is None:
            engine = make_engine(settings.database_url)
            _meta.create_all(engine, checkfirst=True)
            _engines[settings.database_url] = engine
    return engine


def stored_key(settings: Settings) -> str | None:
    hit = _cached.get(settings.database_url)
    if hit and time.monotonic() - hit[1] < KEEP:
        return hit[0]
    try:
        with _engine(settings).connect() as c:
            value = c.execute(select(_table.c.value).where(_table.c.name == "connect_key")).scalar()
    except Exception:
        log.exception("Connect key: couldn't read it from the database.")
        value = hit[0] if hit else None
    _cached[settings.database_url] = (value, time.monotonic())
    return value


def save_key(settings: Settings, key: str | None) -> None:
    with _engine(settings).begin() as c:
        c.execute(delete(_table).where(_table.c.name == "connect_key"))
        if key:
            c.execute(insert(_table).values(name="connect_key", value=key))
    _cached[settings.database_url] = (key, time.monotonic())


def read_value(settings: Settings, name: str) -> str | None:
    """Something else the Platform gave, kept in the same table (app/company.py's passes)."""
    with _engine(settings).connect() as c:
        return c.execute(select(_table.c.value).where(_table.c.name == name)).scalar()


def write_value(settings: Settings, name: str, value: str | None) -> None:
    """Keeps it (or, with None, lets it go)."""
    with _engine(settings).begin() as c:
        c.execute(delete(_table).where(_table.c.name == name))
        if value is not None:
            c.execute(insert(_table).values(name=name, value=value))


def connect_key(settings: Settings) -> str | None:
    """The key to ask the Platform with: PLATFORM_APP_KEY, or the one it delivered.
    None yet: the Platform is asked to deliver it (in the background)."""
    if settings.platform_app_key:
        return settings.platform_app_key.get_secret_value()
    if not settings.platform_api_url:
        return None
    key = stored_key(settings)
    if key is None:
        say_hello(settings)
    return key


def replaced(settings: Settings) -> None:
    """The Platform no longer takes the delivered key: forget it, and ask again."""
    if settings.platform_app_key:
        return
    save_key(settings, None)
    say_hello(settings)


def say_hello(settings: Settings) -> None:
    """Asks the Platform for this application's key, at most once a minute.
    It answers by sending the key to the address registered for this application."""
    global _hello_at
    now = time.monotonic()
    if now - _hello_at < 60:
        return
    _hello_at = now
    url = f"{settings.platform_api_url.rstrip('/')}/connect/hello"

    def run() -> None:
        import httpx

        try:
            httpx.post(url, json={"app": APP}, timeout=5)
        except httpx.HTTPError as e:
            log.warning("Connect key: couldn't reach the Platform at %s (%s).", url, e.__class__.__name__)

    threading.Thread(target=run, name="platform-hello", daemon=True).start()


def _b64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def read_delivery(settings: Settings, token: str) -> str:
    """The key in the Platform's signed delivery, once it's checked."""
    head_b64, body_b64, sig_b64 = token.split(".")
    body = json.loads(_b64(body_b64))
    for key in (platform_pass.public_key(settings), platform_pass.public_key(settings, again=True)):
        if not key:
            continue
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(key)).verify(_b64(sig_b64), f"{head_b64}.{body_b64}".encode())
            break
        except (InvalidSignature, ValueError):
            continue
    else:
        raise ValueError("not signed by the Platform")
    if body.get("iss") not in platform_pass.ISSUERS or body.get("aud") != APP or body.get("kind") != "connect":
        raise ValueError("not this application's key")
    if not isinstance(body.get("exp"), int) or body["exp"] + platform_pass.LEEWAY < time.time():
        raise ValueError("expired")
    key = body.get("key")
    if not isinstance(key, str) or not key.startswith(f"bpk.{APP}."):
        raise ValueError("no key")
    return key


router = APIRouter(tags=["platform"])


class DeliveryIn(BaseModel):
    token: str = Field(min_length=20, max_length=4000)


@router.post("/platform/connect", status_code=status.HTTP_204_NO_CONTENT)
def take_delivery(body: DeliveryIn, request: Request) -> Response:
    """The Platform sends this application its connect key, signed. Nothing else is taken."""
    settings: Settings = request.app.state.settings
    if not settings.platform_api_url:
        raise HTTPException(status.HTTP_409_CONFLICT, "PLATFORM_API_URL isn't set, so the Platform's signature can't be checked.")
    try:
        key = read_delivery(settings, body.token)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"That isn't a delivery from the Platform ({e}).") from None
    save_key(settings, key)
    from app import platform_links

    platform_links.forget()
    log.info("Connect key: delivered by the Platform.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def forget() -> None:
    """Reads the key again next time (tests)."""
    global _hello_at
    _cached.clear()
    _hello_at = -60.0
