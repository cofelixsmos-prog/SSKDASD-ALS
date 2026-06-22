from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from database import get_db
from dependencies import get_current_user, require_role
from models.user import User
from models.batch import Batch, batch_teachers
from models.attendance import AttendanceSession, AttendanceRecord
from schemas.attendance import AttendanceSubmit, AttendanceSessionOut
from typing import Optional
import uuid
from datetime import date, datetime

router = APIRouter(prefix="/api/attendance", tags=["attendance"])
TeacherOrAdmin = Depends(require_role("teacher", "admin"))


# Teacher's assigned batches
@router.get("/my-batches")
async def my_batches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "admin":
        result = await db.execute(select(Batch).order_by(Batch.name))
        batches = result.scalars().all()
    else:
        result = await db.execute(
            select(Batch).join(batch_teachers, Batch.id == batch_teachers.c.batch_id)
            .where(batch_teachers.c.teacher_id == current_user.id)
            .order_by(Batch.name)
        )
        batches = result.scalars().all()
    return [{"id": b.id, "name": b.name} for b in batches]


# Student roster for a batch+section
@router.get("/roster")
async def get_roster(
    batch_id: str,
    section: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify teacher teaches this batch
    if current_user.role == "teacher":
        check = await db.execute(
            select(batch_teachers).where(
                batch_teachers.c.batch_id == batch_id,
                batch_teachers.c.teacher_id == current_user.id,
            )
        )
        if not check.fetchone():
            raise HTTPException(403, "You are not assigned to this batch")

    result = await db.execute(
        select(User)
        .where(User.batch_id == batch_id, User.section == section, User.role == "student", User.is_active == True)
        .order_by(User.name)
    )
    students = result.scalars().all()
    return [{"id": s.id, "name": s.name} for s in students]


# Submit attendance (creates session + records, locks immediately)
@router.post("/submit")
async def submit_attendance(
    body: AttendanceSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "teacher":
        check = await db.execute(
            select(batch_teachers).where(
                batch_teachers.c.batch_id == body.batch_id,
                batch_teachers.c.teacher_id == current_user.id,
            )
        )
        if not check.fetchone():
            raise HTTPException(403, "Not assigned to this batch")

    # Check if session already exists for this date+batch+section
    existing = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.batch_id == body.batch_id,
            AttendanceSession.section == body.section,
            AttendanceSession.date == body.date,
        )
    )
    session = existing.scalar_one_or_none()
    if session and session.is_locked:
        raise HTTPException(400, "Attendance already locked for this date")

    if not session:
        session = AttendanceSession(
            id=str(uuid.uuid4()),
            batch_id=body.batch_id,
            section=body.section,
            date=body.date,
            recorded_by=current_user.id,
            is_locked=True,
        )
        db.add(session)
        await db.flush()
    else:
        # Re-submitting: delete old records
        old = await db.execute(
            select(AttendanceRecord).where(AttendanceRecord.session_id == session.id)
        )
        for r in old.scalars().all():
            await db.delete(r)
        session.is_locked = True

    for rec in body.records:
        db.add(AttendanceRecord(
            id=str(uuid.uuid4()),
            session_id=session.id,
            student_id=rec.student_id,
            status=rec.status,
        ))

    await db.commit()
    return {"ok": True, "session_id": session.id}


# List past sessions for teacher's batches
@router.get("/sessions")
async def list_sessions(
    batch_id: Optional[str] = None,
    section: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "teacher":
        # Only sessions for teacher's batches
        my_batches_result = await db.execute(
            select(batch_teachers.c.batch_id).where(batch_teachers.c.teacher_id == current_user.id)
        )
        my_batch_ids = [r[0] for r in my_batches_result.fetchall()]
        q = select(AttendanceSession).where(AttendanceSession.batch_id.in_(my_batch_ids))
    else:
        q = select(AttendanceSession)

    if batch_id:
        q = q.where(AttendanceSession.batch_id == batch_id)
    if section:
        q = q.where(AttendanceSession.section == section)

    q = q.options(selectinload(AttendanceSession.records)).order_by(AttendanceSession.date.desc())
    result = await db.execute(q)
    sessions = result.scalars().all()

    out = []
    for s in sessions:
        out.append({
            "id": s.id,
            "batch_id": s.batch_id,
            "section": s.section,
            "date": s.date.isoformat(),
            "is_locked": s.is_locked,
            "student_count": len(s.records),
            "present_count": sum(1 for r in s.records if r.status == "present"),
            "absent_count": sum(1 for r in s.records if r.status == "absent"),
            "late_count": sum(1 for r in s.records if r.status == "late"),
        })
    return out


# ── SHARED HELPER ─────────────────────────────────────────────────────────────

async def _student_attendance_data(student_id: str, db: AsyncSession):
    """Return full attendance records + summary for a student."""
    records_result = await db.execute(
        select(AttendanceRecord, AttendanceSession)
        .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
        .where(AttendanceRecord.student_id == student_id)
        .order_by(AttendanceSession.date.desc())
    )
    rows = records_result.fetchall()

    records = []
    for rec, sess in rows:
        records.append({
            "date": sess.date.isoformat(),
            "status": rec.status,
            "section": sess.section,
            "batch_id": sess.batch_id,
        })

    total = len(records)
    present = sum(1 for r in records if r["status"] == "present")
    absent = sum(1 for r in records if r["status"] == "absent")
    late = sum(1 for r in records if r["status"] == "late")
    pct = round(present / total * 100, 1) if total else 0

    return {
        "records": records,
        "summary": {
            "total": total,
            "present": present,
            "absent": absent,
            "late": late,
            "percentage": pct,
        }
    }


# ── STUDENT ENDPOINTS ──────────────────────────────────────────────────────────

@router.get("/student/me")
async def student_my_attendance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise HTTPException(403, "Students only")
    return await _student_attendance_data(current_user.id, db)


# ── PARENT ENDPOINTS ───────────────────────────────────────────────────────────

@router.get("/parent/child")
async def parent_child_attendance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "parent":
        raise HTTPException(403, "Parents only")
    if not current_user.linked_student_id:
        raise HTTPException(404, "No linked student")

    # Get child info
    child_result = await db.execute(select(User).where(User.id == current_user.linked_student_id))
    child = child_result.scalar_one_or_none()
    if not child:
        raise HTTPException(404, "Linked student not found")

    # Get batch name
    batch_name = None
    if child.batch_id:
        b = await db.execute(select(Batch).where(Batch.id == child.batch_id))
        batch = b.scalar_one_or_none()
        batch_name = batch.name if batch else None

    data = await _student_attendance_data(child.id, db)
    return {
        **data,
        "child": {
            "id": child.id,
            "name": child.name,
            "batch_id": child.batch_id,
            "batch_name": batch_name,
            "section": child.section,
        }
    }
