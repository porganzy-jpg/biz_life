/* 잔해 방주 — "살아가는 모습" 레이어
   세계관 인트로 · 방주 일지 티커 · 날씨(안개/비/까치) · 주민 왕래와 일하는 말풍선 · 지상에 나타나는 오늘의 위협 */
(() => {
  const $ = (s) => document.querySelector(s);
  const world = $('#world'), scene = $('#scene');
  let ark = null, rooms = null, todayEvent = null;

  // ── 결정적 난수 (day 기준 날씨) ──────────────────────────
  function rng(seed) { let h = 2166136261; for (const ch of String(seed)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return () => { h += 0x6D2B79F5; let t = h; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const WEATHER = [['맑음', 'clear'], ['안개', 'fog'], ['비', 'rain'], ['바람', 'wind'], ['안개', 'fog'], ['맑음', 'clear']];
  const timeOf = () => { const h = new Date().getHours(); return h < 5 ? '깊은 밤' : h < 10 ? '새벽' : h < 17 ? '낮' : h < 21 ? '저녁' : '밤'; };

  // ── 1. 세계관 인트로 (첫 방문) ───────────────────────────
  function intro() {
    let seen = /nointro/.test(location.search); try { seen = seen || localStorage.getItem('ark_intro') === '1'; } catch { }
    if (seen) return;
    const ov = document.createElement('div'); ov.className = 'intro';
    ov.innerHTML = `<div class="intro-in"><p class="l1">대침묵 213년.</p><p class="l2">문명은 잊혔다. 남은 것은 물건에 새겨진 검은 줄무늬뿐.</p><p class="l3">당신은 그것을 읽을 수 있는 몇 안 되는 사람이다.<br>주민 셋과 함께, 폐허 아래에 방주를 판다.</p><button class="btn lamp" id="introGo">방주로 내려가기</button></div>`;
    $('#app').appendChild(ov);
    requestAnimationFrame(() => ov.classList.add('on'));
    $('#introGo').onclick = () => { ov.classList.add('out'); setTimeout(() => ov.remove(), 900); try { localStorage.setItem('ark_intro', '1'); } catch { } };
  }

  // ── 2. 일지 티커 ─────────────────────────────────────────
  const MOOD = {
    clear: ['하늘이 드물게 맑다. 지상 정찰에 좋은 날.', '까치들이 조용하다. 불길할 정도로.'],
    fog: ['안개가 콘크리트 숲을 삼켰다. 소리만 남는다.', '안개 속에서 누군가 걷는 소리. 우리 사람이 아니다.'],
    rain: ['비가 온다. 정수실이 없다면 빗물을 받아라.', '빗물이 지하 강으로 스며든다. 균류가 좋아하는 날.'],
    wind: ['바람이 폐허의 간판을 흔든다. 낡은 성문이 떨어진다.', '바람 덕에 라디오탑 신호가 멀리 간다.'],
  };
  function journal(w) {
    let el = $('#journal'); if (!el) { el = document.createElement('div'); el.id = 'journal'; el.className = 'journal'; scene.prepend(el); }
    const r = rng('mood' + ark.day + w[1]); const lines = MOOD[w[1]];
    const low = ark.resources.food <= 2 ? ' 식량이 바닥을 보인다.' : ark.resources.water <= 2 ? ' 물이 모자란다.' : ark.injured ? ` 부상자 ${ark.injured}명이 의무실을 기다린다.` : '';
    el.innerHTML = `<span class="j-meta">DAY ${ark.day} · ${timeOf()} · ${w[0]}</span><span class="j-txt">${lines[Math.floor(r() * lines.length)]}${low}</span>`;
  }

  // ── 3. 날씨 레이어 ───────────────────────────────────────
  let rainCv = null, rainOn = false;
  function weatherLayer(w) {
    let fog = $('#fog'); if (!fog) { fog = document.createElement('div'); fog.id = 'fog'; fog.className = 'fog'; scene.appendChild(fog); }
    fog.style.opacity = w[1] === 'fog' ? .75 : w[1] === 'rain' ? .35 : .18;
    if (!rainCv) { rainCv = document.createElement('canvas'); rainCv.className = 'rain'; rainCv.width = 480; rainCv.height = 200; scene.appendChild(rainCv); }
    rainOn = w[1] === 'rain'; rainCv.style.display = rainOn ? 'block' : 'none';
    if (rainOn) rainLoop();
    crows(w[1] !== 'rain');
  }
  function rainLoop() {
    if (!rainOn) return; const x = rainCv.getContext('2d'); x.clearRect(0, 0, 480, 200); x.strokeStyle = 'rgba(200,210,220,.35)'; x.lineWidth = 1;
    for (let i = 0; i < 70; i++) { const px = Math.random() * 480, py = Math.random() * 200; x.beginPath(); x.moveTo(px, py); x.lineTo(px - 3, py + 14); x.stroke(); }
    setTimeout(() => requestAnimationFrame(rainLoop), 70);
  }
  let crowTimer = null;
  function crows(on) {
    clearInterval(crowTimer); document.querySelectorAll('.crow').forEach(c => c.remove()); if (!on) return;
    const spawn = () => { for (let i = 0; i < 3; i++) { const c = document.createElement('i'); c.className = 'crow'; c.style.top = (30 + Math.random() * 70) + 'px'; c.style.animationDuration = (9 + Math.random() * 6) + 's'; c.style.animationDelay = (i * .6) + 's'; scene.appendChild(c); setTimeout(() => c.remove(), 16000); } };
    spawn(); crowTimer = setInterval(spawn, 22000);
  }

  // ── 4. 자유 이동 주민 (경로 기반) ─────────────────────────
  // 주민은 역 홀을 허브로 지어진 방들 사이를 걸어 다니고, 승강기로 지상에 올라가 둘러본다.
  const WORK = { hall: ['승강기를 손보는 중', '선로 끝을 바라보는 중', '모닥불을 지키는 중'], pantry: ['통조림을 세는 중', '말린 실을 나누는 중'], well: ['물을 거르는 중', '물통을 채우는 중'], infirmary: ['붕대를 감는 중', '약을 세는 중'], library: ['청사진을 읽는 중', '책을 말리는 중'], lot: ['지상을 살피는 중', '채소밭에 물을 주는 중', '하늘을 올려다보는 중'], idle: ['벽에 기대어 쉬는 중', '성문을 들여다보는 중'] };
  const ROLE_WORK = { scout: ['지상을 정찰하는 중', '발자국을 살피는 중'], cook: ['냄비를 저어보는 중', '말린 실을 끓이는 중'], medic: ['붕대를 개는 중', '약 상자를 정리하는 중'], engineer: ['파이프를 두드리는 중', '배터리를 잇는 중'], farmer: ['씨앗을 세는 중', '화분을 옮기는 중'], scholar: ['성문을 베끼는 중', '책 냄새를 맡는 중'], trader: ['교역품을 헤아리는 중', '누군가와 값을 재는 중'], kid: ['돌멩이를 모으는 중', '벽에 그림을 그리는 중', '까치를 쫓는 중'] };
  let actors = [], animT = null, lastT = 0;
  const SPEED = 42; // px/s (월드 기준)

  function builtCells() { return [...document.querySelectorAll('.iso-cell.built')].map(c => ({ i: +c.dataset.i, j: +c.dataset.j, stage: c.dataset.stage, room: c.dataset.room })); }
  function posOf(c, jit) { const st = c.stage === 'surf' ? window.WORLD.surf : window.WORLD.under; const p = window.cellCenter(st, c.i, c.j); const W = window.ISO.W * 0.5, H = window.ISO.H * 0.5; const r = jit || { a: 0, b: 0 }; return { x: p.x + (r.a - r.b) * W * 0.28, y: p.y + (r.a + r.b) * H * 0.28, z: (c.i + c.j) * 10 + c.i + 15 + (c.stage === 'surf' ? 0 : 100) }; }
  function jitter() { return { a: Math.random() * 2 - 1, b: Math.random() * 2 - 1 }; }

  function spawnActors() {
    const layer = document.getElementById('actors'); if (!layer) return;
    layer.innerHTML = ''; actors = [];
    const cells = builtCells(); const hall = cells.find(c => c.room === 'hall') || cells[0]; if (!hall) return;
    const list = (ark.residents_list && ark.residents_list.length) ? ark.residents_list : Array.from({ length: ark.residents }, (_, i) => ({ name: '주민 ' + (i + 1), role: ['cook', 'engineer', 'medic'][i % 3], injured: i < ark.injured }));
    list.forEach((r, i) => {
      const el = document.createElement('div'); el.className = 'actor' + (r.injured ? ' hurt' : '') + (r.role === 'kid' ? ' kid' : '');
      el.style.setProperty('--h', (r.role === 'kid' ? 52 : 70) + 'px');
      el.innerHTML = `<img alt="" src="/static/art/chars/${r.role}_dl_b.png" onerror="this.src='/static/art/chars/fallback.png'"><i class="lamp"></i><span class="nm">${r.name}</span><span class="say"></span>`;
      layer.appendChild(el);
      const home = cells[(i + 1) % cells.length] || hall;
      const start = posOf(home, jitter());
      const a = { el, r, x: start.x, y: start.y, cell: home, target: null, path: [], wait: 1 + Math.random() * 3, frame: 0, ft: 0, facing: 'dl', z: start.z };
      actors.push(a); place(a);
      const say = el.querySelector('.say');
      a.talk = () => { const pool = (r.injured ? ['기침을 하는 중'] : (Math.random() < .5 && ROLE_WORK[r.role]) ? ROLE_WORK[r.role] : (WORK[a.cell.room] || WORK.idle)); say.textContent = pool[Math.floor(Math.random() * pool.length)]; say.classList.add('on'); setTimeout(() => say.classList.remove('on'), 2600); };
    });
    if (!animT) { lastT = performance.now(); animT = requestAnimationFrame(tick); }
  }
  function place(a) { a.el.style.left = a.x + 'px'; a.el.style.top = a.y + 'px'; a.el.style.zIndex = a.z; }
  function chooseNext(a) {
    const cells = builtCells(); const hall = cells.find(c => c.room === 'hall');
    const others = cells.filter(c => !(c.i === a.cell.i && c.j === a.cell.j && c.stage === a.cell.stage));
    const surf = others.filter(c => c.stage === 'surf'), und = others.filter(c => c.stage !== 'surf');
    let dest;
    if (a.r.role === 'scout' && surf.length && Math.random() < .6) dest = surf[Math.floor(Math.random() * surf.length)];
    else if (a.r.role === 'farmer' && surf.length && Math.random() < .5) dest = surf[Math.floor(Math.random() * surf.length)];
    else dest = (Math.random() < .25 && surf.length) ? surf[Math.floor(Math.random() * surf.length)] : (und.length ? und[Math.floor(Math.random() * und.length)] : a.cell);
    // 경로: 지하 방 ↔ 지하 방은 홀 경유. 지하 ↔ 지상은 홀에서 승강기(페이드) 후 지상 칸.
    const path = [];
    const viaHall = hall && a.cell.room !== 'hall' && a.cell.stage !== 'surf';
    if (a.cell.stage === 'surf' && dest.stage === 'surf') { path.push({ cell: dest, pos: posOf(dest, jitter()) }); }
    else if (a.cell.stage === 'surf' && dest.stage !== 'surf') { path.push({ cell: hall, pos: posOf(hall, { a: 0.6, b: 0.6 }), lift: true }); if (dest.room !== 'hall') path.push({ cell: dest, pos: posOf(dest, jitter()) }); }
    else if (dest.stage === 'surf') { if (viaHall) path.push({ cell: hall, pos: posOf(hall, { a: 0.6, b: 0.6 }) }); path.push({ cell: dest, pos: posOf(dest, jitter()), lift: true }); }
    else { if (viaHall && dest.room !== 'hall') path.push({ cell: hall, pos: posOf(hall, jitter()) }); path.push({ cell: dest, pos: posOf(dest, jitter()) }); }
    a.path = path;
  }
  function tick(now) {
    const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;
    for (const a of actors) {
      if (a.path.length === 0) {
        a.wait -= dt;
        if (a.wait <= 0) { chooseNext(a); a.wait = 3 + Math.random() * 6; if (Math.random() < .5) a.talk(); }
        continue;
      }
      const wp = a.path[0];
      if (wp.lift && !a.lifting) {   // 승강기: 페이드 아웃 → 순간이동 → 페이드 인
        a.lifting = true; a.el.style.transition = 'opacity .5s'; a.el.style.opacity = 0;
        setTimeout(() => { a.x = wp.pos.x; a.y = wp.pos.y; a.z = wp.pos.z; a.cell = wp.cell; place(a); a.el.style.opacity = 1; setTimeout(() => { a.lifting = false; a.path.shift(); a.el.style.transition = ''; }, 500); }, 550);
        continue;
      }
      if (a.lifting) continue;
      const dx = wp.pos.x - a.x, dy = wp.pos.y - a.y, d = Math.hypot(dx, dy);
      if (d < 2) { a.x = wp.pos.x; a.y = wp.pos.y; a.cell = wp.cell; a.z = wp.pos.z; a.path.shift(); place(a); setFrame(a, 'b'); if (a.path.length === 0 && Math.random() < .7) a.talk(); continue; }
      const step = Math.min(d, SPEED * dt * (a.r.role === 'kid' ? 1.25 : 1));
      a.x += dx / d * step; a.y += dy / d * step;
      a.z = Math.round(a.cell.z !== undefined ? a.cell.z : wp.pos.z) ; a.z = wp.pos.z;
      const dir = dy >= 0 ? (dx < 0 ? 'dl' : 'dr') : (dx < 0 ? 'ul' : 'ur');
      a.el.classList.toggle('flip', dir === 'dr' || dir === 'ur');
      a.facing = (dir === 'dl' || dir === 'dr') ? 'dl' : 'ul';
      a.ft += dt; if (a.ft > 0.22) { a.ft = 0; a.frame ^= 1; setFrame(a, a.frame ? 'a' : 'b'); }
      place(a);
    }
    animT = requestAnimationFrame(tick);
  }
  function setFrame(a, f) { const im = a.el.querySelector('img'); const src = `/static/art/chars/${a.r.role}_${a.facing}_${f}.png`; if (im.getAttribute('src') !== src) im.src = src; }

  function fireflies() {
    const layer = document.getElementById('actors'); if (!layer || !window.WORLD) return;
    const ff = document.createElement('div'); ff.className = 'fireflies';
    for (let i = 0; i < 26; i++) { const f = document.createElement('i'); f.className = 'ff'; f.style.left = (Math.random() * window.WORLD.w) + 'px'; f.style.top = (window.WORLD.under.oy - 200 + Math.random() * 600) + 'px'; f.style.setProperty('--d', (6 + Math.random() * 8) + 's'); f.style.setProperty('--dx', (Math.random() * 80 - 40) + 'px'); f.style.setProperty('--dy', (Math.random() * -80) + 'px'); f.style.animationDelay = (-Math.random() * 8) + 's'; ff.appendChild(f); }
    layer.appendChild(ff);
  }
  function residents() { spawnActors(); fireflies(); }

  // ── 5. 지상에 나타나는 오늘의 위협 ──────────────────────
  function threat() {
    document.querySelectorAll('.threat').forEach(t => t.remove());
    if (!todayEvent || (ark.today_event && ark.today_event.resolved)) return;
    const ev = todayEvent; const t = document.createElement('button'); t.className = 'threat ' + ev.faction; t.type = 'button';
    const ICON = { scavs: '<i class="fig"></i><i class="fig"></i>', mutant: '<i class="wing"></i><i class="wing"></i><i class="wing"></i>', mycel: '<i class="spore"></i><i class="spore"></i>', machine: '<i class="eye"></i>', world: '<i class="note"></i>' };
    t.innerHTML = `${ICON[ev.faction] || ICON.world}<span class="t-lab">${ev.positive ? '무언가 다가온다' : '위협 접근'} · ${ev.name}</span>`;
    t.onclick = () => window.ARK && window.ARK.openEvent();
    scene.appendChild(t);
  }

  // ── 갱신 ────────────────────────────────────────────────
  async function update(detail) {
    ark = detail.ark; rooms = detail.rooms;
    try { const d = await fetch(`/api/event/today?uid=${detail.uid}`).then(r => r.json()); todayEvent = d.event; ark.today_event = d.state; } catch { }
    const w = WEATHER[Math.floor(rng('w' + ark.day)() * WEATHER.length)];
    journal(w); weatherLayer(w); residents(); threat();
  }
  window.addEventListener('ark:update', (e) => update(e.detail));
  window.addEventListener('ark:scene', () => { if (ark) { residents(); } });
  intro();
})();
