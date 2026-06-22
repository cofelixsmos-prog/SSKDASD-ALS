import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(SAEnum("admin", "teacher", "student", "parent", name="user_role"))
    batch_id: Mapped[str | None] = mapped_column(String, ForeignKey("batches.id"), nullable=True)
    section: Mapped[str | None] = mapped_column(SAEnum("A", "B", "C", name="section_enum"), nullable=True)
    linked_student_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped["Batch"] = relationship(
        "Batch",
        primaryjoin="User.batch_id == Batch.id",
        back_populates="students",
        foreign_keys="[User.batch_id]",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
