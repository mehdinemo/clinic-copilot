"""Slot availability tool implementation."""

from datetime import time
from typing import Any, Dict, Optional

from langchain_core.tools import tool

from app import clock
from app.db.database import get_default_session_factory
from app.domain import services
from app.tools.errors import map_exception_to_error
from app.tools.schemas import FindAvailableSlotsInput
from app.tools.timeout import run_with_timeout


def _parse_time(time_str: Optional[str]) -> Optional[time]:
    """Parse 'HH:MM' 24-hour time string into a time object."""
    if not time_str:
        return None
    cleaned = time_str.strip()
    try:
        parts = cleaned.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(hour, minute)
    except Exception as exc:
        raise ValueError(
            f"Invalid time format '{time_str}'. Expected 'HH:MM' in 24-hour format (e.g. '16:00')."
        ) from exc


def _find_available_slots_impl(
    therapist_name: str,
    start_date: str,
    end_date: str,
    duration_minutes: int = 45,
    earliest_time: Optional[str] = None,
    latest_time: Optional[str] = None,
) -> Dict[str, Any]:
    start_dt = clock.parse_iso_to_clinic_naive(start_date)
    end_dt = clock.parse_iso_to_clinic_naive(end_date, is_end_of_day=True)
    earliest_t = _parse_time(earliest_time)
    latest_t = _parse_time(latest_time)

    session_factory = get_default_session_factory()
    with session_factory() as session:
        therapist = services.get_therapist_by_name(session, therapist_name)
        slots = services.get_available_slots(
            session=session,
            therapist_id=therapist.id,
            start=start_dt,
            end=end_dt,
            duration_minutes=duration_minutes,
            earliest_time=earliest_t,
            latest_time=latest_t,
        )

        max_slots = 15
        truncated = len(slots) > max_slots
        slots_slice = slots[:max_slots]

        return {
            "status": "ok",
            "count": len(slots_slice),
            "truncated": truncated,
            "slots": [
                {
                    "start": clock.to_clinic_iso(s[0]),
                    "end": clock.to_clinic_iso(s[1]),
                }
                for s in slots_slice
            ],
        }


@tool(args_schema=FindAvailableSlotsInput)
def find_available_slots(
    therapist_name: str,
    start_date: str,
    end_date: str,
    duration_minutes: int = 45,
    earliest_time: Optional[str] = None,
    latest_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Find free appointment slots for a therapist within a date range and time-of-day filters.

    Prerequisite: Use this to discover valid opening times before proposing or scheduling.
    Dates must be ISO 8601 strings. Times must be 'HH:MM' in 24-hour format (e.g. '16:00').
    """
    try:
        return run_with_timeout(
            _find_available_slots_impl,
            timeout_seconds=10.0,
            therapist_name=therapist_name,
            start_date=start_date,
            end_date=end_date,
            duration_minutes=duration_minutes,
            earliest_time=earliest_time,
            latest_time=latest_time,
        )
    except Exception as exc:
        return map_exception_to_error(exc)
