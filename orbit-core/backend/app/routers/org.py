from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, CurrentUser
from app.models import Division, Subdivision
from app.modules import BY_KEY

router = APIRouter(tags=["organisation"])


def org_tree(db) -> list[dict]:
    divisions = db.scalars(
        select(Division)
        .order_by(Division.sort_order)
        .options(selectinload(Division.subdivisions).selectinload(Subdivision.headquarters))
    )
    return [
        {
            "code": d.code,
            "name": d.name,
            "kind": d.kind,
            # A department an admin added has no screens and can be switched off;
            # the built-in ones bring their own icon, so they send none.
            "isBuiltIn": d.code in BY_KEY,
            "icon": d.icon,
            "isActive": d.is_active,
            "spansDivisions": BY_KEY[d.code].spans_divisions if d.code in BY_KEY else False,
            "teams": [
                {
                    "code": s.code,
                    "name": s.name,
                    "isActive": s.is_active,
                    "headquarters": [{"code": h.code, "name": h.name, "isActive": h.is_active} for h in s.headquarters],
                }
                for s in d.subdivisions
            ],
        }
        for d in divisions
    ]


@router.get("/org")
def org(_user: CurrentUser, db: DB) -> dict:
    """Divisions, their teams and headquarters. Names only; no records."""
    return {"divisions": org_tree(db)}
