import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import get_db
from dependencies import get_current_user
from models.user import User
from models.quiz import Quiz, QuizSubmission
from services.ai_service import analyse_mistakes

router = APIRouter(prefix="/api/student", tags=["student"])


@router.get("/submissions")
async def list_submissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise HTTPException(403, "Students only")

    result = await db.execute(
        select(QuizSubmission)
        .options(selectinload(QuizSubmission.quiz))
        .where(QuizSubmission.student_id == current_user.id)
        .order_by(QuizSubmission.submitted_at.desc())
    )
    subs = result.scalars().all()
    return [
        {
            "id": s.id,
            "quiz_id": s.quiz_id,
            "quiz_title": s.quiz.title if s.quiz else "—",
            "subject": s.quiz.subject if s.quiz else "—",
            "score": s.score,
            "total_points": s.total_points,
            "submitted_at": s.submitted_at.isoformat(),
            "auto_submitted": s.auto_submitted,
            "cheat_flag_count": s.cheat_flag_count,
            "violation_confirmed": s.violation_confirmed,
        }
        for s in subs
    ]


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns full submission detail with AI mistake analysis."""
    if current_user.role != "student":
        raise HTTPException(403, "Students only")

    result = await db.execute(
        select(QuizSubmission)
        .options(selectinload(QuizSubmission.quiz).selectinload(Quiz.questions))
        .where(QuizSubmission.id == submission_id, QuizSubmission.student_id == current_user.id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Submission not found")

    quiz = sub.quiz
    q_map = {q.id: q for q in (quiz.questions if quiz else [])}

    # Build results
    results = []
    for ans_item in (sub.answers or []):
        qid = ans_item.get("question_id")
        q = q_map.get(qid)
        if not q:
            continue
        correct = json.loads(q.correct_answers) if isinstance(q.correct_answers, str) else (q.correct_answers or [])
        opts = json.loads(q.options or "[]") if isinstance(q.options, str) else (q.options or [])
        student_ans = ans_item.get("answer", [])
        if isinstance(student_ans, str):
            student_ans = [student_ans]

        if q.type == "mcq":
            student_texts = [opts[int(i)] for i in student_ans if str(i).isdigit() and int(i) < len(opts)]
            correct_texts = [opts[int(i)] for i in correct if str(i).isdigit() and int(i) < len(opts)]
            is_correct = set(student_texts) == set(correct_texts)
            results.append({
                "question_id": qid,
                "question_text": q.text,
                "student_answer": student_texts[0] if student_texts else "",
                "correct_answer": correct_texts[0] if correct_texts else "",
                "is_correct": is_correct,
                "points": q.points,
            })
        else:
            raw = (student_ans[0] if student_ans else "").strip()
            is_correct = raw in correct if q.case_sensitive else raw.lower() in [c.lower() for c in correct]
            results.append({
                "question_id": qid,
                "question_text": q.text,
                "student_answer": raw,
                "correct_answer": correct[0] if correct else "",
                "is_correct": is_correct,
                "points": q.points,
            })

    # AI analysis — cached
    ai_analysis = sub.ai_analysis
    if not ai_analysis and results:
        try:
            ai_analysis = analyse_mistakes(
                {"score": sub.score, "total_points": sub.total_points, "results": results},
                []
            )
            sub.ai_analysis = ai_analysis
            await db.commit()
        except Exception:
            ai_analysis = None

    return {
        "id": sub.id,
        "quiz_id": sub.quiz_id,
        "quiz_title": quiz.title if quiz else "—",
        "subject": quiz.subject if quiz else "—",
        "score": sub.score,
        "total_points": sub.total_points,
        "submitted_at": sub.submitted_at.isoformat(),
        "auto_submitted": sub.auto_submitted,
        "cheat_flag_count": sub.cheat_flag_count,
        "violation_confirmed": sub.violation_confirmed,
        "results": results,
        "ai_analysis": ai_analysis,
    }
