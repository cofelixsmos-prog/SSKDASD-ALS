import json
import re
from groq import Groq
from config import settings

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def _chat(prompt: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def _extract_json(text: str) -> list:
    """Extract JSON array from LLM output."""
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Find JSON array in text
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    raise ValueError("Could not parse JSON from AI response")


def generate_quiz_questions(
    content: str,
    count: int = 10,
    q_type: str = "mcq",
    difficulty: str = "medium",
) -> list[dict]:
    """
    Returns list of question dicts:
    [{type, text, options, correct_answers, points}]
    """
    type_instruction = {
        "mcq": "multiple choice with 4 options each",
        "short_answer": "short answer (one or two word answers)",
        "mix": "a mix of multiple choice (with 4 options) and short answer questions",
    }.get(q_type, "multiple choice with 4 options each")

    prompt = f"""You are an expert quiz generator. Generate exactly {count} {difficulty}-difficulty {type_instruction} questions based on the following content.

CONTENT:
{content[:8000]}

OUTPUT FORMAT: Return ONLY a valid JSON array with no explanation, no markdown, no code block. Each question object must have:
- "type": "mcq" or "short_answer"
- "text": the question string
- "options": array of 4 strings (for mcq only; empty array for short_answer)
- "correct_answers": array of strings — for mcq: the correct option text(s); for short_answer: acceptable answer(s)
- "points": integer (1 for easy, 2 for medium, 3 for hard)

Example MCQ:
{{"type":"mcq","text":"What is the capital of France?","options":["London","Berlin","Paris","Madrid"],"correct_answers":["Paris"],"points":1}}

Example short answer:
{{"type":"short_answer","text":"What element has the symbol O?","options":[],"correct_answers":["Oxygen","oxygen"],"points":1}}

Generate {count} questions now:"""

    raw = _chat(prompt)
    questions = _extract_json(raw)

    # Normalize: ensure correct_answers for MCQ are indices
    result = []
    for q in questions:
        t = q.get("type", "mcq")
        text = q.get("text", "").strip()
        options = q.get("options", [])
        correct = q.get("correct_answers", [])
        points = int(q.get("points", 1))

        if not text:
            continue

        if t == "mcq" and options:
            # Convert correct_answers (text) to indices
            correct_indices = []
            for c in correct:
                for i, opt in enumerate(options):
                    if opt.strip().lower() == c.strip().lower():
                        correct_indices.append(str(i))
                        break
            result.append({
                "type": "mcq",
                "text": text,
                "options": [o.strip() for o in options],
                "correct_answers": correct_indices or ["0"],
                "points": points,
                "case_sensitive": False,
            })
        else:
            result.append({
                "type": "short_answer",
                "text": text,
                "options": [],
                "correct_answers": [c.strip() for c in correct if c.strip()],
                "points": points,
                "case_sensitive": False,
            })

    return result[:count]


def analyse_mistakes(submission_data: dict, questions_data: list[dict]) -> dict:
    """
    Analyse a student's wrong answers and return structured feedback.
    submission_data: {score, total_points, results: [{question_text, student_answer, correct_answer, is_correct}]}
    """
    wrong = [r for r in submission_data.get("results", []) if not r.get("is_correct")]
    if not wrong:
        return {
            "summary": "Excellent work! You answered all questions correctly. Keep it up!",
            "per_question": [],
        }

    wrong_text = "\n".join(
        f"Q: {r['question_text']}\nStudent answered: {r['student_answer']}\nCorrect answer: {r['correct_answer']}"
        for r in wrong
    )

    prompt = f"""A student scored {submission_data.get('score')}/{submission_data.get('total_points')} on a quiz.

Wrong answers:
{wrong_text}

Task:
1. Write a 2-3 sentence overall summary identifying the student's main weak areas and study advice.
2. For each wrong question, write a 1-2 sentence explanation of why the correct answer is right.

Return ONLY valid JSON (no markdown):
{{
  "summary": "...",
  "per_question": [
    {{"question_text": "...", "explanation": "..."}}
  ]
}}"""

    try:
        raw = _chat(prompt)
        data = json.loads(raw) if raw.strip().startswith('{') else json.loads(re.search(r'\{[\s\S]*\}', raw).group())
        return data
    except Exception:
        return {
            "summary": f"You got {submission_data.get('score')}/{submission_data.get('total_points')} points. Review the topics covered in the quiz.",
            "per_question": [{"question_text": r["question_text"], "explanation": f"The correct answer is: {r['correct_answer']}"} for r in wrong],
        }
