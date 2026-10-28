"""Brings the links between documents made before the document chain (feature plan step 9) into it:
each purchase order and its receipts, each count and its adjustment. Each is saved as a "document.linked" event and sent to the Platform, which keeps each link
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
from app.models import Adjustment, Count, PurchaseOrder, Receipt
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
        for r in db.scalars(select(Receipt).where(Receipt.order_id.is_not(None))):
            po = db.get(PurchaseOrder, r.order_id)
            business_events.link(db, args.company, business_events.ref("purchase_order", po.id, po.number), business_events.ref("receipt", r.id, r.number))
            made += 1
        for a in db.scalars(select(Adjustment).where(Adjustment.count_id.is_not(None))):
            c = db.get(Count, a.count_id)
            business_events.link(db, args.company, business_events.ref("count", c.id, c.number), business_events.ref("adjustment", a.id, a.number))
            made += 1
        db.commit()
        sent = business_events.flush(db, settings)
    print(f"{made} links saved; {sent} sent to the Platform" + ("" if settings.platform_api_url else " (not connected: they go when it is)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
