"""A company's app catalogue (feature plan step 6, decision 10): which catalogue apps and features
are on (app/abilities.py defines them; nbpl_company_switches keeps the company's choices).

- switches(db, company_id): every catalogue app ("app:purchasing") and feature ("inventory.batches"),
  on or off. The one app hides what's off; the screens read them from /identity/me.
- for_service(...): the ones that run inside one service, for its company pass, so each app can
  hide its own menus, fields and reports too.
- service_on(...): a service is open to the company's people while any catalogue app in it is on.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.abilities import CATALOGUE, app_switch, effective
from app.models import Application, CompanyApp, CompanySwitch


def services_of(db: Session, company_id: str) -> set[str]:
    return set(db.scalars(
        select(Application.key).join(CompanyApp, CompanyApp.application_id == Application.id)
        .where(CompanyApp.company_id == company_id, Application.is_active)
    ))


def chosen(db: Session, company_id: str) -> dict[str, bool]:
    return {s.key: s.is_on for s in db.scalars(select(CompanySwitch).where(CompanySwitch.company_id == company_id))}


def switches(db: Session, company_id: str) -> dict[str, bool]:
    return effective(chosen(db, company_id), services_of(db, company_id))


def for_service(db: Session, company_id: str, service: str) -> dict[str, bool]:
    on = switches(db, company_id)
    return {k: v for a in CATALOGUE if a.service == service for k, v in on.items() if k == app_switch(a.key) or k.startswith(f"{a.key}.")}


def service_on(db: Session, company_id: str, service: str) -> bool:
    """Whether the company's people may open this service: any of its catalogue apps on (a service
    the catalogue doesn't list, such as the Platform, is as the company has it)."""
    apps = [a for a in CATALOGUE if a.service == service and not a.later]
    if not apps:
        return True
    on = switches(db, company_id)
    return any(on[app_switch(a.key)] for a in apps)
