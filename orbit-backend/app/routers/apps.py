"""Settings -> Apps: the other applications this company reaches from Orbit.

Orbit is the hub. People, customers, products, prices and roles live here, and
other applications do their own work beside it — the Orders app takes an order
through its eighteen steps, a warehouse app might pick stock, an HR portal might
hold contracts. Which applications a company has, and where they are, is the
company's to say.

That is the whole point of this screen: adding another application later should
be an Admin typing a name and a link, not an environment variable and a
deployment. What an application *can do* stays in code where it has permissions
attached (app/modules.py); where it *is* is a row here.

The built-in ones can be renamed, pointed elsewhere and switched off, but not
removed: their permissions exist whether or not there is a link, and a role
granting "approve orders" would make no sense with the Orders app deleted.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.catalogue import app_links
from app.deps import DB, CurrentUser, require_recovery
from app.errors import Loc, field_errors
from app.models import AppLink
from app.modules import BY_KEY, Kind
from app.schemas import AppLinksIn
from app.scope import is_code, slugify

router = APIRouter(prefix="/admin/apps", tags=["settings"], dependencies=[Depends(require_recovery)])


def app_out(row: AppLink) -> dict:
    return {
        "code": row.code,
        "name": row.name,
        "url": row.url,
        "description": row.description,
        "icon": row.icon,
        "isBuiltIn": row.is_built_in,
        "isActive": row.is_active,
        # True once there is somewhere to send people. Until then the link is
        # kept but never shown, here or in anybody's sidebar.
        "isReady": bool(row.url),
    }


def apps_out(db: Session) -> dict:
    rows = db.scalars(select(AppLink).order_by(AppLink.sort_order, AppLink.name))
    return {"apps": [app_out(r) for r in rows]}


def new_code(name: str, taken: set[str]) -> str:
    """A code from the name, unique in this company. It never changes after
    this: roles and links are granted against it."""
    base = slugify(name)[:32].strip("-")
    if not is_code(base):
        raise field_errors([(("apps",), "Give it a name with letters or numbers in it.")])
    code, n = base, 2
    while code in taken or code in BY_KEY:
        code, n = f"{base}-{n}"[:32], n + 1
    return code


@router.get("")
def read_apps(db: DB) -> dict:
    return apps_out(db)


@router.put("")
def replace_apps(body: AppLinksIn, db: DB, me: CurrentUser) -> dict:
    """The whole list, as the screen holds it.

    A built-in application can be renamed, moved or switched off but never
    dropped: leaving it out of the list leaves it exactly as it was, rather
    than deleting something whose permissions are still in code and still
    granted to people."""
    have = {row.code: row for row in db.scalars(select(AppLink))}
    errors: list[tuple[Loc, str]] = []

    seen: set[str] = set()
    for i, app in enumerate(body.apps):
        if app.code and app.code not in have:
            errors.append((("apps", i, "code"), "That app was removed meanwhile. Reload and try again."))
        name = app.name.strip()
        if name.casefold() in {n.casefold() for n in seen}:
            errors.append((("apps", i, "name"), "Two apps can't share a name."))
        seen.add(name)
    if errors:
        raise field_errors(errors)

    kept: set[str] = set()
    taken = set(have)
    for order, app in enumerate(body.apps):
        row = have.get(app.code) if app.code else None
        if row is None:
            code = new_code(app.name, taken)
            taken.add(code)
            row = AppLink(code=code, is_built_in=False)
            db.add(row)
        row.name = app.name.strip()
        row.url = app.url or ""
        row.description = app.description or ""
        row.icon = app.icon
        row.is_active = app.is_active
        row.sort_order = order
        kept.add(row.code)

    # Anything the screen didn't send is gone — except the built-in ones, which
    # stay whatever happens, because their permissions do.
    for code, row in have.items():
        if code not in kept and not row.is_built_in:
            db.delete(row)

    db.commit()
    audit(db, me, "apps.changed", ", ".join(sorted(kept)))
    return apps_out(db)
