// static/expedition3d.js — 잔해 방주 원정 바깥 화면(물속판) · S15-C (개발/3D)
// 사양: docs/EXPEDITION.md §3-6(문턱 → 따라 나가기 1~2분 → 보내 두기 → 들여다보기 → 귀환)
// 계약: docs/API_EXPEDITION.md §5·§6·§8 — 숫자·결과·고를 것은 전부 서버가 준다. 화면은 계산하지 않는다(D2).
// 문장: data/expedition_text.json(시나리오) → GET /api/text/expedition. 이 파일에는 한국어 문장을 두지 않는다.
// 에셋: static/art/iso_sea/manifest.json(배경) 을 읽어 id 로 고른다. 경로를 코드에 박지 않는다(데이터가 규칙을 든다, D7).
// world.html / world3d.js(육상판)는 건드리지 않는다 — 이 화면은 그 파이프라인(시드 지형·안개 걷기·탭 이동·발견 연출)을
// 물속판으로 다시 짠 것이다. 교본: D2 D4 D6 D8 D9 D10.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ═══════════════════════════════════════════════════════════════════════════
// 0. 설정 — 데이터가 바뀌면 여기만(코드가 아니라 경로·키)
// ═══════════════════════════════════════════════════════════════════════════
const CFG = {
  manifest: '/static/art/iso_sea/manifest.json',
  charMeta: '/static/art/chars/front/p2/meta.json',
  charSrc: (role) => `/static/art/chars/front/p2/src/${role}.png`,      // x1 원본(셀 64, 발선 60)
  octopus: '/static/art/chars/front/p2/octopus.png',                    // x4, 4칸(idle 0~2 + 감기)
  text: '/api/text/moments',                                             // 서버가 expedition_text 묶음(entrance·guest·expedition·sealed_box·spot)을 여기 싣는다
  spots: '/api/spots',
  tile: 6,                                   // manifest: 땅 타일 6 m 격자
  walkMps: 0.7,                              // 무게추 걷기(swim_side 보폭 16px/1.4s=0.42 m/s 의 1.7배 — 1~2분 안에 줍기 셋. 발은 loopSec 이 맞춘다)
  pollSec: 30,
};
// 문장 키는 서버 id 그대로 읽는다(시나리오 S15 §F3: danger air|beast|seam|lost · lengths · destinations · 상자 아홉 갈래).
const Q = new URLSearchParams(location.search);
const MOCK = Q.get('mock') === '1';                       // ★ 개발 전용: 서버가 붙기 전 모의 API
const $ = (s) => document.querySelector(s);
if (Q.has('debug')) document.body.classList.add('debug');
const log = (s) => { const l = $('#log'); l.textContent = (l.textContent + '\n' + s).split('\n').slice(-16).join('\n'); };

const uid = Q.get('uid') || (() => { try { return localStorage.getItem('ark_uid') || 'anon'; } catch { return 'anon'; } })();
const wantExp = Q.get('exp');

// ── 결정적 난수(D6): 같은 terrain_seed = 같은 바닥
function fnv(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function rngOf(seed) { let a = fnv(String(seed)); return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

// ═══════════════════════════════════════════════════════════════════════════
// 1. API (실서버 또는 ★모의)
// ═══════════════════════════════════════════════════════════════════════════
let mockApi = null;
if (MOCK) mockApi = (await import('/static/expedition_mock.js')).mockApi;
async function api(path, body) {
  const opts = body ? { method: 'POST', body } : { method: 'GET' };
  if (mockApi && path.startsWith('/api/expedition')) {
    const r = await mockApi(path, opts);
    if (r.status >= 400) throw Object.assign(new Error(r.body.detail || 'error'), { status: r.status });
    return r.body;
  }
  const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(j.detail || r.status), { status: r.status });
  return j;
}

// ── 문장: 키가 없으면 빈 문자열(그 자리는 그림만 남는다). lines 배열은 원정 id 로 결정적으로 하나 고른다
let TEXT = {};
const GROUPS = ['entrance', 'guest', 'expedition', 'sealed_box', 'spot'];
const textReady = (async () => {
  try { const r = await fetch(CFG.text); if (r.ok) { const j = await r.json(); GROUPS.forEach(g => { if (j && j[g]) TEXT[g] = j[g]; }); } } catch { }
})();
let SPOTS = [];
fetch(CFG.spots + '?uid=' + encodeURIComponent(uid)).then(r => r.ok ? r.json() : []).then(j => { SPOTS = Array.isArray(j) ? j : (j.spots || []); }).catch(() => { });
let pickSalt = 'x';
const dig = (path) => path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), TEXT);
function T(path, vars, salt) {
  let v = dig(path);                                      // 키가 없으면 '' — 그 자리는 그림만 남는다
  if (Array.isArray(v)) v = v.length ? v[fnv(pickSalt + '|' + path + '|' + (salt || '')) % v.length] : '';
  if (typeof v !== 'string') return '';
  return v.replace(/\{(\w+)\}/g, (_, k) => (vars && vars[k] != null ? vars[k] : ''));
}
// 상자 무늬 이름: 서버 cat 'any'(튜토리얼) = 키트·문장의 'blank'
const boxCat = (c) => (c === 'any' || !c ? 'blank' : c);
const boxName = (c) => T('sealed_box.patterns.' + boxCat(c) + '.name') || (boxCat(c) === 'blank' ? T('sealed_box.blank.name') : '');
const timeStr = (ts) => { try { return new Intl.DateTimeFormat('ko-KR', { hour: 'numeric', minute: '2-digit' }).format(new Date(ts * 1000)); } catch { return ''; } };

// ═══════════════════════════════════════════════════════════════════════════
// 2. 렌더러 · 씬 · 카메라 (45°/45° 정사영 — DECISIONS 2026-09-23)
// ═══════════════════════════════════════════════════════════════════════════
const canvas = $('#c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = false;                       // 무광층: 해가 없다. 그림자는 발밑 원판으로(D8)

const scene = new THREE.Scene();
const WATER = new THREE.Color(0x0E3440);                  // manifest.scene_hint.fog 로 덮어쓴다
scene.background = WATER.clone().multiplyScalar(0.55);
const CAM_D = 60;
scene.fog = new THREE.Fog(WATER, CAM_D - 6, CAM_D + 34);   // 정사영이라 '화면 위쪽(먼 쪽)'이 물에 잠긴다(D10 밀도 대신 선형)

let frustum = 7;
const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 400);
const camTarget = new THREE.Vector3(0, 0, 0);
const camAz = Math.PI / 4, camEl = Math.PI / 4;
function placeCamera() {
  const a = innerWidth / innerHeight;
  camera.position.set(
    camTarget.x - Math.cos(camEl) * Math.sin(camAz) * CAM_D,
    camTarget.y + Math.sin(camEl) * CAM_D,
    camTarget.z + Math.cos(camEl) * Math.cos(camAz) * CAM_D);
  camera.lookAt(camTarget);
  camera.left = -frustum * a; camera.right = frustum * a; camera.top = frustum; camera.bottom = -frustum;
  camera.updateProjectionMatrix();
}
// 도트 정수 배율(2.5D 조건 ①): 기본 줌은 사람 셀 64px 이 ×k 가 되는 자리. 큰 화면 ×2, 폰 가로 ×1
const PPM_SRC = 27.5;
function defaultFrustum() { const k = innerHeight >= 600 ? 2 : 1; return innerHeight / (2 * PPM_SRC * k); }
frustum = defaultFrustum(); placeCamera();

// 땅 무리: 계약 좌표(문=원점, +x 트인 쪽, +z 아래)를 그대로 쓴다. 돌리지 않는다 — 6 m 타일 키트가 45° 아이소에서
// 마름모로 보이게 만들어졌다(배경 S15-E). +x 는 화면 오른쪽 위, +z 는 오른쪽 아래로 간다
const LAND_YAW = Number(Q.get('yaw') || 0);               // ★ 검증용
const land = new THREE.Group(); land.rotation.y = LAND_YAW; scene.add(land);
const toWorldV = (x, z, y = 0) => land.localToWorld(new THREE.Vector3(x, y, z));

// ── 빛: 아주 낮은 물빛 + 랜턴 하나(주색 1 = 랜턴, 아트 원칙)
const hemi = new THREE.HemisphereLight(0x2A6A78, 0x0a1a1e, 0.55); scene.add(hemi);
const down = new THREE.DirectionalLight(0xCFE8E6, 0.18); down.position.set(-10, 30, 6); scene.add(down);
const lantern = new THREE.PointLight(0xFFC870, 38, 14, 1.6); scene.add(lantern);
const glbLights = [];                                     // GLB 안 점광원(D10 고정 클램프)

// ═══════════════════════════════════════════════════════════════════════════
// 3. 에셋 — manifest 로 id 를 찾고, 같은 것은 InstancedMesh 로 한 번에(드로우콜 예산 D8)
// ═══════════════════════════════════════════════════════════════════════════
const loader = new GLTFLoader();
let MAN = { assets: [] };
const glbCache = new Map();
function assetById(id) { return (MAN.assets || []).find(a => a.id === id); }
function assetsByTag(tag) { return (MAN.assets || []).filter(a => (a.tags || []).includes(tag)); }
function loadGLB(id) {
  const a = assetById(id); if (!a) return Promise.resolve(null);
  if (!glbCache.has(id)) {
    const base = CFG.manifest.replace(/[^/]+$/, '');
    glbCache.set(id, loader.loadAsync(base + a.file).then(g => g.scene).catch(e => { log(`GLB ${id} 실패 ${e.message || e}`); return null; }));
  }
  return glbCache.get(id);
}
// GLB 한 개 → 메시 조각들(지오메트리·재질·로컬 행렬). 점광원은 따로 센다
function partsOf(root) {
  const parts = []; root.updateMatrixWorld(true);
  root.traverse(o => { if (o.isMesh) parts.push({ geo: o.geometry, mat: o.material, m: o.matrixWorld.clone() }); });
  return parts;
}
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _e = new THREE.Euler(), _p = new THREE.Vector3(), _s = new THREE.Vector3();
function placeM(x, z, rot, sc = 1, y = 0) { _e.set(0, rot, 0); _q.setFromEuler(_e); _p.set(x, y, z); _s.set(sc, sc, sc); return new THREE.Matrix4().compose(_p, _q, _s); }
// placements: [{m: Matrix4, hidden: bool, x, z}] → 메시 조각마다 InstancedMesh 하나
const ZERO = new THREE.Matrix4().makeScale(0, 0, 0);
const hiddenInst = [];                                    // 안개 아래 숨은 소품(걷히면 드러난다)
async function instance(id, placements, opts = {}) {
  if (!placements.length) return [];
  const root = await loadGLB(id); if (!root) return [];
  const out = [];
  for (const pt of partsOf(root)) {
    const mat = Array.isArray(pt.mat) ? pt.mat.map(m => m.clone()) : pt.mat.clone();
    (Array.isArray(mat) ? mat : [mat]).forEach(m => { if (opts.tint && m.color) m.color.multiply(opts.tint); });
    const im = new THREE.InstancedMesh(pt.geo, mat, placements.length);
    placements.forEach((pl, i) => {
      const M = new THREE.Matrix4().multiplyMatrices(pl.m, pt.m);
      if (pl.hidden) { im.setMatrixAt(i, ZERO); hiddenInst.push({ im, i, M, x: pl.x, z: pl.z }); } else im.setMatrixAt(i, M);
    });
    im.instanceMatrix.needsUpdate = true; im.frustumCulled = false;
    land.add(im); out.push(im);
  }
  return out;
}
// 단독 배치(표지·상자처럼 움직이거나 하나뿐인 것). 점광원은 세기를 고정 클램프(D10)
async function single(id, x, z, rot = 0, opts = {}) {
  const root = await loadGLB(id); if (!root) return null;
  const o = root.clone(true);
  o.position.set(x, opts.y || 0, z); o.rotation.y = rot;
  o.traverse(c => {
    if (c.isMesh) {
      c.material = Array.isArray(c.material) ? c.material.map(m => m.clone()) : c.material.clone();
      if (opts.transparentFix) (Array.isArray(c.material) ? c.material : [c.material]).forEach(m => { if (m.transparent || m.opacity < 1) { m.depthWrite = false; } });
    }
    if (c.isLight) { c.intensity = opts.lamp ?? 14; c.distance = opts.lampDist ?? 9; c.decay = 1.6; c.castShadow = false; glbLights.push(c); }
  });
  land.add(o);
  return o;
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. 바닥 — 6 m 타일 격자(시드). 왼쪽 열 = 절벽 밑(벽), 위 줄 = 절벽, 오른쪽·아래 = 심연으로 꺼짐
// ═══════════════════════════════════════════════════════════════════════════
let GRID = null;                                          // {c0,c1,r0,r1}
let fogOfWar = null;
function boundsOf(pts) {
  let x0 = -6, x1 = 30, z0 = -14, z1 = 14;
  pts.forEach(p => { x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); z0 = Math.min(z0, p.z); z1 = Math.max(z1, p.z); });
  const t = CFG.tile;
  return { c0: Math.floor((x0 - 3) / t) - 1, c1: Math.ceil((x1 + 3) / t) + 1, r0: Math.floor((z0 - 3) / t) - 1, r1: Math.ceil((z1 + 3) / t) + 1 };
}
// 경로 근처(사람이 걷는 띠)는 소품을 비운다 — 길이 보이게, 그리고 막히지 않게(D9)
function nearPath(x, z, pts, r) { for (const p of pts) if (Math.hypot(p.x - x, p.z - z) < r) return true; return false; }
function densePath(wp) {
  const out = [];
  for (let i = 0; i + 1 < wp.length; i++) {
    const a = wp[i], b = wp[i + 1], n = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.z - a.z) / 1.5));
    for (let k = 0; k < n; k++) out.push({ x: a.x + (b.x - a.x) * k / n, z: a.z + (b.z - a.z) * k / n });
  }
  if (wp.length) out.push(wp[wp.length - 1]);
  return out;
}

async function buildWorld(seed, keyPts, pathPts) {
  const R = rngOf(seed);
  const t = CFG.tile, B = GRID = boundsOf(keyPts.concat(pathPts));
  const groups = {};                                       // id → placements
  const add = (id, m, hidden, x, z) => { (groups[id] = groups[id] || []).push({ m, hidden, x, z }); };
  // 키트 규약(배경 S15-E 시트와 같은 각): 회전 0 이면 벽은 화면 왼쪽 위(-z), 꺼짐은 +x(화면 오른쪽 위).
  // 카메라 쪽 두 가장자리(-x 왼쪽 아래, +z 오른쪽 아래)는 낮은 꺼짐으로 둔다 — 벽이 사람을 가리지 않게
  const H = -Math.PI / 2, PI = Math.PI;
  for (let c = B.c0; c <= B.c1; c++) for (let r = B.r0; r <= B.r1; r++) {
    const x = c * t, z = r * t;
    if (r === B.r0) { add('ground_edge_wall', placeM(x, z, 0), false); continue; }                 // 위(왼쪽 위) = 절벽 밑
    if (c === B.c1 && r === B.r1) { add('ground_edge_corner', placeM(x, z, H), false); continue; }
    if (c === B.c0 && r === B.r1) { add('ground_edge_corner', placeM(x, z, PI), false); continue; }
    if (c === B.c1) { add('ground_edge_drop', placeM(x, z, 0), false); continue; }                 // 트인 쪽 = 심연
    if (c === B.c0) { add('ground_edge_drop', placeM(x, z, PI), false); continue; }
    if (r === B.r1) { add('ground_edge_drop', placeM(x, z, H), false); continue; }
    const far = (c - B.c0) / Math.max(1, B.c1 - B.c0), u = R();
    const id = u < 0.16 ? 'ground_rock' : far > 0.55 && u < 0.7 ? 'ground_silt' : u < 0.6 ? 'ground_sand_a' : 'ground_sand_b';
    add(id, placeM(x, z, Math.floor(R() * 4) * Math.PI / 2), false);
  }
  // 소품: 타일마다 0~3개. 안개 밑에서는 숨어 있다가 랜턴이 닿으면 드러난다
  const PROPS = [['rock_small', 0.22], ['rock_boulder', 0.10], ['rock_stack', 0.05], ['kelp_clump_a', 0.18], ['kelp_clump_b', 0.10],
    ['fan_a', 0.08], ['fan_b', 0.08], ['relic_cans', 0.07], ['relic_crate', 0.05], ['relic_cart', 0.035], ['relic_vending_husk', 0.025]].filter(([id]) => assetById(id));
  const tot = PROPS.reduce((s, p) => s + p[1], 0) || 1;
  for (let c = B.c0 + 1; c < B.c1; c++) for (let r = B.r0 + 1; r < B.r1; r++) {
    const n = Math.floor(R() * 3.2);
    for (let k = 0; k < n; k++) {
      const x = c * t + (R() - 0.5) * t, z = r * t + (R() - 0.5) * t;
      if (nearPath(x, z, pathPts, 2.2) || nearPath(x, z, keyPts, 2.6) || Math.hypot(x, z) < 5) { R(); R(); continue; }
      let u = R() * tot, id = PROPS[0][0];
      for (const [pid, w] of PROPS) { u -= w; if (u <= 0) { id = pid; break; } }
      add(id, placeM(x, z, R() * 6.283, 0.85 + R() * 0.35), true, x, z);
    }
  }
  await Promise.all(Object.entries(groups).map(([id, pl]) => instance(id, pl)));
  // 출발 표지: 탑 외벽 아랫동 + 사다리. 회전 0 = 외벽이 화면 왼쪽 위, 트인 물은 오른쪽(EXPEDITION §3-6 「왼쪽은 벽」)
  const lm = assetById('base_hatch_landmark');
  if (lm) { const o = await single('base_hatch_landmark', 0, 0, 0, { lamp: 18, lampDist: 10 }); if (o) o.userData.home = true; }
  // 안개(미탐험) — 어두운 물빛 판. 한 번 걸은 곳은 이 기기에 남는다(지도가 쌓인다, H4)
  fogOfWar = makeFog(B, seed);
  log(`world ${B.c1 - B.c0 + 1}×${B.r1 - B.r0 + 1} tiles · ids ${Object.keys(groups).length} · hidden ${hiddenInst.length}`);
}

function makeFog(B, seed) {
  const t = CFG.tile, x0 = (B.c0 + 0.5) * t, z0 = (B.r0 + 0.5) * t, W = (B.c1 - B.c0 - 1) * t, D = (B.r1 - B.r0 - 1) * t;
  const PX = 4, cv = document.createElement('canvas'); cv.width = Math.ceil(W * PX); cv.height = Math.ceil(D * PX);
  const g = cv.getContext('2d');
  g.fillStyle = '#04141a'; g.fillRect(0, 0, cv.width, cv.height);
  const R = rngOf(seed + '|silt');
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(${20 + R() * 30 | 0},${50 + R() * 40 | 0},${58 + R() * 40 | 0},${0.05 + R() * 0.08})`; g.beginPath(); g.arc(R() * cv.width, R() * cv.height, 2 + R() * 14, 0, 6.283); g.fill(); }
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(W, D), new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0.93, depthWrite: false, fog: false }));
  mesh.rotation.x = -Math.PI / 2; mesh.position.set(x0 + W / 2, 0.42, z0 + D / 2); mesh.renderOrder = 3;
  land.add(mesh);
  const key = 'expfog|' + seed;
  let walked = []; try { walked = JSON.parse(localStorage.getItem(key) || '[]'); } catch { }
  let dirty = false, saveT = 0;
  function reveal(x, z, r, keep = true) {
    const cx = (x - x0) * PX, cy = (z - z0) * PX, cr = r * PX;
    g.globalCompositeOperation = 'destination-out';
    const gr = g.createRadialGradient(cx, cy, cr * 0.45, cx, cy, cr);
    gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, cr, 0, 6.283); g.fill();
    g.globalCompositeOperation = 'source-over'; dirty = true;
    for (let i = hiddenInst.length - 1; i >= 0; i--) {
      const h = hiddenInst[i]; if (Math.hypot(h.x - x, h.z - z) > r * 0.92) continue;
      h.im.setMatrixAt(h.i, h.M); h.im.instanceMatrix.needsUpdate = true; hiddenInst.splice(i, 1);
    }
    if (keep) { walked.push([+x.toFixed(1), +z.toFixed(1), +r.toFixed(1)]); if (walked.length > 500) walked.splice(0, walked.length - 500); saveT = performance.now() + 1500; }
  }
  walked.forEach(([x, z, r]) => reveal(x, z, r, false));
  return {
    reveal,
    flush() {
      if (dirty) { tex.needsUpdate = true; dirty = false; }
      if (saveT && performance.now() > saveT) { saveT = 0; try { localStorage.setItem(key, JSON.stringify(walked)); } catch { } }
    },
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. 바다 눈(marine snow) — 화면 주변 상자 안에서 천천히 내려간다. 점 하나 = 드로우콜 하나(D8)
// ═══════════════════════════════════════════════════════════════════════════
const SNOW_N = innerHeight < 500 ? 420 : 700, SNOW = { w: 46, h: 14 };
const snowGeo = new THREE.BufferGeometry(), snowPos = new Float32Array(SNOW_N * 3), snowVel = new Float32Array(SNOW_N);
{ const R = rngOf('snow'); for (let i = 0; i < SNOW_N; i++) { snowPos[i * 3] = (R() - .5) * SNOW.w; snowPos[i * 3 + 1] = R() * SNOW.h; snowPos[i * 3 + 2] = (R() - .5) * SNOW.w; snowVel[i] = 0.12 + R() * 0.25; } }
snowGeo.setAttribute('position', new THREE.BufferAttribute(snowPos, 3));
const snowTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 8; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(2, 2, 4, 4); g.fillRect(3, 1, 2, 6); g.fillRect(1, 3, 6, 2); const t = new THREE.CanvasTexture(c); t.magFilter = t.minFilter = THREE.NearestFilter; return t; })();
const snow = new THREE.Points(snowGeo, new THREE.PointsMaterial({ size: 3, sizeAttenuation: false, map: snowTex, color: 0xcfe8e6, transparent: true, opacity: 0.5, depthWrite: false, fog: false }));
snow.renderOrder = 6; snow.frustumCulled = false; scene.add(snow);
function stepSnow(dt, t) {
  for (let i = 0; i < SNOW_N; i++) {
    let x = snowPos[i * 3], y = snowPos[i * 3 + 1], z = snowPos[i * 3 + 2];
    y -= snowVel[i] * dt; x += Math.sin(t * 0.3 + i) * 0.05 * dt;
    if (y < 0) y += SNOW.h;
    snowPos[i * 3] = x; snowPos[i * 3 + 1] = y;
  }
  snow.position.set(camTarget.x - (camTarget.x % SNOW.w), 0, camTarget.z - (camTarget.z % SNOW.w));
  // 화면 밖으로 나간 점은 반대쪽으로(상자를 카메라에 붙인다)
  for (let i = 0; i < SNOW_N; i++) {
    const wx = snowPos[i * 3] + snow.position.x - camTarget.x, wz = snowPos[i * 3 + 2] + snow.position.z - camTarget.z;
    if (wx > SNOW.w / 2) snowPos[i * 3] -= SNOW.w; else if (wx < -SNOW.w / 2) snowPos[i * 3] += SNOW.w;
    if (wz > SNOW.w / 2) snowPos[i * 3 + 2] -= SNOW.w; else if (wz < -SNOW.w / 2) snowPos[i * 3 + 2] += SNOW.w;
  }
  snowGeo.attributes.position.needsUpdate = true;
}

// ═══════════════════════════════════════════════════════════════════════════
// 6. 사람 — P2 도트 빌보드(DECISIONS 2026-10-01 캐릭터는 도트, 배경은 3D) + 잠수 투구
//    meta.json 에 `suit_layer`(경로 틀, <role>) 나 `swim_side` 행이 생기면 자동으로 그쪽을 쓴다(캐릭터 담당 예정)
// ═══════════════════════════════════════════════════════════════════════════
let META = { rows: { idle: 0 }, frames: { idle: 2 }, anim_seconds: { idle: 2.8 }, cols: 3, src_cell: 64, src_baseline: 60 };
const metaReady = fetch(CFG.charMeta).then(r => r.ok ? r.json() : null).then(j => { if (j && j.rows) META = j; }).catch(() => { });
const imgLoad = (src) => new Promise((res) => { const im = new Image(); im.onload = () => res(im); im.onerror = () => res(null); im.src = src; });

// 투구: 셀마다 머리 꼭대기를 찾아 유리 원을 도트로 찍는다(정수 픽셀, 보간 없음). 테 아래쪽은 놋쇠 목둘레
function drawHelmets(g, w, h, cell) {
  const id = g.getImageData(0, 0, w, h), d = id.data;
  const A = (x, y) => d[(y * w + x) * 4 + 3];
  const put = (x, y, r, gg, b, a) => {
    if (x < 0 || y < 0 || x >= w || y >= h) return; const k = (y * w + x) * 4, al = a / 255;
    d[k] = d[k] * (1 - al) + r * al; d[k + 1] = d[k + 1] * (1 - al) + gg * al; d[k + 2] = d[k + 2] * (1 - al) + b * al; d[k + 3] = Math.max(d[k + 3], a);
  };
  for (let cy = 0; cy + cell <= h; cy += cell) for (let cx = 0; cx + cell <= w; cx += cell) {
    let top = -1;
    for (let y = 2; y < 40 && top < 0; y++) for (let x = 8; x < cell - 8; x++) if (A(cx + x, cy + y) > 40) { top = y; break; }
    if (top < 0) continue;
    let sx = 0, n = 0;
    for (let y = top; y < top + 10; y++) for (let x = 8; x < cell - 8; x++) if (A(cx + x, cy + y) > 40) { sx += x; n++; }
    const hx = Math.round(sx / Math.max(1, n)), hy = top + 9, R = 11;
    for (let y = -R - 1; y <= R + 1; y++) for (let x = -R - 1; x <= R + 1; x++) {
      const dd = Math.hypot(x, y), px = cx + hx + x, py = cy + hy + y;
      if (dd <= R - 0.5) put(px, py, 150, 214, 220, 34);                              // 유리
      else if (dd <= R + 0.5) {
        if (y > R * 0.5) put(px, py, 176, 138, 74, 255);                              // 놋쇠 목둘레
        else put(px, py, 168, 222, 222, 215);                                         // 유리 테
      }
    }
    put(cx + hx - 5, cy + hy - 6, 255, 255, 255, 220); put(cx + hx - 4, cy + hy - 7, 255, 255, 255, 220); put(cx + hx - 6, cy + hy - 4, 255, 255, 255, 150);
  }
  g.putImageData(id, 0, 0);
}
// meta.suit_layer = "static/art/chars/front/p2/suit/<role>_<body>.png (x1) · …" — 앞 경로 틀만 쓴다(캐릭터 S15)
function suitPath(role, body) {
  const m = String(META.suit_layer || '').match(/^\s*(\S+\.png)/);
  return m ? '/' + m[1].replace(/^\//, '').replace('<role>', role).replace('<body>', body) : null;
}
let usedSuit = 0, usedHelmet = 0;                        // 검수용: 캐릭터 잠수복 겹 / 임시 투구
async function suitSheet(role, body = 'a') {
  await metaReady;
  const im = await imgLoad(CFG.charSrc(body === 'b' ? role + '_b' : role)) || await imgLoad(CFG.charSrc(role)) || await imgLoad(CFG.charSrc('scout'));
  if (!im) return null;
  const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight;
  const g = c.getContext('2d', { willReadFrequently: true }); g.imageSmoothingEnabled = false; g.drawImage(im, 0, 0);
  const sp = suitPath(role, body), layer = sp ? await imgLoad(sp) : null;
  if (layer) { g.drawImage(layer, 0, 0); usedSuit++; } else { drawHelmets(g, c.width, c.height, META.src_cell || 64); usedHelmet++; }
  return c;
}

const people = [];                                       // {sp, tex, x, z, path, clip, face, carry, shadow}
const CELL = () => META.src_cell || 64, BASE = () => META.src_baseline || 60;
function makeSprite(canvasOrImg, cols, rows) {
  const tex = new THREE.Texture(canvasOrImg); tex.needsUpdate = true;
  tex.magFilter = THREE.NearestFilter; tex.minFilter = THREE.NearestFilter; tex.generateMipmaps = false; tex.colorSpace = THREE.SRGBColorSpace;
  tex.repeat.set(1 / cols, 1 / rows);
  const mat = new THREE.SpriteMaterial({ map: tex, color: 0xffeacc, depthTest: false, depthWrite: false, fog: false, transparent: true });
  const sp = new THREE.Sprite(mat); sp.renderOrder = 20; sp.center.set(0.5, 0);
  return { sp, tex };
}
const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.38, depthWrite: false, fog: false });
const shadowGeo = new THREE.CircleGeometry(0.42, 16);
async function addPerson(m, x, z) {
  const sheet = await suitSheet(m.role || 'scout'); if (!sheet) return null;
  const cell = CELL(), cols = META.cols || 3, rows = Math.round(sheet.height / cell);
  const { sp, tex } = makeSprite(sheet, cols, rows);
  sp.center.set(0.5, (cell - BASE()) / cell);
  land.add(sp);
  const sh = new THREE.Mesh(shadowGeo, shadowMat); sh.rotation.x = -Math.PI / 2; sh.scale.set(1, 0.55, 1); sh.renderOrder = 4; land.add(sh);
  const p = { m, sp, tex, sh, x, z, path: [], clip: 'idle', face: 1, t0: Math.random() * 3, rows, cols, pose: null, onArrive: null };
  people.push(p); return p;
}
// 물속은 옆모습으로 충분하다(meta.billboard_3d): 움직이면 swim_side(상자를 들면 carry_box_swim), 멈추면 swim_idle.
// 원본이 오른쪽을 보는 행(meta.s15_rows[..].facing == right, 또는 *_side)은 왼쪽으로 갈 때 반전한다.
// 물속 행이 없는 옛 시트면 육상 사슬(walk_side · back_walk · walk)로 내려간다
function clipFor(p, moving, dx, dz) {
  const has = (k) => META.rows && META.rows[k] != null && (META.rows[k] + 1) <= p.rows;
  if (p.pose && has(p.pose)) return p.pose;
  if (!moving) return has('swim_idle') ? 'swim_idle' : 'idle';
  if (p.carry && has('carry_box_swim')) return 'carry_box_swim';
  if (has('swim_side')) return 'swim_side';
  if (Math.abs(dz) > 1.6 * Math.abs(dx)) return dz < 0 ? (has('back_walk') ? 'back_walk' : 'walk') : (has('walk') ? 'walk' : 'idle');
  return has('walk_side') ? 'walk_side' : 'idle';
}
const facesRight = (clip) => /_side$/.test(clip) || (((META.s15_rows || {})[clip] || {}).facing === 'right');
// 발이 미끄러지지 않게: 한 바퀴 시간 = 보폭(원본 px) / (속도 × 27.5)
function loopSec(clip, moving, speed) {
  const st = (((META.s15_rows || {})[clip] || {}).stride_src_px_per_loop || {}).adult
    || ((((META.s12_rows || {})[clip] || {}).stride_src_px_per_loop) || {}).adult;
  if (moving && st) return st / (speed * PPM_SRC);
  return (META.anim_seconds || {})[clip] || 1;
}
function spriteScale() {                                 // 화면 px/m → 정수 배율 k → 월드 크기
  const P = innerHeight / (2 * frustum), k = Math.max(1, Math.round(CELL() / PPM_SRC * P / CELL()));
  return CELL() * k / P;
}
function stepPeople(dt, t) {
  const S = spriteScale();
  for (const p of people) {
    let moving = false, dx = 0, dz = 0;
    if (p.path.length) {
      const tg = p.path[0]; dx = tg.x - p.x; dz = tg.z - p.z; const d = Math.hypot(dx, dz);
      if (d < 0.12) { p.x = tg.x; p.z = tg.z; p.path.shift(); if (!p.path.length && p.onArrive) { const f = p.onArrive; p.onArrive = null; f(); } }
      else { const k = Math.min(1, (p.speed || CFG.walkMps) * dt / d); p.x += dx * k; p.z += dz * k; moving = true; if (Math.abs(dx) > 0.02) p.face = dx > 0 ? 1 : -1; }
    }
    const clip = clipFor(p, moving, dx, dz), row = META.rows[clip] ?? 0;
    const fr = Math.max(1, Math.min(p.cols, (META.frames || {})[clip] || 1)), sec = loopSec(clip, moving, p.speed || CFG.walkMps);
    const f = Math.floor(((t + p.t0) / sec) * fr) % fr;
    const flip = facesRight(clip) && p.face < 0;
    p.tex.repeat.x = (flip ? -1 : 1) / p.cols;
    p.tex.offset.x = (flip ? f + 1 : f) / p.cols;
    p.tex.offset.y = 1 - (row + 1) / p.rows;
    p.sp.scale.set(S, S, 1);
    p.sp.position.set(p.x, 0.05 + (moving ? 0 : Math.sin(t * 1.3 + p.t0) * 0.02), p.z);
    p.sh.position.set(p.x, 0.43, p.z);
  }
}

// 문어(식구) — 원정에 따라 나온 날만. 말하지 않는다(DECISIONS 2026-09-27): 자리와 움직임만
let octo = null;
async function addOctopus(lead) {
  const im = await imgLoad(CFG.octopus); if (!im) return;
  const { sp, tex } = makeSprite(im, 4, 1); land.add(sp);
  octo = { sp, tex, lead, x: lead.x - 1, z: lead.z + 0.6 };
}
function stepOcto(dt, t) {
  if (!octo) return;
  const L = octo.lead, tx = L.x - 1.1 * L.face, tz = L.z + 0.5, d = Math.hypot(tx - octo.x, tz - octo.z);
  if (d > 0.3) { const k = Math.min(1, 1.3 * dt / d * Math.max(1, d)); octo.x += (tx - octo.x) * k; octo.z += (tz - octo.z) * k; }
  const f = Math.floor(t * 1.4) % 3; octo.tex.offset.x = f / 4;
  const S = spriteScale(); octo.sp.scale.set(S * 0.8, S * 0.8, 1);
  octo.sp.position.set(octo.x, 0.6 + Math.sin(t * 1.7) * 0.15, octo.z);
}

// ═══════════════════════════════════════════════════════════════════════════
// 7. 반짝이(줍기) · 갈림길 · 위험 그림자 · 스팟 표지
// ═══════════════════════════════════════════════════════════════════════════
const glowTex = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d');
  const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, 'rgba(255,240,190,1)'); gr.addColorStop(0.25, 'rgba(255,214,130,.55)'); gr.addColorStop(1, 'rgba(255,200,112,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  g.fillStyle = 'rgba(255,255,240,.95)'; g.fillRect(31, 14, 2, 36); g.fillRect(14, 31, 36, 2);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
})();
const glints = [];                                        // {i, x, z, sp, state, obj}
function addGlint(pk) {
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false, fog: false, transparent: true }));
  sp.renderOrder = 15; sp.position.set(pk.pos.x, 0.5, pk.pos.z); land.add(sp);
  const g = { i: pk.i, x: pk.pos.x, z: pk.pos.z, sp, state: pk.state, obj: null };
  glints.push(g); return g;
}
function stepGlints(t) {
  for (const g of glints) {
    if (g.state !== 'sparkle') { g.sp.visible = false; continue; }
    const s = 0.9 + 0.25 * Math.sin(t * 3 + g.i * 2);
    g.sp.scale.set(s, s, 1); g.sp.material.opacity = 0.75 + 0.25 * Math.sin(t * 5 + g.i);
  }
}
// 주운 것이 손에 잡히는 순간: 상자는 갈래 무늬 GLB, 유물·재료는 잔해 GLB 가 잠깐 떠올랐다 사라진다
async function showFound(item, x, z) {
  if (!item || item.kind === 'empty') return;
  const id = item.kind === 'box' ? (assetById('sealed_box_' + boxCat(item.cat)) ? 'sealed_box_' + boxCat(item.cat) : 'sealed_box_blank')
    : item.kind === 'relic' ? 'relic_cans' : 'relic_crate';
  const o = await single(id, x, z, 0.4, { y: 3.0 }); if (!o) return;
  const sc = item.kind === 'material' ? 0.7 : 1.1; o.scale.setScalar(sc);
  o.traverse(c => { if (c.isMesh) { c.renderOrder = 12; (Array.isArray(c.material) ? c.material : [c.material]).forEach(m => { m.depthTest = false; m.fog = false; }); } });
  floaters.push({ o, t: 0 });
}
const floaters = [];
function stepFloaters(dt) {
  for (let i = floaters.length - 1; i >= 0; i--) {
    const f = floaters[i]; f.t += dt; f.o.position.y = 3.0 + Math.min(1, f.t) * 0.4; f.o.rotation.y += dt * 1.2;
    if (f.t > 3) { land.remove(f.o); floaters.splice(i, 1); }
  }
}
let forkObj = null, shadowObj = null, beaconObj = null;

// ═══════════════════════════════════════════════════════════════════════════
// 8. HUD · 서술 · 고르기 카드
// ═══════════════════════════════════════════════════════════════════════════
function narr(text, ms = 6500) {
  const el = $('#narr'); if (!text) { el.classList.remove('show'); return; }
  el.textContent = text; el.classList.add('show');
  clearTimeout(narr._t); if (ms) narr._t = setTimeout(() => el.classList.remove('show'), ms);
}
// 관리실 방송은 문 안에서만 들린다 → 문턱에서 끊긴다(J3)
function paCut(text, cutAfter) {
  const el = $('#pa'); if (!text) return Promise.resolve();
  el.textContent = text; el.className = 'show';
  return new Promise(res => setTimeout(() => { el.className = 'cut'; setTimeout(() => { el.className = ''; res(); }, 520); }, cutAfter));
}
function choice(html, cls = '') {
  document.body.classList.add('choosing');
  const el = $('#choice'); el.className = 'show ' + cls; el.innerHTML = html; return el;
}
function choiceOff() { document.body.classList.remove('choosing'); $('#choice').className = ''; $('#choice').innerHTML = ''; }
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let airTicks = 0;
function paintHud(sc) {
  const names = (sc.members || []).map(m => m.name).filter(Boolean);
  $('#who').textContent = names.join(' · ');
  const band = Math.max(0, Math.min(1, sc.air_band ?? 1));
  $('#airFill').style.width = (band * 100).toFixed(1) + '%';
  const nT = (sc.head && sc.head.picks ? sc.head.picks.length : 0);
  if (nT !== airTicks) { airTicks = nT; $('#airTicks').innerHTML = '<span></span>'.repeat(Math.max(1, nT)); }
  const c = sc.carry || { slots: 0, used: 0, items: [] }, hands = $('#hands');
  const cells = []; let used = 0;
  (c.items || []).forEach(it => { const s = it.kind === 'box' ? 2 : it.kind === 'empty' ? 0 : 1; for (let k = 0; k < s; k++) cells.push(it.kind === 'box' ? 'on box' : 'on'); used += s; });
  for (let k = used; k < (c.slots || 0); k++) cells.push('');
  hands.innerHTML = cells.map(cl => `<b class="${cl}"></b>`).join('');
}
function paintClock(ret) { $('#clock').textContent = ret ? '⏲ ' + timeStr(ret) : ''; }

// ═══════════════════════════════════════════════════════════════════════════
// 9. 흐름 — 문턱 → (따라 나가기 | 보내 두기) → 들여다보기 → 귀환
// ═══════════════════════════════════════════════════════════════════════════
let SC = null, EXP = null, mode = 'loading', lead = null, waypoints = [], pathLen = 0;
const vars = () => {
  const m = (SC && SC.members) || (EXP && (EXP.member_names || []).map(n => ({ name: n }))) || [];
  const kind = (SC && SC.dest && SC.dest.kind) || (EXP && EXP.dest && EXP.dest.kind);
  return {
    name: m[0] ? m[0].name : '', name2: m[1] ? m[1].name : '',
    dest: (EXP && EXP.dest_ko) || (SC && SC.dest_ko) || T('expedition.destinations.' + kind),
    return_at: timeStr((SC && SC.returns_at) || (EXP && EXP.returns_at)),
  };
};
function goBase() { if (Q.has('debug')) console.log('goBase', new Error().stack); location.href = '/base'; }

function setLeave(on) {
  const b = $('#btnLeave'); b.hidden = !on;
  b.textContent = T('expedition.leave_it_label') || '⌂';
}
$('#btnLeave').onclick = async () => {
  // 보내 두기: 나머지는 자동 규칙(서버). 원정은 계속된다. 맡기는 말은 관리실 방송(집 안의 목소리)
  if (SC && SC.open && !SC.committed) { try { SC = await api('/api/expedition/scene', { uid, action: 'done' }); } catch (e) { log('done ' + e.message); } }
  const line = T('expedition.leave_it_line', vars());
  if (line) { $('#pa').textContent = line; $('#pa').className = 'show'; }
  $('#fade').classList.remove('off');
  setTimeout(goBase, line ? 1600 : 700);
};

// 경로(waypoints)를 진행도로 보간 — 들여다보기(④)와 귀환 장면이 쓴다
function pathAt(f) {
  if (!waypoints.length) return { x: 0, z: 0 };
  let need = Math.max(0, Math.min(1, f)) * pathLen;
  for (let i = 0; i + 1 < waypoints.length; i++) {
    const a = waypoints[i], b = waypoints[i + 1], d = Math.hypot(b.x - a.x, b.z - a.z);
    if (need <= d) { const k = d ? need / d : 0; return { x: a.x + (b.x - a.x) * k, z: a.z + (b.z - a.z) * k }; }
    need -= d;
  }
  return waypoints[waypoints.length - 1];
}

async function boot() {
  await textReady;
  try {
    EXP = await api('/api/expedition?uid=' + encodeURIComponent(uid));
  } catch (e) { log('poll ' + e.message); EXP = null; }
  if (!MAN.assets.length) { try { MAN = await (await fetch(CFG.manifest)).json(); applyHint(); } catch (e) { log('manifest 없음'); } }
  const ex = EXP && EXP.expedition, ret = EXP && EXP.expedition_return;
  if (ret && (!wantExp || ret.id === wantExp || !ex)) return startReturn(ret);
  if (!ex) { mode = 'none'; await buildWorld(uid + '|door', [], [{ x: 0, z: 0 }]); fogOfWar.reveal(0, 0, 9); setLeave(true); $('#fade').classList.add('off'); return; }
  EXP = ex; pickSalt = ex.id;
  SC = await api('/api/expedition/scene?uid=' + encodeURIComponent(uid));
  remember(SC);
  await setupScene(SC);
  if (SC.open && !SC.committed) return startThreshold();
  return startPeek();
}
function applyHint() {
  const h = MAN.scene_hint || {};
  if (h.fog) { WATER.set(h.fog); scene.fog.color.copy(WATER); scene.background = WATER.clone().multiplyScalar(0.55); }
  if (h.ambient) hemi.color.set(h.ambient);
  if (h.sun) down.color.set(h.sun);
}
// 귀환 장면은 /api/ark 결과만 받는다(지형 시드·경로가 없다) → 이 기기에서 본 장면을 원정 id 로 기억해 둔다
function remember(sc) { try { sessionStorage.setItem('expscene|' + sc.exp_id, JSON.stringify({ terrain_seed: sc.terrain_seed, waypoints: sc.waypoints, discovers: sc.discovers, members: sc.members, lantern: sc.lantern_radius_m })); } catch { } }
function recall(id) { try { return JSON.parse(sessionStorage.getItem('expscene|' + id) || 'null'); } catch { return null; } }

async function setupScene(sc) {
  waypoints = (sc.waypoints && sc.waypoints.length) ? sc.waypoints : [{ x: 0, z: 0 }, { x: 24, z: 0 }, { x: 0, z: 0 }];
  pathLen = 0; for (let i = 0; i + 1 < waypoints.length; i++) pathLen += Math.hypot(waypoints[i + 1].x - waypoints[i].x, waypoints[i + 1].z - waypoints[i].z);
  const head = sc.head || {}, keys = [];
  (head.picks || []).forEach(p => keys.push(p.pos));
  if (head.fork && head.fork.pos) keys.push(head.fork.pos);
  if (sc.discovers && sc.discovers.pos) keys.push(sc.discovers.pos);
  await buildWorld(sc.terrain_seed || (uid + '|x'), keys, densePath(waypoints));
  lantern.distance = (sc.lantern_radius_m || 8) * 1.7;
  const ms = sc.members || [];
  for (let i = 0; i < ms.length; i++) { const p = await addPerson(ms[i], 0.6 - i * 0.9, 0.3 + i * 0.8); if (i === 0) lead = p; else if (p) p.follow = lead; }
  if (EXP && EXP.lingering === 'octopus' && lead) await addOctopus(lead);
  (head.picks || []).forEach(addGlint);
  if (head.fork && head.fork.pos && assetById('fork_marker')) forkObj = await single('fork_marker', head.fork.pos.x, head.fork.pos.z, -Math.PI / 2, { lamp: 10, lampDist: 6 });
  paintHud(sc); paintClock(sc.returns_at);
}

// ① 문턱 — 관리실 목소리가 끊기고, 랜턴이 닿는 데까지만 보인다
async function startThreshold() {
  mode = 'threshold';
  camTarget.set(...toWorldV(4, 0).toArray()); placeCamera();
  fogOfWar.reveal(0, 0, (SC.lantern_radius_m || 8));
  // hatch_exit 행은 셀 안에 사다리를 함께 그린다 — 출발 표지 GLB 에도 사다리가 있어 두 번 보이므로 쓰지 않는다(캐릭터 S15 안내)
  $('#fade').classList.add('off');
  await paCut(T('expedition.send_off', vars()), 2600);
  narr(T('expedition.follow.start'), 0);
  setLeave(true);
  const el = choice(`<div class="row"><button class="key" id="cFollow">${esc(T('expedition.follow.label') || '▸')}</button>
     <button id="cSend">${esc(T('expedition.leave_it_label') || '⌂')}</button></div>`);
  el.querySelector('#cFollow').onclick = () => { choiceOff(); narr(''); startFollow(); };
  el.querySelector('#cSend').onclick = () => $('#btnLeave').click();
}

// ② 따라 나가기 — 땅을 누르면 걷고, 반짝이를 누르면 줍는다. 공기 띠는 줍기마다(초가 아니다)
let busy = false;
function startFollow() { mode = 'follow'; react(); }
function react() {
  if (mode !== 'follow' || !SC) return;
  paintHud(SC);
  const nx = SC.next || 'done';
  if (!SC.open && !SC.committed) return handoff();
  if (nx === 'danger') return setTimeout(dangerBeat, 1600);
  if (nx === 'fork') return forkBeat();
  if (nx === 'drop') return dropBeat();
  if (nx === 'done') return handoff();
}
async function act(body) {
  busy = true;
  try { SC = await api('/api/expedition/scene', Object.assign({ uid }, body)); return true; }
  catch (e) { log(`scene ${body.action} → ${e.status || ''} ${e.message}`); try { SC = await api('/api/expedition/scene?uid=' + encodeURIComponent(uid)); } catch { } return false; }
  finally { busy = false; }
}
function walkLead(x, z, then) {
  if (!lead) return;
  // 문(x<0.5)과 벽 쪽으로는 가지 않는다 — 벽 대신 경계는 위험이다(D9). 격자 밖은 가장자리로 자른다
  const t = CFG.tile, B = GRID;
  x = Math.max(0.5, Math.min((B.c1 - 0.6) * t, x)); z = Math.max((B.r0 + 0.7) * t, Math.min((B.r1 - 0.6) * t, z));
  lead.path = [{ x, z }]; lead.onArrive = then || null;
  people.forEach(p => { if (p.follow) { p.path = [{ x: x - 0.9, z: z + 0.8 }]; } });
}
async function pickGlint(g) {
  if (busy || mode !== 'follow') return;
  if (SC.next !== 'pick:' + g.i) { if (SC.next === 'danger') dangerBeat(); return; }
  walkLead(g.x - 0.5, g.z + 0.2, async () => {
    if (SC.next !== 'pick:' + g.i) return;
    lead.pose = 'work_34'; setTimeout(() => { if (lead) lead.pose = null; }, 900);
    if (!(await act({ action: 'pick', i: g.i }))) return react();
    const pk = (SC.head.picks || []).find(p => p.i === g.i);
    g.state = 'picked';
    const it = pk && pk.item;
    paintHud(SC);
    showFound(it, lead.x, lead.z);                       // 머리 위로 떠올라 보인다(사람 그림에 가리지 않게)
    lead.carry = (SC.carry && SC.carry.items || []).some(x => x.kind === 'box');
    const lineIx = it ? ({ material: 0, relic: 1, box: 2 }[it.kind]) : undefined;
    const arr = ((((TEXT.expedition || {}).follow) || {}).pickup) || [];
    const lab = it ? (it.ko || (it.kind === 'box' && boxName(it.cat) ? '「' + boxName(it.cat) + '」' : '')) : '';
    narr([lineIx != null ? arr[lineIx] : '', lab].filter(Boolean).join('  ·  '), 3800);
    // 마지막 줍기(튜토리얼이면 빈 원 상자) 뒤에는 그 순간을 3초 남겨 두고 손을 놓는다
    if (SC.next === 'done') setTimeout(react, 3400); else react();
  });
}
async function dangerBeat() {
  if (mode !== 'follow' || SC.next !== 'danger' || $('#choice').classList.contains('show')) return;
  const d = SC.head.danger || {}, k = d.kind;
  // 큰 그림자가 랜턴 너머로 지나간다(배경 danger_shadow — 투명 몸은 depthWrite 끔)
  if (!shadowObj && assetById('danger_shadow')) shadowObj = await single('danger_shadow', lead.x + 4.5, lead.z - 2.5, 0.8, { transparentFix: true });
  if (shadowObj) shadowObj.traverse(c => { if (c.isMesh) c.renderOrder = 5; });   // 안개 판(3) 위에 — 아직 안 걸은 곳을 지나가도 보이게
  if (shadowObj) { shadowObj.userData.v = { x: -0.55, z: 0.75 }; }   // 화면 오른쪽 위에서 랜턴 곁을 지나 왼쪽 아래로
  narr(T(`expedition.danger.kinds.${k}.prompt`), 0);
  const pct = Math.round((d.p_hide || 0) * 100);
  const el = choice(`<div class="row">
     <div class="opt"><button class="key" id="cHide">${esc(T('expedition.danger.hide_label') || '▼')}<span class="pct">${pct}%</span></button></div>
     <div class="opt"><button id="cBack">${esc(T('expedition.danger.turn_back_label') || '◂')}</button><small>${esc(T('expedition.danger.turn_back_line'))}</small></div></div>`, 'danger');
  el.querySelector('#cHide').onclick = async () => {
    choiceOff(); lead.pose = META.rows.sit != null ? 'sit' : null;
    if (await act({ action: 'danger', choice: 'hide' })) { setTimeout(() => { lead.pose = null; narr(''); react(); }, 3600); } else react();
  };
  el.querySelector('#cBack').onclick = async () => {
    choiceOff(); narr(T('expedition.danger.turn_back_line'), 5000);
    if (await act({ action: 'danger', choice: 'turn_back' })) { mode = 'turning'; walkLead(0.6, 0.3, () => handoff(true)); } else react();
  };
}
function forkBeat() {
  const f = SC.head.fork || {};
  narr(T('expedition.follow.fork.prompt'), 0);
  const el = choice(`<div class="row">
     <div class="opt"><button class="key" id="cLit">${esc(T('expedition.follow.fork.light_label') || '☼')}</button><small>${esc(T('expedition.follow.fork.light_desc'))}</small></div>
     <div class="opt"><button id="cDark">${esc(T('expedition.follow.fork.dark_label') || '●')}</button><small>${esc(T('expedition.follow.fork.dark_desc'))}</small></div></div>`);
  if (f.pos) walkLead(f.pos.x - 1.4, f.pos.z + 0.4);
  const go = async (ch) => {
    choiceOff(); narr('');
    if (!(await act({ action: 'fork', choice: ch }))) return react();
    const p = f.pos || { x: lead.x, z: lead.z };
    walkLead(p.x + 3, p.z + (ch === 'lit' ? -2.5 : 2.5), () => react());
  };
  el.querySelector('#cLit').onclick = () => go('lit');
  el.querySelector('#cDark').onclick = () => go('dark');
}
function dropBeat() {
  const items = (SC.carry && SC.carry.items) || [], keep = new Set(items.map(it => it.i));
  narr(T('expedition.follow.hands_full.prompt'), 0);
  const lab = (it) => it.kind === 'box' ? boxName(it.cat) || '▣' : it.ko || (it.kind === 'relic' ? '◆' : '■');
  const el = choice(`<div class="row">${items.map(it => `<button class="item" data-i="${it.i}">${esc(lab(it))}</button>`).join('')}
     <button class="key" id="cDrop">${esc(T('expedition.follow.hands_full.drop_label') || '▾')}</button></div>`);
  el.querySelectorAll('.item').forEach(b => b.onclick = () => { const i = +b.dataset.i; if (keep.has(i)) keep.delete(i); else keep.add(i); b.classList.toggle('off', !keep.has(i)); });
  el.querySelector('#cDrop').onclick = async () => { choiceOff(); narr(''); await act({ action: 'drop', keep: [...keep] }); react(); };
}
// 손을 놓는 자리: 나머지는 그 사람이 알아서 한다. 랜턴 점 하나가 어둠 속으로 멀어진다
async function handoff(turned) {
  if (mode === 'handoff' || mode === 'peek') return;
  mode = 'handoff'; choiceOff();
  if (SC && !SC.committed && SC.open) await act({ action: 'done' });
  if (!turned) narr(T('expedition.follow.handoff', vars()), 7000);
  setLeave(true);
  setTimeout(() => startPeek(true), turned ? 400 : 2500);
}

// ④ 들여다보기 — 시간으로 보간한 자리를 걷는다. 조작 없음. 알림도 없음
let peekT0 = 0;
async function startPeek(fromFollow) {
  mode = 'peek'; setLeave(true); $('#fade').classList.add('off');
  peekT0 = performance.now(); pollSoon = !!fromFollow;
  if (!fromFollow && lead) { const p = pathAt(progressNow()); lead.x = p.x; lead.z = p.z; people.forEach(q => { if (q.follow) { q.x = p.x - 0.9; q.z = p.z + 0.8; } }); }
  pollLoop();
}
function progressNow() {
  const s = (SC && SC.started) || (EXP && EXP.started) || 0, r = (SC && SC.returns_at) || (EXP && EXP.returns_at) || 1;
  const serverNow = ((SC && SC.now) || Date.now() / 1000) + (performance.now() - peekT0) / 1000;
  return Math.max(0, Math.min(1, (serverNow - s) / Math.max(1, r - s)));
}
function stepPeek() {
  if (mode !== 'peek' || !lead) return;
  const p = pathAt(progressNow());
  if (Math.hypot(p.x - lead.x, p.z - lead.z) > 0.25 && !lead.path.length) { lead.path = [p]; people.forEach(q => { if (q.follow) q.path = [{ x: p.x - 0.9, z: p.z + 0.8 }]; }); }
}
let pollSoon = false;
async function pollLoop() {
  clearTimeout(pollLoop._t);
  const soon = pollSoon; pollSoon = false;
  pollLoop._t = setTimeout(async () => {
    try {
      const j = await api('/api/expedition?uid=' + encodeURIComponent(uid));
      if (j.expedition_return) return startReturn(j.expedition_return, true);
      if (j.expedition) { EXP = j.expedition; paintClock(EXP.returns_at); if (SC) { SC.returns_at = EXP.returns_at; SC.now = EXP.now; peekT0 = performance.now(); } }
    } catch (e) { log('poll ' + e.message); }
    pollLoop();
  }, (soon ? 1.5 : mode === 'turning' || mode === 'peek' && progressNow() > 0.97 ? 8 : CFG.pollSec) * 1000);
}

// ⑤ 귀환 — 문으로 걸어 들어오는 장면 → (발견이면 그 자리부터) → 관리실 방송 카드
async function startReturn(ret, live) {
  mode = 'return'; choiceOff(); narr(''); pickSalt = ret.id || pickSalt;
  const mem = recall(ret.id);
  if (!GRID) {
    const ms = (mem && mem.members) || (ret.member_names || []).map((n, i) => ({ id: (ret.members || [])[i], name: n, role: 'scout' }));
    // 이름·역할은 거점 데이터에서 다시 찾는다(결과에는 id 만 온다)
    try { const ark = await (await fetch('/api/ark?uid=' + encodeURIComponent(uid))).json(); (ark.residents_list || []).forEach(r => { const m = ms.find(x => x.id === r.id); if (m) { m.name = r.name; m.role = r.role; } }); } catch { }
    SC = { terrain_seed: (mem && mem.terrain_seed) || uid + '|' + ((ret.dest && ret.dest.kind) || 'door'), waypoints: mem && mem.waypoints, members: ms, discovers: mem && mem.discovers, head: {}, carry: { slots: 0, items: [] }, air_band: 0, lantern_radius_m: (mem && mem.lantern) || 8 };
    await setupScene(SC);
  }
  setLeave(false); paintClock(null); $('#hud').style.visibility = 'hidden';
  const W = waypoints, far = W.length > 2 ? W[Math.max(1, W.length - 3)] : { x: 14, z: 2 };
  if (lead) { lead.x = far.x; lead.z = far.z; lead.carry = (ret.haul && (ret.haul.boxes || []).length) > 0; people.forEach(q => { if (q.follow) { q.x = far.x + 0.9; q.z = far.z - 0.8; } }); }
  $('#fade').classList.add('off');
  if (ret.discovered) await discoverBeat(ret);
  if (lead) {
    const back = W.slice(Math.max(1, W.length - 2)).concat([{ x: 0.6, z: 0.3 }]);
    lead.speed = 1.3; people.forEach(q => { if (q.follow) q.speed = 1.3; });   // 귀환 걸음은 조금 빠르게 — 문에 닿는 장면까지 몇 초 안에
    lead.path = back; people.forEach(q => { if (q.follow) q.path = back.map(p => ({ x: p.x - 0.9, z: p.z + 0.8 })); });
    await new Promise(res => { lead.onArrive = res; setTimeout(res, 14000); });
    lead.pose = 'return_tired';                           // 다친 게 아니라 지친 것(캐릭터 S15)
  }
  showReturnCard(ret);
}
async function discoverBeat(ret) {
  const d = ret.discovered, spot = SPOTS.find(s => s.id === d.spot_id) || {};
  const pos = (SC.discovers && SC.discovers.pos) || { x: 30, z: -6 };
  if (lead) { lead.x = pos.x - 2; lead.z = pos.z + 1; }
  if (assetById('beacon_spot')) beaconObj = await single('beacon_spot', pos.x, pos.z, 0, { lamp: 26, lampDist: 14 });
  for (let i = 0; i < 10; i++) { const a = i / 10 * 6.283; fogOfWar.reveal(pos.x + Math.cos(a) * 6, pos.z + Math.sin(a) * 6, 9); }
  fogOfWar.reveal(pos.x, pos.z, 14);
  const v = vars();
  narr(T('spot.discovery_lead', v), 3000);
  tweenCam(toWorldV(pos.x, pos.z), frustum * 0.8, 2.6);
  await new Promise(r => setTimeout(r, 2700));
  $('#discT').textContent = d.name || spot.name || '';
  $('#discP').textContent = d.discovery_text || spot.discovery_text || '';
  $('#discA').textContent = T('spot.discovery_after', v);
  $('#disc').classList.add('show');
  await new Promise(res => { $('#discOk').onclick = res; });
  $('#disc').classList.remove('show');
  tweenCam(toWorldV(0, 0), defaultFrustum(), 1.4);
}
function showReturnCard(ret) {
  const v = vars(), d = ret.danger, lines = [];
  // 관리실 방송(집 안) — 상황 하나를 고른다
  const early = d && (d.choice === 'turn_back' || (d.ok === false && (d.kind === 'air' || d.kind === 'beast')));
  const late = d && d.ok === false && d.kind === 'lost';
  const sit = ret.recalled ? 'recalled' : ret.injured ? 'injured' : early ? 'early' : late ? 'late' : 'normal';
  lines.push(['pa', T('expedition.return.' + sit, Object.assign({}, v, ret.injured ? { name: ret.injured } : {}))]);
  if (ret.discovered) lines.push(['pa', T('expedition.return.found_spot', Object.assign({}, v, { spot: ret.discovered.name || (SPOTS.find(s => s.id === ret.discovered.spot_id) || {}).name || '' }))]);
  else if (ret.dest && ret.dest.kind === 'clue') lines.push(['pa', T('expedition.return.spot_not_found', v)]);
  if (ret.clue) lines.push(['pa', T('spot.clue_from_expedition', Object.assign({}, v, { spot: ret.clue.name || '' }))]);
  if (ret.newcomer) lines.push(['pa', T('expedition.return.rescued', v)]);
  if (ret.rescued_but_no_room) lines.push(['pa', T('guest.rescued_no_room', v)]);
  // 바깥에서 일어난 일은 서술체(바깥 문장) 한 줄로
  if (d && d.choice !== 'turn_back' && d.ok != null) lines.push(['out', T(`expedition.danger.kinds.${d.kind}.${d.ok ? 'pass' : 'fail'}`)]);
  // ret.line(일지 한 줄)은 일지 화면 몫이다 — 카드에서는 같은 내용을 칩으로 보이므로 되풀이하지 않는다
  const h = ret.haul || {}, nMat = Object.values(h.materials || {}).reduce((a, b) => a + b, 0), boxes = h.boxes || [], nRel = (h.relics || []).length;
  const lb = ret.left_behind || {}, nLeft = Object.values(lb.materials || {}).reduce((a, b) => a + b, 0) + (lb.boxes || 0) + (lb.relics || 0);
  const chips = [];
  if (nMat) chips.push(`<span class="chip"><i style="background:#c9a35a"></i>${esc(T('expedition.summary.materials', { n: nMat }))}</span>`);
  if (boxes.length) chips.push(`<span class="chip"><i style="background:#8a6a3c"></i>${esc(T('expedition.summary.boxes', { n: boxes.length }))}</span>`);
  boxes.forEach(b => { const nm = boxName(b.cat); if (nm) chips.push(`<span class="chip"><i style="background:#3a2f16"></i>「${esc(nm)}」</span>`); });
  if (nRel) chips.push(`<span class="chip"><i style="background:#9fd8d8"></i>${esc(T('expedition.summary.shards', { n: nRel }))}</span>`);
  if (nLeft) chips.push(`<span class="chip"><i style="background:#333"></i>${esc(T('expedition.summary.left_behind', { n: nLeft }))}</span>`);
  if (boxes.length) {
    const b = boxes[0], nm = boxName(b.cat);
    // 빈 원(튜토리얼)은 '같은 갈래'가 아니라 아무 성문이나 맞는다 → 선반 안내 대신 상자 설명
    if (boxCat(b.cat) === 'blank') lines.push(['out', T('sealed_box.patterns.blank.desc') || T('sealed_box.blank.desc')]);
    else lines.push(['pa', T('sealed_box.on_shelf', { pattern: nm })]);
  }
  const card = $('#retCard');
  card.innerHTML = lines.filter(l => l[1]).map(l => `<p class="pa ${l[0] === 'out' ? 'out' : ''}">${esc(l[1])}</p>`).join('')
    + `<h3>${esc(T('expedition.summary.title'))}</h3>`
    + (chips.length ? `<div class="chips">${chips.join('')}</div>` : `<p class="pa out">${esc(T('expedition.summary.empty'))}</p>`)
    + `<div class="foot"><button class="key icon" id="cHome" aria-label="home">⌂</button></div>`;
  $('#ret').classList.add('show');
  card.querySelectorAll('.pa').forEach((p, i) => setTimeout(() => p.classList.add('on'), 300 + i * 900));
  card.querySelector('#cHome').onclick = async () => {
    try { await api('/api/expedition/seen', { uid }); } catch (e) { log('seen ' + e.message); }
    $('#fade').classList.remove('off'); setTimeout(goBase, 700);
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// 10. 입력 — 탭(걷기·줍기·갈림길 표지), 끌어서 둘러보기, 휠/핀치 줌
// ═══════════════════════════════════════════════════════════════════════════
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
function groundAt(cx, cy) {
  ndc.set((cx / innerWidth) * 2 - 1, -(cy / innerHeight) * 2 + 1); ray.setFromCamera(ndc, camera);
  const p = new THREE.Vector3(); if (!ray.ray.intersectPlane(floorPlane, p)) return null;
  return land.worldToLocal(p);
}
function screenOf(x, z, y = 0) { const v = toWorldV(x, z, y).project(camera); return { x: (v.x + 1) / 2 * innerWidth, y: (-v.y + 1) / 2 * innerHeight }; }
let camFree = 0;                                          // 끌어서 둘러보면 잠깐 따라가기를 멈춘다
const ptrs = new Map(); let drag = null, pinch = 0;
canvas.addEventListener('pointerdown', e => {
  try { canvas.setPointerCapture(e.pointerId); } catch { }
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (ptrs.size === 1) drag = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t: performance.now(), moved: 0 };
  if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch = Math.hypot(a.x - b.x, a.y - b.y); drag = null; }
});
canvas.addEventListener('pointermove', e => {
  if (!ptrs.has(e.pointerId)) return;
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (ptrs.size === 2 && pinch) { const [a, b] = [...ptrs.values()]; const d = Math.hypot(a.x - b.x, a.y - b.y); if (d > 4) { zoom(pinch / d); pinch = d; } return; }
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY; drag.moved += Math.abs(dx) + Math.abs(dy);
  if (drag.moved > 10) {
    const k = frustum * 2 / innerHeight;
    camTarget.addScaledVector(new THREE.Vector3(Math.cos(camAz), 0, Math.sin(camAz)), -dx * k).addScaledVector(new THREE.Vector3(Math.sin(camAz), 0, -Math.cos(camAz)), dy * k / Math.sin(camEl));
    camFree = performance.now() + 4000; placeCamera();
  }
});
function endPtr(e) {
  if (drag && ptrs.size === 1 && drag.moved < 10 && performance.now() - drag.t < 700) tap(drag.sx, drag.sy);
  ptrs.delete(e.pointerId); if (ptrs.size < 2) pinch = 0; if (!ptrs.size) drag = null;
}
canvas.addEventListener('pointerup', endPtr); canvas.addEventListener('pointercancel', endPtr);
canvas.addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 0.87); }, { passive: false });
function zoom(f) { const d = defaultFrustum(); frustum = THREE.MathUtils.clamp(frustum * f, d * 0.5, d * 2.2); placeCamera(); }
function tap(cx, cy) {
  if (mode !== 'follow' || busy || !lead) return;
  // 반짝이 먼저(손가락 44px 안이면 그것을 누른 것 — D8)
  let best = null, bd = 44;
  for (const g of glints) { if (g.state !== 'sparkle') continue; const s = screenOf(g.x, g.z, 0.5); const d = Math.hypot(s.x - cx, s.y - cy); if (d < bd) { bd = d; best = g; } }
  if (best) return pickGlint(best);
  if (SC.next === 'fork' && SC.head.fork && SC.head.fork.pos) {
    const f = SC.head.fork.pos, s = screenOf(f.x, f.z, 1);
    if (Math.hypot(s.x - cx, s.y - cy) < 60) return;          // 표지를 누르면 카드가 이미 떠 있다
  }
  const p = groundAt(cx, cy); if (!p) return;
  walkLead(p.x, p.z);
  if (SC.next === 'danger') dangerBeat();
}
addEventListener('resize', () => { renderer.setSize(innerWidth, innerHeight); frustum = defaultFrustum(); placeCamera(); });

// ═══════════════════════════════════════════════════════════════════════════
// 11. 카메라 · 루프
// ═══════════════════════════════════════════════════════════════════════════
let camAnim = null;
function tweenCam(to, f, dur) { camAnim = { t: 0, dur, from: camTarget.clone(), to: to.clone(), f0: frustum, f1: f }; }
const clock = new THREE.Clock();
let fpsN = 0, fpsT = 0, lastRev = { x: 1e9, z: 1e9 };
function tick() {
  const dt = Math.min(0.05, clock.getDelta()), t = clock.elapsedTime;
  stepPeek();
  stepPeople(dt, t); stepOcto(dt, t); stepGlints(t); stepFloaters(dt); stepSnow(dt, t);
  if (lead) {
    const lp = toWorldV(lead.x, lead.z, 2.0);
    lantern.position.copy(lp);
    lantern.intensity = 38 * (0.93 + 0.07 * Math.sin(t * 6.1) * Math.sin(t * 2.3));
    if (fogOfWar && Math.hypot(lead.x - lastRev.x, lead.z - lastRev.z) > 1.2) { fogOfWar.reveal(lead.x, lead.z, (SC && SC.lantern_radius_m) || 8); lastRev = { x: lead.x, z: lead.z }; }
    if (!camAnim && performance.now() > camFree) { const w = toWorldV(lead.x + 2, lead.z, 0); camTarget.lerp(w, Math.min(1, dt * 2.2)); placeCamera(); }
  }
  if (shadowObj && shadowObj.userData.v) {                // 그림자가 천천히 가로질러 지나간다
    shadowObj.position.x += shadowObj.userData.v.x * dt; shadowObj.position.z += shadowObj.userData.v.z * dt;
    if (lead && Math.hypot(shadowObj.position.x - lead.x, shadowObj.position.z - lead.z) > 26) { land.remove(shadowObj); shadowObj = null; }
  }
  if (camAnim) {
    camAnim.t = Math.min(1, camAnim.t + dt / camAnim.dur); const e = camAnim.t < .5 ? 2 * camAnim.t * camAnim.t : 1 - Math.pow(-2 * camAnim.t + 2, 2) / 2;
    camTarget.lerpVectors(camAnim.from, camAnim.to, e); frustum = THREE.MathUtils.lerp(camAnim.f0, camAnim.f1, e); placeCamera();
    if (camAnim.t >= 1) camAnim = null;
  }
  if (fogOfWar) fogOfWar.flush();
  fpsN++; if (t - fpsT > 0.5) { $('#fps').textContent = Math.round(fpsN / (t - fpsT)) + 'fps'; fpsT = t; fpsN = 0; }
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}

// 시작: 첫 프레임을 먼저 돌리고(검은 화면 대신 물빛), 데이터가 오면 세계를 놓는다
tick();
boot().catch(e => { log('boot ' + (e.stack || e.message)); mode = 'error'; setLeave(true); $('#fade').classList.add('off'); });

// ═══════════════════════════════════════════════════════════════════════════
// 12. 외부 훅(★ 검증 전용 — 배포 전 점검 목록)
// ═══════════════════════════════════════════════════════════════════════════
window.EXPED = {
  get mode() { return mode; }, get scene() { return SC; }, get exp() { return EXP; }, get lead() { return lead; },
  glints, people, screenOf, tap, renderer, camera, THREE, land,
  get calls() { return renderer.info.render.calls; },
};
