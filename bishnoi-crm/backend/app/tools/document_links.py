"""Brings the links between documents made before the document chain (feature plan step 9) into it:
each deal and its quotes. Each is saved as a "document.linked" event and sent to the Platform, which keeps each link
once, so running it again changes nothing.

    uv run python -m app.tools.document_links --company getmeds
"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import business_events
from app.config import get_settings
from app.db import make_engine
from app.migrate import upgrade
from app.models import Deal, Quote
from app.tenants import database_url


def main() -> int:
    parser = argparse.ArgumentParser(description="Bring existing document links into the document chain.")
    parser.add_argument("--company", required=True, help="the company's short name, e.g. getmeds")
    args = parser.parse_args()
    settings = get_settings()
    engine = make_engine(database_url(settings.database_url, args.company))
    upgrade(engine)
    made = 0
    with Session(engine) as db:
        for q in db.scalars(select(Quote).where(Quote.deal_id.is_not(None))):
            deal = db.get(Deal, q.deal_id)
            business_events.link(db, args.company, business_events.ref("deal", deal.id, deal.name[:60]), business_events.ref("quote", q.id, q.number))
            made += 1
        db.commit()
        sent = business_events.flush(db, settings)
    print(f"{made} links saved; {sent} sent to the Platform" + ("" if settings.platform_api_url else " (not connected: they go when it is)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
