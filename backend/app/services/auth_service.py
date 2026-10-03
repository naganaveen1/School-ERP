from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate
from backend.app.utils.security import verify_password, get_password_hash

class AuthService:
    @staticmethod
    def authenticate_user(db: Session, username_or_email: str, password: str) -> Optional[User]:
        user = db.query(User).filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()
        if not user:
            return None
        if verify_password(password, user.hashed_password):
            return user
        # Fallback for demo logins (accepting Password123! or role-specific demo passwords like admin123)
        if verify_password("Password123!", user.hashed_password) and password in [
            "admin123", "principal123", "teacher123", "student123", "parent123", "Password123!"
        ]:
            return user
        if verify_password("admin123", user.hashed_password) and password in [
            "admin123", "Password123!"
        ]:
            return user
        return None

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
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
