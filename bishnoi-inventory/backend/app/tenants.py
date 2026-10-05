"""One Inventory for many companies: each company's data in a database of its own.

A company is known by its short name on Bishnoi One Platform (its slug:
getmeds, northwind). Its database is Inventory's DATABASE_URL with the slug
added to the name:

    sqlite:///.data/inventory.db        ->  .data/inventory-getmeds.db
    postgresql://…/neondb?sslmode=…     ->  …/neondb_getmeds?sslmode=…

so nothing one company keeps can be read by another: not a row, not a
setting, not a number. Each company's database is made the first time the
company is used (it must be registered on the platform first: app/company.py),
and brought up to date by the migrations the first time this process opens
it, as the one database was before.

Which company a request is for: the session's token starts with it
("getmeds.<random>"); before signing in, the X-Bishnoi-Company header says
(the sign-in page sends it); on this computer, nothing said means
DEFAULT_COMPANY.
"""

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException, Request, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import make_engine
from app.migrate import upgrade

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,38}[a-z0-9]$")
HEADER = "X-Bishnoi-Company"


def clean(slug: str | None) -> str | None:
    """A company's short name as kept: lower case, or None when it isn't one."""
    value = (slug or "").strip().lower()
    return value if SLUG.fullmatch(value) else None


def database_url(base: str, slug: str) -> str:
    """The company's own database, beside the one DATABASE_URL names."""
    url = make_url(base)
    if url.get_backend_name() == "sqlite":
        path = Path(url.database or "inventory.db")
        return str(url.set(database=str(path.with_name(f"{path.stem}-{slug}{path.suffix or '.db'}")).replace("\\", "/")))
    return url.set(database=f"{url.database}_{slug.replace('-', '_')}").render_as_string(hide_password=False)


def create_postgres_database(base: str, name: str) -> None:
    """Makes the company's database if it isn't there. CREATE DATABASE can't run in
    a transaction, so on a connection of its own, to the database DATABASE_URL names."""
    url = make_url(re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", base))
    engine = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"prepare_threshold": None, "connect_timeout": 10})
    try:
        with engine.connect() as c:
            if not c.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar():
                c.exec_driver_sql(f'CREATE DATABASE "{name}"')
    finally:
        engine.dispose()


@dataclass
class Tenant:
    slug: str
    engine: Engine
    sessions: sessionmaker[Session]


@dataclass
class Tenants:
    """Each company's engine and sessions, made once per process."""

    settings: Settings
    on_new: list = field(default_factory=list)  # called with each Tenant when first opened
    _open: dict[str, Tenant] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, slug: str) -> Tenant:
        with self._lock:
            found = self._open.get(slug)
            if found:
                return found
            url = database_url(self.settings.database_url, slug)
            if make_url(url).get_backend_name() != "sqlite":
                create_postgres_database(self.settings.database_url, make_url(url).database)
            engine = make_engine(url)
            upgrade(engine)
            tenant = Tenant(slug, engine, sessionmaker(engine, expire_on_commit=False, info={"tenant": slug}))
            for hook in self.on_new:
                hook(tenant)
            self._open[slug] = tenant
            return tenant

    def close(self) -> None:
        """Lets go of every company's connections (tests; shutting down)."""
        with self._lock:
            for tenant in self._open.values():
                tenant.engine.dispose()
            self._open.clear()

    def known(self) -> list[str]:
        """The companies with a database already (for the backup and the tools)."""
        return known_at(self.settings.database_url)


def for_tool(argv: list[str]) -> tuple[str, str]:
    """For the command-line tools: the company named by --company (on this
    computer, DEFAULT_COMPANY when not named) and its database's URL."""
    from app.config import get_settings

    settings = get_settings()
    named = argv[argv.index("--company") + 1] if "--company" in argv[:-1] else settings.default_company
    slug = clean(named)
    if slug is None:
        raise SystemExit("Say which company: --company <its short name on Bishnoi One Platform>.")
    url = database_url(settings.database_url, slug)
    if make_url(url).get_backend_name() != "sqlite":
        create_postgres_database(settings.database_url, make_url(url).database)
    return slug, url


def known_at(base: str) -> list[str]:
    """The companies with a database beside the one BASE names."""
    url = make_url(base)
    if url.get_backend_name() == "sqlite":
        path = Path(url.database or "inventory.db")
        prefix = f"{path.stem}-"
        return sorted(p.stem[len(prefix):] for p in path.parent.glob(f"{prefix}*{path.suffix or '.db'}") if clean(p.stem[len(prefix):]))
    engine = make_engine(base)
    try:
        with engine.connect() as c:
            names = c.execute(text("SELECT datname FROM pg_database WHERE datname LIKE :p"), {"p": url.database + "\\_%"}).scalars()
            return sorted(n[len(url.database) + 1:].replace("_", "-") for n in names)
    finally:
        engine.dispose()


def company_header(settings: Settings) -> dict:
    """For a call to another Bishnoi One app: which company it's for."""
    return {HEADER: settings.company} if settings.company else {}


def slug_of_token(token: str | None) -> str | None:
    """The company a session's token is for: what comes before its first dot."""
    if not token or "." not in token:
        return None
    return clean(token.split(".", 1)[0])


def company_of(request: Request) -> str:
    """Which company this request is for, or 400 saying how to say so."""
    settings: Settings = request.app.state.settings
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    if token:
        slug = slug_of_token(token)
        if slug is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has ended. Please sign in again.")
        return slug
    asked = request.headers.get(HEADER) or request.query_params.get("company")
    if asked:
        slug = clean(asked)
        if slug is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "That isn't a company's short name (letters, numbers and dashes).")
        return slug
    default = clean(settings.default_company) if not settings.is_production else None
    if default:
        return default
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Say which company: its short name on Bishnoi One Platform.")
