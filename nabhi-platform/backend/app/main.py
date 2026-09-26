"""Nabhi Platform API: the control tower above every application.

Run with:  uv run main.py   (port 8305)
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.announcements import import_from_database, make_table
from app.config import Settings, get_settings
from app.db import make_engine, make_sessions
from app.discord import DiscordError, logs_for, mirror_audit
from app.first_admin import make_first_admin
from app.migrate import upgrade
from app.models import AuditEntry
from app.routers import (
    access,
    activity,
    applications,
    auth,
    communications,
    companies,
    dashboard,
    incidents,
    monitoring,
    public,
    support,
    users,
)
from app.routers import settings as settings_router
from app.traffic import traffic

# Every response is someone's data: never cached, never framed, never sniffed.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    upgrade(engine)

    # The interactive docs map every endpoint; nobody outside development needs them.
    docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Nabhi Platform API", version="0.1.0", **docs)
    app.state.settings = settings
    app.state.sessions = make_sessions(engine)
    make_first_admin(app.state.sessions, settings)
    # The log goes to Discord too, a thread a day; announcements are kept there (app/announcements.py).
    app.state.logs = logs_for("PLATFORM", settings)
    mirror_audit(app.state.sessions, AuditEntry, app.state.logs)
    app.state.notices = make_table(settings)
    try:
        app.state.notices.load()
        moved = import_from_database(app.state.notices, app.state.sessions)
        if moved:
            logging.getLogger("nabhi.discord").info("[discord:announcements] moved %d announcement(s) out of the database", moved)
    except DiscordError as e:
        logging.getLogger("nabhi.discord").warning("[discord:announcements] couldn't read them yet, trying again in a minute: %s", e)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        # The platform's own traffic (System Monitoring > Traffic).
        traffic.count(response.status_code, round((time.perf_counter() - started) * 1000))
        if traffic.due():
            await run_in_threadpool(traffic.flush, app.state.sessions)
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"ok": True, "app": "platform"}

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(companies.router)
    app.include_router(applications.router)
    app.include_router(users.router)
    app.include_router(access.router)
    app.include_router(support.router)
    app.include_router(incidents.router)
    app.include_router(monitoring.router)
    app.include_router(activity.router)
    app.include_router(communications.router)
    app.include_router(settings_router.router)
    app.include_router(public.router)
    return app
