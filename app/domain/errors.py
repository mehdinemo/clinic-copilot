"""Domain-level custom exceptions."""


class DomainError(Exception):
    """Base domain exception."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TherapistNotFound(DomainError):
    """Raised when a therapist is not found."""

    pass


class AppointmentNotFound(DomainError):
    """Raised when an appointment is not found."""

    pass


class InvalidAppointmentState(DomainError):
    """Raised when an appointment is in an unexpected state (e.g. cancelled/completed)."""

    pass


class PastTime(DomainError):
    """Raised when an appointment time is in the past."""

    pass


class OutsideWorkingHours(DomainError):
    """Raised when a slot or appointment falls outside therapist working hours."""

    pass


class SlotConflict(DomainError):
    """Raised when a slot conflicts with an existing scheduled appointment."""

    pass


class InvalidInputError(DomainError):
    """Raised when domain parameters fail validation."""

    pass
