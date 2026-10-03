# -*- coding: utf-8 -*-
"""러프 스토리보드 — shots.json 의 각 컷을 Blender 로 블록아웃해 한 장씩 렌더한다.

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P mv/blender_storyboard.py
결과: mv/board/S01.png ...  (캡션은 make_board.py 가 붙인다)

캐릭터는 기본 도형으로 만든 대역이다. 화자는 색이 있고, 세션은 진회색 실루엣 —
흰 무대 위에서 '혼자 → 꽉 참'이 한눈에 읽히도록.
"""
import bpy, bmesh, json, math, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "shots.json"), encoding="utf-8"))
OUT = os.path.join(HERE, "board"); os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ── 재질 ─────────────────────────────────────────────
def mat(name, rgb, rough=0.6, metal=0.0, emit=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m

M = {k: mat(k, *v) for k, v in {
    "stage": ((0.92, 0.92, 0.92), 0.8), "skin": ((0.93, 0.74, 0.62), 0.5),
    "hair": ((0.06, 0.05, 0.05), 0.5), "sweater": ((0.62, 0.63, 0.66), 0.9),
    "pants": ((0.10, 0.14, 0.26), 0.8), "shoe": ((0.95, 0.95, 0.95), 0.5),
    "frame": ((0.35, 0.12, 0.06), 0.3), "metal": ((0.15, 0.15, 0.15), 0.25, 0.9),
    "member": ((0.13, 0.13, 0.14), 0.7), "inst": ((0.22, 0.20, 0.19), 0.5),
    "brass": ((0.85, 0.62, 0.20), 0.25, 1.0), "wood": ((0.45, 0.22, 0.08), 0.4),
}.items()}

def link(o, m):
    o.data.materials.append(M[m]); return o

def prim(kind, loc, scale=(1, 1, 1), rot=(0, 0, 0), m="member", parent=None, **kw):
    getattr(bpy.ops.mesh, f"primitive_{kind}_add")(location=loc, rotation=rot, **kw)
    o = bpy.context.object; o.scale = scale
    if kind in ("uv_sphere", "cylinder", "torus", "cone"):
        bpy.ops.object.shade_smooth()
    link(o, m)
    if parent: o.parent = parent
    return o

# ── 무대: 바닥과 뒷벽이 곡면으로 이어진 사이클로라마 ─────────
def cyclorama():
    prof = [(y, 0.0) for y in range(-30, 12, 2)]
    R = 6.0
    for i in range(1, 12):
        a = i / 12 * math.pi / 2
        prof.append((12 + R * math.sin(a), R - R * math.cos(a)))
    prof += [(12 + R, z) for z in (R + 2, R + 8, 26)]
    me = bpy.data.meshes.new("cyc"); bm = bmesh.new()
    rows = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in (-90, 90)]
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("cyc", me); sc.collection.objects.link(o)
    for p in me.polygons: p.use_smooth = True
    link(o, "stage")
cyclorama()

# ── 사람 대역 ────────────────────────────────────────
def figure(name, x, y, face_to=(0, -12), body="member", seated=False, pose="stand", hero=False):
    root = bpy.data.objects.new(name, None); sc.collection.objects.link(root)
    root.location = (x, y, 0)
    root.rotation_euler[2] = math.atan2(face_to[0] - x, -(face_to[1] - y)) if not hero else 0
    dz = -0.35 if seated else 0
    skin = "skin" if hero else body
    legs = "pants" if hero else body
    top = "sweater" if hero else body
    for sx in (-0.13, 0.13):
        prim("cylinder", (sx, 0, 0.35 + dz / 2), (0.11, 0.11, 0.35 + dz / 2), m=legs, parent=root)
        prim("uv_sphere", (sx, -0.05, 0.06), (0.12, 0.18, 0.07), m="shoe" if hero else body, parent=root)
    prim("uv_sphere", (0, 0, 0.98 + dz), (0.30, 0.22, 0.36), m=top, parent=root)     # 몸통
    prim("uv_sphere", (0, 0, 1.58 + dz), (0.34, 0.32, 0.34), m=skin, parent=root)    # 큰 머리 (2.5등신)
    prim("uv_sphere", (0, 0.04, 1.72 + dz), (0.36, 0.34, 0.26), m="hair" if hero else body, parent=root)
    if hero:
        for sx in (-0.12, 0.12):
            prim("torus", (sx, -0.32, 1.57), (1, 1, 1), (math.pi / 2, 0, 0), m="frame",
                 parent=root, major_radius=0.09, minor_radius=0.012)
    # 팔
    arm = {"stand": (0.35, 0.2), "shy": (0.15, 1.1), "open": (2.2, 0.3), "bow": (0.2, 0.4),
           "play": (0.6, 0.9)}[pose]
    for side in (-1, 1):
        o = prim("cylinder", (side * 0.33, -0.05, 1.05 + dz), (0.08, 0.08, 0.30), m=top, parent=root)
        o.rotation_euler = (arm[1], side * arm[0], 0)
    if pose == "bow":
        root.rotation_euler[0] = 0.35
    return root

def mic_stand(x, y, h=1.5):
    prim("cylinder", (x, y, 0.02), (0.22, 0.22, 0.02), m="metal")
    prim("cylinder", (x, y, h / 2), (0.018, 0.018, h / 2), m="metal")
    prim("uv_sphere", (x, y + 0.05, h + 0.05), (0.06, 0.06, 0.09), m="metal")

def instrument(kind, root):
    p = root
    if kind == "drums":
        prim("cylinder", (0, -0.9, 0.4), (0.4, 0.4, 0.22), (math.pi / 2, 0, 0), m="inst", parent=p)
        for sx in (-0.5, 0.5):
            prim("cylinder", (sx, -0.6, 0.75), (0.2, 0.2, 0.12), m="inst", parent=p)
            prim("cylinder", (sx * 1.7, -0.6, 1.3), (0.32, 0.32, 0.01), m="brass", parent=p)
    elif kind == "drums_small":
        for sx in (-0.25, 0.25):
            prim("cylinder", (sx, -0.5, 0.45), (0.17, 0.17, 0.45), m="wood", parent=p)
    elif kind in ("bass", "guitar"):
        prim("uv_sphere", (0.05, -0.28, 0.95), (0.26, 0.08, 0.32), (0, 0.5, 0), m="wood", parent=p)
        prim("cube", (-0.3, -0.3, 1.25), (0.04, 0.03, 0.42 if kind == "bass" else 0.32), (0, 0.9, 0), m="inst", parent=p)
    elif kind == "keys":
        prim("cube", (0, -0.6, 0.9), (0.6, 0.2, 0.04), m="inst", parent=p)
        for sx in (-0.5, 0.5):
            prim("cube", (sx, -0.6, 0.45), (0.03, 0.15, 0.45), m="metal", parent=p)
    elif kind == "strings":
        prim("uv_sphere", (0, -0.45, 0.55), (0.24, 0.12, 0.42), m="wood", parent=p)
        prim("cube", (0, -0.45, 1.1), (0.03, 0.03, 0.3), m="inst", parent=p)
    elif kind == "brass":
        prim("cone", (0, -0.6, 1.55), (1, 1, 1), (math.pi / 2, 0, 0), m="brass", parent=p,
             radius1=0.14, radius2=0.03, depth=0.55)
    elif kind == "chorus":
        prim("uv_sphere", (0.1, -0.35, 1.45), (0.04, 0.04, 0.06), m="metal", parent=p)

# ── 배치 ─────────────────────────────────────────────
mic_stand(0, -0.55)
members = {}
for mb in CFG["members"]:
    seated = mb["kind"] in ("drums", "strings", "drums_small", "keys") and mb["kind"] != "keys"
    pose = "play" if mb["kind"] not in ("chorus",) else "stand"
    r = figure(mb["id"], *mb["pos"], seated=seated, pose=pose)
    instrument(mb["kind"], r)
    members[mb["id"]] = (mb, r)

def set_visible(root, vis):
    for o in [root] + list(root.children_recursive):
        o.hide_render = not vis

# ── 조명 ─────────────────────────────────────────────
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bpy.ops.object.light_add(type="AREA", location=(0, -8, 12)); key = bpy.context.object
key.data.energy = 3500; key.data.size = 14; key.rotation_euler = (math.radians(35), 0, 0)
bpy.ops.object.light_add(type="SUN", location=(0, 0, 10)); sun = bpy.context.object
sun.data.energy = 2.2; sun.data.angle = math.radians(8); sun.rotation_euler = (math.radians(30), math.radians(-18), 0)
bpy.ops.object.light_add(type="SPOT", location=(0, -0.3, 9)); spot = bpy.context.object
spot.data.spot_size = math.radians(16); spot.data.spot_blend = 0.35; spot.data.energy = 6000

# ── 렌더 설정 ────────────────────────────────────────
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = eng; break
    except TypeError: pass
sc.render.resolution_x, sc.render.resolution_y = 960, 540
try: sc.eevee.taa_render_samples = 24
except AttributeError: pass
sc.view_settings.view_transform = "AgX"
try: sc.view_settings.look = "AgX - Medium High Contrast"
except TypeError: pass

cam_data = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam); sc.camera = cam

POSE = {"S01": "stand", "S02": "shy", "S03": "shy", "S06": "open", "S12": "open", "S13": "bow"}
hero = None
for sh in CFG["shots"]:
    t = sh["still_t"]
    # 화자는 컷마다 포즈가 달라 새로 만든다
    if hero:
        for o in list(hero.children_recursive) + [hero]: bpy.data.objects.remove(o, do_unlink=True)
    hx = -3.2 if sh.get("walk") else (0, 0)[0]
    hy = -2.2 if sh["id"] == "S10" else 0          # 큰 후렴: 무대 앞끝까지 걸어 나옴
    hero = figure("hero", hx, hy, hero=True, pose=POSE.get(sh["id"], "stand"))
    if sh.get("walk"): hero.rotation_euler[2] = math.radians(-70)

    for mb, r in members.values():
        set_visible(r, mb["enter"] <= t and not sh.get("dark"))
    dim = sh["id"] in ("S07", "S11")
    dark = sh.get("dark", False)
    bg.inputs["Color"].default_value = (0, 0, 0, 1) if dark else (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = 0.0 if dark else (0.15 if dim else 0.55)
    key.data.energy = 0 if dark else (600 if dim else 3500)
    sun.data.energy = 0 if (dark or dim) else 2.2
    spot.data.energy = 6000 if (dark or dim) else 0
    spot.location = (hx, hy - 3.2, 8.5)
    spot.rotation_euler = (Vector((hx, hy, 1.2)) - spot.location).to_track_quat("-Z", "Y").to_euler()

    c = sh["cam"]
    cam.location = c["pos"]; cam_data.lens = c["lens"]
    d = Vector(c["look"]) - Vector(c["pos"])
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"{sh['id']}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", sh["id"], flush=True)
