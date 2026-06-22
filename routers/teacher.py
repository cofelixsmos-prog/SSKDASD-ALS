import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database import get_db
from dependencies import get_current_user
from models.user import User
from models.batch import Batch, batch_teachers
from models.attendance import AttendanceRecord, AttendanceSession
from models.quiz import Quiz, QuizSubmission

router = APIRouter(prefix="/api/teacher", tags=["teacher"])


def require_teacher(user: User):
    if user.role not in ("teacher", "admin"):
        raise HTTPException(403, "Teachers only")


async def get_teacher_batch_ids(user: User, db: AsyncSession) -> list[str]:
    if user.role == "admin":
        result = await db.execute(select(Batch.id))
        return [r[0] for r in result.all()]
    result = await db.execute(
        select(batch_teachers.c.batch_id).where(batch_teachers.c.teacher_id == user.id)
    )
    return [r[0] for r in result.all()]


@router.get("/reports/students")
async def report_students(
    batch_id: str = Query(None),
    section: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_teacher(current_user)
    batch_ids = await get_teacher_batch_ids(current_user, db)
    if not batch_ids:
        return []

    # Filter
    if batch_id:
        if batch_id not in batch_ids:
            raise HTTPException(403, "Not your batch")
        batch_ids = [batch_id]

    # Get students in those batches
    q = select(User).where(User.role == "student", User.batch_id.in_(batch_ids))
    if section:
        q = q.where(User.section == section)
    result = await db.execute(q)
    students = result.scalars().all()

    out = []
    for s in students:
        # Attendance
        att_result = await db.execute(
            select(AttendanceRecord).join(AttendanceRecord.session)
            .where(AttendanceRecord.student_id == s.id)
        )
        records = att_result.scalars().all()
        total = len(records)
        present = sum(1 for r in records if r.status in ("present", "late"))
        att_pct = round((present / total) * 100) if total else 0

        # Quiz submissions
        sub_result = await db.execute(
            select(QuizSubmission)
            .options(selectinload(QuizSubmission.quiz))
            .where(QuizSubmission.student_id == s.id)
            .order_by(QuizSubmission.submitted_at)
        )
        subs = sub_result.scalars().all()
        pcts = [round((sub.score / sub.total_points) * 100) for sub in subs if sub.total_points]
        quiz_avg = round(sum(pcts) / len(pcts)) if pcts else None

        # Trend: compare last 3 vs first 3 quizzes
        trend = None
        if len(pcts) >= 4:
            half = len(pcts) // 2
            early = sum(pcts[:half]) / half
            late = sum(pcts[half:]) / (len(pcts) - half)
            trend = round(late - early)

        # Batch name
        batch_name = None
        if s.batch_id:
            br = await db.execute(select(Batch.name).where(Batch.id == s.batch_id))
            batch_name = br.scalar_one_or_none()

        out.append({
            "student_id": s.id,
            "name": s.name,
            "batch_name": batch_name,
            "section": s.section,
            "attendance_pct": att_pct,
            "quiz_avg": quiz_avg,
            "quizzes_taken": len(subs),
            "trend": trend,
        })

    return sorted(out, key=lambda x: x["name"])


@router.get("/reports/students/export")
async def export_students_csv(
    batch_id: str = Query(None),
    section: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_teacher(current_user)
    batch_ids = await get_teacher_batch_ids(current_user, db)
    if not batch_ids:
        batch_ids = []
    if batch_id:
        if batch_id not in batch_ids:
            raise HTTPException(403, "Not your batch")
        batch_ids = [batch_id]

    q = select(User).where(User.role == "student")
    if batch_ids:
        q = q.where(User.batch_id.in_(batch_ids))
    if section:
        q = q.where(User.section == section)
    result = await db.execute(q.order_by(User.name))
    students = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Batch", "Section", "Attendance %", "Quiz Avg %", "Quizzes Taken"])

    for s in students:
        att_result = await db.execute(
            select(AttendanceRecord).where(AttendanceRecord.student_id == s.id)
        )
        records = att_result.scalars().all()
        total = len(records)
        present = sum(1 for r in records if r.status in ("present", "late"))
        att_pct = round((present / total) * 100) if total else 0

        sub_result = await db.execute(
            select(QuizSubmission).where(QuizSubmission.student_id == s.id)
        )
        subs = sub_result.scalars().all()
        pcts = [round((sub.score / sub.total_points) * 100) for sub in subs if sub.total_points]
        quiz_avg = round(sum(pcts) / len(pcts)) if pcts else ""

        batch_name = ""
        if s.batch_id:
            br = await db.execute(select(Batch.name).where(Batch.id == s.batch_id))
            batch_name = br.scalar_one_or_none() or ""

        writer.writerow([s.name, s.email, batch_name, s.section or "", att_pct, quiz_avg, len(subs)])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=student_report.csv"},
    )


@router.get("/reports/students/{student_id}")
async def report_student_detail(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_teacher(current_user)
    result = await db.execute(select(User).where(User.id == student_id, User.role == "student"))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")

    att_result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.student_id == student_id)
    )
    records = att_result.scalars().all()
    total = len(records)
    present = sum(1 for r in records if r.status in ("present", "late"))
    att_pct = round((present / total) * 100) if total else 0

    sub_result = await db.execute(
        select(QuizSubmission)
        .options(selectinload(QuizSubmission.quiz))
        .where(QuizSubmission.student_id == student_id)
        .order_by(QuizSubmission.submitted_at.desc())
    )
    subs = sub_result.scalars().all()
    pcts = [round((sub.score / sub.total_points) * 100) for sub in subs if sub.total_points]
    quiz_avg = round(sum(pcts) / len(pcts)) if pcts else None

    return {
        "student_id": student_id,
        "name": student.name,
        "attendance_pct": att_pct,
        "quiz_avg": quiz_avg,
        "quizzes_taken": len(subs),
        "submissions": [
            {
                "quiz_title": s.quiz.title if s.quiz else "—",
                "subject": s.quiz.subject if s.quiz else "—",
                "score": s.score,
                "total_points": s.total_points,
                "submitted_at": s.submitted_at.isoformat(),
            }
            for s in subs
        ],
    }


@router.get("/reports/quizzes")
async def report_quizzes(
    batch_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_teacher(current_user)
    q = select(Quiz).options(selectinload(Quiz.submissions))
    if current_user.role == "teacher":
        q = q.where(Quiz.created_by == current_user.id)
    if batch_id:
        q = q.where(Quiz.batch_id == batch_id)
    result = await db.execute(q.order_by(Quiz.created_at.desc()))
    quizzes = result.scalars().all()

    out = []
    for quiz in quizzes:
        subs = quiz.submissions
        pcts = [round((s.score / s.total_points) * 100) for s in subs if s.total_points]
        # Count students in batch
        completion = 0
        if quiz.batch_id and subs:
            total_students_result = await db.execute(
                select(func.count(User.id)).where(User.role == "student", User.batch_id == quiz.batch_id)
            )
            total_students = total_students_result.scalar() or 1
            completion = round((len(subs) / total_students) * 100)

        out.append({
            "quiz_id": quiz.id,
            "title": quiz.title,
            "subject": quiz.subject,
            "created_at": quiz.created_at.isoformat(),
            "avg_score": round(sum(pcts) / len(pcts)) if pcts else None,
            "highest": max(pcts) if pcts else None,
            "lowest": min(pcts) if pcts else None,
            "completion_rate": completion,
        })
    return out


@router.get("/reports/quizzes/{quiz_id}")
async def report_quiz_detail(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_teacher(current_user)
    result = await db.execute(
        select(Quiz).options(
            selectinload(Quiz.submissions).selectinload(QuizSubmission.student)
        ).where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")

    students = []
    for s in quiz.submissions:
        pct = round((s.score / s.total_points) * 100) if s.total_points else 0
        students.append({
            "submission_id": s.id,
            "student_id": s.student_id,
            "name": s.student.name if s.student else "—",
            "score": s.score,
            "total_points": s.total_points,
            "pct": pct,
            "cheat_flag_count": s.cheat_flag_count,
            "violation_confirmed": s.violation_confirmed,
            "auto_submitted": s.auto_submitted,
        })
    return {"quiz_id": quiz_id, "title": quiz.title, "students": sorted(students, key=lambda x: x["name"])}


@router.patch("/reports/submissions/{submission_id}/violation")
async def confirm_violation(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_teacher(current_user)
    result = await db.execute(select(QuizSubmission).where(QuizSubmission.id == submission_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Submission not found")
    sub.violation_confirmed = True
    await db.commit()
    return {"ok": True}
