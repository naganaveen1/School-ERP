import os
import sys
import zipfile
from datetime import date, datetime, timedelta
import xml.etree.ElementTree as ET
from sqlalchemy.orm import Session

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from backend.app.database import SessionLocal, init_db
from backend.app.models import (
    User, Student, Department, AcademicYear, ClassModel, Section, Fee, Payment
)
from backend.app.utils.security import get_password_hash

def excel_date_to_date(val):
    if not val:
        return date.today()
    val_str = str(val).strip()
    try:
        if "." in val_str:
            num = float(val_str)
        else:
            num = int(val_str)
        return (datetime(1899, 12, 30) + timedelta(days=num)).date()
    except ValueError:
        # Try string date formats
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(val_str, fmt).date()
            except ValueError:
                pass
    return date.today()

def parse_excel_voucher_file(file_path_or_bytes):
    """
    Parses the DNC Fee Voucher Excel file using standard library zipfile + ET.
    Supports both file paths and bytes stream.
    Returns list of parsed records: [{student_name, receipt_num, date, year, mop, ac_date, utr, amount, remarks}]
    """
    if isinstance(file_path_or_bytes, bytes):
        import io
        z = zipfile.ZipFile(io.BytesIO(file_path_or_bytes))
    else:
        z = zipfile.ZipFile(file_path_or_bytes)

    wb_xml = ET.fromstring(z.read('xl/workbook.xml'))
    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    sheets = wb_xml.findall('.//ns:sheet', ns)

    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('.//ns:si', ns):
            strings.append(''.join([t.text for t in si.findall('.//ns:t', ns) if t.text]))

    rel_map = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')).findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')}

    # Table 1: student details & vouchers
    t1_xml = ET.fromstring(z.read('xl/' + rel_map[sheets[0].attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]))
    t1_rows = list(t1_xml.findall('.//ns:row', ns))

    # Table 2: amounts & remarks
    t2_rows = []
    if len(sheets) > 1:
        t2_xml = ET.fromstring(z.read('xl/' + rel_map[sheets[1].attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]))
        t2_rows = list(t2_xml.findall('.//ns:row', ns))

    records = []

    # Map Table 2 rows by row index
    t2_map = {}
    for r in t2_rows:
        r_num = int(r.attrib.get('r'))
        c_vals = {}
        for c in r.findall('.//ns:c', ns):
            ref = c.attrib.get('r', '')
            col = ''.join([ch for ch in ref if ch.isalpha()])
            t = c.attrib.get('t')
            v = c.find('ns:v', ns)
            val = v.text if v is not None else ''
            if t == 's' and val.isdigit() and int(val) < len(strings):
                val = strings[int(val)]
            c_vals[col] = val
        t2_map[r_num] = c_vals

    # Process Table 1 starting from row 3 (Row 1=Title, Row 2=Headers)
    for r in t1_rows:
        r_num = int(r.attrib.get('r'))
        if r_num < 3:
            continue
        
        c_vals = {}
        for c in r.findall('.//ns:c', ns):
            ref = c.attrib.get('r', '')
            col = ''.join([ch for ch in ref if ch.isalpha()])
            t = c.attrib.get('t')
            v = c.find('ns:v', ns)
            val = v.text if v is not None else ''
            if t == 's' and val.isdigit() and int(val) < len(strings):
                val = strings[int(val)]
            c_vals[col] = val

        sn = c_vals.get('A', '').strip()
        student_name = c_vals.get('B', '').strip()
        if not student_name or student_name.upper() == 'STUDENT NAME':
            continue

        receipt_num = c_vals.get('C', '').strip()
        p_date = c_vals.get('D', '').strip()
        year = c_vals.get('E', '').strip() or '2022-23'
        mop = c_vals.get('F', '').strip() or 'CASH'
        ac_date = c_vals.get('G', '').strip()
        utr = c_vals.get('H', '').strip()

        # Table 2 matching row
        t2_vals = t2_map.get(r_num, {})
        amount_raw = t2_vals.get('A', '0').strip()
        remarks = t2_vals.get('B', '').strip()

        try:
            amount = float(amount_raw)
        except ValueError:
            amount = 0.0

        records.append({
            "sn": sn,
            "student_name": student_name,
            "receipt_num": receipt_num,
            "date": excel_date_to_date(p_date),
            "year": year,
            "mop": mop,
            "ac_date": ac_date,
            "utr": utr,
            "amount": amount,
            "remarks": remarks
        })

    return records

def import_vouchers_to_db(db: Session, records: list):
    """
    Imports parsed records into database tables.
    """
    init_db()

    # 1. Department
    dept = db.query(Department).filter(Department.code == "NURS").first()
    if not dept:
        dept = Department(name="Dharani College of Nursing", code="NURS", description="School of Nursing Science")
        db.add(dept)
        db.commit()
        db.refresh(dept)

    # 2. Academic Year
    ay = db.query(AcademicYear).filter(AcademicYear.name == "2022-2023").first()
    if not ay:
        ay = AcademicYear(name="2022-2023", start_date=date(2022, 6, 1), end_date=date(2023, 5, 31), is_current=False)
        db.add(ay)
        db.commit()
        db.refresh(ay)

    # 3. Class & Section
    cls = db.query(ClassModel).filter(ClassModel.name == "B.Sc Nursing").first()
    if not cls:
        cls = ClassModel(name="B.Sc Nursing", grade_level=1, department_id=dept.id, academic_year_id=ay.id)
        db.add(cls)
        db.commit()
        db.refresh(cls)

    sec = db.query(Section).filter(Section.class_id == cls.id, Section.name == "A").first()
    if not sec:
        sec = Section(name="A", class_id=cls.id, room_number="Nursing Hall 1")
        db.add(sec)
        db.commit()
        db.refresh(sec)

    # 4. General Fee Structure
    fee = db.query(Fee).filter(Fee.title == "B.Sc Nursing Fee Voucher Collection 2022-23").first()
    if not fee:
        fee = Fee(
            title="B.Sc Nursing Fee Voucher Collection 2022-23",
            fee_type="Tuition & Vouchers",
            class_id=cls.id,
            academic_year_id=ay.id,
            amount=50000.0,
            due_date=date(2023, 5, 31),
            description="Fee received as per vouchers for Dharani College of Nursing B.Sc"
        )
        db.add(fee)
        db.commit()
        db.refresh(fee)

    student_cache = {}
    total_imported_payments = 0
    total_amount = 0.0

    default_pwd_hash = get_password_hash("Password123!")

    for idx, rec in enumerate(records, 1):
        sname = rec["student_name"]
        
        # Get or create student
        if sname not in student_cache:
            username = "student_" + "".join([c.lower() for c in sname if c.isalnum()])
            if len(username) < 6:
                username = f"{username}_{idx}"
            
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(
                    username=username,
                    email=f"{username}@dharaninursing.edu",
                    hashed_password=default_pwd_hash,
                    full_name=sname,
                    role="STUDENT",
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)

            student = db.query(Student).filter(Student.user_id == user.id).first()
            if not student:
                adm_no = f"ADM-DNC-2022-{idx:04d}"
                student = Student(
                    user_id=user.id,
                    admission_number=adm_no,
                    roll_number=str(idx),
                    class_id=cls.id,
                    section_id=sec.id,
                    gender="Female",
                    address="Dharani Nursing Hostel / Campus"
                )
                db.add(student)
                db.commit()
                db.refresh(student)

            student_cache[sname] = student
        else:
            student = student_cache[sname]

        # Record payment
        txn_id = f"RCP-{rec['receipt_num']}" if rec['receipt_num'] else f"TXN-DNC-{idx:04d}"
        if rec['utr']:
            txn_id = f"{txn_id}-UTR-{rec['utr']}"

        # Check existing payment transaction_id
        existing_payment = db.query(Payment).filter(Payment.transaction_id == txn_id).first()
        if not existing_payment:
            payment_method = "Cash" if "CASH" in rec['mop'].upper() else "Bank Transfer / Online"
            payment = Payment(
                fee_id=fee.id,
                student_id=student.id,
                amount_paid=rec['amount'],
                payment_date=rec['date'],
                payment_method=payment_method,
                payment_status="PAID",
                transaction_id=txn_id,
                remarks=f"Receipt #{rec['receipt_num']} | MOP: {rec['mop']} | {rec['remarks']}".strip()
            )
            db.add(payment)
            total_imported_payments += 1
            total_amount += rec['amount']

    db.commit()
    return {
        "unique_students": len(student_cache),
        "payments_imported": total_imported_payments,
        "total_amount": total_amount
    }

def run_import():
    excel_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../DNC TOTAL RECIVED AS PER VOCHERS (multiple sheets).xlsx"))
    print(f"Parsing Excel file: {excel_file}...")
    records = parse_excel_voucher_file(excel_file)
    print(f"Parsed {len(records)} voucher records from Excel sheets.")

    db = SessionLocal()
    try:
        res = import_vouchers_to_db(db, records)
        print(f"Import Summary:\n - Unique Students Created/Mapped: {res['unique_students']}\n - Fee Voucher Payments Imported: {res['payments_imported']}\n - Total Amount Collected: ₹{res['total_amount']:,.2f}")
    finally:
        db.close()

if __name__ == "__main__":
    run_import()
