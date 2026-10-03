/* 잔해 방주 — 주민 이동 체계(엘리베이터) + 방 안의 삶.  스프린트 11-C
 *
 * 근거: DECISIONS 2026-10-03 「주민 이동은 엘리베이터를 타고 각 방으로 가는 애니메이션으로,
 *       방에서는 일하는 애니메이션」 · 「지금 맵은 폐기하고 새로 고른다」
 *
 * 이 파일은 **화면 좌표를 모른다.** 맵이 바뀌어도 이 파일은 그대로다.
 *   층(floor, 정수)  — 위에서 아래로 0,1,2… (음수도 된다: 지금 맵의 홀은 -1)
 *   가로 위치(x, m) — 그 층 안의 좌우 위치. 단위는 미터
 *   시간(t, 초)
 * 화면에 그리는 일은 **배치 어댑터**(base.js 의 MOVE_ADAPTER)가 한다. 어댑터는 셋만 안다:
 *   graph()            엘리베이터가 어느 가로 위치에, 몇 층부터 몇 층까지, 정원 몇
 *   nodeOf(where,i,n)  방·홀·바깥이 {floor, x} 의 어디인가
 *   toWorld(floor, x)  {floor, x} → 화면 세계 좌표(px). floor 는 소수(엘리베이터 안)도 받는다
 *
 * 이동 = ① 지금 자리에서 가까운 엘리베이터까지 걷기 → ② 기다리기 → ③ 타고 목표 층까지
 *        → ④ 내려서 목표 자리까지 걷기.  자세: walk → elevator_wait → elevator_ride → walk
 * 여러 명이 같은 엘리베이터를 부르면 **같은 층·같은 방향끼리 정원만큼 같이 타고**, 넘치면 다음 차를 기다린다
 * (폴아웃 셸터 방식). 엘리베이터 칸은 한 대씩이고 그 위치(층)도 시간의 함수로 돌려준다.
 */
(function (root) {
  'use strict';

  // ── 기본값 ────────────────────────────────────────────────
  const DEF = {
    walkSpeed: 1.3,        // m/s — 작업복 입은 어른의 느린 걸음
    secPerFloor: 0.9,      // 엘리베이터 한 층 이동(초)
    door: 0.5,             // 문 열고 타기/내리기(초)
    cap: 3,                // 정원. 지금 척추 폭 70px ≈ 1.9 m, 한 사람 0.6 m
    laneGap: 0.45,         // 칸 안에서 사람 간격(m)
    queueGap: 0.5,         // 기다리는 줄 간격(m)
    doorGap: 0.7,          // 엘리베이터 중심에서 줄 첫 자리까지(m)
    transferPenalty: 2.0,  // 길 고를 때 갈아타기 한 번의 예상 대기(초)
    hold: 2.0,             // 문 잡아 주기: 같은 쪽으로 가는 사람이 이만큼 안에 오면 기다렸다 같이 간다(초)
  };
  const EPS = 1e-6;

  // ── 결정적 해시(같은 사람 = 같은 움직임, D6) ─────────────────
  function hash(s) {
    let h = 2166136261 >>> 0;
    s = String(s);
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    h ^= h >>> 15; h = Math.imul(h, 2246822507) >>> 0; h ^= h >>> 13;
    return h >>> 0;
  }
  const rnd = (s) => hash(s) / 4294967296;        // [0,1)

  // ══════════════════════════════════════════════════════════
  //  ① 길 그래프 — 맵 무관
  // ══════════════════════════════════════════════════════════
  /** graph 스펙 정규화.
   *  spec = { shafts:[{id, x, floors:[lo,hi], cap?, secPerFloor?, door?, home?}],
   *           walkSpeed?, walls?:[{floor, x}] }   walls: 그 층의 그 가로 위치는 걸어서 못 지나간다(격벽)
   */
  function makeGraph(spec) {
    const g = {
      walkSpeed: spec.walkSpeed || DEF.walkSpeed,
      walls: (spec.walls || []).slice(),
      shafts: (spec.shafts || []).map(s => ({
        id: String(s.id), x: +s.x,
        lo: Math.min(s.floors[0], s.floors[1]), hi: Math.max(s.floors[0], s.floors[1]),
        cap: Math.max(1, s.cap || DEF.cap),
        secPerFloor: s.secPerFloor || DEF.secPerFloor,
        door: s.door == null ? DEF.door : s.door,
        doorGap: s.doorGap == null ? DEF.doorGap : s.doorGap,      // 통로 폭이 맵마다 달라 줄 자리도 어댑터가 정한다
        home: s.home == null ? Math.min(s.floors[0], s.floors[1]) : s.home,
      })),
    };
    g.byId = {}; g.shafts.forEach(s => { g.byId[s.id] = s; });
    return g;
  }

  function walkable(g, floor, x0, x1) {
    const a = Math.min(x0, x1), b = Math.max(x0, x1);
    return !g.walls.some(w => w.floor === floor && w.x > a + EPS && w.x < b - EPS);
  }
  const serves = (s, f) => f >= s.lo && f <= s.hi;

  /** 길 찾기: 걷기와 엘리베이터 타기의 순서. 시간은 대기 없이 잰 예상치.
   *  반환 legs: [{kind:'walk', floor, x0, x1}, {kind:'ride', shaft, f0, f1}, ...]
   *  못 가는 곳이면 [{kind:'jump', ...}] (D9 직진 폴백 — 막힘은 버그, 멈춤은 안 된다)
   */
  function route(g, from, to) {
    if (from.floor === to.floor && walkable(g, from.floor, from.x, to.x)) {
      return Math.abs(from.x - to.x) < EPS ? [] : [{ kind: 'walk', floor: from.floor, x0: from.x, x1: to.x }];
    }
    // 노드: 0 = 출발, 1 = 도착, 이후 (엘리베이터, 층) 정류장
    const nodes = [{ floor: from.floor, x: from.x }, { floor: to.floor, x: to.x }];
    g.shafts.forEach(s => { for (let f = s.lo; f <= s.hi; f++) nodes.push({ floor: f, x: s.x, shaft: s }); });
    const n = nodes.length, dist = new Array(n).fill(Infinity), prev = new Array(n).fill(-1),
          how = new Array(n).fill(null), done = new Array(n).fill(false);
    dist[0] = 0;
    for (;;) {
      let u = -1;
      for (let i = 0; i < n; i++) if (!done[i] && dist[i] < Infinity && (u < 0 || dist[i] < dist[u])) u = i;
      if (u < 0 || u === 1) break;
      done[u] = true;
      const a = nodes[u];
      for (let v = 0; v < n; v++) {
        if (done[v] || v === u || v === 0) continue;
        const b = nodes[v];
        let c = Infinity, kind = null;
        if (a.floor === b.floor && walkable(g, a.floor, a.x, b.x)) { c = Math.abs(a.x - b.x) / g.walkSpeed; kind = 'walk'; }
        if (a.shaft && b.shaft && a.shaft === b.shaft && a.floor !== b.floor) {
          const s = a.shaft, cr = 2 * s.door + Math.abs(a.floor - b.floor) * s.secPerFloor + DEF.transferPenalty;
          if (cr < c) { c = cr; kind = 'ride'; }
        }
        if (kind && dist[u] + c < dist[v] - EPS) { dist[v] = dist[u] + c; prev[v] = u; how[v] = kind; }
      }
    }
    if (dist[1] === Infinity) return [{ kind: 'jump', f0: from.floor, f1: to.floor, x0: from.x, x1: to.x }];
    const path = [];
    for (let v = 1; v > 0; v = prev[v]) path.unshift({ v, kind: how[v] });
    const legs = [];
    let cur = nodes[0];
    for (const p of path) {
      const b = nodes[p.v];
      if (p.kind === 'walk') {
        const last = legs[legs.length - 1];
        if (last && last.kind === 'walk' && last.floor === b.floor) last.x1 = b.x;
        else if (Math.abs(cur.x - b.x) > EPS) legs.push({ kind: 'walk', floor: b.floor, x0: cur.x, x1: b.x });
      } else {
        legs.push({ kind: 'ride', shaft: b.shaft.id, f0: cur.floor, f1: b.floor });
      }
      cur = b;
    }
    return legs;
  }

  // ══════════════════════════════════════════════════════════
  //  ② 시간표 — 여러 명이 같은 엘리베이터를 쓴다
  // ══════════════════════════════════════════════════════════
  function newCar(s) { return { floor: s.home, free: -Infinity, keys: [] }; }

  /** moves: [{id, from:{floor,x}, to:{floor,x}, t}]   cars0: 이전 상태(이어서 운행) — 없으면 새 차
   *  반환 { plans: {id: {segs:[...], end, to}}, cars: {shaftId: {floor, free, keys:[[t,floor],...]}}, log:[] }
   *  seg = {pose, t0, t1, floor0, floor1, x0, x1, shaft?, keys?}   floor0≠floor1 은 엘리베이터 안뿐
   */
  function simulate(g, moves, cars0) {
    const cars = {};
    g.shafts.forEach(s => {
      const c = cars0 && cars0[s.id];
      cars[s.id] = c ? { floor: c.floor, free: c.free, keys: [] } : newCar(s);
    });
    const log = [];
    const agents = moves.map(m => ({
      id: String(m.id), legs: route(g, m.from, m.to), i: 0, t: m.t || 0,
      floor: m.from.floor, x: m.from.x, segs: [], to: m.to, req: null,
    }));
    const pending = [];
    function advance(a) {
      const tCall = a.t;                               // 걷기 시작할 때 엘리베이터를 부른다(차가 미리 온다)
      while (a.i < a.legs.length) {
        const L = a.legs[a.i];
        if (L.kind === 'walk') {
          const d = Math.abs(L.x1 - L.x0) / g.walkSpeed;
          a.segs.push({ pose: 'walk', t0: a.t, t1: a.t + d, floor0: L.floor, floor1: L.floor, x0: L.x0, x1: L.x1 });
          a.t += d; a.x = L.x1; a.floor = L.floor; a.i++;
        } else if (L.kind === 'jump') {
          const d = Math.max(1, Math.abs(L.x1 - L.x0) / g.walkSpeed);
          a.segs.push({ pose: 'walk', t0: a.t, t1: a.t + d, floor0: L.f0, floor1: L.f1, x0: L.x0, x1: L.x1 });
          a.t += d; a.x = L.x1; a.floor = L.f1; a.i++;
          log.push(a.id + ' 길 없음 → 직진 폴백');
        } else {
          const s = g.byId[L.shaft];
          // 어느 쪽에서 왔나 — 그쪽 문 앞에 줄을 선다. 엘리베이터 한가운데가 아니라 문 앞까지만 걷는다
          const last = a.segs[a.segs.length - 1];
          const intoShaft = last && last.pose === 'walk' && last.floor0 === last.floor1 && Math.abs(last.x1 - s.x) < EPS;
          const cameFrom = intoShaft ? last.x0 : a.x;
          const side = cameFrom < s.x - EPS ? -1 : 1;
          const door = s.x + side * s.doorGap;
          if (intoShaft) {
            last.x1 = door; last.t1 = last.t0 + Math.abs(door - last.x0) / g.walkSpeed; a.t = last.t1;
          } else if (Math.abs(a.x - door) > EPS) {
            const d = Math.abs(door - a.x) / g.walkSpeed;
            a.segs.push({ pose: 'walk', t0: a.t, t1: a.t + d, floor0: a.floor, floor1: a.floor, x0: a.x, x1: door });
            a.t += d;
          }
          a.x = door;
          a.req = { shaft: s.id, f0: L.f0, f1: L.f1, tReady: a.t, tCall, side, door };
          pending.push(a);
          return;
        }
      }
    }
    agents.forEach(advance);

    while (pending.length) {
      // 다음에 태울 사람: **가장 빨리 태울 수 있는 사람**(차가 가까운 쪽 먼저). 동률이면 먼저 줄 선 사람, 그다음 id
      const est = (a) => {
        const c = cars[a.req.shaft], sh = g.byId[a.req.shaft];
        return Math.max(Math.max(c.free, a.req.tCall) + Math.abs(c.floor - a.req.f0) * sh.secPerFloor, a.req.tReady);
      };
      pending.forEach(a => { a.est = est(a); });
      pending.sort((p, q) => (p.est - q.est) || (p.req.tReady - q.req.tReady) || (p.id < q.id ? -1 : p.id > q.id ? 1 : 0));
      const head = pending[0], s = g.byId[head.req.shaft], car = cars[s.id];
      const start = Math.max(car.free, head.req.tCall);
      const reach = start + Math.abs(car.floor - head.req.f0) * s.secPerFloor;
      let pickup = Math.max(reach, head.req.tReady);
      if (car.keys.length === 0 || car.keys[car.keys.length - 1][1] !== car.floor) car.keys.push([start, car.floor]);
      else if (start > car.keys[car.keys.length - 1][0]) car.keys.push([start, car.floor]);
      car.keys.push([reach, head.req.f0]);
      if (pickup > reach) car.keys.push([pickup, head.req.f0]);
      const f0 = head.req.f0;
      const dir = Math.sign(head.req.f1 - head.req.f0);
      // 같은 층·같은 방향, 차가 오기 전에 줄에 선 사람 — 정원만큼
      // (문 잡아 주기: 이미 오고 있는 사람이 hold 초 안에 닿으면 기다렸다 같이 간다)
      const group = pending.filter(a => a.req.shaft === s.id && a.req.f0 === head.req.f0 &&
                                        Math.sign(a.req.f1 - a.req.f0) === dir && a.req.tReady <= pickup + DEF.hold + EPS)
                           .sort((p, q) => (p.req.tReady - q.req.tReady) || (p.id < q.id ? -1 : 1))
                           .slice(0, s.cap);
      if (group.indexOf(head) < 0) group[group.length - 1] = head;       // 맨 앞사람은 반드시 탄다
      group.forEach(a => { if (a.req.tReady > pickup) pickup = a.req.tReady; });
      if (pickup > car.keys[car.keys.length - 1][0] + EPS) car.keys.push([pickup, head.req.f0]);
      // 줄 위치: 같은 층에서 이 차를 기다리는 사람 순서대로(못 탄 사람도 줄에 서 있다)
      const line = pending.filter(a => a.req.shaft === s.id && a.req.f0 === head.req.f0);
      const lineKo = line.map(a => a.id + '@' + a.req.tReady.toFixed(1)).join(' ');   // 기록용(아래에서 req 를 비운다)
      const qIndex = {}; const perSide = { '-1': 0, '1': 0 };
      line.forEach(a => { qIndex[a.id] = perSide[a.req.side]++; });
      const tb = pickup + s.door;
      group.forEach((a, lane) => {
        const qx = s.x + a.req.side * (s.doorGap + (qIndex[a.id] || 0) * DEF.queueGap);
        if (pickup > a.req.tReady + EPS) {
          a.segs.push({ pose: 'elevator_wait', t0: a.req.tReady, t1: pickup, floor0: a.req.f0, floor1: a.req.f0,
                        x0: a.req.door, x1: qx, settle: 0.6, shaft: s.id, queue: qIndex[a.id] || 0 });
        }
        a.lane = lane; a.qx = qx;
      });
      const laneX = (lane, k) => s.x + (lane - (k - 1) / 2) * DEF.laneGap;
      // 내릴 층을 방향 순서대로 들른다
      const dest = new Map(group.map(a => [a, a.req.f1]));          // 내린 사람은 req 를 비우므로 미리 적어 둔다
      const stops = Array.from(new Set(dest.values())).sort((p, q) => dir * (p - q));
      let t = tb, f = head.req.f0;
      car.keys.push([tb, f]);
      const rideKeys = [[pickup, f], [tb, f]];
      for (const stop of stops) {
        const t1 = t + Math.abs(stop - f) * s.secPerFloor;
        car.keys.push([t1, stop]); rideKeys.push([t1, stop]);
        const out = t1 + s.door;
        car.keys.push([out, stop]); rideKeys.push([out, stop]);
        group.filter(a => dest.get(a) === stop).forEach(a => {
          const keys = rideKeys.slice();
          a.segs.push({ pose: 'elevator_ride', t0: pickup, t1: out, floor0: a.req.f0, floor1: stop,
                        x0: a.qx, x1: laneX(a.lane, group.length), shaft: s.id, keys, lane: a.lane,
                        board: tb });
          a.t = out; a.floor = stop; a.x = laneX(a.lane, group.length);
          a.i++; a.req = null;
        });
        t = out; f = stop;
      }
      car.free = t; car.floor = f;
      log.push('[' + s.id + '] ' + f0 + '층 ' + pickup.toFixed(1) + 's 출발 · ' +
               group.map(a => a.id).join(',') + ' → ' + stops.join('·') + '층 · 도착 ' + t.toFixed(1) + 's' +
               (line.length > group.length ? ' · 못 탄 사람 ' + (line.length - group.length) : '') +
               ' (줄: ' + lineKo + ')');
      group.forEach(a => { pending.splice(pending.indexOf(a), 1); });
      // 내린 사람: 엘리베이터 문 앞에서 첫 걸음은 칸 안 자리에서 시작한다
      group.forEach(a => {
        const L = a.legs[a.i];
        if (L && L.kind === 'walk') L.x0 = a.x;
        advance(a);
      });
    }
    const plans = {};
    agents.forEach(a => {
      const end = a.segs.length ? a.segs[a.segs.length - 1].t1 : a.t;
      plans[a.id] = { id: a.id, segs: a.segs, start: a.segs.length ? a.segs[0].t0 : a.t, end, to: a.to, legs: a.legs };
    });
    return { plans, cars, log };
  }

  // ── 시간 → 자리·자세 ──────────────────────────────────────
  function lerpKeys(keys, t) {
    if (!keys.length) return null;
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const [ta, fa] = keys[i - 1], [tb, fb] = keys[i];
      if (t <= tb) return tb - ta < EPS ? fb : fa + (fb - fa) * (t - ta) / (tb - ta);
    }
    return keys[keys.length - 1][1];
  }

  /** plan 의 t 시점: {floor(소수 가능), x, pose, done, shaft?} */
  function sample(plan, t) {
    const segs = plan.segs;
    if (!segs.length || t >= plan.end) {
      return { floor: plan.to.floor, x: plan.to.x, pose: 'idle', done: true };
    }
    if (t < segs[0].t0) { const s0 = segs[0]; return { floor: s0.floor0, x: s0.x0, pose: s0.pose, done: false }; }
    for (const s of segs) {
      if (t > s.t1) continue;
      const k = s.t1 - s.t0 < EPS ? 1 : (t - s.t0) / (s.t1 - s.t0);
      if (s.pose === 'elevator_ride') {
        // 타는 동안(문 열린 시간) 줄 자리에서 칸 안 자리로 옮긴다
        const kb = s.board > s.t0 ? Math.min(1, (t - s.t0) / (s.board - s.t0)) : 1;
        return { floor: lerpKeys(s.keys, t), x: s.x0 + (s.x1 - s.x0) * kb, pose: 'elevator_ride',
                 done: false, shaft: s.shaft, lane: s.lane };
      }
      // 줄 서기: 문 앞에 닿은 뒤 첫 0.6 초 동안 제 줄 자리로 물러선다
      const kx = s.settle ? Math.min(1, (t - s.t0) / s.settle) : k;
      return { floor: s.floor0 + (s.floor1 - s.floor0) * k, x: s.x0 + (s.x1 - s.x0) * kx, pose: s.pose,
               done: false, shaft: s.shaft, facing: Math.sign(s.x1 - s.x0) || 0 };
    }
    return { floor: plan.to.floor, x: plan.to.x, pose: 'idle', done: true };
  }

  function carAt(car, t) {
    if (!car) return null;
    const f = lerpKeys(car.keys, t);
    return f == null ? car.floor : f;
  }

  // ══════════════════════════════════════════════════════════
  //  ③ 방 안의 삶 — 일하다가 10~20초에 한 번 쉬거나 몇 걸음 옮긴다
  // ══════════════════════════════════════════════════════════
  const BREAK = 2.4;                                   // 쉬는/옮기는 시간(초)
  function lifePeriod(id) { return 10 + rnd(id + '|p') * 10; }
  function spot(id, k) {                               // 그 주기에 서 있는 자리(-1..1). 가끔은 그대로
    let j = k, guard = 0;
    while (j > 0 && rnd(id + '|stay|' + j) < 0.45 && guard++ < 64) j--;
    return rnd(id + '|spot|' + j) * 2 - 1;
  }
  /** 방 안에서의 t 시점: {pose:'work'|'rest'|'walk', dx:-1..1, facing} */
  function roomLife(id, t) {
    const P = lifePeriod(id), off = rnd(id + '|o') * P, u = t + off;
    const k = Math.floor(u / P), ph = u - k * P;
    const a = spot(id, k);
    if (ph < P - BREAK) return { pose: 'work', dx: a, facing: 0 };
    const b = spot(id, k + 1), q = (ph - (P - BREAK)) / BREAK;
    if (Math.abs(b - a) < 0.05) return { pose: 'rest', dx: a, facing: 0 };
    return { pose: 'walk', dx: a + (b - a) * q, facing: Math.sign(b - a) };
  }

  // ══════════════════════════════════════════════════════════
  //  ④ 교통 — base.js 가 쓰는 상태 있는 얇은 껍질
  // ══════════════════════════════════════════════════════════
  function createTraffic(spec) {
    let g = makeGraph(spec);
    let cars = {};
    const plans = {};
    const carKeys = {};                                // 그리기용 누적 키(오래된 것은 버린다)
    return {
      setGraph(sp) { g = makeGraph(sp); },
      graph: () => g,
      /** moves: [{id, from, to}] — now(초)에 동시에 출발. 이미 움직이는 사람은 지금 자리에서 다시 출발 */
      go(moves, now) {
        const ms = moves.map(m => {
          const cur = plans[m.id] && !plans[m.id].doneAt(now) ? sample(plans[m.id], now) : null;
          const from = cur ? { floor: Math.round(cur.floor), x: cur.x } : m.from;
          return { id: m.id, from, to: m.to, t: now };
        });
        const r = simulate(g, ms, cars);
        Object.keys(r.cars).forEach(id => {
          const keep = (carKeys[id] || []).filter(k => k[0] < (r.cars[id].keys[0] ? r.cars[id].keys[0][0] : Infinity) && k[0] > now - 30);
          carKeys[id] = keep.concat(r.cars[id].keys);
          cars[id] = { floor: r.cars[id].floor, free: r.cars[id].free };
        });
        Object.keys(r.plans).forEach(id => {
          const p = r.plans[id]; p.doneAt = (t) => t >= p.end; plans[id] = p;
        });
        return r;
      },
      at(id, t) { const p = plans[id]; return p && !p.doneAt(t) ? sample(p, t) : null; },
      arrivedAt(id) { return plans[id] ? plans[id].end : -Infinity; },
      moving(t) { return Object.keys(plans).filter(id => !plans[id].doneAt(t)); },
      car(id, t) { const k = carKeys[id]; return k && k.length ? lerpKeys(k, t) : (g.byId[id] ? g.byId[id].home : null); },
      cars: () => g.shafts.map(s => s.id),
      forget(t) { Object.keys(plans).forEach(id => { if (plans[id].doneAt(t - 5)) delete plans[id]; }); },
    };
  }

  // ══════════════════════════════════════════════════════════
  //  자가 시험 — 화면 없이 부른다(Playwright evaluate 또는 아무 페이지의 콘솔)
  // ══════════════════════════════════════════════════════════
  function fmtPlan(p) {
    return p.segs.map(s => s.pose + '[' + s.t0.toFixed(1) + '→' + s.t1.toFixed(1) + 's ' +
      (s.floor0 === s.floor1 ? s.floor0 + '층' : s.floor0 + '→' + s.floor1 + '층') +
      ' x' + s.x0.toFixed(1) + '→' + s.x1.toFixed(1) + (s.shaft ? ' ' + s.shaft : '') + ']').join(' ');
  }
  function selfTest() {
    const out = [], fails = [];
    const check = (c, msg) => { out.push((c ? 'PASS ' : 'FAIL ') + msg); if (!c) fails.push(msg); };
    // 맵 두 개: 엘리베이터 A(x=0, 0~9층) · B(x=20, 0~9층). 걷기 1.3 m/s, 한 층 0.9 s, 문 0.5 s, 정원 3
    const g = makeGraph({ walkSpeed: 1.3, shafts: [
      { id: 'A', x: 0, floors: [0, 9], cap: 3, secPerFloor: 0.9, door: 0.5, home: 0 },
      { id: 'B', x: 20, floors: [0, 9], cap: 3, secPerFloor: 0.9, door: 0.5, home: 0 } ] });
    const WORKSHOP3 = { floor: 3, x: 4 }, STORAGE7 = { floor: 7, x: 6 };

    out.push('— 시험 1: 3층 공방(x=4) → 7층 창고(x=6), 혼자');
    const r1 = simulate(g, [{ id: 'gaon', from: WORKSHOP3, to: STORAGE7, t: 0 }]);
    const p1 = r1.plans.gaon;
    out.push('  ' + fmtPlan(p1)); r1.log.forEach(l => out.push('  ' + l));
    check(p1.segs.map(s => s.pose).join(',') === 'walk,elevator_wait,elevator_ride,walk', '구간 순서 walk→wait→ride→walk');
    check(p1.segs[2].shaft === 'A', '가까운 엘리베이터 A 를 고른다(x=4 → A 4m, B 16m)');
    // 손 계산: 걷기 x4 → 문 앞 x0.7 = 3.3 m / 1.3 = 2.538 s · 그때 부른 차가 0층→3층 2.7 s
    //          탑승 문 0.5 · 4층 이동 3.6 · 내림 문 0.5 · 걷기 x0 → x6 = 6/1.3 = 4.615 s → 총 13.953 s
    const W1 = 3.3 / 1.3, W2 = 6 / 1.3;
    check(Math.abs(p1.segs[0].t1 - W1) < 1e-6, '걷기 4 m → 문 앞(0.7 m) = 3.3 m = ' + W1.toFixed(2) + ' s');
    // 걷기 시작할 때 부른 차는 0층→3층 2.7 s 에 오고, 사람은 2.54 s 에 문 앞 → 0.16 s 기다린다
    check(Math.abs(p1.segs[1].t1 - p1.segs[1].t0 - (2.7 - W1)) < 1e-6, '기다림 = 2.7 − ' + W1.toFixed(2) + ' = ' + (2.7 - W1).toFixed(2) + ' s(걷기 시작할 때 부른다)');
    check(Math.abs(p1.segs[2].t1 - p1.segs[2].t0 - (0.5 + 3.6 + 0.5)) < 1e-6, '타기 = 문 0.5 + 4층 3.6 + 문 0.5 = 4.6 s');
    check(Math.abs(p1.end - (2.7 + 4.6 + W2)) < 1e-6, '총 ' + p1.end.toFixed(2) + ' s = 2.7 + 4.6 + ' + W2.toFixed(2));
    const mid = sample(p1, p1.segs[2].board + 1.8);
    check(mid.pose === 'elevator_ride' && mid.floor > 4.9 && mid.floor < 5.1, '타고 1.8 s 뒤 = 5층 근처(' + mid.floor.toFixed(2) + ')');
    check(sample(p1, 99).done && sample(p1, 99).floor === 7, '끝나면 7층 창고에 있다');

    out.push('— 시험 2: 엘리베이터 둘 — 출발 x=18 이면 B 를 탄다');
    const r2 = simulate(g, [{ id: 'nuri', from: { floor: 2, x: 18 }, to: { floor: 8, x: 22 }, t: 0 }]);
    out.push('  ' + fmtPlan(r2.plans.nuri));
    check(r2.plans.nuri.segs.find(s => s.pose === 'elevator_ride').shaft === 'B', 'B 를 고른다');

    out.push('— 시험 3: 다섯 명이 동시에 3층에서 7층으로(정원 3) — 셋이 먼저, 둘은 다음 차');
    const five = ['p1', 'p2', 'p3', 'p4', 'p5'].map((id, i) => ({ id, from: { floor: 3, x: 1 + i * 0.5 }, to: STORAGE7, t: 0 }));
    const r3 = simulate(g, five);
    r3.log.forEach(l => out.push('  ' + l));
    const rides = five.map(m => r3.plans[m.id].segs.find(s => s.pose === 'elevator_ride'));
    const firstTrip = rides.filter(s => Math.abs(s.t0 - rides[0].t0) < 1e-6).length;
    check(firstTrip === 3, '첫 차에 정원 3 명');
    check(rides[3].t0 > rides[0].t1 - 1e-6 && rides[4].t0 > rides[0].t1 - 1e-6, '넷째·다섯째는 첫 차가 내려간 뒤 다시 올라온 차를 탄다');
    const w4 = r3.plans.p4.segs.find(s => s.pose === 'elevator_wait');
    check(w4 && w4.t1 - w4.t0 > 4, '넷째의 기다림 ' + (w4 ? (w4.t1 - w4.t0).toFixed(1) : '?') + ' s (차 왕복)');
    check(new Set(rides.slice(0, 3).map(s => s.lane)).size === 3, '같이 탄 셋은 칸 안 자리가 다르다');

    out.push('— 시험 3b: 문 잡아 주기 — 차가 이미 와 있어도 1.3 s 뒤에 닿는 사람을 기다렸다 같이 간다');
    const r3b = simulate(g, [{ id: 'first', from: { floor: 0, x: 1 }, to: STORAGE7, t: 0 },
                             { id: 'late', from: { floor: 0, x: 2.6 }, to: STORAGE7, t: 0 }],
                         { A: { floor: 0, free: 0 }, B: { floor: 0, free: 0 } });
    r3b.log.forEach(l => out.push('  ' + l));
    const ra = r3b.plans.first.segs.find(s => s.pose === 'elevator_ride'), rb = r3b.plans.late.segs.find(s => s.pose === 'elevator_ride');
    check(Math.abs(ra.t0 - rb.t0) < 1e-6, '둘이 같은 차(' + ra.t0.toFixed(2) + ' s)');

    out.push('— 시험 3c: 같이 타서 다른 층에 내린다(4층·6층)');
    const r3c = simulate(g, [{ id: 'm1', from: { floor: 1, x: 1 }, to: { floor: 4, x: 2 }, t: 0 },
                             { id: 'm2', from: { floor: 1, x: 1.3 }, to: { floor: 6, x: 2 }, t: 0 }]);
    r3c.log.forEach(l => out.push('  ' + l));
    const c1 = r3c.plans.m1.segs.find(s => s.pose === 'elevator_ride'), c2 = r3c.plans.m2.segs.find(s => s.pose === 'elevator_ride');
    check(Math.abs(c1.t0 - c2.t0) < 1e-6 && c1.t1 < c2.t1, '같은 차, 4층에서 먼저 내리고 6층까지 간다');
    check(Math.abs(c2.t1 - c1.t1 - (2 * 0.9 + 0.5)) < 1e-6, '4층 문(0.5 s) + 두 층(1.8 s) 뒤에 6층');

    out.push('— 시험 4: 같은 층에서 올라가는 사람과 내려가는 사람은 같이 안 탄다');
    const r4 = simulate(g, [{ id: 'dn', from: { floor: 5, x: 1 }, to: { floor: 8, x: 1 }, t: 0 },
                            { id: 'up', from: { floor: 5, x: -1 }, to: { floor: 1, x: 1 }, t: 0 }]);
    r4.log.forEach(l => out.push('  ' + l));
    const a4 = r4.plans.dn.segs.find(s => s.pose === 'elevator_ride'), b4 = r4.plans.up.segs.find(s => s.pose === 'elevator_ride');
    check(Math.abs(a4.t0 - b4.t0) > 1e-6, '방향이 다르면 따로 탄다');

    out.push('— 시험 4b: 차가 4층에 서 있을 때 — 0층 사람보다 4층 사람을 먼저 태운다(가까운 쪽 먼저)');
    const r4b = simulate(g, [{ id: 'far', from: { floor: 0, x: 1 }, to: { floor: 2, x: 1 }, t: 0 },
                             { id: 'near', from: { floor: 4, x: 3 }, to: { floor: 1, x: 1 }, t: 0 }],
                         { A: { floor: 4, free: 0 }, B: { floor: 0, free: 0 } });
    r4b.log.forEach(l => out.push('  ' + l));
    const fr = r4b.plans.far.segs.find(s => s.pose === 'elevator_ride'), nr = r4b.plans.near.segs.find(s => s.pose === 'elevator_ride');
    check(nr.t0 < fr.t0, '가까운 사람 먼저(4층 ' + nr.t0.toFixed(1) + ' s < 0층 ' + fr.t0.toFixed(1) + ' s)');

    out.push('— 시험 5: 같은 층은 걷기만 · 격벽이 있으면 엘리베이터로 돌아간다');
    const r5 = simulate(g, [{ id: 'flat', from: { floor: 4, x: -3 }, to: { floor: 4, x: 5 }, t: 0 }]);
    check(r5.plans.flat.segs.length === 1 && r5.plans.flat.segs[0].pose === 'walk', '같은 층 = 걷기 한 구간');
    const gw = makeGraph({ shafts: [{ id: 'A', x: 0, floors: [0, 9] }, { id: 'B', x: 20, floors: [3, 6] }],
                           walls: [{ floor: 4, x: 10 }] });
    const lw = route(gw, { floor: 4, x: 5 }, { floor: 4, x: 15 });
    out.push('  ' + lw.map(l => l.kind + (l.kind === 'ride' ? '(' + l.shaft + ' ' + l.f0 + '→' + l.f1 + ')' : '(' + l.floor + '층 ' + l.x0 + '→' + l.x1 + ')')).join(' '));
    check(lw.some(l => l.kind === 'ride'), '격벽(4층 x=10)을 다른 층으로 돌아간다');

    out.push('— 시험 6: 갈아타기 — A 는 0~4층, B 는 4~9층');
    const gt = makeGraph({ shafts: [{ id: 'A', x: 0, floors: [0, 4] }, { id: 'B', x: 12, floors: [4, 9] }] });
    const lt = route(gt, { floor: 1, x: 2 }, { floor: 8, x: 10 });
    out.push('  ' + lt.map(l => l.kind + (l.kind === 'ride' ? '(' + l.shaft + ' ' + l.f0 + '→' + l.f1 + ')' : '(' + l.floor + '층)')).join(' '));
    check(lt.filter(l => l.kind === 'ride').map(l => l.shaft).join('') === 'AB', 'A 로 4층 → 걸어서 B → 8층');
    const rt = simulate(gt, [{ id: 'tr', from: { floor: 1, x: 2 }, to: { floor: 8, x: 10 }, t: 0 }]);
    check(sample(rt.plans.tr, 1e9).floor === 8, '갈아타고 도착');

    out.push('— 시험 7: 결정성 — 같은 입력이면 같은 시간표');
    const again = simulate(g, five);
    check(JSON.stringify(again.plans.p5.segs) === JSON.stringify(r3.plans.p5.segs), '두 번 돌려도 같다');

    out.push('— 시험 8: 방 안의 삶 — 60초 동안 일하는 비율과 쉬는/옮기는 횟수');
    let work = 0, brk = 0, prev = null;
    for (let t = 0; t < 60; t += 0.1) {
      const L = roomLife('cook-1', t);
      if (L.pose === 'work') work++;
      if (prev === 'work' && L.pose !== 'work') brk++;
      prev = L.pose;
      if (Math.abs(L.dx) > 1 + 1e-9) fails.push('dx 범위');
    }
    out.push('  일 ' + (work / 6).toFixed(0) + '% · 쉬거나 옮김 ' + brk + '번 / 60 s');
    check(brk >= 3 && brk <= 6, '10~20 초에 한 번(60 s 에 3~6 번)');
    out.push(fails.length ? '결과: 실패 ' + fails.length : '결과: 전부 통과');
    return { ok: !fails.length, log: out };
  }

  const API = { DEF, makeGraph, route, simulate, sample, carAt, lerpKeys, roomLife, createTraffic, selfTest, hash };
  root.ArkMove = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
