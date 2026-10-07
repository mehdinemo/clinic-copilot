"""Domain service functions for appointment queries, slot availability, and rescheduling."""

import threading
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.domain.errors import (
    AppointmentNotFound,
    InvalidAppointmentState,
    InvalidInputError,
    OutsideWorkingHours,
    PastTime,
    SlotConflict,
    TherapistNotFound,
)
from app.domain.models import Appointment, Therapist

# Process-level lock guaranteeing serialized check-then-write transactions in SQLite
_RESCHEDULE_LOCK = threading.Lock()


def get_therapist_by_name(session: Session, name: str) -> Therapist:
    """Find a therapist by exact or case-insensitive name."""
    cleaned = name.strip()
    # Try exact match first
    stmt = select(Therapist).where(Therapist.name.ilike(cleaned))
    therapist = session.execute(stmt).scalars().first()
    if therapist:
        return therapist

    # Try partial / substring match
    stmt = select(Therapist).where(Therapist.name.ilike(f"%{cleaned}%"))
    therapist = session.execute(stmt).scalars().first()
    if therapist:
        return therapist

    raise TherapistNotFound(f"Therapist '{name}' not found.")


def search_appointments(
    session: Session,
    patient_name: Optional[str] = None,
    therapist_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    status: Optional[str] = "scheduled",
) -> List[Appointment]:
    """Search appointments matching the given criteria."""
    stmt = select(Appointment)

    if patient_name:
        stmt = stmt.where(Appointment.patient_name.ilike(f"%{patient_name.strip()}%"))

    if therapist_id:
        stmt = stmt.where(Appointment.therapist_id == therapist_id.strip())

    if start:
        stmt = stmt.where(Appointment.start_time >= start)

    if end:
        stmt = stmt.where(Appointment.start_time < end)

    if status:
        stmt = stmt.where(Appointment.status == status.strip().lower())

    stmt = stmt.order_by(Appointment.start_time.asc())
    return list(session.execute(stmt).scalars().all())


def get_available_slots(
    session: Session,
    therapist_id: str,
    start: datetime,
    end: datetime,
    duration_minutes: int,
    earliest_time: Optional[time] = None,
    latest_time: Optional[time] = None,
    slot_granularity_minutes: int = 15,
) -> List[Tuple[datetime, datetime]]:
    """Calculate available appointment slots for a therapist within a date range.

    Respects working hours, working days, existing scheduled appointments,
    time constraints (earliest/latest), and current time (cannot book in the past).
    """
    therapist = session.get(Therapist, therapist_id)
    if not therapist:
        raise TherapistNotFound(f"Therapist with ID '{therapist_id}' not found.")

    if duration_minutes <= 0:
        raise InvalidInputError("duration_minutes must be greater than zero.")

    if end <= start:
        raise InvalidInputError("end_date must be strictly after start_date.")

    current_now_naive = clock.to_clinic_naive(clock.now())

    # Fetch existing scheduled appointments that could overlap with the search window
    query_start = start - timedelta(minutes=duration_minutes)
    stmt = (
        select(Appointment)
        .where(
            Appointment.therapist_id == therapist_id,
            Appointment.status == "scheduled",
            Appointment.start_time < end,
            Appointment.start_time >= query_start,
        )
        .order_by(Appointment.start_time.asc())
    )
    existing_appointments = list(session.execute(stmt).scalars().all())

    available_slots: List[Tuple[datetime, datetime]] = []

    # Iterate through days in [start.date(), end.date()]
    current_day: date = start.date()
    end_day: date = end.date()

    while current_day <= end_day:
        day_sample = datetime.combine(current_day, time(12, 0))
        if therapist.is_working_on(day_sample):
            work_start_dt = datetime.combine(current_day, therapist.work_start_time)
            work_end_dt = datetime.combine(current_day, therapist.work_end_time)

            candidate_start = work_start_dt
            step = timedelta(minutes=slot_granularity_minutes)

            while candidate_start + timedelta(minutes=duration_minutes) <= work_end_dt:
                candidate_end = candidate_start + timedelta(minutes=duration_minutes)

                # Must be inside requested window [start, end)
                if candidate_start >= start and candidate_end <= end:
                    # Must not be in the past
                    if candidate_start >= current_now_naive:
                        # Time-of-day filters
                        t = candidate_start.time()
                        earliest_ok = earliest_time is None or t >= earliest_time
                        latest_ok = latest_time is None or t <= latest_time

                        if earliest_ok and latest_ok:
                            # Conflict check: overlap exists if cand_start < appt_end
                            # and cand_end > appt_start
                            conflict = False
                            for appt in existing_appointments:
                                is_overlap = (
                                    candidate_start < appt.end_time
                                    and candidate_end > appt.start_time
                                )
                                if is_overlap:
                                    conflict = True
                                    break

                            if not conflict:
                                available_slots.append((candidate_start, candidate_end))

                candidate_start += step

        current_day += timedelta(days=1)

    return available_slots


def reschedule(
    session: Session,
    appointment_id: str,
    new_start: datetime,
) -> Tuple[Appointment, datetime]:
    """Reschedule an appointment to a new start time under a process-level lock.

    Validates:
      - Appointment exists and is currently in 'scheduled' status.
      - new_start is in the future relative to clock.now().
      - new_start falls strictly within therapist's working hours and working days.
      - Slot conflict: new_start < existing_end AND new_end > existing_start
        (for same therapist, status 'scheduled', excluding the appointment itself).

    Returns:
      Tuple of (updated Appointment, old_start datetime).
    """
    with _RESCHEDULE_LOCK:
        appt = session.get(Appointment, appointment_id)
        if not appt:
            raise AppointmentNotFound(f"Appointment '{appointment_id}' not found.")

        if appt.status.lower() != "scheduled":
            raise InvalidAppointmentState(
                f"Appointment '{appointment_id}' has status '{appt.status}' "
                "and cannot be rescheduled."
            )

        new_start_naive = clock.to_clinic_naive(new_start)
        current_now_naive = clock.to_clinic_naive(clock.now())

        if new_start_naive < current_now_naive:
            raise PastTime(f"Requested start time {new_start_naive} cannot be in the past.")

        therapist: Optional[Therapist] = appt.therapist
        if not therapist:
            therapist = session.get(Therapist, appt.therapist_id)
            if not therapist:
                raise TherapistNotFound(f"Therapist '{appt.therapist_id}' not found.")

        # Check working day
        if not therapist.is_working_on(new_start_naive):
            raise OutsideWorkingHours(
                f"Therapist '{therapist.name}' does not work on {new_start_naive.strftime('%A')}."
            )

        # Check working hours
        new_end_naive = new_start_naive + timedelta(minutes=appt.duration_minutes)
        work_start_dt = datetime.combine(new_start_naive.date(), therapist.work_start_time)
        work_end_dt = datetime.combine(new_start_naive.date(), therapist.work_end_time)

        if new_start_naive < work_start_dt or new_end_naive > work_end_dt:
            raise OutsideWorkingHours(
                f"Requested slot {new_start_naive.time()}-{new_end_naive.time()} falls outside "
                f"working hours ({therapist.work_start_time}-{therapist.work_end_time})."
            )

        # Conflict check: fetch scheduled appointments for same therapist on the same day,
        # excluding the target appointment itself
        day_start = datetime.combine(new_start_naive.date(), time.min)
        day_end = datetime.combine(new_start_naive.date(), time.max)
        stmt = select(Appointment).where(
            Appointment.therapist_id == appt.therapist_id,
            Appointment.status == "scheduled",
            Appointment.appointment_id != appt.appointment_id,
            Appointment.start_time >= day_start,
            Appointment.start_time <= day_end,
        )
        candidates = list(session.execute(stmt).scalars().all())

        for other in candidates:
            # Overlap exists if: new_start < other.end_time AND new_end > other.start_time
            if new_start_naive < other.end_time and new_end_naive > other.start_time:
                raise SlotConflict(
                    f"The requested time slot {new_start_naive.time()}-{new_end_naive.time()} "
                    f"conflicts with an existing appointment ({other.appointment_id})."
                )

        old_start = appt.start_time
        appt.start_time = new_start_naive
        session.commit()
        session.refresh(appt)

        return appt, old_start
