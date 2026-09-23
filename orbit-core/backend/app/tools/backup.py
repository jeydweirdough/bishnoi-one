"""One dated archive of everything, and the older ones tidied up.

    uv run python -m app.tools.backup --out-dir /backups
    uv run python -m app.tools.backup --out-dir /backups --dry-run

The archive is an --all-companies export (app/tools/export.py): every
company's rows, records and uploaded files, in one zip named for the moment it
was taken, e.g. orbit-20260921-030000.zip. It is re-opened and checked before
anything else is touched, and a backup that doesn't come back out again is a
failure: the tool says so, exits non-zero and deletes nothing.

Then the old ones: the newest 30 archives are kept, and so is the first
archive of each of the last 12 months that has one, which leaves a year of
month-ends behind without the pile growing forever. --keep-daily and
--keep-monthly change those two numbers, --dry-run says what it would delete
and deletes nothing.

This tool writes to the directory it is given and nowhere else. Whatever runs
it on a schedule, and whatever copies the directory somewhere safe afterwards,
is somebody else's job: a backup left on the same machine as the database is
not a backup.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.store.records import StoreError
from app.tools.export import ExportError, World, export, open_world

STAMP = "%Y%m%d-%H%M%S"
NAME = re.compile(r"^orbit-(\d{8}-\d{6})\.zip$")
KEEP_DAILY = 30
KEEP_MONTHLY = 12


def archive_name(taken: datetime) -> str:
    return f"orbit-{taken.strftime(STAMP)}.zip"


def dated_archives(out_dir: Path) -> list[tuple[datetime, Path]]:
    """The archives in the directory, newest first. The date comes from the name, not from the file's
    timestamp, which copying a directory about is free to change."""
    found = []
    for path in out_dir.iterdir() if out_dir.is_dir() else []:
        match = NAME.fullmatch(path.name)
        if match and path.is_file():
            found.append((datetime.strptime(match.group(1), STAMP), path))
    return sorted(found, reverse=True)


def verify(path: Path) -> dict:
    """Re-opens what was just written and reads its manifest, so a broken archive is found now rather than
    on the day someone needs it."""
    try:
        with ZipFile(path) as archive:
            damaged = archive.testzip()
            if damaged:
                raise ExportError(f"{path.name} is damaged: {damaged} doesn't read back.")
            manifest = json.loads(archive.read("manifest.json"))
    except (BadZipFile, KeyError, ValueError, OSError) as exc:
        raise ExportError(f"{path.name} can't be read back: {exc}") from exc
    if not manifest.get("companies"):
        raise ExportError(f"{path.name} names no companies; it is not a whole backup.")
    return manifest


def to_keep(dated: list[tuple[datetime, Path]], keep_daily: int, keep_monthly: int) -> set[Path]:
    """The newest `keep_daily`, plus the first archive of each of the last `keep_monthly` months that has one."""
    keep = {path for _, path in dated[:keep_daily]}
    months: dict[str, Path] = {}
    for taken, path in reversed(dated):  # oldest first, so the one each month keeps is its first
        months.setdefault(taken.strftime("%Y-%m"), path)
    for month in sorted(months, reverse=True)[:keep_monthly]:
        keep.add(months[month])
    return keep


def sweep(dated: list[tuple[datetime, Path]], keep_daily: int, keep_monthly: int, dry_run: bool) -> list[Path]:
    keep = to_keep(dated, keep_daily, keep_monthly)
    gone = []
    for taken, path in dated:
        if path in keep:
            continue
        print(f"{'would delete' if dry_run else 'deleted'} {path.name} (taken {taken:%d %B %Y, %H:%M})")
        if not dry_run:
            path.unlink()
        gone.append(path)
    return gone


def make_archive(world: World, out_dir: Path, taken: datetime) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / archive_name(taken)
    manifests = export(world, path, org=None, all_companies=True, force=True)
    print(f"wrote {path.name} ({path.stat().st_size:,} bytes): {', '.join(m['company']['slug'] for m in manifests)}")
    return path


def main(argv: list[str] | None = None, world: World | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tools.backup", description=__doc__.split("\n")[0])
    parser.add_argument("--out-dir", metavar="DIR", required=True, help="where the dated archives are kept")
    parser.add_argument("--keep-daily", type=int, default=KEEP_DAILY, help=f"recent archives (default {KEEP_DAILY})")
    parser.add_argument("--keep-monthly", type=int, default=KEEP_MONTHLY, help=f"how many months (default {KEEP_MONTHLY})")
    parser.add_argument("--dry-run", action="store_true", help="say what would happen, change nothing")
    args = parser.parse_args(argv)
    if args.keep_daily < 1 or args.keep_monthly < 0:
        parser.error("--keep-daily is at least 1, and --keep-monthly is not negative")

    out_dir = Path(args.out_dir)
    try:
        if args.dry_run:
            print(f"would write {archive_name(datetime.now())} to {out_dir}")
        else:
            world = world or open_world(get_settings())
            verify(make_archive(world, out_dir, datetime.now()))
        dated = dated_archives(out_dir)
        gone = sweep(dated, args.keep_daily, args.keep_monthly, args.dry_run)
        print(f"{len(dated) - len(gone)} archive(s) kept, {len(gone)} {'to delete' if args.dry_run else 'deleted'}.")
    except ExportError as exc:
        print(exc, file=sys.stderr)
        return 1
    except (StoreError, SQLAlchemyError) as exc:
        print(f"There is no backup: the database or the records store wouldn't give up everything.\n  {exc}",
              file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Couldn't write the backup: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
