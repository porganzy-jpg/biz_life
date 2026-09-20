# -*- coding: utf-8 -*-
"""
잔해 방주 — 치비 주민 스프라이트 (역할 8종 × 정면좌/후면좌 × 걷기 2프레임)
blender -b --python tools/blender_chars.py -- <out_dir> [role ...]

레퍼런스(Mini Survival 등)의 치비 비율: 머리 크게, 몸 짧게. 방 타일과 같은 아이소 카메라(45°/45°).
출력: <role>_<dl|ul>_<a|b>.png (투명, 256px) + chars_meta.json(발 위치 픽셀).
"""
import bpy, sys, os, math, json
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "art_raw/chars")
ONLY = [a for a in argv[1:] if not a.startswith("--")]
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ROLES = json.load(open(os.path.join(ROOT, "data", "roles.json"), encoding="utf-8"))

RES, ORTHO, AZ, EL = 256, 2.4, 45, 32   # 캐릭터는 고도를 낮춰 얼굴이 보이게
sc = None


def hexcol(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def mat(name, hexc, rough=0.85, emit=None, strength=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hexcol(hexc), 1); b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*hexcol(emit), 1); b.inputs["Emission Strength"].default_value = strength
    return m


def cube(loc, size, m, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot); o = bpy.context.object; o.scale = size; o.data.materials.append(m)
    if parent: o.parent = parent
    return o


def sphere(loc, r, m, parent=None, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=20, ring_count=12); o = bpy.context.object; o.scale = scale; o.data.materials.append(m)
    if parent: o.parent = parent
    return o


def cyl(loc, r, h, m, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, rotation=rot, vertices=16); o = bpy.context.object; o.data.materials.append(m)
    if parent: o.parent = parent
    return o


def build(role, frame):
    """치비: 앞은 +X. frame 'a' = 다리 벌림, 'b' = 모음."""
    v = ROLES[role]["visual"]; small = v.get("small", False); k = 0.78 if small else 1.0
    skin = mat("skin", "#e8c9a8"); body = mat("body", v["body"]); acc = mat("acc", v["accent"]); dark = mat("dark", "#2B2A28"); hair = mat("hair", "#3a2a22"); white = mat("white", "#E8DFCB")
    bpy.ops.object.empty_add(location=(0, 0, 0)); root = bpy.context.object; root.name = "char"
    leg_h = 0.34 * k; body_h = 0.5 * k; head_r = 0.33 * k
    # 다리 (걷기: a = 앞뒤로 벌림)
    off = 0.14 * k if frame == 'a' else 0.0
    cube((off, 0.11 * k, leg_h / 2), (0.16 * k, 0.16 * k, leg_h), dark, parent=root)
    cube((-off, -0.11 * k, leg_h / 2), (0.16 * k, 0.16 * k, leg_h), dark, parent=root)
    cube((off + 0.04 * k, 0.11 * k, 0.05 * k), (0.24 * k, 0.17 * k, 0.1 * k), dark, parent=root)   # 신발
    cube((-off + 0.04 * k, -0.11 * k, 0.05 * k), (0.24 * k, 0.17 * k, 0.1 * k), dark, parent=root)
    # 몸통 (살짝 사다리꼴)
    torso = sphere((0, 0, leg_h + body_h / 2), 0.3 * k, body, parent=root, scale=(0.75, 0.85, body_h / (0.6 * k)))
    cube((0.19 * k, 0, leg_h + body_h * 0.45), (0.02, 0.3 * k, body_h * 0.6), acc, parent=root)          # 앞판 포인트
    # 팔
    arm_sw = 0.12 * k if frame == 'a' else 0.0
    cube((arm_sw, 0.28 * k, leg_h + body_h * 0.55), (0.12 * k, 0.11 * k, body_h * 0.75), body, parent=root, rot=(0, math.radians(-15 if frame == 'a' else 0), 0))
    cube((-arm_sw, -0.28 * k, leg_h + body_h * 0.55), (0.12 * k, 0.11 * k, body_h * 0.75), body, parent=root, rot=(0, math.radians(15 if frame == 'a' else 0), 0))
    sphere((arm_sw + 0.02, 0.28 * k, leg_h + body_h * 0.18), 0.07 * k, skin, parent=root); sphere((-arm_sw + 0.02, -0.28 * k, leg_h + body_h * 0.18), 0.07 * k, skin, parent=root)
    # 머리 (크게)
    hz = leg_h + body_h + head_r * 0.95
    sphere((0, 0, hz), head_r, skin, parent=root, scale=(1, 1, 1.05))
    sphere((-0.1 * k, 0, hz + 0.09 * k), head_r * 0.98, hair, parent=root, scale=(0.9, 1.0, 0.85))            # 머리카락(뒤·위)
    sphere((head_r * 0.86, 0.12 * k, hz + 0.02), 0.045 * k, dark, parent=root)                                   # 눈(둥글게, 크게)
    sphere((head_r * 0.86, -0.12 * k, hz + 0.02), 0.045 * k, dark, parent=root)
    sphere((head_r * 0.8, 0.2 * k, hz - 0.08 * k), 0.05 * k, mat("blush", "#d98a7a"), parent=root, scale=(0.5, 1, 0.7))
    sphere((head_r * 0.8, -0.2 * k, hz - 0.08 * k), 0.05 * k, mat("blush2", "#d98a7a"), parent=root, scale=(0.5, 1, 0.7))
    cyl((0, 0, 0.005), 0.3 * k, 0.01, mat("shadow", "#0a0908"), parent=root)                                     # 발밑 그림자
    # 역할 시그니처
    p = v["prop"]
    if "hood" in v and v["hood"]:
        sphere((-0.16 * k, 0, hz + 0.04), head_r * 1.08, body, parent=root, scale=(0.8, 1.05, 1.0))   # 뒤로 젖힌 후드
    if p == "backpack_binoculars":
        cube((-0.3 * k, 0, leg_h + body_h * 0.55), (0.2 * k, 0.36 * k, body_h * 0.8), mat("bag", "#6e5336"), parent=root)
        cyl((head_r * 0.9, 0.07 * k, hz), 0.05 * k, 0.12 * k, dark, rot=(0, math.radians(90), 0), parent=root); cyl((head_r * 0.9, -0.07 * k, hz), 0.05 * k, 0.12 * k, dark, rot=(0, math.radians(90), 0), parent=root)
    elif p == "pot_apron":
        cube((0.2 * k, 0, leg_h + body_h * 0.35), (0.03, 0.34 * k, body_h * 0.7), white, parent=root)
        cyl((0.3 * k, 0.3 * k, leg_h + body_h * 0.2), 0.12 * k, 0.12 * k, mat("pot", "#4A463F"), parent=root)
        cube((0, 0, hz + head_r * 0.95), (0.4 * k, 0.4 * k, 0.08), white, parent=root)  # 두건
    elif p == "medic_bag_armband":
        cube((0.1 * k, 0.33 * k, leg_h + body_h * 0.55), (0.14 * k, 0.05, 0.12 * k), acc, parent=root)          # 완장
        cube((0.1 * k, 0.36 * k, leg_h + body_h * 0.55), (0.06 * k, 0.02, 0.02), white, parent=root); cube((0.1 * k, 0.36 * k, leg_h + body_h * 0.55), (0.02, 0.02, 0.06 * k), white, parent=root)
        cube((0.22 * k, -0.3 * k, leg_h + body_h * 0.15), (0.22 * k, 0.12 * k, 0.16 * k), mat("bag2", "#5f9a72"), parent=root)
    elif p == "goggles_toolbelt_wrench":
        cube((head_r * 0.85, 0, hz + head_r * 0.45), (0.06, 0.34 * k, 0.09 * k), acc, parent=root)              # 고글
        cube((0, 0, leg_h + 0.06 * k), (0.4 * k, 0.48 * k, 0.07 * k), mat("belt", "#8a6a44"), parent=root)
        cyl((0.3 * k, -0.3 * k, leg_h + body_h * 0.2), 0.025 * k, 0.32 * k, mat("wr", "#7d8790"), rot=(0, math.radians(25), 0), parent=root)
    elif p == "straw_hat_watering_can":
        cyl((0, 0, hz + head_r * 0.8), head_r * 1.5, 0.04, mat("straw", "#c9a75a"), parent=root); cyl((0, 0, hz + head_r * 0.95), head_r * 0.85, 0.22 * k, mat("straw2", "#c9a75a"), parent=root)
        cube((0.3 * k, 0.3 * k, leg_h + body_h * 0.15), (0.18 * k, 0.14 * k, 0.16 * k), acc, parent=root); cyl((0.42 * k, 0.3 * k, leg_h + body_h * 0.2), 0.02, 0.14 * k, acc, rot=(0, math.radians(70), 0), parent=root)
    elif p == "glasses_book":
        cube((head_r * 0.95, 0, hz + 0.02), (0.02, 0.32 * k, 0.09 * k), dark, parent=root)                      # 안경
        cube((0.28 * k, -0.3 * k, leg_h + body_h * 0.3), (0.16 * k, 0.05, 0.22 * k), acc, parent=root)          # 책
    elif p == "coat_hat_scarf":
        cube((0, 0, leg_h + body_h * 0.1), (0.4 * k, 0.48 * k, body_h * 0.5), body, parent=root)                # 코트 자락
        cyl((0, 0, hz + head_r * 0.9), head_r * 1.15, 0.04, dark, parent=root); cyl((0, 0, hz + head_r * 1.1), head_r * 0.7, 0.3 * k, dark, parent=root)  # 모자
        cyl((0, 0, leg_h + body_h * 0.98), 0.2 * k, 0.1 * k, mat("scarf", "#C8442F"), parent=root)
    elif p == "raincoat_small":
        sphere((-0.15 * k, 0, hz + 0.05), head_r * 1.08, body, parent=root, scale=(0.8, 1.05, 1.0))            # 우비 후드(뒤)
        cube((0, 0, leg_h + body_h * 0.2), (0.42 * k, 0.5 * k, body_h * 0.7), body, parent=root)
    return root


def camera():
    az, el = math.radians(AZ), math.radians(EL); d = 20.0
    loc = Vector((-math.cos(el) * math.sin(az) * d, -math.cos(el) * math.cos(az) * d, math.sin(el) * d)) + Vector((0, 0, 0.7))
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = ORTHO
    cam.rotation_euler = (Vector((0, 0, 0.7)) - loc).to_track_quat('-Z', 'Y').to_euler(); sc.camera = cam; return cam


def lights():
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 5), rotation=(math.radians(45), math.radians(20), math.radians(-40))); s = bpy.context.object; s.data.energy = 3.0; s.data.color = (1.0, 0.92, 0.8)
    bpy.ops.object.light_add(type='AREA', location=(-4, -4, 4), rotation=(math.radians(50), 0, math.radians(-45))); f = bpy.context.object; f.data.energy = 300; f.data.size = 8; f.data.color = (0.85, 0.9, 1.0)


def render(path):
    sc.render.engine = 'BLENDER_EEVEE'; sc.render.resolution_x = sc.render.resolution_y = RES
    sc.render.film_transparent = True; sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.render.use_freestyle = True; sc.render.line_thickness = 1.3
    fs = sc.view_layers[0].freestyle_settings; ls = fs.linesets[0] if fs.linesets else fs.linesets.new("c")
    ls.select_silhouette = True; ls.select_crease = True; ls.select_border = True
    if ls.linestyle is None: ls.linestyle = bpy.data.linestyles.new("cls")
    ls.linestyle.color = hexcol("#1a1714"); ls.linestyle.thickness = 1.3
    names = [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items]
    sc.view_settings.view_transform = 'AgX' if 'AgX' in names else 'Filmic'; sc.view_settings.exposure = 0.5
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    roles = ONLY or [r for r in ROLES if not r.startswith("_")]
    meta = {}
    for role in roles:
        for facing, rot in (("dl", math.pi), ("ul", math.pi / 2)):      # dl: -X 방향(카메라 쪽 왼쪽), ul: +Y 방향(뒷모습)
            for frame in ("a", "b"):
                bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
                root = build(role, frame); root.rotation_euler = (0, 0, rot)
                cam = camera(); lights()
                out = os.path.join(OUT, f"{role}_{facing}_{frame}.png"); render(out)
                foot = world_to_camera_view(sc, cam, Vector((0, 0, 0))); top = world_to_camera_view(sc, cam, Vector((0, 0, 1.6)))
                meta[f"{role}_{facing}"] = {"foot": [round(foot.x * RES, 1), round((1 - foot.y) * RES, 1)], "res": RES, "ortho": ORTHO}
                print("RENDERED", out, flush=True)
    mp = os.path.join(OUT, "chars_meta.json"); old = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    old.update(meta); json.dump(old, open(mp, "w", encoding="utf-8"), indent=1); print("ALL DONE", flush=True)
