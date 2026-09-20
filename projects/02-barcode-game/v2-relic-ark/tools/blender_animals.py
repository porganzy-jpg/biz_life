# -*- coding: utf-8 -*-
"""
잔해 방주 — 짝 짐승(개·고양이·까마귀) + 공룡(티렉스·랩터·트리케라톱스) GLB
blender -b --python tools/blender_animals.py -- <mode> [name ...]

  mode = animals  → static/models/animals/{dog,cat,crow}.glb   (원시 도형 + 자체 아마추어 + 손키프레임 Idle/Walk)
         dinos    → static/models/dinos/{trex,velociraptor,triceratops}.glb (Quaternius FBX 액션 선별)
         show     → static/art/chars/show/{dog,cat,crow,trex,velociraptor,triceratops}.png (비교 페이지용 아이소 렌더)
         verify   → 내보낸 GLB를 다시 임포트해 발 z·키·클립 실측
         all      → animals + dinos + show + verify

교본 적용
  C5 짐승은 사람보다 따뜻하게 — 개 Idle은 사람 다리에 기대는 기울인 포즈, 눈은 사람(#17120f)보다 훨씬 밝다.
  C6 공룡은 위협이자 풍경 — 무채 + 초록 톤(정원사의 것)으로 전 종 통일. 사람과 같은 카메라·같은 선 두께.
  C9 발 z=0, 실측 크기, 정면 +Z(glTF) = Blender -Y.

좌표 규약 (캐릭터와 동일)
  Blender 기준 정면 -Y → export_yup=True 이므로 glTF/Three.js 기준 정면 +Z.
  실측 크기: 개 0.55m · 고양이 0.30m · 까마귀 0.25m · 티렉스 5m · 랩터 2m · 트리케라톱스 3m (모두 서 있는 키).
  소품(메시)은 스킨이 아니라 **뼈의 자식 노드**다(캐릭터 v2와 같은 attach 기법). 클라이언트는 재정규화하지 않는다.
"""
import bpy, sys, os, math, json, glob
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
ONLY = [a for a in argv[1:] if not a.startswith("--")]
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
A3 = os.path.join(ROOT, "assets3d")
OUT_ANI = os.path.join(ROOT, "static", "models", "animals")
OUT_DIN = os.path.join(ROOT, "static", "models", "dinos")
OUT_SHOW = os.path.join(ROOT, "static", "art", "chars", "show")
OUT_RAW = os.path.join(ROOT, "art_raw", "chars_beasts")
for d in (OUT_ANI, OUT_DIN, OUT_SHOW, OUT_RAW):
    os.makedirs(d, exist_ok=True)

RAD = math.radians
sc = None


# ---------------------------------------------------------------- 공통 유틸
def hexcol(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def mat(name, hexc, rough=0.9, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs["Base Color"].default_value = (*hexcol(hexc), 1)
    b.inputs["Roughness"].default_value = rough
    try: b.inputs["Metallic"].default_value = metal
    except Exception: pass
    return m


def T(pos, rot=(0, 0, 0), scale=(1, 1, 1)):
    return (Matrix.Translation(Vector(pos)) @
            Euler(rot, 'XYZ').to_matrix().to_4x4() @
            Matrix.Diagonal(Vector(scale).to_4d()))


def attach(o, arm, bone, world):
    """뼈에 부모로 붙이되 지금 포즈에서의 월드 트랜스폼이 world 가 되도록 로컬을 역산한다(캐릭터 v2와 동일)."""
    o.parent = arm; o.parent_type = 'BONE'; o.parent_bone = bone
    o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    pb = arm.pose.bones[bone]
    blen = arm.data.bones[bone].length
    parent_m = arm.matrix_world @ pb.matrix @ Matrix.Translation(Vector((0, blen, 0)))
    o.matrix_basis = parent_m.inverted() @ world
    return o


def _fin(o, m, arm, bone, world, name):
    o.data.materials.append(m); o.name = name
    return attach(o, arm, bone, world)


def box(arm, bone, m, pos, size, rot=(0, 0, 0), name="p"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    return _fin(bpy.context.object, m, arm, bone, T(pos, rot, size), name)


def ball(arm, bone, m, pos, size, rot=(0, 0, 0), name="p"):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=14, ring_count=8, location=(0, 0, 0))
    return _fin(bpy.context.object, m, arm, bone, T(pos, rot, size), name)


def tube(arm, bone, m, pos, r, h, rot=(0, 0, 0), name="p"):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=12, location=(0, 0, 0))
    return _fin(bpy.context.object, m, arm, bone, T(pos, rot), name)


def cone(arm, bone, m, pos, r1, r2, h, rot=(0, 0, 0), name="p"):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=h, vertices=12, location=(0, 0, 0))
    return _fin(bpy.context.object, m, arm, bone, T(pos, rot), name)


def make_armature(name, bones):
    """bones = [(이름, head, tail, 부모|None), ...] — 아마추어는 원점·무회전이므로 아마추어 공간 = 월드 공간."""
    bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
    arm = bpy.context.object; arm.name = name; arm.data.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for b in list(eb):
        eb.remove(b)
    made = {}
    for bn, head, tail, parent in bones:
        b = eb.new(bn); b.head = Vector(head); b.tail = Vector(tail); b.use_deform = True
        if parent:
            b.parent = made[parent]; b.use_connect = False
        made[bn] = b
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
    return arm


def world_rot(arm, bone, spins):
    """월드 축 기준 회전(도)들을 합성해 그 뼈의 로컬 오일러로 바꿔 준다. spins = [('X', 도), ('Z', 도), ...]"""
    R = Matrix.Identity(4)
    for ax, deg in spins:
        R = Matrix.Rotation(RAD(deg), 4, ax) @ R
    M = arm.data.bones[bone].matrix_local.to_3x3().to_4x4()
    return (M.inverted() @ R @ M).to_euler('XYZ')


def keypose(arm, frame, rots=None, locs=None):
    """rots = {뼈: [('X',도),...]}, locs = {뼈: (x,y,z)} (Root 전용, 월드 = 로컬)."""
    bpy.context.scene.frame_set(frame)
    for bn in arm.pose.bones.keys():
        pb = arm.pose.bones[bn]
        spins = (rots or {}).get(bn)
        pb.rotation_euler = world_rot(arm, bn, spins) if spins else Euler((0, 0, 0), 'XYZ')
        pb.location = Vector((locs or {}).get(bn, (0, 0, 0)))
        pb.keyframe_insert("rotation_euler", frame=frame)
        pb.keyframe_insert("location", frame=frame)


def action_fcurves(a):
    """Blender 4.4+ 슬롯 액션은 fcurve 가 layers→strips→channelbags 안에 있다(구버전 a.fcurves 호환)."""
    out = []
    try:
        for layer in a.layers:
            for strip in layer.strips:
                for cb in getattr(strip, "channelbags", []):
                    out += list(cb.fcurves)
    except Exception:
        pass
    if not out:
        out = list(getattr(a, "fcurves", []))
    return out


def strip_object_channels(a):
    """액션에서 **오브젝트 레벨** 채널(location/rotation/scale)을 지운다.
    Quaternius 공룡 FBX 액션은 아마추어 오브젝트의 scale(3,3,3)까지 키로 갖고 있어서,
    우리가 실측 크기로 스케일을 바꿔도 프레임 평가 때마다 원래 값으로 되돌려 버렸다.
    루트 모션(제자리 재생 시 앞으로 미끄러짐)도 함께 사라져 클라이언트가 위치를 온전히 제어한다."""
    removed = 0
    try:
        for layer in a.layers:
            for strip in layer.strips:
                for cb in getattr(strip, "channelbags", []):
                    for fc in list(cb.fcurves):
                        if not fc.data_path.startswith("pose.bones"):
                            cb.fcurves.remove(fc); removed += 1
    except Exception as e:
        print("strip warn", e, flush=True)
    if not removed and hasattr(a, "fcurves"):
        for fc in list(a.fcurves):
            if not fc.data_path.startswith("pose.bones"):
                a.fcurves.remove(fc); removed += 1
    return removed


def clear_pose(arm):
    """포즈를 완전히 초기화한다. 액션을 떼도 포즈 값은 남아 GLB의 기본(무애니) 자세가 되므로 반드시 호출."""
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = Euler((0, 0, 0), 'XYZ')
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()


def new_action(arm, name):
    if arm.animation_data is None:
        arm.animation_data_create()
    a = bpy.data.actions.new(name)
    arm.animation_data.action = a
    try:
        if hasattr(arm.animation_data, "action_slot"):
            # Blender 4.4+ 액션 슬롯: 새 액션은 슬롯이 비어 있으므로 아마추어용 슬롯을 만들어 붙인다
            if not len(a.slots):
                a.slots.new('OBJECT', arm.name)
            arm.animation_data.action_slot = a.slots[0]
    except Exception as e:
        print("slot warn", e, flush=True)
    return a


def bake_to_nla(arm, order):
    """내보내기 직전 상태 정리.
    ★ NLA 트랙으로 밀어 넣지 않는다 — 트랙을 만들면 뎁스그래프가 그 트랙을 평가해 **기본 포즈**(GLB 노드의
      기본 TRS)가 마지막 트랙의 첫 프레임 포즈로 굳는다(개가 Walk 1프레임 자세로 저장되어 발이 바닥을 파고들었다).
      export_animation_mode='ACTIONS' 는 파일 안의 모든 액션을 알아서 각각의 glTF 애니메이션으로 내보낸다.
    order 에 없는 액션은 지워서 GLB에 군더더기가 남지 않게 한다."""
    keep = set(order)
    for a in list(bpy.data.actions):
        if a.name not in keep:
            bpy.data.actions.remove(a)
    if arm.animation_data is None:
        arm.animation_data_create()
    for tr in list(arm.animation_data.nla_tracks):
        arm.animation_data.nla_tracks.remove(tr)
    clear_pose(arm)


def export_glb(path):
    kw = dict(filepath=path, export_format='GLB', export_lights=False, export_cameras=False,
              export_apply=False, use_selection=False, use_visible=False, use_renderable=False,
              export_animations=True, export_yup=True, export_animation_mode='ACTIONS',
              export_nla_strips=False, export_frame_range=False, export_force_sampling=True)
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        for k in ('export_animation_mode', 'export_nla_strips', 'export_frame_range'):
            kw.pop(k, None)
        bpy.ops.export_scene.gltf(**kw)
    print("EXPORTED", path, os.path.getsize(path) // 1024, "KB",
          "clips", sorted(a.name for a in bpy.data.actions), flush=True)


def mesh_bounds(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        if o.type != 'MESH':
            continue
        ev = o.evaluated_get(dg)
        try: m = ev.to_mesh()
        except Exception: continue
        mw = o.matrix_world
        for v in m.vertices:
            pts.append(mw @ v.co)
        ev.to_mesh_clear()
    if not pts:
        return 0.0, 1.0
    return min(p.z for p in pts), max(p.z for p in pts)


# ================================================================ 짝 짐승
# TRUST_AND_COMPANIONS §4 반려 시스템: 개(길손·경고) · 고양이(진열대·재고) · 까마귀(탑·전령)
EYE_BRIGHT = dict(dog="#F2B84A", cat="#A8E86B", crow="#EDE4C4")   # C5 짐승의 눈은 사람보다 밝게

DOG_BONES = [
    ("Root",        (0, 0, 0),           (0, 0.10, 0),        None),
    ("Body",        (0, 0.20, 0.395),    (0, -0.18, 0.415),   "Root"),
    ("Neck",        (0, -0.18, 0.415),   (0, -0.27, 0.495),   "Body"),
    ("Head",        (0, -0.27, 0.495),   (0, -0.42, 0.475),   "Neck"),
    ("Tail",        (0, 0.22, 0.415),    (0, 0.36, 0.505),    "Body"),
    ("FrontLeg.L",  (0.085, -0.14, 0.36), (0.085, -0.14, 0.0), "Body"),
    ("FrontLeg.R",  (-0.085, -0.14, 0.36), (-0.085, -0.14, 0.0), "Body"),
    ("BackLeg.L",   (0.095, 0.16, 0.36), (0.095, 0.16, 0.0),  "Body"),
    ("BackLeg.R",   (-0.095, 0.16, 0.36), (-0.095, 0.16, 0.0), "Body"),
]

CAT_BONES = [
    ("Root",        (0, 0, 0),           (0, 0.06, 0),        None),
    ("Body",        (0, 0.13, 0.205),    (0, -0.11, 0.215),   "Root"),
    ("Neck",        (0, -0.11, 0.215),   (0, -0.17, 0.250),   "Body"),
    ("Head",        (0, -0.17, 0.250),   (0, -0.26, 0.245),   "Neck"),
    ("Tail",        (0, 0.145, 0.215),   (0, 0.26, 0.255),    "Body"),
    ("Tail2",       (0, 0.26, 0.255),    (0, 0.34, 0.300),    "Tail"),
    ("FrontLeg.L",  (0.052, -0.075, 0.19), (0.052, -0.075, 0.0), "Body"),
    ("FrontLeg.R",  (-0.052, -0.075, 0.19), (-0.052, -0.075, 0.0), "Body"),
    ("BackLeg.L",   (0.058, 0.10, 0.19), (0.058, 0.10, 0.0),  "Body"),
    ("BackLeg.R",   (-0.058, 0.10, 0.19), (-0.058, 0.10, 0.0), "Body"),
]

CROW_BONES = [
    ("Root",        (0, 0, 0),           (0, 0.05, 0),        None),
    ("Body",        (0, 0.075, 0.135),   (0, -0.045, 0.165),  "Root"),
    ("Neck",        (0, -0.045, 0.165),  (0, -0.075, 0.190),  "Body"),
    ("Head",        (0, -0.075, 0.190),  (0, -0.135, 0.185),  "Neck"),
    ("Tail",        (0, 0.085, 0.135),   (0, 0.19, 0.125),    "Body"),
    ("Wing.L",      (0.035, -0.01, 0.165), (0.085, 0.06, 0.145), "Body"),
    ("Wing.R",      (-0.035, -0.01, 0.165), (-0.085, 0.06, 0.145), "Body"),
    ("Leg.L",       (0.030, 0.015, 0.085), (0.030, 0.015, 0.0), "Body"),
    ("Leg.R",       (-0.030, 0.015, 0.085), (-0.030, 0.015, 0.0), "Body"),
]


def eyes(arm, bone, key, pos, r, depth):
    """밝은 눈(홍채) + 작은 어두운 동공 + 흰 반짝임. 사람 눈(어둡고 큼)과 정반대."""
    mi = mat("iris_" + key, EYE_BRIGHT[key], 0.25)
    mp = mat("pupil_" + key, "#140f0c", 0.2)
    mg = mat("glint_" + key, "#FFFBEF", 0.05)
    out = []
    for sx in (1, -1):
        x = pos[0] + sx * pos[3]
        out.append(ball(arm, bone, mi, (x, pos[1], pos[2]), (r, r * 0.8, r), name="eye_iris"))
        out.append(ball(arm, bone, mp, (x, pos[1] - depth, pos[2]), (r * 0.5, r * 0.5, r * 0.55), name="eye_pupil"))
        out.append(ball(arm, bone, mg, (x + sx * r * 0.22, pos[1] - depth * 1.1, pos[2] + r * 0.24),
                        (r * 0.22, r * 0.22, r * 0.22), name="eye_glint"))
    return out


def build_dog():
    arm = make_armature("dog", DOG_BONES)
    fur = mat("dog_fur", "#2C241B"); pale = mat("dog_chest", "#CDB68F")
    dark = mat("dog_nose", "#211E1B", 0.5); pad = mat("dog_paw", "#3A3129")
    o = []
    o.append(box(arm, "Body", fur, (0, 0.02, 0.405), (0.205, 0.44, 0.215), name="dog_torso"))
    o.append(ball(arm, "Body", fur, (0, 0.205, 0.405), (0.225, 0.24, 0.225), name="dog_rump"))
    o.append(box(arm, "Body", pale, (0, -0.10, 0.345), (0.185, 0.24, 0.115), name="dog_belly"))
    o.append(tube(arm, "Neck", fur, (0, -0.225, 0.455), 0.078, 0.17,
                  rot=(RAD(50), 0, 0), name="dog_neck"))
    o.append(box(arm, "Head", fur, (0, -0.325, 0.498), (0.150, 0.155, 0.150), name="dog_head"))
    o.append(box(arm, "Head", fur, (0, -0.425, 0.462), (0.092, 0.115, 0.088), name="dog_snout"))
    o.append(ball(arm, "Head", dark, (0, -0.483, 0.474), (0.050, 0.038, 0.040), name="dog_nose"))
    o.append(box(arm, "Head", pale, (0, -0.425, 0.418), (0.070, 0.100, 0.030), name="dog_jaw"))
    for sx in (1, -1):   # 늘어진 귀 (길손의 눈이 된 개 — 크게)
        o.append(box(arm, "Head", fur, (sx * 0.093, -0.292, 0.522), (0.034, 0.105, 0.190),
                     rot=(RAD(-8), RAD(sx * -16), 0), name="dog_ear"))
    o += eyes(arm, "Head", "dog", (0.0, -0.388, 0.527, 0.050), 0.040, 0.016)
    for bn, x, y in (("FrontLeg.L", 0.085, -0.14), ("FrontLeg.R", -0.085, -0.14),
                     ("BackLeg.L", 0.095, 0.16), ("BackLeg.R", -0.095, 0.16)):
        o.append(tube(arm, bn, fur, (x, y, 0.185), 0.036, 0.36, name="dog_leg"))
        o.append(box(arm, bn, pad, (x, y - 0.018, 0.024), (0.080, 0.115, 0.048), name="dog_paw"))
    o.append(cone(arm, "Tail", fur, (0, 0.285, 0.455), 0.044, 0.014, 0.20,
                  rot=(RAD(-122), 0, 0), name="dog_tail"))
    return arm, o


def build_cat():
    arm = make_armature("cat", CAT_BONES)
    fur = mat("cat_fur", "#4E535A"); pale = mat("cat_belly", "#9AA1A8")
    dark = mat("cat_nose", "#241F1E", 0.5)
    o = []
    o.append(box(arm, "Body", fur, (0, 0.01, 0.210), (0.118, 0.27, 0.125), name="cat_torso"))
    o.append(ball(arm, "Body", fur, (0, 0.135, 0.210), (0.130, 0.140, 0.130), name="cat_rump"))
    o.append(box(arm, "Body", pale, (0, -0.045, 0.168), (0.100, 0.155, 0.055), name="cat_belly"))
    o.append(tube(arm, "Neck", fur, (0, -0.140, 0.232), 0.046, 0.08,
                  rot=(RAD(58), 0, 0), name="cat_neck"))
    o.append(ball(arm, "Head", fur, (0, -0.205, 0.252), (0.108, 0.105, 0.100), name="cat_head"))
    o.append(box(arm, "Head", pale, (0, -0.258, 0.238), (0.055, 0.050, 0.042), name="cat_muzzle"))
    o.append(ball(arm, "Head", dark, (0, -0.280, 0.246), (0.024, 0.020, 0.018), name="cat_nose"))
    for sx in (1, -1):   # 뾰족한 삼각 귀 — 실루엣의 핵심
        o.append(cone(arm, "Head", fur, (sx * 0.056, -0.196, 0.318), 0.042, 0.004, 0.075,
                      rot=(0, RAD(sx * 16), 0), name="cat_ear"))
    o += eyes(arm, "Head", "cat", (0.0, -0.250, 0.266, 0.042), 0.036, 0.014)
    for bn, x, y in (("FrontLeg.L", 0.052, -0.075), ("FrontLeg.R", -0.052, -0.075),
                     ("BackLeg.L", 0.058, 0.10), ("BackLeg.R", -0.058, 0.10)):
        o.append(tube(arm, bn, fur, (x, y, 0.100), 0.028, 0.20, name="cat_leg"))
        o.append(box(arm, bn, pale, (x, y - 0.010, 0.016), (0.046, 0.062, 0.032), name="cat_paw"))
    # 꼬리: 엉덩이에서 끊기지 않게 밑동을 몸에 겹쳐 붙이고 두 마디로 잇는다
    o.append(cone(arm, "Tail", fur, (0, 0.185, 0.228), 0.030, 0.020, 0.115,
                  rot=(RAD(-108), 0, 0), name="cat_tail1"))
    o.append(cone(arm, "Tail2", pale, (0, 0.283, 0.268), 0.020, 0.007, 0.095,
                  rot=(RAD(-118), 0, 0), name="cat_tail2"))
    return arm, o


def build_crow():
    arm = make_armature("crow", CROW_BONES)
    blk = mat("crow_body", "#22272C", 0.55); sheen = mat("crow_sheen", "#35464F", 0.3)
    beak = mat("crow_beak", "#9AA0A6", 0.45); leg = mat("crow_leg", "#3A3530", 0.7)
    o = []
    # 몸통: 앞으로 기운 타원 + 등의 광택(청록 윤기 — 두 세계를 오가는 새)
    o.append(ball(arm, "Body", blk, (0, 0.015, 0.140), (0.105, 0.200, 0.125),
                  rot=(RAD(-12), 0, 0), name="crow_body"))
    o.append(ball(arm, "Body", sheen, (0, 0.010, 0.178), (0.078, 0.150, 0.045),
                  rot=(RAD(-12), 0, 0), name="crow_back"))
    o.append(tube(arm, "Neck", blk, (0, -0.058, 0.176), 0.042, 0.055,
                  rot=(RAD(52), 0, 0), name="crow_neck"))
    o.append(ball(arm, "Head", blk, (0, -0.095, 0.192), (0.082, 0.085, 0.078), name="crow_head"))
    # 부리: 넓은 쪽이 머리에 붙고 뾰족한 끝이 앞(-Y). rot +96° 여야 끝이 -Y 로 간다.
    o.append(cone(arm, "Head", beak, (0, -0.152, 0.186), 0.028, 0.003, 0.070,
                  rot=(RAD(96), 0, 0), name="crow_beak"))
    o += eyes(arm, "Head", "crow", (0.0, -0.122, 0.206, 0.033), 0.024, 0.009)
    # 접은 날개: 몸통 옆면에 붙은 얇은 판(활짝 펴지 않는다)
    for bn, sx in (("Wing.L", 1), ("Wing.R", -1)):
        o.append(box(arm, bn, blk, (sx * 0.062, 0.030, 0.150), (0.026, 0.175, 0.090),
                     rot=(RAD(-10), 0, RAD(sx * -6)), name="crow_wing"))
        o.append(box(arm, bn, sheen, (sx * 0.058, 0.108, 0.128), (0.022, 0.075, 0.040),
                     rot=(RAD(-22), 0, RAD(sx * -6)), name="crow_wingtip"))
    # 꼬리깃: 뒤로 뻗은 납작한 부채
    o.append(box(arm, "Tail", blk, (0, 0.170, 0.120), (0.085, 0.150, 0.016),
                 rot=(RAD(-6), 0, 0), name="crow_tail"))
    for bn, x in (("Leg.L", 0.030), ("Leg.R", -0.030)):
        o.append(tube(arm, bn, leg, (x, 0.015, 0.046), 0.0095, 0.092, name="crow_leg"))
        o.append(box(arm, bn, leg, (x, -0.002, 0.006), (0.026, 0.058, 0.012), name="crow_foot"))
    return arm, o


# ---------------------------------------------------------------- 애니메이션
def anim_dog(arm):
    # Idle — C5: 사람 다리에 기대는 포즈. 몸이 +X 쪽(사람이 선 자리)으로 기울고, 얼굴은 위를 본다.
    LEAN = [('Y', -16)]      # -X 쪽(사람이 선 자리)으로 몸을 기울인다
    new_action(arm, "Idle")
    for f, wag, br in ((1, 20, 0.0), (16, -6, 0.004), (31, 22, 0.0), (46, -8, 0.004), (61, 20, 0.0)):
        keypose(arm, f,
                rots={"Root": LEAN,
                      "Body": [('X', -3)],
                      "Neck": [('X', -12)],
                      "Head": [('X', -22), ('Z', -16)],
                      "Tail": [('Z', wag), ('X', -18)],
                      "FrontLeg.L": [('Y', -9)], "FrontLeg.R": [('Y', -4)]},
                locs={"Root": (-0.048, 0, br)})
    # Walk — 대각선 보행(앞왼 + 뒤오른). 몸통 상하 흔들림 + 꼬리 흔들기.
    new_action(arm, "Walk")
    for f, sw, bob, wag in ((1, 24, 0.0, 12), (7, 0, 0.014, -10), (13, -24, 0.0, 12),
                            (19, 0, 0.014, -10), (25, 24, 0.0, 12)):
        keypose(arm, f,
                rots={"FrontLeg.L": [('X', -sw)], "BackLeg.R": [('X', -sw * 0.8)],
                      "FrontLeg.R": [('X', sw)], "BackLeg.L": [('X', sw * 0.8)],
                      "Body": [('X', -2)], "Neck": [('X', -8)],
                      "Head": [('X', -6 - sw * 0.1)],
                      "Tail": [('X', -22), ('Z', wag)]},
                locs={"Root": (0, 0, bob)})


def anim_cat(arm):
    # Idle — 꼬리를 세우고 천천히 흔든다(고양이는 몸을 붙이지 않고 높은 곳을 본다: C5).
    new_action(arm, "Idle")
    for f, flick, br in ((1, 14, 0.0), (20, -10, 0.003), (40, 16, 0.0), (60, -12, 0.003), (81, 14, 0.0)):
        keypose(arm, f,
                rots={"Body": [('X', -1)],
                      "Neck": [('X', -8)], "Head": [('X', -10), ('Z', -7)],
                      "Tail": [('X', -58)], "Tail2": [('X', -20), ('Z', flick)]},
                locs={"Root": (0, 0, br)})
    # Walk — 폭이 작고 부드럽다. 꼬리는 세운 채.
    new_action(arm, "Walk")
    for f, sw, bob in ((1, 18, 0.0), (8, 0, 0.008), (15, -18, 0.0), (22, 0, 0.008), (29, 18, 0.0)):
        keypose(arm, f,
                rots={"FrontLeg.L": [('X', -sw)], "BackLeg.R": [('X', -sw * 0.85)],
                      "FrontLeg.R": [('X', sw)], "BackLeg.L": [('X', sw * 0.85)],
                      "Neck": [('X', -6)], "Head": [('X', -6)],
                      "Tail": [('X', -62)], "Tail2": [('X', -18), ('Z', sw * 0.4)]},
                locs={"Root": (0, 0, bob)})


def anim_crow(arm):
    # Idle — 고개를 까딱이고 가끔 날개를 턴다(탑 부족의 전령).
    new_action(arm, "Idle")
    for f, hx, hz, wg in ((1, 0, 0, 0), (14, -14, 10, 0), (28, 4, -12, 0), (40, 0, 0, 22), (52, 0, 0, 0), (66, -10, 6, 0), (81, 0, 0, 0)):
        keypose(arm, f,
                rots={"Neck": [('X', hx * 0.5)], "Head": [('X', hx), ('Z', hz)],
                      "Wing.L": [('Y', -wg)], "Wing.R": [('Y', wg)],
                      "Tail": [('X', 6)]},
                locs={"Root": (0, 0, 0)})
    # Walk — 총총 뛰는 걸음. 몸이 오르내리고 머리는 앞뒤로 찌른다(새 특유의 head-bob).
    new_action(arm, "Walk")
    for f, sw, hop, hy in ((1, 20, 0.0, -0.012), (6, 0, 0.022, 0.006), (11, -20, 0.0, -0.012), (16, 0, 0.022, 0.006), (21, 20, 0.0, -0.012)):
        keypose(arm, f,
                rots={"Leg.L": [('X', -sw)], "Leg.R": [('X', sw)],
                      "Neck": [('X', 8)], "Head": [('X', -8)],
                      "Wing.L": [('Y', -6)], "Wing.R": [('Y', 6)],
                      "Tail": [('X', 10)]},
                locs={"Root": (0, hy, hop)})


ANIMALS = {
    "dog":  dict(build=build_dog,  anim=anim_dog,  h=0.55, ko="개"),
    "cat":  dict(build=build_cat,  anim=anim_cat,  h=0.30, ko="고양이"),
    "crow": dict(build=build_crow, anim=anim_crow, h=0.25, ko="까마귀"),
}


def use_action(arm, name, t=0.0):
    a = bpy.data.actions.get(name)
    if not a:
        return None
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = a
    try:
        if hasattr(arm.animation_data, "action_slot") and len(a.slots):
            arm.animation_data.action_slot = a.slots[0]
    except Exception: pass
    f0, f1 = a.frame_range
    bpy.context.scene.frame_set(int(f0 + (f1 - f0) * t))
    bpy.context.view_layer.update()
    return a


def level_idle(arm, objs):
    """Idle 포즈에서 발이 z=0 이 되도록 Idle 액션의 Root 높이 키를 통째로 올린다.
    (개는 기대는 포즈 때문에 몸이 기울어 바깥쪽 발이 바닥을 파고든다.)"""
    a = use_action(arm, "Idle", 0.0)
    if not a:
        return
    lo, _ = mesh_bounds(objs)
    if abs(lo) < 1e-5:
        return
    d = lo / max(arm.scale.z, 1e-9)
    fc = next((f for f in action_fcurves(a)
               if f.data_path == 'pose.bones["Root"].location' and f.array_index == 2), None)
    if fc is None:
        return
    for kp in fc.keyframe_points:
        kp.co[1] -= d
        kp.handle_left[1] -= d
        kp.handle_right[1] -= d
    fc.update()
    bpy.context.view_layer.update()


def make_animal(key, for_render=False, action="Idle", t=0.0):
    global sc
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    d = ANIMALS[key]
    arm, objs = d["build"]()
    d["anim"](arm)
    level_idle(arm, objs)
    # 실측 크기·발 원점은 모두 **Idle 첫 프레임** 기준 — 클라이언트가 기본으로 보는 자세와 일치시킨다
    use_action(arm, "Idle", 0.0)
    lo, hi = mesh_bounds(objs)
    arm.scale = tuple(v * (d["h"] / max(hi - lo, 1e-6)) for v in arm.scale)
    bpy.context.view_layer.update()
    use_action(arm, "Idle", 0.0)
    lo, hi = mesh_bounds(objs)
    arm.location = (arm.location.x, arm.location.y, arm.location.z - lo)
    bpy.context.view_layer.update()
    if for_render:
        use_action(arm, action, t)
    else:
        clear_pose(arm)
    bpy.context.view_layer.update()
    return arm, objs


def do_animals():
    for key in (ONLY or list(ANIMALS.keys())):
        arm, objs = make_animal(key)
        use_action(arm, "Idle", 0.0)
        lo, hi = mesh_bounds(objs)
        print("FIT", key, "idle z %.4f..%.4f (목표 %.2f m)" % (lo, hi, ANIMALS[key]["h"]), flush=True)
        bake_to_nla(arm, ["Idle", "Walk"])
        export_glb(os.path.join(OUT_ANI, key + ".glb"))


# ================================================================ 공룡
# C6: 무채 + 초록 톤(정원사의 것). 원본 재질 이름 → 우리 팔레트.
DINO_PALETTE = {
    "Green": "#5C6B4E", "LightGreen": "#7E8C68", "DarkGreen": "#414C39",
    "Brown": "#5A5B52", "LightBrown": "#7C7D71", "DarkBrown": "#3E3F39",
    "Purple": "#4E5A4C", "Red": "#6E5F4A", "LightYellow": "#9AA089",
    "Black": "#20221E", "White": "#A8AC9C", "Grey": "#6B6E66",
}
DINOS = {
    "trex":          dict(fbx="Trex",          h=5.0, ko="티렉스",     accent="#3F4A37"),
    "velociraptor":  dict(fbx="Velociraptor",  h=2.0, ko="랩터",       accent="#4A4F3C"),
    "triceratops":   dict(fbx="Triceratops",   h=3.0, ko="트리케라톱스", accent="#4C5748"),
}
DINO_KEEP = ("Idle", "Walk")


def load_dino(key):
    """FBX 임포트 → 무채+초록 재질 → Idle/Walk만 남기고 이름 정리 → 실측 키·발 z=0."""
    global sc
    d = DINOS[key]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    base = glob.glob(os.path.join(A3, "quaternius_dinos", "*", "FBX"))[0]
    bpy.ops.import_scene.fbx(filepath=os.path.join(base, d["fbx"] + ".fbx"), automatic_bone_orientation=False)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
    arm.name = key; mesh.name = key + "_body"
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'):
            bpy.data.objects.remove(o, do_unlink=True)
    # 재질: 원본 슬롯을 **새 재질로 통째 교체**한다(무채+초록, 정원사의 것).
    # FBX 에서 온 재질은 노드 구성이 제각각이라 색만 바꾸면 흰 도화지로 렌더되는 경우가 있다.
    for i, m in enumerate(list(mesh.data.materials)):
        key_ = (m.name.split('.')[0] if m else "")
        col = DINO_PALETTE.get(key_, d["accent"])
        mesh.data.materials[i] = mat("dino_%s_%s" % (key, key_ or i), col, 0.92)
    # 액션: 'Armature|Armature|TRex_Idle' → 'Idle'
    keep = {}
    for a in list(bpy.data.actions):
        tail = a.name.split('|')[-1].split('_')[-1]
        if tail in DINO_KEEP and tail not in keep:
            a.name = tail; keep[tail] = a
            strip_object_channels(a)
        else:
            bpy.data.actions.remove(a)
    # 실측 키·발 z=0 — 짐승과 같은 규약으로 **Idle 첫 프레임** 기준
    use_action(arm, "Idle", 0.0)
    lo, hi = mesh_bounds([mesh])
    arm.scale = [v * (d["h"] / max(hi - lo, 1e-6)) for v in arm.scale]
    bpy.context.view_layer.update()
    use_action(arm, "Idle", 0.0)
    lo, hi = mesh_bounds([mesh])
    arm.location = (arm.location.x, arm.location.y, arm.location.z - lo)
    bpy.context.view_layer.update()
    return arm, mesh, keep


def do_dinos():
    for key in (ONLY or list(DINOS.keys())):
        arm, mesh, keep = load_dino(key)
        use_action(arm, "Idle", 0.0)
        lo, hi = mesh_bounds([mesh])
        print("FIT", key, "idle z %.4f..%.4f (목표 %.2f m)" % (lo, hi, DINOS[key]["h"]), flush=True)
        bake_to_nla(arm, [n for n in DINO_KEEP if n in keep])
        export_glb(os.path.join(OUT_DIN, key + ".glb"))


# ================================================================ 렌더 (비교 페이지용)
AZ, EL = 45, 32


def camera(ortho, look_z):
    az, el = RAD(AZ), RAD(EL); dist = 40.0
    look = Vector((0, 0, look_z))
    loc = Vector((-math.cos(el) * math.sin(az) * dist, -math.cos(el) * math.cos(az) * dist,
                  math.sin(el) * dist)) + look
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.object
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    cam.data.clip_end = 200
    cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    return cam


def lights():
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 5),
                             rotation=(RAD(45), RAD(20), RAD(-40)))
    s = bpy.context.object; s.data.energy = 2.2; s.data.color = (1.0, 0.92, 0.8)
    bpy.ops.object.light_add(type='AREA', location=(-4, -4, 4), rotation=(RAD(50), 0, RAD(-45)))
    f = bpy.context.object; f.data.energy = 220; f.data.size = 8; f.data.color = (0.85, 0.9, 1.0)


def render(path, res=320):
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.render.use_freestyle = True; sc.render.line_thickness = 1.3
    fs = sc.view_layers[0].freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("c")
    ls.select_silhouette = True; ls.select_crease = True; ls.select_border = True
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("cls")
    ls.linestyle.color = hexcol("#1a1714"); ls.linestyle.thickness = 1.3
    for vt in ('Standard', 'Khronos PBR Neutral', 'Filmic'):
        try:
            sc.view_settings.view_transform = vt; break
        except TypeError:
            continue
    sc.view_settings.exposure = 0.0
    for lk in ('None', 'Standard - None', 'AgX - None'):
        try:
            sc.view_settings.look = lk; break
        except TypeError:
            continue
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.45
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def do_show():
    """캐릭터 스프라이트와 같은 아이소 카메라(45°/32°)·같은 방위(dl = -90°)로 렌더."""
    targets = ONLY or (list(ANIMALS.keys()) + list(DINOS.keys()))
    for key in targets:
        if key in ANIMALS:
            arm, objs = make_animal(key, for_render=True, action="Idle", t=0.0)
            ortho = ANIMALS[key]["h"] * 2.6
        else:
            arm, mesh, keep = load_dino(key)
            use_action(arm, "Idle", 0.0)
            ortho = DINOS[key]["h"] * 2.0
        arm.rotation_euler = (0, 0, RAD(-90))    # dl = 정면 왼쪽 (캐릭터 스프라이트와 동일)
        bpy.context.view_layer.update()
        camera(ortho, ortho * 0.22); lights()
        out = os.path.join(OUT_SHOW, key + ".png")
        render(out, 360)
        render(os.path.join(OUT_RAW, key + ".png"), 360)
        print("RENDERED", out, flush=True)
    # 개가 사람 다리에 기대는지 보이게: 사람 다리 대용 기둥과 함께 한 장 더
    if "dog" in targets:
        arm, objs = make_animal("dog", for_render=True, action="Idle", t=0.0)
        legm = mat("human_leg", "#33302B")
        # ★ 개를 -90° 회전한 뒤이므로 기둥도 같은 프레임으로: 개의 -X(기대는 쪽) = 월드 +Y(카메라 반대편)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.085, depth=0.86, location=(0.0, 0.150, 0.43))
        p = bpy.context.object; p.data.materials.append(legm); p.name = "ref_human_leg"
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.04, 0.150, 0.03))
        q = bpy.context.object; q.scale = (0.26, 0.11, 0.06); q.data.materials.append(legm); q.name = "ref_shoe"
        arm.rotation_euler = (0, 0, RAD(-90)); bpy.context.view_layer.update()
        camera(1.35, 0.33); lights()
        out = os.path.join(OUT_SHOW, "dog_lean.png")
        render(out, 360); print("RENDERED", out, flush=True)


# ================================================================ 검증
# ★ Blender 의 glTF **임포터**는 뼈 길이·롤을 스스로 다시 추정하기 때문에 포즈의 "이동" 채널이
#   원본과 다른 기저로 해석된다(개 발이 6mm 파고든 것처럼 보이는 현상). 그래서 재임포트 대신
#   **GLB 안의 노드·애니메이션을 직접 읽어** 클라이언트(Three.js)가 실제로 보는 값을 잰다.
import struct


def glb_json(path):
    d = open(path, 'rb').read()
    n = struct.unpack('<I', d[12:16])[0]
    return json.loads(d[20:20 + n].decode('utf-8')), d


def _trs(nd):
    m = Matrix.Identity(4)
    if "matrix" in nd:
        v = nd["matrix"]
        return Matrix([[v[0], v[4], v[8], v[12]], [v[1], v[5], v[9], v[13]],
                       [v[2], v[6], v[10], v[14]], [v[3], v[7], v[11], v[15]]])
    t = nd.get("translation", (0, 0, 0)); r = nd.get("rotation", (0, 0, 0, 1)); s = nd.get("scale", (1, 1, 1))
    from mathutils import Quaternion
    m = Matrix.Translation(Vector(t)) @ Quaternion((r[3], r[0], r[1], r[2])).to_matrix().to_4x4() @         Matrix.Diagonal(Vector(s).to_4d())
    return m


def _acc_vals(j, data, idx):
    """accessor 를 float 배열로 (버퍼뷰 하나짜리 GLB 전용, 컴포넌트 타입 FLOAT만)."""
    n0 = struct.unpack('<I', data[12:16])[0]
    bin_off = 20 + n0 + 8            # JSON 청크 뒤 BIN 청크 헤더(8바이트)
    a = j["accessors"][idx]
    bv = j["bufferViews"][a["bufferView"]]
    cnt = a["count"]
    ncomp = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
    off = bin_off + bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    return [struct.unpack_from('<' + 'f' * ncomp, data, off + i * 4 * ncomp) for i in range(cnt)]


def glb_report(path, clip="Idle"):
    """clip 의 t=0 시점에서 각 메시 노드의 월드 바운딩을 계산한다. glTF 는 Y-up 이므로 Y가 키다."""
    j, data = glb_json(path)
    nodes = j["nodes"]
    parent = {}
    for i, nd in enumerate(nodes):
        for c in nd.get("children", []):
            parent[c] = i
    local = [_trs(nd) for nd in nodes]
    # 애니메이션 t=0 샘플로 로컬 TRS 덮어쓰기
    anim = next((a for a in j.get("animations", []) if a.get("name", "").lower() == clip.lower()), None)
    if anim:
        over = {}
        for ch in anim["channels"]:
            smp = anim["samplers"][ch["sampler"]]
            out = _acc_vals(j, data, smp["output"])
            nd_i = ch["target"]["node"]; pth = ch["target"]["path"]
            over.setdefault(nd_i, {})[pth] = out[0]
        from mathutils import Quaternion
        for nd_i, o in over.items():
            base = nodes[nd_i]
            t = o.get("translation", base.get("translation", (0, 0, 0)))
            r = o.get("rotation", base.get("rotation", (0, 0, 0, 1)))
            s = o.get("scale", base.get("scale", (1, 1, 1)))
            local[nd_i] = (Matrix.Translation(Vector(t[:3])) @
                           Quaternion((r[3], r[0], r[1], r[2])).to_matrix().to_4x4() @
                           Matrix.Diagonal(Vector(s[:3]).to_4d()))
    world = {}

    def wm(i):
        if i in world:
            return world[i]
        p = parent.get(i)
        world[i] = (wm(p) @ local[i]) if p is not None else local[i]
        return world[i]

    lo = Vector((1e9, 1e9, 1e9)); hi = Vector((-1e9, -1e9, -1e9))
    for i, nd in enumerate(nodes):
        if "mesh" not in nd:
            continue
        M = wm(i)
        for prim in j["meshes"][nd["mesh"]]["primitives"]:
            a = j["accessors"][prim["attributes"]["POSITION"]]
            mn, mx = a["min"], a["max"]
            for cx in (mn[0], mx[0]):
                for cy in (mn[1], mx[1]):
                    for cz in (mn[2], mx[2]):
                        w = M @ Vector((cx, cy, cz))
                        lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
                        hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    clips = [a.get("name") for a in j.get("animations", [])]
    return lo, hi, clips, len(nodes)


def glb_nodes(path, prefix=None):
    j, _ = glb_json(path)
    names = [nd.get("name", "") for nd in j["nodes"]]
    return sorted(n for n in names if (prefix is None or n.startswith(prefix)))


def do_verify():
    """세 가지를 함께 본다.
      (a) 씬 실측 — 짐승·공룡을 다시 빌드해 뎁스그래프에서 잰 값(가장 정확. 스킨 메시도 정확).
      (b) GLB 직접 읽기 — 클립 이름·노드 수·용량. 스킨 메시의 바운딩은 보수적이라 키 판정에는 쓰지 않는다.
      (c) 8역할 GLB의 imp_ 노드 목록."""
    print()
    print("--- (a) 씬 실측 (Idle 첫 프레임 · Blender Z-up) ---", flush=True)
    print("모델 | 발 z | 키 z | 목표", flush=True)
    for k in ANIMALS:
        arm, objs = make_animal(k, for_render=True, action="Idle", t=0.0)
        lo, hi = mesh_bounds(objs)
        print(f"animals/{k}.glb | {lo:+.4f} | {hi:.4f} | {ANIMALS[k]['h']} m", flush=True)
    for k in DINOS:
        arm, mesh, keep = load_dino(k)
        use_action(arm, "Idle", 0.0)
        lo, hi = mesh_bounds([mesh])
        print(f"dinos/{k}.glb | {lo:+.4f} | {hi:.4f} | {DINOS[k]['h']} m", flush=True)

    print()
    print("--- (b) GLB 직접 읽기 (용량 · 노드 · 클립) ---", flush=True)
    paths = [os.path.join(OUT_ANI, k + ".glb") for k in ANIMALS]
    paths += [os.path.join(OUT_DIN, k + ".glb") for k in DINOS]
    paths += [os.path.join(ROOT, "static", "models", "chars", r + ".glb")
              for r in ("scout", "cook", "medic", "engineer", "farmer", "scholar", "trader", "kid")]
    for path in paths:
        if not os.path.exists(path):
            print(f"{os.path.basename(path)} | MISSING", flush=True); continue
        lo, hi, clips, nn = glb_report(path, "Idle")
        kb = os.path.getsize(path) // 1024
        print(f"{os.path.relpath(path, os.path.join(ROOT, 'static', 'models'))} | {kb} KB | 노드 {nn} | "
              f"{' '.join(str(c) for c in clips)}", flush=True)

    print()
    print("--- (c) 8역할 GLB 의 imp_ 노드 ---", flush=True)
    for r in ("scout", "cook", "medic", "engineer", "farmer", "scholar", "trader", "kid"):
        path = os.path.join(ROOT, "static", "models", "chars", r + ".glb")
        if not os.path.exists(path):
            continue
        imp = glb_nodes(path, "imp_")
        print(f"{r} | {len(imp)}개 | {' '.join(imp)}", flush=True)


if __name__ == "__main__":
    todo = {"animals": [do_animals], "dinos": [do_dinos], "show": [do_show], "verify": [do_verify],
            "all": [do_animals, do_dinos, do_show, do_verify]}[MODE]
    for fn in todo:
        fn()
    print("ALL DONE", flush=True)
