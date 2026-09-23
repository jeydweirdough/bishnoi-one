"""The modules a company actually has.

app/modules.py holds the built-in ones, the same for every company: the six
sales divisions, the departments Orbit ships screens for, and Orders. On top of
those, an Admin adds departments of their own in Settings -> Teams.

A department an admin adds is an organisation unit and a permission target: it
holds teams and people, it can be granted in roles, and records can belong to
it. It has no screens of its own, so it gets the base four actions and nothing
more. Everything else about it — its name, its icon, whether it is switched on
— is a row in `divisions`, which is why it can change without a deployment.

A built-in module renamed by its admins shows the name they gave it, here and
everywhere the name is read from.

The same holds for other applications. Orbit ships knowing what the Orders app
*does* (its eighteen steps are permissions, so they are code), but not where it
lives or whether this company has a second one — those are rows in `app_links`,
edited in Settings -> Apps. Adding an application later is a name and a link,
not a deployment.
"""

from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppLink, Division
from app.modules import BASE_ACTIONS, BY_KEY, MANAGE, MODULES, RECOVER, SALES_ACTIONS, SETTINGS, Kind, Module
from app.tenancy import org_get

# What a department added in Settings can be granted. No "report": that is a
# sales figure, and an added department has no figures of its own yet.
ADDED_ACTIONS: tuple[str, ...] = BASE_ACTIONS


def added_division(code: str, name: str, kind: str) -> Module:
    """A division an admin added, as a module the rest of the code can use.

    A sales one gets the sales workspace and its actions, because that workspace
    is generic: it is the same screens every sales division already shares. A
    department gets the base four and no screens of its own."""
    if kind == Kind.SALES.value:
        return Module(code, name, Kind.SALES, spans_divisions=False, has_screens=False, actions=SALES_ACTIONS)
    return Module(code, name, Kind.DEPARTMENT, spans_divisions=False, has_screens=False, actions=ADDED_ACTIONS)


def added_app(code: str, name: str) -> Module:
    """An application a company added itself.

    It gets the base four actions so it can be granted in a role like anything
    else — which is what decides who sees its link. Orbit knows nothing about
    what it does inside, and does not pretend to: the permissions that matter
    there are its own."""
    return Module(code, name, Kind.APP, spans_divisions=True, has_screens=False, actions=ADDED_ACTIONS)


def seed_app_links(db: Session) -> None:
    """Every company gets a row for each application Orbit ships with, so
    Settings -> Apps has something to point somewhere.

    It starts with no address: nobody is sent to an application this company may
    not run. Seeding never writes over a name, an address or a switch an admin
    has since changed — it only makes sure the row is there and still marked
    built-in, since its permissions are in code."""
    for order, module in enumerate(m for m in MODULES if m.kind is Kind.APP):
        row = org_get(db, AppLink, module.key)
        if row is None:
            db.add(
                AppLink(
                    code=module.key,
                    name=module.name,
                    description=module.blurb,
                    icon=module.key,
                    is_built_in=True,
                    sort_order=order,
                )
            )
        else:
            row.is_built_in = True
    db.flush()


def app_links(db: Session) -> dict[str, AppLink]:
    """This company's applications, by code: the built-in ones and any it added.
    Switched-off links are left out, so retiring one takes it off every screen."""
    rows = db.scalars(select(AppLink).where(AppLink.is_active.is_(True)).order_by(AppLink.sort_order, AppLink.code))
    return {row.code: row for row in rows}


def app_urls(db: Session) -> dict[str, str | None]:
    """Where each application lives, for the sidebar. None until someone says,
    and a link with no address is never offered."""
    return {code: (row.url or None) for code, row in app_links(db).items()}


def catalogue(db: Session) -> tuple[Module, ...]:
    """Every module this company has, in the order screens list them: the
    built-in ones first, then the divisions and departments it added, oldest
    first."""
    rows = db.execute(
        select(Division.code, Division.name, Division.kind, Division.is_active).order_by(Division.sort_order)
    ).all()
    names = {code: name for code, name, _, _ in rows}
    built_in = tuple(replace(m, name=names.get(m.key, m.name)) for m in MODULES)
    added = tuple(added_division(code, name, kind) for code, name, kind, on in rows if on and code not in BY_KEY)
    # An application this company added: a module of its own, so it can be put
    # in a role and so its link has somewhere to hang.
    links = app_links(db)
    built_in = tuple(replace(m, name=links[m.key].name) if m.kind is Kind.APP and m.key in links else m for m in built_in)
    apps = tuple(added_app(code, row.name) for code, row in links.items() if not row.is_built_in and code not in BY_KEY)
    return (*built_in, *added, *apps)


def sales_keys(db: Session) -> tuple[str, ...]:
    """This company's sales divisions, in its own order. Six of them shipped
    with Orbit; a company adds its own in Settings -> Teams, and everything that
    reads "the sales divisions" must ask here rather than the module list."""
    return tuple(m.key for m in catalogue(db) if m.kind is Kind.SALES)


def modules_by_key(db: Session) -> dict[str, Module]:
    return {m.key: m for m in catalogue(db)}


def can_grant(modules: dict[str, Module], module_key: str, action: str) -> bool:
    """Whether a role may be given this action in this module. Settings is the
    one row that isn't a module: it gates the admin screens, and it has two
    keys -- running the company, and keeping it working."""
    if module_key == SETTINGS:
        return action in (MANAGE, RECOVER)
    module = modules.get(module_key)
    return module is not None and action in module.actions
