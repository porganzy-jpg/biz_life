# -*- coding: utf-8 -*-
"""
잔해 방주 — 아이소메트릭(디아블로식 사선 내려보기) 방 타일 렌더
blender -b --python tools/blender_iso.py -- <out_dir> [room_id ...] [--level=1]

방 = 6×6m 바닥, 높이 4m. 카메라가 보는 두 벽(-X, -Y)은 제거하고 뒷벽 둘(+X, +Y)만 남긴다.
직교 카메라, 방위각 45°, 고도 30° (2:1 다이메트릭, 디아블로/폴아웃1 계열).
투명 배경 PNG + tile_meta.json(바닥 마름모의 화면 좌표) → 클라이언트가 격자에 정확히 배치.
"""
import bpy, sys, os, math, json
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "art_raw/iso")
ONLY = [a for a in argv[1:] if not a.startswith("--")]
LEVEL = int(next((a.split("=")[1] for a in argv if a.startswith("--level=")), "1"))
os.makedirs(OUT, exist_ok=True)

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
KENNEY = os.path.join(ROOT, "assets3d", "kenney", "Models", "GLB format")
QUAT = os.path.join(ROOT, "assets3d", "quaternius", "Survival Pack - Sept 2020", "Blends")

S, RH = 6.0, 2.6          # 바닥 한 변, 벽 높이 (낮은 벽: 뒤 칸이 가려지지 않게, 디아블로·폴아웃1식)
HALF = S / 2
RES = 640                  # 정사각 출력
ORTHO = 9.8                # 직교 스케일 (6×6×4 박스가 여유 있게 들어감)
AZ, EL = 45, 45            # 카메라 방위각, 고도 (레퍼런스 7점 분석: 바닥이 넓게 보이는 45°)

sc = None
M = {}
# 지반 판: 3×3 격자(18m)보다 넓게 깔리는 바닥. 픽셀/미터를 클라이언트가 맞추므로 크게 렌더.
PLATES = {"ground_under": dict(size=24.0, ortho=36.0, res=1400), "ground_surface": dict(size=16.0, ortho=24.0, res=1200)}
CUR = dict(size=6.0, ortho=9.8, res=640)


def hexcol(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def mat(name, hexc, rough=0.8, emit=None, strength=0.0, metallic=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hexcol(hexc), 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metallic
    if emit:
        b.inputs["Emission Color"].default_value = (*hexcol(emit), 1); b.inputs["Emission Strength"].default_value = strength
    return m


def make_materials():
    M.clear()
    M.update(dict(
        concrete=mat("concrete", "#4a4640", 0.95), concrete_dk=mat("concrete_dk", "#37342f", 0.95),
        floor=mat("floor", "#5a4a38", 0.9), floor2=mat("floor2", "#4c3f31", 0.9), beam=mat("beam", "#2a2521", 0.9),
        wood=mat("wood", "#8a6a44", 0.85), wood_dk=mat("wood_dk", "#6e5336", 0.85),
        metal=mat("metal", "#7d8790", 0.5, metallic=0.6), copper=mat("copper", "#b5703a", 0.45, metallic=0.7),
        water=mat("water", "#3E7EA6", 0.1, emit="#4FB7E6", strength=0.6),
        white=mat("white", "#E8DFCB", 0.9), red=mat("red", "#C8442F", 0.8), yellow=mat("yellow", "#E0B54A", 0.8),
        blue=mat("blue", "#3E7EA6", 0.8), green=mat("green", "#5f9a72", 0.8), paper=mat("paper", "#DED3BB", 0.95),
        earth=mat("earth", "#1e1813", 1.0), earth2=mat("earth2", "#2a231c", 1.0), rock=mat("rock", "#5a564d", 1.0), weed=mat("weed", "#4f6a3a", 0.9),
        tile=mat("tile", "#6f7a7c", 0.4), tile2=mat("tile2", "#8a9597", 0.4), line=mat("line", "#F2A93B", 0.6),
        rail=mat("rail", "#6a6f73", 0.4, metallic=0.7), lamp_m=mat("lamp_m", "#5a5f63", 0.5, metallic=0.5),
        leaf=mat("leaf", "#5f9a4a", 0.7), leaf_dk=mat("leaf_dk", "#3f6e33", 0.7), moss=mat("moss", "#4a6b3a", 1.0),
        terracotta=mat("terracotta", "#a86a45", 0.9), jug=mat("jug", "#cfe3ea", 0.2), glass_dk=mat("glass_dk", "#1d2326", 0.15, metallic=0.3),
        tarp=mat("tarp", "#6b7a56", 0.9), fabric=mat("fabric", "#8a4a3f", 0.95), fabric2=mat("fabric2", "#4a5c7a", 0.95), pillow=mat("pillow", "#e8e2d0", 0.95),
        fire=mat("fire", "#ffb347", 0.4, emit="#ff7a1a", strength=18), packet_r=mat("packet_r", "#c8442f", 0.8), packet_y=mat("packet_y", "#e0b54a", 0.8),
        packet_b=mat("packet_b", "#3e7ea6", 0.8), packet_w=mat("packet_w", "#e8dfcb", 0.8), packet_g=mat("packet_g", "#5f9a72", 0.8),
        # 지상 매장층(mall_*): 콘크리트 대신 타일·유리·크롬
        mallfloor=mat("mallfloor", "#524a3f", 0.5), grout=mat("grout", "#37322b", 0.9),
        tilewall=mat("tilewall", "#4c5653", 0.5), tilewall2=mat("tilewall2", "#3e4744", 0.5),
        glass_lt=mat("glass_lt", "#8aa3a7", 0.25, emit="#bcd6da", strength=0.55),
        glass_dirty=mat("glass_dirty", "#63777a", 0.3), esc_dk=mat("esc_dk", "#3b4247", 0.55, metallic=0.5),
        metal_lt=mat("metal_lt", "#646d72", 0.5, metallic=0.6), chrome=mat("chrome", "#7b848a", 0.35, metallic=0.8),
        cardboard=mat("cardboard", "#a9824f", 0.95), rubber=mat("rubber", "#26282a", 0.85),
    ))


def cube(name, loc, size, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = size; o.data.materials.append(m); return o


def cyl(name, loc, r, h, m, rot=(0, 0, 0), verts=16):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.object; o.name = name; o.data.materials.append(m); return o


def sphere(name, loc, r, m, seg=16, ring=8):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=ring)
    o = bpy.context.object; o.name = name; o.data.materials.append(m); return o


def _bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == 'MESH' for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def prop(source, x, y, z=0.0, h=0.6, rot_z=0.0, recolor=None):
    before = set(bpy.data.objects)
    kind, name = source.split(":", 1)
    if kind == "k":
        bpy.ops.import_scene.gltf(filepath=os.path.join(KENNEY, name + ".glb"))
    else:
        with bpy.data.libraries.load(os.path.join(QUAT, name + ".blend"), link=False) as (src, dst):
            dst.objects = [n for n in src.objects]
        for o in dst.objects:
            if o is not None:
                bpy.context.collection.objects.link(o)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    if not meshes:
        return None
    bpy.ops.object.empty_add(location=(0, 0, 0)); root = bpy.context.object; root.name = "prop_" + name
    for o in new:
        if o.parent is None and o is not root:
            o.parent = root
    bpy.context.view_layer.update()
    lo, hi = _bbox(meshes)
    dx, dy, dz = hi.x - lo.x, hi.y - lo.y, hi.z - lo.z
    if dz < 0.3 * max(dx, dy):          # 납작한 소품(잔디 패치 등)은 가로 크기 기준으로 정규화
        s = h * 2.0 / max(dx, dy, 1e-4)
    else:
        s = h / max(dz, 1e-4)
    root.scale = (s, s, s); bpy.context.view_layer.update()
    lo, hi = _bbox(meshes)
    root.location = (x - (lo.x + hi.x) / 2, y - (lo.y + hi.y) / 2, z - lo.z)
    root.rotation_euler = (0, 0, rot_z)
    if recolor:
        for o in meshes:
            o.data.materials.clear(); o.data.materials.append(recolor)
    return root


# ── 셸: 바닥 + 뒷벽 2개(+X, +Y). 카메라 쪽 벽·천장 없음 ─────────
def shell(kind="room"):
    if kind == "rock":
        # 미굴착: 벽 없는 낮은 흙 덩이 (방과 명확히 구분)
        cube("floor", (0, 0, -0.15), (S, S, 0.3), M["earth2"])
        cube("mound", (0.4, 0.4, 0.35), (S - 1.2, S - 1.2, 0.7), M["earth"])
        cube("edgeX", (HALF - 0.1, 0, 0.2), (0.2, S, 0.4), M["earth"]); cube("edgeY", (0, HALF - 0.1, 0.2), (S, 0.2, 0.4), M["earth"])
        return
    if kind == "lot":
        cube("ground", (0, 0, -0.15), (S, S, 0.3), M["concrete_dk"])
        return
    if kind == "mall":
        # 지상 매장층: 광택 타일 바닥 + 타일 벽 + 상단 채광 유리 띠 + 매장 기둥
        cube("floor", (0, 0, -0.15), (S, S, 0.3), M["mallfloor"])
        for i in range(-3, 4):
            cube(f"gx{i}", (i * 1.0, 0, 0.004), (0.04, S, 0.008), M["grout"])
            cube(f"gy{i}", (0, i * 1.0, 0.004), (S, 0.04, 0.008), M["grout"])
        cube("wallX", (HALF + 0.15, 0, RH / 2), (0.3, S + 0.3, RH), M["tilewall"])
        cube("wallY", (0, HALF + 0.15, RH / 2), (S + 0.3, 0.3, RH), M["tilewall2"])
        for i in range(-2, 3):      # 벽 타일 줄눈(세로) — 유리 띠 아래까지만
            cube(f"wtx{i}", (HALF - 0.01, i * 1.2, 0.85), (0.02, 0.03, 1.7), M["grout"])
            cube(f"wty{i}", (i * 1.2, HALF - 0.01, 0.85), (0.03, 0.02, 1.7), M["grout"])
        for z in (0.55, 1.15, 1.7):  # 줄눈(가로)
            cube("wtxh", (HALF - 0.01, 0, z), (0.02, S, 0.03), M["grout"])
            cube("wtyh", (0, HALF - 0.01, z), (S, 0.02, 0.03), M["grout"])
        cube("glassX", (HALF - 0.06, 0, 2.15), (0.03, S, 0.8), M["glass_lt"])
        cube("glassY", (0, HALF - 0.06, 2.15), (S, 0.03, 0.8), M["glass_lt"])
        for i in range(-2, 3):      # 창틀 멀리언(유리보다 앞)
            cube(f"mx{i}", (HALF - 0.10, i * 1.3, 2.15), (0.06, 0.07, 0.82), M["metal_lt"])
            cube(f"my{i}", (i * 1.3, HALF - 0.10, 2.15), (0.07, 0.06, 0.82), M["metal_lt"])
        cube("sillX", (HALF - 0.10, 0, 1.73), (0.08, S, 0.06), M["metal_lt"])
        cube("sillY", (0, HALF - 0.10, 1.73), (S, 0.08, 0.06), M["metal_lt"])
        cube("pillar", (2.35, -2.35, RH / 2), (0.5, 0.5, RH), M["tilewall"])
        cube("pillarcap", (2.35, -2.35, RH - 0.07), (0.62, 0.62, 0.14), M["metal_lt"])
        cube("curbX", (-HALF + 0.08, 0, 0.06), (0.16, S, 0.12), M["concrete_dk"])
        cube("curbY", (0, -HALF + 0.08, 0.06), (S, 0.16, 0.12), M["concrete_dk"])
        return
    cube("floor", (0, 0, -0.15), (S, S, 0.3), M["floor"])
    for i in range(-2, 3):  # 바닥 판 이음선
        cube(f"fl{i}", (i * 1.2, 0, 0.002), (0.03, S, 0.01), M["floor2"])
    cube("wallX", (HALF + 0.15, 0, RH / 2), (0.3, S + 0.3, RH), M["concrete"])
    cube("wallY", (0, HALF + 0.15, RH / 2), (S + 0.3, 0.3, RH), M["concrete_dk"])
    # 옛 역 흔적: 벽 하단 타일 띠 + 노선색 띠
    cube("tilesX", (HALF - 0.01, 0, 0.6), (0.02, S, 1.2), M["tile"]); cube("lineX", (HALF - 0.02, 0, 1.3), (0.02, S, 0.1), M["line"])
    cube("tilesY", (0, HALF - 0.01, 0.6), (S, 0.02, 1.2), M["tile"]); cube("lineY", (0, HALF - 0.02, 1.3), (S, 0.02, 0.1), M["line"])
    for i in range(-2, 3):
        cube(f"bx{i}", (HALF - 0.05, i * 1.3, RH / 2), (0.1, 0.08, RH), M["beam"])
        cube(f"by{i}", (i * 1.3, HALF - 0.05, RH / 2), (0.08, 0.1, RH), M["beam"])
    # 바닥 가장자리 콘크리트 테두리 (타일 경계 인식용)
    cube("curbX", (-HALF + 0.08, 0, 0.06), (0.16, S, 0.12), M["concrete_dk"]); cube("curbY", (0, -HALF + 0.08, 0.06), (S, 0.16, 0.12), M["concrete_dk"])


def lantern(color, strength=1000, x=0.0, y=0.0):
    z = RH + 0.6
    cyl("wire", (x, y, RH + 1.1), 0.012, 1.0, M["beam"])
    cyl("lamp", (x, y, z), 0.14, 0.3, M["lamp_m"])
    sphere("bulb", (x, y, z - 0.08), 0.12, mat("bulb" + color, "#FFE1A6", 0.3, emit=color, strength=14))
    bpy.ops.object.light_add(type='POINT', location=(x, y, z - 0.15)); l = bpy.context.object
    l.data.color = hexcol(color); l.data.energy = strength * 4.2; l.data.shadow_soft_size = 0.7
    bpy.ops.object.light_add(type='POINT', location=(x - 1.0, y - 1.0, 0.8)); g = bpy.context.object
    g.data.color = hexcol(color); g.data.energy = strength * 0.5; g.data.shadow_soft_size = 2.0
    bpy.ops.object.light_add(type='AREA', location=(-6, -6, 8), rotation=(math.radians(40), 0, math.radians(-45))); f = bpy.context.object
    f.data.energy = 420; f.data.size = 10; f.data.color = (0.85, 0.9, 1.0)


def shelf_x(y, z, w=2.4, d=0.5):
    """+X 뒷벽에 붙는 선반 (y 위치, 높이 z). 윗면 z 반환."""
    cube("shelf", (HALF - d / 2 - 0.16, y, z), (d, w, 0.06), M["wood"]); cube("shelfb", (HALF - d / 2 - 0.16, y, z - 0.05), (d, w, 0.04), M["wood_dk"])
    return z + 0.03


def shelf_y(x, z, w=2.4, d=0.5):
    """+Y 뒷벽에 붙는 선반."""
    cube("shelf", (x, HALF - d / 2 - 0.16, z), (w, d, 0.06), M["wood"]); cube("shelfb", (x, HALF - d / 2 - 0.16, z - 0.05), (w, d, 0.04), M["wood_dk"])
    return z + 0.03


XB, YB = HALF - 0.42, HALF - 0.42   # 뒷벽 앞 소품 기준선


def books_y(x0, z, n=9, w=2.0):
    cols = [M["red"], M["blue"], M["yellow"], M["green"], M["paper"], M["wood_dk"], M["white"]]
    step = w / n
    for i in range(n):
        h = 0.26 + (i * 7 % 5) * 0.03
        cube("book", (x0 - w / 2 + step * (i + 0.5), YB, z + h / 2), (step * 0.8, 0.22, h), cols[i % len(cols)])


def books_x(y0, z, n=9, w=2.0):
    cols = [M["red"], M["blue"], M["yellow"], M["green"], M["paper"], M["wood_dk"], M["white"]]
    step = w / n
    for i in range(n):
        h = 0.26 + (i * 5 % 5) * 0.03
        cube("book", (XB, y0 - w / 2 + step * (i + 0.5), z + h / 2), (0.22, step * 0.8, h), cols[(i + 2) % len(cols)])


# ── 생활 소품 헬퍼 (아늑한 생존) ────────────────────────────
import random as _R


def plant(x, y, h=0.6, pot=True, lod=False):
    sg, rg, vt = (10, 6, 10) if lod else (16, 8, 16)
    if pot:
        cyl("pot", (x, y, 0.15), 0.17, 0.3, M["terracotta"], verts=vt)
    for k in range(3):
        sphere("leaf", (x + (k - 1) * 0.13, y + (k % 2) * 0.1, 0.3 + h * 0.45 + k * 0.09), 0.15 + 0.04 * k, M["leaf" if k % 2 else "leaf_dk"], sg, rg)


def vine(x, y, z_top, length=1.6, along='x', seed=1, lod=False):
    """벽에서 흘러내리는 덩굴."""
    sg, rg = (10, 6) if lod else (16, 8)
    r = _R.Random(seed)
    n = int(length / 0.2)
    for k in range(n):
        j = (r.random() - 0.5) * 0.18
        cube("vine", (x + (j if along == 'y' else 0), y + (j if along == 'x' else 0), z_top - k * 0.2), (0.09, 0.09, 0.22), M["leaf"] if k % 3 else M["leaf_dk"])
        if k % 2 == 0:
            sphere("vl", (x + (j if along == 'y' else 0) + 0.06, y + (j if along == 'x' else 0) + 0.06, z_top - k * 0.2), 0.07, M["leaf"], sg, rg)


def moss(x, y, w=0.8, d=0.6, rot=0.0):
    cube("moss", (x, y, 0.004), (w, d, 0.008), M["moss"], rot=(0, 0, rot))


def note(x, y, z, wall='x'):
    if wall == 'x':
        cube("note", (HALF - 0.02, y, z), (0.01, 0.22, 0.28), M["paper"])
    else:
        cube("note", (x, HALF - 0.02, z), (0.22, 0.01, 0.28), M["paper"])


def laundry(p0, p1, z=2.0):
    (x0, y0), (x1, y1) = p0, p1
    import math as _m
    L = _m.hypot(x1 - x0, y1 - y0); ang = _m.atan2(y1 - y0, x1 - x0)
    cyl("line", ((x0 + x1) / 2, (y0 + y1) / 2, z), 0.008, L, M["beam"], rot=(0, _m.radians(90), ang))
    for k, m in enumerate(["fabric", "pillow", "fabric2"]):
        t = 0.25 + k * 0.25
        cube("cloth", (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z - 0.3), (0.32, 0.03, 0.5), M[m], rot=(0, 0, ang))


def jug(x, y, rot=0.0):
    prop("k:bottle-large", x, y, 0, h=0.42, rot_z=rot, recolor=M["jug"])


def shelf_unit(x, y, rot=0.0):
    """편의점 진열대: 금속 프레임 + 색색 포장 상품 3단."""
    import math as _m
    c, sn = _m.cos(rot), _m.sin(rot)
    def loc(dx, dy, z):
        return (x + dx * c - dy * sn, y + dx * sn + dy * c, z)
    for dx in (-0.6, 0.6):
        for dy in (-0.22, 0.22):
            cube("frame", loc(dx, dy, 0.85), (0.04, 0.04, 1.7), M["metal2"] if "metal2" in M else M["metal"], rot=(0, 0, rot))
    cols = ["packet_r", "packet_y", "packet_b", "packet_w", "packet_g"]
    for si, z in enumerate((0.45, 0.95, 1.45)):
        cube("shelf", loc(0, 0, z), (1.24, 0.48, 0.03), M["metal"], rot=(0, 0, rot))
        for k in range(6):
            cube("pk", loc(-0.5 + k * 0.2, 0.0, z + 0.14), (0.15, 0.3, 0.25), M[cols[(k + si) % 5]], rot=(0, 0, rot))
    cube("top", loc(0, 0, 1.72), (1.24, 0.48, 0.03), M["metal"], rot=(0, 0, rot))


def fridge(x, y, rot=0.0, dead=True):
    cube("fr", (x, y, 0.9), (0.9, 0.7, 1.8), M["white"], rot=(0, 0, rot))
    import math as _m
    fx = x - 0.36 * _m.sin(rot); fy = y - 0.36 * _m.cos(rot)
    cube("frglass", (fx, fy, 1.0), (0.78, 0.02, 1.4), M["glass_dk"], rot=(0, 0, rot))
    if not dead:
        bpy.ops.object.light_add(type='POINT', location=(fx, fy - 0.2, 1.0)); l = bpy.context.object; l.data.energy = 120; l.data.color = (0.6, 0.85, 1.0)


def firepit(x, y):
    prop("k:campfire-pit", x, y, 0, h=0.35)
    sphere("flame", (x, y, 0.45), 0.16, M["fire"])
    bpy.ops.object.light_add(type='POINT', location=(x, y, 0.8)); l = bpy.context.object; l.data.energy = 700; l.data.color = (1.0, 0.55, 0.2); l.data.shadow_soft_size = 0.5


def bedroll(x, y, rot=0.0):
    prop("k:bedroll", x, y, 0, h=0.3, rot_z=rot)
    import math as _m
    cube("pillow", (x - 0.5 * _m.cos(rot), y - 0.5 * _m.sin(rot), 0.2), (0.35, 0.3, 0.14), M["pillow"], rot=(0, 0, rot))


def mall_fill(energy=160, color=(0.78, 0.86, 1.0)):
    """lantern()이 깔아 둔 차가운 큰 필라이트를 매장층용으로 낮춘다(밖은 차갑고 안은 따뜻하게)."""
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.data.type == 'AREA':
            o.data.energy = energy; o.data.color = color


# ── 매장층 전용 소품 (원시 도형) ────────────────────────────
def cart(x, y, rot=0.0, load=True):
    """쇼핑 카트: 금속 프레임 + 바구니 + 바퀴 + 손잡이."""
    import math as _m
    c, s_ = _m.cos(rot), _m.sin(rot)
    R = (0, 0, rot)

    def loc(dx, dy, z):
        return (x + dx * c - dy * s_, y + dx * s_ + dy * c, z)
    cube("cbase", loc(0, 0, 0.55), (0.82, 0.54, 0.03), M["chrome"], rot=R)
    cube("cwf", loc(0, -0.27, 0.72), (0.82, 0.03, 0.34), M["chrome"], rot=R)
    cube("cwb", loc(0, 0.27, 0.72), (0.82, 0.03, 0.34), M["chrome"], rot=R)
    cube("cwl", loc(-0.41, 0, 0.72), (0.03, 0.54, 0.34), M["chrome"], rot=R)
    cube("cwr", loc(0.41, 0, 0.72), (0.03, 0.54, 0.34), M["chrome"], rot=R)
    for k in range(5):                                   # 바구니 살대
        cube("cbar", loc(-0.32 + k * 0.16, 0, 0.72), (0.02, 0.56, 0.31), M["metal_lt"], rot=R)
    for dx, dy in ((-0.34, -0.21), (0.34, -0.21), (-0.34, 0.21), (0.34, 0.21)):
        cyl("cleg", loc(dx, dy, 0.29), 0.018, 0.54, M["metal_lt"], verts=8)
        cyl("cwheel", loc(dx, dy, 0.05), 0.05, 0.03, M["rubber"], rot=(0, _m.radians(90), rot), verts=8)
    cube("cback", loc(-0.43, 0, 0.80), (0.03, 0.52, 0.5), M["metal_lt"], rot=R)
    cyl("chandle", loc(-0.45, 0, 1.06), 0.022, 0.54, M["rubber"], rot=(_m.radians(90), 0, rot), verts=8)
    if load:
        cols = ["packet_r", "packet_y", "packet_b", "packet_w", "packet_g"]
        for k in range(4):
            cube("cload", loc(-0.26 + k * 0.18, (k % 2) * 0.12 - 0.06, 0.68), (0.16, 0.26, 0.24), M[cols[k % 5]], rot=(0, 0, rot + k * 0.2))


def can_pile(x, y, rows=3, seed=0):
    """통조림 피라미드."""
    r = _R.Random(seed + 7)
    for lv in range(rows):
        n = rows - lv
        for k in range(n):
            cx = x + (k - (n - 1) / 2) * 0.17 + (r.random() - .5) * 0.02
            cyl("can", (cx, y + (r.random() - .5) * 0.05, 0.055 + lv * 0.112), 0.075, 0.11, M["packet_r"] if (k + lv) % 2 else M["packet_y"], verts=10)
            cyl("cantop", (cx, y, 0.112 + lv * 0.112), 0.076, 0.012, M["metal_lt"], verts=10)


def shards(x, y, n=7, spread=0.9, seed=0):
    """깨진 유리 조각."""
    r = _R.Random(seed + 13)
    for _ in range(n):
        cube("shard", (x + (r.random() - .5) * spread * 2, y + (r.random() - .5) * spread * 2, 0.012),
             (0.10 + r.random() * 0.18, 0.05 + r.random() * 0.12, 0.02), M["glass_dirty"], rot=(0, 0, r.random() * 3))


def sapling(x, y, h=1.1, seed=0):
    """계단 틈에서 자란 어린 나무."""
    r = _R.Random(seed + 21)
    cyl("trunk", (x, y, h * 0.42), 0.045, h * 0.84, M["wood_dk"], rot=(r.random() * 0.1, r.random() * 0.1, 0), verts=10)
    for k in range(3):
        sphere("crown", (x + (k - 1) * 0.16, y + (k % 2) * 0.12, h * 0.82 + k * 0.1), 0.24 + r.random() * 0.1, M["leaf"] if k % 2 else M["leaf_dk"], 12, 7)


# ── 방 정의 ──────────────────────────────────────────────────
def room_pantry():
    shell(); lantern("#F2A93B", 1400, x=-0.3, y=-0.3)
    # 편의점 진열대 2대 (+Y 벽), 죽은 냉장고 (+X 벽 모서리)
    shelf_unit(-1.5, YB - 0.1); shelf_unit(-0.1, YB - 0.1)
    fridge(XB - 0.15, 1.6, rot=math.radians(90))
    t = shelf_x(-0.6, 1.3, w=2.2)
    for i, src in enumerate(["q:Can_Red", "q:Can_Closed", "q:Can_Red", "q:Can_Open", "q:Can_Closed", "q:Can_Red"]):
        prop(src, XB, -1.6 + i * 0.38, t, h=0.28)
    t = shelf_x(-0.6, 2.0, w=2.2)
    for i in range(5): prop("k:bottle", XB, -1.5 + i * 0.42, t, h=0.4 if i % 2 else 0.34)
    prop("k:barrel", -2.3, 0.4, 0, h=1.0); prop("k:barrel-open", -1.5, -0.2, 0, h=0.9)
    prop("k:box-large", 1.7, 0.2, 0, h=0.85); prop("k:box-open", 0.9, 0.7, 0, h=0.55); prop("k:box", 2.2, -0.9, 0, h=0.5); prop("k:box", 1.6, -1.0, 0.0, h=0.42)
    cube("table", (-0.6, -1.2, 0.75), (1.5, 0.8, 0.06), M["wood"])
    for dx, dy in ((-0.65, -0.3), (0.65, -0.3), (-0.65, 0.3), (0.65, 0.3)): cube("tleg", (-0.6 + dx, -1.2 + dy, 0.36), (0.08, 0.08, 0.72), M["wood_dk"])
    prop("q:Pot", -0.9, -1.2, 0.78, h=0.26); prop("q:Can_Open", -0.3, -1.1, 0.78, h=0.18); prop("q:Backpack", 0.6, -2.0, 0, h=0.55, rot_z=0.6)
    jug(-2.4, -1.6); jug(-2.0, -1.9, 0.4); jug(-2.4, -2.2)
    plant(2.4, -2.3, 0.7); moss(-1.8, -2.4, 1.0, 0.5, 0.3); moss(2.2, 1.0, 0.7, 0.5)
    vine(XB + 0.4, -0.2, RH, 1.4, 'x', 3); note(0, 0.9, 1.9, 'x'); note(0, 0.5, 1.7, 'x')
    laundry((-2.6, -0.8), (-0.4, 1.4), 2.05)
    if LEVEL >= 2:
        shelf_unit(1.3, YB - 0.1)


def room_well():
    shell(); lantern("#4FB7E6", 1050)
    prop("q:PropaneTank", -1.6, 1.7, 0, h=2.2, recolor=M["metal"]); prop("q:PropaneTank", 0.0, 2.0, 0, h=1.7, recolor=M["metal"])
    cyl("pipe1", (-0.8, 1.85, 1.9), 0.05, 1.6, M["copper"], rot=(0, math.radians(90), 0))
    cyl("pipe2", (1.3, 1.9, 1.3), 0.05, 1.3, M["copper"]); cyl("pipe3", (1.3, 1.2, 0.8), 0.05, 1.4, M["copper"], rot=(math.radians(90), 0, 0))
    cube("basin", (1.3, 0.1, 0.3), (1.2, 0.9, 0.6), M["metal"]); cube("waterS", (1.3, 0.1, 0.58), (1.05, 0.75, 0.04), M["water"])
    cyl("tap", (1.3, 0.6, 0.9), 0.03, 0.5, M["copper"])
    t = shelf_x(-1.4, 1.4, w=2.0)
    for i, sname in enumerate(["q:WaterBottle_1", "q:WaterBottle_2", "q:WaterBottle_3", "q:WaterBottle_1", "q:WaterBottle_2"]): prop(sname, XB, -2.2 + i * 0.4, t, h=0.34)
    t = shelf_x(-1.4, 2.05, w=2.0)
    for i in range(5): prop("k:bottle-large", XB, -2.2 + i * 0.4, t, h=0.38)
    for k, (x, y) in enumerate([(-0.3, -1.4), (0.2, -1.6), (-0.3, -2.0), (0.3, -2.2), (0.8, -1.9), (-0.8, -1.8)]): jug(x, y, k * 0.5)
    prop("k:bucket", -1.4, -0.9, 0, h=0.4); prop("k:barrel", -2.3, -0.4, 0, h=0.9, recolor=M["blue"]); prop("k:barrel", -2.3, 0.6, 0, h=0.9, recolor=M["blue"])
    moss(0.4, -0.6, 1.4, 0.9, 0.2); moss(-1.9, -2.2, 0.8, 0.6); moss(2.3, -1.3, 0.6, 0.9)
    vine(0.6, YB + 0.4, RH, 1.8, 'y', 5); vine(XB + 0.4, 2.2, RH, 1.2, 'x', 6)
    plant(2.4, -2.3, 0.6); plant(-2.4, -2.4, 0.5)
    cube("drip", (1.3, 0.1, 0.9), (0.02, 0.02, 0.6), M["water"])
    if LEVEL >= 2: prop("k:barrel", 0.6, -2.5, 0, h=0.9, recolor=M["blue"])


def room_infirmary():
    shell(); lantern("#7DE0A8", 1000)
    bedroll(-1.7, 1.2, math.radians(90)); bedroll(0.3, 1.2, math.radians(90))
    cyl("ivpole", (-0.8, 1.6, 0.9), 0.02, 1.8, M["metal"]); prop("k:bottle", -0.8, 1.6, 1.75, h=0.25, recolor=M["jug"])
    cube("cab", (XB - 0.05, -1.3, 1.25), (0.4, 1.1, 1.3), M["paper"]); cube("cabdoor", (XB - 0.27, -1.3, 1.25), (0.02, 1.0, 1.2), M["white"])
    cube("crossv", (XB - 0.29, -1.3, 1.25), (0.02, 0.16, 0.56), M["red"]); cube("crossh", (XB - 0.29, -1.3, 1.25), (0.02, 0.56, 0.16), M["red"])
    prop("q:FirstAidKit", -2.3, -0.4, 0, h=0.3); prop("q:Bandages", 1.6, -1.6, 0, h=0.14); prop("q:Bandages", 1.9, -1.3, 0, h=0.14); prop("q:FirstAidKit_Hard", 2.0, 0.6, 0, h=0.28)
    t = shelf_y(-1.0, 2.05, w=2.6)
    for i in range(7): prop("k:bottle", -2.2 + i * 0.4, YB, t, h=0.3 if i % 2 else 0.24, recolor=M["white"] if i % 2 else M["green"])
    prop("k:box", -0.6, -0.4, 0, h=0.4, recolor=M["white"]); cube("screen", (2.0, 0.6, 0.85), (0.04, 1.4, 1.7), M["paper"])
    cube("stool", (-0.6, 0.3, 0.25), (0.35, 0.35, 0.05), M["wood"]); cube("stooll", (-0.6, 0.3, 0.12), (0.06, 0.06, 0.25), M["wood_dk"])
    jug(-2.4, -1.5); jug(-2.4, -2.0)
    plant(2.4, -2.4, 0.7); plant(-2.4, 2.3, 0.5); moss(1.0, -2.2, 1.0, 0.6, 0.4)
    note(0, -0.2, 1.8, 'x'); note(0, 0.3, 1.95, 'x'); note(-1.6, 0, 1.75, 'y'); vine(XB + 0.4, 2.4, RH, 1.0, 'x', 7)
    if LEVEL >= 2: bedroll(-1.7, -1.2, math.radians(90))


def room_library():
    shell(); lantern("#E0B54A", 1200)
    for zz in (0.5, 1.3, 2.05):
        t = shelf_y(-1.2, zz, w=2.8); books_y(-1.2, t, n=11, w=2.7)
    for zz in (0.5, 1.3, 2.05):
        t = shelf_x(0.6, zz, w=2.4); books_x(0.6, t, n=9, w=2.3)
    prop("k:workbench", -0.4, -1.2, 0, h=0.9, rot_z=math.radians(15))
    cube("bluep", (-0.5, -1.25, 0.92), (0.6, 0.42, 0.01), M["blue"], rot=(0, 0, math.radians(15)))
    cyl("candle", (0.2, -1.6, 1.0), 0.03, 0.18, M["paper"]); sphere("flame", (0.2, -1.6, 1.12), 0.035, M["fire"])
    for i in range(3): prop("k:box", 1.6 + (i % 2) * 0.5, -1.8 + i * 0.5, 0, h=0.4)
    prop("q:Radio", XB - 0.1, -2.4, 0.0, h=0.28)
    cube("rug", (-1.4, -0.6, 0.006), (2.0, 1.4, 0.012), M["fabric"]); cube("rug2", (-1.4, -0.6, 0.012), (1.6, 1.0, 0.006), M["fabric2"])
    cube("cushion", (-2.0, -0.4, 0.12), (0.5, 0.5, 0.22), M["pillow"]); cube("cushion2", (-1.0, -0.9, 0.12), (0.5, 0.5, 0.22), M["fabric2"])
    for k in range(4): cube("bookpile", (-2.3, -2.0 + k * 0.05, 0.05 + k * 0.1), (0.35, 0.25, 0.09), M[["red", "blue", "paper", "green"][k]], rot=(0, 0, k * 0.2))
    cube("ladder1", (2.3, -0.6, 1.2), (0.05, 0.05, 2.4), M["wood"], rot=(0, math.radians(8), 0)); cube("ladder2", (2.3, -0.3, 1.2), (0.05, 0.05, 2.4), M["wood"], rot=(0, math.radians(8), 0))
    for i in range(5): cube("rung", (2.3 - i * 0.03, -0.45, 0.5 + i * 0.45), (0.04, 0.3, 0.04), M["wood_dk"])
    plant(2.4, -2.4, 0.7); plant(-2.5, 1.2, 0.4, pot=True); vine(XB + 0.4, -2.0, RH, 1.1, 'x', 9)
    note(0, -1.6, 1.9, 'x'); note(0, -1.2, 2.1, 'x'); note(0, -0.9, 1.8, 'x')


def room_hall():
    """중앙 역 홀 — 옛 승강장에 텐트를 치고 산다."""
    shell(); lantern("#F2A93B", 900, x=-0.8, y=-0.6)
    cube("cage", (HALF - 0.8, HALF - 0.8, RH / 2 - 0.1), (1.5, 1.5, RH - 0.2), M["lamp_m"])
    cube("cageDoor", (HALF - 1.55, HALF - 0.8, 1.1), (0.04, 1.2, 2.2), M["beam"])
    for i in range(6): cube("bar", (HALF - 1.56, HALF - 1.3 + i * 0.2, 1.1), (0.03, 0.03, 2.2), M["metal"])
    cube("rail1", (-0.6, -1.7, 0.05), (S - 0.4, 0.06, 0.1), M["rail"]); cube("rail2", (-0.6, -2.4, 0.05), (S - 0.4, 0.06, 0.1), M["rail"])
    for i in range(7): cube("tie", (-2.6 + i * 0.75, -2.05, 0.02), (0.18, 0.9, 0.04), M["wood_dk"])
    cube("safety", (-0.6, -1.15, 0.003), (S - 0.4, 0.1, 0.01), M["line"])
    cube("bench", (-1.6, 1.6, 0.45), (1.6, 0.4, 0.06), M["wood"]); cube("benchb", (-1.6, 1.8, 0.7), (1.6, 0.05, 0.5), M["wood"])
    for dx in (-0.7, 0.7): cube("bl", (-1.6 + dx, 1.6, 0.22), (0.06, 0.4, 0.44), M["beam"])
    cube("sign", (0.9, YB + 0.15, 2.1), (1.6, 0.05, 0.45), M["tile2"]); cube("signline", (0.9, YB + 0.12, 2.1), (1.4, 0.02, 0.1), M["line"])
    cyl("post", (2.0, -0.4, 1.1), 0.05, 2.2, M["metal"]); sphere("sig", (2.0, -0.4, 2.3), 0.12, mat("sigg", "#7DE0A8", 0.3, emit="#7DE0A8", strength=6))
    # 아늑한 생존: 텐트 + 모닥불 + 침낭 + 물통 + 채소 상자
    prop("k:tent", -1.4, -0.2, 0, h=1.5, rot_z=math.radians(-25))
    firepit(0.6, -0.3); bedroll(1.6, 0.5, math.radians(20))
    jug(0.2, 0.9); jug(0.6, 1.1, 0.5); prop("q:Pot", 1.1, -0.7, 0.0, h=0.24)
    for k in range(3): cube("planter", (-2.2 + k * 0.7, 2.4, 0.15), (0.6, 0.4, 0.3), M["wood_dk"]);
    for k in range(3):
        for q in range(3): sphere("veg", (-2.4 + k * 0.7 + q * 0.2, 2.4 + (q % 2) * 0.1, 0.42), 0.09, M["leaf"])
    prop("q:Trashcan", -2.3, -0.6, 0, h=0.8); prop("k:box", 1.8, 1.7, 0, h=0.45)
    moss(1.6, -1.4, 1.2, 0.5, 0.1); moss(-2.2, 0.8, 0.7, 0.9); vine(XB + 0.4, -1.8, RH, 1.6, 'x', 11); vine(-1.8, YB + 0.4, RH, 1.2, 'y', 12)
    laundry((-2.6, 1.0), (-0.6, 2.4), 2.0)
    note(0, 0.1, 1.8, 'x'); note(0, -0.4, 1.95, 'x')


def room_rock():
    shell("rock")
    bpy.ops.object.light_add(type='POINT', location=(-1.5, -1.5, 2.5)); l = bpy.context.object; l.data.energy = 180; l.data.color = (1, .8, .55)
    for i, sname in enumerate(["k:rock-a", "k:rock-b", "k:rock-c", "k:resource-stone-large", "k:rock-a", "k:resource-stone", "k:rock-b"]):
        prop(sname, -2.0 + (i % 4) * 1.3, -1.8 + (i // 4) * 1.6 + (i % 2) * 0.5, 0, h=0.4 + (i % 3) * 0.25, rot_z=i * 0.7, recolor=M["rock"])
    for i in range(8):
        cube("rubble", (-2.4 + i * 0.7, 1.6 - (i % 3) * 0.5, 0.08), (0.5, 0.35, 0.16), M["rock"], rot=(0, 0, i * 0.4))
    prop("k:tool-pickaxe", 1.8, -2.0, 0, h=0.9, rot_z=0.3)
    for k in range(4): cyl("root", (-1.8 + k * 1.1, 0.4 + (k % 2) * 0.9, 0.72), 0.04, 1.4, M["wood_dk"], rot=(math.radians(85), 0, k * 0.8))
    moss(0.4, 0.4, 1.6, 1.0, 0.2); moss(-1.5, -0.8, 0.9, 0.6, 0.5)


def room_lot():
    shell("lot")
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 8), rotation=(math.radians(50), math.radians(15), math.radians(-30))); sl = bpy.context.object; sl.data.energy = 2.6; sl.data.color = (1.0, 0.9, 0.78)
    for i, (x, y, w, h) in enumerate([(2.2, 2.0, 1.2, 2.6), (0.6, 2.4, 0.9, 1.9), (2.4, 0.2, 0.8, 2.1), (-1.4, 2.3, 1.0, 1.5)]):
        cube("ruin", (x, y, h / 2), (w, 0.5, h), M["concrete_dk"]); vine(x - 0.2, y - 0.3, h, h * 0.8, 'x', 20 + i)
    for i, src in enumerate(["k:patch-grass", "k:grass", "k:patch-grass-large", "k:grass-large", "k:patch-grass", "k:grass", "k:patch-grass-large"]):
        prop(src, -2.3 + (i % 4) * 1.4, -2.2 + (i // 4) * 1.2 + (i % 2) * 0.4, 0, h=0.25 + (i % 2) * 0.2, recolor=M["weed"])
    # 채소밭 3이랑
    for r_ in range(3):
        cube("row", (-1.6, -0.9 + r_ * 0.55, 0.08), (2.2, 0.35, 0.16), M["earth2"])
        for q in range(6): sphere("crop", (-2.6 + q * 0.42, -0.9 + r_ * 0.55, 0.28), 0.1, M["leaf"] if q % 2 else M["leaf_dk"])
    # 방수포 천막 + 급수탑
    for dx, dy in ((-0.6, -0.6), (0.6, -0.6), (-0.6, 0.6), (0.6, 0.6)): cyl("tpole", (1.4 + dx, -1.6 + dy, 0.9), 0.03, 1.8, M["wood"])
    cube("tarp", (1.4, -1.6, 1.85), (1.7, 1.7, 0.04), M["tarp"], rot=(math.radians(6), 0, 0))
    prop("k:box", 1.2, -1.7, 0, h=0.45); prop("k:barrel", 1.8, -1.3, 0, h=0.85)
    for dx, dy in ((-0.3, -0.3), (0.3, -0.3), (-0.3, 0.3), (0.3, 0.3)): cyl("wleg", (-2.0 + dx, 1.4 + dy, 0.8), 0.04, 1.6, M["metal"])
    cyl("wtank", (-2.0, 1.4, 2.0), 0.55, 0.8, M["metal"]); cyl("wtop", (-2.0, 1.4, 2.45), 0.6, 0.1, M["metal2"] if "metal2" in M else M["metal"])
    prop("k:fence-fortified", 0.4, 1.4, 0, h=1.3, rot_z=math.radians(20)); prop("k:signpost", 2.2, -0.6, 0, h=1.6, rot_z=0.4)
    prop("k:metal-panel-screws", -0.2, 0.9, 0, h=1.1, rot_z=1.0); prop("q:Trashcan", 2.4, 1.2, 0, h=0.8)
    moss(0.8, 0.4, 1.0, 0.7, 0.3)



# ── 매장층(B0 지상) 타일 3종 ─────────────────────────────────
def room_mall_camp():
    """매장층 — 진열대 사이의 텐트촌. 편의점 진열대 사이 통로에 사람이 산다."""
    shell("mall"); lantern("#F2A93B", 2300, x=-0.4, y=-1.0); mall_fill(150)
    # 진열대 2열 (뒤·중간) — 그 사이가 통로, 앞쪽이 텐트촌
    for x in (-1.95, -0.6, 0.75):
        shelf_unit(x, 2.15)
    for x in (-1.95, -0.6):
        shelf_unit(x, 0.6)
    # 계산대 잔해 (+X 벽 앞)
    cube("counter", (2.2, 1.25, 0.5), (0.95, 2.1, 1.0), M["wood_dk"])
    cube("countertop", (2.2, 1.25, 1.03), (1.08, 2.24, 0.06), M["metal_lt"])
    cube("register", (2.2, 2.0, 1.2), (0.42, 0.5, 0.3), M["white"], rot=(0, 0, 0.3))
    prop("q:Radio", 2.2, 0.45, 1.06, h=0.26)
    # 텐트촌
    prop("k:tent-canvas", 1.15, -0.6, 0, h=1.5, rot_z=math.radians(-28))
    prop("k:tent-canvas", -2.15, -2.3, 0, h=1.05, rot_z=math.radians(22))
    bedroll(-0.8, -1.4, math.radians(12)); bedroll(-0.25, -2.4, math.radians(-8))
    firepit(0.95, -2.1)
    bpy.ops.object.light_add(type='POINT', location=(0.8, -1.8, 1.7)); _cf = bpy.context.object
    _cf.data.energy = 420; _cf.data.color = (1.0, 0.62, 0.28); _cf.data.shadow_soft_size = 1.6
    cube("rug", (-0.15, -1.3, 0.008), (2.1, 1.5, 0.016), M["fabric"], rot=(0, 0, 0.18))
    cube("rug2", (-0.15, -1.3, 0.018), (1.6, 1.1, 0.008), M["terracotta"], rot=(0, 0, 0.18))
    cube("firelog", (1.55, -2.35, 0.09), (0.7, 0.16, 0.18), M["wood_dk"], rot=(0, 0, 0.5))
    cube("firelog2", (1.45, -1.75, 0.09), (0.6, 0.16, 0.18), M["wood_dk"], rot=(0, 0, -0.3))
    # 살림살이 (밀도)
    cube("crate", (-2.55, 0.25, 0.25), (0.65, 0.9, 0.5), M["cardboard"])
    cube("crate2", (-2.55, 0.25, 0.62), (0.5, 0.7, 0.24), M["cardboard"], rot=(0, 0, 0.25))
    prop("k:box-large", -2.45, 1.4, 0, h=0.8); prop("k:box-open", 0.4, 0.55, 0, h=0.5)
    prop("k:barrel-open", 2.35, -1.25, 0, h=0.85)
    prop("q:Pot", 0.45, -2.3, 0.0, h=0.24); prop("q:Backpack", -1.4, -2.5, 0, h=0.5, rot_z=0.8)
    prop("q:Can_Open", 0.2, -1.85, 0, h=0.16); prop("q:Can_Red", -0.05, -2.0, 0, h=0.18)
    prop("q:Trashcan", -2.7, 1.0, 0, h=0.75)
    jug(2.5, -2.05); jug(2.2, -2.4, 0.5); jug(2.65, -2.55)
    cube("table", (-1.15, -0.35, 0.62), (1.3, 0.75, 0.06), M["wood"], rot=(0, 0, 0.12))
    for dx, dy in ((-0.55, -0.28), (0.55, -0.28), (-0.55, 0.28), (0.55, 0.28)):
        cube("tleg", (-1.15 + dx, -0.35 + dy, 0.3), (0.07, 0.07, 0.6), M["wood_dk"])
    prop("q:Pot", -1.5, -0.35, 0.65, h=0.24); prop("q:Can_Closed", -0.85, -0.5, 0.65, h=0.17)
    prop("q:Match", -0.95, -0.15, 0.65, h=0.06)
    for sx, sy in ((-0.25, -0.6), (-1.95, -0.1)):
        cube("stool", (sx, sy, 0.28), (0.34, 0.34, 0.05), M["wood"]); cube("stooll", (sx, sy, 0.14), (0.07, 0.07, 0.28), M["wood_dk"])
    can_pile(2.05, 0.15, 3, 8)
    laundry((-2.7, -0.45), (-0.5, -2.65), 2.0)
    # 초록: 화분·덩굴·이끼
    plant(-2.65, -2.45, 0.7, lod=True); plant(1.95, 1.0, 0.55, lod=True); plant(-1.3, 1.35, 0.45, lod=True)
    vine(XB + 0.35, -0.7, RH, 1.5, 'x', 31, lod=True); vine(1.55, YB + 0.35, RH, 1.25, 'y', 32, lod=True)
    moss(-1.55, -0.55, 1.2, 0.8, 0.25); moss(1.95, 0.15, 0.8, 0.6, 0.6); moss(-2.35, 2.6, 0.9, 0.4)
    moss(-0.3, 1.45, 1.5, 0.9, 0.15); moss(2.3, -0.3, 0.9, 1.3, 0.2); moss(-2.5, -1.9, 1.0, 0.8, 0.5)
    note(0, -1.15, 1.45, 'x'); note(0, -1.55, 1.6, 'x'); note(0.35, 0, 1.5, 'y')
    if LEVEL >= 2:
        shelf_unit(0.75, 0.6); bedroll(1.95, -2.55, math.radians(90))


def room_mall_food():
    """매장층 — 식품관. 색색 포장, 죽은 냉장고 2대, 카트, 통조림 더미, 진열대를 감는 덩굴."""
    shell("mall"); lantern("#E0B54A", 2300, x=-0.5, y=-0.9); mall_fill(160)
    fridge(XB - 0.2, 2.05, rot=math.radians(90)); fridge(XB - 0.2, 0.55, rot=math.radians(90))
    for fy in (2.05, 0.55):                # 죽은 냉장고 내부 선반·남은 상품
        cube("frsh", (XB - 0.34, fy, 0.75), (0.5, 0.62, 0.03), M["metal_lt"])
        cube("frsh2", (XB - 0.34, fy, 1.25), (0.5, 0.62, 0.03), M["metal_lt"])
        for k in range(3):
            cube("frpk", (XB - 0.34, fy - 0.22 + k * 0.22, 0.86), (0.3, 0.16, 0.2), M[["packet_b", "packet_g", "packet_w"][k]])
        cube("frfr", (XB - 0.62, fy, 0.9), (0.06, 0.74, 1.8), M["metal_lt"])
    for x in (-2.0, -0.65, 0.7):          # 뒤 진열대 열
        shelf_unit(x, 2.15)
    for x in (-2.0, -0.65, 0.7):          # 가운데 진열대 열
        shelf_unit(x, 0.6)
    # 덩굴이 진열대를 감는다
    for k in range(7):
        sphere("ivyA", (-2.62 + k * 0.42, 2.40, 1.80 + (k % 3) * 0.05), 0.12, M["leaf"] if k % 2 else M["leaf_dk"], 10, 6)
    for k in range(6):
        sphere("ivyB", (-2.5 + k * 0.42, 0.86, 1.78 + (k % 2) * 0.06), 0.11, M["leaf_dk"] if k % 2 else M["leaf"], 10, 6)
    vine(-2.0, 1.88, 1.78, 1.5, 'y', 41, lod=True); vine(0.70, 1.88, 1.74, 1.3, 'y', 42, lod=True); vine(-0.65, 0.33, 1.74, 1.4, 'y', 43, lod=True)
    vine(XB + 0.35, -0.5, RH, 1.4, 'x', 44, lod=True)
    # 카트 2대
    cart(1.55, -0.95, math.radians(-25)); cart(-1.15, -1.45, math.radians(115), load=False)
    # 통조림 더미
    can_pile(0.25, -2.15, 3, 1); can_pile(-2.4, -0.5, 4, 2); can_pile(2.4, -1.85, 3, 3); can_pile(1.5, -2.6, 2, 5)
    # 팔레트 + 포대
    cube("pallet", (-1.2, -2.5, 0.07), (1.5, 0.9, 0.14), M["wood_dk"])
    for k in range(4):
        cube("sack", (-1.75 + k * 0.36, -2.5 + (k % 2) * 0.16, 0.29), (0.34, 0.5, 0.3), M[["packet_w", "packet_y", "packet_g", "packet_b"][k]], rot=(0, 0, k * 0.3))
    prop("k:box-large", 2.35, 0.15, 0, h=0.8); prop("k:box-open", -2.5, -1.65, 0, h=0.55); prop("k:box", 2.6, -0.75, 0, h=0.45)
    prop("q:Can_Red", 0.85, -1.5, 0, h=0.18); prop("q:Can_Open", -0.6, -2.45, 0, h=0.16); prop("q:Can_Closed", -0.35, -2.2, 0, h=0.18)
    prop("q:Pan", 1.05, -2.6, 0, h=0.1); prop("q:Backpack", -0.05, -1.25, 0, h=0.45, rot_z=1.2)
    jug(2.6, -2.5); jug(2.3, -2.7, 0.4)
    # 쓰러진 진열대 (오른쪽 빈 바닥 채우기)
    cube("fallen", (1.9, -0.55, 0.22), (1.3, 0.5, 0.06), M["metal_lt"], rot=(0, 0, math.radians(-40)))
    cube("fallen2", (1.9, -0.55, 0.44), (1.24, 0.46, 0.04), M["metal_lt"], rot=(0, 0, math.radians(-40)))
    for k in range(4):
        cube("spill", (1.35 + k * 0.34, -1.05 + (k % 2) * 0.3, 0.12), (0.2, 0.28, 0.24), M[["packet_r", "packet_g", "packet_y", "packet_b"][k]], rot=(0, 0, k * 0.6))
    cube("cratev", (-0.15, -1.75, 0.18), (0.8, 0.6, 0.36), M["cardboard"], rot=(0, 0, 0.2))
    for k in range(4):
        sphere("veg", (-0.35 + (k % 2) * 0.32, -1.9 + (k // 2) * 0.3, 0.42), 0.13, M["leaf"] if k % 2 else M["leaf_dk"], 10, 6)
    # 식품관 간판 (+X 벽)
    cube("sign", (HALF - 0.16, -1.3, 2.18), (0.06, 1.9, 0.44), M["wood_dk"])
    cube("signband", (HALF - 0.20, -1.3, 2.18), (0.03, 1.7, 0.16), M["yellow"])
    # 죽은 자판기 + 상자 더미 (오른쪽 빈 공간)
    cube("vend", (1.55, 1.75, 0.95), (0.75, 0.8, 1.9), M["wood_dk"], rot=(0, 0, math.radians(-14)))
    cube("vendglass", (1.28, 1.68, 1.05), (0.12, 0.6, 1.4), M["glass_dirty"], rot=(0, 0, math.radians(-14)))
    for k in range(6):
        cube("vendpk", (1.26, 1.45 + (k % 3) * 0.24, 0.62 + (k // 3) * 0.44), (0.06, 0.16, 0.26), M[["packet_r", "packet_b", "packet_g", "packet_y", "packet_w", "packet_r"][k]], rot=(0, 0, math.radians(-14)))
    vine(1.2, 2.15, 1.95, 1.2, 'x', 45, lod=True)
    for k in range(3):
        cube("stack", (0.45, 1.45 - k * 0.06, 0.22 + k * 0.42), (0.75, 0.62, 0.42), M["cardboard"], rot=(0, 0, 0.15 * k))
    plant(-2.7, -2.6, 0.7, lod=True); plant(2.65, 1.3, 0.5, lod=True); plant(0.55, -0.35, 0.6, lod=True)
    moss(0.95, -0.25, 1.4, 1.0, 0.2); moss(-1.9, 1.35, 1.2, 0.6); moss(2.0, -2.6, 0.8, 0.6, 0.4)
    moss(-2.7, 1.9, 0.7, 1.6, 0.05); moss(1.1, 1.45, 1.1, 0.5, 0.3)
    note(0, -0.95, 1.5, 'x'); note(-0.35, 0, 1.45, 'y')
    if LEVEL >= 2:
        shelf_unit(-1.3, -0.85); can_pile(-1.05, -1.0, 3, 4)


def room_mall_escalator():
    """매장층 — 무너진 에스컬레이터. 위층 구멍으로 빛이 들어오고 계단 틈에서 나무가 자란다."""
    shell("mall"); lantern("#7DE0A8", 1500, x=-1.9, y=-1.6); mall_fill(95)
    EX, EW = 1.15, 1.5                      # 에스컬레이터 중심 x, 폭
    Y0, SR, SH, N = -1.7, 0.30, 0.20, 14    # 시작 y, 단 깊이·높이, 단 수
    ANG = math.atan2(SH, SR)
    BROKEN = (6, 7, 8)
    for k in range(N):
        y, z = Y0 + k * SR, k * SH
        if k in BROKEN:
            continue
        cube("estep", (EX, y, z + SH / 2), (EW, SR, SH), M["esc_dk"])
        cube("etread", (EX, y, z + SH - 0.008), (EW - 0.08, SR - 0.05, 0.02), M["rubber"])
        cube("enose", (EX, y - SR / 2 + 0.03, z + SH - 0.02), (EW - 0.08, 0.05, 0.05), M["chrome"])
        if k in (2, 4, 10, 12):             # 단 사이 잡초
            prop("k:grass", EX + (0.45 if k % 4 else -0.45), y, z + SH, h=0.22, rot_z=k, recolor=M["weed"])
    # 무너진 구간: 내려앉은 판 + 휜 철골
    cube("eslab", (EX - 0.12, Y0 + 7 * SR, 1.02), (EW, 1.35, 0.12), M["esc_dk"], rot=(math.radians(-26), 0, math.radians(7)))
    cube("ebeam", (EX + 0.55, Y0 + 7.4 * SR, 1.25), (0.1, 1.6, 0.1), M["rail"], rot=(math.radians(-40), 0, 0))
    cube("ebeam2", (EX - 0.6, Y0 + 6.6 * SR, 1.05), (0.09, 1.3, 0.09), M["rail"], rot=(math.radians(-18), 0, math.radians(-6)))
    # 난간: 오른쪽은 유리 남음, 왼쪽은 깨져 프레임만
    mid_y, mid_z = Y0 + (N - 1) * SR / 2, (N - 1) * SH / 2
    up = (-math.sin(ANG), math.cos(ANG))    # 경사면의 위 방향 (y, z)
    slope_len = (N - 1) * SR / math.cos(ANG)
    for side, gx in ((1, EX + EW / 2 + 0.07), (-1, EX - EW / 2 - 0.07)):
        cube("ebalfr", (gx, mid_y, mid_z + 0.02), (0.07, slope_len, 0.1), M["esc_dk"], rot=(ANG, 0, 0))
        cube("erail", (gx, mid_y + up[0] * 0.95, mid_z + up[1] * 0.95), (0.13, slope_len, 0.09), M["rubber"], rot=(ANG, 0, 0))
        if side == 1:                        # 온전한 유리면
            cube("ebalg", (gx, mid_y + up[0] * 0.48, mid_z + up[1] * 0.48), (0.04, slope_len - 0.2, 0.88), M["glass_dirty"], rot=(ANG, 0, 0))
        else:                                # 깨진 쪽: 조각 둘만 남음
            for t, ln in ((-0.34, 1.1), (0.38, 0.9)):
                cube("ebalgb", (gx, mid_y + t * slope_len * math.cos(ANG) + up[0] * 0.44,
                                mid_z + t * slope_len * math.sin(ANG) + up[1] * 0.44), (0.04, ln, 0.8), M["glass_dirty"], rot=(ANG, 0, 0))
        for k in range(6):                   # 난간 지지 기둥
            t = -0.42 + k * 0.17
            cube("ebalp", (gx, mid_y + t * slope_len * math.cos(ANG), mid_z + t * slope_len * math.sin(ANG) + 0.45), (0.05, 0.05, 0.9), M["esc_dk"], rot=(ANG, 0, 0))
    # 위층 바닥 조각 (빛이 들어오는 구멍의 가장자리)
    cube("landing", (EX, 2.72, 2.54), (EW + 0.5, 0.56, 0.16), M["mallfloor"])
    cube("landlip", (EX, 2.45, 2.56), (EW + 0.5, 0.06, 0.2), M["esc_dk"])
    cube("ceilfrag", (-1.9, 2.55, 2.45), (1.6, 0.7, 0.14), M["mallfloor"], rot=(math.radians(-9), 0, math.radians(4)))
    # 위에서 들어오는 빛
    bpy.ops.object.light_add(type='SPOT', location=(EX, 1.9, 5.2), rotation=(math.radians(9), 0, 0)); sp = bpy.context.object
    sp.data.energy = 850; sp.data.spot_size = math.radians(40); sp.data.spot_blend = 0.5
    sp.data.color = (0.86, 1.0, 0.94); sp.data.shadow_soft_size = 1.4
    bpy.ops.object.light_add(type='AREA', location=(EX, 2.3, 4.2), rotation=(math.radians(10), 0, 0)); ap = bpy.context.object
    ap.data.energy = 90; ap.data.size = 2.6; ap.data.color = (0.8, 1.0, 0.92)
    # 계단 틈·바닥에서 자란 초록
    sapling(EX - 0.2, Y0 + 7.1 * SR, 1.45, 1); sapling(-2.1, -0.4, 1.25, 2); sapling(2.55, 2.1, 1.0, 3)
    for i, src in enumerate(["k:patch-grass", "k:grass-large", "k:patch-grass-large", "k:grass", "k:patch-grass", "k:grass-large"]):
        prop(src, -2.6 + (i % 3) * 1.1, -2.6 + (i // 3) * 1.0 + (i % 2) * 0.35, 0, h=0.24 + (i % 2) * 0.16, rot_z=i * 0.9, recolor=M["weed"] if i % 2 else M["leaf_dk"])
    vine(EX + EW / 2 + 0.12, 2.35, 2.5, 1.9, 'x', 51, lod=True); vine(-1.5, YB + 0.35, RH, 1.6, 'y', 52, lod=True); vine(XB + 0.35, -1.9, RH, 1.3, 'x', 53, lod=True)
    # 깨진 유리와 잔해
    shards(-0.45, -0.75, 5, 0.8, 1); shards(EX - 0.95, 0.3, 4, 0.55, 2)
    cube("dirsign", (-1.45, 0.45, 0.62), (0.1, 1.5, 1.24), M["wood_dk"], rot=(0, math.radians(-16), 0.5))
    cube("dirsignf", (-1.5, 0.45, 0.62), (0.03, 1.3, 1.04), M["paper"], rot=(0, math.radians(-16), 0.5))
    for k in range(4):
        cube("dirline", (-1.53, 0.45, 0.3 + k * 0.28), (0.02, 0.9, 0.07), M["green"], rot=(0, math.radians(-16), 0.5))
    for k in range(7):
        cube("rubble", (-2.7 + k * 0.5, 1.15 - (k % 3) * 0.45, 0.07), (0.42, 0.3, 0.14), M["rock"], rot=(0, 0, k * 0.5))
    # 계단 밑 야영 흔적 (아늑한 생존)
    bedroll(0.35, -2.45, math.radians(8)); jug(1.95, -2.35); jug(2.25, -2.6, 0.4)
    prop("k:box", 1.35, -2.75, 0, h=0.42); prop("q:Can_Open", 0.95, -2.3, 0, h=0.16)
    firepit(-0.55, -2.3)
    bpy.ops.object.light_add(type='POINT', location=(-0.4, -2.0, 1.5)); _ef = bpy.context.object
    _ef.data.energy = 520; _ef.data.color = (1.0, 0.6, 0.26); _ef.data.shadow_soft_size = 1.6
    cube("rug", (0.0, -2.0, 0.008), (1.9, 1.3, 0.016), M["fabric2"], rot=(0, 0, 0.1))
    prop("q:Backpack", 1.0, -1.85, 0, h=0.45, rot_z=0.7); prop("k:barrel", 2.6, -1.3, 0, h=0.8)
    laundry((-2.65, -1.2), (-1.0, -2.6), 1.95)
    plant(-2.7, -1.5, 0.65, lod=True); plant(2.7, 0.6, 0.5, lod=True)
    moss(0.1, 0.9, 1.6, 1.2, 0.3); moss(-2.2, -0.9, 1.0, 0.8, 0.7); moss(2.6, 1.45, 0.6, 1.4)
    moss(-0.9, -1.5, 1.3, 0.9, 0.15); moss(1.3, 0.1, 0.9, 0.7, 0.5)
    note(0, -2.2, 1.5, 'x'); note(-2.1, 0, 1.45, 'y')


def plate_under():
    """지하 지반: 어두운 흙, 뿌리, 바위, 물웅덩이, 균류 발광, 옛 선로·파이프 잔해."""
    L = CUR["size"]; h = L / 2
    cube("plate", (0, 0, -0.2), (L, L, 0.4), M["earth2"])
    r = _R.Random(880)
    for _ in range(140):                                  # 흙 얼룩
        cube("dirt", ((r.random() - .5) * L, (r.random() - .5) * L, 0.002), (0.4 + r.random() * 1.6, 0.3 + r.random() * 1.0, 0.006), M["earth"] if r.random() > .4 else M["moss"], rot=(0, 0, r.random() * 3))
    for _ in range(26):                                   # 바위
        prop(r.choice(["k:rock-a", "k:rock-b", "k:rock-c", "k:resource-stone"]), (r.random() - .5) * L, (r.random() - .5) * L, 0, h=0.3 + r.random() * 0.6, rot_z=r.random() * 6, recolor=M["rock"])
    for _ in range(34):                                   # 누운 뿌리
        cyl("root", ((r.random() - .5) * L, (r.random() - .5) * L, 0.06), 0.03 + r.random() * 0.04, 0.8 + r.random() * 2.0, M["wood_dk"], rot=(math.radians(88), 0, r.random() * 6))
    for _ in range(9):                                    # 물웅덩이
        cube("puddle", ((r.random() - .5) * L, (r.random() - .5) * L, 0.004), (0.8 + r.random() * 1.4, 0.6 + r.random() * 1.0, 0.008), M["water"], rot=(0, 0, r.random() * 3))
    for _ in range(40):                                   # 균류 발광
        x, y = (r.random() - .5) * L, (r.random() - .5) * L
        sphere("shroom", (x, y, 0.12), 0.06 + r.random() * 0.1, mat("shm", "#7DE0A8", 0.3, emit="#7DE0A8", strength=3 + r.random() * 4))
    for k in range(6):                                    # 끊어진 선로 조각
        x, y = (r.random() - .5) * L, (r.random() - .5) * L; a = r.random() * 3
        cube("railf", (x, y, 0.05), (2.2, 0.06, 0.1), M["rail"], rot=(0, 0, a)); cube("railf2", (x, y + 0.6, 0.05), (2.2, 0.06, 0.1), M["rail"], rot=(0, 0, a))
    for k in range(5):                                    # 파이프
        cyl("pipe", ((r.random() - .5) * L, (r.random() - .5) * L, 0.12), 0.1, 2 + r.random() * 3, M["copper"], rot=(math.radians(90), 0, r.random() * 3))
    bpy.ops.object.light_add(type='AREA', location=(-8, -8, 14), rotation=(math.radians(35), 0, math.radians(-45))); f = bpy.context.object; f.data.energy = 2500; f.data.size = 24; f.data.color = (0.75, 0.85, 1.0)
    bpy.ops.object.light_add(type='POINT', location=(0, 0, 6)); w = bpy.context.object; w.data.energy = 3000; w.data.color = (1.0, 0.75, 0.45); w.data.shadow_soft_size = 4


def plate_surface():
    """지상 지반: 갈라진 아스팔트, 잡초·풀, 잔해, 웅덩이, 이끼."""
    L = CUR["size"]; h = L / 2
    cube("plate", (0, 0, -0.2), (L, L, 0.4), M["concrete_dk"])
    r = _R.Random(881)
    for _ in range(60):                                   # 갈라진 판·이끼
        cube("crack", ((r.random() - .5) * L, (r.random() - .5) * L, 0.002), (0.6 + r.random() * 2.0, 0.05 + r.random() * 0.1, 0.006), M["earth"], rot=(0, 0, r.random() * 3))
        cube("mossp", ((r.random() - .5) * L, (r.random() - .5) * L, 0.003), (0.5 + r.random() * 1.2, 0.4 + r.random() * 0.9, 0.006), M["moss"], rot=(0, 0, r.random() * 3))
    for _ in range(46):                                   # 풀·잡초
        prop(r.choice(["k:grass", "k:grass-large", "k:patch-grass", "k:patch-grass-large"]), (r.random() - .5) * L, (r.random() - .5) * L, 0, h=0.2 + r.random() * 0.3, rot_z=r.random() * 6, recolor=M["weed"] if r.random() > .3 else M["leaf"])
    for _ in range(14):                                   # 잔해
        prop(r.choice(["k:rock-a", "k:rock-c", "k:resource-planks", "k:box-open", "k:metal-panel-narrow"]), (r.random() - .5) * L, (r.random() - .5) * L, 0, h=0.25 + r.random() * 0.5, rot_z=r.random() * 6)
    for _ in range(6):
        cube("puddle", ((r.random() - .5) * L, (r.random() - .5) * L, 0.004), (0.8 + r.random() * 1.2, 0.6 + r.random() * 0.8, 0.008), M["water"], rot=(0, 0, r.random() * 3))
    for _ in range(10):                                   # 어린 나무
        x, y = (r.random() - .5) * L, (r.random() - .5) * L
        cyl("trunk", (x, y, 0.5), 0.05, 1.0, M["wood_dk"]); sphere("crown", (x, y, 1.2), 0.35 + r.random() * 0.3, M["leaf"] if r.random() > .5 else M["leaf_dk"])
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 8), rotation=(math.radians(50), math.radians(15), math.radians(-30))); sl = bpy.context.object; sl.data.energy = 2.6; sl.data.color = (1.0, 0.9, 0.78)


ROOMS = {"ground_under": plate_under, "ground_surface": plate_surface, "pantry": room_pantry, "well": room_well, "infirmary": room_infirmary, "library": room_library,
         "hall": room_hall, "rock": room_rock, "lot": room_lot,
         "mall_camp": room_mall_camp, "mall_food": room_mall_food, "mall_escalator": room_mall_escalator}


# ── 카메라 · 렌더 ────────────────────────────────────────────
def camera():
    az, el = math.radians(AZ), math.radians(EL)
    d = 30.0
    loc = Vector((-math.cos(el) * math.sin(az) * d, -math.cos(el) * math.cos(az) * d, math.sin(el) * d)) + Vector((0, 0, 1.2))
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = CUR["ortho"]
    direction = Vector((0, 0, 1.2)) - loc
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    return cam


def footprint_meta(cam):
    """바닥 마름모 4꼭짓점의 픽셀 좌표 (좌상단 원점)."""
    pts = {}; hh = CUR["size"] / 2; res = CUR["res"]
    for k, (x, y) in {"front": (-hh, -hh), "right": (hh, -hh), "back": (hh, hh), "left": (-hh, hh)}.items():
        v = world_to_camera_view(sc, cam, Vector((x, y, 0)))
        pts[k] = [round(v.x * res, 1), round((1 - v.y) * res, 1)]
    pts["size_m"] = CUR["size"]; pts["res"] = res
    return pts


def render(path):
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = sc.render.resolution_y = CUR["res"]
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.render.use_freestyle = True; sc.render.line_thickness = 1.0
    fs = sc.view_layers[0].freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("relic")
    ls.select_silhouette = True; ls.select_crease = True; ls.select_border = True
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("relic_ls")
    ls.linestyle.color = hexcol("#1a1714"); ls.linestyle.thickness = 1.0
    names = [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items]
    sc.view_settings.view_transform = 'AgX' if 'AgX' in names else 'Filmic'
    sc.view_settings.exposure = 0.7; sc.view_settings.gamma = 1.05
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.06, 0.055, 0.045, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    targets = ONLY or list(ROOMS.keys())
    meta = {}
    for rid in targets:
        bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
        make_materials()
        CUR.clear(); CUR.update(PLATES.get(rid, dict(size=6.0, ortho=9.8, res=640)))
        ROOMS[rid]()
        cam = camera()
        out = os.path.join(OUT, f"{rid}{'' if LEVEL == 1 else '_L' + str(LEVEL)}.png")
        render(out)
        meta[rid] = footprint_meta(cam)
        print("RENDERED", out, flush=True)
    mp = os.path.join(OUT, "tile_meta.json")
    old = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    old.update(meta); old["_res"] = RES
    json.dump(old, open(mp, "w", encoding="utf-8"), indent=1)
    print("ALL DONE", flush=True)
