/**
 * Permissions and Role Access Control
 */
const permissions = {
  hasRole(role) {
    const current = auth.getRole();
    return current === role;
  },

  hasAnyRole(roles = []) {
    const current = auth.getRole();
    return roles.includes(current);
  },

  canEditAcademicData() {
    return this.hasAnyRole(['SCHOOL_ADMIN']);
  },

  canMarkAttendance() {
    return this.hasAnyRole(['SCHOOL_ADMIN', 'TEACHER', 'PRINCIPAL']);
  },

  canGradeAssignments() {
    return this.hasAnyRole(['SCHOOL_ADMIN', 'TEACHER']);
  },

  canPublishExams() {
    return this.hasAnyRole(['SCHOOL_ADMIN', 'TEACHER', 'PRINCIPAL']);
  },

  canManageFees() {
    return this.hasRole('SCHOOL_ADMIN');
  },

  enforcePageAccess(allowedRoles = []) {
    return auth.requireAuth(allowedRoles);
  }
};

window.permissions = permissions;
