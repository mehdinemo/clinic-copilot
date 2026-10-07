"""Database initialization and session management.

Supports in-memory SQLite with StaticPool and disabled same-thread checks
to support concurrent tool executions cleanly.
"""

import os
from typing import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy domain models."""

    pass


def get_engine(db_url: str | None = None) -> Engine:
    """Create and return a configured SQLAlchemy Engine.

    For SQLite in-memory databases, uses StaticPool and check_same_thread=False
    so multiple threads can share the in-memory database without resets or locking crashes.
    """
    resolved_url = db_url or os.environ.get("DATABASE_URL") or "sqlite:///:memory:"
    connect_args = {}
    engine_kwargs = {}

    if resolved_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in resolved_url:
            engine_kwargs["poolclass"] = StaticPool

    return create_engine(resolved_url, connect_args=connect_args, **engine_kwargs)


def init_db(engine: Engine) -> None:
    """Create all tables defined on Base metadata."""
    Base.metadata.create_all(bind=engine)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_default_session_factory: sessionmaker[Session] | None = None


def set_default_session_factory(factory: sessionmaker[Session] | None) -> None:
    """Set the globally active session factory for tools and operations."""
    global _default_session_factory
    _default_session_factory = factory


def init_and_seed_db(db_url: str | None = None) -> sessionmaker[Session]:
    """Initialize database schema, seed deterministic data, and register default session factory."""
    engine = get_engine(db_url)
    init_db(engine)
    factory = get_session_factory(engine)
    set_default_session_factory(factory)

    from app.db.seed import seed_database

    with factory() as session:
        seed_database(session)

    return factory


def get_default_session_factory() -> sessionmaker[Session]:
    """Get the active session factory, creating and auto-seeding a default one if needed."""
    global _default_session_factory
    if _default_session_factory is None:
        init_and_seed_db()
    assert _default_session_factory is not None
    return _default_session_factory


def get_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Contextual session generator helper."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
