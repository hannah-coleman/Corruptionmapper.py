const t = v => document.createTextNode(v == null ? '' : String(v));
function el(tag, attrs = {}, kids = []) {
  const n = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
  kids.forEach(k => n.append(k));
  return n;
}
async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('X-Signal-Ledger', '1');
  const r = await fetch(path, {...options, headers});
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || 'Request failed');
  return d;
}
const LEVELS = {verified: 'Verified', corrected: 'Corrected', unsupported: 'Not supported', 'stale-check': 'Re-verify', 'unverified-ocr': 'Unverified (OCR)', unverified: 'Unverified'};
const METHODS = {'page-image': 'Page image / original PDF', 'original-record': 'Official original or certified copy', recording: 'Recording', 'agency-response': 'Agency written response'};
const RESULTS = {matches: 'The record says what the lead says', corrected: 'The record differs (enter the correction)', 'not-found': 'The record does not support the lead'};

function select(name, options) {
  return el('select', {name}, Object.entries(options).map(([v, label]) => el('option', {value: v}, [t(label)])));
}
function field(label, input) { return el('label', {}, [t(label), input]); }

function verifyForm(lead, reload) {
  const form = el('form');
  const msg = el('span', {role: 'status'});
  form.append(field('How did you check?', select('method', METHODS)), field('Result', select('result', RESULTS)),
    field('Your name', el('input', {name: 'reviewer', required: ''})), field('Page or location', el('input', {name: 'page'})),
    field('What exactly did you compare? *', el('textarea', {name: 'note', required: ''})),
    field('Correction (if the record differs)', el('input', {name: 'corrected_text'})),
    field('Contrary evidence or other explanation', el('input', {name: 'counter_evidence'})),
    el('button', {}, [t('Save check')]), msg);
  form.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      await api(`/api/discrepancies/${encodeURIComponent(lead.id)}/verify`, {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form).entries())), headers: {'Content-Type': 'application/json'}});
      reload();
    } catch (err) { msg.textContent = err.message; }
  });
  return form;
}

async function load() {
  const home = await api('/api/home');
  const reqs = Object.entries(home.requests).map(([s, n]) => `${n} ${s}`).join(', ') || 'none';
  document.getElementById('status').replaceChildren(
    ...[['Leads by status', Object.entries(home.verification).map(([k, n]) => `${n} ${LEVELS[k]}`).join(', ') || 'none open'],
      ['Records requests', reqs], ['Mapped places', home.places], ['Layoff patterns flagged', home.layoff_flags]]
      .map(([k, v]) => el('div', {class: 'card'}, [el('strong', {}, [t(k)]), el('div', {}, [t(v)])])));
  const checked = Object.entries(home.verification).some(([k, n]) => k !== 'unverified' && k !== 'unverified-ocr' && n > 0);
  const sent = Object.keys(home.requests).some(k => k !== 'draft');
  const steps = [
    [home.documents > 0, 'Add records', `Add records you have, or use the full workspace to search archives and save pages. ${home.documents} documents indexed so far.`, '#upload'],
    [checked, 'Check your leads', 'Open each lead below, compare it with the original page, and record what you found.', '#leads'],
    [sent, 'Request what is missing', 'Send records requests for anything the leads show is missing (drafts are in the request queue).', '/requests.html'],
    [home.places > 0, 'Map places', 'Add properties, businesses and churches from filed records to see shared owners and agents.', '/map.html'],
    [home.packet_built, 'Build a packet', 'Package verified and unverified leads with their sources and hashes.', '#packet']];
  document.getElementById('steps').replaceChildren(...steps.map(([done, title, text, href]) =>
    el('li', {}, [t(done ? '✔ ' : '○ '), el('a', {href}, [t(title)]), t(': ' + text)])));
  const list = await api('/api/discrepancies');
  const leads = list.filter(x => x.lead);
  const box = document.getElementById('leads');
  box.replaceChildren(...(leads.length ? leads.map(lead => {
    const details = el('details', {}, [el('summary', {}, [t('Record a check')])]);
    details.append(verifyForm(lead, load));
    return el('article', {}, [
      el('span', {class: 'tag'}, [t(LEVELS[lead.verification] || lead.verification)]), t(' '), el('strong', {}, [t(lead.message)]),
      el('div', {}, [t(`Meeting/item: ${lead.meeting}. Text read by: ${lead.text_method}.`)]),
      ...lead.evidence.map(ev => el('blockquote', {}, [t(ev.passage), el('br'), el('small', {}, [t(ev.url)])])),
      el('div', {}, [t('Possible innocent explanations: ' + lead.explanations.join(' '))]),
      el('div', {}, [t('Next step: ' + lead.next_action)]), details]);
  }) : [t('No open leads.')]));
}

document.getElementById('packet').addEventListener('click', async () => {
  const msg = document.getElementById('packetmsg');
  try { msg.textContent = 'Written to ' + (await api('/api/lead-packet', {method: 'POST', body: '{}', headers: {'Content-Type': 'application/json'}})).path; }
  catch (e) { msg.textContent = e.message; }
});
load().catch(e => { document.getElementById('leads').textContent = e.message; });

async function watchJob(job, msg) {
  while (job && (job.status === 'queued' || job.status === 'running')) {
    msg.textContent = `Working (${job.status})...`;
    await new Promise(r => setTimeout(r, 2000));
    job = await api('/api/jobs/' + encodeURIComponent(job.id));
  }
  if (!job) return;
  msg.textContent = job.status === 'done' ? 'Finished. Leads below are up to date.' : 'Failed: ' + job.error;
  if (job.status === 'done') load();
}
document.getElementById('upload').addEventListener('submit', async event => {
  event.preventDefault();
  const msg = document.getElementById('uploadmsg');
  const data = new FormData(event.target);
  data.set('protection', document.getElementById('ispublic').checked ? 'public' : 'restricted');
  data.set('kind', 'primary-source');
  try {
    const result = await api('/api/evidence-upload', {method: 'POST', body: data});
    msg.textContent = result.indexing.reason;
    event.target.reset();
    if (result.job) watchJob(result.job, document.getElementById('jobmsg'));
  } catch (e) { msg.textContent = e.message; }
});
document.getElementById('refresh').addEventListener('click', async () => {
  const msg = document.getElementById('jobmsg');
  try { watchJob((await api('/api/jobs/refresh', {method: 'POST', body: '{}', headers: {'Content-Type': 'application/json'}})).job, msg); }
  catch (e) { msg.textContent = e.message; }
});

const ack = document.getElementById('ack');
try { ack.hidden = localStorage.getItem('cm-ack') === '1'; } catch (e) { ack.hidden = false; }
document.getElementById('ackbtn').addEventListener('click', () => {
  try { localStorage.setItem('cm-ack', '1'); } catch (e) { /* private mode: it will show again */ }
  ack.hidden = true;
});
