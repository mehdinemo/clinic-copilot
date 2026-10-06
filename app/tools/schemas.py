"""Pydantic input argument schemas for LangGraph tools."""

from typing import Optional

from pydantic import BaseModel, Field


class SearchAppointmentsInput(BaseModel):
    """Input parameters for searching clinic appointments."""

    patient_name: Optional[str] = Field(
        default=None,
        description="Patient's full name or surname (e.g. 'Sara Ahmadi').",
    )
    therapist_name: Optional[str] = Field(
        default=None,
        description="Therapist's full name or surname (e.g. 'Dr. Rezaei').",
    )
    start_date: str = Field(
        description="Start date/time in ISO 8601 format (e.g. '2026-10-13').",
    )
    end_date: str = Field(
        description="End date/time in ISO 8601 format (e.g. '2026-10-14').",
    )
    status: str = Field(
        default="scheduled",
        description="Status filter: 'scheduled', 'cancelled', 'completed', or 'all'.",
    )


class FindAvailableSlotsInput(BaseModel):
    """Input parameters for finding available appointment slots."""

    therapist_name: str = Field(
        description="Full name or surname of the therapist (e.g. 'Dr. Rezaei').",
    )
    start_date: str = Field(
        description="Start date/time in ISO 8601 format (e.g. '2026-10-13').",
    )
    end_date: str = Field(
        description="End date/time in ISO 8601 format (e.g. '2026-10-14').",
    )
    duration_minutes: int = Field(
        default=45,
        description="Required appointment duration in minutes (45 or 60).",
    )
    earliest_time: Optional[str] = Field(
        default=None,
        description="Optional earliest acceptable time in 24-hour 'HH:MM' (e.g. '16:00').",
    )
    latest_time: Optional[str] = Field(
        default=None,
        description="Optional latest start time in 24-hour 'HH:MM' (e.g. '16:30').",
    )


class RescheduleAppointmentInput(BaseModel):
    """Input parameters for rescheduling an existing appointment."""

    appointment_id: str = Field(
        description="Unique identifier of the appointment to reschedule (e.g. 'apt_rezaei_01').",
    )
    new_start: str = Field(
        description="New appointment start time in ISO 8601 format (e.g. '2026-10-13T14:00:00').",
    )
