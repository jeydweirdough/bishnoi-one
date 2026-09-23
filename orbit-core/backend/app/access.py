"""Who can do what, where.

A person's access is resolved from three things: their assignments (role +
module + scope), the role x module permission matrix, and the team list. The
result is, for each (module, action), the exact set of (division, subdivision)
scopes it applies to. Record queries take that set as-is (see store/query.py).

`resolve` is pure so the rules can be tested without a database.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogue import modules_by_key
from app.models import Assignment, Membership, Profile, RolePermission, Subdivision
from app.modules import ALL_MODULES, BY_KEY, MANAGE, ORDER_HOMES, ORDERS, RECOVER, SETTINGS, Module
from app.scope import Scope
from app.tenancy import all_companies, company_of

# role key -> module key -> actions
Matrix = Mapping[str, Mapping[str, set[str]]]
# division code -> team codes
Teams = Mapping[str, Sequence[str]]


class AssignmentLike(Protocol):
    role_key: str
    module_key: str
    division_code: str | None
    subdivision_code: str | None


@dataclass(frozen=True)
class Access:
    grants: Mapping[tuple[str, str], frozenset[Scope]] = field(default_factory=dict)
    # Running the whole company: the owner's, and anyone they trust with it.
    manage_settings: bool = False
    # The narrower key: the screens somebody needs when the company is broken.
    # Every settings manager holds it too, so there is never a screen a System
    # Admin can't reach (see `can_recover`).
    recover_settings: bool = False
    # The departments somebody runs without running the company -- a department
    # admin's own. Empty for everyone else, a company-wide admin included: their
    # `manage_settings` already covers every department, so it is never listed
    # here twice.
    manage_departments: frozenset[str] = frozenset()

    def scopes(self, module: str, action: str) -> frozenset[Scope]:
        return self.grants.get((module, action), frozenset())

    def can(self, module: str, action: str) -> bool:
        return bool(self.scopes(module, action))

    def can_in(self, module: str, action: str, scope: Scope) -> bool:
        return scope in self.scopes(module, action)

    def require(self, module: str, action: str, scope: Scope | None = None) -> None:
        allowed = self.can(module, action) if scope is None else self.can_in(module, action, scope)
        if not allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that here.")

    def require_settings(self) -> None:
        """The whole company's settings. Unchanged and deliberately unscoped:
        every screen that reaches beyond one department still asks for this."""
        if not self.manage_settings:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can change settings.")

    def manages_department(self, division: str) -> bool:
        """Whether this person runs that department -- theirs, or all of them."""
        return self.manage_settings or division in self.manage_departments

    @property
    def runs_a_department(self) -> bool:
        """Whether there is any department at all to show them the screens for."""
        return self.manage_settings or bool(self.manage_departments)

    def require_department(self, division: str) -> None:
        if not self.manages_department(division):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "You can only change your own department.",
            )

    @property
    def can_recover(self) -> bool:
        """Running the company includes putting it back together, so a settings
        manager reaches every recovery screen without being given anything."""
        return self.manage_settings or self.recover_settings

    def require_recovery(self) -> None:
        if not self.can_recover:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can change settings.")


def expand(assignment: AssignmentLike, module: Module, teams: Teams) -> frozenset[Scope]:
    """The concrete scopes one assignment covers inside one module."""
    module_key = module.key
    division, subdivision = assignment.division_code, assignment.subdivision_code
    if division and subdivision:
        covered = {Scope(division, subdivision)} if subdivision in teams.get(division, ()) else set()
    elif division:
        covered = {Scope(division, s) for s in teams.get(division, ())}
    else:
        covered = {Scope(d, s) for d, codes in teams.items() for s in codes}

    if not module.spans_divisions:
        covered = {s for s in covered if s.division == module_key}
    if module.reaches is not None:
        covered = {s for s in covered if s.division in module.reaches}
    return frozenset(covered)


def resolve(
    assignments: Iterable[AssignmentLike],
    matrix: Matrix,
    teams: Teams,
    modules: Mapping[str, Module] = BY_KEY,
) -> Access:
    """`modules` is the company's own catalogue (app/catalogue.py), so a
    department its admins added grants access like any built-in one."""
    grants: dict[tuple[str, str], set[Scope]] = defaultdict(set)
    manage_settings = False
    recover_settings = False
    manage_departments: set[str] = set()

    for a in assignments:
        role_actions = matrix.get(a.role_key, {})
        targets = [*modules, SETTINGS] if a.module_key == ALL_MODULES else [a.module_key]
        for module_key in targets:
            actions = role_actions.get(module_key, set())
            if not actions:
                continue
            if module_key == SETTINGS:
                if a.division_code is None:
                    manage_settings = manage_settings or MANAGE in actions
                    recover_settings = recover_settings or RECOVER in actions
                elif MANAGE in actions:
                    # A department's own admin: the same screens, over one
                    # department. Scoped to the division and no further -- the
                    # teams and locations under it come with it, because running
                    # a department is running what is inside it.
                    manage_departments.add(a.division_code)
                # Recovery is never scoped. It reaches the company record, its
                # accounts and the log -- none of which is any one department's,
                # and all of which is the way back in when everything is broken.
                continue
            if module_key not in modules:
                continue
            covered = expand(a, modules[module_key], teams)
            for action in actions:
                grants[(module_key, action)] |= covered
        # A sales (or BID) team assignment carries the role's order steps, for the same teams.
        if a.module_key in ORDER_HOMES and a.module_key in modules:
            covered = expand(a, modules[a.module_key], teams)
            for action in role_actions.get(ORDERS, ()):
                grants[(ORDERS, action)] |= covered

    # Somebody who runs the whole company is not also listed as running each of
    # its departments: one answer, in one place, so the two can never disagree.
    return Access(
        {k: frozenset(v) for k, v in grants.items() if v},
        manage_settings,
        recover_settings,
        frozenset() if manage_settings else frozenset(manage_departments),
    )


def owns_company(db: Session, user_id: str) -> bool:
    """Whoever set this company up, or whoever they have trusted with it since.

    Deliberately read from the membership rather than from a role: owning a
    company is not something its own admins can grant themselves by editing the
    permission matrix."""
    row = db.scalar(select(Membership).where(Membership.user_id == user_id))
    return bool(row and row.is_owner and row.status == "active")


def owners(db: Session) -> list[str]:
    return [m.user_id for m in db.scalars(select(Membership).where(Membership.is_owner.is_(True), Membership.status == "active"))]


def load_matrix(db: Session) -> dict[str, dict[str, set[str]]]:
    matrix: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for p in db.scalars(select(RolePermission)):
        matrix[p.role_key][p.module_key].add(p.action)
    return matrix


def load_teams(db: Session) -> dict[str, list[str]]:
    """Every team, active or not: deactivating a team hides it from new records,
    it doesn't hide the records it already has."""
    teams: dict[str, list[str]] = defaultdict(list)
    for division_code, code in db.execute(select(Subdivision.division_code, Subdivision.code)):
        teams[division_code].append(code)
    return teams


def active_member(db: Session, user_id: str) -> Membership | None:
    """The person's membership in the session's company, if it's switched on."""
    return db.scalar(select(Membership).where(Membership.user_id == user_id, Membership.status == "active"))


def is_on(user: Profile, membership: Membership) -> bool:
    """Switched on everywhere, and in this company."""
    return user.is_active and membership.status == "active"


def works_elsewhere(db: Session, user_id: str) -> bool:
    """Whether the person is also in another company, whose admins share their name and password."""
    here = company_of(db)
    with all_companies(db):
        return db.scalar(select(Membership.org_id).where(Membership.user_id == user_id, Membership.org_id != here).limit(1)) is not None


def members(db: Session, *, active_only: bool = True) -> list[Profile]:
    """The session's company's people (the wall limits Membership to it)."""
    stmt = select(Profile).join(Membership, Membership.user_id == Profile.id)
    if active_only:
        stmt = stmt.where(Membership.status == "active", Profile.is_active.is_(True))
    return list(db.scalars(stmt))


def load_access(db: Session, user_id: str) -> Access:
    """What a person may do in the session's company.

    A Developer Admin holds the recovery screens in every company, member or
    not -- that is the whole job (app/platform.py). Everything else still comes
    from their assignments here, which for most of them is nothing: reaching a
    company to fix it is not the same as working in it."""
    from app.platform import is_developer_admin  # here: app.platform reads models, models don't read this

    developer = is_developer_admin(db, user_id)
    if active_member(db, user_id) is None:
        return Access(recover_settings=True) if developer else Access()
    assignments = db.scalars(select(Assignment).where(Assignment.user_id == user_id)).all()
    access = resolve(assignments, load_matrix(db), load_teams(db), modules_by_key(db))
    return replace(access, recover_settings=True) if developer else access


def access_for_everyone(db: Session) -> dict[str, tuple[Profile, Access]]:
    """Resolved access for every active person in the company. Fine at company size (hundreds)."""
    matrix, teams = load_matrix(db), load_teams(db)
    by_user: dict[str, list[Assignment]] = defaultdict(list)
    for a in db.scalars(select(Assignment)):
        by_user[a.user_id].append(a)
    modules = modules_by_key(db)
    return {p.id: (p, resolve(by_user[p.id], matrix, teams, modules)) for p in members(db)}


def settings_managers(db: Session) -> list[Profile]:
    return [p for p, access in access_for_everyone(db).values() if access.manage_settings]


def ensure_owner(db: Session) -> str | None:
    """A company always has an owner. If it has none — it was set up before
    owners existed, or the only one was removed — the longest-standing person
    who can manage settings becomes it, which is whoever has been running it.

    Self-healing on purpose: there is no state of the system where the company's
    own decisions can be reached by nobody."""
    if owners(db):
        return None
    managers = {p.id for p in settings_managers(db)}
    rows = db.scalars(select(Membership).where(Membership.status == "active").order_by(Membership.created_at))
    chosen = next((m for m in rows if m.user_id in managers), None)
    if chosen is None:
        return None
    chosen.is_owner = True
    db.flush()
    return chosen.user_id
