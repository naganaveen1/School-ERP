"""Two-school API and persistence isolation on a disposable database."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import (Assignment, Attendance, ClassModel, Document, Exam, Fee, Message, Parent, Payment, Plan, Result,
                                SaasInvoice, SaasPayment, SaasProviderEvent, Section, Student,
                                Subject, Subscription, Teacher, Tenant, Timetable, User)
from backend.app.config import settings
from backend.app.routes import saas_billing
from backend.app.services import saas_billing_service
from scripts.reconcile_subscriptions import reconcile
from backend.app.utils.security import get_password_hash


@pytest.fixture
def schools(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schools.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        a = Tenant(name="School A", slug="school-a", status="ACTIVE")
        b = Tenant(name="School B", slug="school-b", status="ACTIVE")
        default_plan = Plan(name="Default", price=0, billing_interval="MONTHLY", trial_days=0,
                            features=["attendance", "assignments", "exams", "finance", "messaging",
                                      "reports", "documents"], is_active=True)
        db.add_all([a, b, default_plan])
        db.flush()
        db.add_all([Subscription(tenant_id=a.id, plan_id=default_plan.id, status="ACTIVE"),
                    Subscription(tenant_id=b.id, plan_id=default_plan.id, status="ACTIVE")])
        for tenant in (a, b):
            admin = User(tenant_id=tenant.id, username="admin", email="admin@example.test",
                         full_name=f"{tenant.name} Administrator", role="SCHOOL_ADMIN",
                         hashed_password=get_password_hash("Password123!"), is_active=True)
            child = User(tenant_id=tenant.id, username="student", email="student@example.test",
                         full_name=f"{tenant.name} Student", role="STUDENT",
                         hashed_password=get_password_hash("Password123!"), is_active=True)
            db.add_all([admin, child])
            db.flush()
            db.add(Student(tenant_id=tenant.id, user_id=child.id, admission_number="A001"))
            db.add(Fee(tenant_id=tenant.id, title=f"{tenant.name} Fee", amount=100,
                       due_date=date(2026, 11, 1)))
        db.add(User(username="platform-owner", email="owner@example.test", full_name="Platform Owner",
                    role="PLATFORM_SUPER_ADMIN", hashed_password=get_password_hash("Password123!"),
                    is_active=True))
        db.commit()
        ids = {
            "a": a.id,
            "b": b.id,
            "student_b": db.query(Student).filter(Student.tenant_id == b.id).one().id,
            "fee_b": db.query(Fee).filter(Fee.tenant_id == b.id).one().id,
            "user_b": db.query(User).filter(User.tenant_id == b.id, User.role == "STUDENT").one().id,
        }

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), factory, ids
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _token(client, slug):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Password123!",
                                                     "school_slug": slug})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _role_token(client, slug, username):
    response = client.post("/api/auth/login", json={"username": username,
                                                     "password": "Password123!", "school_slug": slug})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_school_resource_ownership_for_profiles_reports_and_timetable(schools):
    client, factory, ids = schools
    with factory() as db:
        tenant_id = ids["a"]
        first_class = ClassModel(tenant_id=tenant_id, name="First")
        other_class = ClassModel(tenant_id=tenant_id, name="Other")
        db.add_all([first_class, other_class])
        db.flush()
        first_section = Section(tenant_id=tenant_id, name="A", class_id=first_class.id)
        hidden_section = Section(tenant_id=tenant_id, name="B", class_id=first_class.id)
        other_section = Section(tenant_id=tenant_id, name="B", class_id=other_class.id)
        db.add_all([first_section, hidden_section, other_section])
        db.flush()
        first_student = db.query(Student).filter(Student.tenant_id == tenant_id).one()
        first_student.class_id, first_student.section_id = first_class.id, first_section.id
        second_user = User(tenant_id=tenant_id, username="another-student",
                           email="another-student@example.test", full_name="Another Student",
                           role="STUDENT", hashed_password=get_password_hash("Password123!"), is_active=True)
        teacher_user = User(tenant_id=tenant_id, username="teacher-a", email="teacher-a@example.test",
                            full_name="First Teacher", role="TEACHER",
                            hashed_password=get_password_hash("Password123!"), is_active=True)
        parent_user = User(tenant_id=tenant_id, username="parent-a", email="parent-a@example.test",
                           full_name="First Parent", role="PARENT",
                           hashed_password=get_password_hash("Password123!"), is_active=True)
        db.add_all([second_user, teacher_user, parent_user])
        db.flush()
        second_student = Student(tenant_id=tenant_id, user_id=second_user.id, admission_number="A002",
                                 class_id=other_class.id, section_id=other_section.id)
        teacher = Teacher(tenant_id=tenant_id, user_id=teacher_user.id, employee_id="T001")
        parent = Parent(tenant_id=tenant_id, user_id=parent_user.id)
        db.add_all([second_student, teacher, parent])
        db.flush()
        first_student.parent_id = parent.id
        subject_a = Subject(tenant_id=tenant_id, name="First Subject", code="FIRST",
                            class_id=first_class.id, teacher_id=teacher.id)
        subject_b = Subject(tenant_id=tenant_id, name="Other Subject", code="OTHER",
                            class_id=other_class.id)
        db.add_all([subject_a, subject_b])
        db.flush()
        db.add_all([
            Assignment(tenant_id=tenant_id, title="Assigned section", class_id=first_class.id,
                       section_id=first_section.id, subject_id=subject_a.id, teacher_id=teacher.id,
                       due_date=datetime(2026, 10, 15)),
            Assignment(tenant_id=tenant_id, title="Other section", class_id=first_class.id,
                       section_id=hidden_section.id, subject_id=subject_a.id, teacher_id=teacher.id,
                       due_date=datetime(2026, 10, 15)),
        ])
        exam_a = Exam(tenant_id=tenant_id, name="First Exam", exam_type="Quiz",
                      class_id=first_class.id, start_date=date(2026, 10, 1), end_date=date(2026, 10, 1),
                      is_published=True)
        exam_b = Exam(tenant_id=tenant_id, name="Other Exam", exam_type="Quiz",
                      class_id=other_class.id, start_date=date(2026, 10, 1), end_date=date(2026, 10, 1),
                      is_published=True)
        db.add_all([exam_a, exam_b])
        db.flush()
        for student, class_obj, section, subject, exam in (
            (first_student, first_class, first_section, subject_a, exam_a),
            (second_student, other_class, other_section, subject_b, exam_b),
        ):
            db.add_all([
                Attendance(tenant_id=tenant_id, student_id=student.id, class_id=class_obj.id,
                           section_id=section.id, date=date(2026, 10, 1), status="Present"),
                Result(tenant_id=tenant_id, exam_id=exam.id, student_id=student.id,
                       subject_id=subject.id, marks_obtained=80, max_marks=100, grade="A"),
                Timetable(tenant_id=tenant_id, class_id=class_obj.id, section_id=section.id,
                          subject_id=subject.id, teacher_id=teacher.id,
                          day_of_week="Monday", start_time="09:00", end_time="10:00"),
            ])
        db.commit()
        parent_id, teacher_id, first_student_id = parent.id, teacher.id, first_student.id

    student = _role_token(client, "school-a", "student")
    teacher = _role_token(client, "school-a", "teacher-a")
    parent = _role_token(client, "school-a", "parent-a")
    assert client.get(f"/api/parents/{parent_id}", headers=student).status_code == 403
    assert client.get(f"/api/parents/{parent_id}", headers=parent).status_code == 200
    assert client.get(f"/api/teachers/{teacher_id}", headers=student).status_code == 403
    assert client.get("/api/reports/attendance", headers=teacher).json()["total_records"] == 1
    assert client.get("/api/reports/academic", headers=teacher).json()["total_results"] == 1
    assert len(client.get("/api/timetable", headers=student).json()) == 1
    assert len(client.get("/api/timetable", headers=parent).json()) == 1
    assert len(client.get("/api/timetable", headers=teacher).json()) == 1
    assert len(client.get("/api/student/timetable", headers=student).json()) == 1
    assert [a["title"] for a in client.get("/api/student/assignments", headers=student).json()] == ["Assigned section"]
    assert [a["title"] for a in client.get(f"/api/parent/child/{first_student_id}/assignments", headers=parent).json()] == ["Assigned section"]


def test_two_schools_can_login_and_read_only_their_records(schools):
    client, _, ids = schools
    assert client.post("/api/auth/login", json={"username": "admin", "password": "Password123!"}).status_code == 401
    a = _token(client, "school-a")
    b = _token(client, "school-b")
    assert client.get("/api/students", headers=a).json()["total"] == 1
    assert client.get("/api/students", headers=b).json()["total"] == 1
    assert client.get(f"/api/students/{ids['student_b']}", headers=a).status_code == 404
    assert client.get(f"/api/students/{ids['student_b']}", headers=b).status_code == 200
    assert [fee["title"] for fee in client.get("/api/fees", headers=a).json()] == ["School A Fee"]
    assert [fee["title"] for fee in client.get("/api/fees", headers=b).json()] == ["School B Fee"]
    assert client.delete(f"/api/fees/{ids['fee_b']}", headers=a).status_code == 404
    assert client.post("/api/fees/payments", headers=a, json={
        "fee_id": ids["fee_b"], "student_id": ids["student_b"], "amount_paid": 10,
    }).status_code == 404
    assert client.put(f"/api/students/{ids['student_b']}", headers=a,
                      json={"full_name": "Changed"}).status_code == 404


def test_cross_school_document_and_message_ids_are_not_accessible(schools):
    client, factory, ids = schools
    with factory() as db:
        document = Document(tenant_id=ids["b"], user_id=ids["user_b"],
                            title="Private School B", file_path="tenant/b/documents/private.pdf",
                            document_type="General")
        message = Message(tenant_id=ids["b"], sender_id=ids["user_b"],
                          receiver_id=ids["user_b"], subject="School B only", body="Private")
        db.add_all([document, message])
        db.commit()
        document_id, message_id = document.id, message.id
    a = _token(client, "school-a")
    b = _token(client, "school-b")
    assert client.get(f"/api/documents/download/{document_id}", headers=a).status_code == 404
    assert client.delete(f"/api/documents/{document_id}", headers=a).status_code == 404
    assert client.patch(f"/api/messages/{message_id}/read", headers=a).status_code == 404
    assert client.post("/api/messages", headers=a, json={
        "receiver_id": ids["user_b"], "subject": "Wrong school", "body": "Blocked",
    }).status_code == 404
    assert client.get("/api/documents", headers=b).json()[0]["id"] == document_id


def test_fee_balances_include_discounts_and_ignore_pending_payments(schools):
    client, factory, ids = schools
    with factory() as db:
        fee = db.query(Fee).filter(Fee.tenant_id == ids["a"]).one()
        student = db.query(Student).filter(Student.tenant_id == ids["a"]).one()
        db.add_all([
            Payment(tenant_id=ids["a"], fee_id=fee.id, student_id=student.id,
                    amount_paid=30, discount_amount=10, payment_date=date(2026, 10, 4),
                    payment_method="Cash", payment_status="PAID"),
            Payment(tenant_id=ids["a"], fee_id=fee.id, student_id=student.id,
                    amount_paid=20, discount_amount=0, payment_date=date(2026, 10, 4),
                    payment_method="Cash", payment_status="PENDING"),
        ])
        db.commit()
        student_id = student.id
    a = _token(client, "school-a")
    summary = client.get(f"/api/fees/student/{student_id}", headers=a)
    assert summary.status_code == 200
    assert summary.json()["remaining_balance"] == 60
    report = client.get("/api/reports/fees", headers=a)
    assert report.status_code == 200
    assert report.json()["total_collected"] == 30
    assert report.json()["total_outstanding"] == 60


def test_school_branding_changes_only_own_workspace(schools):
    client, _, _ = schools
    a = _token(client, "school-a")
    change = client.patch("/api/admin/school-settings", headers=a,
                          json={"name": "School A Updated", "primary_color": "#245544"})
    assert change.status_code == 200, change.text
    assert client.get("/api/schools/school-a/branding").json()["name"] == "School A Updated"
    assert client.get("/api/schools/school-b/branding").json()["name"] == "School B"
    assert client.patch("/api/admin/school-settings", headers=_token(client, "school-b"),
                        json={"timezone": "invalid-zone"}).status_code == 400


def test_cross_school_foreign_keys_are_rejected(schools):
    _, factory, ids = schools
    with factory() as db:
        db.info.update(tenant_scope="tenant", tenant_id=ids["a"])
        db.add(Student(user_id=ids["user_b"], admission_number="ATTACK"))
        with pytest.raises(PermissionError, match="Cross-tenant relationship"):
            db.flush()


def test_platform_owner_creates_plan_and_school_transactionally(schools):
    client, _, _ = schools
    login = client.post("/api/auth/login", json={"username": "platform-owner", "password": "Password123!"})
    assert login.status_code == 200, login.text
    platform = {"Authorization": f"Bearer {login.json()['access_token']}"}
    school = _token(client, "school-a")
    assert client.get("/api/platform/schools", headers=school).status_code == 403
    plan = client.post("/api/platform/plans", headers=platform, json={
        "name": "Starter", "price": "0", "billing_interval": "MONTHLY", "trial_days": 14,
        "max_students": 500, "features": ["attendance", "assignments"]})
    assert plan.status_code == 201, plan.text
    create = client.post("/api/platform/schools", headers=platform, json={
        "name": "School C", "slug": "school-c", "email": "office@school-c.example.com",
        "admin_name": "C Admin", "admin_username": "admin", "admin_email": "admin@school-c.example.com",
        "admin_password": "StrongPassword123!", "plan_id": plan.json()["id"]})
    assert create.status_code == 201, create.text
    changed = client.post(f"/api/platform/schools/{create.json()['id']}/change-plan", headers=platform,
                          json={"plan_id": plan.json()["id"]})
    assert changed.status_code == 200, changed.text
    extended = client.post(f"/api/platform/schools/{create.json()['id']}/extend-trial", headers=platform,
                           json={"days": 7})
    assert extended.status_code == 200, extended.text
    assert client.get("/api/platform/dashboard", headers=platform).json()["total_schools"] == 3
    assert len(client.get("/api/platform/subscriptions", headers=platform).json()) == 3
    login_c = client.post("/api/auth/login", json={"username": "admin", "password": "StrongPassword123!",
                                                     "school_slug": "school-c"})
    assert login_c.status_code == 200, login_c.text
    assert client.get("/api/students", headers=platform).status_code == 403


def test_student_limit_is_enforced_from_the_subscribed_plan(schools):
    client, factory, ids = schools
    with factory() as db:
        plan = Plan(name="One Student", price=0, billing_interval="MONTHLY", trial_days=0,
                    max_students=1, features=["attendance"], is_active=True)
        db.add(plan)
        db.flush()
        db.query(Subscription).filter(Subscription.tenant_id == ids["a"]).one().plan_id = plan.id
        db.commit()
    response = client.post("/api/students", headers=_token(client, "school-a"), json={
        "username": "new-student", "email": "new-student@example.com", "password": "Password123!",
        "full_name": "New Student", "admission_number": "A002",
    })
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "USAGE_LIMIT_REACHED"


def test_expired_trial_limits_school_admin_to_billing(schools):
    client, factory, ids = schools
    with factory() as db:
        subscription = db.query(Subscription).filter(Subscription.tenant_id == ids["a"]).one()
        subscription.status = "TRIALING"
        subscription.trial_end = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Password123!",
                                                     "school_slug": "school-a"})
    assert response.status_code == 200
    assert response.json()["user"]["billing_only"] is True
    token = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/students", headers=token).status_code == 403
    with factory() as db:
        assert reconcile(db) == 1
        assert db.query(Subscription).filter(Subscription.tenant_id == ids["a"]).one().status == "EXPIRED"
        assert db.get(Tenant, ids["a"]).status == "EXPIRED"
    assert _token(client, "school-b")


def test_plan_feature_gate_is_per_school(schools):
    client, factory, ids = schools
    with factory() as db:
        basic = Plan(name="No Finance", price=0, billing_interval="MONTHLY", trial_days=0,
                     features=["attendance"], is_active=True)
        db.add(basic)
        db.flush()
        db.query(Subscription).filter(Subscription.tenant_id == ids["a"]).one().plan_id = basic.id
        db.commit()
    assert client.get("/api/fees", headers=_token(client, "school-a")).status_code == 403
    assert client.get("/api/fees", headers=_token(client, "school-b")).status_code == 200
    assert client.get("/api/student/fees", headers=_role_token(client, "school-a", "student")).status_code == 403
    assert client.get("/api/student/fees", headers=_role_token(client, "school-b", "student")).status_code == 200


def test_past_due_grace_then_expiry(schools):
    client, factory, ids = schools
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with factory() as db:
        subscription = db.query(Subscription).filter(Subscription.tenant_id == ids["a"]).one()
        subscription.current_period_end = now - timedelta(days=1)
        db.commit()
        assert reconcile(db, now) == 1
        assert subscription.status == "PAST_DUE"
    assert client.get("/api/students", headers=_token(client, "school-a")).status_code == 200
    with factory() as db:
        assert reconcile(db, now + timedelta(days=8)) == 1
        assert db.query(Subscription).filter(Subscription.tenant_id == ids["a"]).one().status == "EXPIRED"
    assert client.get("/api/students", headers=_token(client, "school-a")).status_code == 403


def test_saas_checkout_verification_is_isolated_and_idempotent(schools, monkeypatch):
    client, factory, ids = schools
    with factory() as db:
        paid_plan = Plan(name="Paid", price=100, billing_interval="MONTHLY", trial_days=0,
                         features=["attendance", "finance"], is_active=True)
        db.add(paid_plan)
        db.commit()
        plan_id = paid_plan.id
    order = {"id": "order_saas_test", "amount": 10000, "currency": "INR"}
    payment = {"id": "pay_saas_test", "order_id": order["id"], "amount": 10000,
               "currency": "INR", "status": "captured"}
    provider = SimpleNamespace(order=SimpleNamespace(create=lambda _: order, fetch=lambda _: order),
                               payment=SimpleNamespace(fetch=lambda _: payment),
                               utility=SimpleNamespace(verify_payment_signature=lambda _: None))
    monkeypatch.setattr(settings, "SAAS_RAZORPAY_KEY_ID", "test_public")
    monkeypatch.setattr(settings, "SAAS_RAZORPAY_KEY_SECRET", "test_secret")
    monkeypatch.setattr(saas_billing_service, "_client", lambda: provider)
    monkeypatch.setattr(saas_billing, "_client", lambda: provider)
    a = _token(client, "school-a")
    b = _token(client, "school-b")
    assert client.get("/api/saas/subscription", headers=a).json()["plan_name"] == "Default"
    checkout = client.post("/api/saas/checkout", headers=a, json={"plan_id": plan_id})
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["amount"] == 10000
    assert client.post("/api/saas/checkout", headers=a, json={"plan_id": plan_id}).json()["invoice_id"] == checkout.json()["invoice_id"]
    verify_body = {"razorpay_order_id": order["id"], "razorpay_payment_id": payment["id"],
                   "razorpay_signature": "test_signature"}
    assert client.post("/api/saas/verify", headers=b, json=verify_body).status_code == 404
    payment["amount"] = 9999
    assert client.post("/api/saas/verify", headers=a, json=verify_body).status_code == 409
    payment["amount"] = 10000
    first = client.post("/api/saas/verify", headers=a, json=verify_body)
    second = client.post("/api/saas/verify", headers=a, json=verify_body)
    assert first.status_code == second.status_code == 200
    assert first.json()["payment_id"] == second.json()["payment_id"]
    with factory() as db:
        assert db.query(SaasPayment).count() == 1
        assert db.query(SaasInvoice).filter(SaasInvoice.tenant_id == ids["a"]).one().status == "PAID"
        assert db.query(Subscription).filter(Subscription.tenant_id == ids["a"]).one().plan_id == plan_id


def test_saas_webhook_signature_and_event_id_are_enforced(schools, monkeypatch):
    client, factory, ids = schools
    with factory() as db:
        plan = Plan(name="Webhook Paid", price=50, billing_interval="MONTHLY", trial_days=0,
                    features=["attendance"], is_active=True)
        db.add(plan)
        db.commit()
        plan_id = plan.id
    order = {"id": "order_webhook_test", "amount": 5000, "currency": "INR"}
    payment = {"id": "pay_webhook_test", "order_id": order["id"], "amount": 5000,
               "currency": "INR", "status": "captured"}
    provider = SimpleNamespace(order=SimpleNamespace(create=lambda _: order, fetch=lambda _: order),
                               payment=SimpleNamespace(fetch=lambda _: payment))
    monkeypatch.setattr(settings, "SAAS_RAZORPAY_KEY_ID", "test_public")
    monkeypatch.setattr(settings, "SAAS_RAZORPAY_KEY_SECRET", "test_secret")
    monkeypatch.setattr(settings, "SAAS_RAZORPAY_WEBHOOK_SECRET", "webhook_secret")
    monkeypatch.setattr(saas_billing_service, "_client", lambda: provider)
    assert client.post("/api/saas/checkout", headers=_token(client, "school-a"),
                       json={"plan_id": plan_id}).status_code == 200
    failed_body = json.dumps({"event": "payment.failed", "payload": {"payment": {"entity": payment}}}).encode()
    failed_signature = hmac.new(b"webhook_secret", failed_body, hashlib.sha256).hexdigest()
    failed = client.post("/api/saas/webhooks/razorpay", content=failed_body, headers={
        "x-razorpay-event-id": "evt_saas_failed", "x-razorpay-signature": failed_signature,
        "content-type": "application/json"})
    assert failed.status_code == 200
    with factory() as db:
        assert db.query(SaasInvoice).one().status == "PENDING"
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": payment}}}).encode()
    signature = hmac.new(b"webhook_secret", body, hashlib.sha256).hexdigest()
    headers = {"x-razorpay-event-id": "evt_saas_1", "x-razorpay-signature": signature,
               "content-type": "application/json"}
    assert client.post("/api/saas/webhooks/razorpay", content=body, headers={**headers, "x-razorpay-signature": "bad"}).status_code == 401
    first = client.post("/api/saas/webhooks/razorpay", content=body, headers=headers)
    second = client.post("/api/saas/webhooks/razorpay", content=body, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"
    with factory() as db:
        assert db.query(SaasProviderEvent).count() == 2
        assert db.query(SaasPayment).count() == 1
        assert db.query(Fee).count() == 2
