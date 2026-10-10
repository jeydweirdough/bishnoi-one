"""A database from Orbit Pharmacy (plain users and sessions, no migrations)
becomes Bishnoi One Pharmacy's: every table nbph_, its people kept, a copy of the
file left beside it."""

from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from app.config import Settings
from app.main import create_app
from app.models import User


def test_an_orbit_pharmacy_database_is_carried_over(tmp_path):
    file = tmp_path / "pharmacy.db"
    old = create_engine(f"sqlite:///{file.as_posix()}")
    now = datetime.now(UTC).isoformat()
    with old.begin() as c:
        # The tables exactly as Orbit Pharmacy made them (create_all).
        c.execute(text("""CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE,
            full_name VARCHAR(120) NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(16) NOT NULL,
            is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, password_changed_at DATETIME NOT NULL,
            CONSTRAINT user_role CHECK (role IN ('admin', 'member')))"""))
        c.execute(text("""CREATE TABLE sessions (id VARCHAR(36) PRIMARY KEY, token_hash VARCHAR(64) NOT NULL UNIQUE,
            user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL, revoked_at DATETIME)"""))
        for i, (email, role) in enumerate((("boss@example.com", "admin"), ("ruth@example.com", "member"))):
            c.execute(text("INSERT INTO users VALUES (:id, :email, :name, 'x', :role, 1, :now, :now)"),
                      {"id": f"00000000-0000-0000-0000-00000000000{i}", "email": email, "name": email, "role": role, "now": now})
    old.dispose()

    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{file.as_posix()}")
    app = create_app(settings)
    with app.state.sessions() as db:
        people = {u.email: u.role.name for u in db.query(User)}
    assert people == {"boss@example.com": "Administrator", "ruth@example.com": "Pharmacy Assistant"}
    check = create_engine(f"sqlite:///{file.as_posix()}")
    with check.connect() as c:
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    check.dispose()
    assert tables and all(t.startswith("nbph_") for t in tables), tables
    backups = sorted(p.name for p in tmp_path.iterdir() if ".before-" in p.name)
    assert backups == ["pharmacy.db.before-0004"]  # the latest update's number

    # Starting again changes nothing and copies nothing more.
    create_app(settings)
    assert sorted(p.name for p in tmp_path.iterdir() if ".before-" in p.name) == backups
