"""Bishnoi One Pharmacy API.

Run with:  uv run main.py   (port 8307)
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from modules.pharmacy.config import Settings, get_settings
from modules.pharmacy.db import make_engine, make_sessions
from modules.pharmacy.discord import logs_for, mirror_audit
from modules.pharmacy.models import AuditEntry
from modules.pharmacy.first_admin import make_first_admin
from modules.pharmacy.migrate import upgrade
from modules.pharmacy.routers import admin, auth, profile, batches, dispensing, integration, medicines, patients, prescriptions, reports, sales, stock, suppliers, unset
from modules.pharmacy.guard import install as install_guard

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
    app = FastAPI(title="Bishnoi One Pharmacy API", version="0.2.0", **docs)
    # Rate limits, request size, and errors in plain words (app/guard.py).
    install_guard(app, "Pharmacy")
    app.state.settings = settings
    app.state.sessions = make_sessions(engine)
    # The audit log goes to Discord too, a thread a day (app/discord.py).
    app.state.logs = logs_for("PHARMACY", settings)
    mirror_audit(app.state.sessions, AuditEntry, app.state.logs)
    make_first_admin(app.state.sessions, settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"ok": True, "app": "pharmacy"}

    for module in (auth, profile, admin, reports, medicines, patients, prescriptions, dispensing, sales, batches, stock, suppliers, integration, unset):
        app.include_router(module.router)
    from modules.pharmacy.routers import material_reviews

    app.include_router(material_reviews.router)
    app.include_router(material_reviews.integration)
    from modules.pharmacy import platform_connect, platform_roles

    app.include_router(platform_connect.router)
    app.include_router(platform_roles.router)
    # Data clean-up and the recycle bin, for administrators (2026-10-30).
    from modules.pharmacy.recycle_bin import make_router as recycle_router
    from modules.pharmacy.recycle_kinds import KINDS as recycle_kinds

    app.include_router(recycle_router(recycle_kinds))
    # Connected on the Platform as soon as this runs, not when someone first uses it.
    platform_connect.connect_now(settings)
    return app
