import secrets
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "School/College ERP"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/backend/school_erp.db"
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    OBJECT_STORAGE_BUCKET: str = ""
    OBJECT_STORAGE_ENDPOINT: str = ""
    OBJECT_STORAGE_REGION: str = "us-east-1"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = "pdf,doc,docx,xls,xlsx,ppt,pptx,txt,jpg,jpeg,png,zip"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    SAAS_RAZORPAY_KEY_ID: str = ""
    SAAS_RAZORPAY_KEY_SECRET: str = ""
    SAAS_RAZORPAY_WEBHOOK_SECRET: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
if settings.DATABASE_URL.startswith("postgres://"):
    settings.DATABASE_URL = "postgresql+psycopg2://" + settings.DATABASE_URL[len("postgres://"):]
elif settings.DATABASE_URL.startswith("postgresql://"):
    settings.DATABASE_URL = "postgresql+psycopg2://" + settings.DATABASE_URL[len("postgresql://"):]
if not settings.SECRET_KEY:
    if settings.ENVIRONMENT.lower() == "production":
        raise RuntimeError("SECRET_KEY must be configured in production")
    settings.SECRET_KEY = secrets.token_urlsafe(48)

if settings.ENVIRONMENT.lower() == "production" and settings.DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("Production requires an explicit PostgreSQL DATABASE_URL")
if settings.ENVIRONMENT.lower() == "production" and not settings.OBJECT_STORAGE_BUCKET:
    raise RuntimeError("Production requires OBJECT_STORAGE_BUCKET for durable private files")
