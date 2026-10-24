"""Bishnoi One Inventory API.

Run with:  uv run main.py   (port 8304)
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings, get_settings
from app.discord import logs_for, mirror_audit
from app.models import AuditEntry
from app.first_admin import make_first_admin
from app.tenants import HEADER, Tenants, clean
from app import graphql_api
from app.routers import adjustments, admin, auth, catalog, profile, insight, integration, orders, purchasing, stock, transfers, unset, warehouses
from app.guard import install as install_guard

# Every response is someone's data: never cached, never framed, never sniffed.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    # The interactive docs map every endpoint; nobody outside development needs them.
    docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Bishnoi One Inventory API", version="0.1.0", **docs)
    # Rate limits, request size, and errors in plain words (app/guard.py).
    install_guard(app, "Inventory")
    app.state.settings = settings
    # The audit log goes to Discord too, a thread a day (app/discord.py).
    app.state.logs = logs_for("INVENTORY", settings)

    def set_up(tenant) -> None:
        """Each company's database, the first time this process opens it."""
        mirror_audit(tenant.sessions, AuditEntry, app.state.logs, tenant.slug)
        # Into one company only: the same account in every company's database
        # would let one person into all of them.
        if tenant.slug == (clean(settings.first_admin_company) or (clean(settings.default_company) if not settings.is_production else None)):
            make_first_admin(tenant.sessions, settings)

    # Each company's data in a database of its own (app/tenants.py).
    app.state.tenants = Tenants(settings, on_new=[set_up])
    # On this computer, the default company is opened now, so the tools and
    # tests have its sessions to hand; in production, each when first asked for.
    default = clean(settings.default_company) if not settings.is_production else None
    if default:
        app.state.sessions = app.state.tenants.get(default).sessions

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", HEADER],
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
        return {"ok": True, "app": "inventory"}

    for module in (auth, profile, admin, catalog, warehouses, stock, purchasing, orders, transfers, adjustments, insight, integration, unset, graphql_api):
        app.include_router(module.router)
    from app import platform_connect, platform_roles

    app.include_router(platform_connect.router)
    app.include_router(platform_roles.router)
    # Connected on the Platform as soon as this runs, not when someone first uses it.
    platform_connect.connect_now(settings)
    # The platform's word when a company changes there (hidden: app/company.py).
    from app import company as company_check

    app.include_router(company_check.router)
    return app
