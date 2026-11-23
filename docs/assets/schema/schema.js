/* The database schema page: cards for the tables, links drawn over them. The data (tables, fields,
   descriptions) is in schema-<lang>.json; the page is in the language of ?lang=. */
const params = new URLSearchParams(location.search);
const LANG = params.get('lang') === 'fr' ? 'fr' : 'en';

// follow the colour scheme of the documentation that embeds this page
(function syncTheme() {
  try {
    const root = window.parent && window.parent !== window ? window.parent.document.documentElement : null;
    const body = window.parent && window.parent !== window ? window.parent.document.body : null;
    if (!body) return;
    const apply = () => {
      const scheme = body.getAttribute('data-md-color-scheme');
      document.documentElement.dataset.theme = scheme === 'slate' ? 'dark' : 'light';
    };
    apply();
    new MutationObserver(apply).observe(body, { attributes: true, attributeFilter: ['data-md-color-scheme'] });
  } catch (e) { /* opened alone: the system theme applies */ }
})();

fetch(`schema-${LANG}.json`).then(r => r.json()).then(init);

function init(DATA) {
const UI = DATA.ui, TABLES = DATA.tables;
document.documentElement.lang = UI.lang;
document.title = UI.title;
const BADGE = {u:[UI.badges.u,''], n:[UI.badges.n,''], f:[UI.badges.f,'fk'], m:[UI.badges.m,'m2m'], o:[UI.badges.o,'one']};
const fill = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k]);
const $ = id => document.getElementById(id);
$('title').textContent = UI.title;
$('legend').innerHTML = Object.entries(UI.groups).map(([g, label]) =>
  `<span class="sw"><i style="background:var(--c-${g})"></i>${label}</span>`).join('')
  + `<span class="sw"><span class="ln"></span>${UI.fk}</span><span class="sw"><span class="ln d"></span>${UI.m2m}</span>`;
$('bar').setAttribute('aria-label', UI.toolbar);
$('jumpLabel').textContent = UI.jumpLabel;
$('zout').setAttribute('aria-label', UI.zout); $('zin').setAttribute('aria-label', UI.zin);
$('zfit').textContent = UI.zfit;
$('note').innerHTML = UI.note;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const canvas = document.getElementById('canvas');
const stage = document.getElementById('stage');
const svg = document.getElementById('links');
const viewport = document.getElementById('viewport');
const NS = 'http://www.w3.org/2000/svg';

// ---------- cards
const cols = [0,1,2,3,4,5].map(() => { const c = document.createElement('div'); c.className = 'col'; canvas.appendChild(c); return c; });
const rels = [];
TABLES.forEach(t => {
  const rows = t.fields.map((f, i) => {
    const [n, ty, fl, d, to] = f;
    const rowId = `r-${t.id}-${i}`;
    if (to) rels.push({from: t.id, row: rowId, to, kind: fl.includes('m') ? 'm' : 'f', g: t.g});
    const bd = [...fl].map(k => BADGE[k] ? `<span class="bd ${BADGE[k][1]}">${BADGE[k][0]}</span>` : '').join('');
    const rel = to ? ' rel' : '';
    return `<li class="row${rel}" id="${rowId}"><div class="l1"><code class="fn">${esc(n)}</code><span class="ty">${esc(ty)}</span>${bd}</div><p class="d">${esc(d)}</p></li>`;
  }).join('');
  const el = document.createElement('article');
  el.className = `card g-${t.g}`; el.id = `t-${t.id}`; el.tabIndex = 0;
  el.setAttribute('aria-label', fill(UI.table, {id: t.id}));
  el.innerHTML = `<header><h2>${esc(t.id)}</h2><span class="pk">${esc(t.sub || 'pk id')}</span></header><p class="tn">${esc(t.note)}</p><ul class="rows">${rows}</ul>${t.cons ? `<p class="cons">${t.cons}</p>` : ''}`;
  cols[t.col].appendChild(el);
});
$('sub').innerHTML = fill(UI.sub, {count: fill(UI.count, {tables: TABLES.length, links: rels.length})});

// jump list
const jump = document.getElementById('jump');
jump.options[0].textContent = UI.jump;
TABLES.forEach(t => { const o = document.createElement('option'); o.value = t.id; o.textContent = t.id; jump.appendChild(o); });

// ---------- links
let scale = 1; const st = {hover: null, pinned: null};
const absPos = el => { let x = 0, y = 0; while (el && el !== canvas) { x += el.offsetLeft; y += el.offsetTop; el = el.offsetParent; } return {x, y}; };
function draw() {
  svg.innerHTML = '';
  const W = canvas.offsetWidth, H = canvas.offsetHeight;
  svg.setAttribute('width', W * scale); svg.setAttribute('height', H * scale);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  rels.forEach(r => {
    const row = document.getElementById(r.row), fromCard = document.getElementById('t-' + r.from), toCard = document.getElementById('t-' + r.to);
    const fp = absPos(fromCard), tp = absPos(toCard), rp = absPos(row);
    const fw = fromCard.offsetWidth, tw = toCard.offsetWidth;
    const sy = rp.y + row.offsetHeight / 2, ty = tp.y + 22;
    let sx, tx, c1x, c2x;
    const fc = fp.x + fw / 2, tc = tp.x + tw / 2;
    if (Math.abs(fc - tc) < 10) { sx = fp.x + fw; tx = tp.x + tw; c1x = sx + 80; c2x = tx + 80; }
    else if (tc > fc) { sx = fp.x + fw; tx = tp.x; const k = Math.max(50, (tx - sx) * .45); c1x = sx + k; c2x = tx - k; }
    else { sx = fp.x; tx = tp.x + tw; const k = Math.max(50, (sx - tx) * .45); c1x = sx - k; c2x = tx + k; }
    const color = `var(--c-${r.g})`;
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', `M${sx},${sy} C${c1x},${sy} ${c2x},${ty} ${tx},${ty}`);
    p.setAttribute('class', 'l' + (r.kind === 'm' ? ' m' : ''));
    p.style.stroke = color;
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('cx', sx); dot.setAttribute('cy', sy); dot.setAttribute('r', 4); dot.style.fill = color;
    const dir = tx >= c2x ? 1 : -1;
    const tri = document.createElementNS(NS, 'polygon');
    tri.setAttribute('points', `${tx},${ty} ${tx - dir * 11},${ty - 5.5} ${tx - dir * 11},${ty + 5.5}`); tri.style.fill = color;
    [p, dot, tri].forEach(n => { n.dataset.a = r.from; n.dataset.b = r.to; svg.appendChild(n); });
  });
  applyFocus();
}
function applyFocus() {
  document.querySelectorAll('.card').forEach(c => { c.classList.remove('dim', 'on'); });
  svg.querySelectorAll('[data-a]').forEach(n => { n.classList.remove('h', 'x', 'h-end', 'x-end'); });
  const focus = st.hover || st.pinned;
  if (!focus) return;
  const linked = new Set([focus]);
  svg.querySelectorAll('[data-a]').forEach(n => {
    const hit = n.dataset.a === focus || n.dataset.b === focus;
    const isPath = n.tagName === 'path';
    if (hit) { linked.add(n.dataset.a); linked.add(n.dataset.b); n.classList.add(isPath ? 'h' : 'h-end'); }
    else n.classList.add(isPath ? 'x' : 'x-end');
  });
  document.querySelectorAll('.card').forEach(c => {
    const id = c.id.slice(2);
    if (id === focus) c.classList.add('on'); else if (!linked.has(id)) c.classList.add('dim');
  });
}
const canHover = matchMedia('(hover:hover)');
const toggle = id => { st.pinned = st.pinned === id ? null : id; applyFocus(); };
document.querySelectorAll('.card').forEach(c => {
  const id = c.id.slice(2);
  c.addEventListener('mouseenter', () => { if (canHover.matches) { st.hover = id; applyFocus(); } });
  c.addEventListener('mouseleave', () => { if (canHover.matches) { st.hover = null; applyFocus(); } });
  c.addEventListener('click', () => toggle(id));
  c.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(id); } });
});

// ---------- zoom
function setScale(s) {
  scale = Math.min(1.4, Math.max(0.25, s));
  canvas.style.transform = `scale(${scale})`;
  stage.style.width = canvas.offsetWidth * scale + 'px';
  stage.style.height = canvas.offsetHeight * scale + 'px';
  draw();
}
function fit() { setScale((viewport.clientWidth - 32) / canvas.offsetWidth); }
document.getElementById('zin').onclick = () => setScale(scale * 1.2);
document.getElementById('zout').onclick = () => setScale(scale / 1.2);
document.getElementById('zfit').onclick = fit;
jump.onchange = () => {
  const id = jump.value; if (!id) return;
  st.pinned = id; applyFocus();
  const c = document.getElementById('t-' + id);
  const p = absPos(c);
  viewport.scrollTo({left: Math.max(0, p.x * scale - 16), top: 0, behavior: 'auto'});
  window.scrollTo({top: viewport.offsetTop + p.y * scale - 90, behavior: 'auto'});
  jump.value = '';
};

const start = () => {
  const vw = window.innerWidth;
  setScale(vw < 700 ? 0.8 : Math.min(1, Math.max(0.6, (vw - 32) / canvas.offsetWidth * 1.35)));
};
(document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(start);
window.addEventListener('load', () => setScale(scale));
}
