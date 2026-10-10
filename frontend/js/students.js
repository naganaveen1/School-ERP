/**
 * Student Management Controller
 */
const studentsManager = {
  currentPage: 1,
  pageSize: 10,
  searchTerm: '',
  selectedClass: '',
  selectedSection: '',

  async init() {
    await this.loadClassFilters();
    await this.loadStudents(1);
    this.setupListeners();
  },

  setupListeners() {
    const searchInput = document.getElementById('student-search');
    if (searchInput) {
      searchInput.addEventListener('input', utils.debounce((e) => {
        this.searchTerm = e.target.value.trim();
        this.loadStudents(1);
      }, 350));
    }

    const classFilter = document.getElementById('filter-class');
    if (classFilter) {
      classFilter.addEventListener('change', (e) => {
        this.selectedClass = e.target.value;
        this.loadStudents(1);
      });
    }
  },

  async loadClassFilters() {
    const filterSelect = document.getElementById('filter-class');
    const modalSelect = document.getElementById('modal-student-class');
    try {
      const classes = await api.get('/classes');
      let optionsHtml = '<option value="">All Classes</option>';
      let modalOptionsHtml = '<option value="">Select Class</option>';

      classes.forEach(c => {
        optionsHtml += `<option value="${c.id}">${c.name}</option>`;
        modalOptionsHtml += `<option value="${c.id}">${c.name}</option>`;
      });

      if (filterSelect) filterSelect.innerHTML = optionsHtml;
      if (modalSelect) modalSelect.innerHTML = modalOptionsHtml;
    } catch (e) {
      console.error('Failed to load class filters', e);
    }
  },

  async loadStudents(page = 1) {
    this.currentPage = page;
    const tbody = document.getElementById('students-table-body');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">Loading students...</td></tr>';

    try {
      const res = await api.get('/students', {
        page: this.currentPage,
        page_size: this.pageSize,
        search: this.searchTerm,
        class_id: this.selectedClass
      });

      if (!tbody) return;

      if (!res.items || res.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty-state">No students found matching criteria.</td></tr>';
        components.renderPagination('pagination-container', 1, 1, 'studentsManager.loadStudents');
        return;
      }

      tbody.innerHTML = res.items.map(s => `
        <tr>
          <td><strong>${s.admission_number}</strong></td>
          <td>
            <div class="fw-bold">${s.user ? s.user.full_name : '—'}</div>
            <div class="text-muted small">${s.user ? s.user.email : ''}</div>
          </td>
          <td>${s.class_name || '—'} ${s.section_name ? `(${s.section_name})` : ''}</td>
          <td>${s.roll_number || '—'}</td>
          <td>${s.gender || '—'}</td>
          <td>${s.parent_name || '—'}</td>
          <td>
            <div class="table-actions">
              <a href="/frontend/admin/student-details.html?id=${s.id}" class="table-action-btn" title="View Details">👁️ View</a>
              <button class="table-action-btn text-danger" onclick="studentsManager.deleteStudent(${s.id})" title="Delete">🗑️</button>
            </div>
          </td>
        </tr>
      `).join('');

      components.renderPagination('pagination-container', res.page, res.total_pages, 'studentsManager.loadStudents');
    } catch (e) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">${e.message || 'Error loading students'}</td></tr>`;
    }
  },

  async createStudent(formEvent) {
    if (formEvent) formEvent.preventDefault();
    const form = document.getElementById('add-student-form');
    if (!form) return;

    const payload = {
      username: form.username.value.trim(),
      email: form.email.value.trim(),
      password: form.password.value,
      full_name: form.full_name.value.trim(),
      phone: form.phone.value.trim(),
      admission_number: form.admission_number.value.trim(),
      roll_number: form.roll_number.value.trim() || null,
      class_id: parseInt(form.class_id.value) || null,
      gender: form.gender.value || null,
      date_of_birth: form.date_of_birth.value || null,
      address: form.address.value.trim() || null
    };

    try {
      await api.post('/students', payload);
      utils.showToast('Student registered successfully!', 'success');
      const modalEl = document.getElementById('addStudentModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      form.reset();
      this.loadStudents(1);
    } catch (e) {
      utils.showToast(e.message || 'Failed to create student', 'danger');
    }
  },

  async deleteStudent(id) {
    if (!confirm('Are you sure you want to permanently delete this student record?')) return;
    try {
      await api.delete(`/students/${id}`);
      utils.showToast('Student deleted successfully', 'success');
      this.loadStudents(this.currentPage);
    } catch (e) {
      utils.showToast(e.message || 'Failed to delete student', 'danger');
    }
  },

  currentStudentData: null,

  async loadStudentDetails() {
    const params = utils.getQueryParams();
    const id = params.id;
    if (!id) return;

    try {
      const student = await api.get(`/students/${id}`);
      this.currentStudentData = student;

      const setText = (elemId, val) => {
        const el = document.getElementById(elemId);
        if (el) el.textContent = val || '—';
      };

      setText('detail-name', student.user ? student.user.full_name : '');
      setText('detail-adm', student.admission_number);
      setText('detail-roll', student.roll_number);
      setText('detail-class', `${student.class_name || ''} ${student.section_name ? `(${student.section_name})` : ''}`);
      setText('detail-email', student.user ? student.user.email : '');
      setText('detail-phone', student.user ? student.user.phone : '');
      setText('detail-gender', student.gender);
      setText('detail-blood', student.blood_group);
      setText('detail-dob', utils.formatDate(student.date_of_birth));
      setText('detail-parent', student.parent_name);
      setText('detail-address', student.address);

      // Load attendance stats
      try {
        const att = await api.get(`/students/${id}/attendance`);
        if (att && att.stats) {
          setText('att-percentage', `${att.stats.percentage}%`);
          setText('att-present', `${att.stats.present_days} / ${att.stats.total_days} Days`);
        }
      } catch (e) {
        console.warn('Attendance load warning:', e);
      }

      // Load Fee Ledger & Summary
      await this.loadStudentFeeLedger(id);

    } catch (e) {
      utils.showToast(e.message || 'Failed to load student details', 'danger');
    }
  },

  async loadStudentFeeLedger(studentId) {
    const duesTbody = document.getElementById('student-fee-dues-tbody');
    const historyTbody = document.getElementById('student-payment-history-tbody');
    const payFeeSelect = document.getElementById('record-payment-fee-id');

    const setText = (elemId, val) => {
      const el = document.getElementById(elemId);
      if (el) el.textContent = val || '₹0.00';
    };

    try {
      // 1. Fee summary & assigned dues
      const feeSummary = await api.get(`/students/${studentId}/fees`);
      if (feeSummary) {
        setText('fee-total', utils.formatCurrency(feeSummary.total_fees));
        setText('fee-paid', utils.formatCurrency(feeSummary.total_paid));
        setText('fee-balance', utils.formatCurrency(feeSummary.remaining_balance));

        // Render dues table
        if (duesTbody) {
          if (!feeSummary.items || feeSummary.items.length === 0) {
            duesTbody.innerHTML = '<tr><td colspan="8" class="table-empty-state text-center py-3">No fee dues assigned to student.</td></tr>';
          } else {
            duesTbody.innerHTML = feeSummary.items.map(item => {
              const hasBalance = item.balance > 0;
              const collectBtn = hasBalance
                ? `<button class="btn btn-sm btn-success fw-bold" onclick="studentsManager.openRecordPaymentModal(${item.fee_id}, ${item.balance})">💳 Collect Fee</button>`
                : `<span class="badge bg-success">Cleared</span>`;

              return `
                <tr>
                  <td><strong>${item.title}</strong></td>
                  <td><span class="badge bg-secondary">${item.fee_type}</span></td>
                  <td>${utils.formatDate(item.due_date)}</td>
                  <td><strong>${utils.formatCurrency(item.total_amount)}</strong></td>
                  <td class="text-success fw-bold">${utils.formatCurrency(item.amount_paid)}</td>
                  <td class="text-danger fw-bold">${utils.formatCurrency(item.balance)}</td>
                  <td>${utils.getStatusBadge(item.status)}</td>
                  <td>${collectBtn}</td>
                </tr>
              `;
            }).join('');
          }
        }

        // Populate Fee Select dropdown for Collect Fee Modal
        if (payFeeSelect && feeSummary.items) {
          payFeeSelect.innerHTML = '<option value="">Select Fee Structure</option>' +
            feeSummary.items.map(i => `<option value="${i.fee_id}">${i.title} (Bal: ${utils.formatCurrency(i.balance)})</option>`).join('');
        }
      }

      // 2. Load Payment History Ledger
      const payments = await api.get(`/fees/payments?student_id=${studentId}`);
      if (historyTbody) {
        if (!payments || payments.length === 0) {
          historyTbody.innerHTML = '<tr><td colspan="8" class="table-empty-state text-center py-3">No payment transaction receipts recorded.</td></tr>';
        } else {
          historyTbody.innerHTML = payments.map(p => {
            const isVoid = p.payment_status === 'REFUNDED' || p.payment_status === 'CANCELLED' || p.payment_status === 'VOID';
            const recNo = `REC-${p.id.toString().padStart(6, '0')}`;

            const voidBtn = isVoid
              ? `<span class="badge bg-danger ms-1">REFUNDED</span>`
              : `<button class="btn btn-sm btn-outline-danger fw-bold ms-1" onclick="studentsManager.openVoidModal(${p.id}, '${recNo}')">🚫 Void</button>`;

            return `
              <tr class="${isVoid ? 'table-secondary text-muted' : ''}">
                <td><strong>${recNo}</strong></td>
                <td>${utils.formatDate(p.payment_date)}</td>
                <td>${p.fee_title || 'General Fee'}</td>
                <td><span class="badge bg-secondary">${p.payment_method}</span></td>
                <td><span class="${isVoid ? 'text-decoration-line-through' : 'text-success fw-bold'}">${utils.formatCurrency(p.amount_paid)}</span></td>
                <td>${p.discount_amount > 0 ? `- ${utils.formatCurrency(p.discount_amount)}` : '—'}</td>
                <td>${utils.getStatusBadge(p.payment_status)}</td>
                <td>
                  <button class="btn btn-sm btn-outline-primary fw-bold" onclick="studentsManager.printReceipt(${p.id})" ${isVoid ? 'disabled' : ''}>
                    🖨️ Receipt
                  </button>
                  ${voidBtn}
                </td>
              </tr>
            `;
          }).join('');
        }
      }
    } catch (e) {
      console.error('Error loading fee ledger:', e);
    }
  },

  async openEditModal() {
    if (!this.currentStudentData) return;
    const s = this.currentStudentData;

    // Load class options into edit modal select if empty
    const classSelect = document.getElementById('edit-class-id');
    if (classSelect && classSelect.options.length <= 1) {
      try {
        const classes = await api.get('/classes');
        classSelect.innerHTML = '<option value="">Select Class</option>' +
          classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
      } catch (e) {
        console.error('Failed loading classes for edit modal', e);
      }
    }

    // Pre-fill values
    const setValue = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val || '';
    };

    setValue('edit-full-name', s.user ? s.user.full_name : '');
    setValue('edit-email', s.user ? s.user.email : '');
    setValue('edit-phone', s.user ? s.user.phone : '');
    setValue('edit-admission-number', s.admission_number);
    setValue('edit-roll-number', s.roll_number);
    setValue('edit-class-id', s.class_id);
    setValue('edit-gender', s.gender || 'Male');
    setValue('edit-blood-group', s.blood_group);
    setValue('edit-date-of-birth', s.date_of_birth);
    setValue('edit-address', s.address);

    const modalEl = document.getElementById('editStudentModal');
    if (modalEl && window.bootstrap) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  },

  async submitStudentUpdate(event) {
    if (event) event.preventDefault();
    if (!this.currentStudentData) return;
    const studentId = this.currentStudentData.id;

    const payload = {
      full_name: document.getElementById('edit-full-name').value.trim(),
      email: document.getElementById('edit-email').value.trim(),
      phone: document.getElementById('edit-phone').value.trim() || null,
      admission_number: document.getElementById('edit-admission-number').value.trim(),
      roll_number: document.getElementById('edit-roll-number').value.trim() || null,
      class_id: parseInt(document.getElementById('edit-class-id').value) || null,
      gender: document.getElementById('edit-gender').value || null,
      blood_group: document.getElementById('edit-blood-group').value || null,
      date_of_birth: document.getElementById('edit-date-of-birth').value || null,
      address: document.getElementById('edit-address').value.trim() || null
    };

    try {
      await api.put(`/students/${studentId}`, payload);
      utils.showToast('Student profile updated successfully!', 'success');
      const modalEl = document.getElementById('editStudentModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadStudentDetails();
    } catch (e) {
      utils.showToast(e.message || 'Failed to update student profile', 'danger');
    }
  },

  openRecordPaymentModal(feeId = null, defaultAmount = 0) {
    if (feeId) {
      const feeSelect = document.getElementById('record-payment-fee-id');
      if (feeSelect) feeSelect.value = feeId;
    }
    if (defaultAmount > 0) {
      const amtInput = document.getElementById('record-payment-amount');
      if (amtInput) amtInput.value = defaultAmount;
    }

    const dateInput = document.getElementById('record-payment-date');
    if (dateInput && !dateInput.value) {
      dateInput.value = new Date().toISOString().split('T')[0];
    }

    const modalEl = document.getElementById('recordPaymentModal');
    if (modalEl && window.bootstrap) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  },

  async submitRecordPayment(event) {
    if (event) event.preventDefault();
    if (!this.currentStudentData) return;

    const form = document.getElementById('record-payment-form');
    if (!form) return;

    const feeId = parseInt(document.getElementById('record-payment-fee-id').value);
    const amountPaid = parseFloat(document.getElementById('record-payment-amount').value);
    if (!feeId || isNaN(amountPaid) || amountPaid <= 0) {
      utils.showToast('Please select a fee structure and enter a valid payment amount.', 'warning');
      return;
    }

    const payload = {
      fee_id: feeId,
      student_id: this.currentStudentData.id,
      amount_paid: amountPaid,
      discount_amount: parseFloat(document.getElementById('record-payment-discount').value) || 0.0,
      payment_method: document.getElementById('record-payment-method').value,
      payment_date: document.getElementById('record-payment-date').value || null,
      payment_status: 'PAID',
      transaction_id: document.getElementById('record-payment-txn-id').value.trim() || null,
      remarks: document.getElementById('record-payment-remarks').value.trim() || null
    };

    try {
      await api.post('/fees/payments', payload);
      utils.showToast('Payment collected & recorded successfully!', 'success');
      form.reset();
      const modalEl = document.getElementById('recordPaymentModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadStudentDetails();
    } catch (e) {
      utils.showToast(e.message || 'Failed to record payment', 'danger');
    }
  },

  async printReceipt(paymentId) {
    try {
      const data = await api.get(`/fees/payments/${paymentId}/receipt`);
      const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setText('rec-no', data.receipt_no);
      setText('rec-student-name', data.student_name);
      setText('rec-adm-no', data.admission_number);
      setText('rec-class-name', data.class_name);
      setText('rec-date', utils.formatDate(data.payment_date));
      setText('rec-method', data.payment_method);
      setText('rec-txn-id', data.transaction_id);
      setText('rec-fee-title', data.fee_title);
      setText('rec-fee-type', data.fee_type);
      setText('rec-total-fee', utils.formatCurrency(data.total_fee_amount));
      setText('rec-discount', `- ${utils.formatCurrency(data.discount_amount)}`);
      setText('rec-amount-paid', utils.formatCurrency(data.amount_paid));
      setText('rec-balance', utils.formatCurrency(data.balance_remaining));
      setText('rec-remarks', data.remarks);

      const modalEl = document.getElementById('printReceiptModal');
      if (modalEl && window.bootstrap) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
      }
    } catch (e) {
      utils.showToast(e.message || 'Failed to fetch receipt details', 'danger');
    }
  },

  openVoidModal(paymentId, refNo) {
    document.getElementById('void-payment-id').value = paymentId;
    document.getElementById('void-payment-ref').value = refNo;
    document.getElementById('void-payment-reason').value = '';

    const modalEl = document.getElementById('voidPaymentModal');
    if (modalEl && window.bootstrap) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  },

  async submitVoidPayment(event) {
    if (event) event.preventDefault();
    const paymentId = document.getElementById('void-payment-id').value;
    const reason = document.getElementById('void-payment-reason').value.trim();

    if (!reason) {
      utils.showToast('Please provide a reason for voiding/refunding this payment.', 'warning');
      return;
    }

    try {
      const res = await api.post(`/fees/payments/${paymentId}/void?reason=${encodeURIComponent(reason)}`);
      utils.showToast(res.message, 'success');
      const modalEl = document.getElementById('voidPaymentModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadStudentDetails();
    } catch (e) {
      utils.showToast(e.message || 'Failed to void payment', 'danger');
    }
  }
};

window.studentsManager = studentsManager;
