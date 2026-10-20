"""Administration: users, roles and permissions, teams, and the audit log.

Each part has its own permission (admin.users, admin.roles, admin.teams,
admin.audit), so the jobs can be handed out separately. Every change is
written to the audit log in the same transaction, and nothing may leave the
app with nobody able to manage users and roles (access.keep_an_administrator).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from app.routers.profile import split_name
from app.access import Access, keep_an_administrator, permissions_of, require
from app.api import email_address
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import UserTeam, AuditEntry, Role, RolePermission, SignInSession, Team, User
from app.permissions import ALL_PERMISSIONS, SCOPE_LABELS, SCOPES, catalogue_out
from app.security import check_password_rules, hash_password

router = APIRouter(prefix="/admin", tags=["administration"])

Users = Annotated[Access, Depends(require("admin.users"))]
# The people pages: an administrator for everyone; a manager (department.manage)
# for the people in the teams they manage, as below.
People = Annotated[Access, Depends(require("admin.users", "department.manage"))]


def runs_people(access: Access) -> bool:
    """Whether this person manages every user (an administrator), not only their teams'."""
    return access.can("admin.users")


def grantable(role: Role) -> bool:
    """A role a manager may give: one that reaches its own or its team's records
    (Team Lead, Salesperson, Field agent), never an administrator, a manager or Finance."""
    return not role.is_system and role.scope in ("own", "team")


def in_reach(access: Access, user: User) -> bool:
    """Whether this person may manage this user: an administrator, anyone; a
    manager, the people in the teams they manage, in a role they could give, not themselves."""
    if runs_people(access):
        return True
    return user.id != access.user_id and user.team_id in access.team_ids and grantable(user.role)


def managed_role(db, access: Access, role_id: str) -> Role:
    role = check_role(db, role_id)
    if not runs_people(access) and not grantable(role):
        raise field_error("roleId", "Pick Team Lead, Salesperson or Field agent: other roles are given by an administrator.")
    return role


def managed_team(access: Access, team_id: str | None) -> None:
    if not runs_people(access) and (team_id is None or team_id not in access.team_ids):
        raise field_error("teamId", "Pick one of the teams you manage.")
Roles = Annotated[Access, Depends(require("admin.roles"))]
Teams = Annotated[Access, Depends(require("admin.teams"))]
Audit = Annotated[Access, Depends(require("admin.audit"))]



class Api(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid", str_strip_whitespace=True)


def field_error(field: str, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", field], "msg": message}]
    )


def changed(model: BaseModel) -> dict:
    """The fields a PATCH actually sent, by their Python names."""
    return model.model_dump(exclude_unset=True)


# --- users -----------------------------------------------------------------------------------


class UserIn(Api):
    email: str = Field(max_length=254)
    full_name: str = Field(min_length=1, max_length=120)
    role_id: str = Field(max_length=36)
    team_id: str | None = Field(None, max_length=36)
    # The other teams they're in, beside the main one.
    other_team_ids: list[Annotated[str, Field(max_length=36)]] = Field(default_factory=list, max_length=20)
    password: str = Field(max_length=256)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return email_address(value)

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        problem = check_password_rules(value)
        if problem:
            raise ValueError(problem)
        return value


class UserPatch(Api):
    email: str | None = Field(None, max_length=254)
    full_name: str | None = Field(None, min_length=1, max_length=120)
    role_id: str | None = Field(None, max_length=36)
    team_id: str | None = Field(None, max_length=36)
    other_team_ids: list[Annotated[str, Field(max_length=36)]] | None = Field(None, max_length=20)
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return email_address(value) if value else value


class PasswordIn(Api):
    password: str = Field(max_length=256)

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        problem = check_password_rules(value)
        if problem:
            raise ValueError(problem)
        return value


def iso(moment: datetime | None) -> str | None:
    """A moment for the screens, always with its zone: SQLite hands times back
    without one, and a bare time would be read as the reader's local time."""
    if moment is None:
        return None
    return (moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment).isoformat()


def user_out(user: User, last_sign_in: datetime | None = None) -> dict:
    return {
        "id": user.id,
        "no": user.no,
        "email": user.email,
        "fullName": user.full_name,
        "employeeId": user.employee_id,
        "isActive": user.is_active,
        "role": {"id": user.role.id, "name": user.role.name, "scope": user.role.scope},
        "team": {"id": user.team.id, "name": user.team.name} if user.team else None,
        "otherTeams": [{"id": t.id, "name": t.name} for t in sorted(user.other_teams, key=lambda t: t.name.lower())],
        "createdAt": iso(user.created_at),
        "lastSignInAt": iso(last_sign_in),
    }


def get_user(db: DB, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such person.")
    return user


def reachable_user(db: DB, access: Access, user_id: str) -> User:
    """The user, if this person may manage them; out of reach reads as no such person."""
    user = get_user(db, user_id)
    if not in_reach(access, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such person.")
    return user


def check_role(db: DB, role_id: str) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise field_error("roleId", "Pick a role.")
    return role


def check_team(db: DB, team_id: str | None, *, current: str | None = None) -> Team | None:
    if team_id is None:
        return None
    team = db.get(Team, team_id)
    # A switched-off team keeps the people already in it, but takes nobody new.
    if team is None or (not team.is_active and team_id != current):
        raise field_error("teamId", "Pick a team that's switched on.")
    return team


def set_other_teams(db, access: Access, user: User, wanted: list[str]) -> bool:
    """The other teams a person is in. A manager adds and removes only teams they
    manage; the rest stay as they were. The main team isn't one of them. Whether it changed."""
    wanted_set = set(wanted) - ({user.team_id} if user.team_id else set())
    for team_id in wanted_set:
        check_team(db, team_id, current=team_id if team_id in {t.id for t in user.other_teams} else None)
    if not runs_people(access):
        if outside := wanted_set - access.team_ids - {t.id for t in user.other_teams}:
            raise field_error("otherTeamIds", "Pick only teams you manage.")
        kept = {t.id for t in user.other_teams} - access.team_ids
        wanted_set = (wanted_set & access.team_ids) | kept
    before = {t.id for t in user.other_teams}
    if wanted_set == before:
        return False
    user.other_teams = [db.get(Team, t) for t in sorted(wanted_set)]
    return True


def email_taken(db: DB, email: str, but: str | None = None) -> bool:
    q = select(User.id).where(func.lower(User.email) == email)
    if but:
        q = q.where(User.id != but)
    return db.scalar(q) is not None


@router.get("/users")
def list_users(access: People, db: DB) -> list[dict]:
    last = dict(db.execute(select(SignInSession.user_id, func.max(SignInSession.created_at)).group_by(SignInSession.user_id)).all())
    users = db.scalars(select(User).order_by(User.is_active.desc(), func.lower(User.full_name)))
    return [user_out(u, last.get(u.id)) for u in users if in_reach(access, u)]


@router.get("/users/options")
def user_options(access: People, db: DB) -> dict:
    """The roles and teams a person can be given, for whoever manages users
    (who may not manage roles or teams themselves)."""
    reach = case({"all": 0, "managed": 1, "team": 2, "own": 3}, value=Role.scope, else_=4)
    roles = db.scalars(select(Role).order_by(Role.is_system.desc(), reach, func.lower(Role.name)))
    teams = db.scalars(select(Team).order_by(Team.is_active.desc(), func.lower(Team.name)))
    # A manager gives only the roles below theirs, in the teams they manage.
    everyone = runs_people(access)
    return {
        "roles": [{"id": r.id, "name": r.name, "description": r.description, "scope": r.scope} for r in roles if everyone or grantable(r)],
        "teams": [{"id": t.id, "name": t.name, "isActive": t.is_active} for t in teams if everyone or t.id in access.team_ids],
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(access: People, me: CurrentUser, db: DB, body: UserIn) -> dict:
    if email_taken(db, body.email):
        raise field_error("email", "Someone here already has that email.")
    managed_role(db, access, body.role_id)
    managed_team(access, body.team_id)
    check_team(db, body.team_id)
    # Their employee ID is given as they're saved (app/employee_ids.py).
    user = User(
        email=body.email,
        full_name=body.full_name,
        first_name=split_name(body.full_name)[0] or None,
        last_name=split_name(body.full_name)[1] or None,
        role_id=body.role_id,
        team_id=body.team_id,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()
    set_other_teams(db, access, user, body.other_team_ids)
    audit(db, me, "user.created", target=user.email, target_type="user", target_id=user.id)
    db.commit()
    return user_out(db.get(User, user.id))


@router.get("/users/{user_id}")
def read_user(access: People, db: DB, user_id: str) -> dict:
    user = reachable_user(db, access, user_id)
    last = db.scalar(select(func.max(SignInSession.created_at)).where(SignInSession.user_id == user.id))
    return user_out(user, last)


@router.patch("/users/{user_id}")
def update_user(access: People, me: CurrentUser, db: DB, user_id: str, body: UserPatch) -> dict:
    user = reachable_user(db, access, user_id)
    wanted = changed(body)
    for key in ("email", "full_name", "role_id", "is_active"):
        if key in wanted and wanted[key] is None:
            raise field_error(to_camel(key), "This can't be empty.")
    if wanted.get("is_active") is False and user.id == me.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't switch yourself off. Ask another admin.")
    if "email" in wanted and email_taken(db, wanted["email"], but=user.id):
        raise field_error("email", "Someone here already has that email.")
    if "role_id" in wanted:
        managed_role(db, access, wanted["role_id"])
    if "team_id" in wanted:
        managed_team(access, wanted["team_id"])
        check_team(db, wanted["team_id"], current=user.team_id)

    others = wanted.pop("other_team_ids", None)
    fields = [k for k, v in wanted.items() if getattr(user, k) != v]
    if others is not None and set_other_teams(db, access, user, others):
        fields.append("other_team_ids")
    for key in [f for f in fields if f != "other_team_ids"]:
        setattr(user, key, wanted[key])
    if "full_name" in fields:
        # Typed in one piece here: its parts follow (the person can tidy them on their profile).
        user.first_name, user.last_name = split_name(user.full_name)
        user.middle_initial = user.suffix = None
    if not fields:
        return user_out(user)
    keep_an_administrator(db)
    action = "user.updated"
    if fields == ["is_active"]:
        action = "user.switched_on" if user.is_active else "user.switched_off"
    audit(db, me, action, target=user.email, target_type="user", target_id=user.id, fields=[to_camel(f) for f in fields])
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(access: People, me: CurrentUser, db: DB, user_id: str, body: PasswordIn) -> Response:
    """A new password, set by an admin (or the person's manager). Every session the person had ends."""
    user = reachable_user(db, access, user_id)
    user.password_hash = hash_password(body.password)
    user.password_changed_at = datetime.now(UTC)
    audit(db, me, "user.password_reset", target=user.email, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- roles and permissions --------------------------------------------------------------------


def valid_scope(value: str | None) -> str | None:
    if value is not None and value not in SCOPES:
        raise ValueError("Pick whose records it reaches.")
    return value


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
    scope: str = "own"
    permissions: list[str] = Field(default_factory=list, max_length=len(ALL_PERMISSIONS))

    _scope = field_validator("scope")(valid_scope)
    _permissions = field_validator("permissions")(valid_permissions)


class RolePatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    scope: str | None = None
    permissions: list[str] | None = Field(None, max_length=len(ALL_PERMISSIONS))

    _scope = field_validator("scope")(valid_scope)
    _permissions = field_validator("permissions")(valid_permissions)


def role_out(role: Role, users: int = 0) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "scope": role.scope,
        "isSystem": role.is_system,
        "permissions": sorted(permissions_of(role)),
        "userCount": users,
    }


def role_users(db: DB) -> dict[str, int]:
    return dict(db.execute(select(User.role_id, func.count()).where(User.is_active).group_by(User.role_id)).all())


def get_role(db: DB, role_id: str) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such role.")
    return role


def name_taken(db: DB, model: type[Role] | type[Team], name: str, but: str | None = None) -> bool:
    q = select(model.id).where(func.lower(model.name) == name.lower())
    if but:
        q = q.where(model.id != but)
    return db.scalar(q) is not None


def set_grants(role: Role, permissions: list[str]) -> None:
    role.grants = [RolePermission(permission=p) for p in sorted(set(permissions))]


@router.get("/roles")
def list_roles(_: Roles, db: DB) -> dict:
    counts = role_users(db)
    # Administrator first, then by reach: every record, the team's, their own.
    reach = case({"all": 0, "managed": 1, "team": 2, "own": 3}, value=Role.scope, else_=4)
    roles = db.scalars(select(Role).order_by(Role.is_system.desc(), reach, func.lower(Role.name)))
    return {
        "roles": [role_out(r, counts.get(r.id, 0)) for r in roles],
        "catalogue": catalogue_out(),
        "scopes": [{"key": s, "label": SCOPE_LABELS[s]} for s in SCOPES],
    }


@router.get("/permissions")
def permission_catalogue(_: Roles) -> dict:
    return {"catalogue": catalogue_out(), "scopes": [{"key": s, "label": SCOPE_LABELS[s]} for s in SCOPES]}


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(_: Roles, me: CurrentUser, db: DB, body: RoleIn) -> dict:
    if name_taken(db, Role, body.name):
        raise field_error("name", "There's already a role with that name.")
    role = Role(name=body.name, description=body.description, scope=body.scope)
    set_grants(role, body.permissions)
    db.add(role)
    db.flush()
    audit(db, me, "role.created", target=role.name, target_type="role", target_id=role.id)
    db.commit()
    return role_out(role)


@router.patch("/roles/{role_id}")
def update_role(_: Roles, me: CurrentUser, db: DB, role_id: str, body: RolePatch) -> dict:
    role = get_role(db, role_id)
    wanted = changed(body)
    if role.is_system and set(wanted) - {"description"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "The Administrator role always has everything. Make a new role instead.")
    if "name" in wanted and wanted["name"] is None:
        raise field_error("name", "Give the role a name.")
    if "name" in wanted and name_taken(db, Role, wanted["name"], but=role.id):
        raise field_error("name", "There's already a role with that name.")

    fields = []
    for key in ("name", "description", "scope"):
        if key in wanted and (wanted[key] is not None or key == "description") and getattr(role, key) != wanted[key]:
            setattr(role, key, wanted[key])
            fields.append(key)
    if wanted.get("permissions") is not None and set(wanted["permissions"]) != role.permissions:
        set_grants(role, wanted["permissions"])
        fields.append("permissions")
    if fields:
        keep_an_administrator(db)
        audit(db, me, "role.updated", target=role.name, target_type="role", target_id=role.id, fields=fields)
        db.commit()
    return role_out(role, role_users(db).get(role.id, 0))


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(_: Roles, me: CurrentUser, db: DB, role_id: str) -> Response:
    role = get_role(db, role_id)
    if role.is_system:
        raise HTTPException(status.HTTP_409_CONFLICT, "The Administrator role can't be deleted.")
    holders = db.scalar(select(func.count()).select_from(User).where(User.role_id == role.id)) or 0
    if holders:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{holders} {'person has' if holders == 1 else 'people have'} this role. Give them another one first.",
        )
    audit(db, me, "role.deleted", target=role.name, target_type="role", target_id=role.id)
    db.delete(role)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- teams ------------------------------------------------------------------------------------


def _headquarters(value: list[str]) -> list[str]:
    """Each once (whatever the capitals), blanks dropped, in the order given."""
    seen: dict[str, str] = {}
    for name in (v.strip() for v in value):
        if name and name.lower() not in seen:
            seen[name.lower()] = name
    return list(seen.values())


# The offices a team works from, each a chip on the Teams page.
Headquarters = Annotated[list[Annotated[str, Field(max_length=120)]], Field(max_length=20), AfterValidator(_headquarters)]


class TeamIn(Api):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    headquarters: Headquarters = []
    # The manager over it (above its team lead).
    manager_id: str | None = Field(None, max_length=36)
    # The division it's a branch of; none: a division itself.
    parent_id: str | None = Field(None, max_length=36)


class TeamPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    headquarters: Headquarters | None = None
    is_active: bool | None = None
    manager_id: str | None = Field(None, max_length=36)
    parent_id: str | None = Field(None, max_length=36)


def team_out(team: Team, members: int = 0, db: DB | None = None) -> dict:
    manager = db.get(User, team.manager_id) if db is not None and team.manager_id else None
    return {
        "id": team.id,
        "no": team.no,
        "name": team.name,
        "description": team.description,
        "headquarters": team.headquarters or [],
        "isActive": team.is_active,
        "memberCount": members,
        "manager": {"id": manager.id, "name": manager.full_name} if manager else None,
        "shareCustomers": team.share_customers,
        "parentId": team.parent_id,
    }


def check_manager(db: DB, manager_id: str | None) -> str | None:
    """A team's manager: someone switched on whose role manages teams."""
    if manager_id is None:
        return None
    person = db.get(User, manager_id)
    if person is None or not person.is_active or person.role.scope != "managed":
        raise field_error("managerId", "Pick someone whose role manages teams (scope: the teams they manage).")
    return person.id


def check_parent(db: DB, team: Team | None, parent_id: str | None) -> str | None:
    """A division to be a branch of: one that is itself a division (one level), never the team itself,
    and not for a team that has branches of its own."""
    if parent_id is None:
        return None
    parent = db.get(Team, parent_id)
    if parent is None or (team is not None and parent.id == team.id):
        raise field_error("parentId", "Pick another division.")
    if parent.parent_id is not None:
        raise field_error("parentId", f"{parent.name} is a branch itself: pick its division.")
    if team is not None and db.scalar(select(func.count()).select_from(Team).where(Team.parent_id == team.id)):
        raise field_error("parentId", "This team has branches of its own, so it stays a division.")
    return parent.id


def team_members(db: DB) -> dict[str, int]:
    """Active people per team: those whose main team it is, and those in it as one of their others."""
    counts: dict[str, int] = {}
    for user in db.scalars(select(User).where(User.is_active)):
        for team_id in user.all_team_ids:
            counts[team_id] = counts.get(team_id, 0) + 1
    return counts


def get_team(db: DB, team_id: str) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such team.")
    return team


@router.get("/teams")
def list_teams(_: Teams, db: DB) -> list[dict]:
    counts = team_members(db)
    teams = list(db.scalars(select(Team).order_by(Team.is_active.desc(), func.lower(Team.name))))
    # Each division, then its branches under it.
    ordered = []
    for t in teams:
        if t.parent_id is None or t.parent_id not in {x.id for x in teams}:
            ordered.append(t)
            ordered.extend(b for b in teams if b.parent_id == t.id)
    return [team_out(t, counts.get(t.id, 0), db) for t in ordered]


@router.get("/teams/managers")
def team_managers(_: Teams, db: DB) -> list[dict]:
    """Who can be a team's manager: people switched on whose role manages teams."""
    people = db.scalars(select(User).join(User.role).where(User.is_active, Role.scope == "managed").order_by(func.lower(User.full_name)))
    return [{"id": u.id, "name": u.full_name} for u in people]


@router.post("/teams", status_code=status.HTTP_201_CREATED)
def create_team(_: Teams, me: CurrentUser, db: DB, body: TeamIn) -> dict:
    if name_taken(db, Team, body.name):
        raise field_error("name", "There's already a team with that name.")
    team = Team(name=body.name, description=body.description, headquarters=body.headquarters, manager_id=check_manager(db, body.manager_id), parent_id=check_parent(db, None, body.parent_id))
    db.add(team)
    db.flush()
    audit(db, me, "team.created", target=team.name, target_type="team", target_id=team.id)
    db.commit()
    return team_out(team)


@router.patch("/teams/{team_id}")
def update_team(_: Teams, me: CurrentUser, db: DB, team_id: str, body: TeamPatch) -> dict:
    team = get_team(db, team_id)
    wanted = changed(body)
    if "name" in wanted and wanted["name"] is None:
        raise field_error("name", "Give the team a name.")
    if "name" in wanted and name_taken(db, Team, wanted["name"], but=team.id):
        raise field_error("name", "There's already a team with that name.")
    if "headquarters" in wanted and wanted["headquarters"] is None:
        wanted["headquarters"] = []
    if "manager_id" in wanted:
        wanted["manager_id"] = check_manager(db, wanted["manager_id"])
    if "parent_id" in wanted:
        wanted["parent_id"] = check_parent(db, team, wanted["parent_id"])
    fields = [k for k in ("name", "description", "headquarters", "is_active", "manager_id", "parent_id") if k in wanted and getattr(team, k) != wanted[k]]
    for key in fields:
        setattr(team, key, wanted[key])
    if fields:
        action = "team.updated"
        if fields == ["is_active"]:
            action = "team.switched_on" if team.is_active else "team.switched_off"
        audit(db, me, action, target=team.name, target_type="team", target_id=team.id, fields=[to_camel(f) for f in fields])
        db.commit()
    return team_out(team, team_members(db).get(team.id, 0), db)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(_: Teams, me: CurrentUser, db: DB, team_id: str) -> Response:
    team = get_team(db, team_id)
    members = (db.scalar(select(func.count()).select_from(User).where(User.team_id == team.id)) or 0) + (db.scalar(select(func.count()).select_from(UserTeam).where(UserTeam.team_id == team.id)) or 0)
    if members:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{members} {'person is' if members == 1 else 'people are'} in this team. Move them first, or switch the team off.",
        )
    audit(db, me, "team.deleted", target=team.name, target_type="team", target_id=team.id)
    db.delete(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This team is still in use. Switch it off instead.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the audit log ----------------------------------------------------------------------------


@router.get("/audit")
def audit_log(
    _: Audit,
    db: DB,
    before: int | None = Query(None, ge=1, description="the last id of the page before"),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, max_length=64, description="an action, or its start: 'user.' for every user change"),
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
            {
                "id": e.id,
                "at": iso(e.at),
                "actor": e.actor,
                "actorId": e.actor_id,
                "action": e.action,
                "target": e.target,
                "targetType": e.target_type,
                "fields": e.fields or [],
            }
            for e in entries[:limit]
        ],
        "more": len(entries) > limit,
    }
