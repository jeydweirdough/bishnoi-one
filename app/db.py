from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Every query in the app is built with SQLAlchemy expressions, so values always
# travel as bound parameters and never as SQL text (tests/test_security.py
# keeps it that way). The settings below are about traffic, not injection.


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(
            url,
            pool_pre_ping=True,
            # Enough connections for a busy morning; a request waits up to 10s
            # for one instead of failing the moment all are in use.
            pool_size=10,
            max_overflow=20,
            pool_timeout=10,
            pool_recycle=1800,
            # No statement may run for more than 15 seconds.
            connect_args={"options": "-c statement_timeout=15000"} if parsed.get_backend_name() == "postgresql" else {},
        )

    file_backed = bool(parsed.database and parsed.database != ":memory:")
    if file_backed:
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 10})
    else:
        # In-memory: one shared connection, or each session sees an empty database.
        engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")  # SQLite ignores foreign keys unless asked
        if file_backed:
            # Readers don't wait for a writer, and a writer waits (up to 10s) for
            # another instead of failing with "database is locked".
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def make_sessions(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)
