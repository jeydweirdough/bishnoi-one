"""What the signed-in person may do: their role's permissions and scope.

Endpoints ask with `Depends(require("customers.edit"))`, which answers 403
when the role doesn't have it. The role is read on every request, so a change
to a role or to someone's role applies on their next click.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import CurrentUser
from app.models import Role, RolePermission, User
from app.permissions import ALL_PERMISSIONS, KEYS_TO_ADMINISTRATION


@dataclass(frozen=True)
class Access:
    user_id: str
    role_id: str
    role_name: str
    # own | team | managed | all: whose records the permissions reach.
    scope: str
    team_id: str | None
    permissions: frozenset[str]
    # The teams whose records they reach (team: their own; managed: the ones
    # they manage, and their own). Empty for own and all.
    team_ids: frozenset[str] = frozenset()

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def can_any(self, *permissions: str) -> bool:
        return any(p in self.permissions for p in permissions)

    def require(self, permission: str | tuple[str, ...]) -> None:
        """One permission, or a tuple of which any one will do."""
        wanted = permission if isinstance(permission, tuple) else (permission,)
        if not self.can_any(*wanted):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow that.")

    @property
    def departments(self) -> frozenset[str] | None:
        """The departments (teams) whose settings this person may run: None for
        every one (a role that reaches every record), else the teams they reach."""
        if self.scope == "all":
            return None
        return self.team_ids or (frozenset({self.team_id}) if self.team_id else frozenset())

    def runs(self, team_id: str | None) -> bool:
        """Whether this team's settings are theirs. A company-wide one (no team)
        is only for someone who reaches every record."""
        reach = self.departments
        return reach is None or (team_id is not None and team_id in reach)


def permissions_of(role: Role) -> frozenset[str]:
    # The system role holds everything there is, including permissions added
    # after it was made.
    return ALL_PERMISSIONS if role.is_system else frozenset(role.permissions) & ALL_PERMISSIONS


def access_of(user: User) -> Access:
    return Access(
        user_id=user.id,
        role_id=user.role_id,
        role_name=user.role.name,
        scope=user.role.scope,
        team_id=user.team_id,
        permissions=permissions_of(user.role),
        team_ids=teams_reached(user),
    )


def teams_reached(user: User) -> frozenset[str]:
    """The teams whose records this person's scope reaches."""
    scope = user.role.scope
    own = user.all_team_ids
    if scope == "team":
        return frozenset(own)
    if scope == "managed":
        return frozenset(own | {t.id for t in user.managed_teams})
    return frozenset()


def current_access(user: CurrentUser) -> Access:
    return access_of(user)


CurrentAccess = Annotated[Access, Depends(current_access)]


def require(*permissions: str) -> Callable[[Access], Access]:
    """The route needs this permission; given several, any one of them."""
    unknown = [p for p in permissions if p not in ALL_PERMISSIONS]
    if not permissions or unknown:
        raise ValueError(f"unknown permission {unknown!r}")
    needed = permissions[0] if len(permissions) == 1 else tuple(permissions)

    def check(access: CurrentAccess) -> Access:
        access.require(needed)
        return access

    # Read by GraphQL (app/graphql_api.py), which calls the same route functions
    # and must hold them to the same permission.
    check.permission = needed  # type: ignore[attr-defined]
    return check


# Department settings: an administrator's for every department, a manager's
# (department.manage) for the departments they reach.
DEPARTMENT = ("admin.settings", "department.manage")


def administrators(db: Session) -> int:
    """Active people whose role holds every key to administration."""
    system = select(func.count()).select_from(User).join(Role).where(User.is_active, Role.is_system)
    count = db.scalar(system) or 0
    holders = (
        select(RolePermission.role_id)
        .where(RolePermission.permission.in_(KEYS_TO_ADMINISTRATION))
        .group_by(RolePermission.role_id)
        .having(func.count() == len(KEYS_TO_ADMINISTRATION))
    )
    others = select(func.count()).select_from(User).join(Role).where(User.is_active, ~Role.is_system, Role.id.in_(holders))
    return count + (db.scalar(others) or 0)


def keep_an_administrator(db: Session) -> None:
    """Called after a change, before it's committed: refuses anything that
    would leave nobody able to manage users and roles."""
    db.flush()
    if administrators(db) == 0:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That would leave nobody able to manage users and roles. Give someone else that first.",
        )
