"""Data clean-up and the recycle bin (2026-10-30): the same engine in every Bishnoi One app.

An administrator (the Administrator role: a company administrator or an operator comes in with it) deletes
records to the recycle bin: each record, with what belongs only to it (a quote's lines, an invoice's
payments: its `owns`), is kept as a snapshot and taken out. Something else that still needs it (a product on
twelve quotes) refuses the delete and says what; a link that may be empty (a contact's company) is cleared,
and put back on restore. Restore puts everything back as it was. After 30 days the snapshot is erased; an
administrator can erase one, or empty the bin, sooner. Posted documents (issued invoices, received stock)
can be deleted too: they ask for a second confirmation, and a closed accounting period refuses.

    GET    /data-cleanup/kinds                 what can be cleaned up, by group
    GET    /data-cleanup/kinds/{kind}?q=&page= records of a kind, to pick from
    POST   /data-cleanup/kinds/{kind}/delete   {ids, confirmPosted}: to the recycle bin, all or none
    GET    /data-cleanup/bin                   what's in the bin, newest first (expired ones erased first)
    POST   /data-cleanup/bin/{id}/restore      back as it was
    DELETE /data-cleanup/bin/{id}              erased now
    DELETE /data-cleanup/bin                   the bin emptied

The kinds are this app's (app/recycle_kinds.py). Every delete, restore and erase is in the audit log.
"""

import base64
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import JSON, DateTime, String, Table, and_, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.audit import audit
from app.db import Base
from app.deps import DB, CurrentUser

PREFIX = "nbad_"
DAYS = 30
PAGE = 50


class BinEntry(Base):
    """A deleted record and what was taken out with it, until restored or erased."""

    __tablename__ = PREFIX + "recycle_bin"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(40))
    record_id: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(300))
    # The rows taken out, parent first: [{"t": table, "d": {column: value}}]; links cleared: [{"t", "k", "c", "v"}].
    rows: Mapped[list] = mapped_column(JSON, default=list)
    unlinked: Mapped[list] = mapped_column(JSON, default=list)
    deleted_by: Mapped[str] = mapped_column(String(254))
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


@dataclass(frozen=True)
class Kind:
    """Something that can be cleaned up: its table, how it's named, and what belongs only to it."""

    key: str
    name: str
    table: str
    label: str | Callable[[dict], str]
    group: str = "Records"
    owns: tuple[str, ...] = ()
    search: tuple[str, ...] = ()
    sub: str | Callable[[dict], str] | None = None
    posted: Callable[[dict], bool] | None = None
    # More rows to take out with it (a posted invoice's journal entries): [(table, column, value)].
    extra: Callable[[Session, dict], list[tuple[str, str, object]]] | None = None
    # Refuses (raises HTTPException) when it mustn't go: a closed accounting period.
    guard: Callable[[Session, dict], None] | None = None
    # After its rows are taken out / put back: what else follows (stock balances, for posted stock documents).
    on_delete: Callable[[Session, list[tuple[str, dict]]], None] | None = None
    on_restore: Callable[[Session, list[tuple[str, dict]]], None] | None = None
    tables_named: dict = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(UTC)


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _enc(v):
    if isinstance(v, datetime):
        return {"$dt": v.isoformat()}
    if isinstance(v, date):
        return {"$d": v.isoformat()}
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"$b": base64.b64encode(bytes(v)).decode()}
    if isinstance(v, Decimal):
        return {"$n": str(v)}
    return v


def _dec(v):
    if isinstance(v, dict) and len(v) == 1:
        (k, x), = v.items()
        if k == "$dt":
            return datetime.fromisoformat(x)
        if k == "$d":
            return date.fromisoformat(x)
        if k == "$b":
            return base64.b64decode(x)
        if k == "$n":
            return Decimal(x)
    return v


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def _pk(t: Table):
    """The record's own key column (an id, or a code for lists keyed by code)."""
    return list(t.primary_key.columns)[0]


def _key(t: Table, row: dict) -> dict:
    return {c.name: row[c.name] for c in t.primary_key.columns}


def _where_key(t: Table, key: dict):
    return and_(*(t.c[k] == _dec(v) for k, v in key.items()))


def _rank() -> dict[str, int]:
    """Each table's place in the database's own order: what's referenced comes before what refers to it."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # tables that refer to each other: their order between them doesn't matter here
        return {t.name: i for i, t in enumerate(Base.metadata.sorted_tables)}


def _plain(name: str) -> str:
    return name.removeprefix(PREFIX).replace("_", " ")


def _label(kind: Kind, row: dict) -> str:
    text = kind.label(row) if callable(kind.label) else row.get(kind.label)
    return str(text or row.get("id") or row.get("code") or "")[:300]


class Taken:
    """What deleting some rows takes out: the rows (parent first), the links cleared, and what refuses it."""

    def __init__(self) -> None:
        self.rows: list[tuple[Table, dict]] = []
        self.unlinked: list[tuple[Table, dict, str, object]] = []
        self.blockers: dict[str, int] = {}
        self._seen: set[tuple[str, tuple]] = set()

    def has(self, t: Table, row: dict) -> bool:
        return (t.name, tuple(sorted(_key(t, row).items()))) in self._seen

    def add(self, t: Table, row: dict) -> bool:
        k = (t.name, tuple(sorted(_key(t, row).items())))
        if k in self._seen:
            return False
        self._seen.add(k)
        self.rows.append((t, row))
        return True


def _gather(db: Session, kind: Kind, t: Table, where, taken: Taken, owned: set[str]) -> None:
    found = [dict(r) for r in db.execute(select(t).where(where)).mappings()]
    fresh = [r for r in found if taken.add(t, r)]
    if not fresh:
        return
    for child in Base.metadata.tables.values():
        for fk in child.foreign_keys:
            if fk.column.table is not t:
                continue
            values = [r[fk.column.name] for r in fresh if r.get(fk.column.name) is not None]
            if not values:
                continue
            if child.name in owned:
                _gather(db, kind, child, fk.parent.in_(values), taken, owned)
                continue
            refs = [dict(r) for r in db.execute(select(child).where(fk.parent.in_(values))).mappings()]
            refs = [r for r in refs if not taken.has(child, r)]
            if not refs:
                continue
            if fk.parent.nullable:
                taken.unlinked += [(child, r, fk.parent.name, r[fk.parent.name]) for r in refs]
            else:
                name = kind.tables_named.get(child.name) or _plain(child.name)
                taken.blockers[name] = taken.blockers.get(name, 0) + len(refs)


def take(db: Session, kind: Kind, record_id: str) -> tuple[dict, Taken]:
    t = _table(kind.table)
    row = db.execute(select(t).where(_pk(t) == record_id)).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"That {kind.name.lower()} isn't here any more.")
    row = dict(row)
    if kind.guard:
        kind.guard(db, row)
    taken = Taken()
    owned = set(kind.owns)
    _gather(db, kind, t, _pk(t) == record_id, taken, owned)
    for table, column, value in (kind.extra(db, row) if kind.extra else []):
        extra = _table(table)
        _gather(db, kind, extra, extra.c[column] == value, taken, owned | {table})
    # A link that is itself being taken out (a row of this record pointing at another of its rows) isn't cleared.
    taken.unlinked = [u for u in taken.unlinked if not taken.has(u[0], u[1])]
    return row, taken


def to_bin(db: Session, kind: Kind, record_id: str, actor: str, confirm_posted: bool = False) -> BinEntry:
    row, taken = take(db, kind, record_id)
    label = _label(kind, row)
    if taken.blockers:
        used = ", ".join(f"{n} {what}" for what, n in sorted(taken.blockers.items()))
        raise HTTPException(status.HTTP_409_CONFLICT, f"{label} is still used ({used}). Delete or change those first.")
    if kind.posted and kind.posted(row) and not confirm_posted:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{label} is posted: deleting it changes the books or the stock. Confirm to delete it anyway.")
    for t, r, column, _ in taken.unlinked:
        db.execute(update(t).where(_where_key(t, {k: _enc(v) for k, v in _key(t, r).items()})).values({column: None}))
    rank = _rank()
    taken.rows.sort(key=lambda tr: rank.get(tr[0].name, 0))  # parents first: kept so, put back so, taken out the other way
    for t, r in reversed(taken.rows):
        db.execute(delete(t).where(_where_key(t, {k: _enc(v) for k, v in _key(t, r).items()})))
    if kind.on_delete:
        kind.on_delete(db, [(t.name, r) for t, r in taken.rows])
    now = _now()
    entry = BinEntry(kind=kind.key, record_id=str(record_id), label=label, deleted_by=actor, deleted_at=now, expires_at=now + timedelta(days=DAYS),
                     rows=[{"t": t.name, "d": {k: _enc(v) for k, v in r.items()}} for t, r in taken.rows],
                     unlinked=[{"t": t.name, "k": {k: _enc(v) for k, v in _key(t, r).items()}, "c": c, "v": _enc(v)} for t, r, c, v in taken.unlinked])
    db.add(entry)
    return entry


def restore(db: Session, entry: BinEntry, kind: Kind | None = None) -> None:
    put = []
    rank = _rank()
    for item in sorted(entry.rows, key=lambda i: rank.get(i["t"], 0)):
        t = _table(item["t"])
        values = {k: _dec(v) for k, v in item["d"].items() if k in t.c}
        db.execute(insert(t).values(values))
        put.append((t.name, values))
    if kind is not None and kind.on_restore:
        kind.on_restore(db, put)
    for item in entry.unlinked:
        t = _table(item["t"])
        db.execute(update(t).where(_where_key(t, item["k"])).values({item["c"]: _dec(item["v"])}))
    db.delete(entry)


def purge(db: Session) -> None:
    db.execute(delete(BinEntry).where(BinEntry.expires_at < _now()))


# ---- The routes -------------------------------------------------------------------------------------


def administrator(user: CurrentUser):
    role = getattr(user, "role", None)
    if role is None or not (role.is_system or role.name == "Administrator"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators clean up data and use the recycle bin.")
    return user


Admin = Annotated[object, Depends(administrator)]


class Api(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DeleteIn(Api):
    ids: list[str] = Field(min_length=1, max_length=500)
    confirm_posted: bool = False


def make_router(kinds: list[Kind]) -> APIRouter:
    by_key = {k.key: k for k in kinds}
    router = APIRouter(prefix="/data-cleanup", tags=["data clean-up"])

    def kind_of(key: str) -> Kind:
        if key not in by_key:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "There's nothing like that to clean up.")
        return by_key[key]

    @router.get("/kinds")
    def list_kinds(db: DB, _: Admin) -> dict:
        out = []
        for k in kinds:
            t = _table(k.table)
            out.append({"key": k.key, "name": k.name, "group": k.group, "count": db.scalar(select(func.count()).select_from(t)) or 0,
                        "posted": k.posted is not None})
        return {"kinds": out, "days": DAYS}

    @router.get("/kinds/{key}")
    def list_records(key: str, db: DB, _: Admin, q: Annotated[str, Query(max_length=100)] = "", page: Annotated[int, Query(ge=1, le=10_000)] = 1) -> dict:
        k = kind_of(key)
        t = _table(k.table)
        query = select(t)
        cols = [t.c[c] for c in (k.search or ((k.label,) if isinstance(k.label, str) else ())) if c in t.c]
        if q.strip() and cols:
            like = f"%{q.strip().lower()}%"
            query = query.where(or_(*(func.lower(func.cast(c, String)).like(like) for c in cols)))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        order = t.c.created_at.desc() if "created_at" in t.c else (t.c[k.label] if isinstance(k.label, str) and k.label in t.c else _pk(t))
        rows = [dict(r) for r in db.execute(query.order_by(order).limit(PAGE).offset((page - 1) * PAGE)).mappings()]
        def sub(r: dict) -> str | None:
            if k.sub is None:
                return None
            v = k.sub(r) if callable(k.sub) else r.get(k.sub)
            return None if v is None else str(v)[:200]
        key_col = _pk(t).name
        return {"items": [{"id": str(r[key_col]), "label": _label(k, r), "sub": sub(r), "posted": bool(k.posted and k.posted(r)),
                           "createdAt": _utc(r["created_at"]).isoformat() if isinstance(r.get("created_at"), datetime) else None} for r in rows],
                "total": total, "page": page, "pageSize": PAGE}

    @router.post("/kinds/{key}/delete")
    def delete_records(key: str, body: DeleteIn, db: DB, user: Admin) -> dict:
        k = kind_of(key)
        purge(db)
        made = []
        try:
            for record_id in dict.fromkeys(body.ids):
                entry = to_bin(db, k, record_id, user.email, body.confirm_posted)
                db.flush()
                made.append(entry)
                audit(db, user, "record.deleted", target=entry.label, target_type=k.key, target_id=str(record_id))
        except HTTPException:
            db.rollback()
            raise
        db.commit()
        return {"deleted": len(made), "binIds": [e.id for e in made]}

    @router.get("/bin")
    def bin_list(db: DB, _: Admin) -> dict:
        purge(db)
        db.commit()
        rows = db.scalars(select(BinEntry).order_by(BinEntry.deleted_at.desc()).limit(1000)).all()
        return {"days": DAYS, "items": [{"id": e.id, "kind": e.kind, "kindName": by_key[e.kind].name if e.kind in by_key else e.kind, "label": e.label,
                                         "rows": len(e.rows or []), "deletedBy": e.deleted_by, "deletedAt": _utc(e.deleted_at).isoformat(),
                                         "expiresAt": _utc(e.expires_at).isoformat()} for e in rows]}

    def entry_of(db: Session, entry_id: str) -> BinEntry:
        e = db.get(BinEntry, entry_id)
        if e is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That isn't in the recycle bin any more.")
        return e

    @router.post("/bin/{entry_id}/restore")
    def bin_restore(entry_id: str, db: DB, user: Admin) -> dict:
        e = entry_of(db, entry_id)
        label, kind, rid = e.label, e.kind, e.record_id
        try:
            restore(db, e, by_key.get(kind))
            audit(db, user, "record.restored", target=label, target_type=kind, target_id=rid)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, f"{label} can't come back as it was: something with the same name or number is here now, "
                                                         "or what it belonged to was deleted. Restore that first, or rename the new one.") from None
        return {"restored": label}

    @router.delete("/bin/{entry_id}")
    def bin_erase(entry_id: str, db: DB, user: Admin) -> dict:
        e = entry_of(db, entry_id)
        audit(db, user, "record.erased", target=e.label, target_type=e.kind, target_id=e.record_id)
        db.delete(e)
        db.commit()
        return {"erased": 1}

    @router.delete("/bin")
    def bin_empty(db: DB, user: Admin) -> dict:
        n = db.execute(delete(BinEntry)).rowcount or 0
        audit(db, user, "recycle_bin.emptied", target=f"{n} records", target_type="recycle_bin")
        db.commit()
        return {"erased": n}

    return router
