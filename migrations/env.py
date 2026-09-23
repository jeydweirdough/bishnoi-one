from logging.config import fileConfig

from alembic import context

from app.config import DatabaseSettings
from app.db import make_engine
from app.models import Base

config = context.config
if config.config_file_name and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Tests pass their own URL; otherwise MIGRATION_DATABASE_URL (the tables' owner)
# or, when that isn't set, DATABASE_URL from api/.env.
_settings = DatabaseSettings()
url = config.attributes.get("database_url") or _settings.migration_database_url or _settings.database_url


def run() -> None:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            render_as_batch=True,  # SQLite can't ALTER most things; batch mode rebuilds the table
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run()
