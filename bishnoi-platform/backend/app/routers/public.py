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
    return {"pass": passes.company_pass(settings, found, application, granted)}
