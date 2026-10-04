/**
 * Role-Based Dashboard Controller
 */
const dashboard = {
  async init() {
    const user = auth.getUser();
    if (!user) return;

    try {
      const data = await api.get('/dashboard');
      switch (user.role) {
        case 'SCHOOL_ADMIN':
          this.renderAdminDashboard(data);
          break;
        case 'PRINCIPAL':
          this.renderPrincipalDashboard(data);
          break;
        case 'TEACHER':
          this.renderTeacherDashboard(data);
          break;
        case 'STUDENT':
          this.renderStudentDashboard(data);
          break;
        case 'PARENT':
          this.renderParentDashboard(data);
          break;
      }
    } catch (err) {
      utils.showToast(err.message || 'Failed to load dashboard data', 'danger');
    }
  },

  renderAdminDashboard(data) {
    // Stats cards
    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setText('total-students', data.total_students || 0);
    setText('total-teachers', data.total_teachers || 0);
    setText('total-parents', data.total_parents || 0);
    setText('total-classes', data.total_classes || 0);
    setText('fees-collected', utils.formatCurrency(data.total_fees_collected || 0));
    setText('att-percentage', `${(data.today_attendance && data.today_attendance.percentage) || 0}%`);
    const yearBadge = document.getElementById('active-academic-year');
    if (yearBadge && data.academic_year) {
      yearBadge.textContent = `Session: ${data.academic_year}`;
      yearBadge.hidden = false;
    }

    // Render Recent Notices
    const noticesList = document.getElementById('recent-notices-list');
    if (noticesList && data.recent_notices) {
      if (data.recent_notices.length === 0) {
        noticesList.innerHTML = '<li class="text-muted small py-3">No notices published yet.</li>';
      } else {
        noticesList.innerHTML = data.recent_notices.map(n => `
          <li class="activity-item">
            <span class="activity-dot"></span>
            <div class="activity-content">
              <div class="activity-title">${components.escapeHTML(n.title)}</div>
              <div class="activity-meta">Target: <strong>${components.escapeHTML(n.target_role)}</strong> &bull; ${utils.formatDate(n.publish_date)}</div>
            </div>
          </li>
        `).join('');
      }
    }

    // Render Recent Activities
    const activityList = document.getElementById('recent-activity-list');
    if (activityList && data.recent_activities) {
      if (data.recent_activities.length === 0) {
        activityList.innerHTML = '<li class="text-muted small py-3">No recent activities recorded.</li>';
      } else {
        activityList.innerHTML = data.recent_activities.map(a => `
          <li class="activity-item">
            <span class="activity-dot" style="background:#06b6d4;"></span>
            <div class="activity-content">
              <div class="activity-title">${components.escapeHTML(a.action)} - ${components.escapeHTML(a.entity)}</div>
              <div class="activity-meta">${components.escapeHTML(a.details)} &bull; ${utils.formatDateTime(a.timestamp)}</div>
            </div>
          </li>
        `).join('');
      }
    }

    // Render Attendance Chart if canvas exists
    const chartCanvas = document.getElementById('attendanceChart');
    if (chartCanvas && window.Chart && data.today_attendance) {
      const present = data.today_attendance.present || 0;
      const absent = data.today_attendance.absent || 0;
      const others = Math.max(0, (data.today_attendance.total || 0) - present - absent);

      if (!data.today_attendance.total) {
        chartCanvas.parentElement.innerHTML = '<div class="empty-state"><h3>No attendance recorded today</h3><p>Attendance will appear here once teachers submit it.</p></div>';
        return;
      }

      new Chart(chartCanvas, {
        type: 'doughnut',
        data: {
          labels: ['Present', 'Absent', 'Other'],
          datasets: [{
            data: [present, absent, others],
            backgroundColor: ['#18734d', '#bb453e', '#a65c16']
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' }
          }
        }
      });
    }
  },

  renderPrincipalDashboard(data) {
    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setText('total-students', data.total_students || 0);
    setText('total-teachers', data.total_teachers || 0);
    setText('pending-leaves', data.pending_leaves || 0);
    setText('pending-complaints', data.pending_complaints || 0);
    setText('average-marks', `${data.average_marks || 0}%`);

    const leavesList = document.getElementById('recent-leaves-list');
    if (leavesList && data.recent_leaves) {
      leavesList.innerHTML = data.recent_leaves.map(l => `
        <li class="activity-item">
          <span class="activity-dot" style="background:${l.status === 'APPROVED' ? '#10b981' : '#f59e0b'}"></span>
          <div class="activity-content">
            <div class="activity-title">${components.escapeHTML(l.user)} (${components.escapeHTML(l.role)}) - ${components.escapeHTML(l.type)}</div>
            <div class="activity-meta">Status: ${utils.getStatusBadge(l.status)}</div>
          </div>
        </li>
      `).join('') || '<li class="text-muted small py-2">No leave requests</li>';
    }

    const complaintsList = document.getElementById('recent-complaints-list');
    if (complaintsList && data.recent_complaints) {
      complaintsList.innerHTML = data.recent_complaints.map(c => `
        <li class="activity-item">
          <span class="activity-dot" style="background:#ef4444"></span>
          <div class="activity-content">
            <div class="activity-title">${components.escapeHTML(c.title)}</div>
            <div class="activity-meta">By: ${components.escapeHTML(c.user)} &bull; ${utils.getStatusBadge(c.status)}</div>
          </div>
        </li>
      `).join('') || '<li class="text-muted small py-2">No complaints filed</li>';
    }
  },

  renderTeacherDashboard(data) {
    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setText('teacher-name', data.teacher_name || '');
    setText('teacher-dept', data.department || '');
    setText('assigned-classes', data.assigned_classes_count || 0);
    setText('total-students', data.total_students || 0);
    setText('total-assignments', data.total_assignments || 0);
    setText('pending-grading', data.pending_grading || 0);
    setText('timetable-periods', data.timetable_count || 0);
  },

  renderStudentDashboard(data) {
    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setText('student-name', data.student_name || '');
    setText('admission-num', data.admission_number || '');
    setText('class-info', `${data.class_name || ''} - ${data.section_name || ''}`);
    setText('att-pct', `${(data.attendance && data.attendance.percentage) || 0}%`);
    setText('att-days', `${(data.attendance && data.attendance.present) || 0} / ${(data.attendance && data.attendance.total) || 0} Days`);
    setText('fee-balance', utils.formatCurrency((data.fees && data.fees.balance) || 0));

    // Upcoming assignments
    const asgnList = document.getElementById('upcoming-assignments-list');
    if (asgnList && data.upcoming_assignments) {
      asgnList.innerHTML = data.upcoming_assignments.map(a => `
        <li class="activity-item">
          <span class="activity-dot"></span>
          <div class="activity-content">
            <div class="activity-title"><a href="/frontend/student/assignments.html">${components.escapeHTML(a.title)}</a></div>
            <div class="activity-meta">${components.escapeHTML(a.subject)} &bull; Due: ${utils.formatDate(a.due_date)}</div>
          </div>
        </li>
      `).join('') || '<li class="text-muted small py-2">No upcoming assignments.</li>';
    }

    // Results
    const resList = document.getElementById('recent-results-list');
    if (resList && data.recent_results) {
      resList.innerHTML = data.recent_results.map(r => `
        <li class="activity-item">
          <span class="activity-dot" style="background:#10b981"></span>
          <div class="activity-content">
            <div class="activity-title">${components.escapeHTML(r.subject)}: ${components.escapeHTML(r.marks)} / ${components.escapeHTML(r.max)} (${utils.getGradeBadge(r.grade)})</div>
          </div>
        </li>
      `).join('') || '<li class="text-muted small py-2">No exam results recorded yet.</li>';
    }
  },

  renderParentDashboard(data) {
    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setText('parent-name', data.parent_name || '');

    const childrenContainer = document.getElementById('children-cards-container');
    if (childrenContainer && data.children) {
      childrenContainer.innerHTML = data.children.map(c => `
        <div class="col-md-6 mb-3">
          <div class="card card-custom h-100 p-3">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <h6 class="fw-bold mb-0 text-dark">${components.escapeHTML(c.name)}</h6>
              <span class="badge bg-primary">${components.escapeHTML(c.admission_number)}</span>
            </div>
            <p class="text-secondary small mb-3">Class: ${components.escapeHTML(c.class_name)}</p>
            <div class="row g-2 text-center">
              <div class="col-6">
                <div class="p-2 border rounded bg-light">
                  <div class="text-muted small">Attendance</div>
                  <div class="fw-bold text-success">${c.attendance_percentage}%</div>
                </div>
              </div>
              <div class="col-6">
                <div class="p-2 border rounded bg-light">
                  <div class="text-muted small">Fee Balance</div>
                  <div class="fw-bold text-danger">${utils.formatCurrency(c.fee_balance)}</div>
                </div>
              </div>
            </div>
            <div class="mt-3 text-end">
              <a href="/frontend/parent/child-profile.html?child_id=${c.id}" class="btn btn-sm btn-outline-primary">View Full Profile &rarr;</a>
            </div>
          </div>
        </div>
      `).join('') || '<div class="col-12 text-muted">No linked children found.</div>';
    }
  }
};

window.dashboard = dashboard;
