/* 잔해 방주 — 1막 거점 화면(정면 평면 단면) + **배치 방어 전투**.
 *
 * 근거
 *   DECISIONS 2026-09-23  ① 1막 거점은 정면 평면 단면(원근 없음) ② 성장 방향은 아래
 *                         ③ 방마다 고유 색(전부 따뜻한 쪽, 물보다 밝게)
 *   DECISIONS 2026-10-01  ④ 1막 전투는 배치 방어 ⑤ 종마다 막는 법이 다르다
 *                         ⑥ 죽이는 것이 주된 동사가 아니다 ⑦ 캐릭터는 P2 도트
 *   docs/COMBAT_AND_DEFENSE.md  §3 흐름 · §4 생물별 대응 · §6 아늑함 안전장치 · §6.5 도구 일곱
 *   docs/refs/REF_CROSS_SECTION.md  §1 원리 10가지(두꺼운 검은 테두리, 빈 방 없음, UI 는 가장자리)
 *   docs/refs/REF_ART_FLAT_FOLK.md  §1·§5 평면 채색·음영 1~2단·청록은 물에만
 *
 * 이 화면의 동사는 다섯이다: **옮기다 · 끄다 · 모이다 · 들이다 · 맞서다.** 공격 버튼은 없다.
 */
(() => {
  'use strict';

  // ── 세계 좌표(px). 1층 = 방 2칸 + 가운데 척추 ──────────────────
  const ROOM_W = 208, ROOM_H = 112, SPINE_W = 70, FLOOR_GAP = 18;
  const FLOOR_PITCH = ROOM_H + FLOOR_GAP;          // 층 간격
  const DEPTH_PER_FLOOR = 60;                      // m. server.py 의 같은 상수와 맞춘다
  const PAD = 8;                                   // 방 둘레 어두운 여백(= 물)
  let DOME_FLOOR = 1;                              // 깊이 0 m 의 층(= 시작 방 slot 2 의 층). 서버가 내려준다

  // 깊이 구역: 화면 위는 갈 수 없는 광층, 아래는 해구 (REF_CROSS_SECTION §3)
  const M2PX = FLOOR_PITCH / DEPTH_PER_FLOOR;      // 깊이 1 m = 화면 몇 px. 서버 좌표(m) → 세계(px)
  // 경계는 미터로 정하고 px 로 옮긴다 — server.py DEPTH_ZONES 와 같은 값이어야 한다(0 / 150 / 210 m)
  const ZONES = [
    { y0: -1600,        y1: -100 * M2PX, ko: '광층',    note: '갈 수 없다' },
    { y0: -100 * M2PX,  y1: -45 * M2PX,  ko: '박광층',  note: '실루엣의 층' },
    { y0: -45 * M2PX,   y1: 150 * M2PX,  ko: '무광층',  note: '돔이 사는 층' },
    { y0: 150 * M2PX,   y1: 210 * M2PX,  ko: '해구 문턱', note: '여기부터 값이 달라진다' },
    { y0: 210 * M2PX,   y1: 1600,        ko: '해구',    note: '가장 오래된 성문' },
  ];
  // 물색: 위(광층)에서 아래(해구)로. 청록~남색~검정만 쓴다(FLAT_FOLK §5 — 물만 차갑다)
  const WATER = [[-1600, '#1e737c'], [-500, '#14545e'], [-217, '#0d3b45'], [-97, '#0a2a33'],
                 [130, '#07202a'], [325, '#04141c'], [455, '#020a10'], [1600, '#01060a']];

  // 방 색: 전부 따뜻한 쪽, 명도는 물보다 항상 높게 (DECISIONS 2026-09-23 D1 수정)
  const ROOM_COLOR = {
    pantry:    { base: '#c08a33', shade: '#8c6222', floor: '#5c421a' },  // 황토
    well:      { base: '#d8c9a3', shade: '#a2946f', floor: '#6d6349' },  // 크림/뼈
    infirmary: { base: '#8c9161', shade: '#666a45', floor: '#454833' },  // 탁한 올리브
    library:   { base: '#c6a23a', shade: '#8f7326', floor: '#5e4c1c' },  // 황금 황토
    workshop:  { base: '#b06a3a', shade: '#7f4b28', floor: '#50301b' },  // 적동(공방 — 불을 쓰는 방)
    rock:      { base: '#a2603a', shade: '#74432a', floor: '#4d2d1c' },
    lot:       { base: '#b8ae9c', shade: '#877f70', floor: '#57534a' },
    _default:  { base: '#b4712f', shade: '#815022', floor: '#54351a' },
  };
  const ROLE_COLOR = {
    scout: '#8c9161', cook: '#c08a33', medic: '#d8c9a3', engineer: '#b4712f',
    farmer: '#8a7a4a', scholar: '#c6a23a', trader: '#a2603a', kid: '#e6d7b0',
  };
  const RES_KO = { food: '식량', water: '물', med: '의약', power: '전력', parts: '부품', morale: '사기',
                   cloth: '직물', trade: '교역', knowledge: '지식', scrap: '잔해', chem: '화학',
                   counter_card: '대항 카드', blueprint_progress: '청사진' };
  const CORE_RES = ['food', 'water', 'parts', 'morale'];
  const KIND_KO = { consumable: '소모', install: '설치', durable: '내구', permanent: '영구' };
  const STAGE_LABEL = { sound: '소리', silhouette: '실루엣', contact: '접촉', done: '지나갔다' };

  // ── 바탕 ─────────────────────────────────────────────────
  const $ = (s) => document.querySelector(s);
  const cv = $('#cv'), ctx = cv.getContext('2d');
  const uid = (() => {
    try { let u = localStorage.getItem('ark_uid'); if (!u) { u = 'u' + Math.random().toString(36).slice(2, 10); localStorage.setItem('ark_uid', u); } return u; }
    catch (e) { return 'anon'; }
  })();
  const qs = new URLSearchParams(location.search);
  // p2 = 48px 생활형 도트(DECISIONS 2026-10-01 확정). 아직 front/p2/ 가 없으면 조용히 c→b→a 로 내려가고
  // 그것도 없으면 색 사각형. 폴더만 들어오면 코드 수정 없이 도트가 켜진다.
  const CHAR_VARIANT = qs.get('chars') || 'p2';
  const CHAR_FALLBACK = ['p2', 'c', 'b', 'a'];
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let ark = null, catalog = {}, slots = 10, floorSlots = 2, spots = [];
  let cb = null;                                      // ark.combat
  let sel = null;                                     // {slot} 선택된 칸
  let carry = null;                                   // 집어 든 사람 {id,name,role,from}
  let dragging = null;                                // 드래그 중인 사람(포인터를 따라다닌다)
  let pointer = { x: 0, y: 0 };
  let hits = [];                                      // 이번 프레임의 사람 히트박스
  let lastStage = null, lastRaidId = null, lastBarH = 0;
  let cam = { x: 0, y: 220, z: 1 }, view = { w: 0, h: 0, dpr: 1 };

  function toast(m) {
    const t = $('#toast'); t.textContent = m; t.classList.add('on');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), 2600);
  }

  async function api(path, body) {
    const r = await fetch(path, body
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ uid }, body)) }
      : undefined);
    let j = {};
    try { j = await r.json(); } catch (e) { j = {}; }
    if (!r.ok) throw new Error(j.detail || r.statusText || '통신 실패');
    return j;
  }

  // ── 소리. 예고의 첫 단계는 언제나 소리다(§3-1) ─────────────
  // 자동 재생이 막히면 조용히 넘어간다(첫 진입은 사용자 제스처가 없을 수 있다).
  const sounds = {};
  function play(file, vol) {
    if (!file) return;
    try {
      let a = sounds[file];
      if (!a) { a = sounds[file] = new Audio('/static/audio/' + file); }
      a.volume = vol == null ? 0.55 : vol;
      a.currentTime = 0;
      const p = a.play();
      if (p && p.catch) p.catch(() => {});
    } catch (e) { /* 소리가 없다고 화면이 멈추지는 않는다 */ }
  }

  // ── 캐릭터 스프라이트 ──────────────────────────────────────
  // 변형마다 시트 규약이 다르다. p2(확정, DECISIONS 2026-10-01)는 **도트**라서 x1 원본을
  // 정수 배율·최근접 보간으로 그린다(2.5D 성립 조건 ①). c/b/a 는 옛 렌더 시트(셀 256·5프레임).
  // 폴백 사슬 p2 → c → b → a → 색 사각형. 폴더만 바뀌어도 코드는 그대로다.
  const SHEETS = {
    p2: { path: (r) => '/static/art/chars/front/p2/src/' + r + '.png',
          mask: (r) => '/static/art/chars/front/p2/masks/' + r + '.png',
          cell: 64, baseline: 60, cols: 3, idle: 0, frames: 2, ppm: 27.5, pixel: true },
    c:  { path: (r) => '/static/art/chars/front/c/' + r + '.png', cell: 256, baseline: 240, cols: 5, idle: 0, frames: 5, ppm: 110, pixel: false },
    b:  { path: (r) => '/static/art/chars/front/b/' + r + '.png', cell: 256, baseline: 240, cols: 5, idle: 0, frames: 5, ppm: 110, pixel: false },
    a:  { path: (r) => '/static/art/chars/front/a/' + r + '.png', cell: 256, baseline: 240, cols: 5, idle: 0, frames: 5, ppm: 110, pixel: false },
  };
  const TARGET_PPM = 37.4;        // 화면에서 1 m = 몇 px (cam.z = 1 기준). 옛 규약과 같은 크기

  const sprites = {};
  function sprite(role) {
    if (CHAR_VARIANT === 'none') return null;
    let s = sprites[role];
    if (s === undefined) {
      const chain = [CHAR_VARIANT].concat(CHAR_FALLBACK.filter(v => v !== CHAR_VARIANT))
                                  .filter(v => SHEETS[v]);
      s = sprites[role] = { img: new Image(), ok: false, i: 0, chain, spec: SHEETS[chain[0]], tint: {} };
      s.img.onload = () => { s.ok = s.img.naturalWidth > 0; };
      s.img.onerror = () => {
        s.ok = false; s.i += 1;
        if (s.i < s.chain.length) { s.spec = SHEETS[s.chain[s.i]]; s.img.src = s.spec.path(role); }
      };
      s.img.src = s.spec.path(role);
      if (s.spec.mask) { s.maskImg = new Image(); s.maskImg.onerror = () => { s.maskImg = null; }; s.maskImg.src = s.spec.mask(role); }
    }
    return s.ok ? s : null;
  }

  // 2.5D 성립 조건 ② — 캐릭터가 **그 방의 등불색을 받는다**. 빠뜨리면 붙여 놓은 스티커로 보인다.
  // masks/<role>.png 의 흰 곳만 색을 먹는다(눈·외곽선·불꽃은 건드리지 않는다).
  function tintedSheet(s, role, tint) {
    if (!s.maskImg || !s.maskImg.naturalWidth || !tint) return s.img;
    const key = tint;
    if (s.tint[key]) return s.tint[key];
    const w = s.img.naturalWidth, h = s.img.naturalHeight;
    const c1 = document.createElement('canvas'); c1.width = w; c1.height = h;
    const g1 = c1.getContext('2d'); g1.imageSmoothingEnabled = false;
    g1.drawImage(s.img, 0, 0);
    const c2 = document.createElement('canvas'); c2.width = w; c2.height = h;
    const g2 = c2.getContext('2d'); g2.imageSmoothingEnabled = false;
    g2.fillStyle = tint; g2.fillRect(0, 0, w, h);
    g2.globalCompositeOperation = 'destination-in';
    g2.drawImage(s.maskImg, 0, 0, w, h);
    g1.globalCompositeOperation = 'multiply'; g1.drawImage(c2, 0, 0);
    g1.globalCompositeOperation = 'destination-in'; g1.drawImage(s.img, 0, 0);
    s.tint[key] = c1;
    return c1;
  }
  // 등불색을 30%만 당긴 값(규약 rules_2_5d.2). 꺼진 방은 차가운 쪽으로 가라앉는다.
  const TINT_LIT = '#fae6c8';      // 흰색과 등불(#f0b055)을 7:3
  const TINT_DARK = '#8fa3ad';     // 불 꺼진 방 — 물빛이 남는다

  // ── 칸 기하 ───────────────────────────────────────────────
  const floorOf = (slot) => Math.floor(slot / floorSlots);
  const sideOf = (slot) => slot % floorSlots;                       // 0 왼쪽, 1 오른쪽
  function rectOf(slot) {
    const f = floorOf(slot), side = sideOf(slot);
    const x = side === 0 ? -(SPINE_W / 2 + ROOM_W) : (SPINE_W / 2);
    // 세계의 y=0 은 **돔이 앉은 층**이다. 그 위(slot 0·1)는 돔 상부, 아래로 갈수록 깊다
    return { x, y: (f - DOME_FLOOR) * FLOOR_PITCH, w: ROOM_W, h: ROOM_H, floor: f, side };
  }
  const floorCount = () => Math.max(1, Math.ceil(slots / floorSlots));
  function worldBounds() {
    const b = (floorCount() - DOME_FLOOR) * FLOOR_PITCH;
    return { x0: -(SPINE_W / 2 + ROOM_W) - 30, x1: (SPINE_W / 2 + ROOM_W) + 30,
             y0: -DOME_FLOOR * FLOOR_PITCH - 120, y1: b + 40 };
  }
  // 홀 = 돔 상부의 공용 공간. 배치되지 않은 사람이 여기 모인다
  function hallRect() {
    const l = rectOf(0), r = rectOf(1);
    return { x: l.x, y: l.y - 86, w: (r.x + r.w) - l.x, h: 76 };
  }
  // 에어락 바깥. 밖에 나가 있는 사람이 서는 자리(손톱 무리의 날에만 보인다)
  function outsideRect() {
    const l = rectOf(0);
    return { x: l.x - 150, y: 6, w: 128, h: 70 };
  }

  // ── 카메라 ────────────────────────────────────────────────
  const sx = (wx) => (wx - cam.x) * cam.z + view.w / 2;
  const sy = (wy) => (wy - cam.y) * cam.z + view.h / 2;
  const wxOf = (px) => (px - view.w / 2) / cam.z + cam.x;
  const wyOf = (py) => (py - view.h / 2) / cam.z + cam.y;

  // UI 가 가린 만큼을 빼고 맞춘다. 폰에서 습격 막대가 홀을 덮어 사람을 못 집는 일을 막는다
  function uiInset() {
    const bar = $('#raidbar');
    const top = (bar && !bar.hidden && view.w <= 560) ? bar.offsetHeight + 10 : 0;
    return { top, bottom: view.w <= 560 ? 104 : 72 };
  }
  function fit() {
    const b = worldBounds(), ins = uiInset();
    const h = Math.max(120, view.h - ins.top - ins.bottom);
    const z = Math.min(view.w / (b.x1 - b.x0), h / (b.y1 - b.y0)) * 0.94;
    cam.z = Math.max(0.18, Math.min(2.2, z));
    cam.x = (b.x0 + b.x1) / 2;
    // 보이는 띠의 한가운데에 거점을 둔다
    cam.y = (b.y0 + b.y1) / 2 + ((ins.bottom - ins.top) / 2) / cam.z;
  }
  function zoomAt(px, py, k) {
    const wx = wxOf(px), wy = wyOf(py);
    cam.z = Math.max(0.18, Math.min(2.4, cam.z * k));
    cam.x = wx - (px - view.w / 2) / cam.z;
    cam.y = wy - (py - view.h / 2) / cam.z;
  }

  function resize() {
    view.dpr = Math.min(2, window.devicePixelRatio || 1);
    view.w = cv.clientWidth; view.h = cv.clientHeight;
    cv.width = Math.round(view.w * view.dpr); cv.height = Math.round(view.h * view.dpr);
    ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
  }

  // ── 그리기 ────────────────────────────────────────────────
  function drawWater(t) {
    const g = ctx.createLinearGradient(0, sy(WATER[0][0]), 0, sy(WATER[WATER.length - 1][0]));
    const span = WATER[WATER.length - 1][0] - WATER[0][0];
    WATER.forEach(([y, c]) => g.addColorStop((y - WATER[0][0]) / span, c));
    ctx.fillStyle = g; ctx.fillRect(0, 0, view.w, view.h);
    const topY = sy(WATER[0][0]);
    if (topY > 0) { ctx.fillStyle = WATER[0][1]; ctx.fillRect(0, 0, view.w, topY); }
    const botY = sy(WATER[WATER.length - 1][0]);
    if (botY < view.h) { ctx.fillStyle = WATER[WATER.length - 1][1]; ctx.fillRect(0, botY, view.w, view.h - botY); }

    // 광층에서 내려오는 빛 — 갈 수 없는 밝음(REF_CROSS_SECTION §3)
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 3; i++) {
      const bx = sx(-300 + i * 300 + Math.sin(t / 9000 + i) * 40);
      const y0 = sy(-1600), y1 = sy(-60);
      const lg = ctx.createLinearGradient(0, y0, 0, y1);
      lg.addColorStop(0, 'rgba(120,200,205,0.10)'); lg.addColorStop(1, 'rgba(120,200,205,0)');
      ctx.fillStyle = lg;
      ctx.beginPath();
      ctx.moveTo(bx - 26 * cam.z, y0); ctx.lineTo(bx + 26 * cam.z, y0);
      ctx.lineTo(bx + 120 * cam.z, y1); ctx.lineTo(bx - 120 * cam.z, y1);
      ctx.closePath(); ctx.fill();
    }
    ctx.restore();
  }

  // 부유물(D5). 물은 가만히 있지 않는다
  const MOTES = Array.from({ length: 110 }, (_, i) => ({
    x: -700 + Math.random() * 1400, y: -600 + Math.random() * 1600,
    r: 0.6 + Math.random() * 1.8, v: 4 + Math.random() * 12, ph: Math.random() * 6.3,
  }));
  function drawMotes(t) {
    ctx.fillStyle = 'rgba(200,225,225,0.30)';
    for (const m of MOTES) {
      const y = ((m.y + (t / 1000) * m.v) % 2200 + 2200) % 2200 - 600;
      const x = m.x + Math.sin(t / 2600 + m.ph) * 14;
      const px = sx(x), py = sy(y);
      if (px < -20 || px > view.w + 20 || py < -20 || py > view.h + 20) continue;
      ctx.beginPath(); ctx.arc(px, py, Math.max(0.5, m.r * cam.z), 0, 6.2832); ctx.fill();
    }
  }

  function drawSpots(t) {
    for (const sp of spots) {
      if (!sp.unlocked || !sp.has_pos) continue;
      const px = sx(sp.pos.x * M2PX), py = sy(sp.pos.y * M2PX);
      if (px < -60 || px > view.w + 60 || py < -40 || py > view.h + 40) continue;
      const r = (4 + Math.sin(t / 900 + sp.pos.x) * 1.2) * Math.max(0.6, cam.z);
      const g = ctx.createRadialGradient(px, py, 0, px, py, r * 5);
      g.addColorStop(0, 'rgba(240,176,85,0.55)'); g.addColorStop(1, 'rgba(240,176,85,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, r * 5, 0, 6.2832); ctx.fill();
      ctx.fillStyle = '#f0b055'; ctx.beginPath();
      ctx.moveTo(px, py - r); ctx.lineTo(px + r, py); ctx.lineTo(px, py + r); ctx.lineTo(px - r, py);
      ctx.closePath(); ctx.fill();
      if (cam.z > 0.5) {
        ctx.font = '11px "Noto Sans KR",sans-serif'; ctx.fillStyle = 'rgba(230,215,176,0.72)';
        ctx.fillText(sp.name || '', px + r + 6, py + 4);
      }
    }
  }

  function drawZones() {
    const x = view.w - 14;
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (const z of ZONES) {
      const y0 = sy(z.y0), y1 = sy(z.y1);
      if (y1 < 0 || y0 > view.h) continue;
      ctx.strokeStyle = 'rgba(150,200,200,0.16)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x - 40, y0); ctx.lineTo(x, y0); ctx.stroke();
      const my = Math.max(18, Math.min(view.h - 72, (Math.max(y0, 0) + Math.min(y1, view.h)) / 2));
      ctx.fillStyle = 'rgba(190,225,222,0.42)'; ctx.font = '11px "Noto Sans KR",sans-serif';
      ctx.fillText(z.ko, x, my);
    }
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  }

  function drawSpine() {
    const top = rectOf(0).y + 30, bot = (floorCount() - DOME_FLOOR) * FLOOR_PITCH - FLOOR_GAP;
    const x0 = sx(-SPINE_W / 2), x1 = sx(SPINE_W / 2), y0 = sy(top), y1 = sy(bot);
    ctx.fillStyle = '#0d1512'; ctx.fillRect(x0 - 3, y0, (x1 - x0) + 6, y1 - y0);
    const g = ctx.createLinearGradient(x0, 0, x1, 0);
    g.addColorStop(0, '#1b1a12'); g.addColorStop(0.5, '#3a3018'); g.addColorStop(1, '#1b1a12');
    ctx.fillStyle = g; ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.strokeStyle = '#14110c'; ctx.lineWidth = Math.max(1, 3 * cam.z);
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    ctx.strokeStyle = 'rgba(240,176,85,0.22)'; ctx.lineWidth = Math.max(1, 2 * cam.z);
    for (let y = top + 14; y < bot; y += 34) {
      const yy = sy(y); if (yy < -10 || yy > view.h + 10) continue;
      ctx.beginPath(); ctx.moveTo(x0 + 6, yy); ctx.lineTo(x1 - 6, yy); ctx.stroke();
    }
  }

  function drawDome(t) {
    const r = rectOf(0), rr = rectOf(1);
    const left = sx(r.x - PAD), right = sx(rr.x + rr.w + PAD), cxs = (left + right) / 2;
    const base = sy(r.y - 2), h = 104 * cam.z;
    ctx.beginPath(); ctx.ellipse(cxs, base, (right - left) / 2, h, 0, Math.PI, 0);
    ctx.fillStyle = 'rgba(214,201,163,0.10)'; ctx.fill();
    ctx.strokeStyle = 'rgba(230,215,176,0.55)'; ctx.lineWidth = Math.max(1, 3 * cam.z); ctx.stroke();
    ctx.strokeStyle = 'rgba(230,215,176,0.18)'; ctx.lineWidth = Math.max(1, 1.5 * cam.z);
    for (let i = 1; i < 5; i++) {
      const a = Math.PI + (Math.PI * i) / 5;
      ctx.beginPath(); ctx.moveTo(cxs, base);
      ctx.lineTo(cxs + Math.cos(a) * (right - left) / 2, base + Math.sin(a) * h); ctx.stroke();
    }
  }

  function roomColor(id) { return ROOM_COLOR[id] || ROOM_COLOR._default; }
  const lightOf = (slot) => !cb || !cb.lights || cb.lights[String(slot)] !== false;
  const capOf = (slot) => (cb && cb.caps && cb.caps[String(slot)]) || 0;

  function drawRoom(slot, room, people, t) {
    const r = rectOf(slot);
    const x = sx(r.x), y = sy(r.y), w = r.w * cam.z, h = r.h * cam.z;
    if (x > view.w + 40 || x + w < -40 || y > view.h + 40 || y + h < -40) return;
    const picked = carry || dragging;                 // 사람을 들고 있을 때는 놓을 자리를 밝힌다
    const target = raidTargetSlot();

    if (!room) {   // 빈 자리 — 여기로 자란다(성장 방향은 아래)
      if (r.floor < DOME_FLOOR) { return; }
      ctx.save();
      ctx.setLineDash([6 * cam.z, 6 * cam.z]);
      ctx.strokeStyle = sel && sel.slot === slot ? 'rgba(240,176,85,0.85)' : 'rgba(150,200,200,0.22)';
      ctx.lineWidth = Math.max(1, 2 * cam.z);
      ctx.strokeRect(x + PAD * cam.z, y + PAD * cam.z, w - 2 * PAD * cam.z, h - 2 * PAD * cam.z);
      ctx.restore();
      if (cam.z > 0.42) {
        ctx.fillStyle = 'rgba(190,225,222,0.34)';
        ctx.font = (16 * cam.z) + 'px "Noto Sans KR",sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('+', x + w / 2, y + h / 2);
        ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
      }
      return;
    }

    const col = roomColor(room.id), ix = x + PAD * cam.z, iy = y + PAD * cam.z;
    const iw = w - 2 * PAD * cam.z, ih = h - 2 * PAD * cam.z;

    if (room.flooded) {
      // 잃은 방은 사라지지 않고 **물이 찬 채로 영구히 남는다**(§3-6 흔적). 소리도 없다
      ctx.fillStyle = '#082028'; ctx.fillRect(ix, iy, iw, ih);
      ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
      ctx.strokeStyle = 'rgba(120,180,185,0.10)'; ctx.lineWidth = 1;
      for (let gy = iy + 6 * cam.z; gy < iy + ih; gy += 9 * cam.z) {     // 가라앉은 물의 결
        ctx.beginPath(); ctx.moveTo(ix, gy + Math.sin(t / 1800 + gy) * 1.4); ctx.lineTo(ix + iw, gy); ctx.stroke();
      }
      ctx.fillStyle = 'rgba(60,110,115,0.22)';                           // 안에 남은 그림자(가구의 흔적)
      ctx.fillRect(ix + iw * 0.2, iy + ih * 0.55, iw * 0.22, ih * 0.3);
      ctx.fillRect(ix + iw * 0.6, iy + ih * 0.66, iw * 0.16, ih * 0.2);
      ctx.restore();
      ctx.strokeStyle = '#14110c'; ctx.lineWidth = Math.max(1.5, 3 * cam.z);
      ctx.strokeRect(ix, iy, iw, ih);
      if (cam.z > 0.4) {
        ctx.font = (10.5 * Math.min(1.3, cam.z)) + 'px "Noto Sans KR",sans-serif';
        ctx.fillStyle = 'rgba(140,190,195,0.55)'; ctx.textBaseline = 'middle';
        ctx.fillText('물이 찼다', ix + 6 * cam.z, iy + 10 * Math.min(1.3, cam.z));
        ctx.textBaseline = 'alphabetic';
      }
      return;
    }

    const lit = lightOf(slot);
    // 평면 채색 + 음영 1~2단 (FLAT_FOLK §1-3). 불을 끄면 같은 색이 어둡게 가라앉는다
    ctx.save();
    if (!lit) ctx.globalAlpha = 0.34;
    ctx.fillStyle = col.base; ctx.fillRect(ix, iy, iw, ih);
    ctx.fillStyle = col.shade; ctx.fillRect(ix, iy, iw, ih * 0.26);
    ctx.fillStyle = col.floor; ctx.fillRect(ix, iy + ih * 0.80, iw, ih * 0.20);
    ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
    ctx.strokeStyle = 'rgba(20,17,12,0.13)'; ctx.lineWidth = Math.max(1, 1 * cam.z);
    for (let gx = ix + 16 * cam.z; gx < ix + iw; gx += 22 * cam.z) {
      ctx.beginPath(); ctx.moveTo(gx, iy + ih * 0.26); ctx.lineTo(gx, iy + ih * 0.80); ctx.stroke();
    }
    ctx.restore();
    if (!lit) { ctx.fillStyle = 'rgba(4,16,22,0.55)'; ctx.fillRect(ix, iy, iw, ih); }

    if (lit) {   // 랜턴 하나 = 주색 하나
      ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
      const lx = ix + iw * 0.5, ly = iy + ih * 0.20;
      const lg = ctx.createRadialGradient(lx, ly, 0, lx, ly, ih * 0.9);
      lg.addColorStop(0, 'rgba(240,176,85,0.40)'); lg.addColorStop(1, 'rgba(240,176,85,0)');
      ctx.fillStyle = lg; ctx.fillRect(ix, iy, iw, ih);
      ctx.fillStyle = '#f0b055'; ctx.beginPath();
      ctx.arc(lx, ly, Math.max(1.2, 3 * cam.z), 0, 6.2832); ctx.fill();
      ctx.restore();
    }

    if (room.cracked) drawCrack(ix, iy, iw, ih, slot);

    // 두꺼운 검은 테두리: 방을 각각 "불 켜진 상자"로 읽히게 한다(§1-3)
    let edge = '#14110c', ew = 3;
    if (sel && sel.slot === slot) { edge = '#f0b055'; ew = 4; }
    if (target === slot) { edge = '#b03a24'; ew = 4; }                    // 노려지는 방
    if (picked) {                                                         // 놓을 수 있는 자리
      const full = (people || []).length >= capOf(slot);
      edge = full ? '#6b3b33' : '#8fbf7a'; ew = 4;
    }
    ctx.strokeStyle = edge;
    ctx.lineWidth = Math.max(1.5, ew * cam.z);
    ctx.strokeRect(ix, iy, iw, ih);

    drawInstalled(slot, ix, iy, iw, ih);
    drawPeople(people, ix, iy, iw, ih, t, slot);

    if (cam.z > 0.4) {
      const nm = (catalog[room.id] && catalog[room.id].name) || room.id;
      const cap = capOf(slot), n = (people || []).length;
      const label = nm + (cap ? '  ' + n + '/' + cap : '');
      ctx.font = (11 * Math.min(1.3, cam.z)) + 'px "Noto Sans KR",sans-serif';
      ctx.fillStyle = 'rgba(20,17,12,0.75)';
      const tw = ctx.measureText(label).width + 10 * cam.z;
      ctx.fillRect(ix, iy, tw, 16 * Math.min(1.3, cam.z));
      ctx.fillStyle = lit ? '#e6d7b0' : '#93a6a3';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, ix + 5 * cam.z, iy + 8 * Math.min(1.3, cam.z));
      ctx.textBaseline = 'alphabetic';
      if (!lit) {
        ctx.fillStyle = 'rgba(147,166,163,0.7)';
        ctx.fillText('불 꺼짐', ix + 5 * cam.z, iy + ih - 6 * cam.z);
      }
    }
  }

  function drawCrack(ix, iy, iw, ih, slot) {
    // 막아도 긁힌 자국이 남는다(§3-6). 금은 지워지지 않고 봉합 패치로만 덮인다
    ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
    ctx.strokeStyle = 'rgba(10,30,36,0.85)'; ctx.lineWidth = Math.max(1, 1.6 * cam.z);
    const bx = ix + iw * (0.3 + (slot % 3) * 0.17), by = iy + ih * 0.18;
    ctx.beginPath(); ctx.moveTo(bx, by);
    ctx.lineTo(bx + 12 * cam.z, by + 20 * cam.z);
    ctx.lineTo(bx - 6 * cam.z, by + 36 * cam.z);
    ctx.lineTo(bx + 14 * cam.z, by + 54 * cam.z); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(bx + 12 * cam.z, by + 20 * cam.z);
    ctx.lineTo(bx + 30 * cam.z, by + 16 * cam.z); ctx.stroke();
    ctx.restore();
  }

  function drawInstalled(slot, ix, iy, iw, ih) {
    const rows = (cb && cb.workshop && cb.workshop.installed && cb.workshop.installed[String(slot)]) || [];
    if (!rows.length || cam.z < 0.34) return;
    const mark = { shutter: '▤', lure_lamp: '✦', hush: '◍', long_net: '╳', brace: '═' };
    ctx.font = (11 * Math.min(1.4, cam.z)) + 'px "Noto Sans KR",sans-serif';
    ctx.fillStyle = 'rgba(240,176,85,0.9)';
    rows.forEach((row, i) => {
      ctx.fillText(mark[row.id] || '•', ix + iw - (12 + i * 12) * cam.z, iy + ih - 7 * cam.z);
    });
  }

  function drawPerson(p, px, floorY, t, i, scale, lit) {
    const k = (scale == null ? 1 : scale);
    const bob = Math.sin(t / 700 + i * 1.7) * 0.8 * cam.z;
    const s = sprite(p.role);
    if (s) {
      const sp = s.spec;
      // 도트는 **정수 배율**로만 키운다(2.5D 조건 ①). 렌더 시트는 기존대로 연속 배율
      const want = (TARGET_PPM * cam.z * k) / sp.ppm;
      const z = sp.pixel ? Math.max(1, Math.round(want)) : want;
      const cw = sp.cell * z, base = sp.baseline * z;
      const frame = Math.floor(t / (sp.pixel ? 620 : 170) + i) % sp.frames;
      try {
        const sheet = sp.pixel ? tintedSheet(s, p.role, lit === false ? TINT_DARK : TINT_LIT) : s.img;
        const sm = ctx.imageSmoothingEnabled;
        if (sp.pixel) ctx.imageSmoothingEnabled = false;
        // 2.5D 조건 ③ — 발밑 접지 그림자. 없으면 떠 있는 것처럼 보인다
        ctx.fillStyle = 'rgba(12,10,8,0.42)';
        ctx.beginPath(); ctx.ellipse(px, floorY, cw * 0.22, cw * 0.055, 0, 0, 6.2832); ctx.fill();
        ctx.drawImage(sheet, (sp.idle * sp.cols + frame) % sp.cols * sp.cell,
                      Math.floor((sp.idle * sp.cols + frame) / sp.cols) * sp.cell, sp.cell, sp.cell,
                      px - cw / 2, floorY - base + bob, cw, cw);
        ctx.imageSmoothingEnabled = sm;
        if (p.injured) { ctx.fillStyle = 'rgba(140,59,46,0.5)'; ctx.fillRect(px - 6 * cam.z, floorY - 46 * cam.z, 12 * cam.z, 4 * cam.z); }
        return { w: cw * 0.42, h: base * 0.78 };
      } catch (e) { /* 스프라이트가 아직 덜 왔다 — 아래 색 사각형으로 */ }
    }
    const hgt = (p.role === 'kid' ? 30 : 40) * cam.z * k, wid = 13 * cam.z * k;
    ctx.fillStyle = ROLE_COLOR[p.role] || '#d8c9a3';
    ctx.fillRect(px - wid / 2, floorY - hgt + bob, wid, hgt);
    ctx.fillStyle = '#14110c';
    ctx.fillRect(px - wid / 2, floorY - hgt + bob, wid, Math.max(1, 3 * cam.z));
    if (p.injured) { ctx.fillStyle = '#8c3b2e'; ctx.fillRect(px - wid / 2, floorY - hgt * 0.55 + bob, wid, Math.max(1, 3 * cam.z)); }
    return { w: wid, h: hgt };
  }

  function drawPeople(people, ix, iy, iw, ih, t, slot) {
    if (!people || !people.length) return;
    const floorY = iy + ih * 0.86;
    const step = iw / (people.length + 1);
    people.forEach((p, i) => {
      if (dragging && dragging.id === p.id) return;          // 들고 있는 사람은 손끝에 그린다
      const px = ix + step * (i + 1);
      const box = drawPerson(p, px, floorY, t, i, 1, lightOf(slot));
      if (carry && carry.id === p.id) {                      // 집어 든 표시
        ctx.strokeStyle = '#f0b055'; ctx.lineWidth = Math.max(1, 2 * cam.z);
        ctx.strokeRect(px - box.w / 2 - 3, floorY - box.h - 6, box.w + 6, box.h + 10);
      }
      hits.push({ kind: 'person', id: p.id, name: p.name, role: p.role, from: slot,
                  x: px - box.w / 2 - 6, y: floorY - box.h - 8, w: box.w + 12, h: box.h + 14 });
    });
  }

  function drawHall(t) {
    // 홀: 배치되지 않은 사람이 모이는 돔 상부. 여기도 **빈 방이 아니다**
    const h = hallRect();
    const x = sx(h.x), y = sy(h.y), w = h.w * cam.z, hh = h.h * cam.z;
    const list = (ark.residents_list || []).filter(r =>
      (!cb || cb.stations[r.id] === undefined) && !(cb && cb.outside.indexOf(r.id) >= 0));
    const picked = carry || dragging;
    ctx.save();
    ctx.fillStyle = 'rgba(58,48,24,0.30)'; ctx.fillRect(x, y, w, hh);
    ctx.setLineDash([5 * cam.z, 5 * cam.z]);
    ctx.strokeStyle = picked ? 'rgba(143,191,122,0.85)' : 'rgba(230,215,176,0.22)';
    ctx.lineWidth = Math.max(1, 2 * cam.z);
    ctx.strokeRect(x, y, w, hh);
    ctx.restore();
    if (cam.z > 0.36) {
      ctx.font = (10.5 * Math.min(1.3, cam.z)) + 'px "Noto Sans KR",sans-serif';
      ctx.fillStyle = 'rgba(230,215,176,0.55)';
      ctx.fillText('홀 · 배치 안 된 사람 ' + list.length, x + 6 * cam.z, y + 13 * cam.z);
    }
    const floorY = y + hh - 6 * cam.z, step = w / (list.length + 1);
    list.forEach((p, i) => {
      if (dragging && dragging.id === p.id) return;
      const px = x + step * (i + 1);
      const box = drawPerson(p, px, floorY, t, i, 0.82, !!(cb && cb.power_on));
      if (carry && carry.id === p.id) {
        ctx.strokeStyle = '#f0b055'; ctx.lineWidth = Math.max(1, 2 * cam.z);
        ctx.strokeRect(px - box.w / 2 - 3, floorY - box.h - 6, box.w + 6, box.h + 10);
      }
      hits.push({ kind: 'person', id: p.id, name: p.name, role: p.role, from: null,
                  x: px - box.w / 2 - 6, y: floorY - box.h - 8, w: box.w + 12, h: box.h + 14 });
    });
    hits.push({ kind: 'hall', x, y, w, h: hh });
  }

  function drawOutside(t) {
    // 밖에 나가 있는 사람. 손톱 무리의 날에만 보이고, 들이면 사라진다
    const ids = (cb && cb.outside) || [];
    if (!ids.length) return;
    const o = outsideRect();
    const x = sx(o.x), y = sy(o.y), w = o.w * cam.z, hh = o.h * cam.z;
    ctx.save();
    ctx.setLineDash([4 * cam.z, 4 * cam.z]);
    ctx.strokeStyle = 'rgba(176,58,36,0.75)'; ctx.lineWidth = Math.max(1, 2 * cam.z);
    ctx.strokeRect(x, y, w, hh); ctx.restore();
    ctx.font = (10.5 * Math.min(1.3, cam.z)) + 'px "Noto Sans KR",sans-serif';
    ctx.fillStyle = 'rgba(224,150,130,0.9)';
    ctx.fillText('밖 · ' + ids.length + '명', x + 4 * cam.z, y + 12 * cam.z);
    const list = (ark.residents_list || []).filter(r => ids.indexOf(r.id) >= 0);
    const floorY = y + hh - 5 * cam.z, step = w / (list.length + 1);
    list.forEach((p, i) => drawPerson(p, x + step * (i + 1), floorY, t, i, 0.78, false));
  }

  // ── 실루엣: 바깥 물에 그림자가 **그 방 쪽으로** 다가온다 (§3-2) ──
  let approach = 0;                                   // 0 → 1. 다 와도 접촉하지 않고 창 앞에서 멈춘다
  function drawSilhouette(t, dt) {
    const raid = cb && cb.raid;
    if (!raid || raid.stage !== 'silhouette' || raid.target_slot == null) { approach = 0; return; }
    approach = Math.min(1, approach + dt / 22000);    // 약 22초에 걸쳐 천천히. 놀래키지 않는다(§6-2)
                                                      // 다 와도 창 앞에서 **멈춰 선다** — 접촉은 플레이어가 누를 때만
    const r = rectOf(raid.target_slot);
    const fromLeft = sideOf(raid.target_slot) === 0;
    const tx = fromLeft ? r.x - 26 : r.x + r.w + 26;
    const ox = fromLeft ? tx - 430 : tx + 430;
    const wx = ox + (tx - ox) * (1 - Math.pow(1 - approach, 2));
    const wy = r.y + r.h * 0.45 + Math.sin(t / 1400) * 9;
    const px = sx(wx), py = sy(wy), k = cam.z;
    const alpha = 0.30 + 0.45 * approach;
    ctx.save();
    // 검은 물에 검은 그림자는 안 보인다 — 몸은 더 어둡게, 가장자리는 물빛으로 한 겹.
    // (REF_CROSS_SECTION §3: 바깥의 것은 윤곽으로 먼저 온다)
    ctx.fillStyle = 'rgba(1,7,11,' + Math.min(0.92, alpha + 0.25).toFixed(3) + ')';
    ctx.strokeStyle = 'rgba(1,7,11,' + Math.min(0.92, alpha + 0.25).toFixed(3) + ')';
    ctx.shadowColor = 'rgba(132,198,204,' + (0.18 + 0.30 * approach).toFixed(3) + ')';
    ctx.shadowBlur = 10 * cam.z;
    const c = raid.creature.id;
    if (c === 'longneck') {
      ctx.lineWidth = 15 * k; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(px + (fromLeft ? -210 : 210) * k, py + 80 * k);
      ctx.quadraticCurveTo(px + (fromLeft ? -90 : 90) * k, py - 60 * k, px, py);
      ctx.stroke();
      ctx.beginPath(); ctx.ellipse(px, py, 26 * k, 15 * k, 0, 0, 6.2832); ctx.fill();
    } else if (c === 'swarm') {
      for (let i = 0; i < 46; i++) {
        const a = i * 2.39 + t / 1200;
        const rr = (16 + (i % 7) * 13) * k;
        ctx.beginPath();
        ctx.ellipse(px + Math.cos(a) * rr * (fromLeft ? -1.6 : 1.6) - (fromLeft ? -1 : 1) * 40 * k,
                    py + Math.sin(a) * rr * 0.8, 5 * k, 2.6 * k, a, 0, 6.2832);
        ctx.fill();
      }
    } else if (c === 'warden') {
      ctx.beginPath(); ctx.ellipse(px + (fromLeft ? -170 : 170) * k, py, 190 * k, 112 * k, 0, 0, 6.2832);
      ctx.fill();
      ctx.lineWidth = 3 * k;                          // 압력이 먼저 온다
      ctx.beginPath(); ctx.ellipse(px, py, (30 + 70 * approach) * k, (22 + 50 * approach) * k, 0, 0, 6.2832);
      ctx.stroke();
    } else if (c === 'claws') {
      for (let i = 0; i < 70; i++) {
        const a = i * 1.7;
        ctx.beginPath();
        ctx.arc(px + (fromLeft ? -1 : 1) * (i % 14) * 16 * k, py + 54 * k + Math.sin(a + t / 900) * 8 * k,
                3.4 * k, 0, 6.2832);
        ctx.fill();
      }
    } else {
      ctx.beginPath(); ctx.ellipse(px, py, 26 * k, 20 * k, 0, 0, 6.2832); ctx.fill();
      for (let i = 0; i < 6; i++) {                   // 문어 — 여덟 중 여섯만 보인다
        const a = Math.PI * 0.2 + i * 0.4;
        ctx.lineWidth = 4 * k; ctx.beginPath(); ctx.moveTo(px, py + 10 * k);
        ctx.quadraticCurveTo(px + Math.cos(a + t / 800) * 26 * k, py + 30 * k,
                             px + Math.cos(a) * 44 * k, py + 40 * k + Math.sin(t / 700 + i) * 5 * k);
        ctx.stroke();
      }
    }
    ctx.restore();
    // 노려지는 창에 붉은 테두리가 번진다
    const gx = sx(r.x - PAD), gy = sy(r.y - PAD);
    ctx.save();
    ctx.strokeStyle = 'rgba(176,58,36,' + (0.25 + 0.5 * approach).toFixed(3) + ')';
    ctx.lineWidth = Math.max(2, 5 * cam.z);
    ctx.strokeRect(gx, gy, (r.w + 2 * PAD) * cam.z, (r.h + 2 * PAD) * cam.z);
    ctx.restore();
  }

  const raidTargetSlot = () => (cb && cb.raid && cb.raid.target_slot != null) ? cb.raid.target_slot : null;

  let raf = 0, prev = 0;
  function frame(t) {
    raf = requestAnimationFrame(frame);
    const dt = prev ? Math.min(60, t - prev) : 16; prev = t;
    if (!view.w) return;
    hits = [];
    ctx.clearRect(0, 0, view.w, view.h);
    drawWater(t);
    drawMotes(t);
    if (!ark) return;
    drawSilhouette(t, dt);
    drawDome(t);
    drawSpine();
    const byslot = {}; (ark.rooms || []).forEach(r => { byslot[r.slot] = r; });
    const people = peopleBySlot();
    drawSpots(t);
    for (let s = 0; s < slots; s++) drawRoom(s, byslot[s], people[s], t);
    drawHall(t);
    drawOutside(t);
    if (dragging) {                                   // 손끝에 매달린 사람
      drawPerson(dragging, pointer.x, pointer.y + 22 * cam.z, t, 0, 1, true);
    }
    drawZones();
  }

  // 배치는 **서버가 정본**이다(새로고침해도 같은 자리, 저장된다)
  function peopleBySlot() {
    const map = {};
    if (!cb) return map;
    const out = cb.outside || [];
    (ark.residents_list || []).forEach(p => {
      const s = cb.stations[p.id];
      if (s === undefined || out.indexOf(p.id) >= 0) return;
      (map[s] = map[s] || []).push(p);
    });
    return map;
  }

  // ── 패널 ──────────────────────────────────────────────────
  function costLine(id) {
    const c = (catalog[id] && catalog[id].cost) || {};
    return Object.entries(c).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
  }
  function lacking(id) {
    const c = (catalog[id] && catalog[id].cost) || {}, have = ark.resources || {};
    return Object.entries(c).filter(([k, v]) => (have[k] || 0) < v).map(([k, v]) => (RES_KO[k] || k) + ' ' + ((have[k] || 0)) + '/' + v);
  }
  // 그 방에서 빛나는 스탯. 노려지는 방에서는 언제나 「담」이다(RESIDENT_STATS §5)
  const ROOM_STAT = { workshop: 'hand', library: 'eye', infirmary: 'breath', well: 'hand', pantry: 'hand' };
  function goodStats(slot) {
    const room = (ark.rooms || []).find(r => r.slot === slot);
    const out = [];
    if (room && ROOM_STAT[room.id]) out.push(ROOM_STAT[room.id]);
    if (raidTargetSlot() === slot) out.push('nerve');
    return out;
  }
  function statRows(p, slot) {
    const meta = (ark.stats_meta || {}), keys = meta.keys || ['hand', 'eye', 'breath', 'nerve'];
    const ko = meta.ko || { hand: '손', eye: '눈', breath: '숨', nerve: '담' };
    const st = p.stats || {};
    if (!keys.some(k => st[k])) return '';
    const good = goodStats(slot);
    const q = p.quirk || {};
    return '<div class="stats">' + keys.map(k => {
      const v = Math.max(0, Math.min(10, st[k] || 0));
      return '<div class="srow' + (good.indexOf(k) >= 0 ? ' good' : '') + '">' +
        '<span class="sk">' + esc(ko[k] || k) + '</span>' +
        '<span class="sd"><b>' + '\u25cf'.repeat(v) + '</b>' + '\u00b7'.repeat(10 - v) + '</span></div>';
    }).join('') +
      (q.ko ? '<em class="quirk' + (q.sign < 0 ? ' minus' : '') + '">' + esc(q.ko) + '</em>' : '') +
      '</div>';
  }
  // 사람을 들고 있을 때의 **갈 곳 목록**. 폰에서는 패널이 아래 절반을 덮으므로 캔버스를 못 누른다 —
  // 목록이 있으면 손가락 하나로 끝난다(02_DEV §5-4 "폰 가로 720px에서 손가락으로 조작 가능한가").
  function destList() {
    if (!carry) return '';
    const byslot = peopleBySlot();
    const rows = (ark.rooms || []).filter(r => !r.flooded).sort((a, b) => a.slot - b.slot).map(r => {
      const n = (byslot[r.slot] || []).length, cap = capOf(r.slot);
      const here = cb.stations[carry.id] === r.slot;
      const full = n >= cap && !here;
      const tgt = raidTargetSlot() === r.slot;
      return '<button class="bopt' + (full ? ' lack' : '') + '" data-dest="' + r.slot + '"' +
        (full || here ? ' disabled' : '') + '><b>' + esc((catalog[r.id] || {}).name || r.id) +
        (tgt ? ' · 노려지는 방' : '') + '</b><small>' + n + '/' + cap + '명' +
        (here ? ' · 지금 여기' : (full ? ' · 꽉 찼다' : '')) + '</small></button>';
    });
    rows.push('<button class="bopt" data-dest="hall"' +
      (cb.stations[carry.id] === undefined ? ' disabled' : '') +
      '><b>홀</b><small>돔 상부 · 아무 방도 지키지 않는다</small></button>');
    return '<h3>' + esc(carry.name) + ' 을(를) 어디로</h3><div class="blist">' + rows.join('') + '</div>';
  }
  function bindDest(body) {
    body.querySelectorAll('.bopt[data-dest]').forEach(b => b.addEventListener('click', () =>
      place(carry.id, b.dataset.dest === 'hall' ? null : parseInt(b.dataset.dest, 10))));
  }

  function personRow(p, slot) {
    return '<div class="who' + (carry && carry.id === p.id ? ' pick' : '') + '" data-pid="' + esc(p.id) + '">' +
      '<i style="background:' + (ROLE_COLOR[p.role] || '#d8c9a3') + '"></i>' +
      '<b>' + esc(p.name) + '</b><em>' + esc(p.role_ko || p.role) +
      (p.imprints && p.imprints.length ? ' · 刻 ' + p.imprints.length : '') + '</em>' +
      (p.injured ? '<em class="hurt">부상</em>' : '') +
      '<span class="mv">' + (carry && carry.id === p.id ? '놓기 취소' : '옮기기') + '</span></div>' +
      statRows(p, slot);
  }

  // 패널이 습격 막대 아래에서 열리게 한다(데스크톱). 둘이 겹치면 둘 다 안 읽힌다
  function placePanel() {
    const bar = $('#raidbar'), pan = $('#panel');
    const below = view.w > 560 && !bar.hidden;
    pan.style.top = below ? (bar.offsetHeight + 24) + 'px' : '';
    pan.style.maxHeight = below ? (view.h - bar.offsetHeight - 48) + 'px' : '';
  }

  function openPanel(slot) {
    sel = { slot };
    const room = (ark.rooms || []).find(r => r.slot === slot);
    const f = floorOf(slot), depth = (f - DOME_FLOOR) * DEPTH_PER_FLOOR;
    const fl = (f - DOME_FLOOR + 1);
    const body = $('#panelBody');
    if (room && room.flooded) {
      body.innerHTML = '<h2>' + esc((catalog[room.id] || {}).name || room.id) + '</h2>' +
        '<p class="sub">' + fl + '층 · 깊이 ' + depth + 'm · 격벽이 닫혔다</p>' +
        '<p class="lost">여기는 물이다. 격벽은 다시 열리지 않는다.<br>생산하지 않고, 소리도 나지 않는다. ' +
        '그래도 지워지지 않고 남아 있다.</p>' +
        (room.flooded_day ? '<h3>잃은 날</h3><div class="kv"><span>' + esc(room.flooded_day) + '일째</span>' +
          (room.flooded_by ? '<span>' + esc(creatureName(room.flooded_by)) + '</span>' : '') + '</div>' : '');
      $('#panel').hidden = false; placePanel(); return;
    }
    if (room) {
      const spec = catalog[room.id] || {};
      const people = peopleBySlot()[slot] || [];
      const cap = capOf(slot);
      const lit = lightOf(slot);
      const inst = (cb && cb.workshop.installed[String(slot)]) || [];
      body.innerHTML =
        '<h2>' + esc(spec.name || room.id) + '<span class="cap">' + people.length + '/' + cap + '명</span></h2>' +
        '<p class="sub">' + fl + '층 · 깊이 ' + depth + 'm · ' + esc(zoneAt(f)) + (room.cracked ? ' · 유리에 금' : '') + '</p>' +
        (spec.desc ? '<p class="desc">' + esc(spec.desc) + '</p>' : '') +
        '<div class="rowbtns">' +
        '<button id="lgt" class="' + (lit ? 'on' : '') + '">' + (lit ? '불 켜짐 — 끄기' : '불 꺼짐 — 켜기') + '</button>' +
        '</div>' + destList() +
        '<h3>하루 생산</h3><div class="kv">' +
        (Object.entries(spec.produces || {}).map(([k, v]) =>
          '<span>' + esc(RES_KO[k] || k) + ' +' + esc(v) + '</span>').join('') || '<span>—</span>') +
        '</div>' +
        '<h3>붙어 있는 것</h3><div class="kv">' +
        (inst.length ? inst.map(x => '<span>' + esc(toolName(x.id)) +
            (x.uses != null ? ' ' + x.uses + '회' : '') + '</span>').join('') : '<span>—</span>') +
        '</div>' +
        '<h3>여기 있는 사람</h3>' +
        (people.length ? people.map(p => personRow(p, slot)).join('')
          : '<div class="who"><em>아무도 없다 — 빈 방은 막지 못한다</em></div>');
      const lb = body.querySelector('#lgt');
      if (lb) lb.addEventListener('click', () => setLight(slot, !lit));
      bindDest(body);
      bindPeople(body);
    } else {
      if (f < DOME_FLOOR) {
        body.innerHTML = '<h2>돔 상부 · 홀</h2><p class="sub">깊이 0m 위 · 유리 천장</p>' +
          '<p class="desc">여기엔 더 놓을 자리가 없다. 방주는 아래로 자란다.<br>배치되지 않은 사람은 이 홀에 모인다.</p>';
        $('#panel').hidden = false; placePanel(); return;
      }
      const ids = Object.keys(catalog);
      body.innerHTML =
        '<h2>빈 자리</h2>' +
        '<p class="sub">' + fl + '층 · 깊이 ' + depth + 'm · ' + esc(zoneAt(f)) + '</p>' +
        '<p class="desc">아래로 내려갈수록 유물이 좋아지고 위험해진다.</p>' +
        '<h3>증축</h3><div class="blist">' +
        ids.map(id => {
          const lack = lacking(id);
          const cap = (ark.room_caps || {})[id];
          return '<button class="bopt' + (lack.length ? ' lack' : '') + '" data-room="' + esc(id) + '"' +
            (lack.length ? ' disabled' : '') + '><b>' + esc(catalog[id].name || id) +
            (cap ? ' · 정원 ' + cap : '') + '</b>' +
            '<small>' + esc(lack.length ? '부족: ' + lack.join(' · ') : costLine(id)) + '</small></button>';
        }).join('') + '</div>';
      body.querySelectorAll('.bopt[data-room]').forEach(b => {
        b.addEventListener('click', () => build(b.dataset.room, slot));
      });
    }
    $('#panel').hidden = false; placePanel();
  }

  function bindPeople(body) {
    body.querySelectorAll('.who[data-pid]').forEach(el => {
      el.addEventListener('click', () => {
        const id = el.dataset.pid;
        if (carry && carry.id === id) { setCarry(null); return; }
        const p = (ark.residents_list || []).find(r => r.id === id);
        if (p) { setCarry({ id: p.id, name: p.name, role: p.role }); toast(p.name + ' — 옮길 방을 고르세요'); }
        if (sel) openPanel(sel.slot);
      });
    });
  }

  function openHallPanel() {
    sel = null;
    const list = (ark.residents_list || []).filter(r =>
      cb.stations[r.id] === undefined && cb.outside.indexOf(r.id) < 0);
    const body = $('#panelBody');
    body.innerHTML = '<h2>홀<span class="cap">' + list.length + '명</span></h2>' +
      '<p class="sub">돔 상부 · 배치되지 않은 사람</p>' +
      '<p class="desc">여기 있는 사람은 아무 방도 지키지 않는다. 습격이 오기 전에 자리를 정한다.</p>' +
      destList() +
      (list.length ? list.map(p => personRow(p, null)).join('') : '<div class="who"><em>모두 자리에 있다</em></div>');
    bindDest(body);
    bindPeople(body);
    $('#panel').hidden = false; placePanel();
  }

  function openWorkshop() {
    sel = null;
    const w = cb.workshop;
    const body = $('#panelBody');
    const live = (ark.rooms || []).filter(r => !r.flooded);
    body.innerHTML = '<h2>공방</h2>' +
      '<p class="sub">대응 도구 일곱 · 재료는 전부 유물</p>' +
      (w.has_workshop ? '' : '<p class="desc">아직 공방이 없다. 빈 자리에 공방을 지어야 만들 수 있다.</p>') +
      ((w.tools[0] && w.tools[0].hands) ? '<p class="eye-early">' + esc(w.tools[0].hands.ko) + '</p>'
        : (w.has_workshop ? '<p class="desc">공방에 아무도 없다. 도구는 손이 만든다 — 사람을 공방에 두면 재료가 달라진다.</p>' : '')) +
      w.tools.map(t => {
        const cost = Object.entries(t.cost).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
        const lack = Object.keys(t.lacking || {}).length;
        return '<div class="tool"><div><b>' + esc(t.name) +
          '<span class="kind">' + esc(KIND_KO[t.kind] || t.kind) + '</span>' +
          (t.owned ? '<span class="kind">가진 것 ' + t.owned + '</span>' : '') + '</b>' +
          '<small>' + esc(t.does) + ' · 주로 ' + esc((t.against || []).join('·')) + '</small>' +
          '<small>재료 ' + esc(cost) + (lack ? ' — 부족' : '') + '</small></div>' +
          '<div class="act"><button data-craft="' + esc(t.id) + '"' + (t.can_craft ? '' : ' disabled') + '>만들기</button>' +
          (t.kind !== 'consumable'
            ? '<select data-inst="' + esc(t.id) + '"' + (t.owned ? '' : ' disabled') + '>' +
              '<option value="">붙일 방…</option>' +
              live.map(r => '<option value="' + r.slot + '">' + esc((catalog[r.id] || {}).name || r.id) + '</option>').join('') +
              '</select>'
            : '') +
          '</div></div>';
      }).join('');
    body.querySelectorAll('button[data-craft]').forEach(b =>
      b.addEventListener('click', () => craft(b.dataset.craft)));
    body.querySelectorAll('select[data-inst]').forEach(s =>
      s.addEventListener('change', () => { if (s.value !== '') install(s.dataset.inst, parseInt(s.value, 10)); }));
    $('#panel').hidden = false; placePanel();
  }

  function closePanel() { sel = null; $('#panel').hidden = true; }

  function zoneAt(floor) {
    const y = (floor - DOME_FLOOR) * FLOOR_PITCH;
    const z = ZONES.find(z => y >= z.y0 && y < z.y1);
    return z ? z.ko : '무광층';
  }
  function creatureName(id) { return (cb && cb.creatures && cb.creatures[id] && cb.creatures[id].name) || id; }
  function toolName(id) {
    const t = cb && cb.workshop.tools.find(x => x.id === id);
    return t ? t.name : id;
  }

  // ── 동작 ──────────────────────────────────────────────────
  function setCarry(c) { carry = c; const el = $('#carry'); if (c) { el.textContent = c.name + ' — 놓을 방을 고르세요'; el.hidden = false; } else el.hidden = true; }

  async function place(residentId, slot) {
    try {
      const st = await api('/api/ark/station', { resident_id: residentId, slot: slot });
      apply(st); setCarry(null);
      toast(slot == null ? '홀로 되돌렸다' : '자리를 옮겼다');
      if (slot != null) openPanel(slot); else openHallPanel();
      refreshRaid();
    } catch (e) { toast(e.message || '옮기지 못했다'); setCarry(null); }
  }
  async function setLight(slot, on) {
    try { apply(await api('/api/ark/light', { slot, on })); toast(on ? '불을 켰다' : '불을 껐다 — 이 방은 우리도 못 본다');
          play(on ? 'sfx_lantern_on.ogg' : 'sfx_note_arrive.ogg', 0.4);
          if (sel) openPanel(sel.slot); refreshRaid(); }
    catch (e) { toast(e.message || '실패'); }
  }
  async function setPower(on) {
    try { apply(await api('/api/ark/power', { on })); toast(on ? '전원을 올렸다' : '전원을 내렸다 — 돔이 조용해진다'); refreshRaid(); }
    catch (e) { toast(e.message || '실패'); }
  }
  async function doRecall() {
    try { const r = await api('/api/ark/recall', {}); apply(r.state);
          toast(r.recalled.length ? r.recalled.length + '명을 들였다' : '밖에 아무도 없다');
          play('sfx_airlock_cycle.ogg', 0.5); refreshRaid(); }
    catch (e) { toast(e.message || '실패'); }
  }
  async function craft(id) {
    try { const r = await api('/api/ark/craft', { tool_id: id }); apply(r.state);
          toast((r.made || {}).name + ' 을(를) 만들었다'); openWorkshop(); }
    catch (e) { toast(e.message || '만들지 못했다'); }
  }
  async function install(id, slot) {
    try { apply(await api('/api/ark/install', { tool_id: id, slot })); toast('붙였다'); openWorkshop(); refreshRaid(); }
    catch (e) { toast(e.message || '붙이지 못했다'); openWorkshop(); }
  }
  async function build(roomId, slot) {
    try {
      const st = await api('/api/ark/build', { room_id: roomId, slot });
      apply(st);
      toast(((catalog[roomId] || {}).name || roomId) + ' 증축');
      openPanel(slot);
    } catch (e) { toast(e.message || '증축하지 못했다'); }
  }

  async function advanceRaid() {
    const btn = $('#radv'); btn.disabled = true;
    try {
      const r = await api('/api/raid/advance', {});
      if (r.state) apply(r.state);
      if (r.result) {
        play((cb.raid && cb.raid.creature.audio && cb.raid.creature.audio.contact) || 'sfx_water_splash.ogg', 0.6);
        if (r.result === 'breached') play('sfx_room_flood.ogg', 0.75);
        toast(r.line);
        showOutcome(r);
      }
      renderRaid();
    } catch (e) { toast(e.message || '실패'); }
    btn.disabled = false;
  }

  function showOutcome(r) {
    const body = $('#panelBody'); sel = null;
    const imp = (r.new_imprints || []).map(n =>
      '<div class="who"><b>' + esc(n.resident) + '</b><em>' + esc(n.imprint.name) + '</em></div>' +
      '<p class="desc">' + esc(n.line) + '</p>').join('');
    body.innerHTML = '<h2>' + esc(r.result_ko) + '</h2>' +
      '<p class="sub">' + esc(cb.raid ? cb.raid.creature.name : '') + ' · 점수 ' + r.score + ' / 필요 ' + r.need + '</p>' +
      '<p class="desc">' + esc(r.line) + '</p>' +
      (r.lost_room ? '<p class="lost">' + esc(r.lost_room) + '을(를) 잃었다. 격벽은 다시 열리지 않는다.</p>' : '') +
      (r.injured ? '<p class="lost">' + esc(r.injured) + '이(가) 다쳤다.</p>' : '') +
      '<h3>이번 판정</h3><div class="kv">' +
      (r.parts || []).map(p => '<span>' + esc(p.ko) + ' ' + p.v + '</span>').join('') + '</div>' +
      (Object.keys(r.gained || {}).length
        ? '<h3>남은 것</h3><div class="kv">' + Object.entries(r.gained).map(([k, v]) =>
            '<span>' + esc(RES_KO[k] || k) + ' ' + (v > 0 ? '+' : '') + v + '</span>').join('') + '</div>' : '') +
      (imp ? '<h3>겪은 사람</h3>' + imp : '') +
      ((r.next_raid_hint && r.next_raid_hint.ko) ? '<h3>문어</h3><p class="desc">' + esc(r.next_raid_hint.ko) + '</p>' : '');
    $('#panel').hidden = false; placePanel();
  }

  // ── 습격 막대 ─────────────────────────────────────────────
  function renderRaid() {
    const bar = $('#raidbar'), raid = cb && cb.raid;
    if (!raid) {
      bar.hidden = true; document.body.classList.remove('raid-on');
      if (view.w <= 560 && lastBarH) { cam.y += (lastBarH / 2) / cam.z; lastBarH = 0; }
      const hint = cb && cb.next_raid_hint;
      if (hint && hint.ko) { /* 문어의 예고는 토스트로 한 번만 */ }
      return;
    }
    bar.hidden = false; document.body.classList.add('raid-on');
    bar.classList.toggle('calm', !raid.creature.threat);
    $('#rstage').textContent = STAGE_LABEL[raid.stage] || raid.stage;
    $('#rwho').textContent = raid.creature.name + (raid.target_room ? ' → ' + raid.target_room : '');
    const steps = $('#rsteps').children;
    for (let i = 0; i < steps.length; i++) steps[i].classList.toggle('on', i <= raid.stage_no);
    $('#rtext').textContent = raid.stage === 'sound' ? raid.creature.sound
      : raid.stage === 'silhouette' ? raid.creature.silhouette
      : (raid.line || raid.creature.contact);
    $('#rhow').textContent = raid.creature.threat ? '막는 법 — ' + raid.creature.how : '위협이 아니다. 식구다.';
    let eyeEl = $('#reye');
    if (!eyeEl) { eyeEl = document.createElement('p'); eyeEl.id = 'reye'; eyeEl.className = 'eye-early';
                  $('#rhow').after(eyeEl); }
    eyeEl.hidden = !raid.eye_early;
    if (raid.eye_early) eyeEl.textContent = raid.eye_early.ko;
    const g = $('#rgate'), wd = $('#rwould');
    if (raid.ready && raid.creature.threat && raid.stage !== 'done') {
      g.hidden = false; wd.hidden = false;
      g.classList.toggle('ok', !!raid.ready.gate.ok);
      g.innerHTML = '<b>' + (raid.ready.gate.ok ? '준비됐다' : '아직이다') + '</b>' + esc(raid.ready.gate.ko);
      wd.classList.toggle('bad', raid.ready.would !== 'held');
      wd.innerHTML = '지금 맞서면 <b>' + esc(raid.ready.would_ko) + '</b>';
    } else { g.hidden = true; wd.hidden = true; }
    const btn = $('#radv');
    if (raid.stage === 'sound') { btn.hidden = false; btn.textContent = '귀를 기울인다'; }
    else if (raid.stage === 'silhouette') { btn.hidden = false; btn.textContent = '맞선다'; }
    else { btn.hidden = true; }
    $('#rhint').textContent = raid.stage === 'silhouette'
      ? '서두르지 않아도 된다. 누르기 전까지 아무 일도 일어나지 않는다. 그동안 사람을 옮기고 불을 끄고 도구를 붙인다.'
      : (raid.stage === 'done' ? '오늘은 지나갔다.' : '어느 방으로 오는지는 아직 모른다.');
    // 폰에서 막대 높이가 바뀌면 거점을 그만큼 아래로 민다(줌은 건드리지 않는다).
    // 막대가 홀을 덮어 사람을 못 집는 일을 막는다
    const bh = bar.offsetHeight;
    if (view.w <= 560 && lastBarH && bh !== lastBarH) cam.y -= (bh - lastBarH) / cam.z;
    lastBarH = bh;
    // 단계가 바뀌는 순간에만 소리를 낸다
    if (raid.id !== lastRaidId || raid.stage !== lastStage) {
      lastRaidId = raid.id; lastStage = raid.stage;
      if (raid.stage === 'sound') play(raid.creature.audio.sound, 0.5);
      if (raid.stage === 'silhouette') { approach = 0; play(raid.creature.audio.sound, 0.35); }
    }
  }

  async function refreshRaid() {
    try {
      const r = await api('/api/raid/today?uid=' + encodeURIComponent(uid));
      if (r.state) apply(r.state);
      renderRaid();
    } catch (e) { /* 습격이 없어도 화면은 돈다 */ }
  }

  // ── 상태 반영 ─────────────────────────────────────────────
  function apply(st) {
    ark = st;
    cb = st.combat || cb;
    if (st.rooms_catalog) catalog = st.rooms_catalog;
    slots = st.slots || slots;
    floorSlots = st.floor_slots || floorSlots;
    if (typeof st.dome_floor === 'number') DOME_FLOOR = st.dome_floor;
    $('#dayline').textContent = 'Day ' + st.day;
    $('#actline').textContent = (st.act || 1) + '막 · ' + (st.act_ko || '');
    const res = st.resources || {};
    $('#resbar').innerHTML = Object.keys(res)
      .filter(k => CORE_RES.indexOf(k) >= 0 || res[k] > 0)
      .map(k => '<span>' + esc(RES_KO[k] || k) + '<b>' + esc(res[k]) + '</b></span>').join('');
    const g = st.gauges || {};
    if (g.air) $('#bandAir').style.setProperty('--v', Math.round(g.air.value * 100) + '%');
    if (g.depth) {
      $('#bandDepth').style.setProperty('--v', Math.round(Math.max(0.06, g.depth.value) * 100) + '%');
      $('#zoneline').textContent = g.depth.zone || '';
    }
    const pw = $('#pwr');
    pw.textContent = cb.power_on ? '전원 켜짐' : '전원 내림';
    pw.classList.toggle('off', !cb.power_on);
    $('#recallbtn').hidden = !(cb.outside && cb.outside.length);
  }

  async function load(first) {
    try {
      const st = await api('/api/ark?uid=' + encodeURIComponent(uid));
      apply(st);
      if (first) fit();
      try {
        const rows = await api('/api/spots?uid=' + encodeURIComponent(uid));
        spots = (rows || []).filter(r => r && r.act === 1 && r.pos);
      } catch (e2) { spots = []; }
      await refreshRaid();
      if (first) fit();                 // 습격 막대가 뜬 뒤의 여백으로 다시 맞춘다
      const hint = cb && cb.next_raid_hint;
      if (first && hint && hint.ko && (!cb.raid || cb.raid.stage === 'done')) toast(hint.ko);
    } catch (e) { toast('방주를 불러오지 못했다 — ' + (e.message || '')); }
  }

  // ── 입력: 드래그(데스크톱) · 탭-탭(폰). 둘 다 같은 길로 간다 ──
  const hitAt = (px, py, kind) => {
    for (let i = hits.length - 1; i >= 0; i--) {
      const h = hits[i];
      if (kind && h.kind !== kind) continue;
      if (px >= h.x && px <= h.x + h.w && py >= h.y && py <= h.y + h.h) return h;
    }
    return null;
  };
  function slotAt(px, py) {
    const wx = wxOf(px), wy = wyOf(py);
    for (let s = 0; s < slots; s++) {
      const q = rectOf(s);
      if (wx >= q.x && wx <= q.x + q.w && wy >= q.y && wy <= q.y + q.h) return s;
    }
    return null;
  }

  let drag = null;
  cv.addEventListener('pointerdown', (e) => {
    const r = cv.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top;
    pointer = { x: px, y: py };
    const p = hitAt(px, py, 'person');
    drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: 0, person: p || null };
    cv.setPointerCapture(e.pointerId);
    if (!p) cv.classList.add('dragging');
  });
  cv.addEventListener('pointermove', (e) => {
    const r = cv.getBoundingClientRect();
    pointer = { x: e.clientX - r.left, y: e.clientY - r.top };
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    drag.moved = Math.max(drag.moved, Math.abs(dx) + Math.abs(dy));
    if (drag.person) {
      if (drag.moved > 8 && !dragging) {
        const pr = (ark.residents_list || []).find(z => z.id === drag.person.id);
        dragging = pr ? Object.assign({}, pr) : null;
      }
      return;                                  // 사람을 들고 있을 때 카메라는 움직이지 않는다
    }
    cam.x = drag.cx - dx / cam.z; cam.y = drag.cy - dy / cam.z;
  });
  cv.addEventListener('pointerup', (e) => {
    const d = drag; drag = null; cv.classList.remove('dragging');
    if (!ark || !d) { dragging = null; return; }
    const r = cv.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top;

    if (dragging) {                            // 드롭 — 데스크톱 드래그의 끝
      const id = dragging.id; dragging = null;
      const hall = hitAt(px, py, 'hall');
      const s = slotAt(px, py);
      if (hall && s == null) { place(id, null); return; }
      if (s != null) { place(id, s); return; }
      toast('방이나 홀 위에 놓으세요');
      return;
    }
    if (d.moved > 6) return;                   // 카메라를 끌었을 뿐이다

    const s = slotAt(px, py);
    if (carry) {
      // **들고 있을 때는 '놓기'가 먼저다.** 사람이 있는 방을 탭했다고 그 방 사람을 새로 집으면
      // 영원히 못 옮긴다(폰에서 실제로 걸린 결함).
      if (d.person && d.person.id === carry.id) { setCarry(null); closePanel(); toast('놓았다'); return; }
      if (s != null) { place(carry.id, s); return; }
      if (hitAt(px, py, 'hall')) { place(carry.id, null); return; }
      setCarry(null); toast('그만두었다'); return;
    }
    if (d.person) {                            // 탭 1: 사람을 집는다 — 그 사람의 카드도 함께 연다
      setCarry({ id: d.person.id, name: d.person.name, role: d.person.role });
      toast(d.person.name + ' — 옮길 방을 탭하세요');
      if (d.person.from == null) openHallPanel(); else openPanel(d.person.from);
      return;
    }
    if (s != null) { openPanel(s); return; }
    if (hitAt(px, py, 'hall')) { openHallPanel(); return; }
    closePanel();
  });
  cv.addEventListener('pointercancel', () => { drag = null; dragging = null; cv.classList.remove('dragging'); });
  cv.addEventListener('wheel', (e) => {
    e.preventDefault();
    const r = cv.getBoundingClientRect();
    zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });

  $('#zin').addEventListener('click', () => zoomAt(view.w / 2, view.h / 2, 1.2));
  $('#zout').addEventListener('click', () => zoomAt(view.w / 2, view.h / 2, 1 / 1.2));
  $('#zfit').addEventListener('click', fit);
  $('#panelClose').addEventListener('click', closePanel);
  $('#radv').addEventListener('click', advanceRaid);
  $('#pwr').addEventListener('click', () => setPower(!cb.power_on));
  $('#wbtn').addEventListener('click', openWorkshop);
  $('#recallbtn').addEventListener('click', doRecall);
  window.addEventListener('resize', () => { resize(); });

  // 다른 화면(index)과 같은 규약: 밖에서 쓸 수 있게 몇 개만 연다.
  // slotBox·peopleHits 는 자동 검수(Playwright)가 캔버스를 정확히 누르기 위한 읽기 전용 창이다.
  window.ARKBASE = {
    reload: () => load(false), refreshRaid, fit, uid,
    slotBox: (s) => { const q = rectOf(s); return { x: sx(q.x), y: sy(q.y), w: q.w * cam.z, h: q.h * cam.z }; },
    hallBox: () => { const h = hallRect(); return { x: sx(h.x), y: sy(h.y), w: h.w * cam.z, h: h.h * cam.z }; },
    peopleHits: () => hits.filter(h => h.kind === 'person').map(h => ({ id: h.id, name: h.name, from: h.from,
      cx: h.x + h.w / 2, cy: h.y + h.h / 2 })),
  };

  resize(); fit(); raf = requestAnimationFrame(frame); load(true);
})();
