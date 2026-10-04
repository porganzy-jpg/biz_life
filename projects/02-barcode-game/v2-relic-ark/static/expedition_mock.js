// static/expedition_mock.js — 원정 API 로컬 모의(★ 개발 전용, `?mock=1` 에서만 로드). S15-C.
// 모양은 docs/API_EXPEDITION.md §5·§6·§8 을 그대로 따른다. 서버가 붙으면 이 파일은 쓰이지 않는다.
// 수치는 만들지 않는다: 확률 표는 data/balance/expedition.json(기획) 의 값을 옮겨 왔을 뿐이고,
// 화면은 이 모의가 내려 준 값만 그린다(실제 서버와 같은 자리). 사람·이름은 실제 /api/ark 에서 읽는다.
// 상태는 localStorage(`expmock|uid`) — 같은 uid 로 다시 열면 같은 원정이다.

const P = {                                       // expedition.json 에서 옮김(모의 전용)
  finds: { material: 0.36, box: 0.08, relic: 0.07, empty: 0.49 },
  fork: { lit: { material: 0.10, box: -0.03 }, dark: { material: -0.10, box: 0.03 } },
  lengths: { short: { minutes: 30, tank: 2, danger: 0.08 }, half: { minutes: 240, tank: 4, danger: 0.15 }, long: { minutes: 600, tank: 6, danger: 0.25 } },
  kinds: { air: 'breath', beast: 'nerve', seam: 'hand', lost: 'eye' },
  head: 3,
};
const CATS = ['food', 'drink', 'medical', 'electronics', 'stationery', 'book', 'apparel', 'tobacco'];
const MATS = ['food', 'water', 'med', 'parts', 'cloth', 'trade', 'knowledge', 'scrap'];

function fnv(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { let a = fnv(seed); return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const now = () => Math.floor(Date.now() / 1000);

const Q = new URLSearchParams(location.search);
const KEY = (uid) => 'expmock|' + uid;
function load(uid) { try { return JSON.parse(localStorage.getItem(KEY(uid)) || 'null'); } catch { return null; } }
function save(uid, s) { try { localStorage.setItem(KEY(uid), JSON.stringify(s)); } catch { /* 사생활 창 */ } }

async function residents(uid) {
  try { const r = await fetch('/api/ark?uid=' + encodeURIComponent(uid)); if (r.ok) { const j = await r.json(); return j.residents_list || []; } } catch { }
  return [];
}

// ── 출발(모의): 눈이 가장 좋은 사람 한 명, 목적지·길이는 URL 로 바꿔 볼 수 있다(?dest=unknown&len=half&danger=1&two=1)
async function startMock(uid) {
  const people = await residents(uid);
  const byEye = people.slice().sort((a, b) => ((b.stats || {}).eye || 5) - ((a.stats || {}).eye || 5));
  const two = Q.get('two') === '1' && byEye.length > 1;
  const mem = (two ? byEye.slice(0, 2) : byEye.slice(0, 1)).map(p => ({ id: p.id, name: p.name, role: p.role, stats: p.stats || {}, imprints: p.imprints || [] }));
  if (!mem.length) mem.push({ id: 'scout-mock', name: '—', role: 'scout', stats: { hand: 5, eye: 6, breath: 6, nerve: 5 }, imprints: [] });
  const kind = Q.get('dest') || 'unknown';
  const dest = kind === 'clue' || kind === 'spot' ? { kind, id: Q.get('spot') || 'spot_vent_garden' } : { kind };
  const length = Q.get('len') || (kind === 'door' ? 'short' : 'half');
  const id = 'exp-mock-' + (fnv(uid + '|' + kind + '|' + length) % 1000);
  const R = rng(uid + '|' + id);
  const L = P.lengths[length];
  const minB = Math.min(...mem.map(m => m.stats.breath || 5)), eye = Math.max(...mem.map(m => m.stats.eye || 5));
  const actions = Math.max(1, Math.round(L.tank * (1 + 0.1 * (minB - 5))));
  const carry = mem.reduce((s, m) => s + 2 + Math.ceil((m.stats.hand || 5) / 2), 0);
  const acts = Array.from({ length: Math.max(actions, P.head) }, () => [R(), R(), R()]);
  const forceDanger = Q.get('danger');
  const danger = (forceDanger === '1' || (forceDanger !== '0' && R() < L.danger)) ? (() => {
    const ks = Object.keys(P.kinds), kd = Q.get('dkind') || ks[Math.floor(R() * ks.length)], stat = P.kinds[kd];
    const best = Math.max(...mem.map(m => m.stats[stat] || 5));
    const p = Math.max(0.2, Math.min(0.95, 0.55 + 0.07 * (best - 5) + (mem.length > 1 ? 0.05 : 0)));
    return { kind: kd, stat, p_hide: +p.toFixed(2), before_pick: Q.has('dat') ? +Q.get('dat') : 1 + Math.floor(R() * 2), u: R() };
  })() : null;
  const started = now() - 20;
  const s = {
    id, uid, members: mem, dest, length, started, returns_at: started + L.minutes * 60, actions, carry, eye, acts,
    danger, discovers: kind === 'clue' && R() < 0.6 ? dest.id : null, rescue: kind === 'unknown' && R() < 0.5,
    picked: [], fork: null, danger_choice: null, dropped: [], committed: false, seen: false,
  };
  save(uid, s);
  return s;
}

function itemAt(s, i) {
  const [u, u2, u3] = s.acts[i] || [0.99, 0, 0];
  const pr = { ...P.finds };
  if (i >= P.head && s.fork) { pr.material += P.fork[s.fork].material; pr.box += P.fork[s.fork].box; pr.empty = 1 - pr.material - pr.box - pr.relic; }
  const eyeAdd = 0.01 * (s.eye - 5); pr.box += eyeAdd; pr.relic += eyeAdd; pr.empty -= 2 * eyeAdd;
  let acc = 0, kind = 'empty';
  for (const k of ['material', 'box', 'relic', 'empty']) { acc += pr[k]; if (u < acc) { kind = k; break; } }
  if (kind === 'material') return { kind, res: MATS[Math.floor(u3 * 8) % 8], ko: null };
  if (kind === 'box') return { kind, cat: CATS[Math.floor(u3 * 8) % 8] };
  if (kind === 'relic') return { kind, rarity: u2 < 0.7 ? 'common' : 'uncommon' };
  return { kind: 'empty' };
}
const SLOTS = { box: 2, relic: 1, material: 1, empty: 0 };

function waypoints(s) {                        // 문(0,0)에서 나가 돌아오는 고리. 진행도로 보간
  const R = rng(s.uid + '|wp|' + s.dest.kind), out = [{ x: 0, z: 0 }];
  let x = 0, z = 0;
  for (let k = 1; k <= 7; k++) { x += 5 + R() * 4; z += (R() - 0.5) * 7; z = Math.max(-18, Math.min(18, z)); out.push({ x: +x.toFixed(1), z: +z.toFixed(1) }); }
  for (let k = 6; k >= 0; k--) out.push({ x: +(out[k].x * 0.92).toFixed(1), z: +(out[k].z * 0.7 + 3).toFixed(1) });
  out.push({ x: 0, z: 0 });
  return out;
}

function nextOf(s) {
  if (s.committed) return 'done';
  const n = s.picked.length;
  if (s.danger && !s.danger_choice && n === s.danger.before_pick) return 'danger';
  if (s.danger_choice === 'turn_back') return 'done';
  const used = s.picked.reduce((a, p) => a + SLOTS[p.item.kind], 0) - s.dropped.reduce((a, i) => a + SLOTS[s.picked[i].item.kind], 0);
  if (used > s.carry) return 'drop';
  if (n < P.head) return 'pick:' + n;
  if (!s.fork) return 'fork';
  return 'done';
}

function sceneOf(s) {
  const t = now(), span = Math.max(1, s.returns_at - s.started);
  const openUntil = s.started + Math.min(span * 0.1, 1800);
  const R = rng(s.uid + '|pos|' + s.id);
  const picks = Array.from({ length: P.head }, (_, i) => {
    const p = s.picked.find(q => q.i === i);
    const pos = { x: +(4 + i * 5 + R() * 2).toFixed(1), z: +((R() - 0.5) * 8).toFixed(1) };
    return p ? { i, pos, state: 'picked', item: p.item } : { i, pos, state: 'sparkle' };
  });
  const items = s.picked.filter((p, k) => !s.dropped.includes(k)).map(p => ({ i: p.i, ...p.item }));
  return {
    exp_id: s.id, terrain_seed: s.uid + '|' + s.dest.kind, dest: s.dest, started: s.started, returns_at: s.returns_at, now: t,
    progress: Math.min(1, (t - s.started) / span), members: s.members, lantern_radius_m: 8,
    waypoints: waypoints(s),
    head: {
      picks,
      fork: { after: 3, pos: { x: 20, z: 0 }, options: [{ id: 'lit' }, { id: 'dark' }], auto: 'lit', chosen: s.fork },
      danger: s.danger ? { before_pick: s.danger.before_pick, kind: s.danger.kind, stat: s.danger.stat, p_hide: s.danger.p_hide, options: ['hide', 'turn_back'], auto: s.danger.p_hide >= 0.55 ? 'hide' : 'turn_back', chosen: s.danger_choice } : null,
    },
    carry: { slots: s.carry, used: items.reduce((a, it) => a + SLOTS[it.kind], 0), items },
    air_band: Math.max(0, 1 - s.picked.length / Math.max(1, s.actions)),
    open: !s.committed && t < openUntil, committed: s.committed, next: nextOf(s),
    discovers: s.discovers ? { spot_id: s.discovers, pos: { x: 46, z: -8 } } : null,
    auto_rules: {},
  };
}

function returnOf(s) {
  const n = s.danger_choice === 'turn_back' ? s.danger.before_pick : s.actions;
  const items = [];
  for (let i = 0; i < Math.max(n, s.picked.length); i++) {
    const p = s.picked.find(q => q.i === i); items.push(p ? p.item : itemAt(s, i));
  }
  const mats = {}, boxes = [], relics = [];
  items.forEach((it, k) => {
    if (s.dropped.includes(k)) return;
    if (it.kind === 'material') mats[it.res] = (mats[it.res] || 0) + 1;
    if (it.kind === 'box') boxes.push({ id: 'box-m' + k, cat: it.cat });
    if (it.kind === 'relic') relics.push({ rarity: it.rarity, shelf_slot: k });
  });
  const d = s.danger;
  const dOut = d ? (s.danger_choice === 'turn_back' ? { kind: d.kind, ok: null, choice: 'turn_back' } : { kind: d.kind, ok: d.u < d.p_hide, choice: s.danger_choice || 'auto' }) : null;
  return {
    id: s.id, members: s.members.map(m => m.id), member_names: s.members.map(m => m.name), dest: s.dest, length: s.length, returned_at: s.returns_at,
    haul: { materials: mats, boxes, relics }, left_behind: { materials: {}, boxes: 0, relics: 0 },
    danger: dOut, injured: dOut && dOut.kind === 'seam' && dOut.ok === false ? s.members[0].name : null,
    imprints: [], newcomer: s.rescue ? { guest_id: 'g-mock', name: '…' } : null, rescued_but_no_room: false, clue: null,
    discovered: s.discovers ? { spot_id: s.discovers, name: null, discovery_text: null } : null,
    visit_bonus: null, breath_grew: [], greeted_by: null, line: null, recalled: false, tutorial: false,
    early: !!(dOut && (dOut.choice === 'turn_back' || (dOut.ok === false && (d.kind === 'air' || d.kind === 'beast')))),
    late: !!(dOut && dOut.ok === false && d.kind === 'lost'),
  };
}

function err(code, detail) { return { status: code, body: { detail } }; }

// fetch 와 같은 꼴: (path, {method, body}) → {status, body}
export async function mockApi(path, opts = {}) {
  const url = new URL(path, location.origin), uid = url.searchParams.get('uid') || (opts.body && opts.body.uid);
  let s = load(uid);
  if (!s || Q.get('fresh') === '1' && !sessionStorage.getItem('expmock_fresh')) {
    try { sessionStorage.setItem('expmock_fresh', '1'); } catch { }
    s = await startMock(uid);
  }
  if (Q.get('view') === 'return' && s.returns_at > now()) { s.returns_at = now() - 5; s.committed = true; save(uid, s); }
  const route = (opts.method || 'GET') + ' ' + url.pathname;
  if (route === 'GET /api/expedition') {
    if (s.seen) return { status: 200, body: { expedition: null, expedition_return: null } };
    if (now() >= s.returns_at) return { status: 200, body: { expedition: null, expedition_return: returnOf(s) } };
    return { status: 200, body: { expedition: { id: s.id, members: s.members.map(m => m.id), member_names: s.members.map(m => m.name), dest: s.dest, dest_ko: null, length: s.length, started: s.started, returns_at: s.returns_at, now: now(), progress: sceneOf(s).progress, air_used: s.actions, lingering: Q.get('octo') === '1' ? 'octopus' : null, recalled: false, tutorial: false, scene: { open: sceneOf(s).open, committed: s.committed } }, expedition_return: null } };
  }
  if (route === 'GET /api/expedition/scene') {
    if (now() >= s.returns_at) return err(400, 'no expedition');
    return { status: 200, body: sceneOf(s) };
  }
  if (route === 'POST /api/expedition/scene') {
    const b = opts.body || {}, sc = sceneOf(s);
    if (!sc.open && b.action !== 'done') return err(400, 'scene closed');
    if (b.action === 'pick') {
      if (sc.next !== 'pick:' + b.i) return err(400, 'order');
      s.picked.push({ i: b.i, item: itemAt(s, b.i) });
    } else if (b.action === 'danger') {
      if (sc.next !== 'danger') return err(400, 'order');
      s.danger_choice = b.choice;
      if (b.choice === 'turn_back') { s.committed = true; s.returns_at = now() + 40; }
    } else if (b.action === 'fork') {
      if (sc.next !== 'fork') return err(400, 'order');
      s.fork = b.choice === 'dark' ? 'dark' : 'lit';
    } else if (b.action === 'drop') {
      if (sc.next !== 'drop') return err(400, 'order');
      const keep = new Set((b.keep || []).map(Number));
      s.dropped = s.picked.map((p, k) => k).filter(k => !keep.has(s.picked[k].i));
    } else if (b.action === 'done') {
      s.committed = true;
      if (!s.fork) s.fork = 'lit';
    } else return err(400, 'action');
    save(uid, s);
    return { status: 200, body: sceneOf(s) };
  }
  if (route === 'POST /api/expedition/seen') { s.seen = true; save(uid, s); return { status: 200, body: { ok: true } }; }
  return err(404, 'mock: ' + route);
}
