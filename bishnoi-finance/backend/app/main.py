"""Bishnoi One Finance API.

Run with:  uv run main.py   (port 8303)
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings, get_settings
from app.db import make_engine, make_sessions
from app.discord import log_requests, logs_for
from app.first_admin import make_first_admin
from app.migrate import upgrade
from app.routers import admin, auth, finance, funds, integration, invoices, ledger, receivables, tax, unset
from app.tax import rates as tax_rates
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
    engine = make_engine(settings.database_url)
    upgrade(engine)

    # The interactive docs map every endpoint; nobody outside development needs them.
    docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Bishnoi One Finance API", version="0.1.0", **docs)
    # Rate limits, request size, and errors in plain words (app/guard.py).
    install_guard(app, "Finance")
    app.state.settings = settings
    app.state.sessions = make_sessions(engine)
    # Every change and sign-in goes to Discord as a line, a thread a day (app/discord.py).
    app.state.logs = logs_for("FINANCE", settings)
    log_requests(app, app.state.logs)
    # Each country pack's dated rates, and the company's tax registration row.
    tax_rates.seed(app.state.sessions)
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
        return {"ok": True, "app": "finance"}

    from app import platform_connect

    app.include_router(platform_connect.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(finance.router)
    app.include_router(tax.router)
    app.include_router(integration.router)
    app.include_router(funds.router)
    app.include_router(ledger.router)
    app.include_router(invoices.router)
    app.include_router(receivables.router)
    app.include_router(unset.router)
    app.include_router(integration.funds_router)
    return app
