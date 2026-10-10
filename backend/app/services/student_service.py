from typing import Optional
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from backend.app.models.user import User
from backend.app.models.student import Student
from backend.app.models.enrollment import Enrollment
from backend.app.models.academic_year import AcademicYear
from backend.app.schemas.student import StudentCreate, StudentUpdate
from backend.app.services.auth_service import auth_service
from backend.app.schemas.user import UserCreate
from backend.app.services.entitlement_service import entitlement_service

class StudentService:
    @staticmethod
    def create_student(db: Session, student_in: StudentCreate) -> Student:
        entitlement_service.check_usage(db, "students")
        # Check admission number uniqueness
        if db.query(Student).filter(Student.admission_number == student_in.admission_number).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student with admission number '{student_in.admission_number}' already exists"
            )

        # Create user account
        user_create = UserCreate(
            username=student_in.username,
            email=student_in.email,
            password=student_in.password,
            full_name=student_in.full_name,
            role="STUDENT",
            phone=student_in.phone,
            is_active=True
        )
        user = auth_service.create_user(db, user_create)

        student = Student(
            user_id=user.id,
            admission_number=student_in.admission_number,
            roll_number=student_in.roll_number,
            class_id=student_in.class_id,
            section_id=student_in.section_id,
            parent_id=student_in.parent_id,
            date_of_birth=student_in.date_of_birth,
            gender=student_in.gender,
            blood_group=student_in.blood_group,
            admission_date=student_in.admission_date,
            address=student_in.address
        )
        db.add(student)
        db.commit()
        db.refresh(student)

        # Create enrollment if class is assigned
        if student.class_id:
            current_ay = db.query(AcademicYear).filter(AcademicYear.is_current == True).first()
            if not current_ay:
                current_ay = db.query(AcademicYear).first()
            if current_ay:
                enrollment = Enrollment(
                    student_id=student.id,
                    class_id=student.class_id,
                    section_id=student.section_id,
                    academic_year_id=current_ay.id,
                    enrollment_date=student.admission_date or student.created_at.date(),
                    status="active"
                )
                db.add(enrollment)
                db.commit()

        return student

    @staticmethod
    def get_student_by_id(db: Session, student_id: int) -> Optional[Student]:
        return db.query(Student).options(
            joinedload(Student.user),
            joinedload(Student.class_obj),
            joinedload(Student.section),
            joinedload(Student.parent).joinedload(Student.parent.property.mapper.class_.user)
        ).filter(Student.id == student_id).first()

    @staticmethod
    def get_student_by_user_id(db: Session, user_id: int) -> Optional[Student]:
        return db.query(Student).filter(Student.user_id == user_id).first()

    @staticmethod
    def update_student(db: Session, student_id: int, student_in: StudentUpdate) -> Student:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )

        user = student.user
        if student_in.full_name is not None:
            user.full_name = student_in.full_name
        if student_in.email is not None:
            user.email = student_in.email
        if student_in.phone is not None:
            user.phone = student_in.phone

        if student_in.admission_number is not None:
            student.admission_number = student_in.admission_number
        if student_in.roll_number is not None:
            student.roll_number = student_in.roll_number
        if student_in.class_id is not None:
            student.class_id = student_in.class_id
        if student_in.section_id is not None:
            student.section_id = student_in.section_id
        if student_in.parent_id is not None:
            student.parent_id = student_in.parent_id
        if student_in.date_of_birth is not None:
            student.date_of_birth = student_in.date_of_birth
        if student_in.gender is not None:
            student.gender = student_in.gender
        if student_in.blood_group is not None:
            student.blood_group = student_in.blood_group
        if student_in.address is not None:
            student.address = student_in.address

        db.commit()
        db.refresh(student)
        return student

    @staticmethod
    def delete_student(db: Session, student_id: int) -> bool:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        user = student.user
        db.delete(student)
        if user:
            db.delete(user)
        db.commit()
        return True

student_service = StudentService()
