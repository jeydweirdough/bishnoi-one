"""A company's outside services (app/services.py): Zoho Books and the email
providers, filled in on the company's Connections tab.

    GET  /platform/companies/{id}/services            each service, its details (secrets masked)
    PUT  /platform/companies/{id}/services/{key}      saves what changed; switches it on or off
    POST /platform/companies/{id}/services/{key}/check  tries the details on the service
    GET  /connect/services?company=<slug>             an application asks for its company's
                                                      (its connect key in X-Bishnoi-App-Key)

Seeing them takes a platform user; changing them, a Platform Admin. Secrets go
in and never come out to a screen; only an application that uses the service,
and that the company has, is given them.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import select

from app import links
from app import services as svc
from app.api import Api, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import Company, CompanyApp, ServiceConnection, User

router = APIRouter(tags=["connections"])


def detail_error(key: str, message: str) -> HTTPException:
    """A message for one detail, named by its own key (data_centre), as the screen names it."""
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "values", key], "msg": message}])


def service_for(key: str) -> svc.Service:
    service = svc.BY_KEY.get(key)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such connection.")
    return service


def company_for(db, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise not_found("company")
    return company


def row_of(db, company: Company, key: str) -> ServiceConnection | None:
    return db.scalar(select(ServiceConnection).where(ServiceConnection.company_id == company.id, ServiceConnection.service == key))


def service_out(service: svc.Service, row: ServiceConnection | None, secrets: dict[str, str] | None, who: User | None) -> dict:
    values = row.values if row else {}
    unreadable = secrets is None
    secrets = secrets or {}
    details = []
    for d in service.details:
        out = {"key": d.key, "label": d.label, "hint": d.hint, "secret": d.secret, "required": d.required, "options": [{"value": v, "label": label} for v, label in d.options]}
        if d.secret:
            out |= {"saved": bool(secrets.get(d.key)), "ending": svc.ending(secrets.get(d.key, ""))}
        else:
            out["value"] = values.get(d.key)
        details.append(out)
    return {
        "key": service.key,
        "name": service.name,
        "purpose": service.purpose,
        "helpUrl": service.help_url,
        "apps": list(service.apps),
        "enabled": bool(row and row.is_enabled),
        "details": details,
        "missing": svc.missing(service, values, secrets),
        # The platform's signing key changed since they were saved: type them in again.
        "unreadable": unreadable,
        "check": {"at": iso(row.checked_at), "ok": row.check_ok, "message": row.check_message} if row and row.checked_at else None,
        "updatedAt": iso(row.updated_at) if row else None,
        "updatedBy": {"id": who.id, "name": who.full_name} if who else None,
    }


def _out(db, settings, service: svc.Service, row: ServiceConnection | None) -> dict:
    who = db.get(User, row.updated_by_id) if row and row.updated_by_id else None
    return service_out(service, row, svc.unseal(settings, row.secrets) if row else {}, who)


@router.get("/platform/companies/{company_id}/services")
def list_services(company_id: str, db: DB, settings: SettingsDep, _: CurrentUser) -> dict:
    company = company_for(db, company_id)
    return {"services": [_out(db, settings, s, row_of(db, company, s.key)) for s in svc.SERVICES]}


class ServiceIn(Api):
    # By detail key. A secret left out stays as saved; one sent empty is removed.
    values: dict[str, str | None] = Field(default_factory=dict)
    enabled: bool | None = None


@router.put("/platform/companies/{company_id}/services/{key}")
def save_service(company_id: str, key: str, body: ServiceIn, db: DB, settings: SettingsDep, me: AdminUser) -> dict:
    return save(db, settings, company_for(db, company_id), key, body, me, me.id)


def save(db, settings, company: Company, key: str, body: ServiceIn, actor: User | str, actor_id: str | None) -> dict:
    """Saves what changed (also for a company's own administrator, app/routers/company_console.py)."""
    service = service_for(key)
    row = row_of(db, company, key) or ServiceConnection(company_id=company.id, service=key, values={}, is_enabled=False)
    known = {d.key: d for d in service.details}
    for name in body.values:
        if name not in known:
            raise detail_error(name, "This connection doesn't take that.")
    values = dict(row.values or {})
    # Sealed with another signing key: what was saved can't be read, so it's typed in again.
    secrets = svc.unseal(settings, row.secrets) or {}
    changed: list[str] = []
    for name, raw in body.values.items():
        d, value = known[name], (raw or "").strip()
        if len(value) > 2000:
            raise detail_error(name, "That's too long.")
        if d.options and value and value not in {v for v, _ in d.options}:
            raise detail_error(name, "Pick one of the options.")
        store = secrets if d.secret else values
        if (store.get(name) or "") != value:
            changed.append(name)
            if value:
                store[name] = value
            else:
                store.pop(name, None)
    if body.enabled is not None and body.enabled != row.is_enabled:
        if body.enabled and (gaps := svc.missing(service, values, secrets)):
            raise HTTPException(status.HTTP_409_CONFLICT, f"Fill in {', '.join(gaps)} before switching it on.")
        row.is_enabled = body.enabled
        changed.append("enabled")
    # Switched on, it can't lose what it needs.
    if row.is_enabled and (gaps := svc.missing(service, values, secrets)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{', '.join(gaps)} can't be removed while it's switched on.")
    if changed:
        row.secrets, row.values = svc.seal(settings, secrets), values
        if any(n != "enabled" for n in changed):
            # New details: the last test was of the old ones.
            row.checked_at = row.check_ok = row.check_message = None
        row.updated_at, row.updated_by_id = datetime.now(UTC), actor_id
        db.add(row)
        # Which details changed, never what they are.
        audit(db, actor, "service.updated", category="security", target=f"{company.name} · {service.name}", target_type="company", target_id=company.id, company_id=company.id, fields=changed)
        db.commit()
        db.refresh(row)
    return _out(db, settings, service, row if row.id else None)


@router.post("/platform/companies/{company_id}/services/{key}/check")
def check_service(company_id: str, key: str, db: DB, settings: SettingsDep, me: AdminUser) -> dict:
    return check(db, settings, company_for(db, company_id), key, me)


def check(db, settings, company: Company, key: str, actor: User | str) -> dict:
    """Tries the saved details against the service, and keeps the answer."""
    service = service_for(key)
    row = row_of(db, company, key)
    secrets = svc.unseal(settings, row.secrets) if row else {}
    gaps = svc.missing(service, row.values if row else {}, secrets or {})
    if row is None or secrets is None or gaps:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Fill in {', '.join(gaps) or 'the details'} and save first.")
    try:
        checker = svc.CHECKS.get(key)
        message = checker({**row.values, **secrets}) if checker else "Filled in. Each person now connects their own mailbox in the CRM (Account → Mailbox): that sign-in is the real test."
        row.check_message, row.check_ok = message[:300], True
    except svc.CheckFailed as e:
        row.check_message, row.check_ok = str(e)[:300], False
    row.checked_at = datetime.now(UTC)
    audit(db, actor, "service.checked", target=f"{company.name} · {service.name}", target_type="company", target_id=company.id, company_id=company.id)
    db.commit()
    db.refresh(row)
    return _out(db, settings, service, row)


@router.get("/connect/services")
def my_services(
    db: DB,
    settings: SettingsDep,
    company: Annotated[str, Query(max_length=40)],
    key: Annotated[str | None, Header(alias="X-Bishnoi-App-Key")] = None,
) -> dict:
    """An application's services at one company: switched on, filled in, and
    used by it, with every detail. Only for a company that has the application."""
    app = links.app_of_key(db, key)
    if app is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That connect key isn't one the platform made, or it was replaced. Make a new one in Connections.")
    found = db.scalar(select(Company).where(Company.slug == company.strip().lower()))
    if found is None or db.get(CompanyApp, (found.id, app.id)) is None:
        return {"company": company, "services": {}, "askAgainIn": links.ASK_AGAIN}
    out: dict[str, dict] = {}
    for row in db.scalars(select(ServiceConnection).where(ServiceConnection.company_id == found.id, ServiceConnection.is_enabled)):
        service = svc.BY_KEY.get(row.service)
        secrets = svc.unseal(settings, row.secrets)
        if service is None or app.key not in service.apps or secrets is None or svc.missing(service, row.values or {}, secrets):
            continue
        out[service.key] = {**(row.values or {}), **secrets}
    return {"company": found.slug, "services": out, "askAgainIn": links.ASK_AGAIN}
