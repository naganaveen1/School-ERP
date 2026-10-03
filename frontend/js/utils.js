/**
 * Utility functions for School/College ERP
 */
const utils = {
  showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-msg toast-${type}`;
    toast.innerHTML = `
      <span>${message}</span>
      <button style="background:none;border:none;color:#fff;cursor:pointer;margin-left:10px;" onclick="this.parentElement.remove()">&times;</button>
    `;
    container.appendChild(toast);

    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, 4500);
  },

  formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    if (isNaN(d)) return dateStr;
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  },

  formatDateTime(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    if (isNaN(d)) return dateStr;
    return d.toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  },

  formatCurrency(amount) {
    const val = parseFloat(amount) || 0.0;
    return '₹' + val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },

  getStatusBadge(status) {
    const s = (status || '').toLowerCase();
    let badgeClass = 'badge-info';
    if (['present', 'active', 'paid', 'approved', 'graded', 'resolved'].includes(s)) {
      badgeClass = 'badge-present';
    } else if (['absent', 'inactive', 'unpaid', 'rejected'].includes(s)) {
      badgeClass = 'badge-absent';
    } else if (['late', 'pending', 'partial', 'in_review'].includes(s)) {
      badgeClass = 'badge-late';
    }
    return `<span class="badge-custom ${badgeClass}">${status || 'N/A'}</span>`;
  },

  getGradeBadge(grade) {
    const g = (grade || '').toUpperCase();
    let color = '#2563eb';
    let bg = '#eff6ff';
    if (['A+', 'A'].includes(g)) {
      color = '#065f46';
      bg = '#ecfdf5';
    } else if (['B', 'C'].includes(g)) {
      color = '#1e40af';
      bg = '#eff6ff';
    } else if (['D'].includes(g)) {
      color = '#92400e';
      bg = '#fffbeb';
    } else if (['F'].includes(g)) {
      color = '#991b1b';
      bg = '#fef2f2';
    }
    return `<span style="background:${bg};color:${color};font-weight:700;padding:2px 8px;border-radius:4px;display:inline-block;">${g || '—'}</span>`;
  },

  debounce(func, wait = 300) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  },

  getQueryParams() {
    const params = {};
    const searchParams = new URLSearchParams(window.location.search);
    for (const [key, value] of searchParams.entries()) {
      params[key] = value;
    }
    return params;
  }
};

window.utils = utils;
