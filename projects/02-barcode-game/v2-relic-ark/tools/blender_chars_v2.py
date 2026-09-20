# -*- coding: utf-8 -*-
"""
잔해 방주 — 8역할 정식 캐릭터 v2 (Quaternius Ultimate Animated Characters 기반)
blender -b --python tools/blender_chars_v2.py -- <mode> [role ...]

  mode = glb      → static/models/chars/<role>.glb  (Idle/Walk/Run/PickUp/SitDown/StandUp/Death 클립)
         sprites  → static/art/chars/<role>_{dl,ul}_{a,b}.png (256px 투명, a=Walk 중간·b=Idle)
         all      → 둘 다

성경 반영 (docs/LORE_v2 §3, WORLD_BIBLE_v2 §2)
  - 창백한 피부(#efd9c8): 200년 어둠 적응. 원본 Skin 재질은 검정(0.013)으로 저장되어 있어 반드시 교체한다.
  - 크고 어두운 눈동자: 머리 앞에 구체 2쌍(흰자+동공)을 Head 뼈에 본 페어런팅 → 애니메이션을 따라간다.
  - 역할 색: data/roles.json 의 visual.body / visual.accent 를 옷 재질(Shirt/Clothes/Main/Jacket…)에 입힌다.
  - 소품은 원시 도형으로 만들어 뼈(Head/Neck/Torso/Hips/UpperArm.L/Fist.R/Fist.L)에 붙인다.

좌표 규약
  - Quaternius 원본 정면 = -Y. GLB는 Blender -Y → glTF +Z 이므로 Three.js 기준 "정면 +Z".
  - 리그 기준점(원본 스케일, 키 ≈3.08 유닛): Head 뼈 시작 z=2.117, 머리 꼭대기 +0.96,
    얼굴 앞면 y ≈ -0.53, 머리 반지름 ≈ 0.49, Fist 는 (±0.50, -0.06, 0.89), Torso 1.507, Hips 0.896.
  - 스프라이트: dl = -90°(정면 왼쪽, 카메라 쪽), ul = 180°(뒷모습). 기존 치비(blender_chars.py) 방위와 동일.
  - 발 z=0, 키 1.6m 정규화(아이 1.2m).
"""
import bpy, sys, os, math, json, glob
from mathutils import Vector, Matrix, Euler
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
ONLY = [a for a in argv[1:] if not a.startswith("--")]
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
BLENDS = glob.glob(os.path.join(ROOT, "assets3d", "quaternius_chars", "*", "Blends"))[0]
OUT_GLB = os.path.join(ROOT, "static", "models", "chars")
OUT_PNG = os.path.join(ROOT, "static", "art", "chars")
OUT_RAW = os.path.join(ROOT, "art_raw", "chars_v2")
OUT_SHOW = os.path.join(ROOT, "static", "art", "chars", "show")
for d in (OUT_GLB, OUT_PNG, OUT_RAW, OUT_SHOW):
    os.makedirs(d, exist_ok=True)
ROLES = json.load(open(os.path.join(ROOT, "data", "roles.json"), encoding="utf-8"))

KEEP_ACTIONS = ["Idle", "Walk", "Run", "PickUp", "SitDown", "StandUp", "Death"]
SKIN = "#efd9c8"       # 창백한 살색
FACE = "#f6e6d8"       # 얼굴은 한 톤 더 창백
EYE = "#17120f"        # 크고 어두운 눈동자
DARK = "#2a2622"
METAL = "#8c9299"
RES, ORTHO, AZ, EL = 256, 2.2, 45, 32
sc = None
LOWPOLY = False        # 각인 파츠를 만들 때만 True — 원시 도형 분할을 줄여 GLB 용량을 아낀다


def hexcol(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def mat(name, hexc, rough=0.85, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs["Base Color"].default_value = (*hexcol(hexc), 1)
    b.inputs["Roughness"].default_value = rough
    try: b.inputs["Metallic"].default_value = metal
    except Exception: pass
    return m


def set_mat_color(m, hexc):
    if not m or not m.use_nodes: return
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b: b.inputs["Base Color"].default_value = (*hexcol(hexc), 1)


# ---------------------------------------------------------------- 역할 정의
# mats: 원본 재질 이름(접미사 .001 제거 후) → 색. "$body"/"$accent"는 roles.json 값으로 치환.
# eye_y: 얼굴 앞면 y (머리카락 앞머리가 긴 베이스는 더 앞으로).
ROLE_DEF = {
    "scout":    dict(blend="BlueSoldier_Male",    h=1.60, eye_y=-0.50,
                     mats={"Main": "$body", "Black": "#22201d", "Grey": "#4a5140", "Helmet": "$body"}),
    "cook":     dict(blend="Chef_Hat",            h=1.60, eye_y=-0.48,
                     mats={"Clothes": "$accent", "DarkClothes": "$body", "Band": "$body",
                           "Hat": "$accent", "Moustache": "#4a3a2c"}),
    "medic":    dict(blend="Doctor_Female_Young", h=1.58, eye_y=-0.60,
                     mats={"Main": "$body", "Black": "#2c2a28", "Brown": "$body", "Hair": "#6b4a33"}),
    "engineer": dict(blend="Casual2_Male",        h=1.62, eye_y=-0.48,
                     mats={"Shirt": "$body", "Pants": "#5a554b", "Belt": "$accent", "Hair": "#2e2823"}),
    "farmer":   dict(blend="Cowboy_Male",         h=1.60, eye_y=-0.54,
                     mats={"Jacket": "$body", "Top": "$accent", "Scarf": "#9c8a4a", "Pants": "#4a4032",
                           "HatBrown": "#c8ab62", "HatLightBrown": "#e6cd8c", "Hair": "#4a3a28"}),
    "scholar":  dict(blend="Casual_Female",       h=1.56, eye_y=-0.60,
                     mats={"Shirt": "$body", "Pants": "#3c3442", "Belt": "$accent", "Hair": "#2b2430"}),
    "trader":   dict(blend="Casual3_Male",        h=1.62, eye_y=-0.50,
                     mats={"Shirt": "$body", "Pants": "#3a2f2a", "Belt": "#1d1b19", "Hair": "#2a221d"}),
    "kid":      dict(blend="Casual_Bald",         h=1.20, eye_y=-0.48,
                     mats={"Shirt": "$body", "Pants": "$accent", "Belt": "#7a5f2a", "Hair": "#3a2f26"}),
}


# ---------------------------------------------------------------- 원시 도형 + 본 페어런팅
def attach(o, arm, bone, world):
    """뼈에 부모로 붙이되, 지금 포즈에서의 월드 트랜스폼이 world 가 되도록 로컬을 역산한다."""
    o.parent = arm; o.parent_type = 'BONE'; o.parent_bone = bone
    o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    pb = arm.pose.bones[bone]
    blen = arm.data.bones[bone].length
    parent_m = arm.matrix_world @ pb.matrix @ Matrix.Translation(Vector((0, blen, 0)))
    o.matrix_basis = parent_m.inverted() @ world
    return o


def _finish(o, m, arm, bone, world):
    o.data.materials.append(m)
    return attach(o, arm, bone, world)


def T(pos, rot=(0, 0, 0), scale=(1, 1, 1)):
    return (Matrix.Translation(Vector(pos)) @
            Euler(rot, 'XYZ').to_matrix().to_4x4() @
            Matrix.Diagonal(Vector(scale).to_4d()))


def box(arm, bone, m, pos, size, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    return _finish(bpy.context.object, m, arm, bone, T(pos, rot, size))


def ball(arm, bone, m, pos, size, rot=(0, 0, 0)):
    seg, rng = (10, 6) if LOWPOLY else (18, 10)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=seg, ring_count=rng, location=(0, 0, 0))
    return _finish(bpy.context.object, m, arm, bone, T(pos, rot, size))


def tube(arm, bone, m, pos, r, h, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=8 if LOWPOLY else 16, location=(0, 0, 0))
    return _finish(bpy.context.object, m, arm, bone, T(pos, rot))


def cone(arm, bone, m, pos, r1, r2, h, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=h, vertices=8 if LOWPOLY else 18, location=(0, 0, 0))
    return _finish(bpy.context.object, m, arm, bone, T(pos, rot))


def ring(arm, bone, m, pos, r, thick, rot=(0, 0, 0)):
    mj, mi = (12, 6) if LOWPOLY else (20, 8)
    bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=thick,
                                     major_segments=mj, minor_segments=mi, location=(0, 0, 0))
    return _finish(bpy.context.object, m, arm, bone, T(pos, rot))


def bone_pos(arm, name):
    return (arm.matrix_world @ arm.pose.bones[name].matrix).translation.copy()


# ---------------------------------------------------------------- 소품
def build_props(role, arm):
    v = ROLES[role]["visual"]
    body, acc = v["body"], v["accent"]
    mb, ma = mat("prop_body", body), mat("prop_acc", acc)
    md, mm = mat("prop_dark", DARK, 0.6), mat("prop_metal", METAL, 0.35, 0.7)
    hd = bone_pos(arm, "Head"); nk = bone_pos(arm, "Neck")
    fl, fr = bone_pos(arm, "Fist.L"), bone_pos(arm, "Fist.R")
    ua = bone_pos(arm, "UpperArm.L")
    to = bone_pos(arm, "Torso"); hi = bone_pos(arm, "Hips")
    out = []

    # --- 공통: 크고 어두운 눈동자 -------------------------------------------
    me_, mw = mat("eye", EYE, 0.25), mat("eye_white", "#f4eee4", 0.45)
    ey = ROLE_DEF[role].get("eye_y", -0.50)
    ez = hd.z + 0.50
    for sx in (1, -1):
        out.append(ball(arm, "Head", mw, (hd.x + sx * 0.205, hd.y + ey + 0.02, ez), (0.30, 0.24, 0.34)))
        out.append(ball(arm, "Head", me_, (hd.x + sx * 0.205, hd.y + ey - 0.05, ez - 0.01), (0.19, 0.16, 0.22)))

    if role == "scout":
        # 큰 배낭(실루엣) + 이마 고글 + 목에 건 쌍안경
        out.append(box(arm, "Torso", md, (to.x, to.y + 0.54, to.z + 0.34), (0.90, 0.48, 1.04)))
        out.append(box(arm, "Torso", mb, (to.x, to.y + 0.79, to.z + 0.44), (0.66, 0.14, 0.42)))
        out.append(tube(arm, "Torso", mb, (to.x, to.y + 0.66, to.z + 0.98), 0.15, 0.52, rot=(0, math.radians(90), 0)))
        for sx in (-0.30, 0.30):   # 어깨 멜빵
            out.append(box(arm, "Torso", mb, (to.x + sx, to.y - 0.24, to.z + 0.50), (0.16, 0.14, 0.72)))
        out.append(box(arm, "Head", md, (hd.x, hd.y - 0.24, hd.z + 0.80), (1.02, 0.34, 0.24)))
        for sx in (1, -1):
            out.append(tube(arm, "Head", mat("lens_s", "#9ec24f", 0.25),
                            (hd.x + sx * 0.23, hd.y - 0.44, hd.z + 0.80), 0.125, 0.10, rot=(math.radians(90), 0, 0)))
        out.append(box(arm, "Torso", md, (to.x, to.y - 0.36, to.z + 0.46), (0.36, 0.20, 0.18)))

    elif role == "cook":
        # 원본 Chef_Hat(높은 요리모자) + 주황 두건 + 냄비
        out.append(ring(arm, "Head", mb, (hd.x, hd.y, hd.z + 0.88), 0.47, 0.085))
        out.append(box(arm, "Head", mb, (hd.x + 0.42, hd.y + 0.16, hd.z + 0.84), (0.26, 0.34, 0.18), rot=(0, 0, math.radians(-25))))
        p = fr + Vector((-0.02, -0.14, -0.34))
        out.append(tube(arm, "Fist.R", mm, (p.x, p.y, p.z), 0.34, 0.34))
        out.append(ring(arm, "Fist.R", mm, (p.x, p.y, p.z + 0.17), 0.34, 0.04))
        out.append(box(arm, "Fist.R", md, (p.x - 0.46, p.y, p.z + 0.02), (0.34, 0.10, 0.10)))
        out.append(tube(arm, "Fist.R", mat("stew", "#c97b3a", 0.4), (p.x, p.y, p.z + 0.16), 0.30, 0.02))

    elif role == "medic":
        # 가슴의 큰 붉은 십자 + 완장 + 약가방 + 턱에 걸친 마스크(하얀 부족)
        for fy, sgn in ((-0.42, 1), (0.40, -1)):   # 앞·뒤 양쪽에 붉은 십자
            out.append(box(arm, "Torso", ma, (to.x, to.y + fy, to.z + 0.24), (0.26, 0.10, 0.78)))
            out.append(box(arm, "Torso", ma, (to.x, to.y + fy, to.z + 0.24), (0.72, 0.10, 0.26)))
        out.append(ring(arm, "UpperArm.L", ma, (ua.x + 0.05, ua.y - 0.02, ua.z - 0.30), 0.155, 0.05))
        bg = hi + Vector((0.44, 0.18, 0.04))
        out.append(box(arm, "Hips", mat("bag", "#3f5a3a", 0.9), (bg.x, bg.y, bg.z), (0.46, 0.28, 0.38)))
        out.append(box(arm, "Hips", ma, (bg.x - 0.15, bg.y, bg.z), (0.18, 0.32, 0.10)))
        out.append(box(arm, "Hips", ma, (bg.x - 0.15, bg.y, bg.z), (0.18, 0.10, 0.24)))
        out.append(box(arm, "Head", mat("mask", "#f2ece2", 0.9), (hd.x, hd.y - 0.50, hd.z + 0.19), (0.62, 0.22, 0.26)))

    elif role == "engineer":
        # 시안 고글 + 공구벨트 + 큰 렌치
        out.append(box(arm, "Head", md, (hd.x, hd.y - 0.22, hd.z + 0.62), (1.02, 0.36, 0.28)))
        for sx in (1, -1):
            out.append(tube(arm, "Head", mat("lens_e", acc, 0.15),
                            (hd.x + sx * 0.24, hd.y - 0.43, hd.z + 0.62), 0.145, 0.10, rot=(math.radians(90), 0, 0)))
        out.append(ring(arm, "Hips", md, (hi.x, hi.y - 0.02, hi.z + 0.34), 0.44, 0.08))
        for sx in (-0.26, 0.26):
            out.append(box(arm, "Hips", mm, (hi.x + sx, hi.y - 0.38, hi.z + 0.20), (0.12, 0.12, 0.34)))
        # 밝은 금속 렌치(어두운 몸과 대비)
        mwr = mat("wrench", "#d2d9de", 0.45, 0.1)
        p = fr + Vector((0.14, -0.22, -0.26))
        out.append(box(arm, "Fist.R", mwr, (p.x, p.y, p.z), (0.17, 0.17, 0.70)))
        out.append(box(arm, "Fist.R", mwr, (p.x, p.y, p.z - 0.41), (0.48, 0.19, 0.22)))
        out.append(box(arm, "Fist.R", mat("wr_gap", "#1b1917"), (p.x, p.y - 0.10, p.z - 0.45), (0.19, 0.19, 0.18)))
        # 등의 시안 배터리 팩 (전력 = 불꽃 부족의 빚)
        out.append(box(arm, "Torso", md, (to.x, to.y + 0.44, to.z + 0.36), (0.62, 0.32, 0.66)))
        out.append(box(arm, "Torso", mat("cell", acc, 0.2), (to.x, to.y + 0.61, to.z + 0.36), (0.42, 0.06, 0.44)))
        out.append(box(arm, "Torso", mat("cell2", acc, 0.2), (to.x + 0.30, to.y - 0.30, to.z + 0.46), (0.16, 0.12, 0.40)))

    elif role == "farmer":
        # 넓은 밀짚모자(실루엣) + 물뿌리개
        out.append(cone(arm, "Head", mat("straw", "#e6cd8c", 0.95), (hd.x, hd.y, hd.z + 0.86), 0.98, 0.50, 0.13))
        out.append(cone(arm, "Head", mat("straw2", "#d8bd76", 0.95), (hd.x, hd.y, hd.z + 1.02), 0.48, 0.34, 0.22))
        out.append(ring(arm, "Head", ma, (hd.x, hd.y, hd.z + 0.94), 0.46, 0.055))
        p = fr + Vector((0.0, -0.12, -0.36))
        mcan = mat("can", acc, 0.5)
        out.append(tube(arm, "Fist.R", mcan, (p.x, p.y, p.z), 0.28, 0.44))
        out.append(tube(arm, "Fist.R", mcan, (p.x + 0.34, p.y, p.z + 0.16), 0.075, 0.46, rot=(0, math.radians(58), 0)))
        out.append(cone(arm, "Fist.R", mcan, (p.x + 0.50, p.y, p.z + 0.32), 0.075, 0.17, 0.13, rot=(0, math.radians(58), 0)))
        out.append(ring(arm, "Fist.R", mcan, (p.x - 0.14, p.y, p.z + 0.28), 0.20, 0.04, rot=(0, math.radians(90), 0)))

    elif role == "scholar":
        # 둥근 안경 + 가슴에 안은 노란 책
        for sx in (1, -1):
            out.append(ring(arm, "Head", md, (hd.x + sx * 0.19, hd.y - 0.56, hd.z + 0.50), 0.175, 0.038, rot=(math.radians(90), 0, 0)))
        out.append(box(arm, "Head", md, (hd.x, hd.y - 0.56, hd.z + 0.50), (0.18, 0.06, 0.05)))
        for sx in (1, -1):
            out.append(box(arm, "Head", md, (hd.x + sx * 0.36, hd.y - 0.34, hd.z + 0.50), (0.07, 0.44, 0.05)))
        bk = Vector((to.x + 0.02, to.y - 0.42, to.z + 0.18))
        out.append(box(arm, "Torso", mat("book", acc, 0.7), (bk.x, bk.y, bk.z), (0.62, 0.20, 0.74), rot=(math.radians(14), 0, 0)))
        out.append(box(arm, "Torso", mat("page", "#f1e6cf", 0.95), (bk.x, bk.y - 0.06, bk.z), (0.52, 0.14, 0.64), rot=(math.radians(14), 0, 0)))
        out.append(box(arm, "Torso", mat("ribbon", "#8f5a9c", 0.9), (bk.x, bk.y - 0.13, bk.z - 0.22), (0.07, 0.04, 0.34)))

    elif role == "trader":
        # 챙 넓은 검은 모자 + 붉은 스카프 + 저울 주머니
        mh = mat("hat", "#1d1b19", 0.75)
        out.append(cone(arm, "Head", mh, (hd.x, hd.y, hd.z + 0.90), 0.86, 0.46, 0.11))
        out.append(tube(arm, "Head", mh, (hd.x, hd.y, hd.z + 1.12), 0.42, 0.40))
        out.append(ring(arm, "Head", mat("hatb", "#7a2f26", 0.9), (hd.x, hd.y, hd.z + 0.98), 0.43, 0.05))
        msc = mat("scarf", "#B03A2E", 0.95)
        out.append(ring(arm, "Neck", msc, (nk.x, nk.y + 0.02, nk.z + 0.02), 0.36, 0.12))
        out.append(box(arm, "Torso", msc, (to.x + 0.16, to.y - 0.34, to.z + 0.26), (0.24, 0.12, 0.60), rot=(0, math.radians(-10), 0)))
        out.append(box(arm, "Hips", mat("pouch", acc, 0.9), (hi.x - 0.46, hi.y + 0.06, hi.z + 0.10), (0.28, 0.26, 0.32)))
        out.append(tube(arm, "Hips", mm, (hi.x - 0.46, hi.y + 0.06, hi.z + 0.30), 0.09, 0.06))

    elif role == "kid":
        # 노란 우비 후드(뒤로 젖혀 눈은 보이게) + 작은 가방 + 돌멩이
        mr = mat("raincoat", body, 0.55)
        out.append(ball(arm, "Head", mr, (hd.x, hd.y + 0.22, hd.z + 0.56), (1.16, 1.12, 1.16)))
        out.append(cone(arm, "Head", mr, (hd.x, hd.y - 0.30, hd.z + 0.84), 0.52, 0.30, 0.14, rot=(math.radians(16), 0, 0)))
        out.append(box(arm, "Torso", mat("satchel", acc, 0.8), (to.x - 0.40, to.y + 0.16, to.z + 0.14), (0.38, 0.26, 0.34)))
        out.append(box(arm, "Torso", mat("strap", acc, 0.8), (to.x, to.y - 0.30, to.z + 0.42), (0.78, 0.14, 0.12), rot=(0, math.radians(32), 0)))
        p = fr + Vector((0.0, -0.10, -0.24))
        out.append(ball(arm, "Fist.R", mat("stone", "#8a8278", 0.95), (p.x, p.y, p.z), (0.26, 0.26, 0.24)))

    return out


# ---------------------------------------------------------------- 각인(刻印) 외형 파츠
# data/imprints.json 의 id 8종과 1:1. 노드 이름 규약: **imp_<id>** (빈 오브젝트) + 그 자식 메시들.
# 기본 hidden 으로 만들지만 glTF 2.0 에는 표준 가시성 필드가 없고 Blender 5.2 내보내기도
# KHR_node_visibility 를 쓰지 않는다(직접 확인). 따라서 런타임에 개발이 노드 이름으로 끈다.
# C4: 부위를 정해 겹치지 않게 — 얼굴(왼뺨=반점 / 오른뺨=흉터) · 머리(뒤=베일 / 정수리=젖은 머리)
#     · 목(이빨 목걸이) · 허리(허리띠 유물) · 팔(검은 팔띠) · 손목(놋쇠 팔찌) · 등(방망이) · 팔뚝(그을림)
IMPRINT_IDS = ["spore_mark", "empty_stomach", "warden", "sun_memory",
               "empty_seat", "footprint", "debt_paid", "water_memory"]


def imp_root(arm, bone, iid):
    bpy.ops.object.empty_add(type='PLAIN_AXES', radius=0.15, location=(0, 0, 0))
    e = bpy.context.object
    e.name = "imp_" + iid
    e.empty_display_size = 0.15
    attach(e, arm, bone, Matrix.Identity(4))
    bpy.context.view_layer.update()
    return e


def regroup(objs, e, iid):
    """뼈에 붙여 만든 파츠들을 월드 위치를 유지한 채 imp_ 빈 오브젝트의 자식으로 옮긴다.
    → GLB 에 `imp_<id>` 노드 하나만 끄면 그 각인 전체가 사라진다."""
    bpy.context.view_layer.update()
    for i, o in enumerate(objs):
        w = o.matrix_world.copy()
        o.parent = e; o.parent_type = 'OBJECT'; o.parent_bone = ''
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = e.matrix_world.inverted() @ w
        o.name = "imp_%s_%d" % (iid, i)
    bpy.context.view_layer.update()


def build_imprints(role, arm):
    """각인 8종을 만들어 [(id, 빈오브젝트, [파츠…])] 로 돌려준다. 전부 기본 hidden."""
    global LOWPOLY
    LOWPOLY = True
    hd = bone_pos(arm, "Head"); nk = bone_pos(arm, "Neck")
    to = bone_pos(arm, "Torso"); hi = bone_pos(arm, "Hips")
    ua = bone_pos(arm, "UpperArm.L"); fr = bone_pos(arm, "Fist.R")
    la = bone_pos(arm, "LowerArm.L"); ra = bone_pos(arm, "LowerArm.R")
    ey = ROLE_DEF[role].get("eye_y", -0.50)
    fy = hd.y + ey            # 얼굴 앞면
    ez = hd.z + 0.50          # 눈 높이
    out = []
    # 머리를 구로 근사해 표면에 딱 붙는 좌표를 구한다(반점·흉터가 머리 안에 파묻히지 않게)
    HC = Vector((hd.x, hd.y, hd.z + 0.42)); HR = 0.52

    def on_head(dx, dy, dz, k=0.97):
        v = Vector((dx, dy, dz)); v.normalize()
        p = HC + v * (HR * k)
        return (p.x, p.y, p.z)

    def grp(iid, bone, make):
        e = imp_root(arm, bone, iid)
        parts = make()
        regroup(parts, e, iid)
        for o in [e] + parts:
            o.hide_viewport = True; o.hide_render = True
        out.append((iid, e, parts))

    # 1. 포자의 표식 — 얼굴(왼뺨·턱선)과 목덜미의 녹색 반점
    def _spore():
        g1 = mat("imp_spore_a", "#7CA04A", 0.8); g2 = mat("imp_spore_b", "#5E8236", 0.8)
        return [ball(arm, "Head", g1, on_head(0.62, -0.72, 0.22), (0.19, 0.19, 0.17)),
                ball(arm, "Head", g2, on_head(0.92, -0.34, -0.22), (0.16, 0.16, 0.14)),
                ball(arm, "Head", g1, on_head(0.44, -0.80, -0.36), (0.13, 0.13, 0.12)),
                ball(arm, "Head", g2, on_head(0.86, -0.20, -0.66), (0.12, 0.12, 0.11)),
                ball(arm, "Neck", g2, (nk.x + 0.150, nk.y + 0.05, nk.z + 0.02), (0.13, 0.12, 0.14))]

    # 2. 빈 위장 — 허리띠 유물(놋쇠 버클 + 매달린 금속 표찰)
    def _stomach():
        lea = mat("imp_belt", "#6B5334", 0.85); brs = mat("imp_buckle", "#B98A3C", 0.35, 0.6)
        return [ring(arm, "Hips", lea, (hi.x, hi.y - 0.02, hi.z + 0.22), 0.455, 0.045),
                box(arm, "Hips", brs, (hi.x, hi.y - 0.47, hi.z + 0.22), (0.17, 0.10, 0.17)),
                box(arm, "Hips", brs, (hi.x + 0.16, hi.y - 0.45, hi.z + 0.02), (0.11, 0.05, 0.22)),
                box(arm, "Hips", lea, (hi.x + 0.16, hi.y - 0.45, hi.z + 0.15), (0.05, 0.04, 0.10))]

    # 3. 지킨 자 — 오른뺨 흉터 + 등 뒤 방망이
    def _warden():
        sc_ = mat("imp_scar", "#C2836C", 0.6); wd = mat("imp_club", "#5A4632", 0.9)
        bd = mat("imp_clubband", "#3A3129", 0.8)
        return [box(arm, "Head", sc_, on_head(-0.66, -0.70, 0.20), (0.08, 0.10, 0.36),
                    rot=(0, math.radians(-16), 0)),
                box(arm, "Head", sc_, on_head(-0.90, -0.36, -0.22), (0.08, 0.10, 0.20),
                    rot=(0, math.radians(-16), 0)),
                tube(arm, "Torso", wd, (to.x + 0.17, to.y + 0.31, to.z + 0.26), 0.070, 0.98,
                     rot=(math.radians(14), 0, math.radians(26))),
                tube(arm, "Torso", wd, (to.x + 0.40, to.y + 0.37, to.z + 0.66), 0.110, 0.28,
                     rot=(math.radians(14), 0, math.radians(26))),
                ring(arm, "Torso", bd, (to.x + 0.05, to.y + 0.27, to.z - 0.02), 0.085, 0.030,
                     rot=(math.radians(14), 0, math.radians(26)))]

    # 4. 햇빛의 기억 — 이마 띠 + 뒤로 늘어진 베일 + 팔뚝의 그을림
    def _sun():
        ln = mat("imp_veil", "#DCCFB2", 0.95); ln2 = mat("imp_veil2", "#C9BC9C", 0.95)
        tan = mat("imp_tan", "#C9A183", 0.85)
        return [ring(arm, "Head", ln, (hd.x, hd.y, hd.z + 0.66), 0.475, 0.055),
                box(arm, "Head", ln, (hd.x, hd.y + 0.40, hd.z + 0.16), (0.74, 0.14, 0.88)),
                box(arm, "Head", ln2, (hd.x, hd.y + 0.34, hd.z - 0.26), (0.62, 0.13, 0.22),
                    rot=(math.radians(-14), 0, 0)),
                tube(arm, "LowerArm.L", tan, (la.x + 0.03, la.y - 0.02, la.z - 0.16), 0.115, 0.30),
                tube(arm, "LowerArm.R", tan, (ra.x - 0.03, ra.y - 0.02, ra.z - 0.16), 0.115, 0.30)]

    # 5. 빈 자리 — 왼쪽 위팔의 검은 팔띠 (의무병의 붉은 완장보다 어깨 쪽)
    def _seat():
        bk = mat("imp_armband", "#1A1817", 0.85)
        return [ring(arm, "UpperArm.L", bk, (ua.x + 0.03, ua.y - 0.02, ua.z - 0.09), 0.180, 0.058),
                box(arm, "UpperArm.L", bk, (ua.x + 0.19, ua.y - 0.02, ua.z - 0.09), (0.05, 0.16, 0.13))]

    # 6. 발자국 — 목의 이빨 목걸이 + 어깨의 찢긴 옷자락
    def _foot():
        cd = mat("imp_cord", "#4A4036", 0.95); th = mat("imp_tooth", "#E8E1CA", 0.55)
        tr = mat("imp_torn", "#2E2A25", 0.95)
        return [ring(arm, "Neck", cd, (nk.x, nk.y + 0.01, nk.z - 0.02), 0.305, 0.022),
                cone(arm, "Torso", th, (to.x, to.y - 0.50, to.z + 0.44), 0.105, 0.008, 0.34,
                     rot=(math.radians(180), 0, 0)),
                cone(arm, "Torso", th, (to.x + 0.20, to.y - 0.48, to.z + 0.48), 0.070, 0.006, 0.22,
                     rot=(math.radians(180), 0, math.radians(14))),
                cone(arm, "Torso", th, (to.x - 0.20, to.y - 0.48, to.z + 0.48), 0.070, 0.006, 0.22,
                     rot=(math.radians(180), 0, math.radians(-14))),
                box(arm, "Torso", tr, (to.x - 0.35, to.y - 0.12, to.z + 0.50), (0.24, 0.34, 0.11),
                    rot=(0, math.radians(26), 0))]

    # 7. 갚은 자 — 오른 손목의 놋쇠 팔찌
    def _debt():
        br = mat("imp_brass", "#C08A3A", 0.3, 0.7)
        return [ring(arm, "Fist.R", br, (fr.x, fr.y - 0.02, fr.z + 0.21), 0.160, 0.046),
                ring(arm, "Fist.R", br, (fr.x, fr.y - 0.02, fr.z + 0.13), 0.150, 0.030)]

    # 8. 물의 기억 — 젖은 머리(광택) + 밝아진 눈
    def _water():
        we = mat("imp_wethair", "#2A2520", 0.12); st = mat("imp_strand", "#332C26", 0.15)
        br = mat("imp_bright", "#BFEAF0", 0.05)
        parts = [ball(arm, "Head", we, (hd.x, hd.y + 0.03, hd.z + 0.58), (1.02, 1.00, 0.72))]
        for sx, off in ((1, 0.30), (-1, 0.32), (1, 0.12)):
            parts.append(box(arm, "Head", st, (hd.x + sx * off, hd.y - 0.28, hd.z + 0.50),
                             (0.09, 0.24, 0.46), rot=(math.radians(10), 0, 0)))
        for sx in (1, -1):
            parts.append(ball(arm, "Head", br, (hd.x + sx * 0.205, fy - 0.07, ez), (0.21, 0.13, 0.24)))
        return parts

    grp("spore_mark", "Head", _spore)
    grp("empty_stomach", "Hips", _stomach)
    grp("warden", "Head", _warden)
    grp("sun_memory", "Head", _sun)
    grp("empty_seat", "UpperArm.L", _seat)
    grp("footprint", "Neck", _foot)
    grp("debt_paid", "Fist.R", _debt)
    grp("water_memory", "Head", _water)
    LOWPOLY = False
    return out


# ---------------------------------------------------------------- 빌드
def load_base(blend):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(os.path.join(BLENDS, blend + ".blend"), link=False) as (src, dst):
        dst.objects = list(src.objects); dst.actions = list(src.actions)
    for o in dst.objects:
        if o is not None:
            try: bpy.context.collection.objects.link(o)
            except Exception: pass
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
    return arm, mesh


def assign_action(arm, act, t=0.0):
    if arm.animation_data is None: arm.animation_data_create()
    arm.animation_data.action = act
    try:
        if hasattr(arm.animation_data, "action_slot") and getattr(act, "slots", None) and len(act.slots):
            arm.animation_data.action_slot = act.slots[0]
    except Exception as e:
        print("slot warn", e, flush=True)
    f0, f1 = act.frame_range
    bpy.context.scene.frame_set(int(f0 + (f1 - f0) * t))
    bpy.context.view_layer.update()


def recolor(role, mesh):
    v = ROLES[role]["visual"]
    table = dict(ROLE_DEF[role]["mats"])
    for m in mesh.data.materials:
        if not m: continue
        key = m.name.split('.')[0]
        low = key.lower()
        if low == "skin":
            set_mat_color(m, SKIN)
        elif low == "face":
            set_mat_color(m, FACE)
        elif key in table:
            c = table[key]
            set_mat_color(m, v["body"] if c == "$body" else v["accent"] if c == "$accent" else c)


def evaluated_bounds(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        if o.type != 'MESH': continue
        ev = o.evaluated_get(dg)
        try: m = ev.to_mesh()
        except Exception: continue
        mw = o.matrix_world
        for vtx in m.vertices:
            pts.append(mw @ vtx.co)
        ev.to_mesh_clear()
    if not pts: return 0.0, 1.0
    return min(p.z for p in pts), max(p.z for p in pts)


def build(role, action_name="Idle", t=0.0, imprints=False):
    """역할 캐릭터 한 벌을 씬에 만들고 (arm, mesh, props, imps) 반환. 발 z=0 / 목표 키로 정규화.
    imprints=True 면 각인 파츠 8종(imp_<id>, 기본 hidden)을 함께 만든다."""
    global sc
    d = ROLE_DEF[role]
    arm, mesh = load_base(d["blend"])
    sc = bpy.context.scene
    recolor(role, mesh)
    act = next((a for a in bpy.data.actions if a.name == action_name), None)
    if act: assign_action(arm, act, t)
    props = build_props(role, arm)
    imps = build_imprints(role, arm) if imprints else []
    bpy.context.view_layer.update()
    # 키 정규화: 몸(모자 포함 원본 메시) 기준이 아니라 "머리 꼭대기"가 아닌 실제 몸 높이를 쓰면
    # 요리사 모자 때문에 다른 역할보다 작아지므로, 모자류를 뺀 순수 리그 높이(3.078)를 기준으로 한다.
    s = d["h"] / 3.078
    arm.scale = (s, s, s)
    arm.location = (0, 0, 0)
    bpy.context.view_layer.update()
    # 발 원점: 소품(렌치·물뿌리개 등)이 아래로 삐져나와도 "발"이 z=0 이 되도록 몸만 기준으로 한다
    lo, _ = evaluated_bounds([mesh])
    arm.location = (0, 0, -lo)
    bpy.context.view_layer.update()
    return arm, mesh, props, imps


# ---------------------------------------------------------------- GLB
def export_glb(role):
    arm, mesh, props, imps = build(role, "Idle", 0.0, imprints=True)
    lo, hi = evaluated_bounds([mesh])       # Idle 기준 실측(정규화 직후 상태)
    for a in list(bpy.data.actions):
        if a.name not in KEEP_ACTIONS:
            bpy.data.actions.remove(a)
    if arm.animation_data is None: arm.animation_data_create()
    # ★ NLA 트랙으로 밀어 넣지 않는다. 트랙을 만들면 뎁스그래프가 그것을 평가해 GLB 의 **기본 포즈**가
    #   마지막 트랙의 첫 프레임(Walk)으로 굳는다. export_animation_mode='ACTIONS' 는 파일 안의
    #   모든 액션을 각각 내보내므로 트랙이 필요 없고, 액션만 떼면 기본 포즈가 Idle 로 남는다.
    for tr in list(arm.animation_data.nla_tracks):
        arm.animation_data.nla_tracks.remove(tr)
    arm.animation_data.action = None
    path = os.path.join(OUT_GLB, role + ".glb")
    # use_visible/use_renderable=False → 기본 hidden 인 각인 파츠도 GLB 에 들어간다
    kw = dict(filepath=path, export_format='GLB', export_lights=False, export_cameras=False,
              export_apply=False, use_selection=False, use_visible=False, use_renderable=False,
              export_animations=True, export_yup=True,
              export_animation_mode='ACTIONS', export_nla_strips=False, export_frame_range=False,
              export_force_sampling=True)
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        for k in ('export_animation_mode', 'export_nla_strips', 'export_frame_range'):
            kw.pop(k, None)
        bpy.ops.export_scene.gltf(**kw)
    print("EXPORTED", path, os.path.getsize(path) // 1024, "KB",
          "clips", sorted(a.name for a in bpy.data.actions),
          "| body z %.4f..%.4f" % (lo, hi),
          "| imprints", len(imps), flush=True)


# ---------------------------------------------------------------- 스프라이트
def camera(look_z):
    az, el = math.radians(AZ), math.radians(EL); d = 20.0
    look = Vector((0, 0, look_z))
    loc = Vector((-math.cos(el) * math.sin(az) * d, -math.cos(el) * math.cos(az) * d, math.sin(el) * d)) + look
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.object
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = ORTHO
    cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam; return cam


def lights():
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 5),
                             rotation=(math.radians(45), math.radians(20), math.radians(-40)))
    s = bpy.context.object; s.data.energy = 2.2; s.data.color = (1.0, 0.92, 0.8)
    bpy.ops.object.light_add(type='AREA', location=(-4, -4, 4),
                             rotation=(math.radians(50), 0, math.radians(-45)))
    f = bpy.context.object; f.data.energy = 200; f.data.size = 8; f.data.color = (0.85, 0.9, 1.0)


def render(path):
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = sc.render.resolution_y = RES
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.render.use_freestyle = True; sc.render.line_thickness = 1.3
    fs = sc.view_layers[0].freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("c")
    ls.select_silhouette = True; ls.select_crease = True; ls.select_border = True
    if ls.linestyle is None: ls.linestyle = bpy.data.linestyles.new("cls")
    ls.linestyle.color = hexcol("#1a1714"); ls.linestyle.thickness = 1.3
    # AgX는 채도를 크게 죽인다 → 역할 색이 읽혀야 하므로 Standard 사용
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


# 프레임 규약(기존 치비와 동일): a = 다리 벌림(Walk 중간), b = 모음(Idle)
FRAMES = (("b", "Idle", 0.0), ("a", "Walk", 0.25))


def sprites(role, meta=None):
    for tag, deg in (("dl", -90), ("ul", 180)):
        for frame, act, t in FRAMES:
            arm, mesh, props, _imps = build(role, act, t)
            arm.rotation_euler = (0, 0, math.radians(deg))
            bpy.context.view_layer.update()
            cam = camera(0.80); lights()
            out = os.path.join(OUT_PNG, f"{role}_{tag}_{frame}.png")
            render(out)
            render(os.path.join(OUT_RAW, f"{role}_{tag}_{frame}.png"))
            if meta is not None:
                f = world_to_camera_view(sc, cam, Vector((0, 0, 0)))   # 발(원점)의 픽셀 위치
                meta[f"{role}_{tag}"] = {"foot": [round(f.x * RES, 1), round((1 - f.y) * RES, 1)],
                                         "res": RES, "ortho": ORTHO, "h": ROLE_DEF[role]["h"]}
            print("RENDERED", out, flush=True)


# ---------------------------------------------------------------- 각인 파츠 쇼케이스 렌더
# (ortho, look_z) — 얼굴/머리 각인은 머리 클로즈업, 몸 각인은 상반신, 3개 겹침은 전신.
# (ortho, look_z, 방위°) — 오른뺨 흉터·오른 손목 팔찌는 몸의 -X 쪽이라 0°(정면+오른쪽)에서 봐야 보인다.
# 정규화 후 실제 높이(1.6m 기준): 눈 1.36 · 목 1.03 · 가슴 1.01 · 위팔 0.90 · 허리띠 0.58 · 손목 0.57
IMP_SHOT = {
    "spore_mark":    (0.72, 1.34, -90), "warden":        (1.25, 1.15, 0),
    "sun_memory":    (1.20, 1.18, -90), "water_memory":  (0.72, 1.36, -90),
    "footprint":     (0.85, 1.04, -90), "empty_seat":    (0.80, 0.93, -90),
    "empty_stomach": (0.85, 0.60, -90), "debt_paid":     (0.55, 0.58, 0),
}
IMP_TRIPLE = ["warden", "footprint", "empty_stomach"]


def imp_shots(role="cook"):
    """각인 파츠를 하나씩 켜서 렌더. 기본은 요리사(흰 옷 = 파츠가 가장 잘 보인다)."""
    jobs = [(i, IMP_SHOT[i][0], IMP_SHOT[i][1], IMP_SHOT[i][2], [i]) for i in IMPRINT_IDS]
    jobs.append(("triple", 2.05, 0.95, -90, IMP_TRIPLE))
    jobs.append(("none", 2.05, 0.95, -90, []))
    for tag, ortho, lz, deg, show in jobs:
        arm, mesh, props, imps = build(role, "Idle", 0.0, imprints=True)
        for iid, e, parts in imps:
            vis = iid in show
            for o in [e] + parts:
                o.hide_viewport = not vis; o.hide_render = not vis
        arm.rotation_euler = (0, 0, math.radians(deg))
        bpy.context.view_layer.update()
        camera(lz); sc.camera.data.ortho_scale = ortho; lights()
        out = os.path.join(OUT_SHOW, "imp_%s.png" % tag)
        render(out); print("RENDERED", out, flush=True)


if __name__ == "__main__":
    if MODE == "imp":
        RES = 480
        imp_shots(ONLY[0] if ONLY else "cook")
        print("ALL DONE", flush=True)
        raise SystemExit
    roles = ONLY or list(ROLE_DEF.keys())
    meta = {}
    for r in roles:
        if MODE in ("glb", "all"):
            export_glb(r)
        if MODE in ("sprites", "all"):
            sprites(r, meta)
    if meta:
        mp = os.path.join(OUT_PNG, "chars_meta.json")
        old = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
        old.update(meta)
        json.dump(old, open(mp, "w", encoding="utf-8"), indent=1)
        print("META", mp, flush=True)
    print("ALL DONE", flush=True)
