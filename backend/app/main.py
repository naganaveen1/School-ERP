import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, Request, Depends, status
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.database import engine, get_db
from backend.app.models.tenant import Tenant
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from backend.app.services.file_service import file_service
from backend.app.routes import (
    auth, admin, users, students, teachers, parents, departments,
    classes, subjects, timetable, attendance, leave, assignments,
    materials, exams, results, fees, notices, notifications, events,
    messages, complaints, documents, reports, dashboard, principal,
    teacher, student, parent, platform, saas_billing
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production schema changes are applied explicitly with Alembic before startup.
    if settings.ENVIRONMENT.lower() != "production":
        init_db()
    # Ensure local upload directories exist
    file_service.ensure_upload_dirs()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Role-based ERP Platform for Schools and Colleges",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
@app.exception_handler(PermissionError)
async def tenant_permission_handler(request: Request, exc: PermissionError):
    return JSONResponse(status_code=403, content={"detail": "Resource access denied"})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log error internally and return clean JSON response
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )

# Include REST Routers
api_prefix = settings.API_V1_STR
app.include_router(auth.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)
app.include_router(students.router, prefix=api_prefix)
app.include_router(teachers.router, prefix=api_prefix)
app.include_router(parents.router, prefix=api_prefix)
app.include_router(departments.router, prefix=api_prefix)
app.include_router(classes.router, prefix=api_prefix)
app.include_router(subjects.router, prefix=api_prefix)
app.include_router(timetable.router, prefix=api_prefix)
app.include_router(attendance.router, prefix=api_prefix)
app.include_router(leave.router, prefix=api_prefix)
app.include_router(assignments.router, prefix=api_prefix)
app.include_router(materials.router, prefix=api_prefix)
app.include_router(exams.router, prefix=api_prefix)
app.include_router(results.router, prefix=api_prefix)
app.include_router(fees.router, prefix=api_prefix)
app.include_router(notices.router, prefix=api_prefix)
app.include_router(notifications.router, prefix=api_prefix)
app.include_router(events.router, prefix=api_prefix)
app.include_router(messages.router, prefix=api_prefix)
app.include_router(complaints.router, prefix=api_prefix)
app.include_router(documents.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(principal.router, prefix=api_prefix)
app.include_router(teacher.router, prefix=api_prefix)
app.include_router(student.router, prefix=api_prefix)
app.include_router(parent.router, prefix=api_prefix)
app.include_router(platform.router, prefix=api_prefix)
app.include_router(saas_billing.router, prefix=api_prefix)

# Mount frontend directory for local static file serving
BASE_DIR = Path(__file__).resolve().parent.parent.parent
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

@app.get("/")
def root():
    return RedirectResponse(url="/frontend/login.html")

@app.get("/school/{slug}")
def school_entry(slug: str, db: Session = Depends(get_db)):
    if not db.query(Tenant).filter(Tenant.slug == slug, Tenant.status != "ARCHIVED").first():
        raise HTTPException(status_code=404, detail="School workspace not found")
    return RedirectResponse(url=f"/frontend/login.html?school={quote(slug)}")

@app.get("/api/schools/{slug}/branding")
def school_branding(slug: str, db: Session = Depends(get_db)):
    school = db.query(Tenant).filter(Tenant.slug == slug, Tenant.status != "ARCHIVED").first()
    if school is None:
        raise HTTPException(status_code=404, detail="School workspace not found")
    return {"name": school.name, "slug": school.slug, "logo_url": school.logo_url,
            "favicon_url": school.favicon_url, "primary_color": school.primary_color,
            "secondary_color": school.secondary_color}

@app.get("/health")
def health_check():
    return {"status": "healthy", "app": settings.PROJECT_NAME}

@app.get("/ready")
def readiness_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready"}
