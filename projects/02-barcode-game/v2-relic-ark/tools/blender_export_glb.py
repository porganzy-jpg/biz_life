# -*- coding: utf-8 -*-
"""
잔해 방주 — 실시간 2.5D(Three.js)용 GLB 내보내기
blender -b --python tools/blender_export_glb.py -- rooms [hall pantry ...]
blender -b --python tools/blender_export_glb.py -- chars [Chef_Male Doctor_Female_Young ...]

rooms: blender_iso.py의 방 정의를 그대로 빌드해 static/models/rooms/<id>.glb (랜턴 포인트라이트 포함, KHR_lights_punctual)
chars: Quaternius .blend에서 캐릭터+액션(Idle/Walk/Run/PickUp…)을 append 후 static/models/chars/<name>.glb (애니메이션 포함)
"""
import bpy, sys, os, glob, importlib.util, math

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "rooms"
ONLY = argv[1:]
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT_ROOMS = os.path.join(ROOT, "static", "models", "rooms"); OUT_CHARS = os.path.join(ROOT, "static", "models", "chars")
os.makedirs(OUT_ROOMS, exist_ok=True); os.makedirs(OUT_CHARS, exist_ok=True)


def export(path, animations=False):
    # 카메라 제외, 라이트 포함. 트랜스폼 적용. Y-up 변환은 기본.
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action='SELECT')
    kw = dict(filepath=path, export_format='GLB', export_lights=True, export_cameras=False, export_apply=True,
              use_selection=False, export_animations=animations, export_yup=True)
    if animations:
        kw.update(export_animation_mode='ACTIONS', export_nla_strips=False, export_frame_range=False, export_force_sampling=True)
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        # 구버전/신버전 인자 차이 대응
        kw.pop('export_animation_mode', None); kw.pop('export_nla_strips', None); kw.pop('export_frame_range', None)
        bpy.ops.export_scene.gltf(**kw)
    print("EXPORTED", path, os.path.getsize(path) // 1024, "KB", flush=True)


def _has_texture(m):
    return bool(m and m.use_nodes and any(n.type == 'TEX_IMAGE' for n in m.node_tree.nodes))


def join_static_meshes():
    """정적 방의 메시를 둘로 합친다: 텍스처 있는 CC0 소품 / 단색 원시도형.
    - 큐브 수백 개가 각각 노드·액세서가 되는 낭비 제거
    - 단색 쪽은 UV·버텍스컬러가 필요 없으므로 버린다(GLB의 20~25%)"""
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name in bpy.context.view_layer.objects]
    if len(meshes) < 2:
        return
    tex = [o for o in meshes if any(_has_texture(m) for m in o.data.materials)]
    flat = [o for o in meshes if o not in tex]
    for group, strip in ((flat, True), (tex, False)):
        if not group:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        for o in group:
            o.select_set(True)
        bpy.context.view_layer.objects.active = group[0]
        try:
            if len(group) > 1:
                bpy.ops.object.join()
        except Exception as e:
            print("JOIN SKIPPED", e, flush=True); continue
        ob = bpy.context.view_layer.objects.active
        if strip and ob and ob.type == 'MESH':
            while ob.data.uv_layers:
                ob.data.uv_layers.remove(ob.data.uv_layers[0])
            try:
                for a in list(ob.data.color_attributes):
                    ob.data.color_attributes.remove(a)
            except Exception:
                pass
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY' and not o.children:
            bpy.data.objects.remove(o, do_unlink=True)
    print("JOINED", len(flat), "flat +", len(tex), "textured", flush=True)


def load_iso_module():
    spec = importlib.util.spec_from_file_location("blender_iso", os.path.join(HERE, "blender_iso.py"))
    m = importlib.util.module_from_spec(spec)
    sys.argv = [sys.argv[0], "--", os.path.join(ROOT, "art_raw", "iso"), "__none__"]  # 모듈 로드 시 main 실행 방지용 인자
    spec.loader.exec_module(m)
    return m


def do_rooms():
    iso = load_iso_module()
    targets = ONLY or ["hall", "pantry", "well", "infirmary", "library", "rock", "lot"]
    for rid in targets:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        iso.sc = bpy.context.scene
        iso.make_materials()
        iso.CUR.clear(); iso.CUR.update(iso.PLATES.get(rid, dict(size=6.0, ortho=9.8, res=640)))
        iso.ROOMS[rid]()
        # 실시간용: 라이트 에너지는 Three.js 스케일에 맞게 축소(W→cd 변환은 로더가 함). 그림자용 큰 필라이트는 제거.
        for o in list(bpy.data.objects):
            if o.type == 'LIGHT' and o.data.type in ('AREA', 'SUN'):
                bpy.data.objects.remove(o, do_unlink=True)
        join_static_meshes()
        export(os.path.join(OUT_ROOMS, f"{rid}.glb"))


def do_chars():
    base = glob.glob(os.path.join(ROOT, "assets3d", "quaternius_chars", "*", "Blends"))[0]
    targets = ONLY or ["Chef_Male", "Doctor_Female_Young", "BlueSoldier_Male"]
    for name in targets:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        with bpy.data.libraries.load(os.path.join(base, name + ".blend"), link=False) as (src, dst):
            dst.objects = [n for n in src.objects]; dst.actions = [n for n in src.actions]
        for o in dst.objects:
            if o is not None:
                try: bpy.context.collection.objects.link(o)
                except Exception: pass
        for o in list(bpy.data.objects):
            if o.type in ('CAMERA', 'LIGHT'):
                bpy.data.objects.remove(o, do_unlink=True)
        # 검정으로 저장된 Skin 재질 → 창백한 살색 (어둠 적응 인류)
        for o in bpy.data.objects:
            if o.type == 'MESH':
                for m in o.data.materials:
                    if m and m.name.lower().startswith("skin") and m.use_nodes:
                        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                        if b: b.inputs["Base Color"].default_value = (0.93, 0.82, 0.72, 1)
        arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
        acts = [a for a in bpy.data.actions]
        print("CHAR", name, "actions", [a.name for a in acts], flush=True)
        # 모든 액션을 NLA 트랙으로 밀어 넣어 내보내기(ACTIONS 모드가 안 될 때 대비)
        if arms:
            arm = arms[0]
            if arm.animation_data is None: arm.animation_data_create()
            for a in acts:
                tr = arm.animation_data.nla_tracks.new(); tr.name = a.name
                st = tr.strips.new(a.name, int(a.frame_range[0]), a); st.name = a.name
            arm.animation_data.action = None
        export(os.path.join(OUT_CHARS, f"{name}.glb"), animations=True)


if __name__ == "__main__":
    {"rooms": do_rooms, "chars": do_chars}[MODE]()
    print("ALL DONE", flush=True)
