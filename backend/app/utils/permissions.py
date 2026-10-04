from typing import List, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.tenant import Tenant
from backend.app.models.saas import Subscription
from backend.app.services.subscription_service import can_access_school
from backend.app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_token_from_request(request: Request, bearer_token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    # Support Authorization header first
    if bearer_token:
        return bearer_token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "").strip()
    return None

def get_current_user(
    request: Request,
    token: Optional[str] = Depends(get_token_from_request),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None:
        raise credentials_exception

    if payload.get("tid") != user.tenant_id:
        raise credentials_exception
    if user.tenant_id is None:
        if user.role not in {"PLATFORM_SUPER_ADMIN", "PLATFORM_SUPPORT", "PLATFORM_BILLING"}:
            raise credentials_exception
        db.info["tenant_scope"] = "platform"
    else:
        if user.role.startswith("PLATFORM_"):
            raise credentials_exception
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant or tenant.status not in {"ACTIVE", "TRIAL"}:
            raise HTTPException(status_code=403, detail="School account is unavailable")
        subscription = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
        if not subscription or not can_access_school(subscription):
            raise HTTPException(status_code=403, detail="School subscription is inactive")
        db.info["tenant_scope"] = "tenant"
        db.info["tenant_id"] = user.tenant_id

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return current_user


def get_current_tenant(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Tenant:
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="School account required")
    return db.query(Tenant).filter(Tenant.id == current_user.tenant_id).one()

def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of roles [{', '.join(allowed_roles)}]"
            )
        return current_user
    return role_checker


def require_feature(feature: str):
    def feature_checker(current_user: User = Depends(get_current_active_user),
                        db: Session = Depends(get_db)) -> None:
        from backend.app.services.entitlement_service import entitlement_service
        entitlement_service.require_feature(db, feature)
    return feature_checker
