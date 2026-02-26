// Solo Bank — Two-Portal Frontend

const API = '';
let currentCustomer = null;
let currentPortal = 'customer';
let accounts = [];
let customerName = '';

// ---- Init ----

async function init() {
  const customers = await api('/api/customers');
  const sel = document.getElementById('customerSelect');
  sel.innerHTML = customers.map(c =>
    `<option value="${c.id}">${c.name} (${c.id})</option>`
  ).join('');
  if (customers.length > 0) await switchCustomer(customers[0].id);
}

async function switchCustomer(id) {
  currentCustomer = id;
  const c = await api(`/api/customers/${id}`);
  customerName = c.name;
  document.getElementById('customerGreeting').textContent = `Welcome back, ${c.name}`;
  await refreshAll();
}

async function refreshAll() {
  await Promise.all([
    loadDashboard(),
    loadAllTransactions(),
    loadCreditInfo(),
    loadApprovals(),
    loadAuditLog(),
  ]);
  loadTransferForm();
}

// ---- Portal switching ----

function switchPortal(portal) {
  currentPortal = portal;
  document.querySelectorAll('.portal').forEach(p => p.classList.remove('active'));
  document.getElementById('portal-' + portal).classList.add('active');
  document.getElementById('toggleCustomer').classList.toggle('active', portal === 'customer');
  document.getElementById('toggleAdmin').classList.toggle('active', portal === 'admin');
  // Reset active tabs within portal
  const activePortal = document.getElementById('portal-' + portal);
  const navBtns = activePortal.querySelectorAll('nav button');
  navBtns.forEach((b, i) => b.classList.toggle('active', i === 0));
  const pages = activePortal.querySelectorAll('.page');
  pages.forEach((p, i) => p.classList.toggle('active', i === 0));
}

// ---- Navigation ----

function showPage(pageId, btn) {
  const portal = btn.closest('.portal');
  portal.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + pageId).classList.add('active');
  portal.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

// ---- API helper ----

async function api(path, opts = {}) {
  const res = await fetch(API + path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.error || 'Request failed');
  }
  return res.json();
}

// ---- Dashboard (Customer Portal) ----

async function loadDashboard() {
  accounts = await api(`/api/customers/${currentCustomer}/accounts`);
  document.getElementById('accountsGrid').innerHTML = accounts.map(a => {
    const isNeg = a.balance < 0;
    const display = a.type === 'credit' ? Math.abs(a.balance) : a.balance;
    const label = a.type === 'credit' ? 'Balance Owed' : 'Available';
    return `
      <div class="account-card">
        <div class="type">${a.type}</div>
        <div class="name">${a.name}</div>
        <div class="balance ${isNeg ? 'negative' : 'positive'}">
          ${a.type === 'credit' ? '-' : ''}$${display.toLocaleString('en-US', {minimumFractionDigits: 2})}
        </div>
        <div class="account-id">${label} &middot; ${a.id}</div>
      </div>`;
  }).join('');

  const txns = await api(`/api/customers/${currentCustomer}/transactions?limit=8`);
  document.getElementById('recentTxns').innerHTML = txns.map(t => txnRow(t)).join('');
}

// ---- Transactions ----

function txnRow(t, showBalance) {
  const isPos = t.amount > 0;
  const date = new Date(t.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const amt = `${isPos ? '+' : ''}$${Math.abs(t.amount).toLocaleString('en-US', {minimumFractionDigits: 2})}`;
  let row = `<tr>
    <td>${date}</td>
    <td>${t.account_name || t.account_id}</td>
    <td><span class="txn-type ${t.type}">${t.type.replace(/_/g, ' ')}</span></td>
    <td>${t.description || '-'}</td>
    <td class="txn-amount ${isPos ? 'positive' : 'negative'}">${amt}</td>`;
  if (showBalance) row += `<td>$${(t.balance_after || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>`;
  return row + '</tr>';
}

async function loadAllTransactions() {
  const txns = await api(`/api/customers/${currentCustomer}/transactions?limit=50`);
  document.getElementById('allTxns').innerHTML = txns.length
    ? txns.map(t => txnRow(t, true)).join('')
    : '<tr><td colspan="6" class="empty-state">No transactions</td></tr>';
  // Also load admin txns view
  document.getElementById('adminTxns').innerHTML = txns.length
    ? txns.map(t => txnRow(t, true)).join('')
    : '<tr><td colspan="6" class="empty-state">No transactions</td></tr>';
}

// ---- Credit Info (Customer Portal) ----

async function loadCreditInfo() {
  const c = await api(`/api/customers/${currentCustomer}`);
  const dti = ((c.monthly_debt_payments * 12) / c.annual_income * 100).toFixed(0);
  const infoHtml = `
    <div class="credit-stat"><div class="value">${c.credit_score}</div><div class="label">Credit Score</div></div>
    <div class="credit-stat"><div class="value">$${c.current_credit_limit.toLocaleString()}</div><div class="label">Credit Limit</div></div>
    <div class="credit-stat"><div class="value">${(c.utilization_rate * 100).toFixed(0)}%</div><div class="label">Utilization</div></div>
    <div class="credit-stat"><div class="value">${dti}%</div><div class="label">DTI Ratio</div></div>
    <div class="credit-stat"><div class="value">$${c.annual_income.toLocaleString()}</div><div class="label">Annual Income</div></div>
    <div class="credit-stat"><div class="value">${c.account_age_months} mo</div><div class="label">Account Age</div></div>`;
  document.getElementById('creditInfoCustomer').innerHTML = infoHtml;

  const history = await api(`/api/customers/${currentCustomer}/credit-history`);
  const histHtml = history.length
    ? history.map(h => {
        const date = new Date(h.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        return `<tr><td>${date}</td><td>$${h.old_limit.toLocaleString()}</td><td>$${h.new_limit.toLocaleString()}</td><td>${h.reason || '-'}</td><td><span class="txn-type">${h.status}</span></td></tr>`;
      }).join('')
    : '<tr><td colspan="5" class="empty-state">No credit limit changes</td></tr>';
  document.getElementById('creditHistoryCustomer').innerHTML = histHtml;
}

// ---- Approvals (Admin Portal) ----

async function loadApprovals() {
  const approvals = await api(`/api/customers/${currentCustomer}/approvals`);
  document.getElementById('approvalBadge').textContent = approvals.length > 0 ? `(${approvals.length})` : '';
  const list = document.getElementById('approvalsList');
  if (!approvals.length) { list.innerHTML = '<div class="empty-state">No pending approvals</div>'; return; }
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
      </div>`;
  }).join('');
}

async function handleApproval(id, action) {
  try {
    await api(`/api/approvals/${id}`, { method: 'POST', body: JSON.stringify({ action }) });
    toast(`Transaction ${action === 'approve' ? 'approved' : 'denied'}`, action === 'approve' ? 'success' : 'error');
    await refreshAll();
  } catch (err) { toast(err.message, 'error'); }
}

// ---- Transfer (Admin Portal) ----

function loadTransferForm() {
  const nonCredit = accounts.filter(a => a.type !== 'credit');
  document.getElementById('fromAccount').innerHTML = nonCredit.map(a =>
    `<option value="${a.id}">${a.name} ($${a.balance.toLocaleString('en-US', {minimumFractionDigits:2})})</option>`
  ).join('');
  document.getElementById('toAccount').innerHTML = accounts.map(a =>
    `<option value="${a.id}">${a.name} (${a.id})</option>`
  ).join('');
  loadTransferHistory();
}

async function loadTransferHistory() {
  const txns = await api(`/api/customers/${currentCustomer}/transactions?limit=20`);
  const transfers = txns.filter(t => t.type === 'TRANSFER');
  document.getElementById('transferHistory').innerHTML = transfers.length
    ? transfers.map(t => txnRow(t)).join('')
    : '<tr><td colspan="5" class="empty-state">No transfers yet</td></tr>';
}

async function submitTransfer(e) {
  e.preventDefault();
  const btn = document.getElementById('transferBtn');
  btn.disabled = true; btn.textContent = 'Processing...';
  try {
    await api('/api/transfer', {
      method: 'POST',
      body: JSON.stringify({
        from_account_id: document.getElementById('fromAccount').value,
        to_account_id: document.getElementById('toAccount').value,
        amount: parseFloat(document.getElementById('transferAmount').value),
        description: document.getElementById('transferDesc').value || 'Transfer',
      }),
    });
    toast('Transfer completed!', 'success');
    document.getElementById('transferAmount').value = '';
    document.getElementById('transferDesc').value = '';
    await refreshAll();
  } catch (err) { toast(err.message, 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Transfer Funds'; }
}

// ---- Audit Log (Admin Portal) ----

async function loadAuditLog() {
  const history = await api(`/api/customers/${currentCustomer}/credit-history`);
  const c = await api(`/api/customers/${currentCustomer}`);
  document.getElementById('auditLog').innerHTML = history.length
    ? history.map(h => {
        const date = new Date(h.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        return `<tr><td>${date}</td><td>${c.name}</td><td>$${h.old_limit.toLocaleString()}</td><td>$${h.new_limit.toLocaleString()}</td><td>${h.reason || '-'}</td><td>${h.status}</td><td>${h.assessed_by || '-'}</td></tr>`;
      }).join('')
    : '<tr><td colspan="7" class="empty-state">No credit limit changes recorded</td></tr>';
}

// ---- AI Agent Chat (Admin Portal) ----

async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;
  const messages = document.getElementById('chatMessages');
  const sendBtn = document.getElementById('chatSendBtn');

  messages.innerHTML += `<div class="chat-msg user">${escapeHtml(msg)}</div>`;
  input.value = '';
  sendBtn.disabled = true;
  sendBtn.innerHTML = '<span class="loading"></span>';

  const thinkingId = 'thinking-' + Date.now();
  messages.innerHTML += `<div class="chat-msg agent" id="${thinkingId}" style="opacity:0.6">Analyzing your request...</div>`;
  messages.scrollTop = messages.scrollHeight;

  try {
    const result = await api('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ customer_id: currentCustomer, message: `Customer ID: ${currentCustomer}. ${msg}` }),
    });
    document.getElementById(thinkingId).remove();
    messages.innerHTML += `<div class="chat-msg agent">${escapeHtml(result.response)}</div>`;
    await refreshAll();  // Refresh data in case agent made changes
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
