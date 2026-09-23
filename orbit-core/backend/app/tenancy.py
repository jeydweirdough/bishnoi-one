"""Companies (organizations), and the wall between them in the accounts database.

Every table that belongs to a company carries `org_id`. Rather than trusting
each of the hundreds of queries to remember `WHERE org_id = ...`, the wall is
set once per database session:

- every ORM SELECT, UPDATE and DELETE that touches a company table gets
  `org_id = <the session's company>` added (lists, counts, joins, lookups by
  key, relationship loads, bulk updates and deletes alike);
- every new row is stamped with the session's company, and a row of another
  company can't be written, changed or deleted;
- a session with no company that touches a company table is refused, so a
  forgotten setup fails loudly instead of showing everyone's data.

The session's company comes from the signed-in person's token (see deps.py).
Platform work that spans companies (sign-in, listing a person's companies,
creating a company) says so explicitly with `all_companies(session)`.

People (`profiles`) and their passwords are shared by all companies: one
person, one sign-in, possibly in several companies. What they may do is always
per company (memberships, assignments).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import ForeignKey, String, Table, event, inspect
from sqlalchemy.orm import Mapped, ORMExecuteState, Session, declared_attr, mapped_column, with_loader_criteria
from sqlalchemy.sql.util import find_tables

# The company every record belonged to before there were companies. Existing
# data is moved into it (migration 0005, tools/restamp.py).
FIRST_ORG_ID = "00000000-0000-4000-8000-000000000001"

ORG_KEY = "org_id"
ALL_KEY = "all_companies"


class TenancyError(RuntimeError):
    """A company table was touched without a company, or across companies."""


class Tenant:
    """A row that belongs to one company. Use TenantKey or TenantRow.

    The column is declared here too because the wall's criteria are built
    against this class (with_loader_criteria inspects the mixin itself)."""

    @declared_attr
    def org_id(cls) -> Mapped[str]:
        return mapped_column(String(36), ForeignKey("organizations.id"), index=True, sort_order=-100)


class TenantKey(Tenant):
    """A company row whose natural key is only unique inside its company: org_id leads the primary key."""

    @declared_attr
    def org_id(cls) -> Mapped[str]:
        return mapped_column(String(36), ForeignKey("organizations.id"), primary_key=True, sort_order=-100)


class TenantRow(Tenant):
    """A company row with its own globally unique id: org_id is indexed, not part of the key."""


# --- the session's company -------------------------------------------------------------


def set_company(session: Session, org_id: str) -> None:
    session.info[ORG_KEY] = org_id
    session.info.pop(ALL_KEY, None)


def company_of(session: Session) -> str:
    org = session.info.get(ORG_KEY)
    if not org:
        raise TenancyError("This database session has no company.")
    return org


@contextmanager
def all_companies(session: Session) -> Iterator[Session]:
    """Platform work across companies: the wall is lifted inside this block only."""
    before = session.info.get(ALL_KEY)
    session.info[ALL_KEY] = True
    try:
        yield session
    finally:
        if before is None:
            session.info.pop(ALL_KEY, None)
        else:
            session.info[ALL_KEY] = before


def org_get(session: Session, model: type, *key: Any) -> Any:
    """`session.get` for a company table, by its key inside the company (the company is added)."""
    names = [col.key for col in inspect(model).primary_key if col.key != ORG_KEY]
    if len(names) != len(key):
        raise TypeError(f"{model.__name__} is looked up by {names}")
    if ORG_KEY not in {col.key for col in inspect(model).primary_key}:
        return session.get(model, key[0] if len(key) == 1 else key)
    return session.get(model, {ORG_KEY: company_of(session), **dict(zip(names, key, strict=True))})


# --- the wall -------------------------------------------------------------------------------


def _touches_company_tables(state: ORMExecuteState) -> bool:
    if any(issubclass(m.class_, Tenant) for m in state.all_mappers):
        return True
    # `select(func.count()).select_from(Role)` names no mapper at the top level; look at the tables.
    tables = find_tables(state.statement, include_aliases=True, include_joins=True, include_crud=True)
    return any(ORG_KEY in table.c for table in tables if isinstance(table, Table))


@event.listens_for(Session, "do_orm_execute")
def _wall(state: ORMExecuteState) -> None:
    """Adds the session's company to every ORM statement; refuses one on company tables without a company.

    The criteria reach every place a company entity appears: the columns,
    select_from, joins, aliases, IN (select ...) subqueries and relationship
    loads. Not a Core `exists()` built from bare columns, which the app
    doesn't use (tests/test_tenancy.py checks); use `select(...).exists()`.
    """
    if not (state.is_select or state.is_update or state.is_delete) or state.session.info.get(ALL_KEY):
        return
    org = state.session.info.get(ORG_KEY)
    if not org:
        if _touches_company_tables(state):
            raise TenancyError("A company table was queried without a company.")
        return
    state.statement = state.statement.options(
        with_loader_criteria(Tenant, lambda cls: cls.org_id == org, include_aliases=True)
    )


@event.listens_for(Session, "before_flush")
def _stamp(session: Session, _context: Any, _instances: Any) -> None:
    if session.info.get(ALL_KEY):
        return
    org = session.info.get(ORG_KEY)
    for obj in session.new:
        if not isinstance(obj, Tenant):
            continue
        if not org:
            raise TenancyError(f"A new {type(obj).__name__} has no company.")
        if obj.org_id is None:
            obj.org_id = org
        elif obj.org_id != org:
            raise TenancyError(f"A {type(obj).__name__} of another company can't be added here.")
    for obj in (*session.dirty, *session.deleted):
        if isinstance(obj, Tenant):
            history = inspect(obj).attrs.org_id.history
            if history.has_changes() or obj.org_id != org:
                raise TenancyError(f"A {type(obj).__name__} can't move or be changed across companies.")
