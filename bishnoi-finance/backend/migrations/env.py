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
    supplied = config.attributes.get("connection")
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=Base.metadata, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()
        return
    # The app's own engine when the app runs the migrations (app/migrate.py);
    # one made from the address when alembic is run by hand.
    from app.db import make_engine
    engine = config.attributes.get("engine") or make_engine(config.get_main_option("sqlalchemy.url"),
        postgres_driver=get_settings().postgres_driver)
    with engine.connect() as connection:
        # render_as_batch: SQLite can only change a table by rebuilding it.
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()


run()
