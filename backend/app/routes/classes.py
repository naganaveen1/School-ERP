from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.class_model import ClassModel
from backend.app.models.section import Section
from backend.app.models.academic_year import AcademicYear
from backend.app.schemas.class_schema import (
    ClassCreate, ClassResponse,
    SectionCreate, SectionResponse,
    AcademicYearCreate, AcademicYearResponse
)
from backend.app.utils.permissions import require_roles, get_current_active_user

router = APIRouter(prefix="/classes", tags=["Classes & Academics"])

# Academic Years
@router.get("/academic-years", response_model=List[AcademicYearResponse])
def get_academic_years(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(AcademicYear).order_by(AcademicYear.start_date.desc()).all()

@router.post("/academic-years", response_model=AcademicYearResponse)
def create_academic_year(
    ay_in: AcademicYearCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    if db.query(AcademicYear).filter(AcademicYear.name == ay_in.name).first():
        raise HTTPException(status_code=400, detail="Academic year name already exists")
    
    if ay_in.is_current:
        db.query(AcademicYear).update({"is_current": False})

    ay = AcademicYear(
        name=ay_in.name,
        start_date=ay_in.start_date,
        end_date=ay_in.end_date,
        is_current=ay_in.is_current
    )
    db.add(ay)
    db.commit()
    db.refresh(ay)
    return ay

@router.patch("/academic-years/{ay_id}/set-current")
def set_current_academic_year(
    ay_id: int,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    ay = db.query(AcademicYear).filter(AcademicYear.id == ay_id).first()
    if not ay:
        raise HTTPException(status_code=404, detail="Academic year not found")
    
    db.query(AcademicYear).update({"is_current": False})
    ay.is_current = True
    db.commit()
    return {"message": f"{ay.name} is now the active academic year"}

# Classes
@router.get("", response_model=List[ClassResponse])
def get_classes(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    classes = db.query(ClassModel).options(
        joinedload(ClassModel.department),
        joinedload(ClassModel.academic_year),
        joinedload(ClassModel.sections).joinedload(Section.class_teacher)
    ).order_by(ClassModel.grade_level.asc(), ClassModel.name.asc()).all()

    response = []
    for c in classes:
        sec_list = []
        for s in c.sections:
            sec_list.append(SectionResponse(
                id=s.id,
                name=s.name,
                class_id=s.class_id,
                room_number=s.room_number,
                class_teacher_id=s.class_teacher_id,
                class_name=c.name,
                class_teacher_name=s.class_teacher.user.full_name if s.class_teacher and s.class_teacher.user else None,
                created_at=s.created_at
            ))
        response.append(ClassResponse(
            id=c.id,
            name=c.name,
            grade_level=c.grade_level,
            department_id=c.department_id,
            academic_year_id=c.academic_year_id,
            department_name=c.department.name if c.department else None,
            academic_year_name=c.academic_year.name if c.academic_year else None,
            sections=sec_list,
            created_at=c.created_at
        ))
    return response

@router.post("", response_model=ClassResponse)
def create_class(
    class_in: ClassCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    cls = ClassModel(
        name=class_in.name,
        grade_level=class_in.grade_level,
        department_id=class_in.department_id,
        academic_year_id=class_in.academic_year_id
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return ClassResponse(
        id=cls.id,
        name=cls.name,
        grade_level=cls.grade_level,
        department_id=cls.department_id,
        academic_year_id=cls.academic_year_id,
        sections=[],
        created_at=cls.created_at
    )

@router.put("/{class_id}", response_model=ClassResponse)
def update_class(
    class_id: int,
    class_in: ClassCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    cls = db.query(ClassModel).filter(ClassModel.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    cls.name = class_in.name
    cls.grade_level = class_in.grade_level
    cls.department_id = class_in.department_id
    cls.academic_year_id = class_in.academic_year_id
    db.commit()
    db.refresh(cls)
    return ClassResponse(
        id=cls.id,
        name=cls.name,
        grade_level=cls.grade_level,
        department_id=cls.department_id,
        academic_year_id=cls.academic_year_id,
        sections=[],
        created_at=cls.created_at
    )

@router.delete("/{class_id}")
def delete_class(
    class_id: int,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    cls = db.query(ClassModel).filter(ClassModel.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    db.delete(cls)
    db.commit()
    return {"message": "Class deleted successfully"}

# Sections
@router.get("/{class_id}/sections", response_model=List[SectionResponse])
def get_class_sections(
    class_id: int,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    sections = db.query(Section).options(
        joinedload(Section.class_obj),
        joinedload(Section.class_teacher)
    ).filter(Section.class_id == class_id).all()

    return [
        SectionResponse(
            id=s.id,
            name=s.name,
            class_id=s.class_id,
            room_number=s.room_number,
            class_teacher_id=s.class_teacher_id,
            class_name=s.class_obj.name if s.class_obj else None,
            class_teacher_name=s.class_teacher.user.full_name if s.class_teacher and s.class_teacher.user else None,
            created_at=s.created_at
        )
        for s in sections
    ]

@router.post("/{class_id}/sections", response_model=SectionResponse)
def create_section(
    class_id: int,
    sec_in: SectionCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    cls = db.query(ClassModel).filter(ClassModel.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    sec = Section(
        name=sec_in.name,
        class_id=class_id,
        room_number=sec_in.room_number,
        class_teacher_id=sec_in.class_teacher_id
    )
    db.add(sec)
    db.commit()
    db.refresh(sec)
    return SectionResponse(
        id=sec.id,
        name=sec.name,
        class_id=sec.class_id,
        room_number=sec.room_number,
        class_teacher_id=sec.class_teacher_id,
        class_name=cls.name,
        created_at=sec.created_at
    )

@router.delete("/sections/{section_id}")
def delete_section(
    section_id: int,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    sec = db.query(Section).filter(Section.id == section_id).first()
    if not sec:
        raise HTTPException(status_code=404, detail="Section not found")
    db.delete(sec)
    db.commit()
    return {"message": "Section deleted successfully"}
