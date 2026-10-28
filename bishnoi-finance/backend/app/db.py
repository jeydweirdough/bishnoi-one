"""This app's database. Its tables come from migrations (app/migrate.py)."""

import os
import re
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str, postgres_driver: str = "psycopg") -> Engine:
    if url.startswith("sqlite"):
        # The folder the database file lives in, made on first start.
        path = url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return engine
    if postgres_driver == "pg8000" or url.startswith("postgresql+pg8000:"):
        from app.postgres_driver import python_engine
        return python_engine(url)
    if postgres_driver != "psycopg":
        raise ValueError("Choose psycopg or pg8000 for the Finance PostgreSQL driver.")
    # Postgres (on Vercel: Neon). Its providers hand out postgres:// or
    # postgresql:// addresses; the driver installed here is psycopg 3.
    url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)
    # No prepared statements: a pooler in transaction mode (Supabase's, on
    # port 6543) hands each transaction to any of its connections, where a
    # statement prepared on another one doesn't exist.
    # A database out of reach fails in 10 seconds, rather than hanging the request.
    connect_args = {"prepare_threshold": None, "connect_timeout": 10}
    if os.environ.get("VERCEL"):
        # A serverless function is frozen between requests, so a pooled
        # connection may be dead by the next one. Connect per request; the
        # database's pooler does the pooling on its side.
        return create_engine(url, poolclass=NullPool, connect_args=connect_args)
    # With every pooled connection busy, a request waits at most 10 seconds for one,
    # then answers 503 (app/guard.py), rather than piling up behind the others.
    engine = create_engine(url, connect_args=connect_args, pool_timeout=10)
    _ping_when_idle(engine)
    return engine


# A pooled connection is tested only when it has sat unused a while: the
# database (Neon) may have dropped it while asleep. Testing it on every request
# cost a round trip each time (about 0.1 s from this computer).
IDLE_BEFORE_PING = 60  # seconds


def _ping_when_idle(engine: Engine) -> None:
    import time

    from sqlalchemy import exc

    @event.listens_for(engine, "checkin")
    def _back(dbapi_connection, record) -> None:
        record.info["back_at"] = time.monotonic()

    @event.listens_for(engine, "checkout")
    def _out(dbapi_connection, record, proxy) -> None:
        back = record.info.get("back_at")
        if back is None or time.monotonic() - back < IDLE_BEFORE_PING:
            return
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except Exception as e:
            # The pool drops this connection and hands out a fresh one.
            raise exc.DisconnectionError() from e


def make_sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def open_session(sessions: sessionmaker[Session]) -> Iterator[Session]:
    with sessions() as db:
        yield db
