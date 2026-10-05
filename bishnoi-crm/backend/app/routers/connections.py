"""Settings → Connections: the details the CRM needs to reach outside services
(app/connections.py). Administrators with admin.settings only. Secrets go in
and never come out: a screen sees that one is saved and how it ends."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from app.access import Access, require
from app.api import Api, field_error, iso, person_out
from app.audit import audit
from app import connections as svc
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Connection

Manage = Annotated[Access, Depends(require("admin.settings"))]
router = APIRouter(prefix="/admin/connections", tags=["settings"])


def service_for(key: str) -> svc.Service:
    service = svc.BY_KEY.get(key)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such connection.")
    return service


def ending(secret: str) -> str:
    """The last four characters of a long secret, to tell which one is saved. Short ones show nothing."""
    return secret[-4:] if len(secret) >= 12 else ""


def connection_out(service: svc.Service, row: Connection | None, secrets: dict[str, str]) -> dict:
    values = row.values if row else {}
    details = []
    for d in service.details:
        out = {
            "key": d.key,
            "label": d.label,
            "hint": d.hint,
            "secret": d.secret,
            "required": d.required,
            "options": [{"value": v, "label": label} for v, label in d.options],
        }
        if d.secret:
            out |= {"saved": bool(secrets.get(d.key)), "ending": ending(secrets.get(d.key, ""))}
        else:
            out["value"] = values.get(d.key)
        details.append(out)
    return {
        "key": service.key,
        "name": service.name,
        "purpose": service.purpose,
        "helpUrl": service.help_url,
        "enabled": bool(row and row.is_enabled),
        "details": details,
        "missing": svc.missing(service, values, secrets),
        "check": {"at": iso(row.checked_at), "ok": row.check_ok, "message": row.check_message} if row and row.checked_at else None,
        "updatedAt": iso(row.updated_at) if row else None,
        "updatedBy": person_out(row.updated_by) if row else None,
    }


@router.get("")
def list_connections(_: Manage, db: DB, settings: SettingsDep) -> list[dict]:
    out = []
    for service in svc.SERVICES:
        row = db.get(Connection, service.key)
        out.append(connection_out(service, row, svc.unseal(settings, row.secrets if row else None)))
    return out


class ConnectionIn(Api):
    # By detail key. A secret left out stays as saved; one sent empty is removed.
    values: dict[str, str | None] = Field(default_factory=dict)
    enabled: bool | None = None


@router.put("/{key}")
def save_connection(_: Manage, me: CurrentUser, db: DB, settings: SettingsDep, key: str, body: ConnectionIn) -> dict:
    service = service_for(key)
    row = db.get(Connection, key) or Connection(key=key, values={}, is_enabled=False)
    known = {d.key: d for d in service.details}
    for name in body.values:
        if name not in known:
            raise field_error(name, "This connection doesn't take that.")
    values, secrets = dict(row.values or {}), svc.unseal(settings, row.secrets)
    changed: list[str] = []
    for name, raw in body.values.items():
        d, value = known[name], (raw or "").strip()
        if len(value) > 2000:
            raise field_error(name, "That's too long.")
        if d.options and value and value not in {v for v, _ in d.options}:
            raise field_error(name, "Pick one of the options.")
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
        try:
            row.secrets = svc.seal(settings, secrets)
        except svc.NoKey as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
        row.values = values
        if any(n != "enabled" for n in changed):
            # New details: the last test was of the old ones.
            row.checked_at = row.check_ok = row.check_message = None
        row.updated_at, row.updated_by_id = datetime.now(UTC), me.id
        db.add(row)
        # Which details changed, never what they are.
        audit(db, me, "connection.updated", target=service.name, target_type="connection", target_id=key, fields=changed)
        db.commit()
        db.refresh(row)
    return connection_out(service, row if row.updated_at else None, secrets)


@router.post("/{key}/check")
def check_connection(_: Manage, me: CurrentUser, db: DB, settings: SettingsDep, key: str) -> dict:
    """Tries the saved details against the service, and keeps the answer."""
    service = service_for(key)
    row = db.get(Connection, key)
    secrets = svc.unseal(settings, row.secrets if row else None)
    gaps = svc.missing(service, row.values if row else {}, secrets)
    if row is None or gaps:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Fill in {', '.join(gaps) or 'the details'} and save first.")
    try:
        checker = svc.CHECKS.get(key)
        message = checker({**row.values, **secrets}) if checker else "Filled in. Each person now connects their own mailbox (Account → Mailbox): that sign-in is the real test."
        row.check_message, row.check_ok = message, True
    except svc.CheckFailed as e:
        row.check_message, row.check_ok = str(e)[:300], False
    row.checked_at = datetime.now(UTC)
    audit(db, me, "connection.checked", target=service.name, target_type="connection", target_id=key)
    db.commit()
    db.refresh(row)
    return connection_out(service, row, secrets)
