import pytest
from backend.app.engine.quiz_grading import (
    grade_quiz,
    calculate_course_progress,
    generate_certificate_code
)

def test_grade_quiz_all_correct():
    questions = [
        {"id": "q1", "correct_option_index": 0, "question_text": "Q1", "explanation": "Exp 1"},
        {"id": "q2", "correct_option_index": 2, "question_text": "Q2", "explanation": "Exp 2"},
    ]
    student_answers = {"q1": 0, "q2": 2}
    result = grade_quiz(questions, student_answers, passing_threshold_pct=75.0)

    assert result["score_pct"] == 100.0
    assert result["correct_count"] == 2
    assert result["passed"] is True
    assert len(result["breakdown"]) == 2
    assert result["breakdown"][0]["is_correct"] is True

def test_grade_quiz_failing():
    questions = [
        {"id": "q1", "correct_option_index": 1, "explanation": "E1"},
        {"id": "q2", "correct_option_index": 3, "explanation": "E2"},
        {"id": "q3", "correct_option_index": 0, "explanation": "E3"},
        {"id": "q4", "correct_option_index": 2, "explanation": "E4"},
    ]
    # Only 1 correct out of 4 (25%)
    student_answers = {"q1": 1, "q2": 0, "q3": 1, "q4": 0}
    result = grade_quiz(questions, student_answers, passing_threshold_pct=75.0)

    assert result["score_pct"] == 25.0
    assert result["correct_count"] == 1
    assert result["passed"] is False

def test_calculate_course_progress():
    # 2 out of 4 modules
    pct, is_done = calculate_course_progress(4, ["m1", "m2"])
    assert pct == 50.0
    assert is_done is False

    # 4 out of 4
    pct_full, is_done_full = calculate_course_progress(4, ["m1", "m2", "m3", "m4"])
    assert pct_full == 100.0
    assert is_done_full is True

def test_generate_certificate_code():
    code1 = generate_certificate_code("alice@domain.com", "course-1")
    code2 = generate_certificate_code("bob@domain.com", "course-1")

    assert code1.startswith("CERT-LS-")
    assert code2.startswith("CERT-LS-")
    assert code1 != code2
    assert len(code1) == 16  # "CERT-LS-" + 8 hex chars
