/**
 * Fees & Payments Controller
 */
const feesManager = {
  async initAdmin() {
    await this.loadClassSelect();
    await this.loadFeeStructures();
    await this.loadPayments();
  },

  async loadClassSelect() {
    const sel = document.getElementById('fee-class-id');
    const payFeeSel = document.getElementById('payment-fee-id');
    try {
      const classes = await api.get('/classes');
      if (sel) {
        sel.innerHTML = '<option value="">All Classes</option>' +
          classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
      }

      const fees = await api.get('/fees');
      if (payFeeSel) {
        payFeeSel.innerHTML = '<option value="">Select Fee Structure</option>' +
          fees.map(f => `<option value="${f.id}">${f.title} (${utils.formatCurrency(f.amount)})</option>`).join('');
      }
    } catch (e) {
      console.error(e);
    }
  },

  async loadFeeStructures() {
    const tbody = document.getElementById('fees-table-body');
    if (!tbody) return;

    try {
      const fees = await api.get('/fees');
      if (fees.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty-state">No fee structures configured.</td></tr>';
        return;
      }

      tbody.innerHTML = fees.map(f => `
        <tr>
          <td><strong>${f.title}</strong></td>
          <td><span class="badge bg-secondary">${f.fee_type}</span></td>
          <td><span class="badge bg-info text-dark">${f.installment_name || 'Annual'}</span></td>
          <td>${f.class_name || 'All Classes'}</td>
          <td><strong>${utils.formatCurrency(f.amount)}</strong></td>
          <td>${utils.formatDate(f.due_date)}</td>
          <td>
            <button class="table-action-btn text-danger" onclick="feesManager.deleteFee(${f.id})">🗑️</button>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-danger text-center py-3">${e.message}</td></tr>`;
    }
  },

  async createFee(formEvent) {
    if (formEvent) formEvent.preventDefault();
    const form = document.getElementById('create-fee-form');
    if (!form) return;

    const payload = {
      title: form.title.value.trim(),
      fee_type: form.fee_type.value,
      class_id: parseInt(form.class_id.value) || null,
      amount: parseFloat(form.amount.value),
      due_date: form.due_date.value,
      installment_name: form.installment_name?.value.trim() || 'Semester 1',
      installment_number: parseInt(form.installment_number?.value) || 1,
      description: form.description.value.trim() || null
    };

    try {
      await api.post('/fees', payload);
      utils.showToast('Fee structure added successfully!', 'success');
      form.reset();
      const modalEl = document.getElementById('createFeeModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadFeeStructures();
      this.loadClassSelect();
    } catch (e) {
      utils.showToast(e.message || 'Failed to add fee', 'danger');
    }
  },

  async deleteFee(id) {
    if (!confirm('Are you sure you want to delete this fee structure?')) return;
    try {
      await api.delete(`/fees/${id}`);
      utils.showToast('Fee structure deleted', 'success');
      this.loadFeeStructures();
    } catch (e) {
      utils.showToast(e.message, 'danger');
    }
  },

  async loadPayments() {
    const tbody = document.getElementById('payments-table-body');
    if (!tbody) return;

    try {
      const payments = await api.get('/fees/payments');
      if (payments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="table-empty-state">No payment records found.</td></tr>';
        return;
      }

      tbody.innerHTML = payments.map(p => {
        const discountBadge = p.discount_amount > 0 
          ? `<br><small class="text-danger fw-bold">Scholarship: -${utils.formatCurrency(p.discount_amount)}</small>` 
          : '';
        
        const reconBadge = p.reconciliation_status === 'RECONCILED'
          ? '<span class="badge bg-success ms-1">✓ Reconciled</span>'
          : '<span class="badge bg-secondary ms-1">Unreconciled</span>';

        const isVoid = p.payment_status === 'REFUNDED' || p.payment_status === 'CANCELLED' || p.payment_status === 'VOID';

        const voidActionBtn = isVoid 
          ? `<span class="badge bg-danger ms-1">REFUNDED</span>`
          : `<button class="btn btn-sm btn-outline-danger fw-bold ms-1" onclick="feesManager.openVoidModal(${p.id}, 'REC-${p.id.toString().padStart(6, '0')}')">🚫 Void</button>`;

        return `
          <tr class="${isVoid ? 'table-secondary text-muted' : ''}">
            <td><strong>${p.admission_number || '—'}</strong></td>
            <td>${p.student_name || '—'}</td>
            <td>${p.fee_title || '—'}</td>
            <td>
              <span class="${isVoid ? 'text-decoration-line-through' : 'text-success fw-bold'}">${utils.formatCurrency(p.amount_paid)}</span>
              ${discountBadge}
            </td>
            <td>${utils.formatDate(p.payment_date)} (${p.payment_method})</td>
            <td>
              ${utils.getStatusBadge(p.payment_status)}
              ${reconBadge}
            </td>
            <td>
              <button class="btn btn-sm btn-outline-primary fw-bold" onclick="feesManager.printReceipt(${p.id})" ${isVoid ? 'disabled' : ''}>
                🖨️ Receipt
              </button>
              ${voidActionBtn}
            </td>
          </tr>
        `;
      }).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-danger text-center py-3">${e.message}</td></tr>`;
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
      utils.showToast('Please provide a reason for voiding this payment.', 'warning');
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
      this.loadPayments();
    } catch (e) {
      utils.showToast(e.message || 'Failed to void payment', 'danger');
    }
  },

  async openDailyCashRegister() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('register-date-picker').value = today;
    await this.loadDailyCashRegister(today);
    const modalEl = document.getElementById('cashRegisterModal');
    if (modalEl && window.bootstrap) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  },

  async loadDailyCashRegister(targetDate) {
    const container = document.getElementById('cash-register-summary');
    if (!container) return;
    container.innerHTML = '<div class="text-center py-4"><span class="spinner-border text-primary"></span> Loading register...</div>';

    try {
      const data = await api.get(`/fees/daily-collection-register?target_date=${targetDate}`);

      container.innerHTML = `
        <div class="row g-3 mb-4">
          <div class="col-md-3">
            <div class="card bg-primary text-white text-center p-3 rounded">
              <small class="text-uppercase fw-bold">Total Cash</small>
              <h4 class="mb-0 fw-bold">${utils.formatCurrency(data.collections_by_method.Cash)}</h4>
            </div>
          </div>
          <div class="col-md-3">
            <div class="card bg-success text-white text-center p-3 rounded">
              <small class="text-uppercase fw-bold">Total Online / UPI</small>
              <h4 class="mb-0 fw-bold">${utils.formatCurrency(data.collections_by_method.Online)}</h4>
            </div>
          </div>
          <div class="col-md-3">
            <div class="card bg-info text-white text-center p-3 rounded">
              <small class="text-uppercase fw-bold">Bank Transfers</small>
              <h4 class="mb-0 fw-bold">${utils.formatCurrency(data.collections_by_method['Bank Transfer'])}</h4>
            </div>
          </div>
          <div class="col-md-3">
            <div class="card bg-dark text-white text-center p-3 rounded">
              <small class="text-uppercase fw-bold">Total Collected</small>
              <h4 class="mb-0 fw-bold">${utils.formatCurrency(data.total_collections)}</h4>
            </div>
          </div>
        </div>

        <h6 class="fw-bold mb-2">Detailed Collection Register (${data.transactions.length} Records)</h6>
        <div class="table-responsive">
          <table class="table table-bordered table-sm align-middle">
            <thead class="table-light">
              <tr>
                <th>Receipt ID</th>
                <th>Admission No</th>
                <th>Student Name</th>
                <th>Method</th>
                <th>Amount Collected</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${data.transactions.length === 0 ? '<tr><td colspan="6" class="text-center py-3 text-muted">No transaction receipts recorded on this date.</td></tr>' : 
                data.transactions.map(t => `
                  <tr class="${t.status === 'REFUNDED' ? 'table-secondary text-decoration-line-through' : ''}">
                    <td><strong>${t.transaction_id}</strong></td>
                    <td>${t.admission_number}</td>
                    <td>${t.student_name}</td>
                    <td><span class="badge bg-secondary">${t.method}</span></td>
                    <td class="fw-bold text-success">${utils.formatCurrency(t.amount)}</td>
                    <td>${t.status === 'REFUNDED' ? '<span class="badge bg-danger">REFUNDED</span>' : '<span class="badge bg-success">PAID</span>'}</td>
                  </tr>
                `).join('')
              }
            </tbody>
          </table>
        </div>
      `;
    } catch (e) {
      container.innerHTML = `<div class="alert alert-danger py-3">${e.message}</div>`;
    }
  },

  async loadAcademicYearsForRollover() {
    try {
      const years = await api.get('/academic-years');
      const fromSel = document.getElementById('rollover-from-year');
      const toSel = document.getElementById('rollover-to-year');
      if (fromSel && toSel && years.length > 0) {
        const opts = years.map(y => `<option value="${y.id}">${y.name} ${y.is_active ? '(Active)' : ''}</option>`).join('');
        fromSel.innerHTML = opts;
        toSel.innerHTML = opts;
      }
    } catch (e) {
      console.error(e);
    }
  },

  async submitAcademicRollover(event) {
    if (event) event.preventDefault();
    const fromId = document.getElementById('rollover-from-year').value;
    const toId = document.getElementById('rollover-to-year').value;

    if (fromId === toId) {
      utils.showToast('Source and Target academic years must be different.', 'warning');
      return;
    }

    if (!confirm('Are you sure you want to execute Academic Session Rollover? Unpaid student balances will be carried forward as Arrears.')) return;

    try {
      const res = await api.post(`/fees/academic-year-rollover?from_year_id=${fromId}&to_year_id=${toId}`);
      utils.showToast(`${res.message} ${res.students_carried_forward} students carried forward (${utils.formatCurrency(res.total_carried_amount)}).`, 'success');
      const modalEl = document.getElementById('rolloverModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadFeeStructures();
      this.loadPayments();
    } catch (e) {
      utils.showToast(e.message || 'Session rollover failed', 'danger');
    }
  },

  async recordPayment(formEvent) {
    if (formEvent) formEvent.preventDefault();
    const form = document.getElementById('record-payment-form');
    if (!form) return;

    const payload = {
      fee_id: parseInt(form.fee_id.value),
      student_id: parseInt(form.student_id.value),
      amount_paid: parseFloat(form.amount_paid.value),
      discount_amount: parseFloat(form.discount_amount?.value) || 0.0,
      payment_date: form.payment_date.value || null,
      payment_method: form.payment_method.value,
      payment_status: 'PAID',
      transaction_id: form.transaction_id.value.trim() || null,
      remarks: form.remarks.value.trim() || null
    };

    try {
      await api.post('/fees/payments', payload);
      utils.showToast('Payment recorded successfully!', 'success');
      form.reset();
      const modalEl = document.getElementById('recordPaymentModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadPayments();
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

  async reconcileBankStatement(formEvent) {
    if (formEvent) formEvent.preventDefault();
    const form = document.getElementById('reconcile-bank-form');
    const fileInput = form ? form.querySelector('input[type="file"]') : null;
    if (!fileInput || !fileInput.files[0]) {
      utils.showToast('Please select a Bank Statement CSV file.', 'warning');
      return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const btn = document.getElementById('reconcile-bank-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Reconciling...';
    }

    try {
      const res = await api.post('/fees/reconcile-bank-statement', formData);
      utils.showToast(`Reconciliation complete! ${res.reconciled_count} payments matched (${utils.formatCurrency(res.matched_amount)}).`, 'success');
      form.reset();
      const modalEl = document.getElementById('reconcileBankModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadPayments();
    } catch (e) {
      utils.showToast(e.message || 'Bank statement reconciliation failed', 'danger');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = 'Process Reconciliation';
      }
    }
  },

  async uploadVouchers(formEvent) {
    if (formEvent) formEvent.preventDefault();
    const form = document.getElementById('upload-vouchers-form');
    const fileInput = form ? form.querySelector('input[type="file"]') : null;
    if (!fileInput || !fileInput.files[0]) {
      utils.showToast('Please select an Excel file to upload.', 'warning');
      return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const btn = document.getElementById('upload-voucher-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Importing...';
    }

    try {
      const res = await api.post('/fees/upload-vouchers', formData);
      utils.showToast(`Import Success! ${res.payments_imported} payments imported (${utils.formatCurrency(res.total_amount)}).`, 'success');
      form.reset();
      const modalEl = document.getElementById('uploadVouchersModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.loadFeeStructures();
      this.loadPayments();
    } catch (e) {
      utils.showToast(e.message || 'Failed to import vouchers Excel', 'danger');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = 'Upload & Import';
      }
    }
  },

  async loadStudentFees() {
    const container = document.getElementById('student-fees-container');
    if (!container) return;

    try {
      const summary = await api.get('/student/fees');
      const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setText('fee-summary-total', utils.formatCurrency(summary.total_fees));
      setText('fee-summary-paid', utils.formatCurrency(summary.total_paid));
      setText('fee-summary-balance', utils.formatCurrency(summary.remaining_balance));

      const tbody = document.getElementById('student-fees-tbody');
      if (tbody && summary.items) {
        if (summary.items.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" class="table-empty-state">No fee dues assigned.</td></tr>';
          return;
        }

        tbody.innerHTML = summary.items.map(item => {
          const isPending = item.balance > 0;
          const payBtn = isPending
            ? `<button class="btn btn-sm btn-success fw-bold" onclick="feesManager.payWithRazorpay(${item.fee_id}, ${item.balance}, '${item.title.replace(/'/g, "\\'")}', ${summary.student_id})">💳 Pay Online</button>`
            : `<span class="badge bg-success">Cleared</span>`;

          return `
            <tr>
              <td><strong>${item.title}</strong></td>
              <td><span class="badge bg-secondary">${item.fee_type}</span></td>
              <td>${utils.formatCurrency(item.total_amount)}</td>
              <td class="text-success font-weight-bold">${utils.formatCurrency(item.amount_paid)}</td>
              <td class="text-danger font-weight-bold">${utils.formatCurrency(item.balance)}</td>
              <td>${utils.getStatusBadge(item.status)}</td>
              <td>${payBtn}</td>
            </tr>
          `;
        }).join('');
      }
    } catch (e) {
      container.innerHTML = `<div class="text-danger py-4 text-center">${e.message}</div>`;
    }
  },

  async payWithRazorpay(feeId, amount, feeTitle, studentId) {
    if (!window.Razorpay) {
      utils.showToast('Razorpay Checkout SDK failed to load. Please check your internet connection.', 'danger');
      return;
    }

    try {
      utils.showToast('Initiating Razorpay payment order...', 'info');

      // 1. Request backend to create Razorpay Order
      const orderRes = await api.post('/fees/razorpay/create-order', {
        fee_id: feeId,
        amount: amount,
        student_id: studentId
      });

      const user = auth.getUser() || {};

      // 2. Configure Razorpay Standard Checkout options
      const options = {
        key: orderRes.key_id,
        amount: orderRes.amount,
        currency: orderRes.currency,
        name: "Dharani College of Nursing",
        description: `Fee Payment: ${feeTitle}`,
        order_id: orderRes.order_id,
        prefill: {
          name: user.full_name || "",
          email: user.email || "",
          contact: user.phone || ""
        },
        theme: {
          color: "#0d6efd"
        },
        handler: async function (response) {
          utils.showToast('Payment successful! Verifying payment signature...', 'info');
          try {
            // 3. Send payment signature to backend for verification & receipt logging
            const verifyRes = await api.post('/fees/razorpay/verify', {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              fee_id: feeId,
              student_id: studentId,
              amount_paid: amount
            });

            utils.showToast('🎉 Payment verified & receipt generated!', 'success');
            feesManager.loadStudentFees();
          } catch (e) {
            utils.showToast(`Verification failed: ${e.message}`, 'danger');
          }
        },
        modal: {
          ondismiss: function() {
            utils.showToast('Payment cancelled by user.', 'warning');
          }
        }
      };

      const rzp = new Razorpay(options);
      rzp.open();
    } catch (e) {
      utils.showToast(e.message || 'Failed to initiate Razorpay checkout', 'danger');
    }
  }
};

window.feesManager = feesManager;
