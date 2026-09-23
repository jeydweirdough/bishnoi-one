"""A database made before migrations existed is brought up to date, with its
people kept and a copy of the file left beside it."""

from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from app.config import Settings
from app.main import create_app
from app.models import User


def test_a_database_from_before_administration_is_upgraded(tmp_path):
    file = tmp_path / "sales.db"
    old = create_engine(f"sqlite:///{file.as_posix()}")
    now = datetime.now(UTC).isoformat()
    with old.begin() as c:
        # The tables exactly as the first version made them (create_all, no migrations).
        c.execute(text("""CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE,
            full_name VARCHAR(120) NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(16) NOT NULL,
            is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, password_changed_at DATETIME NOT NULL,
            CONSTRAINT user_role CHECK (role IN ('admin', 'member')))"""))
        c.execute(text("""CREATE TABLE sessions (id VARCHAR(36) PRIMARY KEY, token_hash VARCHAR(64) NOT NULL UNIQUE,
            user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL, revoked_at DATETIME)"""))
        for i, (email, role) in enumerate((("boss@example.com", "admin"), ("rep@example.com", "member"))):
            c.execute(text("INSERT INTO users VALUES (:id, :email, :name, 'x', :role, 1, :now, :now)"),
                      {"id": f"00000000-0000-0000-0000-00000000000{i}", "email": email, "name": email, "role": role, "now": now})
    old.dispose()

    app = create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{file.as_posix()}"))
    with app.state.sessions() as db:
        people = {u.email: u.role.name for u in db.query(User)}
    assert people == {"boss@example.com": "Administrator", "rep@example.com": "Sales Rep"}
    backups = sorted(p.name for p in tmp_path.iterdir() if ".before-" in p.name)
    assert len(backups) == 1  # named after the newest migration

    # Starting again changes nothing and copies nothing more.
    create_app(Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{file.as_posix()}"))
    assert sorted(p.name for p in tmp_path.iterdir() if ".before-" in p.name) == backups


def test_a_failed_migration_leaves_the_database_as_it_was(tmp_path, monkeypatch):
    file = tmp_path / "sales.db"
    old = create_engine(f"sqlite:///{file.as_posix()}")
    with old.begin() as c:
        c.execute(text("""CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE,
            full_name VARCHAR(120) NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(16) NOT NULL,
            is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, password_changed_at DATETIME NOT NULL)"""))
        c.execute(text("""CREATE TABLE sessions (id VARCHAR(36) PRIMARY KEY, token_hash VARCHAR(64) NOT NULL UNIQUE,
            user_id VARCHAR(36) NOT NULL, created_at DATETIME NOT NULL, expires_at DATETIME NOT NULL, revoked_at DATETIME)"""))
    old.dispose()

    from alembic.operations import Operations

    real = Operations.batch_alter_table

    def explode(self, *args, **kwargs):  # fails halfway, after 0002 has made its new tables
        raise RuntimeError("boom")

    monkeypatch.setattr(Operations, "batch_alter_table", explode)
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{file.as_posix()}")
    try:
        create_app(settings)
        raise AssertionError("the migration should have failed")
    except RuntimeError:
        pass
    check = create_engine(f"sqlite:///{file.as_posix()}")
    with check.connect() as c:
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    check.dispose()
    assert "roles" not in tables and "teams" not in tables  # nothing half-made is left

    monkeypatch.setattr(Operations, "batch_alter_table", real)
    create_app(settings)  # and the next start finishes the job
