import pytest
from fastapi.testclient import TestClient
import backend.app.database as db_mod
import backend.app.config as cfg_mod
from backend.app.main import app

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    test_db_dir = tmp_path_factory.mktemp("db")
    test_db = str(test_db_dir / "test_learnsphere.db")

    cfg_mod.DB_PATH = test_db
    db_mod.DB_PATH = test_db

    holding_conn = db_mod.init_db(test_db)

    with TestClient(app) as c:
        yield c

    holding_conn.close()

def test_healthcheck(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["service"] == "LearnSphere LMS"

def test_course_listing_and_syllabus(client):
    res = client.get("/api/courses")
    assert res.status_code == 200
    courses = res.json()["courses"]
    assert len(courses) >= 2

    # Get detailed syllabus by slug
    slug = courses[0]["slug"]
    detail_res = client.get(f"/api/courses/{slug}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["modules"]) >= 3
    assert detail["quiz"] is not None

def test_enrollment_progress_and_certificate_flow(client):
    user_email = "alex.researcher@academic.org"
    user_name = "Alex Researcher"

    # 1. Fetch Course details
    course_res = client.get("/api/courses/applied-ml-pytorch")
    assert course_res.status_code == 200
    c_data = course_res.json()
    course_id = c_data["id"]
    modules = c_data["modules"]

    # 2. Enroll
    enroll_res = client.post(f"/api/courses/{course_id}/enroll", json={
        "user_name": user_name,
        "user_email": user_email
    })
    assert enroll_res.status_code == 201

    # 3. Complete each module in the syllabus
    for m in modules:
        comp_res = client.post(f"/api/courses/{course_id}/modules/{m['id']}/complete", json={
            "user_email": user_email
        })
        assert comp_res.status_code == 200

    # Verify 100% progress
    check_res = client.get(f"/api/courses/{course_id}?user_email={user_email}")
    assert check_res.json()["enrollment"]["progress_pct"] == 100.0
    assert check_res.json()["enrollment"]["is_completed"] is True

    # 4. Fetch Quiz questions
    quiz_res = client.get(f"/api/courses/{course_id}/quiz")
    assert quiz_res.status_code == 200
    questions = quiz_res.json()["questions"]
    assert len(questions) == 3

    # Answers for applied ML: Q1->1 (O(N^2)), Q2->0 (gradient clipping), Q3->1 (model.eval)
    q_map = {
        questions[0]["id"]: 1,
        questions[1]["id"]: 0,
        questions[2]["id"]: 1,
    }

    # 5. Submit Quiz with 100% passing score
    sub_res = client.post(f"/api/courses/{course_id}/quiz/submit", json={
        "user_name": user_name,
        "user_email": user_email,
        "answers": q_map
    })
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["passed"] is True
    assert sub_data["score_pct"] == 100.0
    assert sub_data["certificate"] is not None
    cert_code = sub_data["certificate"]["cert_code"]

    # 6. Verify Certificate publicly
    verify_res = client.get(f"/api/certificates/{cert_code}/verify")
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["status"] == "VALID"
    assert v_data["recipient_name"] == user_name
    assert v_data["course_title"] == "Applied Machine Learning with PyTorch"

    # 7. Check User Profile
    profile_res = client.get(f"/api/users/{user_email}/profile")
    assert profile_res.status_code == 200
    prof = profile_res.json()
    assert len(prof["enrolled_courses"]) >= 1
    assert len(prof["certificates_earned"]) >= 1
