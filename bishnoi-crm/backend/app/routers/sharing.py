"""Whether a division's customers show to other divisions.

Shown (the default): when someone in another division adds a customer, a
customer here with the same name, email or phone is named to them ("Also in
the CRM: St. Luke's · B2C") so nobody adds one twice; and a field that points
at another customer (a doctor's hospital) can pick it. Never more than the
name and the division: details stay with the division.

Hidden: other divisions don't see them at all. People in the division, and
anyone whose role reaches it, still do.

Set by the CRM's administrator (People and access → Teams) for any division,
and by a manager for the divisions they manage.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.access import Access, CurrentAccess
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Company, Team, User
from app.scope import reaches

router = APIRouter(tags=["customers"])


def may_set(access: Access, me: User, team: Team) -> bool:
    return access.can("admin.teams") or team.manager_id == me.id


def shown_to(company: Company, access: Access) -> bool:
    """Whether a customer can be named to someone (look-alikes, customer fields):
    always within its own division and to whoever reaches it; to the other
    divisions while its division shows them."""
    if company.team is None or company.team.share_customers or reaches(company, access):
        return True
    return company.team_id == access.team_id or company.team_id in access.team_ids


def sharing_out(team: Team) -> dict:
    return {"id": team.id, "name": team.name, "shareCustomers": team.share_customers}


@router.get("/customer-sharing")
def list_sharing(access: CurrentAccess, me: CurrentUser, db: DB) -> list[dict]:
    """The divisions this person sets it for: every one for an administrator, the ones they manage for a manager."""
    teams = db.scalars(select(Team).where(Team.is_active).order_by(func.lower(Team.name)))
    return [sharing_out(t) for t in teams if may_set(access, me, t)]


class SharingIn(BaseModel):
    share_customers: bool

    model_config = {"alias_generator": lambda s: "shareCustomers" if s == "share_customers" else s, "populate_by_name": True}


@router.put("/customer-sharing/{team_id}")
def set_sharing(access: CurrentAccess, me: CurrentUser, db: DB, team_id: str, body: SharingIn) -> dict:
    team = db.get(Team, team_id)
    if team is None or not may_set(access, me, team):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such division you manage.")
    if team.share_customers != body.share_customers:
        team.share_customers = body.share_customers
        audit(db, me, "team.sharing_on" if body.share_customers else "team.sharing_off", target=team.name, target_type="team", target_id=team.id)
        db.commit()
    return sharing_out(team)
