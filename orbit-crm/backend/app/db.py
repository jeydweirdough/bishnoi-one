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


def make_engine(url: str) -> Engine:
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
    # Postgres (on Vercel: Neon). Its providers hand out postgres:// or
    # postgresql:// addresses; the driver installed here is psycopg 3.
    url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)
    if os.environ.get("VERCEL"):
        # A serverless function is frozen between requests, so a pooled
        # connection may be dead by the next one. Connect per request; Neon's
        # pooled address does the pooling on its side.
        return create_engine(url, poolclass=NullPool)
    return create_engine(url, pool_pre_ping=True)


def make_sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def open_session(sessions: sessionmaker[Session]) -> Iterator[Session]:
    with sessions() as db:
        yield db
