"""Brings the database up to date. Runs when the API starts, and from the
users tool, so nobody has to remember to.

A database from before migrations (its `users` and `sessions` tables made by
create_all) is brought over by the first migration, which renames them to
nbfi_users and nbfi_sessions, with everyone in them.

Before any migration touches a SQLite file, a copy is kept beside it
(`<name>.before-<revision>-<time>`); if the migration fails, the copy is put
back, so the file is left exactly as it was. SQLite can't undo half a
migration by itself (its schema changes aren't rolled back with a failed
migration), so this is what makes a failure harmless.

The copy is made and put back through SQLite's own backup, never by copying
the file: the database runs in WAL mode, so saved rows can still be in the
`-wal` file beside it, and a file copy would leave them out. Every attempt
makes its own copy and checks it before migrating; an older copy is never
reused, since putting it back would undo whatever was saved after it.
"""

import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.config import API_DIR

log = logging.getLogger("finance.migrate")

# Where the database's migration revision is kept: nbfi_ like every table here.
VERSION_TABLE = "nbfi_alembic_version"


def _config(engine: Engine) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    # %% because the config file's reader treats a lone % as a placeholder,
    # and a password in an address may well have one.
    config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%"))
    # The migrations run on this engine, not one of their own made from the
    # address: its connections carry the app's settings (app/db.py), which a
    # pooler like Supabase's needs (no prepared statements).
    config.attributes["engine"] = engine
    return config


def _sqlite_file(engine: Engine) -> Path | None:
    if engine.url.get_backend_name() != "sqlite":
        return None
    database = engine.url.database
    return Path(database) if database and database != ":memory:" else None


# Any number will do, as long as it is always the same one (and not another app's).
MIGRATION_LOCK = 4303


def upgrade(engine: Engine) -> None:
    if engine.url.get_backend_name() != "postgresql":
        _upgrade(engine)
        return
    # On Postgres several copies of the API may start at once (Vercel starts one
    # per burst of traffic). One migrates; the others wait for it, then find the
    # database already up to date. The lock lasts one transaction: it ends with
    # it, whatever happens, even behind a pooler that hands the connection to
    # someone else afterwards.
    with engine.begin() as lock:
        lock.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK})
        # The schema changes must run on the very transaction holding the lock.
        config = _config(engine)
        config.attributes["connection"] = lock
        command.upgrade(config, "head")


def _upgrade(engine: Engine) -> None:
    config = _config(engine)
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        current = MigrationContext.configure(connection, opts={"version_table": VERSION_TABLE}).get_current_revision()
    if current == head:
        return
    file = _sqlite_file(engine)
    # A brand new database has nothing to lose, so nothing to copy.
    if file is None or not file.exists() or not tables:
        command.upgrade(config, "head")
        return
    engine.dispose()  # this process's connections go before the copy and before any put-back
    backup = file.with_name(f"{file.name}.before-{head}-{datetime.now():%Y%m%d-%H%M%S-%f}")
    _copy(file, backup)
    _check_backup(backup, tables, current)
    log.warning("database backed up to %s before migrating %s -> %s", backup, current, head)
    try:
        command.upgrade(config, "head")
    except Exception:
        engine.dispose()
        _copy(backup, file)
        log.error("migrating %s -> %s failed; the database was put back from %s", current, head, backup)
        raise


def _copy(source: Path, target: Path) -> None:
    """One whole, consistent copy through SQLite, saved rows still in the WAL included."""
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


class BackupNotUsable(RuntimeError):
    """The copy made before migrating isn't a whole copy of the database; nothing was migrated."""


def _check_backup(backup: Path, tables: set[str], revision: str | None) -> None:
    with closing(sqlite3.connect(backup)) as db:
        problems = [row[0] for row in db.execute("PRAGMA integrity_check")]
        copied = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        version = db.execute(f"SELECT version_num FROM {VERSION_TABLE}").fetchone() if VERSION_TABLE in copied else None
    if problems != ["ok"]:
        raise BackupNotUsable(f"The copy {backup.name} failed SQLite's integrity check ({'; '.join(problems[:3])}); the database was not migrated.")
    if missing := tables - copied:
        raise BackupNotUsable(f"The copy {backup.name} is missing tables {sorted(missing)}; the database was not migrated.")
    if (version[0] if version else None) != revision:
        raise BackupNotUsable(f"The copy {backup.name} is at revision {version[0] if version else None}, not {revision}; the database was not migrated.")
