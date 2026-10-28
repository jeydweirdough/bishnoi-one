"""Telling the applications the moment a company changes here.

Each application keeps its companies' passes (30 days) and renews them every
hour by itself (GET /public/company-pass). So that a change here takes effect
at once rather than within the hour, the platform sends each application it
concerns a fresh pass, signed, to the API address registered for it
(Applications): POST <api>/platform/company {"pass": ...}.

- Suspended or reactivated, renamed or moved to another address: every
  application the company has.
- An application given or taken away: that application.
- Deleted: every application it had, with a pass saying so.

The pass is the same signed note the application asks for, so it takes it the
same way: only if the platform's signature checks out, it's for that
application, and it's newer than the one it keeps. Anyone else posting there
gets "Not Found", as if the address didn't exist. Nothing secret is in it:
it says what anyone at the company could see, signed so it can't be made up.

Sent in the background, so nobody here waits for an application; one out of
reach catches up at its next hourly renewal. Every pass sent or asked for is
recorded (CompanyPass), so the platform shows which application holds what.
"""

import logging
import threading

from sqlalchemy import select

from app.config import Settings
from app.models import Application, Company, CompanyApp, CompanyPass

log = logging.getLogger(__name__)


def record(db, company_id: str | None, slug: str, app: Application, token_claims: dict, how: str, answer: str | None = None) -> None:
    """Notes a pass given: to whom, until when, and how it went."""
    from datetime import UTC, datetime

    db.add(
        CompanyPass(
            company_id=company_id,
            company_slug=slug,
            application_id=app.id,
            status=str(token_claims.get("status")),
            granted=bool(token_claims.get("granted")),
            issued_at=datetime.fromtimestamp(token_claims["iat"], UTC),
            expires_at=datetime.fromtimestamp(token_claims["exp"], UTC),
            how=how,
            answer=answer,
        )
    )


def record_asked(db, company: Company, app: Application, claims: dict) -> None:
    """Notes a pass asked for, unless one was noted for this company and application in the last 50 minutes."""
    from datetime import UTC, datetime, timedelta

    recent = db.scalar(
        select(CompanyPass.id).where(
            CompanyPass.company_id == company.id, CompanyPass.application_id == app.id, CompanyPass.how == "asked",
            CompanyPass.issued_at > datetime.now(UTC) - timedelta(minutes=50),
        ).limit(1)
    )
    if recent is None:
        record(db, company.id, company.slug, app, claims, "asked")
        db.commit()


def _send(sessions, settings: Settings, company_id: str, app_ids: set[str], gone: dict | None) -> None:
    import httpx

    from app.catalogue import for_service
    from app.passes import company_pass, claims_of

    with sessions() as db:
        company = db.get(Company, company_id) if gone is None else None
        apps = db.scalars(select(Application).where(Application.id.in_(app_ids), Application.is_active, Application.api_url.is_not(None))).all()
        for app in apps:
            if gone is not None:
                token = company_pass(settings, None, app, granted=False, gone=gone)
                slug = gone["slug"]
            elif company is None:
                continue
            else:
                granted = db.get(CompanyApp, (company.id, app.id)) is not None
                token = company_pass(settings, company, app, granted, features=for_service(db, company.id, app.key))
                slug = company.slug
            url = app.api_url.rstrip("/") + "/platform/company"
            try:
                r = httpx.post(url, json={"pass": token}, timeout=5)
                answer = "taken" if r.status_code == 204 else f"answered {r.status_code}"
            except httpx.HTTPError as e:
                answer = f"out of reach ({e.__class__.__name__})"
            if answer != "taken":
                log.warning("Company push: %s for %r: %s; it catches up at its next renewal.", app.key, slug, answer)
            record(db, None if gone is not None else company_id, slug, app, claims_of(token), "pushed", answer)
        db.commit()


def push(sessions, settings: Settings, company_id: str, app_ids: set[str], gone: dict | None = None) -> None:
    """Sends the applications in app_ids a fresh pass for this company, in the
    background. `gone` ({"id", "slug", "name"}): the company was deleted."""
    if not app_ids:
        return

    def run() -> None:
        try:
            _send(sessions, settings, company_id, app_ids, gone)
        except Exception:  # noqa: BLE001 (the applications catch up at their next renewal)
            log.exception("Company push: couldn't tell the applications about %s.", company_id)

    threading.Thread(target=run, name="company-push", daemon=True).start()


def apps_of(db, company_id: str) -> set[str]:
    """The applications a company has now."""
    return set(db.scalars(select(CompanyApp.application_id).where(CompanyApp.company_id == company_id)))
