import pytest
import uuid
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def get_admin_token():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "Password123!"})
    return res.json()["access_token"]

def get_student_token():
    res = client.post("/api/auth/login", json={"username": "student", "password": "Password123!"})
    return res.json()["access_token"]

def test_list_students_admin():
    token = get_admin_token()
    response = client.get("/api/students", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 2
    assert any(s["admission_number"].startswith("ADM") for s in data["items"])

def test_create_student():
    token = get_admin_token()
    unique_suffix = uuid.uuid4().hex[:6]
    student_payload = {
        "username": f"test_student_{unique_suffix}",
        "email": f"student_{unique_suffix}@schoolerp.com",
        "password": "Password123!",
        "full_name": f"Test Student {unique_suffix}",
        "phone": "+1-555-9999",
        "admission_number": f"ADM_{unique_suffix}",
        "roll_number": "999",
        "class_id": 1,
        "section_id": 1,
        "gender": "Other",
        "date_of_birth": "2010-01-01"
    }
    response = client.post("/api/students", json=student_payload, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    created = response.json()
    assert created["admission_number"] == f"ADM_{unique_suffix}"
    assert created["user"]["full_name"] == f"Test Student {unique_suffix}"

def test_update_student_admin():
    token = get_admin_token()
    unique_suffix = uuid.uuid4().hex[:6]
    # Create student
    student_payload = {
        "username": f"edit_test_{unique_suffix}",
        "email": f"edit_{unique_suffix}@schoolerp.com",
        "password": "Password123!",
        "full_name": f"Original Name {unique_suffix}",
        "admission_number": f"ADM_EDIT_{unique_suffix}",
        "roll_number": "111"
    }
    create_res = client.post("/api/students", json=student_payload, headers={"Authorization": f"Bearer {token}"})
    assert create_res.status_code == 200
    student_id = create_res.json()["id"]

    # Update student details
    update_payload = {
        "full_name": f"Updated Name {unique_suffix}",
        "phone": "+1-555-8888",
        "roll_number": "222",
        "gender": "Female",
        "address": "123 Updated Way"
    }
    update_res = client.put(f"/api/students/{student_id}", json=update_payload, headers={"Authorization": f"Bearer {token}"})
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["user"]["full_name"] == f"Updated Name {unique_suffix}"
    assert updated_data["roll_number"] == "222"
    assert updated_data["address"] == "123 Updated Way"

def test_student_fee_ledger_summary():
    token = get_admin_token()
    students_res = client.get("/api/students", headers={"Authorization": f"Bearer {token}"})
    assert students_res.status_code == 200
    items = students_res.json()["items"]
    assert len(items) > 0
    student_id = items[0]["id"]

    fees_res = client.get(f"/api/students/{student_id}/fees", headers={"Authorization": f"Bearer {token}"})
    assert fees_res.status_code == 200
    summary = fees_res.json()
    assert "total_fees" in summary
    assert "total_paid" in summary
    assert "remaining_balance" in summary

