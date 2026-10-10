"""Focused checks for the legacy application's high-risk paths.

Run against a disposable database seeded with ``backend.app.seed.seed_database``.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.database import SessionLocal
from backend.app.main import app
from backend.app.models.fee import Fee
from backend.app.models.assignment import Assignment
from backend.app.models.payment import Payment
from backend.app.models.student import Student
from backend.app.models.submission import Submission
from backend.app.models.user import User
from backend.app.routes import fees
from backend.app.routes.documents import download_file
from backend.app.schemas.fee import RazorpayCreateOrderRequest, RazorpayVerifyRequest


client = TestClient(app)


def test_database_readiness():
    assert client.get("/ready").json() == {"status": "ready"}


def _login(username, password="Password123!"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_demo_password_aliases_are_not_accepted():
    assert _login("admin", "principal123").status_code == 401


def test_query_string_jwt_is_not_accepted():
    token = _login("student").json()["access_token"]
    response = client.get(f"/api/auth/me?token={token}")
    assert response.status_code == 401


def test_private_submission_path_requires_record_ownership():
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "student").one()
        foreign = db.query(Submission).filter(Submission.student_id != user.student_profile.id).first()
        if foreign is None:
            other = db.query(Student).filter(Student.id != user.student_profile.id).first()
            assignment = db.query(Assignment).first()
            assert other is not None and assignment is not None
            foreign = Submission(assignment_id=assignment.id, student_id=other.id,
                                 file_path="assignments/private-other-student.pdf",
                                 tenant_id=user.tenant_id)
            db.add(foreign)
            db.flush()
        with pytest.raises(HTTPException) as exc:
            download_file(foreign.file_path, user, db)
        assert exc.value.status_code == 404
        db.rollback()


def test_order_uses_server_balance_and_verification_is_idempotent(monkeypatch):
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "student").one()
        db.info.update(tenant_scope="tenant", tenant_id=user.tenant_id)
        student = user.student_profile
        candidates = db.query(Fee).filter((Fee.class_id == student.class_id) | (Fee.class_id.is_(None))).all()
        fee = next((candidate for candidate in candidates if fees._paise(candidate.amount - sum(
            p.amount_paid + p.discount_amount for p in db.query(Payment).filter(
                Payment.fee_id == candidate.id, Payment.student_id == student.id,
                Payment.payment_status == "PAID"
            ).all()
        )) >= 100), None)
        assert fee is not None
        paid = sum(p.amount_paid + p.discount_amount for p in db.query(Payment).filter(
            Payment.fee_id == fee.id, Payment.student_id == student.id, Payment.payment_status == "PAID"
        ).all())
        expected_paise = fees._paise(fee.amount - paid)
        assert expected_paise >= 100

        state = {"order": None}

        def create(data):
            state["order"] = {"id": "order_test_secure", **data}
            return state["order"]

        def fetch_order(_):
            return state["order"]

        def fetch_payment(_):
            return {"order_id": "order_test_secure", "status": "captured",
                    "currency": "INR", "amount": expected_paise}

        provider = SimpleNamespace(
            order=SimpleNamespace(create=create, fetch=fetch_order),
            payment=SimpleNamespace(fetch=fetch_payment),
            utility=SimpleNamespace(verify_payment_signature=lambda _: None),
        )
        monkeypatch.setattr(fees, "_razorpay_client", lambda: provider)
        monkeypatch.setattr(fees.settings, "RAZORPAY_KEY_ID", "test_public_key")

        order = fees.create_razorpay_order(
            RazorpayCreateOrderRequest(fee_id=fee.id, student_id=student.id, amount=0.01), user, db
        )
        assert order["amount"] == expected_paise

        request = RazorpayVerifyRequest(
            razorpay_order_id="order_test_secure", razorpay_payment_id="pay_test_secure_unique",
            razorpay_signature="signature", fee_id=fee.id, student_id=student.id, amount_paid=0.01,
        )
        first = fees.verify_razorpay_payment(request, user, db)
        second = fees.verify_razorpay_payment(request, user, db)
        assert first["payment_id"] == second["payment_id"]
        payment = db.query(Payment).filter(Payment.id == first["payment_id"]).one()
        assert fees._paise(payment.amount_paid) == expected_paise
        db.delete(payment)
        db.commit()


def test_order_cannot_be_created_for_another_student(monkeypatch):
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "student").one()
        other = db.query(Student).filter(Student.id != user.student_profile.id).first()
        fee = db.query(Fee).filter((Fee.class_id == other.class_id) | (Fee.class_id.is_(None))).first()
        with pytest.raises(HTTPException) as exc:
            fees.create_razorpay_order(
                RazorpayCreateOrderRequest(fee_id=fee.id, student_id=other.id, amount=10), user, db
            )
        assert exc.value.status_code == 403


def test_teacher_cannot_read_or_grade_another_teachers_assignment():
    with SessionLocal() as db:
        own = db.query(Assignment).filter(Assignment.title.like("Newton%" )).one()
        foreign = db.query(Assignment).filter(Assignment.title.like("Quadratic%" )).one()
        submission = db.query(Submission).filter(Submission.assignment_id == foreign.id).one()
    token = _login("john_doe").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/assignments/{own.id}", headers=headers).status_code == 200
    assert client.get(f"/api/assignments/{foreign.id}", headers=headers).status_code == 404
    assert client.get(f"/api/assignments/{foreign.id}/submissions", headers=headers).status_code == 404
    assert client.put(f"/api/assignments/submissions/{submission.id}/grade", headers=headers,
                      json={"marks_obtained": 10}).status_code == 404


def test_student_attendance_and_results_are_limited_to_self():
    token = _login("student").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    with SessionLocal() as db:
        me = db.query(User).filter(User.username == "student").one().student_profile.id
        other = db.query(Student).filter(Student.id != me).first().id
    assert client.get(f"/api/attendance/student/{other}", headers=headers).status_code == 403
    assert client.get("/api/attendance", headers=headers).status_code == 200
    assert all(item["student_id"] == me for item in client.get("/api/attendance", headers=headers).json())
    assert client.get("/api/results", headers=headers).status_code == 200
    assert all(item["student_id"] == me for item in client.get("/api/results", headers=headers).json())


def test_teacher_cannot_mark_unassigned_class_or_record_other_subject():
    token = _login("teacher").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    with SessionLocal() as db:
        me = db.query(User).filter(User.username == "teacher").one()
        other_subject = next(assignment for assignment in db.query(Assignment).all()
                             if assignment.teacher_id != me.teacher_profile.id).subject_id
        student_id = db.query(Student).first().id
    assert client.post("/api/results", headers=headers, json={
        "exam_id": 1, "student_id": student_id, "subject_id": other_subject,
        "marks_obtained": 50, "max_marks": 100,
    }).status_code == 403
    assert client.post("/api/attendance", headers=headers, json={
        "class_id": 999999, "section_id": 1, "date": "2026-10-04", "records": [],
    }).status_code == 403
