from typing import Optional, Any
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str
    school_slug: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[Any] = None

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    tid: Optional[int] = None
    exp: Optional[int] = None

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str
