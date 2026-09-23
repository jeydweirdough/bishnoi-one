"""People a record can be given to, for the owner pickers and filters."""

from fastapi import APIRouter

from app.access import CurrentAccess
from app.api import team_out
from app.deps import DB
from app.scope import reachable_people

router = APIRouter(prefix="/people", tags=["people"])


@router.get("/assignable")
def assignable(access: CurrentAccess, db: DB) -> list[dict]:
    """Within the person's reach: just themselves for "own", their team for
    "team", everyone switched on for "all"."""
    return [
        {"id": u.id, "name": u.full_name, "team": team_out(u.team), "isMe": u.id == access.user_id}
        for u in reachable_people(db, access)
    ]
