let nodes = [
  { id: 'mayor', label: 'Paragould City Clerk', type: 'Government', x: 180, y: 130, status: 'fact', summary: 'City records office identified as the official source for municipal meeting records, bids, and contract files.', tags: ['Local government', 'Records custodian'], sources: [['City portal · agendas and procurement', 'https://ar-paragould.civicplus.com/', 'Captured 12 Aug 2026'], ['Paragould council and public notices', 'https://ar-paragould.civicplus.com/', 'Captured 12 Aug 2026']] },
  { id: 'meridian', label: 'Meridian Civic Group', type: 'Entity', x: 395, y: 95, status: 'fact', summary: 'Local consulting entity appearing in procurement and business records tied to county or municipal work.', tags: ['Vendor', 'Awarded contract'], sources: [['Arkansas Secretary of State business registry', 'https://www.sos.arkansas.gov/', 'Captured 12 Aug 2026']] },
  { id: 'chief', label: 'Greene County Finance Office', type: 'Government', x: 610, y: 145, status: 'lead', summary: 'Secondary local records trail points to county financial oversight and meeting minutes that may include the relevant funding references.', tags: ['County government', 'Unverified lead'], sources: [['Greene County official site', 'https://www.greenecounty.arkansas.gov/', 'Captured 13 Aug 2026']] },
  { id: 'civic', label: 'Paragould Vendor Ledger', type: 'Entity', x: 255, y: 270, status: 'fact', summary: 'Business registration and vendor record ties connect the entity to an address and local filing activity.', tags: ['Registered entity', 'Shared address'], sources: [['Arkansas business records search', 'https://www.sos.arkansas.gov/', 'Captured 11 Aug 2026']] },
  { id: 'grant', label: 'Arkansas grant funds', type: 'Public money', x: 500, y: 255, status: 'fact', summary: 'Public-funds trail documents the local funding channel and state-level transparency references.', tags: ['Public funds'], sources: [['Arkansas transparency portal', 'https://transparency.arkansas.gov/', 'Captured 12 Aug 2026']] },
  { id: 'address', label: 'Paragould business address', type: 'Location', x: 375, y: 380, status: 'lead', summary: 'Address documentation requires direct verification against local business filings and public notices.', tags: ['Connection lead'], sources: [['Paragould and Greene County official sites', 'https://ar-paragould.civicplus.com/, https://www.greenecounty.arkansas.gov/', 'Captured 11 Aug 2026']] },
  { id: 'firm', label: 'Arkansas legal services', type: 'Entity', x: 620, y: 350, status: 'fact', summary: 'Outside legal review appears in local government records and related public attachments.', tags: ['Professional services'], sources: [['Paragould city and county records', 'https://ar-paragould.civicplus.com/', 'Captured 12 Aug 2026']] },
  { id: 'watchdog', label: 'Local public records watch', type: 'Organization', x: 115, y: 350, status: 'fact', summary: 'Public-interest organization used for context only; not a subject of the local review.', tags: ['Source organization'], sources: [['Official public records guidance', 'https://www.arkansasethics.com/', 'Captured 13 Aug 2026']] }
];
let edges = [['mayor','meridian','fact'],['mayor','grant','fact'],['meridian','civic','fact'],['meridian','grant','fact'],['meridian','chief','lead'],['civic','address','fact'],['address','firm','lead'],['chief','watchdog','fact'],['grant','firm','fact'],['mayor','civic','lead'],['civic','firm','lead']];
const graph = document.querySelector('#graph');
const detail = document.querySelector('#detail-content');
let lookup = Object.fromEntries(nodes.map(node => [node.id, node]));
let selected = 'meridian';
function renderGraph() { graph.innerHTML = ''; edges.forEach(([from,to,status]) => { const a=lookup[from], b=lookup[to]; const line=document.createElementNS('http://www.w3.org/2000/svg','line'); line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);line.setAttribute('class',`edge ${status==='lead'?'lead':''}`);graph.appendChild(line); }); nodes.forEach(node => { const group=document.createElementNS('http://www.w3.org/2000/svg','g');group.setAttribute('class',`node ${node.status==='lead'?'lead':''} ${node.id===selected?'selected':''}`);group.dataset.id=node.id; const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('cx',node.x);circle.setAttribute('cy',node.y);circle.setAttribute('r',node.id===selected?27:23); const text=document.createElementNS('http://www.w3.org/2000/svg','text');text.setAttribute('x',node.x);text.setAttribute('y',node.y+43);text.setAttribute('text-anchor','middle');text.setAttribute('class','node-label');text.textContent=node.label;group.append(circle,text);group.addEventListener('click',()=>{selected=node.id;renderGraph();renderDetail(node);});graph.appendChild(group); }); }
function renderDetail(node) { detail.innerHTML=`<div class="detail-top"><span class="detail-type">${node.status==='lead'?'UNVERIFIED LEAD':'SOURCED RECORD'} · ${node.type.toUpperCase()}</span><h2 class="detail-title">${node.label}</h2><span class="detail-meta">Added 12 Aug 2026 · Confidence: ${node.status==='lead'?'needs review':'high'}</span></div><div class="detail-body"><h3>Working description</h3><p>${node.summary}</p><div>${node.tags.map(tag=>`<span class="tag">${tag}</span>`).join('')}</div><h3 style="margin-top:23px">Evidence trail · ${node.sources.length}</h3>${node.sources.map(source=>`<div class="evidence-item"><strong>${source[0]}</strong><a href="#" title="Source URL">${source[1]}</a><small>${source[2]}</small></div>`).join('')}<button class="primary-button" style="width:100%;margin-top:12px">＋ Add evidence</button></div>`; }
renderGraph();renderDetail(lookup[selected]);
fetch('/api/case').then(response=>{if(!response.ok)throw new Error('API unavailable');return response.json();}).then(async casefile=>{const [entityResponse,relationshipResponse,catalogResponse,discrepancyResponse,evidenceResponse,requestResponse]=await Promise.all([fetch('/api/entities'),fetch('/api/relationships'),fetch('/api/source-catalog'),fetch('/api/discrepancies'),fetch('/api/evidence-live'),fetch('/api/request-queue')]);if(!entityResponse.ok||!relationshipResponse.ok)throw new Error('Graph API unavailable');const liveEntities=await entityResponse.json();const liveRelationships=await relationshipResponse.json();if(liveEntities.length){nodes=liveEntities.map(entity=>({id:entity.id,label:entity.label,type:entity.entity_type,x:entity.x,y:entity.y,status:entity.status==='unverified-lead'?'lead':'fact',summary:entity.summary||'No description recorded.',tags:[entity.entity_type],sources:[]}));edges=liveRelationships.map(relationship=>[relationship.source_entity_id,relationship.target_entity_id,relationship.evidence_status==='unresolved'?'lead':'fact']);lookup=Object.fromEntries(nodes.map(node=>[node.id,node]));selected=nodes[0].id;renderGraph();renderDetail(nodes[0]);document.querySelector('#node-count').textContent=nodes.length;}if(catalogResponse.ok){const catalog=await catalogResponse.json();document.querySelector('#source-count').textContent=`${catalog.length} source families`;document.querySelector('#source-catalog-body').innerHTML=catalog.map(source=>`<tr><td><strong>${source.label}</strong><small>${source.id}</small></td><td>${source.category}</td><td><span class="table-status ${source.access==='restricted'?'review':'sourced'}">${source.access}</span></td><td>${source.discovery}</td><td>${source.request_route}</td></tr>`).join('');}if(discrepancyResponse.ok){const discrepancies=await discrepancyResponse.json();const list=document.querySelector('#discrepancy-list');const counter=document.querySelector('#discrepancy-count');if(discrepancies.length){counter.textContent=`${discrepancies.length} open`;list.innerHTML=discrepancies.slice(0,4).map((item,index)=>{const severity=(item.severity||'medium').toLowerCase();const label=severity==='high'?'High':severity==='medium'?'Medium':'Low';const kind=(item.kind||'review-item').replace(/[-_]/g,' ');const rationale=(item.routing_rationale||item.next_action||'Review the source trail and preserve the governing record.');return `<article><span class="signal-number">${String(index+1).padStart(2,'0')}</span><div><strong>${kind}</strong><p>${item.message||rationale}</p></div><span class="priority ${severity === 'high' ? 'high' : severity === 'medium' ? 'medium' : 'low'}">${label}</span></article>`;}).join('');}else{counter.textContent='0 open';list.innerHTML='<article><span class="signal-number">00</span><div><strong>No active discrepancies</strong><p>Nothing currently needs review in the live casefile.</p></div><span class="priority low">Clear</span></article>';}}if(evidenceResponse.ok){const evidence=await evidenceResponse.json();const evidenceTable=document.querySelector('#evidence-view tbody');if(evidence.length && evidenceTable){const rows=evidence.map(item=>`<tr><td><strong>${item.title}</strong><small>${item.url||'no url'}</small></td><td>${item.kind||'manual'}</td><td>${new Date().toISOString().slice(0,10)}</td><td><span class="table-status sourced">${item.protection || 'public'}</span></td><td>${item.lane || 'review'}</td></tr>`).join('');evidenceTable.innerHTML=rows;}}if(requestResponse.ok){const requests=await requestResponse.json();const requestTable=document.querySelector('#requests-view tbody');if(requestTable && requests.length){requestTable.innerHTML=requests.map((item,index)=>`<tr><td><strong>${item.record_type || 'Request '+(index+1)}</strong></td><td>${item.agency || 'Unspecified agency'}</td><td>${item.description || 'No description'}</td><td><span class="table-status review">${item.status || 'draft'}</span></td></tr>`).join('');}}document.querySelector('.topbar .eyebrow').textContent=`CASEFILE / ${casefile.title.toUpperCase()}`;document.querySelector('.notice p').innerHTML='<strong>Live casefile connected.</strong> The graph, source catalog, discrepancy queue, evidence intake, and request log are reading from the local workspace.';}).catch(()=>{});
document.querySelector('#search').addEventListener('input', async event => { const term=event.target.value.trim().toLowerCase(); document.querySelectorAll('.node').forEach(item => { const node=lookup[item.dataset.id]; item.style.opacity=(!term || `${node.label} ${node.type} ${node.summary}`.toLowerCase().includes(term))?'1':'.18'; }); const results=document.querySelector('#search-results'); if(!term){results.hidden=true;results.innerHTML='';return;} try{const response=await fetch(`/api/search?q=${encodeURIComponent(term)}`);if(!response.ok)throw new Error('Search unavailable');const matches=await response.json();results.hidden=false;results.innerHTML=matches.length?matches.slice(0,12).map(match=>`<button class="search-result"><strong>${match.title}</strong><small>${match.result_type} · ${match.detail||''}</small></button>`).join(''):'<span>No matching casefile records.</span>';}catch(error){results.hidden=false;results.innerHTML='<span>Live search is unavailable; graph filtering remains active.</span>';}});
document.querySelector('#search').addEventListener('input',async event=>{const term=event.target.value.trim();if(!term)return;const results=document.querySelector('#search-results');try{const response=await fetch(`/api/search-text?q=${encodeURIComponent(term)}`);if(!response.ok)throw new Error('Full-text search unavailable');const matches=await response.json();if(!matches.length)return;results.hidden=false;results.innerHTML=matches.slice(0,12).map(match=>`<button class="search-result" title="Open the preserved source manually"><strong>${match.title||match.url}</strong><small>captured source · ${match.source_family||'unclassified'} · ${match.captured_at||'unknown time'}</small><small>${match.excerpt||'No text excerpt available.'}</small></button>`).join('');}catch(error){}}
);
document.querySelectorAll('.close-notice').forEach(button=>button.addEventListener('click',()=>button.closest('.notice').remove()));
document.querySelectorAll('.nav-item').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('.nav-item').forEach(item=>item.classList.remove('active'));button.classList.add('active');document.querySelectorAll('.view').forEach(view=>view.hidden=button.dataset.view==='map'?!(view.id==='map-view'||view.classList.contains('bottom-grid')):view.id!==`${button.dataset.view}-view`);document.querySelector('h1').textContent={map:'Connection map',evidence:'Evidence index',requests:'Records requests',protocol:'Audit protocol',sources:'Source catalog'}[button.dataset.view];}));
document.querySelector('#import-records').addEventListener('click',()=>document.querySelector('#record-file').click());
document.querySelector('#record-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{const imported=JSON.parse(await file.text());if(!Array.isArray(imported.nodes))throw new Error('JSON must contain a nodes array.');nodes=imported.nodes;edges=Array.isArray(imported.edges)?imported.edges:[];lookup=Object.fromEntries(nodes.map(node=>[node.id,node]));selected=nodes[0].id;renderGraph();renderDetail(nodes[0]);document.querySelector('#node-count').textContent=nodes.length;}catch(error){alert(`Import failed: ${error.message}`);}});

document.getElementById('add-evidence-button').addEventListener('click', async () => {
  const record = {
    title: 'Public source intake',
    url: 'https://www.sos.arkansas.gov/',
    summary: 'Manual evidence intake saved locally for review.',
    kind: 'primary-source',
    protection: 'public',
    lane: 'public-record'
  };
  try {
    const response = await fetch('/api/evidence', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(record)
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Evidence save failed');
    }
    alert(`Evidence saved: ${payload.record.title}`);
    window.location.reload();
  } catch (error) {
    alert(`Evidence intake failed: ${error.message}`);
  }
});

document.getElementById('trigger-collection-button').addEventListener('click', async () => {
  const demoUrls = [
    'https://www.sos.arkansas.gov/',
    'https://transparency.arkansas.gov/',
    'https://www.arkansasethics.com/'
  ];
  try {
    const response = await fetch('/api/collect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ urls: demoUrls })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Collection failed');
    }
    const summary = payload.results.filter(result => result.status === 'collected').length;
    alert(`Collection complete: ${summary} public source(s) preserved locally.`);
    window.location.reload();
  } catch (error) {
    alert(`Collection failed: ${error.message}`);
  }
});
