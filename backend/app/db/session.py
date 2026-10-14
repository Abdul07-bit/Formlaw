"""Single database engine + session factory for the whole backend."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import get_settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def init_engine(url: str | None = None) -> Engine:
    global _engine, _factory
    url = url or get_settings().database_url
    is_sqlite = url.startswith("sqlite")
    _engine = create_engine(url, pool_pre_ping=True, future=True, connect_args={"check_same_thread": False} if is_sqlite else {})
    if is_sqlite:
        @event.listens_for(_engine, "connect")
        def _sqlite_pragmas(conn, _):  # enforce FKs; WAL for concurrent readers
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    _factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def engine() -> Engine:
    return _engine or init_engine()


def session_factory() -> sessionmaker[Session]:
    if _factory is None:
        init_engine()
    assert _factory is not None
    return _factory


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
