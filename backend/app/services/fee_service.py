from datetime import date
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.app.models.fee import Fee
from backend.app.models.payment import Payment
from backend.app.models.student import Student
from backend.app.schemas.fee import PaymentCreate, StudentFeeSummary, StudentFeeItem

class FeeService:
    @staticmethod
    def record_payment(db: Session, payment_in: PaymentCreate) -> Payment:
        fee = db.query(Fee).filter(Fee.id == payment_in.fee_id).first()
        if not fee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fee structure not found"
            )

        student = db.query(Student).filter(Student.id == payment_in.student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )

        payment = Payment(
            fee_id=payment_in.fee_id,
            student_id=payment_in.student_id,
            amount_paid=payment_in.amount_paid,
            discount_amount=payment_in.discount_amount or 0.0,
            payment_date=payment_in.payment_date or date.today(),
            payment_method=payment_in.payment_method,
            payment_status=payment_in.payment_status,
            transaction_id=payment_in.transaction_id,
            remarks=payment_in.remarks
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def get_student_fee_summary(db: Session, student_id: int) -> StudentFeeSummary:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )

        # Get all fees for this student's class or global fees (class_id IS NULL)
        fees = db.query(Fee).filter(
            (Fee.class_id == student.class_id) | (Fee.class_id == None)
        ).all()

        items: List[StudentFeeItem] = []
        total_fees = 0.0
        total_paid = 0.0

        for fee in fees:
            # Exclude CANCELLED, VOID, REFUNDED payments
            payments = db.query(Payment).filter(
                Payment.fee_id == fee.id,
                Payment.student_id == student_id,
                Payment.payment_status.in_(["PAID", "PARTIAL"])
            ).all()
            paid_amount = sum(p.amount_paid for p in payments)
            discount_amount = sum(p.discount_amount for p in payments)
            effective_paid = paid_amount + discount_amount
            balance = max(0.0, fee.amount - effective_paid)

            if effective_paid >= fee.amount:
                pay_status = "PAID"
            elif effective_paid > 0:
                pay_status = "PARTIAL"
            else:
                pay_status = "UNPAID"

            total_fees += fee.amount
            total_paid += paid_amount

            items.append(StudentFeeItem(
                fee_id=fee.id,
                title=fee.title,
                fee_type=fee.fee_type,
                total_amount=fee.amount,
                amount_paid=paid_amount,
                balance=balance,
                status=pay_status,
                due_date=fee.due_date
            ))

        return StudentFeeSummary(
            student_id=student.id,
            student_name=student.user.full_name if student.user else "",
            admission_number=student.admission_number,
            class_name=student.class_obj.name if student.class_obj else None,
            total_fees=round(total_fees, 2),
            total_paid=round(total_paid, 2),
            remaining_balance=round(sum(item.balance for item in items), 2),
            items=items
        )

    @staticmethod
    def void_payment(db: Session, payment_id: int, reason: str) -> Payment:
        from datetime import datetime
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found")

        payment.payment_status = "REFUNDED"
        payment.refund_reason = reason
        payment.refunded_at = datetime.now()
        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def rollover_academic_year(db: Session, from_year_id: int, to_year_id: int) -> dict:
        from backend.app.models.academic_year import AcademicYear
        from datetime import date

        from_year = db.query(AcademicYear).filter(AcademicYear.id == from_year_id).first()
        to_year = db.query(AcademicYear).filter(AcademicYear.id == to_year_id).first()

        if not from_year or not to_year:
            raise HTTPException(status_code=400, detail="Invalid academic year specified.")

        # Find all active students
        students = db.query(Student).all()
        carry_forward_count = 0
        total_carried_amount = 0.0

        for student in students:
            # Check balance in from_year
            summary = FeeService.get_student_fee_summary(db, student.id)
            if summary.remaining_balance > 0:
                # Create carry-forward fee in new academic year
                arrears_fee = Fee(
                    title=f"Arrears Carry Forward ({from_year.name})",
                    fee_type="Arrears",
                    class_id=student.class_id,
                    academic_year_id=to_year_id,
                    amount=summary.remaining_balance,
                    due_date=date.today(),
                    installment_name="Arrears Rollover",
                    installment_number=1,
                    description=f"Unpaid balance carried forward from Academic Year {from_year.name}"
                )
                db.add(arrears_fee)
                carry_forward_count += 1
                total_carried_amount += summary.remaining_balance

        from_year.is_active = False
        to_year.is_active = True
        db.commit()

        return {
            "message": f"Academic Year {from_year.name} closed successfully. Rolled over to {to_year.name}.",
            "students_carried_forward": carry_forward_count,
            "total_carried_amount": round(total_carried_amount, 2)
        }

    @staticmethod
    def get_daily_cash_register(db: Session, target_date: date) -> dict:
        payments = db.query(Payment).filter(Payment.payment_date == target_date).all()

        by_method = {"Cash": 0.0, "Online": 0.0, "Bank Transfer": 0.0, "Cheque": 0.0}
        total_collected = 0.0
        total_refunded = 0.0
        active_count = 0
        refunded_count = 0

        transaction_list = []

        for p in payments:
            if p.payment_status in ["REFUNDED", "CANCELLED", "VOID"]:
                total_refunded += p.amount_paid
                refunded_count += 1
            else:
                total_collected += p.amount_paid
                active_count += 1
                method = p.payment_method if p.payment_method in by_method else "Cash"
                by_method[method] += p.amount_paid

            transaction_list.append({
                "id": p.id,
                "student_name": p.student.user.full_name if p.student and p.student.user else "N/A",
                "admission_number": p.student.admission_number if p.student else "N/A",
                "amount": p.amount_paid,
                "discount": p.discount_amount,
                "method": p.payment_method,
                "status": p.payment_status,
                "transaction_id": p.transaction_id or f"REC-{p.id:06d}"
            })

        return {
            "date": str(target_date),
            "total_collections": round(total_collected, 2),
            "total_refunded": round(total_refunded, 2),
            "active_transactions": active_count,
            "refunded_transactions": refunded_count,
            "collections_by_method": by_method,
            "transactions": transaction_list
        }

fee_service = FeeService()
