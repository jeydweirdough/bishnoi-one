"""Record queries that cannot be unscoped.

Every read of a business record is a Query. A Query always carries the exact
set of (division, subdivision) scopes the caller may see, and filters on the
combined `scopeKey`. Two consequences:

- Nothing can match on subdivision alone. `md-telesales` under B&B and under
  B2C are different keys.
- Access is pairwise. Someone on B&B/MD Telesales and B2C/General sees exactly
  those two teams. Separate filters, `division in [bnb, b2c] && subdivision in
  [md-telesales, general]`, would also let through B2C/MD Telesales and
  B&B/General. That is the bug the project rules warn about.

A Query also carries the company (`org_id`). The records store fills it in
(see Records.for_org), and a query with a company only matches records stamped
with it.

The same Query renders to GROQ for Sanity and evaluates in Python for the
local store, so the two backends share one set of rules. Field names are
checked against a strict pattern and every value is passed as a parameter, so
nothing user-typed is spliced into GROQ.
"""

import operator
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from app.scope import Scope

_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WORD = re.compile(r"[^\W_]+")
_COMPARE = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}
MAX_LIMIT = 5000


def field_name(name: str) -> str:
    if not _FIELD.fullmatch(name):
        raise ValueError(f"invalid field name: {name!r}")
    return name


def words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(text or "")]


@dataclass(frozen=True)
class Eq:
    field: str
    value: Any

    def groq(self, p: str) -> tuple[str, dict]:
        return f"{field_name(self.field)} == ${p}", {p: self.value}

    def test(self, doc: dict) -> bool:
        return doc.get(self.field) == self.value


@dataclass(frozen=True)
class In:
    field: str
    values: tuple

    def groq(self, p: str) -> tuple[str, dict]:
        return f"{field_name(self.field)} in ${p}", {p: list(self.values)}

    def test(self, doc: dict) -> bool:
        return doc.get(self.field) in self.values


@dataclass(frozen=True)
class Cmp:
    field: str
    op: Literal["<", "<=", ">", ">="]
    value: str | int | float

    def groq(self, p: str) -> tuple[str, dict]:
        if self.op not in _COMPARE:
            raise ValueError(f"invalid comparison: {self.op!r}")
        return f"{field_name(self.field)} {self.op} ${p}", {p: self.value}

    def test(self, doc: dict) -> bool:
        value = doc.get(self.field)
        if value is None:
            return False  # GROQ: comparing with null is null, which filters out
        try:
            return _COMPARE[self.op](value, self.value)
        except TypeError:
            return False


@dataclass(frozen=True)
class Search:
    """Every typed word must start some word in one of the fields. Matches GROQ `match "word*"`."""

    fields: tuple[str, ...]
    text: str

    def terms(self) -> list[str]:
        return words(self.text)[:5]

    def groq(self, p: str) -> tuple[str, dict]:
        clauses, params = [], {}
        for i, term in enumerate(self.terms()):
            key = f"{p}_{i}"
            params[key] = f"{term}*"
            clauses.append("(" + " || ".join(f"{field_name(f)} match ${key}" for f in self.fields) + ")")
        return (" && ".join(clauses) or "true"), params

    def test(self, doc: dict) -> bool:
        found = {w for f in self.fields for w in words(str(doc.get(f) or ""))}
        return all(any(w.startswith(term) for w in found) for term in self.terms())


Condition = Eq | In | Cmp | Search


@dataclass(frozen=True)
class Query:
    doc_type: str
    scopes: frozenset[Scope]
    where: tuple[Condition, ...] = ()
    order: tuple[tuple[str, Literal["asc", "desc"]], ...] = ()
    offset: int = 0
    limit: int = 50
    org_id: str | None = None

    def __post_init__(self) -> None:
        field_name(self.doc_type)
        object.__setattr__(self, "scopes", frozenset(self.scopes))
        if not all(isinstance(s, Scope) for s in self.scopes):
            raise TypeError("scopes must be Scope values")
        for f, direction in self.order:
            field_name(f)
            if direction not in ("asc", "desc"):
                raise ValueError(f"invalid sort direction: {direction!r}")
        if self.offset < 0 or not 1 <= self.limit <= MAX_LIMIT:
            raise ValueError("offset/limit out of range")

    @property
    def scope_keys(self) -> list[str]:
        return sorted(s.key for s in self.scopes)

    @property
    def is_empty(self) -> bool:
        """No visible scopes means no results. Callers skip the store entirely."""
        return not self.scopes

    def _filter(self) -> tuple[str, dict]:
        clauses = ["_type == $type", "scopeKey in $scopeKeys"]
        params: dict[str, Any] = {"type": self.doc_type, "scopeKeys": self.scope_keys}
        if self.org_id is not None:
            clauses.append("orgId == $orgId")
            params["orgId"] = self.org_id
        for i, condition in enumerate(self.where):
            clause, p = condition.groq(f"p{i}")
            clauses.append(clause)
            params.update(p)
        return " && ".join(clauses), params

    def groq(self) -> tuple[str, dict]:
        flt, params = self._filter()
        text = f"*[{flt}]"
        if self.order:
            text += " | order(" + ", ".join(f"{f} {d}" for f, d in self.order) + ")"
        text += f"[{self.offset}...{self.offset + self.limit}]"
        return text, params

    def groq_count(self) -> tuple[str, dict]:
        flt, params = self._filter()
        return f"count(*[{flt}])", params

    def test(self, doc: dict) -> bool:
        return (
            doc.get("_type") == self.doc_type
            and doc.get("scopeKey") in self.scope_keys
            and (self.org_id is None or doc.get("orgId") == self.org_id)
            and all(c.test(doc) for c in self.where)
        )

    def apply(self, docs: Iterable[dict]) -> list[dict]:
        hits = [d for d in docs if self.test(d)]
        for f, direction in reversed(self.order):  # stable sorts, last key first
            hits.sort(key=lambda d: (d.get(f) is None, "" if d.get(f) is None else d.get(f)), reverse=direction == "desc")
        return hits[self.offset : self.offset + self.limit]
