// Solo Bank — Frontend JavaScript

const API = '';  // relative to same origin
let currentCustomer = null;
let accounts = [];

// ---- Init ----

async function init() {
  const customers = await api('/api/customers');
  const sel = document.getElementById('customerSelect');
  sel.innerHTML = customers.map(c =>
    `<option value="${c.id}">${c.name} (${c.id})</option>`
  ).join('');
  if (customers.length > 0) {
    await switchCustomer(customers[0].id);
  }
}

async function switchCustomer(id) {
  currentCustomer = id;
  await Promise.all([
    loadDashboard(),
    loadApprovals(),
    loadCreditInfo(),
    loadCreditHistory(),
    loadAllTransactions(),
  ]);
  loadTransferForm();
}

// ---- API helper ----

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.error || 'Request failed');
  }
  return res.json();
}

// ---- Navigation ----

function showPage(page, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
}

// ---- Dashboard ----

async function loadDashboard() {
  accounts = await api(`/api/customers/${currentCustomer}/accounts`);
  const grid = document.getElementById('accountsGrid');
  grid.innerHTML = accounts.map(a => {
    const isNeg = a.balance < 0;
    const display = a.type === 'credit' ? Math.abs(a.balance) : a.balance;
    const label = a.type === 'credit' ? 'Owed' : 'Available';
    return `
      <div class="account-card">
        <div class="type">${a.type}</div>
        <div class="name">${a.name}</div>
        <div class="balance ${isNeg ? 'negative' : 'positive'}">
          ${a.type === 'credit' ? '-' : ''}$${display.toLocaleString('en-US', {minimumFractionDigits: 2})}
        </div>
        <div class="account-id">${label} &middot; ${a.id}</div>
      </div>
    `;
  }).join('');

  const txns = await api(`/api/customers/${currentCustomer}/transactions?limit=10`);
  document.getElementById('recentTxns').innerHTML = txns.map(txnRow).join('');
}

// ---- Transactions ----

function txnRow(t, showBalance) {
  const isPos = t.amount > 0;
  const date = new Date(t.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const amt = `${isPos ? '+' : ''}$${Math.abs(t.amount).toLocaleString('en-US', {minimumFractionDigits: 2})}`;
  const acctName = t.account_name || t.account_id;
  let row = `
    <tr>
      <td>${date}</td>
      <td>${acctName}</td>
      <td><span class="txn-type ${t.type}">${t.type}</span></td>
      <td>${t.description || '-'}</td>
      <td class="txn-amount ${isPos ? 'positive' : 'negative'}">${amt}</td>
  `;
  if (showBalance) {
    row += `<td>$${(t.balance_after || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>`;
  }
  row += '</tr>';
  return row;
}

async function loadAllTransactions() {
  const txns = await api(`/api/customers/${currentCustomer}/transactions?limit=50`);
  document.getElementById('allTxns').innerHTML =
    txns.length ? txns.map(t => txnRow(t, true)).join('') :
    '<tr><td colspan="6" class="empty-state">No transactions yet</td></tr>';
}

// ---- Transfer ----

function loadTransferForm() {
  const fromSel = document.getElementById('fromAccount');
  const toSel = document.getElementById('toAccount');
  const nonCredit = accounts.filter(a => a.type !== 'credit');
  const all = accounts;

  fromSel.innerHTML = nonCredit.map(a =>
    `<option value="${a.id}">${a.name} ($${a.balance.toLocaleString('en-US', {minimumFractionDigits:2})})</option>`
  ).join('');

  toSel.innerHTML = all.map(a =>
    `<option value="${a.id}">${a.name} (${a.id})</option>`
  ).join('');

  loadTransferHistory();
}

async function loadTransferHistory() {
  const txns = await api(`/api/customers/${currentCustomer}/transactions?limit=20`);
  const transfers = txns.filter(t => t.type === 'TRANSFER');
  document.getElementById('transferHistory').innerHTML =
    transfers.length ? transfers.map(txnRow).join('') :
    '<tr><td colspan="5" class="empty-state">No transfers yet</td></tr>';
}

async function submitTransfer(e) {
  e.preventDefault();
  const btn = document.getElementById('transferBtn');
  btn.disabled = true;
  btn.textContent = 'Processing...';

  try {
    const result = await api('/api/transfer', {
      method: 'POST',
      body: JSON.stringify({
        from_account_id: document.getElementById('fromAccount').value,
        to_account_id: document.getElementById('toAccount').value,
        amount: parseFloat(document.getElementById('transferAmount').value),
        description: document.getElementById('transferDesc').value || 'Transfer',
      }),
    });
    toast('Transfer completed successfully!', 'success');
    document.getElementById('transferAmount').value = '';
    document.getElementById('transferDesc').value = '';
    await loadDashboard();
    loadTransferForm();
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Transfer Funds';
  }
}

// ---- Approvals ----

async function loadApprovals() {
  const approvals = await api(`/api/customers/${currentCustomer}/approvals`);
  const badge = document.getElementById('approvalBadge');
  badge.textContent = approvals.length > 0 ? `(${approvals.length})` : '';

  const list = document.getElementById('approvalsList');
  if (approvals.length === 0) {
    list.innerHTML = '<div class="empty-state">No pending approvals</div>';
    return;
  }

  list.innerHTML = approvals.map(a => {
    const date = new Date(a.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    return `
      <div class="approval-card">
        <div class="approval-info">
          <h3>${a.type.replace(/_/g, ' ')}</h3>
          <p>${a.description}</p>
          <p style="font-size:0.75rem;color:var(--text-light)">${date}</p>
        </div>
        <div class="approval-actions">
          <div class="approval-amount">$${a.amount.toLocaleString('en-US', {minimumFractionDigits:2})}</div>
          <div style="display:flex;gap:0.5rem">
            <button class="btn btn-success btn-sm" onclick="handleApproval(${a.id}, 'approve')">Approve</button>
            <button class="btn btn-danger btn-sm" onclick="handleApproval(${a.id}, 'deny')">Deny</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function handleApproval(id, action) {
  try {
    await api(`/api/approvals/${id}`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    });
    toast(`Transaction ${action === 'approve' ? 'approved' : 'denied'}`, action === 'approve' ? 'success' : 'error');
    await loadApprovals();
    await loadDashboard();
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ---- Credit ----

async function loadCreditInfo() {
  const customer = await api(`/api/customers/${currentCustomer}`);
  const info = document.getElementById('creditInfo');
  const dti = ((customer.monthly_debt_payments * 12) / customer.annual_income * 100).toFixed(0);
  info.innerHTML = `
    <div class="credit-stat"><div class="value">${customer.credit_score}</div><div class="label">Credit Score</div></div>
    <div class="credit-stat"><div class="value">$${customer.current_credit_limit.toLocaleString()}</div><div class="label">Credit Limit</div></div>
    <div class="credit-stat"><div class="value">${(customer.utilization_rate * 100).toFixed(0)}%</div><div class="label">Utilization</div></div>
    <div class="credit-stat"><div class="value">${dti}%</div><div class="label">Debt-to-Income</div></div>
    <div class="credit-stat"><div class="value">$${customer.annual_income.toLocaleString()}</div><div class="label">Annual Income</div></div>
    <div class="credit-stat"><div class="value">${customer.account_age_months} mo</div><div class="label">Account Age</div></div>
  `;
}

async function loadCreditHistory() {
  const history = await api(`/api/customers/${currentCustomer}/credit-history`);
  document.getElementById('creditHistory').innerHTML =
    history.length ? history.map(h => {
      const date = new Date(h.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      return `
        <tr>
          <td>${date}</td>
          <td>$${h.old_limit.toLocaleString()}</td>
          <td>$${h.new_limit.toLocaleString()}</td>
          <td>${h.reason || '-'}</td>
          <td><span class="txn-type ${h.status}">${h.status}</span></td>
        </tr>
      `;
    }).join('') :
    '<tr><td colspan="5" class="empty-state">No credit limit changes</td></tr>';
}

// ---- Chat with AI Agent ----

async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;

  const messages = document.getElementById('chatMessages');
  const sendBtn = document.getElementById('chatSendBtn');

  // Add user message
  messages.innerHTML += `<div class="chat-msg user">${escapeHtml(msg)}</div>`;
  input.value = '';
  sendBtn.disabled = true;
  sendBtn.innerHTML = '<span class="loading"></span>';
  messages.scrollTop = messages.scrollHeight;

  // Add thinking indicator
  const thinkingId = 'thinking-' + Date.now();
  messages.innerHTML += `<div class="chat-msg agent" id="${thinkingId}" style="opacity:0.6">Analyzing your request...</div>`;
  messages.scrollTop = messages.scrollHeight;

  try {
    const result = await api('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        customer_id: currentCustomer,
        message: `Customer ID: ${currentCustomer}. ${msg}`,
      }),
    });

    document.getElementById(thinkingId).remove();
    messages.innerHTML += `<div class="chat-msg agent">${escapeHtml(result.response)}</div>`;

    // Refresh credit info in case limit was changed
    await loadCreditInfo();
    await loadCreditHistory();
    await loadDashboard();
  } catch (err) {
    document.getElementById(thinkingId).remove();
    messages.innerHTML += `<div class="chat-msg system">Error: ${escapeHtml(err.message)}</div>`;
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
    messages.scrollTop = messages.scrollHeight;
  }
}

// ---- Helpers ----

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function toast(msg, type) {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ---- Boot ----
init();
