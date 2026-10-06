"""Clinic time and clock management module.

Provides a single injectable now() source of truth and clinic timezone conversions.
All database storage uses naive local datetimes in CLINIC_TZ.
All external tool boundaries consume and return ISO 8601 strings with timezone offset.
"""

from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

# Single source of truth for clinic timezone
CLINIC_TZ = ZoneInfo("Asia/Tehran")

# Deterministic default baseline (Monday, October 12, 2026, 09:00:00 AM)
DEFAULT_BASELINE = datetime(2026, 10, 12, 9, 0, 0, tzinfo=CLINIC_TZ)

_injected_now: Optional[datetime] = None


def now() -> datetime:
    """Return the current clinic datetime (timezone-aware).

    Returns the injected datetime if one was set (for tests/evals),
    otherwise returns DEFAULT_BASELINE.
    """
    if _injected_now is not None:
        return _injected_now
    return DEFAULT_BASELINE


def set_now(dt: Optional[datetime]) -> None:
    """Override the current clinic time for tests, evals, or simulations."""
    global _injected_now
    if dt is None:
        _injected_now = None
        return

    if dt.tzinfo is None:
        _injected_now = dt.replace(tzinfo=CLINIC_TZ)
    else:
        _injected_now = dt.astimezone(CLINIC_TZ)


def reset_now() -> None:
    """Reset the clock back to the default baseline."""
    global _injected_now
    _injected_now = None


def to_clinic_naive(dt: datetime) -> datetime:
    """Convert an aware or naive datetime to a naive datetime in CLINIC_TZ for SQLite storage."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(CLINIC_TZ).replace(tzinfo=None)


def to_clinic_iso(dt: datetime) -> str:
    """Convert a datetime to an ISO 8601 string with CLINIC_TZ offset for tool return values."""
    if dt.tzinfo is None:
        aware_dt = dt.replace(tzinfo=CLINIC_TZ)
    else:
        aware_dt = dt.astimezone(CLINIC_TZ)
    return aware_dt.isoformat()


def parse_iso_to_clinic_naive(iso_str: str, is_end_of_day: bool = False) -> datetime:
    """Parse an ISO 8601 string into a naive datetime in CLINIC_TZ.

    If a date-only string (YYYY-MM-DD) is provided and is_end_of_day is True,
    it returns the end of that day (23:59:59).

    Raises ValueError if the string cannot be parsed as an ISO 8601 datetime.
    """
    cleaned = iso_str.strip()
    try:
        # Check if only date is passed (e.g. "2026-10-13")
        if len(cleaned) == 10 and "-" in cleaned and "T" not in cleaned and " " not in cleaned:
            d = datetime.fromisoformat(cleaned).date()
            t = time(23, 59, 59) if is_end_of_day else time.min
            dt = datetime.combine(d, t, tzinfo=CLINIC_TZ)
            return dt.replace(tzinfo=None)

        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(CLINIC_TZ).replace(tzinfo=None)
    except Exception as exc:
        raise ValueError(
            f"Invalid ISO 8601 datetime format '{iso_str}'. "
            "Expected format like 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'."
        ) from exc
