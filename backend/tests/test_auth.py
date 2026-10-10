import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_login_success():
    roles = [
        ("admin", "Password123!", "SCHOOL_ADMIN"),
        ("principal", "Password123!", "PRINCIPAL"),
        ("teacher", "Password123!", "TEACHER"),
        ("student", "Password123!", "STUDENT"),
        ("parent", "Password123!", "PARENT"),
    ]
    for username, pwd, role in roles:
        response = client.post("/api/auth/login", json={"username": username, "password": pwd})
        assert response.status_code == 200, f"Login failed for {username}: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["role"] == role

def test_login_invalid_password():
    response = client.post("/api/auth/login", json={"username": "admin", "password": "WrongPassword"})
    assert response.status_code == 401
    assert "detail" in response.json()

def test_auth_me():
    # Login as admin
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "Password123!"})
    token = login_res.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["username"] == "admin"
    assert user_data["role"] == "SCHOOL_ADMIN"

def test_auth_me_unauthorized():
    response = client.get("/api/auth/me")
    assert response.status_code == 401

def test_rbac_admin_route_forbidden_for_student():
    # Login as student
    login_res = client.post("/api/auth/login", json={"username": "student", "password": "Password123!"})
    token = login_res.json()["access_token"]

    # Student trying to access admin endpoint
    response = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
