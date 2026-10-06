"""Unit tests for domain services (services.py)."""

from datetime import datetime, time, timedelta

import pytest
from sqlalchemy.orm import Session

from app import clock
from app.domain import services
from app.domain.errors import (
    AppointmentNotFound,
    InvalidAppointmentState,
    OutsideWorkingHours,
    PastTime,
    SlotConflict,
)
from app.domain.models import Appointment


def test_reschedule_adjacent_right_passes(clean_session: Session) -> None:
    """Boundary test: Existing 09:00-10:00 vs target 10:00-11:00 passes with no conflict."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    # Existing appointment: 09:00 - 10:00
    clean_session.add(
        Appointment(
            appointment_id="apt_existing",
            patient_id="pat_1",
            patient_name="Existing Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(9, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    # Target appointment to reschedule: currently at 14:00 - 15:00
    appt_target = Appointment(
        appointment_id="apt_target",
        patient_id="pat_2",
        patient_name="Target Patient",
        therapist_id="th_rezaei",
        start_time=datetime.combine(target_date, time(14, 0)),
        duration_minutes=60,
        status="scheduled",
    )
    clean_session.add(appt_target)
    clean_session.commit()

    # Move target appointment to 10:00 - 11:00 (immediately adjacent)
    new_start = datetime.combine(target_date, time(10, 0))
    updated, old_start = services.reschedule(clean_session, "apt_target", new_start)

    assert updated.start_time == new_start
    assert old_start == datetime.combine(target_date, time(14, 0))


def test_reschedule_adjacent_left_passes(clean_session: Session) -> None:
    """Boundary test: Existing 10:00-11:00 vs target 09:00-10:00 passes with no conflict."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_existing",
            patient_id="pat_1",
            patient_name="Existing Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(10, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.add(
        Appointment(
            appointment_id="apt_target",
            patient_id="pat_2",
            patient_name="Target Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(14, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.commit()

    new_start = datetime.combine(target_date, time(9, 0))
    updated, _ = services.reschedule(clean_session, "apt_target", new_start)
    assert updated.start_time == new_start


def test_reschedule_overlap_end_conflicts(clean_session: Session) -> None:
    """Boundary test: Existing 09:00-10:00 vs target 09:59-10:44 conflicts."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_existing",
            patient_id="pat_1",
            patient_name="Existing Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(9, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.add(
        Appointment(
            appointment_id="apt_target",
            patient_id="pat_2",
            patient_name="Target Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(14, 0)),
            duration_minutes=45,
            status="scheduled",
        )
    )
    clean_session.commit()

    # Starts at 09:59, which overlaps with existing ending at 10:00
    new_start = datetime.combine(target_date, time(9, 59))
    with pytest.raises(SlotConflict):
        services.reschedule(clean_session, "apt_target", new_start)


def test_reschedule_overlap_start_conflicts(clean_session: Session) -> None:
    """Boundary test: Existing 10:00-11:00 vs target 09:30-10:15 conflicts."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_existing",
            patient_id="pat_1",
            patient_name="Existing Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(10, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.add(
        Appointment(
            appointment_id="apt_target",
            patient_id="pat_2",
            patient_name="Target Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(14, 0)),
            duration_minutes=45,
            status="scheduled",
        )
    )
    clean_session.commit()

    # Ends at 10:15, overlapping existing starting at 10:00
    new_start = datetime.combine(target_date, time(9, 30))
    with pytest.raises(SlotConflict):
        services.reschedule(clean_session, "apt_target", new_start)


def test_reschedule_self_exclusion_passes(clean_session: Session) -> None:
    """Target appointment moving within its own existing time window does not self-conflict."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_self",
            patient_id="pat_1",
            patient_name="Self Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(9, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.commit()

    # Reschedule apt_self to 09:15 on the same day (overlaps previous 09:00-10:00 slot)
    new_start = datetime.combine(target_date, time(9, 15))
    updated, old_start = services.reschedule(clean_session, "apt_self", new_start)

    assert updated.start_time == new_start
    assert old_start == datetime.combine(target_date, time(9, 0))


def test_reschedule_cancelled_appointment_ignored(clean_session: Session) -> None:
    """Cancelled appointment occupying a time slot does not block rescheduling into that slot."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_cancelled",
            patient_id="pat_1",
            patient_name="Cancelled Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(10, 0)),
            duration_minutes=60,
            status="cancelled",
        )
    )
    clean_session.add(
        Appointment(
            appointment_id="apt_active",
            patient_id="pat_2",
            patient_name="Active Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(14, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.commit()

    # Move active appointment right into 10:00 - 11:00
    new_start = datetime.combine(target_date, time(10, 0))
    updated, _ = services.reschedule(clean_session, "apt_active", new_start)
    assert updated.start_time == new_start


def test_reschedule_different_therapists_no_conflict(clean_session: Session) -> None:
    """Appointments with different therapists at the exact same time do not conflict."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    # Dr. Moradi has an appointment at 10:00 - 11:00
    clean_session.add(
        Appointment(
            appointment_id="apt_moradi",
            patient_id="pat_1",
            patient_name="Patient One",
            therapist_id="th_moradi",
            start_time=datetime.combine(target_date, time(10, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    # Dr. Rezaei's appointment currently at 14:00 - 15:00
    clean_session.add(
        Appointment(
            appointment_id="apt_rezaei",
            patient_id="pat_2",
            patient_name="Patient Two",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(14, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.commit()

    # Move Dr. Rezaei's appointment to 10:00 - 11:00
    new_start = datetime.combine(target_date, time(10, 0))
    updated, _ = services.reschedule(clean_session, "apt_rezaei", new_start)
    assert updated.start_time == new_start


def test_reschedule_out_of_hours_early(clean_session: Session) -> None:
    """Cannot reschedule before therapist's work start time."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_target",
            patient_id="pat_1",
            patient_name="Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(10, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.commit()

    # 08:30 is before 09:00 work start
    with pytest.raises(OutsideWorkingHours):
        services.reschedule(clean_session, "apt_target", datetime.combine(target_date, time(8, 30)))


def test_reschedule_out_of_hours_late(clean_session: Session) -> None:
    """Cannot reschedule where appointment end exceeds therapist's work end time."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_target",
            patient_id="pat_1",
            patient_name="Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(10, 0)),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.commit()

    # 16:30 + 60 min = 17:30 (work end is 17:00)
    with pytest.raises(OutsideWorkingHours):
        services.reschedule(
            clean_session, "apt_target", datetime.combine(target_date, time(16, 30))
        )


def test_reschedule_past_time_fails(clean_session: Session) -> None:
    """Cannot reschedule to a past timestamp relative to clock.now()."""
    target_date = clock.to_clinic_naive(clock.now()).date() - timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_target",
            patient_id="pat_1",
            patient_name="Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(
                clock.to_clinic_naive(clock.now()).date() + timedelta(days=1), time(10, 0)
            ),
            duration_minutes=60,
            status="scheduled",
        )
    )
    clean_session.commit()

    with pytest.raises(PastTime):
        services.reschedule(clean_session, "apt_target", datetime.combine(target_date, time(10, 0)))


def test_reschedule_appointment_not_found(clean_session: Session) -> None:
    """Rescheduling a nonexistent appointment raises AppointmentNotFound."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)
    with pytest.raises(AppointmentNotFound):
        services.reschedule(
            clean_session, "nonexistent_id", datetime.combine(target_date, time(10, 0))
        )


def test_reschedule_invalid_appointment_state(clean_session: Session) -> None:
    """Cannot reschedule cancelled or completed appointments."""
    target_date = clock.to_clinic_naive(clock.now()).date() + timedelta(days=1)

    clean_session.add(
        Appointment(
            appointment_id="apt_cancelled",
            patient_id="pat_1",
            patient_name="Cancelled Patient",
            therapist_id="th_rezaei",
            start_time=datetime.combine(target_date, time(10, 0)),
            duration_minutes=60,
            status="cancelled",
        )
    )
    clean_session.commit()

    with pytest.raises(InvalidAppointmentState):
        services.reschedule(
            clean_session, "apt_cancelled", datetime.combine(target_date, time(14, 0))
        )
