from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.app.models.user import User
from backend.app.models.tenant import Tenant
from backend.app.schemas.user import UserCreate
from backend.app.utils.security import verify_password, get_password_hash

class AuthService:
    @staticmethod
    def authenticate_user(db: Session, username_or_email: str, password: str,
                          school_slug: Optional[str] = None) -> Optional[User]:
        query = db.query(User).filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        )
        if school_slug:
            query = query.join(Tenant, User.tenant_id == Tenant.id).filter(Tenant.slug == school_slug)
        matches = query.limit(2).all()
        if len(matches) != 1:
            return None
        user = matches[0]
        if verify_password(password, user.hashed_password):
            return user
        return None

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        if user_in.role.upper() not in {"SCHOOL_ADMIN", "PRINCIPAL", "TEACHER", "STUDENT", "PARENT"}:
            raise HTTPException(status_code=400, detail="Invalid school role")
        if user_in.role.upper() == "SCHOOL_ADMIN":
            from backend.app.services.entitlement_service import entitlement_service
            entitlement_service.check_usage(db, "admins")
        if db.query(User).filter(User.username == user_in.username).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        if db.query(User).filter(User.email == user_in.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        user = User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            full_name=user_in.full_name,
            role=user_in.role.upper(),
            phone=user_in.phone,
            is_active=user_in.is_active
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, old_password: str, new_password: str) -> bool:
        if not verify_password(old_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password does not match"
            )
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        return True

auth_service = AuthService()
