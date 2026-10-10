/**
 * Assignments and Submissions Controller
 */
const assignmentsManager = {
  async initTeacher() {
    await this.loadClassAndSubjects();
    await this.loadTeacherAssignments();
  },

  async loadClassAndSubjects() {
    const classSelect = document.getElementById('assignment-class');
    const subjSelect = document.getElementById('assignment-subject');
    try {
      const classes = await api.get('/classes');
      if (classSelect) {
        classSelect.innerHTML = '<option value="">Select Class</option>' +
          classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
      }

      const subjects = await api.get('/subjects');
      if (subjSelect) {
        subjSelect.innerHTML = '<option value="">Select Subject</option>' +
          subjects.map(s => `<option value="${s.id}">${s.name} (${s.code})</option>`).join('');
      }
    } catch (e) {
      console.error(e);
    }
  },

  async loadTeacherAssignments() {
    const container = document.getElementById('teacher-assignments-list');
    if (!container) return;

    try {
      const list = await api.get('/assignments');
      if (list.length === 0) {
        container.innerHTML = '<div class="col-12 text-muted py-4 text-center">No assignments created yet.</div>';
        return;
      }

      container.innerHTML = list.map(a => `
        <div class="col-md-6 mb-3">
          <div class="card card-custom h-100 p-3">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <h5 class="fw-bold mb-0 text-dark">${a.title}</h5>
              <span class="badge bg-primary">${a.subject_name || 'Subject'}</span>
            </div>
            <p class="text-secondary small mb-2">${a.description || ''}</p>
            <div class="d-flex justify-content-between align-items-center small text-muted mb-3">
              <span>Class: <strong>${a.class_name || ''}</strong></span>
              <span>Due: <strong>${utils.formatDate(a.due_date)}</strong></span>
            </div>
            <div class="d-flex justify-content-between align-items-center pt-2 border-top">
              <span class="small text-secondary">Submissions: <strong>${a.submission_count}</strong></span>
              <div>
                <a href="/frontend/teacher/submissions.html?assignment_id=${a.id}" class="btn btn-sm btn-outline-primary">View Submissions</a>
                <button class="btn btn-sm btn-outline-danger" onclick="assignmentsManager.deleteAssignment(${a.id})">Delete</button>
              </div>
            </div>
          </div>
        </div>
      `).join('');
    } catch (e) {
      container.innerHTML = `<div class="col-12 text-danger text-center py-4">${e.message}</div>`;
    }
  },

  async createAssignment(formEvent) {
    if (formEvent) formEvent.preventDefault();
    const form = document.getElementById('create-assignment-form');
    if (!form) return;

    const formData = new FormData(form);
    try {
      await api.post('/assignments', formData);
      utils.showToast('Assignment created successfully!', 'success');
      form.reset();
      const modalEl = document.getElementById('createAssignmentModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadTeacherAssignments();
    } catch (e) {
      utils.showToast(e.message || 'Failed to create assignment', 'danger');
    }
  },

  async deleteAssignment(id) {
    if (!confirm('Are you sure you want to delete this assignment?')) return;
    try {
      await api.delete(`/assignments/${id}`);
      utils.showToast('Assignment deleted', 'success');
      this.loadTeacherAssignments();
    } catch (e) {
      utils.showToast(e.message, 'danger');
    }
  },

  async loadStudentAssignments() {
    const container = document.getElementById('student-assignments-list');
    if (!container) return;

    try {
      const list = await api.get('/student/assignments');
      if (list.length === 0) {
        container.innerHTML = '<div class="col-12 text-muted py-4 text-center">No assignments posted for your class.</div>';
        return;
      }

      container.innerHTML = list.map(a => {
        const hasSub = !!a.submission;
        return `
          <div class="col-md-6 mb-3">
            <div class="card card-custom h-100 p-3">
              <div class="d-flex justify-content-between align-items-start mb-2">
                <h5 class="fw-bold mb-0 text-dark">${a.title}</h5>
                <span class="badge bg-secondary">${a.subject_name}</span>
              </div>
              <p class="text-secondary small mb-2">${a.description || ''}</p>
              <div class="small text-muted mb-3">
                Due: <strong>${utils.formatDateTime(a.due_date)}</strong> &bull; Max Marks: <strong>${a.max_marks}</strong>
              </div>
              <div class="d-flex justify-content-between align-items-center pt-2 border-top">
                <div>
                  Status: ${hasSub ? utils.getStatusBadge(a.submission.status) : '<span class="badge bg-warning text-dark">Pending</span>'}
                  ${hasSub && a.submission.marks_obtained !== null ? `<span class="ms-2 fw-bold text-success">${a.submission.marks_obtained} / ${a.max_marks}</span>` : ''}
                </div>
                <div>
                  <button class="btn btn-sm ${hasSub ? 'btn-outline-secondary' : 'btn-primary'}" onclick="assignmentsManager.openSubmitModal(${a.id}, '${a.title}')">
                    ${hasSub ? 'Re-submit' : 'Submit Now'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        `;
      }).join('');
    } catch (e) {
      container.innerHTML = `<div class="col-12 text-danger text-center py-4">${e.message}</div>`;
    }
  },

  openSubmitModal(assignmentId, title) {
    const inputId = document.getElementById('submit-assignment-id');
    const titleEl = document.getElementById('submit-assignment-title');
    if (inputId) inputId.value = assignmentId;
    if (titleEl) titleEl.textContent = title;

    const modalEl = document.getElementById('submitModal');
    if (modalEl && window.bootstrap) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  },

  async submitAssignment(formEvent) {
    if (formEvent) formEvent.preventDefault();
    const form = document.getElementById('submit-form');
    const assignmentId = document.getElementById('submit-assignment-id').value;
    if (!form || !assignmentId) return;

    const formData = new FormData();
    const fileInput = document.getElementById('submission-file');
    if (!fileInput.files[0]) {
      utils.showToast('Please select a file to upload', 'warning');
      return;
    }
    formData.append('file', fileInput.files[0]);

    try {
      await api.post(`/assignments/${assignmentId}/submit`, formData);
      utils.showToast('Assignment submitted successfully!', 'success');
      const modalEl = document.getElementById('submitModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      form.reset();
      this.loadStudentAssignments();
    } catch (e) {
      utils.showToast(e.message || 'Submission failed', 'danger');
    }
  },

  async loadSubmissions() {
    const params = utils.getQueryParams();
    const assignmentId = params.assignment_id;
    if (!assignmentId) return;

    const tbody = document.getElementById('submissions-table-body');
    try {
      const subs = await api.get(`/assignments/${assignmentId}/submissions`);
      if (subs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty-state">No submissions yet for this assignment.</td></tr>';
        return;
      }

      tbody.innerHTML = subs.map((s, idx) => `
        <tr>
          <td>${idx + 1}</td>
          <td><strong>${s.admission_number}</strong></td>
          <td>${s.student_name}</td>
          <td>${utils.formatDateTime(s.submission_date)}</td>
          <td>${utils.getStatusBadge(s.status)}</td>
          <td>${s.marks_obtained !== null ? `${s.marks_obtained} / ${s.max_marks}` : '—'}</td>
          <td>
            <div class="table-actions">
              <a href="/api/documents/file/${s.file_path}" target="_blank" class="table-action-btn" download>📥 Download</a>
              <button class="table-action-btn text-primary" onclick="assignmentsManager.openGradeModal(${s.id}, ${s.marks_obtained || 0}, '${s.feedback || ''}')">✍️ Grade</button>
            </div>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-danger py-4 text-center">${e.message}</td></tr>`;
    }
  },

  openGradeModal(submissionId, currentMarks, currentFeedback) {
    document.getElementById('grade-sub-id').value = submissionId;
    document.getElementById('grade-marks').value = currentMarks || '';
    document.getElementById('grade-feedback').value = currentFeedback || '';

    const modalEl = document.getElementById('gradeModal');
    if (modalEl && window.bootstrap) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  },

  async saveGrade(formEvent) {
    if (formEvent) formEvent.preventDefault();
    const subId = document.getElementById('grade-sub-id').value;
    const marks = parseFloat(document.getElementById('grade-marks').value);
    const feedback = document.getElementById('grade-feedback').value;

    try {
      await api.put(`/assignments/submissions/${subId}/grade`, {
        marks_obtained: marks,
        feedback: feedback
      });
      utils.showToast('Grade and feedback saved!', 'success');
      const modalEl = document.getElementById('gradeModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadSubmissions();
    } catch (e) {
      utils.showToast(e.message || 'Failed to grade submission', 'danger');
    }
  }
};

window.assignmentsManager = assignmentsManager;
