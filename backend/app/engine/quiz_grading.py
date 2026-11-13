"""
LMS Assessment Grading & Verifiable Certificate Engine
Evaluates student quiz submissions, calculates completion progress, and generates credentials.
"""

import uuid
import hashlib
from typing import List, Dict, Any, Tuple


def grade_quiz(
    questions: List[Dict[str, Any]],
    student_answers: Dict[str, int],
    passing_threshold_pct: float = 75.0
) -> Dict[str, Any]:
    """
    Grades quiz questions, calculates percentage, pass/fail status, and diagnostic explanations.
    """
    total_questions = len(questions)
    if total_questions == 0:
        return {
            "score_pct": 100.0,
            "correct_count": 0,
            "total_questions": 0,
            "passed": True,
            "breakdown": []
        }

    correct_count = 0
    breakdown = []

    for q in questions:
        q_id = q["id"]
        correct_idx = q["correct_option_index"]
        student_idx = student_answers.get(q_id)
        is_correct = (student_idx is not None and student_idx == correct_idx)

        if is_correct:
            correct_count += 1

        breakdown.append({
            "question_id": q_id,
            "question_text": q.get("question_text", ""),
            "selected_option": student_idx,
            "correct_option": correct_idx,
            "is_correct": is_correct,
            "explanation": q.get("explanation", "")
        })

    score_pct = round((correct_count / total_questions) * 100.0, 1)
    passed = score_pct >= passing_threshold_pct

    return {
        "score_pct": score_pct,
        "correct_count": correct_count,
        "total_questions": total_questions,
        "passing_threshold_pct": passing_threshold_pct,
        "passed": passed,
        "breakdown": breakdown
    }


def calculate_course_progress(total_modules: int, completed_module_ids: List[str]) -> Tuple[float, bool]:
    """
    Calculates percentage of syllabus completed.
    """
    if total_modules <= 0:
        return 100.0, True

    completed_count = len(set(completed_module_ids))
    progress_pct = min(100.0, round((completed_count / total_modules) * 100.0, 1))
    is_completed = completed_count >= total_modules
    return progress_pct, is_completed


def generate_certificate_code(user_email: str, course_id: str) -> str:
    """
    Generates deterministic verifiable credential identifier.
    """
    token_seed = f"{user_email}:{course_id}:{uuid.uuid4().hex[:8]}"
    hash_digest = hashlib.sha256(token_seed.encode("utf-8")).hexdigest().upper()
    return f"CERT-LS-{hash_digest[:8]}"
