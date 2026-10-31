"""Bishnoi One CRM API.

Run with:  uv run main.py   (port 8302)
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings, get_settings
from app.discord import logs_for, mirror_audit
from app.models import AuditEntry
from app.first_admin import make_first_admin
from app.inventory import srp_type
from app.tenants import HEADER, Tenants, clean
from app import graphql_api
from app.routers import activities, admin, auth, bulk, catalogue, companies, customer_types, contacts, deals, duplicates, exports, field, imports, insights, kpis, people, price_rules, prices, quote_templates, quotes, retention, sales, crm, unset, integration, integration_prices, connections, attention, media, associations, mailbox
from app.routers import settings as settings_router
from app.routers import reports as reports_router
from app.routers import assistance, field_plan, inbox, lead_finder, profile, quote_links, search, sharing, views
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
    app = FastAPI(title="Bishnoi One CRM API", version="0.1.0", **docs)
    # Rate limits, request size, and errors in plain words (app/guard.py).
    install_guard(app, "CRM")
    app.state.settings = settings
    # The audit log goes to Discord too, a thread a day (app/discord.py).
    app.state.logs = logs_for("CRM", settings)

    def set_up(tenant) -> None:
        """Each company's database, the first time this process opens it."""
        mirror_audit(tenant.sessions, AuditEntry, app.state.logs, tenant.slug)
        # Into one company only: the same account in every company's database
        # would let one person into all of them.
        if tenant.slug == (clean(settings.first_admin_company) or (clean(settings.default_company) if not settings.is_production else None)):
            make_first_admin(tenant.sessions, settings)
        from app.platform_links import effective

        if effective(settings).inventory_linked:
            # The SRP price type, there before any page asks for the price types.
            with tenant.sessions() as db:
                srp_type(db)
                db.commit()

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
        return {"ok": True, "app": "crm"}

    from app import business_events, platform_connect, platform_org, platform_roles

    app.include_router(platform_connect.router)
    app.include_router(platform_roles.router)
    business_events.install(app)
    app.include_router(platform_org.router)
    # Connected on the Platform as soon as this runs, not when someone first uses it.
    platform_connect.connect_now(settings)
    # The platform's word when a company changes there (hidden: app/company.py).
    from app import company as company_check

    app.include_router(company_check.router)
    # Data clean-up and the recycle bin, for administrators (2026-10-30).
    from app.recycle_bin import make_router as recycle_router
    from app.recycle_kinds import KINDS as recycle_kinds

    app.include_router(recycle_router(recycle_kinds))
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(admin.router)
    # Before the record routers, so /companies/bulk isn't read as a company's id.
    app.include_router(bulk.router)
    app.include_router(customer_types.router)
    app.include_router(companies.router)
    app.include_router(graphql_api.router)
    app.include_router(contacts.router)
    app.include_router(duplicates.router)
    app.include_router(activities.router)
    app.include_router(deals.router)
    app.include_router(sales.router)
    app.include_router(people.router)
    app.include_router(insights.router)
    app.include_router(reports_router.router)
    app.include_router(kpis.router)
    app.include_router(imports.router)
    app.include_router(exports.router)
    app.include_router(catalogue.router)
    app.include_router(price_rules.router)
    app.include_router(prices.router)
    app.include_router(quotes.router)
    app.include_router(quote_templates.router)
    app.include_router(retention.router)
    app.include_router(field.router)
    app.include_router(field_plan.router)
    app.include_router(assistance.router)
    app.include_router(settings_router.router)
    app.include_router(connections.router)
    app.include_router(attention.router)
    app.include_router(media.router)
    app.include_router(associations.router)
    app.include_router(mailbox.router)
    app.include_router(crm.router)
    app.include_router(unset.router)
    app.include_router(sharing.router)
    app.include_router(views.router)
    app.include_router(search.router)
    app.include_router(lead_finder.router)
    app.include_router(inbox.router)
    app.include_router(inbox.hooks)
    app.include_router(quote_links.router)
    app.include_router(integration.router)
    app.include_router(integration_prices.router)
    from app.routers import materials

    app.include_router(materials.router)
    app.include_router(materials.integration)
    return app
