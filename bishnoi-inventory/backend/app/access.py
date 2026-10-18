"""What the signed-in person may do: their role's permissions.

Endpoints ask with `Depends(require("adjustments.approve"))`, which answers
403 when the role doesn't have it. The role is read on every request, so a
change to a role or to someone's role applies on their next click.
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
    user: User
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow that.")


def permissions_of(role: Role) -> frozenset[str]:
    # The system role holds everything there is, including permissions added
    # after it was made.
    return ALL_PERMISSIONS if role.is_system else frozenset(role.permissions) & ALL_PERMISSIONS


def access_of(user: User) -> Access:
    return Access(user=user, permissions=permissions_of(user.role))


def current_access(user: CurrentUser) -> Access:
    return access_of(user)


CurrentAccess = Annotated[Access, Depends(current_access)]


def require(permission: str) -> Callable[[Access], Access]:
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"unknown permission {permission!r}")

    def check(access: CurrentAccess) -> Access:
        access.require(permission)
        return access

    # Read by GraphQL (app/graphql_core.py), which calls the same route functions
    # and checks the same permission.
    check.permission = permission  # type: ignore[attr-defined]
    return check


def allowed(permission: str) -> type[Access]:
    """`_: allowed("stock.view")` in an endpoint's signature."""
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
