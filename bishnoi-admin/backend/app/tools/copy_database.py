"""Copies this app's data from one database to another: from the SQLite file on
this computer into Neon (PostgreSQL) when moving online, or from Neon back into
a dated SQLite file as a backup.

    uv run python -m app.tools.copy_database --to "postgresql://...-pooler...neon.tech/neondb?sslmode=require"
    uv run python -m app.tools.copy_database backup          # BACKUP_FROM (or DATABASE_URL) into .data/backups/

Copying: the target gets this app's tables from the migrations (so it's at
the same version), is emptied of what the migrations put in it, and gets every
row of every table, parents before children; then the numbers are checked
table by table. A target that already has people in it is left alone unless
--replace is given. The source is only read, never changed.

Only this app's own tables (its prefix) are touched, so several apps can share
one database.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import MetaData, func, inspect, insert, select, text
from sqlalchemy.engine import Engine

from app.config import API_DIR, DATA_DIR, get_settings
from app.db import make_engine
from app.migrate import VERSION_TABLE, upgrade

KEEP_BACKUPS = 30
CHUNK = 1000


def prefix_of(engine: Engine) -> str:
    """This app's table prefix (nbad_), read from its version table."""
    # This app's own: a database can hold several apps' tables (Admin and
    # Platform share one), so the first version table found may be another's.
    if VERSION_TABLE in inspect(engine).get_table_names():
        return VERSION_TABLE.removesuffix("alembic_version")
    raise SystemExit("That database has no version table: it isn't one of this app's.")


def version(engine: Engine, prefix: str) -> str | None:
    with engine.connect() as c:
        return c.execute(text(f'SELECT version_num FROM "{prefix}alembic_version"')).scalar()


def describe(url: str) -> str:
    """Where a database is, without its password."""
    return make_engine(url).url.render_as_string(hide_password=True)


def tables_of(engine: Engine, prefix: str) -> MetaData:
    meta = MetaData()
    meta.reflect(engine, only=lambda name, _: name.startswith(prefix) and not name.endswith("alembic_version"))
    return meta


def has_people(engine: Engine, prefix: str) -> bool:
    users = f"{prefix}users"
    if users not in inspect(engine).get_table_names():
        return False
    with engine.connect() as c:
        return (c.execute(text(f'SELECT count(*) FROM "{users}"')).scalar() or 0) > 0


def empty(engine: Engine, meta: MetaData) -> None:
    """Takes out what the migrations seeded (roles, stages...), so the copy is exact."""
    names = [t.name for t in meta.sorted_tables]
    with engine.begin() as c:
        if engine.dialect.name == "postgresql":
            c.execute(text("TRUNCATE " + ", ".join(f'"{n}"' for n in names) + " RESTART IDENTITY CASCADE"))
        else:
            c.execute(text("PRAGMA foreign_keys=OFF"))
            for n in reversed(names):
                c.execute(text(f'DELETE FROM "{n}"'))


def copy(source_url: str, target_url: str, *, replace: bool = False) -> dict[str, int]:
    """Copies every row of this app's tables; answers the rows copied, by table."""
    source, target = make_engine(source_url), make_engine(target_url)
    prefix = prefix_of(source)
    print(f"From {describe(source_url)}\nTo   {describe(target_url)}")
    upgrade(target)
    if version(source, prefix) != version(target, prefix):
        raise SystemExit(
            f"The source is at version {version(source, prefix)} and this copy of the app at {version(target, prefix)}. "
            "Start the app once on the source so it's up to date, then copy."
        )
    if has_people(target, prefix) and not replace:
        raise SystemExit("The target already has people in it. Run again with --replace to overwrite it with the source's data.")
    src, dst = tables_of(source, prefix), tables_of(target, prefix)
    missing = sorted(set(src.tables) - set(dst.tables))
    if missing:
        raise SystemExit(f"The target has no {', '.join(missing)}: is it the same app?")
    empty(target, dst)
    copied: dict[str, int] = {}
    with source.connect() as read, target.begin() as write:
        if target.dialect.name == "sqlite":
            write.execute(text("PRAGMA foreign_keys=OFF"))
        for table in dst.sorted_tables:  # parents first
            if table.name not in src.tables:
                continue
            columns = [c.name for c in src.tables[table.name].columns if c.name in table.columns]
            rows = read.execute(select(*(src.tables[table.name].c[n] for n in columns))).mappings()
            count, batch = 0, []
            for row in rows:
                batch.append(dict(row))
                if len(batch) == CHUNK:
                    write.execute(insert(table), batch)
                    count, batch = count + len(batch), []
            if batch:
                write.execute(insert(table), batch)
                count += len(batch)
            copied[table.name] = count
        if target.dialect.name == "postgresql":
            # Numbered rows go on from the highest copied, not from 1.
            for table in dst.sorted_tables:
                for column in table.primary_key.columns:
                    seq = write.execute(text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": table.name, "c": column.name}).scalar()
                    if seq:
                        write.execute(text(f'SELECT setval(:s, COALESCE((SELECT max("{column.name}") FROM "{table.name}"), 0) + 1, false)'), {"s": seq})
    check(source, target, src, copied)
    return copied


def check(source: Engine, target: Engine, src: MetaData, copied: dict[str, int]) -> None:
    """Every table has as many rows on both sides, or the copy says which don't."""
    wrong = []
    with source.connect() as a, target.connect() as b:
        for name in copied:
            left = a.execute(select(func.count()).select_from(src.tables[name])).scalar()
            right = b.execute(text(f'SELECT count(*) FROM "{name}"')).scalar()
            if left != right:
                wrong.append(f"{name}: {left} here, {right} there")
    if wrong:
        raise SystemExit("The copy doesn't match:\n  " + "\n  ".join(wrong))
    print(f"Copied {sum(copied.values())} rows in {len(copied)} tables; every table matches.")


def backup(source_url: str) -> Path:
    """Today's copy of the database into .data/backups/, keeping the last few."""
    folder = DATA_DIR / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    name = API_DIR.parent.name.removeprefix("bishnoi-")  # admin
    file = folder / f"{name}-{date.today().isoformat()}.db"
    if file.exists():
        file.unlink()  # today's again: the latest wins
    copy(source_url, f"sqlite:///{file.as_posix()}", replace=True)
    old = sorted(folder.glob(f"{name}-*.db"))[:-KEEP_BACKUPS]
    for f in old:
        f.unlink()
    print(f"Backup: {file}{f' ({len(old)} older removed)' if old else ''}")
    return file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", nargs="?", choices=["copy", "backup"], default="copy")
    parser.add_argument("--from", dest="source", help="Where to copy from (default: DATABASE_URL, else this computer's SQLite file).")
    parser.add_argument("--to", dest="target", help="Where to copy to (for copy).")
    parser.add_argument("--replace", action="store_true", help="Overwrite a target that already has data.")
    args = parser.parse_args()
    settings = get_settings()
    source = args.source or settings.database_url
    if args.command == "backup":
        # The online database, while this computer keeps its own for trying things.
        backup(args.source or settings.backup_from or settings.database_url)
        return
    if not args.target:
        sys.exit("Say where to copy to: --to \"postgresql://...\"")
    copy(source, args.target, replace=args.replace)


if __name__ == "__main__":
    main()
