from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime


class AttendanceRecordIn(BaseModel):
    student_id: str
    status: str  # present / absent / late


class AttendanceSubmit(BaseModel):
    batch_id: str
    section: str
    date: date
    records: List[AttendanceRecordIn]


class AttendanceSessionOut(BaseModel):
    id: str
    batch_id: str
    section: str
    date: date
    is_locked: bool
    created_at: datetime
    student_count: Optional[int] = 0
    present_count: Optional[int] = 0
    absent_count: Optional[int] = 0
    late_count: Optional[int] = 0

    model_config = {"from_attributes": True}
