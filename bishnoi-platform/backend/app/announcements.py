"""Announcements, kept in Discord (app/discord.py), not in this app's database.

Each one is a row of the "announcements" table: a thread in the
announcements channel named with its id, ANN-YYYYMMDD-NNNN (numbered from
0001 each day, in the company's time zone), holding the announcement as JSON.
In mock mode they're in .data/discord-mock/announcements.json instead.

Announcements made before this lived in nbpl_announcements. On the first
start they're copied across, keeping their ids, and taken out of the
database, so Discord is the only place they're kept.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, select

from app.config import Settings
from app.discord import DiscordError, Table, day_ids

FIELDS = ("kind", "level", "title", "body", "companyId", "applicationId", "startsAt", "endsAt", "publishedAt",
          "createdBy", "createdAt", "updatedAt")


def make_table(settings: Settings) -> Table:
    return Table(
        "announcements",
        webhook_url=settings.secret(settings.discord_announcements_webhook_url),
        bot_token=settings.secret(settings.discord_bot_token),
        enabled=settings.discord_enabled,
        mode=settings.discord_mode,
        per_minute=settings.discord_max_per_minute,
        mock_dir=settings.discord_mock_dir,
        describe=lambda n: f"{n.get('kind', 'announcement').title()}: {n.get('title', '')}",
    )


def iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def when(value: str | None) -> datetime | None:
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def state_of(n: dict, now: datetime | None = None) -> str:
    """draft, scheduled, showing or ended."""
    now = now or datetime.now(UTC)
    if not n.get("publishedAt"):
        return "draft"
    if when(n["startsAt"]) > now:
        return "scheduled"
    if n.get("endsAt") and when(n["endsAt"]) <= now:
        return "ended"
    return "showing"


def next_id(table: Table, settings: Settings) -> str:
    return day_ids("ANN", list(table.rows), settings.org_timezone)


def save(table: Table, row_id: str, data: dict) -> None:
    """Stores it in Discord; says so plainly when Discord doesn't take it (nothing changes then)."""
    try:
        table.save(row_id, data)
    except DiscordError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Discord didn't take it, so nothing was saved: {e}. Try again in a moment.") from None


def remove(table: Table, row_id: str) -> None:
    try:
        table.delete(row_id)
    except DiscordError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Discord didn't take it, so nothing was deleted: {e}. Try again in a moment.") from None


def import_from_database(table: Table, sessions) -> int:
    """Copies what's still in nbpl_announcements into the table, keeping each id, then takes it out."""
    from app.models import Announcement

    with sessions() as db:
        old = db.scalars(select(Announcement)).all()
        for n in old:
            if n.id in table.rows:
                continue
            table.save(n.id, {
                "id": n.id, "kind": n.kind, "level": n.level, "title": n.title, "body": n.body,
                "companyId": n.company_id, "applicationId": n.application_id,
                "startsAt": iso(n.starts_at), "endsAt": iso(n.ends_at), "publishedAt": iso(n.published_at),
                "createdBy": n.created_by, "createdAt": iso(n.created_at), "updatedAt": iso(n.updated_at),
            })
        if old:
            db.execute(delete(Announcement))
            db.commit()
        return len(old)


def notices_table(request: Request) -> Table:
    table: Table = request.app.state.notices
    table.fresh()  # another server may have saved since this one read Discord
    return table


Notices = Annotated[Table, Depends(notices_table)]
