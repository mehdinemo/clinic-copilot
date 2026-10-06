"""Domain entities and SQLAlchemy models."""

from datetime import datetime, time, timedelta
from typing import List

from sqlalchemy import DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Therapist(Base):
    """Represents a clinic therapist/practitioner."""

    __tablename__ = "therapists"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    specialty: Mapped[str] = mapped_column(String, nullable=False)
    work_start_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(9, 0))
    work_end_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(17, 0))
    # Comma-separated weekday integers (0=Monday, 6=Sunday). Default: Mon-Fri ("0,1,2,3,4")
    work_days: Mapped[str] = mapped_column(String, nullable=False, default="0,1,2,3,4")

    appointments: Mapped[List["Appointment"]] = relationship(
        back_populates="therapist", cascade="all, delete-orphan"
    )

    def is_working_on(self, dt: datetime) -> bool:
        """Check if therapist works on the given datetime's weekday."""
        days = [int(d.strip()) for d in self.work_days.split(",") if d.strip()]
        return dt.weekday() in days


class Appointment(Base):
    """Represents a scheduled, completed, or cancelled appointment."""

    __tablename__ = "appointments"

    appointment_id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_id: Mapped[str] = mapped_column(String, nullable=False)
    patient_name: Mapped[str] = mapped_column(String, nullable=False)
    therapist_id: Mapped[str] = mapped_column(ForeignKey("therapists.id"), nullable=False)
    # Stored as naive local datetime in CLINIC_TZ
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="scheduled")

    therapist: Mapped["Therapist"] = relationship(back_populates="appointments")

    @property
    def end_time(self) -> datetime:
        """Calculate the end time based on start_time and duration."""
        return self.start_time + timedelta(minutes=self.duration_minutes)
