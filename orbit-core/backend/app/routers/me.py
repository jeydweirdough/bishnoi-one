"""Things that cut across modules, for the home screen."""

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import DB, CurrentAccess, CurrentUser, RecordsDep, SettingsDep
from app.models import Subdivision
from app.catalogue import sales_keys
from app.modules import BY_KEY
from app.routers.sales import CUSTOMER, FOLLOW_UP, today
from app.scope import Scope
from app.store.query import Eq, In, Query

router = APIRouter(tags=["home"])


@router.get("/me/follow-ups")
def my_follow_ups(user: CurrentUser, access: CurrentAccess, db: DB, records: RecordsDep, settings: SettingsDep) -> dict:
    """Open follow-ups assigned to me in every sales workspace I can see."""
    scopes: frozenset[Scope] = frozenset().union(*(access.scopes(k, "view") for k in sales_keys(db)))
    day = today(settings)
    docs = records.find(
        Query(FOLLOW_UP, scopes, (Eq("assigneeId", user.id), Eq("status", "open")), (("dueOn", "asc"),), limit=100)
    )
    ids = tuple({d["customerId"] for d in docs})
    names = (
        {c["_id"]: c["name"] for c in records.find(Query(CUSTOMER, scopes, (In("_id", ids),), limit=len(ids)))}
        if ids
        else {}
    )
    team_names = {(d, c): n for d, c, n in db.execute(select(Subdivision.division_code, Subdivision.code, Subdivision.name))}
    items = []
    for d in docs:
        scope = Scope.of(d)
        due = d["dueOn"]
        items.append(
            {
                "id": d["_id"],
                "module": scope.division,
                "moduleName": BY_KEY[scope.division].name,
                "team": scope.subdivision,
                "teamName": team_names.get((scope.division, scope.subdivision), scope.subdivision),
                "customerId": d["customerId"],
                "customerName": names.get(d["customerId"]),
                "title": d["title"],
                "dueOn": due,
                "bucket": "overdue" if due < day else "today" if due == day else "upcoming",
            }
        )
    return {"today": day, "items": items}
