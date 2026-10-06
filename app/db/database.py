"""Database initialization and session management.

Supports in-memory SQLite with StaticPool and disabled same-thread checks
to support concurrent tool executions cleanly.
"""

from typing import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy domain models."""

    pass


def get_engine(db_url: str = "sqlite:///:memory:") -> Engine:
    """Create and return a configured SQLAlchemy Engine.

    For SQLite in-memory databases, uses StaticPool and check_same_thread=False
    so multiple threads can share the in-memory database without resets or locking crashes.
    """
    connect_args = {}
    engine_kwargs = {}

    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in db_url:
            engine_kwargs["poolclass"] = StaticPool

    return create_engine(db_url, connect_args=connect_args, **engine_kwargs)


def init_db(engine: Engine) -> None:
    """Create all tables defined on Base metadata."""
    Base.metadata.create_all(bind=engine)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_default_session_factory: sessionmaker[Session] | None = None


def set_default_session_factory(factory: sessionmaker[Session]) -> None:
    """Set the globally active session factory for tools and operations."""
    global _default_session_factory
    _default_session_factory = factory


def get_default_session_factory() -> sessionmaker[Session]:
    """Get the active session factory, creating a default in-memory one if needed."""
    global _default_session_factory
    if _default_session_factory is None:
        engine = get_engine("sqlite:///:memory:")
        init_db(engine)
        _default_session_factory = get_session_factory(engine)
    return _default_session_factory


def get_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Contextual session generator helper."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
