"""The one door to business records.

Routers use Records, never a backend directly. Records adds these checks on
top of whichever backend is configured (Sanity or the local file):

- it only works for one company (`for_org`, handed out by deps.get_records);
  an unbound Records refuses everything, so a forgotten company fails loudly;
- on write, every new record is stamped with the company (`orgId`) and carries
  a consistent scope stamp (division, subdivision, and the scopeKey built from
  them); a patch can't change the company, or one part of the scope stamp
  without the others; and a record of another company can't be patched or
  deleted, even by id;
- on read, only the company's records are asked for, and anything of another
  company, or whose stamp disagrees with itself, or that falls outside the
  query's scopes, is dropped and logged rather than shown.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol

from app.scope import Scope
from app.store.query import Eq, Query
from app.tenancy import TenancyError

log = logging.getLogger("crm.records")

SCOPE_FIELDS = frozenset({"division", "subdivision", "scopeKey"})
ORG_FIELD = "orgId"


class StoreError(Exception):
    """The records backend failed or is unreachable."""


class ConflictError(StoreError):
    """The record changed since it was read, or already exists."""


@dataclass(frozen=True)
class Create:
    doc: dict


@dataclass(frozen=True)
class Patch:
    id: str
    set: dict = field(default_factory=dict)
    unset: tuple[str, ...] = ()
    if_revision: str | None = None


@dataclass(frozen=True)
class Delete:
    id: str


Mutation = Create | Patch | Delete


class Backend(Protocol):
    kind: str

    def fetch(self, query: Query) -> list[dict]: ...

    def count(self, query: Query) -> int: ...

    def commit(self, mutations: Sequence[Mutation]) -> None: ...

    def owners(self, ids: Sequence[str]) -> dict[str, str | None]:
        """The company of each record that exists (None if it has none)."""
        ...


def check_mutation(m: Mutation) -> None:
    if isinstance(m, Create):
        doc = m.doc
        if not doc.get("_id") or not doc.get("_type"):
            raise ValueError("a new record needs _id and _type")
        Scope.of(doc)  # raises if the stamp is missing or inconsistent
    elif isinstance(m, Patch):
        if {"_id", "_type"} & set(m.set):
            raise ValueError("a patch can't change a record's _id or _type")
        if ORG_FIELD in m.set or ORG_FIELD in m.unset:
            raise ValueError("a record can't move to another company")
        touched = SCOPE_FIELDS & (set(m.set) | set(m.unset))
        if touched:
            if touched != SCOPE_FIELDS or set(m.unset) & SCOPE_FIELDS:
                raise ValueError("moving a record sets division, subdivision and scopeKey together")
            Scope.of(m.set)


class Records:
    def __init__(self, backend: Backend, org_id: str | None = None) -> None:
        self.backend = backend
        self.org_id = org_id

    def for_org(self, org_id: str) -> "Records":
        if not org_id:
            raise TenancyError("Records need a company.")
        if self.org_id not in (None, org_id):
            raise TenancyError("These records belong to another company.")
        return self if self.org_id == org_id else Records(self.backend, org_id)

    @property
    def kind(self) -> str:
        return self.backend.kind

    def _org(self) -> str:
        if self.org_id is None:
            raise TenancyError("Records used without a company; use for_org().")
        return self.org_id

    def _own(self, query: Query) -> Query:
        org = self._org()
        if query.org_id not in (None, org):
            raise TenancyError("A query for another company.")
        return replace(query, org_id=org)

    def find(self, query: Query) -> list[dict]:
        query = self._own(query)
        if query.is_empty:
            return []
        keys = set(query.scope_keys)
        kept = []
        for doc in self.backend.fetch(query):
            try:
                ok = doc.get(ORG_FIELD) == query.org_id and Scope.of(doc).key in keys
            except (KeyError, ValueError):
                ok = False
            if ok:
                kept.append(doc)
            else:
                log.error("dropped record %s: company or scope stamp is wrong, or outside the query", doc.get("_id"))
        return kept

    def count(self, query: Query) -> int:
        query = self._own(query)
        return 0 if query.is_empty else self.backend.count(query)

    def get(self, doc_type: str, doc_id: str, scopes: frozenset[Scope]) -> dict | None:
        hits = self.find(Query(doc_type, scopes, (Eq("_id", doc_id),), limit=1))
        return hits[0] if hits else None

    def commit(self, mutations: Sequence[Mutation]) -> None:
        org = self._org()
        stamped: list[Mutation] = []
        for m in mutations:
            if isinstance(m, Create):
                if m.doc.get(ORG_FIELD, org) != org:
                    raise TenancyError("A new record for another company.")
                m = Create({**m.doc, ORG_FIELD: org})
            check_mutation(m)
            stamped.append(m)
        if not stamped:
            return
        # Patches and deletes name records by id alone, so make sure every one is this company's.
        ids = sorted({m.id for m in stamped if isinstance(m, Patch | Delete)})
        if ids:
            foreign = [i for i, owner in self.backend.owners(ids).items() if owner != org]
            if foreign:
                log.error("refused changes to %d record(s) of another company: %s", len(foreign), foreign[:5])
                raise TenancyError("A record of another company can't be changed.")
        self.backend.commit(stamped)
