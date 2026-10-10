from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field

class FeeBase(BaseModel):
    title: str
    fee_type: str = "Tuition"
    class_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    amount: float = Field(gt=0)
    due_date: date
    installment_name: Optional[str] = "Annual"
    installment_number: Optional[int] = 1
    description: Optional[str] = None

class FeeCreate(FeeBase):
    pass

class FeeUpdate(BaseModel):
    title: Optional[str] = None
    fee_type: Optional[str] = None
    class_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    amount: Optional[float] = None
    due_date: Optional[date] = None
    installment_name: Optional[str] = None
    installment_number: Optional[int] = None
    description: Optional[str] = None

class FeeResponse(FeeBase):
    id: int
    class_name: Optional[str] = None
    academic_year_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    fee_id: int
    student_id: int
    amount_paid: float = Field(gt=0)
    discount_amount: Optional[float] = Field(default=0.0, ge=0)
    payment_date: Optional[date] = None
    payment_method: str = "Cash"
    payment_status: str = "PAID"
    transaction_id: Optional[str] = None
    remarks: Optional[str] = None

class PaymentResponse(BaseModel):
    id: int
    fee_id: int
    student_id: int
    amount_paid: float
    discount_amount: float = 0.0
    payment_date: date
    payment_method: str
    payment_status: str
    reconciliation_status: str = "UNRECONCILED"
    transaction_id: Optional[str] = None
    remarks: Optional[str] = None
    refund_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None
    fee_title: Optional[str] = None
    student_name: Optional[str] = None
    admission_number: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class StudentFeeItem(BaseModel):
    fee_id: int
    title: str
    fee_type: str
    total_amount: float
    amount_paid: float
    balance: float
    status: str
    due_date: date

class StudentFeeSummary(BaseModel):
    student_id: int
    student_name: str
    admission_number: str
    class_name: Optional[str] = None
    total_fees: float
    total_paid: float
    remaining_balance: float
    items: List[StudentFeeItem]

class RazorpayCreateOrderRequest(BaseModel):
    fee_id: int
    amount: float  # Legacy client field; server recalculates the balance.
    student_id: int

class RazorpayCreateOrderResponse(BaseModel):
    order_id: str
    amount: int  # in paise
    currency: str = "INR"
    key_id: str
    fee_id: int

class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    fee_id: int
    student_id: int
    amount_paid: float
