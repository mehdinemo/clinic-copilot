from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.tools.appointments import reschedule_appointment, search_appointments
from app.tools.availability import find_available_slots


def test_reschedule_appointment_success(seeded_session: Session) -> None:
    """Rescheduling a valid appointment to an open slot returns status='ok' with details."""
    result = reschedule_appointment.invoke(
        {
            "appointment_id": "apt_rezaei_01",
            "new_start": "2026-10-13T14:00:00+03:30",
        }
    )

    assert result["status"] == "ok"
    assert result["appointment_id"] == "apt_rezaei_01"
    assert result["patient_name"] == "Sara Ahmadi"
    assert result["therapist_name"] == "Dr. Rezaei"
    assert "2026-10-13T14:00:00" in result["new_start"]
    assert result["duration_minutes"] == 45


def test_reschedule_appointment_invalid_iso_format(seeded_session: Session) -> None:
    """Passing a non-ISO date string returns structured INVALID_INPUT error."""
    result = reschedule_appointment.invoke(
        {
            "appointment_id": "apt_rezaei_01",
            "new_start": "tomorrow-at-2pm",
        }
    )

    assert result["status"] == "error"
    assert result["code"] == "INVALID_INPUT"
    assert "retryable" in result
    assert "next_step" in result


def test_reschedule_appointment_not_found(seeded_session: Session) -> None:
    """Nonexistent appointment ID returns structured APPOINTMENT_NOT_FOUND error."""
    result = reschedule_appointment.invoke(
        {
            "appointment_id": "apt_nonexistent",
            "new_start": "2026-10-13T14:00:00+03:30",
        }
    )

    assert result["status"] == "error"
    assert result["code"] == "APPOINTMENT_NOT_FOUND"
    assert result["retryable"] is False


def test_reschedule_appointment_slot_conflict(seeded_session: Session) -> None:
    """Rescheduling into an already-booked slot returns SLOT_UNAVAILABLE with retryable=True."""
    # apt_rezaei_02 is already booked from 10:00 to 11:00 on 2026-10-13
    result = reschedule_appointment.invoke(
        {
            "appointment_id": "apt_rezaei_01",
            "new_start": "2026-10-13T10:00:00+03:30",
        }
    )

    assert result["status"] == "error"
    assert result["code"] == "SLOT_UNAVAILABLE"
    assert result["retryable"] is True
    assert "find_available_slots" in result["next_step"]


def test_reschedule_appointment_past_time(seeded_session: Session) -> None:
    """Rescheduling to a past timestamp returns structured PAST_TIME error."""
    result = reschedule_appointment.invoke(
        {
            "appointment_id": "apt_rezaei_01",
            "new_start": "2026-10-01T10:00:00+03:30",
        }
    )

    assert result["status"] == "error"
    assert result["code"] == "PAST_TIME"
    assert result["retryable"] is False


def test_reschedule_appointment_outside_working_hours(seeded_session: Session) -> None:
    """Rescheduling to a time outside clinic hours returns OUTSIDE_WORKING_HOURS error."""
    result = reschedule_appointment.invoke(
        {
            "appointment_id": "apt_rezaei_01",
            "new_start": "2026-10-13T20:00:00+03:30",
        }
    )

    assert result["status"] == "error"
    assert result["code"] == "OUTSIDE_WORKING_HOURS"
    assert result["retryable"] is False


def test_reschedule_appointment_invalid_state(seeded_session: Session) -> None:
    """Rescheduling a cancelled appointment returns structured INVALID_STATE error."""
    result = reschedule_appointment.invoke(
        {
            "appointment_id": "apt_rezaei_cancelled",
            "new_start": "2026-10-13T15:00:00+03:30",
        }
    )

    assert result["status"] == "error"
    assert result["code"] == "INVALID_STATE"
    assert result["retryable"] is False


def test_search_appointments_success(seeded_session: Session) -> None:
    """search_appointments returns list of appointments and metadata."""
    result = search_appointments.invoke(
        {
            "patient_name": "Sara Ahmadi",
            "start_date": "2026-10-12",
            "end_date": "2026-10-15",
        }
    )

    assert result["status"] == "ok"
    assert result["count"] >= 1
    assert "truncated" in result
    for appt in result["appointments"]:
        assert "Sara Ahmadi" in appt["patient_name"]
        assert "appointment_id" in appt


def test_search_appointments_invalid_date(seeded_session: Session) -> None:
    """Invalid date format in search_appointments returns structured INVALID_INPUT error."""
    result = search_appointments.invoke(
        {
            "start_date": "invalid-date",
            "end_date": "2026-10-15",
        }
    )

    assert result["status"] == "error"
    assert result["code"] == "INVALID_INPUT"


def test_find_available_slots_success(seeded_session: Session) -> None:
    """find_available_slots returns valid slot intervals."""
    result = find_available_slots.invoke(
        {
            "therapist_name": "Dr. Rezaei",
            "start_date": "2026-10-13T09:00:00",
            "end_date": "2026-10-13T17:00:00",
            "duration_minutes": 45,
            "earliest_time": "14:00",
        }
    )

    assert result["status"] == "ok"
    assert result["count"] > 0
    assert "slots" in result
    for slot in result["slots"]:
        assert "start" in slot
        assert "end" in slot


def test_find_available_slots_therapist_not_found(seeded_session: Session) -> None:
    """Querying an unknown therapist returns structured THERAPIST_NOT_FOUND error."""
    result = find_available_slots.invoke(
        {
            "therapist_name": "Dr. Unknown",
            "start_date": "2026-10-13T09:00:00",
            "end_date": "2026-10-13T17:00:00",
            "duration_minutes": 45,
        }
    )

    assert result["status"] == "error"
    assert result["code"] == "THERAPIST_NOT_FOUND"


def test_error_payload_contract_consistency(seeded_session: Session) -> None:
    """Verify that all error payloads satisfy the exact structure contract."""
    result = reschedule_appointment.invoke(
        {
            "appointment_id": "apt_rezaei_01",
            "new_start": "bad-date",
        }
    )

    expected_keys = {"status", "code", "message", "retryable", "next_step"}
    assert set(result.keys()) == expected_keys
    assert result["status"] == "error"
    assert isinstance(result["code"], str)
    assert isinstance(result["message"], str)
    assert isinstance(result["retryable"], bool)
    assert isinstance(result["next_step"], str)


def test_tool_timeout_mapping() -> None:
    """TimeoutError is mapped to structured TOOL_TIMEOUT payload."""
    from app.tools.errors import map_exception_to_error

    err_payload = map_exception_to_error(TimeoutError("Operation timed out."))
    assert err_payload["status"] == "error"
    assert err_payload["code"] == "TOOL_TIMEOUT"
    assert err_payload["retryable"] is True


def test_run_with_timeout_helper() -> None:
    """run_with_timeout raises TimeoutError when callable exceeds time limit."""
    import time

    import pytest

    from app.tools.timeout import run_with_timeout

    def slow_fn() -> None:
        time.sleep(0.1)

    with pytest.raises(TimeoutError):
        run_with_timeout(slow_fn, 0.01)


def test_reschedule_appointment_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """reschedule_appointment maps TimeoutError to structured non-retryable TOOL_TIMEOUT."""
    from app.tools import appointments

    def mock_run_with_timeout(*args: Any, **kwargs: Any) -> Any:
        raise TimeoutError("Simulated timeout")

    monkeypatch.setattr(appointments, "run_with_timeout", mock_run_with_timeout)

    result = appointments.reschedule_appointment.invoke(
        {
            "appointment_id": "apt_01",
            "new_start": "2026-10-13T10:00:00",
        }
    )
    assert result["status"] == "error"
    assert result["code"] == "TOOL_TIMEOUT"
    assert result["retryable"] is False
    assert "verify appointment status" in result["message"]
