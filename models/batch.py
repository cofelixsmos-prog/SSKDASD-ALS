import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

batch_teachers = Table(
    "batch_teachers",
    Base.metadata,
    Column("batch_id", String, ForeignKey("batches.id"), primary_key=True),
    Column("teacher_id", String, ForeignKey("users.id"), primary_key=True),
)


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    teachers: Mapped[list["User"]] = relationship("User", secondary=batch_teachers)
    students: Mapped[list["User"]] = relationship("User", primaryjoin="User.batch_id == Batch.id", back_populates="batch")
    quizzes: Mapped[list["Quiz"]] = relationship("Quiz", back_populates="batch")
    attendance_sessions: Mapped[list["AttendanceSession"]] = relationship("AttendanceSession", back_populates="batch")
