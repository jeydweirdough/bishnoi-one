"""Pages of a list, cut and counted by the database.

A list screen asks for one page (`limit` and `offset`) and gets back
`{"items": [...], "total": N}`: the rows of that page and how many match in
all. The query keeps its filters and order; the database applies LIMIT and
OFFSET, and a COUNT over the same filtered query gives the total.

Without `limit` a route answers as it always has (the whole list), because
forms and pickers pick from the whole list.
"""

from fastapi import Query
from sqlalchemy import LABEL_STYLE_TABLENAME_PLUS_COL, Select, func, select
from sqlalchemy.orm import Session

MAX_PAGE = 200


def Limit():  # noqa: N802 - reads as the parameter it declares
    return Query(None, ge=1, le=MAX_PAGE, description="rows per page; with it, the answer is one page and the total")


def Offset():  # noqa: N802
    return Query(0, ge=0, le=10**7, description="rows to skip, with limit")


def total(db: Session, query: Select) -> int:
    """How many rows the query matches, filters and all, whatever its page."""
    return int(db.scalar(select(func.count()).select_from(query.order_by(None).limit(None).offset(None).set_label_style(LABEL_STYLE_TABLENAME_PLUS_COL).subquery())) or 0)


def cut(query: Select, limit: int, offset: int) -> Select:
    """One page of the query, its order kept."""
    return query.limit(limit).offset(offset)
