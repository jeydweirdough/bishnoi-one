"""The migrations make exactly the tables the models describe, and take over
a database from before migrations without losing anyone."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.db import Base, make_engine
from app.migrate import VERSION_TABLE, upgrade
from app import models  # noqa: F401  (registers the tables)


def test_migrations_match_the_models(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'm.db').as_posix()}")
    upgrade(engine)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection, opts={"version_table": VERSION_TABLE}), Base.metadata)
    # Column types SQLite can't tell apart aren't differences.
    assert [d for d in diff if d[0] not in ("modify_type",)] == []
    tables = set(inspect(engine).get_table_names())
    assert all(t.startswith("nbpl_") for t in tables), tables
    assert VERSION_TABLE in tables


def test_takes_over_a_database_from_before_migrations(tmp_path):
    file = tmp_path / "old.db"
    old = create_engine(f"sqlite:///{file.as_posix()}")
    with old.begin() as c:
        c.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) UNIQUE NOT NULL, full_name VARCHAR(120) NOT NULL,"
                       " password_hash VARCHAR(255) NOT NULL, role VARCHAR(16) NOT NULL, is_active BOOLEAN NOT NULL,"
                       " created_at DATETIME NOT NULL, password_changed_at DATETIME NOT NULL)"))
        c.execute(text("CREATE TABLE sessions (id VARCHAR(36) PRIMARY KEY, token_hash VARCHAR(64) UNIQUE NOT NULL,"
                       " user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at DATETIME NOT NULL,"
                       " expires_at DATETIME NOT NULL, revoked_at DATETIME)"))
        c.execute(text("INSERT INTO users VALUES ('u1', 'jun@x.test', 'Jun', 'h', 'admin', 1, '2026-01-01', '2026-01-01')"))
    old.dispose()
    engine = make_engine(f"sqlite:///{file.as_posix()}")
    upgrade(engine)
    tables = set(inspect(engine).get_table_names())
    assert "users" not in tables and "sessions" not in tables
    with engine.connect() as c:
        assert c.execute(text("SELECT email, last_sign_in_at FROM nbpl_users")).all() == [("jun@x.test", None)]
    assert (tmp_path / "old.db.before-0003").exists()
