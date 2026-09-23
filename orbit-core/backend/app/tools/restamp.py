"""Moves records and files from before there were companies into the first one (Getmeds).

    uv run python -m app.tools.restamp              stamp every record without a company, move loose files
    uv run python -m app.tools.restamp --dry-run    only count what would change

Run it once when upgrading to companies: after `alembic upgrade head` (or
`python -m app.seed`), before people use the new version. Records without a
company are invisible to everyone, so nothing is shown twice or to the wrong
company meanwhile. Safe to stop and run again: it picks up what's left, in
small batches with a pause between them so Sanity's rate limit isn't hit.
Take a Sanity export (or copy .data/) first.
"""

import argparse
import logging
import sys
import time

from app.config import get_settings
from app.store import build_records
from app.store.files import FileStore
from app.store.records import Patch
from app.tenancy import FIRST_ORG_ID

log = logging.getLogger("crm.restamp")

BATCH = 100
PAUSE_SECONDS = 0.5


def restamp_records(backend, *, batch: int = BATCH, pause: float = PAUSE_SECONDS, dry_run: bool = False) -> int:
    if dry_run:
        return len(backend.without_org(1_000_000))
    done = 0
    while ids := backend.without_org(batch):
        backend.commit([Patch(i, {"orgId": FIRST_ORG_ID}) for i in ids])
        done += len(ids)
        left = backend.without_org(batch)
        if set(left) & set(ids):
            raise RuntimeError(f"records {sorted(set(left) & set(ids))[:5]} kept no company after being stamped")
        print(f"  {done} records stamped...", flush=True)
        if left and pause:
            time.sleep(pause)
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tools.restamp", description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="count what would change, change nothing")
    args = parser.parse_args(argv)

    settings = get_settings()
    records = build_records(settings)
    print(f"Records store: {records.kind}")
    count = restamp_records(records.backend, dry_run=args.dry_run)
    print(f"{count} records {'would be' if args.dry_run else 'were'} put in Getmeds.")

    files = FileStore(settings.files_path).for_org(FIRST_ORG_ID)
    if args.dry_run:
        root = settings.files_path
        loose = [p for p in root.iterdir() if p.is_file() and len(p.name) == 32] if root.is_dir() else []
        print(f"{len(loose)} files would move into Getmeds' folder.")
    else:
        print(f"{files.adopt_loose_files()} files moved into Getmeds' folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
