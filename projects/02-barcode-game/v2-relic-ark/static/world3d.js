// static/world3d.js — 잔해 방주(RELIC ARK) 본 화면 프로토타입 · 스프린트2 S2-A (개발/월드)
// 성경: SCREEN_VISION §1~6("가로 화면 한 장에 이어진 세계"), WORLD_PRESENTATION §1-1(문턱 컷·안개·정원사의 몸)
// 교본: D1(규칙 적게) D2(숫자는 화면으로) D6(같은 시드=같은 하루) D8(성능 예산) D9(벽 대신 위험) D10(3D 함정)
// 소유: static/*.js — server.py / app.js / index.html 은 건드리지 않는다(S2-B 동시 작업).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ═══════════════════════════════════════════════════════════════════════════
// 0. 상수 — 세계의 치수
// ═══════════════════════════════════════════════════════════════════════════
const SEED = 20260920;                 // D6: 같은 시드 = 같은 지형. 바꾸면 세계가 바뀐다.
const MAP_W = 400, MAP_D = 250;        // SCREEN_VISION §6 "약 400m × 250m 한 장"
const SEG_X = 200, SEG_Z = 125;        // 2m 격자 → 25,000 쿼드 (D8 예산 안)
const WATER_Y = -0.6;
const MALL_ROT = -Math.PI / 4;         // 몰 로컬 +X(문턱 바깥)가 화면 정확히 오른쪽을 향하도록
const S = 6.2;                         // 방 GLB 격자(6m) + 이음새
const MALL_X0 = -58, MALL_X1 = -0.5, MALL_HZ = 23;   // 몰 내부(로컬)
const DOOR_HZ = 5.0;                   // 문턱 통로 반폭
const SPOT = { x: 62, z: 30, r: 6 };   // 힐링 스팟(정찰병 반경 6m에 들어오면 발견) — 문턱에서 약 69m
const WALK = 4.2;                      // m/s (프로토타입 가독성용. 실제 밸런스는 스프린트3)
const PHASE_SEC = 20;                  // 자동 진행 시 한 단계 길이

// 배경 에이전트(S2-D)가 텍스처를 넣으면 이 경로만 채워지면 자동 교체된다. 없으면 단색 가중치 유지.
const TERRAIN_TEXTURE_SET = {
  grass: '/static/textures/grass.png',
  asphalt: '/static/textures/asphalt.png',
  moss: '/static/textures/moss.png',
  water: '/static/textures/water.png',
};
// 배경 에이전트(S2-D) 씬 GLB 경로 규약. 오면 자동으로 원시 대체물을 대신한다.
const SCENE_GLB = {
  facade: '/static/models/scenes/mall_facade.glb',
  spot_flooded_train: '/static/models/scenes/spot_flooded_train.glb',
};

// 시나리오 소유 데이터(data/spots.json)는 아직 정적 경로로 서빙되지 않는다(server.py 는 /static 만 mount).
// → 아래는 폴백이고, 서빙되면 그쪽이 이긴다(§요청사항 참고).
const SPOT_FALLBACK = {
  id: 'spot_flooded_train', name: '물에 잠긴 전철',
  discovery_text: '잊힌 역의 선로 끝, 물이 무릎까지 차오른 승강장에 열차 한 량이 멈춰 서 있다. 객차 안쪽 바닥은 통째로 맑은 청록 물이고, 손잡이마다 분홍 꽃이 매달려 흔들린다. 깨진 창으로 들어온 빛 기둥 아래를 금붕어들이 천천히 지나간다. 방주에서 온 사람들은 아무 말도 하지 않고, 들어갈 생각도 하지 않고, 문간에 서서 오래 본다.',
};

const PHASES = [
  { id: 'dawn', ko: '새벽', sky: 0x3d4c62, sun: 0xffb98a, sunI: 0.55, el: 0.24, hemiI: 0.30, lamp: 1.00 },
  { id: 'day', ko: '낮', sky: 0xA6BFC4, sun: 0xfff4e0, sunI: 1.55, el: 1.05, hemiI: 0.62, lamp: 0.40 },
  { id: 'dusk', ko: '저녁', sky: 0xB0654F, sun: 0xff9a5e, sunI: 0.72, el: 0.30, hemiI: 0.34, lamp: 0.90 },
  { id: 'night', ko: '밤', sky: 0x11151f, sun: 0x7f93c0, sunI: 0.12, el: 0.14, hemiI: 0.15, lamp: 1.30 },
];

// 없는 파일을 미리 찔러 보면 콘솔에 404가 남으므로, "아직 없는 것"만 옵트인으로 둔다.
// 텍스처(S2-D)·씬 GLB(S2-D)는 2026-09-20 도착 → 기본 로드. data/spots.json 은 아직 서빙 경로가 없어 `?assets` 로만 탐색.
const PROBE = location.search.includes('assets');

const $ = (s) => document.querySelector(s);
if (location.search.includes('debug')) document.body.classList.add('debug');
const log = (s) => { const l = $('#log'); l.textContent = (l.textContent + '\n' + s).split('\n').slice(-14).join('\n'); };

// ═══════════════════════════════════════════════════════════════════════════
// 1. 렌더러 · 씬 · 카메라
// ═══════════════════════════════════════════════════════════════════════════
const canvas = $('#c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
renderer.shadowMap.enabled = !location.search.includes('noshadow');
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x3d4c62);
scene.fog = new THREE.FogExp2(0x3d4c62, 0.0022);   // D10: 밀도 ≤0.006

let aspect = innerWidth / innerHeight, frustum = 26;
const camera = new THREE.OrthographicCamera(-frustum * aspect, frustum * aspect, frustum, -frustum, 0.1, 900);
const camTarget = new THREE.Vector3(-4, 0.8, -4);
let camAz = Math.PI / 4, camEl = Math.PI / 4;
function placeCamera() {
  const d = 260;
  camera.position.set(
    camTarget.x - Math.cos(camEl) * Math.sin(camAz) * d,
    camTarget.y + Math.sin(camEl) * d,
    camTarget.z + Math.cos(camEl) * Math.cos(camAz) * d);
  camera.lookAt(camTarget);
  camera.left = -frustum * aspect; camera.right = frustum * aspect;
  camera.top = frustum; camera.bottom = -frustum;
  camera.updateProjectionMatrix();
}
placeCamera();

// ═══════════════════════════════════════════════════════════════════════════
// 2. 조명 (D10: lanterns 배열은 setPhase 보다 먼저 선언)
// ═══════════════════════════════════════════════════════════════════════════
const lanterns = [];
const hemi = new THREE.HemisphereLight(0x9fb9c9, 0x36401F, 0.3); scene.add(hemi);   // 아래는 풀에서 올라오는 초록 반사
const sun = new THREE.DirectionalLight(0xfff2dc, 1.0);
sun.castShadow = renderer.shadowMap.enabled;
sun.shadow.mapSize.set(2048, 2048);                       // D10: 2048 하나
sun.shadow.camera.left = -80; sun.shadow.camera.right = 80;
sun.shadow.camera.top = 80; sun.shadow.camera.bottom = -80;
sun.shadow.camera.near = 1; sun.shadow.camera.far = 260; sun.shadow.bias = -0.0008;
const sunTarget = new THREE.Object3D(); sunTarget.position.set(-16, 0, -16); scene.add(sunTarget);
sun.target = sunTarget; scene.add(sun);
const SUN_HORIZ = new THREE.Vector3(0.78, 0, 0.62).normalize();   // 항상 문턱 바깥쪽에서 — 천장이 안쪽에 그늘을 만든다

// ═══════════════════════════════════════════════════════════════════════════
// 3. 절차적 지형 (결정적 value noise — D6)
// ═══════════════════════════════════════════════════════════════════════════
function hash2(ix, iz, s) {
  let h = Math.imul(ix | 0, 374761393) ^ Math.imul(iz | 0, 668265263) ^ Math.imul(s | 0, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}
function vnoise(x, z, s) {
  const ix = Math.floor(x), iz = Math.floor(z), fx = x - ix, fz = z - iz;
  const u = fx * fx * (3 - 2 * fx), v = fz * fz * (3 - 2 * fz);
  const a = hash2(ix, iz, s), b = hash2(ix + 1, iz, s), c = hash2(ix, iz + 1, s), d = hash2(ix + 1, iz + 1, s);
  return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
}
function fbm(x, z, s) {
  let a = 0, amp = 1, f = 1, n = 0;
  for (let i = 0; i < 4; i++) { a += amp * vnoise(x * f, z * f, s + i * 977); n += amp; amp *= 0.5; f *= 2; }
  return a / n;
}
const smooth = (e0, e1, x) => { const t = THREE.MathUtils.clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); };
function rectSDF(px, pz, hx, hz) {
  const dx = Math.abs(px) - hx, dz = Math.abs(pz) - hz;
  return Math.hypot(Math.max(dx, 0), Math.max(dz, 0)) + Math.min(Math.max(dx, dz), 0);
}
// 몰 로컬 ↔ 월드 (몰 블록만 45° 회전 — 문턱이 화면에서 수직선이 되도록)
const CR = Math.cos(MALL_ROT), SR = Math.sin(MALL_ROT);
const toWorld = (lx, lz) => ({ x: lx * CR + lz * SR, z: -lx * SR + lz * CR });
const toLocal = (x, z) => ({ x: x * CR - z * SR, z: x * SR + z * CR });

// 강: 월드 +X 쪽 경계. 벽이 아니라 위험이 경계다(D9).
function riverDepth(x, z) {
  const cx = 128 + 26 * Math.sin(z / 62);
  const d = Math.abs(x - cx);
  return d < 16 ? Math.pow(1 - d / 16, 1.4) * 6.2 : 0;
}
function heightAt(x, z) {
  let h = fbm(x / 78 + 11, z / 78 + 7, SEED) * 5.2 + 0.6;
  h += fbm(x / 21, z / 21, SEED + 313) * 1.1 - 0.5;
  h -= riverDepth(x, z);
  // 몰 블록 + 앞마당: 평탄화(로컬 좌표)
  const L = toLocal(x, z);
  const pad = 1 - smooth(0, 16, rectSDF(L.x + 26, L.z, 34, 26));
  h = h * (1 - pad) + 0.0 * pad;
  // 힐링 스팟: 얕은 분지 + 물
  const ds = Math.hypot(x - SPOT.x, z - SPOT.z);
  const rim = 1 - smooth(16, 30, ds);
  h = h * (1 - rim) + 0.25 * rim;
  const basin = 1 - smooth(6, 15, ds);
  h = h * (1 - basin) + (-1.5) * basin;
  return h;
}

const terrainGeo = new THREE.PlaneGeometry(MAP_W, MAP_D, SEG_X, SEG_Z);
terrainGeo.rotateX(-Math.PI / 2);
{
  const p = terrainGeo.attributes.position, n = p.count;
  const colors = new Float32Array(n * 3);
  const splat = new Float32Array(n * 4);      // 풀 / 아스팔트 / 이끼 / 물 가중치 (텍스처 블렌딩용)
  const C_GRASS = new THREE.Color(0x62863F), C_ASPH = new THREE.Color(0x4B4842),
    C_MOSS = new THREE.Color(0x7FA04C), C_WATER = new THREE.Color(0x2C6A69);
  const c = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const x = p.getX(i), z = p.getZ(i), y = heightAt(x, z);
    p.setY(i, y);
    // 스플랫 가중치: 풀 / 아스팔트 / 이끼 / 물
    const L = toLocal(x, z);
    const wAsph = THREE.MathUtils.clamp(1 - smooth(-2, 22, rectSDF(L.x + 26, L.z, 34, 26)), 0, 1)
      * (0.55 + 0.45 * fbm(x / 9, z / 9, SEED + 71));
    const wWater = 1 - smooth(WATER_Y - 0.15, WATER_Y + 0.45, y);   // 실제로 잠긴 곳에만
    // 이끼 텍스처(#2D4323)가 꽤 어두워서 비중을 낮춘다 — 초록(풀)이 화면의 절반 이상이어야 한다(bg_S2 §7-6)
    const wMoss = (1 - wWater) * smooth(0.52, 0.86, fbm(x / 26, z / 26, SEED + 517)) * 0.7 * (1 - wAsph * 0.6);
    const wGrass = Math.max(0, 1 - wAsph - wWater - wMoss);
    const tot = wAsph + wWater + wMoss + wGrass || 1;
    c.setRGB(
      (C_ASPH.r * wAsph + C_WATER.r * wWater + C_MOSS.r * wMoss + C_GRASS.r * wGrass) / tot,
      (C_ASPH.g * wAsph + C_WATER.g * wWater + C_MOSS.g * wMoss + C_GRASS.g * wGrass) / tot,
      (C_ASPH.b * wAsph + C_WATER.b * wWater + C_MOSS.b * wMoss + C_GRASS.b * wGrass) / tot);
    colors[i * 3] = c.r; colors[i * 3 + 1] = c.g; colors[i * 3 + 2] = c.b;
    splat[i * 4] = wGrass / tot; splat[i * 4 + 1] = wAsph / tot;
    splat[i * 4 + 2] = wMoss / tot; splat[i * 4 + 3] = wWater / tot;
  }
  terrainGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  terrainGeo.setAttribute('splat', new THREE.BufferAttribute(splat, 4));
  terrainGeo.computeVertexNormals();
}
const terrainMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, metalness: 0 });
const terrain = new THREE.Mesh(terrainGeo, terrainMat);
terrain.receiveShadow = true; scene.add(terrain);

// 텍스처: 4장을 정점 가중치(splat)로 블렌딩한다. 로드 실패하면 단색 가중치(vertexColors) 그대로.
// bg_S2 §7-1 규약: 512px 타일, RepeatWrapping, sRGB, 1타일 = 4m.
function applyTerrainTextures(paths = TERRAIN_TEXTURE_SET) {
  const tl = new THREE.TextureLoader();
  const load = (url) => new Promise((res, rej) => tl.load(url, (t) => {
    t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4; res(t);
  }, undefined, rej));
  return Promise.all([load(paths.grass), load(paths.asphalt), load(paths.moss), load(paths.water)])
    .then(([g, a, m, w]) => {
      terrainMat.vertexColors = false;                 // 텍스처가 색을 대신한다
      terrainMat.onBeforeCompile = (sh) => {
        sh.uniforms.tG = { value: g }; sh.uniforms.tA = { value: a };
        sh.uniforms.tM = { value: m }; sh.uniforms.tW = { value: w };
        sh.uniforms.tileM = { value: 1 / 6 };          // 1타일 6m (4m 는 아이소 축소 화면에서 점처럼 보인다)
        // 타일별 밝기 보정: moss.png(#2D4323)가 매우 어두워 그대로 섞으면 초록이 죽는다
        sh.uniforms.gain4 = { value: new THREE.Vector4(1.8, 1.15, 3.0, 1.15) };
        sh.vertexShader = sh.vertexShader
          .replace('#include <common>', '#include <common>\nattribute vec4 splat;\nvarying vec4 vSplat;\nvarying vec2 vWxz;')
          .replace('#include <begin_vertex>', '#include <begin_vertex>\nvSplat = splat;\nvWxz = (modelMatrix * vec4(position,1.0)).xz;');
        sh.fragmentShader = sh.fragmentShader
          .replace('#include <common>', '#include <common>\nuniform sampler2D tG,tA,tM,tW;\nuniform float tileM;\nuniform vec4 gain4;\nvarying vec4 vSplat;\nvarying vec2 vWxz;')
          .replace('#include <map_fragment>', [
            'vec2 uvT = vWxz * tileM;',
            'vec4 sw = vSplat / max(1e-4, vSplat.x + vSplat.y + vSplat.z + vSplat.w);',
            'vec3 tx = pow(texture2D(tG,uvT).rgb, vec3(2.2)) * (sw.x * gain4.x)',
            '        + pow(texture2D(tA,uvT).rgb, vec3(2.2)) * (sw.y * gain4.y)',
            '        + pow(texture2D(tM,uvT).rgb, vec3(2.2)) * (sw.z * gain4.z)',
            '        + pow(texture2D(tW,uvT).rgb, vec3(2.2)) * (sw.w * gain4.w);',   // 수동 샘플링이라 sRGB→선형을 직접
            'diffuseColor.rgb *= tx;',
          ].join('\n'));
      };
      terrainMat.needsUpdate = true;
      log('terrain 스플랫 텍스처 4장 적용');
    })
    .catch(() => log('terrain texture 없음 → 단색 가중치 유지'));
}
applyTerrainTextures();

// 물 한 장(강 + 스팟 분지를 동시에 덮는다)
const water = new THREE.Mesh(
  new THREE.PlaneGeometry(MAP_W, MAP_D),
  new THREE.MeshStandardMaterial({ color: 0x2E7E7A, transparent: true, opacity: 0.78, roughness: 0.12, metalness: 0.0 }));
water.rotation.x = -Math.PI / 2; water.position.y = WATER_Y; water.renderOrder = 1;
water.material.depthWrite = false;      // 미탐험 안개가 물 위에 덮이도록
scene.add(water);

// ── 바깥의 밀도: 나무·덤불·폐허 덩어리 (ART_REFERENCES: 초록·소품 밀도. "빈 바닥" 금지 — 공통 교본 §5)
//    InstancedMesh 4개 = 드로우콜 4개. 배치는 SEED 로 결정적(D6). 안개가 걷힌 곳에서만 드러난다.
let revealProps = null;
{
  let s = SEED ^ 0x5bd1;
  const rnd = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967295; };
  const mk = (geo, mat, n) => { const m = new THREE.InstancedMesh(geo, mat, n); m.castShadow = true; m.count = 0; scene.add(m); return m; };
  const trunk = mk(new THREE.CylinderGeometry(0.22, 0.34, 3.4, 6), new THREE.MeshStandardMaterial({ color: 0x4A3B2A, roughness: 1 }), 200);
  const canopy = mk(new THREE.IcosahedronGeometry(2.3, 0), new THREE.MeshStandardMaterial({ color: 0x527F36, roughness: 1, flatShading: true }), 200);
  const bush = mk(new THREE.IcosahedronGeometry(1.0, 0), new THREE.MeshStandardMaterial({ color: 0x6B8F3C, roughness: 1, flatShading: true }), 420);
  const ruin = mk(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0x6A6659, roughness: 1 }), 160);
  const Q = new THREE.Quaternion(), E = new THREE.Euler(), P = new THREE.Vector3(), SC = new THREE.Vector3();
  const ZERO = new THREE.Matrix4().makeScale(0, 0, 0);
  const hidden = [];                      // 안개 아래에 아직 숨어 있는 것들
  const put = (im, x, y, z, sx, sy, sz, ry, rx) => {
    E.set(rx || 0, ry, 0); Q.setFromEuler(E); P.set(x, y, z); SC.set(sx, sy, sz);
    const m = new THREE.Matrix4().compose(P, Q, SC), idx = im.count++;
    im.setMatrixAt(idx, ZERO); hidden.push({ im, idx, m, x, z });
  };
  for (let i = 0; i < 4000 && (trunk.count < 200 || bush.count < 420 || ruin.count < 160); i++) {
    const x = (rnd() - 0.5) * (MAP_W - 12), z = (rnd() - 0.5) * (MAP_D - 12);
    const L = toLocal(x, z);
    if (rectSDF(L.x + 26, L.z, 40, 32) < 0) continue;                  // 몰 블록·앞마당은 비운다
    if (Math.hypot(x - SPOT.x, z - SPOT.z) < 17) continue;             // 스팟 주변은 열어 둔다
    const y = heightAt(x, z); if (y < WATER_Y + 0.5) continue;
    const k = rnd();
    if (k < 0.30 && trunk.count < 200) {
      const h = 0.8 + rnd() * 0.6, ry = rnd() * 6.2832;
      put(trunk, x, y + 1.7 * h, z, 1, h, 1, ry);
      put(canopy, x, y + 3.4 * h + 0.6, z, 1 + rnd() * .5, 0.85 + rnd() * .4, 1 + rnd() * .5, ry);
    } else if (k < 0.78 && bush.count < 420) {
      put(bush, x, y + 0.5 + rnd() * .3, z, 0.7 + rnd(), 0.5 + rnd() * .5, 0.7 + rnd(), rnd() * 6.2832);
    } else if (ruin.count < 160) {
      put(ruin, x, y + 0.4 + rnd() * .6, z, 1 + rnd() * 3.4, 0.6 + rnd() * 2.2, 1 + rnd() * 2.6, rnd() * 6.2832, (rnd() - .5) * 0.25);
    }
  }
  const all = [trunk, canopy, bush, ruin];
  all.forEach(m => { m.instanceMatrix.needsUpdate = true; m.frustumCulled = false; });
  revealProps = (x, z, r) => {
    let hit = false;
    for (let i = hidden.length - 1; i >= 0; i--) {
      const h = hidden[i];
      if (Math.hypot(h.x - x, h.z - z) > r) continue;
      h.im.setMatrixAt(h.idx, h.m); h.im.instanceMatrix.needsUpdate = true;
      hidden.splice(i, 1); hit = true;
    }
    return hit;
  };
  log(`props: tree ${trunk.count} · bush ${bush.count} · ruin ${ruin.count}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. 안개(미탐험) — 지형을 따라가는 반투명 종이 레이어, 정찰이 지운다
// ═══════════════════════════════════════════════════════════════════════════
const FW = 1024, FH = 640;              // 2.56 px/m
const fogCanvas = document.createElement('canvas'); fogCanvas.width = FW; fogCanvas.height = FH;
const fctx = fogCanvas.getContext('2d');
(function paintPaper() {
  fctx.fillStyle = '#A99C80'; fctx.fillRect(0, 0, FW, FH);
  // 종이 섬유: 결정적 난수로 얼룩과 실선
  let s = SEED;
  const rnd = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967295; };
  for (let i = 0; i < 2600; i++) {
    const x = rnd() * FW, y = rnd() * FH, r = 2 + rnd() * 26;
    fctx.fillStyle = `rgba(${140 + rnd() * 80 | 0},${130 + rnd() * 70 | 0},${105 + rnd() * 60 | 0},${0.035 + rnd() * 0.05})`;
    fctx.beginPath(); fctx.arc(x, y, r, 0, 6.2832); fctx.fill();
  }
  for (let i = 0; i < 900; i++) {
    const x = rnd() * FW, y = rnd() * FH, a = rnd() * 6.2832, l = 6 + rnd() * 34;
    fctx.strokeStyle = `rgba(90,82,66,${0.03 + rnd() * 0.05})`; fctx.lineWidth = 0.6 + rnd();
    fctx.beginPath(); fctx.moveTo(x, y); fctx.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); fctx.stroke();
  }
})();
const fogTex = new THREE.CanvasTexture(fogCanvas);
fogTex.flipY = false; fogTex.colorSpace = THREE.SRGBColorSpace;
const fogGeo = terrainGeo.clone();
{
  const p = fogGeo.attributes.position, uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) {
    p.setY(i, p.getY(i) + 0.3);
    uv[i * 2] = (p.getX(i) + MAP_W / 2) / MAP_W;
    uv[i * 2 + 1] = (p.getZ(i) + MAP_D / 2) / MAP_D;
  }
  fogGeo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  fogGeo.deleteAttribute('color'); fogGeo.deleteAttribute('splat');
}
const fogMesh = new THREE.Mesh(fogGeo, new THREE.MeshBasicMaterial({
  map: fogTex, transparent: true, opacity: 0.86, depthWrite: false, fog: false,
}));
fogMesh.renderOrder = 3; scene.add(fogMesh);

let fogDirty = false;
function reveal(x, z, r) {
  const cx = (x + MAP_W / 2) / MAP_W * FW, cy = (z + MAP_D / 2) / MAP_D * FH, cr = r / MAP_W * FW;
  fctx.globalCompositeOperation = 'destination-out';
  const g = fctx.createRadialGradient(cx, cy, cr * 0.42, cx, cy, cr);
  g.addColorStop(0, 'rgba(0,0,0,1)'); g.addColorStop(1, 'rgba(0,0,0,0)');
  fctx.fillStyle = g; fctx.beginPath(); fctx.arc(cx, cy, cr, 0, 6.2832); fctx.fill();
  fctx.globalCompositeOperation = 'source-over';
  fogDirty = true;
  if (revealProps) revealProps(x, z, r * 0.95);     // 안개가 걷히면 나무와 잔해가 드러난다
}
// 시작: 방주 안과 문턱 앞 주차장은 이미 아는 곳(그 너머는 무지)
for (let i = 0; i <= 10; i++) { const w = toWorld(-56 + i * 6, 0); reveal(w.x, w.z, 28); }
for (let gx = 0; gx <= 2; gx++) for (let gz = -1; gz <= 1; gz++) {
  const w = toWorld(gx * 9, gz * 11); reveal(w.x, w.z, 15);     // 문턱 앞 주차장까지만. 그 너머는 무지다
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. 몰 블록 — 기존 방 GLB 재사용 + 어두운 천장(태양 차단) + 랜턴
// ═══════════════════════════════════════════════════════════════════════════
const mall = new THREE.Group(); mall.rotation.y = MALL_ROT; scene.add(mall);
const loader = new GLTFLoader();

const MALL_ROOMS = [
  ['hall', -2, 0], ['mall_camp', -3, -1], ['mall_food', -3, 1], ['mall_escalator', -4, 0],
  ['pantry', -5, -1], ['library', -5, 1], ['infirmary', -6, 0], ['well', -7, -1],
  ['mall_camp', -7, 1], ['rock', -8, 0], ['rock', -1, -3], ['rock', -4, 3],
  ['lot', 1, -1], ['lot', 1, 1],
];
const HALL_L = { x: -2 * S, z: 0 };     // 홀 허브(로컬)

async function loadRoom(id, gx, gz) {
  try {
    const g = await loader.loadAsync(`/static/models/rooms/${id}.glb`);
    const root = g.scene; root.position.set(gx * S, 0, gz * S);
    let own = 0;
    root.traverse(o => {
      if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; }
      if (o.isLight) { // D10: KHR 라이트 세기는 고정 클램프
        o.intensity = 45; o.decay = 2; o.distance = 16; o.castShadow = false;
        lanterns.push({ l: o, night: 45, base: 45, seed: Math.random() * 10 }); own++;
      }
    });
    if (own === 0 && id !== 'rock' && id !== 'lot') {
      const pl = new THREE.PointLight(0xF2A93B, 34, 17, 2);
      pl.position.set(gx * S, 2.6, gz * S); mall.add(pl);
      lanterns.push({ l: pl, night: 34, base: 34, seed: Math.random() * 10 });
    }
    mall.add(root);
  } catch (e) { log(`FAIL room ${id}: ${e.message || e}`); }
}
await Promise.all(MALL_ROOMS.map(([id, x, z]) => loadRoom(id, x, z)));
// D8: 포인트 라이트가 많으면 GTX 1050 에서 포워드 렌더가 무너진다 → 문턱에 가까운 12개만 남긴다
mall.updateMatrixWorld(true);
if (lanterns.length > 10) {
  lanterns.sort((a, b) => {
    const pa = new THREE.Vector3(); a.l.getWorldPosition(pa);
    const pb = new THREE.Vector3(); b.l.getWorldPosition(pb);
    return pa.length() - pb.length();
  });
  lanterns.splice(10).forEach(o => { o.l.intensity = 0; o.l.parent && o.l.parent.remove(o.l); });
}
log(`rooms ${MALL_ROOMS.length} · lanterns ${lanterns.length}`);

// 어두운 천장 = 태양 차단(그림자까지 드리운다) + 반투명 지붕
const ceil = new THREE.Mesh(
  new THREE.PlaneGeometry(59, 50),
  new THREE.MeshBasicMaterial({ color: 0x17120E, transparent: true, opacity: 0.34, side: THREE.DoubleSide, depthWrite: false, fog: false }));
ceil.rotation.x = -Math.PI / 2; ceil.position.set(-28.5, 5.4, 0);
ceil.castShadow = true; ceil.renderOrder = 4; mall.add(ceil);

// 문턱(파사드) — 지금은 원시 기둥·차양. S2-D 의 mall_facade.glb 가 오면 loadFacadeGLB() 가 통째로 대체한다.
const facade = new THREE.Group(); mall.add(facade);
(function buildFacadeFallback() {
  const matF = new THREE.MeshStandardMaterial({ color: 0x3A3630, roughness: .9 });
  for (let i = -4; i <= 4; i++) {
    if (Math.abs(i * 2.4) < DOOR_HZ) continue;
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.5, 5.4, 0.5), matF);
    m.position.set(0, 2.7, i * 2.4); m.castShadow = true; facade.add(m);
  }
  const lintel = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.8, 22), matF);
  lintel.position.set(0, 5.6, 0); lintel.castShadow = true; facade.add(lintel);
})();
// 파사드 규약(bg_S2 §7-2): 원점 = 입구 바닥 중심, **정면 = GLB 로컬 +Z**.
// 우리 몰의 바깥은 몰 로컬 +X 이므로 +Z → +X 로 보내는 회전 = rotation.y = +90°. (자동 추정 없이 한 줄로 고정)
const FACADE_YAW = Math.PI / 2;
function loadFacadeGLB(url = SCENE_GLB.facade) {
  return loader.loadAsync(url).then(g => {
    facade.clear();
    g.scene.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    g.scene.rotation.y = FACADE_YAW;
    facade.add(g.scene); log('facade GLB 적용 (yaw +90°)');
  }).catch(e => log(`facade GLB 없음 (${e.message || e})`));
}

// 입구 뒤판이 없는 GLB라 문턱 너머로 지형이 비친다(bg_S2 §7-2) → 파사드 뒤 5m 에 어두운 실내 판 + 랜턴 하나.
{
  const back = new THREE.Mesh(new THREE.PlaneGeometry(46, 7),
    new THREE.MeshStandardMaterial({ color: 0x0E0B08, roughness: 1, side: THREE.DoubleSide }));
  back.rotation.y = Math.PI / 2; back.position.set(-5.5, 3.2, 0); back.receiveShadow = true; mall.add(back);
  const doorLamp = new THREE.PointLight(0xF2A93B, 30, 15, 2);
  doorLamp.position.set(-4.5, 2.5, 0); mall.add(doorLamp);
  lanterns.push({ l: doorLamp, night: 30, base: 30, seed: 1.7 });   // 문턱 랜턴은 항상 살아 있다
}

// 몰 좌표 도우미
const inMall = (l) => l.x > MALL_X0 && l.x < MALL_X1 && Math.abs(l.z) < MALL_HZ;

// ═══════════════════════════════════════════════════════════════════════════
// 6. 힐링 스팟 — 청록 틴트 + 물. 정찰병이 반경에 들면 안개가 걷히고 카메라가 내려앉는다
// ═══════════════════════════════════════════════════════════════════════════
let spotData = SPOT_FALLBACK;
async function loadSpotsJson(urls = ['/static/data/spots.json', '/api/spots']) {
  for (const u of urls) {
    try {
      const r = await fetch(u); if (!r.ok) continue;
      const j = await r.json(); const arr = Array.isArray(j) ? j : (j.spots || []);
      const f = arr.find(s => s.id === 'spot_flooded_train');
      if (f) { spotData = f; log(`spots.json ← ${u}`); return f; }
    } catch (_) { /* 서빙 전이면 폴백 */ }
  }
  return null;
}

const spotGroup = new THREE.Group(); spotGroup.position.set(SPOT.x, 0, SPOT.z);
spotGroup.visible = false;              // 안개 밑에 있다. 가까이 가야 안개 위로 모습이 올라온다
scene.add(spotGroup);
const TEAL = new THREE.Color(0x66D6CC);
function tintTeal(obj) {
  const tint = (m) => { const c = m.clone(); if (c.color) c.color.multiply(TEAL); return c; };
  obj.traverse(o => {
    if (!o.isMesh || !o.material) return;
    o.castShadow = true; o.receiveShadow = true;
    o.material = Array.isArray(o.material) ? o.material.map(tint) : tint(o.material);
  });
}
const spotFallbackNode = new THREE.Group(); spotGroup.add(spotFallbackNode);
{ // 씬 GLB(S2-D)가 오기 전 대체물: hall.glb 청록 틴트
  const g = await loader.loadAsync('/static/models/rooms/hall.glb');
  const dead = []; g.scene.traverse(o => { if (o.isLight) dead.push(o); });
  dead.forEach(o => { o.intensity = 0; o.parent && o.parent.remove(o); });   // 스팟은 거주 요소 없음 = 랜턴 없음
  tintTeal(g.scene); g.scene.position.y = -0.9; g.scene.rotation.y = 0.5;
  spotFallbackNode.add(g.scene);
}
let spotThreshold = null;                  // 정찰병이 서는 문간(marker_threshold) 월드 좌표
function loadSpotGLB(url = SCENE_GLB.spot_flooded_train) {
  return loader.loadAsync(url).then(g => {
    spotFallbackNode.clear();
    const s = g.scene;
    // 원점 = 승강장 상면(y=0), 수면 = y+0.14 → 지형 수면(WATER_Y)과 맞춘다 (bg_S2 §7-3/§7-4)
    s.position.y = WATER_Y - 0.14;
    const lights = [];
    s.traverse(o => {
      if (o.isMesh) {
        o.castShadow = true; o.receiveShadow = true;
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        ms.forEach(m => {                       // 재질명 'Water' 에 우리 물 셰이딩을 입힌다
          if (!m || m.name !== 'Water') return;
          m.color.set(0x3FA79E); m.transparent = true; m.opacity = 0.74;
          m.roughness = 0.1; m.metalness = 0.0; m.depthWrite = true; m.needsUpdate = true;
        });
      }
      if (o.isLight) lights.push(o);
    });
    lights.forEach(l => { l.intensity = 45 * 0.3; l.decay = 2; l.distance = 22; l.castShadow = false; });
    spotFallbackNode.add(s);
    spotWater.visible = false;                  // GLB 수면과 겹치지 않게 대체 원판은 끈다
    spotGroup.updateMatrixWorld(true);
    const mt = s.getObjectByName('marker_threshold');
    if (mt) { spotThreshold = mt.getWorldPosition(new THREE.Vector3()); mt.visible = false; }
    const n = attachKoi(s, s.position.y);
    log(`spot 씬 GLB 적용 (조명 ${lights.length}×0.3 · koi ${n} · threshold ${!!mt})`);
  }).catch(e => log(`spot 씬 GLB 없음 (${e.message || e})`));
}
loadFacadeGLB(); loadSpotGLB();          // S2-D 씬 GLB 도착 — 원시 대체물을 대신한다
if (PROBE) loadSpotsJson();              // 서빙 경로가 생기면 기본으로 올린다(§요청 7)
// 스팟 물 평면 — **대체물(hall.glb)용**. 실제 씬 GLB 는 자기 수면(`keep_water_surface`)을 갖고 있어
// 겹치면 z-파이팅이 난다(bg_S2 §7-3) → GLB 가 붙으면 이 원판은 끈다.
const spotWater = new THREE.Mesh(new THREE.CircleGeometry(13, 40),
  new THREE.MeshStandardMaterial({ color: 0x4FBEB4, transparent: true, opacity: 0.6, roughness: 0.08 }));
spotWater.rotation.x = -Math.PI / 2; spotWater.position.y = WATER_Y + 0.12; spotWater.renderOrder = 2;
spotWater.material.depthWrite = false;
spotGroup.add(spotWater);

// 금붕어 — koi_1~5 마커에 붙인다(bg_S2 §7-4). 원시 도형(캡슐+꼬리), 수면 18cm 아래에서 천천히 돈다.
const koi = [];
function attachKoi(root, yOff) {
  const body = new THREE.CapsuleGeometry(0.11, 0.26, 4, 8);
  const tail = new THREE.ConeGeometry(0.1, 0.22, 6);
  const mat = new THREE.MeshStandardMaterial({ color: 0xE07A33, roughness: .6, emissive: 0x3A1400, emissiveIntensity: .4 });
  for (let i = 1; i <= 5; i++) {
    const m = root.getObjectByName(`koi_${i}`);
    if (!m) continue;
    const p = m.getWorldPosition(new THREE.Vector3());
    const g = new THREE.Group();
    const b = new THREE.Mesh(body, mat); b.rotation.z = Math.PI / 2; g.add(b);
    const t = new THREE.Mesh(tail, mat); t.rotation.z = -Math.PI / 2; t.position.x = -0.24; g.add(t);
    g.position.copy(p); spotGroup.worldToLocal(g.position);
    spotGroup.add(g);
    koi.push({ g, base: g.position.clone(), r: 0.5 + i * 0.22, w: 0.25 + i * 0.05, ph: i * 1.3 });
    m.visible = false;
  }
  return koi.length;
}

// ═══════════════════════════════════════════════════════════════════════════
// 7. 주민 3명 — GLB 재정규화 금지(발 z=0, 맨머리 1.6m, 정면 +Z)
// ═══════════════════════════════════════════════════════════════════════════
const actors = {};
// 각인 파츠: GLB 에 `imp_<id>` 노드가 들어 있고 glTF 에 가시성 필드가 없어 **기본이 보임** 상태다.
// → 로드 직후 전부 끄고, 주민 데이터의 imprints 에 있는 것만 켠다.
const IMPRINT_IDS = ['spore_mark', 'empty_stomach', 'warden', 'sun_memory', 'empty_seat', 'footprint', 'debt_paid', 'water_memory'];
function hideAllImprints(root) {
  let n = 0;
  root.traverse(o => { if (o.name && o.name.startsWith('imp_')) { o.visible = false; n++; } });
  return n;
}
function setImprints(root, ids) {
  hideAllImprints(root);
  (ids || []).forEach(id => {
    const node = root.getObjectByName(`imp_${id}`);
    if (node) node.traverse(o => { o.visible = true; });
  });
}

async function loadResident(key, file, ko, local) {
  try {
    const g = await loader.loadAsync(`/static/models/chars/${file}.glb`);
    const root = g.scene;
    root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
    const impN = hideAllImprints(root);
    const w = toWorld(local.x, local.z);
    root.position.set(w.x, heightAt(w.x, w.z), w.z);
    root.rotation.y = MALL_ROT + Math.PI / 2;
    scene.add(root);
    const mixer = new THREE.AnimationMixer(root), clips = {};
    g.animations.forEach(c => { clips[c.name.toLowerCase()] = mixer.clipAction(c); });
    const a = {
      key, ko, root, mixer, clips, cur: null, path: [], speed: WALK,
      play(n, once) {
        const c = clips[n] || clips.idle; if (!c || this.cur === c) return;
        if (this.cur) this.cur.fadeOut(0.22);
        c.reset().fadeIn(0.22); c.setLoop(once ? THREE.LoopOnce : THREE.LoopRepeat);
        c.clampWhenFinished = !!once; c.play(); this.cur = c;
      },
    };
    a.setImprints = (ids) => setImprints(root, ids);
    a.play('idle'); actors[key] = a;
    log(`${key}(${file}) clips: ${Object.keys(clips).join(',')} · imp 노드 ${impN}개 숨김`);
  } catch (e) { log(`FAIL char ${file}: ${e.message || e}`); }
}
await loadResident('scout', 'scout', '정찰병', { x: HALL_L.x + 4, z: 3 });
await loadResident('cook', 'cook', '요리사', { x: HALL_L.x - 4, z: -3.5 });
await loadResident('medic', 'medic', '의사', { x: HALL_L.x - 8, z: 4 });

// ── 개 한 마리: 사람 곁에 붙는다. 사람끼리는 떨어져 서고 짐승만 곁에 있다(TRUST_AND_COMPANIONS).
let dog = null;
await loader.loadAsync('/static/models/animals/dog.glb').then(g => {
  const root = g.scene;
  root.traverse(o => { if (o.isMesh) o.castShadow = true; });
  scene.add(root);
  const mixer = new THREE.AnimationMixer(root), clips = {};
  g.animations.forEach(c => { clips[c.name.toLowerCase()] = mixer.clipAction(c); });
  dog = {
    root, mixer, clips, cur: null,
    play(n) { const c = clips[n] || clips.idle; if (!c || this.cur === c) return; if (this.cur) this.cur.fadeOut(0.2); c.reset().fadeIn(0.2).play(); this.cur = c; },
  };
  dog.play('idle');
  log(`dog clips: ${Object.keys(clips).join(',')}`);
}).catch(e => log(`dog GLB 없음 (${e.message || e})`));

// ── 초식 공룡: 낮에 초원 멀리서 어슬렁거린다(위협이 아니라 풍경 = 하루 사이클의 낮 장면)
const dinos = [];
await Promise.all([[130, -55], [146, -44]].map(([dx, dz], i) =>
  loader.loadAsync('/static/models/dinos/triceratops.glb').then(g => {
    const root = g.scene;
    root.traverse(o => { if (o.isMesh) o.castShadow = true; });
    root.position.set(dx, heightAt(dx, dz), dz);
    scene.add(root);
    const mixer = new THREE.AnimationMixer(root), clips = {};
    g.animations.forEach(c => { clips[c.name.toLowerCase()] = mixer.clipAction(c); });
    (clips.walk || clips.idle) && (clips.walk || clips.idle).play();
    dinos.push({ root, mixer, home: new THREE.Vector2(dx, dz), ph: i * 2.7, r: 16 + i * 6 });
  }).catch(e => log(`dino GLB 없음 (${e.message || e})`))));
if (dinos.length) log(`triceratops ${dinos.length}마리 배치`);

// ── 길 찾기: 직선 + 몰 벽 근사 회피(D9 "실패 시 직진 폴백")
function segHitsMall(a, b) {
  for (let i = 1; i < 12; i++) {
    const t = i / 12;
    if (inMall({ x: a.x + (b.x - a.x) * t, z: a.z + (b.z - a.z) * t })) return true;
  }
  return false;
}
function planPath(from, to) {
  const a = toLocal(from.x, from.z), b = toLocal(to.x, to.z);
  const inA = inMall(a), inB = inMall(b), pts = [];
  if (inA !== inB) {                       // 문턱을 통과한다
    const doorZ = THREE.MathUtils.clamp((inA ? b.z : a.z) * 0.3, -DOOR_HZ + 1.5, DOOR_HZ - 1.5);
    const p1 = toWorld(inA ? -4 : 5, doorZ), p2 = toWorld(inA ? 5 : -4, doorZ);
    pts.push(p1, p2);
  } else if (!inA && segHitsMall(a, b)) {  // 바깥끼리인데 몰을 관통 → 옆으로 돈다
    const side = ((a.z + b.z) / 2) >= 0 ? 1 : -1;
    pts.push(toWorld(THREE.MathUtils.clamp((a.x + b.x) / 2, MALL_X0 - 4, 6), side * (MALL_HZ + 5)));
  }
  pts.push({ x: to.x, z: to.z });
  return pts;
}
function sendTo(key, x, z) {
  const list = key === 'all' ? Object.values(actors) : [actors[key]].filter(Boolean);
  list.forEach((a, i) => {
    const off = i * 1.8 - (list.length - 1) * 0.9;
    a.path = planPath({ x: a.root.position.x, z: a.root.position.z }, { x: x + off, z: z + off * 0.4 });
  });
  return list.length;
}

// ═══════════════════════════════════════════════════════════════════════════
// 8. 하루 사이클
// ═══════════════════════════════════════════════════════════════════════════
// 첫 화면은 '낮'에서 시작한다 — 문턱 컷이 "왼쪽 어두운 안 / 오른쪽 밝은 밖"을 한 컷에 보여야 하기 때문(WORLD_PRESENTATION §1-1, P3).
// 새벽 출발(SCREEN_VISION §5)은 사이클이 한 바퀴 돈 뒤에 온다.
let dayT = 1, day = 1, auto = false, lastPhase = 1;
let scoutInside = true, nightNow = false;
const cSky = new THREE.Color(), cSun = new THREE.Color(), cA = new THREE.Color(), cB = new THREE.Color();
function applyDay() {
  const i0 = Math.floor(dayT) % 4, i1 = (i0 + 1) % 4, f = dayT - Math.floor(dayT);
  const A = PHASES[i0], B = PHASES[i1];
  const lerp = THREE.MathUtils.lerp;
  cA.setHex(A.sky); cB.setHex(B.sky); cSky.copy(cA).lerp(cB, f);
  scene.background.copy(cSky); scene.fog.color.copy(cSky);
  cA.setHex(A.sun); cB.setHex(B.sun); cSun.copy(cA).lerp(cB, f);
  sun.color.copy(cSun);
  sun.intensity = lerp(A.sunI, B.sunI, f);
  hemi.intensity = lerp(A.hemiI, B.hemiI, f);
  const el = lerp(A.el, B.el, f);
  sun.position.set(
    sunTarget.position.x + SUN_HORIZ.x * Math.cos(el) * 120,
    sunTarget.position.y + Math.sin(el) * 120,
    sunTarget.position.z + SUN_HORIZ.z * Math.cos(el) * 120);
  const lamp = lerp(A.lamp, B.lamp, f);
  lanterns.forEach(o => { o.base = o.night * lamp; });
  ceil.material.opacity = lerp(0.34, 0.20, THREE.MathUtils.clamp((0.6 - sun.intensity) / 0.6, 0, 1));
  $('#phaseName').textContent = f < 0.5 ? A.ko : B.ko;
  $('#dayNo').textContent = `${day}일차`;
  $('#dayFill').style.width = `${(dayT / 4) * 100}%`;
  $('#dayMark').style.left = `${(dayT / 4) * 100}%`;
  if (i0 !== lastPhase) {
    const id = PHASES[i0].id;
    nightNow = id === 'night';
    fire('world:night', { night: nightNow, phase: id });           // 앰비언트 3.0초 크로스페이드
    if (id === 'dusk' || id === 'night') fire('world:lantern_on', { phase: id });
    if (id === 'dusk') {
      fire('ai:dog_warn', { reason: 'dusk' });                     // A5: 개가 0.4초 먼저 짖는다
      setTimeout(() => warn('해가 기운다. 돌아와야 한다.'), 400);
    }
    if (id === 'dawn' && lastPhase === 3) { day++; $('#dayNo').textContent = `${day}일차`; }
    lastPhase = i0;
  }
}
const fire = (name, detail) => window.dispatchEvent(new CustomEvent(name, { detail }));
function warn(t) {
  const w = $('#warn'); w.textContent = t; w.classList.add('show');
  clearTimeout(warn._t); warn._t = setTimeout(() => w.classList.remove('show'), 5200);
}
applyDay();

// ═══════════════════════════════════════════════════════════════════════════
// 9. 스캔 훅 — /api/scan 성공 시 몰 입구로 카트가 들어온다(원시 도형, D3 "기다림은 장면으로")
// ═══════════════════════════════════════════════════════════════════════════
const carts = [];
const crateMat = new THREE.MeshStandardMaterial({ color: 0x8A6A3C, roughness: .85 });
function makeCart() {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.0, 1.3),
    new THREE.MeshStandardMaterial({ color: 0x7C7F83, roughness: .55, metalness: .35 }));
  body.position.y = 0.85; body.castShadow = true; g.add(body);
  const crate = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.9, 0.9), crateMat);
  crate.position.set(0, 1.75, 0); crate.castShadow = true; g.add(crate);
  const wg = new THREE.CylinderGeometry(0.33, 0.33, 0.18, 10);
  const wm = new THREE.MeshStandardMaterial({ color: 0x24211d, roughness: 1 });
  [[-0.7, 0.55], [0.7, 0.55], [-0.7, -0.55], [0.7, -0.55]].forEach(([x, z]) => {
    const w = new THREE.Mesh(wg, wm); w.rotation.x = Math.PI / 2; w.position.set(x, 0.33, z); g.add(w);
  });
  return { g, crate };
}
const shelf = [];
function onScan(card) {
  const { g, crate } = makeCart();
  const from = toWorld(34, 0), to = toWorld(HALL_L.x + 5, 0);
  g.position.set(from.x, heightAt(from.x, from.z), from.z);
  g.rotation.y = MALL_ROT + Math.PI / 2;
  scene.add(g);
  carts.push({ g, crate, t: 0, from, to, card: card || null, dropped: false });
  toast(card ? `카트 도착 — 「${card.name || card.title || '유물'}」` : '카트가 들어온다');
  return true;
}
function stepCarts(dt) {
  for (let i = carts.length - 1; i >= 0; i--) {
    const c = carts[i]; c.t += dt / 5.5;
    if (c.t < 1) {
      const x = c.from.x + (c.to.x - c.from.x) * c.t, z = c.from.z + (c.to.z - c.from.z) * c.t;
      c.g.position.set(x, heightAt(x, z), z);
      c.crate.rotation.y += dt * 0.7;
    } else if (!c.dropped) {                      // 진열대에 물건이 놓인다
      c.dropped = true;
      const m = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.8, 0.8), crateMat);
      const p = toWorld(HALL_L.x + 2.4 + (shelf.length % 4) * 1.0, 3.0 + Math.floor(shelf.length / 4) * 1.0);
      m.position.set(p.x, heightAt(p.x, p.z) + 0.4, p.z); m.castShadow = true; scene.add(m);
      shelf.push(m); if (shelf.length > 12) scene.remove(shelf.shift());
      c.crate.visible = false;
    } else if (c.t < 2.1) {
      const t2 = (c.t - 1) / 1.1;
      const x = c.to.x + (c.from.x - c.to.x) * t2, z = c.to.z + (c.from.z - c.to.z) * t2;
      c.g.position.set(x, heightAt(x, z), z);
    } else { scene.remove(c.g); carts.splice(i, 1); }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 10. 서버 연결 (app.js 와 같은 uid 규약. server.py 는 수정하지 않는다)
// ═══════════════════════════════════════════════════════════════════════════
const uid = (() => {
  try { let u = localStorage.getItem('ark_uid'); if (!u) { u = 'u' + Math.random().toString(36).slice(2, 10); localStorage.setItem('ark_uid', u); } return u; }
  catch { return 'anon'; }
})();
const SAMPLES = ['8801043015097', '9791162241905', '8806011000013', '8809000111110', '8801044007770'];
function paintRes(r) {
  if (!r) return;
  $('#rFood').textContent = r.food ?? '–'; $('#rWater').textContent = r.water ?? '–';
  $('#rMed').textContent = r.med ?? '–'; $('#rMorale').textContent = r.morale ?? '–';
}
// 리더·정원사 한 줄 (S2-B가 /api/ark 에 실어 준 voice). app.js 의 voiceToast 는 index.html DOM 에 묶여 있어
// 이 화면에서는 로드하지 않고 같은 톤으로 표시만 맞춘다(보고서 §7).
function voiceToast(v, ms = 7000) {
  if (!v || !v.text) return;
  const el = $('#voice');
  el.querySelector('b').textContent = v.who_ko || v.who || '';
  el.querySelector('span').textContent = v.text;
  el.classList.add('show');
  clearTimeout(voiceToast._t); voiceToast._t = setTimeout(() => el.classList.remove('show'), ms);
}
fetch(`/api/ark?uid=${uid}`).then(r => r.ok ? r.json() : null).then(j => {
  if (!j) return;
  paintRes(j.resources);
  setTimeout(() => voiceToast(j.voice, 9000), 1200);           // 문턱 컷의 첫 말 (첫 30분 대본 1비트)
  (j.morning_lines || []).forEach((m, i) => setTimeout(() => voiceToast(typeof m === 'string' ? { who_ko: '아침', text: m } : m), 11000 + i * 8000));
}).catch(() => { });

async function doScan(barcode) {
  const code = barcode || SAMPLES[Math.floor(Math.random() * SAMPLES.length)];
  try {
    const r = await fetch('/api/scan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid, barcode: code }),
    });
    const j = await r.json();
    if (!r.ok) { toast(j.detail || '해독 실패'); return null; }
    paintRes(j.resources); fire('api:scan_ok', { card: j.card }); onScan(j.card);
    if (j.voice) setTimeout(() => voiceToast(j.voice), 1800);    // 카트가 들어온 뒤 리더가 한 줄
    return j;
  } catch (e) { toast('서버에 닿지 않는다'); return null; }
}

function toast(t) {
  const el = $('#toast'); el.textContent = t; el.classList.add('show');
  clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove('show'), 2600);
}

// ═══════════════════════════════════════════════════════════════════════════
// 10.5 오디오 매니저 (S2-F 큐시트 docs/AUDIO_CUES.md — 버스 3개 + 이벤트 구독)
//   · 귀의 위치 = 정찰병(안개를 걷는 사람). 문턱을 넘는 것도 이 사람이다.
//   · 파일이 없거나 재생이 막히면 조용히 넘어간다(콘솔 에러 0).
// ═══════════════════════════════════════════════════════════════════════════
const AUDIO = (() => {
  const DIR = '/static/audio/';
  const FILES = ['amb_inside', 'amb_outside_day', 'amb_outside_night', 'sfx_lantern_on', 'sfx_campfire',
    'sfx_water_splash', 'sfx_scan_ok', 'sfx_note_arrive', 'sfx_card_place', 'sfx_dog_warn', 'cue_spot_found'];
  const AMB_DB = { amb_inside: -12, amb_outside_day: -10, amb_outside_night: -13 };
  const dB = (d) => Math.pow(10, d / 20);
  const vol = { amb: 0.70, sfx: 0.85, music: 0.90 };
  let ctx = null, bus = null, buf = {}, ready = false, cur = null, cue = null, ducked = false, booting = false;

  const want = () => scoutInside ? 'amb_inside' : (nightNow ? 'amb_outside_night' : 'amb_outside_day');

  async function start() {
    if (booting) return;
    if (ctx) { if (ctx.state === 'suspended') { try { await ctx.resume(); } catch (_) { } } return; }
    booting = true;
    try {
      const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      ctx = new AC();
      bus = { amb: ctx.createGain(), sfx: ctx.createGain(), music: ctx.createGain() };
      for (const k in bus) { bus[k].gain.value = vol[k]; bus[k].connect(ctx.destination); }
      await Promise.all(FILES.map(async n => {
        try { const r = await fetch(DIR + n + '.ogg'); if (!r.ok) return; buf[n] = await ctx.decodeAudioData(await r.arrayBuffer()); }
        catch (_) { /* 없으면 그 큐만 조용히 빠진다 */ }
      }));
      ready = true; setAmb(want(), 0.8);
      log(`audio ready ${Object.keys(buf).length}/${FILES.length}`);
    } catch (_) { ready = false; } finally { booting = false; }
  }
  function setAmb(name, dur) {
    if (!ready || !buf[name] || (cur && cur.name === name)) return;
    const now = ctx.currentTime, g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, now);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0002, dB(AMB_DB[name] ?? -12)), now + dur);
    const s = ctx.createBufferSource(); s.buffer = buf[name]; s.loop = true;
    s.connect(g); g.connect(bus.amb); s.start();
    if (cur) {
      const old = cur;
      old.g.gain.cancelScheduledValues(now);
      old.g.gain.setValueAtTime(Math.max(0.0002, old.g.gain.value), now);
      old.g.gain.exponentialRampToValueAtTime(0.0001, now + dur);
      setTimeout(() => { try { old.s.stop(); old.s.disconnect(); old.g.disconnect(); } catch (_) { } }, dur * 1000 + 150);
    }
    cur = { name, s, g };
  }
  function sfx(name, db) {
    if (!ready || !buf[name]) return;
    const g = ctx.createGain(); g.gain.value = dB(db ?? -8);
    const s = ctx.createBufferSource(); s.buffer = buf[name];
    s.connect(g); g.connect(bus.sfx); s.start();
  }
  function duck(on) {
    if (!ready || ducked === on) return; ducked = on;
    const now = ctx.currentTime, t = Math.max(0.0002, vol.amb * (on ? dB(-6) : 1));
    bus.amb.gain.cancelScheduledValues(now);
    bus.amb.gain.setValueAtTime(Math.max(0.0002, bus.amb.gain.value), now);
    bus.amb.gain.exponentialRampToValueAtTime(t, now + 0.3);
  }
  function startCue() {
    if (!ready || !buf.cue_spot_found || cue) return;
    const b = buf.cue_spot_found, now = ctx.currentTime, g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, now);
    g.gain.exponentialRampToValueAtTime(dB(-6), now + 0.3);
    const s = ctx.createBufferSource(); s.buffer = b;
    s.loop = true; s.loopStart = Math.min(0.8, b.duration * 0.05); s.loopEnd = b.duration;  // 0.8초 무음은 첫 회에만
    s.connect(g); g.connect(bus.music); s.start();
    cue = { s, g }; duck(true);
  }
  function endCue() {
    duck(false);
    if (!cue) return;
    const now = ctx.currentTime, c = cue; cue = null;
    c.g.gain.cancelScheduledValues(now);
    c.g.gain.setValueAtTime(Math.max(0.0002, c.g.gain.value), now);
    c.g.gain.exponentialRampToValueAtTime(0.0001, now + 1.2);
    setTimeout(() => { try { c.s.stop(); c.s.disconnect(); c.g.disconnect(); } catch (_) { } }, 1400);
  }
  function setBus(k, v) {
    if (!(k in vol)) return; vol[k] = THREE.MathUtils.clamp(v, 0, 1);
    if (ready && bus[k]) bus[k].gain.value = vol[k] * (k === 'amb' && ducked ? dB(-6) : 1);
  }

  addEventListener('world:threshold', () => setAmb(want(), 1.5));   // 문턱 1.5초
  addEventListener('world:night', () => setAmb(want(), 3.0));       // 시간대 전환 3.0초
  addEventListener('world:spot_found', startCue);
  addEventListener('api:scan_ok', () => sfx('sfx_scan_ok', -6));
  addEventListener('api:event_new', () => sfx('sfx_note_arrive', -8));
  addEventListener('ui:card_place', () => sfx('sfx_card_place', -10));
  addEventListener('world:lantern_on', () => sfx('sfx_lantern_on', -8));
  addEventListener('ai:dog_warn', () => sfx('sfx_dog_warn', -4));
  addEventListener('world:water_splash', () => sfx('sfx_water_splash', -8));
  addEventListener('pointerdown', start, { capture: true });        // 자동재생 정책: 첫 사용자 입력에서 시작
  addEventListener('keydown', start, { capture: true });
  return { start, setBus, endCue, sfx, get ready() { return ready; }, get amb() { return cur && cur.name; }, vol };
})();

// ═══════════════════════════════════════════════════════════════════════════
// 11. 입력 — 줌 · 팬 · 우클릭 기울기 · 지면 클릭 · 핀치
// ═══════════════════════════════════════════════════════════════════════════
let selected = 'scout';
const raycaster = new THREE.Raycaster(), ndc = new THREE.Vector2();
function groundAt(clientX, clientY) {
  ndc.x = (clientX / innerWidth) * 2 - 1; ndc.y = -(clientY / innerHeight) * 2 + 1;
  raycaster.setFromCamera(ndc, camera);
  const hit = raycaster.intersectObject(terrain, false)[0];
  return hit ? hit.point : null;
}
function setFrustum(v) { frustum = THREE.MathUtils.clamp(v, 8, 90); placeCamera(); }

canvas.addEventListener('wheel', e => { e.preventDefault(); setFrustum(frustum * (e.deltaY > 0 ? 1.12 : 0.89)); }, { passive: false });
canvas.addEventListener('contextmenu', e => e.preventDefault());

const ptrs = new Map(); let drag = null, pinch = 0;
canvas.addEventListener('pointerdown', e => {
  try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* 합성 이벤트·이미 해제된 포인터 */ }
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (ptrs.size === 1) drag = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, b: e.button, t: performance.now(), moved: 0 };
  if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch = Math.hypot(a.x - b.x, a.y - b.y); drag = null; }
});
canvas.addEventListener('pointermove', e => {
  if (!ptrs.has(e.pointerId)) return;
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (ptrs.size === 2 && pinch) {
    const [a, b] = [...ptrs.values()]; const d = Math.hypot(a.x - b.x, a.y - b.y);
    if (d > 4) { setFrustum(frustum * (pinch / d)); pinch = d; }
    return;
  }
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  drag.x = e.clientX; drag.y = e.clientY; drag.moved += Math.abs(dx) + Math.abs(dy);
  if (drag.b === 2) {
    camAz += dx * 0.004;
    camEl = THREE.MathUtils.clamp(camEl - dy * 0.004, 0.35, 1.25);
  } else {
    const k = frustum * 2 / innerHeight;
    const right = new THREE.Vector3(Math.cos(camAz), 0, Math.sin(camAz));
    const fwd = new THREE.Vector3(Math.sin(camAz), 0, -Math.cos(camAz));   // 화면 위쪽에 대응하는 월드 방향
    camTarget.addScaledVector(right, -dx * k).addScaledVector(fwd, dy * k);
    camTarget.x = THREE.MathUtils.clamp(camTarget.x, -MAP_W / 2, MAP_W / 2);
    camTarget.z = THREE.MathUtils.clamp(camTarget.z, -MAP_D / 2, MAP_D / 2);
  }
  placeCamera();
});
function endPtr(e) {
  if (drag && ptrs.size === 1 && drag.b !== 2 && drag.moved < 8 && performance.now() - drag.t < 700) {
    const p = groundAt(drag.sx, drag.sy);
    if (p) { const n = sendTo(selected, p.x, p.z); if (n) toast(`${selected === 'all' ? '전원' : actors[selected].ko} 출발`); }
  }
  ptrs.delete(e.pointerId); if (ptrs.size < 2) pinch = 0; if (ptrs.size === 0) drag = null;
}
canvas.addEventListener('pointerup', endPtr);
canvas.addEventListener('pointercancel', endPtr);
canvas.addEventListener('pointerleave', endPtr);

addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight); aspect = innerWidth / innerHeight; placeCamera();
});

// ── HUD 배선
document.querySelectorAll('#who button').forEach(b => b.onclick = () => {
  selected = b.dataset.who;
  document.querySelectorAll('#who button').forEach(x => x.classList.toggle('on', x === b));
});
$('#btnPhase').onclick = () => { dayT = (Math.floor(dayT) + 1) % 4; applyDay(); };   // 날짜는 applyDay 의 새벽 전이에서만 오른다
$('#btnAuto').onclick = () => { auto = !auto; $('#btnAuto').classList.toggle('on', auto); };
$('#btnHome').onclick = () => { const w = toWorld(HALL_L.x, HALL_L.z); sendTo('all', w.x, w.z); toast('홀 허브로 복귀'); };
$('#btnView').onclick = () => { camAz = Math.PI / 4; camEl = Math.PI / 4; frustum = 26; camTarget.set(-4, 0.8, -4); placeCamera(); };
$('#btnScan').onclick = () => doScan();
$('#dClose').onclick = () => { $('#discover').classList.remove('show'); AUDIO.endCue(); if (camSaved) tweenCam(camSaved, 1.2); };

// ═══════════════════════════════════════════════════════════════════════════
// 12. 발견 연출 · 카메라 트윈
// ═══════════════════════════════════════════════════════════════════════════
let camAnim = null, camSaved = null;
function tweenCam(to, dur) {
  camAnim = {
    t: 0, dur,
    from: { x: camTarget.x, y: camTarget.y, z: camTarget.z, f: frustum, el: camEl, az: camAz },
    to: { x: to.x, y: to.y ?? 0.8, z: to.z, f: to.f ?? frustum, el: to.el ?? camEl, az: to.az ?? camAz },
  };
}
let discovered = false;
function discover() {
  discovered = true;
  for (let i = 0; i < 12; i++) {
    const a = i / 12 * 6.2832;
    reveal(SPOT.x + Math.cos(a) * 12, SPOT.z + Math.sin(a) * 12, 20);
  }
  reveal(SPOT.x, SPOT.z, 30);
  fire('world:spot_found', { spot: spotData.id || 'spot_flooded_train' });
  // "아무도 들어가지 않고 문간에 서서 오래 본다" — 정찰병을 marker_threshold 에 세우고 전철(-Z)을 보게
  const sc0 = actors.scout;
  if (sc0 && spotThreshold) {
    sc0.path = [];
    sc0.root.position.set(spotThreshold.x, spotThreshold.y, spotThreshold.z);
    sc0.root.rotation.y = Math.PI;
    sc0.play('idle');
  }
  camSaved ={ x: camTarget.x, z: camTarget.z, y: camTarget.y, f: frustum, el: camEl, az: camAz };
  tweenCam({ x: SPOT.x, z: SPOT.z, y: 0.8, f: 15, el: 0.46 }, 2.6);   // 카메라가 천천히 내려앉는다
  $('#dTitle').textContent = spotData.name || '물에 잠긴 전철';
  $('#dText').textContent = spotData.discovery_text || SPOT_FALLBACK.discovery_text;
  setTimeout(() => $('#discover').classList.add('show'), 900);
}

// ═══════════════════════════════════════════════════════════════════════════
// 13. 루프
// ═══════════════════════════════════════════════════════════════════════════
const clock = new THREE.Clock();
let lastRevealX = 1e9, lastRevealZ = 1e9, fpsAcc = 0, fpsN = 0, fpsT = 0;
reveal(actors.scout ? actors.scout.root.position.x : 0, actors.scout ? actors.scout.root.position.z : 0, 24);

function tick() {
  const dt = Math.min(0.05, clock.getDelta()), t = clock.elapsedTime;

  if (auto) { dayT = (dayT + dt / PHASE_SEC) % 4; applyDay(); }

  lanterns.forEach(o => { o.l.intensity = o.base * (0.86 + 0.14 * Math.sin(t * 7 + o.seed) * Math.sin(t * 3.1 + o.seed)); });

  for (const a of Object.values(actors)) {
    a.mixer.update(dt);
    const wet = a.root.position.y < WATER_Y;              // 물에 들어간다
    if (wet !== !!a.wet) { a.wet = wet; if (wet) fire('world:water_splash', { who: a.key }); }
    if (a.path.length) {
      const tgt = a.path[0];
      const dx = tgt.x - a.root.position.x, dz = tgt.z - a.root.position.z;
      const dist = Math.hypot(dx, dz);
      if (dist < 0.4) { a.path.shift(); if (!a.path.length) a.play('idle'); }
      else {
        const k = a.speed * dt / dist;
        const nx = a.root.position.x + dx * k, nz = a.root.position.z + dz * k;
        a.root.position.set(nx, heightAt(nx, nz), nz);
        a.root.rotation.y = Math.atan2(dx, dz);
        a.play('walk');
      }
    }
  }

  const sc = actors.scout;
  if (sc) {
    const p = sc.root.position;
    if (Math.hypot(p.x - lastRevealX, p.z - lastRevealZ) > 2.5) { reveal(p.x, p.z, 24); lastRevealX = p.x; lastRevealZ = p.z; }
    const nowIn = inMall(toLocal(p.x, p.z));               // 문턱 통과 = 앰비언트 1.5초 크로스페이드
    if (nowIn !== scoutInside) { scoutInside = nowIn; fire('world:threshold', { to: nowIn ? 'inside' : 'outside' }); }
    const dSpot = Math.hypot(p.x - SPOT.x, p.z - SPOT.z);
    if (!spotGroup.visible && dSpot < 30) spotGroup.visible = true;   // 안개 위로 형태가 먼저 올라온다
    if (!discovered && dSpot < SPOT.r) discover();
  }
  if (fogDirty) { fogTex.needsUpdate = true; fogDirty = false; }

  stepCarts(dt);

  if (dog && actors.scout) {                              // 개는 정찰병 왼쪽 1.4m 에 붙어 다닌다
    dog.mixer.update(dt);
    const s = actors.scout.root;
    const tx = s.position.x - Math.cos(s.rotation.y) * 1.3, tz = s.position.z + Math.sin(s.rotation.y) * 1.3;
    const d = Math.hypot(tx - dog.root.position.x, tz - dog.root.position.z);
    if (d > 0.6) {
      const k = Math.min(1, (WALK * 1.15) * dt / d);
      const nx = dog.root.position.x + (tx - dog.root.position.x) * k, nz = dog.root.position.z + (tz - dog.root.position.z) * k;
      dog.root.position.set(nx, heightAt(nx, nz), nz);
      dog.root.rotation.y = Math.atan2(tx - nx, tz - nz);
      dog.play(d > 1.6 ? 'walk' : 'idle');
    } else { dog.root.rotation.y = s.rotation.y; dog.play('idle'); }
  }

  for (const D of dinos) {                                // 초식 공룡: 제 자리 근처를 천천히 돈다
    D.mixer.update(dt);
    const a = t * 0.045 + D.ph;
    const nx = D.home.x + Math.cos(a) * D.r, nz = D.home.y + Math.sin(a) * D.r * 0.7;
    D.root.position.set(nx, heightAt(nx, nz), nz);
    D.root.rotation.y = a + Math.PI / 2;
  }

  for (const k of koi) {                                  // 금붕어가 천천히 돈다
    k.g.position.x = k.base.x + Math.cos(t * k.w + k.ph) * k.r;
    k.g.position.z = k.base.z + Math.sin(t * k.w * 0.8 + k.ph) * k.r * 0.7;
    k.g.rotation.y = -(t * k.w + k.ph) + Math.PI / 2;
  }

  if (camAnim) {
    camAnim.t = Math.min(1, camAnim.t + dt / camAnim.dur);
    const e = camAnim.t < 0.5 ? 2 * camAnim.t * camAnim.t : 1 - Math.pow(-2 * camAnim.t + 2, 2) / 2;
    const f = camAnim.from, o = camAnim.to, L = THREE.MathUtils.lerp;
    camTarget.set(L(f.x, o.x, e), L(f.y, o.y, e), L(f.z, o.z, e));
    frustum = L(f.f, o.f, e); camEl = L(f.el, o.el, e); camAz = L(f.az, o.az, e);
    placeCamera();
    if (camAnim.t >= 1) camAnim = null;
  }

  fpsAcc += dt; fpsN++;
  if (fpsAcc - fpsT > 0.5) { $('#fps').textContent = Math.round(fpsN / (fpsAcc - fpsT)); fpsT = fpsAcc; fpsN = 0; }

  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();

// ═══════════════════════════════════════════════════════════════════════════
// 14. 외부 훅 (★ 일부는 개발/검증 전용 — 배포 전 점검 목록)
// ═══════════════════════════════════════════════════════════════════════════
window.WORLD = {
  onScan,                       // /api/scan 성공 카드 → 카트 연출
  scan: doScan,                 // 버튼과 동일: 서버 호출 + 연출
  sendTo,                       // (key|'all', worldX, worldZ)
  reveal, heightAt, toWorld, toLocal,
  setTerrainTextures: applyTerrainTextures,          // S2-D 텍스처가 오면 호출(또는 ?assets)
  loadFacadeGLB, loadSpotGLB, loadSpotsJson,         // S2-D 씬 GLB / 시나리오 spots.json 훅
  get spotData() { return spotData; },
  select: (k) => {
    selected = k;
    document.querySelectorAll('#who button').forEach(x => x.classList.toggle('on', x.dataset.who === k));
  },
  setCam: (o) => {                    // ★ 검증·연출 전용: 카메라를 직접 놓는다
    if (o.x !== undefined) camTarget.x = o.x; if (o.z !== undefined) camTarget.z = o.z;
    if (o.f !== undefined) frustum = THREE.MathUtils.clamp(o.f, 8, 90);
    if (o.el !== undefined) camEl = o.el; if (o.az !== undefined) camAz = o.az;
    placeCamera();
  },
  setPhase: (i) => { dayT = i % 4; applyDay(); },
  get phase() { return PHASES[Math.floor(dayT) % 4].id; },
  get day() { return day; },
  get discovered() { return discovered; },
  actors, SPOT, audio: AUDIO, fire, voiceToast, setImprints, IMPRINT_IDS,
  get dog() { return dog; }, dinos, koi,
  screenOf(x, z) {              // ★ 검증 전용: 월드 좌표 → 화면 좌표(합성 클릭용)
    const v = new THREE.Vector3(x, heightAt(x, z), z).project(camera);
    return { x: (v.x + 1) / 2 * innerWidth, y: (-v.y + 1) / 2 * innerHeight };
  },
  camera, scene, renderer, THREE, mall, facade, spotGroup,   // ★ 검증/튜닝 전용
};
log('WORLD ready');
