"""What the other applications may read without signing in: the notices
showing for them now, and coming up (maintenance ahead of time); and whether
a company is registered here and may use an application.

    GET /public/notices?app=crm&company=getmeds
    GET /public/company-pass?app=crm&company=getmeds

Nothing here is private: a notice is written to be shown to everyone it names,
and a company pass only says what its application needs to know (signed, so
the application can trust it without a shared secret).
"""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app import passes
from app.announcements import Notices, state_of
from app.deps import DB, SettingsDep
from app.models import Application, Company, CompanyApp
from app.routers.communications import showing

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/applications")
def addresses(db: DB) -> dict:
    """Where each application's screens are, as Applications says: every app's
    sidebar, sign-in button and redirects read them from here, so a new domain
    is set once, here, and every app follows. Not a secret: they're web addresses."""
    apps = db.scalars(select(Application).where(Application.is_active)).all()
    return {
        "addresses": {a.key: a.app_url.rstrip("/") for a in apps if a.app_url},
        # Each API's address too: the one app finds every module's API here, so
        # it needs only PLATFORM_API_URL (decided 2026-10-27).
        "apis": {a.key: a.api_url.rstrip("/") for a in apps if a.api_url},
        "askAgainIn": 300,
    }


@router.get("/notices")
def notices(db: DB, table: Notices, app: str | None = None, company: str | None = None) -> dict:
    return {
        "notices": [
            {"id": n["id"], "kind": n["kind"], "level": n["level"], "title": n["title"], "body": n.get("body"),
             "startsAt": n["startsAt"], "endsAt": n.get("endsAt"), "state": state_of(n)}
            for n in showing(db, table, app, company)
        ]
    }


@router.get("/company-pass")
def company_pass(db: DB, settings: SettingsDep, app: str = Query(max_length=40), company: str = Query(max_length=40)) -> dict:
    """A signed pass saying whether this company is registered, active, and may
    use this application. An application refuses to be used without one."""
    found = db.scalar(select(Company).where(Company.slug == company.strip().lower()))
    application = db.scalar(select(Application).where(Application.key == app))
    if found is None or application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such company registered on the platform.")
    granted = db.get(CompanyApp, (found.id, application.id)) is not None
    token = passes.company_pass(settings, found, application, granted)
    from app.company_push import record_asked

    # Anyone may ask (the pass is what the application checks), so it's
    # recorded at most once an hour per company and application.
    record_asked(db, found, application, passes.claims_of(token))
    return {"pass": token}
