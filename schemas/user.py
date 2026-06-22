from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional, List, Literal
from datetime import datetime

VALID_ROLES = {"admin", "teacher", "student", "parent"}
VALID_SECTIONS = {"A", "B", "C"}


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    batch_id: Optional[str] = None
    batch_ids: Optional[List[str]] = None
    section: Optional[str] = None
    linked_student_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 120:
            raise ValueError("Name too long (max 120 chars)")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v

    @field_validator("section")
    @classmethod
    def section_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_SECTIONS:
            raise ValueError("Section must be A, B, or C")
        return v

    @model_validator(mode="after")
    def check_role_fields(self) -> "UserCreate":
        if self.role == "student" and not self.batch_id:
            pass  # batch optional at creation — admin may assign later
        if self.role == "parent" and not self.linked_student_id:
            pass  # may link later
        return self


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    batch_id: Optional[str] = None
    batch_ids: Optional[List[str]] = None
    section: Optional[str] = None
    linked_student_id: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v

    @field_validator("section")
    @classmethod
    def section_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_SECTIONS:
            raise ValueError("Section must be A, B, or C")
        return v


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    batch_id: Optional[str] = None
    section: Optional[str] = None
    linked_student_id: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PasswordReset(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v
