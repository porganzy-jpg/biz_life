# -*- coding: utf-8 -*-
"""
잔해 방주 — 1막 거점 「정면 평면 단면」 (S4-A, 목표 화풍 적용본)
blender -b --python tools/blender_section.py -- hero
blender -b --python tools/blender_section.py -- zoom
blender -b --python tools/blender_section.py -- palette
blender -b --python tools/blender_section.py -- all

산출물
  art_raw/deep/section_hero.png     거점 전체가 한 화면에 (1600×900)
  art_raw/deep/section_zoom.png     방 3칸 확대 (1600×900)
  art_raw/deep/section_palette.png  팔레트·문양 띠 (1600×500)

근거
  DECISIONS 2026-09-23 ①정면 평면 단면 ②성장 방향은 아래 ③D1 개정(방마다 고유 색상)
  docs/refs/REF_CROSS_SECTION.md  §1 원리 10가지  (형상·구도. 모방 금지, 원리만)
  docs/refs/REF_ART_FLAT_FOLK.md  §1 원리 12가지  (화풍. 모방 금지, 원리만)
  docs/CONCEPT_DEEP_SEA.md §6 D1~D6

── 형상 (2026-09-23 통과분, 손대지 않는다) ─────────────────────
  정면 직교(원근 0). 맨 위 유리돔 → 아래로 유리 척추 → 층마다 좌우로 방.
  방은 평면이 아니라 깊이 1.7m 의 얕은 디오라마(절두각뿔). 뒷벽·바닥·천장이 보인다.
  세로축 = 광층 / 박광층 / 무광층 / 해구. 아래로 자란다.

── 화풍 (이번 개정의 본체) ─────────────────────────────────────
  F1 색은 전부 sRGB → 선형 변환을 거쳐 넣는다. (1차 렌더가 밝았던 원인)
  F2 음영 2단 고정. 램프·볼륨 안개·광원을 전부 버리고,
     ① 방 껍질 = 순수 평면 이미션(면마다 기본색/그림자색 2단만)
     ② 소품·사람 = 고정 광선 방향에 대한 법선 내적 → CONSTANT 컬러램프 2단
     그래서 화면 어디에도 그라데이션이 없다. (§1-3)
  F3 팔레트 고정: 크림/뼈·황토·번트오렌지·적갈·숯검정·탁한 올리브.
     청록~남색은 물에만. 방과 사람에게는 쓰지 않는다. (§5)
  F4 방 배경을 전부 묘사하지 않는다. 단색 면 + 장식 문양 + 상징 소품. (§1-10)
  F5 방마다 다른 반복 문양 — 색 다음의 두 번째 판독 단서. (§1-5)
  F6 손으로 그은 선: Freestyle 두께 NOISE + PERLIN_NOISE_2D + SINUS_DISPLACEMENT,
     종이 결을 컴포지터에서 곱하기. 매끈한 벡터 선 금지. (§1-9)
  F7 극단적 명도 대비: 화면에서 가장 밝은 것은 언제나 방 안의 등불. 물은 거의 검정.
     방 둘레에는 항상 어두운 여백(후광)을 깐다. (§1-2, REF_CROSS_SECTION §1-3)
  F8 뷰 트랜스폼 Standard. 팔레트 hex 가 화면에 그 값 그대로 나와야 관리가 된다.

코드 재사용: blender_dome → blender_scenes → blender_iso 를 import 로 그대로 쓴다.
"""
import bpy, sys, os, math, importlib.util, random, json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"

# ══════════════════════════════════════════════════════════════
# S6-B. 「방 안을 들어가 앉고 싶은 곳으로」
#   REF_ART_FLAT_FOLK §7-4 환경 교정 넷 + 2026-09-27 정정 ①②
#   COZY=False 로 돌리면 S4-A 그대로 — 전·후 비교를 정직하게 내기 위한 스위치다.
#   바깥 물은 어느 쪽에서도 손대지 않는다.
# ══════════════════════════════════════════════════════════════
COZY = True

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT_RAW = os.path.join(ROOT, "art_raw", "deep")
os.makedirs(OUT_RAW, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# F1. sRGB → 선형.  1차 렌더에서 물이 밝게 나온 원인이 여기였다.
#     blender_iso.hexcol 을 이 모듈에서만 갈아 끼운다(다른 스크립트 회귀 없음).
# ══════════════════════════════════════════════════════════════
def _s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_hexcol(h):
    h = h.lstrip('#')
    return tuple(_s2l(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def load_dome():
    spec = importlib.util.spec_from_file_location("blender_dome", os.path.join(HERE, "blender_dome.py"))
    m = importlib.util.module_from_spec(spec)
    saved = list(sys.argv)
    sys.argv = [saved[0], "--", "__none__"]
    spec.loader.exec_module(m)
    sys.argv = saved
    return m


DOME = load_dome()
SC = DOME.SC
iso = DOME.iso
iso.hexcol = srgb_hexcol          # ← F1. iso.mat / SC.alpha_mat / 램프 색 전부가 이 함수를 본다


# ── 정면 직교 시점의 화면 기저 (blender_dome 의 실루엣 헬퍼가 이 값을 본다) ──
V_FRONT = Vector((0, -1, 0))
RIGHT_FRONT = Vector((1, 0, 0))
UP_FRONT = Vector((0, 0, 1))

# 고정 광선 방향 — 화면 왼쪽 위 앞에서. 모든 2단 음영이 이 하나를 쓴다(§1-3)
LDIR = Vector((-0.42, -0.72, 0.55)).normalized()

# ── 규격 ────────────────────────────────────────────────────
DEPTH = 1.7          # 방 디오라마 깊이 (원리 2: 1~2m)
INSET_X = 1.05
INSET_ZB = 0.62
INSET_ZT = 0.46
RH = 3.0
HULL = 0.42
SPINE = 1.35
GAP = 0.55

DOME_C, DOME_R = Vector((0, 0, 17.2)), 5.4
L = {1: 6.4, 2: 2.0, 3: -2.4, 4: -6.8}

# ══════════════════════════════════════════════════════════════
# F3. 팔레트 — REF_ART_FLAT_FOLK §5 그대로. 청록~남색은 물 전용.
# ══════════════════════════════════════════════════════════════
PAL = {
    "cream":   "#E6D8B4",     # 크림/뼈 — 화면에서 가장 밝은 면
    "bone":    "#C9B896",
    "ochre":   "#C68F3E",     # 황토
    "ochre_d": "#8A6531",
    "burnt":   "#B85A24",     # 번트오렌지
    "oxblood": "#6E2A22",     # 적갈
    "char":    "#1C1712",     # 숯검정 — 선·그림자·실루엣
    "char_lt": "#3A312A",
    "olive":   "#6F7A3C",     # 탁한 올리브
    "olive_d": "#464E26",
    # 물 전용 (사람·방에 쓰지 않는다)
    "sea_top": "#2E7E90",
    "sea_mid": "#0B2530",
    "sea_low": "#041016",
    "abyss":   "#000000",
}


def hx(h, f):
    """hex 를 sRGB 영역에서 f 배(명도 계단). 선형 변환은 hexcol 이 나중에 한다."""
    h = h.lstrip('#')
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(int(h[i:i + 2], 16) * f))) for i in (0, 2, 4))


M = {}


def hexm(name, h, rough=0.85, emit=None, strength=0.0):
    return iso.mat(name, h, rough, emit=emit, strength=strength)


# ══════════════════════════════════════════════════════════════
# 재질 — 평면 이미션 / 2단 토온 / 반투명 베일
# ══════════════════════════════════════════════════════════════
def _mark(m):
    m["relic_flat"] = 1          # 전역 평탄화 패스가 건너뛰도록 표시
    return m


def flat_mat(name, hexc, alpha=1.0):
    """순수 평면 이미션. hex 가 화면에 그 값 그대로 찍힌다(F8)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (*srgb_hexcol(hexc), 1); em.inputs[1].default_value = 1.0
    if alpha >= 0.999:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    else:
        mix = nt.nodes.new("ShaderNodeMixShader")
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        _blend(m)
    return _mark(m)


def _blend(m):
    for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED"),
                      ("show_transparent_back", False)):
        try:
            setattr(m, attr, val)
        except Exception:
            pass


def _toon_chain(nt, thresh=0.52):
    """법선·고정 광선 → 0/1 두 단계만 내보내는 CONSTANT 램프 (F2)."""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = 'DOT_PRODUCT'
    dot.inputs[1].default_value = (LDIR.x, LDIR.y, LDIR.z)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0; mr.inputs["From Max"].default_value = 1.0
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = 'CONSTANT'
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], mr.inputs["Value"])
    nt.links.new(mr.outputs[0], ramp.inputs["Fac"])
    return ramp


def toon_mat(name, hexc, shade=0.52, thresh=0.52, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.0
    ramp = _toon_chain(nt, thresh)
    cr = ramp.color_ramp
    base = srgb_hexcol(hexc)
    cr.elements[0].position = 0.0; cr.elements[0].color = (*[v * shade for v in base], 1)
    cr.elements[1].position = thresh; cr.elements[1].color = (*base, 1)
    nt.links.new(ramp.outputs["Color"], em.inputs[0])
    if alpha >= 0.999:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    else:
        mix = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"]); _blend(m)
    return _mark(m)


def mesh_uv_quads(name, quads, material):
    verts, faces = [], []
    for q in quads:
        i = len(verts); verts.extend([tuple(pt) for pt in q]); faces.append([i, i + 1, i + 2, i + 3])
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    uvl = me.uv_layers.new(name="UVMap")
    corner = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for li in range(len(me.loops)):
        uvl.data[li].uv = corner[li % 4]
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def soft_mat(name, hexc, alpha=0.35, strength=1.0, core=0.5):
    """중심에서 가장자리로 사라지는 마스크. 검정이면 어둡게 깎는 후광, 밝으면 부유물."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    grad = nt.nodes.new("ShaderNodeTexGradient"); grad.gradient_type = 'SPHERICAL'
    mapn = nt.nodes.new("ShaderNodeMapping")
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    mapn.inputs["Location"].default_value = (-0.5, -0.5, 0.0)
    mapn.inputs["Scale"].default_value = (2.0, 2.0, 1.0)
    nt.links.new(uv.outputs["UV"], mapn.inputs["Vector"])
    nt.links.new(mapn.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (0, 0, 0, 1)
    cr.elements[1].position = core; cr.elements[1].color = (alpha, alpha, alpha, 1)
    cr.interpolation = 'EASE'
    em.inputs["Color"].default_value = (*srgb_hexcol(hexc), 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(ramp.outputs["Color"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    _blend(m)
    return _mark(m)


# ══════════════════════════════════════════════════════════════
# 물 — 세로 그라데이션 하나가 곧 깊이 축이다 (지적 1)
# ══════════════════════════════════════════════════════════════
ZONE_STOPS = [(0.00, PAL["abyss"]),     # 해구 — 칠흑
              (0.26, "#01060A"),
              (0.45, PAL["sea_low"]),   # 무광층 아래
              (0.60, PAL["sea_mid"]),   # 무광층 — 돔이 사는 층. 거의 검정
              (0.76, "#124455"),        # 박광층
              (0.90, "#227083"),
              (1.00, PAL["sea_top"])]   # 광층 — 갈 수 없는 빛
ZONE_FROM, ZONE_TO = -15.0, 27.0


def zone_gradient(name="WaterZones", mult=1.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mr = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mr.inputs["From Min"].default_value = ZONE_FROM
    mr.inputs["From Max"].default_value = ZONE_TO
    nt.links.new(mr.outputs[0], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = ZONE_STOPS[0][0]
    cr.elements[0].color = (*[v * mult for v in srgb_hexcol(ZONE_STOPS[0][1])], 1)
    for p, c in ZONE_STOPS[1:]:
        e = cr.elements.new(p); e.color = (*[v * mult for v in srgb_hexcol(c)], 1)
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    if alpha >= 0.999:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    else:
        mix = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"]); _blend(m)
    return _mark(m)


def water_backdrop(depth=30.0, w=170.0, h=130.0):
    q = [Vector((-w / 2, depth, -h / 2 + 7)), Vector((w / 2, depth, -h / 2 + 7)),
         Vector((w / 2, depth, h / 2 + 7)), Vector((-w / 2, depth, h / 2 + 7))]
    o = DOME.mesh_of_quads("PRV_backdrop", [q], M["zones"]); o.name = "PRV_backdrop"
    return o


def haze_sheets():
    """감쇠 안개 — 볼륨 대신 물색 반투명 판을 겹친다(합격 기준 ④).
    뒤로 갈수록 판이 여러 겹 끼어서 먼 것이 물색에 잠긴다. 평면 화풍과도 맞는다."""
    for k, (y, a) in enumerate(((19.0, 0.52), (10.5, 0.42), (5.2, 0.26))):
        m = zone_gradient("Haze%d" % k, mult=1.0, alpha=a)
        q = [Vector((-85, y, -58)), Vector((85, y, -58)), Vector((85, y, 72)), Vector((-85, y, 72))]
        o = DOME.mesh_of_quads("PRV_haze%d" % k, [q], m); o.name = "PRV_haze%d" % k


def far_silhouettes():
    """거점 뒤 먼 구조물·바위. 물 그라디언트를 어둡게 한 색이라 높이에 따라 저절로 물에 잠긴다.
    지적 2: 떠 있는 각진 검은 사각형은 전부 없앴다. 남은 것은 둥근 덩어리와 바닥 능선뿐."""
    rnd = random.Random(1234)
    dk = zone_gradient("FarDark", mult=0.55)
    dk2 = zone_gradient("FarDark2", mult=0.72)
    # 해구 바닥 능선 — 화면 맨 아래를 닫는다.
    # 각진 검은 막대가 되지 않게 좁은 기둥을 촘촘히 세우고 윗변을 부드럽게 잇는다.
    def ridge_band(y, base_z, amp, step, seed, hexc):
        r2 = random.Random(seed)
        ctrl = [r2.uniform(0.0, 1.0) for _ in range(14)]
        quads = []
        x = -84.0
        prev = None
        while x < 84.0:
            t = (x + 84.0) / 168.0 * (len(ctrl) - 1)
            i = int(t); f = t - i
            f = f * f * (3 - 2 * f)                       # smoothstep
            hgt = base_z + amp * (ctrl[i] * (1 - f) + ctrl[min(i + 1, len(ctrl) - 1)] * f)
            if prev is not None:
                quads.append([Vector((x - step, y, -34)), Vector((x, y, -34)),
                              Vector((x, y, hgt)), Vector((x - step, y, prev))])
            prev = hgt; x += step
        DOME.mesh_of_quads("PRV_ridge", quads, flat_mat("Ridge%d" % seed, hexc)).name = "PRV_ridge"

    ridge_band(9.0, -11.6, 3.2, 0.7, 501, "#04090E")      # 먼 능선
    ridge_band(3.5, -12.6, 2.1, 0.7, 977, "#010508")      # 가까운 능선, 더 검다
    # 먼 바위 덩어리 — 둥근 것만. 박광층 쪽에만 조금.
    for k in range(7):
        y = rnd.uniform(12.0, 24.0)
        o = iso.sphere("PRV_farrock", (rnd.uniform(-40, 40), y, rnd.uniform(-10.0, 9.0)),
                       rnd.uniform(2.6, 6.4), dk2 if k % 2 else dk, 14, 8)
        o.scale = (1.0, 0.35, 0.44); o.name = "PRV_farrock"
    # 케이블 — 3개→2개, 거의 수직, 물색에 잠긴다 (지적 3)
    for k, x0 in enumerate((-17.5, 21.0)):
        DOME.strut("PRV_farcable", (x0, 13.0 + k * 3.0, 40), (x0 + (3.5 if k else -2.5), 13.0 + k * 3.0, -12),
                   0.05, dk2, 5).name = "PRV_farcable"


def fish_shoal(cx, cz, n, spread, y, seed, mult=0.50, size=0.32):
    """평면 실루엣 물고기 떼. 부유물만으로는 '우주'로 보일 수 있다(합격 기준 ④).
    떼는 위쪽 박광층에만 — 아래 해구는 비어 있어야 깊이가 산다."""
    rnd = random.Random(seed)
    m = zone_gradient("Shoal%d" % seed, mult=mult)
    for k in range(n):
        a = rnd.uniform(0, 6.2832); r = rnd.random() ** 0.62
        x = cx + math.cos(a) * spread[0] * r
        z = cz + math.sin(a) * spread[1] * r
        sz = size * rnd.uniform(0.7, 1.3)
        ry = math.radians(rnd.uniform(-22, 22))
        iso.cube("PRV_fish", (x, y, z), (sz, 0.04, sz * 0.34), m, rot=(0, ry, 0))
        iso.cube("PRV_fish", (x - sz * 0.66, y, z), (sz * 0.30, 0.04, sz * 0.52), m, rot=(0, ry, 0))


def marine_snow():
    """부유물 — 1차 대비 절반 이하, 반투명, 전부 물빛 계열. 방 불빛보다 절대 밝지 않다(지적 5)."""
    rnd = random.Random(818)
    tiers = [(10, 0.44, (-8.0, -5.0), "#16323D", 0.045, 1.0),
             (26, 0.24, (-4.2, -2.2), "#1B3B47", 0.070, 1.4),
             (56, 0.125, (4.0, 9.0),  "#20475A", 0.125, 2.0),
             (72, 0.055, (11.0, 21.0), "#12303C", 0.145, 1.6),
             (32, 0.10, (-6.0, -3.0), "#02090D", 0.30, 1.3)]     # 밝은 위쪽 물에서만 보이는 어두운 알갱이
    for ti, (n, r, dep, col, al, stretch) in enumerate(tiers):
        mt = soft_mat("Snow%d" % ti, col, al, 1.0, 0.06 if ti < 2 else 0.24)
        quads = []
        for _ in range(n):
            x = rnd.uniform(-36, 36); z = rnd.uniform(-13, 28); y = rnd.uniform(dep[0], dep[1])
            rx = r * rnd.uniform(0.55, 1.4)
            rz = rx * stretch * rnd.uniform(0.7, 1.4)
            quads.append([Vector((x - rx, y, z - rz)), Vector((x + rx, y, z - rz)),
                          Vector((x + rx, y, z + rz)), Vector((x - rx, y, z + rz))])
        mesh_uv_quads("PRV_snow%d" % ti, quads, mt).name = "PRV_snow%d" % ti


def soft_jellies():
    """발광 해파리 — 물의 유일한 자연광. 방 등불보다 어둡게."""
    rnd = random.Random(707)
    disc = soft_mat("JellyGlow", "#4FA8B4", 0.30, 1.0, 0.60)
    halo = soft_mat("JellyHalo", "#255C6C", 0.11, 1.0, 0.20)
    qd, qh = [], []
    for k in range(6):
        x = rnd.uniform(-33, 33); z = rnd.uniform(2.0, 24.0); y = rnd.uniform(4.0, 10.0)
        r = 0.30 + rnd.random() * 0.26
        qd.append([Vector((x - r, y, z - r * 0.75)), Vector((x + r, y, z - r * 0.75)),
                   Vector((x + r, y, z + r * 0.75)), Vector((x - r, y, z + r * 0.75))])
        h = r * 3.2
        qh.append([Vector((x - h, y + 0.1, z - h)), Vector((x + h, y + 0.1, z - h)),
                   Vector((x + h, y + 0.1, z + h)), Vector((x - h, y + 0.1, z + h))])
    mesh_uv_quads("PRV_jhalo", qh, halo).name = "PRV_jhalo"
    mesh_uv_quads("PRV_jelly", qd, disc).name = "PRV_jelly"


def soft_shafts():
    """광층에서 내려오는 빛 — 화면 위 1/4 에만, 아주 흐리게."""
    rnd = random.Random(404)
    quads = []
    for k in range(5):
        x = rnd.uniform(-30, 30)
        w = rnd.uniform(3.0, 7.0); top = 36.0; bot = rnd.uniform(14.0, 22.0)
        cz = (top + bot) / 2; hz = (top - bot) / 2
        quads.append([Vector((x - w, 17.0, cz - hz)), Vector((x + w, 17.0, cz - hz)),
                      Vector((x + w, 17.0, cz + hz)), Vector((x - w, 17.0, cz + hz))])
    mt = soft_mat("Shaft", "#4E93A4", 0.038, 1.0, 0.03)
    mesh_uv_quads("PRV_shaft", quads, mt).name = "PRV_shaft"


# ══════════════════════════════════════════════════════════════
# F5. 장식 문양 — 방마다 다른 반복. 색 다음의 두 번째 판독 단서.
#     정교한 묘사 대신 패턴(§1-5). 전부 뒷벽 위 얕은 판.
# ══════════════════════════════════════════════════════════════
PATY = None          # 뒷벽 바로 앞 (build 시 DEPTH 기준으로 채워짐)


def _bar(rid, x, z, w, h, m, ry=0.0):
    iso.cube("pat_" + rid, (x, DEPTH - 0.045, z), (w, 0.05, h), m, rot=(0, ry, 0))


def motif_zigzag(rid, x0, x1, z, m, unit=0.86):
    """거주 — 산 모양 지그재그. 되풀이되는 잠자리."""
    n = max(2, int((x1 - x0) / unit))
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        _bar(rid, x - unit * 0.22, z, 0.62, 0.085, m, math.radians(38))
        _bar(rid, x + unit * 0.22, z, 0.62, 0.085, m, math.radians(-38))


def motif_chevron(rid, x0, x1, z, m, unit=0.80):
    """온실 — 잎맥 갈매기. 두 줄."""
    n = max(2, int((x1 - x0) / unit))
    for row, dz in enumerate((0.0, 0.30)):
        for k in range(n):
            x = x0 + (k + 0.5) * (x1 - x0) / n
            _bar(rid, x - 0.17, z + dz, 0.46, 0.075, m, math.radians(52))
            _bar(rid, x + 0.17, z + dz, 0.46, 0.075, m, math.radians(-52))


def motif_teeth(rid, x0, x1, z, m, unit=0.52):
    """공방 — 사각 톱니. 기계가 문 자국."""
    n = max(2, int((x1 - x0) / unit))
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        h = 0.34 if k % 2 else 0.16
        _bar(rid, x, z + h / 2, 0.24, h, m)


def motif_dots(rid, x0, x1, z, m, unit=0.42):
    """창고 — 점 격자(정사각). 세어 놓은 재고. 에어락의 마름모와 헷갈리지 않게 회전 없음."""
    n = max(2, int((x1 - x0) / unit))
    for row, dz in enumerate((0.0, 0.24, 0.48)):
        for k in range(n):
            x = x0 + (k + 0.5) * (x1 - x0) / n
            _bar(rid, x, z + dz, 0.13, 0.13, m)


def motif_hatch(rid, x0, x1, z, m, unit=0.34):
    """서고 — 세로 빗금. 꽂힌 책등."""
    n = max(2, int((x1 - x0) / unit))
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        h = (0.40, 0.28, 0.52, 0.34)[k % 4]
        _bar(rid, x, z + h / 2, 0.10, h, m)


def motif_wave(rid, x0, x1, z, m, unit=0.22):
    """목욕탕 — 물결. 민물의 사치. 마디가 이어져 한 줄의 파도로 읽혀야 한다."""
    n = max(6, int((x1 - x0) / unit))
    for row, dz0 in enumerate((0.0, 0.34)):
        for k in range(n):
            x = x0 + (k + 0.5) * (x1 - x0) / n
            ph = k * 0.62 + row * 1.6
            dz = math.sin(ph) * 0.15
            _bar(rid, x, z + dz0 + dz, 0.30, 0.10, m, math.radians(math.cos(ph) * 40))


def motif_diamond(rid, x0, x1, z, m, unit=0.76):
    """에어락 — 마름모 사슬. 나갈 때마다 하나씩 세는 표식."""
    n = max(2, int((x1 - x0) / unit))
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        _bar(rid, x, z + 0.16, 0.30, 0.30, m, math.radians(45))
        _bar(rid, x, z + 0.16, 0.15, 0.15, m, math.radians(45))


def motif_arch(rid, x0, x1, z, m, unit=1.30):
    """라운지 — 반원 아치. 유리 너머를 보는 자리."""
    n = max(2, int((x1 - x0) / unit))
    for k in range(n):
        cx = x0 + (k + 0.5) * (x1 - x0) / n
        r = unit * 0.40
        for t in range(7):
            a = math.pi * t / 6.0
            _bar(rid, cx - r * math.cos(a), z + r * math.sin(a), 0.115, 0.115, m)


def motif_slash(rid, x0, x1, z, m, unit=0.44):
    """굴착면 — 한 방향 빗금. 아직 손이 닿지 않은 면."""
    n = max(2, int((x1 - x0) / unit))
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        _bar(rid, x, z + 0.22, 0.09, 0.62, m, math.radians(26))


MOTIF = {"lounge": motif_arch, "quarters": motif_zigzag, "greenhouse": motif_chevron,
         "workshop": motif_teeth, "storage": motif_dots, "library": motif_hatch,
         "bath": motif_wave, "airlock": motif_diamond,
         # S8-C 플레이트에서 새로 생긴 두 방(COMBAT_AND_DEFENSE 5-1)
         "infirmary": motif_arch, "power": motif_slash}


# ══════════════════════════════════════════════════════════════
# 방 — 깊이 1.7m 의 얕은 디오라마 (형상은 그대로, 채색만 평면 2단)
# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# S6-B ①  빛이 번진다 — 정정 ①: 광원 주위만 밝은 것이 아니라 **빛이 방 전체를 데운다**.
#         그림자도 검정이 아니라 따뜻한 갈색. 안팎 대비는 명도가 아니라 색온도로.
# ══════════════════════════════════════════════════════════════
WARM_SHADOW = "#4A3524"        # 방 안의 그림자 — 검정 금지. 따뜻한 갈색 하나로 통일


def mixhex(a, b, t):
    a = a.lstrip('#'); b = b.lstrip('#')
    return "#%02x%02x%02x" % tuple(
        max(0, min(255, int(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t))) for i in (0, 2, 4))


def warm_shade(hue, f=0.66, t=0.42):
    """방 안 그림자. 바탕색을 어둡게 누르되 **따뜻한 갈색 쪽으로** 끌어온다(정정 ①)."""
    return mixhex(hx(hue, f), WARM_SHADOW, t)


def warm_mat(name, hexc, alpha, rx, rz):
    """중심에서 가장자리로 사라지는 따뜻한 번짐.

    기존 `soft_mat` 을 쓰지 않는 이유: 그쪽 Mapping 은 **스케일이 먼저, 위치가 나중**이라
    (0.5,0.5)·scale2 → (1,1)·loc(-0.5) = (0.5,0.5) 로 중심이 어긋난다. 실제로 1~3차 렌더에서
    번짐이 거의 안 보인 원인이 이것이었다. 물(부유물·해파리·빛기둥)이 그 함수를 쓰고 있어
    고치면 바깥이 바뀌므로, **여기서는 손대지 않고 오브젝트 좌표로 새로 짠다.**"""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0 / max(rx, 1e-4), 1.0, 1.0 / max(rz, 1e-4))
    grad = nt.nodes.new("ShaderNodeTexGradient"); grad.gradient_type = 'SPHERICAL'
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = 'EASE'
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (0, 0, 0, 1)
    cr.elements[1].position = 1.0; cr.elements[1].color = (alpha, alpha, alpha, 1)
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.0
    em.inputs[0].default_value = (*srgb_hexcol(hexc), 1)
    mix = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    _blend(m)
    return _mark(m)


def soft_blob(name, cx, cz, rx, rz, hexc, alpha=0.30, y=0.42, core=0.62):
    """가장자리가 풀린 따뜻한 번짐. 정정 ②: 매끈한 벡터 면 금지 — 경계를 풀어 준다.
    (core 는 옛 호출부 호환용으로 남겨 두고 쓰지 않는다 — 감쇠는 반지름이 정한다)"""
    q = [Vector((-rx, 0, -rz)), Vector((rx, 0, -rz)), Vector((rx, 0, rz)), Vector((-rx, 0, rz))]
    o = DOME.mesh_of_quads("PRV_warm_" + name, [q], warm_mat("warmm_" + name, hexc, alpha, rx, rz))
    o.name = "PRV_warm_" + name
    o.location = (cx, y, cz)
    return o


def hxcap(hue, f, cap=0.90):
    """밝게 올리되 날아가지 않게. 크림·뼈 방이 하얗게 타는 것을 막는다."""
    h = hx(hue, f).lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum > cap:
        r, g, b = (c * (cap / lum) for c in (r, g, b))
    return "#%02x%02x%02x" % tuple(int(c * 255) for c in (r, g, b))


def warm_room(x0, x1, z0, hue, rid):
    """방 하나를 통째로 데우는 빛(정정 ①). **원 모양이 보이면 실패다** —
    빛은 도형이 아니라 방 전체의 온도여야 한다. 그래서 방을 다 덮는 낮은 알파 한 겹으로
    깔고, 밝기 차이는 room_shell 의 바탕색 자체가 이미 올려 두었다."""
    cx = (x0 + x1) / 2
    w = (x1 - x0)
    # 번짐은 **방 안에 갇혀 있어야** 한다. 물 쪽으로 새면 안개 뭉치로 읽혀
    # "바깥은 차갑고 검다"(합격 기준 ②)가 깨진다. 4차 렌더에서 실제로 그랬다.
    soft_blob(rid + "_all", cx, z0 + RH * 0.50, w * 0.54, RH * 0.62,
              hxcap(hue, 1.22), alpha=0.22, y=0.26)
    soft_blob(rid + "_back", cx, z0 + RH * 0.54, w * 0.50, RH * 0.56,
              hxcap(hue, 1.34), alpha=0.22, y=DEPTH - 0.08)


# ══════════════════════════════════════════════════════════════
# S6-B ②  생활의 흔적 — §7-4-2. 방마다 최소 5~6가지.
#         "오늘 밤 누가 여기서 잔다"(B4)를 그림으로 증명하는 물건들.
# ══════════════════════════════════════════════════════════════
def pot_steam(x, y, z, rid, r=0.42):
    """김이 오르는 냄비. 온기의 가장 직접적인 증거."""
    iso.cyl("pot_" + rid, (x, y, z + r * 0.62), r, r * 1.05, M["metal"], verts=14)
    iso.cyl("potlid_" + rid, (x, y, z + r * 1.22), r * 0.92, 0.07, M["frame_lt"], verts=14)
    iso.cube("pothdl_" + rid, (x + r * 1.15, y, z + r * 0.70), (0.30, 0.09, 0.07), M["frame_lt"])
    for k in range(4):                      # 김 — 위로 갈수록 크고 옅게
        soft_blob("steam_%s_%d" % (rid, k), x + math.sin(k * 1.7) * 0.22 * (k + 1),
                  z + r * 1.5 + k * 0.42, 0.26 + k * 0.13, 0.22 + k * 0.10,
                  "#FFF2DC", alpha=0.30 - k * 0.055, y=y - 0.18, core=0.55)


def hanging_cloth(x0, x1, z, rid, n=4, drop=0.70, y=0.28):
    """널어 둔 천. 줄 하나에 천 몇 장 — 사람이 오늘 빨래를 했다."""
    iso.cube("cline_" + rid, ((x0 + x1) / 2, y, z), (x1 - x0, 0.035, 0.035), M["frame_lt"])
    keys = ("fabric", "pillow", "fabric2", "tarp")
    for k in range(n):
        cx = x0 + (x1 - x0) * (k + 0.5) / n
        d = drop * (0.72 + 0.42 * ((k * 37) % 5) / 4.0)
        wq = 0.40 + 0.10 * (k % 3)
        DOME.mesh_of_quads("cloth_%s_%d" % (rid, k),
                           [[Vector((cx - wq, y + 0.02, z - d)), Vector((cx + wq, y + 0.02, z - d)),
                             Vector((cx + wq * 0.82, y + 0.02, z)), Vector((cx - wq * 0.82, y + 0.02, z))]],
                           M[keys[k % 4]])


def folded_stack(x, y, z, rid, n=3, w=0.62):
    """개어 둔 담요. 쓰지 않을 때도 자리를 지키는 물건이 방을 집으로 만든다."""
    keys = ("fabric", "tarp", "fabric2")      # 흰 베개천은 등불보다 밝아진다 — 천 계열로
    for k in range(n):
        iso.cube("fold_%s_%d" % (rid, k), (x + (0.03 if k % 2 else -0.03), y, z + 0.09 + k * 0.17),
                 (w * (1.0 - k * 0.06), w * 0.72, 0.16), M[keys[k % 3]])


def wall_notes(x, z, rid, n=4, seed=3):
    """벽에 붙인 종이. 셈한 날짜, 잊지 말 것, 아이가 그린 것."""
    rnd = random.Random(seed)
    for k in range(n):
        nx = x + (k - (n - 1) / 2.0) * 0.44 + rnd.uniform(-0.06, 0.06)
        nz = z + rnd.uniform(-0.18, 0.18)
        iso.cube("note_%s_%d" % (rid, k), (nx, DEPTH - 0.05, nz), (0.28, 0.03, 0.34),
                 M["paper"], rot=(0, rnd.uniform(-0.18, 0.18), 0))


def leaning_thing(x, z, rid, kind="plank", lean=0.20, h=1.5, y=0.30):
    """벽에 기대어 둔 물건. 세워 둔 것이 아니라 **놓아 둔** 것 — 사람이 방금 놓았다."""
    mt = {"plank": M["wood"], "pole": M["frame_lt"], "net": M["tarp"]}.get(kind, M["wood"])
    if kind == "pole":
        iso.cyl("lean_" + rid, (x, y, z + h / 2), 0.055, h, mt, rot=(0, lean, 0), verts=8)
    else:
        iso.cube("lean_" + rid, (x, y, z + h / 2), (0.28 if kind == "plank" else 0.46, 0.09, h),
                 mt, rot=(0, lean, 0))


def floor_shoes(x, y, z, rid):
    """바닥에 벗어 둔 신발 한 켤레. 이 방에 사람이 있다는 가장 조용한 증거."""
    for k, dx in enumerate((-0.16, 0.16)):
        iso.cube("shoe_%s_%d" % (rid, k), (x + dx, y, z + 0.075), (0.20, 0.34, 0.15),
                 M["wood_dk"], rot=(0, 0, 0.12 * (1 if k else -1)))
        iso.cube("shoetop_%s_%d" % (rid, k), (x + dx, y + 0.09, z + 0.18), (0.19, 0.16, 0.13),
                 M["wood_dk"], rot=(0, 0, 0.12 * (1 if k else -1)))


def cup_on(x, y, z, rid, n=2):
    """놓아 둔 컵. 조금 전까지 누가 앉아 있었다."""
    for k in range(n):
        iso.cyl("cup_%s_%d" % (rid, k), (x + k * 0.26, y, z + 0.07), 0.075, 0.14, M["paper"], verts=10)


def deco_rail(x, z, rid, filled=1, slots=3):
    """§7-4-4 **장식을 거는 자리.** E2 가문 도감 보상이 여기 걸린다.
    빈 고리가 보여야 '아직 걸 것이 남았다'가 읽히고, 방이 넓어지는 것이 아니라
    **따뜻해지는 것**으로 자란다."""
    w = 0.52 * slots
    iso.cube("rail_" + rid, (x, DEPTH - 0.07, z), (w, 0.05, 0.08), M["frame_lt"])
    for k in range(slots):
        hx_ = x - w / 2 + (k + 0.5) * w / slots
        iso.cyl("hook_%s_%d" % (rid, k), (hx_, DEPTH - 0.10, z - 0.10), 0.028, 0.17,
                M["frame_lt"], verts=6)
        if k < filled:                       # 걸려 있는 것 — 가문 실타래
            mk = M["red"] if k % 2 == 0 else M["yellow"]
            iso.cyl("skein_%s_%d" % (rid, k), (hx_, DEPTH - 0.12, z - 0.36), 0.15, 0.13,
                    mk, rot=(math.radians(90), 0, 0), verts=12)
            iso.cube("tail_%s_%d" % (rid, k), (hx_ + 0.05, DEPTH - 0.13, z - 0.62),
                     (0.05, 0.04, 0.30), mk, rot=(0, 0.18, 0))


def warm_rug(x, z, w, rid, d=1.15):
    """깔개. 바닥에 천이 깔린 방과 맨바닥인 방은 다른 방이다."""
    DOME.mesh_of_quads("rug_" + rid,
                       [[Vector((x - w / 2, DEPTH - d, z + 0.014)), Vector((x + w / 2, DEPTH - d, z + 0.014)),
                         Vector((x + w / 2 * 0.72, 0.10, z + 0.014)), Vector((x - w / 2 * 0.72, 0.10, z + 0.014))]],
                       M["fabric"])


def room_halo(x0, x1, z0, z1):
    """F7. 방 둘레의 어두운 여백(지적 4). 그라데이션이 아니라 **계단 세 칸**이다(§1-3).
    안쪽일수록 검고 바깥으로 갈수록 그 높이의 물색으로 돌아간다."""
    for mkey, mar, y in (("halo2", 1.45, 4.0), ("halo1", 0.72, 3.6)):
        q = [Vector((x0 - mar, y, z0 - mar)), Vector((x1 + mar, y, z0 - mar)),
             Vector((x1 + mar, y, z1 + mar)), Vector((x0 - mar, y, z1 + mar))]
        DOME.mesh_of_quads("PRV_halo", [q], M[mkey]).name = "PRV_halo"


# S8-C: dim<1 은 등불이 꺼진 방(플레이트의 "빈 방"). 색상은 그대로 두고 밝기만 내린다 —
#       꺼졌어도 그 방이 무슨 방인지는 색으로 읽혀야 한다(B1).
def room_shell(x0, x1, z0, hue, rid, dim=1.0):
    """절두각뿔 상자. 채색은 기본색 / 그림자색 딱 2단(§1-3). 방 안에 그라데이션 없음."""
    if COZY:
        # 정정 ①: 빛이 방 전체를 데운다. 그림자는 검정이 아니라 따뜻한 갈색.
        # 안팎 대비는 명도 극단이 아니라 **색온도**로 만든다 — 물은 그대로 차갑다.
        base = hx(hue, 1.00 * dim)
        floor_c = warm_shade(hue, 0.82 * dim, 0.26)      # 바닥은 빛이 고이는 곳이라 제일 밝은 그림자
        side_c = warm_shade(hue, 0.66 * dim, 0.40)
        ceil_c = warm_shade(hue, 0.54 * dim, 0.50)
    else:
        base = hx(hue, 0.88 * dim)                  # 기본색 — 등불보다 항상 어둡게 눌러 둔다(F7)
        floor_c = side_c = ceil_c = hx(hue, 0.46 * dim)
    shade = side_c
    backm = flat_mat("back_" + rid, base)
    floorm = flat_mat("floor_" + rid, floor_c)
    ceilm = flat_mat("ceil_" + rid, ceil_c)
    sidem = flat_mat("side_" + rid, side_c)
    z1 = z0 + RH
    room_halo(x0, x1, z0, z1)
    fx0, fx1, fz0, fz1 = x0, x1, z0, z1
    bx0, bx1, bz0, bz1 = x0 + INSET_X, x1 - INSET_X, z0 + INSET_ZB, z1 - INSET_ZT
    D = DEPTH
    quads = {
        "floor": [Vector((fx0, 0, fz0)), Vector((fx1, 0, fz0)), Vector((bx1, D, bz0)), Vector((bx0, D, bz0))],
        "ceil": [Vector((fx0, 0, fz1)), Vector((bx0, D, bz1)), Vector((bx1, D, bz1)), Vector((fx1, 0, fz1))],
        "left": [Vector((fx0, 0, fz0)), Vector((bx0, D, bz0)), Vector((bx0, D, bz1)), Vector((fx0, 0, fz1))],
        "right": [Vector((fx1, 0, fz0)), Vector((fx1, 0, fz1)), Vector((bx1, D, bz1)), Vector((bx1, D, bz0))],
    }
    DOME.mesh_of_quads("r_%s_floor" % rid, [quads["floor"]], floorm)
    DOME.mesh_of_quads("r_%s_ceil" % rid, [quads["ceil"]], ceilm)
    DOME.mesh_of_quads("r_%s_side" % rid, [quads["left"], quads["right"]], sidem)
    DOME.mesh_of_quads("r_%s_back" % rid, [[Vector((bx0, D, bz0)), Vector((bx1, D, bz0)),
                                            Vector((bx1, D, bz1)), Vector((bx0, D, bz1))]], backm)
    # F5. 장식 문양 — 뒷벽 위·아래 띠 두 줄
    pcol = M["pat_light"] if _is_dark(hue) else M["pat_dark"]
    if COZY:
        # 문양은 벽의 결이지 주인공이 아니다. 대비를 반쯤 낮춰 생활 소품이 먼저 읽히게 한다.
        pcol = mixhex(pcol, base, 0.48)
    pm = flat_mat("pat_m_" + rid, pcol)
    fn = MOTIF.get(rid, motif_dots)
    fn(rid, bx0 + 0.25, bx1 - 0.25, bz1 - 0.55, pm)
    fn(rid, bx0 + 0.25, bx1 - 0.25, bz0 + 0.09, pm)
    # 구조 테두리 — 방을 물에서 떼어 내는 장치(REF_CROSS_SECTION §1-3)
    fr = M["frame"]
    iso.cube("hull_b_%s" % rid, ((x0 + x1) / 2, D / 2 - 0.1, z0 - HULL / 2), (x1 - x0 + HULL * 2, D + 0.4, HULL), fr)
    iso.cube("hull_t_%s" % rid, ((x0 + x1) / 2, D / 2 - 0.1, z1 + HULL / 2), (x1 - x0 + HULL * 2, D + 0.4, HULL), fr)
    for sx in (x0 - HULL / 2, x1 + HULL / 2):
        iso.cube("hull_s_%s" % rid, (sx, D / 2 - 0.1, (z0 + z1) / 2), (HULL, D + 0.4, RH + HULL * 2), fr)
    for sx in (x0 + 0.5, x1 - 0.5):
        iso.cube("rib_%s" % rid, (sx, -0.06, (z0 + z1) / 2), (0.12, 0.12, RH), M["frame_lt"])
    return z0


def _is_dark(hexc):
    r, g, b = (int(hexc.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128


def room_lamp(x, z0, hue, rid, spread=1.0):
    """F7. 방마다 등불 하나(B1). 화면에서 가장 밝은 것은 언제나 이것이다.
    광원 오브젝트는 쓰지 않는다(평면 2단 고정) — 밝은 알과 바닥의 빛 웅덩이로 그린다."""
    top = z0 + RH
    iso.cyl("lw_" + rid, (x, 0.55, top - 0.18), 0.02, 0.36, M["frame"], rot=(math.radians(90), 0, 0))
    iso.cyl("ls_" + rid, (x, 0.55, top - 0.44), 0.22, 0.18, M["frame_lt"])
    if not COZY:
        # 등불 헤일로 — 평면 원 두 겹(§1-3 초판: 그라데이션 금지)
        disc("PRV_glow2_" + rid, x, top - 0.52, 1.05, M["glow_far"], y=0.50)
        disc("PRV_glow1_" + rid, x, top - 0.52, 0.52, M["glow_near"], y=0.49)
        o = iso.sphere("lb_" + rid, (x, 0.48, top - 0.52), 0.155, M["bulb"], 12, 7)
        o.name = "PRV_bulb_" + rid
        pw = 1.65
        qp = [Vector((x - pw, DEPTH - 0.55, z0 + 0.012)), Vector((x + pw, DEPTH - 0.55, z0 + 0.012)),
              Vector((x + pw * 0.62, 0.12, z0 + 0.012)), Vector((x - pw * 0.62, 0.12, z0 + 0.012))]
        DOME.mesh_of_quads("PRV_pool_" + rid, [qp],
                           flat_mat("poolm_" + rid, hx(hue, 1.34))).name = "PRV_pool_" + rid
        return
    # ── §7-4-1 빛이 번진다 ──────────────────────────────────
    # 계단 넷(민속화의 방식: 빛을 도형으로) + 가장자리를 푼 큰 번짐(정정 ②).
    zb = top - 0.52
    # ── 뒷벽에 쏟아지는 빛 ──────────────────────────────────
    # 정면 단면에서 깊이는 1.7m 뿐이라 **바닥은 거의 안 보인다.**
    # 그래서 빛이 번지는 자리는 뒷벽이다. 등불 밑에서 아래로 벌어지는 사다리꼴 —
    # 민속화가 빛을 그리는 방식(도형)이고, 가장자리는 번짐으로 푼다(정정 ②).
    yb = DEPTH - 0.055
    # 알파 0.2 로 30% 밝은 색을 얹으면 화면은 6% 밖에 안 밝아진다(3차 렌더가 그랬다).
    # 빛으로 읽히려면 색도 알파도 과감해야 한다.
    # spread<1 : 좁은 방(S8-C 플레이트 6m)에서 번짐이 방 밖 물로 새지 않게 가둔다.
    #            4차 전체 렌더에서 똑같은 일이 있었다 — 밖이 밝아지면 안팎 대비가 깨진다.
    for k, (wt, wb, f, a) in enumerate(((0.62, 3.35, 1.55, 0.34), (0.44, 2.05, 1.95, 0.42))):
        wt, wb = wt * spread, wb * spread
        q = [Vector((x - wt, yb - k * 0.008, zb - 0.10)), Vector((x + wt, yb - k * 0.008, zb - 0.10)),
             Vector((x + wb, yb - k * 0.008, z0 + 0.03)), Vector((x - wb, yb - k * 0.008, z0 + 0.03))]
        DOME.mesh_of_quads("PRV_cone%d_%s" % (k, rid), [q],
                           flat_mat("conem%d_%s" % (k, rid), hxcap(hue, f, 0.86), alpha=a)).name = \
            "PRV_cone%d_%s" % (k, rid)
    soft_blob(rid + "_wall", x, zb - 0.85, 3.6 * spread, 2.1, hxcap(hue, 1.95, 0.90), alpha=0.46,
              y=DEPTH - 0.075)
    # ── 등불 둘레의 공기 번짐 ───────────────────────────────
    soft_blob(rid + "_lampwide", x, zb - 0.95, 2.9 * spread, 1.80, "#FFC57E", alpha=0.36, y=0.62)
    soft_blob(rid + "_lamp", x, zb - 0.10, 1.55 * spread, 1.25, "#FFE2B2", alpha=0.56, y=0.54)
    soft_blob(rid + "_core", x, zb, 0.60, 0.56, "#FFF6E4", alpha=0.85, y=0.52)
    o = iso.sphere("lb_" + rid, (x, 0.44, zb), 0.15, M["bulb"], 12, 7)
    o.name = "PRV_bulb_" + rid
    # ── 바닥에 고이는 빛 웅덩이 (보이는 만큼만) ─────────────
    for k, (pw, f, a) in enumerate(((2.45, 1.50, 0.55), (1.45, 1.85, 0.48))):
        pw *= spread
        zz = z0 + 0.010 + k * 0.004
        qp = [Vector((x - pw, DEPTH - 0.50, zz)), Vector((x + pw, DEPTH - 0.50, zz)),
              Vector((x + pw * 0.60, 0.10, zz)), Vector((x - pw * 0.60, 0.10, zz))]
        DOME.mesh_of_quads("PRV_pool%d_%s" % (k, rid), [qp],
                           flat_mat("poolm%d_%s" % (k, rid), hxcap(hue, f, 0.86), alpha=a)).name = \
            "PRV_pool%d_%s" % (k, rid)


def disc(name, x, z, r, m, y=0.45, verts=14):
    """카메라를 향한 평면 다각형. 빛을 그라데이션이 아니라 도형으로 그린다(§1-3)."""
    o = iso.cyl(name, (x, y, z), r, 0.02, m, rot=(math.radians(90), 0, 0), verts=verts)
    o.name = name
    return o


def people(xs, z0, kinds, ys=None):
    if NO_PEOPLE:                        # S8-C (1)
        return
    for i, (x, k) in enumerate(zip(xs, kinds)):
        y = (ys[i] if ys else 0.55 + (i % 3) * 0.32)
        DOME.resident(k, x, y, z0, rot_z=math.radians(180 + (-22 if i % 2 else 20)), h=1.70)


# ══════════════════════════════════════════════════════════════
# S6-B ③  쉬는 자세 — §7-4-3. 전부 서서 일하지 않는다. 앉고 기대고 눕는다.
#         인물은 캐릭터 담당의 정면 스프라이트를 그대로 쓴다(화풍 일치).
#         변형 경로는 한 곳에서만 바뀐다 — 담당이 `d` 를 내면 CHAR_VAR 만 고친다.
# ══════════════════════════════════════════════════════════════
CHAR_VAR = os.environ.get("RELIC_CHAR_VAR", "c")
CHAR_ROOT = os.path.join(ROOT, "static", "art", "chars", "front")
CHAR_FALLBACK = ("c", "b", "a")

# ============================================================
# S8-C (1)  사람 없는 플레이트
#   2026-10-01 결정: 2.5D — 배경은 3D 렌더, 캐릭터는 P2 48px 도트.
#   그래서 배경 렌더에는 이제 사람을 넣지 않는다. 사람은 개발이 도트로 얹는다.
#   RELIC_CHAR_VAR=none  ->  char()/people() 이 아무것도 만들지 않는다.
#   빠지는 것은 사람뿐이다. 방석/요/덮은 담요/신발 같은 생활 흔적은 그대로 둔다
#   (B4 "오늘 밤 누가 여기서 잔다"는 사람이 없어도 성립해야 한다).
# ============================================================
NO_PEOPLE = CHAR_VAR.strip().lower() in ("none", "no", "off", "0", "")


def char_meta():
    try:
        return json.load(open(os.path.join(CHAR_ROOT, "front_meta.json"), encoding="utf-8"))
    except Exception:
        return {"cell": 256, "ppm": 110.0, "baseline": 240, "frames": 5,
                "rows": {"Idle": 0, "Walk": 1, "PickUp": 2}}


CM = char_meta()
CELL = float(CM.get("cell", 256))
PPM = float(CM.get("ppm", 110.0))
BASE_PX = float(CM.get("baseline", 240))
NFRAME = int(CM.get("frames", 5))
ROWS = CM.get("rows", {"Idle": 0, "Walk": 1, "PickUp": 2})
NROW = max(3, max(ROWS.values()) + 1)
SP_H = CELL / PPM                      # 셀 한 칸의 실제 크기(m)
SP_FOOT = (CELL - BASE_PX) / PPM       # 셀 바닥에서 발 기준선까지(m)
_IMG = {}


def char_image(role):
    for var in ([CHAR_VAR] + [v for v in CHAR_FALLBACK if v != CHAR_VAR]):
        p = os.path.join(CHAR_ROOT, var, role + ".png")
        if os.path.exists(p):
            if p not in _IMG:
                _IMG[p] = bpy.data.images.load(p, check_existing=True)
            return _IMG[p]
    return None


def sprite_mat(name, img, frame, row, tint):
    """스프라이트 한 칸. 이미 2단 음영이 구워져 있으므로 셰이딩하지 않고,
    방의 등불색을 곱해서 **인물이 그 빛 안에 잠기게** 한다(정정 ①)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0 / NFRAME, 1.0 / NROW, 1.0)
    mp.inputs["Location"].default_value = (frame / NFRAME, 1.0 - (row + 1) / NROW, 0.0)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img; tex.extension = 'CLIP'; tex.interpolation = 'Linear'
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs["Factor"].default_value = 1.0
    mul.inputs[7].default_value = (*tint, 1.0)
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], mul.inputs[6])
    nt.links.new(mul.outputs[2], em.inputs[0])
    nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    _blend(m)
    return _mark(m)


def char(role, x, zfeet, y=0.62, pose="stand", frame=0, tint=(1.0, 0.94, 0.82),
         flip=False, sc=1.0, tilt=0.0):
    """pose: stand(서서) / work(일하는) / walk / sit(앉은) / lean(기댄) / lie(누운)"""
    if NO_PEOPLE:                     # S8-C (1)
        return None
    img = char_image(role)
    if img is None:
        return None
    row = {"stand": ROWS.get("Idle", 0), "sit": ROWS.get("Idle", 0), "lean": ROWS.get("Idle", 0),
           "lie": ROWS.get("Idle", 0), "walk": ROWS.get("Walk", 1),
           "work": ROWS.get("PickUp", 2)}.get(pose, 0)
    rot = {"lean": 0.22, "lie": math.radians(80.0)}.get(pose, 0.0) + tilt
    if flip:
        rot = -rot
    w = h = SP_H * sc
    foot = SP_FOOT * sc
    q = [Vector((-w / 2, 0, -foot)), Vector((w / 2, 0, -foot)),
         Vector((w / 2, 0, -foot + h)), Vector((-w / 2, 0, -foot + h))]
    mname = "sp_%s_%s_%d_%d" % (role, pose, frame, int(x * 37) & 0xFFF)
    mt = sprite_mat(mname, img, frame % NFRAME, row, tint)
    if flip:
        mt.node_tree.nodes["Mapping"].inputs["Scale"].default_value = (-1.0 / NFRAME, 1.0 / NROW, 1.0)
        mt.node_tree.nodes["Mapping"].inputs["Location"].default_value = \
            ((frame % NFRAME + 1) / NFRAME, 1.0 - (row + 1) / NROW, 0.0)
    o = mesh_uv_quads("PRV_sp_%s_%d" % (role, int(x * 41) & 0xFFFF), [q], mt)
    o.name = "PRV_sp_%s_%d" % (role, int(x * 41) & 0xFFFF)
    o.location = (x, y, zfeet + (0.26 * sc if pose == "lie" else 0.0))
    o.rotation_euler = (0, rot, 0)
    return o


def seat_block(x, y, z, w=0.80, h=0.42, m=None):
    """앉은 사람의 다리를 가려 주는 방석·걸상. 스프라이트를 앉은 것으로 읽히게 하는 장치."""
    iso.cube("seatb_%d" % (int(x * 53) & 0xFFFF), (x, y, z + h / 2), (w, 0.62, h), m or M["fabric2"])


# ══════════════════════════════════════════════════════════════
# 방 내용물 — F4: 전부 묘사하지 않는다. 상징적 소품 몇 개로 충분하다.
# ══════════════════════════════════════════════════════════════
def at(z, fn, *a, **k):
    DOME.at(z, fn, *a, **k)


def fill_quarters(x0, x1, z0):
    c = (x0 + x1) / 2
    for dx in (-4.4, -2.6, 2.4, 4.3):
        at(z0, iso.bedroll, c + dx, 1.05, math.radians(90))
    at(z0, iso.laundry, (c - 5.0, 0.35), (c + 1.0, 0.35), 2.45)
    at(z0, iso.plant, c - 5.4, 0.55, 0.6)
    at(z0, iso.shelf_unit, c + 1.2, 1.15)
    at(z0, iso.jug, c - 1.2, 0.5, 0.3)
    iso.prop("k:chest", c - 0.4, 1.2, z0, h=0.55, rot_z=0.2)
    iso.cube("table", (c + 2.9, 0.85, z0 + 0.25), (1.5, 0.8, 0.07), M["wood"])


def fill_greenhouse(x0, x1, z0):
    c = (x0 + x1) / 2
    rnd = random.Random(77)
    for k in range(3):
        iso.cube("bed", (c - 1.7 + k * 1.7, 1.1, z0 + 0.32), (1.4, 1.0, 0.64), M["wood_dk"])
        iso.cube("soil", (c - 1.7 + k * 1.7, 1.1, z0 + 0.66), (1.26, 0.9, 0.06), M["earth2"])
    for k in range(10):
        gx = c - 1.7 + (k % 3) * 1.7 + rnd.uniform(-0.4, 0.4)
        at(z0 + 0.69, iso.plant, gx, 1.1 + rnd.uniform(-0.3, 0.3), rnd.uniform(0.34, 0.58), False)
    at(z0, iso.plant, c - 2.5, 0.5, 0.7)
    at(z0, iso.jug, c + 1.5, 0.45, -0.3)
    iso.prop("k:bucket", c - 0.9, 0.45, z0, h=0.32, rot_z=0.4)


def fill_workshop(x0, x1, z0):
    c = (x0 + x1) / 2
    iso.prop("k:workbench", c - 1.4, 1.25, z0, h=1.0, rot_z=0.0)
    iso.prop("k:workbench-anvil", c + 1.5, 1.25, z0, h=1.0, rot_z=0.0)
    iso.prop("k:barrel", c + 2.5, 0.55, z0, h=0.85)
    at(z0, iso.can_pile, c - 0.6, 0.45, 3, 5)
    for k in range(5):
        iso.cube("hook", (c - 2.0 + k * 0.72, DEPTH - 0.12, z0 + 2.1 + (k % 3) * 0.13),
                 (0.1, 0.05, 0.36), M["metal"] if k % 2 else M["copper"])
    iso.cube("bench", (c, 0.85, z0 + 0.88), (3.0, 0.8, 0.08), M["wood"])


def fill_storage(x0, x1, z0):
    c = (x0 + x1) / 2
    for dx in (-1.9, 0.2, 2.1):
        at(z0, iso.shelf_unit, c + dx, 1.35)
    for dx, rows, sd in ((-1.3, 3, 1), (0.4, 3, 4), (1.7, 2, 8)):
        at(z0, iso.can_pile, c + dx, 0.45, rows, sd)
    iso.prop("k:box-large", c - 2.5, 0.55, z0, h=0.72, rot_z=0.15)
    iso.prop("k:barrel", c + 2.6, 0.5, z0, h=0.85)
    at(z0, iso.jug, c - 0.6, 0.4, 0.2)


def fill_library(x0, x1, z0):
    c = (x0 + x1) / 2
    rnd = random.Random(31)
    for lv in range(3):
        iso.cube("bshelf", (c, DEPTH - 0.24, z0 + 0.5 + lv * 0.78), (x1 - x0 - 2.6, 0.32, 0.07), M["wood"])
        for k in range(12):
            h = 0.24 + rnd.random() * 0.14
            iso.cube("book", (c - (x1 - x0 - 3.0) / 2 + k * (x1 - x0 - 3.0) / 11, DEPTH - 0.24,
                              z0 + 0.54 + lv * 0.78 + h / 2), (0.19, 0.28, h),
                     M[("red", "yellow", "paper", "wood_dk")[k % 4]])
    iso.cube("desk", (c - 0.6, 0.75, z0 + 0.74), (1.8, 0.9, 0.08), M["wood"])
    for sx in (-0.85, 0.85):
        iso.cube("dleg", (c - 0.6 + sx, 0.75, z0 + 0.37), (0.09, 0.85, 0.74), M["wood_dk"])
    iso.cube("openbook", (c - 0.6, 0.75, z0 + 0.81), (0.5, 0.36, 0.05), M["paper"], rot=(0, 0, 0.2))


def fill_bath(x0, x1, z0):
    """민물 목욕탕. 물이지만 사람이 쓰는 물이라 청록을 주지 않는다(§5의 '청록은 바다에만')."""
    c = (x0 + x1) / 2
    iso.cube("tub", (c - 0.5, 1.05, z0 + 0.42), (3.4, 1.5, 0.84), M["tile"])
    iso.cube("tubw", (c - 0.5, 1.05, z0 + 0.76), (3.2, 1.34, 0.2), M["freshwater"])
    at(z0, iso.laundry, (c - 2.4, 0.35), (c + 2.4, 0.35), 2.5)
    iso.prop("k:bucket", c + 2.2, 0.45, z0, h=0.34, rot_z=0.3)
    for k in range(3):
        iso.cube("towel", (c + 1.3 + k * 0.55, 0.45, z0 + 0.13), (0.45, 0.34, 0.26),
                 M["pillow"] if k % 2 else M["fabric2"], rot=(0, 0, k * 0.3))


def fill_airlock(x0, x1, z0):
    c = (x0 + x1) / 2
    iso.cyl("hatch", (x1 - 0.55, 1.0, z0 + 1.15), 0.95, 0.5, M["frame_lt"], rot=(0, math.radians(90), 0), verts=18)
    iso.cyl("hatchin", (x1 - 0.55, 1.0, z0 + 1.15), 0.78, 0.6, M["frame"], rot=(0, math.radians(90), 0), verts=18)
    for k in range(6):
        a = math.radians(60 * k)
        iso.cube("bolt", (x1 - 0.42, 1.0 + 0.82 * math.cos(a), z0 + 1.15 + 0.82 * math.sin(a)),
                 (0.1, 0.13, 0.13), M["frame_lt"])
    for k in range(5):
        sx = c - 1.9 + k * 0.62
        iso.cube("suit", (sx, DEPTH - 0.34, z0 + 1.25), (0.4, 0.34, 1.4), M["tarp"] if k % 2 else M["fabric2"])
        iso.cyl("helm", (sx, DEPTH - 0.34, z0 + 2.06), 0.2, 0.26, M["frame_lt"], verts=12)
    iso.cube("rack", (c, DEPTH - 0.22, z0 + 2.3), (3.4, 0.1, 0.1), M["frame_lt"])
    for k in range(3):
        iso.cube("haul", (c + 1.3 + k * 0.38, 0.45, z0 + 0.15), (0.3, 0.26, 0.3),
                 M[("packet_y", "packet_r", "packet_y")[k]], rot=(0, 0, k * 0.6))


def fill_lounge(x0, x1, z0):
    c = (x0 + x1) / 2
    iso.cube("rug", (c, 1.0, z0 + 0.03), (4.4, 1.5, 0.06), M["fabric"])
    for k, dx in enumerate((-1.7, 0.0, 1.7)):
        iso.cube("seat", (c + dx, 1.05, z0 + 0.28), (0.9, 0.85, 0.48), M["fabric2"] if k % 2 else M["fabric"])
        iso.cube("sback", (c + dx, 1.42, z0 + 0.68), (0.9, 0.16, 0.54), M["fabric2"] if k % 2 else M["fabric"])
    iso.cyl("table", (c, 0.55, z0 + 0.44), 0.5, 0.07, M["wood"], verts=16)
    iso.cyl("tleg", (c, 0.55, z0 + 0.21), 0.1, 0.42, M["wood_dk"], verts=10)
    at(z0, iso.plant, c - 3.0, 0.55, 0.72)
    at(z0, iso.plant, c + 3.0, 0.55, 0.62)
    for k in range(6):
        iso.cyl("rp", (c - 2.5 + k * 1.0, 0.16, z0 + 0.5), 0.05, 1.0, M["frame_lt"], verts=8)
    iso.cube("rt", (c, 0.16, z0 + 1.0), (5.4, 0.1, 0.1), M["frame_lt"])


# ══════════════════════════════════════════════════════════════
# S6-B ④  E1 — 찍은 물건이 선반에 쌓인다
#   static/art/props/ 의 34종을 그대로 창고 선반에 얹는다.
#   "내가 어제 편의점에서 찍은 그 라면이 저 선반에 있다"(PLAYER_JOURNEY §2 E1)
# ══════════════════════════════════════════════════════════════
PROPS_DIR = os.path.join(ROOT, "static", "art", "props")
PCELL_W, PCELL_H = 0.44, 0.388          # 격자 한 칸(34×30px)이 방 안에서 갖는 크기(m)
_PMETA = None


def props_meta():
    global _PMETA
    if _PMETA is None:
        try:
            _PMETA = json.load(open(os.path.join(PROPS_DIR, "props_meta.json"), encoding="utf-8"))
        except Exception:
            _PMETA = {"props": {}}
    return _PMETA


def png_sprite(name, path, cx, zbase, y, w, h):
    if not os.path.exists(path):
        return None
    if path not in _IMG:
        _IMG[path] = bpy.data.images.load(path, check_existing=True)
    m = bpy.data.materials.new("pm_" + name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _IMG[path]; tex.extension = 'CLIP'; tex.interpolation = 'Linear'
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], em.inputs[0])
    nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    _blend(m); _mark(m)
    q = [Vector((cx - w / 2, y, zbase)), Vector((cx + w / 2, y, zbase)),
         Vector((cx + w / 2, y, zbase + h)), Vector((cx - w / 2, y, zbase + h))]
    o = mesh_uv_quads("PRV_sp_prop_" + name, [q], m)
    o.name = "PRV_sp_prop_" + name
    return o


SHELF_ROWS = [
    ["prop_noodle_box", "prop_dry_jar", "prop_seed_sack", "prop_long_neck_bottle",
     "prop_cap_heap", "prop_crisp_bundle"],
    ["prop_empty_bottle_row", "prop_twelve_cell_box", "prop_white_crock", "prop_cell_tin",
     "prop_stick_bundle", "prop_flat_canteen", "prop_brown_vial"],
    ["prop_folded_cloth", "prop_stacked_books", "prop_nameless_box", "prop_foil_bundle",
     "prop_single_boot", "prop_rolled_strips", "prop_unread_lump"],
]


def shelf_props(x0, x1, z0, rid, rows=None, z_first=0.30, step=0.74):
    """창고 뒷벽의 선반 세 단. 여기가 바코드와 거점이 만나는 자리다."""
    meta = props_meta().get("props", {})
    bx0, bx1 = x0 + INSET_X + 0.30, x1 - INSET_X - 0.30
    for lv, row in enumerate(rows or SHELF_ROWS):
        zb = z0 + z_first + lv * step
        iso.cube("pshelf_%s_%d" % (rid, lv), ((bx0 + bx1) / 2, DEPTH - 0.26, zb - 0.055),
                 (bx1 - bx0 + 0.24, 0.40, 0.11), M["wood"])
        x = bx0 + 0.06
        for pid in row:
            info = meta.get(pid)
            if info is None:
                continue
            w = PCELL_W * int(info.get("slots", 1))
            if x + w > bx1:
                break
            png_sprite("%s_%s" % (rid, pid), os.path.join(PROPS_DIR, "x4", pid + ".png"),
                       x + w / 2, zb, DEPTH - 0.30, w, PCELL_H)
            x += w + 0.055


# ══════════════════════════════════════════════════════════════
# S6-B ⑤  방마다 생활의 흔적 5~6가지 + 쉬는 사람 (§7-4-2·3)
# ══════════════════════════════════════════════════════════════
def cozy_fill(rid, x0, x1, z0, hue):
    c = (x0 + x1) / 2
    if rid == "quarters":
        folded_stack(c - 3.5, 0.55, z0, rid, 3, 0.66)
        folded_stack(c + 3.6, 0.50, z0, rid + "b", 2, 0.58)
        hanging_cloth(c + 1.8, c + 5.4, z0 + 2.48, rid, 4, 0.66, y=0.30)
        wall_notes(c - 2.2, z0 + 2.00, rid, 5, 11)
        floor_shoes(c - 4.9, 0.40, z0, rid)
        floor_shoes(c + 2.2, 0.36, z0, rid + "b")
        pot_steam(c + 5.1, 0.52, z0 + 0.32, rid, 0.34)
        iso.cube("nstand", (c + 5.1, 0.52, z0 + 0.16), (0.7, 0.62, 0.32), M["wood_dk"])
        cup_on(c + 2.6, 0.72, z0 + 0.30, rid)
        deco_rail(c - 0.2, z0 + 2.34, rid, filled=1, slots=3)
        warm_rug(c - 3.4, z0, 3.0, rid)
        at(z0, iso.plant, c + 6.2, 0.45, 0.58)
    elif rid == "lounge":
        warm_rug(c, z0, 5.2, rid, d=1.25)
        folded_stack(c + 2.35, 0.75, z0 + 0.52, rid, 2, 0.50)
        cup_on(c - 0.35, 0.40, z0 + 0.48, rid, 3)
        wall_notes(c - 3.1, z0 + 2.05, rid, 4, 5)
        deco_rail(c + 2.9, z0 + 2.18, rid, filled=2, slots=3)
        hanging_cloth(c - 4.4, c - 2.2, z0 + 2.42, rid, 2, 0.50, y=0.26)
        floor_shoes(c - 2.3, 0.34, z0, rid)
        pot_steam(c + 0.9, 0.42, z0 + 0.48, rid, 0.26)
    elif rid == "greenhouse":
        hanging_cloth(c - 2.6, c + 0.4, z0 + 2.50, rid, 3, 0.52, y=0.24)   # 말리는 씨앗 주머니
        wall_notes(c + 2.2, z0 + 2.05, rid, 4, 23)
        leaning_thing(x1 - 1.1, z0, rid, "pole", 0.22, 1.7, 0.34)
        floor_shoes(x0 + 1.5, 0.34, z0, rid)
        folded_stack(x1 - 1.9, 0.48, z0, rid, 2, 0.46)
        cup_on(c + 2.4, 0.42, z0 + 0.02, rid, 1)
        deco_rail(c - 2.9, z0 + 2.30, rid, filled=1, slots=2)
    elif rid == "workshop":
        wall_notes(c - 2.6, z0 + 1.55, rid, 5, 41)
        leaning_thing(x0 + 0.95, z0, rid, "plank", 0.19, 2.0, 0.34)
        leaning_thing(x0 + 1.45, z0, rid + "b", "pole", 0.15, 1.6, 0.26)
        folded_stack(c + 2.9, 0.44, z0, rid, 2, 0.44)                       # 개어 둔 걸레
        cup_on(c - 1.6, 0.52, z0 + 0.93, rid)
        pot_steam(c + 1.9, 0.48, z0 + 0.93, rid, 0.24)
        floor_shoes(c - 2.9, 0.34, z0, rid)
        deco_rail(c + 2.3, z0 + 2.30, rid, filled=1, slots=3)
    elif rid == "storage":
        shelf_props(x0, x1, z0, rid)
        wall_notes(c + 2.5, z0 + 2.70, rid, 4, 61)
        folded_stack(x0 + 1.3, 0.46, z0, rid, 3, 0.52)
        floor_shoes(x1 - 1.6, 0.34, z0, rid)
        cup_on(c - 0.1, 0.40, z0 + 0.02, rid, 1)
        leaning_thing(x0 + 0.85, z0, rid, "plank", 0.16, 1.5, 0.30)
        deco_rail(c - 2.2, z0 + 2.72, rid, filled=1, slots=2)
    elif rid == "library":
        cup_on(c - 0.9, 0.55, z0 + 0.80, rid, 2)
        wall_notes(c + 1.9, z0 + 2.45, rid, 3, 77)
        folded_stack(c + 1.9, 0.48, z0, rid, 2, 0.46)
        floor_shoes(c - 2.0, 0.34, z0, rid)
        at(z0, iso.plant, c + 2.3, 0.46, 0.52)
        deco_rail(c - 1.6, z0 + 2.45, rid, filled=2, slots=2)
        warm_rug(c - 0.6, z0, 2.4, rid, d=0.95)
    elif rid == "bath":
        for k in range(5):                       # 김 — 목욕탕의 온기
            soft_blob("bathsteam%d" % k, c - 1.6 + k * 0.85, z0 + 1.35 + (k % 3) * 0.32,
                      0.62 + (k % 3) * 0.16, 0.48 + (k % 2) * 0.16, "#FFF2DC",
                      alpha=0.24, y=0.24, core=0.52)
        folded_stack(c + 2.6, 0.48, z0, rid, 3, 0.50)
        wall_notes(c - 2.9, z0 + 2.20, rid, 3, 97)
        floor_shoes(c - 2.6, 0.36, z0, rid)
        cup_on(c - 1.9, 0.44, z0 + 0.88, rid, 1)
        at(z0, iso.plant, c + 3.1, 0.44, 0.50)
        deco_rail(c + 0.4, z0 + 2.36, rid, filled=1, slots=2)
    elif rid == "airlock":
        wall_notes(x0 + 1.5, z0 + 2.05, rid, 5, 13)                          # 나간 날 셈
        floor_shoes(c - 2.4, 0.36, z0, rid)
        folded_stack(c - 0.4, 0.44, z0, rid, 2, 0.48)
        hanging_cloth(c - 2.6, c + 0.2, z0 + 2.72, rid, 3, 0.44, y=0.24)     # 말리는 천
        cup_on(x0 + 0.9, 0.44, z0 + 0.02, rid, 1)
        leaning_thing(x0 + 0.7, z0, rid, "pole", 0.17, 1.6, 0.28)
        pot_steam(x0 + 1.9, 0.46, z0 + 0.02, rid, 0.28)


# (역할, 화면 x 비율, 자세, 프레임, 깊이 y, 좌우반전, 크기)
COZY_CAST = {
    "quarters": [("scholar", 0.10, "lie", 0, 0.95, False, 1.00),
                 ("medic", 0.34, "sit", 1, 0.60, False, 1.00),
                 ("cook", 0.58, "work", 3, 0.48, True, 1.00),
                 ("kid", 0.76, "sit", 2, 0.42, False, 0.86),
                 ("trader", 0.90, "stand", 0, 0.66, True, 1.00)],
    "lounge": [("farmer", 0.28, "sit", 0, 0.42, False, 1.00),
               ("scholar", 0.50, "sit", 2, 0.40, True, 1.00),
               ("kid", 0.66, "lie", 0, 0.34, False, 0.86),
               ("trader", 0.84, "lean", 1, 0.62, True, 1.00)],
    "greenhouse": [("farmer", 0.24, "work", 2, 0.46, False, 1.00),
                   ("kid", 0.52, "sit", 0, 0.42, True, 0.86),
                   ("medic", 0.80, "stand", 1, 0.62, True, 1.00)],
    "workshop": [("engineer", 0.24, "work", 3, 0.46, False, 1.00),
                 ("scout", 0.52, "sit", 0, 0.40, True, 1.00),
                 ("trader", 0.79, "work", 1, 0.58, True, 1.00)],
    "storage": [("trader", 0.22, "work", 2, 0.44, False, 1.00),
                ("kid", 0.78, "sit", 1, 0.40, True, 0.86)],
    "library": [("scholar", 0.34, "sit", 0, 0.44, False, 1.00),
                ("medic", 0.70, "lean", 2, 0.58, True, 1.00)],
    "bath": [("cook", 0.26, "sit", 1, 0.40, False, 1.00),
             ("farmer", 0.54, "stand", 0, 0.64, True, 1.00),
             ("kid", 0.80, "sit", 3, 0.38, False, 0.86)],
    "airlock": [("scout", 0.26, "stand", 2, 0.44, False, 1.00),
                ("engineer", 0.52, "work", 0, 0.60, True, 1.00),
                ("medic", 0.80, "sit", 1, 0.40, False, 1.00)],
}


def cozy_people(rid, x0, x1, z0, hue):
    """§7-4-3. 앉고 기대고 눕는 사람을 섞는다. 전부 서서 일하는 방은 일터지 집이 아니다."""
    tint = tuple(min(1.0, v) for v in (1.0, 0.93, 0.80))
    for role, t, pose, fr, y, flip, sc in COZY_CAST.get(rid, []):
        x = x0 + (x1 - x0) * t
        zf = z0
        if pose == "sit":
            zf = z0 - 0.40 * sc              # 다리를 방석 뒤로 내려 앉은 키를 만든다
            seat_block(x, y - 0.30, z0, 0.86 * sc, 0.40, M["fabric2"])
        elif pose == "lie":
            zf = z0 + 0.10
            iso.cube("mat_%s_%s" % (rid, role), (x + 0.75, y + 0.10, z0 + 0.09),
                     (2.3, 0.85, 0.18), M["fabric"])
        char(role, x, zf, y=y, pose=pose, frame=fr, tint=tint, flip=flip, sc=sc)
        if pose == "lie":                    # 덮은 담요 — 누운 사람 위로
            iso.cube("blank_%s_%s" % (rid, role), (x + 0.42, y - 0.22, z0 + 0.30),
                     (1.5, 0.52, 0.44), M["pillow"], rot=(0, 0.06, 0))


# ══════════════════════════════════════════════════════════════
# 유리 척추 · 돔 · 굴착면
# ══════════════════════════════════════════════════════════════
def spine(z_top, z_bot):
    """수직 통로. 지적 5: 채도를 크게 낮췄다. 숯검정 골조 + 좁은 황토 띠 하나."""
    iso.cube("spine_back", (0, DEPTH + 0.15, (z_top + z_bot) / 2), (SPINE * 2 - 0.3, 0.2, z_top - z_bot),
             flat_mat("spine_back_m", "#2A2119"))
    iso.cube("spine_strip", (0, DEPTH + 0.05, (z_top + z_bot) / 2), (0.5, 0.1, z_top - z_bot),
             flat_mat("spine_strip_m", hx(PAL["ochre_d"], 0.9)))
    for sx in (-SPINE, SPINE):
        iso.cube("spine_col", (sx, DEPTH / 2, (z_top + z_bot) / 2), (0.30, DEPTH + 0.5, z_top - z_bot), M["frame"])
        iso.cube("spine_rib", (sx, -0.05, (z_top + z_bot) / 2), (0.13, 0.13, z_top - z_bot), M["frame_lt"])
    n = int((z_top - z_bot) / 0.55)
    for k in range(n):
        iso.cube("srung", (0, 0.95, z_bot + 0.3 + k * 0.55), (1.5, 0.1, 0.07), M["frame_lt"])
    for zz in (L[1], L[2], L[3], L[4]):
        iso.cube("landing", (0, DEPTH / 2, zz - 0.18), (SPINE * 2 - 0.3, DEPTH + 0.2, 0.22), M["frame_lt"])
    cz = L[3] + 1.1
    iso.cube("cage", (0, 0.72, cz), (2.2, 0.9, 2.2), flat_mat("Cage", PAL["ochre"], alpha=0.22))
    for dz in (-1.1, 1.1):
        iso.cube("cagef", (0, 0.72, cz + dz), (2.4, 1.0, 0.14), M["frame_lt"])
    o = iso.sphere("cagelamp", (0, 0.45, cz + 0.85), 0.11, M["bulb"], 10, 6); o.name = "PRV_bulb_cage"


def glass_dome(rooms_z):
    C, R = DOME_C, DOME_R
    g = flat_mat("SecGlass", "#123544", alpha=0.30)
    seg = 40
    quads = []
    for k in range(seg):
        a0 = 2 * math.pi * k / seg; a1 = 2 * math.pi * (k + 1) / seg
        quads.append([C + Vector((0, DEPTH + 0.1, 0)),
                      C + Vector((R * math.cos(a0), DEPTH + 0.1, R * math.sin(a0))),
                      C + Vector((R * math.cos(a1), DEPTH + 0.1, R * math.sin(a1))),
                      C + Vector((0, DEPTH + 0.1, 0))])
    DOME.mesh_of_quads("dome_backglass", quads, g)
    for k in range(seg):
        a0 = 2 * math.pi * k / seg; a1 = 2 * math.pi * (k + 1) / seg
        p0 = C + Vector((R * math.cos(a0), -0.12, R * math.sin(a0)))
        p1 = C + Vector((R * math.cos(a1), -0.12, R * math.sin(a1)))
        DOME.strut("domerim", p0, p1, 0.16, M["frame_lt"], 6)
    for k in range(4):
        a = math.radians(45 + 45 * k)
        DOME.strut("domerib", C + Vector((0.4 * math.cos(a), 0.0, 0.4 * math.sin(a))),
                   C + Vector((R * math.cos(a), 0.0, R * math.sin(a))), 0.055, M["frame"], 5)
    iso.cyl("domecap", (0, DEPTH / 2, C.z + R + 0.35), 0.9, 0.7, M["frame_lt"], verts=14)
    disc("PRV_glow2_beacon", 0, C.z + R + 0.9, 1.35, M["glow_far"], y=0.32)
    disc("PRV_glow1_beacon", 0, C.z + R + 0.9, 0.62, M["glow_near"], y=0.31)
    o = iso.sphere("beacon", (0, 0.30, C.z + R + 0.9), 0.24, M["bulb"], 10, 6)
    o.name = "PRV_bulb_beacon"


def dig_face(x0, x1, z0):
    """아래로 자란다 — 굴착 중인 다음 칸. 빈 방이 아니라 공사장."""
    fr = M["frame"]
    room_halo(x0, x1, z0, z0 + RH)
    iso.cube("dig_b", ((x0 + x1) / 2, DEPTH / 2, z0 - HULL / 2), (x1 - x0 + HULL * 2, DEPTH + 0.4, HULL), fr)
    for sx in (x0 - HULL / 2, x1 + HULL / 2):
        iso.cube("dig_s", (sx, DEPTH / 2, z0 + RH / 2), (HULL, DEPTH + 0.4, RH), fr)
    DOME.mesh_of_quads("dig_back", [[Vector((x0 + 0.4, DEPTH, z0)), Vector((x1 - 0.4, DEPTH, z0)),
                                     Vector((x1 - 0.4, DEPTH, z0 + RH)), Vector((x0 + 0.4, DEPTH, z0 + RH))]],
                       flat_mat("dig_back_m", "#241C15"))
    motif_slash("dig", x0 + 0.8, x1 - 0.8, z0 + 1.6, flat_mat("dig_pat", "#3A312A"))
    rnd = random.Random(9)
    for k in range(8):
        iso.cube("scaf", (x0 + 0.7 + k * 0.62, 0.9, z0 + 1.4), (0.1, 0.1, 2.8), M["wood_dk"])
    for zz in (z0 + 0.9, z0 + 2.1):
        iso.cube("scafh", ((x0 + x1) / 2, 0.9, zz), (x1 - x0 - 1.0, 0.12, 0.12), M["wood_dk"])
    for k in range(6):
        iso.prop("k:" + ("rock-a", "rock-b", "rock-c")[k % 3], x0 + 1.0 + rnd.random() * (x1 - x0 - 2),
                 0.4 + rnd.random() * 0.8, z0, h=0.3 + rnd.random() * 0.5, rot_z=rnd.uniform(0, 6.2),
                 recolor=toon_mat("digrock%d" % k, "#2E251B"))
    iso.prop("k:tool-pickaxe", x1 - 1.2, 0.5, z0, h=1.1, rot_z=0.4)
    # 작업등 — 굴착면에도 등불 하나(D3)
    cxm = (x0 + x1) / 2
    disc("PRV_glow2_dig", cxm, z0 + 2.55, 1.25, M["glow_far"], y=0.36)
    disc("PRV_glow1_dig", cxm, z0 + 2.55, 0.58, M["glow_near"], y=0.35)
    o = iso.sphere("diglamp", (cxm, 0.34, z0 + 2.55), 0.15, M["bulb"], 10, 6)
    o.name = "PRV_bulb_dig"


# ══════════════════════════════════════════════════════════════
# 거점 조립
# ══════════════════════════════════════════════════════════════
def materials():
    global M
    M = DOME.deep_materials()
    M["zones"] = zone_gradient()
    M["frame"] = flat_mat("Frame", PAL["char"])
    M["frame_lt"] = flat_mat("FrameLt", PAL["char_lt"])
    M["bulb"] = flat_mat("Bulb", "#FFFFFF")
    M["glow_near"] = flat_mat("GlowNear", "#FFF0D2", alpha=0.62)
    M["glow_far"] = flat_mat("GlowFar", "#F2C983", alpha=0.26)
    M["halo1"] = flat_mat("Halo1", "#01060A")
    M["halo2"] = zone_gradient("Halo2", mult=0.52)
    M["pat_light"] = PAL["cream"]
    M["pat_dark"] = PAL["char"]
    M["freshwater"] = flat_mat("FreshWater", PAL["bone"], alpha=0.75)
    M["murk"] = zone_gradient("MurkLev", mult=0.42)          # 대형 생물 실루엣(D6)
    M["murk_lt"] = zone_gradient("MurkLev2", mult=0.60)
    DOME.M = M
    return M


# (id, 층, x0, x1, 고유색, 채움, 사람 수)
#  §5 팔레트만 쓴다. 청록~남색 없음. 명도·색상이 서로 겹치지 않게 8가지.
def layout():
    return [
        ("lounge", 1, -5.0, 5.0, PAL["cream"], fill_lounge, 0),                    # 크림 — 돔 안, 가장 밝은 방
        ("quarters", 1, -13.9, -(SPINE + GAP), PAL["ochre"], fill_quarters, 4),    # 황토
        ("greenhouse", 1, SPINE + GAP, 8.5, PAL["olive"], fill_greenhouse, 3),     # 탁한 올리브
        ("workshop", 2, -8.5, -(SPINE + GAP), PAL["burnt"], fill_workshop, 3),     # 번트오렌지
        ("storage", 2, SPINE + GAP, 8.5, PAL["ochre_d"], fill_storage, 2),         # 어두운 황토
        ("library", 2, 9.05, 15.05, PAL["oxblood"], fill_library, 2),              # 적갈
        ("bath", 3, -8.5, -(SPINE + GAP), PAL["bone"], fill_bath, 3),              # 뼈
        ("airlock", 3, SPINE + GAP, 8.5, "#4C4036", fill_airlock, 3),            # 숯 — 바깥으로 나가는 방
    ]


CREW = ["cook", "farmer", "engineer", "medic", "scholar", "scout", "trader", "kid"]


def build_base():
    materials()
    z_lounge = DOME_C.z - 2.6
    for rid, lv, x0, x1, hue, fill, npc in layout():
        z0 = z_lounge if rid == "lounge" else L[lv]
        room_shell(x0, x1, z0, hue, rid)
        room_lamp((x0 + x1) / 2, z0, hue, rid)
        if (x1 - x0) > 9:
            room_lamp((x0 + x1) / 2 - 3.6, z0, hue, rid + "b")
            room_lamp((x0 + x1) / 2 + 3.6, z0, hue, rid + "c")
        fill(x0, x1, z0)
        if COZY:
            cozy_fill(rid, x0, x1, z0, hue)
            cozy_people(rid, x0, x1, z0, hue)
            warm_room(x0, x1, z0, hue, rid)      # 번짐은 소품 위에 얹혀야 '빛에 잠긴다'가 된다
        else:
            rnd = random.Random(hash(rid) % 9999)
            xs = [x0 + (x1 - x0) * (i + 0.5) / max(npc, 1) + rnd.uniform(-0.5, 0.5) for i in range(npc)]
            people(xs, z0, [CREW[(hash(rid) + i) % 8] for i in range(npc)])
    dig_face(-8.5, -(SPINE + GAP), L[4])
    spine(DOME_C.z - 1.0, L[4] - 1.6)
    glass_dome(z_lounge)
    if NO_PEOPLE:
        pass                               # 척추를 오르내리던 사람도 뺀다
    elif COZY:
        char("trader", 0.0, L[3] + 0.05, y=0.60, pose="walk", frame=2, sc=0.98)
    else:
        DOME.resident("trader", 0.0, 0.7, L[3] + 0.05, rot_z=math.radians(180), h=1.68)


# ══════════════════════════════════════════════════════════════
# F2. 전역 평탄화 — 남아 있는 Principled 재질(생활 소품·CC0·사람)을
#     전부 2단 토온으로 바꾼다. 그래서 화면 어디에도 그라데이션이 없다.
# ══════════════════════════════════════════════════════════════
WARM = (0.78, 0.56, 0.24)          # 사람·천에 씌우는 난색 기준(§5: 사람에게 청록 금지)


def _char_materials():
    out = set()
    for o in bpy.data.objects:
        n = o
        while n is not None:
            if n.name.startswith("PRV_char_"):
                break
            n = n.parent
        if n is None or o.type != 'MESH':
            continue
        for m in o.data.materials:
            if m:
                out.add(m.name)
    return out


LUM_CAP = 0.76           # 등불(1.0)·헤일로보다 항상 어둡게


def _palette_clamp(col):
    """§5 팔레트 규율: 청록~남색은 물 전용. 방·사람·소품에서 몰아낸다.
    푸른 것은 같은 명도의 황토로, 초록은 탁한 올리브로 돌린다. 명도는 상한을 넘지 않는다."""
    r, g, b = col
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if b > r and b >= g:                       # 파랑·청록 → 황토
        col = (lum * 1.22, lum * 0.98, lum * 0.58)
    elif g > r * 1.05:                         # 초록 → 탁한 올리브
        col = (lum * 0.96, lum * 1.08, lum * 0.52)
    lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
    if lum > LUM_CAP:
        col = tuple(c * (LUM_CAP / lum) for c in col)
    return tuple(max(0.0, min(1.0, c)) for c in col)


def flatten_materials():
    chars = _char_materials()
    for m in list(bpy.data.materials):
        if m.get("relic_flat") or not m.use_nodes or m.node_tree is None:
            continue
        b = m.node_tree.nodes.get("Principled BSDF")
        if b is None:
            b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if b is None:
            continue
        col = tuple(b.inputs["Base Color"].default_value)[:3]
        alpha = float(b.inputs["Alpha"].default_value)
        img = None
        for lk in m.node_tree.links:
            if lk.to_socket is b.inputs["Base Color"] and lk.from_node.type == 'TEX_IMAGE':
                img = lk.from_node.image
        try:
            estr = float(b.inputs["Emission Strength"].default_value)
            ecol = tuple(b.inputs["Emission Color"].default_value)[:3]
        except Exception:
            estr, ecol = 0.0, (0, 0, 0)
        if m.name in chars:                       # 사람은 난색 팔레트 안으로 끌어온다(§5)
            col = tuple(c * 0.22 + w * 0.78 for c, w in zip(col, WARM))
            lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
            col = tuple(c * 0.62 + lum * 0.38 for c in col)
            lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
            if lum > 0.40:                        # F7. 사람은 절대 등불보다 밝지 않다
                col = tuple(c * (0.40 / lum) for c in col)
            img = None
        col = _palette_clamp(col)
        _rebuild_flat(m, col, alpha, img, ecol, estr)


def _rebuild_flat(m, col, alpha, img, ecol, estr):
    nt = m.node_tree
    keep = img
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.0
    if estr > 0.5:                                # 원래 발광하던 것 → 그대로 밝게
        em.inputs[0].default_value = (*[min(1.0, c * max(1.0, estr) * 0.35) for c in ecol], 1)
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        m["relic_flat"] = 1
        return
    ramp = _toon_chain(nt)
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = (0.50, 0.50, 0.50, 1)
    cr.elements[1].position = 0.52; cr.elements[1].color = (1.0, 1.0, 1.0, 1)
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mul.inputs[7])
    if keep is not None:
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = keep
        tex.interpolation = 'Closest'
        nt.links.new(tex.outputs["Color"], mul.inputs[6])
    else:
        mul.inputs[6].default_value = (*col, 1)
    nt.links.new(mul.outputs[2], em.inputs[0])
    if alpha >= 0.999:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    else:
        mix = nt.nodes.new("ShaderNodeMixShader"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"]); _blend(m)
    m["relic_flat"] = 1


def drop_lights():
    """F2. 광원을 전부 버린다. 음영은 재질이 계산하고, 밝기는 팔레트가 정한다."""
    for o in list(bpy.data.objects):
        if o.type == 'LIGHT':
            bpy.data.objects.remove(o, do_unlink=True)


# ══════════════════════════════════════════════════════════════
# 세계 · 렌더 (SC.preview 를 쓰지 않고 이 파일에서 직접 — 화풍 제어를 위해)
# ══════════════════════════════════════════════════════════════
def section_world():
    DOME.V, DOME.RIGHT, DOME.UP = V_FRONT, RIGHT_FRONT, UP_FRONT
    w = bpy.data.worlds.new("w"); bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*srgb_hexcol(PAL["abyss"]), 1)
    bg.inputs[1].default_value = 0.0
    try:
        bpy.context.scene.eevee.use_raytracing = False
    except Exception:
        pass


NOLINE_EXTRA = ("PRV_backdrop", "PRV_haze", "PRV_snow", "PRV_jelly", "PRV_jhalo", "PRV_shaft",
                "PRV_ridge", "PRV_farrock", "PRV_farcable", "PRV_lev", "PRV_halo", "PRV_fish",
                "PRV_glow1_", "PRV_glow2_", "PRV_pool_", "dome_backglass", "pat_",
                # S6-B: 번짐·빛웅덩이·스프라이트에는 외곽선을 긋지 않는다.
                # 스프라이트는 그림 안에 이미 손그림 선이 들어 있어서 사각 테두리가 생기면 망가진다.
                "PRV_glow0_", "PRV_glow3_", "PRV_pool0_", "PRV_pool1_", "PRV_pool2_",
                "PRV_warm_", "PRV_sp_", "PRV_cone")


def handdrawn_lines(line=1.9):
    """F6. 손으로 그은 선 — 두께 변화(NOISE) + 흔들림(PERLIN_2D, SINUS). 매끈한 벡터 선 금지."""
    sc = bpy.context.scene
    if line <= 0:                     # S8-C 생물 실루엣: 검은 테두리를 두르면 스티커가 된다
        sc.render.use_freestyle = False
        sc.view_layers[0].use_freestyle = False
        return
    sc.render.use_freestyle = True
    sc.render.line_thickness = 1.0
    vl = sc.view_layers[0]; vl.use_freestyle = True
    fs = vl.freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("relic")
    ls.select_silhouette = ls.select_crease = ls.select_border = True
    fs.crease_angle = math.radians(152.0)      # 잔주름 대신 굵은 형태선만(§1-9)
    ls.select_by_collection = True
    ls.collection = bpy.data.collections["NOLINE"]
    ls.collection_negation = 'EXCLUSIVE'
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("relic_ls")
    st = ls.linestyle
    st.color = srgb_hexcol(PAL["char"])
    st.thickness = line
    try:
        st.caps = 'ROUND'
    except Exception:
        pass
    for nm, kw in (("th_noise", dict(amplitude=1.15, period=17, seed=3)),):
        mo = st.thickness_modifiers.new(name=nm, type='NOISE')
        for k, v in kw.items():
            setattr(mo, k, v)
    g1 = st.geometry_modifiers.new(name="g_perlin", type='PERLIN_NOISE_2D')
    g1.amplitude, g1.frequency, g1.octaves, g1.seed = 1.35, 2.6, 3, 7
    g2 = st.geometry_modifiers.new(name="g_sin", type='SINUS_DISPLACEMENT')
    g2.wavelength, g2.amplitude, g2.phase = 26.0, 0.75, 0.4
    _char_lineset(fs)


def _char_lineset(fs):
    """§1-6 덩어리진 실루엣 / §1-7 얼굴은 최소.
    사람은 주름선을 전부 버리고 바깥 실루엣 한 줄만 굵게 긋는다."""
    sc = bpy.context.scene
    noline = bpy.data.collections.get("NOLINE")
    ch = bpy.data.collections.new("CHARLINE")
    sc.collection.children.link(ch)
    n_moved = 0
    for o in list(bpy.data.objects):
        n = o
        while n is not None and not n.name.startswith("PRV_char_"):
            n = n.parent
        if n is None:
            continue
        try:
            ch.objects.link(o)
        except Exception:
            pass
        if noline is not None and o.name not in noline.objects:
            try:
                noline.objects.link(o)      # 기본 라인셋(주름선 포함)에서는 제외
                n_moved += 1
            except Exception:
                pass
    print("CHARLINE", n_moved, flush=True)
    ls2 = fs.linesets.new("chars")
    ls2.select_silhouette = True
    ls2.select_crease = False
    ls2.select_border = False
    ls2.select_by_collection = True
    ls2.collection = ch
    ls2.collection_negation = 'INCLUSIVE'
    if ls2.linestyle is None:
        ls2.linestyle = bpy.data.linestyles.new("chars_ls")
    st2 = ls2.linestyle
    st2.color = srgb_hexcol(PAL["char"])
    st2.thickness = 2.4
    try:
        st2.caps = 'ROUND'
    except Exception:
        pass
    mo = st2.thickness_modifiers.new(name="th_noise", type='NOISE')
    mo.amplitude, mo.period, mo.seed = 0.9, 13, 11
    g = st2.geometry_modifiers.new(name="g_perlin", type='PERLIN_NOISE_2D')
    g.amplitude, g.frequency, g.octaves, g.seed = 0.9, 3.2, 2, 5


def noline_setup():
    DOME.NOLINE = tuple(set(DOME.NOLINE) | set(NOLINE_EXTRA))
    DOME.noline_setup()


def paper_and_vignette(grain=0.11, vig=0.10):
    """F6. 종이 결을 곱하기로. Blender 5.x 컴포지터는 씬 노드 그룹이다."""
    sc = bpy.context.scene
    try:
        ng = bpy.data.node_groups.new("relic_comp", "CompositorNodeTree")
        ng.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = ng.nodes.new("CompositorNodeRLayers")
        go = ng.nodes.new("NodeGroupOutput")
        coord = ng.nodes.new("CompositorNodeImageCoordinates")
        ng.links.new(rl.outputs["Image"], coord.inputs["Image"])

        def grain_layer(scale, lo, hi, src):
            nz = ng.nodes.new("ShaderNodeTexNoise")
            nz.inputs["Scale"].default_value = scale
            nz.inputs["Detail"].default_value = 2.0
            nz.inputs["Roughness"].default_value = 0.6
            ng.links.new(coord.outputs["Normalized"], nz.inputs["Vector"])
            mr = ng.nodes.new("ShaderNodeMapRange")
            mr.inputs["To Min"].default_value = lo
            mr.inputs["To Max"].default_value = hi
            ng.links.new(nz.outputs["Factor"], mr.inputs["Value"])
            cc = ng.nodes.new("CompositorNodeCombineColor")
            for i in range(3):
                ng.links.new(mr.outputs[0], cc.inputs[i])
            mx = ng.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
            mx.inputs["Factor"].default_value = 1.0
            ng.links.new(src, mx.inputs[6]); ng.links.new(cc.outputs[0], mx.inputs[7])
            return mx.outputs[2]

        cur = rl.outputs["Image"]
        if COZY:
            # 정정 ②: 매끈한 벡터 면 금지. 면과 면의 경계를 조금 풀어 준다.
            sb = ng.nodes.new("CompositorNodeBlur")
            sb.inputs["Size"].default_value = (3.0, 3.0)
            ng.links.new(cur, sb.inputs["Image"])
            sm = ng.nodes.new("ShaderNodeMix"); sm.data_type = 'RGBA'; sm.blend_type = 'MIX'
            sm.inputs["Factor"].default_value = 0.30
            ng.links.new(cur, sm.inputs[6]); ng.links.new(sb.outputs["Image"], sm.inputs[7])
            cur = sm.outputs[2]
        cur = grain_layer(46.0, 1.0 - grain, 1.0 + grain * 0.55, cur)     # 종이 결(굵게)
        cur = grain_layer(340.0, 1.0 - grain * 0.45, 1.0 + grain * 0.2, cur)  # 연필 자국(가늘게)
        if COZY:
            cur = grain_layer(11.0, 1.0 - grain * 0.60, 1.0 + grain * 0.35, cur)   # 큰 붓결
        # 비네트 — 가장자리를 숯검정 쪽으로
        msk = ng.nodes.new("CompositorNodeEllipseMask")
        msk.inputs["Size"].default_value = (1.02, 1.12)
        blur = ng.nodes.new("CompositorNodeBlur")
        blur.inputs["Size"].default_value = (190.0, 190.0)   # 5.x: 2D 픽셀 벡터
        ng.links.new(msk.outputs["Mask"], blur.inputs["Image"])
        vm = ng.nodes.new("ShaderNodeMapRange")
        vm.inputs["To Min"].default_value = 1.0 - vig
        vm.inputs["To Max"].default_value = 1.0
        ng.links.new(blur.outputs["Image"], vm.inputs["Value"])
        cc2 = ng.nodes.new("CompositorNodeCombineColor")
        for i in range(3):
            ng.links.new(vm.outputs[0], cc2.inputs[i])
        mx2 = ng.nodes.new("ShaderNodeMix"); mx2.data_type = 'RGBA'; mx2.blend_type = 'MULTIPLY'
        mx2.inputs["Factor"].default_value = 1.0
        ng.links.new(cur, mx2.inputs[6]); ng.links.new(cc2.outputs[0], mx2.inputs[7])
        ng.links.new(mx2.outputs[2], go.inputs[0])
        sc.compositing_node_group = ng
    except Exception as e:
        print("COMP SKIPPED", e, flush=True)


def render(path, ortho, target, res=(1600, 900), grain=0.11, vig=0.10,
           alpha=False, line=1.9):
    sc = bpy.context.scene
    loc = Vector((target[0], -70.0, target[2]))
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.clip_start, cam.data.clip_end = 0.1, 400.0
    sc.camera = cam
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = bool(alpha)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA' if alpha else 'RGB'
    try:
        sc.eevee.taa_render_samples = 24
    except Exception:
        pass
    handdrawn_lines(line)
    sc.view_settings.view_transform = 'Standard'      # F8
    sc.view_settings.exposure = 0.0
    try:
        sc.view_settings.look = 'None'
    except Exception:
        pass
    paper_and_vignette(grain, vig)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDER", path, flush=True)


def build(extras=True):
    build_base()              # materials() 안의 SC.fresh() 가 씬을 비우므로 이것이 먼저다
    section_world()
    water_backdrop()
    haze_sheets()
    far_silhouettes()
    soft_shafts()
    if extras:
        marine_snow()
        soft_jellies()
        fish_shoal(-20.5, 16.5, 34, (5.6, 3.2), 9.0, 41)
        fish_shoal(19.0, 20.0, 22, (4.2, 2.4), 12.0, 63)
        DOME.leviathan(sr=-13.0, su=23.0, depth=-14.0, length=24.0, seed=5)    # 박광층을 지나간다(D6)
        DOME.leviathan(sr=21.0, su=11.0, depth=-8.0, length=12.0, seed=8)
    flatten_materials()
    drop_lights()
    noline_setup()


def shot_hero():
    build(extras=True)
    render(os.path.join(OUT_RAW, "section_hero.png"), ortho=62.0, target=(0.4, 0, 6.6),
           grain=0.11, vig=0.10)


def shot_zoom():
    build(extras=True)
    render(os.path.join(OUT_RAW, "section_zoom.png"), ortho=21.0, target=(0.0, 0, 3.5),
           grain=0.09, vig=0.08)


# ══════════════════════════════════════════════════════════════
# S6-B 산출물 — 온기판 전체 / 방 2칸 확대 / 전·후 비교용 이전판
#   비교 컷은 같은 카메라·같은 해상도로만 낸다. 구도를 바꾸면 비교가 거짓말이 된다.
# ══════════════════════════════════════════════════════════════
ZOOM2 = dict(ortho=18.6, target=(0.0, 0, 3.55))     # 공방 + 창고(E1 선반) 두 칸, 척추를 사이에


def shot_warm():
    build(extras=True)
    render(os.path.join(OUT_RAW, "section_warm.png"), ortho=62.0, target=(0.4, 0, 6.6),
           grain=0.19, vig=0.10)


def shot_roomzoom():
    build(extras=True)
    render(os.path.join(OUT_RAW, "section_room_zoom.png"), grain=0.17, vig=0.07, **ZOOM2)


def shot_before():
    global COZY
    COZY = False
    build(extras=True)
    render(os.path.join(OUT_RAW, "_before_room_zoom.png"), grain=0.09, vig=0.07, **ZOOM2)


def shot_before_hero():
    global COZY
    COZY = False
    build(extras=True)
    render(os.path.join(OUT_RAW, "_before_hero.png"), ortho=62.0, target=(0.4, 0, 6.6),
           grain=0.11, vig=0.10)


# ══════════════════════════════════════════════════════════════
# S8-C ①  사람 없는 온기판 — 캐릭터 담당의 합성 판정용
#   같은 카메라, 같은 값. 바뀐 것은 사람이 없다는 것뿐이다.
# ══════════════════════════════════════════════════════════════
def shot_warm_noppl():
    build(extras=True)
    render(os.path.join(OUT_RAW, "section_warm_noppl.png"), ortho=62.0, target=(0.4, 0, 6.6),
           grain=0.19, vig=0.10)


def shot_roomzoom_noppl():
    build(extras=True)
    render(os.path.join(OUT_RAW, "section_room_zoom_noppl.png"), grain=0.17, vig=0.07, **ZOOM2)


# ══════════════════════════════════════════════════════════════
# S8-C ②  방 종류별 플레이트 — 2.5D 정수 배율 체계
#
#   2026-10-01 결정: 캐릭터는 P2 「48px 생활형 도트」, 화면 배율 ×3 = 144px.
#   그래서 배경도 **같은 격자**를 써야 한다. 안 그러면 캐릭터만 계단이 지고
#   방은 매끈해서 '붙여 놓은 스티커'가 된다(결정 로그 "2.5D 성립 조건 ①").
#
#     1 m = 28 가상px = 84 화면px      (28 × 3 = 84)
#     방 안쪽 3.0 m = 84 가상px = 252 화면px
#     캔버스 8.0 × 4.5 m = 672 × 378 화면px
#     **바닥선 = 캔버스 위에서 315px.** 이 숫자 하나가 도트 캐릭터의 접지선이다.
#
#   플레이트는 불투명하다. 방 둘레 약 1 m 는 '어두운 물 여백'(F7)이 구워져 있고,
#   생물 실루엣은 그 바깥 물에 따로 얹는다(S8-C ③) — 그래서 겹칠 일이 없다.
# ══════════════════════════════════════════════════════════════
#  격자는 캐릭터가 정한다 — static/art/chars/front/p2/meta.json 이 정본:
#    src_ppm 27.5 (×1 원화의 미터당 px) · room_scale 3 · room_cell 192 · room_baseline 180
#    → 방 안에서 쓰는 배율은 ×3 이고 **82.5 px/m** 이다. 1.6m 키 = 132px.
#  (84 px/m 로 잡았다가 1.8% 어긋났다. 캐릭터 쪽 숫자를 그대로 가져오는 것이 규약이다.)
CHAR_SRC_PPM = 27.5                              # 캐릭터 ×1 원화의 미터당 px
PLATE_SCALE = 3                                  # 방 안에서 쓰는 정수 배율(room_scale)
PLATE_PPM = CHAR_SRC_PPM * PLATE_SCALE           # 82.5 화면 px / m
PLATE_RES = (672, 378)                           # 캔버스는 px 가 먼저다(미터는 여기서 나온다)
PLATE_FLOOR_Y = 315                              # 바닥선 — 도트 캐릭터의 접지선
PLATE_W_M = PLATE_RES[0] / PLATE_PPM             # 8.145 m
PLATE_H_M = PLATE_RES[1] / PLATE_PPM             # 4.582 m
PLATE_ROOM_W = 6.0                               # 방 안쪽 폭 (495px)
PLATE_HEAD = (PLATE_RES[1] - PLATE_FLOOR_Y) / PLATE_PPM
PLATE_STAND_MARGIN = 0.60                        # 옆벽에서 사람이 설 수 없는 띠(m)
PLATE_DIM = 0.46                                 # '빈 방'(등불 꺼짐) 밝기 배수
OUT_PLATE = os.path.join(ROOT, "art_raw", "plates")
OUT_THREAT = os.path.join(ROOT, "art_raw", "threats")


def _m2px_x(xm):
    return int(round(PLATE_RES[0] / 2.0 + xm * PLATE_PPM))


def _m2px_y(zm, z0=0.0):
    """방 바닥 z0 기준의 월드 z → 캔버스 위에서의 px."""
    return int(round(PLATE_FLOOR_Y - (zm - z0) * PLATE_PPM))


# ── 플레이트용 채움 ───────────────────────────────────────────
#  **정면 직교 + 깊이 1.7m** 에서는 바닥에 놓인 것이 거의 안 보인다(S6 §8-3).
#  그래서 플레이트의 가구는 **서 있어야** 한다 — 2층 침대·선반·걸이·벽 장비.
#  1차 플레이트가 "텅 빈 노란 벽"으로 나온 원인이 이것이었다.
# ─────────────────────────────────────────────────────────────
def _bunk(x, z0, w=1.62, tag=""):
    """2층 침대 한 벌. 정면에서 가장 잘 읽히는 '사람이 사는 증거'(B4)."""
    for sx in (x - w / 2, x + w / 2):
        iso.cube("bkpost" + tag, (sx, 1.05, z0 + 1.25), (0.10, 0.74, 2.50), M["frame"])
    for k, zz in enumerate((0.52, 1.72)):
        iso.cube("bkframe" + tag, (x, 1.05, z0 + zz), (w, 0.80, 0.10), M["wood_dk"])
        iso.cube("bkmat" + tag, (x, 1.02, z0 + zz + 0.13), (w - 0.14, 0.72, 0.17),
                 M["fabric"] if k else M["fabric2"])
        iso.cube("bkblank" + tag, (x + 0.16, 0.92, z0 + zz + 0.25), (w - 0.52, 0.66, 0.12),
                 M["tarp"] if k else M["fabric"], rot=(0, 0.03, 0))
        iso.cube("bkpil" + tag, (x - w / 2 + 0.30, 1.00, z0 + zz + 0.26), (0.36, 0.52, 0.14),
                 M["pillow"])
    for k in range(4):                               # 사다리
        iso.cube("bkldr" + tag, (x + w / 2 + 0.12, 0.62, z0 + 0.35 + k * 0.42),
                 (0.34, 0.06, 0.06), M["frame_lt"])


def _wall_rack(x0, x1, z0, levels, mats, tag, zb=0.90, step=0.62, depth=0.30):
    """뒷벽 선반 — 세로를 채우는 가장 싼 방법. 격자는 '사람이 만든 것'이라 격자가 맞다(B5)."""
    rnd = random.Random(hash(tag) % 9991)
    for lv in range(levels):
        z = z0 + zb + lv * step
        iso.cube("wr_%s_%d" % (tag, lv), ((x0 + x1) / 2, DEPTH - depth, z - 0.05),
                 (x1 - x0, depth + 0.08, 0.08), M["wood"])
        n = int((x1 - x0) / 0.34)
        for k in range(n):
            if rnd.random() < 0.22:
                continue
            h = 0.18 + rnd.random() * 0.22
            iso.cube("wri_%s_%d_%d" % (tag, lv, k),
                     (x0 + 0.17 + k * 0.34, DEPTH - depth, z + h / 2),
                     (0.22, depth * 0.7, h), M[mats[(k + lv) % len(mats)]])


def plate_fill_quarters(x0, x1, z0):
    _bunk(-2.00, z0, 1.72, "a")
    _bunk(-0.18, z0, 1.72, "b")
    at(z0, iso.shelf_unit, 2.30, 1.15)
    iso.cube("qtable", (1.20, 0.80, z0 + 0.62), (1.05, 0.72, 0.08), M["wood"])
    for sx in (0.75, 1.65):
        iso.cube("qleg", (sx, 0.80, z0 + 0.31), (0.08, 0.66, 0.62), M["wood_dk"])
    iso.cube("qstool", (1.20, 0.34, z0 + 0.21), (0.44, 0.44, 0.42), M["wood_dk"])
    at(z0, iso.laundry, (-2.80, 0.30), (0.40, 0.30), 2.62)
    at(z0, iso.plant, 2.68, 0.44, 0.52)
    at(z0, iso.jug, 0.62, 0.42, 0.3)
    iso.prop("k:chest", 2.05, 0.52, z0, h=0.52, rot_z=0.2)


def plate_fill_storage(x0, x1, z0):
    # 뒷벽 네 단 전부가 E1 선반 — 창고는 '차오르는 것'이 보여야 한다(P1 비축)
    shelf_props(x0, x1, z0, "storage",
                rows=SHELF_ROWS + [SHELF_ROWS[0]], z_first=0.52, step=0.64)
    at(z0, iso.shelf_unit, -2.35, 0.95)
    for k, hgt in enumerate((0.66, 0.66, 0.60)):
        iso.prop("k:box-large", 2.20, 0.58, z0 + k * 0.52, h=hgt, rot_z=0.1 * k)
    at(z0, iso.can_pile, -1.05, 0.42, 3, 1)
    at(z0, iso.can_pile, 0.35, 0.42, 2, 4)
    iso.prop("k:barrel", 1.35, 0.46, z0, h=0.85)
    at(z0, iso.jug, -1.75, 0.38, 0.2)


def plate_fill_workshop(x0, x1, z0):
    iso.prop("k:workbench", -1.55, 1.25, z0, h=1.05)
    iso.prop("k:workbench-anvil", 1.30, 1.20, z0, h=1.00)
    iso.prop("k:barrel", 2.55, 0.52, z0, h=0.85)
    at(z0, iso.can_pile, -0.45, 0.42, 3, 5)
    # 공구 벽 — 대응 도구 일곱이 나오는 자리(COMBAT §6.5). 걸린 것과 빈 고리가 섞인다
    iso.cube("wpeg", (0.0, DEPTH - 0.17, z0 + 2.10), (4.6, 0.10, 1.40), M["wood_dk"])
    rnd = random.Random(417)
    for k in range(13):
        hxp = -2.10 + k * 0.35
        iso.cube("whookbar", (hxp, DEPTH - 0.21, z0 + 2.72), (0.07, 0.05, 0.14), M["frame_lt"])
        if rnd.random() < 0.26:
            continue
        h = 0.34 + rnd.random() * 0.40
        iso.cube("wtool", (hxp, DEPTH - 0.21, z0 + 2.62 - h / 2), (0.10, 0.06, h),
                 M["metal"] if k % 2 else M["copper"])
    iso.cube("wbench", (0.0, 0.85, z0 + 0.92), (3.1, 0.76, 0.09), M["wood"])
    for sx in (-1.40, 1.40):
        iso.cube("wbleg", (sx, 0.85, z0 + 0.45), (0.10, 0.70, 0.90), M["wood_dk"])
    iso.cube("wvise", (-1.10, 0.70, z0 + 1.06), (0.26, 0.26, 0.20), M["metal"])


def plate_fill_infirmary(x0, x1, z0):
    """의무실 — 부상자가 돌아오는 방(COMBAT §5-1). 다리 달린 간이 침상이라 정면에서 읽힌다."""
    for k, bx in enumerate((-1.90, 0.30)):
        iso.cube("ibed", (bx, 1.05, z0 + 0.58), (1.78, 0.90, 0.14), M["wood_dk"])
        for sx in (bx - 0.80, bx + 0.80):
            iso.cube("ibleg", (sx, 1.05, z0 + 0.26), (0.09, 0.80, 0.52), M["frame_lt"])
        iso.cube("isheet", (bx, 1.02, z0 + 0.71), (1.70, 0.84, 0.14), M["pillow"])
        iso.cube("ipillow", (bx - 0.62, 1.00, z0 + 0.84), (0.42, 0.56, 0.14), M["fabric2"])
        if k == 0:                                   # 한 침상만 쓰던 흔적 — 담요가 젖혀져 있다
            iso.cube("iblank", (bx + 0.32, 0.98, z0 + 0.84), (0.92, 0.76, 0.14),
                     M["fabric"], rot=(0, 0.04, 0))
        iso.cube("ihead", (bx - 0.92, 1.05, z0 + 0.86), (0.08, 0.84, 0.72), M["frame"])
    _wall_rack(1.20, 2.80, z0, 3, ("paper", "red", "pillow", "yellow"), "ivial",
               zb=1.30, step=0.58, depth=0.26)       # 약병 장
    iso.cyl("ibasin", (-2.45, 0.52, z0 + 0.70), 0.32, 0.22, M["metal"], verts=14)
    iso.cube("ibstand", (-2.45, 0.52, z0 + 0.30), (0.56, 0.52, 0.60), M["wood_dk"])
    iso.cube("irail", (-2.00, 0.26, z0 + 2.62), (2.0, 0.07, 0.07), M["frame_lt"])
    hanging_cloth(-2.80, -1.20, z0 + 2.58, "infscreen", 3, 1.30, y=0.24)    # 가림막


def plate_fill_power(x0, x1, z0):
    """발전실 — 조명·소리 차단·격벽이 전부 여기서 나온다(COMBAT §5-1).
    소리가 나는 방이라 문지기 습격 때 가장 먼저 내려야 하는 곳이다."""
    iso.cube("pbase", (-1.45, 1.00, z0 + 0.20), (2.3, 1.2, 0.40), M["frame"])
    iso.cyl("pdrum", (-1.45, 1.00, z0 + 1.08), 0.78, 2.00, M["hull_dk"],
            rot=(0, math.radians(90), 0), verts=18)
    iso.cyl("pdrumr", (-1.45, 0.42, z0 + 1.08), 0.56, 0.10, M["rust"],
            rot=(math.radians(90), 0, 0), verts=16)
    iso.cyl("pstack", (-0.30, 1.00, z0 + 2.30), 0.16, 1.5, M["rust"], verts=12)
    iso.cyl("pstackc", (-0.30, 1.00, z0 + 3.00), 0.23, 0.14, M["frame_lt"], verts=12)
    for k in range(2):
        iso.cyl("ppipe", (0.22 + k * 0.30, DEPTH - 0.28, z0 + 1.70), 0.065, 2.8,
                M["rust"], verts=10)
    iso.cube("ppanel", (1.85, DEPTH - 0.20, z0 + 2.12), (1.9, 0.12, 1.10), M["frame_lt"])
    for k in range(6):                               # 계기 — 등불보다 어둡게(F7)
        iso.cyl("pdial", (1.18 + (k % 3) * 0.60, DEPTH - 0.28, z0 + 2.40 - (k // 3) * 0.50),
                0.11, 0.06, M["copper"] if k % 2 else M["rust"],
                rot=(math.radians(90), 0, 0), verts=12)
    for lv in range(2):                              # 축전지 선반 두 단
        z = z0 + 0.22 + lv * 0.78
        iso.cube("pbshelf", (1.85, 0.62, z - 0.06), (2.1, 0.66, 0.10), M["frame"])
        for k in range(4):
            iso.cube("pbatt", (1.05 + k * 0.52, 0.62, z + 0.30), (0.42, 0.52, 0.60),
                     M["wood_dk"] if (k + lv) % 2 else M["frame_lt"])
            iso.cube("pbcap", (1.05 + k * 0.52, 0.62, z + 0.62), (0.42, 0.52, 0.06), M["copper"])
    iso.prop("k:barrel", -2.60, 0.50, z0, h=0.85)
    for k, cx in enumerate((-2.20, 2.80)):           # 늘어진 케이블
        DOME.strut("pcable", Vector((cx, 0.22, z0 + RH - 0.10)),
                   Vector((cx + (0.40 if k else -0.30), 0.22, z0 + 1.40)), 0.055, M["frame"], 5)


def plate_fill_greenhouse(x0, x1, z0):
    """온실 — 물속이라 **초록은 전부 사람이 기른 것**이다(B2). 세로로 쌓아 초록을 키운다."""
    rnd = random.Random(77)
    for lv in range(3):                              # 뒷벽 재배 선반 세 단
        z = z0 + 0.78 + lv * 0.74
        iso.cube("gshelf", (0.0, DEPTH - 0.36, z - 0.06), (5.0, 0.56, 0.10), M["wood_dk"])
        iso.cube("gtray", (0.0, DEPTH - 0.36, z + 0.08), (4.8, 0.48, 0.16), M["earth2"])
        for k in range(7):
            at(z + 0.14, iso.plant, -2.10 + k * 0.70 + rnd.uniform(-0.09, 0.09),
               DEPTH - 0.36, rnd.uniform(0.30, 0.46), False)
    for k in range(2):                               # 앞쪽 바닥 재배단
        iso.cube("gbed", (-1.35 + k * 2.70, 0.95, z0 + 0.30), (1.70, 1.05, 0.60), M["wood_dk"])
        iso.cube("gsoil", (-1.35 + k * 2.70, 0.95, z0 + 0.63), (1.56, 0.95, 0.06), M["earth2"])
        for j in range(4):
            at(z0 + 0.66, iso.plant, -1.95 + k * 2.70 + j * 0.40,
               0.95 + rnd.uniform(-0.2, 0.2), rnd.uniform(0.34, 0.54), False)
    at(z0, iso.jug, 0.05, 0.42, -0.3)
    iso.prop("k:bucket", 2.55, 0.44, z0, h=0.34, rot_z=0.4)


PLATE_FILL = {"quarters": plate_fill_quarters, "storage": plate_fill_storage,
              "workshop": plate_fill_workshop, "greenhouse": plate_fill_greenhouse,
              "infirmary": plate_fill_infirmary, "power": plate_fill_power}

# (id, 한국어 이름, 고유색, 전투에서의 역할 — COMBAT_AND_DEFENSE §5-1)
PLATE_ROOMS = [
    ("quarters",   "거주",   PAL["ochre"],   "사람이 쉬는 곳. 정원이 가장 많다"),
    ("storage",    "창고",   PAL["ochre_d"], "유물 적재량. E1 선반이 여기"),
    ("workshop",   "공방",   PAL["burnt"],   "대응 도구 일곱을 만든다"),
    ("infirmary",  "의무실", PAL["cream"],   "부상자 복귀 속도"),
    ("power",      "발전실", PAL["oxblood"], "조명·소리 차단·격벽의 전제"),
    ("greenhouse", "온실",   PAL["olive"],   "식량과 산소. 사기와 체력"),
]


def plate_cozy(rid, x0, x1, z0):
    """생활 흔적 — 6 m 방에 맞춘 압축판. 사람은 없고 **사람의 자국만** 있다(B4)."""
    if rid == "quarters":
        folded_stack(2.62, 0.52, z0, rid, 3, 0.52)
        wall_notes(0.95, z0 + 2.12, rid, 5, 11)
        floor_shoes(-1.15, 0.38, z0, rid)
        floor_shoes(0.52, 0.34, z0, rid + "b")
        cup_on(1.15, 0.72, z0 + 0.66, rid, 2)
        deco_rail(-1.05, z0 + 2.86, rid, filled=1, slots=3)
        warm_rug(-1.10, z0, 2.9, rid)
    elif rid == "storage":
        wall_notes(-2.65, z0 + 1.95, rid, 4, 61)
        folded_stack(-2.60, 0.46, z0, rid, 3, 0.50)
        floor_shoes(0.95, 0.34, z0, rid)
        cup_on(-0.10, 0.40, z0 + 0.02, rid, 1)
        leaning_thing(-2.86, z0, rid, "plank", 0.16, 1.5, 0.30)
        deco_rail(-2.10, z0 + 2.80, rid, filled=1, slots=2)
    elif rid == "workshop":
        wall_notes(-2.55, z0 + 1.45, rid, 5, 41)
        leaning_thing(-2.80, z0, rid, "plank", 0.19, 2.0, 0.34)
        leaning_thing(-2.46, z0, rid + "b", "pole", 0.15, 1.6, 0.26)
        folded_stack(2.40, 0.44, z0, rid, 2, 0.42)
        cup_on(-0.70, 0.52, z0 + 0.97, rid)
        pot_steam(0.85, 0.48, z0 + 0.97, rid, 0.22)
        floor_shoes(-1.60, 0.34, z0, rid)
        deco_rail(2.45, z0 + 2.70, rid, filled=1, slots=2)
    elif rid == "greenhouse":
        wall_notes(2.60, z0 + 2.86, rid, 4, 23)
        leaning_thing(2.74, z0, rid, "pole", 0.22, 1.7, 0.34)
        floor_shoes(-2.55, 0.34, z0, rid)
        folded_stack(-2.62, 0.46, z0, rid, 2, 0.44)
        cup_on(0.75, 0.42, z0 + 0.02, rid, 1)
        deco_rail(-2.30, z0 + 2.80, rid, filled=1, slots=2)
    elif rid == "infirmary":
        wall_notes(-0.70, z0 + 2.20, rid, 4, 131)
        folded_stack(2.55, 0.46, z0, rid, 3, 0.46)                        # 개어 둔 붕대
        floor_shoes(-0.95, 0.34, z0, rid)
        cup_on(-2.45, 0.52, z0 + 0.92, rid, 2)
        pot_steam(1.95, 0.48, z0 + 0.02, rid, 0.24)                       # 끓이는 물
        at(z0, iso.plant, 2.74, 0.42, 0.44)
        deco_rail(0.40, z0 + 2.80, rid, filled=1, slots=2)
        warm_rug(-0.80, z0, 2.4, rid, d=0.95)
    elif rid == "power":
        wall_notes(-0.60, z0 + 2.62, rid, 4, 157)
        floor_shoes(-0.35, 0.34, z0, rid)
        folded_stack(-2.62, 0.44, z0, rid, 2, 0.42)                       # 기름 닦는 걸레
        cup_on(0.55, 0.40, z0 + 0.04, rid, 1)
        leaning_thing(2.84, z0, rid, "pole", 0.17, 1.6, 0.28)
        pot_steam(-2.60, 0.50, z0 + 0.88, rid, 0.20)
        deco_rail(-1.90, z0 + 2.80, rid, filled=1, slots=2)


def plate_lamp_off(x, z0, rid):
    """꺼진 등불. 금속만 남고 빛이 없다 — '아직 아무도 살지 않는 방'."""
    top = z0 + RH
    iso.cyl("lw_" + rid, (x, 0.55, top - 0.18), 0.02, 0.36, M["frame"],
            rot=(math.radians(90), 0, 0))
    iso.cyl("ls_" + rid, (x, 0.55, top - 0.44), 0.22, 0.18, M["frame"])
    iso.sphere("lboff_" + rid, (x, 0.44, top - 0.52), 0.15, M["frame_lt"], 12, 7)


def plate_mask(x0, x1, z0):
    """방 바깥 여백을 **어두운 물 한 색으로 못 박는다**(F7의 어두운 여백).

    타일이라 여백이 매번 같아야 하고, 김·널어 둔 천 같은 것이 옆칸으로 삐져나오면
    붙여 놓았을 때 이음매가 지저분해진다. 2차 플레이트에서 발전실의 김이
    방 밖 물로 번져 나갔다 — 그 한 장 때문에 이 판을 넣었다."""
    m = flat_mat("PlateMargin", "#01060A")
    lx, rx = x0 - HULL, x1 + HULL
    bz, tz = z0 - HULL, z0 + RH + HULL
    far = 9.0
    y = -3.0                                     # 카메라(y=-70) 쪽 — 방 안의 모든 번짐보다 앞
    bands = [(-far, lx, -far, far), (rx, far, -far, far),
             (lx, rx, tz, far), (lx, rx, -far, bz)]
    for i, (a, b, c, d) in enumerate(bands):
        q = [Vector((a, y, c)), Vector((b, y, c)), Vector((b, y, d)), Vector((a, y, d))]
        DOME.mesh_of_quads("PRV_halo_mask%d" % i, [q], m).name = "PRV_halo_mask%d" % i


def build_plate(rid, hue, lit=True):
    materials()
    section_world()
    x0, x1, z0 = -PLATE_ROOM_W / 2, PLATE_ROOM_W / 2, 0.0
    # 플레이트는 방 하나를 꽉 채워 보여 준다 — 전체 렌더에서는 작게 지나가던
    # 흰 천·종이가 여기서는 등불을 이긴다(F7). 전체 렌더는 손대지 않고 여기서만 한 단 누른다.
    M["pillow"] = flat_mat("PlatePillow", PAL["bone"])
    M["paper"] = flat_mat("PlatePaper", mixhex(PAL["bone"], PAL["cream"], 0.35))
    room_shell(x0, x1, z0, hue, rid, dim=1.0 if lit else PLATE_DIM)
    if lit:
        room_lamp(0.0, z0, hue, rid, spread=0.70)
        PLATE_FILL[rid](x0, x1, z0)
        plate_cozy(rid, x0, x1, z0)
        warm_room(x0, x1, z0, hue, rid)
    else:
        plate_lamp_off(0.0, z0, rid)
    plate_mask(x0, x1, z0)
    flatten_materials()
    drop_lights()
    noline_setup()


def shot_plates():
    """방 여섯 × 두 상태 = 열두 장. 메타 JSON 한 개."""
    os.makedirs(OUT_PLATE, exist_ok=True)
    z0 = 0.0
    inner = [_m2px_x(-PLATE_ROOM_W / 2), _m2px_y(z0 + RH, z0),
             _m2px_x(PLATE_ROOM_W / 2), _m2px_y(z0, z0)]
    outer = [_m2px_x(-PLATE_ROOM_W / 2 - HULL), _m2px_y(z0 + RH + HULL, z0),
             _m2px_x(PLATE_ROOM_W / 2 + HULL), _m2px_y(z0 - HULL, z0)]
    rooms = []
    for rid, name, hue, note in PLATE_ROOMS:
        files = {}
        for state, lit in (("dark", False), ("lit", True)):
            build_plate(rid, hue, lit=lit)
            fn = "room_plate_%s_%s.png" % (rid, state)
            render(os.path.join(OUT_PLATE, fn), ortho=PLATE_W_M,
                   target=(0.0, 0, z0 + PLATE_H_M / 2 - PLATE_HEAD),
                   res=PLATE_RES, grain=0.16, vig=0.0, line=1.5)
            files[state] = fn
        rooms.append({
            "id": rid, "name": name, "hue": hue, "note": note,
            "files": files,
            "floor_y": _m2px_y(z0, z0),
            "ceil_y": _m2px_y(z0 + RH, z0),
            "stand_x": [_m2px_x(-PLATE_ROOM_W / 2 + PLATE_STAND_MARGIN),
                        _m2px_x(PLATE_ROOM_W / 2 - PLATE_STAND_MARGIN)],
            "lamp": [_m2px_x(0.0), _m2px_y(z0 + RH - 0.52, z0)],
            "inner_rect": inner, "outer_rect": outer,
        })
    meta = {
        "_note": "S8-C 방 플레이트. 좌표 단위는 전부 캔버스 px(좌상단 0,0).",
        "_rule": ("도트 캐릭터(P2 48px)를 ×3 으로 그리고, 발바닥을 floor_y 에 맞춘다. "
                  "플레이트를 확대/축소하지 말 것 — 정수 배율 체계가 깨진다."),
        "grid": {"src_px_per_m": CHAR_SRC_PPM, "char_scale": PLATE_SCALE,
                 "px_per_m": PLATE_PPM,
                 "char_ref": {"set": "static/art/chars/front/p2", "src_cell": 64,
                              "room_cell": 192, "room_baseline": 180, "room_h_1m6": 132,
                              "note": "src/<role>.png 를 NEAREST ×3 으로 키우고 "
                                      "셀 안 baseline(180)을 floor_y 에 맞춘다"}},
        "canvas": list(PLATE_RES),
        "canvas_m": [round(PLATE_W_M, 4), round(PLATE_H_M, 4)],
        "room_inner_m": [PLATE_ROOM_W, RH],
        "floor_y": _m2px_y(z0, z0),
        "inner_rect": inner, "outer_rect": outer,
        "water_margin_px": {"left": outer[0], "right": PLATE_RES[0] - outer[2],
                            "top": outer[1], "bottom": PLATE_RES[1] - outer[3]},
        "states": {"dark": "막 지은 빈 방 — 등불 꺼짐, 소품 없음",
                   "lit": "등불 켜짐 + 생활 흔적. 사람은 없다(도트로 얹는다)"},
        "overlays": {"_dir": "같은 캔버스 672×378 RGBA. tools/gen_damage.py 가 만든다",
                     "crack": ["damage_crack1.png", "damage_crack2.png", "damage_crack3.png"],
                     "flood": "room_flood.png"},
        "rooms": rooms,
    }
    with open(os.path.join(OUT_PLATE, "plates_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("PLATE META", os.path.join(OUT_PLATE, "plates_meta.json"), flush=True)


# ══════════════════════════════════════════════════════════════
# S8-C ③  바깥에서 오는 것들 — 전투 예고 2단계
#   WORLD_BIBLE_DEEP §3 + COMBAT_AND_DEFENSE §4.
#   규칙 셋:
#     ⓐ **악당이 아니다.** 이빨·발톱·붉은 눈을 그리지 않는다. 덩어리와 윤곽뿐.
#     ⓑ **물색으로 그린다.** 물보다 조금 어두운 같은 색. 그래서 '우주'가 아니라 물속이다.
#     ⓒ 멀리(far)는 물에 거의 녹아 있고, 가까이(near)는 거의 검다.
#        같은 생물의 두 장은 **접근 = 짙어짐**으로 읽혀야 한다.
#   캔버스 12 × 6 m = 1008 × 504 px, 같은 84px/m 격자. 투명 PNG, 외곽선 없음.
#   오른쪽(+x)이 거점 쪽이다 — 생물은 오른쪽을 향해 다가온다.
# ══════════════════════════════════════════════════════════════
THREAT_W_M, THREAT_H_M = 12.0, 6.0
THREAT_RES = (int(THREAT_W_M * PLATE_PPM), int(THREAT_H_M * PLATE_PPM))   # 1008 × 504

TH_FAR = ("#06151D", 0.34)
TH_NEAR = ("#02080C", 0.86)
TH_RIM = "#1E4C5C"          # 물빛이 스치는 가장자리. 유일한 밝은 값이고 아주 약하다


def _th_col(near):
    return TH_NEAR if near else TH_FAR


def th_blob(name, cx, cz, rx, rz, near, k=1.0, y=0.0):
    c, a = _th_col(near)
    return soft_blob("th_" + name, cx, cz, rx, rz, c, alpha=min(0.95, a * k), y=y)


def th_rim(name, cx, cz, rx, rz, near, k=1.0, y=-0.2):
    return soft_blob("thr_" + name, cx, cz, rx, rz, TH_RIM,
                     alpha=(0.16 if near else 0.07) * k, y=y)


def th_mat(near, k=1.0, name="th"):
    c, a = _th_col(near)
    return flat_mat("thm_%s_%d" % (name, int(k * 1000)), c, alpha=min(0.95, a * k))


def th_poly(name, pts, mat, y=0.0):
    """닫힌 폴리곤 하나. 중심에서 부채꼴로 쪼갠다 — 실루엣의 **단단한 속**이다.
    soft_blob 만으로는 연기가 된다(1차 렌더가 그랬다). 속은 도형, 가장자리는 번짐."""
    cx = sum(p[0] for p in pts) / len(pts)
    cz = sum(p[1] for p in pts) / len(pts)
    quads = []
    for a, b in zip(pts, list(pts[1:]) + [pts[0]]):
        quads.append([Vector((cx, y, cz)), Vector((a[0], y, a[1])),
                      Vector((b[0], y, b[1])), Vector((b[0], y, b[1]))])
    o = DOME.mesh_of_quads("PRV_th_" + name, quads, mat)
    o.name = "PRV_th_" + name
    return o


def th_strip(name, pts, mat, y=0.0):
    """(x, z, 반폭) 중심선 → 굵기가 변하는 띠. 목·몸통용.

    **마디마다 법선을 평균 낸다(마이터 조인).** 구간별 법선을 그대로 쓰면 휜 자리에서
    이웃 사각형의 변이 어긋나 틈이 생기고, 반투명이라 그 틈으로 물이 비쳐
    등에 흰 줄이 죽 그어진다(3차 렌더가 그랬다 — 문지기가 빗금 친 고래였다)."""
    nrm = []
    for i in range(len(pts)):
        acc = [0.0, 0.0]
        for a, b in ((i - 1, i), (i, i + 1)):
            if a < 0 or b >= len(pts):
                continue
            dx, dz = pts[b][0] - pts[a][0], pts[b][1] - pts[a][1]
            ln = math.hypot(dx, dz) or 1.0
            acc[0] += -dz / ln
            acc[1] += dx / ln
        ln = math.hypot(*acc) or 1.0
        nrm.append((acc[0] / ln, acc[1] / ln))
    quads = []
    for i in range(len(pts) - 1):
        (x0, z0, w0), (x1, z1, w1) = pts[i], pts[i + 1]
        (a0, b0), (a1, b1) = nrm[i], nrm[i + 1]
        quads.append([Vector((x0 + a0 * w0, y, z0 + b0 * w0)),
                      Vector((x1 + a1 * w1, y, z1 + b1 * w1)),
                      Vector((x1 - a1 * w1, y, z1 - b1 * w1)),
                      Vector((x0 - a0 * w0, y, z0 - b0 * w0))])
    o = DOME.mesh_of_quads("PRV_th_" + name, quads, mat)
    o.name = "PRV_th_" + name
    return o


# 물고기 한 마리의 윤곽(단위 길이 1). 꼬리가 갈라져 있어서 작아도 물고기로 읽힌다.
FISH = [(1.00, 0.00), (0.46, 0.30), (-0.30, 0.28), (-0.70, 0.52), (-0.58, 0.00),
        (-0.70, -0.52), (-0.30, -0.28), (0.46, -0.30)]
# 손톱 하나 — 작은 쉼표. 몸 하나에 갈고리 하나.
CLAW = [(1.00, 0.00), (0.10, 0.26), (-0.85, 0.20), (-1.00, -0.02), (-0.10, -0.22)]


def th_shape(name, outline, x, z, s, mat, ang=0.0, sy=1.0):
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(x + (px * s) * ca - (pz * s * sy) * sa, z + (px * s) * sa + (pz * s * sy) * ca)
           for px, pz in outline]
    return th_poly(name, pts, mat)


def threat_swarm(near):
    """작은 떼 — 수십 마리가 **한 덩어리로** 움직인다(COMBAT §4). 막는 법: 사람 수.
    판독 단서: 중간 크기의 개체가 여럿, 덩어리의 윤곽이 렌즈 모양."""
    rnd = random.Random(21)
    cx = 2.3 if near else -0.4
    rx, rz = (3.1, 1.45) if near else (3.9, 1.15)
    th_blob("swarm_cloud", cx, 0.2, rx * 1.25, rz * 1.9, near, k=0.42)
    th_rim("swarm_rim", cx, 0.2, rx * 1.45, rz * 2.2, near, k=0.9)
    mat = th_mat(near, 1.0 if near else 0.86, "swarm")
    n = 74 if near else 46
    for i in range(n):
        a = rnd.uniform(0, 6.2832)
        r = rnd.random() ** 0.55
        x = cx + math.cos(a) * rx * r
        z = 0.2 + math.sin(a) * rz * r
        sz = (0.40 if near else 0.25) * rnd.uniform(0.75, 1.30)
        th_shape("sw%d" % i, FISH, x, z, sz, mat, ang=math.radians(rnd.uniform(-18, 18)))
    if near:                                     # 유리에 먼저 닿은 몇 마리 — 가장 크게
        for i, (x, z, sz) in enumerate(((5.35, 0.95, 0.60), (5.55, -0.35, 0.56),
                                        (5.15, -1.25, 0.52), (5.70, 0.30, 0.50))):
            th_shape("swn%d" % i, FISH, x, z, sz, mat, ang=math.radians(rnd.uniform(-10, 10)))


def threat_longneck(near):
    """긴목 — **목이 먼저 온다.** 몸은 아직 어둠 속이다(§3-1).
    불빛에 끌려 유리에 얼굴을 붙인다. 막는 법: 불을 끈다.
    판독 단서: 화면을 가로지르는 **한 줄기 곡선**과 그 끝의 작은 머리."""
    if near:
        p0, p1, p2 = (-7.0, -3.0), (-0.8, -1.8), (4.5, 1.05)
        wb, wt = 0.78, 0.46
    else:
        p0, p1, p2 = (-7.0, -1.6), (-3.0, 2.0), (1.4, 0.45)
        wb, wt = 0.40, 0.20
    pts = []
    for k in range(37):
        t = k / 36.0
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        z = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        # 굵기에 아주 느린 흔들림 — 띠(리본)로 읽히지 않게 한다
        w = (wb + (wt - wb) * t ** 0.7) * (1.0 + 0.16 * math.sin(t * 7.0 + 0.6))
        pts.append((x, z, w))
    mat = th_mat(near, 1.0, "ln")
    th_strip("lnneck", pts, mat)
    hxx, hzz, hr = pts[-1]
    ang = math.atan2(pts[-1][1] - pts[-4][1], pts[-1][0] - pts[-4][0])
    # 머리 — 아래턱이 길고 뒤통수가 둥근 물뱀 머리. 사각 조각을 따로 붙이지 않는다
    head = [(2.35, -0.10), (1.80, 0.34), (0.70, 0.78), (-0.35, 0.80), (-1.05, 0.30),
            (-1.05, -0.40), (-0.20, -0.74), (1.10, -0.64), (2.05, -0.44)]
    th_shape("lnhead", head, hxx + hr * 0.9 * math.cos(ang), hzz + hr * 0.9 * math.sin(ang),
             hr * 1.45, mat, ang=ang)
    # 어둠 속의 몸 — 목보다 훨씬 흐리다. "몸은 아직 안 보인다"
    th_blob("lnbody", p0[0] + 0.6, p0[1] + 0.3, 3.2 if near else 2.4,
            1.9 if near else 1.4, near, k=0.60)
    th_rim("lnrim", hxx + hr * 1.0, hzz + hr * 0.4, hr * 3.4, hr * 2.4, near, k=0.55)
    if near:                                     # 눈 — 밝지 않다. 물빛이 한 점 스칠 뿐
        soft_blob("th_lneye", hxx + hr * 1.55, hzz + hr * 1.05, 0.15, 0.13, TH_RIM,
                  alpha=0.30, y=-0.4)


def threat_gatekeeper(near):
    """문지기 — 화면을 가로지르는 그림자. 크기는 **양쪽 화면 밖으로 이어져야** 전해진다(§3-2).
    소리에 온다. 물이 조용해지면 온 것이다. 막는 법: 소리를 죽인다.

    3차 렌더에서 아래를 잘라 덩어리로 놓았더니 **산등성이**로 읽혔다(바다에 섬은 없다).
    그래서 위아래가 다 휜 긴 방추형으로 바꿨다 — 끝이 양쪽 화면 밖이라 길이를 알 수 없다.
    판독 단서: 화면을 가로지르는 **한 몸**, 지느러미 둘, 둘레에 다른 것이 하나도 없다."""
    n = 44
    if near:
        zc, hmax, hend, mat = -0.55, 2.45, 1.05, th_mat(True, 0.98, "gk")
        fin_s, hz_r = 1.35, 3.0
    else:
        zc, hmax, hend, mat = -1.70, 1.25, 0.50, th_mat(False, 1.45, "gk")
        fin_s, hz_r = 0.85, 1.9
    pts = []
    for k in range(n):
        t = k / (n - 1.0)
        x = -8.4 + 16.8 * t
        z = zc + 0.55 * math.sin(math.pi * t) + 0.18 * math.sin(t * 2.2)
        hw = hend + (hmax - hend) * math.sin(math.pi * (0.06 + 0.88 * t)) ** 0.55
        pts.append((x, z, hw))
    th_strip("gkbody", pts, mat)
    # 등지느러미 — 뒤로 휜다. 삼각 피라미드는 기하 도형으로 보인다(2차 렌더가 그랬다)
    fin = [(0.00, 1.00), (-0.26, 0.66), (-0.40, 0.26), (-0.42, -0.05),
           (0.52, -0.08), (0.74, 0.10), (0.46, 0.44), (0.20, 0.78)]
    fx, fz, fw = pts[13]
    th_shape("gkfin", fin, fx, fz + fw * 0.88, fin_s, mat, ang=0.10)
    # 가슴지느러미 — 몸 아래로 한 장. 이것이 '바위'와 '생물'을 가른다
    pec = [(0.0, 0.2), (1.25, -0.35), (1.6, -0.95), (0.5, -0.78), (-0.5, -0.25)]
    px_, pz_, pw_ = pts[27]
    th_shape("gkpec", pec, px_, pz_ - pw_ * 0.80, fin_s * 1.15, mat, ang=-0.12)
    th_blob("gkhaze", 0.0, zc, 7.8, hz_r, near, k=0.38)
    th_rim("gkrim", 0.0, zc + hmax * 0.55, 7.4, 0.9, near, k=0.55)


def threat_clawswarm(near):
    """손톱 무리 — 느리고 작고 수백. 바닥 쪽에서 올라온다(§3-3).
    막는 법: 밖에 나간 사람을 즉시 들인다.
    판독 단서: **점의 밀도**다. 개체는 끝내 안 보이고 알갱이 띠로만 읽힌다."""
    rnd = random.Random(404)
    mat = th_mat(near, 1.0 if near else 1.95, "claw")
    n = 760 if near else 520
    for i in range(n):
        if near:
            x = rnd.uniform(-5.8, 5.9)
            z = rnd.gauss(-1.45, 1.05)
            sz = rnd.uniform(0.045, 0.085)
        else:
            x = rnd.uniform(-5.9, 3.8)
            z = rnd.gauss(-2.00, 0.80)
            sz = rnd.uniform(0.038, 0.068)
        if z < -2.9 or z > 1.6:
            continue
        th_shape("cl%d" % i, CLAW, x, z, sz, mat,
                 ang=math.radians(rnd.uniform(-35, 35)), sy=1.35)
    th_blob("claw_haze", 0.8 if near else -1.0, -1.7 if near else -2.1,
            6.0, 1.7 if near else 1.1, near, k=0.34)
    th_rim("claw_rim", 0.6, -1.6, 6.4, 1.6, near, k=0.5)


THREATS = [
    ("swarm", "작은 떼", threat_swarm, "사람 수로 막는다. 누구든 여럿"),
    ("longneck", "긴목", threat_longneck, "불을 끈다(차광 덧문·유인 등불)"),
    ("gatekeeper", "문지기", threat_gatekeeper, "소리를 죽인다(소리 가리개·전원 차단)"),
    ("clawswarm", "손톱 무리", threat_clawswarm, "밖에 나간 사람을 즉시 들인다(귀환 신호기)"),
]


def build_threat(fn, near):
    materials()
    section_world()
    fn(near)
    flatten_materials()
    drop_lights()
    noline_setup()


def shot_threats():
    os.makedirs(OUT_THREAT, exist_ok=True)
    out = []
    for tid, name, fn, counter in THREATS:
        files = {}
        for stage, near in (("far", False), ("near", True)):
            build_threat(fn, near)
            f = "threat_%s_%s.png" % (tid, stage)
            render(os.path.join(OUT_THREAT, f), ortho=THREAT_W_M, target=(0.0, 0, 0.0),
                   res=THREAT_RES, grain=0.13, vig=0.0, alpha=True, line=0.0)
            files[stage] = f
        out.append({"id": tid, "name": name, "counter": counter, "files": files})
    meta = {
        "_note": "S8-C 바깥에서 오는 것들. 전투 예고 2단계(COMBAT_AND_DEFENSE §3-2).",
        "_rule": ("물 위에 그대로 얹는 RGBA. 플레이트와 같은 84px/m 격자다. "
                  "오른쪽(+x)이 거점 쪽 — 거점이 왼쪽이면 좌우 반전해서 쓴다."),
        "canvas": list(THREAT_RES), "px_per_m": PLATE_PPM,
        "stages": {"far": "멀리 있는 흐릿한 그림자 — 어느 방이 위험한지 아직 모른다",
                   "near": "창에 가까이 온 상태 — 대상 방이 정해졌다"},
        "approach": "right",
        "threats": out,
    }
    with open(os.path.join(OUT_THREAT, "threats_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("THREAT META", os.path.join(OUT_THREAT, "threats_meta.json"), flush=True)




# ══════════════════════════════════════════════════════════════
# 팔레트 띠 — 색과 문양을 한 장으로 (작업 기준표)
# ══════════════════════════════════════════════════════════════
def shot_palette():
    materials()
    section_world()
    rows = [(rid, hue) for rid, lv, x0, x1, hue, fill, npc in layout()]
    w, gap = 3.4, 0.45
    total = len(rows) * (w + gap) - gap
    x = -total / 2
    for rid, hue in rows:
        # 기본색 / 그림자색 2단
        DOME.mesh_of_quads("sw_" + rid, [[Vector((x, 0, 0)), Vector((x + w, 0, 0)),
                                          Vector((x + w, 0, 3.0)), Vector((x, 0, 3.0))]],
                           flat_mat("sw_m_" + rid, hue))
        DOME.mesh_of_quads("sh_" + rid, [[Vector((x, 0, -1.1)), Vector((x + w, 0, -1.1)),
                                          Vector((x + w, 0, 0)), Vector((x, 0, 0))]],
                           flat_mat("sh_m_" + rid, hx(hue, 0.52)))
        pm = flat_mat("pp_" + rid, M["pat_light"] if _is_dark(hue) else M["pat_dark"])
        MOTIF[rid](rid, x + 0.3, x + w - 0.3, 1.2, pm)
        x += w + gap
    # 물 그라디언트 띠 — 위 광층에서 아래 해구까지
    DOME.mesh_of_quads("sw_water", [[Vector((-total / 2, 0.4, -5.6)), Vector((total / 2, 0.4, -5.6)),
                                     Vector((total / 2, 0.4, -2.2)), Vector((-total / 2, 0.4, -2.2))]],
                       _water_strip())
    flatten_materials()
    drop_lights()
    noline_setup()
    render(os.path.join(OUT_RAW, "section_palette.png"), ortho=total + 3.0,
           target=(0.0, 0, -1.2), res=(1600, 500), grain=0.08, vig=0.05)


def _water_strip():
    """팔레트 띠에서 물만 가로 방향 그라디언트로 보여 준다(위=광층 → 아래=해구)."""
    m = bpy.data.materials.new("WaterStrip"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); geo = nt.nodes.new("ShaderNodeNewGeometry")
    mr = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["X"], mr.inputs["Value"])
    mr.inputs["From Min"].default_value = -16.0; mr.inputs["From Max"].default_value = 16.0
    nt.links.new(mr.outputs[0], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*srgb_hexcol(ZONE_STOPS[-1][1]), 1)
    for p, c in ZONE_STOPS[-2::-1]:
        e = cr.elements.new(1.0 - p); e.color = (*srgb_hexcol(c), 1)
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return _mark(m)


if __name__ == "__main__":
    jobs = {"hero": shot_hero, "zoom": shot_zoom, "palette": shot_palette,
            "warm": shot_warm, "roomzoom": shot_roomzoom,
            "before": shot_before, "beforehero": shot_before_hero,
            # S8-C
            "warmnoppl": shot_warm_noppl, "roomzoomnoppl": shot_roomzoom_noppl,
            "plates": shot_plates, "threats": shot_threats}
    for k in (["hero", "zoom", "palette"] if MODE == "all" else [MODE]):
        jobs[k]()
    print("ALL DONE", flush=True)
