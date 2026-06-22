import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Enum as SAEnum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    batch_id: Mapped[str | None] = mapped_column(String, ForeignKey("batches.id"), nullable=True)
    status: Mapped[str] = mapped_column(SAEnum("draft", "active", "closed", name="quiz_status"), default="draft")
    code: Mapped[str | None] = mapped_column(String(6), nullable=True, unique=True)
    timer_minutes: Mapped[int] = mapped_column(Integer, default=30)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=False)
    show_answers_on_close: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    teacher: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    batch: Mapped["Batch"] = relationship("Batch", back_populates="quizzes")
    questions: Mapped[list["Question"]] = relationship("Question", back_populates="quiz", cascade="all, delete-orphan", order_by="Question.order")
    submissions: Mapped[list["QuizSubmission"]] = relationship("QuizSubmission", back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    quiz_id: Mapped[str] = mapped_column(String, ForeignKey("quizzes.id"))
    type: Mapped[str] = mapped_column(SAEnum("mcq", "short_answer", name="question_type"))
    text: Mapped[str] = mapped_column(String(2000))
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_answers: Mapped[list] = mapped_column(JSON)
    points: Mapped[int] = mapped_column(Integer, default=1)
    order: Mapped[int] = mapped_column(Integer, default=0)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)

    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="questions")


class QuizSubmission(Base):
    __tablename__ = "quiz_submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    quiz_id: Mapped[str] = mapped_column(String, ForeignKey("quizzes.id"))
    student_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    answers: Mapped[list] = mapped_column(JSON, default=list)
    score: Mapped[int] = mapped_column(Integer, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    auto_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    cheat_flag_count: Mapped[int] = mapped_column(Integer, default=0)
    cheat_events: Mapped[list] = mapped_column(JSON, default=list)
    violation_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="submissions")
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
