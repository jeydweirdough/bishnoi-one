"""Division + subdivision: the key that scopes every record.

A subdivision code is not unique on its own. `md-telesales` exists under B&B,
B2C, STC and URO, so anything that identifies a team carries both parts.
Records store the combined `scopeKey` built here, and reads filter on that
key, never on subdivision alone and never on separate division/subdivision
lists (see store/query.py for why).
"""

import re
from dataclasses import dataclass

SEPARATOR = "/"
CODE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def is_code(value: str) -> bool:
    return bool(CODE.fullmatch(value))


@dataclass(frozen=True, order=True)
class Scope:
    division: str
    subdivision: str

    def __post_init__(self) -> None:
        if not is_code(self.division) or not is_code(self.subdivision):
            raise ValueError(f"invalid scope: {self.division!r}, {self.subdivision!r}")

    @property
    def key(self) -> str:
        return f"{self.division}{SEPARATOR}{self.subdivision}"

    @classmethod
    def from_key(cls, key: str) -> "Scope":
        division, _, subdivision = key.partition(SEPARATOR)
        return cls(division, subdivision)

    @classmethod
    def of(cls, doc: dict) -> "Scope":
        """The scope a stored record claims, checked against its scopeKey."""
        scope = cls(doc["division"], doc["subdivision"])
        if doc.get("scopeKey") != scope.key:
            raise ValueError(f"record {doc.get('_id')!r} has a scopeKey that disagrees with its fields")
        return scope

    def stamp(self) -> dict[str, str]:
        """The three fields every record carries. Written only through here."""
        return {"division": self.division, "subdivision": self.subdivision, "scopeKey": self.key}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
