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

  // ── 세계 좌표(px) — S12-B: M5 「절벽 끝에 기댄 가라앉은 탑」. 칸·승강로·홀은 m5map.js(맵 어댑터)가 준다 ──
  // 세계 1 m = 82.5 px(플레이트·도트 ×3 과 같은 자). 칸 = 플레이트 outer_rect 564×317 을 1:1.
  const DEPTH_PER_FLOOR = 60;                      // m. server.py 의 같은 상수와 맞춘다
  const PAD = 0;                                   // 칸 = 플레이트 바깥 테두리(벽까지). 여백은 탑 골조가 그린다
  let DOME_FLOOR = 1;                              // 깊이 0 m 의 층(= 시작 방 slot 2 의 층). 서버가 내려준다
  const MAP = () => window.ArkMap.get();

  // 깊이 구역: 화면 위는 갈 수 없는 광층, 아래는 해구 (REF_CROSS_SECTION §3)
  // 경계는 **미터로** 정하고 맵의 깊이 자(depthY: 0 m = 1층 윗변, 60 m = 한 층)로 옮긴다 —
  // server.py DEPTH_ZONES 와 같은 값이어야 한다(0 / 180 / 210 m).
  // 해구 문턱 180 m = threats.json 등급 4 의 깊이. 두 곳이 달랐던 것을 S10-C 에서 180 으로 통일.
  // M5 에서 180 m 선은 탑 4번째 층(storey 3) 윗변 = layout.json depth.trench_y(2295)와 같다(S12-B 에서 대조).
  const TRENCH_M = 180, TRENCH_DEEP_M = 210;
  const ZONE_M = [
    { m0: -1e4, m1: -100, ko: '광층',    note: '갈 수 없다' },
    { m0: -100, m1: -45,  ko: '박광층',  note: '실루엣의 층' },
    { m0: -45,  m1: TRENCH_M, ko: '무광층',  note: '돔이 사는 층' },
    { m0: TRENCH_M, m1: TRENCH_DEEP_M, ko: '해구 문턱', note: '여기부터 값이 달라진다' },
    { m0: TRENCH_DEEP_M, m1: 1e4, ko: '해구',    note: '가장 오래된 성문' },
  ];
  const zoneY = (m) => MAP().depthY(Math.max(-400, Math.min(400, m)));
  const ZONES_OF = () => ZONE_M.map(z => ({ y0: z.m0 < -1e3 ? -1e5 : zoneY(z.m0), y1: z.m1 > 1e3 ? 1e5 : zoneY(z.m1), ko: z.ko, note: z.note }));
  // 물색: 위(광층)에서 아래(해구)로. 청록~남색~검정만 쓴다(FLAT_FOLK §5 — 물만 차갑다). 단위는 깊이 m
  const WATER_M = [[-200, '#1e737c'], [-130, '#14545e'], [-60, '#0d3b45'], [-20, '#0a2a33'],
                   [40, '#07202a'], [120, '#04141c'], [200, '#020a10'], [300, '#01060a']];

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
    if (!r.ok) { const er = new Error(j.detail || r.statusText || '통신 실패'); er.status = r.status; throw er; }
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
  const TARGET_PPM = 82.5;        // 세계 1 m = 82.5 px (cam.z = 1 이면 도트 ×3 — 플레이트와 같은 자, S12-B)

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

  // ── 칸 기하 (S12-B: 서버 slot → M5 칸은 m5map.js 의 대응표 하나) ─────────────
  const floorOf = (slot) => Math.floor(slot / floorSlots);          // 서버 층(깊이 계산의 정본)
  const storeyOf = (slot) => floorOf(slot) - DOME_FLOOR;            // 맵 층(storey 0 = 깊이 0 m)
  function cellOf(slot) { return window.ArkMap.slotCell(slot, floorSlots, DOME_FLOOR); }
  // rectOf 는 예전 이름 그대로 — 칸의 세계 사각형. 서버 칸이 맵에 없으면(돔 상부 slot 0·1) null
  function rectOf(slot) {
    const c = cellOf(slot);
    if (!c) return null;
    return { x: c.x, y: c.y, w: c.w, h: c.h, floor: floorOf(slot), storey: c.storey, col: c.col,
             floorY: c.floor_y, stand: c.stand_x || [c.x + 84, c.x + c.w - 84], cell: c };
  }
  const floorCount = () => Math.max(1, Math.ceil(slots / floorSlots));
  function worldBounds() { return MAP().world; }
  // 홀 = 돔 안의 공용 공간. 배치되지 않은 사람이 여기 모인다
  function hallRect() {
    const d = MAP().dome;
    const w = Math.min(d.w, 1240), x = d.x + (d.w - w) / 2;          // 돔 유리 아래 가운데. 바닥 = dome.floor_y
    return { x, y: d.floor_y - 230, w, h: 230 };
  }
  // 에어락 바깥. 밖에 나가 있는 사람이 서는 자리(손톱 무리의 날에만 보인다) — 탑 오른 외벽 밖, 심연 쪽
  function outsideRect() {
    const L = MAP(), s0 = L.tower.storeys[0];
    return { x: L.tower.x1 + 30, y: s0.floor_y - 200, w: 300, h: 200 };
  }

  // ══════════════════════════════════════════════════════════════
  //  이동 어댑터 — **맵마다 다른 것은 이 블록 하나뿐이다.** (S11-C → S12-B M5)
  //  길 계산·엘리베이터 시간표·방 안의 삶은 movement.js 가 하고, 그쪽은 화면 좌표를 모른다.
  //  M5: 승강로 둘(layout.json shafts A·B). 층 = storey(0 = 깊이 0 m), 홀 = -1층(돔 바닥).
  // ══════════════════════════════════════════════════════════════
  const PX_PER_M = TARGET_PPM;                       // 세계 px / m — 캐릭터 키를 재는 자와 같은 자
  const HALL_FLOOR = -1;
  function floorLine(f) {                            // 그 층 사람들의 발선(세계 px)
    return MAP().floorY(f <= HALL_FLOOR ? -1 : f);
  }
  function standX(r, i, n) { return r.stand[0] + (r.stand[1] - r.stand[0]) * (i + 1) / (n + 1); }
  const MOVE_ADAPTER = {
    graph() {
      const L = MAP(), last = L.storeys.length - 1, cap = (L.car && (L.car.cap || L.car.cap_hint)) || 2;
      return { walkSpeed: 1.3, shafts: L.shafts.map(s => ({ id: s.id, x: s.cx / PX_PER_M, floors: [HALL_FLOOR, last],
               cap, secPerFloor: 0.9, door: 0.5, home: 0,
               doorGap: (s.w / 2) / PX_PER_M + 0.3 })) };            // 승강로 바로 바깥에 줄을 선다
    },
    nodeOf(where, i, n) {                            // where: slot 번호 | 'hall' | 'out'
      if (where === 'out') { const o = outsideRect(); return { floor: 0, x: (o.x + o.w * (i + 1) / (n + 1)) / PX_PER_M }; }
      if (where === 'hall') { const h = hallRect(); return { floor: HALL_FLOOR, x: (h.x + h.w * (i + 1) / (n + 1)) / PX_PER_M }; }
      const r = rectOf(where);
      if (!r) { const h = hallRect(); return { floor: HALL_FLOOR, x: (h.x + h.w / 2) / PX_PER_M }; }
      return { floor: r.storey, x: standX(r, i, n) / PX_PER_M };
    },
    toWorld(floor, x) {                              // floor 는 소수도 받는다(엘리베이터 안)
      const f0 = Math.floor(floor), f1 = Math.ceil(floor), y0 = floorLine(f0);
      return { x: x * PX_PER_M, y: y0 + (floorLine(f1) - y0) * (floor - f0) };
    },
  };
  // movement.js 가 없으면(로드 실패) 이동 없이 예전처럼 자리에 바로 나타난다 — 화면은 멈추지 않는다
  const NO_TRAFFIC = { go() {}, at() { return null; }, arrivedAt() { return -Infinity; }, moving() { return []; },
                       car() { return null; }, cars() { return []; }, setGraph() {}, graph() { return { byId: {} }; }, forget() {} };
  const traffic = window.ArkMove ? ArkMove.createTraffic(MOVE_ADAPTER.graph()) : NO_TRAFFIC;
  let movingNow = {};

  // ── 카메라 ────────────────────────────────────────────────
  const sx = (wx) => (wx - cam.x) * cam.z + view.w / 2;
  const sy = (wy) => (wy - cam.y) * cam.z + view.h / 2;
  const wxOf = (px) => (px - view.w / 2) / cam.z + cam.x;
  const wyOf = (py) => (py - view.h / 2) / cam.z + cam.y;

  // ── 가로 화면(S12-B, DECISIONS 2026-10-03 「화면은 가로」) ─────────────
  // UI 가 가린 만큼을 빼고 맞춘다. 가로에서는 HUD 가 왼쪽 위·왼쪽 아래·오른쪽 아래 가장자리에만 있다.
  // 오른쪽은 열린 심연 — 위협이 오는 쪽이라 비워 둔다(습격 막대만 오른쪽 위에 뜬다).
  const isPortrait = () => view.h > view.w;
  function uiInset() {
    const bar = $('#raidbar');
    if (isPortrait()) {
      const top = (bar && !bar.hidden && view.w <= 560) ? bar.offsetHeight + 10 : 0;
      return { top, bottom: view.w <= 560 ? 104 : 72, left: 0, right: 0 };
    }
    const phone = view.h <= 500;
    return { top: phone ? 34 : 64, bottom: phone ? 52 : 70, left: 0, right: 0 };
  }
  const ZMIN_ABS = 0.12, ZMAX = 2.4;
  function zMin() {                                  // 세계 밖이 보이지 않을 만큼만 물러난다
    const b = worldBounds();
    return Math.max(ZMIN_ABS, Math.max(view.w / (b.x1 - b.x0), view.h / (b.y1 - b.y0)));
  }
  // 카메라는 세계 경계 안에 묶는다(가로·세로 팬 + 줌). 성장은 아래 — 세로로 끌면 깊이 내려간다
  function clampCam() {
    const b = worldBounds();
    cam.z = Math.max(zMin(), Math.min(ZMAX, cam.z));
    const hw = view.w / 2 / cam.z, hh = view.h / 2 / cam.z;
    cam.x = (b.x1 - b.x0) <= 2 * hw ? (b.x0 + b.x1) / 2 : Math.max(b.x0 + hw, Math.min(b.x1 - hw, cam.x));
    cam.y = (b.y1 - b.y0) <= 2 * hh ? (b.y0 + b.y1) / 2 : Math.max(b.y0 + hh, Math.min(b.y1 - hh, cam.y));
  }
  // 처음 화면(PM 결정 2026-10-03, 두 단계): ① 홀·돔 가운데, 주민이 70 CSS px 이상으로 보이는 줌에서 연다
  // ② 습격 예고(실루엣)가 열리면 심연 쪽으로 옮긴다(raidPan). 도트는 정수 배율이라 ×2 가 되는 첫 줌(0.5)이 하한 —
  // 키 1.6 m = 원본 44 px × 2 = 88 px. 그 아래(×1)는 44 px 로 판독 하한에 못 미친다
  const READ_Z = (1.5 * 27.5) / TARGET_PPM + 0.005;
  function fit() {
    const L = MAP(), d = L.dome;
    cam.z = Math.max(zMin(), Math.min(ZMAX, READ_Z));
    cam.x = L.glass ? L.glass.cx : d.x + d.w / 2;
    // 돔 꼭대기가 HUD 바로 아래에 오게 — 그 아래로 홀과 1층이 이어진다
    const ins = uiInset();
    cam.y = (d.y - 30) + (view.h / 2 - ins.top) / cam.z;
    if (isPortrait()) cam.y = d.floor_y + 120;
    clampCam();
  }
  // 습격 예고가 열리면 노려지는 방과 그 오른쪽 심연이 한 화면에 들어오게 천천히 옮긴다(줌은 그대로)
  let raidPanned = null;
  function raidPan(raid) {
    if (!raid || raid.stage !== 'silhouette' || raid.target_slot == null || raidPanned === raid.id + ':' + raid.stage) return;
    const r = rectOf(raid.target_slot); if (!r) return;
    raidPanned = raid.id + ':' + raid.stage;
    const L = MAP(), bar = $('#raidbar');
    // 습격 막대가 덮지 않는 폭 안에 [노려지는 방 … 외벽 밖 600 px] 이 들어오게. 안 들어갈 때만 그만큼 물러난다
    const barW = (!bar.hidden && !isPortrait()) ? bar.offsetWidth + 24 : 0;
    const avail = Math.max(200, view.w - barW), span = (L.tower.x1 + 600) - (r.x - 60);
    const z = Math.max(zMin(), Math.min(cam.z, avail / span));
    const x = (r.x - 60) + (view.w / 2) / z;
    camTo = { from: { x: cam.x, y: cam.y, z: cam.z }, x, y: r.y + r.h / 2, z, t0: performance.now(), dur: 1200 };
  }
  function zoomAt(px, py, k) {
    const wx = wxOf(px), wy = wyOf(py);
    cam.z = Math.max(zMin(), Math.min(ZMAX, cam.z * k));
    cam.x = wx - (px - view.w / 2) / cam.z;
    cam.y = wy - (py - view.h / 2) / cam.z;
    clampCam();
  }

  function resize() {
    view.dpr = Math.min(2, window.devicePixelRatio || 1);
    view.w = cv.clientWidth; view.h = cv.clientHeight;
    cv.width = Math.round(view.w * view.dpr); cv.height = Math.round(view.h * view.dpr);
    ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
    if (ark) clampCam();
  }

  // ── 그리기: 겹 다섯(S12-B) — 뒤(물·빛) · 가운데(절벽·먼 것) · 탑 껍데기 · 승강기 · 앞(해초·부유물) ──
  // 배경 담당의 층 그림(layout.json layers.files)이 오면 그 겹 자리에 그대로 얹는다. 오기 전에는 같은 자리에
  // 벡터로 그린다. 매 프레임 겹마다 drawImage 한 번 또는 경로 몇 개 — 픽셀 단위 작업은 없다(D8).
  const layerImgs = {};                               // 겹 이름 → [{img, x, y, w, h, parallax}]
  function loadLayers() {
    MAP().layers.forEach(f => {
      const key = f.layer || f.id || f.name || 'back';
      const img = new Image();
      const sc = f.scale || 1;
      // place[] 가 있으면 같은 그림을 여러 자리에(승강로 A·B)
      const spots = (f.place && f.place.length) ? f.place : [{ x: f.x || 0, y: f.y || 0 }];
      const rows = spots.map(p => ({ img, ok: false, x: p.x, y: p.y, w: f.w != null ? f.w * sc : null, h: f.h != null ? f.h * sc : null,
                                     sc, parallax: f.parallax || 1 }));
      img.onload = () => rows.forEach(row => {
        row.ok = img.naturalWidth > 0;
        if (row.w == null) row.w = img.naturalWidth * sc;
        if (row.h == null) row.h = img.naturalHeight * sc;
      });
      img.src = window.ArkMap.dir + f.file;
      (layerImgs[key] = layerImgs[key] || []).push(...rows);
    });
  }
  // 겹 이름은 배경 담당 표기 어느 쪽이든 받는다
  const LAYER_ALIAS = { back: ['back', 'bg', 'far'], mid: ['cliff', 'mid'], shell: ['tower_shell', 'shell', 'tower'],
                        elevator: ['elevator_shaft', 'elevator', 'shaft'], front: ['front', 'fg', 'near'] };
  function layerReady(name) { return (LAYER_ALIAS[name] || [name]).some(k => (layerImgs[k] || []).some(r => r.ok)); }
  // 보이는 부분만 잘라 그린다(원본 픽셀 → 화면). 큰 겹(탑 껍데기 3907×2890)도 매 프레임 화면 크기만큼만 옮긴다(D8)
  function drawLayer(name) {
    let drew = false;
    (LAYER_ALIAS[name] || [name]).forEach(k => (layerImgs[k] || []).forEach(r => {
      if (!r.ok) return;
      drew = true;
      // 시차(앞 겹 1.12): 카메라가 기준점에서 움직인 만큼 조금 더 움직인다
      let ox = 0, oy = 0;
      if (r.parallax !== 1) { const L = MAP(); ox = -(cam.x - (L.tower.x0 + L.tower.x1) / 2) * (r.parallax - 1); oy = -(cam.y - L.depth.y0) * (r.parallax - 1) * 0.5; }
      const vx0 = wxOf(0) - ox, vy0 = wyOf(0) - oy, vx1 = wxOf(view.w) - ox, vy1 = wyOf(view.h) - oy;
      const x0 = Math.max(r.x, vx0), y0 = Math.max(r.y, vy0), x1 = Math.min(r.x + r.w, vx1), y1 = Math.min(r.y + r.h, vy1);
      if (x1 <= x0 || y1 <= y0) return;
      const k = r.img.naturalWidth / r.w;               // 세계 px → 원본 px
      ctx.drawImage(r.img, (x0 - r.x) * k, (y0 - r.y) * k, (x1 - x0) * k, (y1 - y0) * k,
                    sx(x0 + ox), sy(y0 + oy), (x1 - x0) * cam.z, (y1 - y0) * cam.z);
    }));
    return drew;
  }

  function drawWater(t) {
    const W = WATER_M.map(([m, c]) => [zoneY(m), c]);
    const g = ctx.createLinearGradient(0, sy(W[0][0]), 0, sy(W[W.length - 1][0]));
    const span = W[W.length - 1][0] - W[0][0];
    W.forEach(([y, c]) => g.addColorStop(Math.max(0, Math.min(1, (y - W[0][0]) / span)), c));
    ctx.fillStyle = g; ctx.fillRect(0, 0, view.w, view.h);
    if (drawLayer('back')) return;
    // 광층에서 내려오는 빛 — 갈 수 없는 밝음(REF_CROSS_SECTION §3). 심연 쪽으로 기운다
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const L = MAP();
    for (let i = 0; i < 4; i++) {
      const bx = sx(L.tower.x0 + i * 1100 + Math.sin(t / 9000 + i) * 60);
      const y0 = sy(0), y1 = sy(L.depth.y0 + 200);
      const lg = ctx.createLinearGradient(0, y0, 0, y1);
      lg.addColorStop(0, 'rgba(120,200,205,0.10)'); lg.addColorStop(1, 'rgba(120,200,205,0)');
      ctx.fillStyle = lg;
      ctx.beginPath();
      ctx.moveTo(bx - 50 * cam.z, y0); ctx.lineTo(bx + 50 * cam.z, y0);
      ctx.lineTo(bx + 340 * cam.z, y1); ctx.lineTo(bx - 160 * cam.z, y1);
      ctx.closePath(); ctx.fill();
    }
    ctx.restore();
  }

  // 가운데 겹: 절벽(왼쪽 바위). 탑이 기대 선다. 절벽은 해구 문턱 바로 아래에서 끝난다(MAP_CONCEPTS M2)
  function drawCliff() {
    const L = MAP();
    if (!drawLayer('mid')) {
      const c = L.cliff, xT = c.x1_at_tower, top = c.top_y, bot = c.bottom_y;
      const pts = [[0, top + 40], [180, top], [520, top + 30], [760, top + 120], [xT - 60, top + 260], [xT, top + 420],
                   [xT, bot - 260], [xT - 140, bot - 80], [xT - 420, bot], [0, bot + 60]];
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(sx(x), sy(y)) : ctx.moveTo(sx(x), sy(y))));
      ctx.closePath();
      const g = ctx.createLinearGradient(0, sy(top), 0, sy(bot));
      g.addColorStop(0, '#3a2b1d'); g.addColorStop(0.55, '#24190f'); g.addColorStop(1, '#0c0907');
      ctx.fillStyle = g; ctx.fill();
      ctx.strokeStyle = 'rgba(12,9,6,0.9)'; ctx.lineWidth = Math.max(1.5, 6 * cam.z); ctx.stroke();
      // 지층 결 몇 줄 — 바위가 읽히게(Oxygen Not Included: 땅이 지도)
      ctx.save(); ctx.clip();
      ctx.strokeStyle = 'rgba(150,110,70,0.16)'; ctx.lineWidth = Math.max(1, 3 * cam.z);
      for (let k = 1; k < 8; k++) {
        const y = top + 140 + k * 240;
        ctx.beginPath(); ctx.moveTo(sx(0), sy(y)); ctx.bezierCurveTo(sx(300), sy(y - 40), sx(640), sy(y + 50), sx(xT), sy(y + 10)); ctx.stroke();
      }
      ctx.restore();
    }
    // 바위 칸으로 가는 굴(아직 파지 못했다 — 서버 칸이 없다. 칸 자체는 drawSealed). 절벽 그림에는 이미 있다
    if (!layerReady('mid')) L.rock.forEach(r => {
      if (!r.tunnel) return;
      const tu = r.tunnel;
      ctx.fillStyle = 'rgba(13,10,7,0.92)'; ctx.fillRect(sx(tu.x), sy(tu.y), tu.w * cam.z, tu.h * cam.z);
      ctx.strokeStyle = 'rgba(90,67,32,0.6)'; ctx.lineWidth = Math.max(1, 3 * cam.z);
      ctx.strokeRect(sx(tu.x), sy(tu.y), tu.w * cam.z, tu.h * cam.z);
    });
  }

  // 부유물(D5). 물은 가만히 있지 않는다. 세계 좌표에 뿌리고 화면 밖은 건너뛴다
  const MOTES = Array.from({ length: 140 }, () => ({
    x: Math.random() * 5600, y: Math.random() * 3400,
    r: 1 + Math.random() * 3.5, v: 6 + Math.random() * 18, ph: Math.random() * 6.3,
  }));
  function drawMotes(t) {
    ctx.fillStyle = 'rgba(200,225,225,0.30)';
    for (const m of MOTES) {
      const y = ((m.y + (t / 1000) * m.v) % 3400 + 3400) % 3400;
      const x = m.x + Math.sin(t / 2600 + m.ph) * 24;
      const px = sx(x), py = sy(y);
      if (px < -20 || px > view.w + 20 || py < -20 || py > view.h + 20) continue;
      ctx.beginPath(); ctx.arc(px, py, Math.max(0.5, m.r * cam.z), 0, 6.2832); ctx.fill();
    }
  }

  // 바깥의 삶: 물고기 떼·해파리·먹 얼룩·어둠 속 눈. 배경의 생물 아틀라스(layers.creatures: frames + spawn)를
  // 스폰 표대로 띄운다 — 흐름(drift)·위아래(bob)·깜빡임(blink). 열몇 장뿐이고 탭이 숨으면 rAF 가 멈춘다.
  // 아틀라스가 없으면 작은 윤곽으로 대신한다. 심연 쪽에 산다 — 바깥이 살아 있다(MAP_CONCEPTS §3)
  const LIFE = [];
  const atlas = { img: new Image(), ok: false };
  function initLife() {
    LIFE.length = 0;
    const L = MAP(), C = L.creatures;
    if (C && C.file && C.frames && C.spawn) {
      atlas.img.onload = () => { atlas.ok = atlas.img.naturalWidth > 0; };
      atlas.img.src = window.ArkMap.dir + C.file;
      C.spawn.forEach((sp, i) => { const f = C.frames[sp.s]; if (f) LIFE.push(Object.assign({ fr: f, i }, sp)); });
      return;
    }
    const a = L.abyss;
    for (let i = 0; i < 3; i++) LIFE.push({ vec: 'school', x: a.x + 300 + i * 600, y: a.y + 300 + i * 520, speed: 22 + i * 7, drift: [-1, 0], z: 10, i });
    for (let i = 0; i < 4; i++) LIFE.push({ vec: 'jelly', x: a.x + 260 + i * 420, y: L.depth.y0 + 300 + (i * 431) % 1300, bob: [0, 30], period: 5 + i, z: 12, i });
  }
  function lifePos(c, s) {
    const W = MAP().world.x1, w = c.fr ? c.fr.w : 300;
    let x = c.x, y = c.y;
    if (c.drift) { const span = W + 2 * w; x = ((c.x + w + c.drift[0] * c.speed * s) % span + span) % span - w; }
    if (c.bob) y += Math.sin((s / (c.period || 5)) * 6.2832 + c.i) * c.bob[1];
    return { x, y };
  }
  function drawLife(t, front) {
    const s = t / 1000;
    for (const c of LIFE) {
      if ((c.z || 0) >= 20 ? !front : front) continue;   // z<20 은 탑 뒤, 20 이상은 탑 앞
      const p = lifePos(c, s);
      if (c.fr) {
        if (!atlas.ok) continue;
        const w = c.fr.w * cam.z, h = c.fr.h * cam.z, px = sx(p.x), py = sy(p.y);
        if (px + w < 0 || px > view.w || py + h < 0 || py > view.h) continue;
        let a = c.alpha == null ? 1 : c.alpha;
        if (c.blink) a *= (Math.sin(s * 0.7 + c.i * 2.3) > 0.55) ? 1 : 0.0;   // 어둠 속 눈 — 가끔만 뜬다
        if (a <= 0) continue;
        const flip = !!c.flip;                       // 아틀라스의 떼는 오른쪽을 본다 — 스폰 표의 flip 이 왼쪽
        ctx.save(); ctx.globalAlpha = a;
        if (flip) { ctx.translate(px + w, py); ctx.scale(-1, 1); ctx.drawImage(atlas.img, c.fr.x, c.fr.y, c.fr.w, c.fr.h, 0, 0, w, h); }
        else ctx.drawImage(atlas.img, c.fr.x, c.fr.y, c.fr.w, c.fr.h, px, py, w, h);
        ctx.restore();
        continue;
      }
      if (c.vec === 'school') {
        if (sx(p.x + 400) < 0 || sx(p.x - 400) > view.w || sy(p.y + 200) < 0 || sy(p.y - 200) > view.h) continue;
        ctx.fillStyle = 'rgba(150,200,205,0.30)';
        for (let i = 0; i < 26; i++) {
          const ox = ((i * 53) % 260) - 130 + Math.sin(s * 1.3 + i) * 8, oy = ((i * 37) % 120) - 60 + Math.cos(s + i * 0.7) * 6;
          ctx.beginPath(); ctx.ellipse(sx(p.x + ox), sy(p.y + oy), Math.max(0.8, 9 * cam.z), Math.max(0.5, 3 * cam.z), 0, 0, 6.2832); ctx.fill();
        }
      } else {
        const px = sx(p.x), py = sy(p.y), r = 24 * cam.z;
        if (px < -60 || px > view.w + 60 || py < -80 || py > view.h + 80) continue;
        ctx.fillStyle = 'rgba(160,220,225,0.22)'; ctx.strokeStyle = 'rgba(160,220,225,0.32)'; ctx.lineWidth = Math.max(0.6, 2 * cam.z);
        ctx.beginPath(); ctx.ellipse(px, py, r, r * 0.7, 0, Math.PI, 0); ctx.fill();
        for (let k = -2; k <= 2; k++) { ctx.beginPath(); ctx.moveTo(px + k * r * 0.35, py); ctx.lineTo(px + k * r * 0.35 + Math.sin(s * 1.6 + k) * 4 * cam.z, py + r * 1.8); ctx.stroke(); }
      }
    }
  }

  function drawSpots(t) {
    const L = MAP(), ppd = L.depth.pxPerM;
    for (const sp of spots) {
      if (!sp.unlocked || !sp.has_pos) continue;
      // 서버의 스팟 좌표(m, 가로 0 = 거점 가운데)를 같은 깊이 자로 옮긴다
      const px = sx((L.tower.x0 + L.tower.x1) / 2 + sp.pos.x * ppd), py = sy(L.depthY(sp.pos.y));
      if (px < -60 || px > view.w + 60 || py < -40 || py > view.h + 40) continue;
      const r = (6 + Math.sin(t / 900 + sp.pos.x) * 1.5) * Math.max(0.6, cam.z * 2);
      const g = ctx.createRadialGradient(px, py, 0, px, py, r * 5);
      g.addColorStop(0, 'rgba(240,176,85,0.55)'); g.addColorStop(1, 'rgba(240,176,85,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, r * 5, 0, 6.2832); ctx.fill();
      ctx.fillStyle = '#f0b055'; ctx.beginPath();
      ctx.moveTo(px, py - r); ctx.lineTo(px + r, py); ctx.lineTo(px, py + r); ctx.lineTo(px - r, py);
      ctx.closePath(); ctx.fill();
      if (cam.z > 0.25) {
        ctx.font = '11px "Noto Sans KR",sans-serif'; ctx.fillStyle = 'rgba(230,215,176,0.72)';
        ctx.fillText(sp.name || '', px + r + 6, py + 4);
      }
    }
  }

  // 깊이 구역 표지: 오른쪽(심연) 가장자리. 180 m 해구 문턱은 심연을 가로지르는 점선으로 보인다
  function drawZones() {
    const x = view.w - 14, Z = ZONES_OF();
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (const z of Z) {
      const y0 = sy(z.y0), y1 = sy(z.y1);
      if (y1 < 0 || y0 > view.h) continue;
      ctx.strokeStyle = 'rgba(150,200,200,0.16)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x - 40, y0); ctx.lineTo(x, y0); ctx.stroke();
      const my = Math.max(18, Math.min(view.h - 72, (Math.max(y0, 0) + Math.min(y1, view.h)) / 2));
      ctx.fillStyle = 'rgba(190,225,222,0.42)'; ctx.font = '11px "Noto Sans KR",sans-serif';
      ctx.fillText(z.ko, x, my);
    }
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    const ty = sy(zoneY(TRENCH_M));                    // 해구 문턱 180 m — 심연을 가로지르는 선
    if (ty > 0 && ty < view.h) {
      const x0 = Math.max(0, sx(MAP().tower.x1 + 20));
      ctx.save(); ctx.setLineDash([10, 8]); ctx.strokeStyle = 'rgba(176,58,36,0.38)'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(x0, ty); ctx.lineTo(view.w, ty); ctx.stroke(); ctx.restore();
      ctx.fillStyle = 'rgba(224,150,130,0.62)'; ctx.font = '11px "Noto Sans KR",sans-serif';
      ctx.fillText('180 m · 해구 문턱', x0 + 10, ty - 6);
    }
  }

  // 탑 껍데기: 바깥 골조(파사드)·층 슬래브·지붕. 서버 칸이 없는 칸은 물이 찬 칸으로(drawSealed)
  function drawShell() {
    if (drawLayer('shell')) return;
    const L = MAP(), t = L.tower, last = t.storeys[t.storeys.length - 1];
    const top = sy(t.roof_y), bot = sy(last.bottom_y + 160);
    ctx.fillStyle = '#17130e';                        // 탑 몸통(콘크리트 그늘)
    ctx.fillRect(sx(t.x0), top, (t.x1 - t.x0) * cam.z, bot - top);
    // 파사드 격자(양옆) — M4 의 건물 실루엣
    ctx.strokeStyle = 'rgba(120,100,70,0.32)'; ctx.lineWidth = Math.max(1, 4 * cam.z);
    [[t.x0, t.section_x0], [t.section_x1, t.x1]].forEach(([a, b]) => {
      for (let y = t.roof_y + 50; y < last.bottom_y + 100; y += 121) {
        const yy = sy(y); if (yy < -60 || yy > view.h + 10) continue;
        ctx.strokeRect(sx(a + 24), yy, (b - a - 48) * cam.z, 90 * cam.z);
      }
    });
    // 슬래브(층 바닥)와 지붕
    ctx.fillStyle = '#2b241a';
    t.storeys.forEach(s => ctx.fillRect(sx(t.section_x0 - 10), sy(s.bottom_y), (t.section_x1 - t.section_x0 + 20) * cam.z, Math.max(2, t.slab_h * cam.z)));
    ctx.fillRect(sx(t.x0 - 30), sy(t.roof_y), (t.x1 - t.x0 + 60) * cam.z, Math.max(2, 46 * cam.z));
  }
  // 탑 밑동은 해구의 어둠으로 녹아든다(칸·사람 위에 덮는다)
  function drawDeepDark() {
    if (layerReady('shell')) return;                  // 껍데기 그림에 이미 구워져 있다
    const L = MAP(), t = L.tower, last = t.storeys[t.storeys.length - 1];
    const y0 = sy(last.top_y - 120), dk = sy(L.depth.darkY);
    if (y0 > view.h) return;
    const g = ctx.createLinearGradient(0, y0, 0, dk);
    g.addColorStop(0, 'rgba(1,6,10,0)'); g.addColorStop(1, 'rgba(1,6,10,0.94)');
    ctx.fillStyle = g; ctx.fillRect(0, y0, view.w, dk - y0 + 1);
    ctx.fillStyle = 'rgba(1,6,10,0.94)'; ctx.fillRect(0, dk, view.w, Math.max(0, view.h - dk));
  }
  function drawDome(t) {
    if (layerReady('shell')) return;                  // 돔 골조와 유리는 탑 껍데기 그림에 있다
    const gl = MAP().glass;
    const cxs = sx(gl.cx), base = sy(gl.base_y), rx = gl.rx * cam.z, ry = gl.ry * cam.z;
    ctx.beginPath(); ctx.ellipse(cxs, base, rx, ry, 0, Math.PI, 0);
    ctx.fillStyle = 'rgba(214,201,163,0.08)'; ctx.fill();
    ctx.strokeStyle = 'rgba(230,215,176,0.55)'; ctx.lineWidth = Math.max(1, 6 * cam.z); ctx.stroke();
    ctx.strokeStyle = 'rgba(230,215,176,0.16)'; ctx.lineWidth = Math.max(1, 3 * cam.z);
    for (let i = 1; i < 7; i++) {
      const a = Math.PI + (Math.PI * i) / 7;
      ctx.beginPath(); ctx.moveTo(cxs, base);
      ctx.lineTo(cxs + Math.cos(a) * rx, base + Math.sin(a) * ry); ctx.stroke();
    }
    ctx.beginPath(); ctx.ellipse(cxs, base, rx * 0.62, ry * 0.62, 0, Math.PI, 0); ctx.stroke();
  }
  // 유인 등불: 탑 지붕에서 심연 쪽으로 뻗은 철골 끝의 등불 하나(M5 그림 그대로). 랜턴 하나 = 주색 하나
  function drawLure(t) {
    const lu = MAP().lure; if (!lu || layerReady('shell')) return;
    ctx.strokeStyle = '#3a2416'; ctx.lineWidth = Math.max(1.5, 14 * cam.z); ctx.lineJoin = 'round';
    ctx.beginPath(); lu.girder.forEach(([x, y], i) => (i ? ctx.lineTo(sx(x), sy(y)) : ctx.moveTo(sx(x), sy(y)))); ctx.stroke();
    const [gx, gy] = lu.girder[lu.girder.length - 1], sway = Math.sin(t / 2200) * 18;
    ctx.strokeStyle = 'rgba(200,190,160,0.45)'; ctx.lineWidth = Math.max(1, 2 * cam.z);
    ctx.beginPath(); ctx.moveTo(sx(gx), sy(gy)); ctx.lineTo(sx(lu.x + sway), sy(lu.y)); ctx.stroke();
    const px = sx(lu.x + sway), py = sy(lu.y), r = 22 * cam.z;
    const g = ctx.createRadialGradient(px, py, 0, px, py, r * 9);
    g.addColorStop(0, 'rgba(240,176,85,0.45)'); g.addColorStop(1, 'rgba(240,176,85,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(px, py, r * 9, 0, 6.2832); ctx.fill();
    ctx.fillStyle = '#f0b055'; ctx.beginPath(); ctx.arc(px, py, Math.max(2, r), 0, 6.2832); ctx.fill();
  }
  // 승강로: 레일 두 줄 + 정류장 문틀. 칸은 drawCars 에서
  function drawShafts() {
    if (drawLayer('elevator')) return;
    const L = MAP();
    L.shafts.forEach(s => {
      const x0 = sx(s.x), w = s.w * cam.z, y0 = sy(L.dome.floor_y - 230), y1 = sy(s.bottom);
      ctx.fillStyle = 'rgba(10,9,7,0.88)'; ctx.fillRect(x0, y0, w, y1 - y0);
      ctx.strokeStyle = 'rgba(150,120,70,0.55)'; ctx.lineWidth = Math.max(1, 5 * cam.z);
      ctx.beginPath(); ctx.moveTo(x0 + 10 * cam.z, y0); ctx.lineTo(x0 + 10 * cam.z, y1);
      ctx.moveTo(x0 + w - 10 * cam.z, y0); ctx.lineTo(x0 + w - 10 * cam.z, y1); ctx.stroke();
      ctx.strokeStyle = 'rgba(150,120,70,0.18)'; ctx.lineWidth = Math.max(1, 2 * cam.z);
      for (let y = L.dome.floor_y - 200; y < s.bottom; y += 60) {
        const yy = sy(y); if (yy < -4 || yy > view.h + 4) continue;
        ctx.beginPath(); ctx.moveTo(x0 + 10 * cam.z, yy); ctx.lineTo(x0 + w - 10 * cam.z, yy + 30 * cam.z); ctx.stroke();
      }
      Object.values(s.doors).forEach(dy => {                     // 정류장 문턱
        ctx.fillStyle = 'rgba(240,176,85,0.30)'; ctx.fillRect(x0, sy(dy) - 2 * cam.z, w, Math.max(1, 5 * cam.z));
      });
    });
  }
  // 앞 겹: 해초 몇 줄(탑 발치·절벽 턱)
  const KELP = [[1090, 1300], [1110, 2100], [3540, 1700], [3560, 2500], [700, 760], [3500, 1000]];
  function drawFront(t) {
    if (drawLayer('front')) return;
    ctx.strokeStyle = 'rgba(40,70,40,0.75)'; ctx.lineCap = 'round';
    KELP.forEach(([x, y], i) => {
      const h = 260 + (i % 3) * 90;
      if (sx(x) < -80 || sx(x) > view.w + 80 || sy(y) < -40 || sy(y - h) > view.h) return;
      ctx.lineWidth = Math.max(1, 10 * cam.z);
      ctx.beginPath(); ctx.moveTo(sx(x), sy(y));
      ctx.quadraticCurveTo(sx(x + Math.sin(t / 1800 + i) * 50), sy(y - h * 0.5), sx(x + Math.sin(t / 1500 + i) * 70), sy(y - h));
      ctx.stroke();
    });
    ctx.lineCap = 'butt';
  }

  // ── 방 플레이트(배경 S8-C). 칸 = outer_rect 564×317 을 1:1 로 자른 것(키우지도 줄이지도 않는다) ──
  // 플레이트가 있는 방 여섯. 나머지 방은 같은 칸에 평면 채색(FLAT_FOLK)으로 그린다
  const PLATE_OF = { quarters: 'quarters', storage: 'storage', pantry: 'storage', workshop: 'workshop',
                     infirmary: 'infirmary', generator: 'power', power: 'power', greenhouse: 'greenhouse' };
  const plateImgs = {};
  function plateImg(file) {
    let p = plateImgs[file];
    if (!p) { p = plateImgs[file] = { img: new Image(), ok: false }; p.img.onload = () => { p.ok = p.img.naturalWidth > 0; }; p.img.src = '/static/art/plates/' + file; }
    return p.ok ? p.img : null;
  }
  const ovImgs = {};
  function overlayImg(id) {                          // 배경 S12-A 칸 덧그림(cell_plan·cell_flood)
    const o = MAP().overlays && MAP().overlays[id]; if (!o) return null;
    let p = ovImgs[id];
    if (!p) { p = ovImgs[id] = { img: new Image(), ok: false }; p.img.onload = () => { p.ok = p.img.naturalWidth > 0; }; p.img.src = window.ArkMap.dir + o.file; }
    return p.ok ? p.img : null;
  }
  function drawPlate(file, x, y, w, h, alpha) {
    const img = plateImg(file); if (!img) return false;
    const r = (MAP().plate && MAP().plate.src_rect) || [54, 33, 564, 317];
    if (alpha != null) { ctx.save(); ctx.globalAlpha = alpha; }
    ctx.drawImage(img, r[0], r[1], r[2], r[3], x, y, w, h);
    if (alpha != null) ctx.restore();
    return true;
  }

  // 서버 칸이 없는 맵 칸: 탑의 오른쪽 열·맨 아래층 = 물이 찬 칸, 바위 칸 = 아직 파지 못한 바위.
  // 빈 바닥이 아니라 '되찾을 곳'으로 보인다(REF_CROSS_SECTION §1 빈 방 없음). + 는 없다 — 지금은 못 짓는다
  function drawSealed(c, t) {
    const x = sx(c.x), y = sy(c.y), w = c.w * cam.z, h = c.h * cam.z;
    if (x > view.w + 40 || x + w < -40 || y > view.h + 40 || y + h < -40) return;
    if (c.kind === 'rock') {
      if (!layerReady('mid')) { ctx.fillStyle = '#1a130c'; ctx.fillRect(x, y, w, h); }
      ctx.strokeStyle = 'rgba(90,67,32,0.55)'; ctx.lineWidth = Math.max(1, 4 * cam.z); ctx.setLineDash([10 * cam.z, 8 * cam.z]);
      ctx.strokeRect(x, y, w, h); ctx.setLineDash([]);
    } else {
      const fl = overlayImg('cell_flood');
      if (fl) { ctx.fillStyle = 'rgba(3,14,19,0.45)'; ctx.fillRect(x, y, w, h); ctx.drawImage(fl, x, y, w, h); }
      else {
        if (!drawPlate('room_flood.png', x, y, w, h, 0.9)) { ctx.fillStyle = '#082028'; ctx.fillRect(x, y, w, h); }
        ctx.fillStyle = 'rgba(3,14,19,0.55)'; ctx.fillRect(x, y, w, h);
      }
      ctx.strokeStyle = 'rgba(20,17,12,0.9)'; ctx.lineWidth = Math.max(1.5, 5 * cam.z); ctx.strokeRect(x, y, w, h);
    }
    if (cam.z > 0.3) {
      ctx.font = (11 * Math.min(1.6, cam.z * 2)) + 'px "Noto Sans KR",sans-serif';
      ctx.fillStyle = c.kind === 'rock' ? 'rgba(170,140,100,0.55)' : 'rgba(140,190,195,0.5)';
      ctx.textBaseline = 'middle';
      ctx.fillText(c.kind === 'rock' ? '바위 — 아직 파지 못했다' : '물이 찬 칸 — 아직 되찾지 못했다', x + 14 * cam.z, y + 24 * cam.z);
      ctx.textBaseline = 'alphabetic';
    }
    hits.push({ kind: 'sealed', cell: c, x, y, w, h });
  }
  function drawSealedAll(t) {
    const L = MAP(), used = {};
    for (let s = 0; s < slots; s++) { const c = cellOf(s); if (c) used[c.id] = true; }
    L.cells.forEach(c => { if (!used[c.id]) drawSealed(c, t); });
    L.rock.forEach(c => drawSealed(c, t));
  }

  function roomColor(id) { return ROOM_COLOR[id] || ROOM_COLOR._default; }
  const lightOf = (slot) => !cb || !cb.lights || cb.lights[String(slot)] !== false;
  const capOf = (slot) => (cb && cb.caps && cb.caps[String(slot)]) || 0;

  function drawRoom(slot, room, people, t) {
    const r = rectOf(slot);
    if (!r) return;                                   // 돔 상부(slot 0·1) — 맵에서는 홀이다
    const x = sx(r.x), y = sy(r.y), w = r.w * cam.z, h = r.h * cam.z;
    if (x > view.w + 40 || x + w < -40 || y > view.h + 40 || y + h < -40) return;
    const picked = carry || dragging;                 // 사람을 들고 있을 때는 놓을 자리를 밝힌다
    const target = raidTargetSlot();
    const ix = x, iy = y, iw = w, ih = h;

    if (!room) {   // 빈 자리 — 여기로 자란다(성장 방향은 아래). 탭하면 물을 뺀다(/api/ark/build)
      const pl = overlayImg('cell_plan');
      if (pl) ctx.drawImage(pl, x, y, w, h); else { ctx.fillStyle = 'rgba(6,18,22,0.72)'; ctx.fillRect(x, y, w, h); }
      ctx.save();
      ctx.setLineDash([12 * cam.z, 10 * cam.z]);
      ctx.strokeStyle = sel && sel.slot === slot ? 'rgba(240,176,85,0.9)' : 'rgba(190,225,222,0.38)';
      ctx.lineWidth = Math.max(1, 4 * cam.z);
      ctx.strokeRect(x + 16 * cam.z, y + 16 * cam.z, w - 32 * cam.z, h - 32 * cam.z);
      ctx.restore();
      ctx.fillStyle = 'rgba(190,225,222,0.55)';
      ctx.font = Math.max(14, 64 * cam.z) + 'px "Noto Sans KR",sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('+', x + w / 2, y + h / 2);
      ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
      return;
    }

    const col = roomColor(room.id);
    if (room.flooded) {
      // 잃은 방은 사라지지 않고 **물이 찬 채로 영구히 남는다**(§3-6 흔적). 소리도 없다
      const pf = PLATE_OF[room.id];
      if (!(pf && drawPlate('room_plate_' + pf + '_dark.png', ix, iy, iw, ih, 0.5))) { ctx.fillStyle = '#082028'; ctx.fillRect(ix, iy, iw, ih); }
      const fo = overlayImg('cell_flood');
      if (fo) ctx.drawImage(fo, ix, iy, iw, ih);
      else if (!drawPlate('room_flood.png', ix, iy, iw, ih)) { ctx.fillStyle = 'rgba(8,32,40,0.8)'; ctx.fillRect(ix, iy, iw, ih); }
      ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
      ctx.strokeStyle = 'rgba(120,180,185,0.10)'; ctx.lineWidth = 1;
      for (let gy = iy + 14 * cam.z; gy < iy + ih; gy += 22 * cam.z) {     // 가라앉은 물의 결
        ctx.beginPath(); ctx.moveTo(ix, gy + Math.sin(t / 1800 + gy) * 1.4); ctx.lineTo(ix + iw, gy); ctx.stroke();
      }
      ctx.restore();
      ctx.strokeStyle = '#14110c'; ctx.lineWidth = Math.max(1.5, 6 * cam.z);
      ctx.strokeRect(ix, iy, iw, ih);
      if (cam.z > 0.2) {
        ctx.font = (11 * Math.min(1.6, cam.z * 2)) + 'px "Noto Sans KR",sans-serif';
        ctx.fillStyle = 'rgba(140,190,195,0.7)'; ctx.textBaseline = 'middle';
        ctx.fillText('물이 찼다', ix + 14 * cam.z, iy + 24 * cam.z);
        ctx.textBaseline = 'alphabetic';
      }
      return;
    }

    const lit = lightOf(slot);
    const pf = PLATE_OF[room.id];
    // 플레이트가 있는 방은 그림으로(켜짐 = lit, 꺼짐 = dark), 없는 방은 평면 채색 + 음영 1~2단(FLAT_FOLK §1-3)
    if (!(pf && drawPlate('room_plate_' + pf + (lit ? '_lit' : '_dark') + '.png', ix, iy, iw, ih))) {
      const p = 34 * cam.z, fx = ix + p, fy = iy + p, fw = iw - 2 * p, fh = ih - p - 30 * cam.z;
      ctx.fillStyle = '#14110c'; ctx.fillRect(ix, iy, iw, ih);
      ctx.save();
      if (!lit) ctx.globalAlpha = 0.34;
      ctx.fillStyle = col.base; ctx.fillRect(fx, fy, fw, fh);
      ctx.fillStyle = col.shade; ctx.fillRect(fx, fy, fw, fh * 0.26);
      ctx.fillStyle = col.floor; ctx.fillRect(fx, fy + fh * 0.80, fw, fh * 0.20);
      ctx.beginPath(); ctx.rect(fx, fy, fw, fh); ctx.clip();
      ctx.strokeStyle = 'rgba(20,17,12,0.13)'; ctx.lineWidth = Math.max(1, 2 * cam.z);
      for (let gx = fx + 40 * cam.z; gx < fx + fw; gx += 54 * cam.z) {
        ctx.beginPath(); ctx.moveTo(gx, fy + fh * 0.26); ctx.lineTo(gx, fy + fh * 0.80); ctx.stroke();
      }
      ctx.restore();
      if (!lit) { ctx.fillStyle = 'rgba(4,16,22,0.55)'; ctx.fillRect(fx, fy, fw, fh); }
    }
    if (lit) {   // 랜턴 하나 = 주색 하나 — 칸 위쪽 등 자리에서 번진다
      const c = r.cell, lp = c.lamp || [c.x + c.w / 2, c.y + 77];
      ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
      const lx = sx(lp[0]), ly = sy(lp[1]);
      const lg = ctx.createRadialGradient(lx, ly, 0, lx, ly, ih * 0.9);
      lg.addColorStop(0, 'rgba(240,176,85,0.22)'); lg.addColorStop(1, 'rgba(240,176,85,0)');
      ctx.fillStyle = lg; ctx.fillRect(ix, iy, iw, ih);
      ctx.restore();
    }

    if (room.cracked) drawCrack(ix, iy, iw, ih, slot);

    // 두꺼운 검은 테두리: 방을 각각 "불 켜진 상자"로 읽히게 한다(§1-3)
    let edge = '#14110c', ew = 6;
    if (sel && sel.slot === slot) { edge = '#f0b055'; ew = 9; }
    if (target === slot) { edge = '#b03a24'; ew = 9; }                    // 노려지는 방
    if (picked) {                                                         // 놓을 수 있는 자리
      const full = (people || []).length >= capOf(slot);
      edge = full ? '#6b3b33' : '#8fbf7a'; ew = 9;
    }
    ctx.strokeStyle = edge;
    ctx.lineWidth = Math.max(1.5, ew * cam.z);
    ctx.strokeRect(ix, iy, iw, ih);

    drawShelf(slot, ix, iy, iw, ih, lit);
    drawInstalled(slot, ix, iy, iw, ih);
    drawPeople(people, r, t, slot);

    if (cam.z > 0.16) {
      const nm = (catalog[room.id] && catalog[room.id].name) || room.id;
      const cap = capOf(slot), n = (people || []).length;
      const label = nm + (cap ? '  ' + n + '/' + cap : '');
      const fz = Math.max(10.5, Math.min(15, 26 * cam.z));
      ctx.font = fz + 'px "Noto Sans KR",sans-serif';
      ctx.fillStyle = 'rgba(20,17,12,0.78)';
      const tw = ctx.measureText(label).width + 10;
      ctx.fillRect(ix + 4, iy + 4, tw, fz + 6);
      ctx.fillStyle = lit ? '#e6d7b0' : '#93a6a3';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, ix + 9, iy + 7 + fz / 2);
      ctx.textBaseline = 'alphabetic';
      if (!lit) {
        ctx.fillStyle = 'rgba(147,166,163,0.85)';
        ctx.fillText('불 꺼짐', ix + 9, iy + ih - 8);
      }
    }
  }

  function drawCrack(ix, iy, iw, ih, slot) {
    // 막아도 긁힌 자국이 남는다(§3-6). 금은 지워지지 않고 봉합 패치로만 덮인다. 배경의 금 그림이 있으면 그것을
    if (drawPlate('damage_crack' + (1 + (slot % 3)) + '.png', ix, iy, iw, ih)) return;
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
    if (!rows.length || cam.z < 0.15) return;
    const mark = { shutter: '▤', lure_lamp: '✦', hush: '◍', long_net: '╳', brace: '═' };
    const fz = Math.max(11, Math.min(18, 30 * cam.z));
    ctx.font = fz + 'px "Noto Sans KR",sans-serif';
    ctx.fillStyle = 'rgba(240,176,85,0.95)';
    rows.forEach((row, i) => {
      ctx.fillText(mark[row.id] || '•', ix + iw - (fz + 6) * (i + 1), iy + ih - 8);
    });
  }

  // ── 자세(클립). 정본은 front/p2/meta.json 의 rows·frames·anim_seconds(DECISIONS 2026-10-01 자세 정본) ──
  // 캐릭터 담당이 elevator_wait·elevator_ride·work_<방> 행을 만들고 있다. meta 에 생기고 **시트에도 그 행이
  // 실제로 있으면** 자동으로 쓰고, 없으면 사슬을 따라 내려가 idle 로 그린다. 코드 수정 없이 켜진다.
  let CLIPS = { rows: { idle: 0 }, frames: { idle: 2 }, anim_seconds: { idle: 1.24 } };
  fetch('/static/art/chars/front/p2/meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    if (j && j.rows) CLIPS = { rows: j.rows, frames: j.frames || {}, anim_seconds: j.anim_seconds || {} };
  }).catch(() => {});
  const POSE_CHAIN = {
    walk: ['walk'], elevator_wait: ['elevator_wait'], elevator_ride: ['elevator_ride', 'elevator_wait'],
    hurt: ['hurt'], rest: [], idle: [],
  };
  function clipFor(s, pose, roomId) {
    const cand = (pose === 'work' ? ['work_' + roomId, 'work'] : (POSE_CHAIN[pose] || [])).concat('idle');
    for (const c of cand) {
      const row = CLIPS.rows[c];
      if (row == null) continue;
      if ((row + 1) * s.spec.cell > s.img.naturalHeight) continue;      // meta 는 새것, 시트는 아직 옛것
      const fr = Math.max(1, Math.min(s.spec.cols, CLIPS.frames[c] || 1));
      return { name: c, row, frames: fr, ms: ((CLIPS.anim_seconds[c] || 1) * 1000) / fr };
    }
    return { name: 'idle', row: 0, frames: 2, ms: 620 };
  }
  const usedClips = {};                               // 검수용: 지금까지 실제로 그린 클립 이름

  function drawPerson(p, px, floorY, t, i, scale, lit, pose, roomId) {
    const k = (scale == null ? 1 : scale);
    const moving = pose === 'walk' || pose === 'elevator_ride';
    const bob = moving ? 0 : Math.sin(t / 700 + i * 1.7) * 0.8 * cam.z;
    const s = sprite(p.role);
    if (s) {
      const sp = s.spec;
      // 도트는 **정수 배율**로만 키운다(2.5D 조건 ①). 렌더 시트는 기존대로 연속 배율
      const want = (TARGET_PPM * cam.z * k) / sp.ppm;
      // 아주 멀리서(폰 가로 맞춤 등) ×1 이 방보다 크면 그때만 소수 배율로 줄인다 — 사람이 방보다 커 보이면 안 된다
      const z = sp.pixel ? (want >= 0.75 ? Math.max(1, Math.round(want)) : want) : want;
      const cw = sp.cell * z, base = sp.baseline * z;
      const clip = sp.pixel ? clipFor(s, pose || 'idle', roomId) : { name: 'idle', row: sp.idle, frames: sp.frames, ms: 170 };
      usedClips[clip.name] = (usedClips[clip.name] || 0) + 1;
      const frame = Math.floor(t / clip.ms + i) % clip.frames;
      try {
        const sheet = sp.pixel ? tintedSheet(s, p.role, lit === false ? TINT_DARK : TINT_LIT) : s.img;
        const sm = ctx.imageSmoothingEnabled;
        if (sp.pixel) ctx.imageSmoothingEnabled = false;
        // 2.5D 조건 ③ — 발밑 접지 그림자. 없으면 떠 있는 것처럼 보인다
        ctx.fillStyle = 'rgba(12,10,8,0.42)';
        ctx.beginPath(); ctx.ellipse(px, floorY, cw * 0.22, cw * 0.055, 0, 0, 6.2832); ctx.fill();
        const cell = sp.pixel ? clip.row * sp.cols + frame : sp.idle * sp.cols + frame;
        ctx.drawImage(sheet, (cell % sp.cols) * sp.cell, Math.floor(cell / sp.cols) * sp.cell, sp.cell, sp.cell,
                      px - cw / 2, floorY - base + bob, cw, cw);
        ctx.imageSmoothingEnabled = sm;
        if (p.injured) { ctx.fillStyle = 'rgba(140,59,46,0.5)'; ctx.fillRect(px - 13 * cam.z, floorY - 101 * cam.z, 26 * cam.z, 9 * cam.z); }
        return { w: cw * 0.42, h: base * 0.78 };
      } catch (e) { /* 스프라이트가 아직 덜 왔다 — 아래 색 사각형으로 */ }
    }
    const hgt = (p.role === 'kid' ? 66 : 88) * cam.z * k, wid = 29 * cam.z * k;
    ctx.fillStyle = ROLE_COLOR[p.role] || '#d8c9a3';
    ctx.fillRect(px - wid / 2, floorY - hgt + bob, wid, hgt);
    ctx.fillStyle = '#14110c';
    ctx.fillRect(px - wid / 2, floorY - hgt + bob, wid, Math.max(1, 3 * cam.z));
    if (p.injured) { ctx.fillStyle = '#8c3b2e'; ctx.fillRect(px - wid / 2, floorY - hgt * 0.55 + bob, wid, Math.max(1, 3 * cam.z)); }
    return { w: wid, h: hgt };
  }

  // 방 안의 삶: 그 방의 일을 하다가 10~20초에 한 번 쉬거나 몇 걸음 옮긴다(movement.js roomLife).
  // 막 도착한 사람은 1.2초에 걸쳐 제 자리로 걸어 들어간다 — 도착 순간 순간이동하지 않게
  function lifeAt(p, slot, t, step) {
    const now = t / 1000, room = (ark.rooms || []).find(r => r.slot === slot);
    let L = window.ArkMove ? ArkMove.roomLife(p.id, now) : { pose: 'work', dx: 0 };
    const since = now - traffic.arrivedAt(p.id);
    const ramp = since < 0 ? 0 : Math.min(1, since / 1.2);
    const spread = Math.min(step * 0.3, 48 * cam.z);
    let pose = L.pose;
    if (ramp < 1 && Math.abs(L.dx) * spread > 2) pose = 'walk';
    if (!lightOf(slot)) pose = 'idle';                         // 불 꺼진 방에서는 손을 놓고 기다린다
    if (p.injured) pose = 'hurt';
    return { pose, off: L.dx * spread * ramp, room: room ? room.id : '' };
  }
  function lifeOffsetM(id, slot, i, n, t) {                    // 이동 출발점에 같은 오프셋을 쓴다(세계 m)
    const r = rectOf(slot); if (!r) return 0;
    const step = (r.stand[1] - r.stand[0]) / (n + 1);
    const L = window.ArkMove ? ArkMove.roomLife(id, t / 1000) : { dx: 0 };
    return (L.dx * Math.min(step * 0.3, 48)) / PX_PER_M;
  }

  function drawPeople(people, r, t, slot) {
    if (!people || !people.length) return;
    const floorY = sy(r.floorY);                             // 플레이트 발선(floor_in_cell 282)
    const step = (r.stand[1] - r.stand[0]) * cam.z / (people.length + 1);
    people.forEach((p, i) => {
      if (dragging && dragging.id === p.id) return;          // 들고 있는 사람은 손끝에 그린다
      if (movingNow[p.id]) return;                           // 아직 오는 중 — 이동 층에서 그린다
      const life = lifeAt(p, slot, t, step);
      const px = sx(standX(r, i, people.length)) + life.off;
      const box = drawPerson(p, px, floorY, t, i, 1, lightOf(slot), life.pose, life.room);
      if (carry && carry.id === p.id) {                      // 집어 든 표시
        ctx.strokeStyle = '#f0b055'; ctx.lineWidth = Math.max(1, 2 * cam.z);
        ctx.strokeRect(px - box.w / 2 - 3, floorY - box.h - 6, box.w + 6, box.h + 10);
      }
      hits.push({ kind: 'person', id: p.id, name: p.name, role: p.role, from: slot,
                  x: px - box.w / 2 - 6, y: floorY - box.h - 8, w: box.w + 12, h: box.h + 14 });
    });
  }

  const labelFont = (base) => Math.max(10.5, Math.min(15, base * cam.z * 2.2));
  function drawHall(t) {
    // 홀: 배치되지 않은 사람이 모이는 돔 안. 여기도 **빈 방이 아니다**
    const h = hallRect();
    const x = sx(h.x), y = sy(h.y), w = h.w * cam.z, hh = h.h * cam.z;
    const list = (ark.residents_list || []).filter(r =>
      (!cb || cb.stations[r.id] === undefined) && !(cb && cb.outside.indexOf(r.id) >= 0));
    const picked = carry || dragging;
    // 돔 바닥의 따뜻한 빛(홀 = 공용의 불 하나)
    const lg = ctx.createRadialGradient(x + w / 2, y + hh * 0.4, 0, x + w / 2, y + hh * 0.4, w * 0.6);
    lg.addColorStop(0, 'rgba(240,176,85,' + (cb && cb.power_on ? 0.22 : 0.06) + ')'); lg.addColorStop(1, 'rgba(240,176,85,0)');
    ctx.fillStyle = lg; ctx.fillRect(x - w * 0.1, y - hh * 0.6, w * 1.2, hh * 1.6);
    ctx.save();
    ctx.fillStyle = 'rgba(58,48,24,0.30)'; ctx.fillRect(x, y, w, hh);
    ctx.setLineDash([10 * cam.z, 10 * cam.z]);
    ctx.strokeStyle = picked ? 'rgba(143,191,122,0.85)' : 'rgba(230,215,176,0.22)';
    ctx.lineWidth = Math.max(1, 4 * cam.z);
    ctx.strokeRect(x, y, w, hh);
    ctx.restore();
    if (cam.z > 0.12) {
      ctx.font = labelFont(10.5) + 'px "Noto Sans KR",sans-serif';
      ctx.fillStyle = 'rgba(230,215,176,0.62)';
      ctx.fillText('홀 · 배치 안 된 사람 ' + list.length, x + 8, y + 16);
    }
    const floorY = sy(MAP().dome.floor_y), step = w / (list.length + 1);
    list.forEach((p, i) => {
      if (dragging && dragging.id === p.id) return;
      if (movingNow[p.id]) return;
      const px = x + step * (i + 1);
      const box = drawPerson(p, px, floorY, t, i, 1, !!(cb && cb.power_on), 'idle');
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
    // 밖에 나가 있는 사람(탑 오른 외벽 바깥, 심연 쪽). 손톱 무리의 날에만 보이고, 들이면 사라진다
    const ids = (cb && cb.outside) || [];
    if (!ids.length) return;
    const o = outsideRect();
    const x = sx(o.x), y = sy(o.y), w = o.w * cam.z, hh = o.h * cam.z;
    ctx.save();
    ctx.setLineDash([8 * cam.z, 8 * cam.z]);
    ctx.strokeStyle = 'rgba(176,58,36,0.75)'; ctx.lineWidth = Math.max(1, 4 * cam.z);
    ctx.strokeRect(x, y, w, hh); ctx.restore();
    ctx.font = labelFont(10.5) + 'px "Noto Sans KR",sans-serif';
    ctx.fillStyle = 'rgba(224,150,130,0.9)';
    ctx.fillText('밖 · ' + ids.length + '명', x + 6, y + 16);
    const list = (ark.residents_list || []).filter(r => ids.indexOf(r.id) >= 0);
    const floorY = sy(o.y + o.h), step = w / (list.length + 1);
    list.forEach((p, i) => { if (!movingNow[p.id]) drawPerson(p, x + step * (i + 1), floorY, t, i, 1, false, 'idle'); });
  }

  // ── 이동 중인 사람과 엘리베이터 칸 (S11-C → S12-B: M5 승강로 A·B) ─────────────────
  // 칸 그림은 배경의 elevator_car.png(138×190, 아래 가운데 = 정류장 문턱)가 있으면 그것을, 없으면 틀을 그린다.
  // 칸은 움직이는 사람보다 **먼저** 그린다 — 사람이 칸 안에 서 있는 것처럼 보인다
  const carImg = { img: new Image(), ok: false };
  function loadCar() {
    const f = (MAP().car && MAP().car.sprite) || 'elevator_car.png';
    carImg.img.onload = () => { carImg.ok = carImg.img.naturalWidth > 0; };
    carImg.img.onerror = () => { carImg.ok = false; };
    carImg.img.src = window.ArkMap.dir + f;
  }
  function drawCars(t) {
    const g = traffic.graph(), C = MAP().car || { w: 138, h: 190 };
    traffic.cars().forEach(id => {
      const f = traffic.car(id, t / 1000), sh = g.byId[id];
      if (f == null || !sh) return;
      const w = MOVE_ADAPTER.toWorld(f, sh.x);
      const ax = C.anchor ? C.anchor[0] : C.w / 2, ay = C.anchor ? C.anchor[1] : C.h;   // 아래 가운데 = 정류장 바닥
      const x0 = sx(w.x - ax), y0 = sy(w.y - ay), cw = C.w * cam.z, ch = C.h * cam.z;
      if (y0 + ch < -20 || y0 > view.h + 20) return;
      ctx.strokeStyle = 'rgba(230,215,176,0.35)'; ctx.lineWidth = Math.max(1, 2 * cam.z);   // 줄 — 위로 이어진다
      ctx.beginPath(); ctx.moveTo(x0 + cw / 2, y0); ctx.lineTo(x0 + cw / 2, sy(MAP().dome.floor_y - 230)); ctx.stroke();
      if (carImg.ok) { ctx.drawImage(carImg.img, x0, y0, cw, ch); return; }
      ctx.fillStyle = 'rgba(28,22,14,0.82)'; ctx.fillRect(x0, y0, cw, ch);
      const lg = ctx.createLinearGradient(0, y0, 0, y0 + ch);
      lg.addColorStop(0, 'rgba(240,176,85,0.28)'); lg.addColorStop(1, 'rgba(240,176,85,0.04)');
      ctx.fillStyle = lg; ctx.fillRect(x0, y0, cw, ch);
      ctx.strokeStyle = 'rgba(240,176,85,0.75)'; ctx.lineWidth = Math.max(1, 4 * cam.z);
      ctx.strokeRect(x0, y0, cw, ch);
      ctx.strokeStyle = 'rgba(240,176,85,0.28)'; ctx.lineWidth = Math.max(1, 2 * cam.z);
      for (let k = 1; k < 4; k++) { const xx = x0 + cw * k / 4; ctx.beginPath(); ctx.moveTo(xx, y0 + 6 * cam.z); ctx.lineTo(xx, y0 + ch * 0.55); ctx.stroke(); }
      ctx.fillStyle = '#f0b055'; ctx.beginPath(); ctx.arc(x0 + cw / 2, y0 + 12 * cam.z, Math.max(1.5, 5 * cam.z), 0, 6.2832); ctx.fill();
    });
  }
  function drawMovers(t) {
    const now = t / 1000, ids = Object.keys(movingNow);
    if (!ids.length) return;
    const byId = {}; (ark.residents_list || []).forEach(p => { byId[p.id] = p; });
    ids.forEach((id, i) => {
      const p = byId[id], m = traffic.at(id, now);
      if (!p || !m || (dragging && dragging.id === id)) return;
      const w = MOVE_ADAPTER.toWorld(m.floor, m.x);
      const k = 1;
      drawPerson(p, sx(w.x), sy(w.y), t, i, k, !!(cb && cb.power_on), m.pose);
    });
  }
  // 드래그 중: 손끝 아래 방에서 빛나는 능력치를 숫자로 띄운다(배치할 때 강조 — RESIDENT_STATS §5, 숫자로 2026-10-03)
  function drawDropStat() {
    const s = slotAt(pointer.x, pointer.y);
    if (s == null || !dragging || !dragging.stats) return;
    const ko = (ark.stats_meta || {}).ko || STAT_KO_DEF;
    const ks = goodStats(s);
    if (!ks.length) return;
    const label = ks.map(k => (ko[k] || k) + ' ' + (dragging.stats[k] || 0)).join('  ');
    ctx.font = 'bold 13px "Noto Sans KR",sans-serif';
    const tw = ctx.measureText(label).width + 14, x = pointer.x + 16, y = pointer.y - 36;
    ctx.fillStyle = 'rgba(20,17,12,0.88)'; ctx.fillRect(x, y, tw, 22);
    ctx.strokeStyle = '#f0b055'; ctx.lineWidth = 1.5; ctx.strokeRect(x, y, tw, 22);
    ctx.fillStyle = '#f0b055'; ctx.textBaseline = 'middle'; ctx.fillText(label, x + 7, y + 11);
    ctx.textBaseline = 'alphabetic';
  }

  // ── 실루엣: 열린 심연(오른쪽)에서 그림자가 **그 방 쪽으로** 다가온다 (§3-2, M5: 위협은 한쪽에서만 온다) ──
  // 그림은 배경의 static/art/threats(990×495, 82.5 px/m — 세계와 같은 자). 그림의 +x 가 거점 쪽이라 좌우를 뒤집는다
  // (거점이 생물의 왼쪽에 있다). far → near 는 다가올수록 알파로 바뀐다. over_room(덮개·큰 입·그늘)은 방 위에 얹는다.
  let silDbg = null;
  let approach = 0;                                   // 0 → 1. 다 와도 접촉하지 않고 창 앞에서 멈춘다
  let threatMeta = {};                                // creature_id → {files, over_room, body}
  const threatImgs = {};
  fetch('/static/art/threats/threats_meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    ((j && j.threats) || []).forEach(x => { threatMeta[x.creature_id || x.id] = x; });
  }).catch(() => { threatMeta = {}; });
  function threatImg(file) {
    let p = threatImgs[file];
    if (!p) { p = threatImgs[file] = { img: new Image(), ok: false }; p.img.onload = () => { p.ok = p.img.naturalWidth > 0; }; p.img.src = '/static/art/threats/' + file; }
    return p.ok ? p.img : null;
  }
  function silhouetteState(dt) {
    const raid = cb && cb.raid;
    if (!raid || raid.stage !== 'silhouette' || raid.target_slot == null) { approach = 0; return null; }
    approach = Math.min(1, approach + dt / 22000);    // 약 22초에 걸쳐 천천히. 놀래키지 않는다(§6-2)
    const r = rectOf(raid.target_slot);              // 다 와도 창 앞에서 **멈춰 선다** — 접촉은 플레이어가 누를 때만
    if (!r) return null;
    return { raid, r, meta: threatMeta[raid.creature.id] || null };
  }
  // 몸이 있는 것: 심연 물속(탑 앞 겹보다 뒤)에서 다가온다
  function drawSilhouette(t, dt) {
    const S = silhouetteState(dt); if (!S) return;
    const { raid, r, meta } = S, L = MAP();
    if (meta && meta.over_room) return;               // 방 위에 얹는 것은 drawOverRoom 에서
    const tx = L.tower.x1 + 260, ox = L.tower.x1 + 1000;          // 외벽 창 바로 앞 ← 심연 안쪽(처음부터 화면 안에서 보인다)
    const e = 1 - Math.pow(1 - approach, 2);
    const wx = ox + (tx - ox) * e;
    silDbg = { approach, wx, id: raid.creature.id, meta: !!meta };
    const wy = r.y + r.h * 0.5 + Math.sin(t / 1400) * 18;
    const alpha = 0.30 + 0.55 * approach;
    const far = meta && threatImg(meta.files.far), near = meta && threatImg(meta.files.near);
    if (far || near) {
      const w = 990 * cam.z, h = 495 * cam.z, px = sx(wx), py = sy(wy);
      ctx.save();
      ctx.translate(px, py); ctx.scale(-1, 1);        // +x 가 거점 쪽 → 왼쪽을 보게 뒤집는다
      // 검은 물에 검은 그림자는 안 보인다 — 가장자리에 물빛 한 겹(REF_CROSS_SECTION §3: 바깥의 것은 윤곽으로 먼저 온다)
      ctx.shadowColor = 'rgba(132,198,204,' + (0.35 + 0.4 * approach).toFixed(3) + ')';
      ctx.shadowBlur = Math.max(6, 22 * cam.z);
      if (far) { ctx.globalAlpha = alpha * (1 - approach); ctx.drawImage(far, -w / 2, -h / 2, w, h); }
      if (near) { ctx.globalAlpha = alpha * approach; ctx.drawImage(near, -w / 2, -h / 2, w, h); }
      ctx.restore();
    } else drawSilhouetteVector(t, raid, wx, wy, alpha);
    redWindow(r);
  }
  // 몸이 없는 것(덮개·큰 입·그늘): 방이 꺼지거나 흐려지는 것이 그 생물이다 — 방 위에 얹는다
  function drawOverRoom(t) {
    const raid = cb && cb.raid;
    if (!raid || raid.stage !== 'silhouette' || raid.target_slot == null) return;
    const meta = threatMeta[raid.creature.id], r = rectOf(raid.target_slot);
    if (!meta || !meta.over_room || !r) return;
    const far = threatImg(meta.files.far), near = threatImg(meta.files.near);
    const x = sx(r.x), y = sy(r.y), w = r.w * cam.z, h = r.h * cam.z;
    ctx.save(); ctx.beginPath(); ctx.rect(x - 40 * cam.z, y - 40 * cam.z, w + 80 * cam.z, h + 80 * cam.z); ctx.clip();
    const iw = 990 * cam.z, ih = 495 * cam.z, cx = x + w / 2, cy = y + h / 2;
    ctx.translate(cx, cy); ctx.scale(-1, 1);
    const a = 0.35 + 0.6 * approach;
    if (far) { ctx.globalAlpha = a * (1 - approach); ctx.drawImage(far, -iw / 2, -ih / 2, iw, ih); }
    if (near) { ctx.globalAlpha = a * approach; ctx.drawImage(near, -iw / 2, -ih / 2, iw, ih); }
    if (!far && !near) { ctx.globalAlpha = 0.25 + 0.5 * approach; ctx.fillStyle = '#01070b'; ctx.fillRect(-w / 2, -h / 2, w, h); }
    ctx.restore();
    redWindow(r);
  }
  function redWindow(r) {                             // 노려지는 창에 붉은 테두리가 번진다
    ctx.save();
    ctx.strokeStyle = 'rgba(176,58,36,' + (0.25 + 0.5 * approach).toFixed(3) + ')';
    ctx.lineWidth = Math.max(2, 12 * cam.z);
    ctx.strokeRect(sx(r.x) - 6 * cam.z, sy(r.y) - 6 * cam.z, (r.w + 12) * cam.z, (r.h + 12) * cam.z);
    ctx.restore();
  }
  // 그림이 없을 때의 윤곽(옛 S8·S10 벡터). 크기는 옛 자(37.4 px/m)로 적혀 있어 ×2.2
  function drawSilhouetteVector(t, raid, wx, wy, alpha) {
    const px = sx(wx), py = sy(wy), k = cam.z * 2.2, fromLeft = false;
    ctx.save();
    ctx.fillStyle = 'rgba(1,7,11,' + Math.min(0.92, alpha + 0.25).toFixed(3) + ')';
    ctx.strokeStyle = 'rgba(1,7,11,' + Math.min(0.92, alpha + 0.25).toFixed(3) + ')';
    ctx.shadowColor = 'rgba(132,198,204,' + (0.18 + 0.30 * approach).toFixed(3) + ')';
    ctx.shadowBlur = 10 * k;
    const c = raid.creature.id;
    if (c === 'longneck') {
      ctx.lineWidth = 15 * k; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(px + 210 * k, py + 80 * k);
      ctx.quadraticCurveTo(px + 90 * k, py - 60 * k, px, py); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(px, py, 26 * k, 15 * k, 0, 0, 6.2832); ctx.fill();
    } else if (c === 'swarm') {
      for (let i = 0; i < 46; i++) {
        const a = i * 2.39 + t / 1200, rr = (16 + (i % 7) * 13) * k;
        ctx.beginPath(); ctx.ellipse(px + Math.cos(a) * rr * 1.6 - 40 * k, py + Math.sin(a) * rr * 0.8, 5 * k, 2.6 * k, a, 0, 6.2832); ctx.fill();
      }
    } else if (c === 'warden') {
      ctx.beginPath(); ctx.ellipse(px + 170 * k, py, 190 * k, 112 * k, 0, 0, 6.2832); ctx.fill();
      ctx.lineWidth = 3 * k;
      ctx.beginPath(); ctx.ellipse(px, py, (30 + 70 * approach) * k, (22 + 50 * approach) * k, 0, 0, 6.2832); ctx.stroke();
    } else if (c === 'claws') {
      for (let i = 0; i < 70; i++) {
        ctx.beginPath(); ctx.arc(px + (i % 14) * 16 * k, py + 54 * k + Math.sin(i * 1.7 + t / 900) * 8 * k, 3.4 * k, 0, 6.2832); ctx.fill();
      }
    } else if (FISH[c]) {
      const f = FISH[c], dir = fromLeft ? -1 : 1, bx = px + dir * f.back * k;
      ctx.beginPath(); ctx.ellipse(bx, py + f.dy * k, f.rx * k, f.ry * k, 0, 0, 6.2832); ctx.fill();
      if (f.tail) {
        ctx.beginPath(); ctx.moveTo(bx + dir * f.rx * 0.8 * k, py + f.dy * k);
        ctx.lineTo(bx + dir * (f.rx + f.tail) * k, py + f.dy * k - f.tail * 0.6 * k);
        ctx.lineTo(bx + dir * (f.rx + f.tail) * k, py + f.dy * k + f.tail * 0.6 * k); ctx.closePath(); ctx.fill();
      }
      if (f.eye) {
        ctx.shadowBlur = 0; ctx.fillStyle = 'rgba(200,230,232,' + (0.25 + 0.5 * approach).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(bx - dir * f.rx * 0.55 * k, py + f.dy * k - f.ry * 0.2 * k, 5 * k, 0, 6.2832); ctx.fill();
      }
    } else {
      ctx.beginPath(); ctx.ellipse(px, py, 26 * k, 20 * k, 0, 0, 6.2832); ctx.fill();
      for (let i = 0; i < 6; i++) {
        const a = Math.PI * 0.2 + i * 0.4;
        ctx.lineWidth = 4 * k; ctx.beginPath(); ctx.moveTo(px, py + 10 * k);
        ctx.quadraticCurveTo(px + Math.cos(a + t / 800) * 26 * k, py + 30 * k, px + Math.cos(a) * 44 * k, py + 40 * k + Math.sin(t / 700 + i) * 5 * k);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // 신규 일곱의 윤곽 수치(옛 세계 px). rx·ry 몸, back 창에서 물러난 거리, tail 꼬리, dy 높이
  const FISH = {
    mirror_eye:   { rx: 70, ry: 26, back: 70, tail: 26, dy: 0, eye: true },
    straight_one: { rx: 120, ry: 7, back: 120, tail: 14, dy: 0 },
    lid:          { rx: 150, ry: 16, back: 0, tail: 0, dy: -70 },
    needle:       { rx: 160, ry: 4, back: 150, tail: 10, dy: 10 },
    big_maw:      { rx: 150, ry: 80, back: 150, tail: 50, dy: 10 },
    follower:     { rx: 48, ry: 20, back: 60, tail: 22, dy: 20 },
    upper_child:  { rx: 22, ry: 12, back: 30, tail: 12, dy: -30 },
  };
  const raidTargetSlot = () => (cb && cb.raid && cb.raid.target_slot != null) ? cb.raid.target_slot : null;

  // 탭이 숨으면 그리기를 멈춘다(배터리·발열 — D8). 돌아오면 이어서
  let raf = 0, prev = 0, fpsLog = [], workLog = [];
  function frame(t) {
    raf = requestAnimationFrame(frame);
    const w0 = performance.now();
    try { frameBody(t); } finally { if (workLog.length > 240) workLog.shift(); workLog.push(performance.now() - w0); }
  }
  function frameBody(t) {
    const dt = prev ? Math.min(60, t - prev) : 16; prev = t;
    if (fpsLog.length > 240) fpsLog.shift(); fpsLog.push(dt);
    if (!view.w) return;
    stepCam(t);
    hits = [];
    ctx.clearRect(0, 0, view.w, view.h);
    // 그리는 순서 = 배경 계약 layout.json layers.draw_order
    drawWater(t);                                     // 겹 1 — 뒤(바다)
    drawLife(t, false);                               //   생물(z<20, 탑 뒤)
    if (!ark) { drawShell(); drawShafts(); drawCliff(); drawFront(t); return; }
    drawSpots(t);
    drawSilhouette(t, dt);                            //   심연의 위협은 탑보다 뒤 물속에
    drawShell();                                      // 겹 2 — 탑 껍데기
    drawDome(t);
    drawLure(t);
    drawShafts();                                     // 겹 3 — 승강로
    drawCliff();                                      // 겹 4 — 절벽(탑의 왼쪽 외벽을 감싼다)
    movingNow = {}; traffic.moving(t / 1000).forEach(id => { movingNow[id] = true; });
    drawSealedAll(t);
    const byslot = {}; (ark.rooms || []).forEach(r => { byslot[r.slot] = r; });
    const people = peopleBySlot();
    for (let s = 0; s < slots; s++) drawRoom(s, byslot[s], people[s], t);
    drawOverRoom(t);
    drawCars(t);                                      //   승강기 칸 — 사람은 그 위에
    drawHall(t);
    drawOutside(t);
    drawMovers(t);
    drawLife(t, true);                                //   생물(z≥20)
    drawDeepDark();
    drawMotes(t);
    drawFront(t);                                     // 겹 5 — 앞(시차 1.12)
    if (dragging) {                                   // 손끝에 매달린 사람
      drawPerson(dragging, pointer.x, pointer.y + 48 * cam.z, t, 0, 1, true, 'idle');
      drawDropStat();
    }
    drawZones();
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(raf); raf = 0; }
    else if (!raf) { prev = 0; raf = requestAnimationFrame(frame); }
  });

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
  // S11-C: 12종으로 넓혔다. 손 = 만들고 고치는 방, 눈 = 읽고 내다보는 방, 숨 = 버티고 돌보는 방.
  // 거주·목욕·홀은 일하는 방이 아니라 비워 둔다. ★ 기획 확인 대상(TASKS 요청함)
  const ROOM_STAT = { workshop: 'hand', generator: 'hand', storage: 'hand', pantry: 'hand', well: 'hand',
                      library: 'eye', decoder: 'eye', lounge: 'eye',
                      infirmary: 'breath', greenhouse: 'breath', airlock: 'breath' };
  const STAT_KO_DEF = { hand: '손', eye: '눈', breath: '숨', nerve: '담' };
  function goodStats(slot) {
    const room = (ark.rooms || []).find(r => r.slot === slot);
    const out = [];
    if (room && ROOM_STAT[room.id]) out.push(ROOM_STAT[room.id]);
    if (raidTargetSlot() === slot) out.push('nerve');
    return out;
  }
  // 능력치는 **숫자로**(사용자 지시, DECISIONS 2026-10-03 — 10-01 의 '점 네 줄'은 철회).
  // 넷을 한 줄에 「손 7 · 눈 5 · 숨 6 · 담 4」. 이 방에 유리한 것은 등불색으로, 특이점이 붙은 숫자엔 밑줄.
  function statRows(p, slot) {
    const meta = (ark.stats_meta || {}), keys = meta.keys || ['hand', 'eye', 'breath', 'nerve'];
    const ko = meta.ko || STAT_KO_DEF, use = meta.use || {};
    const st = p.stats || {};
    if (!keys.some(k => st[k])) return '';
    const good = slot == null ? [] : goodStats(slot);
    const q = p.quirk || {};
    return '<div class="stats"><div class="snum">' + keys.map(k => {
      const v = Math.max(0, Math.min(10, st[k] || 0));
      const qc = q.stat === k ? (q.sign < 0 ? ' qm' : ' qp') : '';
      return '<span class="sn' + (good.indexOf(k) >= 0 ? ' good' : '') + qc + '"' +
        (use[k] ? ' title="' + esc(use[k]) + '"' : '') + '><i>' + esc(ko[k] || k) + '</i><b>' + v + '</b></span>';
    }).join('') + '</div>' +
      (q.ko ? '<em class="quirk' + (q.sign < 0 ? ' minus' : '') + '">' + esc(q.ko) + '</em>' : '') +
      '</div>';
  }
  // 들고 있는 사람의 '그 방에 유리한 숫자'(갈 곳 목록에 붙인다)
  function destStat(slot) {
    const p = carry && (ark.residents_list || []).find(r => r.id === carry.id);
    if (!p || !p.stats) return '';
    const ko = (ark.stats_meta || {}).ko || STAT_KO_DEF;
    const ks = goodStats(slot);
    return ks.length ? '<span class="bstat">' + ks.map(k => esc(ko[k] || k) + ' ' + (p.stats[k] || 0)).join(' · ') + '</span>' : '';
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
        (tgt ? ' · 노려지는 방' : '') + destStat(r.slot) + '</b><small>' + n + '/' + cap + '명' +
        (here ? ' · 지금 여기' : (full ? ' · 꽉 찼다' : '')) + '</small></button>';
    });
    rows.push('<button class="bopt" data-dest="hall"' +
      (cb.stations[carry.id] === undefined ? ' disabled' : '') +
      '><b>홀</b><small>돔 상부 · 아무 방도 지키지 않는다</small></button>');
    return '<h3>' + esc(carry.name) + ' 을(를) 어디로</h3>' +
      (raidLive('lid') ? '<p class="rno">덮개 앞이다. 옮기는 순간 관문이 깨진다 — 그대로 두려면 사람을 다시 누른다.</p>' : '') +
      '<div class="blist">' + rows.join('') + '</div>';
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
    const desk = view.w > 560 && view.h > 500, raid = !bar.hidden;
    // 가로 데스크톱: 습격 막대 아래 자리가 좁으면(< 380 px) 패널은 왼쪽으로 — 둘 다 읽혀야 한다
    const below = desk && raid && (view.h - bar.offsetHeight - 48) >= 380;
    const left = desk && raid && !below;
    pan.classList.toggle('left', left);
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
        lightButton(slot, lit) +
        '</div>' + destList() + shelfSection(slot) + upgradeSection((ark.upgrades || {})[String(slot)], slot) +
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
      bindUpgrade(body);
    } else {
      if (f < DOME_FLOOR) {
        body.innerHTML = '<h2>돔 상부 · 홀</h2><p class="sub">깊이 0m 위 · 유리 천장</p>' +
          '<p class="desc">여기엔 더 놓을 자리가 없다. 방주는 아래로 자란다.<br>배치되지 않은 사람은 이 홀에 모인다.</p>';
        $('#panel').hidden = false; placePanel(); return;
      }
      const bo = ark.build_options || null;               // 서버가 '지금 지을 수 있나'를 주면 그것을 그린다
      const ids = Object.keys(catalog).filter(id => !catalog[id].fixed && (!bo || bo[id]));
      body.innerHTML =
        '<h2>물이 찬 칸</h2>' +
        '<p class="sub">' + fl + '층 · 깊이 ' + depth + 'm · ' + esc(zoneAt(f)) + '</p>' +
        '<p class="desc">물을 빼면 칸을 되찾는다. 아래로 내려갈수록 유물이 좋아지고 위험해진다.</p>' +
        '<h3>물을 빼고 무엇으로 쓸까</h3><div class="blist">' +
        ids.map(id => {
          const o = bo && bo[id];
          const lack = o ? Object.entries(o.lacking || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v)
                              .concat((o.cond_missing || []).map(plain)) : lacking(id);
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
      (list.length ? list.map(p => personRow(p, null)).join('') : '<div class="who"><em>모두 자리에 있다</em></div>') +
      upgradeSection(ark.hall_upgrade, 'hall');
    bindDest(body);
    bindUpgrade(body);
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

  function zoneAt(floor) {                            // 서버 층 → 깊이(m) → 구역. 경계는 미터(ZONE_M)
    const m = (floor - DOME_FLOOR) * DEPTH_PER_FLOOR;
    const z = ZONE_M.find(z => m >= z.m0 && m < z.m1);
    return z ? z.ko : '무광층';
  }
  function creatureName(id) { return (cb && cb.creatures && cb.creatures[id] && cb.creatures[id].name) || id; }
  function toolName(id) {
    const t = cb && cb.workshop.tools.find(x => x.id === id);
    return t ? t.name : id;
  }

  // ── 동작 ──────────────────────────────────────────────────
  function setCarry(c) {
    carry = c; const el = $('#carry');
    const lid = !!c && raidLive('lid');               // 반전 ② — 이 게임의 주된 동사가 최악수가 되는 날
    el.classList.toggle('warn', lid);
    if (c) { el.textContent = c.name + (lid ? ' — 덮개 앞이다. 옮기면 최악수' : ' — 놓을 방을 고르세요'); el.hidden = false; }
    else el.hidden = true;
  }

  async function place(residentId, slot) {
    try {
      const st = await api('/api/ark/station', { resident_id: residentId, slot: slot });
      apply(st); setCarry(null);
      toast(raidLive('lid') ? '옮겼다 — 덮개가 움직임을 느꼈다'
                            : (slot == null ? '홀로 되돌렸다' : '자리를 옮겼다'));
      if (slot != null) openPanel(slot); else openHallPanel();
      refreshRaid();
    } catch (e) { toast(e.message || '옮기지 못했다'); setCarry(null); }
  }
  async function setLight(slot, on) {
    const wrongDark = !on && raidLive('mirror_eye') && (raidTargetSlot() == null || raidTargetSlot() === slot);
    try { apply(await api('/api/ark/light', { slot, on }));
          toast(wrongDark ? '불을 껐다 — 거울눈이 비침을 잃었다. 긴목 때와 반대다'
                          : (on ? '불을 켰다' : '불을 껐다 — 이 방은 우리도 못 본다'));
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
  // ── 되찾기 한 줄(S12-B · 시나리오 S12-D tower_lore.json). 깊이 띠(top 0~60·mid 60~120·low 120~) 안에서
  // 아직 안 쓴 줄. 첫 되찾기 = order_hint first, 180 m 칸 = last. 쓴 줄은 이 기계에만 적는다(없어도 동작)
  let towerLore = null;
  fetch('/api/lore/tower').then(r => (r.ok ? r.json() : null)).then(j => { towerLore = j; }).catch(() => {});
  function loreUsed() { try { return JSON.parse(localStorage.getItem('ark_reclaim_' + uid) || '[]'); } catch (e) { return []; } }
  function reclaimLine(slot) {
    const rows = (towerLore && towerLore.reclaim) || [];
    if (!rows.length) return '';
    const m = (floorOf(slot) - DOME_FLOOR) * DEPTH_PER_FLOOR;
    const band = m < 60 ? 'top' : m < 120 ? 'mid' : 'low';
    const used = loreUsed(), free = rows.filter(r => used.indexOf(r.id) < 0);
    let pick = null;
    if (!used.length) pick = free.find(r => r.order_hint === 'first');
    if (!pick && m >= TRENCH_M) pick = free.find(r => r.order_hint === 'last');
    if (!pick) pick = free.find(r => r.band === band && r.order_hint !== 'last' && r.order_hint !== 'first');
    if (!pick) pick = free.find(r => r.band === 'any' || r.band === band);
    if (!pick) return '';
    try { localStorage.setItem('ark_reclaim_' + uid, JSON.stringify(used.concat(pick.id))); } catch (e) { /* 이 기계에 못 적어도 줄은 보인다 */ }
    return pick.line;
  }
  // 서버 칸이 없는 맵 칸을 눌렀을 때 — 지금은 되찾을 수 없다고 정직하게. 180 m 아래는 시나리오의 below_limit
  function openSealed(c) {
    sel = null;
    const deep = (c.depth_m || 0) >= TRENCH_M;
    const bl = towerLore && towerLore.below_limit && towerLore.below_limit.line;
    const body = $('#panelBody');
    body.innerHTML = c.kind === 'rock'
      ? '<h2>벽 쪽 바위</h2><p class="sub">깊이 ' + esc(c.depth_m) + 'm</p><p class="desc">아직 파지 못했다. 굴 끝에 손전등을 비추면 바위 결만 돌아온다.</p>'
      : '<h2>' + (deep ? '검게 잠긴 칸' : '물이 찬 칸') + '</h2><p class="sub">깊이 ' + esc(c.depth_m) + 'm' + (deep ? ' · ' + esc(zoneAt(DOME_FLOOR + c.depth_m / DEPTH_PER_FLOOR)) : '') + '</p>' +
        '<p class="desc">' + esc(deep && bl ? bl : '격벽이 아직 열리지 않는다. 지금은 물을 뺄 수 없는 칸이다.') + '</p>';
    $('#panel').hidden = false; placePanel();
  }
  async function build(roomId, slot) {
    try {
      const st = await api('/api/ark/build', { room_id: roomId, slot });
      apply(st);
      // M5: 짓는 것이 아니라 물을 빼고 되찾는다(라벨만 — API 는 /api/ark/build 그대로). 되찾은 칸의 한 줄은 시나리오 data/tower_lore.json
      const line = reclaimLine(slot);
      toast(((catalog[roomId] || {}).name || roomId) + ' — 물을 뺐다' + (line ? '. ' + line : ''));
      openPanel(slot);
      if (line) { const d = $('#panelBody .desc'); if (d) d.insertAdjacentHTML('beforebegin', '<p class="reclaim">' + esc(line) + '</p>'); }
    } catch (e) { toast(e.message || '물을 빼지 못했다'); }
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
      $('#rflip').hidden = true; $('#ract').hidden = true;
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
      g.innerHTML = '<b>' + (raid.ready.gate.ok ? '준비됐다' : '아직이다') + '</b><span>' + esc(raid.ready.gate.ko) + '</span>';
      wd.classList.toggle('bad', raid.ready.would !== 'held');
      wd.innerHTML = '지금 맞서면 <b>' + esc(raid.ready.would_ko) + '</b>';
    } else { g.hidden = true; wd.hidden = true; }
    renderGate(raid);
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
      raidPan(raid);
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
  // 서버 상태가 바뀌어 누군가의 자리가 달라지면 그 사람을 **걸어서·엘리베이터로** 옮긴다.
  // 배치는 여전히 서버가 정본이고(새로고침하면 바로 그 자리), 이동은 눈에 보이는 연출일 뿐이다.
  let lastWhere = null, lastLists = null, moveLog = [];
  function whereOf(id) {
    if (cb.outside && cb.outside.indexOf(id) >= 0) return 'out';
    const s = cb.stations[id]; return s === undefined ? 'hall' : s;
  }
  function trackMoves() {
    if (!cb || !ark) return;
    const where = {}, lists = {};
    (ark.residents_list || []).forEach(p => { const w = whereOf(p.id); where[p.id] = w; (lists[w] = lists[w] || []).push(p.id); });
    if (lastWhere) {
      const t = performance.now(), moves = [];
      const nodeIn = (id, w, ls, wander) => {
        const L = ls[w] || [id], i = Math.max(0, L.indexOf(id)), n = Math.max(L.length, i + 1);
        const nd = MOVE_ADAPTER.nodeOf(w, i, n);
        // 출발은 방 안에서 서성이던 그 자리에서. 도착은 제 자리 — 거기서부터 다시 서성인다(lifeAt 의 ramp)
        if (wander && typeof w === 'number') nd.x += lifeOffsetM(id, w, i, n, t);
        return nd;
      };
      Object.keys(where).forEach(id => {
        if (lastWhere[id] === undefined || lastWhere[id] === where[id]) return;
        moves.push({ id, from: nodeIn(id, lastWhere[id], lastLists, true), to: nodeIn(id, where[id], lists, false) });
      });
      if (moves.length) {
        traffic.setGraph(MOVE_ADAPTER.graph());
        const r = traffic.go(moves, t / 1000); traffic.forget(t / 1000);
        moveLog = moveLog.concat((r && r.log) || []).slice(-20);
      }
    }
    lastWhere = where; lastLists = lists;
  }

  function apply(st) {
    ark = st;
    cb = st.combat || cb;
    if (Array.isArray(st.shelf)) shelf = st.shelf.filter(x => x && typeof x.slot === 'number');
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
    // 이동은 연출이다 — 여기서 무엇이 터져도 상태 반영(정본)은 끝난 뒤다. 숨기지 않고 콘솔에 남긴다(D4)
    try { trackMoves(); } catch (e) { lastWhere = null; console.error('이동 계산 실패', e); }
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

  // ══════════════════════════════════════════════════════════════
  //  스프린트 10-E — 이 화면에 빠져 있던 조작 넷
  //   ① 찍기(/api/scan) ② 관문 행동(/api/ark/act) ③ 열쇠(/api/account) ④ E1 선반
  //  근거: PLAYER_JOURNEY §2 E1 · §3 J5, COMBAT_AND_DEFENSE §4, data/creatures.json 의 wrong_move
  // ══════════════════════════════════════════════════════════════
  const plain = (s) => String(s == null ? '' : s).replace(/\*\*/g, '');      // 서버 문장의 강조 표시를 걷는다
  const raidLive = (cid) => !!(cb && cb.raid && cb.raid.creature && cb.raid.creature.id === cid &&
                               cb.raid.stage !== 'done' && !cb.raid.resolved);

  // ── 카메라가 천천히 그 자리로 간다(선반으로 데려가기) ─────────────
  let camTo = null;
  function stepCam(t) {
    if (!camTo) return;
    const k = Math.min(1, Math.max(0, (t - camTo.t0) / camTo.dur)), e = 1 - Math.pow(1 - k, 3);
    cam.x = camTo.from.x + (camTo.x - camTo.from.x) * e;
    cam.y = camTo.from.y + (camTo.y - camTo.from.y) * e;
    cam.z = camTo.from.z + (camTo.z - camTo.from.z) * e;
    clampCam();
    if (k >= 1) camTo = null;
  }
  function flyToSlot(slot) {
    const r = rectOf(slot), ins = uiInset();
    const h = Math.max(120, view.h - ins.top - ins.bottom);
    if (!r) return;
    const z = Math.max(cam.z, Math.min(0.9, (view.w * 0.6) / r.w, (h * 0.7) / r.h));
    camTo = { from: { x: cam.x, y: cam.y, z: cam.z }, x: r.x + r.w / 2,
              y: r.y + r.h / 2 + ((ins.bottom - ins.top) / 2) / z, z, t0: performance.now(), dur: 750 };
  }

  // ── ④ E1 선반: 찍은 물건이 창고 선반에 놓인다 ───────────────────
  // 창고 방이 생기면 그 방, 아직 없으면 시작 방인 식량창고. 서버가 shelf_room{slot,capacity} 를 주면 그것이 이긴다.
  const SHELF_ROOMS = ['storage', 'store', 'pantry'];
  const PROP_ID_OK = /^[a-z0-9_]+$/;
  const CAT_KO = { food: '식품', drink: '음료', medical: '의약·화학', electronics: '전자', stationery: '문구',
                   book: '도서', apparel: '의류', tobacco: '담배·주류', unknown: '정체불명' };
  const RAR_KO = { common: '흔함', uncommon: '쓸만함', rare: '귀함', epic: '진귀함', legendary: '전설' };  // ROOMS_AND_ITEMS §1
  const CAT_FILL = { food: '#c08a33', drink: '#d8c9a3', medical: '#e6d7b0', electronics: '#39312a',
                     stationery: '#b03a24', book: '#8d8f4a', apparel: '#96703f', tobacco: '#dc7728', unknown: '#7e8d8c' };
  let shelf = [], propsMeta = {}, shelfFlash = null;
  fetch('/static/art/props/props_meta.json').then(r => (r.ok ? r.json() : null))
    .then(j => { propsMeta = (j && j.props) || {}; }).catch(() => { propsMeta = {}; });
  const propImgs = {};
  function propImg(id) {
    if (!id || !PROP_ID_OK.test(id)) return null;
    let p = propImgs[id];
    if (!p) {
      p = propImgs[id] = { x1: new Image(), x4: new Image(), ok1: false, ok4: false };
      p.x1.onload = () => { p.ok1 = p.x1.naturalWidth > 0; };
      p.x4.onload = () => { p.ok4 = p.x4.naturalWidth > 0; };
      p.x1.src = '/static/art/props/' + id + '.png';
      p.x4.src = '/static/art/props/x4/' + id + '.png';
    }
    return p;
  }
  function propSpec(id) {
    const m = propsMeta[id] || {};
    return { w: m.w || 34, h: m.h || 30, slots: Math.max(1, m.slots || 1), name: m.name || '' };
  }
  function propForCategory(cat) {
    const ids = Object.keys(propsMeta);
    return ids.find(k => propsMeta[k].category === cat) || ids.find(k => propsMeta[k].category === 'unknown') || null;
  }
  function shelfRoomSlot() {
    if (!ark) return null;
    if (ark.shelf_room && typeof ark.shelf_room.slot === 'number') return ark.shelf_room.slot;   // 서버가 정한 선반 방
    if (typeof ark.shelf_room_slot === 'number') return ark.shelf_room_slot;
    const live = (ark.rooms || []).filter(r => !r.flooded);
    for (const id of SHELF_ROOMS) { const r = live.find(x => x.id === id); if (r) return r.slot; }
    return null;
  }
  function shelfCap() {
    let end = 0;
    shelf.forEach(it => { end = Math.max(end, (it.slot | 0) + propSpec(it.prop_id).slots); });
    const cap = (ark.shelf_room && typeof ark.shelf_room.capacity === 'number') ? ark.shelf_room.capacity
      : (typeof ark.shelf_cap === 'number' ? ark.shelf_cap : 6);
    return Math.max(1, cap, end);
  }
  // 선반 격자(방 안쪽 기준 세계 좌표). 방 이름표 아래에서 바닥 띠 위까지. 칸이 늘면 줄과 칸 크기가 바뀐다
  function shelfGrid() {
    const cap = shelfCap(), perRow = cap <= 12 ? 6 : 10, rows = Math.ceil(cap / perRow);
    // M5 칸(564×317, 플레이트 1:1)의 뒷벽: 방 이름표 아래 ~ 사람 머리 위. 칸 좌표(px)
    const innerW = 470, top = 46, avail = 108;
    const S = Math.min(2, innerW / (perRow * 34), (avail - rows * 3) / (rows * 30));
    return { cap, perRow, rows, S, cw: 34 * S, ch: 30 * S, x0: 47 + (innerW - perRow * 34 * S) / 2, top };
  }
  function drawShelf(slot, ix, iy, iw, ih, lit) {
    if (slot !== shelfRoomSlot() || cam.z < 0.1) return;
    const g = shelfGrid(), z = cam.z, now = performance.now();
    const X = (wx) => ix + wx * z, Y = (wy) => iy + wy * z;
    const baseOf = (row) => g.top + row * (g.ch + 3) + g.ch;
    ctx.save();
    ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
    if (!lit) ctx.globalAlpha = 0.45;
    for (let r = 0; r < g.rows; r++) {                         // 선반 판: 흙색 두 단(FLAT_FOLK §1-3)
      const n = Math.min(g.perRow, g.cap - r * g.perRow), by = baseOf(r);
      ctx.fillStyle = '#49331d'; ctx.fillRect(X(g.x0 - 2), Y(by), (n * g.cw + 4) * z, Math.max(1, 3 * z));
      ctx.fillStyle = '#96703f'; ctx.fillRect(X(g.x0 - 2), Y(by), (n * g.cw + 4) * z, Math.max(1, 1 * z));
    }
    const used = new Set();
    shelf.forEach(it => { for (let k = 0; k < propSpec(it.prop_id).slots; k++) used.add((it.slot | 0) + k); });
    if (z > 0.45) {                                           // 빈 칸 — 채우고 싶게 한다(증축 동기)
      ctx.strokeStyle = 'rgba(20,17,12,0.28)'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      for (let i = 0; i < g.cap; i++) {
        if (used.has(i)) continue;
        const row = Math.floor(i / g.perRow), col = i % g.perRow;
        ctx.strokeRect(Math.round(X(g.x0 + col * g.cw + 2)) + 0.5, Math.round(Y(baseOf(row) - g.ch + 3)) + 0.5,
                       Math.round((g.cw - 4) * z), Math.round((g.ch - 4) * z));
      }
      ctx.setLineDash([]);
    }
    // 정수 배율: 소품 원화 1px 이 화면 몇 px 인가. 1보다 크면 정수(칸에 들어가면 반올림, 아니면 내림),
    // 1보다 작으면 4배 그림을 줄여 쓴다(축소는 뭉개지지 않는다)
    const sc = g.S * z;
    // 배율은 선반 전체가 하나다(칸 하나 34px 기준). 물건마다 다르면 한 선반에서 크기가 들쭉날쭉해진다
    let k = sc;
    if (sc >= 1) { k = Math.round(sc); if (34 * k > g.cw * z + 3) k = Math.max(1, Math.floor(sc)); }
    shelf.forEach(it => {
      const i = it.slot | 0; if (i < 0 || i >= g.cap) return;
      const row = Math.floor(i / g.perRow), col = i % g.perRow, sp = propSpec(it.prop_id);
      const span = sp.slots * g.cw;                          // 폭 2 소품은 두 칸(줄 끝이면 판 밖으로 조금 나간다)
      const w = sp.w * k, h = sp.h * k;
      const px = Math.round(X(g.x0 + col * g.cw) + (span * z - w) / 2), py = Math.round(Y(baseOf(row)) - h);
      const fl = shelfFlash && shelfFlash.slot === i && now < shelfFlash.until;
      if (fl) {                                               // 방금 놓인 칸 — 등불색이 숨 쉬듯 번진다
        const a = 0.35 + 0.3 * Math.sin(now / 220);
        const rg = ctx.createRadialGradient(px + w / 2, py + h / 2, 0, px + w / 2, py + h / 2, Math.max(w, h));
        rg.addColorStop(0, 'rgba(240,176,85,' + a.toFixed(3) + ')'); rg.addColorStop(1, 'rgba(240,176,85,0)');
        ctx.fillStyle = rg; ctx.fillRect(px - w, py - h, w * 3, h * 3);
      }
      const p = propImg(it.prop_id);
      if (p && (p.ok4 || p.ok1)) {
        const useX4 = p.ok4 && (k < 4 || !p.ok1);
        ctx.imageSmoothingEnabled = useX4;
        if (useX4) ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(useX4 ? p.x4 : p.x1, px, py, w, h);
        ctx.imageSmoothingEnabled = true;
      } else {                                                // 그림이 아직 안 왔다 — 카테고리 색 상자
        ctx.fillStyle = CAT_FILL[it.category] || CAT_FILL.unknown;
        ctx.fillRect(px + 2, py + h * 0.3, w - 4, h * 0.7);
        ctx.strokeStyle = '#14110c'; ctx.lineWidth = 1; ctx.strokeRect(px + 2, py + h * 0.3, w - 4, h * 0.7);
      }
      if (fl) {
        ctx.strokeStyle = '#f0b055'; ctx.lineWidth = Math.max(1.5, 2 * z);
        ctx.strokeRect(px - 2, py - 2, w + 4, h + 4);
      }
      hits.push({ kind: 'shelf', item: it, x: px, y: py, w, h });
    });
    ctx.restore();
    // 방금 놓인 물건의 이름. 방 밖으로 넘쳐도 읽히게 clip 밖에서 쓴다
    const f = shelfFlash && now < shelfFlash.until && shelf.find(x => (x.slot | 0) === shelfFlash.slot);
    if (f) {
      const lbl = '방금 찍은 것 · ' + (f.name || propSpec(f.prop_id).name || '');
      ctx.font = '700 ' + Math.max(11, 12 * Math.min(1.3, z)) + 'px "Noto Sans KR",sans-serif';
      const tw = ctx.measureText(lbl).width + 14, lx = ix + iw / 2 - tw / 2, ly = iy - 24;
      ctx.fillStyle = 'rgba(240,176,85,0.95)'; ctx.fillRect(lx, ly, tw, 20);
      ctx.fillStyle = '#1a150e'; ctx.textBaseline = 'middle'; ctx.fillText(lbl, lx + 7, ly + 10.5);
      ctx.textBaseline = 'alphabetic';
    }
  }
  // "어제 편의점에서 찍은 그것"(J5) — 언제 찍었는지를 날짜가 아니라 말로
  function whenKo(ts) {
    if (!ts) return '';
    const a = new Date(ts * 1000), b = new Date();
    const d0 = new Date(a.getFullYear(), a.getMonth(), a.getDate()), d1 = new Date(b.getFullYear(), b.getMonth(), b.getDate());
    const days = Math.round((d1 - d0) / 86400000);
    if (days <= 0) return (Date.now() / 1000 - ts) < 600 ? '방금' : '오늘';
    return days === 1 ? '어제' : days + '일 전';
  }
  function shelfLine(it) {
    const nm = it.name || propSpec(it.prop_id).name || '물건';
    const w = whenKo(it.scanned_at);
    return nm + (w ? ' — ' + w + ' 찍은 것' : '') + (it.category ? ' · ' + (CAT_KO[it.category] || it.category) : '');
  }
  function shelfSection(slot) {
    if (slot !== shelfRoomSlot()) return '';
    const cap = shelfCap();
    const rows = shelf.slice().sort((a, b) => (b.scanned_at || 0) - (a.scanned_at || 0));
    const fresh = shelfFlash && performance.now() < shelfFlash.until ? shelfFlash.slot : null;
    return '<h3>선반 · ' + rows.length + '점 / ' + cap + '칸</h3><div class="kv shelfkv">' +
      (rows.length ? rows.map(it => '<span' + ((it.slot | 0) === fresh ? ' class="new"' : '') + '>' +
          esc(it.name || propSpec(it.prop_id).name || it.prop_id) + ' · ' + esc(whenKo(it.scanned_at)) + '</span>').join('')
        : '<span>비어 있다 — 찍은 물건이 여기 놓인다</span>') + '</div>';
  }
  function focusShelf(slot) {
    const rs = shelfRoomSlot();
    if (rs == null) { toast('물건을 둘 창고가 없다'); return; }
    flyToSlot(rs);
    shelfFlash = { slot, until: performance.now() + 9000 };
    setTimeout(() => play('sfx_card_place.ogg', 0.55), 700);
    const it = shelf.find(x => (x.slot | 0) === slot);
    const room = (ark.rooms || []).find(r => r.slot === rs);
    const nm = (room && (catalog[room.id] || {}).name) || '창고';
    toast(nm + ' 선반에 놓였다' + (it ? ' — ' + (it.name || propSpec(it.prop_id).name) : ''));
  }

  // 불 버튼. 거울눈 앞에서 노려지는 방의 불을 끄는 것은 **긴목에게 배운 정답이 오답이 되는 자리**다
  function lightButton(slot, lit) {
    const tgt = raidTargetSlot();
    const worst = lit && raidLive('mirror_eye') && (tgt == null || tgt === slot);
    return '<button id="lgt" class="' + (lit ? 'on' : '') + (worst ? ' worst' : '') + '">' +
      (lit ? (worst ? '불 켜짐 — 끄면 최악수(거울눈)' : '불 켜짐 — 끄기') : '불 꺼짐 — 켜기') + '</button>';
  }

  // ── ② 관문 행동 · 반전 ───────────────────────────────────
  // 반전 둘(creatures.json wrong_move): 거울눈은 '불을 끄면', 덮개는 '사람을 옮기면' 최악수다
  const REVERSAL = {
    mirror_eye: {
      base: () => '<b>긴목 때와 반대다.</b> 불을 끄지 않는다 — 비침이 사라지면 짝을 찾으러 유리를 민다.',
      bad: (raid) => (raid.target_slot != null && !lightOf(raid.target_slot))
        ? '<b>' + esc(raid.target_room || '그 방') + '의 불이 꺼져 있다.</b> 긴목에게 통한 수가 여기서는 가장 나쁜 수다.' +
          '<button data-relight="' + raid.target_slot + '">다시 켠다</button>' : null,
    },
    lid: {
      base: () => '<b>아무도 옮기지 않는다.</b> 사람을 옮기는 것이 지금은 가장 나쁜 수다 — 움직이는 것 위에는 앉지 않는다.',
      bad: (raid) => (raid.moves > 0)
        ? '<b>이미 ' + raid.moves + '번 옮겼다.</b> 덮개가 움직임을 느꼈다. 살아 있는 줄 알면 놀라서 몸을 턴다.' : null,
    },
  };
  const ACT_SFX = { light_elsewhere: 'sfx_lantern_on.ogg', cloud_water: 'sfx_water_splash.ogg', make_way: 'sfx_tool_install.ogg',
                    feed: 'sfx_airlock_cycle.ogg', return_it: 'sfx_airlock_cycle.ogg', guide_up: 'sfx_light_on.ogg' };
  const paidLog = {};                                   // 습격 id → 이번에 치른 것(화면에 남긴다)
  function renderGate(raid) {
    const fl = $('#rflip'), box = $('#ract');
    const live = !!(raid.creature.threat && raid.stage !== 'done' && !raid.resolved);
    const rv = live && REVERSAL[raid.creature.id];
    if (rv) {
      const bad = rv.bad(raid);
      fl.hidden = false; fl.classList.toggle('bad', !!bad);
      fl.innerHTML = bad || rv.base();
      const fb = fl.querySelector('button[data-relight]');
      if (fb) fb.addEventListener('click', () => setLight(parseInt(fb.dataset.relight, 10), true));
    } else fl.hidden = true;
    const a = live ? raid.action : null;
    // 폰에서 습격 막대가 화면 3분의 1을 넘지 않게 — 행동·반전 줄이 있으면 서술 줄을 접는다(CSS)
    $('#raidbar').classList.toggle('has-act', !!a || !!rv);
    if (!a) { box.hidden = true; return; }
    box.hidden = false; box.classList.toggle('done', !!a.done);
    const lack = Object.entries(a.lacking || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
    const no = a.done ? '' : ((a.blocked && a.blocked.length) ? '할 수 없다 — ' + a.blocked.join(' · ')
                              : (lack ? '모자란다 — ' + lack : ''));
    const paid = paidLog[raid.id];
    box.innerHTML =
      '<button class="ractbtn" data-act="' + esc(a.id) + '"' + (a.can ? '' : ' disabled') + '>' +
        (a.done ? '했다 — ' : '') + esc(plain(a.ko)) + '</button>' +
      (a.done ? '' : '<div class="rcost' + (lack ? ' lack' : '') + '">대가 — ' + esc(plain(a.cost_ko)) + '</div>' +
                     (no ? '' : '<div class="rwhy">' + esc(plain(a.why)) + '</div>')) +
      (no ? '<div class="rno">' + esc(no) + '</div>' : '') +
      (paid ? '<div class="rpaid">' + esc(paid) + '</div>' : '');
    const b = box.querySelector('.ractbtn');
    if (b && a.can) b.addEventListener('click', () => doAct(a.id, raid.id));
  }
  async function doAct(id, raidId) {
    const b = $('#ract .ractbtn'); if (b) b.disabled = true;
    try {
      const r = await api('/api/ark/act', { action: id });
      if (r.state) apply(r.state);
      paidLog[raidId] = plain(r.ko);
      toast(plain(r.ko).split('. ')[0] + '.');
      play(ACT_SFX[id] || 'sfx_tool_install.ogg', 0.5);
      renderRaid();
      if (sel) openPanel(sel.slot);
    } catch (e) { toast(e.message || '하지 못했다'); refreshRaid(); }
  }

  // ── ① 찍기: 카메라 → 카드가 뒤집힌다 → 선반에 놓는다 (J5) ────────
  // app.js(옛 2D 화면)의 BarcodeDetector + 후면 카메라 + 숫자 폴백을 이 화면으로 옮겼다.
  const SAMPLES = [['8801043015097', '식품'], ['9791162241905', '도서'], ['8806011000013', '의약'],
                   ['8809000111110', '문구'], ['4901234567894', '미지 가문'], ['8801044007770', '패턴']];
  let stream = null, detector = null, scanning = false, lastCode = '', lastAt = 0, scanBusy = false;
  let pendingCode = null, lastScan = null;
  function openScan() {
    if (!ark) return;
    closePanel(); setCarry(null);
    $('#scan').hidden = false; $('#scanCam').hidden = false; $('#scanCard').hidden = true;
    $('#picker').hidden = true; $('#manual').value = ''; pendingCode = null;
    $('#quota').textContent = '오늘 읽은 성문 ' + (ark.scans_today || 0) + ' / ' + (ark.scan_cap || 20) +
      ' · 같은 물건은 다시 읽을수록 덜 나온다';
    // 예시 번호는 개발 기계에서만 — 이 게임의 훅은 진짜 물건을 찍는 것이다
    const dev = /^(127\.0\.0\.1|localhost)$/.test(location.hostname) || qs.has('samples');
    const sm = $('#samples'); sm.hidden = !dev;
    if (dev) sm.innerHTML = SAMPLES.map(([c, l]) => '<button data-c="' + c + '">' + esc(l) + ' ' + c + '</button>').join('');
    startCam();
  }
  function closeScan() { stopCam(); $('#scan').hidden = true; }
  async function startCam() {
    const st = $('#camstatus'), box = $('#cam');
    box.classList.remove('off');
    if (!('BarcodeDetector' in window)) {
      box.classList.add('off'); st.textContent = '이 브라우저는 카메라로 줄무늬를 못 읽는다 — 아래에 숫자를 적는다'; return;
    }
    if (!navigator.mediaDevices || !window.isSecureContext) {
      box.classList.add('off'); st.textContent = '카메라는 HTTPS 에서만 열린다 — 아래에 숫자를 적는다'; return;
    }
    try {
      detector = detector || new BarcodeDetector({ formats: ['ean_13', 'upc_a', 'ean_8'] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1280 } } });
      if ($('#scan').hidden) { stopCam(); return; }
      const v = $('#video'); v.srcObject = stream; await v.play();
      st.textContent = '줄무늬를 붉은 선에 맞춘다'; scanning = true; camLoop();
    } catch (e) { box.classList.add('off'); st.textContent = '카메라를 열 수 없다 — 아래에 숫자를 적는다'; }
  }
  function stopCam() {
    scanning = false;
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    const v = $('#video'); if (v) v.srcObject = null;
  }
  async function camLoop() {
    if (!scanning) return;
    try {
      const codes = await detector.detect($('#video'));
      const c = codes.find(x => x.rawValue && x.rawValue.length >= 8);
      if (c && !scanBusy && (c.rawValue !== lastCode || Date.now() - lastAt > 4000)) {
        lastCode = c.rawValue; lastAt = Date.now();
        if (navigator.vibrate) navigator.vibrate(30);
        await handleCode(c.rawValue);
      }
    } catch (e) { /* 한 프레임 건너뛴다 */ }
    if (scanning) setTimeout(camLoop, 220);
  }
  async function handleCode(raw, userCat) {
    if (scanBusy) return;
    const code = String(raw || '').replace(/\D/g, '');
    if (code.length < 8) { toast('숫자 8~13자리를 적는다'); return; }
    scanBusy = true; $('#manualBtn').disabled = true;
    try {
      if (userCat === undefined) {
        const pk = await api('/api/peek?barcode=' + code);
        if (pk.needs_category) { showPicker(pk); return; }
      }
      const r = await api('/api/scan', { barcode: code, user_category: userCat || null });
      stopCam(); pendingCode = null;
      play('sfx_scan_ok.ogg', 0.5);
      // 선반의 정본은 /api/ark 다. 카드 앞면 그림을 선반에 놓일 물건과 같게 하려고 먼저 받는다
      try { apply(await api('/api/ark?uid=' + encodeURIComponent(uid))); } catch (e2) { /* 카드는 그래도 뒤집힌다 */ }
      showReveal(r);
    } catch (e) { toast(e.message || '읽지 못했다'); }
    finally { scanBusy = false; $('#manualBtn').disabled = false; }
  }
  function showPicker(pk) {
    pendingCode = pk.barcode;
    const w = $('#picker'); w.hidden = false;
    w.innerHTML = '<p>이 가문의 성문은 처음이다. 이 물건은 무엇인가?</p>' +
      (pk.categories || []).map(c => '<button data-cat="' + esc(c) + '">' + esc(CAT_KO[c] || c) + '</button>').join('') +
      '<button data-cat="">모른다</button>';
  }
  function showReveal(r) {
    lastScan = r;
    const c = r.card || {};
    const has = Object.prototype.hasOwnProperty.call(r, 'shelf_slot');
    const slot = typeof r.shelf_slot === 'number' ? r.shelf_slot : null;
    const item = slot != null ? shelf.find(x => (x.slot | 0) === slot) : null;
    const pid = (item && item.prop_id) || propForCategory(c.category);
    const sp = propSpec(pid);
    const front = $('#rcFront');
    front.className = 'rc-face rc-front ' + (RAR_KO[c.rarity] ? c.rarity : 'common');
    front.innerHTML = '<div class="rr">' + esc(RAR_KO[c.rarity] || c.rarity || '') + (r.first_time ? ' · 처음 보는 것' : '') + '</div>' +
      '<h3>' + esc(c.name || '이름 없는 것') + '</h3>' +
      '<div class="art">' + (pid && PROP_ID_OK.test(pid)
        ? '<img alt="" width="' + sp.w * 3 + '" height="' + sp.h * 3 + '" src="/static/art/props/x4/' + pid + '.png">' : '') + '</div>' +
      (c.flavor ? '<p class="fl">"' + esc(c.flavor) + '"</p>' : '') +
      '<div class="meta"><span>' + esc(CAT_KO[c.category] || c.category || '') + '</span>' +
        (c.family_name ? '<span>' + esc(c.family_name) + '</span>' : '') +
        (c.tags || []).filter(t => t !== '미확인').slice(0, 3).map(t => '<span>#' + esc(t) + '</span>').join('') + '</div>';
    const g = Object.entries(r.gained || {}).map(([k, v]) => '<b>' + esc(RES_KO[k] || k) + ' +' + esc(v) + '</b>').join(' · ');
    const shelfNote = slot != null
      ? '<span class="where">' + esc((item && item.name) || sp.name || '물건') + ' — 선반 ' + (slot + 1) + '번째 칸으로</span>'
      : (has ? '<span class="where">선반이 꽉 찼다. 창고를 넓히면 더 놓인다</span>' : '');
    $('#rgain').innerHTML = (r.first_time ? '<span class="first">도감에 처음 적힌 유물</span><br>' : '') +
      (g || '<span>이미 읽은 성문 — 얻은 것 없음</span>') +
      ((r.rescan_multiplier > 0 && r.rescan_multiplier < 1) ? ' <span>(다시 읽음 ×' + esc(r.rescan_multiplier) + ')</span>' : '') +
      shelfNote +
      ((r.voice && r.voice.text) ? '<span class="voice">' + esc(r.voice.who_ko || '') + (r.voice.who_ko ? ' — ' : '') + esc(r.voice.text) + '</span>' : '');
    const btn = $('#shelfBtn');
    btn.textContent = slot != null ? '선반에 둔다' : '닫는다';
    btn.classList.remove('on');
    $('#scanCam').hidden = true; $('#scanCard').hidden = false;
    const card = $('#rcard'); card.classList.remove('flip');
    void card.offsetWidth;                              // 다시 찍어도 뒤집기가 처음부터
    setTimeout(() => card.classList.add('flip'), 380);
    setTimeout(() => btn.classList.add('on'), 1150);
    if (navigator.vibrate && ['rare', 'epic', 'legendary'].indexOf(c.rarity) >= 0) setTimeout(() => navigator.vibrate([40, 60, 80]), 900);
  }
  function toShelf() {
    const r = lastScan; closeScan();
    if (r && typeof r.shelf_slot === 'number') focusShelf(r.shelf_slot);
  }

  // ── 레벨업(서버 S10 upgrades·hall_upgrade). 숫자가 아니라 '새로 할 수 있는 것'을 먼저 말한다 ──
  function upgradeSection(opt, key) {
    if (!opt) return '';
    const cost = Object.entries(opt.cost || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
    const lack = Object.entries(opt.lacking || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
    const miss = (opt.cond_missing || []).join(' · ');
    return '<h3>올리기 · Lv' + esc(opt.to) + '</h3><div class="blist"><button class="bopt' + (opt.can ? '' : ' lack') +
      '" data-up="' + esc(key) + '"' + (opt.can ? '' : ' disabled') + '><b>' + esc(plain(opt.opens) || ('Lv' + opt.to)) + '</b>' +
      '<small>' + esc(cost) + (opt.cond ? ' · 조건: ' + esc(plain(opt.cond)) : '') + '</small>' +
      (miss ? '<small>아직 — ' + esc(miss) + '</small>' : (lack ? '<small>모자란다 — ' + esc(lack) + '</small>' : '')) +
      '</button></div>';
  }
  function bindUpgrade(body) {
    body.querySelectorAll('.bopt[data-up]').forEach(b => b.addEventListener('click', async () => {
      const k = b.dataset.up;
      try {
        const st = await api('/api/ark/upgrade', k === 'hall' ? { room_id: 'hall' } : { slot: parseInt(k, 10) });
        apply(st);
        const u = st.upgraded || {};
        toast((u.name || '') + ' Lv' + (u.level || '') + (u.opens ? ' — ' + plain(u.opens) : ''));
        play('sfx_tool_install.ogg', 0.5);
        if (k === 'hall') openHallPanel(); else openPanel(parseInt(k, 10));
      } catch (e) { toast(e.message || '올리지 못했다'); }
    }));
  }

  // ── ③ 열쇠: 복구 코드 · 다른 기계에서 이어 하기 ─────────────────
  async function openAccount() {
    sel = null; setCarry(null);
    const body = $('#panelBody');
    body.innerHTML = '<h2>방주의 열쇠</h2><p class="sub">복구 코드</p><div class="keycode">· · ·</div>';
    $('#panel').hidden = false; placePanel();
    let a;
    try { a = await api('/api/account?uid=' + encodeURIComponent(uid)); }
    catch (e) { body.innerHTML = '<h2>방주의 열쇠</h2><p class="lost">열쇠를 꺼내지 못했다 — ' + esc(e.message || '') + '</p>'; return; }
    body.innerHTML = '<h2>방주의 열쇠</h2>' +
      '<p class="sub">' + esc(a.day) + '일째 · 방 ' + esc(a.rooms) + ' · 사람 ' + esc(a.residents) + '</p>' +
      '<div class="keycode" id="keycode">' + esc(a.pretty || a.code) + '</div>' +
      '<p class="desc">' + esc(a.ko || '적어 두면 다른 기계에서도 이어서 할 수 있다.') + '</p>' +
      '<div class="rowbtns"><button id="keycopy">베껴 두기</button></div>' +
      '<h3>다른 기계의 방주로</h3>' +
      '<p class="desc">다른 데서 적어 둔 열쇠를 넣는다. 지금 이 방주로 돌아오려면 위의 열쇠를 먼저 적어 둔다.</p>' +
      '<div class="keyrow"><input id="keyin" maxlength="9" autocomplete="off" autocapitalize="characters" spellcheck="false"' +
        ' placeholder="열쇠 여섯 글자" aria-label="복구 코드"><button id="keygo">이어 하기</button></div>' +
      '<p class="keyerr" id="keyerr"></p>';
    $('#keycopy').addEventListener('click', () => {
      const txt = a.pretty || a.code;
      try {
        navigator.clipboard.writeText(txt).then(() => toast('베꼈다 — ' + txt), () => toast('길게 눌러 베낀다'));
      } catch (e) { toast('길게 눌러 베낀다'); }
    });
    const go = async () => {
      const v = $('#keyin').value.trim(), err = $('#keyerr');
      err.className = 'keyerr'; err.textContent = '';
      if (!v) { err.textContent = '열쇠를 적는다'; return; }
      $('#keygo').disabled = true;
      try {
        const r = await api('/api/account/restore', { code: v });
        if (r.uid === uid) { err.className = 'keyerr keyok'; err.textContent = '이미 이 방주다.'; return; }
        try { localStorage.setItem('ark_uid', r.uid); }
        catch (e) { err.textContent = '이 브라우저에는 저장할 수 없다(사생활 보호 창?)'; return; }
        err.className = 'keyerr keyok'; err.textContent = r.ko || '돌아왔다.';
        setTimeout(() => location.reload(), 900);
      } catch (e) {
        // 429 = 잠금(틀린 열쇠를 여러 번), 400 = 형식, 404 = 없는 열쇠. 셋은 할 일이 다르다
        err.textContent = e.status === 429 ? '잠시 뒤 다시 — ' + (e.message || '너무 여러 번 틀렸다')
          : e.status === 400 ? '열쇠 형식이 다르다 — ' + (e.message || '여섯 글자')
          : (e.message || '열리지 않았다');
      }
      finally { const b = $('#keygo'); if (b) b.disabled = false; }
    };
    $('#keygo').addEventListener('click', go);
    $('#keyin').addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
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
      if (q && wx >= q.x && wx <= q.x + q.w && wy >= q.y && wy <= q.y + q.h) return s;
    }
    return null;
  }

  let drag = null;
  // 두 손가락 = 핀치 줌(폰). 손가락이 둘이 되는 순간 드래그·집기는 취소된다
  const touches = new Map();
  let pinch = null;
  function pinchState() {
    const [a, b] = [...touches.values()];
    return { d: Math.hypot(a.x - b.x, a.y - b.y), cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 };
  }
  cv.addEventListener('pointerdown', (e) => {
    camTo = null;                                // 손이 닿으면 자동 이동은 멈춘다
    const r = cv.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top;
    pointer = { x: px, y: py };
    touches.set(e.pointerId, { x: px, y: py });
    if (touches.size === 2) { pinch = pinchState(); drag = null; dragging = null; cv.classList.remove('dragging'); return; }
    const p = hitAt(px, py, 'person');
    drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: 0, person: p || null };
    cv.setPointerCapture(e.pointerId);
    if (!p) cv.classList.add('dragging');
  });
  cv.addEventListener('pointermove', (e) => {
    const r = cv.getBoundingClientRect();
    pointer = { x: e.clientX - r.left, y: e.clientY - r.top };
    if (touches.has(e.pointerId)) touches.set(e.pointerId, { x: pointer.x, y: pointer.y });
    if (pinch && touches.size === 2) {
      const n = pinchState();
      if (pinch.d > 0) zoomAt(n.cx, n.cy, n.d / pinch.d);
      cam.x -= (n.cx - pinch.cx) / cam.z; cam.y -= (n.cy - pinch.cy) / cam.z; clampCam();
      pinch = n; return;
    }
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
    clampCam();
  });
  cv.addEventListener('pointerup', (e) => {
    touches.delete(e.pointerId);
    if (pinch) { if (touches.size < 2) pinch = null; drag = null; return; }
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
    const sh = hitAt(px, py, 'shelf');
    if (sh) { toast(shelfLine(sh.item)); openPanel(s != null ? s : shelfRoomSlot()); return; }
    if (s != null) { openPanel(s); return; }
    if (hitAt(px, py, 'hall')) { openHallPanel(); return; }
    const sc = hitAt(px, py, 'sealed');
    if (sc) { openSealed(sc.cell); return; }
    closePanel();
  });
  cv.addEventListener('pointercancel', (e) => { touches.delete(e.pointerId); pinch = null; drag = null; dragging = null; cv.classList.remove('dragging'); });
  cv.addEventListener('wheel', (e) => {
    e.preventDefault(); camTo = null;
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
  $('#keybtn').addEventListener('click', openAccount);
  $('#scanbtn').addEventListener('click', openScan);
  $('#scanClose').addEventListener('click', closeScan);
  $('#manualBtn').addEventListener('click', () => handleCode($('#manual').value));
  $('#manual').addEventListener('keydown', (e) => { if (e.key === 'Enter') handleCode(e.target.value); });
  $('#samples').addEventListener('click', (e) => { const b = e.target.closest('button[data-c]'); if (b) handleCode(b.dataset.c); });
  $('#picker').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-cat]'); if (b && pendingCode) handleCode(pendingCode, b.dataset.cat || null);
  });
  $('#shelfBtn').addEventListener('click', toShelf);
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#scan').hidden) closeScan(); });
  let lastPortrait = null;
  window.addEventListener('resize', () => {
    resize(); orient();
    const p = isPortrait();                          // 돌렸을 때만 다시 맞춘다(창 크기만 바뀌면 보던 자리 유지)
    if (lastPortrait !== null && p !== lastPortrait && ark) fit();
    lastPortrait = p;
  });
  // 폰 세로: 가로로 돌려 달라는 부드러운 안내. 닫으면 세로 그대로 쓸 수 있다(옛 세로 배치가 남아 있다)
  function orient() {
    const el = $('#rotate'); if (!el) return;
    let dismissed = false; try { dismissed = sessionStorage.getItem('ark_rotate_ok') === '1'; } catch (e) { /* 저장 못 해도 */ }
    el.hidden = !(isPortrait() && view.w <= 560) || dismissed || !!el._ok;
  }
  const rb = $('#rotateOk');
  if (rb) rb.addEventListener('click', () => { $('#rotate')._ok = true; try { sessionStorage.setItem('ark_rotate_ok', '1'); } catch (e) { /* */ } orient(); fit(); });

  // 다른 화면(index)과 같은 규약: 밖에서 쓸 수 있게 몇 개만 연다.
  // slotBox·peopleHits 는 자동 검수(Playwright)가 캔버스를 정확히 누르기 위한 읽기 전용 창이다.
  window.ARKBASE = {
    reload: () => load(false), refreshRaid, fit, uid,
    slotBox: (s) => { const q = rectOf(s); return q ? { x: sx(q.x), y: sy(q.y), w: q.w * cam.z, h: q.h * cam.z } : null; },
    // ★ S12-B 검수용: 맵·카메라·프레임 시간
    map: () => ({ id: window.ArkMap.id, provisional: MAP().provisional, world: MAP().world, layers: Object.keys(layerImgs),
                  slots: Array.from({ length: slots }, (_, i) => { const c = cellOf(i); return c ? { slot: i, cell: c.id, storey: c.storey, col: c.col } : null; }).filter(Boolean),
                  trenchY: zoneY(TRENCH_M), layoutTrenchY: MAP().depth.trenchY }),
    cam: () => Object.assign({}, cam, { zmin: zMin() }),
    sil: () => silDbg,                                 // ★ 검수용: 지금 다가오는 실루엣의 세계 x
    fps: () => { const a = fpsLog.slice(-120); const m = a.reduce((x, y) => x + y, 0) / Math.max(1, a.length); const b = workLog.slice(-120), wm = b.reduce((x, y) => x + y, 0) / Math.max(1, b.length);
      return { avgMs: +m.toFixed(2), fps: +(1000 / m).toFixed(1), worstMs: Math.max(...a), drawMs: +wm.toFixed(2), drawWorstMs: +Math.max(...b).toFixed(2) }; },
    zoomBy: (k) => zoomAt(view.w / 2, view.h / 2, k), panTo: (x, y) => { cam.x = x; cam.y = y; clampCam(); },
    hallBox: () => { const h = hallRect(); return { x: sx(h.x), y: sy(h.y), w: h.w * cam.z, h: h.h * cam.z }; },
    peopleHits: () => hits.filter(h => h.kind === 'person').map(h => ({ id: h.id, name: h.name, from: h.from,
      cx: h.x + h.w / 2, cy: h.y + h.h / 2 })),
    shelfHits: () => hits.filter(h => h.kind === 'shelf').map(h => ({ slot: h.item.slot, prop_id: h.item.prop_id,
      x: h.x, y: h.y, w: h.w, h: h.h })),
    shelfRoomSlot: () => shelfRoomSlot(),
    focusShelf: (s) => focusShelf(s), openScan: () => openScan(), openAccount: () => openAccount(),
    // ★ S11-C 검수용 읽기 창: 지금 움직이는 사람·그 자세·엘리베이터 칸 층·지금까지 그린 클립
    moving: () => { const t = performance.now() / 1000;
      return traffic.moving(t).map(id => Object.assign({ id }, traffic.at(id, t))); },
    car: () => traffic.cars().map(id => ({ id, floor: traffic.car(id, performance.now() / 1000) })),
    clips: () => Object.assign({}, usedClips),
    moveLog: () => moveLog.slice(),                    // 엘리베이터 배차 기록(시각은 performance.now 초)
  };

  // 맵(layout.json)이 먼저, 상태가 나중. 맵 파일이 없어도 잠정 배치로 바로 돈다(m5map.js)
  resize(); orient(); raf = requestAnimationFrame(frame);
  window.ArkMap.ready.then(() => {
    loadLayers(); initLife(); loadCar();
    // 플레이트·덧그림은 미리 받아 둔다 — 물을 뺀 순간 첫 프레임부터 그림으로 보이게
    new Set(Object.values(PLATE_OF)).forEach(id => { plateImg('room_plate_' + id + '_lit.png'); plateImg('room_plate_' + id + '_dark.png'); });
    ['damage_crack1.png', 'damage_crack2.png', 'damage_crack3.png', 'room_flood.png'].forEach(plateImg);
    overlayImg('cell_plan'); overlayImg('cell_flood');
    traffic.setGraph(MOVE_ADAPTER.graph());
    fit(); lastPortrait = isPortrait(); load(true);
  });
})();
