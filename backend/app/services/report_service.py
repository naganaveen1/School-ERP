from datetime import date
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.user import User
from backend.app.models.student import Student
from backend.app.models.teacher import Teacher
from backend.app.models.parent import Parent
from backend.app.models.class_model import ClassModel
from backend.app.models.academic_year import AcademicYear
from backend.app.models.attendance import Attendance
from backend.app.models.fee import Fee
from backend.app.models.payment import Payment
from backend.app.models.notice import Notice
from backend.app.models.audit_log import AuditLog
from backend.app.models.assignment import Assignment
from backend.app.models.submission import Submission
from backend.app.models.exam import Exam
from backend.app.models.result import Result
from backend.app.models.leave import Leave
from backend.app.models.complaint import Complaint
from backend.app.models.timetable import Timetable
from backend.app.services.attendance_service import attendance_service
from backend.app.services.fee_service import fee_service

class ReportService:
    @staticmethod
    def get_admin_dashboard(db: Session) -> Dict[str, Any]:
        total_students = db.query(Student).count()
        total_teachers = db.query(Teacher).count()
        total_parents = db.query(Parent).count()
        total_classes = db.query(ClassModel).count()

        # Fee collections
        total_fees = db.query(func.sum(Fee.amount)).scalar() or 0.0
        total_collected = db.query(func.sum(Payment.amount_paid)).scalar() or 0.0

        # Today attendance
        today = date.today()
        today_att = db.query(Attendance).filter(Attendance.date == today).all()
        att_present = sum(1 for a in today_att if a.status.lower() == "present")
        att_absent = sum(1 for a in today_att if a.status.lower() == "absent")
        att_total = len(today_att)

        recent_notices = db.query(Notice).order_by(Notice.publish_date.desc()).limit(5).all()
        recent_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
        active_year = db.query(AcademicYear).filter(AcademicYear.is_current.is_(True)).first()

        return {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_parents": total_parents,
            "total_classes": total_classes,
            "academic_year": active_year.name if active_year else None,
            "total_fees_expected": round(float(total_fees), 2),
            "total_fees_collected": round(float(total_collected), 2),
            "today_attendance": {
                "total": att_total,
                "present": att_present,
                "absent": att_absent,
                "percentage": round(att_present / att_total * 100, 2) if att_total > 0 else 0.0
            },
            "recent_notices": [
                {"id": n.id, "title": n.title, "target_role": n.target_role, "publish_date": str(n.publish_date)}
                for n in recent_notices
            ],
            "recent_activities": [
                {"id": l.id, "action": l.action, "entity": l.entity, "details": l.details, "timestamp": str(l.timestamp)}
                for l in recent_logs
            ]
        }

    @staticmethod
    def get_principal_dashboard(db: Session) -> Dict[str, Any]:
        total_students = db.query(Student).count()
        total_teachers = db.query(Teacher).count()
        pending_leaves = db.query(Leave).filter(Leave.status == "PENDING").count()
        pending_complaints = db.query(Complaint).filter(Complaint.status == "PENDING").count()
        
        # Overall exam average
        avg_marks = db.query(func.avg(Result.marks_obtained)).scalar() or 0.0

        recent_leaves = db.query(Leave).order_by(Leave.created_at.desc()).limit(5).all()
        recent_complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).limit(5).all()

        return {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "pending_leaves": pending_leaves,
            "pending_complaints": pending_complaints,
            "average_marks": round(float(avg_marks), 2),
            "recent_leaves": [
                {"id": l.id, "user": l.user.full_name if l.user else "", "role": l.applicant_role, "type": l.leave_type, "status": l.status}
                for l in recent_leaves
            ],
            "recent_complaints": [
                {"id": c.id, "user": c.user.full_name if c.user else "", "title": c.title, "status": c.status}
                for c in recent_complaints
            ]
        }

    @staticmethod
    def get_teacher_dashboard(db: Session, teacher_id: int) -> Dict[str, Any]:
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if not teacher:
            return {}

        assigned_subjects = teacher.subjects
        class_ids = list(set([s.class_id for s in assigned_subjects]))
        
        total_students = db.query(Student).filter(Student.class_id.in_(class_ids)).count() if class_ids else 0
        total_assignments = db.query(Assignment).filter(Assignment.teacher_id == teacher.id).count()

        # Pending submissions to grade
        sub_count = db.query(Submission).join(Assignment).filter(
            Assignment.teacher_id == teacher.id,
            Submission.status == "submitted"
        ).count()

        # Timetable for teacher
        timetable_entries = db.query(Timetable).filter(Timetable.teacher_id == teacher.id).all()

        return {
            "teacher_name": teacher.user.full_name if teacher.user else "",
            "department": teacher.department.name if teacher.department else "General",
            "assigned_classes_count": len(class_ids),
            "total_students": total_students,
            "total_assignments": total_assignments,
            "pending_grading": sub_count,
            "timetable_count": len(timetable_entries)
        }

    @staticmethod
    def get_student_dashboard(db: Session, student_id: int) -> Dict[str, Any]:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {}

        att_stats = attendance_service.get_student_stats(db, student.id)
        fee_summary = fee_service.get_student_fee_summary(db, student.id)

        # Assignments
        assignments = db.query(Assignment).filter(
            Assignment.class_id == student.class_id
        ).order_by(Assignment.due_date.asc()).limit(5).all()

        # Results
        results = db.query(Result).filter(
            Result.student_id == student.id
        ).order_by(Result.created_at.desc()).limit(5).all()

        # Notices
        notices = db.query(Notice).filter(
            (Notice.target_role == "ALL") | (Notice.target_role == "STUDENT"),
            Notice.is_published == True
        ).order_by(Notice.publish_date.desc()).limit(5).all()

        return {
            "student_name": student.user.full_name if student.user else "",
            "admission_number": student.admission_number,
            "class_name": student.class_obj.name if student.class_obj else "N/A",
            "section_name": student.section.name if student.section else "N/A",
            "attendance": {
                "total": att_stats.total_days,
                "present": att_stats.present_days,
                "percentage": att_stats.percentage
            },
            "fees": {
                "total": fee_summary.total_fees,
                "paid": fee_summary.total_paid,
                "balance": fee_summary.remaining_balance
            },
            "upcoming_assignments": [
                {"id": a.id, "title": a.title, "due_date": str(a.due_date), "subject": a.subject.name if a.subject else ""}
                for a in assignments
            ],
            "recent_results": [
                {"id": r.id, "subject": r.subject.name if r.subject else "", "marks": r.marks_obtained, "max": r.max_marks, "grade": r.grade}
                for r in results
            ],
            "notices": [
                {"id": n.id, "title": n.title, "date": str(n.publish_date)}
                for n in notices
            ]
        }

    @staticmethod
    def get_parent_dashboard(db: Session, parent_id: int) -> Dict[str, Any]:
        parent = db.query(Parent).filter(Parent.id == parent_id).first()
        if not parent:
            return {}

        children_data = []
        for child in parent.students:
            att = attendance_service.get_student_stats(db, child.id)
            fee = fee_service.get_student_fee_summary(db, child.id)
            children_data.append({
                "id": child.id,
                "name": child.user.full_name if child.user else "",
                "admission_number": child.admission_number,
                "class_name": child.class_obj.name if child.class_obj else "",
                "attendance_percentage": att.percentage,
                "fee_balance": fee.remaining_balance
            })

        notices = db.query(Notice).filter(
            (Notice.target_role == "ALL") | (Notice.target_role == "PARENT"),
            Notice.is_published == True
        ).order_by(Notice.publish_date.desc()).limit(5).all()

        return {
            "parent_name": parent.user.full_name if parent.user else "",
            "children": children_data,
            "notices": [{"id": n.id, "title": n.title, "date": str(n.publish_date)} for n in notices]
        }

report_service = ReportService()
