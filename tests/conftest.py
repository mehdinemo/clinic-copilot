"""Pytest fixtures for unit and integration testing."""

from datetime import time
from typing import Generator

import pytest
from sqlalchemy.orm import Session

from app import clock
from app.db.database import (
    get_engine,
    get_session_factory,
    init_db,
    set_default_session_factory,
)
from app.db.seed import seed_database
from app.domain.models import Therapist


@pytest.fixture(autouse=True)
def reset_clinic_clock() -> Generator[None, None, None]:
    """Ensure clock starts and finishes each test at the fixed baseline."""
    clock.reset_now()
    yield
    clock.reset_now()


@pytest.fixture
def clean_session() -> Generator[Session, None, None]:
    """Provide a fresh in-memory database with default therapists but no appointments."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    set_default_session_factory(session_factory)

    with session_factory() as session:
        # Add baseline therapists (Dr. Rezaei & Dr. Moradi)
        th1 = Therapist(
            id="th_rezaei",
            name="Dr. Rezaei",
            specialty="Clinical Psychology",
            work_start_time=time(9, 0),
            work_end_time=time(17, 0),
            work_days="0,1,2,3,4",
        )
        th2 = Therapist(
            id="th_moradi",
            name="Dr. Moradi",
            specialty="Psychiatry",
            work_start_time=time(9, 0),
            work_end_time=time(17, 0),
            work_days="0,1,2,3,4",
        )
        session.add_all([th1, th2])
        session.commit()

        yield session


@pytest.fixture
def seeded_session() -> Generator[Session, None, None]:
    """Provide an in-memory database seeded with the deterministic seed dataset."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    set_default_session_factory(session_factory)

    with session_factory() as session:
        seed_database(session)
        yield session
