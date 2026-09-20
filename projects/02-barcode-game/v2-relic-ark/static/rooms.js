/* 잔해 방주 — 절차적 픽셀 룸 렌더러 (결정 #4: 방주는 도트)
   192×128 픽셀 캔버스에 4px 그리드로 그린 뒤 CSS image-rendering:pixelated로 확대.
   외부 이미지 없이 일관된 스타일. 나중에 손으로 그린 타일로 교체 가능. */
(() => {
  const W = 192, H = 128, P = 4; // 논리 해상도, 픽셀 크기
  const C = {
    wall: '#3a3631', wall2: '#443f39', wallDk: '#2a2723', floor: '#5a4a38', floor2: '#4a3d2e', beam: '#2a2521',
    lamp: '#F2A93B', lampHi: '#FFE1A6', wood: '#8a6a44', wood2: '#6e5336', metal: '#7d8790', metal2: '#5c656d',
    red: '#C8442F', yellow: '#E0B54A', orange: '#E0813A', green: '#7DE0A8', cyan: '#4FB7E6', blue: '#3E7EA6', white: '#E8DFCB', paper: '#DED3BB',
    earth: '#2a231c', earth2: '#332a21', rock: '#5a564d', root: '#5a4020', weed: '#4f6a3a', sky: '#6d6a63', rubble: '#6E6A62',
  };
  function rng(seed) { let h = 2166136261; for (const ch of String(seed)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return () => { h += 0x6D2B79F5; let t = h; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const px = (x, gx, gy, w, h, c) => { x.fillStyle = c; x.fillRect(gx * P, gy * P, w * P, h * P); }; // 그리드 단위 사각형
  const GW = W / P, GH = H / P; // 48 × 32 그리드

  function base(x, r, lampColor, dim) {
    // 벽 (콘크리트 블록 패턴)
    px(x, 0, 0, GW, GH, C.wall);
    for (let gy = 0; gy < GH - 4; gy += 3) for (let gx = (gy / 3) % 2 ? 3 : 0; gx < GW; gx += 6) px(x, gx, gy, 5, 2, r() > .5 ? C.wall2 : C.wall);
    for (let i = 0; i < 18; i++) px(x, Math.floor(r() * GW), Math.floor(r() * (GH - 5)), 1, 1, C.wallDk); // 얼룩
    px(x, 0, 0, GW, 2, C.beam);                          // 천장 보
    px(x, 0, GH - 4, GW, 4, C.floor); px(x, 0, GH - 4, GW, 1, C.floor2); // 바닥
    for (let gx = 0; gx < GW; gx += 8) px(x, gx, GH - 3, 1, 3, C.floor2);
    if (lampColor && !dim) {                              // 랜턴 + 빛
      px(x, GW / 2 - 1, 2, 2, 3, C.beam); px(x, GW / 2 - 2, 5, 4, 3, lampColor); px(x, GW / 2 - 1, 6, 2, 1, C.lampHi);
      const g = x.createRadialGradient(W / 2, 36, 6, W / 2, 60, 120); g.addColorStop(0, hexA(lampColor, .38)); g.addColorStop(1, 'rgba(0,0,0,0)');
      x.fillStyle = g; x.fillRect(0, 0, W, H);
    }
    if (dim) { x.fillStyle = 'rgba(0,0,0,.45)'; x.fillRect(0, 0, W, H); }
  }
  const hexA = (h, a) => { const n = parseInt(h.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
  const shelf = (x, gx, gy, w) => { px(x, gx, gy, w, 1, C.wood); px(x, gx, gy + 1, w, 1, C.wood2); };
  const packet = (x, gx, gy, c) => { px(x, gx, gy, 2, 3, c); px(x, gx, gy, 2, 1, C.white); };
  const can = (x, gx, gy) => { px(x, gx, gy, 2, 3, C.metal); px(x, gx, gy, 2, 1, C.metal2); };
  const sack = (x, gx, gy) => { px(x, gx, gy + 1, 4, 3, C.wood); px(x, gx + 1, gy, 2, 1, C.wood2); };
  const person = (x, gx, gy, c) => { px(x, gx, gy, 2, 2, C.paper); px(x, gx, gy + 2, 2, 4, c); px(x, gx, gy + 6, 1, 2, C.beam); px(x, gx + 1, gy + 6, 1, 2, C.beam); };

  const ROOMS = {
    pantry(x, r) {
      base(x, r, C.lamp);
      shelf(x, 3, 12, 18); shelf(x, 3, 19, 18); shelf(x, 27, 12, 16); shelf(x, 27, 19, 16);
      const cols = [C.red, C.yellow, C.orange, C.red, C.cyan];
      for (let i = 0; i < 8; i++) packet(x, 4 + i * 2.25 | 0, 9, cols[i % cols.length]);
      for (let i = 0; i < 7; i++) can(x, 28 + i * 2.3 | 0, 9);
      for (let i = 0; i < 6; i++) packet(x, 4 + i * 3, 16, cols[(i + 2) % cols.length]);
      for (let i = 0; i < 4; i++) can(x, 28 + i * 3, 16); packet(x, 41, 16, C.yellow);
      sack(x, 5, 24); sack(x, 10, 24); sack(x, 38, 24);
      px(x, 20, 25, 8, 3, C.wood); px(x, 20, 27, 1, 1, C.wood2); px(x, 27, 27, 1, 1, C.wood2); // 탁자
      person(x, 30, 21, C.orange);
    },
    well(x, r) {
      base(x, r, C.cyan);
      px(x, 5, 8, 8, 18, C.metal2); px(x, 6, 7, 6, 1, C.metal); px(x, 6, 9, 6, 15, C.metal); px(x, 8, 12, 2, 6, C.blue); // 탱크 1
      px(x, 15, 10, 7, 16, C.metal2); px(x, 16, 9, 5, 1, C.metal); px(x, 16, 11, 5, 13, C.metal); // 탱크 2
      px(x, 13, 14, 2, 1, C.orange); px(x, 22, 16, 8, 1, C.orange); px(x, 29, 16, 1, 6, C.orange); // 구리관
      px(x, 26, 22, 8, 1, C.metal); px(x, 25, 23, 10, 5, C.metal2); px(x, 26, 24, 8, 3, C.blue); // 수반
      for (let i = 0; i < 3; i++) px(x, 29, 17 + i * 2, 1, 1, C.cyan);                              // 물방울
      shelf(x, 36, 12, 10); for (let i = 0; i < 4; i++) { px(x, 37 + i * 2.4 | 0, 9, 2, 3, C.cyan); px(x, 37 + i * 2.4 | 0, 9, 2, 1, C.white); }
      shelf(x, 36, 19, 10); for (let i = 0; i < 4; i++) { px(x, 37 + i * 2.4 | 0, 16, 2, 3, C.cyan); }
      person(x, 38, 21, C.blue);
    },
    infirmary(x, r) {
      base(x, r, C.green);
      const cot = (gx) => { px(x, gx, 22, 12, 1, C.wood2); px(x, gx, 23, 1, 5, C.wood2); px(x, gx + 11, 23, 1, 5, C.wood2); px(x, gx, 19, 12, 3, C.white); px(x, gx + 1, 18, 3, 1, C.paper); };
      cot(3); cot(18);
      px(x, 34, 8, 11, 16, C.paper); px(x, 35, 9, 9, 14, C.white); px(x, 38, 11, 3, 9, C.red); px(x, 35, 14, 9, 3, C.red); // 약장 + 십자
      for (let i = 0; i < 3; i++) px(x, 36 + i * 3, 20, 2, 2, C.yellow);
      px(x, 5, 16, 3, 3, C.green); // 램프 대신 작은 녹색 등
      person(x, 20, 15, C.white);
    },
    library(x, r) {
      base(x, r, C.yellow);
      const spines = [C.red, C.blue, C.yellow, C.green, C.orange, C.paper, C.wood];
      for (let row = 0; row < 3; row++) { shelf(x, 3, 9 + row * 6, 20); for (let i = 0; i < 9; i++) px(x, 4 + i * 2.2 | 0, 5 + row * 6, 2, 4, spines[(i + row) % spines.length]); }
      for (let row = 0; row < 2; row++) { shelf(x, 30, 9 + row * 6, 15); for (let i = 0; i < 6; i++) px(x, 31 + i * 2.3 | 0, 5 + row * 6, 2, 4, spines[(i + row + 3) % spines.length]); }
      px(x, 26, 24, 12, 1, C.wood); px(x, 27, 25, 1, 3, C.wood2); px(x, 36, 25, 1, 3, C.wood2); // 책상
      px(x, 28, 22, 6, 2, C.cyan); px(x, 35, 21, 1, 3, C.paper); px(x, 35, 20, 1, 1, C.lampHi); // 청사진 + 촛불
      px(x, 42, 18, 1, 10, C.wood); px(x, 45, 18, 1, 10, C.wood); for (let i = 0; i < 4; i++) px(x, 42, 19 + i * 2.5 | 0, 4, 1, C.wood2); // 사다리
      person(x, 22, 21, C.wood);
    },
    rock(x, r) {
      px(x, 0, 0, GW, GH, C.earth);
      for (let i = 0; i < 90; i++) px(x, Math.floor(r() * GW), Math.floor(r() * GH), 1 + Math.floor(r() * 3), 1, r() > .5 ? C.earth2 : C.wallDk);
      for (let i = 0; i < 14; i++) px(x, Math.floor(r() * GW), Math.floor(r() * GH), 2 + Math.floor(r() * 3), 1 + Math.floor(r() * 2), C.rock);
      for (let i = 0; i < 6; i++) { let gx = Math.floor(r() * GW), gy = 0; for (let k = 0; k < 8; k++) { px(x, gx, gy, 1, 2, C.root); gy += 2; gx += r() > .5 ? 1 : -1; } }
      px(x, 38, 22, 1, 7, C.wood); px(x, 36, 22, 5, 1, C.metal); // 곡괭이
      x.fillStyle = 'rgba(0,0,0,.35)'; x.fillRect(0, 0, W, H);
    },
    lot(x, r) {
      px(x, 0, 0, GW, GH, C.sky);
      const g = x.createLinearGradient(0, 0, 0, H); g.addColorStop(0, 'rgba(120,115,105,.9)'); g.addColorStop(1, 'rgba(60,58,54,1)'); x.fillStyle = g; x.fillRect(0, 0, W, H);
      for (let i = 0; i < 6; i++) { const gx = Math.floor(r() * GW), h = 6 + Math.floor(r() * 10); px(x, gx, GH - 6 - h, 3 + Math.floor(r() * 5), h, C.wallDk); } // 폐건물 실루엣
      px(x, 0, GH - 6, GW, 6, C.rubble); px(x, 0, GH - 6, GW, 1, C.wall2);
      for (let i = 0; i < 24; i++) px(x, Math.floor(r() * GW), GH - 6 + Math.floor(r() * 5), 1 + Math.floor(r() * 3), 1, r() > .5 ? C.wall : C.wallDk);
      for (let i = 0; i < 10; i++) px(x, Math.floor(r() * GW), GH - 8 + Math.floor(r() * 2), 1, 2, C.weed);
      px(x, 30, GH - 11, 6, 4, C.metal2); px(x, 30, GH - 7, 1, 1, C.wallDk); px(x, 35, GH - 7, 1, 1, C.wallDk); // 쇼핑카트
    },
  };

  function draw(cv, id, seed) {
    cv.width = W; cv.height = H; const x = cv.getContext('2d'); x.imageSmoothingEnabled = false;
    (ROOMS[id] || ROOMS.rock)(x, rng(id + (seed || '')));
    return cv;
  }
  window.ROOMS = { draw, ids: Object.keys(ROOMS) };
})();
