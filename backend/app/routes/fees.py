from typing import List, Optional
from decimal import Decimal, ROUND_HALF_UP
import secrets
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.fee import Fee
from backend.app.models.payment import Payment
from backend.app.models.student import Student
from backend.app.config import settings
from backend.app.schemas.fee import (
    FeeCreate, FeeUpdate, FeeResponse,
    PaymentCreate, PaymentResponse, StudentFeeSummary,
    RazorpayCreateOrderRequest, RazorpayCreateOrderResponse, RazorpayVerifyRequest
)
from backend.app.services.fee_service import fee_service
from backend.app.utils.permissions import require_roles, get_current_active_user, require_feature
from backend.app.utils.helpers import log_audit_action
from backend.app.seed.import_vouchers import parse_excel_voucher_file, import_vouchers_to_db

router = APIRouter(prefix="/fees", tags=["Fees"], dependencies=[Depends(require_feature("finance"))])

def _payment_context(db: Session, user: User, fee_id: int, student_id: int):
    fee = db.query(Fee).filter(Fee.id == fee_id).first()
    student = db.query(Student).filter(Student.id == student_id).first()
    if not fee or not student or (fee.class_id is not None and fee.class_id != student.class_id):
        raise HTTPException(status_code=404, detail="Fee or student not found")
    if user.role == "STUDENT":
        permitted = bool(user.student_profile and user.student_profile.id == student_id)
    elif user.role == "PARENT":
        permitted = bool(user.parent_profile and any(child.id == student_id for child in user.parent_profile.students))
    else:
        permitted = user.role == "SCHOOL_ADMIN"
    if not permitted:
        raise HTTPException(status_code=403, detail="Cannot pay for this student")
    return fee, student

def _razorpay_client():
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=503, detail="Online payments are not configured")
    import razorpay
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def _paise(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

@router.get("", response_model=List[FeeResponse])
def list_fees(
    class_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Fee).options(
        joinedload(Fee.class_obj),
        joinedload(Fee.academic_year)
    )
    if current_user.role == "STUDENT":
        student = current_user.student_profile
        if not student:
            return []
        query = query.filter((Fee.class_id == student.class_id) | Fee.class_id.is_(None))
    elif current_user.role == "PARENT":
        parent = current_user.parent_profile
        if not parent:
            return []
        class_ids = {child.class_id for child in parent.students if child.class_id}
        query = query.filter((Fee.class_id.in_(class_ids)) | Fee.class_id.is_(None))
    elif current_user.role not in {"SCHOOL_ADMIN", "PRINCIPAL"}:
        raise HTTPException(status_code=403, detail="Cannot view fees")
    if class_id:
        query = query.filter((Fee.class_id == class_id) | (Fee.class_id == None))

    fees = query.order_by(Fee.due_date.desc()).all()
    return [
        FeeResponse(
            id=f.id,
            title=f.title,
            fee_type=f.fee_type,
            class_id=f.class_id,
            academic_year_id=f.academic_year_id,
            amount=f.amount,
            due_date=f.due_date,
            description=f.description,
            class_name=f.class_obj.name if f.class_obj else "All Classes",
            academic_year_name=f.academic_year.name if f.academic_year else None,
            created_at=f.created_at
        )
        for f in fees
    ]

@router.post("", response_model=FeeResponse)
def create_fee(
    fee_in: FeeCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    fee = Fee(
        title=fee_in.title,
        fee_type=fee_in.fee_type,
        class_id=fee_in.class_id,
        academic_year_id=fee_in.academic_year_id,
        amount=fee_in.amount,
        due_date=fee_in.due_date,
        description=fee_in.description
    )
    db.add(fee)
    db.commit()
    db.refresh(fee)

    log_audit_action(db, "FEE_CREATE", "Fee", str(fee.id), f"Created fee {fee.title} ({fee.amount})", current_user.id)

    return FeeResponse(
        id=fee.id,
        title=fee.title,
        fee_type=fee.fee_type,
        class_id=fee.class_id,
        academic_year_id=fee.academic_year_id,
        amount=fee.amount,
        due_date=fee.due_date,
        description=fee.description,
        created_at=fee.created_at
    )

@router.delete("/{fee_id}")
def delete_fee(
    fee_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    fee = db.query(Fee).filter(Fee.id == fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee structure not found")
    db.delete(fee)
    db.commit()
    log_audit_action(db, "FEE_DELETE", "Fee", str(fee_id), "Deleted fee structure", current_user.id)
    return {"message": "Fee structure deleted successfully"}

# Payments
@router.post("/payments", response_model=PaymentResponse)
def record_payment(
    payment_in: PaymentCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    payment = fee_service.record_payment(db, payment_in)
    log_audit_action(db, "PAYMENT_RECORD", "Payment", str(payment.id), f"Payment of {payment.amount_paid} recorded for student {payment.student_id}", current_user.id)

    return PaymentResponse(
        id=payment.id,
        fee_id=payment.fee_id,
        student_id=payment.student_id,
        amount_paid=payment.amount_paid,
        discount_amount=payment.discount_amount,
        payment_date=payment.payment_date,
        payment_method=payment.payment_method,
        payment_status=payment.payment_status,
        reconciliation_status=payment.reconciliation_status,
        transaction_id=payment.transaction_id,
        remarks=payment.remarks,
        fee_title=payment.fee.title if payment.fee else None,
        student_name=payment.student.user.full_name if payment.student and payment.student.user else None,
        admission_number=payment.student.admission_number if payment.student else None,
        created_at=payment.created_at
    )

@router.get("/payments", response_model=List[PaymentResponse])
def list_payments(
    student_id: Optional[int] = None,
    fee_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Payment).options(
        joinedload(Payment.fee),
        joinedload(Payment.student).joinedload(Student.user)
    )

    if current_user.role == "STUDENT" and current_user.student_profile:
        query = query.filter(Payment.student_id == current_user.student_profile.id)
    elif current_user.role == "PARENT" and current_user.parent_profile:
        child_ids = [child.id for child in current_user.parent_profile.students]
        query = query.filter(Payment.student_id.in_(child_ids))
    elif current_user.role not in ("SCHOOL_ADMIN", "PRINCIPAL"):
        raise HTTPException(status_code=403, detail="Cannot view payments")

    if student_id:
        query = query.filter(Payment.student_id == student_id)

    if fee_id:
        query = query.filter(Payment.fee_id == fee_id)

    payments = query.order_by(Payment.payment_date.desc()).all()
    return [
        PaymentResponse(
            id=p.id,
            fee_id=p.fee_id,
            student_id=p.student_id,
            amount_paid=p.amount_paid,
            discount_amount=p.discount_amount,
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            payment_status=p.payment_status,
            reconciliation_status=p.reconciliation_status,
            transaction_id=p.transaction_id,
            remarks=p.remarks,
            fee_title=p.fee.title if p.fee else None,
            student_name=p.student.user.full_name if p.student and p.student.user else None,
            admission_number=p.student.admission_number if p.student else None,
            created_at=p.created_at
        )
        for p in payments
    ]

@router.get("/student/{student_id}", response_model=StudentFeeSummary)
def get_student_fee_summary(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "STUDENT":
        if not current_user.student_profile or current_user.student_profile.id != student_id:
            raise HTTPException(status_code=403, detail="Can only view your own fee status")
    elif current_user.role == "PARENT":
        parent = current_user.parent_profile
        if not parent or not any(s.id == student_id for s in parent.students):
            raise HTTPException(status_code=403, detail="Can only view your child's fee status")
    elif current_user.role not in ("SCHOOL_ADMIN", "PRINCIPAL"):
        raise HTTPException(status_code=403, detail="Cannot view fee status")

    return fee_service.get_student_fee_summary(db, student_id)

@router.post("/upload-vouchers")
async def upload_vouchers(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported.")
    
    contents = await file.read()
    try:
        records = parse_excel_voucher_file(contents)
        res = import_vouchers_to_db(db, records)
        log_audit_action(
            db, "FEE_VOUCHERS_IMPORT", "Payment", "BULK",
            f"Imported {res['payments_imported']} voucher payments totaling {res['total_amount']}",
            current_user.id
        )
        return {
            "message": "Voucher payments imported successfully",
            "unique_students": res["unique_students"],
            "payments_imported": res["payments_imported"],
            "total_amount": res["total_amount"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process Excel file: {str(e)}")

@router.get("/payments/{payment_id}/receipt")
def get_payment_receipt(
    payment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    payment = db.query(Payment).options(
        joinedload(Payment.fee),
        joinedload(Payment.student).joinedload(Student.user),
        joinedload(Payment.student).joinedload(Student.class_obj)
    ).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    if current_user.role == "STUDENT":
        permitted = bool(current_user.student_profile and payment.student_id == current_user.student_profile.id)
    elif current_user.role == "PARENT":
        permitted = bool(current_user.parent_profile and any(
            child.id == payment.student_id for child in current_user.parent_profile.students
        ))
    else:
        permitted = current_user.role in ("SCHOOL_ADMIN", "PRINCIPAL")
    if not permitted:
        raise HTTPException(status_code=403, detail="Access denied")

    fee_amount = payment.fee.amount if payment.fee else payment.amount_paid
    discount = payment.discount_amount or 0.0
    paid = payment.amount_paid
    balance = max(0.0, fee_amount - (paid + discount))

    return {
        "receipt_no": f"REC-{payment.id:06d}",
        "payment_id": payment.id,
        "payment_date": payment.payment_date,
        "student_name": payment.student.user.full_name if payment.student and payment.student.user else "N/A",
        "admission_number": payment.student.admission_number if payment.student else "N/A",
        "class_name": payment.student.class_obj.name if payment.student and payment.student.class_obj else "N/A",
        "fee_title": payment.fee.title if payment.fee else "General Fee",
        "fee_type": payment.fee.fee_type if payment.fee else "Tuition",
        "total_fee_amount": fee_amount,
        "discount_amount": discount,
        "amount_paid": paid,
        "balance_remaining": balance,
        "payment_method": payment.payment_method,
        "payment_status": payment.payment_status,
        "reconciliation_status": payment.reconciliation_status,
        "transaction_id": payment.transaction_id or f"TXN-{payment.id}",
        "remarks": payment.remarks or "Payment received with thanks."
    }

@router.post("/reconcile-bank-statement")
async def reconcile_bank_statement(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Only CSV bank statement files are supported.")

    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    import csv, io
    reader = csv.reader(io.StringIO(text))
    
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    reconciled_count = 0
    matched_amount = 0.0
    unmatched_rows = 0

    all_payments = db.query(Payment).all()
    # Map by transaction_id and amount
    tx_map = {p.transaction_id.strip().upper(): p for p in all_payments if p.transaction_id}

    for row in rows:
        row_str = " ".join(row).upper()
        matched = False

        # Try to find matching transaction_id in row
        for tx_id, payment in tx_map.items():
            if tx_id in row_str and payment.reconciliation_status != "RECONCILED":
                payment.reconciliation_status = "RECONCILED"
                reconciled_count += 1
                matched_amount += payment.amount_paid
                matched = True
                break

        if not matched:
            unmatched_rows += 1

    db.commit()

    log_audit_action(
        db, "BANK_RECONCILIATION", "Payment", "BULK",
        f"Reconciled {reconciled_count} payments totaling INR {matched_amount:,.2f}",
        current_user.id
    )

    return {
        "message": "Bank statement processed successfully.",
        "reconciled_count": reconciled_count,
        "matched_amount": matched_amount,
        "unmatched_rows": unmatched_rows
    }

@router.post("/payments/{payment_id}/void")
def void_payment(
    payment_id: int,
    reason: str = Query(..., description="Reason for voiding/refunding receipt"),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    payment = fee_service.void_payment(db, payment_id, reason)
    log_audit_action(
        db, "PAYMENT_REFUND", "Payment", str(payment_id),
        f"Voided payment REC-{payment.id:06d}. Reason: {reason}",
        current_user.id
    )
    return {
        "message": f"Payment REC-{payment.id:06d} successfully voided/refunded.",
        "payment_id": payment.id,
        "status": payment.payment_status,
        "refund_reason": payment.refund_reason
    }

@router.post("/academic-year-rollover")
def rollover_academic_year(
    from_year_id: int = Query(...),
    to_year_id: int = Query(...),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    res = fee_service.rollover_academic_year(db, from_year_id, to_year_id)
    log_audit_action(
        db, "ACADEMIC_YEAR_ROLLOVER", "AcademicYear", str(to_year_id),
        f"Rolled over from year {from_year_id} to year {to_year_id}. Carried forward {res['students_carried_forward']} students.",
        current_user.id
    )
    return res

@router.get("/daily-collection-register")
def get_daily_collection_register(
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    from datetime import datetime, date
    req_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()
    return fee_service.get_daily_cash_register(db, req_date)

@router.post("/razorpay/create-order", response_model=RazorpayCreateOrderResponse)
def create_razorpay_order(
    req: RazorpayCreateOrderRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    fee, student = _payment_context(db, current_user, req.fee_id, req.student_id)
    already_paid = sum(p.amount_paid + p.discount_amount for p in db.query(Payment).filter(
        Payment.fee_id == fee.id,
        Payment.student_id == student.id,
        Payment.payment_status == "PAID"
    ).all())
    amount_in_paise = _paise(max(0, fee.amount - already_paid))
    if amount_in_paise < 100:
        raise HTTPException(status_code=400, detail="No payable balance remains")
    client = _razorpay_client()
    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": f"school_fee_{secrets.token_hex(8)}",
        "notes": {
            "fee_id": str(fee.id),
            "student_id": str(student.id),
            "user_id": str(current_user.id)
        }
    }
    
    try:
        order = client.order.create(data=order_data)
        return {
            "order_id": order["id"],
            "amount": amount_in_paise,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
            "fee_id": req.fee_id
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to start online payment"
        )

@router.post("/razorpay/verify")
def verify_razorpay_payment(
    req: RazorpayVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    import razorpay
    _payment_context(db, current_user, req.fee_id, req.student_id)
    client = _razorpay_client()
    
    # 1. Verify Razorpay Signature
    params_dict = {
        'razorpay_order_id': req.razorpay_order_id,
        'razorpay_payment_id': req.razorpay_payment_id,
        'razorpay_signature': req.razorpay_signature
    }
    try:
        client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Razorpay payment signature verification failed."
        )
    # A valid signature only binds IDs. Fetch provider records to verify the
    # captured amount and the server-created order intent before recording it.
    try:
        order = client.order.fetch(req.razorpay_order_id)
        provider_payment = client.payment.fetch(req.razorpay_payment_id)
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to verify payment with provider")

    notes = order.get("notes") or {}
    valid = (
        str(notes.get("fee_id")) == str(req.fee_id)
        and str(notes.get("student_id")) == str(req.student_id)
        and str(notes.get("user_id")) == str(current_user.id)
        and provider_payment.get("order_id") == req.razorpay_order_id
        and provider_payment.get("status") == "captured"
        and provider_payment.get("currency") == "INR"
        and order.get("currency") == "INR"
        and provider_payment.get("amount") == order.get("amount")
        and isinstance(order.get("amount"), int)
        and order["amount"] > 0
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    existing = db.query(Payment).filter(Payment.transaction_id == req.razorpay_payment_id).first()
    if existing:
        if existing.fee_id != req.fee_id or existing.student_id != req.student_id:
            raise HTTPException(status_code=409, detail="Payment already recorded for another fee")
        return {"status": "SUCCESS", "message": "Payment already recorded", "payment_id": existing.id,
                "transaction_id": existing.transaction_id}

    payment_create = PaymentCreate(
        fee_id=req.fee_id,
        student_id=req.student_id,
        amount_paid=order["amount"] / 100,
        discount_amount=0.0,
        payment_method="Online (Razorpay)",
        payment_status="PAID",
        transaction_id=req.razorpay_payment_id,
        remarks=f"Razorpay Payment Verified. Order: {req.razorpay_order_id}"
    )
    
    try:
        payment = fee_service.record_payment(db, payment_create)
    except IntegrityError:
        db.rollback()
        existing = db.query(Payment).filter(Payment.transaction_id == req.razorpay_payment_id).first()
        if not existing or existing.fee_id != req.fee_id or existing.student_id != req.student_id:
            raise HTTPException(status_code=409, detail="Payment could not be recorded")
        payment = existing
    log_audit_action(
        db, "RAZORPAY_PAYMENT_VERIFIED", "Payment", str(payment.id),
        f"Razorpay payment of ₹{payment.amount_paid} verified for Student #{req.student_id} (Txn: {req.razorpay_payment_id})",
        current_user.id
    )
    
    return {
        "status": "SUCCESS",
        "message": "Razorpay payment verified & recorded successfully!",
        "payment_id": payment.id,
        "transaction_id": req.razorpay_payment_id
    }
