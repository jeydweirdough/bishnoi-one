"""The migrations build the same schema as the models, so moving to Supabase
Postgres is `alembic upgrade head` against the new DATABASE_URL."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.config import API_DIR
from app.db import make_engine
from app.models import Base


def test_migrations_match_the_models(tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    config = Config(str(API_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")

    with make_engine(url).connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_an_existing_database_gets_inventory_grants(tmp_path):
    """Seeding only adds roles to an empty database, so 0002 grants the new
    Inventory module to the starting roles an existing one already has."""
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    config = Config(str(API_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    command.upgrade(config, "0001")
    with make_engine(url).begin() as connection:
        connection.execute(
            text(
                "INSERT INTO roles (key, name, description, sort_order) VALUES "
                "('department_staff', 'Department Staff', '', 0), ('executive', 'Executive', '', 1), ('rep', 'Rep', '', 2)"
            )
        )
    command.upgrade(config, "head")
    with make_engine(url).connect() as connection:
        rows = set(connection.execute(text("SELECT role_key, action FROM role_permissions WHERE module_key = 'inventory'")).all())
        reports = set(connection.execute(text("SELECT role_key, module_key FROM role_permissions WHERE action = 'report'")).all())
    assert rows == {("department_staff", "view"), ("department_staff", "create"), ("department_staff", "edit"), ("executive", "view")}
    # 0003: Reports in every sales module for the roles that had them seeded; not reps.
    # 0006 adds Management, which has them too. 0023 makes BID the seventh sales
    # division and copies B2C's grants onto it, so its figures are seen the same way.
    assert reports == {
        (role, m) for role in ("executive", "management") for m in ("b2c", "stc", "uro", "bnb", "b2b", "hos", "bid")
    }
