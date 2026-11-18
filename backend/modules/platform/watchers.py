"""Who monitors whom (2026-11-18, step 4E: "seeing people: inclusive, and separate from permissions").

Viewing people for monitoring is its own list, nbpl_watchers. It is built from the chart: every manager the chart gives a
person (the heads of their unit and of every unit above it, and who they report to, unit_heads.managers_of) is added as a
watcher with source "chart". The chart only ever ADDS: a person who moves keeps their old managers watching until an
administrator removes them. Administrators also add watchers by hand (source "added").

What the apps are told someone is seen by (the chart event's and each pass's "managers") is the chart's managers plus
the watchers. Watching gives reach (seeing records within the role's managed scope), never actions.

record(execute, company_id) reads the tables with plain SQL on named columns, so the migration that made the table (0030)
fills it with the same code that keeps it filled afterwards, whatever later columns the models gain.
"""

import logging
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import DateTime, bindparam, text

from modules.platform import unit_heads

log = logging.getLogger(__name__)


def chart_pairs(execute, company_id: str | None = None) -> set[tuple[str, str]]:
    """(watched id, watcher id) for every manager the chart gives every person, at one company or all of them."""
    where, args = ("WHERE company_id = :c", {"c": company_id}) if company_id else ("", {})
    units = {r[0]: SimpleNamespace(id=r[0], parent_id=r[1], manager_id=r[2], company_id=r[3])
             for r in execute(text(f"SELECT id, parent_id, manager_id, company_id FROM nbpl_units {where}"), args)}
    heads: dict[str, list[str]] = {}
    for u in units.values():
        if u.manager_id:
            heads.setdefault(u.id, []).append(u.manager_id)
    for unit_id, identity_id in execute(text("SELECT unit_id, identity_id FROM nbpl_unit_heads")):
        if unit_id in units and identity_id not in heads.setdefault(unit_id, []):
            heads[unit_id].append(identity_id)
    people = [SimpleNamespace(id=r[0], company_id=r[1], main_unit_id=r[2], reports_to_id=r[3])
              for r in execute(text(f"SELECT id, company_id, main_unit_id, reports_to_id FROM nbpl_identities {where}"
                                    + (" AND" if where else " WHERE") + " via_operator = :no"), {**args, "no": False})]
    ids = {p.id: p.company_id for p in people}
    others: dict[str, list[str]] = {}
    for membership_id, unit_id in execute(text("SELECT membership_id, unit_id FROM nbpl_membership_units")):
        if membership_id in ids:
            others.setdefault(membership_id, []).append(unit_id)
    same = {i: i for i in ids}  # managers_of gives back whatever this maps a head to: here, the head's own id
    pairs = set()
    for p in people:
        mine = {k: u for k, u in units.items() if u.company_id == p.company_id}
        for watcher in unit_heads.managers_of(mine, heads, same, p, others.get(p.id, [])):
            if ids.get(watcher) == p.company_id and watcher != p.id:
                pairs.add((p.id, watcher))
    return pairs


def record(execute, company_id: str | None = None) -> int:
    """Adds every pair the chart gives that isn't kept yet, as source "chart". Never removes. How many were added."""
    have = {(r[0], r[1]) for r in execute(text("SELECT watched_id, watcher_id FROM nbpl_watchers"))}
    now = datetime.now(UTC)
    added = 0
    for watched, watcher in sorted(chart_pairs(execute, company_id) - have):
        execute(text("INSERT INTO nbpl_watchers (watched_id, watcher_id, source, added_at) VALUES (:a, :b, 'chart', :t)")
                .bindparams(bindparam("t", type_=DateTime(timezone=True))), {"a": watched, "b": watcher, "t": now})
        added += 1
    return added


def remember(sessions, company_id: str) -> None:
    """record() at one company in its own session, committed: called as the chart changes, before the apps are told."""
    try:
        with sessions() as db:
            if record(db.execute, company_id):
                db.commit()
    except Exception:  # noqa: BLE001 (the next change records them; the chart push still goes)
        log.exception("Watchers: couldn't keep the chart's managers at %s.", company_id)


def watcher_emails(db, company_id: str) -> dict[str, list[str]]:
    """Each person's watchers' emails (lower-cased), oldest first."""
    rows = db.execute(text(
        "SELECT w.watched_id, lower(i.email) FROM nbpl_watchers w JOIN nbpl_identities i ON i.id = w.watcher_id "
        "WHERE i.company_id = :c ORDER BY w.added_at, i.email"), {"c": company_id})
    out: dict[str, list[str]] = {}
    for watched, email in rows:
        out.setdefault(watched, []).append(email)
    return out


def union(managers: list[str], watchers: list[str], own_email: str) -> list[str]:
    """The chart's managers first (nearest first), then the other watchers; never themselves."""
    out = list(managers)
    for e in watchers:
        if e not in out and e != own_email.lower():
            out.append(e)
    return out
