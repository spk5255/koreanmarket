"""Database engine & session management.

Single source for the SQLAlchemy engine/sessionmaker, built from
``settings.resolved_db_url``. Use :func:`session_scope` for a transactional
block and :func:`init_db` to create tables (Phase 0 bootstrap; swap to Alembic
migrations once the schema starts evolving in prod).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from src.logging_setup import get_logger
from src.storage.models import Base

log = get_logger(__name__)

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        settings.ensure_dirs()
        url = settings.resolved_db_url
        connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
        _engine = create_engine(url, echo=False, future=True, connect_args=connect_args)
        if settings.is_sqlite:
            _enable_sqlite_pragmas(_engine)
        log.debug("Created engine for %s", url)
    return _engine


def _enable_sqlite_pragmas(engine: Engine) -> None:
    """Turn on foreign-key enforcement (off by default in SQLite)."""
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionFactory


def get_session() -> Session:
    """Return a new Session. Caller is responsible for closing it."""
    return get_session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session block: commits on success, rolls back on error."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(*, drop: bool = False) -> None:
    """Create all tables (and optionally drop first). Idempotent.

    Args:
        drop: if True, drop all known tables before creating (destructive —
            dev convenience only).
    """
    engine = get_engine()
    if drop:
        log.warning("Dropping all tables before re-create (drop=True)")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    log.info("Initialized database at %s (%d tables)", settings.resolved_db_url, len(Base.metadata.tables))
