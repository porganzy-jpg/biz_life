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
    { m0: -1e4, m1: -100, ko: '광층',    note: '못 가는 곳' },
    { m0: -100, m1: -45,  ko: '박광층',  note: '그림자가 비치는 층' },
    { m0: -45,  m1: TRENCH_M, ko: '무광층',  note: '돔이 있는 층' },
    { m0: TRENCH_M, m1: TRENCH_DEEP_M, ko: '해구 문턱', note: '여기부터 값이 달라집니다' },
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
  const STAGE_LABEL = { sound: '소리', silhouette: '실루엣', contact: '접촉', done: '지나감' };

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
  // ── 문장 자리표시 채우기(S13). ui_moments·creatures 대사·하루 마감에 {room}·{creature}·{name}·{total}·{family}… 가 남아 올 수 있다.
  //    vars 에 있으면 그 값, 없으면 지금 습격의 방·생물 이름, 그래도 없으면 **빈칸**. 화면에 중괄호가 그대로 나가지 않게
  //    esc·plain·toast 가 모두 이 길을 지난다(다른 텍스트에 중괄호가 쓰일 일은 없다)
  const PH = /\{([a-z_]+)\}/g;
  function phDefaults() {
    const r = (typeof cb !== 'undefined' && cb && cb.raid) || null;
    return { room: r && r.target_room, creature: r && r.creature && r.creature.name };
  }
  // S18: 조사 고르기(플레이테스트 버그 9 「식량창고을」). 앞말 마지막 글자의 받침으로 을/를·이/가·은/는·과/와·으로/로·이나/나·아/야·이랑/랑.
  //      숫자는 읽는 소리로(1 일·3 삼·6 육·7 칠·8 팔·0 영), 닫는 따옴표·괄호는 건너뛰고 본다. 「으로」는 ㄹ 받침이면 「로」
  const JOSA = { '을': ['을', '를'], '를': ['을', '를'], '이': ['이', '가'], '가': ['이', '가'], '은': ['은', '는'], '는': ['은', '는'],
                 '과': ['과', '와'], '와': ['과', '와'], '으로': ['으로', '로'], '로': ['으로', '로'], '이나': ['이나', '나'], '나': ['이나', '나'],
                 '아': ['아', '야'], '야': ['아', '야'], '이랑': ['이랑', '랑'], '랑': ['이랑', '랑'] };
  function jongOf(word) {                             // 0 받침 없음 · 1 받침 · 2 ㄹ 받침
    const w = String(word == null ? '' : word).replace(/[\s'"」』〉》)\]>.,!?·…]+$/, '');
    const ch = w.charAt(w.length - 1); if (!ch) return 0;
    const c = ch.charCodeAt(0);
    if (c >= 0xAC00 && c <= 0xD7A3) { const j = (c - 0xAC00) % 28; return j === 0 ? 0 : (j === 8 ? 2 : 1); }
    if (ch >= '0' && ch <= '9') return [1, 2, 0, 1, 0, 0, 1, 2, 2, 0][+ch];
    if (/[lr]/i.test(ch)) return 2;
    if (/[mnk]/i.test(ch)) return 1;
    return 0;
  }
  function josa(word, p) {
    const pair = JOSA[p], w = String(word == null ? '' : word);
    if (!pair) return w + (p || '');
    const j = jongOf(w);
    return w + (pair[0] === '으로' ? (j === 1 ? '으로' : '로') : (j ? pair[0] : pair[1]));
  }
  // 자리표시 바로 뒤에 붙은 조사는 채운 말에 맞춰 바꾼다({room}을 → 「식량창고를」이 아니라 받침에 따라). 말이 비면 조사도 뺀다
  const PH_JOSA = /\{([a-z_]+)\}(으로|이랑|이나|을|를|이|가|은|는|과|와|로|랑|나|아|야)(?=[\s,.!?·…」』)'"]|$)/g;
  function fillText(str, vars) {
    const t = String(str == null ? '' : str);
    if (t.indexOf('{') < 0) return t;
    const d = phDefaults();
    const val = (k) => { const v = vars && vars[k] != null ? vars[k] : d[k]; return v == null ? '' : String(v); };
    return t.replace(PH_JOSA, (m, k, pt) => { const v = val(k); return v ? josa(v, pt) : ''; })
            .replace(PH, (m, k) => val(k))
            .replace(/\s{2,}/g, ' ').replace(/ ([,.])/g, '$1');
  }
  const esc = (s) => fillText(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let ark = null, catalog = {}, slots = 10, floorSlots = 2, spots = [];
  let cb = null;                                      // ark.combat
  let sel = null;                                     // {slot} 선택된 칸
  let carry = null;                                   // 집어 든 사람 {id,name,role,from}
  let dragging = null;                                // 드래그 중인 사람(포인터를 따라다닌다)
  let pointer = { x: 0, y: 0 };
  let hits = [];                                      // 이번 프레임의 사람 히트박스
  let lastStage = null, lastRaidId = null, lastBarH = 0;
  let cam = { x: 0, y: 220, z: 1 }, view = { w: 0, h: 0, dpr: 1 };

  const braceLog = { toasts: 0, canvas: 0, samples: [] };
  (() => {                                             // 캔버스 글자도 센다(검수용, 비용은 indexOf 한 번)
    const ft = CanvasRenderingContext2D.prototype.fillText;
    CanvasRenderingContext2D.prototype.fillText = function (t, ...a) {
      if (typeof t === 'string' && t.indexOf('{') >= 0) { braceLog.canvas++; if (braceLog.samples.length < 10) braceLog.samples.push(t); }
      return ft.call(this, t, ...a);
    };
  })();
  // S18: 화면 줄(큐). 밤사이 → 귀환 → 만남 → 하루 마감 같은 큰 창은 하나씩, 그동안의 방송(say)은 뒤로 미룬다.
  //      show(done) 는 창을 띄우고 닫힐 때 done() 을 부른다. 사용자가 누른 일의 토스트(toast)는 미루지 않는다
  const modalQ = [], heldSay = [];
  let modalBusy = null, qReady = false;
  function enqueue(tag, show, first) {             // first: 줄 맨 앞(「밤사이」는 언제나 먼저)
    if (modalBusy && modalBusy.tag === tag) return;
    if (modalQ.some(x => x.tag === tag)) return;
    if (first) modalQ.unshift({ tag, show }); else modalQ.push({ tag, show });
    setTimeout(pumpQ, 0);                              // 같은 순간에 들어온 것끼리는 「first」가 앞에 서게 한 박자 늦춘다
  }
  let pumpT = 0;
  function pumpQ() {
    if (modalBusy || !qReady) return;
    // 찍기 창·끌기 중에는 다음 창을 띄우지 않는다(만남 카드가 찍기 위에 덮이던 것) — 닫힌 뒤에
    if ((modalQ.length || heldSay.length) && (!$('#scan').hidden || dragging)) { clearTimeout(pumpT); pumpT = setTimeout(pumpQ, 1200); return; }
    const it = modalQ.shift();
    if (!it) { flushSay(); return; }
    let done = false;
    modalBusy = it;
    const fin = () => { if (done) return; done = true; modalBusy = null; qLog.push('done ' + it.tag); setTimeout(pumpQ, 450); };
    qLog.push('show ' + it.tag);
    try { it.show(fin); } catch (e) { fin(); }
  }
  function flushSay() {
    if (!heldSay.length) return;
    const l = heldSay.shift(); toast(l);
    if (heldSay.length) setTimeout(() => { if (!modalBusy) flushSay(); }, 3200);
  }
  function say(m) {                                   // 관리실 방송 한 줄 — 큰 창이 떠 있으면 닫힌 뒤에
    if (!m) return;
    if (modalBusy || modalQ.length || !qReady) { if (heldSay.indexOf(m) < 0) heldSay.push(m); return; }
    toast(m);
  }
  const qLog = [];
  // 패널이 닫히거나(숨김) 다른 내용으로 바뀌면 그 창은 끝난 것
  function whenPanelGone(cb) {
    const pn = $('#panel'), pb = $('#panelBody'), first = pb.firstChild;
    const mo = new MutationObserver(() => { if (pn.hidden || !first || !pb.contains(first)) { mo.disconnect(); cb(); } });
    mo.observe(pn, { attributes: true, attributeFilter: ['hidden'] });
    mo.observe(pb, { childList: true });
  }
  function toast(m) {
    m = fillText(m);
    if (String(m).indexOf('{') >= 0) { braceLog.toasts++; braceLog.samples.push(m); }
    const t = $('#toast'); t.textContent = fillText(m); t.classList.add('on');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), 2600);
  }

  async function api(path, body) {
    const r = await fetch(path, body
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ uid }, body)) }
      : undefined);
    let j = {};
    try { j = await r.json(); } catch (e) { j = {}; }
    if (!r.ok) { const er = new Error(j.detail || r.statusText || '연결이 끊겼습니다'); er.status = r.status; throw er; }
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
  const SIDE_STRIDE_ADULT = 16, SIDE_LOOP_ADULT = 0.8, SRC_PPM = 27.5;
  const WALK_MPS = SIDE_STRIDE_ADULT / SIDE_LOOP_ADULT / SRC_PPM;
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
      return { walkSpeed: WALK_MPS, shafts: L.shafts.map(s => ({ id: s.id, x: s.cx / PX_PER_M, floors: [HALL_FLOOR, last],
               cap, secPerFloor: 0.9, door: 0.5, home: 0,
               doorGap: (s.w / 2) / PX_PER_M + 0.3 })) };            // 승강로 바로 바깥에 줄을 선다
    },
    nodeOf(where, i, n) {                            // where: slot 번호 | 'hall' | 'out'
      if (where === 'out') {                           // S15: 밖 = 원정. 입구 해치까지 걸어 나간다
        const E = MAP().entrance;
        if (E && E.hatch) return { floor: HALL_FLOOR, x: (E.hatch.x - 20 - i * 30) / PX_PER_M };
        const o = outsideRect(); return { floor: 0, x: (o.x + o.w * (i + 1) / (n + 1)) / PX_PER_M };
      }
      if (where === 'hall') { const h = hallRect(); return { floor: HALL_FLOOR, x: (h.x + h.w * (i + 1) / (n + 1)) / PX_PER_M }; }
      if (typeof where === 'string' && where.indexOf('pod:') === 0) {
        const sp = podSpot(+where.slice(4)); if (sp) return { floor: HALL_FLOOR, x: sp.x / PX_PER_M };
      }
      const r = rectOf(where);
      if (!r) { const h = hallRect(); return { floor: HALL_FLOOR, x: (h.x + h.w / 2) / PX_PER_M }; }
      return { floor: r.storey, x: standX(r, i, n) / PX_PER_M };
    },
    toWorld(floor, x) {                              // floor 는 소수도 받는다(엘리베이터 안)
      const f0 = Math.floor(floor), f1 = Math.ceil(floor), y0 = floorLine(f0);
      return { x: x * PX_PER_M, y: y0 + (floorLine(f1) - y0) * (floor - f0) };
    },
  };
  // movement.js 가 없으면(로드 잘 안 됐습니다) 이동 없이 예전처럼 자리에 바로 나타난다 — 화면은 멈추지 않는다
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
    return { top: phone ? 40 : 46, bottom: 0, left: 0, right: 0 };     // S12-B2: 고정 UI 는 위 한 줄뿐
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
    const L = MAP(), d = L.dome, E = L.entrance, ins = uiInset();
    if (isPortrait()) {
      cam.z = Math.max(zMin(), Math.min(ZMAX, READ_Z));
      cam.x = L.glass ? L.glass.cx : d.x + d.w / 2; cam.y = d.floor_y + 120; clampCam(); return;
    }
    // S15-0: 처음 보는 사람이 볼 것 = 입구 포드의 식구들 + 돔(PC) / 포드 + 식량창고와 그 안내(폰).
    // 그 상자가 여백까지 다 들어오는 줌(판독 하한 READ_Z 를 넘지 않게)으로 맞추고 상자 가운데에 둔다
    const box = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
    const add = (x0, y0, x1, y1) => { box.x0 = Math.min(box.x0, x0); box.y0 = Math.min(box.y0, y0); box.x1 = Math.max(box.x1, x1); box.y1 = Math.max(box.y1, y1); };
    const phone = view.h <= 500;
    if (E && E.pod) add(E.pod.x0 - 30, E.pod.y0 - 20, E.pod.x1 + 40, E.pod.y1 + 10);
    if (phone) {
      const r = rectOf(DOME_FLOOR * floorSlots);             // 시작 방(식량창고) + 그 아래 「한 분만」 안내
      if (r) add(r.x + r.w * 0.2, r.y - 10, r.x + r.w, r.y + r.h + 46);
    } else {
      const h = hallRect();
      add(h.x, d.y + 40, h.x + h.w, h.y + h.h + 40);
      const r = rectOf(DOME_FLOOR * floorSlots);
      if (r) add(r.x, r.y, r.x + r.w, r.y + r.h + 46);
    }
    if (!isFinite(box.x0)) { add(d.x, d.y, d.x + d.w, d.floor_y + 400); }
    const availW = view.w - 24, availH = view.h - ins.top - 74;    // 아래 74 = 찍기·≡ 줄
    cam.z = Math.max(zMin(), Math.min(ZMAX, READ_Z, availW / (box.x1 - box.x0), availH / (box.y1 - box.y0)));
    cam.x = (box.x0 + box.x1) / 2;
    cam.y = (box.y0 + box.y1) / 2 + ((ins.top - 74) / 2) / cam.z * -1;
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
    const barW = 0;                                   // S12-B2: 습격은 위 가운데 띠 — 옆을 덮지 않는다
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
    // 바위 칸으로 가는 굴(아직 파지 못완료 · 서버 칸이 없다. 칸 자체는 drawSealed). 절벽 그림에는 이미 있다
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
    // S12-B2(사용자 결정): 서버는 한 층 2칸 그대로. 이 칸들은 2막 뒤에 열린다 — 「곧 되찾을 칸」처럼 보이면 안 된다.
    // 점선 없이, 더 어둡게, 글자도 낮게
    if (c.kind === 'rock') {
      if (!layerReady('mid')) { ctx.fillStyle = '#1a130c'; ctx.fillRect(x, y, w, h); }
      ctx.fillStyle = 'rgba(6,4,2,0.45)'; ctx.fillRect(x, y, w, h);
    } else {
      const fl = overlayImg('cell_flood');
      if (fl) { ctx.fillStyle = 'rgba(3,14,19,0.45)'; ctx.fillRect(x, y, w, h); ctx.drawImage(fl, x, y, w, h); }
      else if (!drawPlate('room_flood.png', x, y, w, h, 0.9)) { ctx.fillStyle = '#082028'; ctx.fillRect(x, y, w, h); }
      ctx.fillStyle = 'rgba(1,6,9,0.62)'; ctx.fillRect(x, y, w, h);     // 지을 수 있는 칸보다 확실히 가라앉게
    }
    if (cam.z > 0.3) {
      ctx.font = (11 * Math.min(1.6, cam.z * 2)) + 'px "Noto Sans KR",sans-serif';
      ctx.fillStyle = c.kind === 'rock' ? 'rgba(170,140,100,0.38)' : 'rgba(140,190,195,0.34)';
      ctx.textBaseline = 'middle';
      ctx.fillText(SEALED_KO[c.kind === 'rock' ? 'rock' : 'tower'], x + 14 * cam.z, y + 24 * cam.z);
      ctx.textBaseline = 'alphabetic';
    }
    hits.push({ kind: 'sealed', cell: c, x, y, w, h });
  }
  const SEALED_KO = { tower: '물이 너무 깊게 차 있어서, 지금은 손댈 수 없습니다', rock: '아직 파지 못한 바위' };
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
        ctx.fillText('물에 잠김', ix + 14 * cam.z, iy + 24 * cam.z);
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
    if (target === slot && cb.raid && cb.raid.stage !== 'done' && !cb.raid.resolved) {   // 노려지는 방 — 천천히 깜빡(UI_SIMPLE §4)
      const a = 0.55 + 0.45 * Math.sin(t / 420);
      edge = 'rgba(176,58,36,' + a.toFixed(3) + ')'; ew = 9 + 5 * a;
    }
    if (picked) {                                                         // 놓을 수 있는 자리
      const full = (people || []).length >= capOf(slot);
      edge = full ? '#6b3b33' : '#8fbf7a'; ew = 9;
    }
    ctx.strokeStyle = edge;
    ctx.lineWidth = Math.max(1.5, ew * cam.z);
    ctx.strokeRect(ix, iy, iw, ih);

    drawShelf(slot, ix, iy, iw, ih, lit);
    drawRoomAnim(slot, ix, iy, iw, ih, t);
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
  let CLIPS = { rows: { idle: 0 }, frames: { idle: 2 }, anim_seconds: { idle: 1.24 }, room_work: {}, stride: {} };
  fetch('/static/art/chars/front/p2/meta.json').then(r => (r.ok ? r.json() : null)).then(j => {
    if (!j || !j.rows) return;
    const stride = {};                                  // S12-C: 옆걸음 보폭(원본 px / 한 바퀴) — 발이 미끄러지지 않게
    Object.entries(j.s12_rows || {}).forEach(([k, v]) => { if (v && v.stride_src_px_per_loop) stride[k] = v.stride_src_px_per_loop; });
    CLIPS = { rows: j.rows, frames: j.frames || {}, anim_seconds: j.anim_seconds || {}, room_work: j.room_work || {}, stride };
  }).catch(() => {});
  // 바닥 걷기 속도 = 보폭 × 배율 / 초(meta side_speed). 어른 walk_side 16 원본px / 0.8 s = 20 원본px/s
  // = 20 / 27.5 m/s ≈ 0.73 m/s(×3 화면에서 60 px/s). 이동 시간표(movement.js)는 이 속도로 짠다.
  // 아이는 보폭 12 라 같은 속도에서 한 바퀴를 0.6 s 로 줄여 돌린다(발이 바닥에 붙는다)
  // (SIDE_STRIDE_ADULT·WALK_MPS 는 이동 어댑터가 먼저 쓰므로 파일 위쪽 TARGET_PPM 옆에 있다)
  // S12-B3: 바닥 걷기 = walk_side(오른쪽이 원본, 왼쪽은 반전) · 들고 걷기 = carry_side · 방 밖 일 = work_34 ·
  // 홀에서 가끔 idle_glance. 정면 walk·work·carry 는 사슬 끝에 남는다(시트가 옛것이면 그쪽으로 내려간다)
  const POSE_CHAIN = {
    walk: ['walk_side', 'walk'], carry: ['carry_side', 'carry_34', 'walk_side', 'walk'],
    elevator_wait: ['elevator_wait'], elevator_ride: ['elevator_ride', 'elevator_wait'],
    glance: ['idle_glance'], hurt: ['hurt'], sit: ['sit'], lounge: ['rest_lounge'], rest: [], idle: [],
  };
  const SIDE_CLIPS = { walk_side: 1, carry_side: 1 };
  function clipFor(s, pose, roomId) {
    const rw = CLIPS.room_work[roomId];
    const cand = (pose === 'work' ? [rw, 'work_' + roomId, 'work_34', 'work'].filter(Boolean) : (POSE_CHAIN[pose] || [])).concat('idle');
    for (const c of cand) {
      const row = CLIPS.rows[c];
      if (row == null) continue;
      if ((row + 1) * s.spec.cell > s.img.naturalHeight) continue;      // meta 는 새것, 시트는 아직 옛것
      const fr = Math.max(1, Math.min(s.spec.cols, CLIPS.frames[c] || 1));
      return { name: c, row, frames: fr, ms: ((CLIPS.anim_seconds[c] || 1) * 1000) / fr, side: !!SIDE_CLIPS[c] };
    }
    return { name: 'idle', row: 0, frames: 2, ms: 620 };
  }
  const usedClips = {}, flipLog = {};                 // 검수용: 그린 클립·반전해 그린 클립                               // 검수용: 지금까지 실제로 그린 클립 이름

  // opts: {face: -1 왼쪽 / 1 오른쪽(옆걸음), mirror: true(작업 행 셀 반전), frame: 고정 프레임, glance: 홀에서 둘러보기}
  function drawPerson(p, px, floorY, t, i, scale, lit, pose, roomId, opts) {
    opts = opts || {};
    const k = (scale == null ? 1 : scale);
    const moving = pose === 'walk' || pose === 'carry' || pose === 'elevator_ride';
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
      // 옆걸음: 아이는 보폭이 작아 같은 속도에서 더 빨리 돈다(발 미끄럼 0)
      if (clip.side && p.role === 'kid') {
        const st = CLIPS.stride[clip.name] || {}, ad = st.adult || SIDE_STRIDE_ADULT, kd = st.kid || 12;
        clip.ms *= kd / ad;
      }
      usedClips[clip.name] = (usedClips[clip.name] || 0) + 1;
      const frame = opts.frame != null ? Math.min(clip.frames - 1, opts.frame) : Math.floor(t / clip.ms + i) % clip.frames;
      // 반전: 옆걸음은 왼쪽으로 갈 때, 작업 행은 설비가 오른쪽에 와야 할 때. 축 = 셀 가운데, 발 기준선 그대로
      const flip = (clip.side && opts.face < 0) || (!clip.side && opts.mirror && /^work_|^carry_34$/.test(clip.name));
      try {
        const sheet = sp.pixel ? tintedSheet(s, p.role, lit === false ? TINT_DARK : TINT_LIT) : s.img;
        const sm = ctx.imageSmoothingEnabled;
        if (sp.pixel) ctx.imageSmoothingEnabled = false;
        // 2.5D 조건 ③ — 발밑 접지 그림자. 없으면 떠 있는 것처럼 보인다
        ctx.fillStyle = 'rgba(12,10,8,0.42)';
        ctx.beginPath(); ctx.ellipse(px, floorY, cw * 0.22, cw * 0.055, 0, 0, 6.2832); ctx.fill();
        const cell = sp.pixel ? clip.row * sp.cols + frame : sp.idle * sp.cols + frame;
        if (flip) {
          ctx.save(); ctx.translate(px, 0); ctx.scale(-1, 1);
          ctx.drawImage(sheet, (cell % sp.cols) * sp.cell, Math.floor(cell / sp.cols) * sp.cell, sp.cell, sp.cell,
                        -cw / 2, floorY - base + bob, cw, cw);
          ctx.restore();
          flipLog[clip.name] = (flipLog[clip.name] || 0) + 1;
        } else {
          ctx.drawImage(sheet, (cell % sp.cols) * sp.cell, Math.floor(cell / sp.cols) * sp.cell, sp.cell, sp.cell,
                        px - cw / 2, floorY - base + bob, cw, cw);
        }
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
  const CARRY_ROOMS = { storage: 1, pantry: 1, workshop: 1 };
  function lifeAt(p, slot, t, step) {
    const now = t / 1000, room = (ark.rooms || []).find(r => r.slot === slot);
    let L = window.ArkMove ? ArkMove.roomLife(p.id, now) : { pose: 'work', dx: 0 };
    const since = now - traffic.arrivedAt(p.id);
    const ramp = since < 0 ? 0 : Math.min(1, since / 1.2);
    const spread = Math.min(step * 0.3, 48 * cam.z);
    let pose = L.pose, face = L.facing || 0;
    if (ramp < 1 && Math.abs(L.dx) * spread > 2) { pose = 'walk'; face = L.dx > 0 ? -1 : 1; }   // 제자리로 걸어 들어온다
    if (pose === 'walk' && room && CARRY_ROOMS[room.id]) pose = 'carry';     // 창고·식량창고·공방에서는 상자를 안고 옮긴다
    if (!lightOf(slot)) pose = 'idle';                         // 불 꺼진 방에서는 손을 놓고 기다린다
    if (p.injured) pose = 'hurt';
    return { pose, off: L.dx * spread * ramp, room: room ? room.id : '', face };
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
      // 작업 행(7~16)은 설비가 왼쪽인 것이 원본. 방의 오른쪽 절반에 선 사람은 셀째 반전 — 설비가 가까운 벽 쪽에 온다
      const mirror = people.length > 1 && (i + 0.5) / people.length > 0.5;
      const box = drawPerson(p, px, floorY, t, i, 1, lightOf(slot), life.pose, life.room, { face: life.face, mirror });
      if (carry && carry.id === p.id) {                      // 집어 든 표시
        ctx.strokeStyle = '#f0b055'; ctx.lineWidth = Math.max(1, 2 * cam.z);
        ctx.strokeRect(px - box.w / 2 - 3, floorY - box.h - 6, box.w + 6, box.h + 10);
      }
      hits.push({ kind: 'person', id: p.id, name: p.name, role: p.role, from: slot,
                  x: px - box.w / 2 - 6, y: floorY - box.h - 8, w: box.w + 12, h: box.h + 14 });
    });
  }

  const KO_N = (n) => (['', '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉', '열'][n] || String(n));
  const labelFont = (base) => Math.max(10.5, Math.min(15, base * cam.z * 2.2));
  function drawHall(t) {
    // 홀: 배치되지 않은 사람이 모이는 돔 안. 여기도 **빈 방이 아니다**
    const h = hallRect();
    const x = sx(h.x), y = sy(h.y), w = h.w * cam.z, hh = h.h * cam.z;
    const list = (ark.residents_list || []).filter(r =>
      (!cb || cb.stations[r.id] === undefined) && !(cb && cb.outside.indexOf(r.id) >= 0) && podSeat[r.id] == null);
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
      if (list.length) ctx.fillText('홀에 ' + KO_N(list.length) + ' 분 계십니다', x + 8, y + 16);   // 0 명이면 쓰지 않는다
    }
    const floorY = sy(MAP().dome.floor_y), step = w / (list.length + 1);
    list.forEach((p, i) => {
      if (dragging && dragging.id === p.id) return;
      if (movingNow[p.id]) return;
      const px = x + step * (i + 1);
      const box = drawPerson(p, px, floorY, t, i, 1, !!(cb && cb.power_on), glanceAt(p.id, t) ? 'glance' : 'idle', null,
                             { frame: glanceFrame(p.id, t) });
      if (carry && carry.id === p.id) {
        ctx.strokeStyle = '#f0b055'; ctx.lineWidth = Math.max(1, 2 * cam.z);
        ctx.strokeRect(px - box.w / 2 - 3, floorY - box.h - 6, box.w + 6, box.h + 10);
      }
      hits.push({ kind: 'person', id: p.id, name: p.name, role: p.role, from: null,
                  x: px - box.w / 2 - 6, y: floorY - box.h - 8, w: box.w + 12, h: box.h + 14 });
    });
    hits.push({ kind: 'hall', x, y, w, h: hh });
  }

  // 둘러보기: 사람마다 주기 8~20 s(id 해시), 한 번에 idle_glance 한 바퀴(2.4 s)
  function hashId(id) { let h = 2166136261; for (let k = 0; k < id.length; k++) { h ^= id.charCodeAt(k); h = Math.imul(h, 16777619); } return h >>> 0; }
  function glancePhase(id, t) {
    const h = hashId(id), period = 8000 + (h % 12000), dur = ((CLIPS.anim_seconds.idle_glance || 2.4) * 1000);
    const ph = (t + (h >> 8) % period) % period;
    return ph < dur ? ph / dur : -1;
  }
  const glanceAt = (id, t) => CLIPS.rows.idle_glance != null && glancePhase(id, t) >= 0;
  function glanceFrame(id, t) { const k = glancePhase(id, t); return k < 0 ? null : Math.min(2, Math.floor(k * 3)); }
  // 포드의 사람: 자리마다 자세(sit_bench→sit · window→rest_lounge 뒷모습 · gear_rack→work_34 · lean_wall→idle+둘러보기)
  const POD_POSE = { sit_bench: 'sit', window: 'lounge', gear_rack: 'work', lean_wall: 'idle' };
  function drawPod(t) {
    const E = MAP().entrance; if (!E || !ark || !cb) return;
    const ids = Object.keys(podSeat);
    const byId = {}; (ark.residents_list || []).forEach(p => { byId[p.id] = p; });
    const lit = !!cb.power_on, picked = carry || dragging;
    const wa = E.waiting_area;
    if (picked && wa) {                               // 놓을 수 있는 자리(= 홀)로 밝힌다
      ctx.save(); ctx.setLineDash([10 * cam.z, 10 * cam.z]); ctx.strokeStyle = 'rgba(143,191,122,0.85)'; ctx.lineWidth = Math.max(1, 4 * cam.z);
      ctx.strokeRect(sx(wa.x), sy(wa.y), wa.w * cam.z, wa.h * cam.z); ctx.restore();
    }
    ids.forEach((id, i) => {
      const p = byId[id], sp = podSpot(podSeat[id]);
      if (!p || !sp || movingNow[id] || (dragging && dragging.id === id)) return;
      let pose = POD_POSE[sp.pose] || 'idle', room = null, opt = { mirror: sp.face > 0 };
      // S15 문간 활동: 수선(손)=장비 손질 · 망보기(눈)=창 · 공기 펌프(숨)=일 · 마중(담)=문 앞. 밖의 친구를 기다리는 사람은 창
      const act = K.ext.podAct && K.ext.podAct(id);
      if (act) pose = { hand: 'work', eye: 'lounge', breath: 'work', nerve: 'idle', waiting: 'lounge', kid: 'idle' }[act] || pose;
      if (pose === 'work') room = 'gear';                // work_34 로 떨어진다(방 행 없음)
      if ((sp.pose === 'lean_wall' || act === 'nerve') && glanceAt(id, t)) { pose = 'glance'; opt.frame = glanceFrame(id, t); }
      const fy = sy(sp.floor_y), px = sx(sp.x);
      const box = drawPerson(p, px, fy, t, i, 1, lit, pose, room, opt);
      podPoseLog[sp.pose] = (podPoseLog[sp.pose] || 0) + 1;
      if (act && K.ext.podLabel && cam.z > 0.3) {          // 작은 이름표(활동) — 눌러야 설명
        const lb = K.ext.podLabel(act);
        if (lb) { ctx.font = 'bold 11px "Noto Sans KR",sans-serif'; const tw = ctx.measureText(lb).width + 10;
          ctx.fillStyle = act === 'waiting' ? 'rgba(40,52,60,0.9)' : 'rgba(20,17,12,0.82)'; ctx.fillRect(px - tw / 2, fy + 4, tw, 16);
          ctx.fillStyle = act === 'waiting' ? '#bfe0e6' : '#e6d7b0'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(lb, px, fy + 12);
          ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; }
      }
      if (carry && carry.id === id) {
        ctx.strokeStyle = '#f0b055'; ctx.lineWidth = Math.max(1, 2 * cam.z);
        ctx.strokeRect(px - box.w / 2 - 3, fy - box.h - 6, box.w + 6, box.h + 10);
      }
      hits.push({ kind: 'person', id, name: p.name, role: p.role, from: null,
                  x: px - box.w / 2 - 6, y: fy - box.h - 8, w: box.w + 12, h: box.h + 14 });
    });
    // S15 손님: 비어 있는 포드 자리(없으면 해치 옆)에 앉아 기다린다. 누르면 손님 카드
    const guests = (K.ext.guests && K.ext.guests()) || [];
    if (guests.length) {
      const used = new Set(Object.values(podSeat)), spots = E.spots || [];
      const free = spots.map((sp, k) => k).filter(k => !used.has(k)).reverse();
      guests.forEach((g, gi) => {
        const sp = free[gi] != null ? spots[free[gi]] : { x: (E.hatch ? E.hatch.x - 60 : wa.x + wa.w - 40) - gi * 50, floor_y: wa.floor_y || wa.y + wa.h };
        const fy = sy(sp.floor_y), px = sx(sp.x);
        const box = drawPerson({ id: g.id, role: g.role || 'trader', name: g.name }, px, fy, t, 7 + gi, 1, lit, gi === 0 && glanceAt(g.id, t) ? 'glance' : 'idle', null,
                               { frame: glanceFrame(g.id, t) });
        ctx.font = 'bold 11px "Noto Sans KR",sans-serif'; const lb = '손님'; const tw = ctx.measureText(lb).width + 10;
        ctx.fillStyle = 'rgba(70,52,20,0.92)'; ctx.fillRect(px - tw / 2, fy + 4, tw, 16);
        ctx.fillStyle = '#ffe2a8'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(lb, px, fy + 12);
        ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
        hits.push({ kind: 'guest', id: g.id, x: px - box.w / 2 - 6, y: fy - box.h - 8, w: box.w + 12, h: box.h + 30 });
      });
    }
    // S15 봉인 상자(선반이 찼거나 아직 선반 밖): 문간 바닥 왼쪽에 무늬 찍힌 작은 상자. 누르면 상자 카드
    const boxes = (K.ext.floorBoxes && K.ext.floorBoxes()) || [];
    boxes.forEach((b, bi) => {
      const bw = Math.max(18, 40 * cam.z), bx = sx(wa.x - 80 - bi * 50), by = sy((wa.floor_y || wa.y + wa.h)) - bw * 0.78;   // 안쪽 문 바로 밖 홀 바닥(사람과 겹치지 않게)
      drawSealedBox(bx, by, bw, b, t);
      hits.push({ kind: 'box', id: b.id, x: bx - 4, y: by - 4, w: Math.max(18, 40 * cam.z) + 8, h: Math.max(18, 40 * cam.z) * 0.8 + 8 });
    });
    // S13: 문어 선물 — 하루 한 번 포드 위에 작은 방울(누르면 방송, base_collect.js)
    const gift = K.ext.gift;
    if (gift && wa) {
      const gx = sx(wa.x + wa.w * 0.5), gy = sy(wa.y) - 16 + Math.sin(t / 500) * 4, R = 20;
      const pop = Math.min(1, ((t / 1000) % 6) < 0.3 ? 1.15 : 1);
      ctx.beginPath(); ctx.arc(gx, gy, R * pop, 0, 6.2832); ctx.fillStyle = 'rgba(200,236,232,0.95)'; ctx.fill();
      ctx.strokeStyle = '#14110c'; ctx.lineWidth = 2.5; ctx.stroke();
      ctx.fillStyle = '#1a150e'; ctx.font = 'bold 12px "Noto Sans KR",sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('선물', gx, gy + 1); ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
      hits.push({ kind: 'gift', x: gx - R - 4, y: gy - R - 4, w: 2 * R + 8, h: 2 * R + 8 });
    }
    if (wa) hits.push({ kind: 'hall', x: sx(wa.x), y: sy(wa.y), w: wa.w * cam.z, h: wa.h * cam.z });   // 포드 = 홀의 일부
  }
  const podPoseLog = {};
  // 봉인 상자 한 개: 나무 상자 + 뚜껑에 갈래 무늬(이삭·물방울·엇갈린 띠·번개·깃·겹친 장·실타래·연기, 빈 원)
  function drawSealedBox(x, y, w, b, t) {
    const h = w * 0.78;
    ctx.fillStyle = '#5a3f22'; ctx.fillRect(x, y, w, h);
    ctx.fillStyle = '#7a5630'; ctx.fillRect(x, y, w, h * 0.28);
    ctx.strokeStyle = '#14110c'; ctx.lineWidth = Math.max(1, w / 20); ctx.strokeRect(x, y, w, h);
    const cx = x + w / 2, cy = y + h * 0.62, r = w * 0.22;
    ctx.strokeStyle = b.pry_ok ? '#ffd59a' : '#e6d7b0'; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = Math.max(1, w / 16);
    ctx.beginPath();
    switch (b.any ? 'blank' : b.cat) {                // 모르는 갈래는 default = 빈 원
      case 'food': for (let k = -1; k <= 1; k++) { ctx.moveTo(cx + k * r * 0.7, cy + r); ctx.lineTo(cx + k * r * 0.7, cy - r); } break;
      case 'drink': ctx.arc(cx, cy + r * 0.2, r * 0.6, 0, Math.PI); ctx.moveTo(cx - r * 0.6, cy + r * 0.2); ctx.lineTo(cx, cy - r); ctx.lineTo(cx + r * 0.6, cy + r * 0.2); break;
      case 'medical': ctx.moveTo(cx - r, cy - r); ctx.lineTo(cx + r, cy + r); ctx.moveTo(cx + r, cy - r); ctx.lineTo(cx - r, cy + r); break;
      case 'electronics': ctx.moveTo(cx - r * 0.3, cy - r); ctx.lineTo(cx + r * 0.2, cy); ctx.lineTo(cx - r * 0.2, cy); ctx.lineTo(cx + r * 0.3, cy + r); break;
      case 'stationery': ctx.moveTo(cx - r, cy + r); ctx.lineTo(cx + r, cy - r); ctx.moveTo(cx, cy); ctx.lineTo(cx + r * 0.5, cy + r * 0.3); break;
      case 'book': for (let k = 0; k < 3; k++) { ctx.moveTo(cx - r, cy - r * 0.6 + k * r * 0.6); ctx.lineTo(cx + r, cy - r * 0.6 + k * r * 0.6); } break;
      case 'apparel': ctx.arc(cx, cy, r * 0.8, 0, 6.2832); ctx.moveTo(cx + r * 0.4, cy); ctx.arc(cx, cy, r * 0.4, 0, 6.2832); break;
      case 'tobacco': for (let k = -1; k <= 1; k++) { ctx.moveTo(cx + k * r * 0.6, cy + r); ctx.quadraticCurveTo(cx + k * r * 0.6 + r * 0.4, cy, cx + k * r * 0.6, cy - r); } break;
      default: ctx.arc(cx, cy, r * 0.8, 0, 6.2832);
    }
    ctx.stroke();
    if (b.pry_ok) { ctx.fillStyle = 'rgba(255,213,154,' + (0.25 + 0.2 * Math.sin(t / 400)).toFixed(3) + ')'; ctx.fillRect(x, y, w, h); }
  }

  // 해치: 기본은 닫힘. hatchCycle() 이 약 2초 열고 물방울을 띄운 뒤 닫기(탐사대·도착 체계가 부를 자리)
  let hatchOpenUntil = 0, hatchT0 = 0;
  const hatchImgs = {};
  function hatchImg(f) {
    let h = hatchImgs[f];
    if (!h) { h = hatchImgs[f] = { img: new Image(), ok: false }; h.img.onload = () => { h.ok = h.img.naturalWidth > 0; }; h.img.src = window.ArkMap.dir + f; }
    return h.ok ? h.img : null;
  }
  function drawHatch(t) {
    const H = MAP().hatch; if (!H || !H.files) return;
    const open = t < hatchOpenUntil;
    const img = hatchImg(open ? H.files.open : H.files.closed) || hatchImg(H.files.closed);
    if (!img) return;
    const x = sx(H.x), y = sy(H.y);
    if (x > view.w || x + H.w * cam.z < 0) return;
    ctx.drawImage(img, x, y, H.w * cam.z, H.h * cam.z);
  }
  function drawBubbles2(t) {
    const B = MAP().bubbles; if (!B || t >= hatchOpenUntil) return;
    const img = hatchImg(B.file); if (!img) return;
    const fr = Math.floor((t - hatchT0) / (1000 / (B.fps || 6))) % (B.frames || 3);
    const x = sx(B.place[0] - B.anchor[0]), y = sy(B.place[1] - B.anchor[1]);
    ctx.drawImage(img, fr * B.frame_w, 0, B.frame_w, B.frame_h, x, y, B.frame_w * cam.z, B.frame_h * cam.z);
  }
  function hatchCycle(ms) {
    hatchT0 = performance.now(); hatchOpenUntil = hatchT0 + (ms || 2000);
    play('sfx_airlock_cycle.ogg', 0.5);
    return hatchOpenUntil;
  }
  function drawOutside(t) {
    // 밖에 나가 있는 사람(탑 오른 외벽 바깥, 심연 쪽). 손톱 무리의 날에만 보이고, 들이면 사라진다
    // S15: 원정 나간 사람은 그리지 않는다(바깥에 있다 — 위 한 줄의 원정 표시가 대신한다)
    const away = (K.ext.expMembers && K.ext.expMembers()) || [];
    const ids = ((cb && cb.outside) || []).filter(id => away.indexOf(id) < 0);
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
  const moverState = {};
  function drawMovers(t) {
    const now = t / 1000, ids = Object.keys(movingNow);
    if (!ids.length) return;
    const byId = {}; (ark.residents_list || []).forEach(p => { byId[p.id] = p; });
    const away = (K.ext.expMembers && K.ext.expMembers()) || [];
    ids.forEach((id, i) => {
      const p = byId[id], m = traffic.at(id, now);
      if (!p || !m || (dragging && dragging.id === id)) return;
      if (away.indexOf(id) >= 0 && m.done) return;
      const w = MOVE_ADAPTER.toWorld(m.floor, m.x);
      const st = moverState[id] || (moverState[id] = { face: 1, pose: null, since: t });
      if (m.facing) st.face = m.facing;
      if (m.pose !== st.pose) { st.prev = st.pose; st.pose = m.pose; st.since = t; }
      let pose = m.pose, opt = { face: st.face };
      // 옆걸음 → 엘리베이터 앞 정면: 갑자기 돌지 않게 고개 돌린 한 장(idle_glance f1)을 0.2 초 끼운다
      if (pose === 'elevator_wait' && st.prev === 'walk' && t - st.since < 200 && CLIPS.rows.idle_glance != null) { pose = 'glance'; opt.frame = 1; }
      drawPerson(p, sx(w.x), sy(w.y), t, i, 1, !!(cb && cb.power_on), pose, null, opt);
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
    drawLayer('entrance'); drawHatch(t);              //   입구 포드·해치(S12-B4)
    drawCliff();                                      // 겹 4 — 절벽(탑의 왼쪽 외벽을 감싼다)
    movingNow = {}; traffic.moving(t / 1000).forEach(id => { movingNow[id] = true; });
    drawSealedAll(t);
    const byslot = {}; (ark.rooms || []).forEach(r => { byslot[r.slot] = r; });
    const people = peopleBySlot();
    for (let s = 0; s < slots; s++) drawRoom(s, byslot[s], people[s], t);
    drawBubbles(t);
    drawOverRoom(t);
    drawCars(t);                                      //   승강기 칸 — 사람은 그 위에
    drawHall(t);
    drawPod(t);
    drawOutside(t);
    drawMovers(t);
    drawBubbles2(t);                                  //   해치 물방울
    drawLife(t, true);                                //   생물(z≥20)
    drawDeepDark();
    drawMotes(t);
    drawFront(t);                                     // 겹 5 — 앞(시차 1.12)
    if (carry || dragging) drawCarryNumbers();        // 끄는 동안 방마다 그 사람의 숫자 하나
    if (dragging) {                                   // 손끝에 매달린 사람
      drawPerson(dragging, pointer.x, pointer.y + 48 * cam.z, t, 0, 1, true, 'idle');
    }
    drawWords(t);
    drawLidMark(t);
    drawNudge(t);
    placeCard();
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
  // S14: 방 → 능력치 표의 정본은 서버 /api/ark stats_meta.room_stat(기획 stakes.json). 클라이언트 사본은 없앴다
  const roomStat = (id) => ((ark && ark.stats_meta && ark.stats_meta.room_stat) || {})[id] || null;
  const STAT_KO_DEF = { hand: '손', eye: '눈', breath: '숨', nerve: '담' };
  function goodStats(slot) {
    const room = (ark.rooms || []).find(r => r.slot === slot);
    const out = [];
    if (room && roomStat(room.id)) out.push(roomStat(room.id));
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
    if (!p) return '';
    const pv = movePreview(p.id, slot), t = pv && pctKo(pv.room_delta_pct);
    if (t) return '<span class="bstat' + (pv.room_delta_pct < 0 ? ' neg' : '') + '">' + esc(t) + '</span>';
    if (!p.stats) return '';
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
        (here ? ' · 지금 여기' : (full ? ' · 꽉 참' : '')) + '</small></button>';
    });
    rows.push('<button class="bopt" data-dest="hall"' +
      (cb.stations[carry.id] === undefined ? ' disabled' : '') +
      '><b>홀</b><small>돔 상부 · 아무 방도 안 지킴</small></button>');
    return '<h3>' + esc(carry.name) + ' 님 자리 옮기기</h3>' +
      (raidLive('lid') ? '<p class="rno">덮개 앞입니다. 지금 옮기시면 관문이 깨집니다. 그대로 두시려면 그분을 한 번 더 눌러 주세요.</p>' : '') +
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
      statRows(p, slot) +
      (K.ext.wishFor ? K.ext.wishFor(p) : '');   // S13: 주민의 바람(/api/wishes)
  }

  // 패널이 습격 막대 아래에서 열리게 한다(데스크톱). 둘이 겹치면 둘 다 안 읽힌다
  function placePanel() {
    const bar = $('#raidbar'), pan = $('#panel');
    // S12-B2: 패널(「자세히」)은 위 한 줄 아래에서 연다. 습격 카드가 열려 있으면 접는다
    pan.classList.remove('left');
    const desk = view.w > 560 && view.h > 500;
    pan.style.top = desk ? '56px' : ''; pan.style.maxHeight = desk ? (view.h - 140) + 'px' : '';
    if (raidOpen) { raidOpen = false; renderRaid(); }
  }

  function openPanel(slot) {
    sel = { slot };
    const room = (ark.rooms || []).find(r => r.slot === slot);
    const f = floorOf(slot), depth = (f - DOME_FLOOR) * DEPTH_PER_FLOOR;
    const fl = (f - DOME_FLOOR + 1);
    const body = $('#panelBody');
    if (room && room.flooded) {
      body.innerHTML = '<h2>' + esc((catalog[room.id] || {}).name || room.id) + '</h2>' +
        '<p class="sub">' + fl + '층 · 깊이 ' + depth + 'm · 격벽 닫힘</p>' +
        '<p class="lost">여기는 물에 잠겼습니다. 격벽은 다시 열리지 않습니다.<br>일도 하지 않고, 소리도 나지 않습니다. ' +
        '그래도 지워지지 않고 그대로 남아 있습니다.</p>' +
        (room.flooded_day ? '<h3>잃은 날</h3><div class="kv"><span>' + esc(room.flooded_day) + '일째</span>' +
          (room.flooded_by ? '<span>' + esc(creatureName(room.flooded_by)) + '</span>' : '') + '</div>' : '') +
        rebuildList(slot);
      body.querySelectorAll('.bopt[data-room]').forEach(b => b.addEventListener('click', () => build(b.dataset.room, slot)));
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
          '<span>' + esc(RES_KO[k] || k) + ' +' + esc(v) + '</span>').join('') || '<span>없음</span>') +
        '</div>' +
        '<h3>붙여 둔 도구</h3><div class="kv">' +
        (inst.length ? inst.map(x => '<span>' + esc(toolName(x.id)) +
            (x.uses != null ? ' ' + x.uses + '회' : '') + '</span>').join('') : '<span>없음</span>') +
        '</div>' +
        '<h3>여기 계신 분</h3>' +
        (people.length ? people.map(p => personRow(p, slot)).join('')
          : '<div class="who"><em>아무도 안 계십니다. 빈 방은 막지 못합니다.</em></div>');
      const lb = body.querySelector('#lgt');
      if (lb) lb.addEventListener('click', () => setLight(slot, !lit));
      bindDest(body);
      bindPeople(body);
      bindUpgrade(body);
    } else {
      if (f < DOME_FLOOR) {
        body.innerHTML = '<h2>돔 상부 · 홀</h2><p class="sub">깊이 0m 위 · 유리 천장</p>' +
          '<p class="desc">여기는 더 놓을 자리가 없습니다. 방주는 아래로 넓어집니다.<br>자리를 정하지 않은 분은 이 홀에 모이십니다.</p>';
        $('#panel').hidden = false; placePanel(); return;
      }
      const bo = ark.build_options || null;               // 서버가 '지금 지을 수 있나'를 주면 그것을 그린다
      const ids = Object.keys(catalog).filter(id => !catalog[id].fixed && (!bo || bo[id]));
      body.innerHTML =
        '<h2>물이 찬 칸</h2>' +
        '<p class="sub">' + fl + '층 · 깊이 ' + depth + 'm · ' + esc(zoneAt(f)) + '</p>' +
        '<p class="desc">물을 빼면 이 칸을 되찾습니다. 아래로 내려갈수록 좋은 유물이 나오지만, 그만큼 위험합니다.</p>' +
        '<h3>물 빼고 쓸 방 고르기</h3><div class="blist">' +
        ids.map(id => {
          const o = bo && bo[id];
          const lack = o ? Object.entries(o.lacking || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v)
                              .concat((o.cond_missing || []).map(plain)) : lacking(id);
          const cap = (ark.room_caps || {})[id];
          return '<button class="bopt' + (lack.length ? ' lack' : '') + '" data-room="' + esc(id) + '"' +
            (lack.length ? ' disabled' : '') + '><b>' + esc(catalog[id].name || id) +
            (cap ? ' · 정원 ' + cap : '') + '</b>' +
            '<small>' + esc(lack.length ? '부족: ' + lack.join(' · ') : costLine(id)) + '</small>' + (o && lack.length ? srcHint(o.lacking) : '') + '</button>';
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
        if (p) { setCarry({ id: p.id, name: p.name, role: p.role }); toast(p.name + ' 님, 옮겨 갈 방을 골라 주세요'); }
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
      '<p class="sub">돔 상부 · 자리 안 정한 분</p>' +
      '<p class="desc">여기 계신 분은 아무 방도 지키지 않습니다. 습격이 오기 전에 자리를 정해 주세요.</p>' +
      destList() +
      (list.length ? list.map(p => personRow(p, null)).join('') : '<div class="who"><em>모두 자리에 계십니다</em></div>') +
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
      (w.has_workshop ? '' : '<p class="desc">아직 공방이 없습니다. 물을 뺀 칸을 공방으로 쓰셔야 도구를 만들 수 있습니다.</p>') +
      ((w.tools[0] && w.tools[0].hands) ? '<p class="eye-early">' + esc(w.tools[0].hands.ko) + '</p>'
        : (w.has_workshop ? '<p class="desc">공방에 아무도 안 계십니다. 도구는 사람 손이 만듭니다. 공방에 사람을 두시면 드는 재료가 달라집니다.</p>' : '')) +
      w.tools.map(t => {
        const cost = Object.entries(t.cost).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
        const lack = Object.keys(t.lacking || {}).length;
        return '<div class="tool"><div><b>' + esc(t.name) +
          '<span class="kind">' + esc(KIND_KO[t.kind] || t.kind) + '</span>' +
          (t.owned ? '<span class="kind">가진 것 ' + t.owned + '</span>' : '') + '</b>' +
          '<small>' + esc(t.does) + ' · 주로 ' + esc((t.against || []).join('·')) + '</small>' +
          '<small>재료 ' + esc(cost) + (lack ? ' · 모자람' : '') + '</small></div>' +
          '<div class="act"><button data-craft="' + esc(t.id) + '"' + (t.can_craft ? '' : ' disabled') + '>만들기</button>' +
          (t.kind !== 'consumable'
            ? '<select data-inst="' + esc(t.id) + '"' + (t.owned ? '' : ' disabled') + '>' +
              '<option value="">붙일 방 고르기…</option>' +
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
    if (c) { el.textContent = c.name + (lid ? ' 님, 덮개 앞이라 지금 옮기시면 안 됩니다' : ' 님, 모실 방을 골라 주세요'); el.hidden = false; }
    else el.hidden = true;
  }

  async function place(residentId, slot) {
    try {
      const st = await api('/api/ark/station', { resident_id: residentId, slot: slot });
      apply(st); setCarry(null);
      toast(raidLive('lid') ? '자리를 옮겼습니다. 덮개가 움직임을 느낀 것 같습니다'
                            : (slot == null ? '홀로 모셨습니다' : '자리를 옮겼습니다'));
      if (!$('#panel').hidden) { if (slot != null) openPanel(slot); else openHallPanel(); }
      refreshRaid();
    } catch (e) { toast(e.message || '옮기지 못했습니다'); setCarry(null); }
  }
  async function setLight(slot, on) {
    const wrongDark = !on && raidLive('mirror_eye') && (raidTargetSlot() == null || raidTargetSlot() === slot);
    try { apply(await api('/api/ark/light', { slot, on }));
          toast(wrongDark ? '불을 껐습니다. 거울눈이 제 모습을 못 보게 됐습니다. 긴목 때와는 반대입니다'
                          : (on ? '불을 켰습니다' : '불을 껐습니다. 이 방은 저희도 안 보입니다'));
          play(on ? 'sfx_lantern_on.ogg' : 'sfx_note_arrive.ogg', 0.4);
          if (sel) openPanel(sel.slot); refreshRaid(); }
    catch (e) { toast(e.message || '잘 안 됐습니다'); }
  }
  async function setPower(on) {
    try { apply(await api('/api/ark/power', { on })); toast(on ? '전원을 올렸습니다' : '전원을 내렸습니다. 돔이 조용해집니다'); refreshRaid(); }
    catch (e) { toast(e.message || '잘 안 됐습니다'); }
  }
  async function doRecall() {
    try { const r = await api('/api/ark/recall', {}); apply(r.state);
          toast(r.recalled.length ? r.recalled.length + '분이 들어오셨습니다' : '밖에 계신 분이 없습니다');
          play('sfx_airlock_cycle.ogg', 0.5); refreshRaid(); }
    catch (e) { toast(e.message || '잘 안 됐습니다'); }
  }
  async function craft(id) {
    try { const r = await api('/api/ark/craft', { tool_id: id }); apply(r.state);
          toast((r.made || {}).name + ' 하나 만들었습니다'); openWorkshop(); }
    catch (e) { toast(e.message || '만들지 못했습니다'); }
  }
  async function install(id, slot) {
    try { apply(await api('/api/ark/install', { tool_id: id, slot })); toast('도구를 붙였습니다'); openWorkshop(); refreshRaid(); }
    catch (e) { toast(e.message || '붙이지 못했습니다'); openWorkshop(); }
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
  // 물 찬 칸 되찾기 목록(S13 flooded_cells). 보통 건설비로 Lv1 부터 — 잃기 전 방을 맨 위에 둔다
  function rebuildList(slot) {
    const fc = (ark.flooded_cells || []).find(f => f.slot === slot); if (!fc) return '';
    const bo = ark.build_options || {};
    const ids = Object.keys(catalog).filter(id => !catalog[id].fixed && bo[id]).sort((a, b) => (b === fc.was_id) - (a === fc.was_id));
    return '<h3>물을 빼고 다시 짓기 · Lv1</h3><div class="blist">' + ids.map(id => {
      const o = bo[id];
      const lack = Object.entries(o.lacking || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).concat((o.cond_missing || []).map(plain));
      return '<button class="bopt' + (lack.length ? ' lack' : '') + '" data-room="' + esc(id) + '"' + (lack.length ? ' disabled' : '') + '><b>' +
        esc(catalog[id].name || id) + (id === fc.was_id ? ' · 예전 그 방' : '') + '</b><small>' +
        esc(lack.length ? '모자람: ' + lack.join(' · ') : costLine(id)) + '</small>' + (lack.length ? srcHint(o.lacking) : '') + '</button>';
    }).join('') + '</div>';
  }
  async function build(roomId, slot) {
    try {
      const st = await api('/api/ark/build', { room_id: roomId, slot });
      apply(st);
      // M5: 짓는 것이 아니라 물을 빼고 되찾는다(라벨만 — API 는 /api/ark/build 그대로). 되찾은 칸의 한 줄은 시나리오 data/tower_lore.json
      const line = reclaimLine(slot);
      toast(((catalog[roomId] || {}).name || roomId) + ' 자리, 물을 다 뺐습니다' + (line ? '. ' + line : ''));
      closePanel(); animStart(slot, 'reclaim'); play('sfx_water_splash.ogg', 0.4);
      setTimeout(() => { play('sfx_lantern_on.ogg', 0.4); openCard({ slot });
        if (line) { const h = $('#roomcard h4'); if (h) h.insertAdjacentHTML('afterend', '<p class="rcline reclaim">' + esc(line) + '</p>'); placeCard(); } }, 1150);
    } catch (e) { toast(e.message || '물을 빼지 못했습니다'); }
  }

  async function advanceRaid() {
    const btn = $('#radv'); btn.disabled = true;
    try {
      const r = await api('/api/raid/advance', {});
      if (r.state) apply(r.state);
      if (r.result) {
        play((cb.raid && cb.raid.creature.audio && cb.raid.creature.audio.contact) || 'sfx_water_splash.ogg', 0.6);
        if (r.result === 'breached') play('sfx_room_flood.ogg', 0.75);
        const tgt = raidTargetSlot();
        const wd = RESULT_WORD[r.result] || [r.result_ko || '', '#e6d7b0'];
        floatWord(tgt, wd[0], wd[1]);
        lastOutcome = Object.assign({ raidId: cb.raid && cb.raid.id }, r);
        raidOpen = false;
        toast(r.line);
      }
      renderRaid();
    } catch (e) { toast(e.message || '잘 안 됐습니다'); }
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
      (r.lost_room ? '<p class="lost">' + esc(r.lost_room) + ' 쪽이 물에 잠겼습니다. 격벽은 다시 열리지 않습니다.</p>' : '') +
      (r.injured ? '<p class="lost">' + esc(r.injured) + ' 님이 다치셨습니다.</p>' : '') +
      '<h3>이번 판정</h3><div class="kv">' +
      (r.parts || []).map(p => '<span>' + esc(p.ko) + ' ' + p.v + '</span>').join('') + '</div>' +
      (Object.keys(r.gained || {}).length
        ? '<h3>남은 것</h3><div class="kv">' + Object.entries(r.gained).map(([k, v]) =>
            '<span>' + esc(RES_KO[k] || k) + ' ' + (v > 0 ? '+' : '') + v + '</span>').join('') + '</div>' : '') +
      (imp ? '<h3>겪은 분</h3>' + imp : '') +
      ((r.next_raid_hint && r.next_raid_hint.ko) ? '<h3>문어</h3><p class="desc">' + esc(r.next_raid_hint.ko) + '</p>' : '');
    $('#panel').hidden = false; placePanel();
  }

  // ── 습격 막대 ─────────────────────────────────────────────
  function renderRaid() {
    const bar = $('#raidbar'), raid = cb && cb.raid;
    if (!raid) {
      bar.hidden = true; document.body.classList.remove('raid-on'); renderStrip(null);
      $('#rflip').hidden = true; $('#ract').hidden = true;
      if (view.w <= 560 && lastBarH) { cam.y += (lastBarH / 2) / cam.z; lastBarH = 0; }
      const hint = cb && cb.next_raid_hint;
      if (hint && hint.ko) { /* 문어의 예고는 토스트로 한 번만 */ }
      return;
    }
    renderStrip(raid);
    bar.hidden = !raidOpen; document.body.classList.add('raid-on');
    bar.classList.toggle('calm', !raid.creature.threat);
    $('#rstage').textContent = STAGE_LABEL[raid.stage] || raid.stage;
    $('#rwho').textContent = raid.creature.name + (raid.target_room ? ' → ' + raid.target_room : '');
    const steps = $('#rsteps').children;
    for (let i = 0; i < steps.length; i++) steps[i].classList.toggle('on', i <= raid.stage_no);
    $('#rtext').textContent = plain(raid.stage === 'sound' ? raid.creature.sound
      : raid.stage === 'silhouette' ? raid.creature.silhouette
      : (raid.line || raid.creature.contact));
    $('#rhow').textContent = plain(raid.creature.threat ? '막는 법: ' + raid.creature.how : '걱정 안 하셔도 됩니다. 우리 식구입니다.');
    let eyeEl = $('#reye');
    if (!eyeEl) { eyeEl = document.createElement('p'); eyeEl.id = 'reye'; eyeEl.className = 'eye-early';
                  $('#rhow').after(eyeEl); }
    eyeEl.hidden = !raid.eye_early;
    if (raid.eye_early) eyeEl.textContent = plain(raid.eye_early.ko);
    const g = $('#rgate'), wd = $('#rwould');
    if (raid.ready && raid.creature.threat && raid.stage !== 'done') {
      g.hidden = false; wd.hidden = false;
      g.classList.toggle('ok', !!raid.ready.gate.ok);
      g.innerHTML = '<b>' + (raid.ready.gate.ok ? '준비 끝' : '아직') + '</b><span>' + esc(raid.ready.gate.ko) + '</span>';
      wd.classList.toggle('bad', raid.ready.would !== 'held');
      wd.innerHTML = '지금 맞서시면 <b>' + esc((K.ext.T && K.ext.T('raid_preview.' + raid.ready.would, {}, '')) || raid.ready.would_ko) + '</b>';   // S18 TSV: 미리 보기는 미래형
    } else { g.hidden = true; wd.hidden = true; }
    renderGate(raid);
    clueMode(raid);
    const btn = $('#radv');
    if (raid.stage === 'sound') { btn.hidden = false; btn.textContent = '귀 기울이기'; }
    else if (raid.stage === 'silhouette') { btn.hidden = false; btn.textContent = '맞서기'; }
    else { btn.hidden = true; }
    $('#rhint').textContent = raid.stage === 'silhouette'
      ? '급하게 안 하셔도 됩니다. 「맞서기」를 누르시기 전까지는 아무 일도 없으니, 천천히 자리 옮기시고 불도 정리하시고 도구도 붙여 두세요.'
      : (raid.stage === 'done' ? '오늘은 지나갔습니다.' : '어느 방으로 올지는 아직 모릅니다.');
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

  // S18 「답 대신 단서」: 처음 두 번 만나는 손님은 막는 법·관문·반전을 숨기고 **버릇 한 줄 + 할 수 있는 일(동사)** 만 보인다.
  //      동사를 고르면 그때 미리 보기(지금 맞서시면 …)가 열리고, 맞서기 전까지 몇 번이든 바꿀 수 있다.
  //      두 번 겪은 손님(서버 answer_known / encounters, 없으면 도감 /api/collection 의 times)은 예전처럼 답을 보여 준다
  const RAID_VERBS = [['light', '불'], ['power', '전원'], ['move', '자리'], ['tool', '도구']];
  const verbPick = {};                                  // 습격 id → 고른 동사
  const metTimes = {};                                  // 생물 id → 겪은 횟수(도감)
  let metAt = 0;
  async function loadMet() {
    if (performance.now() - metAt < 60000) return; metAt = performance.now();
    try { const c = await api('/api/collection?uid=' + encodeURIComponent(uid)); (c.creatures || []).forEach(x => { if (x.id) metTimes[x.id] = x.times || 0; }); renderRaid(); }
    catch (e) { /* 도감이 없으면 단서 모드 그대로 */ }
  }
  function answerKnown(raid) {
    if (raid.card_mode) return raid.card_mode !== 'clue';             // 서버 S18(stakes raid_card)
    if (typeof raid.answer_known === 'boolean') return raid.answer_known;
    const need = raid.answer_after != null ? raid.answer_after : 2;
    const n = raid.encounters != null ? raid.encounters : (raid.creature.encounters != null ? raid.creature.encounters : metTimes[raid.creature.id]);
    if (n == null) { loadMet(); return false; }
    return n >= need;
  }
  const actPick = {};                                  // 습격 id → 「행동」 안에서 고른 것(화면 몫 — 누르기 전까지 서버는 모른다)
  async function pickVerb(raid, verb) {
    verbPick[raid.id] = verb;
    try { const r = await api('/api/raid/verb', { verb }); if (r.state) apply(r.state); }   // 서버가 그 동사의 미리보기를 연다
    catch (e) { /* 옛 서버: 화면만 바꾼다 */ }
    renderRaid();
  }
  function clueMode(raid) {
    let vb = $('#rverbs');
    const on = !!(raid.creature.threat && raid.stage !== 'done' && !raid.resolved && !answerKnown(raid));
    $('#raidbar').classList.toggle('clue', on);
    if (!on) { if (vb) vb.hidden = true; return; }
    if (!vb) {
      vb = document.createElement('div'); vb.id = 'rverbs'; vb.className = 'rverbs'; $('#rhow').after(vb);
      vb.addEventListener('click', (e) => {
        const r = cb.raid; if (!r) return;
        const b = e.target.closest('button[data-verb]'), o = e.target.closest('button[data-opt]'), go = e.target.closest('button[data-try]');
        if (b) { pickVerb(r, b.dataset.verb); return; }
        if (o) { actPick[r.id] = o.dataset.opt; renderRaid(); return; }
        if (go) { go.disabled = true; doAct(go.dataset.try, r.id); }
      });
    }
    vb.hidden = false;
    const habit = raid.habit || (raid.creature && raid.creature.habit);
    $('#rhow').textContent = plain(habit ? '버릇: ' + habit : '처음 보는 손님입니다. 무엇을 해 볼지 골라 보세요.');
    const verbs = (raid.verbs && raid.verbs.length) ? raid.verbs : RAID_VERBS.filter(v => v[0] !== 'tool' || raid.action).map(v => ({ id: v[0], ko: v[1] }));
    const pick = raid.verb || verbPick[raid.id], pv = verbs.find(v => v.id === pick) || null;
    const how = { light: '방마다 불을 켜고 끄면서 아래 미리 보기를 보세요.', power: '≡ 메뉴의 전원으로 집 전체 불을 켜고 끌 수 있습니다.',
                  move: '사람을 끌어다 다른 방으로 옮겨 보세요. 맞서기 전까지는 몇 번이든 됩니다.', station: '사람을 끌어다 다른 방으로 옮겨 보세요. 맞서기 전까지는 몇 번이든 됩니다.',
                  tool: '방의 「자세히」에서 도구를 붙이거나 뗄 수 있습니다.', act: '해 볼 일을 하나 고르세요. 대가는 누를 때 냅니다.' };
    let sub = '';
    const ap = actPick[raid.id];
    if (pick === 'act' && pv && pv.options) {
      sub = '<div class="rvb sub">' + pv.options.map(o => '<button data-opt="' + esc(o.id) + '"' + (ap === o.id ? ' class="on"' : '') + '>' + esc(plain(o.ko)) + '</button>').join('') + '</div>';
      const o = ap && pv.options.find(x => x.id === ap);
      const done = (raid.acts || []).indexOf(ap) >= 0;
      if (o) sub += '<p class="rvhow">대가: ' + esc(plain(o.cost_ko || '')) + '</p>' +
        (done ? '<p class="rvhow">이미 해 두었습니다.</p>' : '<div class="rowbtns"><button class="on" data-try="' + esc(o.id) + '">이걸로 해 보기</button></div>');
    }
    vb.innerHTML = '<div class="rvb">' + verbs.map(v => '<button data-verb="' + esc(v.id) + '"' + (pick === v.id ? ' class="on"' : '') + '>' + esc(v.ko) + '</button>').join('') + '</div>' +
      (pick ? '<p class="rvhow">' + esc(how[pick] || '') + '</p>' + sub : '<p class="rvhow">고르시면 그때 「지금 맞서시면 …」이 보입니다.</p>');
    $('#rgate').hidden = true; $('#rflip').hidden = true;     // 관문·반전 문장은 답이다
    $('#rwould').hidden = !pick || !raid.ready;
    $('#ract').hidden = true;                                 // 단서 모드에서는 맞는 행동 하나를 콕 집지 않는다(서버 action:null)
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
    const s = cb.stations[id];
    if (s !== undefined) return s;
    return podSeat[id] != null ? 'pod:' + podSeat[id] : 'hall';
  }
  // ── 입구 포드(S12-B4, layout.json entrance) ── 서버 칸이 아니라 홀의 일부. 배치 안 된 사람이 여기서 기다린다
  const podSeat = {};                                  // 주민 id → 자리 번호(0~5)
  function seatPod() {
    const E = MAP().entrance; if (!E || !cb) return;
    const spots = E.spots || [];
    const idle = (ark.residents_list || []).filter(r => cb.stations[r.id] === undefined && (cb.outside || []).indexOf(r.id) < 0).map(r => r.id);
    Object.keys(podSeat).forEach(id => { if (idle.indexOf(id) < 0) delete podSeat[id]; });
    const used = new Set(Object.values(podSeat));
    idle.forEach(id => {
      if (podSeat[id] != null) return;
      const k = spots.findIndex((_, i) => !used.has(i));
      if (k >= 0) { podSeat[id] = k; used.add(k); }
    });
  }
  function podSpot(k) { const E = MAP().entrance; return E && E.spots ? E.spots[k] : null; }
  function trackMoves() {
    if (!cb || !ark) return;
    seatPod();
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

  const applyHooks = [];
  function apply(st) {
    ark = st;
    cb = st.combat || cb;
    if (Array.isArray(st.shelf)) shelf = st.shelf.filter(x => x && typeof x.slot === 'number');
    if (Array.isArray(st.stored)) stored = st.stored.filter(x => x && x.id);      // S18: 선반에 못 놓인 유물(창고 상자)
    if (st.rooms_catalog) catalog = st.rooms_catalog;
    slots = st.slots || slots;
    floorSlots = st.floor_slots || floorSlots;
    if (typeof st.dome_floor === 'number') DOME_FLOOR = st.dome_floor;
    $('#dayline').textContent = 'Day ' + st.day;
    $('#actline').textContent = (st.act || 1) + '막 · ' + (st.act_ko || '');
    renderTop(st);                                   // S12-B2: 위 한 줄(핵심 넷) + ≡ 메뉴 창고(나머지)
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
    try { trackMoves(); } catch (e) { lastWhere = null; console.error('이동 계산 잘 안 됐습니다', e); }
    // S13-B: 수집·사건 모듈(base_collect.js)이 상태가 바뀔 때마다 듣는다
    applyHooks.forEach(f => { try { f(st); } catch (e) { console.error('수집 모듈 반영 실패', e); } });
  }

  const loadHooks = [];
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
      if (first && hint && hint.ko && (!cb.raid || cb.raid.stage === 'done')) say(hint.ko);
      if (first) loadHooks.forEach(f => { try { f(st); } catch (e) { console.error('첫 로드 훅 실패', e); } });
      if (first) { qReady = true; setTimeout(pumpQ, 0); }   // S18: 첫 로드의 창들(밤사이·만남·귀환)이 다 모인 뒤에 순서대로
    } catch (e) { qReady = true; toast('방주를 불러오지 못했습니다: ' + (e.message || '')); }
  }

  // ══════════════════════════════════════════════════════════════
  //  스프린트 10-E — 이 화면에 빠져 있던 조작 넷
  //   ① 찍기(/api/scan) ② 관문 행동(/api/ark/act) ③ 열쇠(/api/account) ④ E1 선반
  //  근거: PLAYER_JOURNEY §2 E1 · §3 J5, COMBAT_AND_DEFENSE §4, data/creatures.json 의 wrong_move
  // ══════════════════════════════════════════════════════════════
  const plain = (s, vars) => fillText(s, vars).replace(/\*\*/g, '');      // 서버 문장의 강조 표시를 걷는다
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
  let shelf = [], propsMeta = {}, shelfFlash = null, stored = [];
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
      // 닦기(S13): 2단계 = 윗면에 얇은 빛, 3단계 = 등불색 테두리 빛. 은은하게(판독을 해치지 않게)
      const lv = it.polish | 0;
      if (lv >= 3) {
        const rg = ctx.createRadialGradient(px + w / 2, py + h / 2, 0, px + w / 2, py + h / 2, Math.max(w, h) * 0.9);
        rg.addColorStop(0, 'rgba(255,230,170,0.30)'); rg.addColorStop(1, 'rgba(255,230,170,0)');
        ctx.fillStyle = rg; ctx.fillRect(px - w * 0.4, py - h * 0.4, w * 1.8, h * 1.8);
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
      if (lv >= 2) {                                          // 닦인 윗면 — 한 줄 빛
        ctx.fillStyle = 'rgba(255,244,214,' + (lv >= 3 ? 0.55 : 0.32) + ')';
        ctx.fillRect(px + w * 0.15, py + Math.max(1, h * 0.08), w * 0.7, Math.max(1, h * 0.05));
      }
      if (it.variant === 'sea') {                             // 바다 무늬 — 청록 빛줄이 천천히 지나간다
        const k = ((now / 2600) + (i * 0.37)) % 1, bx = px - w * 0.3 + (w * 1.6) * k;
        ctx.save(); ctx.beginPath(); ctx.rect(px, py, w, h); ctx.clip();
        const lg = ctx.createLinearGradient(bx - w * 0.25, 0, bx + w * 0.25, 0);
        lg.addColorStop(0, 'rgba(120,220,215,0)'); lg.addColorStop(0.5, 'rgba(120,220,215,0.45)'); lg.addColorStop(1, 'rgba(120,220,215,0)');
        ctx.fillStyle = lg; ctx.fillRect(px, py, w, h); ctx.restore();
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
      const lbl = '방금 들어온 물건 · ' + (f.name || propSpec(f.prop_id).name || '');
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
    return nm + (w ? ', ' + w + ' 찍은 것' : '') + (it.category ? ' · ' + (CAT_KO[it.category] || it.category) : '');
  }
  const POLISH_KO = { 1: '건진 그대로', 2: '한 번 닦음', 3: '윤이 남' };
  function shelfSection(slot) {
    if (slot !== shelfRoomSlot()) return '';
    const cap = shelfCap();
    const rows = shelf.slice().sort((a, b) => (b.scanned_at || 0) - (a.scanned_at || 0));
    const fresh = shelfFlash && performance.now() < shelfFlash.until ? shelfFlash.slot : null;
    return '<h3>선반 · ' + rows.length + '점 / ' + cap + '칸</h3><div class="kv shelfkv">' +
      (rows.length ? rows.map(it => '<span' + ((it.slot | 0) === fresh ? ' class="new"' : '') + '>' +
          esc(it.name || propSpec(it.prop_id).name || it.prop_id) + ' · ' + esc(whenKo(it.scanned_at)) +
          ((it.polish | 0) > 1 ? ' · ' + esc(it.polish_label || POLISH_KO[it.polish] || '') : '') + (it.variant === 'sea' ? ' · 바다 무늬' : '') + '</span>').join('')
        : '<span>비어 있습니다. 찍은 물건이 여기 놓입니다</span>') + '</div>' + storedSection();
  }
  // S18: 창고 상자 — 선반이 찬 뒤 들어온 유물도 사라지지 않고 여기 보인다. 빈 칸이 있으면 「선반에 올리기」
  function shelfFree() {
    const used = new Set(); shelf.forEach(it => { for (let k = 0; k < propSpec(it.prop_id).slots; k++) used.add((it.slot | 0) + k); });
    return Math.max(0, shelfCap() - used.size);
  }
  function storedSection() {
    if (!stored.length) return '';
    const free = shelfFree();
    return '<h3>' + esc(STO()) + ' · ' + stored.length + '점</h3><p class="desc">선반에 자리가 없어서 넣어 둔 것들입니다. 도감에는 그대로 남아 있습니다.' + (free ? ' 선반에 빈 칸이 ' + free + '칸 있습니다.' : '') + '</p>' +
      '<div class="storedlist">' + stored.slice().reverse().slice(0, 12).map(it =>
        '<div class="sto"><span><b>' + esc(it.relic_name || it.name || '물건') + '</b> · ' + esc(RAR_KO[it.rarity] || '') + ' · ' + esc(whenKo(it.scanned_at)) + '</span>' +
        (free ? '<button data-unstore="' + esc(it.id) + '">선반에 올리기</button>' : '') + '</div>').join('') + '</div>';
  }
  function storedLine(slot) {
    if (slot !== shelfRoomSlot() || !stored.length) return '';
    return '<p class="rcline stoline">선반 ' + shelf.length + '점 / ' + shelfCap() + '칸 <button class="stochip" data-c="stored">' + esc(STO()) + ' ' + stored.length + '</button></p>';
  }
  // 창고 상자 ↔ 선반(POST /api/shelf/swap). slot 을 주면 그 칸 물건과 바꾼다
  async function shelfSwap(storedId, slot) {
    try {
      const r = await api('/api/shelf/swap', slot == null ? { stored_id: storedId } : { stored_id: storedId, slot });
      if (r.state) apply(r.state);
      const it = shelf.find(x => (x.slot | 0) === r.slot);
      if (r.ko || r.down_ko) toast(plain([r.ko, r.down_ko].filter(Boolean).join(' ')));   // 서버 S18 문장(shelf.full.placed·moved)
      else toast(r.down ? plain(TT('shelf.full.moved', { item: r.down }, josa('\'' + r.down + '\'', '은') + ' ' + STO() + '에 넣어 두었습니다.'))
                   : ((it ? '\'' + (it.relic_name || it.name) + '\', ' : '') + '선반 ' + (r.slot + 1) + '번째 칸에 올렸습니다.'));
      if (typeof r.slot === 'number') { shelfFlash = { slot: r.slot, until: performance.now() + 9000 }; }
      return r;
    } catch (e) { toast(e.message || '바꾸지 못했습니다'); return null; }
  }
  // 같은 날 다시 찍으면 서버 polish.ko 가 비어 온다 → ui_moments 의 shelf.rescan(최대면 rescan_max) 문장으로
  function rescanLine(pol, it) {
    if (pol && pol.ko) return plain(pol.ko);
    const item = (it && (it.name || propSpec(it.prop_id).name)) || '';
    const T = K.ext.T;
    const atMax = pol && pol.max && pol.level >= pol.max;
    // S18: 오늘 세지 않은 재스캔에 「한 번 더 닦아 두었습니다」를 쓰면 거짓 문장이다(서버도 그때 ko 를 비운다)
    if (pol && pol.counted_today === false && !atMax) return '「' + item + '」은 오늘 이미 닦아 두었습니다. 다른 날 다시 찍으시면 한 번 더 닦입니다.'.replace('」은', jongOf(item) ? '」은' : '」는');
    const key = atMax ? 'shelf.rescan_max' : 'shelf.rescan';
    return T ? T(key, { item }, '') : '';
  }
  function focusShelf(slot, pol) {
    const rs = shelfRoomSlot();
    if (rs == null) { toast('물건을 둘 창고가 없습니다'); return; }
    flyToSlot(rs);
    shelfFlash = { slot, until: performance.now() + 9000 };
    setTimeout(() => play('sfx_card_place.ogg', 0.55), 700);
    const it = shelf.find(x => (x.slot | 0) === slot);
    const room = (ark.rooms || []).find(r => r.slot === rs);
    const nm = (room && (catalog[room.id] || {}).name) || '창고';
    if (pol) { toast(rescanLine(pol, it)); return; }
    toast((it ? '\'' + (it.name || propSpec(it.prop_id).name) + '\', ' : '') + nm + ' 선반에 두었습니다.');
  }

  // 불 버튼. 거울눈 앞에서 노려지는 방의 불을 끄는 것은 **긴목에게 배운 정답이 오답이 되는 자리**다
  function lightButton(slot, lit) {
    const tgt = raidTargetSlot();
    const worst = lit && raidLive('mirror_eye') && (tgt == null || tgt === slot);
    return '<button id="lgt" class="' + (lit ? 'on' : '') + (worst ? ' worst' : '') + '">' +
      (lit ? (worst ? '불 켜짐 · 끄지 마세요(거울눈)' : '불 끄기') : '불 켜기') + '</button>';
  }

  // ── ② 관문 행동 · 반전 ───────────────────────────────────
  // 반전 둘(creatures.json wrong_move): 거울눈은 '불을 끄면', 덮개는 '사람을 옮기면' 최악수다
  const REVERSAL = {
    mirror_eye: {
      base: () => '<b>긴목 때와는 반대입니다.</b> 불은 끄지 마세요. 비친 모습이 사라지면 짝을 찾겠다고 유리를 밉니다.',
      bad: (raid) => (raid.target_slot != null && !lightOf(raid.target_slot))
        ? '<b>' + esc(raid.target_room || '그 방') + '의 불이 꺼져 있습니다.</b> 긴목 때 통하던 방법이 여기서는 가장 나쁜 방법입니다.' +
          '<button data-relight="' + raid.target_slot + '">다시 켜기</button>' : null,
    },
    lid: {
      base: () => '<b>지금은 아무도 옮기지 마세요.</b> 사람을 옮기는 게 지금은 가장 나쁜 수입니다. 저 녀석은 움직이는 것 위에는 앉지 않습니다.',
      bad: (raid) => (raid.moves > 0)
        ? '<b>벌써 ' + raid.moves + '번 옮기셨습니다.</b> 덮개가 움직임을 느꼈습니다. 살아 있는 줄 알면 놀라서 몸을 텁니다.' : null,
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
    const no = a.done ? '' : ((a.blocked && a.blocked.length) ? '지금은 못 합니다: ' + a.blocked.join(' · ')
                              : (lack ? '모자랍니다: ' + lack : ''));
    const paid = paidLog[raid.id];
    box.innerHTML =
      '<button class="ractbtn" data-act="' + esc(a.id) + '"' + (a.can ? '' : ' disabled') + '>' +
        (a.done ? '완료 · ' : '') + esc(plain(a.ko)) + '</button>' +
      (a.done ? '' : '<div class="rcost' + (lack ? ' lack' : '') + '">대가: ' + esc(plain(a.cost_ko)) + '</div>' +
                     (no ? '' : '<div class="rwhy">' + esc(plain(a.why)) + '</div>')) +
      (no ? '<div class="rno">' + esc(no) + '</div>' + (lack ? srcHint(a.lacking, true).replace(/small/g, 'div') : '') : '') +
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
    } catch (e) { toast(e.message || '하지 못했습니다'); refreshRaid(); }
  }

  // ── ① 찍기: 카메라 → 카드가 뒤집힌다 → 선반에 놓는다 (J5) ────────
  // app.js(옛 2D 화면)의 BarcodeDetector + 후면 카메라 + 숫자 폴백을 이 화면으로 옮겼다.
  const SAMPLES = [['8801043015097', '식품'], ['9791162241905', '도서'], ['8806011000013', '의약'],
                   ['8809000111110', '문구'], ['4901234567894', '미지 가문'], ['8801044007770', '패턴']];
  let stream = null, detector = null, scanning = false, lastCode = '', lastAt = 0, scanBusy = false;
  let pendingCode = null, lastScan = null, K_cardTest = null;
  function openScan() {
    if (!ark) return;
    closePanel(); setCarry(null);
    $('#scan').hidden = false; $('#scanCam').hidden = false; $('#scanCard').hidden = true;
    $('#picker').hidden = true; $('#manual').value = ''; pendingCode = null;
    $('#quota').textContent = '오늘 읽은 성문 ' + (ark.scans_today || 0) + ' / ' + (ark.scan_cap || 20) +
      ' · 같은 물건은 다시 읽을수록 덜 나옵니다';
    // 예시 번호는 개발 기계에서만 — 이 게임의 훅은 진짜 물건을 찍는 것이다
    const dev = /^(127\.0\.0\.1|localhost)$/.test(location.hostname) || qs.has('samples');
    const sm = $('#samples'); sm.hidden = !dev;
    if (dev) sm.innerHTML = SAMPLES.map(([c, l]) => '<button data-c="' + c + '">' + esc(l) + ' ' + c + '</button>').join('');
    startCam();
  }
  function closeScan() { stopCam(); if (K.ext.cards) K.ext.cards.stop(); $('#scan').hidden = true; }
  async function startCam() {
    const st = $('#camstatus'), box = $('#cam');
    box.classList.remove('off');
    if (!('BarcodeDetector' in window)) {
      box.classList.add('off'); st.textContent = '이 브라우저는 카메라로 줄무늬를 못 읽습니다. 아래에 숫자를 적어 주세요'; return;
    }
    if (!navigator.mediaDevices || !window.isSecureContext) {
      box.classList.add('off'); st.textContent = '카메라는 HTTPS에서만 열립니다. 아래에 숫자를 적어 주세요'; return;
    }
    try {
      detector = detector || new BarcodeDetector({ formats: ['ean_13', 'upc_a', 'ean_8'] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1280 } } });
      if ($('#scan').hidden) { stopCam(); return; }
      const v = $('#video'); v.srcObject = stream; await v.play();
      st.textContent = '줄무늬를 붉은 선에 맞춰 주세요'; scanning = true; camLoop();
    } catch (e) { box.classList.add('off'); st.textContent = '카메라를 열 수 없습니다. 아래에 숫자를 적어 주세요'; }
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
    if (code.length < 8) { toast('숫자 8~13자리를 적어 주세요'); return; }
    scanBusy = true; $('#manualBtn').disabled = true;
    try {
      if (userCat === undefined) {
        const pk = await api('/api/peek?barcode=' + code + '&uid=' + encodeURIComponent(uid));
        if (pk.needs_category) { showPicker(pk); return; }
      }
      const r = await api('/api/scan', { barcode: code, user_category: userCat || null });
      stopCam(); pendingCode = null;
      play('sfx_scan_ok.ogg', 0.5);
      // 선반의 정본은 /api/ark 다. 카드 앞면 그림을 선반에 놓일 물건과 같게 하려고 먼저 받는다
      try { apply(await api('/api/ark?uid=' + encodeURIComponent(uid))); } catch (e2) { /* 카드는 그래도 뒤집힌다 */ }
      showReveal(r);
    } catch (e) { toast(e.message || '읽지 못했습니다'); }
    finally { scanBusy = false; $('#manualBtn').disabled = false; }
  }
  function showPicker(pk) {
    pendingCode = pk.barcode;
    const w = $('#picker'); w.hidden = false;
    w.innerHTML = '<p>이 가문의 성문은 처음 봅니다. 어떤 물건인가요?</p>' +
      (pk.categories || []).map(c => '<button data-cat="' + esc(c) + '">' + esc(CAT_KO[c] || c) + '</button>').join('') +
      '<button data-cat="">모름</button>';
  }
  // S16: 선반 물건 → 카드 한 장의 재료
  function shelfCardOf(it) {
    const lv = it.polish | 0;
    const when = it.scanned_at ? whenKo(it.scanned_at) + ' 찍은 것' : '';
    const pl = lv > 1 ? (it.polish_label || POLISH_KO[lv] || '') : '';
    return { rarity: it.rarity, sea: it.variant === 'sea', name: it.relic_name || it.name || propSpec(it.prop_id).name || '물건', category: it.category,
             prop_id: it.prop_id, lines: [[pl, when].filter(Boolean).join(' · ')].filter(Boolean) };
  }
  // 닦기 도장 글: 오늘 센 것만 「닦였습니다」(세지 않은 재스캔에 '닦았다'고 찍으면 거짓 문장이 된다 — 서버 polish 와 같은 규칙)
  // S18: 선반이 꽉 찼다 — 방금 것은 창고 상자에 들어갔고, 덜 닦인 것과 바꿀지 묻는다(누르지 않으면 상자에 그대로)
  const TT = (k, v, fb) => (K.ext.T ? K.ext.T(k, v || {}, '') : '') || fb;   // 시나리오 문장(ui_moments) 먼저
  const STO = () => TT('shelf.full.storage_label', {}, '창고 상자');
  function swapOffer(so, item) {
    const c = (so.candidates || []).slice(0, 3);
    return '<span class="where swapq">' + esc(plain(TT('shelf.full.prompt', { item }, so.ko || '선반이 꽉 차서 ' + STO() + '에 넣어 두었습니다. 선반의 물건과 바꾸시겠습니까?'))) + '</span>' +
      (c.length ? '<span class="swapbtns">' + c.map(x => '<button data-swap="' + esc(so.stored_id) + '" data-slot="' + esc(x.slot) + '">' +
        esc('「' + (x.relic_name || x.name || '물건') + '」') + '<small>' + esc(TT('shelf.full.swap_label', {}, '바꿔 놓기')) + (POLISH_KO[x.polish] ? ' · ' + esc(POLISH_KO[x.polish]) : '') + '</small></button>').join('') +
        '<button data-keep="1">' + esc(TT('shelf.full.keep_label', {}, '그대로 두기')) + '</button></span>' : '');
  }
  function polishStamp(pol) {
    if (!pol) return '';
    if (!pol.counted_today) return pol.max && pol.level >= pol.max ? (pol.label || '윤이 남') : '오늘은 이미 닦음';
    return '닦였습니다' + (pol.leveled_up && pol.label ? ' · ' + pol.label : '');
  }
  // S18: 값 0 재스캔(같은 날 같은 물건 등)에도 작은 반응. 서버 zero_note(있으면) → 시나리오 문장(ui_moments rescan_zero) → 기존 문장.
  //      카드는 뒤집힌 뒤 고개를 한 번 갸웃한다(.zero)
  // 카드 위에 작게 톡 — 「닦기가 하나 쌓였습니다」「문어가 좋아합니다」 같은 한 줄(서버 zero_reaction.ko). 3.6초 뒤 사라짐
  function zeroPop(z) {
    const host = $('#rcard'); if (!host) return;
    const old = host.querySelector('.zpop'); if (old) old.remove();
    const el = document.createElement('div'); el.className = 'zpop zp-' + (z.kind || 'x');
    const FB = { box_key_hint: '이 성문을 기다리는 상자가 문간에 있습니다.', polish_progress: '닦은 횟수가 하나 쌓였습니다.',
                 wish_hint: (z.resident ? z.resident + ' 님이 ' : '') + '이런 물건을 반가워하십니다.', octopus_mood: '문어가 좋아합니다.' };
    const t = z.ko || (K.ext.T ? K.ext.T('zero.' + z.kind, { name: z.resident || '' }, '') : '') || FB[z.kind] || '';
    if (!t) return;
    el.innerHTML = '<i aria-hidden="true"></i><span>' + esc(plain(t)) + '</span>';
    host.appendChild(el);
    setTimeout(() => el.classList.add('off'), 3600); setTimeout(() => el.remove(), 4200);
  }
  function zeroLine(r) {
    const zn = r.zero_note || r.rescan_zero || null;
    let t = zn && (zn.ko || zn.line || (typeof zn === 'string' ? zn : ''));
    if (!t && K.ext.T) {
      const c = r.card || {}, item = c.name || '';
      const arr = K.ext.Tarr ? (K.ext.Tarr('shelf.rescan_zero') || K.ext.Tarr('rescan_zero.lines')) : null;
      if (arr && arr.length) { let h = 0; String(c.barcode || c.id || item).split('').forEach(ch => { h = (h * 31 + ch.charCodeAt(0)) >>> 0; }); t = fillText(arr[h % arr.length], { item }); }
      else t = K.ext.T('rescan_zero.line', { item }, '');
    }
    return '<span class="zeroline">' + esc(plain(t || '이미 읽은 성문이라 새로 얻은 건 없습니다')) + '</span>';
  }
  function showReveal(r) {
    lastScan = r;
    const c = r.card || {};
    const has = Object.prototype.hasOwnProperty.call(r, 'shelf_slot');
    const slot = typeof r.shelf_slot === 'number' ? r.shelf_slot : null;
    const item = slot != null ? shelf.find(x => (x.slot | 0) === slot) : null;
    const pid = (item && item.prop_id) || propForCategory(c.category);
    const sp = propSpec(pid);
    const sea = !!((r.variant && r.variant.shiny) || c.sea_variant || (item && item.variant === 'sea'));
    const front = $('#rcFront');
    const CR = K.ext.cards;
    if (CR) {                                           // S16: 틀·그림 창·갈래 무늬·희귀도 이름이 있는 카드 한 장
      front.className = 'rc-face rc-front rkhost';
      front.innerHTML = CR.face({ rarity: c.rarity, sea, name: c.name, category: c.category, flavor: c.flavor,
                                   prop_id: pid && PROP_ID_OK.test(pid) ? pid : null });
    } else {
      front.className = 'rc-face rc-front ' + (RAR_KO[c.rarity] ? c.rarity : 'common') + (sea ? ' sea' : '');
      front.innerHTML = '<div class="rr">' + esc(RAR_KO[c.rarity] || c.rarity || '') + (r.first_time ? ' · 처음 보는 것' : '') + '</div>' +
        '<h3>' + esc(c.name || '이름 없는 것') + '</h3>' +
        '<div class="art">' + (pid && PROP_ID_OK.test(pid)
          ? '<img alt="" width="' + sp.w * 3 + '" height="' + sp.h * 3 + '" src="/static/art/props/x4/' + pid + '.png">' : '') + '</div>' +
        (c.flavor ? '<p class="fl">"' + esc(c.flavor) + '"</p>' : '') +
        '<div class="meta"><span>' + esc(CAT_KO[c.category] || c.category || '') + '</span>' +
          (c.family_name ? '<span>' + esc(c.family_name) + '</span>' : '') +
          (c.tags || []).filter(t => t !== '미확인').slice(0, 3).map(t => '<span>#' + esc(t) + '</span>').join('') + '</div>';
    }
    const g = Object.entries(r.gained || {}).map(([k, v]) => '<b>' + esc(RES_KO[k] || k) + ' +' + esc(v) + '</b>').join(' · ');
    // S13: 이미 선반에 있는 바코드면 새 칸을 먹지 않고 「닦였습니다」(polish). 서버가 준 문장이 이긴다
    const pol = r.polish || null, again = pol && r.shelf_new === false;
    const shelfNote = again
      ? '<span class="where polished">' + esc(rescanLine(pol, item)) + (pol.label ? ' <b class="plv lv' + esc(pol.level) + '">' + esc(pol.label) + '</b>' : '') + '</span>'
      : (slot != null
        ? '<span class="where">' + esc((item && item.name) || sp.name || '물건') + ', 선반 ' + (slot + 1) + '번째 칸에 두겠습니다</span>'
        : (r.swap_offer && r.swap_offer.stored_id ? swapOffer(r.swap_offer, c.name || '')
          : (has ? '<span class="where">선반이 꽉 찼습니다. 창고를 넓히시면 더 둘 수 있습니다</span>' : '')));
    const vr = r.variant && r.variant.shiny ? r.variant : null;
    const extra = (vr ? '<span class="variantline">' + esc(plain(vr.ko || '')) + '</span>' : '') +
      (r.first_meet || []).map(m => '<span class="meetline">' + esc(plain(m.line || '')) + '</span>').join('') +
      (r.family_set && r.family_set.ko ? '<span class="famline' + (r.family_set.just_completed ? ' done' : '') + '">' + esc(plain(r.family_set.ko)) + '</span>' : '') +
      (r.wishes_done || []).map(w => '<span class="wishline">' + esc(plain(w.line || '')) + '</span>').join('') +
      // S16: 찍기로 열린 상자 — 문장은 그대로, 앞에 작은 상자가 「열림」 하고 튄다
      (r.box_opened && K.ext.boxOpenedLine ? '<span class="boxline"><i class="boxpop" aria-hidden="true"><s></s><em>열림</em></i>' + esc(K.ext.boxOpenedLine(r)) + '</span>' : '');
    const rg = $('#rgain');
    rg.innerHTML = (r.first_time ? '<span class="first">도감에 처음 적힌 유물</span><br>' : '') +
      (g || zeroLine(r)) +
      ((r.rescan_multiplier > 0 && r.rescan_multiplier < 1) ? ' <span>(다시 읽음 ×' + esc(r.rescan_multiplier) + ')</span>' : '') +
      shelfNote + extra +
      ((r.voice && r.voice.text) ? '<span class="voice">' + esc(r.voice.who_ko || '') + (r.voice.who_ko ? ': ' : '') + esc(r.voice.text) + '</span>' : '');
    const btn = $('#shelfBtn');
    btn.textContent = slot != null ? (again ? '선반 보기' : '선반에 두기') : '닫기';
    btn.classList.remove('on');
    $('#scanCam').hidden = true; $('#scanCard').hidden = false;
    const card = $('#rcard'); card.classList.remove('flip');
    const rare = ['rare', 'epic', 'legendary'].indexOf(c.rarity) >= 0;
    const zero = !Object.keys(r.gained || {}).length;
    const after = () => {
      rg.classList.add('show'); btn.classList.add('on');
      if (r.zero_reaction) zeroPop(r.zero_reaction);
      if (zero && card.animate && !(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches))
        card.animate([{ transform: 'none' }, { transform: 'rotate(-3deg)' }, { transform: 'rotate(2deg)' }, { transform: 'none' }], { duration: 520, easing: 'ease-in-out' });
      if (r.family_set && r.family_set.just_completed && K.ext.celebrate) setTimeout(() => K.ext.celebrate(plain(r.family_set.ko)), 700);
    };
    if (CR) {
      rg.classList.remove('show');
      CR.reveal({ rarity: c.rarity, again, stamp: polishStamp(pol),
                  onFlip: () => { if (navigator.vibrate && rare && !again) navigator.vibrate([40, 60, 80]); },
                  onDone: after });
      return;
    }
    rg.classList.add('show');
    void card.offsetWidth;                              // 다시 찍어도 뒤집기가 처음부터
    setTimeout(() => card.classList.add('flip'), 380);
    setTimeout(after, 1150);
    if (navigator.vibrate && rare) setTimeout(() => navigator.vibrate([40, 60, 80]), 900);
  }
  // ★ S16 개발 전용 시험대(?cardtest=1 — RELIC_DEV 서버에서만 base_cards.js 가 단추를 띄운다). 서버를 부르지 않고 가짜 응답으로 연출만 본다
  K_cardTest = (rar, sea, again, box) => {
    const it = shelf[0] || null;
    const cats = ['food', 'drink', 'medical', 'electronics', 'stationery'];
    const cat = again && it ? it.category : (cats[['common', 'uncommon', 'rare', 'epic', 'legendary'].indexOf(rar)] || 'food');
    closePanel(); closeCard(); $('#scan').hidden = false;
    showReveal({ card: { rarity: rar, name: '시험 카드 ' + (RAR_KO[rar] || rar), category: cat, flavor: '입구만 남은 병이다. 귀에 대면 바깥 소리가 들린다.', family_name: '붉은 실 가문', sea_variant: sea },
                 gained: again ? {} : { food: 3, morale: 1 }, rescan_multiplier: again ? 0.5 : 1, first_time: !again,
                 shelf_slot: it ? it.slot : null, shelf_new: !again,
                 variant: sea ? { shiny: true, ko: '관리실에서 알려 드립니다. 이번 물건에는 바다 무늬가 들어 있습니다.' } : { shiny: false },
                 polish: again ? { level: 2, prev_level: 1, leveled_up: true, counted_today: true, max: 3, label: '한 번 닦음', ko: '' } : null,
                 box_opened: box ? { cat, gained: { parts: 2 } } : null });
  };
  function toShelf() {
    const r = lastScan; closeScan();
    if (r && typeof r.shelf_slot === 'number') focusShelf(r.shelf_slot, r.polish && r.shelf_new === false ? r.polish : null);
  }

  // ── 레벨업(서버 S10 upgrades·hall_upgrade). 숫자가 아니라 '새로 할 수 있는 것'을 먼저 말한다 ──
  // S18: 「모자랍니다: X」 옆에 X 가 어디서 나오는지(서버 material_sources + 시나리오 ui_moments material_hint).
  //      버튼 안에는 짧게(「직물: 의류 찍기 · 위를 보는 숲(원정)」), 패널 문단에는 시나리오 문장 그대로
  function srcShort(k) {
    const ms = (ark.material_sources || {})[k];
    if (!ms) return '';
    const parts = [ms.scan ? ms.scan + ' 찍기' : ''].concat((ms.other || []).slice(0, 2)).filter(Boolean);
    return parts.length ? (RES_KO[k] || k) + ': ' + parts.join(' · ') : '';
  }
  function srcLine(k) {
    const t = K.ext.T ? K.ext.T('material_hint.' + k, {}, '') : '';
    return t || srcShort(k);
  }
  function srcHint(lackObj, long) {
    const ks = Object.keys(lackObj || {}).filter(k => (ark.material_sources || {})[k] || (K.ext.T && K.ext.T('material_hint.' + k, {}, '')));
    if (!ks.length) return '';
    return ks.slice(0, 2).map(k => '<small class="srchint">' + esc(long ? srcLine(k) : srcShort(k) || srcLine(k)) + '</small>').join('');
  }
  function upgradeSection(opt, key) {
    if (!opt) return '';
    const cost = Object.entries(opt.cost || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
    const lack = Object.entries(opt.lacking || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
    const miss = (opt.cond_missing || []).join(' · ');
    return '<h3>올리기 · Lv' + esc(opt.to) + '</h3><div class="blist"><button class="bopt' + (opt.can ? '' : ' lack') +
      '" data-up="' + esc(key) + '"' + (opt.can ? '' : ' disabled') + '><b>' + esc(plain(opt.opens) || ('Lv' + opt.to)) + '</b>' +
      '<small>' + esc(cost) + (opt.cond ? ' · 조건: ' + esc(plain(opt.cond)) : '') + '</small>' +
      (miss ? '<small>아직: ' + esc(miss) + '</small>' : (lack ? '<small>모자람: ' + esc(lack) + '</small>' : '')) +
      '</button></div>' + (miss ? '' : srcHint(opt.lacking, true).replace(/<small class="srchint">/g, '<p class="srchint">').replace(/<\/small>/g, '</p>'));
  }
  function bindUpgrade(body) {
    body.querySelectorAll('.bopt[data-up]').forEach(b => b.addEventListener('click', async () => {
      const k = b.dataset.up;
      try {
        const st = await api('/api/ark/upgrade', k === 'hall' ? { room_id: 'hall' } : { slot: parseInt(k, 10) });
        apply(st);
        const u = st.upgraded || {};
        toast(josa((u.name || '') + ' Lv' + (u.level || ''), '으로') + ' 올렸습니다.' + (u.opens ? ' ' + plain(u.opens) : ''));
        play('sfx_tool_install.ogg', 0.5);
        if (k === 'hall') openHallPanel(); else { animStart(parseInt(k, 10), 'level'); openPanel(parseInt(k, 10)); }
      } catch (e) { toast(e.message || '올리지 못했습니다'); }
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
    catch (e) { body.innerHTML = '<h2>방주의 열쇠</h2><p class="lost">열쇠를 꺼내지 못했습니다: ' + esc(e.message || '') + '</p>'; return; }
    body.innerHTML = '<h2>방주의 열쇠</h2>' +
      '<p class="sub">' + esc(a.day) + '일째 · 방 ' + esc(a.rooms) + ' · 사람 ' + esc(a.residents) + '</p>' +
      '<div class="keycode" id="keycode">' + esc(a.pretty || a.code) + '</div>' +
      '<p class="desc">' + esc(a.ko || '적어 두시면 다른 기계에서도 이어서 하실 수 있습니다.') + '</p>' +
      '<div class="rowbtns"><button id="keycopy">베껴 두기</button></div>' +
      '<h3>다른 기계의 방주로</h3>' +
      '<p class="desc">다른 기계에서 적어 둔 열쇠를 넣어 주세요. 지금 이 방주로 다시 오시려면 위 열쇠를 먼저 적어 두세요.</p>' +
      '<div class="keyrow"><input id="keyin" maxlength="9" autocomplete="off" autocapitalize="characters" spellcheck="false"' +
        ' placeholder="열쇠 여섯 글자" aria-label="복구 코드"><button id="keygo">이어 하기</button></div>' +
      '<p class="keyerr" id="keyerr"></p>';
    $('#keycopy').addEventListener('click', () => {
      const txt = a.pretty || a.code;
      try {
        navigator.clipboard.writeText(txt).then(() => toast('베껴 두었습니다: ' + txt), () => toast('길게 눌러 베껴 주세요'));
      } catch (e) { toast('길게 눌러 베껴 주세요'); }
    });
    const go = async () => {
      const v = $('#keyin').value.trim(), err = $('#keyerr');
      err.className = 'keyerr'; err.textContent = '';
      if (!v) { err.textContent = '열쇠를 적어 주세요'; return; }
      $('#keygo').disabled = true;
      try {
        const r = await api('/api/account/restore', { code: v });
        if (r.uid === uid) { err.className = 'keyerr keyok'; err.textContent = '이미 이 방주입니다.'; return; }
        try { localStorage.setItem('ark_uid', r.uid); }
        catch (e) { err.textContent = '이 브라우저에는 저장할 수 없습니다(사생활 보호 창인가요?)'; return; }
        err.className = 'keyerr keyok'; err.textContent = plain(r.ko || '돌아오셨습니다.');
        setTimeout(() => location.reload(), 900);
      } catch (e) {
        // 429 = 잠금(틀린 열쇠를 여러 번), 400 = 형식, 404 = 없는 열쇠. 셋은 할 일이 다르다
        err.textContent = e.status === 429 ? '잠시 뒤 다시 해 주세요: ' + (e.message || '너무 여러 번 틀리셨습니다')
          : e.status === 400 ? '열쇠 형식이 다릅니다: ' + (e.message || '여섯 글자')
          : (e.message || '열리지 않았습니다');
      }
      finally { const b = $('#keygo'); if (b) b.disabled = false; }
    };
    $('#keygo').addEventListener('click', go);
    $('#keyin').addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
  }

  // ══════════════════════════════════════════════════════════════
  //  S12-B2 — UI 단순화(docs/UI_SIMPLE.md). 고정 UI 는 위 한 줄 + 찍기·≡ 둘.
  //  방 카드 · 생산 방울 · 끌 때 방마다 숫자 하나 · 습격 띠 · 작은 애니메이션(방울·되찾기·레벨업·결과 글자).
  //  기존 패널(openPanel 등)은 지우지 않고 카드의 「자세히」 뒤로 숨겼다.
  // ══════════════════════════════════════════════════════════════
  const CHIP = { power: '전', food: '식', water: '물', parts: '부' };
  const TOP_RES = ['power', 'food', 'water', 'parts'];
  function renderTop(st) {
    const res = st.resources || {};
    $('#resbar').innerHTML = TOP_RES.map(k =>
      '<span class="rchip ' + k + '" data-res="' + k + '" title="' + esc(RES_KO[k] || k) + '"><i>' + CHIP[k] + '</i>' + esc(res[k] || 0) + '</span>').join('');
    // 나머지는 ≡ 메뉴의 「창고」에 — 0 인 것도 보인다(보이지 않는 자원 때문에 막히지 않게, S9-C 지적)
    $('#mres').innerHTML = Object.keys(res).filter(k => TOP_RES.indexOf(k) < 0)
      .map(k => '<span>' + esc(RES_KO[k] || k) + '<b>' + esc(res[k]) + '</b></span>').join('');
    const g = st.gauges || {};
    const gm = $('#gmini');
    if (g.air) gm.style.setProperty('--a', Math.round(g.air.value * 100) + '%');
    if (g.depth) gm.style.setProperty('--d', Math.round(Math.max(0.06, g.depth.value) * 100) + '%');
  }

  // ── 팝오버 셋(≡ 메뉴 · 공기/깊이 · 습격 카드)은 하나만 열린다 ──
  let raidOpen = false;
  function closePops(except) {
    if (except !== 'menu') { $('#menu').hidden = true; $('#menubtn').setAttribute('aria-expanded', 'false'); }
    if (except !== 'gauge') { $('#gaugepop').hidden = true; $('#gaugebtn').setAttribute('aria-expanded', 'false'); }
    if (except !== 'raid' && raidOpen) { raidOpen = false; renderRaid(); }
  }
  $('#menubtn').addEventListener('click', () => {
    const open = $('#menu').hidden; closePops('menu'); closeCard();
    $('#menu').hidden = !open; $('#menubtn').setAttribute('aria-expanded', String(open));
  });
  $('#gaugebtn').addEventListener('click', () => {
    const open = $('#gaugepop').hidden; closePops('gauge');
    $('#gaugepop').hidden = !open; $('#gaugebtn').setAttribute('aria-expanded', String(open));
  });
  ['#pwr', '#wbtn', '#recallbtn', '#keybtn'].forEach(id => $(id).addEventListener('click', () => {
    if (id !== '#pwr') { $('#menu').hidden = true; $('#menubtn').setAttribute('aria-expanded', 'false'); }
  }));

  // ── 습격 띠(위 가운데) ── 생물 그림자 + 한 줄 + 노려지는 방. 누르면 작은 카드(#raidbar)
  let lastOutcome = null;
  function renderStrip(raid) {
    const sp = $('#rstrip');
    if (!raid) { sp.hidden = true; return; }
    sp.hidden = false;
    const done = raid.stage === 'done' || raid.resolved;
    sp.classList.toggle('calm', !raid.creature.threat);
    sp.classList.toggle('done', !!done);
    const meta = threatMeta[raid.creature.id];
    $('#rsil').style.backgroundImage = meta ? 'url(/static/art/threats/' + meta.files.far + ')' : '';
    const stage = STAGE_LABEL[raid.stage] || raid.stage;
    const rko = raid.result_ko || ((lastOutcome && lastOutcome.raidId === raid.id) ? lastOutcome.result_ko : '');
    const res = done && rko ? ' · ' + rko + (raid.auto ? ' (밤사이)' : '') : '';
    // 소리 단계: 관리실 방송 한 줄을 띠에. 넘치면 여는 말을 「관리실입니다.」로 줄인다(전문은 카드의 서술 줄에)
    const el = $('#rsline');
    if (raid.stage === 'sound' && raid.creature.sound) {
      const full = plain(raid.creature.sound);
      el.textContent = full; el.title = full;
      if (el.scrollWidth > el.clientWidth + 1) el.textContent = full.replace(/^관리실에서 (알려|안내 말씀) 드립니다\.\s*/, '관리실입니다. ');
    } else {
      el.title = '';
      el.textContent = raid.creature.name + (raid.target_room ? ' → ' + raid.target_room : '') + ' · ' + (res ? res.slice(3) : stage);
    }
    sp.setAttribute('aria-expanded', String(raidOpen));
  }
  $('#rstrip').addEventListener('click', () => {
    const raid = cb && cb.raid;
    if (raid && (raid.stage === 'done' || raid.resolved) && lastOutcome) { closePops(); showOutcome(lastOutcome); return; }
    const open = !raidOpen; closePops('raid'); closeCard();
    raidOpen = open; renderRaid();
  });
  $('#rclose').addEventListener('click', () => { raidOpen = false; renderRaid(); });
  $('#rtext').addEventListener('click', () => $('#rtext').classList.toggle('open'));   // 이야기 문장은 눌러서 다 읽는다

  // ── 방 위 작은 카드 ── 이름·레벨·사람 수·유리한 능력치 한 글자 + 버튼 둘 이하 + 「자세히」
  let card = null;                                     // {slot} | {hall:true} | {sealed:cell}
  function closeCard() { card = null; $('#roomcard').hidden = true; }
  function cardAnchor() {                              // 세계 좌표 → 화면(위 가운데)
    if (!card) return null;
    if (card.hall) { const h = hallRect(); return { x: h.x + h.w / 2, y: h.y + 40, bottom: h.y + h.h }; }
    const c = card.sealed || (rectOf(card.slot) || {}).cell;
    return c ? { x: c.x + c.w / 2, y: c.y + 12, bottom: c.y + c.h } : null;
  }
  function placeCard() {
    const el = $('#roomcard'); if (el.hidden || !card) return;
    const a = cardAnchor(); if (!a) return;
    let x = sx(a.x), y = sy(a.y);
    const below = y - el.offsetHeight < 52;          // 위 한 줄에 걸리면 방 아래로
    if (below) y = Math.min(view.h - el.offsetHeight - 70, sy(a.bottom) - 8);
    el.classList.toggle('below', below);
    x = Math.max(el.offsetWidth / 2 + 8, Math.min(view.w - el.offsetWidth / 2 - 8, x));
    el.style.left = x + 'px'; el.style.top = y + 'px';
  }
  function openCard(c) {
    closePops();
    card = c;
    const el = $('#roomcard');
    let h = '';
    if (c.hall) {
      const n = (ark.residents_list || []).filter(r => cb.stations[r.id] === undefined && cb.outside.indexOf(r.id) < 0).length;
      h = '<h4>홀<small>Lv' + esc(ark.hall_level || 1) + '</small></h4><div class="rcmeta">자리 안 정한 분 ' + n + '명</div>' +
          '<div class="rcbtns">' + (K.ext.openSendOff ? '<button data-c="send" class="on">내보내기</button>' : '') + '<button data-c="more">자세히</button></div>';
    } else if (c.sealed) {
      const deep = (c.sealed.depth_m || 0) >= TRENCH_M && c.sealed.kind !== 'rock';
      const bl = towerLore && towerLore.below_limit && towerLore.below_limit.line;
      h = '<h4>' + (c.sealed.kind === 'rock' ? '벽 쪽 바위' : (deep ? '검게 잠긴 칸' : '물이 찬 칸')) + '<small>깊이 ' + esc(c.sealed.depth_m) + 'm</small></h4>' +
          '<p class="rcline">' + esc(deep && bl ? bl : SEALED_KO[c.sealed.kind === 'rock' ? 'rock' : 'tower']) + '</p>';
    } else {
      const slot = c.slot, room = (ark.rooms || []).find(r => r.slot === slot);
      const depth = (floorOf(slot) - DOME_FLOOR) * DEPTH_PER_FLOOR;
      if (!room) {
        h = '<h4>물이 찬 칸<small>깊이 ' + depth + 'm</small></h4><p class="rcline">물을 빼면 이 칸을 되찾습니다.</p>' +
            '<div class="rcbtns"><button class="on" data-c="build">물 빼기</button></div>';
      } else if (room.flooded) {
        const fc = (ark.flooded_cells || []).find(f => f.slot === slot) || {};
        const was = fc.was_name || (catalog[room.id] || {}).name || room.id;
        h = '<h4>' + esc(was) + '<small>물에 잠김</small></h4>' +
            '<p class="rcline">' + esc(was) + ' 자리가 물에 잠겼습니다. 물을 빼면 처음부터 다시 지을 수 있습니다.</p>' +
            '<div class="rcbtns"><button class="on" data-c="build">물 빼기</button><button data-c="more">자세히</button></div>';
      } else {
        const spec = catalog[room.id] || {}, n = (peopleBySlot()[slot] || []).length, cap = capOf(slot), lit = lightOf(slot);
        const ko = (ark.stats_meta || {}).ko || STAT_KO_DEF, st = goodStats(slot);
        const worst = lit && raidLive('mirror_eye') && (raidTargetSlot() == null || raidTargetSlot() === slot);
        const prod = (ark.production || {})[String(slot)] || null;
        const crk = !!room.cracked, rp = ark.repair || {};
        const rcost = Object.entries(rp.cost || {}).map(([k, v]) => (RES_KO[k] || k) + ' ' + v).join(' · ');
        h = '<h4>' + esc(spec.name || room.id) + '<small>Lv' + esc(room.level || 1) + '</small>' +
            (crk ? '<i class="rctag crack">' + esc(K.ext.T ? K.ext.T('crack.label_cracked', {}, '금 감') : '금 감') + '</i>' : '') +
            (prod && prod.label ? '<i class="rctag">' + esc(prod.label) + '</i>' : '') + '</h4>' +
            (crk ? '<p class="rcline">' + esc(K.ext.T ? K.ext.T('crack.still_cracked', { room: spec.name || room.id }, '') : '') + '</p>' : '') +
            (prod && prod.ko && !crk ? '<p class="rcline">' + esc(plain(prod.ko)) + '</p>' : '') +
            contribLine(prod) + storedLine(slot) +
            '<div class="rcmeta"><span>' + n + '/' + cap + '명</span>' +
            (prod && typeof prod.mult === 'number' ? '<span class="rcmult' + (prod.mult < 1 ? ' neg' : (prod.mult > 1 ? ' pos' : '')) + '">생산 ×' + (Math.round(prod.mult * 100) / 100) + '</span>' : '') +
            st.map(k => '<span class="rcstat" title="이 방에 유리한 능력치">' + esc(ko[k] || k) + '</span>').join('') + '</div>' +
            (crk
              ? '<div class="rcbtns"><button data-c="repair" class="on">' + esc(K.ext.T ? K.ext.T('crack.label_repair', {}, '수리하기') : '수리하기') +
                  (rp.have_patch ? '' : (rcost ? '<small>' + esc(rcost) + '</small>' : '')) + (rp.have_patch ? '<small>봉합 패치 ' + rp.have_patch + '</small>' : '') +
                  '</button><button data-c="more">자세히</button></div>'
              : '<div class="rcbtns"><button data-c="light" class="' + (lit ? 'on' : '') + (worst ? ' worst' : '') + '">' +
                  (lit ? (worst ? '끄지 마세요' : '불 끄기') : '불 켜기') + '</button>' + (room.id === 'workshop' ? '<button data-c="trade">바꾸기</button>' : '') + '<button data-c="more">자세히</button></div>');
      }
    }
    el.innerHTML = h; el.hidden = false;
    el.querySelectorAll('button[data-c]').forEach(b => b.addEventListener('click', () => {
      const k = b.dataset.c;
      if (k === 'more') { const cc = card; closeCard(); if (cc.hall) openHallPanel(); else openPanel(cc.slot); }
      else if (k === 'build') { const sl = card.slot; closeCard(); openPanel(sl); }   // 빈 칸·물 찬 칸 모두 같은 짓기 흐름
      else if (k === 'repair') { const sl = card.slot; repairRoom(sl); }
      else if (k === 'send') { closeCard(); K.ext.openSendOff && K.ext.openSendOff(); }
      else if (k === 'trade') { const sl = card.slot; closeCard(); openTrade(sl); }
      else if (k === 'stored') { const sl = card.slot; closeCard(); openPanel(sl); setTimeout(() => { const h = $('#panelBody .storedlist'); if (h) h.scrollIntoView({ block: 'center' }); }, 60); }
      else if (k === 'light') { const sl = card.slot; setLight(sl, !lightOf(sl)).then(() => { if (card && card.slot === sl) openCard({ slot: sl }); }); }
    }));
    placeCard();
  }

  // S18 공방 바꾸기(POST /api/workshop/trade): 남는 식량·물 4개 → 막힌 재료 1개, 하루 2개까지(서버가 판정, 화면은 고르기만)
  const tradeLeft = {};                                 // 날 → 오늘 남은 개수(서버 응답 left_today)
  function openTrade(slot) {
    const give = ['food', 'water'], get = ['cloth', 'parts', 'scrap'];
    const left = tradeLeft[ark.day];
    const pick = openTrade.pick || (openTrade.pick = { give: 'food', get: 'cloth' });
    const res = ark.resources || {};
    const body = K.panel('<h2>공방 바꾸기</h2><p class="sub">남는 식량·물 4개를 막힌 재료 1개로 바꿉니다. 하루 2개까지' + (left != null ? ' · 오늘 ' + left + '개 남음' : '') + '</p>' +
      '<h3>내는 것</h3><div class="chips">' + give.map(k => '<button class="chip' + (pick.give === k ? ' on' : '') + '" data-give="' + k + '">' + esc(RES_KO[k] || k) + ' 4 <small>(지금 ' + (res[k] || 0) + ')</small></button>').join('') + '</div>' +
      '<h3>받는 것</h3><div class="chips">' + get.map(k => '<button class="chip' + (pick.get === k ? ' on' : '') + '" data-get="' + k + '">' + esc(RES_KO[k] || k) + ' 1 <small>(지금 ' + (res[k] || 0) + ')</small></button>').join('') + '</div>' +
      '<p class="srchint">' + esc(srcLine(pick.get)) + '</p>' +
      '<div class="rowbtns"><button class="on" id="tradeGo"' + (left === 0 ? ' disabled' : '') + '>' + esc(RES_KO[pick.give]) + ' 4 → ' + esc(RES_KO[pick.get]) + ' 1</button></div>');
    body.querySelectorAll('[data-give]').forEach(b => b.addEventListener('click', () => { pick.give = b.dataset.give; openTrade(slot); }));
    body.querySelectorAll('[data-get]').forEach(b => b.addEventListener('click', () => { pick.get = b.dataset.get; openTrade(slot); }));
    body.querySelector('#tradeGo').addEventListener('click', async (e) => {
      e.target.disabled = true;
      try {
        const r = await api('/api/workshop/trade', { give: pick.give, get: pick.get, n: 1 });
        if (r.state) apply(r.state);
        if (typeof r.left_today === 'number') tradeLeft[ark.day] = r.left_today;
        toast(josa(RES_KO[pick.give] + ' ' + ((r.paid || {})[pick.give] || 4) + '개', '을') + ' 내고 ' + josa(RES_KO[pick.get] + ' ' + ((r.got || {})[pick.get] || 1) + '개', '을') + ' 받았습니다.');
        play('sfx_tool_install.ogg', 0.5);
      } catch (err) { toast(err.message || '바꾸지 못했습니다'); if (/까지만|0개/.test(err.message || '')) tradeLeft[ark.day] = 0; }
      openTrade(slot);
    });
  }
  // S14: 누가 이 방 산출을 얼마나 올리고 내리는지(production[slot].per_person, 서버 계산). 셋까지만
  function contribLine(prod) {
    const pp = (prod && prod.per_person) || [];
    if (!pp.length) return '';
    const ko = (ark.stats_meta || {}).ko || STAT_KO_DEF;
    return '<p class="rccontrib">' + pp.slice(0, 3).map(x => {
      const pct = Math.round((x.v || 0) * 100);
      return '<span class="' + (pct > 0 ? 'pos' : (pct < 0 ? 'neg' : '')) + '">' + esc(ko[x.stat] || x.stat) + ' ' + esc(x.value) + ' ' +
        esc(x.name) + ' 님 ' + (pct > 0 ? '+' : (pct < 0 ? '−' : '±')) + Math.abs(pct) + '%</span>';
    }).join('') + '</p>';
  }
  // 금 간 방 수리(API_S13 §5). 봉합 패치가 있으면 그것을 먼저 쓴다
  async function repairRoom(sl) {
    const rp = ark.repair || {};
    try {
      const r = await api('/api/ark/repair', { slot: sl, use_patch: !!rp.have_patch });
      if (r.state) apply(r.state);
      toast(plain(r.ko || '수리를 마쳤습니다.')); play('sfx_tool_install.ogg', 0.5);
      animStart(sl, 'level'); openCard({ slot: sl });
    } catch (e) { toast(e.message || '수리하지 못했습니다'); }
  }
  // ── 끄는 동안: 방마다 그 사람의 유리한 숫자 하나만(목록 UI 가 아니다) ──
  // ±% 꼴(서버가 계산한 값만 보여 준다 — D2·PM 결정). null 이면 쌓이는 산출이 없는 방
  const pctKo = (v) => (v == null ? null : (v > 0 ? '+' : (v < 0 ? '−' : '±')) + Math.abs(Math.round(v)) + '%');
  function movePreview(id, slot) {
    const mp = (ark.move_preview || {})[id] || {};
    return mp[slot == null ? 'hall' : String(slot)] || null;
  }
  function pill(x, y, text, kind, big, anchorRight) {   // kind: up | down | off | flat
    ctx.font = 'bold ' + (big ? 22 : 15) + 'px "Noto Sans KR",sans-serif';
    const tw = Math.max(34, ctx.measureText(text).width + (big ? 22 : 16)), h = big ? 36 : 26;
    if (anchorRight) x -= tw / 2;                      // x 가 오른쪽 끝이면 알약 가운데로 옮긴다
    const C = { up: ['rgba(20,34,18,0.94)', '#8fbf7a', '#c8f0b0'], down: ['rgba(60,24,18,0.94)', '#d08a72', '#ffd2c0'],
                off: ['rgba(30,28,26,0.85)', '#4a4440', '#7a726c'], flat: ['rgba(20,17,12,0.92)', '#f0b055', '#f0b055'] }[kind];
    ctx.fillStyle = C[0]; ctx.fillRect(x - tw / 2, y - h / 2, tw, h);
    ctx.strokeStyle = C[1]; ctx.lineWidth = 1.5; ctx.strokeRect(x - tw / 2, y - h / 2, tw, h);
    ctx.fillStyle = C[2]; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, x, y + 1);
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  }
  // S18: 끄는 동안 숫자는 **하나** — 「방주 전체 생산 ±n%」(플레이테스트: 방마다 ±%는 어디로 옮겨도 이득처럼 읽혔다).
  //      서버가 칸마다 ark_delta_pct 를 주면 그것을, 없으면 같은 서버 미리보기(room/from_delta_pct)에 방마다의
  //      기준 산출(목록 생산량 + 역할 보탬) × 배율 × 불을 곱해 방주 전체로 합친다. 꽉 찬 방·일손 없음은 글자로 함께
  function roomBaseOut(slot) {
    const pr = (ark.production || {})[String(slot)];
    const room = (ark.rooms || []).find(r => r.slot === slot);
    if (!pr || !room) return 0;
    const spec = catalog[room.id] || {}, prod = spec.produces || {}, rb = pr.role_bonus || {};
    let tot = 0;
    Object.keys(prod).forEach(k => { const v = prod[k]; if (typeof v === 'number' && k !== 'power_supply' && k !== 'craft_slots') tot += v + (rb[k] || 0); });
    const m = typeof pr.now_mult === 'number' ? pr.now_mult : (typeof pr.mult === 'number' ? pr.mult : 1);
    return tot * m * (lightOf(slot) ? 1 : 0.5);
  }
  function arkDeltaPct(pv, tgt, from) {
    if (!pv) return null;
    if (typeof pv.ark_delta_pct === 'number') return pv.ark_delta_pct;
    let all = 0; Object.keys(ark.production || {}).forEach(k => { all += roomBaseOut(+k); });
    if (all <= 0) return null;
    let d = 0;
    if (tgt != null && typeof pv.room_delta_pct === 'number') d += roomBaseOut(tgt) * pv.room_delta_pct / 100;
    if (from != null && typeof pv.from_delta_pct === 'number') d += roomBaseOut(from) * pv.from_delta_pct / 100;
    return d / all * 100;
  }
  const carryLog = [];
  function drawCarryNumbers() {
    const who = dragging || (carry && (ark.residents_list || []).find(r => r.id === carry.id));
    if (!who) return;
    const here = cb.stations[who.id];
    const hover = dragging ? slotAt(pointer.x, pointer.y) : null;
    if (hover == null || hover === here) return;           // 손끝이 방 위에 있을 때만, 그 방으로 옮기면 어떻게 되는지
    const pv = movePreview(who.id, hover);
    const bx = Math.min(view.w - 120, pointer.x + 110), by = Math.max(60, pointer.y - 74);   // 손끝 오른쪽 위 — 사람 그림 밖
    if (pv && pv.can === false) { pill(bx, by, '꽉 참', 'off', true); return; }
    const dp = arkDeltaPct(pv, hover, here != null ? here : null);
    const r1 = dp == null ? null : Math.round(dp);
    const txt = '방주 전체 생산 ' + (r1 == null ? '변화 없음' : (r1 > 0 ? '+' : (r1 < 0 ? '−' : '±')) + Math.abs(r1) + '%');
    pill(bx, by, txt, r1 == null || r1 === 0 ? 'flat' : (r1 > 0 ? 'up' : 'down'), true);
    // 떠나는 방이 비게 되면 한 줄(숫자가 아니라 글자)
    const pr = here != null ? (ark.production || {})[String(here)] : null;
    if (pr) {
      const left = Math.max(0, (pr.staff != null ? pr.staff : (peopleBySlot()[here] || []).length) - 1);
      if (left === 0) {
        const nm = ((ark.rooms || []).find(r => r.slot === here) || {}).id;
        pill(bx, by + 34, (catalog[nm] || {}).name ? (catalog[nm].name + ' ' + (K.ext.T ? K.ext.T('staffing.label', {}, '일손 없음') : '일손 없음')) : '일손 없음', 'down', false);
      }
    }
    if (carryLog[carryLog.length - 1] !== txt) { carryLog.push(txt); if (carryLog.length > 40) carryLog.shift(); }
  }

  // ── 생산 방울 ── 서버는 생산을 시간에 맞춰 이미 더한다(tick_production, 8시간마다). 새 API 를 만들지 않았다:
  // 방울은 그 방이 한 번에 내는 양(+N)을 보여 주는 **눈에 보이는 수확 신호**다. 누르면 HUD 로 날아가고 숫자 칩이 한 번 튄다.
  // 다시 뜨는 간격은 화면 연출(45초) — 서버 값은 바뀌지 않는다.
  const BUBBLE_GAP_MS = 45000;
  const bubbleAt = {};                                 // slot → 다시 뜨는 시각(performance.now)
  function bubbleOf(room) {
    const spec = catalog[room.id] || {}, pr = spec.produces || {};
    const k = Object.keys(pr).find(x => CHIP[x]) || Object.keys(pr)[0];
    if (!k) return null;
    const pm = (ark.production || {})[String(room.slot)];
    const mult = pm && typeof pm.mult === 'number' ? pm.mult : 1;
    const n = Math.max(1, Math.round(pr[k] * mult));           // 방울은 정수로(1.4 같은 소수는 읽기 어렵다)
    return { res: k, n, mult, label: pm && pm.label };
  }
  function drawBubbles(t) {
    if (!cb || !cb.power_on) return;
    (ark.rooms || []).forEach((room, i) => {
      if (room.flooded || !lightOf(room.slot)) return;
      const b = bubbleOf(room); if (!b) return;
      if (bubbleAt[room.slot] == null) bubbleAt[room.slot] = t + 1200 + i * 700;
      if (t < bubbleAt[room.slot]) return;
      const r = rectOf(room.slot); if (!r) return;
      const since = t - bubbleAt[room.slot], pop = Math.min(1, since / 260);
      const k = pop < 1 ? 1 + 0.35 * Math.sin(pop * Math.PI) : 1;               // 톡 튀어 오른다
      const x = sx(r.x + r.w - 70), y = sy(r.y) - 14 + Math.sin(t / 650 + i) * 3 - (1 - pop) * 10;
      if (x < -30 || x > view.w + 30 || y < -30 || y > view.h + 30) return;
      const R = 19 * k * (0.7 + 0.3 * Math.min(1, b.mult));          // 일손이 줄면 방울도 작아진다
      ctx.beginPath(); ctx.arc(x, y, R, 0, 6.2832);
      ctx.fillStyle = b.mult < 1 ? 'rgba(200,190,170,0.9)' : 'rgba(250,230,200,0.95)'; ctx.fill();
      ctx.strokeStyle = '#14110c'; ctx.lineWidth = 2.5; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x - 5, y + R - 2); ctx.lineTo(x, y + R + 7); ctx.lineTo(x + 5, y + R - 2); ctx.fillStyle = 'rgba(250,230,200,0.95)'; ctx.fill();
      ctx.fillStyle = '#1a150e'; ctx.font = 'bold 12px "Noto Sans KR",sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText((CHIP[b.res] || (RES_KO[b.res] || b.res).slice(0, 1)) + '+' + b.n, x, y + 1);
      ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
      hits.push({ kind: 'bubble', slot: room.slot, res: b.res, n: b.n, x: x - R - 4, y: y - R - 4, w: 2 * R + 8, h: 2 * R + 14 });
    });
  }
  function collectBubble(h) {
    bubbleAt[h.slot] = performance.now() + BUBBLE_GAP_MS;
    play('sfx_card_place.ogg', 0.35);
    const chip = $('#resbar [data-res="' + h.res + '"]');
    const fly = document.createElement('div');
    fly.className = 'flyer'; fly.textContent = '+' + h.n;
    fly.style.background = chip ? getComputedStyle(chip.querySelector('i')).backgroundColor : '#f0b055';
    fly.style.left = (h.x + h.w / 2) + 'px'; fly.style.top = (h.y + h.h / 2) + 'px';
    $('#flyers').appendChild(fly);
    const dst = chip ? chip.getBoundingClientRect() : { left: view.w / 2, top: 10, width: 0, height: 0 };
    const cvr = cv.getBoundingClientRect();
    requestAnimationFrame(() => {
      fly.style.transform = 'translate(' + (dst.left - cvr.left + dst.width / 2 - (h.x + h.w / 2)) + 'px,' + (dst.top - cvr.top + dst.height / 2 - (h.y + h.h / 2)) + 'px) scale(.7)';
      fly.style.opacity = '0.2';
    });
    setTimeout(() => { fly.remove(); if (chip) { chip.classList.remove('bump'); void chip.offsetWidth; chip.classList.add('bump'); } }, 660);
    const room = (ark.rooms || []).find(r => r.slot === h.slot);
    toast(((room && (catalog[room.id] || {}).name) || '') + '에서 ' + (RES_KO[h.res] || h.res) + ' ' + h.n + '만큼 나옵니다. 8시간마다 창고로 들어옵니다.');
  }

  // ── 작은 애니메이션: 되찾기(먼지 → 수면이 내려감 → 불이 켜짐, 약 1.1초) · 레벨업(번쩍 + 반짝) · 결과 글자 ──
  const anims = {};                                    // slot → {kind, t0}
  const words = [];                                    // {slot, text, color, t0}
  function animStart(slot, kind) { anims[slot] = { kind, t0: performance.now() }; }
  function drawRoomAnim(slot, ix, iy, iw, ih, t) {
    const a = anims[slot]; if (!a) return;
    const k = (t - a.t0) / (a.kind === 'reclaim' ? 1100 : 700);
    if (k >= 1 || k < 0) { delete anims[slot]; return; }
    ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
    if (a.kind === 'reclaim') {
      const dark = Math.max(0, 1 - k / 0.75);           // 불은 끝에 켜진다
      ctx.fillStyle = 'rgba(2,8,12,' + (0.7 * dark).toFixed(3) + ')'; ctx.fillRect(ix, iy, iw, ih);
      const water = Math.min(1, k / 0.7);                // 수면이 위에서 아래로 내려간다
      const fl = overlayImg('cell_flood'), top = iy + ih * water;
      if (water < 1) {
        if (fl) { ctx.save(); ctx.beginPath(); ctx.rect(ix, top, iw, iy + ih - top); ctx.clip(); ctx.drawImage(fl, ix, iy, iw, ih); ctx.restore(); }
        else { ctx.fillStyle = 'rgba(8,40,52,0.85)'; ctx.fillRect(ix, top, iw, iy + ih - top); }
        ctx.fillStyle = 'rgba(160,220,225,0.7)'; ctx.fillRect(ix, top - 2, iw, 3);
      }
      ctx.fillStyle = 'rgba(200,180,140,' + (0.5 * (1 - k)).toFixed(3) + ')';    // 먼지
      for (let i = 0; i < 24; i++) {
        const px = ix + ((i * 97) % 100) / 100 * iw, py = iy + ih * (0.9 - k * 0.6) - ((i * 37) % 40) * cam.z;
        ctx.beginPath(); ctx.arc(px + Math.sin(i + k * 6) * 8 * cam.z, py, Math.max(1, (3 + i % 4) * cam.z), 0, 6.2832); ctx.fill();
      }
      if (k > 0.75) { ctx.fillStyle = 'rgba(250,230,200,' + (0.5 * (1 - (k - 0.75) / 0.25)).toFixed(3) + ')'; ctx.fillRect(ix, iy, iw, ih); }
    } else {                                           // 레벨업
      ctx.fillStyle = 'rgba(255,240,210,' + (0.6 * (1 - k)).toFixed(3) + ')'; ctx.fillRect(ix, iy, iw, ih);
      ctx.fillStyle = '#ffe9b0';
      for (let i = 0; i < 10; i++) {
        const ang = i * 0.63, rr = (20 + k * 120) * cam.z;
        const px = ix + iw / 2 + Math.cos(ang) * rr * 2, py = iy + ih / 2 + Math.sin(ang) * rr;
        ctx.beginPath(); ctx.arc(px, py, Math.max(1.5, 5 * cam.z * (1 - k)), 0, 6.2832); ctx.fill();
      }
    }
    ctx.restore();
  }
  // 첫날 살짝 찌르기(S13): 일손 없는 생산 방에 은은한 초록 테두리 + 「한 분만」. 강제 안내가 아니다 — 누가 들어가면 사라진다
  function drawNudge(t) {
    const sl = K.ext.nudgeSlot; if (sl == null || carry || dragging) return;
    const pr = (ark.production || {})[String(sl)];
    if (!pr || (pr.staff || 0) > 0) { K.ext.nudgeSlot = null; return; }
    const r = rectOf(sl); if (!r) return;
    const a = 0.35 + 0.35 * Math.sin(t / 600);
    ctx.save(); ctx.strokeStyle = 'rgba(143,191,122,' + a.toFixed(3) + ')'; ctx.lineWidth = Math.max(2, 10 * cam.z);
    ctx.strokeRect(sx(r.x) - 4, sy(r.y) - 4, r.w * cam.z + 8, r.h * cam.z + 8); ctx.restore();
    const lbl = '한 분만 와 주세요', x = sx(r.x + r.w / 2), y = sy(r.y + r.h) + 18;
    ctx.font = 'bold 13px "Noto Sans KR",sans-serif';
    const tw = ctx.measureText(lbl).width + 16;
    ctx.fillStyle = 'rgba(20,30,18,0.9)'; ctx.fillRect(x - tw / 2, y - 11, tw, 22);
    ctx.fillStyle = '#b8e0a6'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(lbl, x, y);
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  }
  function drawLidMark(t) {
    const raid = cb && cb.raid;
    if (!raid || !raid.lid_revealed || raid.target_slot == null || raid.stage === 'done' || raid.resolved) return;
    const r = rectOf(raid.target_slot); if (!r) return;
    const x = sx(r.x + r.w / 2), y = sy(r.y) - 18 - Math.abs(Math.sin(t / 380)) * 8;
    ctx.fillStyle = '#ffd59a'; ctx.strokeStyle = '#14110c'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(x - 14, y - 16); ctx.lineTo(x + 14, y - 16); ctx.lineTo(x, y); ctx.closePath(); ctx.stroke(); ctx.fill();
  }
  function floatWord(slot, text, color) { words.push({ slot, text: fillText(text), color, t0: performance.now() }); }
  function drawWords(t) {
    for (let i = words.length - 1; i >= 0; i--) {
      const w = words[i], k = (t - w.t0) / 2600;
      if (k >= 1) { words.splice(i, 1); continue; }
      const r = w.slot != null ? rectOf(w.slot) : null;
      const x = r ? sx(r.x + r.w / 2) : view.w / 2, y = (r ? sy(r.y + r.h / 2) : view.h / 2) - k * 40;
      const a = k < 0.15 ? k / 0.15 : (k > 0.7 ? (1 - k) / 0.3 : 1), s = k < 0.15 ? 0.6 + 0.4 * (k / 0.15) : 1;
      ctx.save(); ctx.globalAlpha = a; ctx.translate(x, y); ctx.scale(s, s);
      ctx.font = 'bold 40px "Noto Sans KR",sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.lineWidth = 7; ctx.strokeStyle = 'rgba(10,8,6,0.9)'; ctx.strokeText(w.text, 0, 0);
      ctx.fillStyle = w.color; ctx.fillText(w.text, 0, 0);
      ctx.restore();
    }
  }
  const RESULT_WORD = { held: ['막았다', '#8fbf7a'], scarred: ['금이 갔다', '#f0b055'], breached: ['잃었다', '#e07a62'], passed: ['지나감', '#cfe6e4'] };

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
      toast('방이나 홀 위에 놓아 주세요');
      return;
    }
    if (d.moved > 6) return;                   // 카메라를 끌었을 뿐이다

    const s = slotAt(px, py);
    if (carry) {
      // **들고 있을 때는 '놓기'가 먼저다.** 사람이 있는 방을 탭했다고 그 방 사람을 새로 집으면
      // 영원히 못 옮긴다(폰에서 실제로 걸린 결함).
      if (d.person && d.person.id === carry.id) { setCarry(null); closePanel(); toast('내려놓았습니다'); return; }
      if (s != null) { place(carry.id, s); return; }
      if (hitAt(px, py, 'hall')) { place(carry.id, null); return; }
      setCarry(null); toast('그만두었습니다'); return;
    }
    if (d.person) {                            // 탭 1: 사람을 집는다 — 그 사람의 카드도 함께 연다
      setCarry({ id: d.person.id, name: d.person.name, role: d.person.role });
      closeCard(); closePops();
      const cap = d.person.from == null && K.ext.podCaption ? K.ext.podCaption(d.person.id) : '';
      toast((cap ? cap + ' ' : '') + d.person.name + ' 님, 옮겨 갈 방을 눌러 주세요');
      return;
    }
    if (hitAt(px, py, 'gift') && K.ext.onGift) { K.ext.onGift(); return; }
    const gh = hitAt(px, py, 'guest'); if (gh && K.ext.onGuest) { K.ext.onGuest(gh.id); return; }
    const bh = hitAt(px, py, 'box'); if (bh && K.ext.onBox) { K.ext.onBox(bh.id); return; }
    const bb = hitAt(px, py, 'bubble');
    if (bb) { collectBubble(bb); return; }
    const sh = hitAt(px, py, 'shelf');
    if (sh) {                                  // S16: 선반 물건을 누르면 그 유물 카드(틀·희귀도 이름). 창고 카드는 카드 아래 단추로
      closePanel();
      const rs = s != null ? s : shelfRoomSlot();
      if (K.ext.cards) { closeCard(); K.ext.cards.peek(shelfCardOf(sh.item), '', { label: '창고 보기', fn: () => openCard({ slot: rs }) }); }
      else { toast(shelfLine(sh.item)); openCard({ slot: rs }); }
      return;
    }
    if (s != null) { closePanel(); openCard({ slot: s }); return; }
    if (hitAt(px, py, 'hall')) { closePanel(); openCard({ hall: true }); return; }
    const sc = hitAt(px, py, 'sealed');
    if (sc) { closePanel(); openCard({ sealed: sc.cell }); return; }
    closePanel(); closeCard(); closePops();
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
  $('#rgain').addEventListener('click', async (e) => {
    const kb = e.target.closest('button[data-keep]');
    if (kb) { const box = $('#rgain .swapbtns'); if (box) box.remove(); const q = $('#rgain .swapq');
      if (q) q.textContent = plain(((lastScan || {}).swap_offer || {}).kept_ko || TT('shelf.full.kept', { item: ((lastScan || {}).card || {}).name || '' }, STO() + '에 넣어 두었습니다.')); return; }
    const b = e.target.closest('button[data-swap]'); if (!b) return;
    e.stopPropagation(); b.disabled = true;
    const r = await shelfSwap(b.dataset.swap, parseInt(b.dataset.slot, 10));
    if (r && lastScan) { lastScan.shelf_slot = r.slot; lastScan.swapped = true; const box = $('#rgain .swapbtns'); if (box) box.remove();
      const q = $('#rgain .swapq'); if (q) q.textContent = plain(r.ko || TT('shelf.full.placed', { item: ((lastScan || {}).card || {}).name || '' }, '선반 ' + (r.slot + 1) + '번째 칸에 올렸습니다.'));
      $('#shelfBtn').textContent = '선반 보기'; }
  });
  $('#panelBody').addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-unstore]'); if (!b) return;
    b.disabled = true;
    const r = await shelfSwap(b.dataset.unstore, null);
    if (r && sel) openPanel(sel.slot);
  });
  // S16: 개봉 중에 카드 화면 아무 데나 누르면 바로 앞면(건너뛰기)
  $('#scanCard').addEventListener('pointerdown', (e) => { if (K.ext.cards && K.ext.cards.running() && !e.target.closest('#shelfBtn')) { e.preventDefault(); K.ext.cards.skip(); } });
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
  // S13-B: base_collect.js 가 쓰는 안쪽 손잡이(화면 모듈끼리만). 상태는 읽기만 하고, 바꾸는 길은 api → apply 하나다
  const K = {
    api, toast, play, esc, plain, uid, fill: fillText, josa, say, enqueue, whenPanelGone, qLog,
    get ark() { return ark; }, get cb() { return cb; }, get catalog() { return catalog; }, RES_KO, RAR_KO,
    propSpec: (id) => propSpec(id), propForCategory: (c) => propForCategory(c),
    apply: (st) => apply(st), reload: () => load(false),
    onApply: (f) => applyHooks.push(f), onLoad: (f) => loadHooks.push(f),
    panel(html) { closeCard(); closePops(); sel = null; $('#panelBody').innerHTML = html; $('#panel').hidden = false; placePanel(); return $('#panelBody'); },
    closePanel: () => closePanel(), closeMenu: () => { $('#menu').hidden = true; $('#menubtn').setAttribute('aria-expanded', 'false'); },
    propImgSrc: (cat) => { const id = propForCategory(cat); return id ? '/static/art/props/x4/' + id + '.png' : ''; },
    flyToSlot: (s) => flyToSlot(s), openCard: (c) => openCard(c), floatWord: (slot, t, c) => floatWord(slot, t, c),
    ext: {},                                           // base_collect.js 가 채운다(방 카드·그리기에 끼우는 자리)
  };
  K.ext.drawSealedBox = drawSealedBox;
  K.ext.cardTestReveal = (...a) => K_cardTest && K_cardTest(...a);   // ★ S16 시험대
  window.ARKBASE = {
    _k: K,
    reload: () => load(false), refreshRaid, fit, uid,
    slotBox: (s) => { const q = rectOf(s); return q ? { x: sx(q.x), y: sy(q.y), w: q.w * cam.z, h: q.h * cam.z } : null; },
    // ★ S12-B 검수용: 맵·카메라·프레임 시간
    map: () => ({ id: window.ArkMap.id, provisional: MAP().provisional, world: MAP().world, layers: Object.keys(layerImgs),
                  slots: Array.from({ length: slots }, (_, i) => { const c = cellOf(i); return c ? { slot: i, cell: c.id, storey: c.storey, col: c.col } : null; }).filter(Boolean),
                  trenchY: zoneY(TRENCH_M), layoutTrenchY: MAP().depth.trenchY }),
    cam: () => Object.assign({}, cam, { zmin: zMin() }),
    sil: () => silDbg,
    // ★ S13 검수: 화면에 보이는 글(DOM 글자 + 지금까지 띄운 토스트 + 캔버스 글자)에 '{' 가 몇 번 나왔나
    braceCheck: () => {
      const dom = (document.body.innerText.match(/[{}]/g) || []).length;
      return { dom, toasts: braceLog.toasts, canvas: braceLog.canvas, samples: braceLog.samples.slice(0, 5) };
    },
    bubbles: () => hits.filter(h => h.kind === 'bubble').map(h => ({ slot: h.slot, res: h.res, n: h.n, cx: h.x + h.w / 2, cy: h.y + h.h / 2 })),   // ★ 검수용                                 // ★ 검수용: 지금 다가오는 실루엣의 세계 x
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
    flips: () => Object.assign({}, flipLog),
    hatchCycle: (ms) => hatchCycle(ms),                // 탐사대·도착 체계가 부를 함수(해치 ~2 s 열림 + 물방울)
    hatchOpen: () => performance.now() < hatchOpenUntil,
    pod: () => Object.keys(podSeat).map(id => ({ id, seat: podSeat[id], pose: (podSpot(podSeat[id]) || {}).pose })),   // ★ 검수용
    podPoses: () => Object.assign({}, podPoseLog),     // ★ 검수용           // ★ S12-B3 검수용: 반전해 그린 클립 수
    moveLog: () => moveLog.slice(),
    carryLog: () => carryLog.slice(), queue: () => ({ busy: modalBusy && modalBusy.tag, wait: modalQ.map(x => x.tag), held: heldSay.slice(), log: qLog.slice() }),   // ★ S18 검수용
    josa: (w, p) => josa(w, p),
    openTrade: (sl) => openTrade(sl),                  // ★ S18 검수용                    // 엘리베이터 배차 기록(시각은 performance.now 초)
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
