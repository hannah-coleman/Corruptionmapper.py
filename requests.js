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
const iso = d => d.toISOString().slice(0, 10);
function threeWorkingDays(from) {
  const d = new Date(from);
  let n = 0;
  while (n < 3) { d.setDate(d.getDate() + 1); if (d.getDay() % 6) n++; }
  return d;
}
function card(r, deadlines) {
  const text = r.request_text || r.description || '';
  const mail = 'mailto:?subject=' + encodeURIComponent('Public records request') + '&body=' + encodeURIComponent(text);
  const kids = [el('strong', {}, [t(`${r.agency} (${r.status})`)]), el('div', {}, [el('small', {}, [t(r.basis || '')])]), el('pre', {}, [t(text)])];
  const note = deadlines.find(d => d.id === r.id);
  if (r.sent_on) kids.push(el('div', {}, [t(`Sent ${r.sent_on}. ${note ? note.message + ' ' + (note.days_remaining != null ? `Days remaining: ${note.days_remaining}.` : '') : ''}`)]));
  if (r.status === 'draft') {
    const copy = el('button', {type: 'button'}, [t('Copy text')]);
    copy.addEventListener('click', async () => { await navigator.clipboard.writeText(text); copy.textContent = 'Copied'; });
    const sent = el('input', {type: 'date'}); sent.value = iso(new Date());
    const due = el('input', {type: 'date'}); due.value = iso(threeWorkingDays(new Date()));
    const mark = el('button', {type: 'button'}, [t('I sent it: track the deadline')]);
    const msg = el('span', {role: 'status'});
    mark.addEventListener('click', async () => {
      try {
        await api(`/api/requests/${r.id}/sent`, {method: 'POST', body: JSON.stringify({sent_on: sent.value, deadline: due.value}), headers: {'Content-Type': 'application/json'}});
        await draw();
      } catch (e) { msg.textContent = e.message; }
    });
    kids.push(copy, el('a', {href: mail, class: 'btn'}, [t('Open in my email app')]),
      el('div', {}, [el('label', {}, [t('Date sent '), sent]), t(' '), el('label', {}, [t('Response due (edit if the agency states otherwise) '), due]), mark, msg]));
  }
  return el('article', {}, kids);
}
async function draw() {
  const [list, deadlines] = await Promise.all([api('/api/request-queue'), api('/api/request-deadlines')]);
  document.getElementById('list').replaceChildren(...(list.length ? list.map(r => card(r, deadlines)) : [t('No requests yet.')]));
}
draw().catch(e => { document.getElementById('list').textContent = e.message; });
