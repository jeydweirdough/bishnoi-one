"""Brings the database up to date. Runs when the API starts, and from the
users tool, so nobody has to remember to.

A database made before migrations existed (its tables made by create_all) is
recognised by its `users` table and marked as being at 0001 first.

Before any migration touches a SQLite file, a copy is kept beside it
(`<name>.before-<revision>`); if the migration fails, the copy is put back,
so the file is left exactly as it was. SQLite can't undo half a migration by
itself (its schema changes aren't rolled back with a failed migration), so
this is what makes a failure harmless. An existing copy is never overwritten:
it is the last good one.
"""

import logging
import shutil
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.config import API_DIR

log = logging.getLogger("sales.migrate")


def _config(engine: Engine) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    return config


def _sqlite_file(engine: Engine) -> Path | None:
    if engine.url.get_backend_name() != "sqlite":
        return None
    database = engine.url.database
    return Path(database) if database and database != ":memory:" else None


def upgrade(engine: Engine) -> None:
    config = _config(engine)
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        current = MigrationContext.configure(connection).get_current_revision()
    if current is None and "users" in tables:
        command.stamp(config, "0001")
        current = "0001"
    if current == head:
        return
    file = _sqlite_file(engine)
    if file is None or not file.exists() or current is None:
        command.upgrade(config, "head")
        return
    engine.dispose()  # let go of the file so the copy is whole
    backup = file.with_name(f"{file.name}.before-{head}")
    if not backup.exists():
        shutil.copy2(file, backup)
        log.warning("database backed up to %s before migrating %s -> %s", backup, current, head)
    try:
        command.upgrade(config, "head")
    except Exception:
        engine.dispose()
        for extra in ("-wal", "-shm"):
            file.with_name(file.name + extra).unlink(missing_ok=True)
        shutil.copy2(backup, file)
        log.error("migrating %s -> %s failed; the database was put back from %s", current, head, backup)
        raise
