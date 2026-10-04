# Role-Based Access Control (RBAC) & Security Policy

## 1. Role Hierarchy & Access Matrix

The ERP enforces 5 distinct system roles with strict server-side separation:

| Module / Resource | ADMIN | PRINCIPAL | TEACHER | STUDENT | PARENT |
|---|:---:|:---:|:---:|:---:|:---:|
| **User & Role Administration** | Full CRUD | Read-Only | - | - | - |
| **System Audit Logs** | Full Read | - | - | - | - |
| **Academic Hierarchy (Depts/Classes)** | Full CRUD | Read-Only | Read-Only | - | - |
| **Faculty & Staff Records** | Full CRUD | Read-Only | - | - | - |
| **Student Directory** | Full CRUD | Read-Only | Assigned Classes | Self Record | Linked Children |
| **Daily Attendance** | Full CRUD | Read-Only | Mark (Assigned) | Self Record | Linked Children |
| **Coursework & Assignments** | Full CRUD | Read-Only | Create / Grade | Submit (Enrolled)| View (Children) |
| **Examinations** | Full CRUD | Read-Only | Create / Schedule| View (Enrolled) | View (Children) |
| **Marks & Grading** | Full CRUD | Read-Only | Enter / Edit | View (Published)| View (Published) |
| **Tuition & Payment Ledgers** | Full CRUD | Read-Only | - | View (Self) | View (Children) |
| **Notices & Circulars** | Full CRUD | Full CRUD | View (Targeted) | View (Targeted) | View (Targeted) |
| **Leave Management** | Review / Edit | Review / Edit | Apply / View Self | Apply / View Self| Apply / View Self|
| **Grievance Resolution** | Resolve | Resolve | Submit / View | Submit / View | Submit / View |
| **Internal Messaging** | Inbox / Sent | Inbox / Sent | Inbox / Sent | Inbox / Sent | Inbox / Sent |
| **File Storage & Documents** | Full Access | Full Access | Scoped Upload | Scoped Upload | Scoped Upload |

---

## 2. Server-Side Enforcement Mechanisms

### Dependency Injection with `require_roles`
Protected routes declare required permissions directly in the route handler signature using FastAPI dependencies:
```python
from backend.app.utils.permissions import require_roles

@router.post("/classes", response_model=ClassResponse)
def create_class(
    class_in: ClassCreate,
    current_user: User = Depends(require_roles(["ADMIN"])),
    db: Session = Depends(get_db)
):
    ...
```
If an unauthenticated request is received, a `401 Unauthorized` is raised. If the user's role is not within the authorized array, a `403 Forbidden` is raised.

### Resource Ownership Checks
Role checks alone are not sufficient for multi-tenant isolation. Some routes enforce resource ownership checks at the service/database layer, including these examples. Coverage is incomplete; the current application must not be used for multiple schools. See [the architecture gap analysis](ARCHITECTURE_GAP_ANALYSIS.md).

1. **Student Isolation:**
   Students can only access their own attendance, grades, and submissions. Routes automatically bind to `current_user.student_profile.id`:
   ```python
   student = current_user.student_profile
   results = db.query(Result).filter(Result.student_id == student.id).all()
   ```

2. **Parent-Child Scoping:**
   Parents can only access records for verified linked children via the `parent_id` foreign key:
   ```python
   def get_parent_and_child(parent_user: User, child_id: int, db: Session) -> Student:
       parent = parent_user.parent_profile
       student = db.query(Student).filter(
           Student.id == child_id,
           Student.parent_id == parent.id
       ).first()
       if not student:
           raise HTTPException(status_code=403, detail="Child not found or not linked to this parent account")
       return student
   ```

3. **Teacher Class Scoping:**
   Teachers can only view students, mark attendance, and evaluate submissions for classes to which they are assigned via taught subjects or section teacher roles.

---

## 3. Client-Side Route Protection
Frontend HTML pages incorporate client-side guards to immediately bounce unauthorized attempts before page rendering occurs:
```javascript
<script>
  if (permissions.enforcePageAccess(['ADMIN'])) {
    components.renderLayout('Admin Dashboard');
    dashboard.init();
  }
</script>
```
If the token is missing or the role does not match, `permissions.enforcePageAccess` clears the invalid session and redirects to `/frontend/login.html`.

---

## 4. Audit Logging Policy
Sensitive operations trigger an immutable record in `audit_logs`:
- User authentication events (login, logout, failed credentials)
- Entity creation and deletion (students, teachers, classes, exams, fees)
- Marks entry and publication
- Leave approvals and rejections
- Grievance resolutions
