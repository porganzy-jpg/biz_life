# -*- coding: utf-8 -*-
"""
잔해 방주 — 캐릭터 후보 쇼케이스 렌더 (여러 스타일을 같은 카메라로 나란히 비교)
blender -b --python tools/blender_charshow.py -- <out_dir> [kb|kp|qd|qc ...]

  kb  Kenney Blocky Characters (GLB, 애니메이션 내장, 18종 스킨)
  kp  Kenney Protagonists (FBX 모델 + 스킨 텍스처 + run.fbx 애니메이션)
  qd  Quaternius Animated Dinosaurs (FBX, 걷기/달리기/공격 액션)
  qc  Quaternius Ultimate Animated Characters (FBX, 다운로드 후)

같은 아이소 카메라(방위 45°, 고도 32°, 직교)로 렌더해 스타일 비교. 투명 PNG + charshow_meta.json(액션 목록).
"""
import bpy, sys, os, math, json, glob
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "art_raw/charshow")
ONLY = [a for a in argv[1:] if not a.startswith("--")]
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); A3 = os.path.join(ROOT, "assets3d")
AZ, EL = 45, 32
sc = None
meta = {}


def hexcol(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def reset():
    global sc
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene


def import_any(path):
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".glb" or ext == ".gltf":
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == 'MESH' for c in o.bound_box]
    if not pts:
        return Vector((0, 0, 0)), Vector((1, 1, 1))
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def group(objs, name):
    bpy.ops.object.empty_add(location=(0, 0, 0)); root = bpy.context.object; root.name = name
    for o in objs:
        if o.parent is None:
            o.parent = root
    return root


def normalize(root, objs, height, face_rot):
    """높이 정규화 + 바닥 z=0 + 중심 x,y=0 + 정면(+X)이 face_rot 방향."""
    bpy.context.view_layer.update()
    lo, hi = bbox(objs); s = height / max(hi.z - lo.z, 1e-4)
    root.scale = (s, s, s); bpy.context.view_layer.update()
    lo, hi = bbox(objs)
    root.location = (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)
    root.rotation_euler = (0, 0, face_rot)
    bpy.context.view_layer.update()


def assign_action(arm, act):
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    try:
        if hasattr(arm.animation_data, "action_slot") and getattr(act, "slots", None) and len(act.slots):
            arm.animation_data.action_slot = act.slots[0]
    except Exception as e:
        print("slot warn", e)


def set_action_frame(objs, prefer=("walk", "run", "idle"), t=0.3):
    """아마추어에 선호 액션을 붙이고 구간의 t 지점 프레임으로."""
    arms = [o for o in objs if o.type == 'ARMATURE']
    acts = list(bpy.data.actions)
    names = [a.name for a in acts]
    chosen = None
    for p in prefer:
        for a in acts:
            if p in a.name.lower():
                chosen = a; break
        if chosen:
            break
    if not chosen and acts:
        chosen = acts[0]
    if arms and chosen:
        arm = arms[0]
        assign_action(arm, chosen)
        f0, f1 = chosen.frame_range
        sc.frame_set(int(f0 + (f1 - f0) * t))
    return names, (chosen.name if chosen else None)


def camera(ortho):
    az, el = math.radians(AZ), math.radians(EL); d = 30.0
    look = Vector((0, 0, ortho * 0.28))
    loc = Vector((-math.cos(el) * math.sin(az) * d, -math.cos(el) * math.cos(az) * d, math.sin(el) * d)) + look
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler(); sc.camera = cam; return cam


def lights():
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 5), rotation=(math.radians(45), math.radians(20), math.radians(-40))); s = bpy.context.object; s.data.energy = 3.0; s.data.color = (1.0, 0.92, 0.8)
    bpy.ops.object.light_add(type='AREA', location=(-4, -4, 4), rotation=(math.radians(50), 0, math.radians(-45))); f = bpy.context.object; f.data.energy = 300; f.data.size = 8; f.data.color = (0.85, 0.9, 1.0)


def render(path, res=320):
    sc.render.engine = 'BLENDER_EEVEE'; sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = True; sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.render.use_freestyle = True; sc.render.line_thickness = 1.2
    fs = sc.view_layers[0].freestyle_settings; ls = fs.linesets[0] if fs.linesets else fs.linesets.new("c")
    ls.select_silhouette = True; ls.select_crease = True; ls.select_border = True
    if ls.linestyle is None: ls.linestyle = bpy.data.linestyles.new("cls")
    ls.linestyle.color = hexcol("#1a1714"); ls.linestyle.thickness = 1.2
    names = [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items]
    sc.view_settings.view_transform = 'AgX' if 'AgX' in names else 'Filmic'; sc.view_settings.exposure = 0.5
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)


def shot(tag, objs, height=1.8, ortho=2.8, face=math.pi, res=320, prefer=("walk", "run", "idle"), t=0.3):
    root = group(objs, tag)
    acts, chosen = set_action_frame(objs, prefer, t) if prefer else ([a.name for a in bpy.data.actions], 'preassigned')
    normalize(root, objs, height, face)
    camera(ortho); lights()
    out = os.path.join(OUT, f"{tag}.png"); render(out, res)
    meta[tag] = {"actions": acts, "used": chosen, "height": height}
    print("RENDERED", out, "actions:", acts[:6], flush=True)


def do_kb():
    files = sorted(glob.glob(os.path.join(A3, "kenney_blocky", "Models", "GLB format", "character-*.glb")))
    for f in files[:6]:
        reset(); objs = import_any(f); shot("kb_" + os.path.basename(f).split(".")[0], objs, height=1.7, ortho=2.8)


def do_kp():
    model = os.path.join(A3, "kenney_prot", "Model", "characterMedium.fbx")
    anim = os.path.join(A3, "kenney_prot", "Animations", "run.fbx")
    for skin in ("skaterFemaleA", "criminalMaleA", "cyborgFemaleA", "skaterMaleA"):
        reset(); objs = import_any(model)
        # 스킨 텍스처: 새 재질로 전면 교체 (FBX 재질은 노드가 없어 흰색으로 나옴)
        img = bpy.data.images.load(os.path.join(A3, "kenney_prot", "Skins", skin + ".png"))
        m = bpy.data.materials.new("skin_" + skin); m.use_nodes = True
        nt = m.node_tree; bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'); bsdf.inputs["Roughness"].default_value = 0.85
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.interpolation = 'Closest'; nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        for o in objs:
            if o.type == 'MESH':
                o.data.materials.clear(); o.data.materials.append(m)
        # 애니메이션: run.fbx의 'Run' 액션을 모델 아마추어에
        before = set(bpy.data.actions); anim_objs = import_any(anim)
        new_acts = [a for a in bpy.data.actions if a not in before]
        for o in anim_objs: bpy.data.objects.remove(o, do_unlink=True)
        run = next((a for a in new_acts if 'run' in a.name.lower()), new_acts[0] if new_acts else None)
        arms = [o for o in objs if o.type == 'ARMATURE']
        if arms and run:
            arm = arms[0]; assign_action(arm, run)
            f0, f1 = run.frame_range; sc.frame_set(int(f0 + (f1 - f0) * 0.3))
        shot("kp_" + skin, objs, height=1.8, ortho=2.8, prefer=(), t=0.3)


def do_qd():
    base = glob.glob(os.path.join(A3, "quaternius_dinos", "*", "FBX"))
    if not base: print("no dino fbx"); return
    for name, h in (("Trex", 5.0), ("Velociraptor", 2.0), ("Triceratops", 3.0), ("Stegosaurus", 3.2)):
        f = os.path.join(base[0], name + ".fbx")
        if not os.path.exists(f): continue
        reset(); objs = import_any(f)
        col = {"Trex": "#6b7a4a", "Velociraptor": "#8a6a45", "Triceratops": "#6e7f8a", "Stegosaurus": "#7a5a3a"}[name]
        m = bpy.data.materials.new("dino_" + name); m.use_nodes = True
        bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); bsdf.inputs["Base Color"].default_value = (*hexcol(col), 1); bsdf.inputs["Roughness"].default_value = 0.9
        for o in objs:
            if o.type == 'MESH':
                o.data.materials.clear(); o.data.materials.append(m)
        shot("qd_" + name, objs, height=h, ortho=h * 1.9, face=math.pi, res=420, prefer=("walk", "run", "idle"), t=0.35)


def do_qc():
    """Quaternius Ultimate Animated Characters: .blend에서 오브젝트·액션을 append."""
    base = glob.glob(os.path.join(A3, "quaternius_chars", "*", "Blends"))
    if not base: print("no qc blends"); return
    picks = ["Chef_Male", "Doctor_Female_Young", "BlueSoldier_Male", "Casual_Female", "Cowboy_Male", "Casual2_Male"]
    for name in picks:
        f = os.path.join(base[0], name + ".blend")
        if not os.path.exists(f): print("missing", name); continue
        reset()
        before = set(bpy.data.objects)
        with bpy.data.libraries.load(f, link=False) as (src, dst):
            dst.objects = [n for n in src.objects]; dst.actions = [n for n in src.actions]
        for o in dst.objects:
            if o is not None and o.name not in bpy.context.scene.objects:
                try: bpy.context.collection.objects.link(o)
                except Exception: pass
        objs = [o for o in bpy.data.objects if o not in before and o.type in ('MESH', 'ARMATURE', 'EMPTY')]
        # 카메라·라이트가 섞여 왔으면 제거
        for o in list(bpy.data.objects):
            if o.type in ('CAMERA', 'LIGHT') and o not in before:
                bpy.data.objects.remove(o, do_unlink=True)
        # 원본 Skin 재질이 검정(0.01)으로 저장되어 있어 살색으로 교체
        for o in objs:
            if o.type == 'MESH':
                for m in o.data.materials:
                    if m and m.name.lower().startswith("skin") and m.use_nodes:
                        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                        if b: b.inputs["Base Color"].default_value = (*hexcol("#e8c4a0"), 1)
        print("QC", name, "objs", [(o.name, o.type) for o in objs][:4], flush=True)
        # Quaternius 기본 정면은 -Y → 카메라 왼쪽 아래(dl)를 보게 하려면 -90°
        shot("qc_" + name, objs, height=1.8, ortho=2.8, face=math.radians(-90), prefer=("walk", "run", "idle"), t=0.3)
        if name == "Chef_Male":
            # 물건 집는 모션 (음식 가져오기) 데모
            arms = [o for o in objs if o.type == 'ARMATURE']; pick = next((a for a in bpy.data.actions if a.name.lower() == "pickup"), None)
            if arms and pick:
                assign_action(arms[0], pick); f0, f1 = pick.frame_range; sc.frame_set(int(f0 + (f1 - f0) * 0.55))
                for o in list(bpy.data.objects):
                    if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o, do_unlink=True)
                camera(2.8); lights(); out = os.path.join(OUT, "qc_Chef_PickUp.png"); render(out, 320); print("RENDERED", out, flush=True)


def do_orient():
    base = glob.glob(os.path.join(A3, "quaternius_chars", "*", "Blends"))[0]
    for deg in (0, 90, 180, 270):
        reset(); before = set(bpy.data.objects)
        with bpy.data.libraries.load(os.path.join(base, "Chef_Male.blend"), link=False) as (src, dst):
            dst.objects = [n for n in src.objects]; dst.actions = [n for n in src.actions]
        for o in dst.objects:
            if o is not None:
                try: bpy.context.collection.objects.link(o)
                except Exception: pass
        objs = [o for o in bpy.data.objects if o not in before and o.type in ('MESH', 'ARMATURE')]
        shot(f"orient_{deg}", objs, height=1.8, ortho=2.8, face=math.radians(deg), prefer=("walk",), t=0.3)


if __name__ == "__main__":
    todo = ONLY or ["kb", "kp", "qd"]
    for t in todo:
        try:
            {"kb": do_kb, "kp": do_kp, "qd": do_qd, "qc": do_qc, "orient": do_orient}[t]()
        except Exception as e:
            print("FAILED", t, repr(e), flush=True)
    mp = os.path.join(OUT, "charshow_meta.json"); old = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    old.update(meta); json.dump(old, open(mp, "w", encoding="utf-8"), indent=1, ensure_ascii=False); print("ALL DONE", flush=True)
