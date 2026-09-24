"""Administration: users, roles and permissions, and the activity log.

Each part has its own permission (admin.users, admin.roles, admin.audit), so
the jobs can be handed out separately. Every change is written to the log in
the same transaction, and nothing may leave the app with nobody able to
manage users and roles (access.keep_an_administrator).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field, field_validator
from pydantic.alias_generators import to_camel
from sqlalchemy import func, select

from app.access import Can, keep_an_administrator, permissions_of
from app.api import Api, changed, check_email, field_error, get_or_404, iso
from app.audit import audit
from app.deps import DB
from app.models import AuditEntry, Role, RolePermission, SignInSession, User
from app.permissions import ALL_PERMISSIONS, catalogue_out
from app.security import check_password_rules, hash_password

router = APIRouter(prefix="/admin", tags=["administration"])


def good_password(value: str) -> str:
    problem = check_password_rules(value)
    if problem:
        raise ValueError(problem)
    return value


# --- users -----------------------------------------------------------------------------------


class UserIn(Api):
    email: str = Field(max_length=254)
    full_name: str = Field(min_length=1, max_length=120)
    role_id: str = Field(max_length=36)
    license_no: str | None = Field(None, max_length=40)
    password: str = Field(max_length=256)

    _email = field_validator("email")(check_email)
    _password = field_validator("password")(good_password)


class UserPatch(Api):
    email: str | None = Field(None, max_length=254)
    full_name: str | None = Field(None, min_length=1, max_length=120)
    role_id: str | None = Field(None, max_length=36)
    license_no: str | None = Field(None, max_length=40)
    is_active: bool | None = None

    _email = field_validator("email")(check_email)


class PasswordIn(Api):
    password: str = Field(max_length=256)

    _password = field_validator("password")(good_password)


def user_out(user: User, last_sign_in: datetime | None = None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "fullName": user.full_name,
        "licenseNo": user.license_no,
        "isActive": user.is_active,
        "role": {"id": user.role.id, "name": user.role.name},
        "createdAt": iso(user.created_at),
        "lastSignInAt": iso(last_sign_in),
    }


def check_role(db: DB, role_id: str) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise field_error("roleId", "Pick a role.")
    return role


def email_taken(db: DB, email: str, but: str | None = None) -> bool:
    q = select(User.id).where(func.lower(User.email) == email)
    if but:
        q = q.where(User.id != but)
    return db.scalar(q) is not None


def roles_list(db: DB) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.is_system.desc(), func.lower(Role.name))))


@router.get("/users")
def list_users(_: Can("admin.users"), db: DB) -> dict:
    last = dict(db.execute(select(SignInSession.user_id, func.max(SignInSession.created_at)).group_by(SignInSession.user_id)).all())
    users = db.scalars(select(User).order_by(User.is_active.desc(), func.lower(User.full_name)))
    return {
        "users": [user_out(u, last.get(u.id)) for u in users],
        "roles": [{"id": r.id, "name": r.name, "description": r.description} for r in roles_list(db)],
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(access: Can("admin.users"), db: DB, body: UserIn) -> dict:
    if email_taken(db, body.email):
        raise field_error("email", "Someone here already has that email.")
    check_role(db, body.role_id)
    user = User(email=body.email, full_name=body.full_name, role_id=body.role_id, license_no=body.license_no, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    audit(db, access.user, "user.created", target=user.email, target_type="user", target_id=user.id)
    db.commit()
    return user_out(db.get(User, user.id))


@router.get("/users/{user_id}")
def read_user(_: Can("admin.users"), db: DB, user_id: str) -> dict:
    user = get_or_404(db, User, user_id, "person")
    last = db.scalar(select(func.max(SignInSession.created_at)).where(SignInSession.user_id == user.id))
    return {**user_out(user, last), "roles": [{"id": r.id, "name": r.name, "description": r.description} for r in roles_list(db)]}


@router.patch("/users/{user_id}")
def update_user(access: Can("admin.users"), db: DB, user_id: str, body: UserPatch) -> dict:
    user = get_or_404(db, User, user_id, "person")
    wanted = changed(body)
    for key in ("email", "full_name", "role_id", "is_active"):
        if key in wanted and wanted[key] is None:
            raise field_error(to_camel(key), "This can't be empty.")
    if wanted.get("is_active") is False and user.id == access.user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't switch yourself off. Ask another admin.")
    if "email" in wanted and email_taken(db, wanted["email"], but=user.id):
        raise field_error("email", "Someone here already has that email.")
    if "role_id" in wanted:
        check_role(db, wanted["role_id"])
    fields = [k for k, v in wanted.items() if getattr(user, k) != v]
    for key in fields:
        setattr(user, key, wanted[key])
    if fields:
        keep_an_administrator(db)
        action = "user.updated"
        if fields == ["is_active"]:
            action = "user.switched_on" if user.is_active else "user.switched_off"
        audit(db, access.user, action, target=user.email, target_type="user", target_id=user.id, fields=[to_camel(f) for f in fields])
        db.commit()
        db.refresh(user)
    return user_out(user)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(access: Can("admin.users"), db: DB, user_id: str, body: PasswordIn) -> Response:
    """A new password, set by an admin. Every session the person had ends."""
    user = get_or_404(db, User, user_id, "person")
    user.password_hash = hash_password(body.password)
    user.password_changed_at = datetime.now(UTC)
    audit(db, access.user, "user.password_reset", target=user.email, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- roles and permissions --------------------------------------------------------------------


def valid_permissions(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    unknown = sorted(set(value) - ALL_PERMISSIONS)
    if unknown:
        raise ValueError(f"Unknown permission: {', '.join(unknown)}.")
    return sorted(set(value))


class RoleIn(Api):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    permissions: list[str] = Field(default_factory=list, max_length=len(ALL_PERMISSIONS))

    _permissions = field_validator("permissions")(valid_permissions)


class RolePatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    permissions: list[str] | None = Field(None, max_length=len(ALL_PERMISSIONS))

    _permissions = field_validator("permissions")(valid_permissions)


def role_out(role: Role, users: int = 0) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "isSystem": role.is_system,
        "permissions": sorted(permissions_of(role)),
        "userCount": users,
    }


def role_users(db: DB) -> dict[str, int]:
    return dict(db.execute(select(User.role_id, func.count()).where(User.is_active).group_by(User.role_id)).all())


def role_name_taken(db: DB, name: str, but: str | None = None) -> bool:
    q = select(Role.id).where(func.lower(Role.name) == name.lower())
    if but:
        q = q.where(Role.id != but)
    return db.scalar(q) is not None


@router.get("/roles")
def list_roles(_: Can("admin.roles"), db: DB) -> dict:
    counts = role_users(db)
    return {"roles": [role_out(r, counts.get(r.id, 0)) for r in roles_list(db)], "catalogue": catalogue_out()}


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(access: Can("admin.roles"), db: DB, body: RoleIn) -> dict:
    if role_name_taken(db, body.name):
        raise field_error("name", "There's already a role with that name.")
    role = Role(name=body.name, description=body.description)
    role.grants = [RolePermission(permission=p) for p in body.permissions]
    db.add(role)
    db.flush()
    audit(db, access.user, "role.created", target=role.name, target_type="role", target_id=role.id)
    db.commit()
    return role_out(role)


@router.patch("/roles/{role_id}")
def update_role(access: Can("admin.roles"), db: DB, role_id: str, body: RolePatch) -> dict:
    role = get_or_404(db, Role, role_id, "role")
    wanted = changed(body)
    if role.is_system and set(wanted) - {"description"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "The Administrator role always has everything. Make a new role instead.")
    if "name" in wanted and wanted["name"] is None:
        raise field_error("name", "Give the role a name.")
    if "name" in wanted and role_name_taken(db, wanted["name"], but=role.id):
        raise field_error("name", "There's already a role with that name.")
    fields = []
    for key in ("name", "description"):
        if key in wanted and getattr(role, key) != wanted[key]:
            setattr(role, key, wanted[key])
            fields.append(key)
    if wanted.get("permissions") is not None and set(wanted["permissions"]) != role.permissions:
        role.grants = [RolePermission(permission=p) for p in wanted["permissions"]]
        fields.append("permissions")
    if fields:
        keep_an_administrator(db)
        audit(db, access.user, "role.updated", target=role.name, target_type="role", target_id=role.id, fields=fields)
        db.commit()
    return role_out(role, role_users(db).get(role.id, 0))


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(access: Can("admin.roles"), db: DB, role_id: str) -> Response:
    role = get_or_404(db, Role, role_id, "role")
    if role.is_system:
        raise HTTPException(status.HTTP_409_CONFLICT, "The Administrator role can't be deleted.")
    holders = db.scalar(select(func.count()).select_from(User).where(User.role_id == role.id)) or 0
    if holders:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{holders} {'person has' if holders == 1 else 'people have'} this role. Give them another one first.",
        )
    audit(db, access.user, "role.deleted", target=role.name, target_type="role", target_id=role.id)
    db.delete(role)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the activity log --------------------------------------------------------------------------


@router.get("/audit")
def activity_log(
    _: Can("admin.audit"),
    db: DB,
    before: int | None = Query(None, ge=1, description="the last id of the page before"),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, max_length=64, description="an action, or its start: 'prescription.' for every prescription"),
    actor_id: str | None = Query(None, max_length=36, alias="actorId"),
) -> dict:
    """Newest first. Pass the last entry's id as `before` for the next page."""
    q = select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit + 1)
    if before is not None:
        q = q.where(AuditEntry.id < before)
    if action:
        q = q.where(AuditEntry.action.startswith(action) if action.endswith(".") else AuditEntry.action == action)
    if actor_id:
        q = q.where(AuditEntry.actor_id == actor_id)
    entries = db.scalars(q).all()
    return {
        "items": [
            {"id": e.id, "at": iso(e.at), "actor": e.actor, "actorId": e.actor_id, "action": e.action, "target": e.target,
             "targetType": e.target_type, "fields": e.fields or []}
            for e in entries[:limit]
        ],
        "more": len(entries) > limit,
    }
