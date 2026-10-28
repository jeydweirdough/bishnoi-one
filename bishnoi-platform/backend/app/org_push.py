"""Telling the applications the org chart (feature plan step 4, agreed 2026-10-28).

- placement(db, person): where someone sits, for their sign-in pass ("org"): their main
  unit, the units above it (top first), their other units, their branch and their manager
  (the main unit's head; for the head themselves, the head of the unit above).
- push(...): the company's units and where each person sits, as the business event
  "organisation.changed" (step 7, app/events.py): kept, delivered to each app that takes it (the
  CRM's teams), in order, and retried; each sign-in pass also carries the person's own placing.
"""

import logging
import secrets
import threading
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access_roles import modules_of
from app.config import Settings
from app.models import Branch, Company, Identity, MembershipUnit, Unit

log = logging.getLogger(__name__)

LIFETIME = 600  # seconds a note may be taken


def _units(db: Session, company_id: str) -> dict[str, Unit]:
    return {u.id: u for u in db.scalars(select(Unit).where(Unit.company_id == company_id))}


def path_of(units: dict[str, Unit], unit_id: str | None) -> list[Unit]:
    """The unit and the units above it, top first."""
    path, seen = [], set()
    while unit_id and unit_id in units and unit_id not in seen:
        seen.add(unit_id)
        path.append(units[unit_id])
        unit_id = units[unit_id].parent_id
    return path[::-1]


def manager_of(db: Session, units: dict[str, Unit], person: Identity) -> str | None:
    for unit in reversed(path_of(units, person.main_unit_id)):
        if unit.manager_id and unit.manager_id != person.id:
            head = db.get(Identity, unit.manager_id)
            return head.email if head else None
    return None


def placement(db: Session, person: Identity) -> dict | None:
    """Where they sit, for their pass; None when they aren't placed anywhere."""
    units = _units(db, person.company_id)
    others = list(db.scalars(select(MembershipUnit.unit_id).where(MembershipUnit.membership_id == person.id)))
    branch = db.get(Branch, person.branch_id) if person.branch_id else None
    if not person.main_unit_id and not others and branch is None:
        return None
    main = units.get(person.main_unit_id) if person.main_unit_id else None
    return {
        "unit": {"id": main.id, "name": main.name, "kind": main.kind} if main else None,
        "units": [u.id for u in path_of(units, person.main_unit_id)],
        "otherUnits": others,
        "branch": {"id": branch.id, "name": branch.name} if branch else None,
        "manager": manager_of(db, units, person),
    }


def chart(db: Session, company: Company) -> dict:
    """The company's units, and where each of its people sits: the "organisation.changed" event's data."""
    units = _units(db, company.id)
    heads = {i.id: i.email for i in db.scalars(select(Identity).where(Identity.company_id == company.id))}
    others: dict[str, list[str]] = {}
    for m in db.scalars(select(MembershipUnit).join(Identity, Identity.id == MembershipUnit.membership_id).where(Identity.company_id == company.id)):
        others.setdefault(m.membership_id, []).append(m.unit_id)
    people = db.scalars(select(Identity).where(Identity.company_id == company.id, Identity.via_operator.is_(False))).all()
    return {
        "units": [{"id": u.id, "kind": u.kind, "name": u.name, "parentId": u.parent_id, "manager": heads.get(u.manager_id),
                   "areas": u.areas or [], "active": u.is_active} for u in units.values()],
        "people": [{"email": p.email.lower(), "unit": p.main_unit_id, "otherUnits": others.get(p.id, [])} for p in people],
    }


def _send(sessions, settings: Settings, company_id: str) -> None:
    """The chart as a business event (step 7): kept, delivered to each app that takes it, retried."""
    from app import events

    with sessions() as db:
        company = db.get(Company, company_id)
        if company is None:
            return
        events.publish(db, company, "organisation.changed", chart(db, company))
        db.commit()
        events.deliver_due(db, settings)


def push(sessions, settings: Settings, company_id: str) -> None:
    """Sends every application the company has its org chart, in the background."""

    def run() -> None:
        try:
            _send(sessions, settings, company_id)
        except Exception:  # noqa: BLE001 (each sign-in carries the person's placing too)
            log.exception("Org chart push: couldn't tell the applications about %s.", company_id)

    threading.Thread(target=run, name="org-push", daemon=True).start()
