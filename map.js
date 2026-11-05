const COLORS = {property: '#3b6ea8', business: '#2f8f4e', church: '#8a4fb0', government: '#c0392b', nonprofit: '#d68910', other: '#666'};
const NS = 'http://www.w3.org/2000/svg';
const text = value => document.createTextNode(value == null ? '' : String(value));

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  children.forEach(c => node.append(c));
  return node;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('X-Signal-Ledger', '1');
  const response = await fetch(path, {...options, headers});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function showDetail(place, linkList, byId) {
  const box = document.getElementById('detail');
  box.replaceChildren();
  const rows = [['Kind', place.kind], ['Address', place.address], ['Parcel', place.parcel_id], ['Owner of record', place.owner], ['Registered agent', place.agent],
    ['Entity ID', place.entity_id], ['Mailing address', place.mailing_address], ['Source', place.source], ['Source date', place.source_date], ['Note', place.note]];
  box.append(el('strong', {}, [text(place.name)]));
  rows.filter(r => r[1]).forEach(([k, v]) => box.append(el('div', {}, [text(`${k}: ${v}`)])));
  const related = linkList.filter(l => l.a === place.id || l.b === place.id);
  related.forEach(l => {
    const other = byId[l.a === place.id ? l.b : l.a];
    box.append(el('div', {}, [text(`${l.relation} ("${l.value}") with ${other.name}. Sources: ${l.sources.join('; ')}`)]));
  });
}

async function draw() {
  const data = await api('/api/places');
  const byId = Object.fromEntries(data.places.map(p => [p.id, p]));
  const svg = document.getElementById('map');
  svg.replaceChildren();
  const placed = data.places.filter(p => p.lat != null);
  const W = 1000, H = 520, pad = 30;
  if (placed.length) {
    const lats = placed.map(p => p.lat), lons = placed.map(p => p.lon);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const spanLat = (maxLat - minLat) || 0.01, spanLon = (maxLon - minLon) || 0.01;
    const pos = p => [pad + (p.lon - minLon) / spanLon * (W - 2 * pad), H - pad - (p.lat - minLat) / spanLat * (H - 2 * pad)];
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    data.links.forEach(l => {
      if (byId[l.a].lat == null || byId[l.b].lat == null) return;
      const [x1, y1] = pos(byId[l.a]), [x2, y2] = pos(byId[l.b]);
      const line = document.createElementNS(NS, 'line');
      [['x1', x1], ['y1', y1], ['x2', x2], ['y2', y2], ['stroke', '#999'], ['stroke-dasharray', '4 3']].forEach(([k, v]) => line.setAttribute(k, v));
      const title = document.createElementNS(NS, 'title');
      title.textContent = `${l.relation}: ${l.value}`;
      line.append(title);
      svg.append(line);
    });
    placed.forEach(p => {
      const [x, y] = pos(p);
      const dot = document.createElementNS(NS, 'circle');
      [['cx', x], ['cy', y], ['r', 8], ['class', 'pin'], ['fill', COLORS[p.kind] || COLORS.other], ['tabindex', 0]].forEach(([k, v]) => dot.setAttribute(k, v));
      const title = document.createElementNS(NS, 'title');
      title.textContent = `${p.name} (${p.kind})`;
      dot.append(title);
      const pick = () => showDetail(p, data.links, byId);
      dot.addEventListener('click', pick);
      dot.addEventListener('keydown', e => { if (e.key === 'Enter') pick(); });
      svg.append(dot);
    });
  }
  const legend = document.getElementById('legend');
  legend.replaceChildren(...Object.entries(COLORS).map(([k, c]) => el('span', {style: `margin-right:1rem;color:${c}`}, [text(`● ${k}`)])));
  const linkBox = document.getElementById('links');
  linkBox.replaceChildren(...data.links.map(l => el('li', {class: 'link'}, [text(`${byId[l.a].name} and ${byId[l.b].name}: ${l.relation} ("${l.value}"). ${l.caution}`)])));
  if (!data.links.length) linkBox.append(el('li', {}, [text('None found in the saved places.')]));
  document.getElementById('unplaced').replaceChildren(...data.unplaced.map(id => el('li', {}, [text(`${byId[id].name} (${byId[id].kind})`)])));
}

document.getElementById('add').addEventListener('submit', async event => {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(event.target).entries());
  const msg = document.getElementById('addmsg');
  try {
    await api('/api/places', {method: 'POST', body: JSON.stringify(body), headers: {'Content-Type': 'application/json'}});
    event.target.reset();
    msg.textContent = 'Added.';
    await draw();
  } catch (error) { msg.textContent = error.message; }
});

document.getElementById('csv').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  const msg = document.getElementById('csvmsg');
  try {
    const result = await api('/api/places/import', {method: 'POST', body: JSON.stringify({csv: await file.text()}), headers: {'Content-Type': 'application/json'}});
    msg.textContent = `Added ${result.added}. ${result.errors.join(' ')}`;
    await draw();
  } catch (error) { msg.textContent = error.message; }
});

draw().catch(error => { document.getElementById('detail').textContent = error.message; });
