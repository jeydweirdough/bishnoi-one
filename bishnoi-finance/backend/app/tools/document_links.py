"""Brings the links between documents made before the document chain (feature plan step 9) into it:
each voided invoice and the invoice that replaced it. Each is saved as a "document.linked" event and sent to the Platform, which keeps each link
once, so running it again changes nothing.

    uv run python -m app.tools.document_links
"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import business_events
from app.config import get_settings
from app.db import make_engine
from app.migrate import upgrade
from app.models import Invoice


def main() -> int:
    parser = argparse.ArgumentParser(description="Bring existing document links into the document chain.")

    args = parser.parse_args()
    settings = get_settings()
    engine = make_engine(settings.database_url)
    upgrade(engine)
    made = 0
    with Session(engine) as db:
        for new in db.scalars(select(Invoice).where(Invoice.replaces_id.is_not(None))):
            old = db.get(Invoice, new.replaces_id)
            business_events.link(db, None, business_events.ref("invoice", old.id, old.number), business_events.ref("invoice", new.id, new.number))
            made += 1
        db.commit()
        sent = business_events.flush(db, settings)
    print(f"{made} links saved; {sent} sent to the Platform" + ("" if settings.platform_api_url else " (not connected: they go when it is)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
