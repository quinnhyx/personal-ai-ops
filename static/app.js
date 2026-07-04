let emails = [];
let selectedId = null;
let statusFilter = 'all';
let categoryFilter = 'all';
let tabFilter = 'all';
let draftState = {};

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
  bindEvents();
  await loadHealth();
  await loadEmails();
  pollProgress();
}

function bindEvents() {
  document.getElementById('syncBtn').addEventListener('click', refreshEmails);
  document.getElementById('refreshBtn').addEventListener('click', refreshEmails);
  document.getElementById('categorySelect').addEventListener('change', event => {
    categoryFilter = event.target.value;
    render();
  });
  document.getElementById('sortSelect').addEventListener('change', renderEmailList);

  document.querySelectorAll('.nav-item[data-filter]').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(button => button.classList.remove('active'));
      item.classList.add('active');
      statusFilter = item.dataset.filter;
      render();
    });
  });

  document.querySelectorAll('.tab-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.tab-chip').forEach(button => button.classList.remove('active'));
      chip.classList.add('active');
      tabFilter = chip.dataset.tab;
      renderEmailList();
    });
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

async function refreshEmails() {
  document.getElementById('lastSync').textContent = 'Syncing Gmail...';
  await fetch('/refresh', { method: 'POST' });
  pollProgress();
}

async function loadEmails() {
  const response = await fetch('/emails');
  const data = await response.json();
  if (data.loading) return;
  emails = Array.isArray(data) ? data : [];
  if (!selectedId && emails.length) selectedId = emails[0].id;
  render();
}

function render() {
  renderCounts();
  renderCategorySelect();
  renderCategoryCard();
  renderEmailList();
  renderDetail();
}

function renderCounts() {
  const total = emails.length;
  const needs = countStatus('needs_reply');
  const pending = countStatus('pending_review');
  const drafts = countStatus('draft_created');
  const noReply = countStatus('no_reply_needed');

  setText('statTotal', total);
  setText('statNeeds', needs);
  setText('statPending', pending);
  setText('statDrafts', drafts);
  setText('statNo', noReply);
  setText('navAll', total);
  setText('navEmails', total);
  setText('navNeeds', needs);
  setText('navPending', pending);
  setText('navDrafts', drafts);
  setText('navNo', noReply);
  setText('navAlerts', emails.filter(email => email.category === 'Alert').length);
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
  return emails
    .filter(email => statusFilter === 'all' || email.reply_status === statusFilter)
    .filter(email => categoryFilter === 'all' || email.category === categoryFilter)
    .filter(email => tabFilter === 'all' || email.category === tabFilter)
    .sort((a, b) => {
      const sort = document.getElementById('sortSelect').value;
      if (sort === 'confidence') return (b.reply_confidence || 0) - (a.reply_confidence || 0);
      return new Date(b.timestamp || 0) - new Date(a.timestamp || 0);
    });
}

function renderEmailList() {
  const list = document.getElementById('emailList');
  const visible = viewEmails();
  setText('panelCount', `${visible.length} emails`);
  if (!visible.length) {
    list.innerHTML = '<div class="empty-state">No emails match this view.</div>';
    return;
  }
  list.innerHTML = visible.map(email => emailCard(email)).join('');
  list.querySelectorAll('.email-card').forEach(card => {
    card.addEventListener('click', event => {
      if (event.target.closest('button')) return;
      selectedId = card.dataset.id;
      render();
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
  const draftUrl = getDraftUrl(email.id) || email.draft_url;
  return `
    <article class="email-card ${selected}" data-id="${escapeAttr(email.id)}">
      <input class="email-check" type="checkbox" aria-label="Select email">
      <div class="avatar">${avatarText(email.sender)}</div>
      <div>
        <div class="email-from">${escapeHtml(email.sender)}</div>
        <div class="email-subject">${escapeHtml(email.title)}</div>
        <div class="email-snippet">${escapeHtml(email.snippet)}</div>
      </div>
      <span class="badge ${className(email.category)}">${escapeHtml(email.category || 'Other')}</span>
      <div class="email-time">${formatDate(email.timestamp)}</div>
      ${confidenceMarkup(email.reply_confidence || 0)}
      <div class="email-actions">
        <button class="list-button" data-action="draft" data-id="${escapeAttr(email.id)}">Generate Draft</button>
        <button class="list-button gmail-button" data-action="open" data-id="${escapeAttr(email.id)}" ${draftUrl ? '' : 'disabled'}>Open in Gmail</button>
      </div>
    </article>
  `;
}

function renderDetail() {
  const panel = document.getElementById('detailPanel');
  const email = emails.find(item => item.id === selectedId);
  if (!email) {
    panel.innerHTML = '<div class="empty-state">Select an email to inspect details and generate a Gmail draft.</div>';
    return;
  }

  const state = draftState[email.id] || {};
  const draftText = state.draft_text || email.draft_text || '';
  const draftUrl = state.draft_url || email.draft_url || '';
  const replyState = state.status || (draftText ? 'Generated' : 'Not generated');

  panel.innerHTML = `
    <div class="card-heading">
      <h2>${escapeHtml(email.title || 'No subject')}</h2>
      <span class="badge ${email.reply_status}">${statusLabel[email.reply_status] || 'No Reply'}</span>
    </div>
    <div class="detail-grid">
      ${detailField('From', email.sender)}
      ${detailField('To', email.to || 'Me')}
      ${detailField('Date', formatDate(email.timestamp))}
      ${detailField('Category', `<span class="badge ${className(email.category)}">${escapeHtml(email.category || 'Other')}</span>`, true)}
      ${detailField('AI Confidence', `${email.reply_confidence || 0}%`)}
      ${detailField('Reason', email.reply_reason || 'No reason available.')}
    </div>
    <h3>Original Email</h3>
    <div class="message-body">${escapeHtml(email.snippet || 'No email preview available.')}</div>
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
  `;
}

function detailField(label, value, isHtml = false) {
  return `<div class="detail-field"><span>${label}</span><b>${isHtml ? value : escapeHtml(value || '')}</b></div>`;
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
