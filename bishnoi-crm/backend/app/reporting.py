"""Whose records a person reaches, from the links between people (2026-11-03).

The platform keeps who reports to whom (Employees: Reports to, Assistant to) and sends it here. A manager reaches
the people who report to them and, through those, everyone below, to any depth. An assistant reaches what the one they
assist reaches, and does what their own role allows. Departments, divisions and teams no longer decide it.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.models import User

ORDER = {"own": 0, "team": 1, "managed": 2, "all": 3}


def below(db: Session, ids: set[str]) -> set[str]:
    """Everyone who reports to any of these, directly or through others."""
    found: set[str] = set()
    frontier = set(ids)
    while frontier:
        nxt = set(db.scalars(select(User.id).where(User.reports_to_id.in_(frontier)))) - found - ids
        found |= nxt
        frontier = nxt
    return found


def reach_of(user: User) -> tuple[str, frozenset[str], frozenset[str]]:
    """(scope, the teams whose records they reach, the people whose records they reach): themselves, and for a manager
    everyone below; an assistant is added to what the one they assist reaches."""
    scope = user.role.scope
    db = object_session(user)
    people = [user]
    boss = db.get(User, user.assistant_of_id) if db is not None and user.assistant_of_id else None
    if boss is not None and boss.is_active:
        people.append(boss)
        if ORDER[boss.role.scope] > ORDER[scope]:
            scope = boss.role.scope
    teams = frozenset(t for p in people for t in p.all_team_ids) if scope in ("team", "managed") else frozenset()
    ids = {p.id for p in people}
    if scope == "managed" and db is not None:
        ids |= below(db, ids)
    return scope, teams, frozenset(ids)
