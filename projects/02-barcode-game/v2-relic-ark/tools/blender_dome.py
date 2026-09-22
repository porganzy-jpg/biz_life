# -*- coding: utf-8 -*-
"""
잔해 방주 — 1막 거점 「심해 유리돔 단면」 씬 생성기 (S3-B)
blender -b --python tools/blender_dome.py -- hero
blender -b --python tools/blender_dome.py -- airlock
blender -b --python tools/blender_dome.py -- depth
blender -b --python tools/blender_dome.py -- glb
blender -b --python tools/blender_dome.py -- all

산출물
  art_raw/deep/dome_hero.png      첫 화면 후보 (1600×900). 검은 물 + 방마다 다른 등불색
  art_raw/deep/dome_airlock.png   에어락에서 주민이 나가는 순간 (1600×900)
  art_raw/deep/dome_depth.png     부유물 + 대형 생물 실루엣으로 깊이감 (1600×900)
  static/models/scenes/dome_core.glb  돔 본체(기둥+8방+유리껍질). 해저·부유물·생물 제외

구조 (CONCEPT_DEEP_SEA §3)
  원점 (0,0,0) = 해저 바닥의 앵커 기둥 발 중심. +Z 위.
  중앙 앵커 기둥이 해저에 박히고, 그 위로 구형 유리돔(중심 z=15, 반지름 13)이 자란다.
  방은 기존 6m 격자를 육각으로 읽은 것: 기둥 셀을 중심으로 이웃 6칸이 거리 6.0m, 60° 간격.
  방 셀 = 정육각 프리즘(맞변 6.0m = 격자 한 칸), 벽 높이 2.6m(기존 규약).
  층 3개: L0 z=7.0 / L1 z=11.4 / L2 z=15.8.

원칙
  D1 난색 안 / 한색 밖, 세 번째 주색 없음 — 방 등불은 전부 호박~주황 대역 안의 색온도 차이로만 구분
  D2 검정을 아낀다 — 화면의 절반 가까이가 빈 물
  D3 빛은 전부 근거가 있다 — 방 등불 / 에어락 등 / 발광 생물 / 위에서 내려오는 잔광(박광층)
  D4 유리는 두 번 보인다 — 사선 절단면 아래쪽 유리는 남겨 방을 '투과'로 보이게, 위 실루엣에 한색 반사 띠
  D5 부유물 3겹, D6 대형 생물은 그림자로 먼저
  B4 소품 밀도 / B6 45°/45° 직교 / B8 GLB ≤1.5MB / B9 자연은 흩어서
"""
import bpy, sys, os, math, importlib.util, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT_RAW = os.path.join(ROOT, "art_raw", "deep")
OUT_SCENES = os.path.join(ROOT, "static", "models", "scenes")
CHARS = os.path.join(ROOT, "static", "models", "chars")
for d in (OUT_RAW, OUT_SCENES):
    os.makedirs(d, exist_ok=True)


def load_scenes():
    """blender_scenes.py(→blender_iso.py)의 재질·원시도형·CC0 소품·내보내기·프리뷰 헬퍼를 그대로 재사용."""
    spec = importlib.util.spec_from_file_location("blender_scenes", os.path.join(HERE, "blender_scenes.py"))
    m = importlib.util.module_from_spec(spec)
    saved = list(sys.argv)
    sys.argv = [saved[0], "--", "__none__"]
    spec.loader.exec_module(m)
    sys.argv = saved
    return m


SC = load_scenes()
iso = SC.iso

# ── 규격 ────────────────────────────────────────────────────
R = 13.0                 # 유리 껍질 반지름
CZ = 15.0                # 껍질 중심 높이 (바닥 z=2, 꼭대기 z=28)
GRID = 6.0               # 기존 6m 격자 = 육각 셀 맞변
HEXR = GRID / math.sqrt(3.0)     # 육각 외접반지름 3.464
RH = 2.6                 # 벽 높이 (기존 규약)
SLAB = 0.3               # 바닥 슬래브
COL_R = 1.5              # 앵커 기둥 반지름
LEVELS = {0: 7.0, 1: 11.4, 2: 15.8}
SEA_R = 17.0             # 해저 대지 반지름 (그 밖은 어둠 속으로 떨어진다)

AZ, EL = 45.0, 45.0
_a, _e = math.radians(AZ), math.radians(EL)
V = Vector((-math.cos(_e) * math.sin(_a), -math.cos(_e) * math.cos(_a), math.sin(_e)))   # 씬→카메라 단위벡터
RIGHT = Vector((math.cos(_a), -math.sin(_a), 0)).normalized()     # 화면 오른쪽
UP = V.cross(RIGHT).normalized()                                  # 화면 위
VXY = Vector((V.x, V.y, 0)).normalized()
DEEP_MIN = -22.0        # 시선 방향 최대 후퇴 (직교 카메라 clip_end=100 안에 들어오게)

# 사선 절단면: 수평 시선 방향 VXY 기준으로 앞면에 창을 뚫되, 꼭대기 유리는 남긴다.
#   남긴다 ⇔ dot(u, VXY) < CUT_OFF - CUT_TILT * u.z     (법선 VXY+CUT_TILT*Z → 수평에서 24° 기운 평면)
#   위쪽 유리를 남겨야 "위에서 유리 너머로 방을 내려다보는" 투과가 생기고(D4),
#   아래앞쪽 유리도 남아 가장 낮은 방이 유리 뒤로 보인다.
CUT_OFF, CUT_TILT = 0.62, 0.45


def screen_at(sr, su, depth=0.0):
    """화면 좌표(오른쪽 sr, 위 su)와 시선 깊이 depth 로 월드 좌표를 만든다(직교 카메라)."""
    return Vector(RIGHT) * sr + Vector(UP) * su + Vector(V) * depth


# ══════════════════════════════════════════════════════════════
# 재질 — iso.mat / SC.alpha_mat 재사용
# ══════════════════════════════════════════════════════════════
def deep_materials():
    M = SC.fresh()
    M["_dark"] = iso.mat("InteriorDark", "#0c0f10", 1.0)
    M["hull"] = iso.mat("Hull", "#3a4247", 0.55, metallic=0.55)
    M["hull_dk"] = iso.mat("HullDark", "#22282c", 0.7, metallic=0.4)
    M["hull_lt"] = iso.mat("HullLight", "#6c7a80", 0.4, metallic=0.7)
    M["rust"] = iso.mat("Rust", "#7a4a2e", 0.9)
    M["deck"] = iso.mat("Deck", "#57452f", 0.85)
    M["deck2"] = iso.mat("Deck2", "#3d362e", 0.9)
    M["silt"] = iso.mat("Silt", "#05090c", 1.0)
    M["silt2"] = iso.mat("Silt2", "#02050700"[:7], 1.0)
    M["glass"] = SC.alpha_mat("DomeGlass", "#5b9ec4", 0.075, 0.03)
    M["glass_warm"] = SC.alpha_mat("DomeGlassWarm", "#a7743c", 0.085, 0.04)
    M["glass_rim"] = SC.alpha_mat("DomeGlassRim", "#8ad3f0", 0.17, 0.02)
    M["murk"] = iso.mat("Murk", "#000000", 1.0, emit="#0b1a24", strength=0.72)
    M["murk_lt"] = iso.mat("MurkRim", "#000000", 1.0, emit="#16303c", strength=0.7)
    M["bio"] = iso.mat("Bio", "#0a1418", 0.3, emit="#38a4b4", strength=1.5)
    M["bio_dim"] = iso.mat("BioDim", "#0a1418", 0.3, emit="#2b7b88", strength=0.9)
    M["snow"] = iso.mat("Snow", "#0a0e10", 0.9, emit="#7f9ea8", strength=0.55)
    M["snow_far"] = iso.mat("SnowFar", "#0a0e10", 0.9, emit="#2a3c44", strength=0.20)
    M["pool"] = SC.alpha_mat("PoolWater", "#2d6b78", 0.55, 0.05)
    M["kelp"] = iso.mat("Kelp", "#16302c", 0.95)
    M["backdrop"] = gradient_mat("WaterColumn", "#04161f", "#000101", -20.0, 70.0)
    return M


M = {}
LOW = False      # GLB 내보내기용 저폴리 모드(렌더는 항상 풀 디테일)


# ══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ══════════════════════════════════════════════════════════════
def at(z, fn, *a, **k):
    """z=0 을 가정하는 blender_iso 의 생활 소품 헬퍼를 층 높이 z 로 올려서 재사용한다."""
    before = set(bpy.data.objects)
    fn(*a, **k)
    for o in bpy.data.objects:
        if o not in before and o.parent is None:
            o.location.z += z


def gradient_mat(name, top_hex, bot_hex, z0, z1):
    """수직 그라디언트 발광 재질 — 물기둥(위는 잔광, 아래는 칠흑)."""
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
    mr.inputs["From Min"].default_value = z0; mr.inputs["From Max"].default_value = z1
    nt.links.new(mr.outputs[0], ramp.inputs["Fac"])
    ramp.color_ramp.elements[0].color = (*iso.hexcol(bot_hex), 1)
    ramp.color_ramp.elements[1].color = (*iso.hexcol(top_hex), 1)
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def water_backdrop(depth=-21.0, w=170.0, h=130.0):
    """물기둥 배경판 — 시선에 수직. 검정 대신 '검은 물'로 읽히게 한다(D2는 비움이지 무채가 아니다)."""
    c = Vector(V) * depth
    q = [c - RIGHT * (w / 2) - UP * (h / 2), c + RIGHT * (w / 2) - UP * (h / 2),
         c + RIGHT * (w / 2) + UP * (h / 2), c - RIGHT * (w / 2) + UP * (h / 2)]
    o = mesh_of_quads("PRV_backdrop", [q], M["backdrop"])
    o.name = "PRV_backdrop"
    return o


NOLINE = ("PRV_backdrop", "PRV_snow", "PRV_lev", "PRV_seafloor", "PRV_mound", "PRV_plank",
          "PRV_jelly", "PRV_tent", "PRV_rock", "PRV_worm", "keep_shell_glass")


def noline_setup():
    """손그림 선(B7)은 방·소품에만. 유리·부유물·물기둥·실루엣에는 윤곽선을 그리지 않는다."""
    sc = bpy.context.scene
    sc.render.use_freestyle = True
    vl = sc.view_layers[0]; vl.use_freestyle = True
    coll = bpy.data.collections.new("NOLINE")
    sc.collection.children.link(coll)
    def tagged(o):
        n = o
        while n is not None:
            if n.name.startswith(NOLINE):
                return True
            n = n.parent
        return False
    for o in list(bpy.data.objects):
        if tagged(o):
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
    fs = vl.freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("relic")
    ls.select_by_collection = True
    ls.collection = coll
    ls.collection_negation = 'EXCLUSIVE'


def mesh_of_quads(name, quads, material):
    verts, faces = [], []
    for q in quads:
        i = len(verts)
        verts.extend([tuple(p) for p in q]); faces.append([i, i + 1, i + 2, i + 3])
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def pod_lamp(x, y, z, color, energy=1500, hang=0.75, name="lamp"):
    """방 등불 하나(D3: 근거 있는 빛). iso.lantern 은 고정 높이·전역 필라이트를 붙이므로 여기선 위치형으로."""
    top = z + RH
    iso.cyl("lampwire", (x, y, top - hang / 2), 0.012, hang, M["beam"])
    iso.cyl("lampcap", (x, y, top - hang), 0.17, 0.14, M["lamp_m"])
    iso.sphere("bulb", (x, y, top - hang - 0.16), 0.14,
               iso.mat("bulb_" + name, "#FFE9C4", 0.3, emit=color, strength=16), 12, 7)
    bpy.ops.object.light_add(type='POINT', location=(x, y, top - hang - 0.16))
    l = bpy.context.object; l.name = "L_" + name
    l.data.color = iso.hexcol(color); l.data.energy = energy; l.data.shadow_soft_size = 0.6
    return Vector((x, y, top - hang - 0.16))


def slot_xy(deg):
    a = math.radians(deg)
    return GRID * math.cos(a), GRID * math.sin(a)


def strut(name, p0, p1, r, m, verts=8):
    """두 점을 잇는 원통(케이블·버팀대)."""
    p0, p1 = Vector(p0), Vector(p1)
    seg = p1 - p0
    o = iso.cyl(name, (p0 + p1) / 2, r, seg.length, m, verts=verts)
    o.rotation_euler = seg.to_track_quat('Z', 'Y').to_euler()
    return o


def wall_pt(cx, cy, deg, t, out=0.0):
    """육각 셀에서 deg 방향 벽면 위의 점. t = 벽을 따라간 거리, out = 벽에서 안쪽(-)/바깥(+)."""
    a = math.radians(deg)
    nx, ny = math.cos(a), math.sin(a)
    return (cx + nx * (3.0 + out) - ny * t, cy + ny * (3.0 + out) + nx * t)


# ══════════════════════════════════════════════════════════════
# 육각 셀 (방) — 기존 6m 격자를 육각으로 읽는다
# ══════════════════════════════════════════════════════════════
WALL_DIRS = [0, 60, 120, 180, 240, 300]
CAM_DEG = math.degrees(math.atan2(VXY.y, VXY.x)) % 360      # 225°


def _faces_camera(deg, thresh=0.10):
    return math.cos(math.radians(deg - CAM_DEG)) > thresh


def hex_cell(cx, cy, z, slot_deg, floor_mat=None, inner_door=True):
    """육각 프리즘 셸: 바닥 슬래브 + 카메라 반대쪽 벽 3장 + 모서리 기둥 6 + 상단 림보 6.
    카메라 쪽 벽은 제거(B6). 기둥을 향한 안쪽 벽에는 문을 뚫는다."""
    iso.cyl("cellfloor", (cx, cy, z - SLAB / 2), HEXR, SLAB, floor_mat or M["deck"],
            rot=(0, 0, math.radians(30)), verts=6)
    iso.cyl("cellrim", (cx, cy, z - SLAB - 0.06), HEXR + 0.10, 0.12, M["hull_dk"],
            rot=(0, 0, math.radians(30)), verts=6)
    inner = (slot_deg + 180) % 360
    for w in WALL_DIRS:
        if _faces_camera(w):
            continue
        a = math.radians(w)
        px, py = cx + 3.0 * math.cos(a), cy + 3.0 * math.sin(a)
        if inner_door and w == inner:
            for s in (-1, 1):                     # 문설주 둘 + 상인방
                ox, oy = -math.sin(a), math.cos(a)
                iso.cube("jamb", (px + ox * s * 1.27, py + oy * s * 1.27, z + RH / 2),
                         (0.22, 0.92, RH), M["hull"], rot=(0, 0, a))
            iso.cube("lintel", (px, py, z + RH - 0.28), (0.22, 1.7, 0.56), M["hull"], rot=(0, 0, a))
        else:
            iso.cube("cellwall", (px, py, z + RH / 2), (0.20, HEXR, RH), M["hull"], rot=(0, 0, a))
            if not LOW:
                iso.cube("cellwainscot", (px, py, z + 0.34), (0.24, HEXR, 0.68), M["hull_dk"], rot=(0, 0, a))
    for k in range(6):                            # 모서리 기둥 + 상단 림보 (벽이 없어도 육각이 읽히게)
        a0 = math.radians(30 + 60 * k); a1 = math.radians(30 + 60 * (k + 1))
        vx, vy = cx + HEXR * math.cos(a0), cy + HEXR * math.sin(a0)
        iso.cube("cellpost", (vx, vy, z + RH / 2), (0.24, 0.24, RH + 0.1), M["hull_lt"], rot=(0, 0, a0))
        mx = (HEXR * math.cos(a0) + HEXR * math.cos(a1)) / 2
        my = (HEXR * math.sin(a0) + HEXR * math.sin(a1)) / 2
        iso.cube("cellbeam", (cx + mx, cy + my, z + RH + 0.09), (0.18, HEXR, 0.18), M["hull_lt"],
                 rot=(0, 0, math.atan2(my, mx)))


def corridor(slot_deg, z):
    """기둥에서 셀로 뻗는 짧은 연결관 (r=1.5 → 3.0)."""
    a = math.radians(slot_deg)
    mid = (COL_R + 3.0) / 2
    iso.cyl("corr", (mid * math.cos(a), mid * math.sin(a), z + 1.15), 0.95, 3.0 - COL_R,
            M["hull_dk"], rot=(0, math.radians(90), a), verts=12)
    iso.cyl("corrrib", (3.0 * math.cos(a), 3.0 * math.sin(a), z + 1.15), 1.05, 0.16,
            M["hull_lt"], rot=(0, math.radians(90), a), verts=12)


# ══════════════════════════════════════════════════════════════
# 방 8칸 — 소품은 blender_iso 헬퍼 재사용 (B4 밀도)
# ══════════════════════════════════════════════════════════════
def r_quarters(cx, cy, z):
    """거주 — 오늘 밤 세 사람이 여기서 잔다."""
    at(z, iso.bedroll, cx - 1.5, cy + 0.9, math.radians(20))
    at(z, iso.bedroll, cx + 0.2, cy + 1.6, math.radians(-15))
    at(z, iso.bedroll, cx + 1.7, cy + 0.4, math.radians(55))
    at(z, iso.laundry, (cx - 2.3, cy - 0.6), (cx + 2.2, cy + 1.2), 2.05)
    at(z, iso.plant, cx + 2.2, cy - 1.5, 0.55, True, LOW)
    at(z, iso.plant, cx - 2.4, cy + 1.6, 0.42, True, LOW)
    at(z, iso.jug, cx - 0.9, cy - 1.5, 0.3)
    at(z, iso.shelf_unit, cx + 1.9, cy + 1.9, math.radians(-30))
    iso.prop("k:chest", cx - 2.1, cy - 1.4, z, h=0.55, rot_z=0.4)
    iso.prop("k:box", cx + 1.1, cy - 1.9, z, h=0.4, rot_z=-0.5)
    iso.prop("k:box-open", cx + 1.75, cy - 1.35, z, h=0.42, rot_z=0.9)
    for k, t in enumerate((-0.9, -0.2, 0.6)):    # 60° 벽면에 붙인 쪽지
        nx, ny = wall_pt(cx, cy, 60, t, -0.13)
        iso.cube("note", (nx, ny, z + 1.55 + (k % 2) * 0.3), (0.02, 0.22, 0.28),
                 M["paper"], rot=(0, 0, math.radians(60)))
    iso.cube("lowtable", (cx - 0.2, cy - 0.5, z + 0.22), (1.1, 0.7, 0.06), M["wood"])
    for dx, dy in ((-0.4, -0.2), (0.3, 0.25)):
        iso.cyl("mug", (cx - 0.2 + dx, cy - 0.5 + dy, z + 0.3), 0.05, 0.1, M["white"], verts=8)
    return pod_lamp(cx - 0.2, cy + 0.2, z, "#FF9236", 4600, name="quarters")


def r_greenhouse(cx, cy, z):
    """온실 — 산소. 화분이 벽을 타고 올라간다."""
    for k in range(3):                            # 재배 단
        iso.cube("bed", (cx - 1.7 + k * 1.7, cy + 0.6, z + 0.30), (1.3, 3.0, 0.60), M["wood_dk"])
        iso.cube("soil", (cx - 1.7 + k * 1.7, cy + 0.6, z + 0.62), (1.18, 2.86, 0.06), M["earth2"])
    rnd = random.Random(4411)
    for k in range(7 if LOW else 16):             # B9: 격자로 놓지 않는다
        gx = cx - 1.7 + (k % 3) * 1.7 + rnd.uniform(-0.35, 0.35)
        gy = cy + 0.6 + rnd.uniform(-1.3, 1.3)
        at(z + 0.65, iso.plant, gx, gy, rnd.uniform(0.34, 0.62), False, LOW)
    at(z, iso.plant, cx + 2.3, cy - 1.7, 0.7, True, LOW)
    at(z, iso.plant, cx - 2.4, cy - 1.5, 0.55, True, LOW)
    for k, (vx, vy) in enumerate(((cx + 2.75, cy + 1.2), (cx + 1.9, cy + 2.5), (cx - 2.6, cy + 1.0))):
        at(z, iso.vine, vx, vy, RH - 0.2, 1.5 + (k % 2) * 0.5, 'x', 7 + k, LOW)
    at(z, iso.jug, cx + 0.9, cy - 1.9, 0.9)
    at(z, iso.jug, cx + 1.45, cy - 1.75, -0.4)
    iso.prop("k:bucket", cx - 0.6, cy - 1.9, z, h=0.32, rot_z=0.3)
    iso.prop("k:tool-hoe", cx - 2.5, cy + 2.1, z, h=1.0, rot_z=0.2)
    return pod_lamp(cx, cy + 0.6, z, "#FFB63F", 4300, name="greenhouse")


def r_workshop(cx, cy, z):
    """작업장 — 건져 온 쓰레기를 뜯어 고치는 자리."""
    iso.prop("k:workbench", cx - 1.2, cy + 1.8, z, h=1.0, rot_z=math.radians(180))
    iso.prop("k:workbench-anvil", cx + 1.3, cy + 1.9, z, h=1.0, rot_z=math.radians(180))
    iso.prop("k:barrel", cx + 2.3, cy - 0.4, z, h=0.85, rot_z=0.2)
    iso.prop("k:barrel-open", cx + 2.4, cy + 0.9, z, h=0.85, rot_z=-0.4)
    iso.prop("k:box-large", cx - 2.3, cy - 0.7, z, h=0.75, rot_z=0.1)
    iso.prop("k:box", cx - 2.2, cy + 0.6, z, h=0.45, rot_z=0.7)
    iso.prop("k:resource-planks", cx - 0.2, cy - 2.0, z, h=0.3, rot_z=1.2)
    iso.prop("k:tool-hammer", cx - 1.4, cy + 1.2, z + 0.02, h=0.42, rot_z=0.9)
    iso.prop("k:tool-pickaxe", cx + 2.6, cy + 2.0, z, h=1.2, rot_z=-0.3)
    at(z, iso.can_pile, cx + 0.6, cy - 1.4, 3, 5)
    at(z, iso.can_pile, cx - 0.9, cy - 1.1, 2, 9)
    at(z, iso.shards, cx + 1.4, cy - 1.9, 6, 0.6, 3)
    for k in range(6):                            # 60° 벽면에 건 공구·부품
        hx, hy = wall_pt(cx, cy, 60, -1.3 + k * 0.5, -0.16)
        iso.cube("hook", (hx, hy, z + 1.85 + (k % 3) * 0.12), (0.07, 0.13, 0.36),
                 M["metal"] if k % 2 else M["copper"], rot=(0, 0, math.radians(60)))
    iso.cube("bench_top", (cx, cy - 0.3, z + 0.86), (2.6, 0.8, 0.08), M["wood"])
    for sx in (-1.15, 1.15):
        iso.cube("bench_leg", (cx + sx, cy - 0.3, z + 0.42), (0.1, 0.7, 0.84), M["wood_dk"])
    for k, m in enumerate(("packet_r", "packet_b", "packet_y", "metal")):
        iso.cube("part", (cx - 0.9 + k * 0.6, cy - 0.3, z + 0.98), (0.26, 0.3, 0.16), M[m])
    return pod_lamp(cx, cy + 0.9, z, "#FF6E1E", 5400, name="workshop")


def r_airlock(cx, cy, z):
    """에어락 — 나가는 것 자체가 사건. 바닥의 문풀과 아래로 이어지는 관."""
    iso.cyl("poolrim", (cx, cy - 0.6, z - 0.04), 1.30, 0.30, M["hull_lt"], verts=20)
    iso.cyl("pool", (cx, cy - 0.6, z - 0.12), 1.12, 0.14, M["pool"], verts=20)
    for k in range(5):                            # 잠수복 걸이 (0° 벽면)
        sx, sy = wall_pt(cx, cy, 0, -1.24 + k * 0.62, -0.42)
        iso.cube("suit", (sx, sy, z + 1.25), (0.34, 0.42, 1.4), M["tarp"] if k % 2 else M["fabric2"])
        iso.cyl("helm", (sx, sy, z + 2.06), 0.2, 0.26, M["hull_lt"], verts=12)
    rx, ry = wall_pt(cx, cy, 0, 0.0, -0.30)
    iso.cube("rack", (rx, ry, z + 2.3), (0.12, 3.2, 0.12), M["hull_lt"])
    iso.prop("k:box-large", cx + 2.2, cy + 1.2, z, h=0.7, rot_z=0.2)
    iso.prop("k:barrel", cx - 2.4, cy + 0.2, z, h=0.8, rot_z=-0.3)
    iso.prop("k:bucket", cx + 1.9, cy - 1.5, z, h=0.34, rot_z=0.5)
    at(z, iso.jug, cx - 1.9, cy - 1.3, 0.4)
    at(z, iso.jug, cx - 1.45, cy - 1.7, -0.6)
    at(z, iso.can_pile, cx + 1.1, cy + 0.4, 2, 2)
    for k in range(3):                            # 채집망에 걸린 유물(인간이 만든 쓰레기)
        iso.cube("haul", (cx + 1.5 + (k % 2) * 0.3, cy - 0.9 + k * 0.32, z + 0.14),
                 (0.3, 0.24, 0.28), M[("packet_y", "packet_b", "packet_r")[k]], rot=(0, 0, k * 0.7))
    return pod_lamp(cx, cy + 1.1, z, "#FFA82A", 6000, name="airlock")


def r_storage(cx, cy, z):
    """저장고 — 비축이 곧 안심."""
    at(z, iso.shelf_unit, cx - 1.9, cy + 1.9, math.radians(0))
    at(z, iso.shelf_unit, cx + 0.2, cy + 2.1, math.radians(0))
    at(z, iso.shelf_unit, cx + 2.2, cy + 0.9, math.radians(-60))
    piles = ((-1.2, -0.4, 3, 1), (0.3, -1.1, 3, 4), (1.4, -0.2, 2, 8), (-0.3, 0.3, 2, 11))
    for i, (px, py, rows, sd) in enumerate(piles[:2] if LOW else piles):
        at(z, iso.can_pile, cx + px, cy + py, rows, sd)
    iso.prop("k:box-large", cx - 2.3, cy - 1.2, z, h=0.75, rot_z=0.15)
    iso.prop("k:box", cx - 2.2, cy - 1.3, z + 0.75, h=0.42, rot_z=-0.6)
    iso.prop("k:box-open", cx + 1.9, cy - 1.7, z, h=0.45, rot_z=0.8)
    iso.prop("k:barrel", cx + 2.5, cy - 0.6, z, h=0.85, rot_z=0.0)
    iso.prop("k:chest", cx + 0.9, cy + 0.9, z, h=0.5, rot_z=-0.4)
    at(z, iso.jug, cx - 1.0, cy - 1.9, 0.2)
    at(z, iso.jug, cx - 0.5, cy - 2.1, 0.9)
    return pod_lamp(cx, cy + 0.4, z, "#E88A38", 3600, name="storage")


def r_lounge(cx, cy, z):
    """전망 라운지 — 각박함 속의 사치(§3 고급 방). 유리를 향해 앉는다."""
    iso.cyl("rug", (cx - 0.2, cy - 0.4, z + 0.02), 1.7, 0.04, M["fabric"], verts=20)
    for k, (sx, sy, rot) in enumerate(((-1.5, -1.3, 0.5), (0.6, -1.8, -0.3), (1.7, -0.4, -1.1))):
        iso.cube("seat", (cx + sx, cy + sy, z + 0.26), (0.9, 0.85, 0.44),
                 M["fabric2"] if k % 2 else M["fabric"], rot=(0, 0, rot))
        iso.cube("seatback", (cx + sx + 0.3 * math.sin(rot), cy + sy + 0.42, z + 0.64),
                 (0.9, 0.16, 0.5), M["fabric2"] if k % 2 else M["fabric"], rot=(0, 0, rot))
    iso.cyl("table", (cx - 0.2, cy - 0.4, z + 0.42), 0.52, 0.06, M["wood"], verts=16)
    iso.cyl("tableleg", (cx - 0.2, cy - 0.4, z + 0.2), 0.1, 0.4, M["wood_dk"], verts=10)
    for dx, dy, m in ((-0.2, 0.1, "white"), (0.2, -0.15, "packet_y"), (0.0, 0.25, "copper")):
        iso.cyl("cup", (cx - 0.2 + dx, cy - 0.4 + dy, z + 0.51), 0.06, 0.12, M[m], verts=8)
    at(z, iso.plant, cx + 2.1, cy + 1.3, 0.75, True, LOW)
    at(z, iso.plant, cx - 2.3, cy + 0.7, 0.6, True, LOW)
    at(z, iso.vine, cx + 2.4, cy + 2.1, RH - 0.3, 1.4, 'x', 31, LOW)
    iso.prop("k:chest", cx - 2.2, cy + 1.9, z, h=0.5, rot_z=0.3)
    iso.cube("books", (cx - 2.2, cy + 1.9, z + 0.56), (0.5, 0.36, 0.1), M["red"])
    # 창가 난간 — 카메라 쪽(열린 면)에 사람이 서는 자리
    for k in range(5):
        iso.cyl("railpost", (cx - 2.0 + k * 1.0, cy - 2.75, z + 0.5), 0.05, 1.0, M["hull_lt"], verts=8)
    iso.cube("railtop", (cx, cy - 2.75, z + 1.0), (4.4, 0.1, 0.1), M["hull_lt"])
    return pod_lamp(cx - 0.2, cy + 0.3, z, "#FFB468", 4200, name="lounge")


def r_bath(cx, cy, z):
    """목욕탕 — 민물. 고급 방은 자원이 아니라 사기를 만든다."""
    iso.cyl("tubwall", (cx - 0.3, cy + 0.6, z + 0.36), 1.65, 0.72, M["tile"], verts=24)
    iso.cyl("tubwater", (cx - 0.3, cy + 0.6, z + 0.62), 1.48, 0.22, M["pool"], verts=24)
    iso.cyl("tublip", (cx - 0.3, cy + 0.6, z + 0.74), 1.70, 0.08, M["tile2"], verts=24)
    rnd = random.Random(9090)
    for k in range(2 if LOW else 9):              # 김 (D3: 뜨거운 물에서 오르는 것)
        iso.sphere("steam", (cx - 0.3 + rnd.uniform(-1.1, 1.1), cy + 0.6 + rnd.uniform(-1.1, 1.1),
                             z + 0.95 + rnd.uniform(0, 0.9)), 0.18 + rnd.random() * 0.16,
                   SC.alpha_mat("Steam%d" % k, "#cfd9d6", 0.10, 0.9), 10, 6)
    at(z, iso.laundry, (cx - 2.2, cy + 1.5), (cx + 2.0, cy + 2.0), 2.1)
    iso.prop("k:bucket", cx + 1.9, cy - 0.9, z, h=0.34, rot_z=0.4)
    iso.prop("k:bucket", cx - 2.2, cy - 0.6, z, h=0.32, rot_z=-0.8)
    at(z, iso.jug, cx + 2.2, cy + 0.6, 0.1)
    at(z, iso.plant, cx - 2.2, cy + 1.3, 0.5, True, LOW)
    for k in range(4):
        iso.cube("towel", (cx - 1.4 + k * 0.9, cy - 2.1, z + 0.12), (0.5, 0.34, 0.24),
                 M["pillow"] if k % 2 else M["fabric2"], rot=(0, 0, k * 0.4))
    return pod_lamp(cx - 0.3, cy - 0.1, z, "#FF9A5E", 3800, name="bath")


def r_library(cx, cy, z):
    """도서실 — 200년 치 종이. 서고 부족의 말이 처음 닿는 곳."""
    for w, sgn in ((60, 1), (0, 1), (120, 1)):
        a = math.radians(w)
        px, py = cx + 2.55 * math.cos(a), cy + 2.55 * math.sin(a)
        for lv in range(3):
            iso.cube("bshelf", (px, py, z + 0.55 + lv * 0.72), (0.42, 3.0, 0.06), M["wood"], rot=(0, 0, a))
            rnd = random.Random(w * 7 + lv)
            for k in range(4 if LOW else 9):
                h = 0.22 + rnd.random() * 0.14
                off = -1.25 + k * 0.28
                iso.cube("book", (px - off * math.sin(a), py + off * math.cos(a), z + 0.58 + lv * 0.72 + h / 2),
                         (0.3, 0.2, h), M[("red", "blue", "yellow", "green", "paper", "wood_dk")[k % 6]],
                         rot=(0, 0, a))
    iso.cube("desk", (cx - 0.4, cy - 1.2, z + 0.72), (1.6, 0.9, 0.08), M["wood"])
    for sx, sy in ((-1.1, -0.38), (0.35, -0.38), (-1.1, 0.36), (0.35, 0.36)):
        iso.cube("desk_leg", (cx - 0.4 + sx, cy - 1.2 + sy, z + 0.36), (0.09, 0.09, 0.72), M["wood_dk"])
    iso.cube("openbook", (cx - 0.4, cy - 1.2, z + 0.79), (0.5, 0.36, 0.05), M["paper"], rot=(0, 0, 0.3))
    iso.cube("stool", (cx - 0.4, cy - 2.1, z + 0.22), (0.5, 0.5, 0.44), M["wood_dk"])
    at(z, iso.plant, cx + 1.9, cy - 1.5, 0.5, True, LOW)
    for k in range(6):                            # 바닥에 쌓인 책탑
        iso.cube("stack", (cx + 1.0 + (k % 2) * 0.4, cy - 1.9 + (k // 2) * 0.05, z + 0.05 + k * 0.09),
                 (0.36, 0.28, 0.09), M[("paper", "red", "blue")[k % 3]], rot=(0, 0, k * 0.25))
    return pod_lamp(cx - 0.4, cy - 0.4, z, "#FFA844", 4200, name="library")


ROOMS = [
    # (id, 레벨, 슬롯각, 빌더)
    ("airlock", 0, 240, r_airlock),
    ("storage", 0, 0, r_storage),
    ("quarters", 1, 180, r_quarters),
    ("workshop", 1, 300, r_workshop),
    ("greenhouse", 1, 60, r_greenhouse),
    ("lounge", 2, 240, r_lounge),
    ("bath", 2, 120, r_bath),
    ("library", 2, 0, r_library),
]


# ══════════════════════════════════════════════════════════════
# 중앙 앵커 기둥 · 유리 껍질 · 에어락 관
# ══════════════════════════════════════════════════════════════
def anchor_column():
    iso.cyl("column", (0, 0, 13.6), COL_R, 27.6, M["hull"], verts=20)
    iso.cyl("column_core", (0, 0, 13.6), COL_R - 0.22, 27.8, M["hull_dk"], verts=20)
    for k in range(5 if LOW else 9):              # 기둥 마디
        iso.cyl("colband", (0, 0, 1.4 + k * (5.6 if LOW else 3.1)), COL_R + 0.09, 0.22, M["hull_lt"], verts=20)
    nstep = 10 if LOW else 26                     # 기둥에 감긴 사다리
    for k in range(nstep):
        t = k / (nstep - 1.0)
        a = t * math.radians(900)
        z = 1.2 + t * 24.0
        iso.cube("step", ((COL_R + 0.28) * math.cos(a), (COL_R + 0.28) * math.sin(a), z),
                 (0.72, 0.16, 0.06), M["hull_lt"], rot=(0, 0, a))
    # 해저에 박힌 발 + 버팀 케이블
    iso.cyl("foot", (0, 0, 0.35), 3.2, 0.7, M["hull_dk"], verts=18)
    iso.cyl("foot2", (0, 0, 0.12), 4.4, 0.24, M["hull_dk"], verts=18)
    for k in range(6):
        a = math.radians(30 + 60 * k)
        ex, ey = 8.6 * math.cos(a), 8.6 * math.sin(a)
        strut("guy", (COL_R * math.cos(a), COL_R * math.sin(a), 6.2), (ex, ey, 0.45), 0.07, M["hull_dk"], 6)
        iso.cube("anchorpin", (ex, ey, 0.3), (0.7, 0.7, 0.6), M["hull_dk"], rot=(0, 0, a))
    iso.cyl("colcap", (0, 0, 27.5), COL_R - 0.45, 0.40, M["hull_dk"], verts=16)
    iso.cyl("colcap2", (0, 0, 27.90), COL_R - 0.95, 0.34, M["hull_dk"], verts=14)
    for k in range(6):                            # 꼭대기 표지등 고리
        a = math.radians(60 * k)
        iso.sphere("capmark", ((COL_R - 0.3) * math.cos(a), (COL_R - 0.3) * math.sin(a), 27.82), 0.10,
                   iso.mat("capmark_m%d" % k, "#FFD9A8", 0.3, emit="#FF9E3A", strength=9), 8, 5)
    bpy.ops.object.light_add(type='POINT', location=(0, 0, 28.6))    # 꼭대기 표지등(D3)
    l = bpy.context.object; l.name = "L_beacon"
    l.data.color = iso.hexcol("#FFB066"); l.data.energy = 900; l.data.shadow_soft_size = 0.4
    iso.sphere("beacon", (0, 0, 28.42), 0.17, iso.mat("beacon_m", "#FFE0B0", 0.3, emit="#FFA64A", strength=9), 10, 6)


def airlock_tube(lamps):
    """에어락(L0 @240) 바닥 문풀에서 껍질을 뚫고 나가는 관 + 바깥 발판 + 해저로 내려가는 사다리."""
    cx, cy = slot_xy(240)
    cx, cy = cx, cy - 0.6
    z_top, z_bot = LEVELS[0], 2.6
    iso.cyl("alt_tube", (cx, cy, (z_top + z_bot) / 2), 1.24, z_top - z_bot, M["hull"], verts=16)
    iso.cyl("alt_core", (cx, cy, (z_top + z_bot) / 2), 1.06, z_top - z_bot + 0.1, M["hull_dk"], verts=16)
    for k in range(4):
        iso.cyl("alt_band", (cx, cy, z_bot + 0.6 + k * 1.1), 1.32, 0.16, M["hull_lt"], verts=16)
    for k in range(9):                            # 관 속 사다리
        iso.cube("alt_step", (cx + 1.0, cy, z_bot + 0.5 + k * 0.48), (0.5, 0.12, 0.05), M["hull_lt"])
    # 바깥 해치 + 발판
    iso.cyl("alt_collar", (cx, cy, z_bot - 0.1), 1.5, 0.4, M["hull_lt"], verts=18)
    iso.cyl("alt_deck", (cx + 0.4, cy - 0.9, z_bot - 0.34), 2.1, 0.22, M["hull_dk"], verts=18)
    for k in range(7):                            # 발판 난간
        a = math.radians(150 + k * 30)
        iso.cyl("alt_rail", (cx + 0.4 + 2.0 * math.cos(a), cy - 0.9 + 2.0 * math.sin(a), z_bot + 0.16),
                0.05, 0.9, M["hull_lt"], verts=6)
    iso.cube("alt_hatch", (cx - 1.34, cy - 0.2, z_bot + 0.55), (0.12, 1.5, 1.6), M["hull_lt"],
             rot=(0, 0, math.radians(-25)))
    # 해저로 내려가는 사다리
    for sx in (-0.34, 0.34):
        iso.cyl("alt_lrail", (cx + 0.4 + sx + 1.5, cy - 2.5, 1.25), 0.06, 2.6, M["hull_lt"], verts=6)
    for k in range(7):
        iso.cube("alt_lstep", (cx + 1.9, cy - 2.5, 0.25 + k * 0.38), (0.66, 0.1, 0.05), M["hull_lt"])
    # 출입구 등 하나 — 검은 물로 새어 나가는 유일한 빛 (D3)
    iso.cyl("alt_lampcase", (cx + 0.4, cy - 2.4, z_bot + 0.9), 0.22, 0.34, M["hull_lt"],
            rot=(math.radians(58), 0, 0), verts=10)
    iso.sphere("alt_bulb", (cx + 0.45, cy - 2.62, z_bot + 0.72), 0.18,
               iso.mat("alt_bulb_m", "#FFE2B4", 0.3, emit="#FFA63C", strength=26), 12, 7)
    bpy.ops.object.light_add(type='SPOT', location=(cx + 0.45, cy - 2.62, z_bot + 0.72))
    l = bpy.context.object; l.name = "L_airlock_out"
    l.data.color = iso.hexcol("#FFA63C"); l.data.energy = 2600; l.data.spot_size = math.radians(74)
    l.data.spot_blend = 0.55; l.data.shadow_soft_size = 0.3
    l.data.use_custom_distance = True; l.data.cutoff_distance = 12.0
    SC.aim(l, (cx + 1.4, cy - 7.0, 0.0))
    lamps.append(Vector((cx + 0.45, cy - 2.62, z_bot + 0.72)))
    return Vector((cx + 1.9, cy - 3.2, 0.0))       # 사다리 발치 = 주민이 서는 자리


def glass_shell(lamps, nt=None, np_=None):
    nt = nt or (10 if LOW else 15); np_ = np_ or (20 if LOW else 30)
    """구형 유리 껍질을 사선 평면으로 자른다. 카메라를 향한 캡만 제거하고 뒷면·아래앞면은 남긴다(D4)."""
    def dirv(t, p):
        return Vector((math.sin(t) * math.cos(p), math.sin(t) * math.sin(p), math.cos(t)))

    def sph(t, p, rr=R):
        return Vector((0, 0, CZ)) + dirv(t, p) * rr

    plain, warm, rim_hi, ribs = [], [], [], []
    inset = 0.10
    for i in range(nt):
        t0, t1 = math.pi * i / nt, math.pi * (i + 1) / nt
        for j in range(np_):
            p0, p1 = 2 * math.pi * j / np_, 2 * math.pi * (j + 1) / np_
            tm, pm = (t0 + t1) / 2, (p0 + p1) / 2
            u = dirv(tm, pm)
            if u.dot(VXY) >= CUT_OFF - CUT_TILT * u.z:
                continue                                   # 잘려 나간 캡
            ta = t0 + (t1 - t0) * inset; tb = t1 - (t1 - t0) * inset
            pa = p0 + (p1 - p0) * inset; pb = p1 - (p1 - p0) * inset
            quad = [sph(ta, pa), sph(ta, pb), sph(tb, pb), sph(tb, pa)]
            near = u.dot(V) > 0.05
            surf = sph(tm, pm)
            d = min((surf - lp).length for lp in lamps) if lamps else 99
            if not near and d < 5.0:
                warm.append(quad)                          # 안쪽 등불이 직접 때리는 뒷면 유리
            elif near and u.z > 0.15:
                rim_hi.append(quad)                        # 위에서 내려오는 잔광이 스치는 앞면 유리
            else:
                plain.append(quad)
            if j % 5 == 0:                                 # 세로 리브
                ribs.append([sph(t0, pm - 0.009, R * 1.008), sph(t0, pm + 0.009, R * 1.008),
                             sph(t1, pm + 0.009, R * 1.008), sph(t1, pm - 0.009, R * 1.008)])
            if i % 3 == 0:                                 # 가로 링
                ribs.append([sph(tm - 0.009, p0, R * 1.008), sph(tm + 0.009, p0, R * 1.008),
                             sph(tm + 0.009, p1, R * 1.008), sph(tm - 0.009, p1, R * 1.008)])
    mesh_of_quads("keep_shell_glass", plain, M["glass"])
    mesh_of_quads("keep_shell_glass_warm", warm, M["glass_warm"])
    mesh_of_quads("keep_shell_glass_rim", rim_hi, M["glass_rim"])
    mesh_of_quads("shell_ribs", ribs, M["hull_dk"])

    # 절단면 테두리(구조 칼라) — 사선 평면 ∩ 구 = 기울어진 원
    mv = VXY + Vector((0, 0, CUT_TILT))
    m = mv.normalized()
    off = CUT_OFF / mv.length
    rr = R * math.sqrt(max(1e-3, 1 - off * off))
    c = Vector((0, 0, CZ)) + m * (R * off)
    e1 = m.cross(Vector((0, 0, 1))).normalized(); e2 = m.cross(e1).normalized()
    n = 28 if LOW else 72
    for k in range(n):
        a0 = 2 * math.pi * k / n; a1 = 2 * math.pi * (k + 1) / n
        p0 = c + e1 * (rr * math.cos(a0)) + e2 * (rr * math.sin(a0))
        p1 = c + e1 * (rr * math.cos(a1)) + e2 * (rr * math.sin(a1))
        mid = (p0 + p1) / 2
        seg = (p1 - p0)
        o = iso.cyl("cutrim", mid, 0.30, seg.length * 1.06, M["hull_lt"], verts=6 if LOW else 8)
        o.rotation_euler = seg.to_track_quat('Z', 'Y').to_euler()
    # 기둥이 껍질을 뚫는 자리의 밀폐 칼라
    for zz in (CZ - R, CZ + R):
        iso.cyl("polecollar", (0, 0, zz), 2.5, 0.5, M["hull_lt"], verts=20)


# ══════════════════════════════════════════════════════════════
# 바깥 — 해저, 부유물, 발광 생물, 대형 생물 실루엣
# ══════════════════════════════════════════════════════════════
def seafloor():
    o = iso.cyl("PRV_seafloor", (0, 0, -0.35), SEA_R - 3.0, 0.7, M["silt"], verts=64)
    o.name = "PRV_seafloor"
    quads = []                                   # 가장자리가 어둠 속으로 떨어지는 사면(하드 엣지 금지)
    n = 64
    for k in range(n):
        a0 = 2 * math.pi * k / n; a1 = 2 * math.pi * (k + 1) / n
        r0, r1 = SEA_R - 3.0, SEA_R + 4.0
        quads.append([Vector((r0 * math.cos(a0), r0 * math.sin(a0), 0.0)),
                      Vector((r0 * math.cos(a1), r0 * math.sin(a1), 0.0)),
                      Vector((r1 * math.cos(a1), r1 * math.sin(a1), -11.0)),
                      Vector((r1 * math.cos(a0), r1 * math.sin(a0), -11.0))])
    mesh_of_quads("PRV_seafloor_skirt", quads, M["silt2"]).name = "PRV_seafloor_skirt"
    rnd = random.Random(1212)
    for k in range(34):                          # 퇴적 둔덕 (B9)
        a = rnd.uniform(0, 6.283); d = rnd.uniform(5.0, SEA_R - 1.0)
        s = iso.sphere("PRV_mound", (d * math.cos(a), d * math.sin(a), -0.5 + rnd.random() * 0.3),
                       0.9 + rnd.random() * 2.6, M["silt2"], 12, 7)
        s.scale = (1.0, 1.0, 0.24); s.name = "PRV_mound"
    for k in range(26):
        a = rnd.uniform(0, 6.283); d = rnd.uniform(6.0, SEA_R - 1.5)
        p = iso.prop("k:" + ("rock-a", "rock-b", "rock-c")[k % 3], d * math.cos(a), d * math.sin(a),
                     -0.1, h=0.4 + rnd.random() * 1.4, rot_z=rnd.uniform(0, 6.283), recolor=M["silt2"])
        if p:
            p.name = "PRV_rock"
    for k in range(9):                           # 관벌레 무리 (어두운 실루엣 + 발광 끝)
        a = rnd.uniform(0, 6.283); d = rnd.uniform(9.0, SEA_R - 2.0)
        bx, by = d * math.cos(a), d * math.sin(a)
        for t in range(5):
            h = 0.6 + rnd.random() * 1.1
            tx, ty = bx + rnd.uniform(-0.8, 0.8), by + rnd.uniform(-0.8, 0.8)
            c = iso.cyl("PRV_worm", (tx, ty, h / 2), 0.07, h, M["kelp"], verts=6)
            c.name = "PRV_worm"
            s = iso.sphere("PRV_wormtip", (tx, ty, h), 0.09, M["bio_dim"], 8, 5); s.name = "PRV_wormtip"


def particulates(seed=77):
    """D5 부유물 — 시선 방향으로 3겹. 직교 카메라라 겹마다 크기·밝기로 깊이를 만든다."""
    rnd = random.Random(seed)
    layers = [(150, 0.022, -17.0, 7.0, "snow_far"), (110, 0.036, -3.0, 12.0, "snow"),
              (55, 0.062, 12.0, 10.0, "snow")]
    for li, (n, size, dep0, dspan, key) in enumerate(layers):
        quads = []
        for _ in range(n):
            sr = rnd.uniform(-58, 58); su = rnd.uniform(-22, 40)
            c = screen_at(sr, su, dep0 + rnd.uniform(0, dspan))
            s = size * rnd.uniform(0.6, 1.6)
            quads.append([c - RIGHT * s - UP * s, c + RIGHT * s - UP * s,
                          c + RIGHT * s + UP * s, c - RIGHT * s + UP * s])
        o = mesh_of_quads("PRV_snow%d" % li, quads, M[key])
        o.name = "PRV_snow%d" % li


def bioluminescence(seed=55):
    """D3 근거 있는 빛 — 발광 해파리·플랑크톤 무리. 한색 쪽 유일한 악센트."""
    rnd = random.Random(seed)
    for k in range(4):
        c = screen_at(rnd.uniform(-52, 52), rnd.uniform(-8, 34), rnd.uniform(DEEP_MIN, 18))
        if (c - Vector((0, 0, CZ))).length < R + 3.5:
            continue
        s = iso.sphere("PRV_jelly", c, 0.30 + rnd.random() * 0.28, M["bio"], 12, 7)
        s.scale = (1.0, 1.0, 0.7); s.name = "PRV_jelly"
        for t in range(4):                      # 촉수
            tt = iso.cyl("PRV_tent", c + Vector((rnd.uniform(-.2, .2), rnd.uniform(-.2, .2), -0.55)),
                         0.02, 1.0, M["bio_dim"], verts=4)
            tt.name = "PRV_tent"
        bpy.ops.object.light_add(type='POINT', location=c)
        l = bpy.context.object; l.name = "PRV_L_bio"
        l.data.color = iso.hexcol("#5fe0d6"); l.data.energy = 120; l.data.shadow_soft_size = 0.8
    for k in range(1):                          # 플랑크톤 점묘 무리
        cc = screen_at(rnd.uniform(-50, 50), rnd.uniform(-6, 30), rnd.uniform(DEEP_MIN, 12))
        for t in range(14):
            p = cc + Vector((rnd.uniform(-2.5, 2.5), rnd.uniform(-2.5, 2.5), rnd.uniform(-2.0, 2.0)))
            s = iso.sphere("PRV_plank", p, 0.045 + rnd.random() * 0.04, M["bio_dim"], 6, 4)
            s.name = "PRV_plank"


def leviathan(sr, su, depth, length=22.0, seed=3, lit=False):
    """D6 대형 생물은 형체보다 그림자로. 물보다 아주 조금 밝은 단색으로만 그린다."""
    rnd = random.Random(seed)
    base = screen_at(sr, su, depth)
    fwd = Vector((RIGHT.x, RIGHT.y, 0)).normalized()          # 화면 가로로 지나간다
    side = Vector((-fwd.y, fwd.x, 0))
    mm = M["murk_lt"] if lit else M["murk"]
    segs = 26
    for k in range(segs):
        t = k / (segs - 1.0)
        r = length * 0.085 * math.sin(math.pi * (0.10 + 0.90 * t)) ** 0.45 + 0.10
        p = base + fwd * (length * (t - 0.5)) + Vector((0, 0, math.sin(t * 3.0) * 0.5))
        s = iso.sphere("PRV_lev", p, r, mm, 14, 8)
        s.scale = (1.0, 0.68, 0.80); s.name = "PRV_lev"
    head = base + fwd * (length * 0.5)
    h = iso.sphere("PRV_levhead", head + fwd * 0.6, length * 0.055, mm, 14, 8)
    h.scale = (1.5, 0.7, 0.62); h.name = "PRV_levhead"
    for sgn in (-1, 1):                                        # 노처럼 생긴 지느러미 두 쌍
        for off, sz, sw in ((-0.06, 0.20, 0.30), (0.22, 0.13, 0.20)):
            for t in range(6):
                u = t / 5.0
                p = (base + fwd * (length * (off - u * sw * 0.45))
                     + side * (sgn * length * (0.05 + u * sz))
                     + Vector((0, 0, -length * u * 0.035)))
                f = iso.sphere("PRV_levfin", p, length * sz * (0.16 - u * 0.09) + 0.1, mm, 10, 6)
                f.scale = (1.0, 1.0, 0.42); f.name = "PRV_levfin"
    for t in range(7):                                         # 가늘어지는 꼬리 + 꼬리날
        u = t / 6.0
        p = base - fwd * (length * (0.47 + u * 0.11)) + Vector((0, 0, math.sin(2.6 + u) * 0.5))
        f = iso.sphere("PRV_levtail", p, length * (0.055 - u * 0.045) + 0.07, mm, 10, 6)
        f.scale = (1.0, 0.7, 1.0 + u * 1.9); f.name = "PRV_levtail"


# ══════════════════════════════════════════════════════════════
# 사람 — 기존 역할 GLB 를 그대로 (잠수복은 아직 없음)
# ══════════════════════════════════════════════════════════════
def resident(glb, x, y, z=0.0, rot_z=0.0, h=1.68):
    saved = iso.KENNEY
    iso.KENNEY = CHARS
    try:
        o = iso.prop("k:" + glb, x, y, z, h=h, rot_z=rot_z)
    finally:
        iso.KENNEY = saved
    if o:
        o.name = "PRV_char_" + glb
    return o


# ══════════════════════════════════════════════════════════════
# 세계 · 조명 · 렌더
# ══════════════════════════════════════════════════════════════
def deep_world(fog=0.0030):
    """검은 물 + 위에서 겨우 내려오는 잔광(박광층). 정체불명의 환경광 금지(D3)."""
    SC.sky(top="#02060a", strength=0.03)
    w = bpy.context.scene.world
    try:
        nt = w.node_tree
        vs = nt.nodes.new("ShaderNodeVolumeScatter")
        vs.inputs["Color"].default_value = (*iso.hexcol("#2f6f8a"), 1)
        vs.inputs["Density"].default_value = fog
        nt.links.new(vs.outputs["Volume"], nt.nodes["World Output"].inputs["Volume"])
        sc = bpy.context.scene
        for attr, val in (("volumetric_start", 1.0), ("volumetric_end", 160.0),
                          ("volumetric_samples", 48), ("use_volumetric_lights", True),
                          ("volumetric_tile_size", '8')):
            try:
                setattr(sc.eevee, attr, val)
            except Exception:
                pass
    except Exception as e:
        print("VOLUME SKIPPED", e, flush=True)
    try:
        bpy.context.scene.eevee.use_raytracing = True
    except Exception as e:
        print("RAYTRACE SKIPPED", e, flush=True)
    # 광원 1: 위에서 내려오는 잔광. 돔 위 실루엣에 한색 반사 띠를 만든다(D4)
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 60))
    s = bpy.context.object; s.name = "PRV_L_down"
    s.data.energy = 0.11; s.data.color = iso.hexcol("#4d8ea3"); s.data.angle = math.radians(14)
    s.rotation_euler = (math.radians(11), 0, math.radians(-38))
    # 광원 2: 카메라 쪽 위에서 오는 아주 약한 한색 — 돔 윗 유리에 반사 띠를 만든다(D4의 '반사')
    bpy.ops.object.light_add(type='AREA', location=(-15, -15, 46))
    a = bpy.context.object; a.name = "PRV_L_rim"
    a.data.energy = 1500; a.data.size = 20; a.data.color = iso.hexcol("#3f8fae")
    SC.aim(a, (0, 0, CZ + 7))


def build_dome(with_chars=False):
    """돔 본체만(해저·부유물 제외). GLB 로 내보내는 것과 같은 내용."""
    lamps = []
    anchor_column()
    for rid, lv, slot, fn in ROOMS:
        z = LEVELS[lv]
        cx, cy = slot_xy(slot)
        hex_cell(cx, cy, z, slot)
        corridor(slot, z)
        lamps.append(fn(cx, cy, z))
    ladder_foot = airlock_tube(lamps)
    glass_shell(lamps)
    mk = bpy.data.objects.new("marker_airlock_exit", None)
    bpy.context.collection.objects.link(mk); mk.location = ladder_foot
    return lamps, ladder_foot


# ── 렌더 ─────────────────────────────────────────────────────
def shot_hero():
    global M
    M = deep_materials()
    deep_world()
    build_dome()
    seafloor()
    bioluminescence(55)
    particulates(77)
    leviathan(sr=-24.0, su=24.5, depth=-19.0, length=19.0, seed=4)
    water_backdrop()
    noline_setup()
    SC.preview(os.path.join(OUT_RAW, "dome_hero.png"), ortho=66.0, target=(0, 0, 14.6),
               res=(1600, 900), az=AZ, el=EL, freestyle=True, exposure=-0.10)


def shot_airlock():
    global M
    M = deep_materials()
    deep_world(fog=0.0055)
    lamps, foot = build_dome()
    seafloor()
    particulates(31)
    bioluminescence(12)
    water_backdrop(depth=-20.0, w=90.0, h=70.0)

    # 사다리를 막 내려선 주민 + 해치에서 지켜보는 주민 (잠수복 미구현 — 기존 역할 GLB 그대로)
    resident("scout", foot.x + 0.9, foot.y - 1.6, 0.0, rot_z=math.radians(212), h=1.72)
    resident("engineer", foot.x - 3.1, foot.y + 2.0, 2.37, rot_z=math.radians(22), h=1.68)
    noline_setup()
    SC.preview(os.path.join(OUT_RAW, "dome_airlock.png"), ortho=15.5,
               target=(foot.x - 0.6, foot.y + 0.9, 1.6), res=(1600, 900), az=AZ, el=EL,
               freestyle=True, exposure=-0.30)


def shot_depth():
    global M
    M = deep_materials()
    deep_world(fog=0.0044)
    build_dome()
    seafloor()
    bioluminescence(91)
    leviathan(sr=-17.0, su=27.0, depth=-19.0, length=30.0, seed=9)
    leviathan(sr=31.0, su=4.0, depth=-20.0, length=16.0, seed=17)
    particulates(5)
    particulates(19)
    water_backdrop(depth=-24.0, w=200.0, h=150.0)
    noline_setup()
    SC.preview(os.path.join(OUT_RAW, "dome_depth.png"), ortho=104.0, target=(0, 0, 16.0),
               res=(1600, 900), az=AZ, el=EL, freestyle=True, exposure=-0.26)


def dedupe_assets():
    """같은 CC0 소품을 여러 번 임포트하면 동일한 텍스처·재질의 사본(.001, .002 …)이 쌓인다.
    GLB 용량의 주범이므로 이름 기준으로 하나로 합친다(B8: 소품을 줄이기 전에 합친다)."""
    def base(n):
        return n.rsplit(".", 1)[0] if n.rsplit(".", 1)[-1].isdigit() else n
    for coll in (bpy.data.images, bpy.data.materials):
        seen = {}
        for it in list(coll):
            b = base(it.name)
            if b in seen and seen[b] is not it:
                it.user_remap(seen[b])
            else:
                seen.setdefault(b, it)


def build_glb():
    global M, LOW
    LOW = True
    M = deep_materials()
    build_dome()
    dedupe_assets()
    SC.join_scene("dome_core")
    SC.export(os.path.join(OUT_SCENES, "dome_core.glb"))
    lo, hi = iso._bbox([o for o in bpy.data.objects if o.type == 'MESH'])
    print("BBOX blender  x %.2f~%.2f  y %.2f~%.2f  z %.2f~%.2f" % (lo.x, hi.x, lo.y, hi.y, lo.z, hi.z), flush=True)


if __name__ == "__main__":
    jobs = {"hero": shot_hero, "airlock": shot_airlock, "depth": shot_depth, "glb": build_glb}
    for k in (["hero", "airlock", "depth", "glb"] if MODE == "all" else [MODE]):
        jobs[k]()
    print("ALL DONE", flush=True)
