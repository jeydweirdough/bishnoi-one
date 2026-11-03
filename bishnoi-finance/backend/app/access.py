"""What the signed-in person may do: their role's permissions.

Endpoints ask with `Depends(require("funds.release"))`, which answers
403 when the role doesn't have it. The role is read on every request, so a
change to a role or to someone's role applies on their next click.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import CurrentUser
from app.models import Role, RolePermission, User
from app.permissions import ALL_PERMISSIONS, KEYS_TO_ADMINISTRATION, PER_PERSON


@dataclass(frozen=True)
class Access:
    user: User
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow that.")


def permissions_of(role: Role) -> frozenset[str]:
    # The system role holds everything there is, including permissions added
    # after it was made, except what's switched on per person.
    return (ALL_PERMISSIONS if role.is_system else frozenset(role.permissions) & ALL_PERMISSIONS) - PER_PERSON


def access_of(user: User) -> Access:
    # The role's permissions, and what's switched on for this person (the calendar).
    own = {"calendar.use"} if user.calendar_on else set()
    return Access(user=user, permissions=permissions_of(user.role) | own)


def current_access(user: CurrentUser) -> Access:
    return access_of(user)


CurrentAccess = Annotated[Access, Depends(current_access)]


def require(permission: str) -> Callable[[Access], Access]:
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"unknown permission {permission!r}")

    def check(access: CurrentAccess) -> Access:
        access.require(permission)
        return access

    return check


def allowed(permission: str) -> type[Access]:
    """`_: allowed("funds.view")` in an endpoint's signature."""
    return Annotated[Access, Depends(require(permission))]  # type: ignore[return-value]


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


def permitted(permission: str) -> type[User]:
    """`user: permitted("funds.release")`: the signed-in person, once their role
    allows it. For endpoints that need the person themselves (their name on a
    fund step), not only the yes or no."""
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"unknown permission {permission!r}")

    def check(access: CurrentAccess) -> User:
        access.require(permission)
        return access.user

    return Annotated[User, Depends(check)]  # type: ignore[return-value]


# A settings change (2026-10-31): connected to Bishnoi One, Finance's settings are changed only by the company's
# administrators, from the Admin Console (the Administrator role the Platform gives them). Standalone (tests,
# a single install), the permission alone, as before. Reading a setting is never limited here.
ADMINISTRATORS_ONLY = "Only your company's administrators change Finance's settings, in the Admin Console."


def settings_change(permission: str) -> Callable[..., Access]:
    """require(permission) for a settings route; its changes, once connected, only by an administrator."""
    inner = require(permission)

    def check(request: Request, access: CurrentAccess) -> Access:
        inner(access)
        if request.method != "GET" and request.app.state.settings.platform_api_url and not access.user.role.is_system:
            raise HTTPException(status.HTTP_403_FORBIDDEN, ADMINISTRATORS_ONLY)
        return access

    check.permission = permission  # type: ignore[attr-defined]
    return check


def settings_allowed(permission: str) -> type[Access]:
    """`_: settings_allowed("warehouses.manage")` in a settings endpoint's signature."""
    return Annotated[Access, Depends(settings_change(permission))]  # type: ignore[return-value]


def settings_permitted(permission: str) -> type[User]:
    """permitted(permission) for a settings endpoint: the person, once their role allows it; its changes,
    once connected to Bishnoi One, only by an administrator (settings_change)."""
    check_access = settings_change(permission)

    def check(request: Request, access: CurrentAccess) -> User:
        return check_access(request, access).user

    return Annotated[User, Depends(check)]  # type: ignore[return-value]
