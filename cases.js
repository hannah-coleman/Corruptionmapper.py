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
const line = (label, text) => el('div', {}, [el('strong', {}, [t(label + ' ')]), t(text)]);
async function openCase(name) {
  const a = await api('/api/case-review?case=' + encodeURIComponent(name));
  const box = document.getElementById('analysis');
  const kids = [el('h2', {}, [t('Case: ' + name)]), el('h3', {}, [t('Timeline')])];
  a.timeline.forEach(r => kids.push(el('div', {}, [t(`${r.date}: ${r.title} (${r.kind}; source: ${r.source})`)])));
  kids.push(el('h3', {}, [t('Where the records differ')]));
  if (!a.differences.length) kids.push(el('p', {}, [t('None found in the labelled fields.')]));
  a.differences.forEach(d => kids.push(el('article', {}, [el('strong', {}, [t(d.message)]),
    ...d.values.map(v => el('div', {}, [t(`${v.title} (${v.kind}): ${v.value} [source: ${v.source}]`)])),
    line('Ordinary explanations:', d.ordinary_explanations.join(' ')), line('Next step:', d.next_step)])));
  kids.push(el('h3', {}, [t('Policy text beside record text')]));
  if (!a.policy.length) kids.push(el('p', {}, [t('No policy requirements entered for this case.')]));
  a.policy.forEach(p => kids.push(el('article', {}, [el('strong', {}, [t(`${p.policy.title} ${p.agency ? '(' + p.agency + ')' : ''}`)]),
    el('blockquote', {}, [t(p.requirement)]), ...(p.version_note ? [line('Version:', p.version_note)] : []),
    ...p.record_passages.map(r => el('blockquote', {}, [t(`${r.title} (${r.given_as}): ${r.passage}`)])), el('small', {}, [t(p.note)])])));
  kids.push(el('h3', {}, [t('Wording features')]), el('small', {}, [t('How sentences are built. Not a statement about what happened or why.')]));
  a.wording.slice(0, 30).forEach(w => kids.push(el('div', {}, [t(`${w.feature}: "${w.sentence}"`)])));
  const report = el('button', {}, [t('Build redacted report')]);
  const out = el('pre', {style: 'white-space:pre-wrap'});
  report.addEventListener('click', async () => { out.textContent = (await api('/api/case-review/report?case=' + encodeURIComponent(name))).markdown; });
  kids.push(el('h3', {}, [t('Report')]), report, out, el('h3', {}, [t('Limits')]), ...a.limits.map(l => el('div', {}, [t('- ' + l)])));
  box.replaceChildren(...kids);
}
async function draw() {
  const d = await api('/api/case-review');
  document.getElementById('cases').replaceChildren(...(d.cases.length ? d.cases.map(c => {
    const b = el('button', {}, [t(`${c.case_id} (${c.entries} records)`)]);
    b.addEventListener('click', () => openCase(c.case_id).catch(e => alert(e.message)));
    return b;
  }) : [t('No cases yet. Add a record below.')]));
  const p = d.patterns;
  document.getElementById('patterns').replaceChildren(
    t(`${p.cases_entered} case(s) entered; records differ in ${p.cases_with_record_differences}.`),
    ...p.officials_in_two_or_more_cases.map(o => el('div', {}, [t(`${o.name}: appears in ${o.cases} cases (${o.cases_with_record_differences} with record differences)`)])),
    el('small', {}, [t(p.caution)]));
  const people = (await api('/api/case-review/people')).people;
  document.getElementById('people').replaceChildren(...(people.length ? people.map(x => {
    const box = el('input', {type: 'checkbox'});
    box.checked = x.named_ok;
    box.addEventListener('change', async () => { await api('/api/case-review/consent', {method: 'POST', body: JSON.stringify({name: x.name, named_ok: box.checked}), headers: {'Content-Type': 'application/json'}}); });
    return el('label', {}, [box, t(` ${x.code}: ${x.name} (check only if this person agreed to be named)`)]);
  }) : [t('None yet.')]));
}
document.getElementById('add').addEventListener('submit', async event => {
  event.preventDefault();
  const msg = document.getElementById('msg');
  try {
    await api('/api/case-review/entries', {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.target).entries())), headers: {'Content-Type': 'application/json'}});
    event.target.reset(); msg.textContent = 'Added.'; await draw();
  } catch (e) { msg.textContent = e.message; }
});
draw().catch(e => { document.getElementById('cases').textContent = e.message; });
document.getElementById('policyReq').addEventListener('click', async () => {
  const pmsg = document.getElementById('pmsg');
  try {
    await api('/api/case-review/policy-request', {method: 'POST', body: JSON.stringify({agency: document.getElementById('agency').value}), headers: {'Content-Type': 'application/json'}});
    pmsg.textContent = 'Draft queued (not sent).';
  } catch (e) { pmsg.textContent = e.message; }
});
