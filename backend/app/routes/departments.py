from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.department import Department
from backend.app.schemas.class_schema import DepartmentCreate, DepartmentResponse
from backend.app.utils.permissions import require_roles, get_current_active_user

router = APIRouter(prefix="/departments", tags=["Departments"])

@router.get("", response_model=List[DepartmentResponse])
def get_departments(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(Department).order_by(Department.name.asc()).all()

@router.post("", response_model=DepartmentResponse)
def create_department(
    dept_in: DepartmentCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    if db.query(Department).filter(Department.name == dept_in.name).first():
        raise HTTPException(status_code=400, detail="Department with this name already exists")
    if db.query(Department).filter(Department.code == dept_in.code).first():
        raise HTTPException(status_code=400, detail="Department with this code already exists")

    dept = Department(
        name=dept_in.name,
        code=dept_in.code.upper(),
        description=dept_in.description
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept

@router.put("/{dept_id}", response_model=DepartmentResponse)
def update_department(
    dept_id: int,
    dept_in: DepartmentCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    dept.name = dept_in.name
    dept.code = dept_in.code.upper()
    dept.description = dept_in.description
    db.commit()
    db.refresh(dept)
    return dept

@router.delete("/{dept_id}")
def delete_department(
    dept_id: int,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(dept)
    db.commit()
    return {"message": "Department deleted successfully"}
