let emails = [];
let selectedId = null;
let statusFilter = 'all';
let categoryFilter = 'all';
let tabFilter = 'all';
let draftState = {};
let emailDetails = new Map();
let detailLoadingId = null;
let expandedThreadMessages = new Set();
let inboxAnalysis = { summary: { total: 0, reply: 0, action: 0, read: 0, ignore: 0 }, groups: {} };
let activeDecision = null;
let currentView = 'overview';
let dateRange = '7d';
let isSyncing = false;
let activeAccount = null;

const statusLabel = {
  needs_reply: 'Needs Reply',
  pending_review: 'Pending',
  no_reply_needed: 'No Reply',
  draft_created: 'Draft Created',
};

const categoryColors = {
  Job: '#2563eb',
  'Social Media': '#06b6d4',
  Newsletter: '#f97316',
  Shopping: '#d1d50d',
  Other: '#94a3b8',
  Finance: '#7c3aed',
  Personal: '#ec4899',
  Education: '#9333ea',
  Alert: '#ef4444',
  Travel: '#0f766e',
};

document.addEventListener('DOMContentLoaded', init);

async function init() {
  const loginSuccess = new URLSearchParams(window.location.search).get('login_success') === '1';
  const connected = await checkAccountStatus(loginSuccess);
  if (!connected) return;
  const rangeSelect = document.getElementById('dateRange');
  dateRange = rangeSelect?.value || '7d';
  bindEvents();
  await loadHealth();
  await loadEmails();
  if (loginSuccess) {
    console.log('[Auth] login success, starting Gmail sync');
    try {
      await syncGmail({ auto: true });
    } finally {
      clearLoginSuccessParam();
    }
  } else {
    pollProgress();
  }
}

async function checkAccountStatus(loginSuccess = false) {
  console.log('[Auth] checking account status');
  try {
    const response = await fetch('/api/accounts/status');
    if (!response.ok) throw new Error(`Account status check failed (${response.status})`);
    const status = await response.json();
    if (!status.connected) {
      if (loginSuccess) {
        throw new Error('Google OAuth completed but no connected Gmail account was found.');
      }
      console.log('[Auth] connected=false, redirecting to OAuth');
      window.location.replace('/auth/google/start');
      return false;
    }
    console.log('[Auth] connected=true');
    activeAccount = status.active_account || null;
    updateAccountDisplay();
    document.body.classList.remove('auth-pending', 'auth-error');
    return true;
  } catch (error) {
    console.error(`[Auth] status check failed: ${error.message || error}`);
    const gate = document.getElementById('authGate');
    if (gate) gate.textContent = 'Unable to check Gmail connection.';
    document.body.classList.remove('auth-pending');
    document.body.classList.add('auth-error');
    return false;
  }
}

function updateAccountDisplay() {
  const avatar = document.getElementById('accountAvatar');
  if (avatar) avatar.textContent = activeAccount?.email?.charAt(0)?.toUpperCase() || '';
}

async function disconnectGmail() {
  const accountId = activeAccount?.id;
  if (accountId) {
    const response = await fetch(`/api/accounts/${encodeURIComponent(accountId)}/disconnect`, { method: 'POST' });
    if (!response.ok) throw new Error(`Gmail disconnect failed (${response.status})`);
  }
  activeAccount = null;
  emails = [];
  inboxAnalysis = { summary: { total: 0, reply: 0, action: 0, read: 0, ignore: 0 }, groups: {} };
  emailDetails.clear();
  selectedId = null;
  updateAccountDisplay();
  render();
  window.location.replace('/auth/google/start');
}

function bindEvents() {
  document.getElementById('syncBtn').addEventListener('click', () => syncGmail());
  document.getElementById('refreshBtn').addEventListener('click', loadEmails);
  document.getElementById('dateRange').addEventListener('change', event => {
    dateRange = event.target.value;
    loadEmails();
  });
  document.getElementById('categorySelect').addEventListener('change', event => {
    categoryFilter = event.target.value;
    render();
  });

  document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(button => button.classList.remove('active'));
      item.classList.add('active');
      currentView = item.dataset.view;
      activeDecision = currentView === 'overview' ? null : currentView;
      if (currentView === 'emails') activeDecision = 'all';
      render();
    });
  });

  document.querySelectorAll('.decision-card').forEach(card => {
    card.addEventListener('click', () => {
      activeDecision = card.dataset.decision;
      currentView = activeDecision;
      render();
    });
  });
  document.getElementById('closeDecision').addEventListener('click', () => {
    activeDecision = null;
    currentView = 'overview';
    selectedId = null;
    render();
  });
}

async function loadHealth() {
  try {
    const response = await fetch('/health');
    const health = await response.json();
    const model = health.llm_backend === 'ollama' ? 'Ollama (qwen3:8b)' : health.llm_backend;
    document.getElementById('ollamaStatus').textContent = model;
    document.getElementById('modelName').textContent = 'qwen3:8b';
  } catch {
    document.getElementById('ollamaStatus').textContent = 'Ollama status unknown';
  }
}

async function pollProgress() {
  if (isSyncing) return;
  try {
    const response = await fetch('/progress');
    const progress = await response.json();
    if (progress.loading) {
      document.getElementById('lastSync').textContent = `Syncing Gmail: ${progress.progress || 0}%`;
      setTimeout(pollProgress, 1000);
      return;
    }
    document.getElementById('lastSync').textContent = progress.error ? 'Last sync: Gmail unavailable' : `Last sync: ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    await loadEmails();
  } catch {
    document.getElementById('lastSync').textContent = 'Last sync: offline';
  }
}

async function syncGmail(options = {}) {
  if (isSyncing) return false;
  isSyncing = true;
  const syncButton = document.getElementById('syncBtn');
  const refreshButton = document.getElementById('refreshBtn');
  syncButton.disabled = true;
  refreshButton.disabled = true;
  emailDetails.clear();
  expandedThreadMessages.clear();
  detailLoadingId = null;
  console.log('[Sync] started');
  document.getElementById('lastSync').textContent = 'Syncing Gmail...';
  setText('analysisCaption', 'Syncing Gmail...');
  try {
    const response = await fetch('/api/gmail/sync', { method: 'POST' });
    const result = await response.json();
    if (!response.ok || result.error) {
      throw new Error(result.error || `Gmail sync failed (${response.status})`);
    }
    console.log(`[Sync] completed sync_count=${result.sync_count || 0} failed_count=${result.failed_count || 0}`);
    document.getElementById('lastSync').textContent = result.last_sync_at
      ? `Last sync: ${formatDate(result.last_sync_at)}`
      : 'Last sync: completed';
    await loadEmails();
    return true;
  } catch (error) {
    console.error(`[Sync] failed: ${error.message || error}`);
    document.getElementById('lastSync').textContent = 'Last sync: Gmail sync failed';
    if (options.auto) await loadEmails();
    setText('analysisCaption', 'Gmail sync failed. Showing cached emails.');
    return false;
  } finally {
    isSyncing = false;
    syncButton.disabled = false;
    refreshButton.disabled = false;
  }
}

function clearLoginSuccessParam() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has('login_success')) return;
  url.searchParams.delete('login_success');
  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  history.replaceState({}, document.title, nextUrl || '/');
}

async function loadEmails() {
  const button = document.getElementById('refreshBtn');
  button.disabled = true;
  button.textContent = 'Analyzing...';
  console.log(`[Inbox] loading range=${dateRange}`);
  try {
    const response = await fetch(`/api/emails?range=${encodeURIComponent(dateRange)}`);
    if (!response.ok) throw new Error(`Email load failed (${response.status})`);
    const result = await response.json();
    emails = result.emails || [];
    console.log(`[Inbox] received emails=${emails.length}`);
    inboxAnalysis = buildInboxAnalysis(emails, result.range || dateRange, result.range_label || dateRange);
    emailDetails.clear();
    expandedThreadMessages.clear();
    selectedId = null;
    setText('analysisCaption', `Showing ${inboxAnalysis.range_label || dateRange} from SQLite cache.`);
    render();
  } catch (error) {
    setText('analysisCaption', `Analysis failed: ${error.message}`);
  } finally {
    button.disabled = isSyncing;
    button.textContent = 'Refresh';
  }
}

function buildInboxAnalysis(items, range, rangeLabel) {
  const groups = { reply: [], action: [], read: [], ignore: [] };
  items.forEach(email => {
    const key = decisionKey(email);
    groups[key].push(email);
  });
  const summary = {
    total: items.length,
    reply: groups.reply.length,
    action: groups.action.length,
    read: groups.read.length,
    ignore: groups.ignore.length,
  };
  return { range, range_label: rangeLabel, summary, groups };
}

function decisionKey(email) {
  const label = String(email.decision_label || email.suggested_next_step || '').toLowerCase();
  if (label.includes('reply')) return 'reply';
  if (label.includes('action') || label.includes('complete')) return 'action';
  if (label.includes('ignore') || label.includes('archive')) return 'ignore';
  if (label.includes('read')) return 'read';
  if (email.reply_status === 'needs_reply' || email.reply_status === 'draft_created') return 'reply';
  return 'read';
}

function render() {
  renderCounts();
  renderCategorySelect();
  renderEmailList();
  const workspace = document.getElementById('analysisWorkspace');
  workspace.classList.toggle('hidden', !activeDecision);
  document.getElementById('decisionGrid').classList.toggle('compact', Boolean(activeDecision));
  document.querySelectorAll('.decision-card').forEach(card => {
    card.classList.toggle('selected', card.dataset.decision === activeDecision);
  });
  if (!selectedId) document.getElementById('detailPanel').classList.add('hidden');
  if (selectedId) renderDetail();
}

function renderCounts() {
  const summary = inboxAnalysis.summary || {};
  setText('analysisTotal', `${summary.total || 0} analyzed`);
  setText('decisionReply', summary.reply || 0);
  setText('decisionAction', summary.action || 0);
  setText('decisionRead', summary.read || 0);
  setText('decisionIgnore', summary.ignore || 0);
  setText('navAll', summary.total || 0);
  setText('navEmails', summary.total || 0);
  setText('navNeeds', summary.reply || 0);
  setText('navPending', summary.action || 0);
  setText('navDrafts', summary.read || 0);
  setText('navNo', summary.ignore || 0);
}

function countStatus(status) {
  return emails.filter(email => email.reply_status === status).length;
}

function renderCategorySelect() {
  const select = document.getElementById('categorySelect');
  const categories = ['all', ...new Set(emails.map(email => email.category || 'Other'))];
  select.innerHTML = categories.map(category => `<option value="${escapeAttr(category)}">${category === 'all' ? 'Categories: All' : category}</option>`).join('');
  select.value = categoryFilter;
}

function renderCategoryCard() {
  const counts = {};
  emails.forEach(email => counts[email.category || 'Other'] = (counts[email.category || 'Other'] || 0) + 1);
  setText('donutTotal', emails.length);
  const list = document.getElementById('categoryList');
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  list.innerHTML = rows.map(([category, count]) => {
    const percent = emails.length ? Math.round(count / emails.length * 100) : 0;
    return `
      <div class="category-row">
        <span class="category-dot" style="background:${categoryColors[category] || '#94a3b8'}"></span>
        <span>${escapeHtml(category)}</span>
        <span>${count} (${percent}%)</span>
      </div>
    `;
  }).join('') || '<div class="empty-state">No category data yet.</div>';
}

function viewEmails() {
  const source = activeDecision === 'all'
    ? emails
    : (inboxAnalysis.groups?.[activeDecision] || []);
  return source
    .filter(email => categoryFilter === 'all' || email.category === categoryFilter)
    .sort((a, b) => (b.priority || 0) - (a.priority || 0) || (b.confidence || 0) - (a.confidence || 0));
}

function renderEmailList() {
  const list = document.getElementById('emailList');
  const visible = viewEmails();
  setText('panelCount', `${visible.length} emails`);
  setText('decisionPanelTitle', activeDecision === 'all' ? 'All analyzed email' : `${titleCase(activeDecision)} decisions`);
  if (!visible.length) {
    list.innerHTML = '<div class="empty-state">No emails match this view.</div>';
    return;
  }
  list.innerHTML = visible.map(email => emailCard(email)).join('');
  list.querySelectorAll('.email-card').forEach(card => {
    card.addEventListener('click', event => {
      if (event.target.closest('button')) return;
      selectedId = card.dataset.id;
      renderEmailList();
      document.getElementById('detailPanel').classList.remove('hidden');
      renderDetail();
      loadEmailDetail(selectedId);
    });
  });
  list.querySelectorAll('[data-action="draft"]').forEach(button => {
    button.addEventListener('click', event => {
      event.stopPropagation();
      createDraft(button.dataset.id);
    });
  });
  list.querySelectorAll('[data-action="open"]').forEach(button => {
    button.addEventListener('click', event => {
      event.stopPropagation();
      openDraft(button.dataset.id);
    });
  });
}

function emailCard(email) {
  const selected = email.id === selectedId ? 'selected' : '';
  return `
    <article class="email-card decision-email ${selected}" data-id="${escapeAttr(email.id)}">
      <div class="avatar">${avatarText(email.sender)}</div>
      <div class="decision-email-copy">
        <div class="email-from">${escapeHtml(email.sender)}</div>
        <div class="email-subject">${escapeHtml(email.title)}</div>
        <div class="email-reason">${escapeHtml(email.reason || email.decision_reason)}</div>
      </div>
      <span class="badge ${className(email.category)}">${escapeHtml(email.category || 'Other')}</span>
      <div class="priority" title="Priority ${email.priority || 3} of 5">${priorityStars(email.priority || 3)}</div>
      ${confidenceMarkup(email.confidence || email.reply_confidence || 0)}
      <span class="next-step">${escapeHtml(email.suggested_next_step || 'Read')}</span>
    </article>
  `;
}

function renderDetail() {
  const panel = document.getElementById('detailPanel');
  const email = emailDetails.get(selectedId) || emails.find(item => item.id === selectedId);
  if (!email) {
    panel.innerHTML = '<div class="empty-state">Select an email to inspect details and generate a Gmail draft.</div>';
    return;
  }
  if (detailLoadingId === selectedId && !emailDetails.has(selectedId)) {
    panel.innerHTML = '<div class="empty-state">Loading full email and thread...</div>';
    return;
  }

  const state = draftState[email.id] || {};
  const draftText = state.draft_text || email.draft_text || '';
  const draftUrl = state.draft_url || email.draft_url || '';
  const replyState = state.status || (draftText ? 'Generated' : 'Not generated');
  const thread = Array.isArray(email.thread) && email.thread.length ? email.thread : [email];

  panel.innerHTML = `
    <div class="card-heading">
      <h2>${escapeHtml(email.title || 'No subject')}</h2>
      <div class="detail-top-actions">
        <span class="badge ${email.reply_status}">${statusLabel[email.reply_status] || 'No Reply'}</span>
        <button class="secondary-button compact-button" onclick="openEmailInGmail('${escapeAttr(email.id)}')">Open in Gmail</button>
      </div>
    </div>
    <div class="open-email-layout">
      <section class="email-body-card">
        <div class="detail-grid">
          ${detailField('From', email.sender)}
          ${detailField('To', email.to || 'Me')}
          ${detailField('Date', formatDate(email.timestamp))}
          ${detailField('Thread', `${thread.length} message${thread.length === 1 ? '' : 's'}`)}
        </div>
        <h3>Full Email Body</h3>
        ${renderEmailBody(email)}
        <h3>Thread</h3>
        ${renderThreadViewer(thread, email.id)}
      </section>
      <section class="ai-analysis-card">
        <h3>AI Analysis</h3>
        <div class="detail-grid single-column">
          ${detailField('Category', `<span class="badge ${className(email.category)}">${escapeHtml(email.category || 'Other')}</span>`, true)}
          ${detailField('Confidence', `${email.reply_confidence || 0}%`)}
          ${detailField('Reason', email.reply_reason || 'No reason available.')}
        </div>
        <section class="ai-reply-card">
          <div class="card-heading"><h2>AI Suggested Reply</h2><span class="reply-state">${escapeHtml(replyState)}</span></div>
          <div class="reply-body">${escapeHtml(draftText || 'Generate a Gmail draft to preview the AI reply here. Nothing will be sent automatically.')}</div>
          <div class="reply-actions">
            <button class="primary-button" onclick="createDraft('${escapeAttr(email.id)}')">Generate Gmail Draft</button>
            <button class="secondary-button" onclick="regenerateReply('${escapeAttr(email.id)}')">Regenerate</button>
            <button class="secondary-button" onclick="copyReply('${escapeAttr(email.id)}')" ${draftText ? '' : 'disabled'}>Copy</button>
            <button class="secondary-button" onclick="openDraft('${escapeAttr(email.id)}')" ${draftUrl ? '' : 'disabled'}>Open in Gmail Draft</button>
          </div>
        </section>
      </section>
    </div>
  `;
}

function detailField(label, value, isHtml = false) {
  return `<div class="detail-field"><span>${label}</span><b>${isHtml ? value : escapeHtml(value || '')}</b></div>`;
}

function renderEmailBody(email) {
  const html = String(email.body_html || '').trim();
  const text = String(email.body_text || email.body || '').trim();
  if (html) {
    return `<div class="message-body html-body">${sanitizeHtml(html)}</div>`;
  }
  if (text) {
    return `<div class="message-body">${escapeHtml(text)}</div>`;
  }
  return '<div class="message-body empty-body">Body unavailable. Click Refresh to reload from provider.</div>';
}

function renderThreadViewer(thread, activeId) {
  const ordered = [...thread].sort((a, b) => new Date(a.timestamp || a.received_at || 0) - new Date(b.timestamp || b.received_at || 0));
  let previousSubject = '';
  const items = ordered.map(email => {
    const id = String(email.id);
    const subject = email.title || email.subject || 'No subject';
    const subjectChanged = normalizeSubject(subject) !== normalizeSubject(previousSubject);
    previousSubject = subject;
    return threadMessage(email, activeId, subjectChanged);
  }).join('');
  return `<div class="thread-viewer"><div class="thread-list">${items}</div></div>`;
}

function threadMessage(email, activeId, showSubject) {
  const id = String(email.id);
  const expanded = expandedThreadMessages.has(id);
  const body = plainTextBody(email);
  const preview = body || 'Body unavailable. Click Refresh to reload from provider.';
  const shouldCollapse = preview.length > 260;
  const visibleText = expanded || !shouldCollapse ? preview : `${preview.slice(0, 260).trim()}...`;
  return `
    <article class="thread-message ${id === String(activeId) ? 'active' : ''}">
      <div class="thread-meta">
        <b>${escapeHtml(email.sender || 'Unknown sender')}</b>
        <span>${formatDate(email.timestamp || email.received_at)}</span>
      </div>
      ${showSubject ? `<div class="thread-subject">${escapeHtml(email.title || email.subject || 'No subject')}</div>` : ''}
      <div class="thread-body">${escapeHtml(visibleText)}</div>
      ${shouldCollapse ? `<button class="thread-toggle" onclick="toggleThreadMessage('${escapeAttr(id)}')">${expanded ? 'Collapse' : 'Expand'}</button>` : ''}
    </article>
  `;
}

function toggleThreadMessage(id) {
  if (expandedThreadMessages.has(id)) {
    expandedThreadMessages.delete(id);
  } else {
    expandedThreadMessages.add(id);
  }
  renderDetail();
}

function plainTextBody(email) {
  const text = String(email.body_text || email.body || '').trim();
  if (text) return text;
  const html = String(email.body_html || '').trim();
  if (!html) return '';
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return (doc.body?.textContent || '').replace(/\s+/g, ' ').trim();
}

function normalizeSubject(subject) {
  return String(subject || '').toLowerCase().replace(/^(re|fw|fwd):\s*/g, '').trim();
}

async function loadEmailDetail(id) {
  if (!id) return;
  if (emailDetails.has(id)) {
    renderDetail();
    return;
  }
  detailLoadingId = id;
  renderDetail();
  try {
    const response = await fetch(`/api/emails/${encodeURIComponent(id)}`);
    const data = await response.json();
    if (!data.error) {
      emailDetails.set(id, data);
      const index = emails.findIndex(email => email.id === id);
      if (index >= 0) emails[index] = { ...emails[index], ...data };
    }
  } catch (error) {
    emailDetails.set(id, { ...(emails.find(email => email.id === id) || {}), body: `Failed to load full email: ${error}` });
  } finally {
    if (detailLoadingId === id) detailLoadingId = null;
    renderDetail();
  }
}

async function createDraft(id) {
  selectedId = id;
  draftState[id] = { status: 'Generating...', draft_text: '', draft_url: '' };
  render();
  try {
    const response = await fetch(`/api/emails/${encodeURIComponent(id)}/draft`, { method: 'POST' });
    const data = await response.json();
    draftState[id] = {
      status: data.status === 'draft_created' ? 'Gmail draft generated' : (data.message || 'Generated'),
      draft_text: data.draft_text || '',
      draft_url: data.draft_url || '',
    };
    await loadEmails();
  } catch (error) {
    draftState[id] = { status: `Failed: ${error}`, draft_text: '', draft_url: '' };
    renderDetail();
  }
}

async function regenerateReply(id) {
  selectedId = id;
  draftState[id] = { status: 'Generating...', draft_text: '', draft_url: '' };
  renderDetail();
  try {
    const response = await fetch(`/emails/${encodeURIComponent(id)}/generate-reply`, { method: 'POST' });
    const data = await response.json();
    draftState[id] = { status: 'Generated, not yet saved as Gmail draft', draft_text: data.draft_text || data.reply || '', draft_url: data.draft_url || '' };
    renderDetail();
  } catch (error) {
    draftState[id] = { status: `Failed: ${error}`, draft_text: '', draft_url: '' };
    renderDetail();
  }
}

async function copyReply(id) {
  const text = (draftState[id]?.draft_text) || emails.find(email => email.id === id)?.draft_text || '';
  if (!text) return;
  await navigator.clipboard.writeText(text);
  draftState[id] = { ...(draftState[id] || {}), status: 'Copied to clipboard' };
  renderDetail();
}

function openDraft(id) {
  const email = emails.find(item => item.id === id);
  const url = getDraftUrl(id) || email?.draft_url;
  if (url) window.open(url, '_blank', 'noopener');
}

function openEmailInGmail(id) {
  const email = emailDetails.get(id) || emails.find(item => item.id === id);
  const threadId = email?.gmail_thread_id || email?.provider_thread_id;
  const messageId = email?.gmail_message_id || email?.provider_message_id;
  const url = threadId
    ? `https://mail.google.com/mail/u/0/#inbox/${encodeURIComponent(threadId)}`
    : `https://mail.google.com/mail/u/0/#search/${encodeURIComponent(messageId || email?.title || '')}`;
  window.open(url, '_blank', 'noopener');
}

function getDraftUrl(id) {
  return draftState[id]?.draft_url || '';
}

function confidenceMarkup(value) {
  const level = value >= 70 ? 'high' : value >= 40 ? 'mid' : 'low';
  return `
    <div class="confidence">
      <span>${value}%</span>
      <span class="confidence-bar"><span class="confidence-fill ${level}" style="width:${Math.max(0, Math.min(100, value))}%"></span></span>
    </div>
  `;
}

function priorityStars(value) {
  const priority = Math.max(1, Math.min(5, Number(value) || 3));
  return `<span aria-label="Priority ${priority} of 5">${'★'.repeat(priority)}${'☆'.repeat(5 - priority)}</span>`;
}

function titleCase(value) {
  const text = String(value || '');
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

function className(value) {
  return String(value || 'Other').replace(/[^a-zA-Z]/g, '') || 'Other';
}

function avatarText(sender) {
  const clean = String(sender || 'AI').trim();
  return escapeHtml(clean.charAt(0).toUpperCase() || 'A');
}

function formatDate(value) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#096;');
}

function sanitizeHtml(html) {
  const allowedTags = new Set([
    'A', 'P', 'BR', 'STRONG', 'B', 'EM', 'I', 'U', 'UL', 'OL', 'LI', 'BLOCKQUOTE',
    'PRE', 'CODE', 'SPAN', 'DIV', 'TABLE', 'THEAD', 'TBODY', 'TR', 'TH', 'TD',
    'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'HR'
  ]);
  const discardTags = new Set(['STYLE', 'SCRIPT', 'HEAD', 'META', 'LINK', 'TITLE', 'NOSCRIPT']);
  const allowedAttrs = new Set(['href', 'title', 'alt', 'colspan', 'rowspan']);
  const template = document.createElement('template');
  template.innerHTML = html;

  [...template.content.querySelectorAll('*')].forEach(node => {
    if (discardTags.has(node.tagName)) {
      node.remove();
      return;
    }
    if (!allowedTags.has(node.tagName)) {
      node.replaceWith(document.createTextNode(node.textContent || ''));
      return;
    }
    [...node.attributes].forEach(attr => {
      const name = attr.name.toLowerCase();
      const value = attr.value || '';
      if (name.startsWith('on') || !allowedAttrs.has(name)) {
        node.removeAttribute(attr.name);
        return;
      }
      if (name === 'href' && !/^(https?:|mailto:|#)/i.test(value)) {
        node.removeAttribute(attr.name);
      }
    });
    if (node.tagName === 'A' && node.getAttribute('href')) {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer');
    }
  });

  return template.innerHTML;
}
