/**
 * Authentication and Session Management
 */
const auth = {
  getUser() {
    try {
      const u = localStorage.getItem('user');
      return u ? JSON.parse(u) : null;
    } catch {
      return null;
    }
  },

  getToken() {
    return localStorage.getItem('token');
  },

  isAuthenticated() {
    return !!this.getToken() && !!this.getUser();
  },

  getRole() {
    const user = this.getUser();
    return user ? user.role : null;
  },

  async login(username, password, schoolSlug = null) {
    const data = await api.post('/auth/login', { username, password, school_slug: schoolSlug || null });
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data.user;
  },

  async logout() {
    try {
      if (this.isAuthenticated()) {
        await api.post('/auth/logout', {});
      }
    } catch (e) {
      // Ignore network failure on logout
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/frontend/login.html';
    }
  },

  getRoleDashboardUrl(role) {
    if (this.getUser()?.billing_only) return '/frontend/school/subscription.html';
    switch ((role || '').toUpperCase()) {
      case 'SCHOOL_ADMIN':
        return '/frontend/admin/dashboard.html';
      case 'PLATFORM_SUPER_ADMIN':
      case 'PLATFORM_SUPPORT':
      case 'PLATFORM_BILLING':
        return '/frontend/platform/dashboard.html';
      case 'PRINCIPAL':
        return '/frontend/principal/dashboard.html';
      case 'TEACHER':
        return '/frontend/teacher/dashboard.html';
      case 'STUDENT':
        return '/frontend/student/dashboard.html';
      case 'PARENT':
        return '/frontend/parent/dashboard.html';
      default:
        return '/frontend/login.html';
    }
  },

  redirectBasedOnRole(role) {
    window.location.href = this.getRoleDashboardUrl(role);
  },

  requireAuth(allowedRoles = []) {
    if (!this.isAuthenticated()) {
      window.location.href = `/frontend/login.html?redirect=${encodeURIComponent(window.location.pathname)}`;
      return false;
    }

    const currentRole = this.getRole();
    if (allowedRoles.length > 0 && !allowedRoles.includes(currentRole)) {
      alert(`Access denied: requires one of [${allowedRoles.join(', ')}]. You are logged in as ${currentRole}.`);
      this.redirectBasedOnRole(currentRole);
      return false;
    }

    return true;
  }
};

window.auth = auth;

// Download private files with the bearer header so tokens never enter URLs,
// browser history, referrer headers, or web-server access logs.
document.addEventListener('click', async (event) => {
  const link = event.target.closest('a[href^="/api/documents/file/"], a[href^="/api/documents/download/"]');
  if (!link) return;
  event.preventDefault();
  const token = auth.getToken();
  if (!token) return auth.redirectBasedOnRole(null);
  link.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(link.href, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new Error('Unable to download this file.');
    const objectUrl = URL.createObjectURL(await response.blob());
    const download = document.createElement('a');
    download.href = objectUrl;
    download.download = link.getAttribute('download') || decodeURIComponent(new URL(link.href).pathname.split('/').pop());
    document.body.appendChild(download);
    download.click();
    download.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
  } catch (error) {
    window.alert(error.message);
  } finally {
    link.removeAttribute('aria-busy');
  }
});
