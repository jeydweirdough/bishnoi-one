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
    # "Sales Rep" then; "Salesperson" since the three roles (0008).
    assert people == {"boss@example.com": "Administrator", "rep@example.com": "Salesperson"}
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


def test_three_roles_managers_become_team_leads(tmp_path):
    """0008: Manager goes (its people become Team Leads), Sales Rep is Salesperson,
    and Team Lead approves quotes."""
    from alembic import command

    from app.migrate import _config

    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    cfg = _config(engine)
    command.upgrade(cfg, "0007")
    with engine.begin() as db:
        manager = db.execute(text("SELECT id FROM roles WHERE name = 'Manager'")).scalar()
        db.execute(
            text("INSERT INTO users (id, email, full_name, password_hash, role_id, is_active, created_at, password_changed_at) VALUES ('u1', 'lorna@x.com', 'Lorna', 'x', :r, 1, '2026-01-01', '2026-01-01')"),
            {"r": manager},
        )
    command.upgrade(cfg, "0008")
    with engine.begin() as db:
        names = set(db.execute(text("SELECT name FROM roles")).scalars())
        lorna = db.execute(text("SELECT r.name FROM users u JOIN roles r ON r.id = u.role_id WHERE u.email = 'lorna@x.com'")).scalar()
        approve = db.execute(text("SELECT count(*) FROM role_permissions p JOIN roles r ON r.id = p.role_id WHERE r.name = 'Team Lead' AND p.permission = 'quotes.approve'")).scalar()
    assert names == {"Administrator", "Team Lead", "Salesperson"}
    assert (lorna, approve) == ("Team Lead", 1)


def test_table_names_are_put_right_whatever_the_recorded_revision_says(tmp_path):
    """A database at 0013 on paper, whose tables are under all three names
    (a deploy that stopped partway): 0014 brings each one to nbcm_."""
    from sqlalchemy import inspect

    from app.migrate import VERSION_TABLE, upgrade
    from app.db import make_engine

    engine = make_engine(f"sqlite:///{(tmp_path / 'mixed.db').as_posix()}")
    upgrade(engine)  # all the way: every table nbcm_
    with engine.begin() as db:
        db.execute(text("ALTER TABLE nbcm_teams RENAME TO teams"))  # never renamed
        db.execute(text("ALTER TABLE nbcm_users RENAME TO orcm_users"))  # renamed once
        # nbcm_quotes: already where it belongs
        db.execute(text(f"UPDATE {VERSION_TABLE} SET version_num = '0013'"))
    upgrade(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"nbcm_teams", "nbcm_users", "nbcm_quotes"} <= tables
    assert not {"teams", "orcm_users", "orcm_teams"} & tables
    with engine.connect() as db:
        assert db.execute(text(f"SELECT version_num FROM {VERSION_TABLE}")).scalar() == "0014"
