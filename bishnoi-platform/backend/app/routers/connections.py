"""Connections: the switchboard between applications (app/links.py).

    GET  /connect/links                     an application asks what it's linked to
                                            (its connect key in X-Bishnoi-App-Key)
    GET  /platform/connections              every application's connection, and every link
    POST /platform/applications/{id}/connect-key    a new connect key, shown once
    DELETE /platform/applications/{id}/connect-key  disconnects it
    POST /platform/links                    links two applications (one the code knows)
    PATCH /platform/links/{id}              switches a link on or off
    POST /platform/links/{id}/new-key       a new key between the two
    DELETE /platform/links/{id}

Seeing them takes a platform user; changing them, a Platform Admin. Every
change is in the activity log. Keys between applications never leave the
platform except to the two applications on the link.
"""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import links
from app.api import Api, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import AppLink, Application, utcnow
from app.routers.applications import statuses

router = APIRouter(tags=["connections"])


@router.get("/connect/links")
def my_links(db: DB, settings: SettingsDep, key: Annotated[str | None, Header(alias="X-Bishnoi-App-Key")] = None) -> dict:
    app = links.app_of_key(db, key)
    if app is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That connect key isn't one the platform made, or it was replaced. Make a new one in Connections.")
    answer = links.links_for(db, settings, app)
    links.seen(app)
    db.commit()
    return answer


def _apps(db: Session) -> dict[str, Application]:
    return {a.id: a for a in db.scalars(select(Application).where(Application.is_active).order_by(Application.sort_order, Application.name))}


def link_out(link: AppLink, apps: dict[str, Application], health: dict[str, str], settings) -> dict | None:
    caller, target = apps.get(link.from_app_id), apps.get(link.to_app_id)
    if caller is None or target is None:
        return None
    state, why = links.link_state(link, caller, target, health)
    if link.is_on and links.unseal(settings, link.secret) is None:
        state, why = "problem", "The platform's signing key changed, so this link's key can't be read: make a new key."
    return {
        "id": link.id,
        "from": {"id": caller.id, "key": caller.key, "name": caller.name},
        "to": {"id": target.id, "key": target.key, "name": target.name},
        "isOn": link.is_on,
        "state": state,
        "why": why,
        "what": links.KNOWN.get((caller.key, target.key), ""),
        "changedAt": iso(link.changed_at),
    }


@router.get("/platform/connections")
def connections(db: DB, settings: SettingsDep, _: CurrentUser) -> dict:
    apps = _apps(db)
    health = statuses(db, list(apps.values()))
    made = {(l.from_app_id, l.to_app_id): l for l in db.scalars(select(AppLink))}
    by_key = {a.key: a for a in apps.values()}
    # Links the code knows whose two applications are registered, not made yet: offered.
    offered = [
        {"from": {"id": by_key[f].id, "key": f, "name": by_key[f].name}, "to": {"id": by_key[t].id, "key": t, "name": by_key[t].name}, "what": what}
        for (f, t), what in links.KNOWN.items()
        if f in by_key and t in by_key and (by_key[f].id, by_key[t].id) not in made
    ]
    return {
        "applications": [
            {
                "id": a.id,
                "key": a.key,
                "name": a.name,
                "apiUrl": a.api_url,
                "appUrl": a.app_url,
                "status": health.get(a.id),
                "connected": bool(a.connect_key_hash),
                "keyHint": a.connect_key_hint,
                "keyMadeAt": iso(a.connect_key_made_at),
                "connectedAt": iso(a.connected_at),
            }
            for a in apps.values()
            # Only the applications that take part in a link the code knows: the rest have nothing to connect.
            if any(a.key in pair for pair in links.KNOWN)
        ],
        "links": [out for l in made.values() if (out := link_out(l, apps, health, settings))],
        "offered": offered,
        "askAgainIn": links.ASK_AGAIN,
    }


def _app(db: Session, app_id: str) -> Application:
    a = db.get(Application, app_id)
    if a is None or not a.is_active:
        raise not_found("application")
    return a


@router.post("/platform/applications/{app_id}/connect-key")
def new_connect_key(app_id: str, db: DB, me: AdminUser) -> dict:
    a = _app(db, app_id)
    replaced = bool(a.connect_key_hash)
    key = links.make_connect_key(a)
    audit(db, me, "application.connect_key_replaced" if replaced else "application.connect_key_made", target=a.name, target_type="application", target_id=a.id, application_id=a.id)
    db.commit()
    return {"key": key, "replaced": replaced}


@router.delete("/platform/applications/{app_id}/connect-key", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(app_id: str, db: DB, me: AdminUser) -> Response:
    a = _app(db, app_id)
    a.connect_key_hash = a.connect_key_hint = a.connect_key_made_at = a.connected_at = None
    audit(db, me, "application.disconnected", target=a.name, target_type="application", target_id=a.id, application_id=a.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class LinkIn(Api):
    from_app_id: str = Field(max_length=36)
    to_app_id: str = Field(max_length=36)


class LinkPatch(Api):
    is_on: bool


def _link(db: Session, link_id: str) -> AppLink:
    link = db.get(AppLink, link_id)
    if link is None:
        raise not_found("link")
    return link


def _name(db: Session, link: AppLink) -> str:
    caller, target = db.get(Application, link.from_app_id), db.get(Application, link.to_app_id)
    return f"{caller.name if caller else '?'} uses {target.name if target else '?'}"


@router.post("/platform/links", status_code=status.HTTP_201_CREATED)
def add_link(body: LinkIn, db: DB, settings: SettingsDep, me: AdminUser) -> dict:
    caller, target = _app(db, body.from_app_id), _app(db, body.to_app_id)
    if (caller.key, target.key) not in links.KNOWN:
        raise field_error("toAppId", f"{caller.name} can't use {target.name}: the applications don't have that link.")
    if db.scalar(select(AppLink).where(AppLink.from_app_id == caller.id, AppLink.to_app_id == target.id)):
        raise field_error("toAppId", f"{caller.name} already uses {target.name}.")
    link = AppLink(from_app_id=caller.id, to_app_id=target.id, secret=links.seal(settings, links.new_link_secret()))
    db.add(link)
    db.flush()
    audit(db, me, "link.made", target=f"{caller.name} uses {target.name}", target_type="link", target_id=link.id, application_id=caller.id)
    db.commit()
    apps = _apps(db)
    return {"link": link_out(link, apps, statuses(db, list(apps.values())), settings)}


@router.patch("/platform/links/{link_id}")
def switch_link(link_id: str, body: LinkPatch, db: DB, settings: SettingsDep, me: AdminUser) -> dict:
    link = _link(db, link_id)
    if link.is_on != body.is_on:
        link.is_on, link.changed_at = body.is_on, utcnow()
        audit(db, me, "link.switched_on" if body.is_on else "link.switched_off", target=_name(db, link), target_type="link", target_id=link.id, application_id=link.from_app_id)
        db.commit()
    apps = _apps(db)
    return {"link": link_out(link, apps, statuses(db, list(apps.values())), settings)}


@router.post("/platform/links/{link_id}/new-key")
def new_link_key(link_id: str, db: DB, settings: SettingsDep, me: AdminUser) -> dict:
    """A new key between the two: the old one stops working as both pick the new one up."""
    link = _link(db, link_id)
    link.secret, link.changed_at = links.seal(settings, links.new_link_secret()), utcnow()
    audit(db, me, "link.key_replaced", target=_name(db, link), target_type="link", target_id=link.id, application_id=link.from_app_id)
    db.commit()
    apps = _apps(db)
    return {"link": link_out(link, apps, statuses(db, list(apps.values())), settings)}


@router.delete("/platform/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_link(link_id: str, db: DB, me: AdminUser) -> Response:
    link = _link(db, link_id)
    audit(db, me, "link.removed", target=_name(db, link), target_type="link", target_id=link.id, application_id=link.from_app_id)
    db.delete(link)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
