"""Applications: the registry of every app on the platform, the versions
deployed, what each one connects to, and whether it is working.

The platform doesn't run these apps; it keeps the record of them and asks
each one whether it is up (app/monitor.py). What a screen shows as an app's
status comes from one place, `statuses`, so every screen agrees.
"""

import ipaddress
import re
from datetime import datetime
from urllib.parse import urlsplit
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import monitor, platform_settings
from app.api import Api, camel, changed, check_url, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import (
    TICKET_STATUSES,
    Application,
    Company,
    CompanyApp,
    Deployment,
    HealthCheck,
    Identity,
    IdentityApp,
    Incident,
    Integration,
    Ticket,
)

router = APIRouter(prefix="/platform", tags=["applications"])

OPEN = [s for s in TICKET_STATUSES if s not in ("resolved", "closed")]
KEY = re.compile(r"[a-z][a-z0-9-]{1,39}")


class UrlFields(Api):
    @field_validator("app_url", "health_url", "api_url", check_fields=False)
    @classmethod
    def _url(cls, v):
        return check_url(v)


class ApplicationIn(UrlFields):
    key: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(None, max_length=2000)
    app_url: str | None = Field(None, max_length=500)
    health_url: str | None = Field(None, max_length=500)
    # Its API, for the applications linked to it (Connections).
    api_url: str | None = Field(None, max_length=500)
    version: str | None = Field(None, max_length=40)

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not KEY.fullmatch(v):
            raise ValueError("A short lower-case name like crm or hris: letters, numbers and dashes.")
        return v


class ApplicationPatch(UrlFields):
    name: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = Field(None, max_length=2000)
    app_url: str | None = Field(None, max_length=500)
    health_url: str | None = Field(None, max_length=500)
    # Its API, for the applications linked to it (Connections).
    api_url: str | None = Field(None, max_length=500)
    version: str | None = Field(None, max_length=40)
    is_active: bool | None = None
    status_override: Literal["degraded", "maintenance", "outage"] | None = None
    status_note: str | None = Field(None, max_length=300)
    sort_order: int | None = Field(None, ge=0, le=1000)


class DeploymentIn(Api):
    version: str = Field(min_length=1, max_length=40)
    environment: Literal["production", "staging", "development"] = "production"
    notes: str | None = Field(None, max_length=4000)
    deployed_at: datetime | None = None


class IntegrationIn(UrlFields):
    name: str = Field(min_length=2, max_length=120)
    target: str | None = Field(None, max_length=200)
    health_url: str | None = Field(None, max_length=500)
    status: Literal["operational", "degraded", "down", "unknown"] = "unknown"
    notes: str | None = Field(None, max_length=2000)


class IntegrationPatch(UrlFields):
    name: str | None = Field(None, min_length=2, max_length=120)
    target: str | None = Field(None, max_length=200)
    health_url: str | None = Field(None, max_length=500)
    status: Literal["operational", "degraded", "down", "unknown"] | None = None
    notes: str | None = Field(None, max_length=2000)


def statuses(db: Session, apps: list[Application]) -> dict[str, str]:
    """What each application's status is, as every screen shows it."""
    checks = monitor.latest(db, "application", [a.id for a in apps])
    return {a.id: monitor.app_status(a, checks.get(a.id)) for a in apps}


def app_out(a: Application, check: HealthCheck | None = None, **extra) -> dict:
    return {
        "id": a.id,
        "no": a.no,
        "key": a.key,
        "name": a.name,
        "description": a.description,
        "appUrl": a.app_url,
        "healthUrl": a.health_url,
        "apiUrl": a.api_url,
        "version": a.version,
        "connected": bool(a.connect_key_hash),
        "connectedAt": iso(a.connected_at),
        "isActive": a.is_active,
        "status": monitor.app_status(a, check),
        "statusOverride": a.status_override,
        "statusNote": a.status_note,
        "sortOrder": a.sort_order,
        "lastCheck": monitor.check_out(check),
        "createdAt": iso(a.created_at),
        **extra,
    }


def deployment_out(d: Deployment, app_name: str | None = None) -> dict:
    return {
        "id": d.id,
        "applicationId": d.application_id,
        "applicationName": app_name,
        "version": d.version,
        "environment": d.environment,
        "notes": d.notes,
        "deployedAt": iso(d.deployed_at),
        "recordedBy": d.recorded_by,
    }


def integration_out(i: Integration, app_name: str | None = None, check: HealthCheck | None = None) -> dict:
    return {
        "id": i.id,
        "applicationId": i.application_id,
        "applicationName": app_name,
        "name": i.name,
        "target": i.target,
        "healthUrl": i.health_url,
        "status": i.status,
        "notes": i.notes,
        "lastCheck": monitor.check_out(check),
    }


def _app(db: Session, app_id: str) -> Application:
    a = db.get(Application, app_id)
    if a is None:
        raise not_found("application")
    return a


def _fresh(db: Session, settings) -> None:
    monitor.ensure_fresh(db, platform_settings.monitoring(db, settings))


@router.get("/applications")
def list_applications(db: DB, settings: SettingsDep, _: CurrentUser, retired: bool = False) -> dict:
    _fresh(db, settings)
    query = select(Application).order_by(Application.sort_order, Application.name)
    if not retired:
        query = query.where(Application.is_active)
    apps = db.scalars(query).all()
    checks = monitor.latest(db, "application", [a.id for a in apps])
    up = monitor.uptime(db, "application")
    companies = dict(db.execute(select(CompanyApp.application_id, func.count()).group_by(CompanyApp.application_id)).all())
    users = dict(db.execute(select(IdentityApp.application_id, func.count()).group_by(IdentityApp.application_id)).all())
    tickets = dict(
        db.execute(select(Ticket.application_id, func.count()).where(Ticket.status.in_(OPEN)).group_by(Ticket.application_id)).all()
    )
    incidents = dict(
        db.execute(
            select(Incident.application_id, func.count()).where(Incident.status != "resolved").group_by(Incident.application_id)
        ).all()
    )
    return {
        "applications": [
            app_out(
                a,
                checks.get(a.id),
                uptime=up.get(a.id),
                companyCount=companies.get(a.id, 0),
                userCount=users.get(a.id, 0),
                openTickets=tickets.get(a.id, 0),
                activeIncidents=incidents.get(a.id, 0),
            )
            for a in apps
        ]
    }


@router.post("/applications", status_code=status.HTTP_201_CREATED)
def add_application(body: ApplicationIn, db: DB, me: AdminUser) -> dict:
    if db.scalar(select(Application).where(Application.key == body.key)):
        raise field_error("key", f"There's already an application called {body.key}.")
    highest = db.scalar(select(func.max(Application.sort_order))) or 0
    a = Application(**body.model_dump(), sort_order=highest + 1)
    db.add(a)
    db.flush()
    audit(db, me, "application.created", target=a.name, target_type="application", target_id=a.id, application_id=a.id)
    db.commit()
    return {"application": app_out(a)}


@router.get("/applications/{app_id}")
def get_application(app_id: str, db: DB, settings: SettingsDep, _: CurrentUser) -> dict:
    _fresh(db, settings)
    a = _app(db, app_id)
    check = monitor.latest(db, "application", [a.id]).get(a.id)
    per_company = dict(
        db.execute(
            select(Identity.company_id, func.count())
            .join(IdentityApp, IdentityApp.identity_id == Identity.id)
            .where(IdentityApp.application_id == a.id)
            .group_by(Identity.company_id)
        ).all()
    )
    companies = db.scalars(
        select(Company).join(CompanyApp, CompanyApp.company_id == Company.id).where(CompanyApp.application_id == a.id).order_by(Company.name)
    ).all()
    deployments = db.scalars(select(Deployment).where(Deployment.application_id == a.id).order_by(Deployment.deployed_at.desc()).limit(20)).all()
    links = db.scalars(select(Integration).where(Integration.application_id == a.id).order_by(Integration.name)).all()
    link_checks = monitor.latest(db, "integration", [i.id for i in links])
    history = db.scalars(
        select(HealthCheck).where(HealthCheck.target_kind == "application", HealthCheck.target_id == a.id)
        .order_by(HealthCheck.checked_at.desc()).limit(48)
    ).all()
    tickets = db.scalars(
        select(Ticket).where(Ticket.application_id == a.id, Ticket.status.in_(OPEN)).order_by(Ticket.created_at.desc()).limit(10)
    ).all()
    incidents = db.scalars(select(Incident).where(Incident.application_id == a.id).order_by(Incident.started_at.desc()).limit(10)).all()
    return {
        "application": app_out(
            a,
            check,
            uptime=monitor.uptime(db, "application").get(a.id),
            slowMs=platform_settings.monitoring(db, settings).slow_ms,
            userCount=sum(per_company.values()),
            companies=[
                {"id": c.id, "name": c.name, "status": c.status, "userCount": per_company.get(c.id, 0)} for c in companies
            ],
            deployments=[deployment_out(d) for d in deployments],
            integrations=[integration_out(i, a.name, link_checks.get(i.id)) for i in links],
            history=[monitor.check_out(h) for h in history],
            openTickets=[
                {"id": t.id, "number": t.number, "title": t.title, "kind": t.kind, "severity": t.severity, "status": t.status,
                 "createdAt": iso(t.created_at)}
                for t in tickets
            ],
            incidents=[
                {"id": i.id, "number": i.number, "title": i.title, "severity": i.severity, "status": i.status,
                 "startedAt": iso(i.started_at), "resolvedAt": iso(i.resolved_at)}
                for i in incidents
            ],
        )
    }


# --- Addresses that follow the platform's (decided 2026-10-22) -------------
# When a Platform administrator opens the platform at an address that names it
# (platform-bishnoi.local, platform.bishnoi-one.cloud-ip.cc), every app is taken
# to be at the same address with its own name in place of "platform"
# (crm-bishnoi.local, crm.bishnoi-one.cloud-ip.cc), and its App URL is set so.
# Only from an administrator's own visit: an address a request merely claims
# can't move where people are sent to sign in. An App URL set by hand to an
# address of its own (not this computer's, not the old pattern) is left alone.

# An app's name in its address, where it isn't its key.
ADDRESS_NAME = {"exec": "admin"}


class AdoptIn(Api):
    platform_url: str = Field(min_length=8, max_length=300)


def _is_local(host: str | None) -> bool:
    if not host or host in ("localhost",) or host.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _pattern(url: str | None) -> tuple[str, str, str] | None:
    """(scheme, host with {app} for "platform", ":port" or ""), or None when the address doesn't name the platform."""
    if not url:
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or _is_local(host) or "platform" not in host:
        return None
    return parts.scheme, host.replace("platform", "{app}", 1), f":{parts.port}" if parts.port else ""


@router.post("/applications/adopt-address")
def adopt_address(body: AdoptIn, db: DB, me: AdminUser) -> dict:
    new = _pattern(body.platform_url)
    if new is None:
        return {"changed": []}
    scheme, host, port = new
    apps = list(db.scalars(select(Application)))
    platform = next((a for a in apps if a.key == "platform"), None)
    old = _pattern(platform.app_url) if platform else None
    changed_apps = []
    for a in apps:
        target = f"{scheme}://{host.format(app=ADDRESS_NAME.get(a.key, a.key))}{port}"
        if a.app_url == target:
            continue
        current = urlsplit(a.app_url or "")
        follows_old = bool(old) and (current.hostname or "") == old[1].format(app=ADDRESS_NAME.get(a.key, a.key))
        if a.app_url and not _is_local(current.hostname) and not follows_old:
            continue  # an address of its own, set by hand
        audit(db, me, "application.address_followed", target=a.name, target_type="application", target_id=a.id, application_id=a.id, fields=["appUrl"])
        a.app_url = target
        changed_apps.append({"key": a.key, "appUrl": target})
    db.commit()
    return {"changed": changed_apps}


@router.patch("/applications/{app_id}")
def update_application(app_id: str, body: ApplicationPatch, db: DB, me: AdminUser) -> dict:
    a = _app(db, app_id)
    fields = changed(body)
    for required in ("name", "is_active", "sort_order"):
        if required in fields and fields[required] is None:
            raise field_error(required, "This can't be empty.")
    fields = {k: v for k, v in fields.items() if getattr(a, k) != v}
    if "status_override" in fields and fields["status_override"] is None and "status_note" not in fields:
        fields["status_note"] = None  # back to what the check says, and its note goes with it
    for name, value in fields.items():
        setattr(a, name, value)
    if fields:
        action = "application.status_declared" if "status_override" in fields else "application.updated"
        audit(db, me, action, target=a.name, target_type="application", target_id=a.id, application_id=a.id, fields=camel(fields))
    db.commit()
    return {"application": app_out(a, monitor.latest(db, "application", [a.id]).get(a.id))}


@router.post("/applications/{app_id}/deployments", status_code=status.HTTP_201_CREATED)
def add_deployment(app_id: str, body: DeploymentIn, db: DB, me: AdminUser) -> dict:
    """Records a release. One to production makes it the version people are on."""
    a = _app(db, app_id)
    d = Deployment(application_id=a.id, version=body.version, environment=body.environment, notes=body.notes, recorded_by=me.email)
    if body.deployed_at:
        d.deployed_at = body.deployed_at
    db.add(d)
    if body.environment == "production":
        a.version = body.version
    db.flush()
    audit(db, me, "application.deployed", target=f"{a.name} {body.version} ({body.environment})", target_type="application",
          target_id=a.id, application_id=a.id)
    db.commit()
    return {"deployment": deployment_out(d, a.name)}


@router.get("/deployments")
def list_deployments(db: DB, _: CurrentUser, application_id: str | None = None) -> dict:
    query = select(Deployment, Application.name).join(Application).order_by(Deployment.deployed_at.desc()).limit(100)
    if application_id:
        query = query.where(Deployment.application_id == application_id)
    return {"deployments": [deployment_out(d, name) for d, name in db.execute(query)]}


@router.get("/integrations")
def list_integrations(db: DB, settings: SettingsDep, _: CurrentUser) -> dict:
    _fresh(db, settings)
    rows = db.execute(
        select(Integration, Application.name).join(Application).where(Application.is_active).order_by(Application.sort_order, Integration.name)
    ).all()
    checks = monitor.latest(db, "integration", [i.id for i, _ in rows])
    return {"integrations": [integration_out(i, name, checks.get(i.id)) for i, name in rows]}


@router.post("/applications/{app_id}/integrations", status_code=status.HTTP_201_CREATED)
def add_integration(app_id: str, body: IntegrationIn, db: DB, me: AdminUser) -> dict:
    a = _app(db, app_id)
    i = Integration(application_id=a.id, **body.model_dump())
    db.add(i)
    db.flush()
    audit(db, me, "integration.created", target=f"{a.name} · {i.name}", target_type="integration", target_id=i.id, application_id=a.id)
    db.commit()
    return {"integration": integration_out(i, a.name)}


def _integration(db: Session, integration_id: str) -> Integration:
    i = db.get(Integration, integration_id)
    if i is None:
        raise not_found("integration")
    return i


@router.patch("/integrations/{integration_id}")
def update_integration(integration_id: str, body: IntegrationPatch, db: DB, me: AdminUser) -> dict:
    i = _integration(db, integration_id)
    fields = changed(body)
    for required in ("name", "status"):
        if required in fields and fields[required] is None:
            raise field_error(required, "This can't be empty.")
    fields = {k: v for k, v in fields.items() if getattr(i, k) != v}
    for name, value in fields.items():
        setattr(i, name, value)
    if fields:
        audit(db, me, "integration.updated", target=i.name, target_type="integration", target_id=i.id,
              application_id=i.application_id, fields=camel(fields))
    db.commit()
    return {"integration": integration_out(i)}


@router.delete("/integrations/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_integration(integration_id: str, db: DB, me: AdminUser) -> Response:
    i = _integration(db, integration_id)
    audit(db, me, "integration.deleted", target=i.name, target_type="integration", target_id=i.id, application_id=i.application_id)
    db.execute(delete(HealthCheck).where(HealthCheck.target_kind == "integration", HealthCheck.target_id == i.id))
    db.delete(i)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(app_id: str, db: DB, me: AdminUser) -> Response:
    """Gone from the registry, with its deployments, integrations and links.
    Only while no company has it: the applications sign in through it."""
    a = _app(db, app_id)
    using = db.scalar(select(func.count()).select_from(CompanyApp).where(CompanyApp.application_id == a.id)) or 0
    if using:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{using} {'company has' if using == 1 else 'companies have'} {a.name}. Take it from them first (each company's Applications tab), or retire it instead.")
    audit(db, me, "application.deleted", category="security", target=a.name, target_type="application", target_id=a.id)
    db.delete(a)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/deployments/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deployment(deployment_id: str, db: DB, me: AdminUser) -> Response:
    """A deployment recorded by mistake: gone from the history."""
    d = db.get(Deployment, deployment_id)
    if d is None:
        raise not_found("deployment")
    a = db.get(Application, d.application_id)
    audit(db, me, "deployment.deleted", target=f"{a.name if a else 'An application'} {d.version}", target_type="application", target_id=d.application_id, application_id=d.application_id)
    db.delete(d)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
