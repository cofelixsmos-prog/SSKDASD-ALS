import io
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from dependencies import get_current_user
from models.user import User
from services.ai_service import generate_quiz_questions
from typing import Optional

router = APIRouter(prefix="/api/ai", tags=["ai"])
limiter = Limiter(key_func=get_remote_address)


def check_teacher(user: User):
    if user.role not in ("teacher", "admin"):
        raise HTTPException(403, "Teachers only")


@router.post("/generate-from-topic")
@limiter.limit("5/minute")
async def generate_from_topic(
    request: Request,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    check_teacher(current_user)
    topic = (body.get("topic") or "").strip()
    if not topic:
        raise HTTPException(400, "Topic is required")
    count = min(int(body.get("count", 10)), 30)
    q_type = body.get("q_type", "mcq")
    difficulty = body.get("difficulty", "medium")

    try:
        questions = generate_quiz_questions(
            content=f"Topic: {topic}\n\nGenerate questions about this subject.",
            count=count,
            q_type=q_type,
            difficulty=difficulty,
        )
        return {"questions": questions}
    except Exception as e:
        raise HTTPException(500, f"AI generation failed: {str(e)}")


@router.post("/generate-from-pdf")
@limiter.limit("5/minute")
async def generate_from_pdf(
    request: Request,
    file: UploadFile = File(...),
    count: int = Form(10),
    q_type: str = Form("mcq"),
    difficulty: str = Form("medium"),
    current_user: User = Depends(get_current_user),
):
    check_teacher(current_user)
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content_bytes = await file.read()
    if len(content_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "PDF must be under 10MB")

    # Extract text from PDF
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        text = text.strip()
        if not text:
            raise HTTPException(400, "Could not extract text from PDF. Try a text-based PDF.")
    except ImportError:
        raise HTTPException(500, "pypdf not installed")
    except Exception as e:
        raise HTTPException(400, f"PDF reading failed: {str(e)}")

    try:
        questions = generate_quiz_questions(
            content=text,
            count=min(count, 30),
            q_type=q_type,
            difficulty=difficulty,
        )
        return {"questions": questions}
    except Exception as e:
        raise HTTPException(500, f"AI generation failed: {str(e)}")
