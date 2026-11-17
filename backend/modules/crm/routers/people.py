"""People a record can be given to, for the owner pickers and filters."""

from fastapi import APIRouter

from modules.crm.access import CurrentAccess
from modules.crm.api import team_out
from modules.crm.deps import DB
from modules.crm.scope import reachable_people

router = APIRouter(prefix="/people", tags=["people"])


@router.get("/assignable")
def assignable(access: CurrentAccess, db: DB) -> list[dict]:
    """Within the person's reach: just themselves for "own", their team for
    "team", everyone switched on for "all"."""
    return [
        {"id": u.id, "name": u.full_name, "team": team_out(u.team), "isMe": u.id == access.user_id}
        for u in reachable_people(db, access)
    ]
