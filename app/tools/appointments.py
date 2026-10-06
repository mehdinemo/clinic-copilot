"""Appointment search and reschedule tool implementations."""

from typing import Any, Dict, Optional

from langchain_core.tools import tool

from app import clock
from app.db.database import get_default_session_factory
from app.domain import services
from app.tools.errors import format_tool_error, map_exception_to_error
from app.tools.schemas import RescheduleAppointmentInput, SearchAppointmentsInput
from app.tools.timeout import run_with_timeout


def _search_appointments_impl(
    patient_name: Optional[str] = None,
    therapist_name: Optional[str] = None,
    start_date: str = "",
    end_date: str = "",
    status: str = "scheduled",
) -> Dict[str, Any]:
    start_dt = clock.parse_iso_to_clinic_naive(start_date)
    end_dt = clock.parse_iso_to_clinic_naive(end_date, is_end_of_day=True)

    session_factory = get_default_session_factory()
    with session_factory() as session:
        therapist_id = None
        if therapist_name:
            therapist = services.get_therapist_by_name(session, therapist_name)
            therapist_id = therapist.id

        query_status = None if status.lower() == "all" else status
        appts = services.search_appointments(
            session=session,
            patient_name=patient_name,
            therapist_id=therapist_id,
            start=start_dt,
            end=end_dt,
            status=query_status,
        )

        max_results = 20
        truncated = len(appts) > max_results
        appts_slice = appts[:max_results]

        results = [
            {
                "appointment_id": a.appointment_id,
                "patient_name": a.patient_name,
                "therapist_name": a.therapist.name if a.therapist else "",
                "start": clock.to_clinic_iso(a.start_time),
                "end": clock.to_clinic_iso(a.end_time),
                "duration_minutes": a.duration_minutes,
                "status": a.status,
            }
            for a in appts_slice
        ]

        return {
            "status": "ok",
            "count": len(results),
            "truncated": truncated,
            "appointments": results,
        }


@tool(args_schema=SearchAppointmentsInput)
def search_appointments(
    patient_name: Optional[str] = None,
    therapist_name: Optional[str] = None,
    start_date: str = "",
    end_date: str = "",
    status: str = "scheduled",
) -> Dict[str, Any]:
    """Search appointments matching patient name, therapist name, date range, or status.

    Prerequisite: Use this to discover appointment IDs, check bookings, and verify patient details.
    Never invent or guess appointment IDs. Dates must be ISO 8601 strings.
    """
    try:
        return run_with_timeout(
            _search_appointments_impl,
            timeout_seconds=10.0,
            patient_name=patient_name,
            therapist_name=therapist_name,
            start_date=start_date,
            end_date=end_date,
            status=status,
        )
    except Exception as exc:
        return map_exception_to_error(exc)


def _reschedule_appointment_impl(
    appointment_id: str,
    new_start: str,
) -> Dict[str, Any]:
    new_start_dt = clock.parse_iso_to_clinic_naive(new_start)

    session_factory = get_default_session_factory()
    with session_factory() as session:
        appt, old_start = services.reschedule(
            session=session,
            appointment_id=appointment_id,
            new_start=new_start_dt,
        )

        therapist_name = appt.therapist.name if appt.therapist else ""

        return {
            "status": "ok",
            "appointment_id": appt.appointment_id,
            "patient_name": appt.patient_name,
            "therapist_name": therapist_name,
            "old_start": clock.to_clinic_iso(old_start),
            "new_start": clock.to_clinic_iso(appt.start_time),
            "duration_minutes": appt.duration_minutes,
        }


@tool(args_schema=RescheduleAppointmentInput)
def reschedule_appointment(
    appointment_id: str,
    new_start: str,
) -> Dict[str, Any]:
    """Reschedule an existing scheduled appointment to a new date and time.

    Prerequisite: Must obtain appointment_id from search_appointments first.
    Must check find_available_slots to confirm opening before rescheduling.
    new_start must be an ISO 8601 string (e.g. '2026-10-13T14:00:00').
    """
    try:
        return run_with_timeout(
            _reschedule_appointment_impl,
            timeout_seconds=10.0,
            appointment_id=appointment_id,
            new_start=new_start,
        )
    except TimeoutError:
        return format_tool_error(
            code="TOOL_TIMEOUT",
            message=(
                "The reschedule operation timed out while executing. The change may have been "
                "applied; verify appointment status with search_appointments before attempting "
                "again."
            ),
            retryable=False,
            next_step=(
                "Check the appointment status with search_appointments before attempting to "
                "reschedule again."
            ),
        )

    except Exception as exc:
        return map_exception_to_error(exc)
