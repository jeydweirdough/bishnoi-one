"""Alembic's entry point. The database is this app's own (DATABASE_URL)."""

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db import Base
from app.migrate import VERSION_TABLE
from app import models  # noqa: F401  (registers the tables)
from app import recycle_bin  # noqa: F401  (its table too)

config = context.config
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run() -> None:
    engine = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        # render_as_batch: SQLite can only change a table by rebuilding it.
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()


run()
