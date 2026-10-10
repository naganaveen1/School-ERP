# Local Setup & Installation Guide

## 1. System Requirements
- **Operating System:** macOS (Apple Silicon or Intel) or Linux (Ubuntu, Debian, Fedora, Arch)
- **Python Version:** Python 3.10, 3.11, or 3.12
- **Disk Space:** ~200 MB for Python environment and dependencies
- **Browser:** Modern web browser (Chrome, Firefox, Safari, Edge)

---

## 2. Installation Steps

### Step 1: Clone or Navigate to the Project Root
```bash
cd school-college-erp
```

### Step 2: Create and Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```
*(On Windows cmd/powershell: `venv\Scripts\activate`)*

### Step 3: Install Required Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy the example environment configuration:
```bash
cp .env.example .env
```
Default `.env` configuration:
```env
PROJECT_NAME="School/College ERP"
SECRET_KEY="replace-with-a-long-random-secret"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL="sqlite:///./backend/school_erp.db"
MAX_UPLOAD_SIZE_MB=10
ALLOWED_EXTENSIONS=["pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "zip", "csv", "xlsx"]
```

### Step 5: Initialize Database & Seed Demo Data
The application creates all required tables automatically on startup. To seed the database with comprehensive demo accounts, classes, subjects, attendance, and exam results:
```bash
python3 -m backend.app.seed.seed_database
```

---

## 3. Running the Server

Start the FastAPI application with auto-reloading enabled:
```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running:
- **Application Portal:** [http://127.0.0.1:8000](http://127.0.0.1:8000) (auto-redirects to `/frontend/login.html`)
- **Interactive Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc API Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 4. Running the Pytest Test Suite
To execute the automated test suite testing auth, students, attendance, assignments, and results:
```bash
pytest
```
Use a disposable database seeded for tests. The checked-in sample database has drifted from some demo-specific assertions; see [TESTING.md](TESTING.md).

---

## 5. Pre-Configured Demo Credentials
All demo accounts are pre-seeded with the password: **`Password123!`**

| Role | Username | Password | Direct Portal Entry |
|---|---|---|---|
| **ADMIN** | `admin` | `Password123!` | `/frontend/admin/dashboard.html` |
| **PRINCIPAL** | `principal` | `Password123!` | `/frontend/principal/dashboard.html` |
| **TEACHER** | `teacher` | `Password123!` | `/frontend/teacher/dashboard.html` |
| **STUDENT** | `student` | `Password123!` | `/frontend/student/dashboard.html` |
| **PARENT** | `parent` | `Password123!` | `/frontend/parent/dashboard.html` |

The login page does not display demo passwords. These accounts are for local development only.
