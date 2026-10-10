from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate, UserUpdate, UserResponse
from backend.app.services.auth_service import auth_service
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.pagination import paginate_query
from backend.app.utils.helpers import log_audit_action

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("", response_model=dict)
def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    query = db.query(User)
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (User.full_name.ilike(f"%{search}%"))
        )
    if role:
        query = query.filter(User.role == role.upper())
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    query = query.order_by(User.id.desc())
    paginated = paginate_query(query, page, page_size)
    paginated["items"] = [UserResponse.model_validate(u) for u in paginated["items"]]
    return paginated

@router.post("", response_model=UserResponse)
def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    user = auth_service.create_user(db, user_in)
    log_audit_action(db, "USER_CREATE", "User", str(user.id), f"Created user {user.username} ({user.role})", current_user.id)
    return user

@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["SCHOOL_ADMIN", "PRINCIPAL"] and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "SCHOOL_ADMIN" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user_in.email is not None:
        existing = db.query(User).filter(User.email == user_in.email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = user_in.email

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.password:
        from backend.app.utils.security import get_password_hash
        user.hashed_password = get_password_hash(user_in.password)

    # Only admin can change role or active status
    if current_user.role == "SCHOOL_ADMIN":
        if user_in.is_active is not None:
            user.is_active = user_in.is_active
        if user_in.role is not None:
            new_role = user_in.role.upper()
            if new_role not in {"SCHOOL_ADMIN", "PRINCIPAL", "TEACHER", "STUDENT", "PARENT"}:
                raise HTTPException(status_code=400, detail="Invalid school role")
            if new_role == "SCHOOL_ADMIN" and user.role != "SCHOOL_ADMIN":
                from backend.app.services.entitlement_service import entitlement_service
                entitlement_service.check_usage(db, "admins")
            user.role = new_role

    db.commit()
    db.refresh(user)
    log_audit_action(db, "USER_UPDATE", "User", str(user.id), f"Updated user {user.username}", current_user.id)
    return user

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    log_audit_action(db, "USER_DELETE", "User", str(user_id), f"Deleted user {user.username}", current_user.id)
    return {"message": "User deleted successfully"}

@router.patch("/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot change status of your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    db.commit()
    log_audit_action(db, "USER_STATUS_TOGGLE", "User", str(user.id), f"Set is_active={user.is_active}", current_user.id)
    return {"message": f"User status set to {'active' if user.is_active else 'inactive'}", "is_active": user.is_active}
