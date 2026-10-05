"""What the other applications may read without signing in: the notices
showing for them now, and coming up (maintenance ahead of time).

    GET /public/notices?app=crm&company=getmeds

Nothing here is private: a notice is written to be shown to everyone it names.
"""

from fastapi import APIRouter

from app.announcements import Notices, state_of
from app.deps import DB
from app.routers.communications import showing

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/notices")
def notices(db: DB, table: Notices, app: str | None = None, company: str | None = None) -> dict:
    return {
        "notices": [
            {"id": n["id"], "kind": n["kind"], "level": n["level"], "title": n["title"], "body": n.get("body"),
             "startsAt": n["startsAt"], "endsAt": n.get("endsAt"), "state": state_of(n)}
            for n in showing(db, table, app, company)
        ]
    }
