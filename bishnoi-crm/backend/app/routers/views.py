"""Saved views (benchmark E2, after Twenty): a list's filters, search and sort
kept by name, so "My overdue drugstores" is one click away.

A view is what the list's address holds after "?" (without the page), so it
works for every list the same way and keeps working as lists gain filters.
Anyone who sees a list keeps views of their own. Someone whose role reaches
more than their own records (a team lead, a manager, an administrator) can
share one with everyone who sees that list. Only its owner (or an
administrator) changes or deletes a view.
"""

from typing import Literal
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.access import Access, CurrentAccess
from app.api import Api, iso
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import SAVED_VIEW_LISTS, SavedView

router = APIRouter(prefix="/views", tags=["views"])

ListKey = Literal["companies", "contacts", "deals", "quotes", "activities"]
# Who sees a list: its own view permission.
SEES = {"companies": "customers.view", "contacts": "customers.view", "deals": "deals.view", "quotes": "quotes.view", "activities": "activities.view"}
# Never kept: which page of the list it was on.
DROPPED = {"page"}
MAX_VIEWS = 30


def may_see(access: Access, list_key: str) -> None:
    if list_key not in SAVED_VIEW_LISTS or not access.can(SEES[list_key]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't see that list.")


def may_share(access: Access) -> bool:
    """Sharing a view with everyone: a role that reaches more than its own records."""
    return access.scope != "own" or access.can("admin.settings")


def clean_query(raw: str) -> str:
    """The list's address after "?", in a steady order, without the page or empty values."""
    pairs = [(k, v) for k, v in parse_qsl(raw.lstrip("?"), keep_blank_values=False) if k not in DROPPED and v]
    return urlencode(sorted(pairs))


def view_out(v: SavedView, access: Access) -> dict:
    mine = v.owner_id == access.user_id
    return {
        "id": v.id, "list": v.list, "name": v.name, "query": v.query, "shared": v.shared,
        "mine": mine, "owner": {"id": v.owner_id, "name": v.owner.full_name if v.owner else None},
        "canEdit": mine or access.can("admin.settings"), "updatedAt": iso(v.updated_at),
    }


def found(db, access: Access, view_id: str) -> SavedView:
    v = db.get(SavedView, view_id)
    if v is None or not (v.owner_id == access.user_id or v.shared):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That view isn't there any more.")
    may_see(access, v.list)
    return v


def editable(access: Access, v: SavedView) -> None:
    if v.owner_id != access.user_id and not access.can("admin.settings"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the person who saved this view changes it.")


@router.get("")
def list_views(access: CurrentAccess, db: DB, list: ListKey = Query(...)) -> dict:  # noqa: A002 (the API's word)
    """This person's views of a list, then the ones shared with everyone, by name."""
    may_see(access, list)
    rows = db.scalars(
        select(SavedView).where(SavedView.list == list, or_(SavedView.owner_id == access.user_id, SavedView.shared)).order_by(func.lower(SavedView.name))
    ).unique()
    items = sorted((view_out(v, access) for v in rows), key=lambda x: (not x["mine"], x["name"].lower()))
    return {"items": items, "canShare": may_share(access)}


class ViewIn(Api):
    list: ListKey
    name: str = Field(min_length=1, max_length=60)
    query: str = Field("", max_length=1000)
    shared: bool = False


@router.post("", status_code=status.HTTP_201_CREATED)
def create_view(access: CurrentAccess, me: CurrentUser, db: DB, body: ViewIn) -> dict:
    may_see(access, body.list)
    if body.shared and not may_share(access):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role keeps views for yourself; a team lead or manager shares them.")
    if db.scalar(select(func.count()).select_from(SavedView).where(SavedView.owner_id == me.id, SavedView.list == body.list)) >= MAX_VIEWS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You have {MAX_VIEWS} views of this list already: delete one first.")
    v = SavedView(list=body.list, name=body.name, query=clean_query(body.query), shared=body.shared, owner_id=me.id)
    db.add(v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"You have a view called {body.name!r} already.") from None
    audit(db, me, "view.created", target=v.name, target_type="view", target_id=v.id)
    db.commit()
    db.refresh(v)
    return view_out(v, access)


class ViewPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=60)
    query: str | None = Field(None, max_length=1000)
    shared: bool | None = None


@router.patch("/{view_id}")
def update_view(access: CurrentAccess, me: CurrentUser, db: DB, view_id: str, body: ViewPatch) -> dict:
    v = found(db, access, view_id)
    editable(access, v)
    fields = []
    if body.name is not None and body.name != v.name:
        v.name, fields = body.name, [*fields, "name"]
    if body.query is not None and clean_query(body.query) != v.query:
        v.query, fields = clean_query(body.query), [*fields, "query"]
    if body.shared is not None and body.shared != v.shared:
        if body.shared and not may_share(access):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role keeps views for yourself; a team lead or manager shares them.")
        v.shared, fields = body.shared, [*fields, "shared"]
    if fields:
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, f"You have a view called {body.name!r} already.") from None
        audit(db, me, "view.updated", target=v.name, target_type="view", target_id=v.id, fields=fields)
        db.commit()
        db.refresh(v)
    return view_out(v, access)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_view(access: CurrentAccess, me: CurrentUser, db: DB, view_id: str) -> Response:
    v = found(db, access, view_id)
    editable(access, v)
    audit(db, me, "view.deleted", target=v.name, target_type="view", target_id=v.id)
    db.delete(v)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

