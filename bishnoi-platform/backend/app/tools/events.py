"""Business events from the command line (feature plan step 7): the nightly check, for a scheduler
(Coolify's scheduled task, cron) when GET /cron/events-check isn't used.

    uv run python -m app.tools.events check   # deliver what is due, ask each app to send what it holds, count what is stuck
    uv run python -m app.tools.events run     # deliver what is due now
"""

import argparse
import json

from app import events
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade


def main() -> int:
    parser = argparse.ArgumentParser(description="Business events.")
    parser.add_argument("action", choices=["check", "run"])
    args = parser.parse_args()
    settings = get_settings()
    engine = make_engine(settings.database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        said = events.check(db, settings) if args.action == "check" else events.deliver_due(db, settings)
    print(json.dumps(said))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
