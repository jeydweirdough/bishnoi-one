"""A database from before migrations (plain users and sessions, made by
create_all) keeps its accounts, under the nbrg_ names."""

from sqlalchemy import create_engine, inspect, text

from app.config import Settings
from app.main import create_app

OLD_USERS = (
    "CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) UNIQUE, full_name VARCHAR(120), password_hash VARCHAR(255), "
    "role VARCHAR(16), is_active BOOLEAN, created_at DATETIME, password_changed_at DATETIME)"
)
OLD_SESSIONS = (
    "CREATE TABLE sessions (id VARCHAR(36) PRIMARY KEY, token_hash VARCHAR(64) UNIQUE, "
    "user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE, created_at DATETIME, expires_at DATETIME, revoked_at DATETIME)"
)


def test_an_old_database_keeps_its_accounts(tmp_path):
    url = f"sqlite:///{(tmp_path / 'old.db').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text(OLD_USERS))
        c.execute(text(OLD_SESSIONS))
        c.execute(text("INSERT INTO users VALUES ('u1', 'old@example.com', 'Old Admin', 'x', 'admin', 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"))
    engine.dispose()
    app = create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=url))
    engine = app.state.sessions.kw["bind"]
    with engine.connect() as c:
        assert c.execute(text("SELECT email FROM nbrg_users")).scalars().all() == ["old@example.com"]
    assert set(inspect(engine).get_table_names()) == {"nbrg_users", "nbrg_sessions", "nbrg_alembic_version"}
    engine.dispose()
