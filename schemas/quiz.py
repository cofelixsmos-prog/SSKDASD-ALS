from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Literal
from datetime import datetime


class QuestionIn(BaseModel):
    type: Literal["mcq", "short_answer"]
    text: str
    options: Optional[List[str]] = None
    correct_answers: List[str]
    points: int = 1
    order: int = 0
    case_sensitive: bool = False

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question text cannot be empty")
        if len(v) > 2000:
            raise ValueError("Question text too long (max 2000 chars)")
        return v

    @field_validator("points")
    @classmethod
    def points_positive(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("Points must be between 1 and 100")
        return v

    @model_validator(mode="after")
    def check_mcq_options(self) -> "QuestionIn":
        if self.type == "mcq":
            if not self.options or len(self.options) < 2:
                raise ValueError("MCQ questions need at least 2 options")
            if not self.correct_answers:
                raise ValueError("MCQ questions need at least one correct answer")
        if self.type == "short_answer" and not self.correct_answers:
            raise ValueError("Short answer questions need at least one accepted answer")
        return self


class QuizCreate(BaseModel):
    title: str
    subject: str
    batch_id: Optional[str] = None
    timer_minutes: int = 30
    shuffle_questions: bool = False
    shuffle_options: bool = False
    show_answers_on_close: bool = True
    questions: List[QuestionIn] = []

    @field_validator("title", "subject")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty")
        return v

    @field_validator("timer_minutes")
    @classmethod
    def timer_valid(cls, v: int) -> int:
        if v < 1 or v > 180:
            raise ValueError("Timer must be 1–180 minutes")
        return v


class QuizUpdate(BaseModel):
    title: Optional[str] = None
    subject: Optional[str] = None
    batch_id: Optional[str] = None
    timer_minutes: Optional[int] = None
    shuffle_questions: Optional[bool] = None
    shuffle_options: Optional[bool] = None
    show_answers_on_close: Optional[bool] = None
    questions: Optional[List[QuestionIn]] = None

    @field_validator("timer_minutes")
    @classmethod
    def timer_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 180):
            raise ValueError("Timer must be 1–180 minutes")
        return v


class QuizOut(BaseModel):
    id: str
    title: str
    subject: str
    batch_id: Optional[str] = None
    status: str
    code: str
    timer_minutes: int
    shuffle_questions: bool
    shuffle_options: bool
    show_answers_on_close: bool
    created_at: datetime
    question_count: Optional[int] = 0

    model_config = {"from_attributes": True}
