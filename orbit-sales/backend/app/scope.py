"""Whose records a person reaches: their role's scope, applied to owned records.

- own:  records they own;
- team: records owned in their team (their own too, even without a team);
- all:  every record.

Reading and changing use the same reach; the role's permissions then say what
they may do within it. A record out of reach is answered as not found, so
nobody learns what exists outside what they can see.
"""

from fastapi import HTTPException, status
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.access import Access
from app.models import Owned, User


def within(query: Select, model: type[Owned], access: Access) -> Select:
    """The query, narrowed to what this person reaches."""
    if access.scope == "all":
        return query
    if access.scope == "team" and access.team_id:
        return query.where(or_(model.team_id == access.team_id, model.owner_id == access.user_id))
    return query.where(model.owner_id == access.user_id)


def reaches(record: Owned, access: Access) -> bool:
    if access.scope == "all" or record.owner_id == access.user_id:
        return True
    return access.scope == "team" and access.team_id is not None and record.team_id == access.team_id


def reachable_people(db: Session, access: Access) -> list[User]:
    """Who this person may give a record to: anyone they could then still see
    the record of. Switched-off people get nothing new."""
    q = select(User).where(User.is_active).order_by(User.full_name)
    if access.scope == "all":
        return list(db.scalars(q))
    if access.scope == "team" and access.team_id:
        return list(db.scalars(q.where(or_(User.team_id == access.team_id, User.id == access.user_id))))
    return list(db.scalars(q.where(User.id == access.user_id)))


def owner_for(db: Session, access: Access, owner_id: str | None) -> User:
    """The owner a new or changed record gets: the one asked for if this person
    may give it to them, else a field error. Nobody asked for: themselves."""
    wanted = owner_id or access.user_id
    if wanted not in {u.id for u in reachable_people(db, access)}:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [{"type": "value_error", "loc": ["body", "ownerId"], "msg": "Pick someone you can give records to."}],
        )
    return db.get(User, wanted)
