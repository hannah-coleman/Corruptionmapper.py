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
function syncFields() {
  const table = document.getElementById('table').value;
  document.querySelectorAll('[data-for]').forEach(label => {
    const on = label.dataset.for.split(' ').includes(table);
    label.hidden = !on;
    label.querySelectorAll('input').forEach(i => { i.disabled = !on; });
  });
}
async function draw() {
  const {flags} = await api('/api/layoffs');
  const box = document.getElementById('flags');
  box.replaceChildren(...(flags.length ? flags.map(f => el('article', {}, [
    el('strong', {}, [t(f.message)]),
    el('div', {}, [t('Sources: ' + f.sources.join('; '))]),
    el('div', {}, [t('Ordinary explanations: ' + f.innocent_explanations.join(' '))]),
    el('div', {}, [t('Next step: ' + f.next_step)]),
    el('small', {}, [t(f.caution)])])) : [t('No patterns found in the entries so far.')]));
}
document.getElementById('table').addEventListener('change', syncFields);
document.getElementById('add').addEventListener('submit', async event => {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(event.target).entries());
  const msg = document.getElementById('msg');
  try {
    await api('/api/layoffs', {method: 'POST', body: JSON.stringify(body), headers: {'Content-Type': 'application/json'}});
    event.target.reset(); syncFields(); msg.textContent = 'Added.'; await draw();
  } catch (e) { msg.textContent = e.message; }
});
syncFields();
draw().catch(e => { document.getElementById('flags').textContent = e.message; });
