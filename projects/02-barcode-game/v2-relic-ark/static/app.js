/* 잔해 방주 Phase 0 — 방주(거점)가 메인 화면. 스캔·카드·쪽지는 그 위에서 여는 시트. */
(() => {
  const $ = (s) => document.querySelector(s);
  const uid = (() => { try { let u = localStorage.getItem('ark_uid'); if (!u) { u = 'u' + Math.random().toString(36).slice(2, 10); localStorage.setItem('ark_uid', u); } return u; } catch { return 'anon'; } })();
  const api = async (path, body) => {
    const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid, ...body }) } : undefined);
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || r.statusText);
    return j;
  };
  const toast = (m) => { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), 2200); };
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const RES_KO = { food: '식량', water: '물', med: '의약', power: '전력', parts: '부품', morale: '사기', cloth: '직물', trade: '교역', knowledge: '지식', scrap: '잔해', chem: '화학' };
  const CAT_KO = { food: '식품', drink: '음료', medical: '의약·화학', electronics: '전자', stationery: '문구', book: '도서', apparel: '의류', tobacco: '담배·주류', unknown: '정체불명' };
  const TYPE_KO = { supply: '보급', counter: '대항', facility: '시설', event: '이벤트', blueprint: '청사진', gear: '장비', trade: '교역' };
  const RAR_KO = { common: '일반 · COMMON', uncommon: '고급 · UNCOMMON', rare: '희귀 · RARE', epic: '에픽 · EPIC', legendary: '전설 · LEGENDARY' };
  const FAC_KO = { mycel: '균류 군체', scavs: '약탈자', machine: '기계 잔재', mutant: '변이체', world: '반도 잔해', tribe: '부족', gardener: '정원사', reader: '리더' };
  const TRIBE_KO = { wayfarer: '길손', shelf: '진열대', flame: '불꽃', white: '하얀', archive: '서고', greenhouse: '온실', tower: '탑' };
  const ROOM_IMG = { pantry: 'room_pantry.jpg', well: 'room_well.jpg', infirmary: 'room_infirmary.jpg', library: 'room_library.jpg' };
  const SURFACE_SLOTS = 2, FLOOR_W = 2; // 슬롯 0-1 지상, 2-9 지하(층당 2칸)
  let ark = null, rooms = null, cardIndex = {}, artOk = {};
  const ROOM3D = {}; // id -> true/false (static/art/rooms3d/<id>.jpg 존재 여부)
  ['pantry', 'well', 'infirmary', 'library', 'rock', 'lot'].forEach(id => { const im = new Image(); im.onload = () => { ROOM3D[id] = true; if (ark) renderScene(); }; im.onerror = () => { ROOM3D[id] = false; }; im.src = `/static/art/rooms3d/${id}.jpg`; });
  function roomTile(id, seed) {
    if (ROOM3D[id]) { const im = document.createElement('img'); im.className = 'tile r3d'; im.alt = ''; im.src = `/static/art/rooms3d/${id}.jpg`; return im; }
    const cv = document.createElement('canvas'); cv.className = 'tile'; window.ROOMS.draw(cv, id, seed); return cv;
  }

  fetch('/static/art/cards_index.json').then(r => r.ok ? r.json() : {}).then(j => { cardIndex = j || {}; }).catch(() => { });
  const artUrl = (f) => `/static/art/${f}`;
  const cardArtFor = (c) => { const stem = Object.keys(cardIndex).find(s => c.name.endsWith(s)); return stem ? artUrl(cardIndex[stem]) : null; };

  // ── 결정적 난수 ─────────────────────────────────────────
  function rng(seed) { let h = 2166136261; for (const ch of String(seed)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return () => { h += 0x6D2B79F5; let t = h; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  // ── 카드 DOM ────────────────────────────────────────────
  function cardEl(c, opts = {}) {
    const el = document.createElement('div');
    el.className = 'tcg ' + c.rarity; el.dataset.id = c.id || '';
    const yields = Object.entries(c.yields || {}).map(([k, v]) => `${RES_KO[k] || k} +${v}`).join(' · ');
    const art = cardArtFor(c);
    el.innerHTML = `${opts.badge !== false ? `<span class="rar">${RAR_KO[c.rarity]}</span>` : ''}<div class="inner">
      <div class="head"><span>${esc(c.name)}</span><small>${esc((c.card_type || '').toUpperCase())}</small></div>
      <div class="art">${art ? `<img alt="" src="${art}">` : '<canvas width="200" height="150"></canvas>'}</div>
      <div class="body"><i>"${esc(c.flavor)}"</i>${yields}</div>
      <div class="stats"><span>${TYPE_KO[c.card_type] || c.card_type}</span><span>${CAT_KO[c.category] || c.category}</span><span>${esc(c.family_name)}</span>${(c.tags || []).map(t => `<span>#${esc(t)}</span>`).join('')}</div>
      <div class="code"><canvas width="190" height="22"></canvas><em>${c.barcode.slice(0, 1)} ${c.barcode.slice(1, 7)} ${c.barcode.slice(7)}</em></div></div>`;
    if (!art) drawArt(el.querySelector('.art canvas'), c); else el.querySelector('.art img').onerror = (e) => { const cv = document.createElement('canvas'); cv.width = 200; cv.height = 150; e.target.replaceWith(cv); drawArt(cv, c); };
    drawBars(el.querySelector('.code canvas'), c.barcode);
    return el;
  }
  const CAT_COLOR = { food: '#F2A93B', drink: '#4FB7E6', medical: '#7DE0A8', electronics: '#4FB7E6', stationery: '#E8DFCB', book: '#D4AF37', apparel: '#B8AE9C', tobacco: '#D9483B', unknown: '#8C8677' };
  function drawArt(cv, c) {
    const x = cv.getContext('2d'), r = rng(c.seed || c.barcode), col = CAT_COLOR[c.category] || '#8C8677';
    x.fillStyle = '#5c5a52'; x.fillRect(0, 0, 200, 150);
    x.fillStyle = '#3a3833'; for (let i = 0; i < 9; i++) { const w = 14 + r() * 24, h = 20 + r() * 60; x.fillRect(i * 23, 110 - h, w, h); }
    x.fillStyle = '#4A463F'; x.fillRect(0, 110, 200, 40);
    x.fillStyle = col; x.globalAlpha = .25; x.beginPath(); x.ellipse(100, 44, 46, 10, 0, 0, Math.PI * 2); x.fill(); x.globalAlpha = 1;
    for (let i = 0; i < 3; i++) { const w = 18 + r() * 30, h = 30 + r() * 50, px = 100 - w / 2 + (r() - .5) * 60; x.fillStyle = i === 0 ? col : '#DED3BB'; x.globalAlpha = i === 0 ? .95 : .5; x.fillRect(px, 115 - h, w, h); }
    x.globalAlpha = 1;
  }
  function drawBars(cv, code) {
    const x = cv.getContext('2d'), W = cv.width, H = cv.height, r = rng(code), u = W / 95; x.fillStyle = '#2B2A28';
    x.fillRect(0, 0, u, H); x.fillRect(2 * u, 0, u, H); let px = 3 * u;
    for (let i = 0; i < 12; i++) { let m = 0; while (m < 7) { const bw = 1 + Math.floor(r() * 3); if (r() > .45) x.fillRect(px, 0, bw * u, H); px += bw * u; m += bw; } }
    x.fillRect(W - 3 * u, 0, u, H); x.fillRect(W - u, 0, u, H);
  }

  // ── HUD ─────────────────────────────────────────────────
  function renderHud() {
    if (!ark) return;
    $('#dayline').textContent = `DAY ${ark.day} · 주민 ${ark.residents}${ark.injured ? ` · 부상 ${ark.injured}` : ''}`;
    const order = ['food', 'water', 'med', 'knowledge', 'parts', 'morale'];
    $('#resbar').innerHTML = order.map(k => `<span class="${ark.resources[k] <= 2 && ['food', 'water', 'morale'].includes(k) ? 'lo' : ''}">${RES_KO[k]} <b>${ark.resources[k] ?? 0}</b></span>`).join('');
    $('#dkScanSub').textContent = `${ark.scans_today} / ${ark.scan_cap}`;
    $('#dkCardsSub').textContent = `손패 ${ark.hand.length}`;
    const pending = !(ark.today_event && ark.today_event.resolved);
    $('#evDot').classList.toggle('on', pending); $('#dkEventSub').textContent = pending ? '도착' : '내일';
    // 시간대 톤
    const h = new Date().getHours(); $('#night').style.opacity = (h >= 21 || h < 5) ? .55 : (h >= 18 || h < 7) ? .3 : 0;
  }
  async function refresh() {
    const a = await api(`/api/ark?uid=${uid}`); rooms = a.rooms_catalog; ark = a;
    renderHud(); renderScene(a.produced_while_away);
    window.dispatchEvent(new CustomEvent('ark:update', { detail: { ark, rooms, uid } }));
  }

  // ── 방주 월드: 아이소 격자 + 지반 판 + 줌/팬 ────────────────
  // 지하 3×3: 중앙(1,1) = 역 홀(고정), 주변 8칸 = 슬롯 2~9. 지상 2칸 = 슬롯 0,1.
  const ISO = { W: 517.2, H: 258.6, fx: 320, fy: 512.6, res: 640, meta: null };
  const S0 = 0.5;   // 월드 기본 배율 (줌은 CSS transform으로)
  fetch('/static/art/iso/tile_meta.json').then(r => r.ok ? r.json() : null).then(m => {
    if (!m || !m.pantry) return; const p = m.pantry; ISO.meta = m;
    ISO.W = p.right[0] - p.left[0]; ISO.H = p.front[1] - p.back[1]; ISO.fx = p.front[0]; ISO.fy = p.front[1]; ISO.res = m._res || 640;
    if (ark) renderScene();
  }).catch(() => { });
  const GRID = [[0, 0], [1, 0], [2, 0], [0, 1], [2, 1], [0, 2], [1, 2], [2, 2]];   // slot-2 → (i,j)
  const isoTile = (id) => `/static/art/iso/${id}.png`;
  window.ISO = ISO; window.GRID = GRID;

  // 격자 좌표 → 월드 픽셀 (칸 중심). stage: {ox, oy}
  function cellCenter(st, i, j) { const s = S0, W = ISO.W * s, H = ISO.H * s; return { x: st.ox + (i - j) * W / 2, y: st.oy + (i + j) * H / 2 - H / 2 }; }
  window.cellCenter = cellCenter;

  function isoCell(stage, st, i, j, opts) {
    const s = S0, W = ISO.W * s, H = ISO.H * s, imgW = ISO.res * s;
    const fxp = st.ox + (i - j) * W / 2, fyp = st.oy + (i + j) * H / 2;
    const cell = document.createElement('div'); cell.className = 'iso-cell ' + (opts.cls || '');
    cell.style.cssText = `left:${fxp - ISO.fx * s}px;top:${fyp - ISO.fy * s}px;width:${imgW}px;height:${imgW}px;z-index:${(i + j) * 10 + i + 10}`;
    const lx = ISO.fx * s - W / 2, rx = ISO.fx * s + W / 2, by = ISO.fy * s - H, my = ISO.fy * s - H / 2, wall = H * 0.85;
    cell.style.clipPath = `polygon(${lx}px ${my}px, ${lx}px ${my - wall}px, ${ISO.fx * s}px ${by - wall}px, ${rx}px ${my - wall}px, ${rx}px ${my}px, ${ISO.fx * s}px ${ISO.fy * s}px)`;
    const im = document.createElement('img'); im.alt = ''; im.src = isoTile(opts.tile); im.draggable = false; cell.appendChild(im);
    if (opts.glow) { const g = document.createElement('div'); g.className = 'glow'; g.style.setProperty('--g', opts.glow); g.style.cssText += `;left:${lx}px;top:${my - wall}px;width:${W}px;height:${H + wall}px`; cell.appendChild(g); }
    if (opts.label !== undefined) { const l = document.createElement('div'); l.className = 'lab'; l.style.left = ISO.fx * s + 'px'; l.style.top = (my + H * 0.3) + 'px'; l.innerHTML = opts.label; cell.appendChild(l); }
    if (opts.plus) { const p = document.createElement('div'); p.className = 'plus'; p.style.left = ISO.fx * s + 'px'; p.style.top = (my - H * 0.1) + 'px'; p.innerHTML = `<b>+</b>${opts.plus}`; cell.appendChild(p); }
    if (opts.prod) { const p = document.createElement('div'); p.className = 'prod'; p.style.left = ISO.fx * s + 'px'; p.style.top = (my - H * 0.42) + 'px'; p.textContent = opts.prod; cell.appendChild(p); }
    cell.dataset.room = opts.tile; cell.dataset.i = i; cell.dataset.j = j; cell.dataset.stage = st.name;
    if (opts.onclick) cell.addEventListener('click', (e) => { if (window.__panMoved) return; opts.onclick(e); });
    stage.appendChild(cell);
    return cell;
  }

  function plate(stage, id, cx, cy, size_m) {
    const m = ISO.meta && ISO.meta[id]; if (!m) return;
    const Wp = m.right[0] - m.left[0];                            // 판 마름모 폭(px, 원본)
    const k = S0 * (size_m / 6) * ISO.W / Wp;                     // 방 타일과 픽셀/미터 일치
    const img = document.createElement('img'); img.className = 'plate'; img.alt = ''; img.src = isoTile(id); img.draggable = false;
    const mx = (m.left[0] + m.right[0]) / 2, my = (m.front[1] + m.back[1]) / 2;
    img.style.cssText = `left:${cx - mx * k}px;top:${cy - my * k}px;width:${m.res * k}px;height:${m.res * k}px`;
    stage.appendChild(img);
  }

  let WORLD = { w: 1100, h: 1500, under: null, surf: null };
  function renderScene(produced) {
    const F = $('#floors'); F.innerHTML = '';
    const p = produced || {}, keys = Object.keys(p);
    const s = S0, W = ISO.W * s, H = ISO.H * s;
    const worldW = Math.round(W * 4.2), ox = worldW / 2;
    const surfOY = 300 + ISO.fy * s;                        // 지상 밴드 원점 (앞 꼭짓점 y 기준)
    const underOY = surfOY + H * 1.4 + 420;                  // 지하 격자 원점
    const worldH = Math.round(underOY + 2 * H + ISO.res * s * 0.4);
    WORLD = { w: worldW, h: worldH, under: { name: 'under', ox, oy: underOY }, surf: { name: 'surf', ox: ox - W / 4, oy: surfOY } };
    const stage = document.createElement('div'); stage.className = 'iso-world'; stage.style.width = worldW + 'px'; stage.style.height = worldH + 'px';
    // 하늘·스카이라인
    const sky = document.createElement('div'); sky.className = 'w-sky'; sky.style.height = (surfOY - ISO.fy * s + 120) + 'px'; stage.appendChild(sky);
    // 지반 판
    const sc = cellCenter(WORLD.surf, 0.5, 0); plate(stage, 'ground_surface', sc.x, sc.y + H * 0.15, 16);
    const uc = cellCenter(WORLD.under, 1, 1); plate(stage, 'ground_under', uc.x, uc.y, 24);
    // 지층 경계(지상↔지하) 띠
    const strata = document.createElement('div'); strata.className = 'strata'; strata.style.top = (surfOY + H * 0.9) + 'px'; strata.style.height = (underOY - ISO.fy * s - (surfOY + H * 0.9) + H * 0.5) + 'px'; stage.appendChild(strata);
    if (keys.length) { const d = document.createElement('div'); d.className = 'away'; d.textContent = `자리를 비운 사이 방주가 생산했습니다: ${keys.map(k => `${RES_KO[k]} +${p[k]}`).join(', ')}`; F.appendChild(d); }
    const roomOpts = (room, slot) => {
      const sp = rooms[room.id];
      const prod = Object.entries(sp.produces).map(([k, v]) => typeof v === 'number' ? `${RES_KO[k]} +${v}` : '대항').join(' ') + ' / 8h';
      return { tile: room.id, cls: 'built', glow: sp.light, label: sp.name, prod, onclick: () => openBuild(slot, true) };
    };
    const lab0 = document.createElement('div'); lab0.className = 'floor-lab surface'; lab0.style.top = (surfOY - ISO.fy * s + 80) + 'px'; lab0.textContent = 'B0 · 지상 — 재건'; stage.appendChild(lab0);
    [0, 1].forEach(slot => { const room = ark.rooms.find(r => r.slot === slot); isoCell(stage, WORLD.surf, slot, 0, room ? roomOpts(room, slot) : { tile: 'lot', cls: 'empty', plus: '재건', onclick: () => openBuild(slot, false) }); });
    const lab1 = document.createElement('div'); lab1.className = 'floor-lab'; lab1.style.top = (underOY - ISO.fy * s - 10) + 'px'; lab1.textContent = 'B1 · 잊힌 역 — 굴착'; stage.appendChild(lab1);
    isoCell(stage, WORLD.under, 1, 1, { tile: 'hall', cls: 'built hall', glow: '#F2A93B', label: '역 홀 · 승강기', onclick: () => openHall() });
    GRID.forEach(([i, j], k) => { const slot = k + 2; const room = ark.rooms.find(r => r.slot === slot); isoCell(stage, WORLD.under, i, j, room ? roomOpts(room, slot) : { tile: 'rock', cls: 'empty', plus: '굴착', onclick: () => openBuild(slot, false) }); });
    const actors = document.createElement('div'); actors.className = 'actors'; actors.id = 'actors'; stage.appendChild(actors);
    F.appendChild(stage);
    F.querySelectorAll('img').forEach(im => im.addEventListener('error', () => { im.style.display = 'none'; }));
    window.WORLD = WORLD;
    fitView(true);
    window.dispatchEvent(new CustomEvent('ark:scene'));
  }

  // ── 줌 / 팬 ─────────────────────────────────────────────
  const view = { z: 1, tx: 0, ty: 0, min: 0.45, max: 2.6 };
  function applyView() { const F = $('#floors'); F.style.transform = `translate(${view.tx}px,${view.ty}px) scale(${view.z})`; }
  function fitView(initial) {
    const vp = $('#world'); const vw = vp.clientWidth, vh = vp.clientHeight;
    if (initial) { view.z = Math.max(view.min, Math.min(1.2, vw / (ISO.W * S0 * 3.3))); const uc = cellCenter(WORLD.under, 1, 1); view.tx = vw / 2 - uc.x * view.z; view.ty = vh * 0.58 - uc.y * view.z; }
    applyView();
  }
  function zoomAt(f, cx, cy) { const nz = Math.max(view.min, Math.min(view.max, view.z * f)); const k = nz / view.z; view.tx = cx - (cx - view.tx) * k; view.ty = cy - (cy - view.ty) * k; view.z = nz; applyView(); }
  (function bindPanZoom() {
    const vp = $('#world'); const pts = new Map(); let last = null, moved = 0, pinch0 = null;
    vp.addEventListener('wheel', (e) => { e.preventDefault(); const r = vp.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
    vp.addEventListener('pointerdown', (e) => { pts.set(e.pointerId, { x: e.clientX, y: e.clientY }); if (pts.size === 1) { last = { x: e.clientX, y: e.clientY }; moved = 0; window.__panMoved = false; } if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch0 = { d: Math.hypot(a.x - b.x, a.y - b.y), z: view.z, cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 }; } });
    vp.addEventListener('pointermove', (e) => {
      if (!pts.has(e.pointerId)) return; pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pts.size === 2 && pinch0) { const [a, b] = [...pts.values()]; const d = Math.hypot(a.x - b.x, a.y - b.y); const r = vp.getBoundingClientRect(); const target = Math.max(view.min, Math.min(view.max, pinch0.z * d / pinch0.d)); zoomAt(target / view.z, pinch0.cx - r.left, pinch0.cy - r.top); moved = 99; window.__panMoved = true; return; }
      if (pts.size === 1 && last) { const dx = e.clientX - last.x, dy = e.clientY - last.y; moved += Math.abs(dx) + Math.abs(dy); if (moved > 6) window.__panMoved = true; view.tx += dx; view.ty += dy; last = { x: e.clientX, y: e.clientY }; applyView(); }
    });
    const up = (e) => { pts.delete(e.pointerId); if (pts.size < 2) pinch0 = null; if (pts.size === 0) { last = null; setTimeout(() => { window.__panMoved = false; }, 50); } };
    vp.addEventListener('pointerup', up); vp.addEventListener('pointercancel', up); vp.addEventListener('pointerleave', up);
    vp.addEventListener('dblclick', (e) => { const r = vp.getBoundingClientRect(); zoomAt(view.z < 1.3 ? 1.6 : 0.5, e.clientX - r.left, e.clientY - r.top); });
  })();
  window.ARKVIEW = { fitView, zoomAt, view };

  // 각인 배지: 이름·외형 변화·대가를 title 로 물린다 (docs/GROWTH_AND_MYTH.md §1)
  function imprintBadges(r) {
    const cat = ark.imprints_catalog || {};
    return (r.imprints || []).map(id => {
      const im = cat[id]; if (!im) return '';
      return `<span class="imp" title="${esc(im.visual)} — 대가: ${esc(im.cost || '')}">刻 ${esc(im.name)}</span>`;
    }).join('');
  }
  function trustOf(r) { const t = (ark.trust || {})[r.id]; return t ? t.avg : 0; }

  function openHall() {
    const list = ark.residents_list || [];
    const roster = list.map(r => {
      const badges = imprintBadges(r), tv = trustOf(r);
      return `<div class="ro"><img alt="" src="/static/art/chars/${r.role}_dl_b.png" onerror="this.style.display='none'"><div><b>${esc(r.name)}</b> <span class="tag">${esc(r.evolved_ko || r.role_ko)}</span>${r.role_evolved ? '<span class="evo">역할 진화</span>' : ''}
        <div class="ds">${esc(r.ability)}${r.trait ? ' · ' + esc(r.trait) : ''}${r.injured ? ' · <span style="color:var(--danger)">부상</span>' : ''}</div>
        ${badges ? `<div class="imps">${badges}</div>` : ''}
        <div class="trust"><span>신뢰 평균 ${tv}</span><i><u style="width:${Math.max(2, tv)}%"></u></i></div></div></div>`;
    }).join('');
    const avg = list.length ? Math.round(list.reduce((s, r) => s + trustOf(r), 0) / list.length) : 0;
    const marked = list.filter(r => (r.imprints || []).length).length;
    openSheet(`<div class="eyebrow">B1 · 역 홀</div><h2>잊힌 역의 승강장</h2><img class="room-hero iso" alt="" src="${isoTile('hall')}"><p class="hint">방주의 중심. 승강기가 지상과 지하를 잇고, 끊어진 선로는 어둠 속 터널로 이어진다.</p>
      <h3 style="font-family:var(--serif);margin:10px 0 4px">주민 ${ark.residents}</h3>
      <p class="hint" style="margin:0 0 6px">각인 가진 사람 ${marked}명 · 서로에 대한 신뢰 평균 ${avg}/100. 사람은 사람을 쉽게 믿지 않는다. 함께 위기를 넘겨야만 오른다.</p>
      <div class="roster">${roster || '<p class="hint">주민 정보가 없습니다.</p>'}</div>`);
  }

  // ── 시트 ────────────────────────────────────────────────
  function openSheet(html) { $('#sheetBody').innerHTML = html; $('#sheetBg').classList.add('on'); $('#sheet').classList.add('on'); }
  function closeSheet() { $('#sheetBg').classList.remove('on'); $('#sheet').classList.remove('on'); stopCam(); clearInterval(evTimer); }
  $('#sheetBg').addEventListener('click', closeSheet);

  // ── 건설 ────────────────────────────────────────────────
  function paintRoomCanvases() { document.querySelectorAll('#sheetBody canvas[data-room]').forEach(cv => { const id = cv.dataset.room; if (ROOM3D[id]) { const im = document.createElement('img'); im.className = cv.className; im.alt = ''; im.src = `/static/art/rooms3d/${id}.jpg`; cv.replaceWith(im); } else window.ROOMS.draw(cv, id); }); }
  function openBuild(slot, built) {
    const surface = slot < SURFACE_SLOTS;
    if (built) {
      const room = ark.rooms.find(r => r.slot === slot), s = rooms[room.id];
      openSheet(`<div class="eyebrow">${surface ? '지상' : '지하'} · ${s.name}</div><h2>${s.name}</h2><img class="room-hero iso" alt="" src="${isoTile(room.id)}"><p class="hint">${esc(s.desc)}</p>
        <p class="hint" style="font-family:var(--mono);font-size:.7rem">생산 ${Object.entries(s.produces).map(([k, v]) => typeof v === 'number' ? `${RES_KO[k]} +${v} / 8시간` : `대항 카드(${v})`).join(', ')}<br>대항 ${s.counters.map(c => '#' + c).join(' ')}${s.adjacency_bonus ? '<br>인접 보너스: ' + Object.keys(s.adjacency_bonus).map(k => rooms[k].name).join(', ') : ''}</p>`);
      return;
    }
    const opts = Object.entries(rooms).map(([id, s]) => {
      const lack = Object.entries(s.cost).filter(([k, v]) => (ark.resources[k] || 0) < v);
      const cost = Object.entries(s.cost).map(([k, v]) => `<span class="${(ark.resources[k] || 0) < v ? 'lack' : ''}">${RES_KO[k]} ${v}</span>`).join(' · ');
      return `<div class="room-opt"><img class="thumb iso" alt="" src="${isoTile(id)}"><div><div class="nm"><i style="background:${s.light}"></i>${s.name}</div><div class="cost">${cost}</div></div><button class="btn ${lack.length ? 'ghost' : ''}" data-r="${id}" ${lack.length ? 'disabled' : ''}>짓기</button><div class="ds">${esc(s.desc)}</div></div>`;
    }).join('');
    openSheet(`<div class="eyebrow">${surface ? 'B0 지상 · 재건' : '지하 · 굴착'}</div><h2>${surface ? '폐허 위에 무엇을 세울까요?' : '무엇을 파낼까요?'}</h2><p class="hint">방은 8시간마다 생산하고, 자리를 비워도 최대 3번까지 쌓입니다. 유물을 해독해 자원을 모으세요.</p>${opts}`);
    paintRoomCanvases();
    $('#sheetBody').onclick = async (e) => {
      const b = e.target.closest('button[data-r]'); if (!b) return;
      try { const st = await api('/api/ark/build', { room_id: b.dataset.r, slot }); ark = { ...ark, ...st }; toast(`${rooms[b.dataset.r].name}을(를) 지었습니다`); closeSheet(); renderHud(); renderScene(); }
      catch (err) { toast(err.message); }
    };
  }

  // ── 스캔 ────────────────────────────────────────────────
  let stream = null, detector = null, scanning = false, lastCode = '', lastAt = 0, busy = false;
  const SAMPLES = [['8801043015097', '식품'], ['9791162241905', '도서'], ['8806011000013', '의약'], ['8809000111110', '문구'], ['4901234567894', '미지 가문'], ['8801044007770', '패턴']];
  $('#dkScan').addEventListener('click', () => {
    openSheet(`<div class="eyebrow">성문 해독</div><h2>물건의 줄무늬를 리더에 비추세요</h2><p class="hint">집과 편의점의 모든 것이 유물입니다. 책(ISBN)은 청사진이 됩니다.</p>
      <div class="cam" id="cam"><video id="video" playsinline muted></video><div class="reticle"></div><div class="status" id="camstatus">카메라 준비 중…</div></div>
      <div class="manual"><input id="manual" inputmode="numeric" placeholder="바코드 숫자 13자리" maxlength="14"><button class="btn" id="manualBtn">해독</button></div>
      <div class="samples">${SAMPLES.map(([c, l]) => `<button data-c="${c}">${l} ${c}</button>`).join('')}</div>
      <div class="quota">오늘의 해독 ${ark.scans_today} / ${ark.scan_cap} · 같은 물건은 2회차 50%, 3회차 10%</div><div id="pickerWrap" hidden></div>`);
    $('#manualBtn').onclick = () => handleCode($('#manual').value);
    $('#manual').onkeydown = (e) => { if (e.key === 'Enter') handleCode(e.target.value); };
    $('#sheetBody').querySelector('.samples').onclick = (e) => { const b = e.target.closest('button'); if (b) handleCode(b.dataset.c); };
    startCam();
  });
  async function startCam() {
    const st = $('#camstatus'), cam = $('#cam'); if (!st) return;
    if (!('BarcodeDetector' in window)) { cam.classList.add('off'); st.textContent = '이 브라우저는 카메라 바코드 인식을 지원하지 않습니다 — 아래 숫자 입력 또는 샘플을 쓰세요'; return; }
    if (!navigator.mediaDevices || !window.isSecureContext) { cam.classList.add('off'); st.textContent = '카메라는 HTTPS 또는 localhost에서만 열립니다'; return; }
    try {
      detector = detector || new BarcodeDetector({ formats: ['ean_13', 'upc_a', 'ean_8'] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1280 } } });
      const v = $('#video'); v.srcObject = stream; await v.play();
      st.textContent = '성문을 붉은 선에 맞추세요'; scanning = true; loop();
    } catch (e) { cam.classList.add('off'); st.textContent = '카메라를 열 수 없습니다: ' + e.message; }
  }
  function stopCam() { scanning = false; if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; } }
  async function loop() {
    if (!scanning) return;
    try {
      const v = $('#video'); if (!v) { scanning = false; return; }
      const codes = await detector.detect(v);
      const c = codes.find(x => x.rawValue && x.rawValue.length >= 12);
      if (c && !busy && (c.rawValue !== lastCode || Date.now() - lastAt > 4000)) { lastCode = c.rawValue; lastAt = Date.now(); if (navigator.vibrate) navigator.vibrate(30); await handleCode(c.rawValue); }
    } catch { /* skip frame */ }
    setTimeout(loop, 220);
  }
  async function handleCode(raw, userCategory) {
    if (busy) return; busy = true;
    try {
      const code = String(raw).replace(/\D/g, '');
      if (userCategory === undefined) {
        const pk = await api(`/api/peek?barcode=${code}`);
        if (pk.needs_category) { showPicker(pk); busy = false; return; }
      }
      const r = await api('/api/scan', { barcode: code, user_category: userCategory || null });
      ark && (ark.resources = r.resources, ark.scans_today = r.scans_today); renderHud();
      closeSheet(); openPack(r);
    } catch (e) { toast(e.message); }
    busy = false;
  }
  function showPicker(pk) {
    const w = $('#pickerWrap'); if (!w) return; w.hidden = false;
    w.innerHTML = `<p class="hint" style="margin-top:12px">이 가문의 성문은 처음입니다. 이 물건은 무엇입니까?</p><div class="picker">${pk.categories.map(c => `<button data-c="${c}">${CAT_KO[c]}<small>${c}</small></button>`).join('')}<button data-c="">모름<small>unknown</small></button></div>`;
    w.querySelector('.picker').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; handleCode(pk.barcode, b.dataset.c || null); };
  }
  function openPack(r) {
    const ov = $('#overlay'), pack = $('#pack'); ov.classList.add('on'); ov.classList.remove('ready'); pack.className = 'pack';
    pack.innerHTML = `<div class="paper l">RELIC</div><div class="paper r">PACK</div>`; pack.appendChild(cardEl(r.card));
    const g = Object.entries(r.gained).map(([k, v]) => `<b>${RES_KO[k]} +${v}</b>`).join(' ');
    $('#gain').innerHTML = `${r.first_time ? '<span class="first">✦ 도감에 처음 기록된 유물</span><br>' : ''}${g || '<span>이미 해독한 성문 — 얻은 것 없음</span>'}${r.rescan_multiplier < 1 && r.rescan_multiplier > 0 ? `<br><span>재해독 ×${r.rescan_multiplier}</span>` : ''}`;
    setTimeout(() => pack.classList.add('tear'), 350);
    setTimeout(() => ov.classList.add('ready'), 1200);
    if (navigator.vibrate && ['rare', 'epic', 'legendary'].includes(r.card.rarity)) setTimeout(() => navigator.vibrate([40, 60, 80]), 900);
  }
  $('#closePack').addEventListener('click', () => { $('#overlay').classList.remove('on'); refresh(); });

  // ── 카드 ────────────────────────────────────────────────
  $('#dkCards').addEventListener('click', async () => {
    const codex = await api(`/api/codex?uid=${uid}`);
    openSheet(`<div class="eyebrow">유물 카드</div><h2>손패와 도감</h2><p class="hint">태그가 있는 카드는 쪽지(사건)에 대항할 때 쓸 수 있습니다.</p>
      <div class="codex">${codex.map(c => `<div><b>${CAT_KO[c.category]}</b>${c.found} / ${c.total}<div class="bar"><i style="width:${c.total ? c.found / c.total * 100 : 0}%"></i></div></div>`).join('')}</div><div class="hand" id="hand"></div>`);
    const h = $('#hand');
    if (!ark.hand.length) h.innerHTML = '<div class="waiting" style="grid-column:1/-1">아직 손패가 없습니다. 태그 있는 유물을 해독하면 여기에 쌓입니다.</div>';
    [...ark.hand].reverse().forEach(c => h.appendChild(cardEl(c)));
  });

  // ── 쪽지(사건) ──────────────────────────────────────────
  let evTimer = null;
  $('#dkEvent').addEventListener('click', openEvent);
  async function openEvent() {
    await refresh();
    const d = await api(`/api/event/today?uid=${uid}`); const ev = d.event, st = d.state, pos = !!ev.positive;
    openSheet(`<div class="eyebrow">오늘의 쪽지 · DAY ${st.day}</div><h2>쪽지가 도착했습니다</h2><p class="hint">시간 안에 대항 카드를 누르세요. 대항할 방이 있으면 카드 없이도 반은 막습니다.</p>
      <div class="slip ${pos ? 'pos' : ''}" id="slip"><div class="timer" id="tm">${ev.timer_sec}</div><div class="fac">${ev.tribe ? esc(TRIBE_KO[ev.tribe] || ev.tribe) + ' 부족' : esc(FAC_KO[ev.faction] || ev.faction)} · 심각도 ${ev.severity}</div><h3>${esc(ev.name)}</h3><p>${esc(ev.text)}</p>
      <div class="tags">대항 태그 ${ev.counter_tags.map(t => `<span>#${esc(t)}</span>`).join('')}${ev.counter_room ? ` · 방 <span>${rooms[ev.counter_room].name}${d.room_backup ? ' ✓' : ' ✗'}</span>` : ''}</div></div>
      <div class="counter-row" id="crow"></div><div class="result" id="result"></div>`);
    requestAnimationFrame(() => setTimeout(() => $('#slip').classList.add('in'), 30));
    if (st.resolved) { showResult({ countered: st.countered, how: st.how, applied: {} }, ev, true); $('#tm').textContent = '·'; return; }
    const row = $('#crow');
    if (!ark.hand.length) row.innerHTML = `<div class="none">손패가 없습니다.<br>대항할 방이 있으면 50%로 막습니다.</div>`;
    ark.hand.forEach(c => { const el = cardEl(c, { badge: false }); if (d.matching_card_ids.includes(c.id)) el.classList.add('match'); el.addEventListener('click', () => resolveEvent(c.id, ev)); row.appendChild(el); });
    let left = ev.timer_sec; const tm = $('#tm');
    clearInterval(evTimer);
    evTimer = setInterval(() => { left -= 1; if (!$('#tm')) { clearInterval(evTimer); return; } tm.textContent = left; if (left <= 0) { clearInterval(evTimer); resolveEvent(null, ev); } }, 1000);
  }
  async function resolveEvent(cardId, ev) {
    clearInterval(evTimer);
    try { const r = await api('/api/event/resolve', { card_id: cardId }); ark = { ...ark, ...r.state }; renderHud(); renderScene(); showResult(r, ev, false); }
    catch (e) { toast(e.message); }
  }
  // "겪어본 적 없는 위험을 넘긴 자만 변한다" — 결과 화면의 각인 연출
  // 받침 여부로 조사 고르기 (이/가, 은/는)
  const josa = (w, withJong, without) => { const c = String(w).charCodeAt(String(w).length - 1); return (c >= 0xAC00 && c <= 0xD7A3 && (c - 0xAC00) % 28) ? withJong : without; };
  function imprintBlock(r) {
    const ns = r.new_imprints || []; if (!ns.length) return '';
    return `<div class="imprint-news">${ns.map(n => `<div class="one"><b>${esc(n.resident)}에게 각인 「${esc(n.imprint.name)}」${josa(n.imprint.name, '이', '가')} 생겼다</b>
      <div class="vis">${esc(n.line)}</div>
      <div class="meta">외형 — ${esc(n.imprint.visual)} · 대가 — ${esc(n.imprint.cost || '없음')}</div>
      ${n.evolved ? `<div class="evoline">세 번째 각인. ${esc(n.resident)}의 역할이 「${esc(n.evolved_ko)}」로 진화했다.</div>` : ''}</div>`).join('')}</div>`;
  }
  function showResult(r, ev, replay) {
    const el = $('#result'); if (!el) return; el.className = 'result on ' + (r.countered ? 'ok' : 'bad');
    const how = { card: '대항 카드가 통했습니다', room: '방이 대신 막았습니다', role: (r.hero ? `${esc(r.hero.name)}(${esc(r.hero.role_ko)})이(가) 나서서 막았습니다` : '주민이 나서서 막았습니다'), none: '' }[r.how] || '';
    const APPLIED_KO = { injured: '부상', resident: '합류', capture: '포획', free_pack: '무료 팩', spot_clue: '힐링 스팟 단서', flag: '기록' };
    const delta = Object.entries(r.applied || {}).filter(([k]) => !['newcomer', 'hero', 'flags'].includes(k))
      .map(([k, v]) => typeof v === 'number' ? `${RES_KO[k] || APPLIED_KO[k] || k} ${v > 0 ? '+' : ''}${v}` : `${APPLIED_KO[k] || k}: ${esc(v)}`).join(' · ');
    el.innerHTML = `<b>${r.countered ? (ev.positive ? '기회를 잡았습니다' : '막아냈습니다') : (ev.positive ? '기회가 지나갔습니다' : '피해를 입었습니다')}</b> ${how ? '— ' + how : ''}<div class="delta">${delta || (replay ? '오늘 쪽지는 이미 처리되었습니다' : '변화 없음')}</div>${r.used_card ? `<div class="delta">사용한 카드: ${esc(r.used_card.name)}</div>` : ''}${r.applied && r.applied.newcomer ? `<div class="delta" style="color:#3f9a68">새 주민 합류: ${esc(r.applied.newcomer.name)} · ${esc(r.applied.newcomer.role_ko)} — ${esc(r.applied.newcomer.ability)}</div>` : ''}${imprintBlock(r)}${typeof r.trust_delta === 'number' ? `<div class="delta">서로에 대한 신뢰 ${r.trust_delta > 0 ? '+' : ''}${r.trust_delta}</div>` : ''}<div class="delta" style="margin-top:6px">다음 쪽지는 내일 도착합니다.</div>`;
    const crow = $('#crow'); if (crow) crow.innerHTML = '';
  }

  window.ARK = { openEvent, refresh };
  $('#zin').addEventListener('click', () => { const vp = $('#world'); zoomAt(1.3, vp.clientWidth / 2, vp.clientHeight / 2); });
  $('#zout').addEventListener('click', () => { const vp = $('#world'); zoomAt(1 / 1.3, vp.clientWidth / 2, vp.clientHeight / 2); });
  $('#zfit').addEventListener('click', () => fitView(true));
  refresh();
})();
