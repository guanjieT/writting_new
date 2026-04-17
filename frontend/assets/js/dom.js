export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function formatDate(value) {
  if (!value) {
    return '未记录';
  }
  try {
    return new Date(value).toLocaleString('zh-CN');
  } catch {
    return String(value);
  }
}

export function summarizeList(items, fallback = '无') {
  return Array.isArray(items) && items.length ? items.join('、') : fallback;
}

export function truncate(value, length = 140) {
  const text = String(value ?? '').trim();
  if (text.length <= length) {
    return text || '暂无内容';
  }
  return `${text.slice(0, length)}…`;
}

export function nl2br(value) {
  return escapeHtml(value ?? '').replace(/\n/g, '<br />');
}

export function renderNotice(container, message, type = 'info') {
  container.innerHTML = `<div class="notice ${type}">${escapeHtml(message)}</div>`;
}

export function renderEmpty(container, message) {
  container.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

export function renderJsonPreview(value) {
  return `<pre class="json-preview">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

export function badge(text, tone = 'soft') {
  return `<span class="chip ${tone}">${escapeHtml(text)}</span>`;
}
