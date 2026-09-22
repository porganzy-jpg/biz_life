# -*- coding: utf-8 -*-
"""
잔해 방주 — 1막 거점 「정면 평면 단면」 (S4-B)
blender -b --python tools/blender_section.py -- hero
blender -b --python tools/blender_section.py -- zoom
blender -b --python tools/blender_section.py -- all

산출물
  art_raw/deep/section_hero.png   거점 전체가 한 화면에 (1600×900)
  art_raw/deep/section_zoom.png   방 3칸 확대 (1600×900)

근거
  DECISIONS 2026-09-23 ①정면 평면 단면 ②성장 방향은 아래 ③D1 개정(방마다 고유 색상)
  docs/refs/REF_CROSS_SECTION.md §1 원리 10가지 (모방 금지, 원리만)

화면 문법
  · 정면 직교(원근 0). 카메라는 -Y 에서 +Y 를 본다. 화면 가로 = +X, 화면 세로 = +Z
  · 방은 평면이 아니라 **깊이 1.7m 의 얕은 디오라마**. 앞면이 뒷면보다 커서(절두각뿔)
    정면 직교에서도 바닥·천장·옆벽이 비스듬히 보인다 = 납작하지 않다 (원리 2)
  · 방과 방 사이 = **물**. 저쪽의 검은 바위 자리가 우리는 움직이는 물이다 (원리 3 + 우리 강점)
  · 방마다 고유 색 (원리 4, D1 개정). 전부 난색 쪽, 명도는 항상 물보다 높다
  · 유리 척추 = 유일한 수직 채도 축 = 승강 통로 (원리 5)
  · 방마다 사람 2~6명, 빈 방 없음 (원리 6)
  · 세로축 = 광층 / 박광층 / 무광층 / 해구. 아래로 자란다 (우리 성경)

코드 재사용: blender_dome → blender_scenes → blender_iso 를 import 로 그대로 쓴다.
             재질·원시도형·CC0 소품·부유물·대형 생물 실루엣·선 제외 컬렉션 모두 재정의하지 않는다.
"""
import bpy, sys, os, math, importlib.util, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT_RAW = os.path.join(ROOT, "art_raw", "deep")
os.makedirs(OUT_RAW, exist_ok=True)


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

# ── 정면 직교 시점의 화면 기저 (blender_dome 의 부유물·실루엣 헬퍼가 이 값을 본다) ──
V_FRONT = Vector((0, -1, 0))          # 씬 → 카메라
RIGHT_FRONT = Vector((1, 0, 0))       # 화면 오른쪽 = +X
UP_FRONT = Vector((0, 0, 1))          # 화면 위   = +Z

# ── 규격 ────────────────────────────────────────────────────
DEPTH = 1.7          # 방 디오라마 깊이 (원리 2: 1~2m)
INSET_X = 1.05       # 뒷벽이 앞면보다 좌우로 들어간 양 → 옆벽이 보인다
INSET_ZB = 0.62      # 바닥이 뒤로 갈수록 올라오는 양 → 바닥이 보인다
INSET_ZT = 0.46      # 천장이 뒤로 갈수록 내려오는 양 → 천장이 보인다
RH = 3.0             # 방 안높이
HULL = 0.42          # 방을 두르는 구조 테두리 두께(물에서 떼어 내는 장치)
SPINE = 1.35         # 유리 척추 반폭
GAP = 0.55           # 척추와 방 사이 / 방과 방 사이의 물 틈

DOME_C, DOME_R = Vector((0, 0, 17.2)), 5.4       # 꼭대기 유리돔 (기존 아이소 돔과 같은 형상)

# 층 바닥 높이 — 성장 방향은 아래(DECISIONS 2026-09-23)
L = {1: 6.4, 2: 2.0, 3: -2.4, 4: -6.8}

# 방 정의: (id, 이름, 층, 좌우, 칸수, 고유색, 채움함수)
#   고유색은 전부 난색 쪽이고 명도는 물보다 높다 (D1 개정)
ROOMS = []


def hexm(name, h, rough=0.85, emit=None, strength=0.0):
    return iso.mat(name, h, rough, emit=emit, strength=strength)


M = {}


# ══════════════════════════════════════════════════════════════
# 물 — 네 구역 그라디언트 + 안개 + 부유물 + 실루엣
# ══════════════════════════════════════════════════════════════
def zone_gradient():
    """광층 → 박광층 → 무광층 → 해구. 한 장의 세로 그라디언트가 곧 지도이자 진행도다."""
    m = bpy.data.materials.new("WaterZones"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mr = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mr.inputs["From Min"].default_value = -16.0     # 해구
    mr.inputs["From Max"].default_value = 30.0      # 광층
    nt.links.new(mr.outputs[0], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    stops = [(0.00, "#000000"),      # 해구 — 칠흑
             (0.30, "#01080e"),      # 해구 ↔ 무광층
             (0.52, "#05202b"),      # 무광층 — 돔이 사는 층
             (0.78, "#0f4055"),      # 박광층 — 실루엣의 층
             (1.00, "#3d94a8")]      # 광층 — 갈 수 없는 빛
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = stops[0][0]; cr.elements[0].color = (*iso.hexcol(stops[0][1]), 1)
    for p, c in stops[1:]:
        e = cr.elements.new(p); e.color = (*iso.hexcol(c), 1)
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def water_plane(depth=26.0, w=140.0, h=110.0):
    q = [Vector((-w / 2, depth, -h / 2 + 7)), Vector((w / 2, depth, -h / 2 + 7)),
         Vector((w / 2, depth, h / 2 + 7)), Vector((-w / 2, depth, h / 2 + 7))]
    o = DOME.mesh_of_quads("PRV_backdrop", [q], M["zones"]); o.name = "PRV_backdrop"
    return o



# ══════════════════════════════════════════════════════════════
# 물의 부피 — 초점 없는 부유물 / 감쇠 안개 / 내려오는 빛
#   별과 부유물의 차이는 초점이다. 또렷한 흰 점은 하나도 쓰지 않는다.
# ══════════════════════════════════════════════════════════════
def mesh_uv_quads(name, quads, material):
    """쿼드마다 0..1 UV 를 붙인 메시. 소프트 마스크 재질이 이 UV 를 쓴다."""
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


def soft_mat(name, hexc, alpha=0.35, strength=1.0, edge=0.0, core=1.0):
    """중심에서 가장자리로 사라지는 발광 마스크 = 초점 안 맞은 덩어리.
    core 를 낮추면 더 퍼진다(= 더 흐리다)."""
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
    cr.elements[0].position = edge; cr.elements[0].color = (0, 0, 0, 1)
    cr.elements[1].position = core; cr.elements[1].color = (alpha, alpha, alpha, 1)
    cr.interpolation = 'EASE'
    em.inputs["Color"].default_value = (iso.hexcol(hexc)[0], iso.hexcol(hexc)[1], iso.hexcol(hexc)[2], 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(ramp.outputs["Color"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED"),
                      ("show_transparent_back", False)):
        try:
            setattr(m, attr, val)
        except Exception:
            pass
    return m


def marine_snow():
    """부유물 4단계. 가까울수록 크고 흐리고, 멀수록 작고 물빛에 가깝다.
    또렷한 흰 점은 하나도 없다 — 전부 소프트 마스크이고 색도 물빛 계열이다."""
    rnd = random.Random(818)
    tiers = [(22, 0.85, (-9.0, -5.0), "#1e3f4c", 0.085, 1.0),
             (55, 0.34, (-4.5, -2.0), "#26505f", 0.12, 1.4),
             (120, 0.135, (-1.8, 3.0), "#2e5f70", 0.17, 2.2),
             (170, 0.060, (3.5, 15.0), "#173846", 0.20, 1.7)]
    for ti, (n, r, dep, col, al, stretch) in enumerate(tiers):
        mt = soft_mat("Snow%d" % ti, col, al, 1.0, 0.0, 0.05 if ti < 2 else 0.25)
        quads = []
        for _ in range(n):
            x = rnd.uniform(-34, 34); z = rnd.uniform(-14, 30); y = rnd.uniform(dep[0], dep[1])
            rx = r * rnd.uniform(0.55, 1.5)
            rz = rx * stretch * rnd.uniform(0.7, 1.5)
            quads.append([Vector((x - rx, y, z - rz)), Vector((x + rx, y, z - rz)),
                          Vector((x + rx, y, z + rz)), Vector((x - rx, y, z + rz))])
        mesh_uv_quads("PRV_snow%d" % ti, quads, mt).name = "PRV_snow%d" % ti


def soft_jellies():
    """발광 해파리 — 또렷한 구가 아니라 부드러운 발광 원반 + 짧은 촉수 + 넓은 헤일로."""
    rnd = random.Random(707)
    disc = soft_mat("JellyGlow", "#57c6cf", 0.55, 2.2, 0.0, 0.62)
    halo = soft_mat("JellyHalo", "#3a8fa0", 0.20, 1.1, 0.0, 0.22)
    tent = soft_mat("JellyTent", "#3f9aa8", 0.28, 0.9, 0.0, 0.5)
    qd, qh, qt = [], [], []
    for k in range(9):
        x = rnd.uniform(-32, 32); z = rnd.uniform(-8, 26); y = rnd.uniform(-6.0, 9.0)
        r = 0.34 + rnd.random() * 0.34
        qd.append([Vector((x - r, y, z - r * 0.75)), Vector((x + r, y, z - r * 0.75)),
                   Vector((x + r, y, z + r * 0.75)), Vector((x - r, y, z + r * 0.75))])
        h = r * 3.4
        qh.append([Vector((x - h, y + 0.1, z - h)), Vector((x + h, y + 0.1, z - h)),
                   Vector((x + h, y + 0.1, z + h)), Vector((x - h, y + 0.1, z + h))])
        tw, th = r * 0.85, r * 2.4
        qt.append([Vector((x - tw, y - 0.05, z - th)), Vector((x + tw, y - 0.05, z - th)),
                   Vector((x + tw, y - 0.05, z + 0.1)), Vector((x - tw, y - 0.05, z + 0.1))])
    mesh_uv_quads("PRV_jhalo", qh, halo).name = "PRV_jhalo"
    mesh_uv_quads("PRV_jtent", qt, tent).name = "PRV_jtent"
    mesh_uv_quads("PRV_jelly", qd, disc).name = "PRV_jelly"


def soft_shafts():
    """광층에서 내려오는 흐린 빛기둥. 위는 미세하게 밝고 해구로 갈수록 완전한 검정."""
    rnd = random.Random(404)
    quads = []
    for k in range(9):
        x = rnd.uniform(-32, 32)
        w = rnd.uniform(2.4, 6.0); top = 33.0; bot = rnd.uniform(2.0, 15.0)
        cz = (top + bot) / 2; hz = (top - bot) / 2
        quads.append([Vector((x - w, 17.0, cz - hz)), Vector((x + w, 17.0, cz - hz)),
                      Vector((x + w, 17.0, cz + hz)), Vector((x - w, 17.0, cz + hz))])
    mt = soft_mat("Shaft", "#6fbccb", 0.055, 1.0, 0.0, 0.03)
    mesh_uv_quads("PRV_shaft", quads, mt).name = "PRV_shaft"


def deep_structures():
    """거점 뒤 5~20m 에 놓는 구조물·바위. 안개가 이것을 절반쯤 먹어서
    '거리에 따라 물빛이 물체를 먹는다'가 눈에 보이게 한다 — 이것이 물속의 80%다."""
    rnd = random.Random(1234)
    dk = hexm("FarRock", "#08161d", 1.0)
    dk2 = hexm("FarSteel", "#0d2029", 0.9)
    for k in range(4):
        y = rnd.uniform(6.0, 11.0)
        x = rnd.uniform(-26, 26); z = rnd.uniform(-8, 12)
        w, h = rnd.uniform(3.0, 7.0), rnd.uniform(2.2, 3.4)
        iso.cube("far_mod", (x, y, z), (w, 2.0, h), dk2)
        iso.cube("far_modf", (x, y - 1.1, z), (w + 0.5, 0.3, h + 0.5), dk)
    for k in range(3):
        y = rnd.uniform(5.0, 9.0)
        x0, x1 = rnd.uniform(-26, 26), rnd.uniform(-26, 26)
        DOME.strut("far_cable", (x0, y, 32), (x1, y, -14), 0.06, dk2, 5)
    for k in range(12):
        y = rnd.uniform(4.0, 10.0)
        x = rnd.uniform(-34, 34)
        r = rnd.uniform(1.6, 5.0)
        o = iso.sphere("far_rock", (x, y, rnd.uniform(-18, -8)), r, dk, 10, 6)
        o.scale = (1.0, 0.5, 0.45)


def absorb_fog(density=0.013):
    """감쇠 안개 — 산란 + 흡수. 가까운 방은 선명하고 뒤는 물색에 잠긴다."""
    w = bpy.context.scene.world
    try:
        nt = w.node_tree
        out = nt.nodes["World Output"]
        for lk in list(nt.links):
            if lk.to_socket is out.inputs["Volume"]:
                nt.links.remove(lk)
        vs = nt.nodes.new("ShaderNodeVolumeScatter")
        vs.inputs["Color"].default_value = (iso.hexcol("#2f7f96")[0], iso.hexcol("#2f7f96")[1], iso.hexcol("#2f7f96")[2], 1)
        vs.inputs["Density"].default_value = density * 0.30
        try:
            vs.inputs["Anisotropy"].default_value = 0.35
        except Exception:
            pass
        va = nt.nodes.new("ShaderNodeVolumeAbsorption")
        va.inputs["Color"].default_value = (iso.hexcol("#123642")[0], iso.hexcol("#123642")[1], iso.hexcol("#123642")[2], 1)
        va.inputs["Density"].default_value = density * 1.6
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(vs.outputs["Volume"], add.inputs[0])
        nt.links.new(va.outputs["Volume"], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs["Volume"])
    except Exception as e:
        print("ABSORB SKIPPED", e, flush=True)


# ══════════════════════════════════════════════════════════════
# 방 — 깊이 1.7m 의 얕은 디오라마 (원리 2)
# ══════════════════════════════════════════════════════════════
def room_shell(x0, x1, z0, hue, rid, dark=False):
    """절두각뿔 상자: 앞면(열림) > 뒷면. 바닥·천장·옆벽이 비스듬해 정면에서도 보인다."""
    base = hexm("wall_" + rid, hue, 0.9)
    backm = hexm("back_" + rid, hue, 0.9, emit=hue, strength=0.34)
    floorm = hexm("floor_" + rid, _shade(hue, 0.62), 0.9)
    ceilm = hexm("ceil_" + rid, _shade(hue, 0.42), 0.9)
    sidem = hexm("side_" + rid, _shade(hue, 0.78), 0.9)
    z1 = z0 + RH
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
    # 구조 테두리 — 방을 물에서 떼어 내는 장치(원리 3). 우리는 검정이 아니라 어두운 선체색
    fr = M["frame"]
    iso.cube("hull_b_%s" % rid, ((x0 + x1) / 2, D / 2 - 0.1, z0 - HULL / 2), (x1 - x0 + HULL * 2, D + 0.4, HULL), fr)
    iso.cube("hull_t_%s" % rid, ((x0 + x1) / 2, D / 2 - 0.1, z1 + HULL / 2), (x1 - x0 + HULL * 2, D + 0.4, HULL), fr)
    for sx in (x0 - HULL / 2, x1 + HULL / 2):
        iso.cube("hull_s_%s" % rid, (sx, D / 2 - 0.1, (z0 + z1) / 2), (HULL, D + 0.4, RH + HULL * 2), fr)
    for sx in (x0 + 0.5, x1 - 0.5):                     # 앞면 모서리 리브 = 유리 프레임
        iso.cube("rib_%s" % rid, (sx, -0.06, (z0 + z1) / 2), (0.12, 0.12, RH), M["frame_lt"])
    return z0


def room_lamp(x, z0, hue, rid, energy=260):
    """방마다 등불 하나(B1). 정면 단면이라 앞쪽 천장에 매단다."""
    top = z0 + RH
    iso.cyl("lw_" + rid, (x, 0.55, top - 0.18), 0.02, 0.36, M["frame"], rot=(math.radians(90), 0, 0))
    sh = iso.cyl("ls_" + rid, (x, 0.55, top - 0.44), 0.22, 0.18, M["frame_lt"])
    iso.sphere("lb_" + rid, (x, 0.55, top - 0.52), 0.13,
               hexm("bulb_" + rid, "#FFEAC6", 0.3, emit=hue, strength=14), 10, 6)
    bpy.ops.object.light_add(type='POINT', location=(x, 0.62, top - 0.52))
    l = bpy.context.object; l.name = "L_" + rid
    l.data.color = iso.hexcol(hue); l.data.energy = energy; l.data.shadow_soft_size = 0.5
    return sh


def _shade(h, f):
    r, g, b = iso.hexcol(h)
    return "#%02x%02x%02x" % (int(r * 255 * f), int(g * 255 * f), int(b * 255 * f))


def people(xs, z0, kinds, ys=None):
    """방마다 사람 2~6명(원리 6). 기존 역할 GLB 그대로."""
    for i, (x, k) in enumerate(zip(xs, kinds)):
        y = (ys[i] if ys else 0.55 + (i % 3) * 0.32)
        DOME.resident(k, x, y, z0, rot_z=math.radians(180 + (-22 if i % 2 else 20)), h=1.70)


# ══════════════════════════════════════════════════════════════
# 방 내용물 — blender_iso 의 생활 소품 헬퍼를 그대로 (B4 밀도)
# ══════════════════════════════════════════════════════════════
def at(z, fn, *a, **k):
    DOME.at(z, fn, *a, **k)


def fill_quarters(x0, x1, z0):
    c = (x0 + x1) / 2
    for i, dx in enumerate((-4.4, -2.6, 2.4, 4.3)):
        at(z0, iso.bedroll, c + dx, 1.05, math.radians(90))
    at(z0, iso.laundry, (c - 5.0, 0.35), (c + 1.0, 0.35), 2.45)
    at(z0, iso.plant, c - 5.4, 0.55, 0.6)
    at(z0, iso.plant, c + 5.2, 0.6, 0.5)
    at(z0, iso.shelf_unit, c + 1.2, 1.15)
    at(z0, iso.jug, c - 1.2, 0.5, 0.3)
    iso.prop("k:chest", c - 0.4, 1.2, z0, h=0.55, rot_z=0.2)
    iso.prop("k:box", c + 5.6, 1.15, z0, h=0.42, rot_z=-0.3)
    for k, dx in enumerate((-3.6, -3.0, -2.4)):
        iso.cube("note", (c + dx, DEPTH - 0.08, z0 + 1.9 + (k % 2) * 0.25), (0.22, 0.02, 0.28), M["paper"])
    iso.cube("table", (c + 2.9, 0.85, z0 + 0.25), (1.5, 0.8, 0.07), M["wood"])


def fill_greenhouse(x0, x1, z0):
    c = (x0 + x1) / 2
    rnd = random.Random(77)
    for k in range(3):
        iso.cube("bed", (c - 1.7 + k * 1.7, 1.1, z0 + 0.32), (1.4, 1.0, 0.64), M["wood_dk"])
        iso.cube("soil", (c - 1.7 + k * 1.7, 1.1, z0 + 0.66), (1.26, 0.9, 0.06), M["earth2"])
    for k in range(12):
        gx = c - 1.7 + (k % 3) * 1.7 + rnd.uniform(-0.4, 0.4)
        at(z0 + 0.69, iso.plant, gx, 1.1 + rnd.uniform(-0.3, 0.3), rnd.uniform(0.34, 0.58), False)
    at(z0, iso.plant, c - 2.5, 0.5, 0.7)
    at(z0, iso.plant, c + 2.4, 0.55, 0.62)
    for k, vx in enumerate((c - 2.2, c + 1.6)):
        at(z0, iso.vine, vx, DEPTH - 0.25, RH - 0.35, 1.5, 'x', 5 + k)
    at(z0, iso.jug, c + 1.5, 0.45, -0.3)
    iso.prop("k:bucket", c - 0.9, 0.45, z0, h=0.32, rot_z=0.4)


def fill_workshop(x0, x1, z0):
    c = (x0 + x1) / 2
    iso.prop("k:workbench", c - 1.4, 1.25, z0, h=1.0, rot_z=0.0)
    iso.prop("k:workbench-anvil", c + 1.5, 1.25, z0, h=1.0, rot_z=0.0)
    iso.prop("k:barrel", c + 2.5, 0.55, z0, h=0.85)
    iso.prop("k:box-large", c - 2.5, 0.6, z0, h=0.75, rot_z=0.2)
    iso.prop("k:resource-planks", c + 0.2, 0.4, z0, h=0.3, rot_z=1.4)
    at(z0, iso.can_pile, c - 0.6, 0.45, 3, 5)
    at(z0, iso.shards, c + 1.0, 0.4, 5, 0.5, 3)
    for k in range(6):
        iso.cube("hook", (c - 2.0 + k * 0.72, DEPTH - 0.1, z0 + 2.1 + (k % 3) * 0.13),
                 (0.1, 0.05, 0.36), M["metal"] if k % 2 else M["copper"])
    iso.cube("bench", (c, 0.85, z0 + 0.88), (3.0, 0.8, 0.08), M["wood"])
    for k, m in enumerate(("packet_r", "packet_b", "packet_y")):
        iso.cube("part", (c - 0.8 + k * 0.8, 0.85, z0 + 1.0), (0.3, 0.3, 0.18), M[m])


def fill_storage(x0, x1, z0):
    c = (x0 + x1) / 2
    for dx in (-1.9, 0.2, 2.1):
        at(z0, iso.shelf_unit, c + dx, 1.35)
    for i, (dx, rows, sd) in enumerate(((-1.3, 3, 1), (0.4, 3, 4), (1.7, 2, 8))):
        at(z0, iso.can_pile, c + dx, 0.45, rows, sd)
    iso.prop("k:box-large", c - 2.5, 0.55, z0, h=0.72, rot_z=0.15)
    iso.prop("k:barrel", c + 2.6, 0.5, z0, h=0.85)
    iso.prop("k:chest", c + 1.0, 1.25, z0, h=0.5, rot_z=-0.3)
    at(z0, iso.jug, c - 0.6, 0.4, 0.2)


def fill_library(x0, x1, z0):
    c = (x0 + x1) / 2
    rnd = random.Random(31)
    for lv in range(3):                                  # 뒷벽 서가 3단
        iso.cube("bshelf", (c, DEPTH - 0.22, z0 + 0.5 + lv * 0.78), (x1 - x0 - 2.6, 0.36, 0.07), M["wood"])
        for k in range(14):
            h = 0.24 + rnd.random() * 0.14
            iso.cube("book", (c - (x1 - x0 - 3.0) / 2 + k * (x1 - x0 - 3.0) / 13, DEPTH - 0.22,
                              z0 + 0.54 + lv * 0.78 + h / 2), (0.19, 0.3, h),
                     M[("red", "blue", "yellow", "green", "paper", "wood_dk")[k % 6]])
    iso.cube("desk", (c - 0.6, 0.75, z0 + 0.74), (1.8, 0.9, 0.08), M["wood"])
    for sx in (-0.85, 0.85):
        iso.cube("dleg", (c - 0.6 + sx, 0.75, z0 + 0.37), (0.09, 0.85, 0.74), M["wood_dk"])
    iso.cube("openbook", (c - 0.6, 0.75, z0 + 0.81), (0.5, 0.36, 0.05), M["paper"], rot=(0, 0, 0.2))
    at(z0, iso.plant, c + 2.2, 0.5, 0.5)
    for k in range(6):
        iso.cube("stack", (c + 1.5 + (k % 2) * 0.42, 0.5, z0 + 0.05 + k * 0.09),
                 (0.36, 0.28, 0.09), M[("paper", "red", "blue")[k % 3]], rot=(0, 0, k * 0.3))


def fill_bath(x0, x1, z0):
    c = (x0 + x1) / 2
    iso.cube("tub", (c - 0.5, 1.05, z0 + 0.42), (3.4, 1.5, 0.84), M["tile"])
    iso.cube("tubw", (c - 0.5, 1.05, z0 + 0.76), (3.2, 1.34, 0.2), M["pool"])
    rnd = random.Random(12)
    for k in range(6):
        iso.sphere("steam", (c - 0.5 + rnd.uniform(-1.5, 1.5), 1.0 + rnd.uniform(-0.4, 0.4),
                             z0 + 1.05 + rnd.uniform(0, 0.8)), 0.2 + rnd.random() * 0.16,
                   SC.alpha_mat("StSec%d" % k, "#d5dedb", 0.10, 0.9), 10, 6)
    at(z0, iso.laundry, (c - 2.4, 0.35), (c + 2.4, 0.35), 2.5)
    iso.prop("k:bucket", c + 2.2, 0.45, z0, h=0.34, rot_z=0.3)
    at(z0, iso.plant, c - 2.5, 0.5, 0.5)
    for k in range(3):
        iso.cube("towel", (c + 1.3 + k * 0.55, 0.45, z0 + 0.13), (0.45, 0.34, 0.26),
                 M["pillow"] if k % 2 else M["fabric2"], rot=(0, 0, k * 0.3))


def fill_airlock(x0, x1, z0):
    c = (x0 + x1) / 2
    # 오른쪽 벽을 뚫고 나가는 해치 = 두 시점의 전환점 (REF §6)
    iso.cyl("hatch", (x1 - 0.55, 1.0, z0 + 1.15), 0.95, 0.5, M["frame_lt"], rot=(0, math.radians(90), 0), verts=18)
    iso.cyl("hatchin", (x1 - 0.55, 1.0, z0 + 1.15), 0.78, 0.6, M["frame"], rot=(0, math.radians(90), 0), verts=18)
    for k in range(6):
        a = math.radians(60 * k)
        iso.cube("bolt", (x1 - 0.42, 1.0 + 0.82 * math.cos(a), z0 + 1.15 + 0.82 * math.sin(a)),
                 (0.1, 0.13, 0.13), M["frame_lt"])
    for k in range(5):                                    # 잠수복 걸이
        sx = c - 1.9 + k * 0.62
        iso.cube("suit", (sx, DEPTH - 0.32, z0 + 1.25), (0.4, 0.34, 1.4), M["tarp"] if k % 2 else M["fabric2"])
        iso.cyl("helm", (sx, DEPTH - 0.32, z0 + 2.06), 0.2, 0.26, M["frame_lt"], verts=12)
    iso.cube("rack", (c, DEPTH - 0.2, z0 + 2.3), (3.4, 0.1, 0.1), M["frame_lt"])
    iso.prop("k:box-large", c - 2.5, 0.5, z0, h=0.7, rot_z=0.2)
    at(z0, iso.can_pile, c + 0.6, 0.45, 2, 2)
    for k in range(3):                                    # 건져 온 유물
        iso.cube("haul", (c + 1.3 + k * 0.38, 0.45, z0 + 0.15), (0.3, 0.26, 0.3),
                 M[("packet_y", "packet_b", "packet_r")[k]], rot=(0, 0, k * 0.6))


def fill_lounge(x0, x1, z0):
    """돔 안의 전망 라운지 — 각박함 속의 사치."""
    c = (x0 + x1) / 2
    iso.cube("rug", (c, 1.0, z0 + 0.03), (4.4, 1.5, 0.06), M["fabric"])
    for k, dx in enumerate((-1.7, 0.0, 1.7)):
        iso.cube("seat", (c + dx, 1.05, z0 + 0.28), (0.9, 0.85, 0.48), M["fabric2"] if k % 2 else M["fabric"])
        iso.cube("sback", (c + dx, 1.42, z0 + 0.68), (0.9, 0.16, 0.54), M["fabric2"] if k % 2 else M["fabric"])
    iso.cyl("table", (c, 0.55, z0 + 0.44), (0.5), 0.07, M["wood"], verts=16)
    iso.cyl("tleg", (c, 0.55, z0 + 0.21), 0.1, 0.42, M["wood_dk"], verts=10)
    at(z0, iso.plant, c - 3.0, 0.55, 0.72)
    at(z0, iso.plant, c + 3.0, 0.55, 0.62)
    for k in range(6):                                    # 유리를 향한 난간
        iso.cyl("rp", (c - 2.5 + k * 1.0, 0.16, z0 + 0.5), 0.05, 1.0, M["frame_lt"], verts=8)
    iso.cube("rt", (c, 0.16, z0 + 1.0), (5.4, 0.1, 0.1), M["frame_lt"])


# ══════════════════════════════════════════════════════════════
# 유리 척추 · 돔 · 굴착면
# ══════════════════════════════════════════════════════════════
def spine(z_top, z_bot):
    """유일한 수직 채도 축(원리 5). 승강 통로 = 기존 앵커 기둥."""
    iso.cube("spine_back", (0, DEPTH + 0.15, (z_top + z_bot) / 2), (SPINE * 2 - 0.3, 0.2, z_top - z_bot),
             hexm("spine_back_m", "#4a2f13", 0.9, emit="#c06a1e", strength=0.55))
    for sx in (-SPINE, SPINE):
        iso.cube("spine_col", (sx, DEPTH / 2, (z_top + z_bot) / 2), (0.30, DEPTH + 0.5, z_top - z_bot), M["frame"])
        iso.cube("spine_rib", (sx, -0.05, (z_top + z_bot) / 2), (0.13, 0.13, z_top - z_bot), M["frame_lt"])
    n = int((z_top - z_bot) / 0.55)
    for k in range(n):                                     # 사다리
        iso.cube("srung", (0, 0.95, z_bot + 0.3 + k * 0.55), (1.5, 0.1, 0.07), M["frame_lt"])
    for zz in (L[1], L[2], L[3], L[4]):                    # 층참
        iso.cube("landing", (0, DEPTH / 2, zz - 0.18), (SPINE * 2 - 0.3, DEPTH + 0.2, 0.22), M["frame_lt"])
    # 승강 케이지 — 지금 3층에 서 있다
    cz = L[3] + 1.1
    iso.cube("cage", (0, 0.72, cz), (2.2, 0.9, 2.2), SC.alpha_mat("Cage", "#ffb457", 0.20, 0.35))
    for dz in (-1.1, 1.1):
        iso.cube("cagef", (0, 0.72, cz + dz), (2.4, 1.0, 0.14), M["frame_lt"])
    bpy.ops.object.light_add(type='POINT', location=(0, 0.5, cz))
    l = bpy.context.object; l.name = "L_spine"
    l.data.color = iso.hexcol("#FFA33C"); l.data.energy = 300; l.data.shadow_soft_size = 0.5


def glass_dome(rooms_z):
    """꼭대기 유리돔 — 여기서 시작했고, 아래로 자랐다."""
    C, R = DOME_C, DOME_R
    g = SC.alpha_mat("SecGlass", "#3f7f99", 0.085, 0.03)
    seg = 44
    quads = []
    for k in range(seg):
        a0 = 2 * math.pi * k / seg; a1 = 2 * math.pi * (k + 1) / seg
        for ri, ro in ((0.0, R),):
            quads.append([C + Vector((ri * math.cos(a0), DEPTH + 0.1, ri * math.sin(a0))),
                          C + Vector((ro * math.cos(a0), DEPTH + 0.1, ro * math.sin(a0))),
                          C + Vector((ro * math.cos(a1), DEPTH + 0.1, ro * math.sin(a1))),
                          C + Vector((ri * math.cos(a1), DEPTH + 0.1, ri * math.sin(a1)))])
    DOME.mesh_of_quads("dome_backglass", quads, g)
    for k in range(seg):                                   # 앞쪽 유리 껍질(격자)
        a0 = 2 * math.pi * k / seg; a1 = 2 * math.pi * (k + 1) / seg
        p0 = C + Vector((R * math.cos(a0), -0.12, R * math.sin(a0)))
        p1 = C + Vector((R * math.cos(a1), -0.12, R * math.sin(a1)))
        DOME.strut("domerim", p0, p1, 0.16, M["frame_lt"], 6)
    for k in range(4):                                     # 방사 리브 (최소한만)
        a = math.radians(45 + 45 * k)
        DOME.strut("domerib", C + Vector((0.4 * math.cos(a), 0.0, 0.4 * math.sin(a))),
                   C + Vector((R * math.cos(a), 0.0, R * math.sin(a))), 0.055, M["frame"], 5)
    iso.cyl("domecap", (0, DEPTH / 2, C.z + R + 0.35), 0.9, 0.7, M["frame_lt"], verts=14)
    iso.sphere("beacon", (0, DEPTH / 2, C.z + R + 0.9), 0.20,
               hexm("beacon_m", "#FFE0B0", 0.3, emit="#FF9E3A", strength=13), 10, 6)
    bpy.ops.object.light_add(type='POINT', location=(0, 0.2, C.z + R + 0.9))
    l = bpy.context.object; l.name = "L_beacon2"
    l.data.color = iso.hexcol("#FF9E3A"); l.data.energy = 160


def dig_face(x0, x1, z0):
    """아래로 자란다 — 굴착 중인 다음 칸(빈 방이 아니라 공사장)."""
    fr = M["frame"]
    iso.cube("dig_b", ((x0 + x1) / 2, DEPTH / 2, z0 - HULL / 2), (x1 - x0 + HULL * 2, DEPTH + 0.4, HULL), fr)
    for sx in (x0 - HULL / 2, x1 + HULL / 2):
        iso.cube("dig_s", (sx, DEPTH / 2, z0 + RH / 2), (HULL, DEPTH + 0.4, RH), fr)
    DOME.mesh_of_quads("dig_back", [[Vector((x0 + 0.4, DEPTH, z0)), Vector((x1 - 0.4, DEPTH, z0)),
                                     Vector((x1 - 0.4, DEPTH, z0 + RH)), Vector((x0 + 0.4, DEPTH, z0 + RH))]],
                       hexm("dig_back_m", "#241a12", 1.0))
    rnd = random.Random(9)
    for k in range(9):                                     # 비계
        iso.cube("scaf", (x0 + 0.7 + k * 0.62, 0.9, z0 + 1.4), (0.1, 0.1, 2.8), M["wood_dk"])
    for zz in (z0 + 0.9, z0 + 2.1):
        iso.cube("scafh", ((x0 + x1) / 2, 0.9, zz), (x1 - x0 - 1.0, 0.12, 0.12), M["wood_dk"])
    for k in range(7):
        iso.prop("k:" + ("rock-a", "rock-b", "rock-c")[k % 3], x0 + 1.0 + rnd.random() * (x1 - x0 - 2),
                 0.4 + rnd.random() * 0.8, z0, h=0.3 + rnd.random() * 0.5, rot_z=rnd.uniform(0, 6.2),
                 recolor=hexm("digrock%d" % k, "#2a2119", 1.0))
    iso.prop("k:tool-pickaxe", x1 - 1.2, 0.5, z0, h=1.1, rot_z=0.4)
    bpy.ops.object.light_add(type='SPOT', location=((x0 + x1) / 2, -0.6, z0 + 2.6))
    l = bpy.context.object; l.name = "L_dig"
    l.data.color = iso.hexcol("#FFD27A"); l.data.energy = 900; l.data.spot_size = math.radians(90)
    l.data.spot_blend = 0.5
    SC.aim(l, ((x0 + x1) / 2, 1.2, z0))


# ══════════════════════════════════════════════════════════════
# 거점 조립
# ══════════════════════════════════════════════════════════════
def materials():
    global M
    M = DOME.deep_materials()
    M["zones"] = zone_gradient()
    M["frame"] = hexm("Frame", "#14191c", 0.85, )
    M["frame_lt"] = hexm("FrameLt", "#5d6a70", 0.45)
    DOME.M = M
    return M


# (id, 이름, 층, x0, x1, 고유색, 채움)
def layout():
    return [
        ("lounge", 1, -5.0, 5.0, "#D8AE6C", fill_lounge, 0),          # 돔 안
        ("quarters", 1, -13.9, -(SPINE + GAP), "#CC8A46", fill_quarters, 4),
        ("greenhouse", 1, SPINE + GAP, 8.5, "#9CA249", fill_greenhouse, 3),
        ("workshop", 2, -8.5, -(SPINE + GAP), "#B25A30", fill_workshop, 3),
        ("storage", 2, SPINE + GAP, 8.5, "#AD8B4E", fill_storage, 2),
        ("library", 2, 9.05, 15.05, "#8C6A46", fill_library, 2),
        ("bath", 3, -8.5, -(SPINE + GAP), "#6E9E92", fill_bath, 3),
        ("airlock", 3, SPINE + GAP, 8.5, "#C97A2A", fill_airlock, 3),
    ]


CREW = ["cook", "farmer", "engineer", "medic", "scholar", "scout", "trader", "kid"]


def build_base():
    materials()
    z_lounge = DOME_C.z - 2.6
    for rid, lv, x0, x1, hue, fill, npc in layout():
        z0 = z_lounge if rid == "lounge" else L[lv]
        if rid != "lounge":
            room_shell(x0, x1, z0, hue, rid)
        else:
            room_shell(x0, x1, z0, hue, rid)
        room_lamp((x0 + x1) / 2, z0, hue, rid, 300 if (x1 - x0) < 9 else 520)
        if (x1 - x0) > 9:
            room_lamp((x0 + x1) / 2 - 3.6, z0, hue, rid + "b", 300)
            room_lamp((x0 + x1) / 2 + 3.6, z0, hue, rid + "c", 300)
        fill(x0, x1, z0)
        rnd = random.Random(hash(rid) % 9999)
        xs = [x0 + (x1 - x0) * (i + 0.5) / max(npc, 1) + rnd.uniform(-0.5, 0.5) for i in range(npc)]
        people(xs, z0, [CREW[(hash(rid) + i) % 8] for i in range(npc)])
    dig_face(-8.5, -(SPINE + GAP), L[4])
    spine(DOME_C.z - 1.0, L[4] - 1.6)
    glass_dome(z_lounge)
    # 척추 안에도 사람 하나 (승강 케이지)
    DOME.resident("trader", 0.0, 0.7, L[3] + 0.05, rot_z=math.radians(180), h=1.68)


# ══════════════════════════════════════════════════════════════
# 세계 · 렌더
# ══════════════════════════════════════════════════════════════
def section_world(fog=0.013):
    DOME.V, DOME.RIGHT, DOME.UP = V_FRONT, RIGHT_FRONT, UP_FRONT
    DOME.deep_world(fog=fog)
    absorb_fog(fog)
    for o in bpy.data.objects:                       # 빛은 위에서만 온다 (광층)
        if o.name == "PRV_L_down":
            o.data.energy = 0.07
            o.rotation_euler = (math.radians(6), 0, 0)
        if o.name == "PRV_L_rim":
            o.location = (0, -26, 40); o.data.energy = 220; o.data.size = 26
            SC.aim(o, (0, 2, 12))


def shot(path, ortho, target, res=(1600, 900), exposure=-0.10, fog=0.013, extras=True):
    section_world(fog)
    build_base()
    water_plane()
    deep_structures()
    soft_shafts()
    if extras:
        marine_snow()
        soft_jellies()
        DOME.leviathan(sr=-12.0, su=27.0, depth=-13.0, length=26.0, seed=5)
        DOME.leviathan(sr=20.0, su=12.5, depth=-9.0, length=13.0, seed=8)
    DOME.NOLINE = tuple(set(DOME.NOLINE) | {"PRV_shaft", "PRV_backdrop", "dome_backglass",
                                            "PRV_jhalo", "PRV_jtent", "far_"})
    DOME.noline_setup()
    SC.preview(path, ortho=ortho, target=target, res=res, az=0, el=0,
               freestyle=True, exposure=exposure)


def shot_hero():
    shot(os.path.join(OUT_RAW, "section_hero.png"), ortho=56.0, target=(0.6, 0, 6.4), exposure=-0.10)


def shot_zoom():
    shot(os.path.join(OUT_RAW, "section_zoom.png"), ortho=23.0, target=(0.0, 0, 3.4),
         exposure=-0.05, fog=0.016)


if __name__ == "__main__":
    jobs = {"hero": shot_hero, "zoom": shot_zoom}
    for k in (["hero", "zoom"] if MODE == "all" else [MODE]):
        jobs[k]()
    print("ALL DONE", flush=True)
