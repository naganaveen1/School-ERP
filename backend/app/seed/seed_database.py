import os
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from backend.app.database import SessionLocal, init_db, engine
from backend.app.models import (
    Role, Tenant, Plan, Subscription, User, Principal, Teacher, Parent, Student, Department,
    AcademicYear, ClassModel, Section, Subject, Enrollment, Timetable,
    Attendance, Assignment, Submission, StudyMaterial, Exam, Result,
    Fee, Payment, Notice, Notification, Event, Message, Complaint, AuditLog
)
from backend.app.utils.security import get_password_hash
from backend.app.utils.helpers import calculate_grade, calculate_percentage
from backend.app.seed.demo_data import DEMO_USERS, DEMO_DEPARTMENTS, DEMO_ROLES

def seed_database():
    print("Initializing database tables...")
    init_db()
    db: Session = SessionLocal()

    try:
        # Check if already seeded
        if db.query(User).filter(User.username == "admin").first():
            print("Database already contains seed data. Skipping seed.")
            return

        tenant = Tenant(name="Demo School", slug="demo-school", status="ACTIVE")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        db.info["tenant_scope"] = "tenant"
        db.info["tenant_id"] = tenant.id
        legacy_plan = db.query(Plan).filter(Plan.name == "Legacy").first()
        if legacy_plan is None:
            legacy_plan = Plan(name="Legacy", description="Development demo entitlement",
                               price=0, billing_interval="MONTHLY", trial_days=0,
                               features=["attendance", "assignments", "exams", "finance",
                                         "messaging", "reports", "documents", "advanced_reports"],
                               is_active=False)
            db.add(legacy_plan)
            db.flush()
        db.add(Subscription(tenant_id=tenant.id, plan_id=legacy_plan.id, status="ACTIVE"))
        db.commit()

        print("Seeding Roles...")
        for r in DEMO_ROLES:
            db.add(Role(name=r["name"], description=r["description"]))
        db.commit()

        print("Seeding Academic Year...")
        ay = AcademicYear(
            name="2025-2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=True
        )
        db.add(ay)
        db.commit()
        db.refresh(ay)

        print("Seeding Departments...")
        depts = {}
        for d in DEMO_DEPARTMENTS:
            dept = Department(name=d["name"], code=d["code"], description=d["description"])
            db.add(dept)
            db.commit()
            db.refresh(dept)
            depts[d["code"]] = dept

        print("Seeding Classes and Sections...")
        cls10 = ClassModel(name="Grade 10", grade_level=10, department_id=depts["SCI"].id, academic_year_id=ay.id)
        cls11 = ClassModel(name="Grade 11", grade_level=11, department_id=depts["SCI"].id, academic_year_id=ay.id)
        db.add_all([cls10, cls11])
        db.commit()
        db.refresh(cls10)
        db.refresh(cls11)

        sec10a = Section(name="A", class_id=cls10.id, room_number="Room 101")
        sec10b = Section(name="B", class_id=cls10.id, room_number="Room 102")
        sec11a = Section(name="A", class_id=cls11.id, room_number="Room 201")
        db.add_all([sec10a, sec10b, sec11a])
        db.commit()
        db.refresh(sec10a)
        db.refresh(sec10b)
        db.refresh(sec11a)

        print("Seeding Users & Profiles...")
        # 1. Admin
        admin_u = User(
            username="admin",
            email="admin@schoolerp.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="System Administrator",
            role="SCHOOL_ADMIN",
            phone="+1-555-0100",
            is_active=True
        )
        db.add(admin_u)

        # 2. Principal
        prin_u = User(
            username="principal",
            email="principal@schoolerp.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="Dr. Eleanor Vance",
            role="PRINCIPAL",
            phone="+1-555-0101",
            is_active=True
        )
        db.add(prin_u)
        db.commit()
        db.refresh(prin_u)

        prin_prof = Principal(
            user_id=prin_u.id,
            employee_id="PRN001",
            qualification="Ph.D. in Educational Leadership",
            joining_date=date(2020, 1, 15)
        )
        db.add(prin_prof)

        # 3. Teachers
        teacher1_u = User(
            username="teacher",
            email="teacher@schoolerp.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="Sarah Connor",
            role="TEACHER",
            phone="+1-555-0102",
            is_active=True
        )
        teacher2_u = User(
            username="john_doe",
            email="john.doe@schoolerp.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="John Doe",
            role="TEACHER",
            phone="+1-555-0103",
            is_active=True
        )
        db.add_all([teacher1_u, teacher2_u])
        db.commit()
        db.refresh(teacher1_u)
        db.refresh(teacher2_u)

        tch1 = Teacher(
            user_id=teacher1_u.id,
            employee_id="TCH001",
            department_id=depts["MATH"].id,
            qualification="M.Sc. Mathematics",
            designation="Senior Math Faculty",
            joining_date=date(2021, 8, 1),
            phone="+1-555-0102",
            address="124 Elm Street, Cityville"
        )
        tch2 = Teacher(
            user_id=teacher2_u.id,
            employee_id="TCH002",
            department_id=depts["SCI"].id,
            qualification="M.Sc. Physics",
            designation="Physics Lecturer",
            joining_date=date(2022, 1, 10),
            phone="+1-555-0103",
            address="456 Oak Avenue, Cityville"
        )
        db.add_all([tch1, tch2])
        db.commit()
        db.refresh(tch1)
        db.refresh(tch2)

        # Assign class teacher
        sec10a.class_teacher_id = tch1.id
        sec10b.class_teacher_id = tch2.id
        db.commit()

        # Subjects
        subj_math = Subject(name="Mathematics", code="MATH10", class_id=cls10.id, teacher_id=tch1.id)
        subj_phy = Subject(name="Physics", code="PHY10", class_id=cls10.id, teacher_id=tch2.id)
        subj_eng = Subject(name="English Literature", code="ENG10", class_id=cls10.id, teacher_id=tch1.id)
        db.add_all([subj_math, subj_phy, subj_eng])
        db.commit()
        db.refresh(subj_math)
        db.refresh(subj_phy)
        db.refresh(subj_eng)

        # 4. Parents
        parent_u = User(
            username="parent",
            email="parent@schoolerp.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="Robert Smith",
            role="PARENT",
            phone="+1-555-0104",
            is_active=True
        )
        db.add(parent_u)
        db.commit()
        db.refresh(parent_u)

        parent_prof = Parent(
            user_id=parent_u.id,
            occupation="Software Architect",
            relation_type="Father",
            address="789 Pine Road, Cityville",
            emergency_contact="+1-555-0199"
        )
        db.add(parent_prof)
        db.commit()
        db.refresh(parent_prof)

        # 5. Students
        student1_u = User(
            username="student",
            email="student@schoolerp.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="Alice Smith",
            role="STUDENT",
            phone="+1-555-0105",
            is_active=True
        )
        student2_u = User(
            username="bob_johnson",
            email="bob@schoolerp.com",
            hashed_password=get_password_hash("Password123!"),
            full_name="Bob Johnson",
            role="STUDENT",
            phone="+1-555-0106",
            is_active=True
        )
        db.add_all([student1_u, student2_u])
        db.commit()
        db.refresh(student1_u)
        db.refresh(student2_u)

        stud1 = Student(
            user_id=student1_u.id,
            admission_number="ADM2025001",
            roll_number="101",
            class_id=cls10.id,
            section_id=sec10a.id,
            parent_id=parent_prof.id,
            date_of_birth=date(2009, 5, 14),
            gender="Female",
            blood_group="O+",
            admission_date=date(2025, 9, 1),
            address="789 Pine Road, Cityville"
        )
        stud2 = Student(
            user_id=student2_u.id,
            admission_number="ADM2025002",
            roll_number="102",
            class_id=cls10.id,
            section_id=sec10a.id,
            parent_id=parent_prof.id,
            date_of_birth=date(2009, 8, 22),
            gender="Male",
            blood_group="A+",
            admission_date=date(2025, 9, 1),
            address="321 Maple Lane, Cityville"
        )
        db.add_all([stud1, stud2])
        db.commit()
        db.refresh(stud1)
        db.refresh(stud2)

        # Enrollments
        enr1 = Enrollment(student_id=stud1.id, class_id=cls10.id, section_id=sec10a.id, academic_year_id=ay.id, enrollment_date=date(2025, 9, 1))
        enr2 = Enrollment(student_id=stud2.id, class_id=cls10.id, section_id=sec10a.id, academic_year_id=ay.id, enrollment_date=date(2025, 9, 1))
        db.add_all([enr1, enr2])
        db.commit()

        print("Seeding Timetable...")
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for d in days:
            db.add(Timetable(
                class_id=cls10.id, section_id=sec10a.id, subject_id=subj_math.id,
                teacher_id=tch1.id, day_of_week=d, start_time="09:00", end_time="10:00", room_number="101"
            ))
            db.add(Timetable(
                class_id=cls10.id, section_id=sec10a.id, subject_id=subj_phy.id,
                teacher_id=tch2.id, day_of_week=d, start_time="10:15", end_time="11:15", room_number="Lab 1"
            ))
            db.add(Timetable(
                class_id=cls10.id, section_id=sec10a.id, subject_id=subj_eng.id,
                teacher_id=tch1.id, day_of_week=d, start_time="11:30", end_time="12:30", room_number="101"
            ))
        db.commit()

        print("Seeding Attendance records...")
        today = date.today()
        for i in range(5, 0, -1):
            att_d = today - timedelta(days=i)
            # Monday-Friday only (weekday < 5)
            if att_d.weekday() < 5:
                db.add(Attendance(
                    student_id=stud1.id, class_id=cls10.id, section_id=sec10a.id,
                    date=att_d, status="Present", remarks="On time", recorded_by=teacher1_u.id
                ))
                db.add(Attendance(
                    student_id=stud2.id, class_id=cls10.id, section_id=sec10a.id,
                    date=att_d, status="Present" if i != 2 else "Late", remarks="Traffic delay" if i == 2 else "On time", recorded_by=teacher1_u.id
                ))
        db.commit()

        print("Seeding Assignments & Submissions...")
        asgn1 = Assignment(
            title="Quadratic Equations & Polynomials",
            description="Complete exercise 4.2 questions 1 to 10 from textbook.",
            class_id=cls10.id,
            section_id=sec10a.id,
            subject_id=subj_math.id,
            teacher_id=tch1.id,
            due_date=datetime.now() + timedelta(days=5),
            max_marks=50.0
        )
        asgn2 = Assignment(
            title="Newton's Laws of Motion Lab Report",
            description="Submit experimental observations on friction and acceleration.",
            class_id=cls10.id,
            section_id=sec10a.id,
            subject_id=subj_phy.id,
            teacher_id=tch2.id,
            due_date=datetime.now() + timedelta(days=7),
            max_marks=100.0
        )
        db.add_all([asgn1, asgn2])
        db.commit()
        db.refresh(asgn1)
        db.refresh(asgn2)

        # Alice submitted assignment 1
        sub1 = Submission(
            assignment_id=asgn1.id,
            student_id=stud1.id,
            file_path="assignments/demo_submission_alice.pdf",
            marks_obtained=48.0,
            feedback="Excellent work on question 7!",
            status="graded"
        )
        db.add(sub1)
        db.commit()

        print("Seeding Study Materials...")
        sm1 = StudyMaterial(
            title="Mathematics Chapter 4 Formula Sheet",
            description="Complete summary of algebraic equations and quadratic formula.",
            class_id=cls10.id,
            subject_id=subj_math.id,
            teacher_id=tch1.id,
            file_path="study-materials/math_ch4_summary.pdf",
            file_type="pdf",
            file_size=1024 * 350
        )
        db.add(sm1)
        db.commit()

        print("Seeding Exams & Results...")
        exam = Exam(
            name="Term 1 Mid-Session Examination",
            exam_type="Midterm",
            academic_year_id=ay.id,
            class_id=cls10.id,
            start_date=today - timedelta(days=20),
            end_date=today - timedelta(days=15),
            is_published=True
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        res1 = Result(
            exam_id=exam.id, student_id=stud1.id, subject_id=subj_math.id,
            marks_obtained=95.0, max_marks=100.0, grade="A+", remarks="Outstanding performance"
        )
        res2 = Result(
            exam_id=exam.id, student_id=stud1.id, subject_id=subj_phy.id,
            marks_obtained=88.0, max_marks=100.0, grade="A", remarks="Very good understanding"
        )
        res3 = Result(
            exam_id=exam.id, student_id=stud2.id, subject_id=subj_math.id,
            marks_obtained=78.0, max_marks=100.0, grade="B", remarks="Consistent effort"
        )
        res4 = Result(
            exam_id=exam.id, student_id=stud2.id, subject_id=subj_phy.id,
            marks_obtained=82.0, max_marks=100.0, grade="A", remarks="Great lab skills"
        )
        db.add_all([res1, res2, res3, res4])
        db.commit()

        print("Seeding Fees and Payments...")
        fee1 = Fee(
            title="Annual Academic Tuition Fee",
            fee_type="Tuition",
            class_id=cls10.id,
            academic_year_id=ay.id,
            amount=1200.0,
            due_date=today + timedelta(days=30),
            description="Standard tuition covering terms 1 & 2"
        )
        fee2 = Fee(
            title="Science Laboratory Fee",
            fee_type="Laboratory",
            class_id=cls10.id,
            academic_year_id=ay.id,
            amount=150.0,
            due_date=today + timedelta(days=15),
            description="Lab consumables and equipment maintenance"
        )
        db.add_all([fee1, fee2])
        db.commit()
        db.refresh(fee1)
        db.refresh(fee2)

        pay1 = Payment(
            fee_id=fee1.id,
            student_id=stud1.id,
            amount_paid=1200.0,
            payment_date=today - timedelta(days=10),
            payment_method="Bank Transfer",
            payment_status="PAID",
            transaction_id="TXN-2025-00129",
            remarks="Full tuition paid"
        )
        db.add(pay1)
        db.commit()

        print("Seeding Notices...")
        n1 = Notice(
            title="Welcome to Academic Session 2025-2026",
            content="We warmly welcome all new and returning students and faculty to an exciting academic year ahead.",
            target_role="ALL",
            published_by=prin_u.id,
            is_published=True
        )
        n2 = Notice(
            title="Faculty Development and Department Meeting",
            content="All department heads and teaching staff are requested to attend the faculty alignment meeting this Friday at 3:30 PM.",
            target_role="TEACHER",
            published_by=prin_u.id,
            is_published=True
        )
        n3 = Notice(
            title="Annual Parent-Teacher Conference (PTC)",
            content="PTC meetings will be conducted next Saturday. Slots can be booked through the parent portal.",
            target_role="PARENT",
            published_by=admin_u.id,
            is_published=True
        )
        n4 = Notice(
            title="Inter-School Science Olympiad Registration",
            content="Interested Grade 10 and 11 students can register with their Physics or Math teacher before the end of the week.",
            target_role="STUDENT",
            published_by=teacher1_u.id,
            is_published=True
        )
        db.add_all([n1, n2, n3, n4])
        db.commit()

        print("Seeding Events...")
        ev1 = Event(
            title="Annual Science & Innovation Exhibition",
            description="Showcase of student physics, chemistry, and computing projects.",
            start_time=datetime.now() + timedelta(days=14, hours=9),
            end_time=datetime.now() + timedelta(days=14, hours=16),
            location="Main Auditorium & Science Quad",
            target_audience="ALL",
            created_by=admin_u.id
        )
        ev2 = Event(
            title="Annual Athletics Meet 2025",
            description="Track and field events for all grades.",
            start_time=datetime.now() + timedelta(days=25, hours=8),
            end_time=datetime.now() + timedelta(days=25, hours=15),
            location="School Sports Ground",
            target_audience="ALL",
            created_by=admin_u.id
        )
        db.add_all([ev1, ev2])
        db.commit()

        print("Seeding Audit Log...")
        db.add(AuditLog(
            user_id=admin_u.id,
            action="SYSTEM_INITIALIZED",
            entity="Database",
            details="Demo seed data populated successfully",
            ip_address="127.0.0.1"
        ))
        db.commit()

        print("Database seeded successfully with all demo accounts and records!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
