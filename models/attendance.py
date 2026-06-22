import uuid
from datetime import datetime, date
from sqlalchemy import String, Boolean, DateTime, Date, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id: Mapped[str] = mapped_column(String, ForeignKey("batches.id"))
    section: Mapped[str] = mapped_column(SAEnum("A", "B", "C", name="session_section_enum"))
    date: Mapped[date] = mapped_column(Date)
    recorded_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    is_locked: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped["Batch"] = relationship("Batch", back_populates="attendance_sessions")
    teacher: Mapped["User"] = relationship("User", foreign_keys=[recorded_by])
    records: Mapped[list["AttendanceRecord"]] = relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("attendance_sessions.id"))
    student_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(SAEnum("present", "absent", "late", name="attendance_status"))

    session: Mapped["AttendanceSession"] = relationship("AttendanceSession", back_populates="records")
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
