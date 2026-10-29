"""The copy kept before a SQLite migration is whole (saved rows still in the
WAL included), is made fresh for every attempt, and is what a failed
migration puts back."""

import sqlite3
from contextlib import closing

import pytest
from alembic import command
from alembic.script import ScriptDirectory

from app import migrate
from app.db import make_engine
from app.migrate import VERSION_TABLE, _config, upgrade


def one_before_head(engine) -> tuple[str, str]:
    script = ScriptDirectory.from_config(_config(engine))
    head = script.get_current_head()
    return script.get_revision(head).down_revision, head


def at_previous_revision(tmp_path):
    """A database one migration behind, with a writer that saved a row the
    file itself doesn't hold yet: it is still in the WAL."""
    file = tmp_path / "finance.db"
    engine = make_engine(f"sqlite:///{file.as_posix()}")
    previous, head = one_before_head(engine)
    command.upgrade(_config(engine), previous)
    engine.dispose()
    writer = sqlite3.connect(file)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("CREATE TABLE probe (note TEXT)")
    writer.execute("INSERT INTO probe VALUES ('saved before the upgrade')")
    writer.commit()
    return file, engine, writer, previous, head


def rows(file, sql):
    with closing(sqlite3.connect(file)) as db:
        return db.execute(sql).fetchall()


def backups(file):
    return sorted(file.parent.glob(f"{file.name}.before-*"))


def test_the_copy_holds_rows_still_in_the_wal(tmp_path):
    file, engine, writer, previous, head = at_previous_revision(tmp_path)
    with closing(writer):
        # The row really is only in the WAL: a plain copy of the file misses it.
        plain = tmp_path / "plain-copy.db"
        plain.write_bytes(file.read_bytes())
        assert rows(plain, "SELECT name FROM sqlite_master WHERE name = 'probe'") == []

        upgrade(engine)

        [copy] = backups(file)
        assert rows(copy, "SELECT note FROM probe") == [("saved before the upgrade",)]
        assert rows(copy, f"SELECT version_num FROM {VERSION_TABLE}") == [(previous,)]
        assert rows(file, f"SELECT version_num FROM {VERSION_TABLE}") == [(head,)]
    engine.dispose()


def test_a_failed_migration_puts_back_everything_including_wal_rows(tmp_path, monkeypatch):
    file, engine, writer, previous, _ = at_previous_revision(tmp_path)

    def half_done(config, revision):
        # Leaves a schema change behind, as a migration failing midway would.
        with closing(sqlite3.connect(file)) as db:
            db.execute("CREATE TABLE half_done (x INTEGER)")
            db.commit()
        raise RuntimeError("migration failed midway")

    monkeypatch.setattr(migrate.command, "upgrade", half_done)
    with closing(writer), pytest.raises(RuntimeError, match="midway"):
        upgrade(engine)
    engine.dispose()

    assert rows(file, "SELECT note FROM probe") == [("saved before the upgrade",)]
    assert rows(file, "SELECT name FROM sqlite_master WHERE name = 'half_done'") == []
    assert rows(file, f"SELECT version_num FROM {VERSION_TABLE}") == [(previous,)]
    assert rows(file, "PRAGMA integrity_check") == [("ok",)]


def test_every_attempt_makes_its_own_copy_and_never_puts_back_an_older_one(tmp_path, monkeypatch):
    file, engine, writer, _, _ = at_previous_revision(tmp_path)
    writer.close()
    monkeypatch.setattr(migrate.command, "upgrade", lambda config, revision: (_ for _ in ()).throw(RuntimeError("fails")))

    with pytest.raises(RuntimeError):
        upgrade(engine)
    # Saved between the two attempts: the second failure must not undo it.
    with closing(sqlite3.connect(file)) as db:
        db.execute("INSERT INTO probe VALUES ('saved between attempts')")
        db.commit()
    with pytest.raises(RuntimeError):
        upgrade(engine)
    engine.dispose()

    first, second = backups(file)
    assert rows(first, "SELECT count(*) FROM probe") == [(1,)]
    assert rows(second, "SELECT count(*) FROM probe") == [(2,)]
    assert rows(file, "SELECT count(*) FROM probe") == [(2,)]


def test_a_copy_that_fails_its_check_stops_the_migration(tmp_path, monkeypatch):
    file, engine, writer, previous, _ = at_previous_revision(tmp_path)
    writer.close()
    ran = []
    monkeypatch.setattr(migrate.command, "upgrade", lambda config, revision: ran.append(revision))
    # A copy that lost a table: the check must refuse it rather than migrate without a whole copy.
    real_copy = migrate._copy

    def lossy(source, target):
        real_copy(source, target)
        with closing(sqlite3.connect(target)) as db:
            db.execute("DROP TABLE probe")
            db.commit()

    monkeypatch.setattr(migrate, "_copy", lossy)
    with pytest.raises(migrate.BackupNotUsable, match="missing tables"):
        upgrade(engine)
    engine.dispose()
    assert ran == []
    assert rows(file, f"SELECT version_num FROM {VERSION_TABLE}") == [(previous,)]
