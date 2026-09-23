"""Orbit API.

Run with:  uv run uvicorn app.main:create_app --factory --reload
"""

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import ratelimit
from app.config import Settings, get_settings
from app.db import make_engine, make_sessions
from app.jobs import JobQueue
from app.routers import (
    admin,
    apps,
    platform_api,
    auth,
    bulk,
    company,
    data,
    dashboard,
    fields,
    finance,
    inventory,
    lists,
    me,
    order_settings,
    orders_api,
    org,
    photos,
    pricing_rules,
    team_prices,
    retention,
    sales,
    sso,
)
from app.store import build_records
from app.store.files import FileStore
from app.store.records import ConflictError, Records, StoreError
from app.store.sanity import SanityBackend
from app.tenancy import TenancyError

log = logging.getLogger("crm")

# Every response is someone's data: never cached, never framed, never sniffed.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def install_edges(app: FastAPI, settings: Settings) -> None:
    """What every request passes through, outermost first: a known host name,
    security headers, CORS, then the rate limit. Starlette runs the last one
    added first, so they're added innermost first."""
    ratelimit.install(app, settings)
    # An explicit empty list refuses every cross-origin browser call, preflights included.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)


def create_app(
    settings: Settings | None = None, records: Records | None = None, files: FileStore | None = None
) -> FastAPI:
    settings = settings or get_settings()
    records = records or build_records(settings)
    files = files or FileStore(settings.files_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if isinstance(records.backend, SanityBackend):
            public = records.backend.dataset_is_public()
            if public and not settings.allow_public_dataset:
                raise RuntimeError(
                    f"Sanity dataset '{settings.sanity_dataset}' can be read by anyone. Make it private "
                    "(sanity.io/manage -> your project -> Datasets -> Edit -> Private) and start again."
                )
            if public is None:
                log.warning("couldn't confirm the Sanity dataset is private; check it in sanity.io/manage")
        else:
            log.warning("records are in the local file store (%s); set SANITY_PROJECT_ID to use Sanity", settings.local_store_path)
        yield

    # The interactive docs map every endpoint; nobody outside development needs them.
    docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Orbit API", version="0.1.0", lifespan=lifespan, **docs)
    install_edges(app, settings)
    app.state.settings = settings
    app.state.sessions = make_sessions(make_engine(settings.database_url))
    app.state.records = records
    app.state.files = files
    app.state.jobs = JobQueue(settings.bulk_batch_size, settings.bulk_pause_seconds, inline=settings.jobs_inline)

    @app.exception_handler(ConflictError)
    async def _conflict(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            {"detail": "Someone else changed this while you were working on it. Reload and try again."},
            status_code=409,
        )

    @app.exception_handler(TenancyError)
    async def _no_company(_request: Request, exc: TenancyError) -> JSONResponse:
        """Something belonging to a company was asked for from a session that is
        in none -- a Developer Admin who has not opened one yet. It is a plain
        answer, not a fault: open a company and ask again."""
        return JSONResponse({"detail": "Open a company first: this belongs to one."}, status_code=409)

    @app.exception_handler(StoreError)
    async def _store_down(_request: Request, exc: StoreError) -> JSONResponse:
        log.error("records store error: %s", exc)
        return JSONResponse({"detail": "Records are unavailable right now. Try again in a minute."}, status_code=503)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"ok": True, "records": records.kind}

    routers = (
        auth, sso, org, me, dashboard, sales, retention, finance, inventory, bulk,
        pricing_rules, team_prices, lists, fields, company, apps, platform_api, data, order_settings, orders_api, photos, admin,
    )
    for router in (r.router for r in routers):
        app.include_router(router)
    app.include_router(photos.admin)
    return app
