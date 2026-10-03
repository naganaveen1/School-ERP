import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from backend.app.database import SessionLocal
from backend.app.models import (
    User, Student, Fee, Payment, Attendance, Submission, Result, Enrollment, Leave
)

def clear_demo_data():
    db = SessionLocal()
    try:
        print("Wiping demo payments...")
        db.query(Payment).delete(synchronize_session=False)

        print("Wiping demo fees...")
        db.query(Fee).delete(synchronize_session=False)

        print("Wiping demo submissions & results...")
        db.query(Submission).delete(synchronize_session=False)
        db.query(Result).delete(synchronize_session=False)

        print("Wiping demo attendance & leave records...")
        db.query(Attendance).delete(synchronize_session=False)
        db.query(Leave).delete(synchronize_session=False)

        print("Wiping demo enrollments...")
        db.query(Enrollment).delete(synchronize_session=False)

        print("Wiping demo students & student user accounts...")
        student_users = db.query(User).filter(User.role == "STUDENT").all()
        for u in student_users:
            if u.student_profile:
                db.delete(u.student_profile)
            db.delete(u)

        db.commit()
        print("Successfully cleared all demo student, fee, and payment data from database!")
    except Exception as e:
        db.rollback()
        print(f"Error clearing demo data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    clear_demo_data()
