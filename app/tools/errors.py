import logging
from typing import Any, Dict

from app.domain.errors import (
    AppointmentNotFound,
    DomainError,
    InvalidAppointmentState,
    InvalidInputError,
    OutsideWorkingHours,
    PastTime,
    SlotConflict,
    TherapistNotFound,
)

logger = logging.getLogger(__name__)


def format_tool_error(
    code: str, message: str, retryable: bool = False, next_step: str = ""
) -> Dict[str, Any]:
    """Build a structured tool error response dictionary."""
    return {
        "status": "error",
        "code": code,
        "message": message,
        "retryable": retryable,
        "next_step": next_step,
    }


def map_exception_to_error(exc: Exception) -> Dict[str, Any]:
    """Map domain and system exceptions to standardized structured error dictionaries."""
    if isinstance(exc, TherapistNotFound):
        return format_tool_error(
            code="THERAPIST_NOT_FOUND",
            message=exc.message,
            retryable=False,
            next_step="Check the therapist's name and re-try with a known therapist.",
        )
    elif isinstance(exc, AppointmentNotFound):
        return format_tool_error(
            code="APPOINTMENT_NOT_FOUND",
            message=exc.message,
            retryable=False,
            next_step="Use search_appointments to verify the appointment ID first.",
        )
    elif isinstance(exc, InvalidAppointmentState):
        return format_tool_error(
            code="INVALID_STATE",
            message=exc.message,
            retryable=False,
            next_step="Verify current appointment status with search_appointments.",
        )
    elif isinstance(exc, PastTime):
        return format_tool_error(
            code="PAST_TIME",
            message=exc.message,
            retryable=False,
            next_step="Select a slot strictly in the future relative to today's date.",
        )
    elif isinstance(exc, OutsideWorkingHours):
        return format_tool_error(
            code="OUTSIDE_WORKING_HOURS",
            message=exc.message,
            retryable=False,
            next_step="Select a time within the therapist's active working hours.",
        )
    elif isinstance(exc, SlotConflict):
        return format_tool_error(
            code="SLOT_UNAVAILABLE",
            message=exc.message,
            retryable=True,
            next_step="Call find_available_slots again to choose an unoccupied slot.",
        )
    elif isinstance(exc, (InvalidInputError, ValueError)):
        return format_tool_error(
            code="INVALID_INPUT",
            message=str(exc),
            retryable=False,
            next_step="Ensure dates and times use valid ISO 8601 format and valid values.",
        )
    elif isinstance(exc, TimeoutError):
        return format_tool_error(
            code="TOOL_TIMEOUT",
            message="The operation timed out while executing.",
            retryable=True,
            next_step="Try running the request again.",
        )
    elif isinstance(exc, DomainError):
        return format_tool_error(
            code="INVALID_INPUT",
            message=exc.message,
            retryable=False,
            next_step="Review the parameters and try again.",
        )
    else:
        # Sanitized error - never leak raw SQL or stack traces to LLM
        logger.exception("Unexpected tool failure", exc_info=exc)
        return format_tool_error(
            code="INTERNAL_ERROR",
            message="An unexpected internal error occurred while processing the request.",
            retryable=True,
            next_step="Try again or inform the clinic administrator.",
        )
