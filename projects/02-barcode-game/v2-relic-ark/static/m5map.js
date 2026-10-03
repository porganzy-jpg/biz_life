/* 잔해 방주 — 맵 어댑터 M5 「절벽 끝에 기댄 가라앉은 탑」 (S12-B)
 *
 * **맵마다 다른 것은 이 파일 하나뿐이다.** base.js 는 여기서 칸·승강로·홀·심연·깊이 자를 받는다.
 * 정본은 배경 담당의 static/art/maps/m5/layout.json(생성기 tools/m5_layout.py). 파일이 없거나 깨졌으면
 * 같은 숫자로 만든 잠정 배치(provisional)로 돈다 — 화면은 멈추지 않는다(02_DEV D4).
 *
 * 서버 칸 ↔ 맵 칸 (클라이언트 대응표, 서버는 바꾸지 않았다)
 *   서버: SLOTS 10 · 한 층 2칸(floor_slots) · 층 = slot / 2 · 깊이 0 m 의 층 = dome_floor(1). 층 0 은 돔 상부(홀).
 *   맵:   탑 3열 × 5층(storey 0~4, 60 m 간격) + 바위 칸 셋(r0~r2).
 *   → 층은 그대로 맞춘다(storey = 서버 층 − dome_floor). 깊이 띠가 거짓말하지 않게(D2).
 *   → 한 층 두 칸은 SERVER_COLS 순서대로 열에 앉는다: 첫 칸 = 가운데(1열, 돔 바로 아래 = 시작 방), 둘째 = 왼쪽(0열).
 *   → 서버 칸이 없는 맵 칸(오른쪽 2열·storey 4·바위 칸)은 **물이 찬 칸 / 아직 파지 못한 바위**로 그린다(+ 없음).
 *     서버가 한 층 3칸으로 늘면 SERVER_COLS 에 2를 더하는 한 줄로 끝난다.
 */
(() => {
  'use strict';
  const URL = '/static/art/maps/m5/layout.json';
  const SERVER_COLS = [1, 0];             // 서버 slot % floor_slots → 탑 열

  // ── 잠정 배치: layout.json 이 없을 때. 숫자는 2026-10-03 배경 계약과 같다 ───────────
  function provisional() {
    const cols = [[1264, 1828], [2010, 2574], [2756, 3320]], pitch = 363, top0 = 1206, W = 564, H = 317;
    const storeys = [0, 1, 2, 3, 4].map(s => ({ storey: s, top_y: top0 + s * pitch, floor_y: top0 + s * pitch + 282,
                                                bottom_y: top0 + s * pitch + H, depth_m: s * 60 }));
    const cells = [];
    storeys.forEach(st => cols.forEach(([x0], c) => cells.push({ id: st.storey * 3 + c, kind: 'tower', storey: st.storey, col: c,
      x: x0, y: st.top_y, w: W, h: H, floor_y: st.floor_y, depth_m: st.depth_m, stand_x: [x0 + 84, x0 + 480] })));
    const rock = [0, 1, 2].map(s => ({ id: 'r' + s, kind: 'rock', storey: s, x: 380, y: storeys[s].top_y, w: W, h: H,
      floor_y: storeys[s].floor_y, depth_m: s * 60, stand_x: [464, 860],
      tunnel: { x: 944, y: storeys[s].top_y + 86, w: 320, h: 206, floor_y: storeys[s].floor_y, connects_to: s * 3 } }));
    const stops = [{ floor: 'hall', door_y: 1160 }].concat(storeys.map(s => ({ floor: s.storey, door_y: s.floor_y })));
    return {
      _provisional: true,
      scale: { px_per_m: 82.5 }, world: { w: 5600, h: 3400 },
      plates: { src_rect: [54, 33, 564, 317], floor_in_cell: 282, stand_in_cell: [84, 480], lamp_in_cell: [282, 77] },
      tower: { x0: 1064, x1: 3520, section_x0: 1264, section_x1: 3320, facade_w: 200, columns: cols.map(([a, b], c) => ({ col: c, x0: a, x1: b })),
               storeys, slab_h: 46, pitch_y: pitch, roof_y: 1160 },
      cells, rock_cells: rock,
      shafts: [{ id: 'A', x_center: 1919, x: 1844, w: 150, top_y: 800, bottom_y: 2975, stops },
               { id: 'B', x_center: 2665, x: 2590, w: 150, top_y: 800, bottom_y: 2975, stops }],
      shaft_car: { w: 138, h: 190, sprite: 'elevator_car.png', cap_hint: 3 },
      dome: { x: 1264, y: 760, w: 2056, h: 400, floor_y: 1160 },
      dome_glass: { cx: 2292, base_y: 1160, rx: 1080, ry: 560 },
      abyss: { x: 3560, y: 380, w: 2040, h: 3020 },
      lure_lamp: { x: 4820, y: 1520, girder: [[3480, 1120], [4280, 860], [4820, 900]] },
      cliff: { top_y: 560, bottom_y: 2440, x1_at_tower: 1064 },
      depth: { px_per_depth_m: 6.05, y_of_0m: 1206, zones_m: [0, 180, 210], trench_y: 2295, dark_full_y: 3060 },
      layers: { files: [] },
    };
  }

  // ── 정규화: base.js 가 읽는 모양은 이것 하나 ─────────────────────────
  function normalize(j) {
    const L = j;
    const ppm = (L.scale && L.scale.px_per_m) || 82.5;
    const dep = L.depth || {};
    const y0m = dep.y_of_0m != null ? dep.y_of_0m : L.tower.storeys[0].top_y;
    const pxd = dep.px_per_depth_m || (L.tower.pitch_y / 60);
    const tower = (L.cells || []).filter(c => c.kind === 'tower');
    const rock = L.rock_cells || [];
    const byStoreyCol = {};
    tower.forEach(c => { byStoreyCol[c.storey + ':' + c.col] = c; });
    const shafts = (L.shafts || []).map(s => {
      const doors = {};
      (s.stops || []).forEach(st => { doors[st.floor === 'hall' ? -1 : st.floor] = st.door_y; });
      return { id: s.id, x: s.x, w: s.w, cx: s.x_center != null ? s.x_center : s.x + s.w / 2,
               top: s.top_y, bottom: s.bottom_y, doors };
    });
    const LY = L.layers || {};
    const layerFiles = (LY.files || []).filter(f => f && f.file);
    // 칸 그림: 배경 S12-A 의 layers.car(150×208, anchor 아래 가운데)가 있으면 그것이 이긴다
    const car = Object.assign({ w: 138, h: 190, anchor: null, cap_hint: 3 }, L.shaft_car || {},
                              LY.car ? { w: LY.car.w, h: LY.car.h, anchor: LY.car.anchor, sprite: LY.car.file } : {});
    // 정원은 2(PM 결정 2026-10-03): 칸 폭 150 px 에 셋이 타면 겹친다. layout 의 cap_hint 3 보다 이것이 이긴다
    car.cap = 2;
    const overlays = {}; (LY.overlays || []).forEach(o => { if (o && o.id && o.file) overlays[o.id] = o; });
    return {
      raw: L, provisional: !!L._provisional, ppm,
      world: { x0: 0, y0: 0, x1: L.world.w, y1: L.world.h },
      plate: L.plates || {},
      tower: L.tower, storeys: L.tower.storeys, cells: tower, rock,
      shafts, car, overlays, creatures: LY.creatures || null,
      entrance: podSpots(L.entrance), hatch: LY.hatch || null, bubbles: LY.bubbles || null,   // S12-B4 입구 포드
      dome: L.dome, glass: L.dome_glass, abyss: L.abyss, lure: L.lure_lamp, cliff: L.cliff,
      depth: { y0: y0m, pxPerM: pxd, trenchY: dep.trench_y != null ? dep.trench_y : y0m + 180 * pxd,
               darkY: dep.dark_full_y || (y0m + 300 * pxd) },
      layers: layerFiles,
      ambient: (L.ambient || L.life || []),
      cellAt(storey, col) { return byStoreyCol[storey + ':' + col] || null; },
      depthY(m) { return y0m + m * pxd; },
      floorY(storey) {                               // 그 층 사람들의 발선
        if (storey < 0) return L.dome.floor_y;
        const s = L.tower.storeys[Math.max(0, Math.min(L.tower.storeys.length - 1, storey))];
        return s.floor_y;
      },
    };
  }

  // S12-B5 포드 자리: 도트는 정수 배율이라 기본 줌(0.505)에서 사람이 세계보다 약 1.3배 크게 그려진다.
  // 원래 여섯 자리(간격 88~92 px)에서는 다섯 명이 한 덩어리로 겹쳤다 → 둘째 의자(e2)를 빼고 다섯 자리를
  // 첫 자리~끝 자리 사이에 고르게 편다(간격 약 129 px). 자세 힌트(벽·의자·창·장비 걸이·해치 옆)는 그대로다.
  function podSpots(E) {
    if (!E || !Array.isArray(E.spots) || E.spots.length < 6) return E || null;
    const keep = E.spots.filter(sp => sp.id !== 'e2');
    const x0 = keep[0].x, x1 = keep[keep.length - 1].x, step = (x1 - x0) / (keep.length - 1);
    return Object.assign({}, E, { spots_raw: E.spots, spots: keep.map((sp, i) => Object.assign({}, sp, { x: Math.round(x0 + step * i) })) });
  }

  // 서버 slot → 맵 칸 (dome_floor·floor_slots 는 서버가 내려준 값)
  function slotCell(M, slot, floorSlots, domeFloor) {
    const storey = Math.floor(slot / floorSlots) - domeFloor;
    const col = SERVER_COLS[slot % floorSlots];
    if (storey < 0 || col == null) return null;
    return M.cellAt(storey, col);
  }
  function cellSlot(M, cell, floorSlots, domeFloor, slots) {
    if (!cell || cell.kind !== 'tower') return null;
    const k = SERVER_COLS.indexOf(cell.col);
    if (k < 0 || k >= floorSlots) return null;
    const s = (cell.storey + domeFloor) * floorSlots + k;
    return s < slots ? s : null;
  }

  let M = normalize(provisional());
  const ready = fetch(URL, { cache: 'no-store' })
    .then(r => (r.ok ? r.json() : null))
    .then(j => { if (j && j.tower && j.cells && j.world) M = normalize(j); return M; })
    .catch(() => M);

  window.ArkMap = {
    id: 'm5', ready, SERVER_COLS,
    get: () => M,
    slotCell: (slot, fs, df) => slotCell(M, slot, fs, df),
    cellSlot: (cell, fs, df, n) => cellSlot(M, cell, fs, df, n),
    dir: '/static/art/maps/m5/',
  };
})();
