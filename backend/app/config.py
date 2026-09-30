import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "School/College ERP"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "school_erp_secret_key_change_in_production_jwt_token_auth"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/backend/school_erp.db"
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = "pdf,doc,docx,xls,xlsx,ppt,pptx,txt,jpg,jpeg,png,zip"
    RAZORPAY_KEY_ID: str = "rzp_test_TiIP72t6cBs3QV"
    RAZORPAY_KEY_SECRET: str = "rh15ojbKCd3WRWSBvu5PhnO3"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
