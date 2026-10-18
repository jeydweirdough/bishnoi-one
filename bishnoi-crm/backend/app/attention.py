"""What needs someone's attention today: the prompts on their home page.

A few clear prompts, each with why and one thing to do, ranked so the most
pressing come first (the home page shows five). Only what the person can act
on: their own customers, follow-ups and quotes; and for an approver, the
quotes waiting on them. Each prompt has a key, so it can be put aside for a
while (snoozed) or for good (dismissed), and comes back if it changes (a
birthday is a new one each year).

When something is worth a prompt is set per division (Settings → Attention,
AttentionRule): how long before a customer is quiet, how far ahead to say a
birthday is coming, and so on.
"""

from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clidp
from app.access import Access
from app.config import Settings
from app.extra import applies, fields_for
from app.models import PLANNED_KINDS, Activity, AttentionDismissal, AttentionRule, Company, Product, Quote, User, Visit
from app.pricing import today
from app.scope import within

BIRTHDAY, ANNIVERSARY, CATEGORY = "x_birth_date", "x_anniversary", "x_category"


@dataclass
class Prompt:
    key: str
    kind: str
    title: str
    reason: str
    action: str
    href: str
    rank: int


def rule_for(db: Session, team_id: str | None) -> AttentionRule:
    """The division's own rule, else everyone's, else the defaults."""
    found = db.scalar(select(AttentionRule).where(AttentionRule.team_id == team_id)) if team_id else None
    found = found or db.scalar(select(AttentionRule).where(AttentionRule.team_id.is_(None)))
    return found or AttentionRule(quiet_days=45, notice_days=7, clidp_days=30, stuck_days=2)


def _next(day: str, on: date) -> date | None:
    """The next time a yearly date comes round, from `on` (29 Feb falls on 28 Feb in other years)."""
    try:
        d = date.fromisoformat(day)
    except (TypeError, ValueError):
        return None
    for year in (on.year, on.year + 1):
        when = date(year, d.month, min(d.day, monthrange(year, d.month)[1]))
        if when >= on:
            return when
    return None


def _aware(t: datetime) -> datetime:
    """SQLite hands times back without their zone: they're UTC."""
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _days(n: int) -> str:
    return "today" if n == 0 else "tomorrow" if n == 1 else f"in {n} days"


def prompts(db: Session, access: Access, me: User, settings: Settings) -> list[Prompt]:
    on = date.fromisoformat(today(settings.org_timezone))
    now = datetime.now(UTC)
    rule = rule_for(db, me.team_id)
    out: list[Prompt] = []
    mine = list(db.scalars(select(Company).where(Company.owner_id == me.id)).unique())

    # Follow-ups past their time: a promise not kept.
    overdue = db.scalars(
        select(Activity).where(Activity.owner_id == me.id, Activity.kind.in_(PLANNED_KINDS), Activity.done_at.is_(None), Activity.at < now).order_by(Activity.at)
    ).unique()
    for a in list(overdue)[:5]:
        late = max(0, (now - _aware(a.at)).days)
        who = f" with {a.company.name}" if a.company else ""
        out.append(Prompt(
            f"overdue:{a.id}", "overdue", f"{a.subject}{who}", "Due today and not done yet." if late == 0 else f"{late} {'day' if late == 1 else 'days'} overdue.",
            "Open it", f"/companies/{a.company_id}" if a.company_id else "/activities", 90 + min(late, 9),
        ))

    # Birthdays and anniversaries coming up: a reason to call.
    for c in mine:
        for key, what in ((BIRTHDAY, "birthday"), (ANNIVERSARY, "wedding anniversary")):
            when = _next((c.extra or {}).get(key), on)
            if when is None or (when - on).days > rule.notice_days:
                continue
            n = (when - on).days
            out.append(Prompt(
                f"{key}:{c.id}:{when.year}", "occasion", f"{c.name}'s {what} is {_days(n)}", f"On {when:%A}, {when.day} {when:%B}. A call or a greeting keeps the relationship warm.",
                "Open their page", f"/companies/{c.id}", 80 - n,
            ))

    # Customers gone quiet: nothing done with them for a while. Category A first.
    ids = [c.id for c in mine]
    if ids:
        done = select(Activity.company_id, func.max(Activity.done_at)).where(Activity.company_id.in_(ids), Activity.done_at.is_not(None)).group_by(Activity.company_id)
        touched = {cid: _aware(at) for cid, at in db.execute(done).all()}
        for cid, at in db.execute(select(Visit.company_id, func.max(Visit.visited_at)).where(Visit.company_id.in_(ids)).group_by(Visit.company_id)).all():
            touched[cid] = max(_aware(at), touched.get(cid) or _aware(at))
        for c in mine:
            last = touched.get(c.id) or _aware(c.created_at)
            quiet = (now - last).days
            if quiet < rule.quiet_days:
                continue
            top = (c.extra or {}).get(CATEGORY) == "A"
            out.append(Prompt(
                f"quiet:{c.id}:{quiet // rule.quiet_days}", "quiet", f"{c.name} hasn't heard from you in {quiet} days",
                ("A category A customer. " if top else "") + "Plan a visit or a call before they drift.", "Open their page", f"/companies/{c.id}", (65 if top else 45) + min(quiet // 15, 9),
            ))

    # Quotes waiting too long for approval: a sale stuck. Mine, and for an approver, the team's.
    stuck_before = now - timedelta(days=rule.stuck_days)
    waiting = select(Quote).where(Quote.approval_status == "pending", Quote.created_at < stuck_before)
    # A quote at a requested price waits for Finance, not the team lead.
    def finances(q: Quote) -> bool:
        return "price" in (q.approval_reasons or [])

    for q in db.scalars(waiting.where(Quote.owner_id == me.id)).unique():
        who = "Finance is reviewing the price you asked for" if finances(q) else "Remind your team lead"
        out.append(Prompt(f"stuck:{q.id}", "quote", f"Quote {q.number} is still waiting for approval", f"{who}: the customer is waiting.", "Open the quote", f"/quotes/{q.id}", 70))
    if access.can("quotes.approve"):
        for q in db.scalars(within(waiting, Quote, access).where(Quote.owner_id != me.id)).unique():
            if finances(q):
                continue
            out.append(Prompt(f"approve:{q.id}", "quote", f"Quote {q.number} is waiting for your approval", f"{getattr(db.get(User, q.owner_id), 'full_name', 'A salesperson')}'s customer is waiting.", "Review it", f"/quotes/{q.id}", 82))

    # Behind on this month's revenue target, with the month running out.
    from app.routers.sales import results  # here: sales needs this module's neighbours first

    try:
        month = results(db, access, settings, "mine", on.isoformat()[:7], None)["totals"]
    except Exception:  # noqa: BLE001 (a prompt is never worth a broken home page)
        month = {}
    target, won = month.get("targetCentavos") or 0, month.get("wonCentavos") or 0
    days_in, left = monthrange(on.year, on.month)[1], monthrange(on.year, on.month)[1] - on.day
    if target and won < target * on.day / days_in * 0.85:
        out.append(Prompt(
            f"target:{on:%Y-%m}:{round(100 * won / target) // 10}", "target", "You're behind this month's revenue target",
            f"{round(100 * won / target)}% won, {round(100 * on.day / days_in)}% of the month gone, {left} {'day' if left == 1 else 'days'} left.", "See your open deals", "/deals", 85,
        ))

    # CLIDPs running out, for the divisions that sell on them.
    if me.team and me.team.name.upper() in clidp.NEEDED_BY:
        soon = (on + timedelta(days=rule.clidp_days)).isoformat()
        for p in db.scalars(select(Product).where(Product.is_active)):
            until = str((p.extra or {}).get(clidp.VALID_UNTIL) or "")
            if until and on.isoformat() <= until <= soon:
                out.append(Prompt(f"clidp:{p.id}:{until}", "clidp", f"{p.name}'s CLIDP runs out on {until}", "Bids and quotes with it will be refused after that. Tell Regulatory.", "See the products", f"/products?q={p.code}", 75))

    # Profiles barely started: one prompt for all of them.
    fields = fields_for(db, "company", added_only=True, shown_only=True)
    thin = []
    for c in mine:
        own = [f for f in fields if applies(f, c.team_id, c.status) and f.type != "customer"]
        if len(own) >= 4:
            filled = sum(1 for f in own if (c.extra or {}).get(f.key) not in (None, "", []))
            if filled / len(own) < 0.5:
                thin.append((filled / len(own), c))
    if thin:
        thin.sort(key=lambda t: t[0])
        first = thin[0][1]
        out.append(Prompt(
            f"profiles:{len(thin)}", "profile", f"{len(thin)} of your customers' profiles are under half done" if len(thin) > 1 else f"{first.name}'s profile is under half done",
            "Fill in what you learned on the last visit: it makes targeting better.", "Complete a profile", f"/companies/{first.id}/edit?complete=1", 20,
        ))

    put_aside = {d.key: d.until for d in db.scalars(select(AttentionDismissal).where(AttentionDismissal.user_id == me.id))}
    shown = [p for p in out if not (p.key in put_aside and (put_aside[p.key] is None or put_aside[p.key] > on.isoformat()))]
    return sorted(shown, key=lambda p: -p.rank)


def as_json(found: list[Prompt]) -> list[dict]:
    return [asdict(p) for p in found]
