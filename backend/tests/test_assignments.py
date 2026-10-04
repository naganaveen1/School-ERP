import io
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def get_teacher_token(username="teacher"):
    res = client.post("/api/auth/login", json={"username": username, "password": "Password123!"})
    return res.json()["access_token"]

def get_student_token():
    res = client.post("/api/auth/login", json={"username": "student", "password": "Password123!"})
    return res.json()["access_token"]

def test_create_assignment():
    token = get_teacher_token()
    due = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
    response = client.post(
        "/api/assignments",
        data={
            "title": "Geometry Homework 1",
            "class_id": 1,
            "subject_id": 1,
            "due_date": due,
            "max_marks": 50.0,
            "description": "Triangle congruence proofs"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    created = response.json()
    assert created["title"] == "Geometry Homework 1"
    assert created["max_marks"] == 50.0

def test_list_assignments_student():
    student_token = get_student_token()
    response = client.get("/api/assignments", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1

def test_student_submit_and_grade():
    teacher_token = get_teacher_token("john_doe")
    student_token = get_student_token()

    # Submit to assignment 2 (Newton's Laws)
    dummy_file = io.BytesIO(b"%PDF-1.4 dummy test assignment submission content")
    files = {"file": ("my_submission.pdf", dummy_file, "application/pdf")}
    sub_res = client.post("/api/assignments/2/submit", files=files, headers={"Authorization": f"Bearer {student_token}"})
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    submission_id = sub_data["submission_id"]

    # Teacher grades submission
    grade_res = client.put(
        f"/api/assignments/submissions/{submission_id}/grade",
        json={"marks_obtained": 92.5, "feedback": "Great experimental methodology."},
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    assert grade_res.status_code == 200
    graded = grade_res.json()
    assert graded["marks_obtained"] == 92.5
    assert graded["status"] == "graded"

def test_student_cannot_grade():
    student_token = get_student_token()
    res = client.put(
        "/api/assignments/submissions/1/grade",
        json={"marks_obtained": 100.0, "feedback": "Self grading"},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert res.status_code == 403
