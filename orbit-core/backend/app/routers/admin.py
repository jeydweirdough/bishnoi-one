"""Settings: people, their assignments, the role x module matrix, and teams.

Every change that could remove the last person able to manage settings is
checked before commit and refused, so the system can't be locked out.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.access import is_on, owners, settings_managers, works_elsewhere
from app.audit import audit
from app.catalogue import can_grant, catalogue, modules_by_key
from app.deps import DB, CurrentUser, require_owner, require_recovery, require_settings
from app.models import (
    Assignment,
    AuditEntry,
    Division,
    Headquarters,
    LocalCredential,
    Membership,
    Position,
    Profile,
    Role,
    RolePermission,
    Subdivision,
)
from app.modules import (
    ACTIONS,
    ALL_MODULES,
    BY_KEY,
    MANAGE,
    ORDER_STEPS,
    RECOVER,
    SALES_ACTIONS,
    SETTINGS,
    SETTINGS_ACTIONS,
)
from app.price_book import start_selling
from app.routers.org import org_tree
from app.routers.photos import photo_times
from app.schemas import (
    PositionIn,
    PositionPatch,
    AssignmentIn,
    DepartmentIn,
    DepartmentPatch,
    MatrixIn,
    NameIn,
    NamePatch,
    RoleIn,
    RolePatch,
    UserIn,
    UserPatch,
)
from app.scope import is_code, slugify
from app.security import hash_password
from app.tenancy import org_get


router = APIRouter(prefix="/admin", tags=["settings"], dependencies=[Depends(require_recovery)])
# Everything under /admin is reachable by a Developer Admin unless it says
# otherwise: `settings` marks the routes that stay an Admin's alone,
# because they decide what roles mean and how the company is shaped.
settings = Depends(require_settings)


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def invalid(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def commit_keeping_an_admin(db: Session) -> None:
    # SQLite's single writer makes this check-then-commit safe. On Supabase
    # Postgres, run it SERIALIZABLE (or lock the admins' rows) so two admins
    # removing each other at the same moment can't both pass.
    db.flush()
    if not settings_managers(db):
        db.rollback()
        raise conflict("That would leave nobody able to manage settings. Give someone else the Admin role first.")
    if not owners(db):
        db.rollback()
        raise conflict("That would leave the company with no owner. Make someone else an owner first.")
    db.commit()


# --- people ----------------------------------------------------------------------


def scope_label(a: Assignment, names: dict) -> str:
    if a.division_code is None:
        return "All divisions"
    division = names["divisions"].get(a.division_code, a.division_code)
    if a.subdivision_code is None:
        return f"{division} · all teams"
    return f"{division} · {names['teams'].get((a.division_code, a.subdivision_code), a.subdivision_code)}"


def name_lookup(db: Session) -> dict:
    return {
        "divisions": dict(db.execute(select(Division.code, Division.name)).all()),
        "teams": {(d, c): n for d, c, n in db.execute(select(Subdivision.division_code, Subdivision.code, Subdivision.name))},
        "roles": dict(db.execute(select(Role.key, Role.name)).all()),
        "modules": {m.key: m.name for m in catalogue(db)},
    }


def assignment_out(a: Assignment, names: dict) -> dict:
    module_name = "All modules" if a.module_key == ALL_MODULES else names["modules"].get(a.module_key, "Settings")
    return {
        "id": a.id,
        "roleKey": a.role_key,
        "roleName": names["roles"].get(a.role_key, a.role_key),
        "moduleKey": a.module_key,
        "moduleName": module_name,
        "divisionCode": a.division_code,
        "subdivisionCode": a.subdivision_code,
        "scopeLabel": scope_label(a, names),
    }


def user_out(user: Profile, membership: Membership, names: dict, photo_at: str | None = None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "fullName": user.full_name,
        "photoAt": photo_at,
        "isActive": is_on(user, membership),
        "isOwner": membership.is_owner,
        "createdAt": membership.created_at.isoformat(),
        "assignments": [assignment_out(a, names) for a in user.assignments],
    }


def people_here():
    """The company's people with their membership. People of other companies don't exist here."""
    return select(Profile, Membership).join(Membership, Membership.user_id == Profile.id)


def get_user(db: Session, user_id: str) -> tuple[Profile, Membership]:
    row = db.execute(people_here().where(Profile.id == user_id)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such person.")
    user, membership = row
    return user, membership


def build_assignment(db: Session, user_id: str, body: AssignmentIn) -> Assignment:
    if org_get(db, Role, body.role_key) is None:
        raise invalid("Pick a role.")
    module = body.module_key
    if module not in (ALL_MODULES, SETTINGS) and module not in modules_by_key(db):
        raise invalid("Pick a module.")
    division, team = body.division_code, body.subdivision_code
    if team and not division:
        raise invalid("A team is always picked inside its division.")
    if division and org_get(db, Division, division) is None:
        raise invalid("Pick a division.")
    if team and org_get(db, Subdivision, division, team) is None:
        raise invalid("That team isn't in that division.")
    if module in BY_KEY and not BY_KEY[module].spans_divisions and division not in (None, module):
        raise invalid(f"{BY_KEY[module].name} only has its own division's records. Pick one of its teams.")
    reaches = BY_KEY[module].reaches if module in BY_KEY else None
    if division and reaches is not None and division not in reaches:
        names = ", ".join(BY_KEY[d].name for d in reaches)
        raise invalid(f"{BY_KEY[module].name} only reaches {names}.")
    if module == SETTINGS and (division or team):
        # A department's own admin: the settings screens, over one department.
        # A department is the smallest unit this comes in -- running a
        # department is running the teams inside it, so a grant limited to one
        # of those teams would leave an admin who cannot see their own people.
        if team:
            raise invalid("Settings reach a whole department, not one of its teams.")
        granted = set(
            db.scalars(
                select(RolePermission.action).where(
                    RolePermission.role_key == body.role_key,
                    RolePermission.module_key == SETTINGS,
                )
            )
        )
        # Recovery reaches the company record, its accounts and the log. None of
        # that belongs to one department, and it is the way back in when
        # everything is broken, so it is company-wide or nothing.
        if RECOVER in granted:
            raise invalid("Technical recovery reaches the whole company, so it can't be limited to a department.")
        if MANAGE not in granted:
            raise invalid("That role doesn't run settings, so limiting it to a department would grant nothing.")

    exists = db.scalar(
        select(Assignment).where(
            Assignment.user_id == user_id,
            Assignment.role_key == body.role_key,
            Assignment.module_key == module,
            Assignment.division_code.is_(division) if division is None else Assignment.division_code == division,
            Assignment.subdivision_code.is_(team) if team is None else Assignment.subdivision_code == team,
        )
    )
    if exists:
        raise conflict("They already have that.")
    return Assignment(user_id=user_id, role_key=body.role_key, module_key=module, division_code=division, subdivision_code=team)


def user_view(db: Session, user_id: str) -> dict:
    db.expire_all()
    user, membership = db.execute(
        people_here().where(Profile.id == user_id).options(selectinload(Profile.assignments))
    ).one()
    return user_out(user, membership, name_lookup(db), photo_times(db, [user.id]).get(user.id))


@router.get("/users")
def list_users(db: DB) -> list[dict]:
    names = name_lookup(db)
    rows = db.execute(people_here().options(selectinload(Profile.assignments)).order_by(func.lower(Profile.full_name))).all()
    photos = photo_times(db, [u.id for u, _ in rows])
    return [user_out(u, m, names, photos.get(u.id)) for u, m in rows]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(body: UserIn, db: DB, me: CurrentUser) -> dict:
    email = body.email.lower()
    user = db.scalar(select(Profile).where(Profile.email == email))
    existing = user is not None
    if existing:
        if db.scalar(select(Membership).where(Membership.user_id == user.id)) is not None:
            raise conflict("Someone already has that email.")
        # They already have an account through another company: they join this
        # one and keep signing in with their own password, which this
        # company's admins can't see or set.
    else:
        user = Profile(email=email, full_name=body.full_name)
        db.add(user)
        db.flush()
        db.add(LocalCredential(user_id=user.id, password_hash=hash_password(body.password)))
    db.add(Membership(user_id=user.id))
    db.flush()
    for a in body.assignments:
        db.add(build_assignment(db, user.id, a))
        db.flush()
    db.commit()
    audit(db, me, "person.added" if existing else "person.created", email)
    return {**user_view(db, user.id), "existingAccount": existing}


@router.get("/users/{user_id}")
def read_user(user_id: str, db: DB) -> dict:
    get_user(db, user_id)
    return user_view(db, user_id)


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserPatch, db: DB, me: CurrentUser) -> dict:
    user, membership = get_user(db, user_id)
    if body.is_active is False and user.id == me.id:
        raise conflict("You can't switch off your own account.")
    # A person's name and password are theirs across every company they're in,
    # so one company's admins can't change them for the others.
    if (body.full_name is not None or body.password is not None) and works_elsewhere(db, user.id):
        raise conflict("This person also works in another company, so only they can change their name or password.")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_active is not None:
        membership.status = "active" if body.is_active else "suspended"
    if "position_id" in body.model_fields_set:
        # Recorded, never consulted. Clearing it is "" or null, because a
        # company that does not use positions should not have to invent one.
        membership.position_id = position_or_none(db, body.position_id)
    if body.password is not None:
        credential = db.get(LocalCredential, user.id)
        if credential is None:
            db.add(LocalCredential(user_id=user.id, password_hash=hash_password(body.password)))
        else:
            credential.password_hash = hash_password(body.password)
    commit_keeping_an_admin(db)
    audit(db, me, "person.updated", user.email, body.model_fields_set)
    return user_view(db, user_id)


@router.post("/users/{user_id}/assignments", status_code=status.HTTP_201_CREATED)
def add_assignment(user_id: str, body: AssignmentIn, db: DB, me: CurrentUser) -> dict:
    user, _ = get_user(db, user_id)
    db.add(build_assignment(db, user.id, body))
    db.commit()
    audit(db, me, "assignment.added", f"{user.email}: {body.role_key} in {body.module_key}")
    return user_view(db, user_id)


@router.delete("/assignments/{assignment_id}")
def remove_assignment(assignment_id: str, db: DB, me: CurrentUser) -> dict:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Already removed.")
    user_id = assignment.user_id
    db.delete(assignment)
    commit_keeping_an_admin(db)
    audit(db, me, "assignment.removed", assignment_id)
    return user_view(db, user_id)


# --- roles and the permission matrix ---------------------------------------------


def matrix_out(db: Session) -> dict:
    counts = dict(db.execute(select(Assignment.role_key, func.count()).group_by(Assignment.role_key)).all())
    roles = db.scalars(select(Role).order_by(Role.sort_order, Role.name)).all()
    permissions: dict[str, dict[str, list[str]]] = {r.key: {} for r in roles}
    for p in db.scalars(select(RolePermission)):
        permissions.setdefault(p.role_key, {}).setdefault(p.module_key, []).append(p.action)
    for by_module in permissions.values():
        for actions in by_module.values():
            actions.sort(key=lambda a: (ACTIONS + (MANAGE, RECOVER)).index(a))
    return {
        "roles": [
            {"key": r.key, "name": r.name, "description": r.description, "assignmentCount": counts.get(r.key, 0)}
            for r in roles
        ],
        "modules": [
            {
                "key": m.key,
                "name": m.name,
                "kind": m.kind.value,
                "built": m.built,
                "actions": list(m.actions),
                "reaches": list(m.reaches) if m.reaches is not None else None,
            }
            for m in catalogue(db)
        ],
        "actions": list(SALES_ACTIONS),
        # Settings is not one switch: running the company and keeping it
        # working are different jobs, so the role screen offers both.
        "settingsActions": [
            {"action": action, "label": label, "hint": hint} for action, label, hint in SETTINGS_ACTIONS
        ],
        # The Orders module's steps, grouped as the role screen shows them.
        "orderSteps": [
            {"group": group, "steps": [{"action": key, "label": label} for key, label in steps]} for group, steps in ORDER_STEPS
        ],
        "permissions": permissions,
    }


@router.get("/roles")
def roles(db: DB) -> dict:
    return matrix_out(db)


@router.put("/permissions", dependencies=[settings])
def replace_permissions(body: MatrixIn, db: DB, me: CurrentUser) -> dict:
    known = set(db.scalars(select(Role.key)))
    modules = modules_by_key(db)
    for role_key, by_module in body.permissions.items():
        if role_key not in known:
            raise invalid(f"Unknown role: {role_key}")
        for module_key, actions in by_module.items():
            for action in actions:
                if not can_grant(modules, module_key, action):
                    raise invalid(f"{action} isn't something you can grant in {module_key}.")
            if actions and module_key != SETTINGS and "view" not in actions:
                raise invalid(f"Anyone who can {actions[0]} in {modules[module_key].name} must also be able to view it.")

    for role_key, by_module in body.permissions.items():
        db.execute(RolePermission.__table__.delete().where(RolePermission.role_key == role_key))
        for module_key, actions in by_module.items():
            for action in set(actions):
                db.add(RolePermission(role_key=role_key, module_key=module_key, action=action))
    commit_keeping_an_admin(db)
    audit(db, me, "roles.permissions_changed", ", ".join(sorted(body.permissions)))
    return matrix_out(db)


@router.post("/roles", status_code=status.HTTP_201_CREATED, dependencies=[settings])
def create_role(body: RoleIn, db: DB) -> dict:
    key = slugify(body.name).replace("-", "_")
    if not key:
        raise invalid("Give the role a name with letters or numbers.")
    if org_get(db, Role, key) or db.scalar(select(Role).where(func.lower(Role.name) == body.name.casefold())):
        raise conflict("There's already a role with that name.")
    last = db.scalar(select(func.max(Role.sort_order))) or 0
    db.add(Role(key=key, name=body.name, description=body.description, sort_order=last + 1))
    db.commit()
    return matrix_out(db)


@router.patch("/roles/{role_key}", dependencies=[settings])
def update_role(role_key: str, body: RolePatch, db: DB) -> dict:
    role = org_get(db, Role, role_key)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such role.")
    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    db.commit()
    return matrix_out(db)


@router.delete("/roles/{role_key}", dependencies=[settings])
def delete_role(role_key: str, db: DB) -> dict:
    role = org_get(db, Role, role_key)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such role.")
    in_use = db.scalar(select(func.count()).select_from(Assignment).where(Assignment.role_key == role_key))
    if in_use:
        raise conflict(f"{in_use} assignment(s) still use this role. Move those people to another role first.")
    db.delete(role)
    commit_keeping_an_admin(db)
    return matrix_out(db)


# --- teams and headquarters --------------------------------------------------------


def teams_out(db: Session) -> dict:
    return {"divisions": org_tree(db)}


def new_code(name: str) -> str:
    code = slugify(name)
    if not is_code(code):
        raise invalid("Give it a name with letters or numbers.")
    return code[:40]


@router.put("/users/{user_id}/owner", dependencies=[Depends(require_owner)])
def set_owner(user_id: str, keep: bool, db: DB, me: CurrentUser) -> dict:
    """Trust someone else with the company, or step back from it yourself.

    Only an owner may do this: it is the one thing an Admin cannot give
    themselves by editing roles. A company never runs out of owners, so the last
    one cannot step back until they have named someone else."""
    user, membership = get_user(db, user_id)
    if not keep and len([u for u in owners(db) if u != user_id]) == 0:
        raise conflict("Somebody has to own the company. Make someone else an owner first.")
    if keep and membership.status != "active":
        raise invalid("They would have to be switched back on first.")
    membership.is_owner = keep
    db.commit()
    audit(db, me, "owner.granted" if keep else "owner.removed", user.email)
    return user_view(db, user_id)


@router.post("/departments", status_code=status.HTTP_201_CREATED, dependencies=[settings])
def add_department(body: DepartmentIn, db: DB, me: CurrentUser) -> dict:
    """A division of the company's own. A department holds teams and people and
    can be granted in roles, but brings no screens; a sales one also gets the
    sales workspace, and the rules a division needs before it can quote.

    Either starts with one team, because people are always assigned to a team
    inside a division."""
    kind = body.kind or "department"
    what = "sales division" if kind == "sales" else "department"
    code = new_code(body.name)
    if org_get(db, Division, code) is not None:
        raise conflict("There's already a division with that name.")
    last = db.scalar(select(func.max(Division.sort_order))) or 0
    db.add(Division(code=code, name=body.name, kind=kind, icon=body.icon, sort_order=last + 1))
    db.add(Subdivision(division_code=code, code="general", name="General", sort_order=1))
    db.flush()
    if kind == "sales":
        start_selling(db, code)
    db.commit()
    audit(db, me, f"{what.replace(' ', '_')}.added", code)
    return teams_out(db)


@router.patch("/departments/{code}", dependencies=[settings])
def update_department(code: str, body: DepartmentPatch, db: DB, me: CurrentUser) -> dict:
    division = org_get(db, Division, code)
    if division is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such department.")
    if body.is_active is not None and code in BY_KEY:
        raise invalid(f"{division.name} comes with Orbit's modules, so it can't be switched off.")
    if body.name is not None:
        division.name = body.name
    if body.icon is not None:
        division.icon = body.icon
    if body.is_active is not None:
        division.is_active = body.is_active
    db.commit()
    audit(db, me, "department.updated", code, body.model_fields_set)
    return teams_out(db)


@router.post("/teams/{division_code}", status_code=status.HTTP_201_CREATED, dependencies=[settings])
def add_team(division_code: str, body: NameIn, db: DB, me: CurrentUser) -> dict:
    if org_get(db, Division, division_code) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such division.")
    code = new_code(body.name)
    if org_get(db, Subdivision, division_code, code):
        raise conflict("That division already has a team with that name.")
    last = db.scalar(select(func.max(Subdivision.sort_order)).where(Subdivision.division_code == division_code)) or 0
    db.add(Subdivision(division_code=division_code, code=code, name=body.name, sort_order=last + 1))
    db.commit()
    audit(db, me, "team.added", f"{division_code}/{code}")
    return teams_out(db)


@router.patch("/teams/{division_code}/{team_code}", dependencies=[settings])
def update_team(division_code: str, team_code: str, body: NamePatch, db: DB, me: CurrentUser) -> dict:
    team = org_get(db, Subdivision, division_code, team_code)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such team.")
    if body.name is not None:
        team.name = body.name
    if body.is_active is not None:
        team.is_active = body.is_active
    db.commit()
    audit(db, me, "team.updated", f"{division_code}/{team_code}", body.model_fields_set)
    return teams_out(db)


@router.post("/teams/{division_code}/{team_code}/headquarters", status_code=status.HTTP_201_CREATED, dependencies=[settings])
def add_headquarters(division_code: str, team_code: str, body: NameIn, db: DB) -> dict:
    if org_get(db, Subdivision, division_code, team_code) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such team.")
    code = new_code(body.name)
    if org_get(db, Headquarters, division_code, team_code, code):
        raise conflict("This team already has that headquarters.")
    db.add(Headquarters(division_code=division_code, subdivision_code=team_code, code=code, name=body.name))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("Couldn't add that headquarters.") from exc
    return teams_out(db)


@router.patch("/teams/{division_code}/{team_code}/headquarters/{hq_code}", dependencies=[settings])
def update_headquarters(division_code: str, team_code: str, hq_code: str, body: NamePatch, db: DB) -> dict:
    hq = org_get(db, Headquarters, division_code, team_code, hq_code)
    if hq is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such headquarters.")
    if body.name is not None:
        hq.name = body.name
    if body.is_active is not None:
        hq.is_active = body.is_active
    db.commit()
    return teams_out(db)


# --- the audit log ---------------------------------------------------------------------


@router.get("/audit")
def audit_log(db: DB, before: datetime | None = None, limit: int = Query(50, ge=1, le=200)) -> dict:
    """Newest first. Pass the last entry's `at` as `before` for the next page."""
    stmt = select(AuditEntry).order_by(AuditEntry.at.desc(), AuditEntry.id.desc()).limit(limit)
    if before is not None:
        stmt = stmt.where(AuditEntry.at < before)
    entries = db.scalars(stmt).all()
    return {
        "items": [
            {"id": e.id, "at": e.at.isoformat(), "actor": e.actor, "action": e.action, "target": e.target, "fields": e.fields}
            for e in entries
        ],
        "more": len(entries) == limit,
    }


def position_or_none(db: Session, position_id: str | None) -> str | None:
    """The position they hold, checked. There is no foreign key on the column
    (see migration 0028), so the check lives here."""
    if not position_id:
        return None
    position = db.get(Position, position_id)
    if position is None or not position.is_active:
        raise invalid("Pick a position that's switched on.")
    return position.id


def position_out(p: Position) -> dict:
    return {"id": p.id, "title": p.title, "divisionCode": p.division_code, "isActive": p.is_active}


@router.get("/positions")
def list_positions(db: DB) -> dict:
    """Every job title this company names. A title, and the department that
    named it -- nothing about permissions, which are roles."""
    rows = db.scalars(select(Position).order_by(Position.title))
    return {"positions": [position_out(p) for p in rows]}


@router.post("/positions", status_code=status.HTTP_201_CREATED, dependencies=[settings])
def create_position(body: PositionIn, db: DB, me: CurrentUser) -> dict:
    if body.division_code and org_get(db, Division, body.division_code) is None:
        raise invalid("Pick a department.")
    if db.scalar(
        select(Position).where(
            func.lower(Position.title) == body.title.casefold(),
            Position.division_code.is_(None) if body.division_code is None else Position.division_code == body.division_code,
        )
    ):
        raise conflict("That department already has a position with that title.")
    position = Position(title=body.title, division_code=body.division_code)
    db.add(position)
    db.commit()
    audit(db, me, "position.created", body.title)
    return position_out(position)


@router.patch("/positions/{position_id}", dependencies=[settings])
def update_position(position_id: str, body: PositionPatch, db: DB, me: CurrentUser) -> dict:
    position = db.get(Position, position_id)
    if position is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such position.")
    if body.title is not None:
        position.title = body.title
    # Switched off, never deleted: a title somebody held should keep its name in
    # the records of the people who held it.
    if body.is_active is not None:
        position.is_active = body.is_active
    db.commit()
    audit(db, me, "position.updated", position.title, body.model_fields_set)
    return position_out(position)
