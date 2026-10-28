"""The document chain (feature plan step 9, pattern P16): every document links to the one it came from
and the ones that followed, across apps, so any document opens the ones before and after it, and
reports can follow a sale or a purchase end to end.

- keep(...): one link, from the business event "document.linked" that any app sends
  ({"from": {app, kind, id, number}, "to": {...}}); kept once. An app may only link documents where
  one side is its own.
- trail(...): everything linked to a document, both ways, as the documents before it (oldest first)
  and after it, with every link between them. References only; each app still decides who may open
  each document.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import DocumentLink

LIMIT = 60  # documents in one trail


def _ref(side: dict) -> dict | None:
    if not isinstance(side, dict):
        return None
    out = {k: str(side.get(k) or "").strip()[:size] for k, size in (("app", 40), ("kind", 40), ("id", 36), ("number", 60))}
    return out if out["app"] and out["kind"] and out["id"] else None


def keep(db: Session, company_id: str, source: str, data: dict) -> bool:
    """Keeps the link an app sent; False when it isn't valid or was already kept."""
    a, b = _ref(data.get("from")), _ref(data.get("to"))
    if a is None or b is None or source not in (a["app"], b["app"]) or a == b:
        return False
    found = db.scalar(select(DocumentLink).where(
        DocumentLink.company_id == company_id, DocumentLink.from_app == a["app"], DocumentLink.from_kind == a["kind"], DocumentLink.from_id == a["id"],
        DocumentLink.to_app == b["app"], DocumentLink.to_kind == b["kind"], DocumentLink.to_id == b["id"]))
    if found is not None:
        # A number given later (a draft numbered when issued) fills in what was missing.
        found.from_number = found.from_number or a["number"] or None
        found.to_number = found.to_number or b["number"] or None
        return False
    db.add(DocumentLink(id=str(uuid.uuid4()), company_id=company_id, from_app=a["app"], from_kind=a["kind"], from_id=a["id"], from_number=a["number"] or None,
                        to_app=b["app"], to_kind=b["kind"], to_id=b["id"], to_number=b["number"] or None, created_at=datetime.now(UTC)))
    return True


def _key(app: str, kind: str, id_: str) -> tuple[str, str, str]:
    return (app, kind, id_)


def trail(db: Session, company_id: str, app: str, kind: str, id_: str) -> dict:
    """The documents linked to this one, both ways: before it (its sources, theirs, …) and after it."""
    start = _key(app, kind, id_)
    numbers: dict[tuple, str | None] = {}
    edges: set[tuple[tuple, tuple]] = set()
    seen = {start}
    frontier = [start]
    while frontier and len(seen) < LIMIT:
        conditions = [or_(and_(DocumentLink.from_app == a, DocumentLink.from_kind == k, DocumentLink.from_id == i),
                          and_(DocumentLink.to_app == a, DocumentLink.to_kind == k, DocumentLink.to_id == i)) for a, k, i in frontier]
        links = db.scalars(select(DocumentLink).where(DocumentLink.company_id == company_id, or_(*conditions))).all()
        frontier = []
        for link in links:
            f, t = _key(link.from_app, link.from_kind, link.from_id), _key(link.to_app, link.to_kind, link.to_id)
            numbers[f] = numbers.get(f) or link.from_number
            numbers[t] = numbers.get(t) or link.to_number
            edges.add((f, t))
            for node in (f, t):
                if node not in seen and len(seen) < LIMIT:
                    seen.add(node)
                    frontier.append(node)

    def walk(node, forward: bool) -> list:
        """Documents reached following the links one way, nearest last for `before`, nearest first for `after`."""
        out, level, done = [], [node], {node}
        while level:
            nxt = []
            for n in level:
                for f, t in sorted(edges):
                    other = t if forward and f == n else f if not forward and t == n else None
                    if other is not None and other not in done:
                        done.add(other)
                        nxt.append(other)
            out.extend(nxt)
            level = nxt
        return out if forward else list(reversed(out))

    as_out = lambda n: {"app": n[0], "kind": n[1], "id": n[2], "number": numbers.get(n)}  # noqa: E731
    before, after = walk(start, False), walk(start, True)
    linked = set(before) | set(after) | {start}
    return {
        "document": as_out(start),
        "before": [as_out(n) for n in before],
        "after": [as_out(n) for n in after],
        # Linked another way (a sibling: another receipt of the same purchase order).
        "related": [as_out(n) for n in sorted(seen - linked)],
        "links": [{"from": as_out(f), "to": as_out(t)} for f, t in sorted(edges)],
    }
