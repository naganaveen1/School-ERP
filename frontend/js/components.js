/**
 * Reusable Components and Layout Renderer
 */
const components = {
  escapeHTML(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  },

  iconFor(label) {
    const text = label.toLowerCase();
    let path = '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>';
    if (/student|teacher|parent|user|children|profile/.test(text)) path = '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>';
    else if (/attendance|leave|calendar|event|year|timetable/.test(text)) path = '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>';
    else if (/fee|payment/.test(text)) path = '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20m-15 5h4"/>';
    else if (/class|section|department|school/.test(text)) path = '<path d="M3 21V8l9-5 9 5v13M3 10h18M9 21v-6h6v6"/>';
    else if (/notice|notification|message/.test(text)) path = '<path d="M4 5h16v12H8l-4 4V5Z"/><path d="M8 9h8m-8 4h5"/>';
    else if (/report|result|performance|audit/.test(text)) path = '<path d="M5 20V4h14v16H5Z"/><path d="m8 15 3-3 2 2 3-4"/>';
    else if (/assignment|exam|submission|material|document|subject/.test(text)) path = '<path d="M6 2h9l4 4v16H6V2Z"/><path d="M15 2v5h4M9 11h7m-7 4h7"/>';
    else if (/setting/.test(text)) path = '<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2"/>';
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
  },
  getNavItems(role) {
    const r = (role || '').toUpperCase();
    switch (r) {
      case 'SCHOOL_ADMIN':
        return [
          { section: 'Main' },
          { label: 'Dashboard', icon: '📊', url: '/frontend/admin/dashboard.html' },
          { label: 'User Accounts', icon: '👥', url: '/frontend/admin/users.html' },
          { label: 'Students', icon: '🎓', url: '/frontend/admin/students.html' },
          { label: 'Teachers', icon: '👨‍🏫', url: '/frontend/admin/teachers.html' },
          { label: 'Parents', icon: '👨‍👩‍👧', url: '/frontend/admin/parents.html' },
          { section: 'Academic Management' },
          { label: 'Academic Years', icon: '📅', url: '/frontend/admin/academic-years.html' },
          { label: 'Departments', icon: '🏢', url: '/frontend/admin/departments.html' },
          { label: 'Classes', icon: '🏫', url: '/frontend/admin/classes.html' },
          { label: 'Sections', icon: '🚪', url: '/frontend/admin/sections.html' },
          { label: 'Subjects', icon: '📚', url: '/frontend/admin/subjects.html' },
          { label: 'Timetable', icon: '⏰', url: '/frontend/admin/timetable.html' },
          { section: 'Finance & Communications' },
          { label: 'Fees & Payments', icon: '💳', url: '/frontend/admin/fees.html' },
          { label: 'School Subscription', icon: '💳', url: '/frontend/school/subscription.html' },
          { label: 'Notices', icon: '📢', url: '/frontend/admin/notices.html' },
          { label: 'Reports', icon: '📈', url: '/frontend/admin/reports.html' },
          { label: 'Audit Logs', icon: '📜', url: '/frontend/admin/audit-logs.html' },
          { label: 'Settings', icon: '⚙️', url: '/frontend/admin/settings.html' }
        ];

      case 'PRINCIPAL':
        return [
          { section: 'Principal Portal' },
          { label: 'Dashboard', icon: '📊', url: '/frontend/principal/dashboard.html' },
          { label: 'Students Directory', icon: '🎓', url: '/frontend/principal/students.html' },
          { label: 'Teachers Directory', icon: '👨‍🏫', url: '/frontend/principal/teachers.html' },
          { label: 'Attendance Overview', icon: '📋', url: '/frontend/principal/attendance.html' },
          { label: 'Academic Performance', icon: '🏆', url: '/frontend/principal/performance.html' },
          { label: 'Leave Requests', icon: '🏖️', url: '/frontend/principal/leave-requests.html' },
          { label: 'Complaints', icon: '⚠️', url: '/frontend/principal/complaints.html' },
          { label: 'School Notices', icon: '📢', url: '/frontend/principal/notices.html' },
          { label: 'Executive Reports', icon: '📈', url: '/frontend/principal/reports.html' }
        ];

      case 'TEACHER':
        return [
          { section: 'Teacher Portal' },
          { label: 'Dashboard', icon: '📊', url: '/frontend/teacher/dashboard.html' },
          { label: 'My Classes', icon: '🏫', url: '/frontend/teacher/my-classes.html' },
          { label: 'My Students', icon: '🎓', url: '/frontend/teacher/students.html' },
          { label: 'Daily Timetable', icon: '⏰', url: '/frontend/teacher/timetable.html' },
          { label: 'Mark Attendance', icon: '📋', url: '/frontend/teacher/attendance.html' },
          { section: 'Academics' },
          { label: 'Assignments', icon: '📝', url: '/frontend/teacher/assignments.html' },
          { label: 'Submissions', icon: '📥', url: '/frontend/teacher/submissions.html' },
          { label: 'Study Materials', icon: '📂', url: '/frontend/teacher/study-materials.html' },
          { label: 'Exams', icon: '📑', url: '/frontend/teacher/exams.html' },
          { label: 'Enter Marks', icon: '✍️', url: '/frontend/teacher/marks.html' },
          { section: 'Personal' },
          { label: 'Leave Applications', icon: '🏖️', url: '/frontend/teacher/leave.html' },
          { label: 'My Profile', icon: '👤', url: '/frontend/teacher/profile.html' }
        ];

      case 'STUDENT':
        return [
          { section: 'Student Portal' },
          { label: 'Dashboard', icon: '📊', url: '/frontend/student/dashboard.html' },
          { label: 'Class Timetable', icon: '⏰', url: '/frontend/student/timetable.html' },
          { label: 'Attendance', icon: '📋', url: '/frontend/student/attendance.html' },
          { label: 'Assignments', icon: '📝', url: '/frontend/student/assignments.html' },
          { label: 'Study Materials', icon: '📂', url: '/frontend/student/study-materials.html' },
          { label: 'Exams', icon: '📑', url: '/frontend/student/exams.html' },
          { label: 'Report Cards', icon: '🏆', url: '/frontend/student/results.html' },
          { label: 'Fees & Dues', icon: '💳', url: '/frontend/student/fees.html' },
          { label: 'Announcements', icon: '📢', url: '/frontend/student/notices.html' },
          { label: 'School Events', icon: '🎉', url: '/frontend/student/events.html' },
          { label: 'Apply Leave', icon: '🏖️', url: '/frontend/student/leave.html' },
          { label: 'Documents', icon: '📄', url: '/frontend/student/documents.html' },
          { label: 'My Profile', icon: '👤', url: '/frontend/student/profile.html' }
        ];

      case 'PARENT':
        return [
          { section: 'Parent Portal' },
          { label: 'Dashboard', icon: '📊', url: '/frontend/parent/dashboard.html' },
          { label: 'My Children', icon: '👨‍👧‍👦', url: '/frontend/parent/children.html' },
          { label: 'Child Attendance', icon: '📋', url: '/frontend/parent/attendance.html' },
          { label: 'Assignments', icon: '📝', url: '/frontend/parent/assignments.html' },
          { label: 'Exam Results', icon: '🏆', url: '/frontend/parent/results.html' },
          { label: 'Fee Payments', icon: '💳', url: '/frontend/parent/fees.html' },
          { label: 'School Notices', icon: '📢', url: '/frontend/parent/notices.html' },
          { label: 'Calendar Events', icon: '🎉', url: '/frontend/parent/events.html' },
          { label: 'Leave Requests', icon: '🏖️', url: '/frontend/parent/leave.html' },
          { label: 'Messages', icon: '✉️', url: '/frontend/parent/messages.html' },
          { label: 'Documents', icon: '📄', url: '/frontend/parent/documents.html' }
        ];

      default:
        return [];
    }
  },

  renderLayout(pageTitle = 'Dashboard') {
    const user = auth.getUser() || { full_name: 'User', role: 'GUEST' };
    if (user.school_slug) {
      api.get(`/schools/${encodeURIComponent(user.school_slug)}/branding`).then(branding => {
        if (/^#[0-9a-fA-F]{6}$/.test(branding.primary_color || '')) {
          document.documentElement.style.setProperty('--primary', branding.primary_color);
        }
        if (branding.name) {
          const brand = document.querySelector('.sidebar-brand');
          if (brand) brand.textContent = branding.name;
        }
        if (branding.logo_url && /^https:\/\//i.test(branding.logo_url)) {
          const mark = document.querySelector('.sidebar-header .brand-mark');
          if (mark) {
            const logo = document.createElement('img');
            logo.src = branding.logo_url;
            logo.alt = '';
            logo.style.cssText = 'max-width:28px;max-height:28px;object-fit:contain';
            mark.replaceChildren(logo);
          }
        }
        if (branding.favicon_url) {
          let icon = document.querySelector('link[rel="icon"]');
          if (!icon) { icon = document.createElement('link'); icon.rel = 'icon'; document.head.append(icon); }
          icon.href = branding.favicon_url;
        }
      }).catch(() => {});
    }
    const navItems = this.getNavItems(user.role);
    const currentPath = window.location.pathname;

    // Render Sidebar
    let navHtml = '';
    navItems.forEach(item => {
      if (item.section) {
        navHtml += `<div class="nav-section-title">${this.escapeHTML(item.section)}</div>`;
      } else {
        const isActive = currentPath === item.url || currentPath.endsWith(item.url.split('/').pop());
        navHtml += `
          <a href="${item.url}" class="sidebar-link ${isActive ? 'active' : ''}" ${isActive ? 'aria-current="page"' : ''} title="${this.escapeHTML(item.label)}">
            <span class="icon">${this.iconFor(item.label)}</span>
            <span>${this.escapeHTML(item.label)}</span>
          </a>
        `;
      }
    });

    const sidebarContainer = document.getElementById('sidebar-container');
    if (sidebarContainer) {
      if (localStorage.getItem('school-erp-sidebar') === 'collapsed') {
        document.querySelector('.app-wrapper')?.classList.add('sidebar-collapsed');
      }
      sidebarContainer.innerHTML = `
        <div class="sidebar-backdrop" onclick="components.toggleSidebar()"></div>
        <aside class="app-sidebar" id="app-sidebar">
          <div class="sidebar-header">
            <div class="brand-mark">${this.iconFor('School')}</div>
            <div>
              <div class="sidebar-brand">${this.escapeHTML(user.school_name || 'School ERP')}</div>
              <span class="sidebar-role-badge">${this.escapeHTML(user.role)}</span>
            </div>
          </div>
          <nav class="sidebar-nav" aria-label="Primary navigation">
            ${navHtml}
          </nav>
        </aside>
      `;
    }

    // Render Navbar
    const navbarContainer = document.getElementById('navbar-container');
    if (navbarContainer) {
      navbarContainer.innerHTML = `
        <header class="app-navbar">
          <div class="d-flex align-items-center gap-3">
            <button class="shell-action" type="button" aria-label="Toggle navigation" aria-controls="app-sidebar" onclick="components.toggleSidebar()">
              <span class="shell-icon">${this.iconFor('menu')}</span>
            </button>
            <span class="shell-title d-none d-sm-block">${this.escapeHTML(pageTitle)}</span>
          </div>

          <div class="d-flex align-items-center gap-3">
            <select class="form-select form-select-sm" aria-label="Color theme" title="Color theme" onchange="schoolTheme.setPreference(this.value)" style="width:auto; min-height:36px;">
              <option value="system" ${schoolTheme.getPreference() === 'system' ? 'selected' : ''}>System</option>
              <option value="light" ${schoolTheme.getPreference() === 'light' ? 'selected' : ''}>Light</option>
              <option value="dark" ${schoolTheme.getPreference() === 'dark' ? 'selected' : ''}>Dark</option>
            </select>
            <!-- Notifications Bell -->
            <div class="dropdown">
              <button class="shell-action position-relative" type="button" id="notifDropdown" aria-label="Notifications" data-bs-toggle="dropdown" aria-expanded="false" onclick="components.loadNotifications()">
                <span class="shell-icon">${this.iconFor('notifications')}</span>
                <span id="notif-badge" class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger d-none" style="font-size:0.65rem;">
                  0
                </span>
              </button>
              <ul class="dropdown-menu dropdown-menu-end shadow border-0 p-2" aria-labelledby="notifDropdown" style="width: 320px; max-height: 400px; overflow-y: auto;" id="notif-menu">
                <li class="dropdown-header fw-bold">Notifications</li>
                <li id="notif-empty" class="text-muted small text-center py-3">No notifications</li>
              </ul>
            </div>

            <!-- User Menu -->
            <div class="dropdown">
              <button class="navbar-user-btn" type="button" id="userMenuBtn" data-bs-toggle="dropdown" aria-expanded="false">
                <div class="user-avatar-placeholder">
                  ${this.escapeHTML(user.full_name ? user.full_name.charAt(0).toUpperCase() : 'U')}
                </div>
                <div class="text-start d-none d-md-block">
                  <div style="font-size: 0.85rem; font-weight: 600; line-height: 1.2;">${this.escapeHTML(user.full_name)}</div>
                  <div style="font-size: 0.7rem; color: var(--text-muted);">${this.escapeHTML(user.role)}</div>
                </div>
              </button>
              <ul class="dropdown-menu dropdown-menu-end shadow border-0" aria-labelledby="userMenuBtn">
                <li><h6 class="dropdown-header">${this.escapeHTML(user.email || user.username)}</h6></li>
                <li><hr class="dropdown-divider"></li>
                <li>
                  <a class="dropdown-item text-danger fw-semibold" href="javascript:void(0)" onclick="auth.logout()">
                    Log out
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </header>
      `;
    }

    // Existing role dashboards share the same stat markup. Replace their
    // inconsistent emoji decorations with the shell's icon system.
    document.querySelectorAll('.stat-card .stat-icon').forEach(icon => {
      const label = icon.closest('.stat-card')?.querySelector('.stat-label')?.textContent || 'Dashboard';
      icon.innerHTML = this.iconFor(label);
    });

    document.querySelectorAll('.page-content button, .page-content a').forEach(control => {
      const textNode = Array.from(control.childNodes).find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      if (!textNode) return;
      const match = textNode.textContent.match(/^\s*[\p{Extended_Pictographic}\uFE0F\u200D]+\s*/u);
      if (!match) return;
      const label = control.textContent.replace(match[0], '').trim();
      textNode.textContent = textNode.textContent.slice(match[0].length);
      const icon = document.createElement('span');
      icon.className = 'inline-icon';
      icon.innerHTML = this.iconFor(label);
      control.insertBefore(icon, textNode);
    });

    // Load notification count initially
    this.checkUnreadNotifications();
  },

  toggleSidebar() {
    const sidebar = document.getElementById('app-sidebar');
    const backdrop = document.querySelector('.sidebar-backdrop');
    if (window.matchMedia('(min-width: 992px)').matches) {
      const collapsed = document.querySelector('.app-wrapper')?.classList.toggle('sidebar-collapsed');
      localStorage.setItem('school-erp-sidebar', collapsed ? 'collapsed' : 'expanded');
    } else {
      if (sidebar) sidebar.classList.toggle('show');
      if (backdrop) backdrop.classList.toggle('show');
    }
  },

  async checkUnreadNotifications() {
    try {
      if (!auth.isAuthenticated()) return;
      const notifs = await api.get('/notifications', { unread_only: true });
      const badge = document.getElementById('notif-badge');
      if (badge && Array.isArray(notifs)) {
        if (notifs.length > 0) {
          badge.textContent = notifs.length > 9 ? '9+' : notifs.length;
          badge.classList.remove('d-none');
        } else {
          badge.classList.add('d-none');
        }
      }
    } catch (e) {
      // Ignore background check failure
    }
  },

  async loadNotifications() {
    const menu = document.getElementById('notif-menu');
    if (!menu) return;
    try {
      const notifs = await api.get('/notifications');
      if (!notifs || notifs.length === 0) {
        menu.innerHTML = '<li class="dropdown-header fw-bold">Notifications</li><li class="text-muted small text-center py-3">No notifications</li>';
        return;
      }

      let html = `
        <li class="dropdown-header d-flex justify-content-between align-items-center">
          <span class="fw-bold">Notifications</span>
          <button class="btn btn-link btn-sm text-decoration-none p-0" style="font-size:0.75rem;" onclick="components.markAllNotificationsRead(event)">Mark all read</button>
        </li>
        <li><hr class="dropdown-divider my-1"></li>
      `;

      notifs.slice(0, 8).forEach(n => {
        html += `
          <li class="p-2 border-bottom ${n.is_read ? 'bg-white' : 'bg-light'}" style="font-size:0.8rem; cursor:pointer;" onclick="components.readNotification(${n.id})">
            <div class="fw-semibold text-dark">${this.escapeHTML(n.title)}</div>
            <div class="text-secondary small text-truncate">${this.escapeHTML(n.message)}</div>
            <div class="text-muted" style="font-size:0.7rem;">${utils.formatDate(n.created_at)}</div>
          </li>
        `;
      });
      menu.innerHTML = html;
    } catch (e) {
      menu.innerHTML = '<li class="dropdown-header fw-bold">Notifications</li><li class="text-danger small text-center py-2">Failed to load</li>';
    }
  },

  async markAllNotificationsRead(event) {
    if (event) event.stopPropagation();
    try {
      await api.post('/notifications/read-all', {});
      const badge = document.getElementById('notif-badge');
      if (badge) badge.classList.add('d-none');
      this.loadNotifications();
    } catch (e) {
      utils.showToast('Could not mark all as read', 'danger');
    }
  },

  async readNotification(id) {
    try {
      await api.patch(`/notifications/${id}/read`);
      this.checkUnreadNotifications();
      this.loadNotifications();
    } catch (e) {}
  },

  renderPagination(containerId, currentPage, totalPages, onPageClickFnName) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (totalPages <= 1) {
      container.innerHTML = '';
      return;
    }

    let html = `<ul class="pagination pagination-sm justify-content-end mb-0">`;
    html += `
      <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
        <a class="page-link" href="javascript:void(0)" onclick="${onPageClickFnName}(${currentPage - 1})">Previous</a>
      </li>
    `;

    for (let p = 1; p <= totalPages; p++) {
      if (p === 1 || p === totalPages || (p >= currentPage - 2 && p <= currentPage + 2)) {
        html += `
          <li class="page-item ${p === currentPage ? 'active' : ''}">
            <a class="page-link" href="javascript:void(0)" onclick="${onPageClickFnName}(${p})">${p}</a>
          </li>
        `;
      } else if (p === currentPage - 3 || p === currentPage + 3) {
        html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
      }
    }

    html += `
      <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
        <a class="page-link" href="javascript:void(0)" onclick="${onPageClickFnName}(${currentPage + 1})">Next</a>
      </li>
    `;
    html += `</ul>`;
    container.innerHTML = html;
  }
};

window.components = components;
