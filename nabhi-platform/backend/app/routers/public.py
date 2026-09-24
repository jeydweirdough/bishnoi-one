"""What the other applications may read without signing in: the notices
showing for them now, and coming up (maintenance ahead of time).

    GET /public/notices?app=crm&company=getmeds

Nothing here is private: a notice is written to be shown to everyone it names.
"""

from fastapi import APIRouter

from app.api import iso
from app.deps import DB
from app.routers.communications import showing, state_of

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/notices")
def notices(db: DB, app: str | None = None, company: str | None = None) -> dict:
    return {
        "notices": [
            {"id": n.id, "kind": n.kind, "level": n.level, "title": n.title, "body": n.body,
             "startsAt": iso(n.starts_at), "endsAt": iso(n.ends_at), "state": state_of(n)}
            for n in showing(db, app, company)
        ]
    }
