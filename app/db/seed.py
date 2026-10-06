"""Deterministic seed data for the Clinic Operations Assistant.

All dates are generated relative to the clock.now() reference datetime, ensuring
scenarios like "tomorrow" or "next Tuesday" are permanently reproducible in tests and CLI runs.
"""

from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app import clock
from app.domain.models import Appointment, Therapist


def seed_database(session: Session) -> None:
    """Populate the database with deterministic therapists and appointments."""
    # Clear any existing rows
    session.query(Appointment).delete()
    session.query(Therapist).delete()
    session.flush()

    # 1. Therapists
    dr_rezaei = Therapist(
        id="th_rezaei",
        name="Dr. Rezaei",
        specialty="Clinical Psychology",
        work_start_time=time(9, 0),
        work_end_time=time(17, 0),
        work_days="0,1,2,3,4",  # Monday to Friday
    )
    dr_moradi = Therapist(
        id="th_moradi",
        name="Dr. Moradi",
        specialty="Psychiatry",
        work_start_time=time(9, 0),
        work_end_time=time(17, 0),
        work_days="0,1,2,3,4",  # Monday to Friday
    )
    session.add_all([dr_rezaei, dr_moradi])
    session.flush()

    # 2. Date references relative to clock.now()
    base_now = clock.now()
    base_date = clock.to_clinic_naive(base_now).date()
    yesterday = base_date - timedelta(days=1)
    tomorrow = base_date + timedelta(days=1)
    day_after = base_date + timedelta(days=2)

    appointments = [
        # Past appointment (completed yesterday)
        Appointment(
            appointment_id="apt_past_01",
            patient_id="pat_sara_101",
            patient_name="Sara Ahmadi",
            therapist_id=dr_rezaei.id,
            start_time=datetime.combine(yesterday, time(10, 0)),
            duration_minutes=45,
            status="completed",
        ),
        # Dr. Rezaei tomorrow: 45 min and 60 min mix, plus cancelled slot
        Appointment(
            appointment_id="apt_rezaei_01",
            patient_id="pat_sara_101",
            patient_name="Sara Ahmadi",
            therapist_id=dr_rezaei.id,
            start_time=datetime.combine(tomorrow, time(9, 0)),
            duration_minutes=45,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_rezaei_02",
            patient_id="pat_ali_102",  # Shared surname "Ahmadi" for ambiguity checks
            patient_name="Ali Ahmadi",
            therapist_id=dr_rezaei.id,
            start_time=datetime.combine(tomorrow, time(10, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_rezaei_03",
            patient_id="pat_neda_103",
            patient_name="Neda Karimi",
            therapist_id=dr_rezaei.id,
            start_time=datetime.combine(tomorrow, time(11, 0)),
            duration_minutes=45,
            status="scheduled",
        ),
        # Cancelled appointment occupying 14:00-15:00 (must NOT block available slots!)
        Appointment(
            appointment_id="apt_rezaei_cancelled",
            patient_id="pat_babak_104",
            patient_name="Babak Rahimi",
            therapist_id=dr_rezaei.id,
            start_time=datetime.combine(tomorrow, time(14, 0)),
            duration_minutes=60,
            status="cancelled",
        ),
        # Dr. Rezaei late afternoon appointment
        Appointment(
            appointment_id="apt_rezaei_04",
            patient_id="pat_babak_104",
            patient_name="Babak Rahimi",
            therapist_id=dr_rezaei.id,
            start_time=datetime.combine(tomorrow, time(16, 15)),
            duration_minutes=45,
            status="scheduled",
        ),
        # Dr. Moradi tomorrow: FULLY BOOKED for the entire day (09:00 - 17:00 back-to-back)
        Appointment(
            appointment_id="apt_moradi_01",
            patient_id="pat_neda_103",
            patient_name="Neda Karimi",
            therapist_id=dr_moradi.id,
            start_time=datetime.combine(tomorrow, time(9, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_moradi_02",
            patient_id="pat_babak_104",
            patient_name="Babak Rahimi",
            therapist_id=dr_moradi.id,
            start_time=datetime.combine(tomorrow, time(10, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_moradi_03",
            patient_id="pat_ali_102",
            patient_name="Ali Ahmadi",
            therapist_id=dr_moradi.id,
            start_time=datetime.combine(tomorrow, time(11, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_moradi_04",
            patient_id="pat_sara_101",
            patient_name="Sara Ahmadi",
            therapist_id=dr_moradi.id,
            start_time=datetime.combine(tomorrow, time(12, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_moradi_05",
            patient_id="pat_neda_103",
            patient_name="Neda Karimi",
            therapist_id=dr_moradi.id,
            start_time=datetime.combine(tomorrow, time(13, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_moradi_06",
            patient_id="pat_babak_104",
            patient_name="Babak Rahimi",
            therapist_id=dr_moradi.id,
            start_time=datetime.combine(tomorrow, time(14, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_moradi_07",
            patient_id="pat_ali_102",
            patient_name="Ali Ahmadi",
            therapist_id=dr_moradi.id,
            start_time=datetime.combine(tomorrow, time(15, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        Appointment(
            appointment_id="apt_moradi_08",
            patient_id="pat_sara_101",
            patient_name="Sara Ahmadi",
            therapist_id=dr_moradi.id,
            start_time=datetime.combine(tomorrow, time(16, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
        # Appointment on day after tomorrow
        Appointment(
            appointment_id="apt_rezaei_05",
            patient_id="pat_sara_101",
            patient_name="Sara Ahmadi",
            therapist_id=dr_rezaei.id,
            start_time=datetime.combine(day_after, time(10, 0)),
            duration_minutes=60,
            status="scheduled",
        ),
    ]

    session.add_all(appointments)
    session.commit()
