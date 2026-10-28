"""The org chart from Bishnoi One Platform (feature plan step 4, agreed 2026-10-28).

The company's divisions, departments and teams are kept on the Platform (one chart, edited
in the Admin Console's Organisation screen). The CRM's teams are its copy, with the same ids,
so every record here keeps pointing at the right team:

- POST /platform/organisation: the chart and where each person sits, signed by the Platform
  (kind "organisation"). Each unit is kept as a team (name, the division above it, its
  manager by email, its areas as the team's places, switched on or off); each person's main
  unit becomes their team and their other units their other teams. Teams the note doesn't
  name are left as they are. What is the CRM's own about a team (its description, customer
  sharing, retention windows) isn't touched.
- follow_pass(db, user, claims): a sign-in pass carries the person's own placing ("org"), so a
  note missed while this was out of reach doesn't matter for them.
- on_platform: once connected, teams are made and arranged on the Platform, not here.

The CRM keeps one level (divisions, and teams under them): a unit deeper down sits here under
the division at the top of its branch.
"""

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app.audit import audit
from app.models import Team, User
from app.platform_roles import PLATFORM, NoteIn, _checked, _nowhere, managed, sessions_for

router = APIRouter(prefix="/platform", tags=["platform"])
_newest: dict[str, int] = {}  # by company: when the last note taken was signed

ARRANGED_THERE = {"name", "parentId", "managerId", "headquarters", "isActive"}
ON_PLATFORM = "Divisions and teams, and who is in them, are kept in Bishnoi One: change them in the Admin Console's Organisation."


def _top(units: dict[str, dict], unit_id: str | None) -> str | None:
    """The division a unit sits under here: its parent when that is at the top, else the top of its branch."""
    parent = units.get(unit_id, {}).get("parentId") if unit_id else None
    seen = set()
    while parent and units.get(parent, {}).get("parentId") and parent not in seen:
        seen.add(parent)
        parent = units[parent]["parentId"]
    return parent


def keep_units(db, units: list[dict]) -> int:
    by_id = {str(u.get("id")): u for u in units if isinstance(u, dict) and u.get("id") and u.get("name")}
    emails = {str(u.get("manager") or "").lower() for u in by_id.values()} - {""}
    managers = {e: uid for e, uid in db.execute(select(func.lower(User.email), User.id).where(func.lower(User.email).in_(emails)))} if emails else {}
    changed = 0
    # Divisions first, so a team finds the one above it.
    for unit_id, u in sorted(by_id.items(), key=lambda kv: _top(by_id, kv[0]) is not None):
        team = db.get(Team, unit_id)
        name = str(u["name"]).strip()[:80]
        clash = db.scalar(select(Team.id).where(func.lower(Team.name) == name.lower(), Team.id != unit_id))
        if clash:  # the CRM's names are unique: keep its own name until the clash is resolved
            name = team.name if team else f"{name} ({unit_id[:4]})"
        wanted = {
            "name": name,
            "parent_id": _top(by_id, unit_id),
            "manager_id": managers.get(str(u.get("manager") or "").lower()),
            "headquarters": [str(a)[:80] for a in u.get("areas") or []],
            "is_active": bool(u.get("active", True)),
        }
        if team is None:
            team = Team(id=unit_id, **wanted)
            db.add(team)
            db.flush()
            audit(db, PLATFORM, "team.created", target=team.name, target_type="team", target_id=team.id, fields=["from the Platform"])
            changed += 1
            continue
        fields = [k for k, v in wanted.items() if getattr(team, k) != v]
        for k in fields:
            setattr(team, k, wanted[k])
        if fields:
            audit(db, PLATFORM, "team.updated", target=team.name, target_type="team", target_id=team.id, fields=fields)
            changed += 1
    db.flush()
    return changed


def place(db, user: User, unit_id: str | None, others: list[str] | None) -> bool:
    """Their team and other teams, as the Platform has them (teams this CRM doesn't have are skipped)."""
    fields = []
    if unit_id and unit_id != user.team_id and db.get(Team, unit_id) is not None:
        user.team_id = unit_id
        fields.append("team")
    if others is not None:
        wanted = [t for t in (db.get(Team, str(i)) for i in others) if t is not None and t.id != user.team_id]
        if {t.id for t in wanted} != {t.id for t in user.other_teams}:
            user.other_teams = wanted
            fields.append("otherTeams")
    if fields:
        audit(db, PLATFORM, "user.updated", target=user.email, target_type="user", target_id=user.id, fields=fields)
    return bool(fields)


def follow_pass(db, user: User, claims: dict) -> None:
    org = claims.get("org")
    if isinstance(org, dict):
        unit = org.get("unit") if isinstance(org.get("unit"), dict) else {}
        place(db, user, unit.get("id"), org.get("otherUnits") if isinstance(org.get("otherUnits"), list) else None)


@router.post("/organisation", status_code=status.HTTP_204_NO_CONTENT)
def take_chart(body: NoteIn, request: Request) -> Response:
    claims = _checked(request.app.state.settings, body.token, "organisation")
    if claims is None or claims["iat"] < _newest.get(claims["slug"], 0):
        raise _nowhere()
    with sessions_for(request, claims["slug"])() as db:
        keep_units(db, claims.get("units") or [])
        for p in claims.get("people") or []:
            if not isinstance(p, dict):
                continue
            user = db.scalar(select(User).where(func.lower(User.email) == str(p.get("email") or "").strip().lower()))
            if user is not None:
                place(db, user, p.get("unit"), p.get("otherUnits") if isinstance(p.get("otherUnits"), list) else None)
        db.commit()
    _newest[claims["slug"]] = claims["iat"]
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def on_platform(request: Request) -> None:
    """Making, removing or arranging teams here, and moving people between them: refused once the
    Platform keeps the chart. A team's own CRM settings (description, sharing, retention) still change here."""
    if not managed(request.app.state.settings):
        return
    if request.method == "PATCH":
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 (not JSON: let the endpoint answer it)
            return
        keys = ARRANGED_THERE if "/teams/" in request.url.path else {"teamId", "otherTeamIds"}
        if not isinstance(body, dict) or not keys.intersection(body):
            return
    raise HTTPException(status.HTTP_409_CONFLICT, ON_PLATFORM)
