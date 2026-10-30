"""Roles from Bishnoi One Platform (decided 2026-10-23: access in one place, step R1).

A company's roles are made on the Platform, for every module, and each person
has one role there. This application still declares its permissions
(app/permissions.py) and checks every request against its own role tables; the
Platform tells it the roles, and who holds which:

- GET  /platform/catalog: what this application declares, for the Platform's
  roles screen.
- POST /platform/roles: the company's roles and who holds them, signed by the
  Platform (kind "roles"). Each role is kept by its name; each person's role is
  set by their email. Only a note signed by the Platform, for this application,
  not older than the last one taken, is taken; anything else is answered as if
  the address didn't exist.
- POST /platform/roles/export: the roles here today, for the Platform to bring
  in the first time (asked with a note it signed, kind "roles-ask").
- keep(db, spec): one role as the Platform has it; each sign-in pass carries the
  person's (roleDef), so a note missed while this was out of reach doesn't matter.

The Administrator role stays this application's own and is never changed: a role
with everything on the Platform is the Administrator here.

The same in every Bishnoi One application but for the part marked below.
"""

import base64
import json
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select

from app import platform_pass
from app.audit import audit
from app.models import Role, RolePermission, User, SignInSession
from app.permissions import ALL_PERMISSIONS, catalogue_out

# ---- This application ----------------------------------------------------------------------
APP_KEY = "crm"  # this application's key on the Platform

def sessions_for(request: Request, slug: str):
    """The company's database, once it's known it may use this application."""
    from app.deps import open_company

    return open_company(request, slug).sessions


def scopes_out() -> list[dict]:
    from app.permissions import SCOPE_LABELS, SCOPES

    return [{"key": s, "label": SCOPE_LABELS[s]} for s in SCOPES]


def scope_of(role: Role) -> str | None:
    return role.scope


def set_scope(role: Role, scope) -> bool:
    from app.permissions import SCOPES

    if scope in SCOPES and role.scope != scope:
        role.scope = scope
        return True
    return False


def give(user: User, role: Role) -> None:
    user.role_id = role.id
# --------------------------------------------------------------------------------------------

PLATFORM = "Bishnoi One Platform"  # who the audit log says made the change
router = APIRouter(prefix="/platform", tags=["platform"])
_newest: dict[str, int] = {}  # by company: when the last note taken was signed


class NoteIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    token: str = Field(alias="pass", min_length=20, max_length=500_000)


def _b64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _checked(settings, token: str, kind: str) -> dict | None:
    """The note's claims, once the Platform's signature, this application, its kind and its time are right."""
    try:
        head_b64, body_b64, sig_b64 = token.split(".")
        body = json.loads(_b64(body_b64))
    except (ValueError, TypeError):
        return None
    for key in (platform_pass.public_key(settings), platform_pass.public_key(settings, again=True)):
        if not key:
            continue
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(key)).verify(_b64(sig_b64), f"{head_b64}.{body_b64}".encode())
            break
        except (InvalidSignature, ValueError):
            continue
    else:
        return None
    if body.get("iss") not in platform_pass.ISSUERS or body.get("aud") != APP_KEY or body.get("kind") != kind:
        return None
    if not isinstance(body.get("exp"), int) or not isinstance(body.get("iat"), int) or body["exp"] + platform_pass.LEEWAY < time.time():
        return None
    if not isinstance(body.get("slug"), str) or not body["slug"]:
        return None
    return body


def _nowhere() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")


@router.get("/catalog")
def catalog() -> dict:
    """What a role can hold here, as the Platform's roles screen offers it."""
    return {"app": APP_KEY, "areas": catalogue_out(), "scopes": scopes_out()}


def administrator(db) -> Role | None:
    return db.scalar(select(Role).where(Role.is_system))


def keep(db, spec: dict) -> Role | None:
    """One role as the Platform has it, kept here by its name (made if it's new)."""
    name = str(spec.get("name") or "").strip()[:80]
    if not name:
        return None
    if spec.get("admin"):
        return administrator(db)
    role = db.scalar(select(Role).where(func.lower(Role.name) == name.lower()))
    if role is not None and role.is_system:
        return role
    made = role is None
    if made:
        role = Role(name=name)
        db.add(role)
    fields = []
    description = spec.get("description") or None
    if role.description != description:
        role.description = description
        fields.append("description")
    if set_scope(role, spec.get("scope")):
        fields.append("scope")
    wanted = sorted({p for p in spec.get("permissions") or [] if p in ALL_PERMISSIONS})
    if made or set(wanted) != {g.permission for g in role.grants}:
        role.grants = [RolePermission(permission=p) for p in wanted]
        fields.append("permissions")
    if made or fields:
        db.flush()
        audit(db, PLATFORM, "role.created" if made else "role.updated", target=role.name, target_type="role", target_id=role.id, fields=[] if made else fields)
    return role


@router.post("/roles", status_code=status.HTTP_204_NO_CONTENT)
def take_roles(body: NoteIn, request: Request) -> Response:
    claims = _checked(request.app.state.settings, body.token, "roles")
    if claims is None or claims["iat"] < _newest.get(claims["slug"], 0):
        raise _nowhere()
    with sessions_for(request, claims["slug"])() as db:
        roles: dict[str, Role] = {}
        for spec in claims.get("roles") or []:
            if isinstance(spec, dict) and (role := keep(db, spec)) is not None:
                roles[str(spec["name"]).strip().lower()] = role
        boss = administrator(db)
        for p in claims.get("people") or []:
            if not isinstance(p, dict):
                continue
            role = boss if p.get("admin") else roles.get(str(p.get("role") or "").strip().lower())
            user = db.scalar(select(User).where(func.lower(User.email) == str(p.get("email") or "").strip().lower()))
            if role is not None and user is not None and user.role_id != role.id:
                give(user, role)
                audit(db, PLATFORM, "user.updated", target=user.email, target_type="user", target_id=user.id, fields=["role"])
            # Their details as the Platform keeps them (2026-10-30): an employee ID, a licence number.
            if user is not None and isinstance(p.get("details"), dict):
                moved = [col for key, col in DETAILS.items() if key in p["details"] and hasattr(user, col) and getattr(user, col) != p["details"][key]]
                for col in moved:
                    setattr(user, col, next(p["details"][k] for k, c in DETAILS.items() if c == col))
                if moved:
                    audit(db, PLATFORM, "user.updated", target=user.email, target_type="user", target_id=user.id, fields=moved)
            # Switched off (or on) on the Platform: the same here (R2).
            if user is not None and follow_status(db, user, p.get("active")):
                audit(db, PLATFORM, "user.updated", target=user.email, target_type="user", target_id=user.id, fields=["isActive"])
        db.commit()
    _newest[claims["slug"]] = claims["iat"]
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/roles/export")
def export_roles(body: NoteIn, request: Request) -> dict:
    claims = _checked(request.app.state.settings, body.token, "roles-ask")
    if claims is None:
        raise _nowhere()
    with sessions_for(request, claims["slug"])() as db:
        return {
            "roles": [
                {"name": r.name, "description": r.description, "scope": scope_of(r), "permissions": sorted(g.permission for g in r.grants), "isSystem": r.is_system}
                for r in db.scalars(select(Role).order_by(Role.name))
            ]
        }


# ---- R2 (decided 2026-10-26): the Platform keeps people, roles and passwords ----------------
# Once this application is connected to Bishnoi One Platform (PLATFORM_API_URL), a person is added,
# given their role, given a password and switched off only there (the one app's People), and signs
# in only with their Bishnoi One account. This application keeps a copy of the roles to check every
# request against (taken from the Platform, never edited here) and what is its own about a person.
# Not connected (a standalone install, the tests): everything here works as before.

PLATFORM_OWNS = {"fullName", "email", "roleId", "isActive", "password",
                 # What the app keeps of its own about a person is kept on the Platform too since 2026-10-30.
                 "employeeId", "licenseNo", "calendarOn"}
# The Platform's names for those details, and the column each is kept in here (an app has the ones it uses).
DETAILS = {"employeeId": "employee_id", "licenseNo": "license_no", "calendarOn": "calendar_on"}
ON_PLATFORM = "People, their roles and passwords, and switching people off are kept in Bishnoi One: change it in People."


def managed(settings) -> bool:
    return bool(getattr(settings, "platform_api_url", None))


async def kept_on_platform(request: Request) -> None:
    """On adding people, setting passwords and changing roles here: refused once the Platform keeps them.
    A change to what is this application's own about a person (a licence number, a team) still goes."""
    if not managed(request.app.state.settings):
        return
    if request.method == "PATCH" and "/users/" in request.url.path:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 (not JSON: let the endpoint answer it)
            return
        if not isinstance(body, dict) or not PLATFORM_OWNS.intersection(body):
            return
    raise HTTPException(status.HTTP_409_CONFLICT, ON_PLATFORM)


async def signs_in_here(request: Request) -> None:
    """This application's own password sign-in: closed once people sign in with their Bishnoi One account."""
    if managed(request.app.state.settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in with your Bishnoi One account.")


def follow_status(db, user: User, active) -> bool:
    """Switched off (or on) on the Platform: the same here, and switched off ends their sessions at once."""
    if active is None or bool(active) == user.is_active:
        return False
    user.is_active = bool(active)
    if not user.is_active:
        db.execute(delete(SignInSession).where(SignInSession.user_id == user.id))
    return True


# ---- View as (decided 2026-10-26) ------------------------------------------------------------
# An administrator sees this application exactly as one of its people does: their permissions,
# their scope, their records. Read-only: nothing can be changed while viewing. Asked for with the
# X-Bishnoi-View-As header (a person's id), honoured only for someone who manages users here.

VIEW_AS_HEADER = "x-bishnoi-view-as"
READ_ONLY = {"GET", "HEAD", "OPTIONS"}


def may_view_as(user: User) -> bool:
    from app.access import permissions_of

    return "admin.users" in permissions_of(user.role)


def viewed_as(request: Request, db, user: User) -> User:
    """The person to answer as: `user`, or whom they're viewing as (see above)."""
    wanted = request.headers.get(VIEW_AS_HEADER)
    if not wanted or wanted == user.id:
        return user
    if not may_view_as(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can view as someone else.")
    other = db.get(User, wanted)
    if other is None or not other.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That person isn't here, or is switched off.")
    # /graphql is a read-only schema (graphql_core.graphql_router has no mutations).
    # Pages use POST for queries, so the HTTP verb alone cannot identify a write.
    reading_graphql = request.method == "POST" and request.url.path.rstrip("/") == "/graphql"
    if request.method not in READ_ONLY and not reading_graphql and not request.url.path.endswith(("/auth/logout", "/auth/view-as")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You're viewing as {other.full_name}: changes are off. Stop viewing to make changes.")
    request.state.viewed_by = user
    return other


def people_by_role(db) -> list[dict]:
    """Everyone switched on, by role: the role that may do most first, down to the one that may do least."""
    from app.access import permissions_of

    groups: dict[str, dict] = {}
    for u in db.scalars(select(User).where(User.is_active).order_by(func.lower(User.full_name))):
        r = u.role
        g = groups.setdefault(r.id, {"role": r.name, "size": len(permissions_of(r)), "people": []})
        g["people"].append({"id": u.id, "fullName": u.full_name, "email": u.email})
    return sorted(groups.values(), key=lambda g: (-g["size"], g["role"].lower()))
