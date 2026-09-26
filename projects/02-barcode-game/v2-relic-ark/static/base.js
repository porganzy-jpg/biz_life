/* 잔해 방주 — 1막 거점 화면(정면 평면 단면)의 뼈대.
 *
 * 근거
 *   DECISIONS 2026-09-23  ① 1막 거점은 정면 평면 단면(원근 없음) ② 성장 방향은 아래
 *                         ③ 방마다 고유 색(전부 따뜻한 쪽, 물보다 밝게)
 *   docs/refs/REF_CROSS_SECTION.md  §1 원리 10가지(두꺼운 검은 테두리 = 우리에겐 물, 빈 방 없음, UI 는 가장자리)
 *   docs/refs/REF_ART_FLAT_FOLK.md  §1·§5 평면 채색·음영 1~2단·청록은 물에만
 *   docs/SCRIPT_first_10min_deep.md 3:00 공기 게이지는 숫자가 아니라 줄어드는 띠
 *
 * 이 파일은 **아트가 오기 전의 구조**다. 방은 색 사각형과 격자, 캐릭터는 스프라이트가 있으면 쓰고
 * 없으면 색 사각형. 배경 그라데이션(위 광층 → 아래 해구)과 층·척추·좌우 방 배치가 진짜 산출물이다.
 */
(() => {
  'use strict';

  // ── 세계 좌표(px). 1층 = 방 2칸 + 가운데 척추 ──────────────────
  const ROOM_W = 208, ROOM_H = 112, SPINE_W = 70, FLOOR_GAP = 18;
  const FLOOR_PITCH = ROOM_H + FLOOR_GAP;          // 층 간격
  const DEPTH_PER_FLOOR = 60;                      // m. server.py 의 같은 상수와 맞춘다
  const PAD = 8;                                   // 방 둘레 어두운 여백(= 물)
  const PPM = 110, CELL = 256, BASELINE = 240;     // 캐릭터 스프라이트 규약(front_meta.json)
  let DOME_FLOOR = 1;                              // 깊이 0 m 의 층(= 시작 방 slot 2 의 층). 서버가 내려준다
  const CHAR_SCALE = 0.34;                         // 1.6 m → 176 px → 약 60 px

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
    rock:      { base: '#a2603a', shade: '#74432a', floor: '#4d2d1c' },  // 적동
    lot:       { base: '#b8ae9c', shade: '#877f70', floor: '#57534a' },
    _default:  { base: '#b4712f', shade: '#815022', floor: '#54351a' },
  };
  const ROLE_COLOR = {
    scout: '#8c9161', cook: '#c08a33', medic: '#d8c9a3', engineer: '#b4712f',
    farmer: '#8a7a4a', scholar: '#c6a23a', trader: '#a2603a', kid: '#e6d7b0',
  };
  const RES_KO = { food: '식량', water: '물', med: '의약', power: '전력', parts: '부품', morale: '사기',
                   cloth: '직물', trade: '교역', knowledge: '지식', scrap: '잔해', chem: '화학' };
  const CORE_RES = ['food', 'water', 'parts', 'morale'];

  // ── 바탕 ─────────────────────────────────────────────────
  const $ = (s) => document.querySelector(s);
  const cv = $('#cv'), ctx = cv.getContext('2d');
  const uid = (() => {
    try { let u = localStorage.getItem('ark_uid'); if (!u) { u = 'u' + Math.random().toString(36).slice(2, 10); localStorage.setItem('ark_uid', u); } return u; }
    catch (e) { return 'anon'; }
  })();
  const qs = new URLSearchParams(location.search);
  const CHAR_VARIANT = qs.get('chars') || 'b';       // ?chars=a|b|none — 캐릭터 담당의 A/B 판정 전까지
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let ark = null, catalog = {}, slots = 10, floorSlots = 2, spots = [];
  let sel = null;                                     // {slot} 선택된 칸
  let cam = { x: 0, y: 220, z: 1 }, view = { w: 0, h: 0, dpr: 1 };

  function toast(m) {
    const t = $('#toast'); t.textContent = m; t.classList.add('on');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), 2200);
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

  // ── 캐릭터 스프라이트: 있으면 쓰고, 없으면 색 사각형 ─────────
  // 캐릭터 담당이 A/B 판정 중이라 경로가 바뀔 수 있다. 실패해도 콘솔 에러를 내지 않는다.
  const sprites = {};
  function sprite(role) {
    if (CHAR_VARIANT === 'none') return null;
    let s = sprites[role];
    if (s === undefined) {
      s = sprites[role] = { img: new Image(), ok: false, tried: 0 };
      s.img.onload = () => { s.ok = s.img.naturalWidth > 0; };
      s.img.onerror = () => {
        s.ok = false;
        if (s.tried === 0) { s.tried = 1; s.img.src = '/static/art/chars/front/a/' + role + '.png'; }
      };
      s.img.src = '/static/art/chars/front/' + CHAR_VARIANT + '/' + role + '.png';
    }
    return s.ok ? s : null;
  }

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

  // ── 카메라 ────────────────────────────────────────────────
  const sx = (wx) => (wx - cam.x) * cam.z + view.w / 2;
  const sy = (wy) => (wy - cam.y) * cam.z + view.h / 2;
  const wxOf = (px) => (px - view.w / 2) / cam.z + cam.x;
  const wyOf = (py) => (py - view.h / 2) / cam.z + cam.y;

  function fit() {
    const b = worldBounds();
    const z = Math.min(view.w / (b.x1 - b.x0), view.h / (b.y1 - b.y0)) * 0.94;
    cam.z = Math.max(0.18, Math.min(2.2, z));
    cam.x = (b.x0 + b.x1) / 2; cam.y = (b.y0 + b.y1) / 2;
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
    // 위쪽 끝을 물 색으로 덮어 두면 화면 밖까지 같은 색이 이어진다
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

  // 부유물(D5). 물은 가만히 있지 않는다 — 저쪽(바위 매트)보다 우리가 유리한 지점
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
    // 심해 힐링 스팟: 깊이가 곧 지도다. data/spots_deep.json 이 없으면 목록이 비어 아무것도 안 그린다.
    // 아직 소문으로 열지 않은 곳은 그리지 않는다 — 발견은 스캔이 연다(/api/spots.unlocked).
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
    // 오른쪽 가장자리의 깊이 눈금 — UI 는 가장자리에만(§1-9)
    const x = view.w - 14;
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (const z of ZONES) {
      const y0 = sy(z.y0), y1 = sy(z.y1);
      if (y1 < 0 || y0 > view.h) continue;
      ctx.strokeStyle = 'rgba(150,200,200,0.16)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x - 40, y0); ctx.lineTo(x, y0); ctx.stroke();
      // 오른쪽 아래 구석은 카메라 버튼 자리라 비워 둔다
      const my = Math.max(18, Math.min(view.h - 72, (Math.max(y0, 0) + Math.min(y1, view.h)) / 2));
      ctx.fillStyle = 'rgba(190,225,222,0.42)'; ctx.font = '11px "Noto Sans KR",sans-serif';
      ctx.fillText(z.ko, x, my);
    }
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  }

  function drawSpine() {
    // 유리 척추 = 승강 통로. 층 사이를 잇는 유일한 세로선(§1-5: 동선이 색으로 보인다)
    const top = rectOf(0).y + 30, bot = (floorCount() - DOME_FLOOR) * FLOOR_PITCH - FLOOR_GAP;
    const x0 = sx(-SPINE_W / 2), x1 = sx(SPINE_W / 2), y0 = sy(top), y1 = sy(bot);
    ctx.fillStyle = '#0d1512'; ctx.fillRect(x0 - 3, y0, (x1 - x0) + 6, y1 - y0);
    const g = ctx.createLinearGradient(x0, 0, x1, 0);
    g.addColorStop(0, '#1b1a12'); g.addColorStop(0.5, '#3a3018'); g.addColorStop(1, '#1b1a12');
    ctx.fillStyle = g; ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.strokeStyle = '#14110c'; ctx.lineWidth = Math.max(1, 3 * cam.z);
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    // 층마다 사다리 칸
    ctx.strokeStyle = 'rgba(240,176,85,0.22)'; ctx.lineWidth = Math.max(1, 2 * cam.z);
    for (let y = top + 14; y < bot; y += 34) {
      const yy = sy(y); if (yy < -10 || yy > view.h + 10) continue;
      ctx.beginPath(); ctx.moveTo(x0 + 6, yy); ctx.lineTo(x1 - 6, yy); ctx.stroke();
    }
  }

  function drawDome() {
    // 시작은 무광층에 박힌 유리돔 하나. 아래로 척추가 뻗는다(REF_CROSS_SECTION §4)
    const r = rectOf(0), rr = rectOf(1);
    const left = sx(r.x - PAD), right = sx(rr.x + rr.w + PAD), cxs = (left + right) / 2;
    const base = sy(r.y - 2), h = 104 * cam.z;
    ctx.beginPath(); ctx.ellipse(cxs, base, (right - left) / 2, h, 0, Math.PI, 0);
    ctx.fillStyle = 'rgba(214,201,163,0.10)'; ctx.fill();
    ctx.strokeStyle = 'rgba(230,215,176,0.55)'; ctx.lineWidth = Math.max(1, 3 * cam.z); ctx.stroke();
    ctx.strokeStyle = 'rgba(230,215,176,0.18)'; ctx.lineWidth = Math.max(1, 1.5 * cam.z);
    for (let i = 1; i < 5; i++) {   // 유리 뼈대
      const a = Math.PI + (Math.PI * i) / 5;
      ctx.beginPath(); ctx.moveTo(cxs, base);
      ctx.lineTo(cxs + Math.cos(a) * (right - left) / 2, base + Math.sin(a) * h); ctx.stroke();
    }
  }

  function roomColor(id) { return ROOM_COLOR[id] || ROOM_COLOR._default; }

  function drawRoom(slot, room, people, t) {
    const r = rectOf(slot);
    const x = sx(r.x), y = sy(r.y), w = r.w * cam.z, h = r.h * cam.z;
    if (x > view.w + 40 || x + w < -40 || y > view.h + 40 || y + h < -40) return;

    if (!room) {   // 빈 자리 — 여기로 자란다(성장 방향은 아래)
      if (r.floor < DOME_FLOOR) { return; }      // 돔 상부는 유리 천장. 증축 자리가 아니다
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

    if (room.flooded) {   // 잃은 방은 사라지지 않고 물이 찬 채로 남는다(첫 10분 8:00 비트)
      ctx.fillStyle = '#082028'; ctx.fillRect(ix, iy, iw, ih);
      ctx.strokeStyle = '#14110c'; ctx.lineWidth = Math.max(1, 3 * cam.z);
      ctx.strokeRect(ix, iy, iw, ih);
      return;
    }

    // 평면 채색 + 음영 1~2단 (FLAT_FOLK §1-3). 그라데이션 없음
    ctx.fillStyle = col.base; ctx.fillRect(ix, iy, iw, ih);
    ctx.fillStyle = col.shade; ctx.fillRect(ix, iy, iw, ih * 0.26);               // 뒷벽 위쪽 그늘
    ctx.fillStyle = col.floor; ctx.fillRect(ix, iy + ih * 0.80, iw, ih * 0.20);   // 바닥
    // 방마다 반복 무늬 — 정교한 묘사 대신 패턴(FLAT_FOLK §1-5)
    ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
    ctx.strokeStyle = 'rgba(20,17,12,0.13)'; ctx.lineWidth = Math.max(1, 1 * cam.z);
    for (let gx = ix + 16 * cam.z; gx < ix + iw; gx += 22 * cam.z) {
      ctx.beginPath(); ctx.moveTo(gx, iy + ih * 0.26); ctx.lineTo(gx, iy + ih * 0.80); ctx.stroke();
    }
    // 랜턴 하나 = 주색 하나
    const lx = ix + iw * 0.5, ly = iy + ih * 0.20;
    const lg = ctx.createRadialGradient(lx, ly, 0, lx, ly, ih * 0.9);
    lg.addColorStop(0, 'rgba(240,176,85,0.40)'); lg.addColorStop(1, 'rgba(240,176,85,0)');
    ctx.fillStyle = lg; ctx.fillRect(ix, iy, iw, ih);
    ctx.fillStyle = '#f0b055'; ctx.beginPath();
    ctx.arc(lx, ly, Math.max(1.2, 3 * cam.z), 0, 6.2832); ctx.fill();
    ctx.restore();

    // 두꺼운 검은 테두리: 방과 방 사이를 막아 각각 "불 켜진 상자"로 읽히게 한다(§1-3)
    ctx.strokeStyle = sel && sel.slot === slot ? '#f0b055' : '#14110c';
    ctx.lineWidth = Math.max(1.5, (sel && sel.slot === slot ? 4 : 3) * cam.z);
    ctx.strokeRect(ix, iy, iw, ih);

    drawPeople(people, ix, iy, iw, ih, t);

    if (cam.z > 0.4) {
      const nm = (catalog[room.id] && catalog[room.id].name) || room.id;
      ctx.font = (11 * Math.min(1.3, cam.z)) + 'px "Noto Sans KR",sans-serif';
      ctx.fillStyle = 'rgba(20,17,12,0.75)';
      const tw = ctx.measureText(nm).width + 10 * cam.z;
      ctx.fillRect(ix, iy, tw, 16 * Math.min(1.3, cam.z));
      ctx.fillStyle = '#e6d7b0';
      ctx.textBaseline = 'middle';
      ctx.fillText(nm, ix + 5 * cam.z, iy + 8 * Math.min(1.3, cam.z));
      ctx.textBaseline = 'alphabetic';
    }
  }

  function drawPeople(people, ix, iy, iw, ih, t) {
    if (!people || !people.length) return;
    const floorY = iy + ih * 0.86;                       // 사람이 서는 바닥선
    const step = iw / (people.length + 1);
    people.forEach((p, i) => {
      const px = ix + step * (i + 1);
      const bob = Math.sin(t / 700 + i * 1.7) * 0.8 * cam.z;
      const s = sprite(p.role);
      if (s) {
        const k = CHAR_SCALE * cam.z;
        const frame = Math.floor(t / 170 + i) % 5;       // Idle 5프레임(front_meta.json)
        try {
          ctx.drawImage(s.img, frame * CELL, 0, CELL, CELL,
                        px - (CELL / 2) * k, floorY - BASELINE * k + bob, CELL * k, CELL * k);
          if (p.injured) { ctx.fillStyle = 'rgba(140,59,46,0.45)'; ctx.fillRect(px - 6 * cam.z, floorY - 46 * cam.z, 12 * cam.z, 4 * cam.z); }
          return;
        } catch (e) { /* 스프라이트가 아직 덜 왔다 — 아래 색 사각형으로 */ }
      }
      // 폴백: 색 사각형(캐릭터 담당 A/B 판정 전)
      const hgt = (p.role === 'kid' ? 30 : 40) * cam.z, wid = 13 * cam.z;
      ctx.fillStyle = ROLE_COLOR[p.role] || '#d8c9a3';
      ctx.fillRect(px - wid / 2, floorY - hgt + bob, wid, hgt);
      ctx.fillStyle = '#14110c';
      ctx.fillRect(px - wid / 2, floorY - hgt + bob, wid, Math.max(1, 3 * cam.z));   // 머리
      if (p.injured) { ctx.fillStyle = '#8c3b2e'; ctx.fillRect(px - wid / 2, floorY - hgt * 0.55 + bob, wid, Math.max(1, 3 * cam.z)); }
    });
  }

  // 주민 배치: 방마다 사람이 있어야 한다(§1-6 빈 방이 없다). uid 로 고정 — 새로고침해도 같은 자리(D6)
  function assignPeople() {
    const map = {};
    const rooms = (ark.rooms || []).slice().sort((a, b) => a.slot - b.slot);
    const res = (ark.residents_list || []).filter(r => r && r.role);
    if (!rooms.length) return map;
    res.forEach((p, i) => {
      const r = rooms[i % rooms.length];
      (map[r.slot] = map[r.slot] || []).push(p);
    });
    return map;
  }

  let raf = 0;
  function frame(t) {
    raf = requestAnimationFrame(frame);
    if (!view.w) return;
    ctx.clearRect(0, 0, view.w, view.h);
    drawWater(t);
    drawMotes(t);
    if (!ark) return;
    drawDome();
    drawSpine();
    const byslot = {}; (ark.rooms || []).forEach(r => { byslot[r.slot] = r; });
    const people = assignPeople();
    drawSpots(t);
    for (let s = 0; s < slots; s++) drawRoom(s, byslot[s], people[s], t);
    drawZones();
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

  function openPanel(slot) {
    sel = { slot };
    const room = (ark.rooms || []).find(r => r.slot === slot);
    const f = floorOf(slot), depth = (f - DOME_FLOOR) * DEPTH_PER_FLOOR;
    const fl = (f - DOME_FLOOR + 1);                 // 돔이 앉은 층이 1층. 아래로 2·3·4층
    const body = $('#panelBody');
    if (room) {
      const spec = catalog[room.id] || {};
      const people = assignPeople()[slot] || [];
      body.innerHTML =
        '<h2>' + esc(spec.name || room.id) + '</h2>' +
        '<p class="sub">' + fl + '층 · 깊이 ' + depth + 'm · ' + esc(zoneAt(f)) + '</p>' +
        (spec.desc ? '<p class="desc">' + esc(spec.desc) + '</p>' : '') +
        '<h3>하루 생산</h3><div class="kv">' +
        (Object.entries(spec.produces || {}).map(([k, v]) =>
          '<span>' + esc(RES_KO[k] || k) + ' +' + esc(v) + '</span>').join('') || '<span>—</span>') +
        '</div>' +
        '<h3>막아 내는 것</h3><div class="kv">' +
        ((spec.counters || []).map(c => '<span>#' + esc(c) + '</span>').join('') || '<span>—</span>') +
        '</div>' +
        '<h3>여기 있는 사람</h3>' +
        (people.length ? people.map(p =>
          '<div class="who"><i style="background:' + (ROLE_COLOR[p.role] || '#d8c9a3') + '"></i>' +
          '<b>' + esc(p.name) + '</b><em>' + esc(p.role_ko || p.role) +
          (p.imprints && p.imprints.length ? ' · 刻 ' + p.imprints.length : '') + '</em>' +
          (p.injured ? '<em class="hurt">부상</em>' : '') + '</div>').join('')
          : '<div class="who"><em>아무도 없다</em></div>');
    } else {
      if (f < DOME_FLOOR) {
        body.innerHTML = '<h2>돔 상부</h2><p class="sub">깊이 0m 위 · 유리 천장</p>' +
          '<p class="desc">여기엔 더 놓을 자리가 없다. 방주는 아래로 자란다.</p>';
        $('#panel').hidden = false; return;
      }
      const ids = Object.keys(catalog);
      body.innerHTML =
        '<h2>빈 자리</h2>' +
        '<p class="sub">' + fl + '층 · 깊이 ' + depth + 'm · ' + esc(zoneAt(f)) + '</p>' +
        '<p class="desc">아래로 내려갈수록 유물이 좋아지고 위험해진다.</p>' +
        '<h3>증축</h3><div class="blist">' +
        ids.map(id => {
          const lack = lacking(id);
          return '<button class="bopt' + (lack.length ? ' lack' : '') + '" data-room="' + esc(id) + '"' +
            (lack.length ? ' disabled' : '') + '><b>' + esc(catalog[id].name || id) + '</b>' +
            '<small>' + esc(lack.length ? '부족: ' + lack.join(' · ') : costLine(id)) + '</small></button>';
        }).join('') + '</div>';
      body.querySelectorAll('.bopt[data-room]').forEach(b => {
        b.addEventListener('click', () => build(b.dataset.room, slot));
      });
    }
    $('#panel').hidden = false;
  }
  function closePanel() { sel = null; $('#panel').hidden = true; }

  function zoneAt(floor) {
    const y = (floor - DOME_FLOOR) * FLOOR_PITCH;
    const z = ZONES.find(z => y >= z.y0 && y < z.y1);
    return z ? z.ko : '무광층';
  }

  async function build(roomId, slot) {
    try {
      const st = await api('/api/ark/build', { room_id: roomId, slot });
      apply(st);
      toast(((catalog[roomId] || {}).name || roomId) + ' 증축');
      openPanel(slot);
    } catch (e) { toast(e.message || '증축하지 못했다'); }
  }

  // ── 상태 반영 ─────────────────────────────────────────────
  function apply(st) {
    ark = st;
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
  }

  async function load(first) {
    try {
      const st = await api('/api/ark?uid=' + encodeURIComponent(uid));
      apply(st);
      if (first) fit();
      // 스팟은 있으면 그리고 없으면 만다(파일이 없어도 화면이 죽지 않는다)
      try {
        const rows = await api('/api/spots?uid=' + encodeURIComponent(uid));
        spots = (rows || []).filter(r => r && r.act === 1 && r.pos);
      } catch (e2) { spots = []; }
    } catch (e) { toast('방주를 불러오지 못했다 — ' + (e.message || '')); }
  }

  // ── 입력 ─────────────────────────────────────────────────
  let drag = null;
  cv.addEventListener('pointerdown', (e) => {
    drag = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y, moved: 0 };
    cv.setPointerCapture(e.pointerId); cv.classList.add('dragging');
  });
  cv.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    drag.moved = Math.max(drag.moved, Math.abs(dx) + Math.abs(dy));
    cam.x = drag.cx - dx / cam.z; cam.y = drag.cy - dy / cam.z;
  });
  cv.addEventListener('pointerup', (e) => {
    const wasDrag = drag && drag.moved > 6;
    drag = null; cv.classList.remove('dragging');
    if (wasDrag || !ark) return;
    const r = cv.getBoundingClientRect(), wx = wxOf(e.clientX - r.left), wy = wyOf(e.clientY - r.top);
    for (let s = 0; s < slots; s++) {
      const q = rectOf(s);
      if (wx >= q.x && wx <= q.x + q.w && wy >= q.y && wy <= q.y + q.h) { openPanel(s); return; }
    }
    closePanel();
  });
  cv.addEventListener('pointercancel', () => { drag = null; cv.classList.remove('dragging'); });
  cv.addEventListener('wheel', (e) => {
    e.preventDefault();
    const r = cv.getBoundingClientRect();
    zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });

  $('#zin').addEventListener('click', () => zoomAt(view.w / 2, view.h / 2, 1.2));
  $('#zout').addEventListener('click', () => zoomAt(view.w / 2, view.h / 2, 1 / 1.2));
  $('#zfit').addEventListener('click', fit);
  $('#panelClose').addEventListener('click', closePanel);
  window.addEventListener('resize', () => { resize(); });

  // 다른 화면(index)과 같은 규약: 밖에서 쓸 수 있게 몇 개만 연다
  window.ARKBASE = { reload: () => load(false), fit, uid };

  resize(); fit(); raf = requestAnimationFrame(frame); load(true);
})();
