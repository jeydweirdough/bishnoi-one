"""Alembic's entry point. The database is this app's own (DATABASE_URL)."""

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db import Base
from app.migrate import VERSION_TABLE
from app import models  # noqa: F401  (registers the tables)

config = context.config
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run() -> None:
    # The app's own engine when the app runs the migrations (app/migrate.py);
    # one made from the address when alembic is run by hand.
    engine = config.attributes.get("engine") or engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # Rebuilding a table drops the old one, and with foreign keys on, its
            # ON DELETE CASCADE children would go with it. Off while migrating
            # (it can't change inside a transaction), on after.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        # render_as_batch: SQLite can only change a table by rebuilding it.
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            connection.commit()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


run()
