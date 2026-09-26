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
import bpy, sys, os, math, importlib.util, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"

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
    # 해구 바닥 능선 — 화면 맨 아래를 닫는다
    ridge = []
    x = -80.0
    while x < 80.0:
        w = rnd.uniform(6.0, 15.0); hgt = rnd.uniform(1.6, 5.2)
        ridge.append([Vector((x, 15.0, -30)), Vector((x + w, 15.0, -30)),
                      Vector((x + w, 15.0, -11.4 + hgt)), Vector((x, 15.0, -11.4 + hgt))])
        x += w * 0.92
    DOME.mesh_of_quads("PRV_ridge", ridge, dk).name = "PRV_ridge"
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


def marine_snow():
    """부유물 — 1차 대비 절반 이하, 반투명, 전부 물빛 계열. 방 불빛보다 절대 밝지 않다(지적 5)."""
    rnd = random.Random(818)
    tiers = [(9,  0.70, (-8.0, -5.0), "#16323D", 0.055, 1.0),
             (22, 0.30, (-4.2, -2.2), "#1B3B47", 0.075, 1.4),
             (48, 0.125, (4.0, 9.0),  "#20475A", 0.11, 2.0),
             (64, 0.055, (11.0, 21.0), "#12303C", 0.13, 1.6)]
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


def motif_dots(rid, x0, x1, z, m, unit=0.46):
    """창고 — 점 격자. 세어 놓은 재고."""
    n = max(2, int((x1 - x0) / unit))
    for row, dz in enumerate((0.0, 0.26, 0.52)):
        for k in range(n):
            x = x0 + (k + 0.5) * (x1 - x0) / n + (0.2 if row % 2 else 0.0)
            _bar(rid, x, z + dz, 0.11, 0.11, m, math.radians(45))


def motif_hatch(rid, x0, x1, z, m, unit=0.34):
    """서고 — 세로 빗금. 꽂힌 책등."""
    n = max(2, int((x1 - x0) / unit))
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        h = (0.40, 0.28, 0.52, 0.34)[k % 4]
        _bar(rid, x, z + h / 2, 0.10, h, m)


def motif_wave(rid, x0, x1, z, m, unit=0.30):
    """목욕탕 — 물결. 민물의 사치."""
    n = max(4, int((x1 - x0) / unit))
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        dz = math.sin(k * 0.9) * 0.17
        _bar(rid, x, z + dz, 0.22, 0.085, m, math.radians(math.cos(k * 0.9) * 34))


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
         "bath": motif_wave, "airlock": motif_diamond}


# ══════════════════════════════════════════════════════════════
# 방 — 깊이 1.7m 의 얕은 디오라마 (형상은 그대로, 채색만 평면 2단)
# ══════════════════════════════════════════════════════════════
def room_halo(x0, x1, z0, z1):
    """F7. 방 둘레의 어두운 여백(지적 4). 그라데이션이 아니라 **계단 세 칸**이다(§1-3).
    안쪽일수록 검고 바깥으로 갈수록 그 높이의 물색으로 돌아간다."""
    for mkey, mar, y in (("halo2", 1.95, 4.0), ("halo1", 0.78, 3.6)):
        q = [Vector((x0 - mar, y, z0 - mar)), Vector((x1 + mar, y, z0 - mar)),
             Vector((x1 + mar, y, z1 + mar)), Vector((x0 - mar, y, z1 + mar))]
        DOME.mesh_of_quads("PRV_halo", [q], M[mkey]).name = "PRV_halo"


def room_shell(x0, x1, z0, hue, rid):
    """절두각뿔 상자. 채색은 기본색 / 그림자색 딱 2단(§1-3). 방 안에 그라데이션 없음."""
    base = hx(hue, 0.88)                      # 기본색 — 등불보다 항상 어둡게 눌러 둔다(F7)
    shade = hx(hue, 0.46)                     # 단 한 단계의 그림자. 이것이 전부다.
    backm = flat_mat("back_" + rid, base)
    floorm = flat_mat("floor_" + rid, shade)
    ceilm = flat_mat("ceil_" + rid, shade)
    sidem = flat_mat("side_" + rid, shade)
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
    pm = flat_mat("pat_m_" + rid, M["pat_light"] if _is_dark(hue) else M["pat_dark"])
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


def room_lamp(x, z0, hue, rid):
    """F7. 방마다 등불 하나(B1). 화면에서 가장 밝은 것은 언제나 이것이다.
    광원 오브젝트는 쓰지 않는다(평면 2단 고정) — 밝은 알과 바닥의 빛 웅덩이로 그린다."""
    top = z0 + RH
    iso.cyl("lw_" + rid, (x, 0.55, top - 0.18), 0.02, 0.36, M["frame"], rot=(math.radians(90), 0, 0))
    iso.cyl("ls_" + rid, (x, 0.55, top - 0.44), 0.22, 0.18, M["frame_lt"])
    # 등불 헤일로 — 평면 원 두 겹(§1-3: 그라데이션 금지)
    disc("PRV_glow2_" + rid, x, top - 0.52, 1.05, M["glow_far"], y=0.50)
    disc("PRV_glow1_" + rid, x, top - 0.52, 0.52, M["glow_near"], y=0.49)
    o = iso.sphere("lb_" + rid, (x, 0.48, top - 0.52), 0.155, M["bulb"], 12, 7)
    o.name = "PRV_bulb_" + rid
    # 바닥의 빛 웅덩이 — 민속화의 방식: 빛을 그라데이션이 아니라 '도형'으로 그린다
    pw = 1.65
    qp = [Vector((x - pw, DEPTH - 0.55, z0 + 0.012)), Vector((x + pw, DEPTH - 0.55, z0 + 0.012)),
          Vector((x + pw * 0.62, 0.12, z0 + 0.012)), Vector((x - pw * 0.62, 0.12, z0 + 0.012))]
    DOME.mesh_of_quads("PRV_pool_" + rid, [qp], flat_mat("poolm_" + rid, hx(hue, 1.34))).name = "PRV_pool_" + rid


def disc(name, x, z, r, m, y=0.45, verts=14):
    """카메라를 향한 평면 다각형. 빛을 그라데이션이 아니라 도형으로 그린다(§1-3)."""
    o = iso.cyl(name, (x, y, z), r, 0.02, m, rot=(math.radians(90), 0, 0), verts=verts)
    o.name = name
    return o


def people(xs, z0, kinds, ys=None):
    for i, (x, k) in enumerate(zip(xs, kinds)):
        y = (ys[i] if ys else 0.55 + (i % 3) * 0.32)
        DOME.resident(k, x, y, z0, rot_z=math.radians(180 + (-22 if i % 2 else 20)), h=1.70)


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
    M["halo2"] = zone_gradient("Halo2", mult=0.30)
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
        rnd = random.Random(hash(rid) % 9999)
        xs = [x0 + (x1 - x0) * (i + 0.5) / max(npc, 1) + rnd.uniform(-0.5, 0.5) for i in range(npc)]
        people(xs, z0, [CREW[(hash(rid) + i) % 8] for i in range(npc)])
    dig_face(-8.5, -(SPINE + GAP), L[4])
    spine(DOME_C.z - 1.0, L[4] - 1.6)
    glass_dome(z_lounge)
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
            col = tuple(c * 0.35 + w * 0.65 for c, w in zip(col, WARM))
            lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
            col = tuple(c * 0.55 + lum * 0.45 for c in col)
            lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
            if lum > 0.34:                        # F7. 사람은 절대 등불보다 밝지 않다
                col = tuple(c * (0.34 / lum) for c in col)
            img = None
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
                "PRV_ridge", "PRV_farrock", "PRV_farcable", "PRV_lev", "PRV_halo",
                "PRV_glow1_", "PRV_glow2_", "PRV_pool_", "dome_backglass", "pat_")


def handdrawn_lines():
    """F6. 손으로 그은 선 — 두께 변화(NOISE) + 흔들림(PERLIN_2D, SINUS). 매끈한 벡터 선 금지."""
    sc = bpy.context.scene
    sc.render.use_freestyle = True
    sc.render.line_thickness = 1.0
    vl = sc.view_layers[0]; vl.use_freestyle = True
    fs = vl.freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("relic")
    ls.select_silhouette = ls.select_crease = ls.select_border = True
    ls.select_by_collection = True
    ls.collection = bpy.data.collections["NOLINE"]
    ls.collection_negation = 'EXCLUSIVE'
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("relic_ls")
    st = ls.linestyle
    st.color = srgb_hexcol(PAL["char"])
    st.thickness = 1.9
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
        cur = grain_layer(46.0, 1.0 - grain, 1.0 + grain * 0.55, cur)     # 종이 결(굵게)
        cur = grain_layer(340.0, 1.0 - grain * 0.45, 1.0 + grain * 0.2, cur)  # 연필 자국(가늘게)
        # 비네트 — 가장자리를 숯검정 쪽으로
        msk = ng.nodes.new("CompositorNodeEllipseMask")
        msk.inputs["Size"].default_value = (1.02, 1.12)
        blur = ng.nodes.new("CompositorNodeBlur")
        blur.inputs["Size"].default_value = 210.0
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


def render(path, ortho, target, res=(1600, 900), grain=0.11, vig=0.10):
    sc = bpy.context.scene
    loc = Vector((target[0], -70.0, target[2]))
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.clip_start, cam.data.clip_end = 0.1, 400.0
    sc.camera = cam
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    try:
        sc.eevee.taa_render_samples = 24
    except Exception:
        pass
    handdrawn_lines()
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
    render(os.path.join(OUT_RAW, "section_zoom.png"), ortho=24.0, target=(0.0, 0, 3.2),
           grain=0.09, vig=0.08)


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
    jobs = {"hero": shot_hero, "zoom": shot_zoom, "palette": shot_palette}
    for k in (["hero", "zoom", "palette"] if MODE == "all" else [MODE]):
        jobs[k]()
    print("ALL DONE", flush=True)
