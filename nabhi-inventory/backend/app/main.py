"""Nabhi Inventory API.

Run with:  uv run main.py   (port 8304)
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings, get_settings
from app.db import make_engine, make_sessions
from app.discord import logs_for, mirror_audit
from app.models import AuditEntry
from app.first_admin import make_first_admin
from app.migrate import upgrade
from app.routers import adjustments, admin, auth, catalog, insight, integration, orders, purchasing, stock, transfers, warehouses

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
    app = FastAPI(title="Nabhi Inventory API", version="0.1.0", **docs)
    app.state.settings = settings
    app.state.sessions = make_sessions(engine)
    # The audit log goes to Discord too, a thread a day (app/discord.py).
    app.state.logs = logs_for("INVENTORY", settings)
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
        return {"ok": True, "app": "inventory"}

    for module in (auth, admin, catalog, warehouses, stock, purchasing, orders, transfers, adjustments, insight, integration):
        app.include_router(module.router)
    return app
