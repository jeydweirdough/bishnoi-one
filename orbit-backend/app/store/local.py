"""A JSON-file stand-in for Sanity, for development before Sanity is connected
and for tests. Same Query semantics (it evaluates Query.test/apply), same
transaction behaviour (all mutations apply or none do)."""

import copy
import json
import os
import threading
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.store.query import Query
from app.store.records import ConflictError, Create, Delete, Mutation, Patch, StoreError


class LocalBackend:
    kind = "local"

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._docs: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if self._path and self._path.exists():
            return json.loads(self._path.read_text(encoding="utf-8"))["documents"]
        return {}

    def _save(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"documents": self._docs}, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._path)

    def fetch(self, query: Query) -> list[dict]:
        with self._lock:
            return copy.deepcopy(query.apply(self._docs.values()))

    def count(self, query: Query) -> int:
        with self._lock:
            return sum(1 for d in self._docs.values() if query.test(d))

    def owners(self, ids: Sequence[str]) -> dict[str, str | None]:
        with self._lock:
            return {i: self._docs[i].get("orgId") for i in ids if i in self._docs}

    def without_org(self, limit: int) -> list[str]:
        """Ids of records not yet stamped with a company (tools/restamp.py)."""
        with self._lock:
            return [i for i, d in self._docs.items() if "scopeKey" in d and not d.get("orgId")][:limit]

    def commit(self, mutations: Sequence[Mutation]) -> None:
        with self._lock:
            docs = copy.deepcopy(self._docs)
            now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            for m in mutations:
                if isinstance(m, Create):
                    if m.doc["_id"] in docs:
                        raise ConflictError(f"record {m.doc['_id']} already exists")
                    docs[m.doc["_id"]] = {**m.doc, "_createdAt": now, "_updatedAt": now, "_rev": _rev()}
                elif isinstance(m, Patch):
                    doc = docs.get(m.id)
                    if doc is None:
                        raise StoreError(f"record {m.id} not found")
                    if m.if_revision and doc.get("_rev") != m.if_revision:
                        raise ConflictError(f"record {m.id} changed since it was read")
                    doc.update(copy.deepcopy(m.set))
                    for key in m.unset:
                        doc.pop(key, None)
                    doc["_updatedAt"], doc["_rev"] = now, _rev()
                elif isinstance(m, Delete):
                    docs.pop(m.id, None)
            self._docs = docs
            self._save()


def _rev() -> str:
    return uuid.uuid4().hex[:22]
