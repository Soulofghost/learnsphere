import uuid
import json
import datetime
from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional, List

from backend.app.database import get_connection
from backend.app.schemas import EnrollRequest, CompleteModuleRequest, QuizSubmitRequest
from backend.app.engine.quiz_grading import (
    grade_quiz,
    calculate_course_progress,
    generate_certificate_code
)

router = APIRouter(prefix="/api", tags=["lms"])

@router.get("/health")
def healthcheck():
    return {"status": "ok", "service": "LearnSphere LMS", "version": "1.0.0"}

@router.get("/courses")
def list_courses(category: Optional[str] = None, level: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM courses WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if level:
        query += " AND level = ?"
        params.append(level)

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, params)
    courses = cursor.fetchall()

    results = []
    for c in courses:
        cursor.execute("SELECT COUNT(*) FROM modules WHERE course_id = ?;", (c["id"],))
        mod_count = cursor.fetchone()[0]

        results.append({
            "id": c["id"],
            "title": c["title"],
            "slug": c["slug"],
            "description": c["description"],
            "category": c["category"],
            "level": c["level"],
            "instructor": c["instructor"],
            "duration_hours": c["duration_hours"],
            "modules_count": mod_count
        })

    conn.close()
    return {"total": len(results), "courses": results}

@router.get("/courses/{id_or_slug}")
def get_course_details(id_or_slug: str, user_email: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM courses WHERE id = ? OR slug = ?;", (id_or_slug, id_or_slug))
    course = cursor.fetchone()
    if not course:
        conn.close()
        raise HTTPException(status_code=404, detail="Course not found")

    c_id = course["id"]

    cursor.execute("SELECT * FROM modules WHERE course_id = ? ORDER BY sequence_order ASC;", (c_id,))
    modules = [{
        "id": m["id"],
        "title": m["title"],
        "sequence_order": m["sequence_order"],
        "content": m["content"],
        "duration_minutes": m["duration_minutes"]
    } for m in cursor.fetchall()]

    cursor.execute("SELECT id, title, passing_score_pct FROM quizzes WHERE course_id = ?;", (c_id,))
    quiz_row = cursor.fetchone()
    quiz_info = None
    if quiz_row:
        cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = ?;", (quiz_row["id"],))
        q_count = cursor.fetchone()[0]
        quiz_info = {
            "id": quiz_row["id"],
            "title": quiz_row["title"],
            "passing_score_pct": quiz_row["passing_score_pct"],
            "questions_count": q_count
        }

    enrollment_info = None
    if user_email:
        cursor.execute("SELECT * FROM enrollments WHERE course_id = ? AND user_email = ?;", (c_id, user_email))
        enr = cursor.fetchone()
        if enr:
            completed_mods = json.loads(enr["completed_modules_json"] or "[]")
            enrollment_info = {
                "progress_pct": enr["progress_pct"],
                "completed_modules": completed_mods,
                "is_completed": bool(enr["is_completed"]),
                "enrolled_at": enr["enrolled_at"]
            }

    conn.close()

    return {
        "id": course["id"],
        "title": course["title"],
        "slug": course["slug"],
        "description": course["description"],
        "category": course["category"],
        "level": course["level"],
        "instructor": course["instructor"],
        "duration_hours": course["duration_hours"],
        "modules": modules,
        "quiz": quiz_info,
        "enrollment": enrollment_info
    }

@router.post("/courses/{course_id}/enroll", status_code=status.HTTP_201_CREATED)
def enroll_course(course_id: str, payload: EnrollRequest):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM courses WHERE id = ? OR slug = ?;", (course_id, course_id))
    course = cursor.fetchone()
    if not course:
        conn.close()
        raise HTTPException(status_code=404, detail="Course not found")

    real_c_id = course["id"]

    cursor.execute("SELECT id, progress_pct FROM enrollments WHERE course_id = ? AND user_email = ?;",
                   (real_c_id, payload.user_email))
    existing = cursor.fetchone()

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if existing:
        conn.close()
        return {
            "message": "User is already enrolled in this course",
            "enrollment_id": existing["id"],
            "progress_pct": existing["progress_pct"]
        }

    enr_id = str(uuid.uuid4())
    cursor.execute("""
    INSERT INTO enrollments (id, user_email, user_name, course_id, progress_pct, completed_modules_json, is_completed, enrolled_at)
    VALUES (?, ?, ?, ?, 0.0, '[]', 0, ?);
    """, (enr_id, payload.user_email, payload.user_name, real_c_id, now_iso))

    conn.commit()
    conn.close()

    return {
        "enrollment_id": enr_id,
        "course_id": real_c_id,
        "user_email": payload.user_email,
        "user_name": payload.user_name,
        "progress_pct": 0.0,
        "enrolled_at": now_iso
    }

@router.post("/courses/{course_id}/modules/{module_id}/complete")
def complete_module(course_id: str, module_id: str, payload: CompleteModuleRequest):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM courses WHERE id = ? OR slug = ?;", (course_id, course_id))
    c_row = cursor.fetchone()
    if not c_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Course not found")
    real_c_id = c_row["id"]

    cursor.execute("SELECT * FROM enrollments WHERE course_id = ? AND user_email = ?;", (real_c_id, payload.user_email))
    enr = cursor.fetchone()
    if not enr:
        conn.close()
        raise HTTPException(status_code=400, detail="User must enroll in course before completing modules")

    cursor.execute("SELECT COUNT(*) FROM modules WHERE course_id = ?;", (real_c_id,))
    total_mods = cursor.fetchone()[0]

    completed_mods = json.loads(enr["completed_modules_json"] or "[]")
    if module_id not in completed_mods:
        completed_mods.append(module_id)

    progress_pct, is_completed = calculate_course_progress(total_mods, completed_mods)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    completed_at = now_iso if is_completed else enr["completed_at"]

    cursor.execute("""
    UPDATE enrollments SET
        progress_pct = ?,
        completed_modules_json = ?,
        is_completed = ?,
        completed_at = ?
    WHERE id = ?;
    """, (progress_pct, json.dumps(completed_mods), 1 if is_completed else 0, completed_at, enr["id"]))

    conn.commit()
    conn.close()

    return {
        "course_id": real_c_id,
        "module_id": module_id,
        "progress_pct": progress_pct,
        "completed_modules_count": len(completed_mods),
        "total_modules": total_mods,
        "is_syllabus_completed": is_completed
    }

@router.get("/courses/{course_id}/quiz")
def get_course_quiz(course_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM courses WHERE id = ? OR slug = ?;", (course_id, course_id))
    c_row = cursor.fetchone()
    if not c_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Course not found")
    real_c_id = c_row["id"]

    cursor.execute("SELECT * FROM quizzes WHERE course_id = ?;", (real_c_id,))
    quiz = cursor.fetchone()
    if not quiz:
        conn.close()
        raise HTTPException(status_code=404, detail="No assessment found for this course")

    cursor.execute("SELECT id, question_text, options_json FROM quiz_questions WHERE quiz_id = ?;", (quiz["id"],))
    questions = [{
        "id": q["id"],
        "question_text": q["question_text"],
        "options": json.loads(q["options_json"])
    } for q in cursor.fetchall()]

    conn.close()

    return {
        "quiz_id": quiz["id"],
        "title": quiz["title"],
        "passing_score_pct": quiz["passing_score_pct"],
        "questions": questions
    }

@router.post("/courses/{course_id}/quiz/submit")
def submit_course_quiz(course_id: str, payload: QuizSubmitRequest):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title FROM courses WHERE id = ? OR slug = ?;", (course_id, course_id))
    c_row = cursor.fetchone()
    if not c_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Course not found")
    real_c_id = c_row["id"]

    cursor.execute("SELECT * FROM quizzes WHERE course_id = ?;", (real_c_id,))
    quiz = cursor.fetchone()
    if not quiz:
        conn.close()
        raise HTTPException(status_code=404, detail="Quiz not found")

    cursor.execute("SELECT * FROM quiz_questions WHERE quiz_id = ?;", (quiz["id"],))
    q_rows = cursor.fetchall()
    questions_list = [{
        "id": q["id"],
        "question_text": q["question_text"],
        "correct_option_index": q["correct_option_index"],
        "explanation": q["explanation"]
    } for q in q_rows]

    grade_result = grade_quiz(
        questions=questions_list,
        student_answers=payload.answers,
        passing_threshold_pct=quiz["passing_score_pct"]
    )

    certificate_issued = None

    if grade_result["passed"]:
        # Verify enrollment and modules completed
        cursor.execute("SELECT * FROM enrollments WHERE course_id = ? AND user_email = ?;", (real_c_id, payload.user_email))
        enr = cursor.fetchone()

        if enr and bool(enr["is_completed"]):
            # Check if certificate already exists
            cursor.execute("SELECT * FROM certificates WHERE course_id = ? AND user_email = ?;", (real_c_id, payload.user_email))
            existing_cert = cursor.fetchone()

            if existing_cert:
                certificate_issued = {
                    "cert_code": existing_cert["cert_code"],
                    "issued_at": existing_cert["issued_at"],
                    "score_pct": existing_cert["score_pct"],
                    "is_new": False
                }
            else:
                cert_code = generate_certificate_code(payload.user_email, real_c_id)
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cert_id = str(uuid.uuid4())

                cursor.execute("""
                INSERT INTO certificates (id, cert_code, user_name, user_email, course_id, score_pct, issued_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (cert_id, cert_code, payload.user_name, payload.user_email, real_c_id, grade_result["score_pct"], now_iso))

                conn.commit()

                certificate_issued = {
                    "cert_code": cert_code,
                    "issued_at": now_iso,
                    "score_pct": grade_result["score_pct"],
                    "is_new": True
                }

    conn.close()

    return {
        "course_id": real_c_id,
        "score_pct": grade_result["score_pct"],
        "correct_count": grade_result["correct_count"],
        "total_questions": grade_result["total_questions"],
        "passed": grade_result["passed"],
        "breakdown": grade_result["breakdown"],
        "certificate": certificate_issued
    }

@router.get("/certificates/{cert_code}/verify")
def verify_certificate(cert_code: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.*, crs.title as course_title, crs.instructor, crs.duration_hours
    FROM certificates c
    JOIN courses crs ON c.course_id = crs.id
    WHERE c.cert_code = ?;
    """, (cert_code.upper(),))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Invalid certificate credential identifier")

    return {
        "status": "VALID",
        "cert_code": row["cert_code"],
        "recipient_name": row["user_name"],
        "recipient_email": row["user_email"],
        "course_title": row["course_title"],
        "instructor": row["instructor"],
        "duration_hours": row["duration_hours"],
        "score_percentage": row["score_pct"],
        "issued_at": row["issued_at"]
    }

@router.get("/users/{email}/profile")
def get_user_learning_profile(email: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT e.*, c.title as course_title, c.category, c.level
    FROM enrollments e
    JOIN courses c ON e.course_id = c.id
    WHERE e.user_email = ?;
    """, (email,))
    enrollment_rows = cursor.fetchall()

    enrollments = [{
        "course_id": r["course_id"],
        "course_title": r["course_title"],
        "category": r["category"],
        "level": r["level"],
        "progress_pct": r["progress_pct"],
        "is_completed": bool(r["is_completed"]),
        "enrolled_at": r["enrolled_at"],
        "completed_at": r["completed_at"]
    } for r in enrollment_rows]

    cursor.execute("""
    SELECT c.*, crs.title as course_title
    FROM certificates c
    JOIN courses crs ON c.course_id = crs.id
    WHERE c.user_email = ?;
    """, (email,))
    cert_rows = cursor.fetchall()

    certificates = [{
        "cert_code": c["cert_code"],
        "course_title": c["course_title"],
        "score_pct": c["score_pct"],
        "issued_at": c["issued_at"]
    } for c in cert_rows]

    conn.close()

    return {
        "user_email": email,
        "enrolled_courses": enrollments,
        "certificates_earned": certificates
    }
