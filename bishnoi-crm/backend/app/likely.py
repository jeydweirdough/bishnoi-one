"""How likely a deal is to be won: worked out, not typed.

It starts from its stage's own probability (Settings > Deal stages), and is
adjusted by the owner's record over the last 12 months against everyone's:
how many of their deals were won rather than lost, and how many of their
quotes became orders rather than being rejected or running out. A rep who
wins more often than the rest gets a higher figure at the same stage, one
who wins less a lower one. With fewer than MIN_DECIDED decided deals and
quotes to go by (the rep's, or everyone's), it's the stage's own.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Deal, DealStage, Quote

MIN_DECIDED = 5
OVER_DAYS = 365


def _record(db: Session, owner_id: str | None, on: date) -> tuple[int, int]:
    """(won, decided): deals won or lost, quotes ordered or not, over the last OVER_DAYS."""
    since = datetime.now(UTC) - timedelta(days=OVER_DAYS)
    deals = select(DealStage.outcome, func.count()).select_from(Deal).join(DealStage, DealStage.code == Deal.stage_code).where(
        DealStage.outcome.in_(("won", "lost")), Deal.closed_at.is_not(None), Deal.closed_at >= since
    )
    if owner_id:
        deals = deals.where(Deal.owner_id == owner_id)
    by = dict(db.execute(deals.group_by(DealStage.outcome)).all())
    won, decided = by.get("won", 0), by.get("won", 0) + by.get("lost", 0)

    quotes = select(Quote.sales_order, Quote.approval_status, Quote.letter_status, Quote.valid_until).where(Quote.created_at >= since)
    if owner_id:
        quotes = quotes.where(Quote.owner_id == owner_id)
    today = on.isoformat()
    for order, approval, letter, valid_until in db.execute(quotes):
        if order:
            won += 1
            decided += 1
        elif "rejected" in (approval, letter) or (valid_until and valid_until < today):
            decided += 1
    return won, decided


def likely(db: Session, owner_id: str, stage: DealStage, on: date) -> tuple[int, str]:
    """(the probability, in words why)."""
    base = stage.probability
    if stage.outcome != "open":
        return base, f"{stage.name}: {base}%."
    mine_won, mine = _record(db, owner_id, on)
    all_won, everyone = _record(db, None, on)
    if mine < MIN_DECIDED or everyone < MIN_DECIDED or all_won == 0:
        return base, f"{base}%, the {stage.name} stage's own: not enough won or lost deals and quotes in the last 12 months to go by yet."
    mine_rate, all_rate = mine_won / mine, all_won / everyone
    value = max(1, min(99, round(base * mine_rate / all_rate)))
    return value, (
        f"{base}% at {stage.name}, adjusted for the owner's record: {mine_won} of {mine} deals and quotes won in the last 12 months "
        f"({round(100 * mine_rate)}%), against {round(100 * all_rate)}% for everyone."
    )
