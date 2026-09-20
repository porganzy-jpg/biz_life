# -*- coding: utf-8 -*-
"""
잔해 방주 — 방 디오라마 3D → 2.5D 프리렌더 (Fallout Shelter / This War of Mine 방식)

blender -b --python tools/blender_rooms.py -- <out_dir> [room_id ...] [--level=1]

방 셸(콘크리트, 정면 개방) + 방 주색 랜턴 + CC0 소품(Kenney GLB, Quaternius .blend) 배치,
직교 카메라 정면 8° 하향, EEVEE + Freestyle 손그림 선. 768×512 PNG.
"""
import bpy, sys, os, math, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "art_raw/rooms3d")
ONLY = [a for a in argv[1:] if not a.startswith("--")]
LEVEL = int(next((a.split("=")[1] for a in argv if a.startswith("--level=")), "1"))
os.makedirs(OUT, exist_ok=True)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KENNEY = os.path.join(ROOT, "assets3d", "kenney", "Models", "GLB format")
QUAT = os.path.join(ROOT, "assets3d", "quaternius", "Survival Pack - Sept 2020", "Blends")

# 방 규격 (m): 폭 6, 높이 4, 깊이 3. 정면(-Y)이 열려 있고 카메라가 -Y에서 본다.
RW, RH, RD = 6.0, 4.0, 3.0

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def hexcol(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def mat(name, hexc, rough=0.8, emit=None, strength=0.0, metallic=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hexcol(hexc), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emit:
        b.inputs["Emission Color"].default_value = (*hexcol(emit), 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


M = dict(
    concrete=mat("concrete", "#4a4640", 0.95), concrete_dk=mat("concrete_dk", "#37342f", 0.95),
    floor=mat("floor", "#5a4a38", 0.9), beam=mat("beam", "#2a2521", 0.9),
    wood=mat("wood", "#8a6a44", 0.85), wood_dk=mat("wood_dk", "#6e5336", 0.85),
    metal=mat("metal", "#7d8790", 0.5, metallic=0.6), copper=mat("copper", "#b5703a", 0.45, metallic=0.7),
    water=mat("water", "#3E7EA6", 0.1, emit="#4FB7E6", strength=0.6),
    white=mat("white", "#E8DFCB", 0.9), red=mat("red", "#C8442F", 0.8), yellow=mat("yellow", "#E0B54A", 0.8),
    blue=mat("blue", "#3E7EA6", 0.8), green=mat("green", "#5f9a72", 0.8), paper=mat("paper", "#DED3BB", 0.95),
    earth=mat("earth", "#1e1813", 1.0), rock=mat("rock", "#5a564d", 1.0), weed=mat("weed", "#4f6a3a", 0.9),
    tile=mat("tile", "#6f7a7c", 0.4), sky=mat("sky", "#5a5852", 1.0),
)


def cube(name, loc, size, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = size; o.data.materials.append(m); return o


def cyl(name, loc, r, h, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, rotation=rot, vertices=16)
    o = bpy.context.object; o.name = name; o.data.materials.append(m); return o


def sphere(name, loc, r, m):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=16, ring_count=8)
    o = bpy.context.object; o.name = name; o.data.materials.append(m); return o


# ── 소품 임포트 ──────────────────────────────────────────────
def _bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == 'MESH' for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def prop(source, x, y, z=0.0, h=0.6, rot_z=0.0, recolor=None):
    """소품을 불러와 바닥 기준(z)에 세우고 높이 h(m)로 정규화. source: 'k:barrel' 또는 'q:Can_Red'."""
    before = set(bpy.data.objects)
    kind, name = source.split(":", 1)
    if kind == "k":
        bpy.ops.import_scene.gltf(filepath=os.path.join(KENNEY, name + ".glb"))
    else:
        path = os.path.join(QUAT, name + ".blend")
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = [n for n in src.objects]
        for o in dst.objects:
            if o is not None:
                bpy.context.collection.objects.link(o)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    if not meshes:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in new: o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    # 하나의 빈 오브젝트 아래로 묶기
    bpy.ops.object.empty_add(location=(0, 0, 0)); root = bpy.context.object; root.name = "prop_" + name
    for o in new:
        if o.parent is None and o is not root:
            o.parent = root
    bpy.context.view_layer.update()
    lo, hi = _bbox(meshes)
    cur_h = max(hi.z - lo.z, 1e-4); s = h / cur_h
    root.scale = (s, s, s); bpy.context.view_layer.update()
    lo, hi = _bbox(meshes)
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    root.location = (x - cx, y - cy, z - lo.z)
    root.rotation_euler = (0, 0, rot_z)
    if recolor:
        for o in meshes:
            o.data.materials.clear(); o.data.materials.append(recolor)
    return root


# ── 방 셸 ────────────────────────────────────────────────────
def shell(kind="room"):
    wall = M["earth"] if kind == "rock" else M["concrete"]
    cube("back", (0, RD / 2, RH / 2), (RW, 0.2, RH), wall)              # 뒷벽
    cube("floor", (0, 0, -0.1), (RW, RD + 0.4, 0.2), M["earth"] if kind == "rock" else M["floor"])
    cube("ceil", (0, 0, RH + 0.15), (RW, RD + 0.4, 0.3), M["beam"] if kind == "room" else wall)
    cube("left", (-RW / 2 - 0.15, 0, RH / 2), (0.3, RD + 0.4, RH), M["concrete_dk"] if kind != "rock" else M["earth"])
    cube("right", (RW / 2 + 0.15, 0, RH / 2), (0.3, RD + 0.4, RH), M["concrete_dk"] if kind != "rock" else M["earth"])
    if kind == "room":
        # 옛 역 흔적: 벽 하단 타일 띠 + 노선색 띠
        cube("tiles", (0, RD / 2 - 0.11, 0.6), (RW - 0.02, 0.02, 1.2), M["tile"])
        for i in range(-2, 3):
            cube(f"beamv{i}", (i * 1.4, RD / 2 - 0.12, RH / 2), (0.08, 0.04, RH), M["beam"])


def lantern(color, strength=900, z=RH - 0.95, x=0.0):
    cyl("wire", (x, 0.2, RH - 0.45), 0.01, 0.9, M["beam"])
    body = cyl("lamp", (x, 0.2, z), 0.12, 0.28, M["metal"])
    sphere("bulb", (x, 0.2, z - 0.06), 0.11, mat("bulb" + color, "#FFE1A6", 0.3, emit=color, strength=14))
    bpy.ops.object.light_add(type='POINT', location=(x, 0.2, z - 0.1))
    l = bpy.context.object; l.data.color = hexcol(color); l.data.energy = strength * 3.2; l.data.shadow_soft_size = 0.5
    bpy.ops.object.light_add(type='AREA', location=(0, -RD, RH - 0.2), rotation=(math.radians(60), 0, 0))
    f = bpy.context.object; f.data.energy = 220; f.data.size = 7; f.data.color = (0.85, 0.9, 1.0)  # 차가운 약한 필
    bpy.ops.object.light_add(type='POINT', location=(x, -0.6, 0.9)); g = bpy.context.object; g.data.color = hexcol(color); g.data.energy = strength * 0.5; g.data.shadow_soft_size = 1.5  # 바닥 바운스


def shelf(x, z, w=2.2, d=0.5):
    cube("shelf", (x, RD / 2 - d / 2 - 0.15, z), (w, d, 0.06), M["wood"])
    cube("shelfb", (x, RD / 2 - d / 2 - 0.15, z - 0.05), (w, d, 0.04), M["wood_dk"])
    return z + 0.03  # 선반 윗면


def books(x0, z, n=9, w=2.0):
    cols = [M["red"], M["blue"], M["yellow"], M["green"], M["paper"], M["wood_dk"], M["white"]]
    step = w / n
    for i in range(n):
        h = 0.26 + (i * 7 % 5) * 0.03
        cube("book", (x0 - w / 2 + step * (i + 0.5), RD / 2 - 0.42, z + h / 2), (step * 0.8, 0.22, h), cols[i % len(cols)])


# ── 방 정의 ──────────────────────────────────────────────────
def room_pantry():
    shell(); lantern("#F2A93B")
    y = RD / 2 - 0.42
    for zz in (1.35, 2.35):
        t = shelf(-1.6, zz); t2 = shelf(1.6, zz)
        for i, src in enumerate(["q:Can_Red", "q:Can_Closed", "q:Can_Red", "q:Can_Open", "q:Can_Closed", "q:Can_Red"]):
            prop(src, -2.5 + i * 0.38, y, t, h=0.28)
        for i in range(5):
            prop("k:bottle", 0.9 + i * 0.36, y, t2, h=0.42 if i % 2 else 0.36)
        if zz > 2:
            for i in range(3): prop("k:box", -2.4 + i * 0.7, y - 0.05, t, h=0.45)
    prop("k:barrel", -2.3, 0.5, 0, h=1.0); prop("k:barrel-open", -1.5, 0.3, 0, h=0.9)
    prop("k:box-large", 2.2, 0.6, 0, h=0.9); prop("k:box-open", 1.3, 0.2, 0, h=0.55)
    prop("q:Backpack", 0.2, -0.2, 0, h=0.55, rot_z=0.4)
    cube("table", (0.1, 0.4, 0.75), (1.4, 0.7, 0.06), M["wood"]); cube("tleg", (-0.5, 0.4, 0.36), (0.08, 0.6, 0.72), M["wood_dk"]); cube("tleg2", (0.7, 0.4, 0.36), (0.08, 0.6, 0.72), M["wood_dk"])
    prop("q:Pot", -0.2, 0.4, 0.78, h=0.25); prop("q:Can_Open", 0.4, 0.3, 0.78, h=0.18)
    if LEVEL >= 2:
        for i in range(4): prop("k:box", -2.5 + i * 0.5, 1.0, 0.9, h=0.45)


def room_well():
    shell(); lantern("#4FB7E6", 700)
    prop("q:PropaneTank", -2.0, 0.6, 0, h=2.2, recolor=M["metal"]); prop("q:PropaneTank", -0.6, 0.8, 0, h=1.7, recolor=M["metal"])
    cyl("pipe1", (-1.3, 0.6, 1.9), 0.05, 1.4, M["copper"], rot=(0, math.radians(90), 0))
    cyl("pipe2", (0.3, 0.6, 1.4), 0.05, 1.2, M["copper"], rot=(math.radians(0), 0, 0))
    cyl("pipe3", (0.3, 0.6, 0.85), 0.05, 0.9, M["copper"], rot=(0, math.radians(90), 0))
    cube("basin", (1.0, 0.4, 0.3), (1.2, 0.8, 0.6), M["metal"]); cube("waterS", (1.0, 0.4, 0.58), (1.05, 0.65, 0.04), M["water"])
    cyl("tap", (0.55, 0.4, 0.9), 0.03, 0.5, M["copper"])
    t = shelf(2.2, 1.5, w=1.4);
    for i, s in enumerate(["q:WaterBottle_1", "q:WaterBottle_2", "q:WaterBottle_3", "q:WaterBottle_1"]): prop(s, 1.7 + i * 0.34, RD / 2 - 0.42, t, h=0.34)
    t = shelf(2.2, 2.4, w=1.4)
    for i in range(4): prop("k:bottle-large", 1.7 + i * 0.34, RD / 2 - 0.42, t, h=0.4)
    prop("k:bucket", 2.4, -0.3, 0, h=0.4); prop("k:barrel", -2.6, -0.4, 0, h=0.9, recolor=M["blue"])
    if LEVEL >= 2: prop("k:barrel", 2.6, 0.9, 0, h=0.9, recolor=M["blue"])


def room_infirmary():
    shell(); lantern("#7DE0A8", 650)
    prop("k:bedroll", -1.8, 0.2, 0, h=0.35, recolor=None); prop("k:bedroll", 0.6, 0.2, 0, h=0.35)
    cube("cab", (2.3, RD / 2 - 0.35, 1.5), (1.0, 0.4, 1.6), M["paper"]); cube("cabdoor", (2.3, RD / 2 - 0.56, 1.5), (0.9, 0.02, 1.5), M["white"])
    cube("crossv", (2.3, RD / 2 - 0.58, 1.5), (0.14, 0.02, 0.6), M["red"]); cube("crossh", (2.3, RD / 2 - 0.58, 1.5), (0.6, 0.02, 0.14), M["red"])
    prop("q:FirstAidKit", -2.5, 0.5, 0, h=0.3); prop("q:Bandages", 2.2, -0.2, 0, h=0.14); prop("q:Bandages", 1.9, 0.1, 0, h=0.14)
    t = shelf(-1.2, 2.3, w=2.0)
    for i in range(5): prop("k:bottle", -2.0 + i * 0.4, RD / 2 - 0.42, t, h=0.3 if i % 2 else 0.24, recolor=M["white"] if i % 2 else M["green"])
    prop("k:box", -0.4, 0.8, 0, h=0.4, recolor=M["white"])
    if LEVEL >= 2: prop("k:bedroll", -0.6, 0.6, 0, h=0.35)


def room_library():
    shell(); lantern("#E0B54A", 800)
    for zz in (0.5, 1.4, 2.3):
        t = shelf(-1.6, zz, w=2.4); books(-1.6, t, n=10, w=2.3)
    for zz in (1.4, 2.3):
        t = shelf(1.9, zz, w=1.6); books(1.9, t, n=7, w=1.5)
    prop("k:workbench", 1.6, -0.2, 0, h=0.9)
    cube("bluep", (1.5, -0.25, 0.92), (0.6, 0.42, 0.01), M["blue"])
    cyl("candle", (2.1, -0.3, 1.0), 0.03, 0.18, M["paper"]); sphere("flame", (2.1, -0.3, 1.12), 0.035, mat("flame", "#FFE1A6", 0.3, emit="#F2A93B", strength=12))
    for i in range(3): prop("k:box", -2.6 + i * 0.55, -0.2 + i * 0.1, 0, h=0.4)
    prop("q:Radio", 2.6, RD / 2 - 0.5, 0.0, h=0.28)
    cube("ladder1", (2.75, 1.0, 1.6), (0.05, 0.05, 3.0), M["wood"], rot=(math.radians(-8), 0, 0)); cube("ladder2", (2.45, 1.0, 1.6), (0.05, 0.05, 3.0), M["wood"], rot=(math.radians(-8), 0, 0))
    for i in range(6): cube("rung", (2.6, 1.0 + i * 0.07, 0.5 + i * 0.45), (0.3, 0.04, 0.04), M["wood_dk"])


def room_rock():
    shell("rock")
    bpy.ops.object.light_add(type='POINT', location=(0.5, -1.2, 2.2)); l = bpy.context.object; l.data.energy = 160; l.data.color = (1, .8, .55)
    for i, s in enumerate(["k:rock-a", "k:rock-b", "k:rock-c", "k:resource-stone-large", "k:rock-a", "k:resource-stone"]):
        prop(s, -2.4 + i * 0.95, 0.4 + (i % 2) * 0.5, 0, h=0.5 + (i % 3) * 0.25, rot_z=i * 0.7, recolor=M["rock"])
    for i in range(7):
        cube("rubble", (-2.6 + i * 0.85, 1.0, 0.08), (0.5, 0.35, 0.16), M["rock"], rot=(0, 0, i * 0.4))
    prop("k:tool-pickaxe", 2.3, 0.3, 0, h=1.0, rot_z=0.3)
    for i in range(5):  # 뿌리
        cyl("root", (-2.5 + i * 1.2, RD / 2 - 0.25, RH - 0.5 - i * 0.1), 0.03, 1.0 + i * 0.1, M["wood_dk"], rot=(math.radians(15 * (i % 2 * 2 - 1)), 0, 0))


def room_lot():
    # 지상: 벽 없음. 바닥 잔해 + 폐허 실루엣 + 하늘판
    cube("ground", (0, 0, -0.1), (RW + 1, RD + 2, 0.2), M["concrete_dk"])
    cube("skyplane", (0, RD / 2 + 0.6, RH / 2 + 0.5), (RW + 2, 0.1, RH + 1), M["sky"])
    for i, (x, w, h) in enumerate([(-2.6, 0.9, 2.6), (-1.5, 0.6, 1.8), (0.4, 1.2, 3.2), (1.9, 0.7, 2.2), (2.8, 0.5, 1.4)]):
        cube("ruin", (x, RD / 2 + 0.3, h / 2), (w, 0.3, h), M["concrete_dk"])
    bpy.ops.object.light_add(type='SUN', location=(0, -3, 6), rotation=(math.radians(55), math.radians(10), 0)); s = bpy.context.object; s.data.energy = 2.2; s.data.color = (1.0, 0.9, 0.78)
    for i, src in enumerate(["k:patch-grass", "k:grass", "k:patch-grass-large", "k:grass-large", "k:patch-grass"]):
        prop(src, -2.5 + i * 1.25, -0.4 + (i % 2) * 0.6, 0, h=0.25 + (i % 2) * 0.2, recolor=M["weed"])
    prop("k:fence-fortified", -2.2, 0.9, 0, h=1.3); prop("k:signpost", 2.4, 0.6, 0, h=1.6, rot_z=0.3)
    prop("k:metal-panel-screws", 0.6, 0.7, 0, h=1.1, rot_z=1.2); prop("k:box-open", 1.4, -0.4, 0, h=0.5, rot_z=0.5)
    prop("q:Trashcan", -0.6, -0.2, 0, h=0.8)


ROOMS = {"pantry": room_pantry, "well": room_well, "infirmary": room_infirmary, "library": room_library, "rock": room_rock, "lot": room_lot}


# ── 카메라 · 렌더 설정 ───────────────────────────────────────
def camera():
    bpy.ops.object.camera_add(location=(0, -12, RH / 2 + 0.15), rotation=(math.radians(90 - 4), 0, 0))
    cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = RW + 0.4; sc.camera = cam


def render(path):
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 768, 512
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.use_freestyle = True; sc.render.line_thickness = 1.1
    fs = sc.view_layers[0].freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("relic")
    ls.select_silhouette = True; ls.select_crease = True; ls.select_border = True
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("relic_ls")
    ls.linestyle.color = hexcol("#1a1714"); ls.linestyle.thickness = 1.1
    sc.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
    sc.view_settings.look = 'None'
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.06, 0.055, 0.045, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    targets = ONLY or list(ROOMS.keys())
    first = True
    for rid in targets:
        if not first:
            bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
            # 재질 재생성 (씬 리셋으로 사라짐)
            M.update(dict(
                concrete=mat("concrete", "#4a4640", 0.95), concrete_dk=mat("concrete_dk", "#37342f", 0.95),
                floor=mat("floor", "#5a4a38", 0.9), beam=mat("beam", "#2a2521", 0.9),
                wood=mat("wood", "#8a6a44", 0.85), wood_dk=mat("wood_dk", "#6e5336", 0.85),
                metal=mat("metal", "#7d8790", 0.5, metallic=0.6), copper=mat("copper", "#b5703a", 0.45, metallic=0.7),
                water=mat("water", "#3E7EA6", 0.1, emit="#4FB7E6", strength=0.6),
                white=mat("white", "#E8DFCB", 0.9), red=mat("red", "#C8442F", 0.8), yellow=mat("yellow", "#E0B54A", 0.8),
                blue=mat("blue", "#3E7EA6", 0.8), green=mat("green", "#5f9a72", 0.8), paper=mat("paper", "#DED3BB", 0.95),
                earth=mat("earth", "#1e1813", 1.0), rock=mat("rock", "#5a564d", 1.0), weed=mat("weed", "#4f6a3a", 0.9),
                tile=mat("tile", "#6f7a7c", 0.4), sky=mat("sky", "#5a5852", 1.0),
            ))
        first = False
        ROOMS[rid]()
        camera()
        out = os.path.join(OUT, f"{rid}{'' if LEVEL == 1 else '_L' + str(LEVEL)}.png")
        render(out)
        print("RENDERED", out, flush=True)
    print("ALL DONE", flush=True)
