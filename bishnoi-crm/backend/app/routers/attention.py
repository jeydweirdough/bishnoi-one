"""The prompts on someone's home page (app/attention.py), putting one aside,
and Settings → Attention: when something is worth a prompt, per division."""

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import Field
from sqlalchemy import select

from app import attention
from app.access import Access, CurrentAccess, require
from app.api import Api, field_error, team_out
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import AttentionDismissal, AttentionRule, Team
from app.pricing import today

router = APIRouter(tags=["attention"])
Manage = Annotated[Access, Depends(require("admin.settings"))]


@router.get("/attention")
def read_attention(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep) -> list[dict]:
    """What needs this person's attention, most pressing first."""
    return attention.as_json(attention.prompts(db, access, me, settings))


class PutAsideIn(Api):
    key: str = Field(min_length=1, max_length=120)
    # Snoozed for a week, or dismissed for good.
    how: Literal["snooze", "dismiss"] = "snooze"


@router.post("/attention/put-aside", status_code=status.HTTP_204_NO_CONTENT)
def put_aside(me: CurrentUser, db: DB, settings: SettingsDep, body: PutAsideIn) -> Response:
    until = (date.fromisoformat(today(settings.org_timezone)) + timedelta(days=7)).isoformat() if body.how == "snooze" else None
    found = db.get(AttentionDismissal, (me.id, body.key)) or AttentionDismissal(user_id=me.id, key=body.key)
    found.until = until
    db.add(found)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Settings → Attention -----------------------------------------------------------------


def rule_out(r: AttentionRule, team: Team | None) -> dict:
    return {"team": team_out(team), "quietDays": r.quiet_days, "noticeDays": r.notice_days, "clidpDays": r.clidp_days, "stuckDays": r.stuck_days}


@router.get("/admin/attention-rules")
def read_rules(_: Manage, db: DB) -> dict:
    """Everyone's rule, and the divisions that have their own."""
    rules = {r.team_id: r for r in db.scalars(select(AttentionRule))}
    everyone = rules.get(None) or AttentionRule(quiet_days=45, notice_days=7, clidp_days=30, stuck_days=2)
    teams = {t.id: t for t in db.scalars(select(Team).order_by(Team.name))}
    return {
        "everyone": rule_out(everyone, None),
        "divisions": [rule_out(r, teams.get(tid)) for tid, r in rules.items() if tid and tid in teams],
        "teams": [{"id": t.id, "name": t.name} for t in teams.values() if t.is_active],
    }


class RuleIn(Api):
    # None: everyone's rule.
    team_id: str | None = Field(None, max_length=36)
    quiet_days: int = Field(ge=1, le=365)
    notice_days: int = Field(ge=0, le=60)
    clidp_days: int = Field(ge=1, le=365)
    stuck_days: int = Field(ge=1, le=60)


@router.put("/admin/attention-rules")
def save_rule(access: Manage, me: CurrentUser, db: DB, body: RuleIn) -> dict:
    team = db.get(Team, body.team_id) if body.team_id else None
    if body.team_id and team is None:
        raise field_error("teamId", "Pick a team from the list.")
    rule = db.scalar(select(AttentionRule).where(AttentionRule.team_id == body.team_id if body.team_id else AttentionRule.team_id.is_(None))) or AttentionRule(team_id=body.team_id)
    rule.quiet_days, rule.notice_days, rule.clidp_days, rule.stuck_days = body.quiet_days, body.notice_days, body.clidp_days, body.stuck_days
    db.add(rule)
    audit(db, me, "attention.updated", target=team.name if team else "Everyone", target_type="settings")
    db.commit()
    return read_rules(access, db)


@router.delete("/admin/attention-rules/{team_id}")
def drop_rule(access: Manage, me: CurrentUser, db: DB, team_id: str) -> dict:
    """A division goes back to everyone's rule."""
    rule = db.scalar(select(AttentionRule).where(AttentionRule.team_id == team_id))
    if rule is not None:
        team = db.get(Team, team_id)
        audit(db, me, "attention.updated", target=f"{team.name if team else 'A division'}: back to everyone's", target_type="settings")
        db.delete(rule)
        db.commit()
    return read_rules(access, db)
