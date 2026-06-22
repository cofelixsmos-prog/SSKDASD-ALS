from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from database import get_db
from dependencies import get_current_user
from models.user import User
from models.quiz import QuizSubmission
from models.attendance import AttendanceRecord
from models.notification import Notification
from models.batch import Batch

router = APIRouter(prefix="/api/parent", tags=["parent"])


def require_parent(user: User):
    if user.role != "parent":
        raise HTTPException(403, "Parents only")


async def get_child(user: User, db: AsyncSession) -> User:
    if not user.linked_student_id:
        raise HTTPException(400, "No linked student")
    result = await db.execute(select(User).where(User.id == user.linked_student_id))
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(404, "Linked student not found")
    return child


@router.get("/summary")
async def parent_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_parent(current_user)
    child = await get_child(current_user, db)

    # Attendance
    att_result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.student_id == child.id)
    )
    records = att_result.scalars().all()
    total = len(records)
    present = sum(1 for r in records if r.status in ("present", "late"))
    att_pct = round((present / total) * 100) if total else 0

    # Latest quiz
    sub_result = await db.execute(
        select(QuizSubmission)
        .options(selectinload(QuizSubmission.quiz))
        .where(QuizSubmission.student_id == child.id)
        .order_by(QuizSubmission.submitted_at.desc())
    )
    subs = sub_result.scalars().all()
    latest_quiz_score = None
    if subs:
        s = subs[0]
        pct = round((s.score / s.total_points) * 100) if s.total_points else 0
        latest_quiz_score = {"score": s.score, "total": s.total_points, "pct": pct, "title": s.quiz.title if s.quiz else "—"}

    # Unread notifications
    notif_result = await db.execute(
        select(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    unread_count = len(notif_result.scalars().all())

    # Batch name
    batch_name = None
    if child.batch_id:
        br = await db.execute(select(Batch.name).where(Batch.id == child.batch_id))
        batch_name = br.scalar_one_or_none()

    return {
        "child_name": child.name,
        "batch": batch_name,
        "section": child.section,
        "attendance_pct": att_pct,
        "total_classes": total,
        "latest_quiz_score": latest_quiz_score,
        "quizzes_taken": len(subs),
        "notifications_unread_count": unread_count,
    }


@router.get("/quizzes")
async def parent_quizzes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_parent(current_user)
    child = await get_child(current_user, db)

    result = await db.execute(
        select(QuizSubmission)
        .options(selectinload(QuizSubmission.quiz))
        .where(QuizSubmission.student_id == child.id)
        .order_by(QuizSubmission.submitted_at.desc())
    )
    subs = result.scalars().all()
    return [
        {
            "id": s.id,
            "quiz_title": s.quiz.title if s.quiz else "—",
            "subject": s.quiz.subject if s.quiz else "—",
            "score": s.score,
            "total_points": s.total_points,
            "pct": round((s.score / s.total_points) * 100) if s.total_points else 0,
            "submitted_at": s.submitted_at.isoformat(),
            "violation_confirmed": s.violation_confirmed,
            "cheat_flag_count": s.cheat_flag_count,
        }
        for s in subs
    ]


@router.get("/notifications")
async def parent_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_parent(current_user)
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifs = result.scalars().all()
    return [
        {
            "id": n.id,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifs
    ]


@router.patch("/notifications/read")
async def mark_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_parent(current_user)
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}
