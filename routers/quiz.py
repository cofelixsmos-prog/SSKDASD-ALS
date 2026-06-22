import uuid
import json
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from database import get_db
from dependencies import get_current_user
from models.user import User
from models.quiz import Quiz, Question, QuizSubmission
from schemas.quiz import QuizCreate, QuizUpdate, QuizOut
from services.quiz_service import generate_quiz_code
from typing import Optional

router = APIRouter(prefix="/api/quizzes", tags=["quiz"])


def _quiz_out(quiz: Quiz, questions) -> dict:
    return {
        "id": quiz.id,
        "title": quiz.title,
        "subject": quiz.subject,
        "batch_id": quiz.batch_id,
        "status": quiz.status,
        "code": quiz.code,
        "timer_minutes": quiz.timer_minutes,
        "shuffle_questions": quiz.shuffle_questions,
        "shuffle_options": quiz.shuffle_options,
        "show_answers_on_close": quiz.show_answers_on_close,
        "created_at": quiz.created_at.isoformat(),
        "question_count": len(questions),
    }


@router.get("")
async def list_quizzes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Quiz).options(selectinload(Quiz.questions))
    if current_user.role == "teacher":
        q = q.where(Quiz.created_by == current_user.id)
    result = await db.execute(q.order_by(Quiz.created_at.desc()))
    quizzes = result.scalars().all()
    return [_quiz_out(qz, qz.questions) for qz in quizzes]


@router.post("")
async def create_quiz(
    body: QuizCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("teacher", "admin"):
        raise HTTPException(403, "Teachers only")
    code = generate_quiz_code()
    # Ensure code is unique
    while True:
        existing = await db.execute(select(Quiz).where(Quiz.code == code))
        if not existing.scalar_one_or_none():
            break
        code = generate_quiz_code()

    quiz = Quiz(
        id=str(uuid.uuid4()),
        title=body.title,
        subject=body.subject,
        created_by=current_user.id,
        batch_id=body.batch_id,
        status="draft",
        code=code,
        timer_minutes=body.timer_minutes,
        shuffle_questions=body.shuffle_questions,
        shuffle_options=body.shuffle_options,
        show_answers_on_close=body.show_answers_on_close,
    )
    db.add(quiz)
    await db.flush()

    for i, q in enumerate(body.questions):
        db.add(Question(
            id=str(uuid.uuid4()),
            quiz_id=quiz.id,
            type=q.type,
            text=q.text,
            options=json.dumps(q.options or []),
            correct_answers=json.dumps(q.correct_answers),
            points=q.points,
            order=i,
            case_sensitive=q.case_sensitive,
        ))

    await db.commit()
    await db.refresh(quiz)
    return _quiz_out(quiz, body.questions)


@router.get("/{quiz_id}")
async def get_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if current_user.role == "teacher" and quiz.created_by != current_user.id:
        raise HTTPException(403, "Not your quiz")

    questions = sorted(quiz.questions, key=lambda q: q.order)
    return {
        **_quiz_out(quiz, questions),
        "questions": [{
            "id": q.id,
            "type": q.type,
            "text": q.text,
            "options": (json.loads(q.options) if isinstance(q.options, str) else (q.options or [])),
            "correct_answers": (json.loads(q.correct_answers) if isinstance(q.correct_answers, str) else (q.correct_answers or [])),
            "points": q.points,
            "order": q.order,
            "case_sensitive": q.case_sensitive,
        } for q in questions],
    }


@router.patch("/{quiz_id}")
async def update_quiz(
    quiz_id: str,
    body: QuizUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if current_user.role == "teacher" and quiz.created_by != current_user.id:
        raise HTTPException(403, "Not your quiz")
    if quiz.status == "active":
        raise HTTPException(400, "Cannot edit an active quiz")

    data = body.model_dump(exclude_none=True)
    questions_data = data.pop("questions", None)

    for field, val in data.items():
        setattr(quiz, field, val)

    if questions_data is not None:
        await db.execute(delete(Question).where(Question.quiz_id == quiz_id))
        for i, q in enumerate(questions_data):
            db.add(Question(
                id=str(uuid.uuid4()),
                quiz_id=quiz.id,
                type=q["type"],
                text=q["text"],
                options=json.dumps(q.get("options") or []),
                correct_answers=json.dumps(q.get("correct_answers", [])),
                points=q.get("points", 1),
                order=i,
                case_sensitive=q.get("case_sensitive", False),
            ))

    await db.commit()
    await db.refresh(quiz)
    result2 = await db.execute(select(Question).where(Question.quiz_id == quiz_id))
    qs = result2.scalars().all()
    return _quiz_out(quiz, qs)


@router.delete("/{quiz_id}")
async def delete_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if current_user.role == "teacher" and quiz.created_by != current_user.id:
        raise HTTPException(403, "Not your quiz")
    await db.delete(quiz)
    await db.commit()
    return {"ok": True}


@router.post("/{quiz_id}/launch")
async def launch_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if current_user.role == "teacher" and quiz.created_by != current_user.id:
        raise HTTPException(403, "Not your quiz")
    if not quiz.questions:
        raise HTTPException(400, "Quiz has no questions")
    quiz.status = "active"
    await db.commit()
    return {"ok": True, "code": quiz.code, "quiz_id": quiz.id}


@router.post("/{quiz_id}/close")
async def close_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if current_user.role == "teacher" and quiz.created_by != current_user.id:
        raise HTTPException(403, "Not your quiz")
    quiz.status = "closed"
    await db.commit()
    return {"ok": True}


@router.get("/join/{code}")
async def join_by_code(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from routers.websocket import started_quizzes
    result = await db.execute(select(Quiz).where(Quiz.code == code.upper()))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if quiz.status != "active":
        raise HTTPException(400, "Quiz is not active")
    if quiz.id in started_quizzes:
        raise HTTPException(400, "Quiz has already started — late joining is not allowed")
    return {"quiz_id": quiz.id, "title": quiz.title, "subject": quiz.subject, "timer_minutes": quiz.timer_minutes}


@router.get("/{quiz_id}/take")
async def take_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student endpoint: returns quiz with questions (shuffled if enabled), no correct_answers."""
    result = await db.execute(
        select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if quiz.status != "active":
        raise HTTPException(400, "Quiz is not active")

    questions = sorted(quiz.questions, key=lambda q: q.order)
    if quiz.shuffle_questions:
        random.shuffle(questions)

    q_list = []
    for q in questions:
        opts = json.loads(q.options or "[]") if isinstance(q.options, str) else (q.options or [])
        if quiz.shuffle_options and q.type == "mcq" and opts:
            indexed = list(enumerate(opts))
            random.shuffle(indexed)
            opts = [o for _, o in indexed]
        q_list.append({
            "id": q.id,
            "type": q.type,
            "text": q.text,
            "options": opts,
            "points": q.points,
            "order": q.order,
        })

    return {
        "id": quiz.id,
        "title": quiz.title,
        "subject": quiz.subject,
        "timer_minutes": quiz.timer_minutes,
        "shuffle_questions": quiz.shuffle_questions,
        "shuffle_options": quiz.shuffle_options,
        "questions": q_list,
    }


@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student submits answers. Scores immediately."""
    result = await db.execute(
        select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    if quiz.status not in ("active", "closed"):
        raise HTTPException(400, "Quiz is not active")

    # Check duplicate submission
    existing = await db.execute(
        select(QuizSubmission).where(
            QuizSubmission.quiz_id == quiz_id,
            QuizSubmission.student_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Already submitted")

    # Build lookup map
    q_map = {q.id: q for q in quiz.questions}
    student_answers = body.get("answers", [])  # [{question_id, answer: []}]

    score = 0
    total_points = sum(q.points for q in quiz.questions)
    results = []

    for ans_item in student_answers:
        qid = ans_item.get("question_id")
        student_ans = ans_item.get("answer", [])
        if isinstance(student_ans, str):
            student_ans = [student_ans]

        q = q_map.get(qid)
        if not q:
            continue

        correct = json.loads(q.correct_answers) if isinstance(q.correct_answers, str) else (q.correct_answers or [])
        opts = json.loads(q.options or "[]") if isinstance(q.options, str) else (q.options or [])

        is_correct = False
        if q.type == "mcq":
            # student_ans contains option indices as strings
            student_texts = [opts[int(i)] for i in student_ans if i.isdigit() and int(i) < len(opts)]
            correct_texts = [opts[int(i)] for i in correct if str(i).isdigit() and int(i) < len(opts)]
            is_correct = set(student_texts) == set(correct_texts)
            display_student = student_texts[0] if student_texts else ""
            display_correct = correct_texts[0] if correct_texts else ""
        else:
            raw = (student_ans[0] if student_ans else "").strip()
            if q.case_sensitive:
                is_correct = raw in correct
            else:
                is_correct = raw.lower() in [c.lower() for c in correct]
            display_student = raw
            display_correct = correct[0] if correct else ""

        if is_correct:
            score += q.points

        results.append({
            "question_id": qid,
            "question_text": q.text,
            "student_answer": display_student,
            "correct_answer": display_correct,
            "is_correct": is_correct,
            "points": q.points if is_correct else 0,
        })

    submission = QuizSubmission(
        id=str(uuid.uuid4()),
        quiz_id=quiz_id,
        student_id=current_user.id,
        answers=student_answers,
        score=score,
        total_points=total_points,
        auto_submitted=body.get("auto_submitted", False),
    )
    db.add(submission)
    await db.commit()

    return {
        "score": score,
        "total_points": total_points,
        "auto_submitted": body.get("auto_submitted", False),
        "show_answers": quiz.show_answers_on_close,
        "results": results if quiz.show_answers_on_close else [],
    }


@router.get("/{quiz_id}/my-result")
async def my_result(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student fetches their own result after quiz closes."""
    result = await db.execute(
        select(QuizSubmission).where(
            QuizSubmission.quiz_id == quiz_id,
            QuizSubmission.student_id == current_user.id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "No submission found")

    qr = await db.execute(select(Quiz).options(selectinload(Quiz.questions)).where(Quiz.id == quiz_id))
    quiz = qr.scalar_one_or_none()

    if not quiz or not quiz.show_answers_on_close:
        return {"score": sub.score, "total_points": sub.total_points, "auto_submitted": sub.auto_submitted, "results": []}

    q_map = {q.id: q for q in quiz.questions}
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
            results.append({"question_id": qid, "question_text": q.text, "student_answer": student_texts[0] if student_texts else "", "correct_answer": correct_texts[0] if correct_texts else "", "is_correct": is_correct})
        else:
            raw = (student_ans[0] if student_ans else "").strip()
            is_correct = raw in correct if q.case_sensitive else raw.lower() in [c.lower() for c in correct]
            results.append({"question_id": qid, "question_text": q.text, "student_answer": raw, "correct_answer": correct[0] if correct else "", "is_correct": is_correct})

    return {"score": sub.score, "total_points": sub.total_points, "auto_submitted": sub.auto_submitted, "results": results}
