"""Who heads each unit, and who therefore sees whom (2026-11-04).

A unit has any number of heads. Everyone placed in a unit (mainly, or as one of their other units) is seen by the heads of
that unit and by the heads of every unit above it, up to the top: a team head, the division head and the department head
all see a team member. That, with the explicit "reports to" link for the odd one outside the chart, is the whole rule;
what each head may then do is their role's.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Identity, Unit, UnitHead


def heads_by_unit(db: Session, company_id: str) -> dict[str, list[str]]:
    """Each unit's heads' ids, first head first."""
    units = db.scalars(select(Unit).where(Unit.company_id == company_id)).all()
    rows: dict[str, list[str]] = {}
    for unit_id, identity_id in db.execute(select(UnitHead.unit_id, UnitHead.identity_id).join(Unit, Unit.id == UnitHead.unit_id).where(Unit.company_id == company_id)):
        rows.setdefault(unit_id, []).append(identity_id)
    out = {}
    for u in units:
        ids = rows.get(u.id, [])
        if u.manager_id and u.manager_id not in ids:
            ids = [u.manager_id, *ids]
        elif u.manager_id:
            ids = [u.manager_id, *[i for i in ids if i != u.manager_id]]
        if ids:
            out[u.id] = ids
    return out


def set_heads(db: Session, unit: Unit, identity_ids: list[str]) -> None:
    """The unit's heads are exactly these; the first is also kept as Unit.manager_id."""
    ids = list(dict.fromkeys(identity_ids))
    db.execute(delete(UnitHead).where(UnitHead.unit_id == unit.id))
    for i in ids:
        db.add(UnitHead(unit_id=unit.id, identity_id=i))
    unit.manager_id = ids[0] if ids else None


def add_head(db: Session, unit: Unit, identity_id: str) -> None:
    """One more head; the unit's first stays first."""
    if db.get(UnitHead, (unit.id, identity_id)) is None:
        db.add(UnitHead(unit_id=unit.id, identity_id=identity_id))
    if unit.manager_id is None:
        unit.manager_id = identity_id


def managers_of(units: dict[str, Unit], heads: dict[str, list[str]], emails: dict[str, str], person: Identity, other_units: list[str]) -> list[str]:
    """Everyone who sees this person: the heads of their unit and of every unit above it (and the same for their other
    units), then who they were linked to by hand. Never themselves. Emails, first the nearest."""
    out: list[str] = []
    seen_units: set[str] = set()
    for start in [person.main_unit_id, *other_units]:
        at, guard = start, 0
        while at and at in units and at not in seen_units and guard < 20:
            seen_units.add(at)
            for head in heads.get(at, []):
                email = emails.get(head)
                if email and head != person.id and email not in out:
                    out.append(email)
            at, guard = units[at].parent_id, guard + 1
    if person.reports_to_id and person.reports_to_id != person.id:
        linked = emails.get(person.reports_to_id)
        if linked and linked not in out:
            out.append(linked)
    return out
