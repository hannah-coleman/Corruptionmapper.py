// Signal Ledger: Professional Evidence Management System
// Sophisticated relationship mapping with exculpatory evidence tracking

// The server rejects state-changing requests without this header, which cross-site pages cannot send.
const nativeFetch = window.fetch.bind(window);
window.fetch = (resource, options = {}) => {
  const method = (options.method || 'GET').toUpperCase();
  if (method === 'GET' || method === 'HEAD') return nativeFetch(resource, options);
  const headers = new Headers(options.headers || {});
  headers.set('X-Signal-Ledger', '1');
  return nativeFetch(resource, { ...options, headers });
};

let nodes = [];
let edges = [];
const graph = document.querySelector('#graph');
const detail = document.querySelector('#detail-content');
let lookup = Object.fromEntries(nodes.map(node => [node.id, node]));
let selected = null;
let liveEvidenceData = [];
let liveDiscrepancies = [];
let liveClaims = [];

function renderGraph() { 
  graph.innerHTML = ''; 
  if (!nodes.length) {
    const empty=document.createElementNS('http://www.w3.org/2000/svg','text');empty.setAttribute('x',380);empty.setAttribute('y',235);empty.setAttribute('text-anchor','middle');empty.setAttribute('class','node-label');empty.textContent='No entities yet. Add sourced entities from reviewed evidence.';graph.appendChild(empty);
    return;
  }
  edges.forEach(([from,to,status]) => { 
    const a=lookup[from], b=lookup[to]; 
    const line=document.createElementNS('http://www.w3.org/2000/svg','line'); 
    line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);line.setAttribute('class',`edge ${status==='lead'?'lead':''}`);graph.appendChild(line); 
  }); 
  nodes.forEach(node => { 
    const group=document.createElementNS('http://www.w3.org/2000/svg','g');group.setAttribute('class',`node ${node.status==='lead'?'lead':''} ${node.id===selected?'selected':''}`);group.dataset.id=node.id; 
    const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('cx',node.x);circle.setAttribute('cy',node.y);circle.setAttribute('r',node.id===selected?27:23); 
    const text=document.createElementNS('http://www.w3.org/2000/svg','text');text.setAttribute('x',node.x);text.setAttribute('y',node.y+43);text.setAttribute('text-anchor','middle');text.setAttribute('class','node-label');text.textContent=node.label;group.append(circle,text);group.addEventListener('click',()=>{selected=node.id;renderGraph();renderDetail(node);});graph.appendChild(group); 
  }); 
}

function renderDetail(node) { 
  if (!node) { detail.innerHTML='<div class="detail-body"><h3>Nothing selected</h3><p>The relationship graph is empty until sourced entities are added.</p></div>'; return; }
  detail.innerHTML=`<div class="detail-top"><span class="detail-type">${node.status==='lead'?'UNVERIFIED LEAD':'SOURCED RECORD'} · ${node.type.toUpperCase()}</span><h2 class="detail-title">${node.label}</h2><span class="detail-meta">Status: ${node.status==='lead'?'needs review':'sourced'}</span></div><div class="detail-body"><h3>Working description</h3><p>${node.summary}</p><div>${node.tags.map(tag=>`<span class="tag">${tag}</span>`).join('')}</div><h3 style="margin-top:23px">Evidence trail · ${node.sources.length}</h3>${node.sources.map(source=>`<div class="evidence-item"><strong>${source[0]}</strong><a href="#" title="Source URL">${source[1]}</a><small>${source[2]}</small></div>`).join('')}<button class="primary-button" data-action="add-evidence" style="width:100%;margin-top:12px">＋ Add evidence</button></div>`; 
}

renderGraph();renderDetail(lookup[selected]);

function renderGraphCounts() {
  const nodeCount = document.querySelector('#node-count');
  const edgeCount = document.querySelector('#edge-count');
  if (nodeCount) nodeCount.textContent = nodes.length;
  if (edgeCount) edgeCount.textContent = edges.length;
}

// Initialize modals and forms
function initModals() {
  const modal = document.getElementById('evidence-modal');
  const closeBtn = document.querySelector('.modal-close');
  
  if (!modal) return;
  
  closeBtn?.addEventListener('click', () => { modal.hidden = true; });
  window.addEventListener('click', (e) => { if (e.target === modal) modal.hidden = true; });
}

// Open evidence intake modal
function openEvidenceModal() {
  const modal = document.getElementById('evidence-modal');
  if (modal) modal.hidden = false;
}

// Submit evidence form
async function submitEvidenceForm(event) {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);
  const record = {
    title: formData.get('title') || 'Untitled evidence',
    url: formData.get('url') || '',
    summary: formData.get('summary') || '',
    kind: formData.get('kind') || 'primary-source',
    protection: formData.get('protection') || 'public',
    lane: formData.get('lane') || 'public-record',
    citation_page: formData.get('citation_page') || '',
    citation_section: formData.get('citation_section') || '',
    citation_excerpt: formData.get('citation_excerpt') || '',
    location_label: formData.get('location_label') || '',
    latitude: formData.get('latitude') || '',
    longitude: formData.get('longitude') || '',
    geographic_source_url: formData.get('geographic_source_url') || '',
    imagery_captured_at: formData.get('imagery_captured_at') || ''
  };
  
  try {
    const response = await fetch('/api/evidence', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(record)
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Evidence save failed');
    
    form.reset();
    document.getElementById('evidence-modal').hidden = true;
    alert(`Evidence saved: ${payload.record.title}`);
    refreshEvidenceTable();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

// Refresh evidence table from live API
async function refreshEvidenceTable() {
  try {
    const response = await fetch('/api/evidence-live');
    if (!response.ok) throw new Error('Failed to load evidence');
    liveEvidenceData = await response.json();
    renderEvidenceTable();
    renderCoverage();
  } catch (error) {
    console.error('Evidence refresh failed:', error);
  }
}

// Render evidence table
function markedExcerpt(text) {
  return escapeHtml(text).replace(/&lt;mark&gt;/g, '<mark>').replace(/&lt;\/mark&gt;/g, '</mark>');
}

function safeHref(url) {
  return /^https?:\/\//i.test(url) ? escapeHtml(url) : '#';
}

async function initSearch() {
  const input = document.getElementById('search');
  const agency = document.getElementById('search-agency');
  const kind = document.getElementById('search-kind');
  const results = document.getElementById('search-results');
  if (!input || !results) return;
  const catalog = await fetch('/api/source-catalog').then(r => r.ok ? r.json() : []);
  catalog.filter(item => item.hosts && item.hosts.length).forEach(item => agency.append(new Option(item.label, item.id)));
  let timer;
  let latest = 0;
  const run = async () => {
    const term = input.value.trim();
    if (term.length < 2) { results.hidden = true; return; }
    const ticket = ++latest;
    const params = new URLSearchParams({ q: term });
    if (agency.value) params.set('agency', agency.value);
    if (kind.value) params.set('kind', kind.value);
    const unfiltered = !agency.value && !kind.value;
    const [docResponse, recordResponse] = await Promise.all([
      fetch(`/api/search-text?${params}`),
      unfiltered ? fetch(`/api/search?q=${encodeURIComponent(term)}`) : Promise.resolve(null)
    ]);
    if (ticket !== latest) return;
    const docs = docResponse.ok ? await docResponse.json() : [];
    const records = recordResponse && recordResponse.ok ? await recordResponse.json() : [];
    results.hidden = false;
    results.innerHTML = `
      <h3>Captured pages and documents · ${docs.length}</h3>
      ${docs.map(doc => `<article class="search-hit"><a href="${safeHref(doc.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(doc.title || doc.url)}</a>
        <small>${escapeHtml(doc.url)} · ${doc.content_type === 'application/pdf' ? 'PDF' : 'Web page'} · captured ${escapeHtml((doc.captured_at || '').slice(0, 10))} · SHA-256 ${escapeHtml((doc.sha256 || '').slice(0, 12))}</small>
        <p>${markedExcerpt(doc.excerpt || '')}</p></article>`).join('') || '<p>No captured pages match. Absence here is not absence in the public record: consider a records request.</p>'}
      ${unfiltered ? `<h3>Casefile records · ${records.length}</h3>${records.map(item => `<article class="search-hit"><strong>${escapeHtml(item.title)}</strong> <small>${escapeHtml(item.result_type)}</small><p>${escapeHtml(item.detail || '')}</p></article>`).join('') || '<p>No casefile records match.</p>'}` : ''}`;
  };
  const schedule = () => { clearTimeout(timer); timer = setTimeout(() => run().catch(error => console.error('Search failed:', error)), 250); };
  input.addEventListener('input', schedule);
  agency.addEventListener('change', schedule);
  kind.addEventListener('change', schedule);
}

function renderCoverage() {
  const total = liveEvidenceData.length;
  const cited = liveEvidenceData.filter(item => item.url && (item.captured_at || item.recorded_at)).length;
  const percent = total ? Math.round((cited / total) * 100) : 0;
  const set = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
  set('coverage-percent', `${percent}%`);
  set('coverage-headline', total ? (percent === 100 ? 'All records cited' : 'Citations incomplete') : 'No evidence yet');
  set('coverage-detail', total ? `${cited} of ${total} records have a source URL and capture date.` : 'Preserve or collect a source to begin.');
  const counts = { primary: 0, secondary: 0, lead: 0 };
  liveEvidenceData.forEach(item => { const kind = String(item.kind || ''); if (kind.includes('primary')) counts.primary++; else if (kind.includes('secondary')) counts.secondary++; else counts.lead++; });
  Object.entries(counts).forEach(([key, value]) => {
    set(`coverage-${key}-count`, value);
    const bar = document.getElementById(`coverage-${key}-bar`);
    if (bar) bar.style.width = `${total ? Math.round((value / total) * 100) : 0}%`;
  });
}

function renderEvidenceTable() {
  const tbody = document.querySelector('#evidence-view tbody');
  if (!tbody) return;
  
  if (!liveEvidenceData.length) {
    tbody.innerHTML = '<tr><td colspan="5">No evidence records yet. Add your first source to begin.</td></tr>';
    return;
  }
  
  tbody.innerHTML = liveEvidenceData.map((item, idx) => `
    <tr>
      <td>
        <strong>${item.title || 'Untitled'}</strong>
        <small>${item.url || 'no url'}</small>
        <small>Record ID: ${item.id}</small>
        ${item.sha256 ? `<small>SHA-256: ${item.sha256}</small>` : ''}
        ${(item.citation_page || item.citation_section || item.citation_excerpt) ? `<small>Citation: ${escapeHtml([item.citation_page, item.citation_section, item.citation_excerpt].filter(Boolean).join(' · '))}</small>` : ''}
        ${item.location_label ? `<small>Geography: ${escapeHtml(item.location_label)}</small>` : ''}
        ${(item.latitude !== '' && item.longitude !== '' && item.latitude != null && item.longitude != null) ? `<small><a href="https://earth.google.com/web/search/${encodeURIComponent(`${item.latitude},${item.longitude}`)}" target="_blank" rel="noopener noreferrer">Open coordinates in Google Earth</a></small>` : ''}
      </td>
      <td>${(item.kind || 'manual').replace(/-/g, ' ')}</td>
      <td>${new Date().toISOString().split('T')[0]}</td>
      <td><span class="table-status sourced">${item.protection || 'public'}</span></td>
      <td><span class="tag">${item.lane || 'review'}</span></td>
    </tr>
  `).join('');
  populateClaimEvidenceOptions();
}

function populateClaimEvidenceOptions() {
  const select = document.getElementById('claim-sources');
  if (!select) return;
  select.innerHTML = liveEvidenceData.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.title || 'Untitled evidence')} (${escapeHtml(item.id)})</option>`).join('');
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
}

async function refreshClaims() {
  const response = await fetch('/api/claims');
  if (!response.ok) throw new Error('Failed to load claims');
  liveClaims = await response.json();
  const list = document.getElementById('claims-list');
  if (!list) return;
  if (!liveClaims.length) {
    list.innerHTML = '<p>No claims logged. Add a question, theory, or record-backed finding.</p>';
    return;
  }
  list.innerHTML = liveClaims.map(claim => `<article class="claim-record ${escapeHtml(claim.status)}"><span class="table-status ${claim.status === 'finding' ? 'sourced' : 'review'}">${escapeHtml(claim.status.replace(/-/g, ' '))}</span><h3>${escapeHtml(claim.statement)}</h3><p><strong>Sources:</strong> ${claim.source_ids.length ? escapeHtml(claim.source_ids.join(', ')) : 'None yet'}</p><p><strong>Alternative explanation:</strong> ${claim.alternative_explanations.length ? escapeHtml(claim.alternative_explanations.join('; ')) : 'Not recorded yet'}</p><p><strong>Next test:</strong> ${escapeHtml(claim.next_test || 'Not recorded yet')}</p><p><strong>Latest review:</strong> ${escapeHtml(claim.review_status || 'unreviewed')}</p><button class="quiet-button" data-action="review-claim" data-claim-id="${escapeHtml(claim.id)}">Review claim</button></article>`).join('');
  refreshResearchQueue().catch(error => console.error('Research queue refresh failed:', error));
}

async function refreshResearchQueue() {
  const response = await fetch('/api/research-queue');
  if (!response.ok) throw new Error('Failed to calculate research queue');
  const queue = await response.json();
  const container = document.getElementById('research-queue');
  if (!container) return;
  if (!queue.length) {
    container.innerHTML = '<h3>Research queue</h3><p>No open questions require action.</p>';
    return;
  }
  container.innerHTML = `<h3>Research queue · ${queue.length} open</h3><ol>${queue.map(item => `<li><strong>${escapeHtml(item.statement)}</strong><br>${escapeHtml(item.reason)} ${item.next_test ? `Next: ${escapeHtml(item.next_test)}` : ''}</li>`).join('')}</ol>`;
}

async function refreshCollectionAudit() {
  const response = await fetch('/api/collection-audit');
  if (!response.ok) throw new Error('Failed to load collection audit');
  const report = await response.json();
  const container = document.getElementById('collection-audit');
  if (!container) return;
  const totals = report.totals;
  container.innerHTML = `
    <article class="claim-record"><span class="table-status sourced">Collection summary</span><h3>${totals.collected} collected · ${totals.unavailable} unavailable · ${totals.unique_hosts} hosts</h3><p>${escapeHtml(report.scope)}</p><p>${escapeHtml(report.interpretation)}</p></article>
    <article class="claim-record"><span class="table-status review">Access limitations</span><h3>${report.access_limitations.length} URL${report.access_limitations.length === 1 ? '' : 's'} need a different lawful route</h3>${report.access_limitations.length ? report.access_limitations.map(item => `<p><strong>${escapeHtml(item.url)}</strong><br>${escapeHtml(item.reason)} ${escapeHtml(item.next_action)}</p>`).join('') : '<p>None recorded.</p>'}</article>
    <article class="claim-record"><span class="table-status review">Duplicate-content check</span><h3>${report.duplicate_content.length} potential duplicate group${report.duplicate_content.length === 1 ? '' : 's'}</h3>${report.duplicate_content.length ? report.duplicate_content.map(item => `<p>${escapeHtml(item.urls.join(' | '))}<br>${escapeHtml(item.message)}</p>`).join('') : '<p>No duplicate content groups in the latest collection result for each URL.</p>'}</article>`;
}

async function refreshSourceChanges() {
  const response = await fetch('/api/source-changes');
  if (!response.ok) throw new Error('Failed to compare source captures');
  const changes = await response.json();
  const container = document.getElementById('source-changes');
  if (!container) return;
  if (!changes.length) {
    container.innerHTML = '<p>Each URL has one capture so far; run another approved collection to establish a comparison.</p>';
    return;
  }
  container.innerHTML = changes.map((change, index) => `<article class="claim-record"><span class="table-status ${change.change_type === 'content-unchanged' ? 'sourced' : 'review'}">${escapeHtml(change.change_type.replace(/-/g, ' '))}</span><h3>${escapeHtml(change.url)}</h3><p><strong>Prior capture:</strong> ${escapeHtml(new Date(change.previous_captured_at).toLocaleString())}<br><strong>Latest capture:</strong> ${escapeHtml(new Date(change.captured_at).toLocaleString())}</p><p>${escapeHtml(change.detail)}</p>${change.sha256 ? `<p><strong>Latest SHA-256:</strong> ${escapeHtml(change.sha256)}</p>` : ''}<button class="quiet-button" data-action="compare-source" data-source-url="${encodeURIComponent(change.url)}" data-diff-target="source-diff-${index}">Compare preserved text</button><pre id="source-diff-${index}" class="source-diff" hidden></pre></article>`).join('');
}

async function showSourceDiff(encodedUrl, targetId) {
  const output = document.getElementById(targetId);
  const response = await fetch(`/api/source-diff?url=${encodedUrl}`);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Comparison failed');
  output.hidden = false;
  output.textContent = result.available ? `${result.message}\n\n${result.lines.join('\n') || 'No text differences detected.'}${result.truncated ? '\n\nOutput truncated.' : ''}` : result.message;
}

async function refreshTimeline() {
  const response = await fetch('/api/timeline');
  if (!response.ok) throw new Error('Failed to load chronology');
  const events = await response.json();
  const container = document.getElementById('timeline-list');
  if (!container) return;
  if (!events.length) {
    container.innerHTML = '<p>No chronological events have been recorded.</p>';
    return;
  }
  container.innerHTML = events.map(event => `<article class="timeline-event"><span class="table-status ${event.type === 'collection' && event.status === 'collected' ? 'sourced' : 'review'}">${escapeHtml(event.type)} · ${escapeHtml(event.status)}</span><h3>${escapeHtml(event.title)}</h3><time>${event.timestamp ? escapeHtml(new Date(event.timestamp).toLocaleString()) : 'Date not recorded'}</time><p>${escapeHtml(event.detail)}</p></article>`).join('');
}

async function refreshAuditor() {
  const response = await fetch('/api/audit-status');
  if (!response.ok) throw new Error('Failed to verify audit ledger');
  const audit = await response.json();
  const container = document.getElementById('auditor-status');
  if (!container) return;
  const statusClass = audit.valid ? 'sourced' : 'review';
  container.innerHTML = `<article class="claim-record"><span class="table-status ${statusClass}">${audit.valid ? 'Verified' : 'Review required'}</span><h3>${audit.entries} append-only action${audit.entries === 1 ? '' : 's'} verified</h3><p>Latest chain hash: ${escapeHtml(audit.latest_hash || 'No entries yet')}</p>${audit.issues.length ? `<p>${escapeHtml(audit.issues.join(' '))}</p>` : '<p>Every entry links to the previous entry and matches its recorded integrity hash.</p>'}</article><article class="claim-record"><span class="table-status review">Recent activity</span><h3>Most recent operational events</h3>${audit.recent_entries.length ? audit.recent_entries.slice().reverse().map(entry => `<p><strong>${escapeHtml(entry.action)}</strong> · ${escapeHtml(entry.timestamp)}<br>Object: ${escapeHtml(entry.object_id || 'system event')}</p>`).join('') : '<p>No audited actions yet.</p>'}</article>`;
}

async function refreshBackupStatus() {
  const response = await fetch('/api/backup-status');
  if (!response.ok) throw new Error('Failed to check backup status');
  const backup = await response.json();
  const container = document.getElementById('backup-status');
  if (!container) return;
  container.innerHTML = `<article class="claim-record"><span class="table-status ${backup.valid ? 'sourced' : 'review'}">${backup.valid ? 'Backup verified' : 'Backup needed'}</span><h3>${backup.valid ? `${backup.files} files verified` : 'No verified backup available'}</h3><p>${backup.valid ? `Archive: ${escapeHtml(backup.archive)}` : escapeHtml(backup.issues.join(' '))}</p></article>`;
}

async function refreshSecurityStatus() {
  const response = await fetch('/api/security-status');
  if (!response.ok) throw new Error('Failed to check local access');
  const security = await response.json();
  const container = document.getElementById('security-status');
  if (!container) return;
  container.innerHTML = `<article class="claim-record"><span class="table-status ${security.private ? 'sourced' : 'review'}">${security.private ? 'Owner-only access' : 'Access review needed'}</span><h3>${security.checked} evidence paths checked</h3><p>${security.private ? 'No group or world filesystem access detected.' : escapeHtml(security.issues.join(' '))}</p><p>${escapeHtml(security.limitation)}</p></article>`;
}

async function hardenEvidenceAccess() {
  const button = document.getElementById('harden-evidence-button');
  button.disabled = true;
  button.textContent = 'Hardening access...';
  try {
    const response = await fetch('/api/harden-evidence', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Access hardening failed');
    await refreshSecurityStatus();
    refreshAuditor().catch(error => console.error('Auditor refresh failed:', error));
  } finally {
    button.disabled = false;
    button.textContent = 'Harden local access';
  }
}

async function createVerifiedBackup() {
  const button = document.getElementById('create-backup-button');
  button.disabled = true;
  button.textContent = 'Creating backup...';
  try {
    const response = await fetch('/api/backup', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Backup failed');
    await refreshBackupStatus();
    refreshAuditor().catch(error => console.error('Auditor refresh failed:', error));
  } finally {
    button.disabled = false;
    button.textContent = 'Create verified backup';
  }
}

async function runApprovedCollection() {
  const button = document.getElementById('run-approved-collection');
  if (button) {
    button.disabled = true;
    button.textContent = 'Collecting approved sources...';
  }
  try {
    const response = await fetch('/api/collect-approved', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Collection failed');
    await refreshCollectionAudit();
    const collected = payload.results.filter(item => item.status === 'collected').length;
    alert(`Approved collection complete: ${collected} of ${payload.results.length} sources preserved.`);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = 'Run approved collection';
    }
  }
}

async function submitClaimForm(event) {
  event.preventDefault();
  const formData = new FormData(event.target);
  const record = {
    statement: formData.get('statement'),
    source_ids: formData.getAll('source_ids'),
    alternative_explanations: String(formData.get('alternatives') || '').split('\n').map(item => item.trim()).filter(Boolean),
    next_test: formData.get('next_test'),
    status: formData.get('status'),
    review_status: 'unreviewed'
  };
  const response = await fetch('/api/claims', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(record) });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Claim save failed');
  event.target.reset();
  document.getElementById('claim-modal').hidden = true;
  await refreshClaims();
}

async function submitReviewForm(event) {
  event.preventDefault();
  const claimId = document.getElementById('review-claim-id').value;
  const formData = new FormData(event.target);
  const response = await fetch(`/api/claims/${encodeURIComponent(claimId)}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.fromEntries(formData)) });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Review save failed');
  event.target.reset();
  document.getElementById('review-modal').hidden = true;
  await refreshClaims();
  refreshAuditor().catch(error => console.error('Auditor refresh failed:', error));
  refreshBackupStatus().catch(error => console.error('Backup status refresh failed:', error));
  refreshSecurityStatus().catch(error => console.error('Security status refresh failed:', error));
}

async function preserveSelectedFile(event) {
  const file = event.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', file.name);
  formData.append('protection', 'restricted');
  const response = await fetch('/api/evidence-upload', { method: 'POST', body: formData });
  const payload = await response.json();
  event.target.value = '';
  if (!response.ok) throw new Error(payload.error || 'File preservation failed');
  await refreshEvidenceTable();
  alert(`Local file preserved: ${payload.record.title}`);
}

async function exportCounselPacket() {
  const response = await fetch('/api/counsel-packet');
  if (!response.ok) throw new Error('Counsel packet export failed');
  const packet = await response.json();
  const blob = new Blob([JSON.stringify(packet, null, 2)], { type: 'application/json' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'signal-ledger-counsel-packet.json';
  link.click();
  URL.revokeObjectURL(link.href);
}

function openPrintableCounselPacket() {
  window.open('/api/counsel-packet-print', '_blank', 'noopener');
}

// Render discrepancies with sophistication
async function refreshDiscrepancies() {
  try {
    const response = await fetch('/api/discrepancies');
    if (!response.ok) return;
    liveDiscrepancies = await response.json();
    renderDiscrepancies();
  } catch (error) {
    console.error('Discrepancy refresh failed:', error);
  }
}

function renderDiscrepancies() {
  const list = document.querySelector('#discrepancy-list');
  const counter = document.querySelector('#discrepancy-count');
  if (!list) return;
  
  if (!liveDiscrepancies.length) {
    counter.textContent = '0 open';
    list.innerHTML = '<article><span class="signal-number">00</span><div><strong>No discrepancies recorded</strong><p>No comparison has been run yet. An empty list does not mean the records are consistent.</p></div><span class="priority medium">Not run</span></article>';
    return;
  }
  
  counter.textContent = `${liveDiscrepancies.length} open`;
  list.innerHTML = liveDiscrepancies.slice(0,4).map((item, idx) => {
    const severity = (item.severity || 'medium').toLowerCase();
    const severityLabel = severity === 'high' ? 'High' : severity === 'medium' ? 'Medium' : 'Low';
    const icon = item.kind?.includes('innocence') ? '✓' : '!';
    const isExculpatory = item.kind?.includes('innocence-supporting');
    const classOverride = isExculpatory ? 'exculpatory' : severity === 'high' ? 'high' : severity === 'medium' ? 'medium' : 'low';
    
    return `
      <article class="${isExculpatory ? 'exculpatory-evidence' : ''}">
        <span class="signal-number">${String(idx + 1).padStart(2, '0')}</span>
        <div>
          <strong>${item.kind?.replace(/[-_]/g, ' ') || 'Review item'}</strong>
          <p>${item.message || item.routing_rationale || 'Review the evidence chain.'}</p>
        </div>
        <span class="priority ${classOverride}">${isExculpatory ? 'Supports innocence' : severityLabel}</span>
      </article>
    `;
  }).join('');
}

function renderRequestTable(requests) {
  const table = document.querySelector('#requests-view tbody');
  if (!table || !requests.length) return;
  table.innerHTML = requests.map(item => `<tr><td><strong>${escapeHtml(item.description)}</strong><small>${escapeHtml(item.date_range || 'Date range not recorded')}</small></td><td>${escapeHtml(item.agency)}</td><td>${escapeHtml(item.custodian || 'Not recorded')}</td><td><span class="table-status review">${escapeHtml(item.status)}</span><small>${escapeHtml(item.deadline ? `Deadline: ${item.deadline}` : 'No deadline recorded')}</small><small>Response files: ${(item.response_evidence_ids || []).length}</small><button class="quiet-button" data-action="link-response-evidence" data-request-id="${escapeHtml(item.id)}">Link response</button></td></tr>`).join('');
}

async function refreshFoiaPlan() {
  const container = document.getElementById('foia-plan');
  if (!container) return;
  const response = await fetch('/api/foia-plan');
  if (!response.ok) { container.innerHTML = '<p>FOIA plan unavailable.</p>'; return; }
  const plan = await response.json();
  container.innerHTML = plan.agencies.map((agency, a) => `
    <details class="foia-agency"${agency.suggestions.some(s => s.basis === 'evidence-indicated') ? ' open' : ''}>
      <summary><strong>${escapeHtml(agency.agency)}</strong> · ${escapeHtml(agency.law)} · ${agency.captured_pages} captured page(s)</summary>
      <p><small>Route: ${escapeHtml(agency.route || 'not recorded')}${agency.law_note ? ' · ' + escapeHtml(agency.law_note) : ''}${agency.source_status === 'verify-official-url' ? ' · Verify the official URL and custodian before filing.' : ''}</small></p>
      ${agency.suggestions.map((item, i) => `
        <article class="foia-item">
          <strong>${escapeHtml(item.document_type)}</strong> <span class="table-status ${item.basis === 'evidence-indicated' ? 'review' : 'sourced'}">${item.basis === 'evidence-indicated' ? 'Indicated by captured pages' : 'Standard record set'}</span>
          <p>${escapeHtml(item.rationale)}</p>
          ${item.evidence.map(e => `<small>${escapeHtml(e.url)}: “…${escapeHtml(e.excerpt)}…”</small>`).join('<br>')}
          <details><summary>Draft request text</summary><p>${escapeHtml(item.draft.request_text)}</p><ul>${item.draft.notes.map(n => `<li>${escapeHtml(n)}</li>`).join('')}</ul></details>
          ${item.already_requested ? '<small>Already in your request log.</small>' : `<button class="text-button" data-foia-agency="${a}" data-foia-item="${i}">＋ Add draft to request log</button>`}
        </article>`).join('')}
    </details>`).join('') || '<p>No agencies in the source registry.</p>';
  container.onclick = async event => {
    const button = event.target.closest('[data-foia-agency]');
    if (!button) return;
    const agency = plan.agencies[Number(button.dataset.foiaAgency)];
    const item = agency.suggestions[Number(button.dataset.foiaItem)];
    button.disabled = true;
    const saved = await fetch('/api/request-queue', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      agency: agency.agency, description: item.draft.request_text, date_range: plan.time_range, status: 'draft', jurisdiction: agency.jurisdiction }) });
    if (!saved.ok) { button.disabled = false; alert((await saved.json()).error || 'Could not save draft'); return; }
    button.replaceWith(Object.assign(document.createElement('small'), { textContent: 'Added to request log.' }));
    refreshRequests().catch(() => {});
  };
}

async function refreshRequests() {
  const response = await fetch('/api/request-queue');
  if (!response.ok) throw new Error('Failed to load request log');
  renderRequestTable(await response.json());
  refreshRequestDeadlines().catch(error => console.error('Request deadline refresh failed:', error));
}

async function refreshRequestDeadlines() {
  const response = await fetch('/api/request-deadlines');
  if (!response.ok) throw new Error('Failed to load request deadlines');
  const risks = await response.json();
  let container = document.getElementById('request-deadlines');
  if (!container) {
    container = document.createElement('div');
    container.id = 'request-deadlines';
    container.className = 'research-queue';
    document.querySelector('#requests-view .panel-heading')?.insertAdjacentElement('afterend', container);
  }
  if (!container) return;
  if (!risks.length) {
    container.innerHTML = '<h3>Request deadlines</h3><p>No submitted or pending requests need deadline review.</p>';
    return;
  }
  container.innerHTML = `<h3>Request deadline review · ${risks.length} tracked</h3><ol>${risks.map(risk => `<li><strong>${escapeHtml(risk.agency || 'Agency not recorded')} · ${escapeHtml(risk.level.replace(/-/g, ' '))}</strong><br>${escapeHtml(risk.message)}${Number.isInteger(risk.days_remaining) ? ` ${risk.days_remaining} day${risk.days_remaining === 1 ? '' : 's'} remaining.` : ''}</li>`).join('')}</ol>`;
}

async function submitRequestForm(event) {
  event.preventDefault();
  const response = await fetch('/api/request-queue', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.fromEntries(new FormData(event.target))) });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Request save failed');
  event.target.reset();
  document.getElementById('request-modal').hidden = true;
  await refreshRequests();
  refreshAuditor().catch(error => console.error('Auditor refresh failed:', error));
}

function openResponseEvidenceModal(requestId) {
  const select = document.getElementById('response-evidence-id');
  select.innerHTML = liveEvidenceData.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.title || 'Untitled evidence')} (${escapeHtml(item.id)})</option>`).join('');
  document.getElementById('response-request-id').value = requestId;
  document.getElementById('response-evidence-modal').hidden = false;
}

async function submitResponseEvidenceForm(event) {
  event.preventDefault();
  const requestId = document.getElementById('response-request-id').value;
  const evidenceId = new FormData(event.target).get('evidence_id');
  const response = await fetch(`/api/requests/${encodeURIComponent(requestId)}/response-evidence`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ evidence_id: evidenceId }) });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Response linking failed');
  document.getElementById('response-evidence-modal').hidden = true;
  await refreshRequests();
  refreshAuditor().catch(error => console.error('Auditor refresh failed:', error));
}

// Main initialization
fetch('/api/case').then(response => {
  if (!response.ok) throw new Error('API unavailable');
  return response.json();
}).then(async casefile => {
  const [entityResponse, relationshipResponse, catalogResponse, discrepancyResponse, evidenceResponse, requestResponse] = await Promise.all([
    fetch('/api/entities'),
    fetch('/api/relationships'),
    fetch('/api/source-catalog'),
    fetch('/api/discrepancies'),
    fetch('/api/evidence-live'),
    fetch('/api/request-queue')
  ]);
  
  if (!entityResponse.ok || !relationshipResponse.ok) throw new Error('Graph API unavailable');
  
  const liveEntities = await entityResponse.json();
  const liveRelationships = await relationshipResponse.json();
  
  if (liveEntities.length) {
    nodes = liveEntities.map(entity => ({
      id: entity.id, label: entity.label, type: entity.entity_type,
      x: entity.x, y: entity.y,
      status: entity.status === 'unverified-lead' ? 'lead' : 'fact',
      summary: entity.summary || 'No description recorded.',
      tags: [entity.entity_type],
      sources: []
    }));
    edges = liveRelationships.map(relationship => [
      relationship.source_entity_id,
      relationship.target_entity_id,
      relationship.evidence_status === 'unresolved' ? 'lead' : 'fact'
    ]);
    lookup = Object.fromEntries(nodes.map(node => [node.id, node]));
    selected = nodes[0]?.id;
    renderGraph();
    renderDetail(lookup[selected]);
  }
  renderGraphCounts();
  
  if (catalogResponse.ok) {
    const catalog = await catalogResponse.json();
    document.querySelector('#source-count').textContent = `${catalog.length} source families`;
    document.querySelector('#source-catalog-body').innerHTML = catalog.map(source => 
      `<tr><td><strong>${source.label}</strong><small>${source.id}</small></td><td>${source.category}</td><td><span class="table-status ${source.access === 'restricted' ? 'review' : 'sourced'}">${source.access}</span></td><td>${source.discovery}</td><td>${source.request_route}</td></tr>`
    ).join('');
  }
  
  if (discrepancyResponse.ok) {
    liveDiscrepancies = await discrepancyResponse.json();
    renderDiscrepancies();
  }
  
  if (evidenceResponse.ok) {
    liveEvidenceData = await evidenceResponse.json();
    renderEvidenceTable();
    renderCoverage();
  }

  initSearch().catch(error => console.error('Search init failed:', error));
  refreshFoiaPlan().catch(error => console.error('FOIA plan failed:', error));
  refreshClaims().catch(error => console.error('Claims refresh failed:', error));
  refreshCollectionAudit().catch(error => console.error('Collection audit refresh failed:', error));
  refreshSourceChanges().catch(error => console.error('Source change refresh failed:', error));
  refreshTimeline().catch(error => console.error('Timeline refresh failed:', error));
  refreshAuditor().catch(error => console.error('Auditor refresh failed:', error));
  
  if (requestResponse.ok) {
    const requests = await requestResponse.json();
    renderRequestTable(requests);
    refreshRequestDeadlines().catch(error => console.error('Request deadline refresh failed:', error));
  }
  
  document.querySelector('.topbar .eyebrow').textContent = `CASEFILE / ${casefile.title.toUpperCase()}`;
  document.querySelector('.notice p').innerHTML = '<strong>Live casefile connected.</strong> All evidence, relationships, and discrepancies update in real-time from your local workspace.';
}).catch(() => {});

// Cleaner event delegation
function initializeUi() {
  initModals();
  document.addEventListener('click', event => {
    if (event.target.closest('[data-action="add-evidence"]')) openEvidenceModal();
    const reviewButton = event.target.closest('[data-action="review-claim"]');
    if (reviewButton) {
      document.getElementById('review-claim-id').value = reviewButton.dataset.claimId;
      document.getElementById('review-modal').hidden = false;
    }
    const responseButton = event.target.closest('[data-action="link-response-evidence"]');
    if (responseButton) openResponseEvidenceModal(responseButton.dataset.requestId);
    const compareButton = event.target.closest('[data-action="compare-source"]');
    if (compareButton) showSourceDiff(compareButton.dataset.sourceUrl, compareButton.dataset.diffTarget).catch(error => alert(`Error: ${error.message}`));
    if (event.target.closest('#requests-view .text-button')) {
      document.getElementById('request-modal').hidden = false;
    }
  });
  
  // Navigation
  document.querySelectorAll('.nav-item').forEach(button => {
    button.addEventListener('click', () => {
      const view = button.dataset.view;
      document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      
      document.querySelectorAll('.view').forEach(v => {
        if (view === 'map') {
          v.hidden = !(v.id === 'map-view' || v.classList.contains('bottom-grid'));
        } else {
          v.hidden = v.id !== `${view}-view`;
        }
      });
      
      const titles = { map: 'Connection map', evidence: 'Evidence index', claims: 'Claims ledger', audit: 'Collection audit', changes: 'Source changes', timeline: 'Chronology', auditor: 'Integrity auditor', requests: 'Records requests', protocol: 'Audit protocol', sources: 'Source catalog' };
      document.querySelector('h1').textContent = titles[view] || 'Signal Ledger';
    });
  });
  
  // Import records
  document.querySelector('#import-records')?.addEventListener('click', () => document.querySelector('#record-file').click());
  document.querySelector('#record-file')?.addEventListener('change', async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const imported = JSON.parse(await file.text());
      if (!Array.isArray(imported.nodes)) throw new Error('JSON must contain a nodes array.');
      nodes = imported.nodes;
      edges = Array.isArray(imported.edges) ? imported.edges : [];
      lookup = Object.fromEntries(nodes.map(node => [node.id, node]));
      selected = nodes[0]?.id;
      renderGraph();
      renderDetail(lookup[selected]);
      renderGraphCounts();
    } catch (error) {
      alert(`Import failed: ${error.message}`);
    }
  });
  
  // Evidence modal
  document.getElementById('add-evidence-button')?.addEventListener('click', openEvidenceModal);
  document.getElementById('evidence-form')?.addEventListener('submit', submitEvidenceForm);
  document.getElementById('preserve-file-button')?.addEventListener('click', () => document.getElementById('evidence-file').click());
  document.getElementById('evidence-file')?.addEventListener('change', event => preserveSelectedFile(event).catch(error => alert(`Error: ${error.message}`)));
  document.getElementById('add-claim-button')?.addEventListener('click', () => { document.getElementById('claim-modal').hidden = false; });
  document.getElementById('claim-form')?.addEventListener('submit', event => submitClaimForm(event).catch(error => alert(`Error: ${error.message}`)));
  document.querySelector('[data-action="close-claim-modal"]')?.addEventListener('click', () => { document.getElementById('claim-modal').hidden = true; });
  document.querySelector('[data-action="close-review-modal"]')?.addEventListener('click', () => { document.getElementById('review-modal').hidden = true; });
  document.querySelector('[data-action="close-request-modal"]')?.addEventListener('click', () => { document.getElementById('request-modal').hidden = true; });
  document.querySelector('[data-action="close-response-evidence-modal"]')?.addEventListener('click', () => { document.getElementById('response-evidence-modal').hidden = true; });
  document.getElementById('review-form')?.addEventListener('submit', event => submitReviewForm(event).catch(error => alert(`Error: ${error.message}`)));
  document.getElementById('request-form')?.addEventListener('submit', event => submitRequestForm(event).catch(error => alert(`Error: ${error.message}`)));
  document.getElementById('response-evidence-form')?.addEventListener('submit', event => submitResponseEvidenceForm(event).catch(error => alert(`Error: ${error.message}`)));
  document.getElementById('create-backup-button')?.addEventListener('click', () => createVerifiedBackup().catch(error => alert(`Error: ${error.message}`)));
  document.getElementById('harden-evidence-button')?.addEventListener('click', () => hardenEvidenceAccess().catch(error => alert(`Error: ${error.message}`)));
  document.getElementById('export-counsel-packet')?.addEventListener('click', () => exportCounselPacket().catch(error => alert(`Error: ${error.message}`)));
  document.getElementById('print-counsel-packet')?.addEventListener('click', openPrintableCounselPacket);
  document.getElementById('run-approved-collection')?.addEventListener('click', () => runApprovedCollection().catch(error => alert(`Error: ${error.message}`)));
  
  // Close notice
  document.querySelectorAll('.close-notice').forEach(btn => {
    btn.addEventListener('click', () => btn.closest('.notice').remove());
  });
}

initializeUi();
