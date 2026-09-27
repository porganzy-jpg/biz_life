# -*- coding: utf-8 -*-
"""
잔해 방주 — 1막 「정면 평면 단면」용 2D 캐릭터 스프라이트 시험 (S4-C)

  1) 렌더 (Blender 안에서)
     "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --python tools/render_sprites.py -- render
     "...blender.exe" -b --python tools/render_sprites.py -- render scout cook      # 일부 역할만

  1-b) 비율 보정판 렌더 (S5-C 「더 귀엽게」 — PLAYER_JOURNEY §5-3)
     "...blender.exe" -b --python tools/render_sprites.py -- cute            # 대표 4역할 + 문어
     "...blender.exe" -b --python tools/render_sprites.py -- cute scout      # 일부만

  2) 후처리 (맨 파이썬, Pillow + numpy)
     python tools/render_sprites.py post            # a/b 전체
     python tools/render_sprites.py post --cute     # 비율 보정판(c)만

왜 새로 그리지 않고 3D에서 뽑는가 (07 §3-4 일관성 함정)
  · 8역할 GLB(static/models/chars/*.glb)가 이미 같은 골격·같은 재질 규약으로 서 있다.
    여기서 정면 직교로 뽑으면 8역할 일관성이 "공짜로" 완벽하다.
  · 각인 조합은 imp_<id> 노드만 켜고 다시 렌더하면 된다. 생성 AI로는 이 조합 폭발을 감당할 수 없다.
  · 애니메이션 프레임도 공짜다.
  생성 AI는 한 점도 쓰지 않는다.

시점 규약 (기존 dl/ul 아이소 방위와 다르다 — 그래서 새 폴더다)
  · 카메라: 정면 직교. (0, -20, look_z) 에서 +Y 를 본다. Quaternius 원본 정면이 -Y 이므로 방위 0° = 정면.
  · 화면 가로 = +X, 세로 = +Z. blender_section.py 의 거점 화면 기저와 동일하다.
  · 발 원점 유지: Idle 0프레임에서 발바닥 z=0 으로 정규화한 뒤 그 오프셋을 전 클립에 고정한다.
    (걷는 중에 발이 뜨는 것은 애니메이션이 맞다. 기준선은 Idle 이다.)
  · 셀 256px, PPM(미터당 픽셀) 110 고정, 발 기준선 = 셀 아래에서 16px 째 (y=240).
    PPM 이 고정이므로 아이(1.20m)는 어른(1.60m)보다 실제로 작게 나온다 = chars_meta.json 규약 유지.

두 가지 후처리 (이번 태스크의 핵심)
  A안 "렌더 그대로"  : 지금 static/art/chars/*_dl_a.png 계열 톤. 부드러운 음영 + 옅은 외곽선.
  B안 "납작한 그림체": 음영 3단 포스터화 + 어두운 굵은 외곽선 + 채도/대비 상승.
                      근거는 단면 화면의 실제 배경이다 — 방 뒷벽은 밝고(#e4ce9a) 바닥·구석은 어둡다(#1a180d).
                      한 스프라이트가 그 둘 위에 동시에 놓인다. 어두운 외곽선이 밝은 벽을 끊고,
                      올린 명부(明部)가 어두운 바닥에서 뜬다. 한쪽만 손보면 다른 쪽에서 묻힌다.
"""
import sys, os, math, json

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
MODE = argv[0] if argv else "render"
FOLK = MODE == "folk"
CUTE_MODE = MODE == "cute"          # S5-C: 비율 보정판(3등신). 화풍은 folk 그대로 쓴다
if FOLK or CUTE_MODE: MODE = "render"
ONLY = [a for a in argv[1:] if not a.startswith("-")]

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "art_raw", "chars_front")
RAWF = os.path.join(ROOT, "art_raw", "chars_folk")
RAWC = os.path.join(ROOT, "art_raw", "chars_cute")
OUT = os.path.join(ROOT, "static", "art", "chars", "front")

# ── 시트 규약 ────────────────────────────────────────────────
CELL = 256          # 셀 한 변
PPM = 110.0         # 미터당 픽셀 (전 역할 공통 — 키 비율이 화면에 그대로 남는다)
BASE_Y = 240        # 발 기준선 (셀 위에서 240px 째)
NFRAME = 5          # 클립당 프레임
# (클립, 샘플 시작 t, 끝 t, 순환 여부)
#   ★ PickUp 을 0~100% 로 뽑으면 정면 단면에서 죽는다. 캐릭터가 카메라 쪽으로 완전히 접히면서
#     얼굴이 사라지고 등짐만 남은 덩어리가 된다(1회차 렌더에서 직접 확인, docs/reports/char_S4.md §4).
#     평면 단면은 깊이 방향 동작을 읽지 못한다 — 폴아웃 셸터 주민이 늘 좌우로만 움직이는 이유다.
#     그래서 읽히는 구간(0~22%, "아래로 손을 뻗는다")만 쓴다. 제대로 된 일하는 모션은
#     좌우·상하로 새로 만들어야 한다(스프린트 5 후보).
CLIP_SPEC = [("Idle", 0.00, 1.00, True), ("Walk", 0.00, 1.00, True), ("PickUp", 0.00, 0.22, False)]
CLIPS = [c[0] for c in CLIP_SPEC]       # 3종. 세 번째 = 일하는 포즈 (04 C7)
# 비율 보정판은 머리가 1.26배라 같은 22% 에서도 정수리가 훨씬 크게 보인다.
#   (22% 는 보정 전에도 아슬아슬했다 — 아이의 PickUp 4프레임은 b 에서 이미 얼굴이 사라진다)
#   그래서 보정판만 15% 까지 쓰고, 턱을 들어 얼굴을 카메라로 되돌린다.
CLIP_SPEC_CUTE = [("Idle", 0.00, 1.00, True), ("Walk", 0.00, 1.00, True),
                  ("PickUp", 0.00, 0.18, False)]
IMP_TRIPLE = ["warden", "footprint", "empty_stomach"]   # 각인 3개 겹침 예시
IMP_ROLES = ["cook", "scout"]           # 밝은 옷 / 어두운 옷 각각 하나
ROLE_ORDER = ["scout", "cook", "medic", "engineer", "farmer", "scholar", "trader", "kid"]
# 대표 캐릭터 4종 — PM 지정. 각각 이 게임의 한 장면을 대표한다.
HERO = ["scout", "medic", "kid", "engineer"]

# ── 평면 민속화풍 팔레트 (REF_ART_FLAT_FOLK §5) ────────────────
#   (밝은 면, 그림자) 두 값뿐. 청록·남색은 없다 — 물에만 쓰고 사람에게는 쓰지 않는다.
FOLK_PALETTE = {
    "cream":    ("#F2E7CE", "#B39A70"),   # 크림/뼈 — 화면에서 가장 밝은 값
    "ochre":    ("#E4B453", "#8E5F1B"),   # 황토
    "burnt":    ("#DC7728", "#84360F"),   # 번트오렌지 — 등불, 강조
    "oxblood":  ("#B03A24", "#5C170F"),   # 적갈 — 위험, 피
    "olive":    ("#8D8F4A", "#464821"),   # 탁한 올리브 — 천, 이끼
    "umber":    ("#96703F", "#49331D"),   # 흙
    "charcoal": ("#39312A", "#15110E"),   # 숯검정 — 선, 그림자, 실루엣
}
FOLK_LINE = "#12100D"
# 역할별 고유 반복 무늬 (§1-5) — 70px 에서 실루엣 다음가는 판별 단서
MOTIF = {"scout": "hatch", "cook": "dots", "medic": "cross", "engineer": "zig",
         "farmer": "saw", "scholar": "bars", "trader": "diamond", "kid": "rings"}
MOTIF_KO = {"hatch": "빗금(기운 자국)", "dots": "박음질 점", "cross": "십자 박음",
            "zig": "지그재그 이음매", "saw": "톱니", "bars": "세로 이중선",
            "diamond": "마름모", "rings": "따개비 고리"}

# ══════════════════════════════════════════════════════════════════
# S5-C 「더 귀엽게」 — 비율 보정 (PLAYER_JOURNEY §5-3)
# ══════════════════════════════════════════════════════════════════
#   화풍은 **확정이고 바꾸지 않는다**. 팔레트·2단 음영·무늬·손그림 선은 folk 경로를
#   한 줄도 고치지 않고 그대로 쓴다. 바꾸는 것은 비율과 인상뿐이다.
#   메시를 새로 만들지 않고 **포즈 뼈 스케일**만 건드린다 → 각인 파츠·소품·의상·
#   애니메이션 클립이 전부 공짜로 따라온다(04 C8 공용 골격).
#   ★ 총 키는 보정 후 다시 맞춘다. 그래서 `실측 키`·`미터당 110px`·`발 기준선 240px`
#     규약이 한 글자도 바뀌지 않는다(개발이 쓰는 값은 그대로다).
CUTE = dict(
    head=1.26,        # 머리 뼈 배율 — 이것이 등신을 만든다 (1.50 은 2등신이 되어 몸이 사라졌다)
    neck=0.70,        # 목 길이(큰 머리가 어깨에 얹히게)
    leg=0.78, leg_xz=1.30,   # 다리: 짧고 통통하게 (IK 이므로 발 타깃도 같이 올린다)
    arm=0.84, arm_xz=1.12,   # 팔
    fist=1.08,        # 손
    shoulder=0.72,    # 어깨 폭 — §5-3-3 「각진 어깨를 없앤다」
    torso_y=0.88, torso_xz=1.06,
    abdomen_y=0.86, abdomen_xz=1.10,
    hips_xz=1.16,     # §5-3-3 「아래가 넓고 부드러운 덩어리」
    eye=0.95,         # 흰자 배율(원본 build_props 대비. folk 는 0.52 로 줄였다 = 점)
    pupil=0.62,       # 동공 = 흰자 대비 비율(흰자보다 반드시 작아야 흘러내리지 않는다)
    eye_drop=0.075,   # §5-3-2 「눈 위치를 살짝 아래로」 (m, 1.6m 기준)
    eye_wide=1.06,    # 눈 사이 간격
    hilite=0.30,      # 눈 하이라이트 크기(동공 대비)
    skirt=1.04,       # 잠수복 자락을 조금 더 넓게
)
# 역할별 예외: 요리사는 **높은 요리모자가 머리 메시에 들어 있어** 머리 배율이 그대로
#   곱해지면 모자가 접시 더미처럼 퍼지고, 키를 되돌리는 과정에서 몸이 눌린다(8역할 대조에서 확인).
CUTE_HEAD = {"cook": 1.12}
# §5-3-4 동작 과장. 정면 직교는 깊이 동작을 읽지 못하므로(char_S4 §5)
#   과장은 전부 **화면 평면 안에서** 준다: 상하 흔들림 · 좌우 기울기 · 위아래 눌림.
EXAG = dict(
    idle_breath=0.011,   # m — 아주 느린 호흡(5프레임 한 주기)
    idle_tilt=0.9,       # °
    walk_bob=0.052,      # m — 걸을 때 상하 흔들림(한 걸음마다)
    walk_tilt=3.6,       # ° 좌우 기울기
    walk_squash=0.045,   # 착지 때 눌림
    pick_lean=6.0,       # ° 뒤로 젖힘(§5-3-4) — 정면에서는 세로 단축으로 읽힌다.
                         #   13° 로 하니 얼굴이 사라지고 헬멧 윗면만 남았다(char_S4 §5 재현)
    pick_squat=0.050,    # m 무릎 굽힘(젖힘을 화면에서 보이게 만드는 짝)
    pick_tilt=4.0,       # °
)


def srgb_to_lin(hexc):
    """★ 기존 파이프라인(blender_chars_v2.hexcol)은 sRGB 값을 선형 슬롯에 그대로 넣는다.
    그러면 렌더 결과가 의도한 색보다 한참 밝게 나온다(올리브 #8D8F4A → 화면 #C4C593).
    민속화풍은 **팔레트가 화면에 그대로 찍혀야** 하므로 여기서만 제대로 변환한다.
    기존 산출물과 톤이 어긋나는 것은 의도한 것이다(B안은 새 화풍이다)."""
    h = hexc.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def folk_family(hexc):
    """재질의 **원본(빛 안 받은) 색**으로 계열을 정한다. 렌더된 픽셀은 환경광에 씻겨
    채도가 0.1 대로 떨어져 색상 분류가 불가능하다(1회차에서 정찰병 올리브가 갈색이 됐다).
    그래서 팔레트 강제는 렌더 단계에서, 2단 음영은 후처리에서 한다."""
    import colorsys
    h = hexc.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    hu, _, _ = colorsys.rgb_to_hsv(r, g, b)
    hu *= 360.0
    v = max(r, g, b); mn = min(r, g, b)
    sa = (v - mn) / v if v > 1e-5 else 0.0
    if v < 0.22:
        return "charcoal"
    if sa < 0.22:
        return "cream" if v >= 0.60 else ("umber" if v >= 0.32 else "charcoal")
    if hu < 16 or hu >= 345:
        return "oxblood"
    if hu < 32:
        return "burnt" if sa >= 0.30 else "cream"
    if hu < 54:
        return "ochre"
    if hu < 150:
        return "olive"
    if hu < 262:
        return "burnt"        # 청록~남색은 사람에게 쓰지 않는다 (§5) → 따뜻한 강조로 번역
    return "umber"            # 자주 → 흙. 적갈로 보내면 학자가 교섭가·의무병과 겹친다


# 카메라 파생값: 셀 중앙(128)이 look_z, 아래로 PPM px = 1m
LOOK_Z = (BASE_Y - CELL / 2) / PPM       # = 1.0182 m
ORTHO = CELL / PPM                       # = 2.3273 m (세로 시야)


# ══════════════════════════════════════════════════════════════════
# 1) Blender 렌더
# ══════════════════════════════════════════════════════════════════
def run_render():
    import bpy, importlib.util
    from mathutils import Vector

    # blender_chars_v2 를 모듈로 그대로 쓴다 (재질·소품·각인·정규화를 재정의하지 않는다)
    spec = importlib.util.spec_from_file_location("bchars", os.path.join(HERE, "blender_chars_v2.py"))
    m = importlib.util.module_from_spec(spec)
    saved = list(sys.argv)
    sys.argv = [saved[0], "--", "__none__"]     # 그쪽 __main__ 이 돌지 않게
    spec.loader.exec_module(m)
    sys.argv = saved

    m.RES = CELL

    def front_camera():
        """정면 직교. to_track_quat 은 시선이 업축과 평행해 퇴화하므로 오일러를 직접 준다."""
        bpy.ops.object.camera_add(location=(0, -20.0, LOOK_Z))
        cam = bpy.context.object
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ORTHO
        cam.rotation_euler = (math.radians(90), 0, 0)   # -Z → +Y, 업 +Z
        m.sc.camera = cam
        return cam

    def sun(direction, energy, color):
        d = Vector(direction).normalized()
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 4))
        L = bpy.context.object
        L.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        L.data.energy = energy
        L.data.color = color
        return L

    def front_lights():
        # 키: 카메라 뒤 왼쪽 위에서 (따뜻함) / 필: 오른쪽에서 약하게 (차가움) / 톱: 위에서
        sun((0.34, 0.74, -0.58), 2.4, (1.00, 0.93, 0.82))
        sun((-0.55, 0.62, -0.30), 1.0, (0.80, 0.88, 1.00))
        sun((0.05, 0.20, -1.00), 0.8, (1.00, 0.96, 0.90))

    # ── 평면 민속화풍(REF_ART_FLAT_FOLK) 을 위한 3D 추가분 ─────────────────
    # 후처리만으로는 §1-6(덩어리진 실루엣·작은 머리)과 §1-7(최소한의 얼굴)이 나오지 않는다.
    # 형상은 3D에서 바꾼다. 원작의 형태(새 두개골·털 목도리)는 쓰지 않고 §3의 우리 소재로 번역한다.
    # ── S5-C 비율 보정 도구 ───────────────────────────────────────────
    def bone_world(arm, name):
        """뼈의 월드 행렬 (부모 관계·스케일 전부 반영)."""
        import bpy
        bpy.context.view_layer.update()
        return arm.matrix_world @ arm.pose.bones[name].matrix

    def set_bone_world(arm, name, W):
        import bpy
        arm.pose.bones[name].matrix = arm.matrix_world.inverted() @ W
        bpy.context.view_layer.update()

    def world_move(arm, name, d):
        """뼈를 월드 좌표로 밀어 준다(액션이 넣은 회전은 그대로 둔다)."""
        from mathutils import Matrix, Vector
        set_bone_world(arm, name, Matrix.Translation(Vector(d)) @ bone_world(arm, name))

    def world_rot(arm, name, axis, deg):
        """뼈를 자기 머리 위치를 축으로 월드 축 둘레로 돌린다."""
        from mathutils import Matrix
        W = bone_world(arm, name)
        p = W.translation.copy()
        D = (Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, axis) @
             Matrix.Translation(-p))
        set_bone_world(arm, name, D @ W)

    def prop_world_move(o, arm, bone, d):
        """뼈에 붙은 소품을 월드 좌표로 민다(attach 와 같은 부모 행렬 규약)."""
        import bpy
        from mathutils import Matrix, Vector
        bpy.context.view_layer.update()
        pb = arm.pose.bones[bone]
        blen = arm.data.bones[bone].length
        P = arm.matrix_world @ pb.matrix @ Matrix.Translation(Vector((0, blen, 0)))
        o.matrix_basis = P.inverted() @ (Matrix.Translation(Vector(d)) @ (P @ o.matrix_basis))

    def cute_eyes(arm, role):
        """§5-3-2 눈을 키우고 살짝 아래로. 코·입은 계속 없다(REF §1-7 「얼굴은 최소」).
        folk 경로가 흰자를 0.52 배로 줄여 **점**이 된 것을 되돌리고 원본보다 키운다.
        동공은 반드시 흰자보다 작게 — 크면 뺨으로 흘러내린 자국처럼 보인다."""
        import bpy
        u = m.ROLE_DEF[role]["h"] / 1.60
        eyes = []
        for o in list(bpy.data.objects):
            if o.type != 'MESH' or not o.data.materials:
                continue
            mn = (o.data.materials[0].name or "").split('.')[0]
            if mn in ("eye", "eye_white"):
                eyes.append((mn, o))
        hl = m.mat("eye_hl", "#F6EFDF", 0.3)     # 크림 계열로 스냅 → 하이라이트 하나
        for mn, o in eyes:
            # 흰자는 원본(build_props) 대비 CUTE["eye"] 배, 동공은 흰자의 pupil 배.
            # 원본 동공/흰자 비가 약 0.64 이므로 동공 쪽은 그 비를 나눠서 맞춘다.
            k = CUTE["eye"] if mn == "eye_white" else CUTE["eye"] * (CUTE["pupil"] / 0.64)
            o.scale = tuple(c * k for c in o.scale)
        bpy.context.view_layer.update()
        for mn, o in eyes:
            x = o.matrix_world.translation.x
            prop_world_move(o, arm, "Head",
                            (x * (CUTE["eye_wide"] - 1.0), 0, -CUTE["eye_drop"] * u))
        bpy.context.view_layer.update()
        for mn, o in eyes:                       # 동공 위에 하이라이트 점 하나
            if mn != "eye":
                continue
            p = o.matrix_world.translation
            sx = 1.0 if p.x >= 0 else -1.0
            r = 0.058 * u * CUTE["eye"] * CUTE["hilite"] / 0.30
            m.ball(arm, "Head", hl,
                   (p.x + sx * 0.022 * u, p.y - 0.020 * u, p.z + 0.028 * u), (r, r * 0.9, r))
        bpy.context.view_layer.update()

    # 손에 든 소품은 키 정규화(몸 메시 기준)에 포함되지 않는다. 다리를 줄이면 손이
    # 발 쪽으로 내려오므로 긴 소품이 셀 아래로 삐져나간다. 기술자의 렌치가 255px(셀 끝)에
    # 닿아 잘렸다 — 셀 바닥 256px 안으로 들어오게 들어 올린다.
    CUTE_LIFT = {"engineer": (("wrench", "wr_gap"), 0.15)}

    def cute_props(arm, role):
        import bpy
        spec = CUTE_LIFT.get(role)
        if not spec:
            return
        names, dz = spec
        u = m.ROLE_DEF[role]["h"] / 1.60
        for o in list(bpy.data.objects):
            if o.type != 'MESH' or not o.data.materials or o.parent_type != 'BONE':
                continue
            if (o.data.materials[0].name or "").split('.')[0] in names:
                prop_world_move(o, arm, o.parent_bone, (0, 0, dz * u))
        bpy.context.view_layer.update()

    def cute_static(arm, role):
        """뼈 **스케일**만 바꾸는 부분. 액션은 scale 을 키프레임하지 않으므로
        (Walk/Idle/PickUp 채널을 직접 확인함: location·rotation_quaternion 뿐)
        한 번 걸어 두면 클립을 갈아 끼워도 유지된다."""
        import bpy
        P = arm.pose.bones
        def s(name, sy, sxz):
            if name in P:
                b = P[name]
                b.scale = (b.scale[0] * sxz, b.scale[1] * sy, b.scale[2] * sxz)
        hk = CUTE_HEAD.get(role, CUTE["head"])
        s("Head", hk, hk)                              # §5-3-1 머리를 키운다
        s("Neck", CUTE["neck"], 1.0)
        s("Torso", CUTE["torso_y"], CUTE["torso_xz"])
        s("Abdomen", CUTE["abdomen_y"], CUTE["abdomen_xz"])
        s("Hips", 1.0, CUTE["hips_xz"])                # §5-3-3 아래를 넓게
        s("Shoulder.L", CUTE["shoulder"], 1.0)         # §5-3-3 각진 어깨를 없앤다
        s("Shoulder.R", CUTE["shoulder"], 1.0)
        for n in ("UpperArm.L", "UpperArm.R", "LowerArm.L", "LowerArm.R"):
            s(n, CUTE["arm"], CUTE["arm_xz"])
        for n in ("Fist.L", "Fist.R"):
            s(n, CUTE["fist"], CUTE["fist"])
        for n in ("UpperLeg.L", "UpperLeg.R", "LowerLeg.L", "LowerLeg.R"):
            s(n, CUTE["leg"], CUTE["leg_xz"])
        bpy.context.view_layer.update()

    # 다리를 줄이면 발 IK 타깃이 닿지 않는다 → 발을 그만큼 올려 준다.
    LEG_RIG = 0.4538 + 0.5270        # 원본 리그 단위 다리 길이(뼈 덤프에서 실측)

    def cute_frame(arm, role):
        """액션이 매 프레임 덮어쓰는 **위치** 보정. assign_action 뒤에 다시 건다."""
        dz = LEG_RIG * (1.0 - CUTE["leg"]) * arm.scale[2]
        for n in ("Foot.L", "Foot.R"):
            if n in arm.pose.bones:
                world_move(arm, n, (0, 0, dz))

    def exaggerate(arm, clip, f, role):
        """§5-3-4 동작 과장. 전부 화면 평면(가로 X · 세로 Z) 안에서 준다."""
        import bpy
        u = m.ROLE_DEF[role]["h"] / 1.60
        ph = f * math.tau
        if clip == "Idle":
            # 아주 느린 호흡 — 5프레임에 한 번. 가슴이 아니라 몸 전체가 조금 뜬다.
            arm.location[2] += EXAG["idle_breath"] * u * math.sin(ph)
            world_rot(arm, "Torso", 'Y', EXAG["idle_tilt"] * math.sin(ph))
            world_rot(arm, "Head", 'Y', -EXAG["idle_tilt"] * 0.8 * math.sin(ph))
        elif clip == "Walk":
            # 한 주기에 두 걸음 → 상하 흔들림도 두 번. 착지에서 눌리고 중간에 뜬다.
            b = abs(math.sin(ph))
            arm.location[2] += EXAG["walk_bob"] * u * (b - 0.5)
            arm.scale[2] *= 1.0 - EXAG["walk_squash"] * (1.0 - b)
            world_rot(arm, "Abdomen", 'Y', EXAG["walk_tilt"] * math.sin(ph / 2.0))
            world_rot(arm, "Head", 'Y', -EXAG["walk_tilt"] * 1.4 * math.sin(ph / 2.0))
        elif clip == "PickUp":
            # 「물건을 들 때 뒤로 젖힌다」 — 정면 직교에서 젖힘 자체는 세로 단축으로만
            # 읽히므로(char_S4 §5), 무릎을 굽혀 몸을 낮추는 동작과 짝지어 화면에 보이게 한다.
            k = f
            world_move(arm, "Body", (0, 0, -EXAG["pick_squat"] * u * k))
            world_rot(arm, "Abdomen", 'X', -EXAG["pick_lean"] * k)
            world_rot(arm, "Torso", 'X', -EXAG["pick_lean"] * 0.4 * k)
            # 머리는 몸이 젖힌 만큼 되돌려 **얼굴이 계속 카메라를 본다**.
            # 안 되돌리면 정면 직교에서 얼굴이 사라지고 정수리만 남는다.
            # ★ 머리를 따로 되돌리려 해 봤으나(pick_chin) 화면에 아무 변화가 없었다 —
            #   Head 는 pb.matrix 로 월드 회전을 걸어도 부모 갱신 순서 때문에 먹지 않는다.
            #   진짜 원인은 젖힘의 **부호**였다: +X 가 앞으로 숙이는 방향이라 얼굴이 사라졌다.
            #   −X(= 뒤로 젖힘)로 바로잡으니 다섯 프레임 전부 얼굴이 남는다.
            world_rot(arm, "Abdomen", 'Y', EXAG["pick_tilt"] * k)
        bpy.context.view_layer.update()

    def folk_extras(arm, role, cute=False):
        """★ 좌표 단위 주의: build() 가 이미 정규화(스케일+이동)를 끝낸 뒤라
        m.bone_pos() 는 **미터**를 돌려준다. blender_chars_v2.build_props 는 정규화 전
        원본 리그 단위(전체 3.078)로 썼지만 여기서는 전부 미터다. 1회차에 이걸 놓쳐
        헬멧이 머리 위 0.7m 에 떠 있었다.
        기준선(1.6m 기준): 머리꼭대기 1.60 · 눈 1.36 · 머리중심 1.344 · 목 1.03 · 허리 0.58 · 골반 0.466
        역할 키가 다르면 u 배로 줄인다."""
        import bpy
        v = m.ROLES[role]["visual"]
        u = m.ROLE_DEF[role]["h"] / 1.60
        # (1) §1-7 최소한의 얼굴 — 흰자와 동공을 줄여 "작은 눈 점"으로
        #     cute=True 면 여기를 건너뛰고 cute_eyes() 가 반대로 키운다(PLAYER_JOURNEY §5-3-2).
        #     코·입이 없는 것은 두 경우 모두 같다 — 바뀌는 것은 눈 하나뿐이다.
        if not cute:
            for o in list(bpy.data.objects):
                if o.type != 'MESH' or not o.data.materials:
                    continue
                mn = (o.data.materials[0].name or "").split('.')[0]
                if mn == "eye_white":
                    o.scale = tuple(c * 0.52 for c in o.scale)
                elif mn == "eye":
                    # 흰자보다 크면 동공이 뺨으로 흘러내린 것처럼 보인다(10회차에서 발견)
                    o.scale = tuple(c * 0.56 for c in o.scale)
        nk = m.bone_pos(arm, "Neck")
        hp = m.bone_pos(arm, "Hips")
        # (2) §3 번역: 털 목도리 → 잠수복 목 실링 고무테. 같은 물결의 반복 3겹
        rub = m.mat("folk_seal", "#43302A", 0.95)
        for dz, r, t in ((-0.030, 0.150, 0.020), (0.012, 0.172, 0.024), (0.054, 0.146, 0.018)):
            m.ring(arm, "Neck", rub, (nk.x, nk.y + 0.010 * u, nk.z + dz * u), r * u, t * u)
        # (3) §1-6 덩어리진 실루엣 — 아래가 넓은 잠수복 자락 + 무게추 벨트
        #     "주민은 헤엄치지 않고 무게추로 해저를 걷는다"(CONCEPT_DEEP_SEA §7) 를 형상으로
        sk = m.mat("folk_skirt", v["body"], 0.92)
        if cute:
            # §5-3-3 「실루엣 아래쪽을 둥글게」 — 원뿔(직선 옆면 + 각진 밑단)을 버리고
            # 눌린 구로 바꾼다. 아래가 넓고 모서리가 없는 덩어리가 된다.
            kw = CUTE["skirt"]
            m.ball(arm, "Hips", sk, (hp.x, hp.y + 0.006 * u, hp.z - 0.045 * u),
                   (0.640 * u * kw, 0.470 * u * kw, 0.430 * u))
            # 허리로 이어지는 곡면. 크게 하면 가슴의 시그니처(의무병의 붉은 십자 등)를 덮는다.
            m.ball(arm, "Torso", sk, (hp.x, hp.y + 0.006 * u, hp.z + 0.075 * u),
                   (0.400 * u * kw, 0.330 * u * kw, 0.200 * u))
        else:
            m.cone(arm, "Hips", sk, (hp.x, hp.y + 0.006 * u, hp.z - 0.005 * u),
                   0.290 * u, 0.175 * u, 0.30 * u)
        blt = m.mat("folk_belt", "#2E241C", 0.9)
        m.ring(arm, "Hips", blt, (hp.x, hp.y + 0.006 * u, hp.z + 0.105 * u), 0.170 * u, 0.019 * u)
        wt = m.mat("folk_weight", "#5A4632", 0.6, 0.3)
        for sx in (-0.115, 0.0, 0.115):
            m.box(arm, "Hips", wt, (hp.x + sx * u, hp.y - 0.145 * u, hp.z + 0.085 * u),
                  (0.060 * u, 0.046 * u, 0.086 * u))
        # (4) 정찰병만 — 구식 잠수 헬멧. 얼굴을 덮지 않고 면갑을 위로 젖혀 둔다.
        #     원작의 새 두개골·부리 형태는 쓰지 않는다(REF §6). 명백한 기계 배관으로 번역.
        if role == "scout":
            hd = m.bone_pos(arm, "Head")
            hm = m.mat("folk_helm", "#655C50", 0.45)      # 흙 계열로 스냅 → 돔
            vz = m.mat("folk_visor", "#8A7A5E", 0.4, 0.3)  # 황토 계열로 스냅 → 면갑(밝게 떨어진다)
            dk = m.mat("folk_helmdk", "#3B3025", 0.7)
            m.ball(arm, "Head", hm, (hd.x, hd.y + 0.010 * u, hd.z + 0.345 * u),
                   (0.530 * u, 0.520 * u, 0.440 * u))
            # 들어 올린 면갑 — 이마 위로 젖혀 세운 판. 얼굴을 덮지 않는다(REF §1-8 의 원리만)
            # cute: 머리가 1.26배가 되면 이 판이 머리 위의 **탁자**처럼 읽힌다 → 줄여서 돔에 붙인다.
            fv = 0.78 if cute else 1.0
            m.box(arm, "Head", vz, (hd.x, hd.y - 0.165 * u, hd.z + (0.520 if cute else 0.605) * u),
                  (0.430 * u * fv, 0.235 * u * fv, 0.034 * u), rot=(math.radians(-34), 0, 0))
            m.box(arm, "Head", dk, (hd.x, hd.y - 0.150 * u, hd.z + 0.470 * u),
                  (0.450 * u, 0.034 * u, 0.034 * u))       # 경첩
            for sx in (-1, 1):                              # 면갑 걸쇠 두 개
                m.box(arm, "Head", dk, (hd.x + sx * 0.205 * u, hd.y - 0.150 * u, hd.z + 0.520 * u),
                      (0.030 * u, 0.030 * u, 0.110 * u))
            m.tube(arm, "Head", dk, (hd.x + 0.230 * u, hd.y + 0.060 * u, hd.z + 0.315 * u),
                   0.027 * u, 0.175 * u, rot=(math.radians(26), 0, 0))
            m.tube(arm, "Head", dk, (hd.x + 0.230 * u, hd.y + 0.015 * u, hd.z + 0.195 * u),
                   0.027 * u, 0.125 * u, rot=(math.radians(74), 0, 0))

    def folk_materials():
        """§1-1 팔레트 강제 + §1-3 음영 2단을 **재질 단계**에서 끝낸다.
        후처리에서 명도만 두 값으로 밀면 계열 정보가 사라져 숯검정 옷이 흰옷이 된다
        (3회차에 기술자가 통째로 크림이 됐다). 그래서 계열별 (밝은 면, 그림자) 쌍을
        Diffuse → ShaderToRGB → 상수 보간 ColorRamp → Emission 으로 직접 굽는다.
        이것이 REF §4-2 의 '음영 램프를 2단으로 고정'이다."""
        import bpy
        for mt in bpy.data.materials:
            if not mt.use_nodes:
                continue
            bsdf = next((n for n in mt.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bsdf is None:
                continue
            base = mt.name.split('.')[0]
            c = bsdf.inputs["Base Color"].default_value
            # ★ 감마 보정하지 않는다. blender_chars_v2.hexcol() 은 sRGB 값을 선형 슬롯에
            #   그대로 넣는 기존 규약이라(char_S2.md §8) 저장값 = hex/255 이다.
            hexc = "#%02x%02x%02x" % tuple(int(round(max(0.0, min(1.0, c[i])) * 255))
                                           for i in range(3))
            fam = "charcoal" if base == "eye" else folk_family(hexc)
            lightc, shadowc = FOLK_PALETTE[fam]
            if base == "eye":
                lightc = shadowc = FOLK_LINE          # 눈동자는 선과 같은 검정 한 값
            nt = mt.node_tree
            nt.nodes.clear()
            out = nt.nodes.new('ShaderNodeOutputMaterial')
            dif = nt.nodes.new('ShaderNodeBsdfDiffuse')
            dif.inputs["Color"].default_value = (1, 1, 1, 1)
            s2r = nt.nodes.new('ShaderNodeShaderToRGB')
            rmp = nt.nodes.new('ShaderNodeValToRGB')
            rmp.color_ramp.interpolation = 'CONSTANT'
            e0, e1 = rmp.color_ramp.elements[0], rmp.color_ramp.elements[1]
            e0.position = 0.0; e0.color = (*srgb_to_lin(shadowc), 1)
            e1.position = 0.42; e1.color = (*srgb_to_lin(lightc), 1)
            emi = nt.nodes.new('ShaderNodeEmission')
            nt.links.new(dif.outputs[0], s2r.inputs[0])
            nt.links.new(s2r.outputs[0], rmp.inputs[0])
            nt.links.new(rmp.outputs[0], emi.inputs[0])
            nt.links.new(emi.outputs[0], out.inputs[0])

    def folk_render(path):
        """REF §4-2 비사실 렌더 — 환경광을 크게 낮춰 재질 색이 살아남게 하고(0.45→0.18),
        선을 굵게 한다. 환경광이 높으면 전 픽셀 채도가 0.1 대로 씻겨 팔레트가 무의미해진다."""
        import bpy
        m.render(path)   # 설정을 그대로 쓰되 아래에서 월드·선만 덮어쓰고 다시 렌더한다
        sc = m.sc
        # 재질이 Emission 이라 환경광은 의미가 없지만, 혹시 남은 BSDF 를 위해 0 에 가깝게
        sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.0
        sc.render.line_thickness = 1.6
        fs = sc.view_layers[0].freestyle_settings
        if fs.linesets and fs.linesets[0].linestyle:
            fs.linesets[0].linestyle.thickness = 1.6
            fs.linesets[0].linestyle.color = srgb_to_lin(FOLK_LINE)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)

    def build_octopus(cute=False):
        """동거 문어 (WORLD_BIBLE_DEEP §3-4) — 위협이 아니라 식구.
        아마추어 없이 원시 도형만. 발 원점 z=0, 정면 -Y. 팔레트는 folk_materials 가 입힌다.
        C5(짐승은 사람보다 따뜻하게·눈은 사람보다 밝게)를 지킨다."""
        import bpy
        from mathutils import Vector, Matrix, Euler
        bpy.ops.wm.read_factory_settings(use_empty=True)
        m.sc = bpy.context.scene
        body = m.mat("oct_body", "#B24A2E", 0.95)     # 적갈 계열로 스냅된다
        dark = m.mat("oct_dark", "#5C1A10", 0.95)
        iris = m.mat("oct_iris", "#E8B24E", 0.4)      # 짐승의 눈은 사람보다 밝게 (C5)
        pup = m.mat("eye", "#17120f", 0.25)           # 이름 eye → 팔레트에서 검정 유지
        suck = m.mat("oct_suck", "#EFD9B8", 0.9)
        def ball(mat, pos, size):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=18, ring_count=10)
            o = bpy.context.object
            o.matrix_world = (Matrix.Translation(Vector(pos)) @
                              Matrix.Diagonal(Vector(size).to_4d()))
            o.data.materials.append(mat)
            return o
        # cute=True — 사람과 같은 규칙: 머리(외투막)를 키우고 눈을 키우고 아래를 넓게.
        # 색은 한 값도 바꾸지 않는다(§5-3-5 「귀여움을 색으로 내지 않는다」).
        if cute:
            hl = m.mat("oct_hl", "#F6EFDF", 0.3)
            ball(body, (0, 0, 0.335), (0.445, 0.415, 0.470))
            ball(body, (0, 0, 0.165), (0.505, 0.455, 0.330))
            for sx in (1, -1):
                ball(iris, (sx * 0.135, -0.160, 0.292), (0.190, 0.155, 0.190))
                ball(pup, (sx * 0.139, -0.216, 0.286), (0.100, 0.080, 0.124))
                ball(hl, (sx * 0.168, -0.238, 0.322), (0.050, 0.040, 0.050))
            arm_rad, arm_sz = 0.055, 0.118
        else:
            ball(body, (0, 0, 0.335), (0.345, 0.325, 0.42))
            ball(body, (0, 0, 0.175), (0.415, 0.375, 0.30))
            for sx in (1, -1):
                ball(iris, (sx * 0.118, -0.128, 0.310), (0.140, 0.115, 0.140))
                ball(pup, (sx * 0.121, -0.176, 0.307), (0.078, 0.062, 0.098))
            arm_rad, arm_sz = 0.07, 0.125
        # 팔 여덟 — 밖으로 퍼졌다가 바닥에 닿는다. 빨판은 반복 점(§1-5)
        for k in range(8):
            th = (k / 8.0) * math.tau + 0.2
            for j in range(11):
                t = j / 10.0
                rad = arm_rad + t * (0.38 if cute else 0.44)
                z = max(0.026, 0.155 - t * 0.135 + 0.075 * math.sin(t * 3.1))
                sz = arm_sz - t * (0.082 if cute else 0.092)
                ball(body if t < 0.72 else dark,
                     (math.cos(th) * rad, math.sin(th) * rad, z), (sz, sz, sz * 0.86))
                if 2 <= j <= 8 and j % 2 == 0 and math.sin(th) < 0.1:
                    ball(suck, (math.cos(th) * rad, math.sin(th) * rad - sz * 0.48,
                                z - sz * 0.12), (sz * 0.26, sz * 0.26, sz * 0.26))
        return 0.57 if cute else 0.52

    def measure(mesh):
        """★ 포즈를 바꾼 직후의 실측. `view_layer.update()` 만으로는 백그라운드에서
        뎁스그래프가 한 스텝 뒤처져 **보정 전 메시**를 돌려주는 일이 있다(발이 셀 밖으로
        13px 삐져나가는 것으로 드러났다). 명시적으로 depsgraph.update() 를 부른다."""
        import bpy
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        pts = []
        ev = mesh.evaluated_get(dg)
        me = ev.to_mesh()
        mw = mesh.matrix_world
        for vtx in me.vertices:
            pts.append((mw @ vtx.co).z)
        ev.to_mesh_clear()
        return (min(pts), max(pts)) if pts else (0.0, 1.0)

    def setup(role, folk, cute, imprints=False):
        """역할 하나를 세우고(folk 화풍 → 비율 보정 → 키 재정규화) 기준 변환을 돌려준다.
        ★ 재정규화가 핵심이다. 비율만 바꾸고 **총 키는 보정 전과 똑같이** 되돌려 놓기 때문에
          `실측 키`·`미터당 110px`·`발 기준선 240px` 규약이 그대로 유지된다."""
        arm, mesh, props, imps = m.build(role, "Idle", 0.0, imprints=imprints)
        lo0, hi0 = measure(mesh)                    # 보정 전 실측 키 — 이 값을 지킨다
        if folk or cute:
            folk_extras(arm, role, cute=cute)
            if cute:
                cute_eyes(arm, role)
            folk_materials()
        if cute:
            if arm.animation_data:
                arm.animation_data.action = None   # 위 pose_frame 의 ★ 와 같은 이유
            cute_props(arm, role)
            cute_static(arm, role)
            cute_frame(arm, role)
            arm.location = (0, 0, 0)
            lo, hi = measure(mesh)
            f = (hi0 - lo0) / max(1e-6, hi - lo)
            arm.scale = tuple(c * f for c in arm.scale)
            lo, hi = measure(mesh)
            arm.location = (0, 0, -lo)
            bpy.context.view_layer.update()
            print("  cute renorm f=%.4f  h %.4f -> %.4f" % (f, hi - lo, measure(mesh)[1] - measure(mesh)[0]), flush=True)
        u = m.ROLE_DEF[role]["h"] / 1.60
        land = {"wave": round(m.bone_pos(arm, "Neck").z, 4),
                "hem": round(m.bone_pos(arm, "Hips").z - 0.121 * u, 4),
                "head": round(m.bone_pos(arm, "Head").z, 4)}
        return arm, mesh, props, imps, tuple(arm.location), tuple(arm.scale), (lo0, hi0), land

    def pose_frame(arm, role, base_loc, base_scale, act, t, clip, f, cute):
        """한 프레임을 만든다. 액션은 location/rotation 을 덮어쓰므로 보정을 다시 건다.
        ★ 그리고 보정을 걸기 전에 **액션을 떼어 낸다.** bpy.ops.render.render() 는 렌더용
          뎁스그래프에서 애니메이션을 다시 평가하므로, 액션이 붙어 있는 한 우리가 손으로
          넣은 뼈의 location/rotation 이 렌더 순간에 전부 되돌아간다(발 IK 타깃이 13px
          아래로 되돌아가 발이 셀 밖으로 나갔다). frame_set 으로 포즈가 이미 뼈에 쓰였으므로
          액션을 떼도 포즈는 그대로 남는다. 뼈 **스케일**은 키프레임이 없어 영향을 받지 않았다."""
        m.assign_action(arm, act, t)
        if cute and arm.animation_data:
            arm.animation_data.action = None
        arm.location = base_loc          # 기준선은 Idle 로 고정
        arm.scale = base_scale
        if cute:
            cute_frame(arm, role)        # 발 IK 타깃 올림(액션이 매 프레임 지운다)
            exaggerate(arm, clip, f, role)
        bpy.context.view_layer.update()

    roles = [r for r in (ONLY or (HERO if CUTE_MODE else ROLE_ORDER)) if r in m.ROLE_DEF]
    folk = "--folk" in argv or FOLK or CUTE_MODE
    cute = CUTE_MODE
    out_root = RAWC if cute else (RAWF if folk else RAW)
    meta = {"cell": CELL, "ppm": PPM, "baseline": BASE_Y, "ortho": round(ORTHO, 4),
            "view": "front_ortho", "clips": CLIPS, "frames": NFRAME, "roles": {},
            "cute": CUTE if cute else None, "exag": EXAG if cute else None}

    for role in roles:
        rdir = os.path.join(out_root, role)
        os.makedirs(rdir, exist_ok=True)
        # 한 번만 짓고 클립을 갈아 끼운다 (역할당 blend 로드 1회)
        arm, mesh, props, _, base_loc, base_scale, (lo, hi), land = setup(role, folk, cute)
        front_camera(); front_lights()
        for clip, t0, t1, cyclic in (CLIP_SPEC_CUTE if cute else CLIP_SPEC):
            act = next((a for a in bpy.data.actions if a.name == clip), None)
            if act is None:
                print("MISSING CLIP", role, clip, flush=True); continue
            for i in range(NFRAME):
                f = i / float(NFRAME) if cyclic else i / float(NFRAME - 1)
                pose_frame(arm, role, base_loc, base_scale, act, t0 + (t1 - t0) * f, clip, f, cute)
                (folk_render if folk else m.render)(os.path.join(rdir, "%s_%d.png" % (clip, i)))
        meta["roles"][role] = {"h": round(hi - lo, 4), "px": round((hi - lo) * PPM, 1),
                               "norm_h": m.ROLE_DEF[role]["h"],
                               "blend": m.ROLE_DEF[role]["blend"], "land": land}
        print("RENDERED", role, "h=%.4f" % (hi - lo), "land", land, flush=True)

        # 각인 3개 겹침 변형 (Idle 0프레임 한 장)
        if role in IMP_ROLES:
            arm, mesh, props, imps, bl, bs, _hh, _ld = setup(role, folk, cute, imprints=True)
            for iid, e, parts in imps:
                vis = iid in IMP_TRIPLE
                for o in [e] + parts:
                    o.hide_viewport = not vis; o.hide_render = not vis
            front_camera(); front_lights()
            bpy.context.view_layer.update()
            (folk_render if folk else m.render)(os.path.join(rdir, "imp3_0.png"))
            print("RENDERED", role, "imp3", flush=True)

        # 대표 캐릭터 쇼케이스 — 같은 프레이밍으로 해상도만 2배 (512px)
        if folk and role in HERO:
            arm, mesh, props, _i, bl, bs, _hh, _ld = setup(role, folk, cute)
            m.RES = CELL * 2
            front_camera(); front_lights()
            bpy.context.view_layer.update()
            folk_render(os.path.join(rdir, "hero_0.png"))
            m.RES = CELL
            print("RENDERED", role, "hero512", flush=True)

        # 실패 컷 — PickUp 전 구간(0~100%). 비교 페이지 §5 에 "쓰지 않는 이유"로 붙인다.
        if role in IMP_ROLES and not folk:
            arm, mesh, props, _i, bl, bs, _hh, _ld = setup(role, folk, cute)
            front_camera(); front_lights()
            act = next((a for a in bpy.data.actions if a.name == "PickUp"), None)
            if act:
                for i in range(NFRAME):
                    pose_frame(arm, role, bl, bs, act, i / float(NFRAME - 1), "PickUp",
                               i / float(NFRAME - 1), False)
                    m.render(os.path.join(rdir, "blob_%d.png" % i))
                print("RENDERED", role, "blob", flush=True)

    if folk and (not ONLY or "octopus" in ONLY):
        odir = os.path.join(out_root, "octopus")
        os.makedirs(odir, exist_ok=True)
        h_oct = build_octopus(cute=cute)
        folk_materials()
        front_camera(); front_lights()
        bpy.context.view_layer.update()
        folk_render(os.path.join(odir, "Idle_0.png"))
        m.RES = CELL * 2
        front_camera(); front_lights()
        folk_render(os.path.join(odir, "hero_0.png"))
        m.RES = CELL
        meta["roles"]["octopus"] = {"h": h_oct, "px": round(h_oct * PPM, 1),
                                    "norm_h": 1.60, "blend": "procedural"}
        print("RENDERED octopus", flush=True)

    os.makedirs(OUT, exist_ok=True)
    mp = os.path.join(out_root, "render_meta.json")
    old = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    if old.get("roles"):
        old["roles"].update(meta["roles"]); old.update({k: v for k, v in meta.items() if k != "roles"})
        meta = old
    json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ALL DONE", mp, flush=True)


# ══════════════════════════════════════════════════════════════════
# 2) 후처리 A / B  (Pillow + numpy)
# ══════════════════════════════════════════════════════════════════
def run_post():
    import numpy as np
    from PIL import Image, ImageFilter

    # ═══════════════════════════════════════════════════════════════
    # B안 = 평면 민속화풍 (docs/refs/REF_ART_FLAT_FOLK.md §1 의 원리)
    #   §1-1 제한된 따뜻한 팔레트  → 팔레트 강제 스냅(청록·남색은 사람에게 쓰지 않는다)
    #   §1-2 극단적 명도 대비      → 밝은 면은 크림, 선·그림자는 거의 검정. 중간 명도 없음
    #   §1-3 음영 2단 고정          → 색계열마다 (밝은 면, 그림자) 두 값뿐. 그라데이션 0
    #   §1-4 질감은 손자국          → 종이 결을 곱하기로. 광택 없음
    #   §1-5 장식 무늬가 디테일     → 목 실링의 물결 + 역할마다 다른 옷단 무늬
    #   §1-9 흔들리는 선            → 저주파 노이즈로 화면을 미세하게 뒤틀고,
    #                                외곽선 두께를 자리마다 다르게 한다
    # ═══════════════════════════════════════════════════════════════
    LINE_V = 0.155                 # Freestyle 선(#1a1714, v=0.102)만 잡는 폭
    LINE_RGB = (0x12, 0x10, 0x0D)
    V_LIGHT, V_SHADOW = 0.93, 0.44 # §1-2 극단적 명도 대비 · §1-3 음영 2단 (중간 명도 없음)
    SAT = 1.35                     # 환경광에 씻긴 채도를 재질 수준으로 되돌린다(과장 아님)
    WOBBLE = 1.35                  # px (256 기준) — §1-9
    RING_MIN, RING_MAX = 3, 6      # 외곽선 두께 범위 — 자리마다 달라진다
    GRAIN = 0.055                  # §1-4 종이 결 (512px 쇼케이스에서 거칠어 0.085→0.055)

    def hx(h):
        h = h.lstrip('#')
        return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)

    LINEC = hx(FOLK_LINE)
    CREAM = hx(FOLK_PALETTE["cream"][0])

    def noise(h, w, scale, seed):
        rng = np.random.default_rng(seed)
        small = (rng.random((max(2, h // scale + 2), max(2, w // scale + 2))) * 255).astype(np.uint8)
        return np.asarray(Image.fromarray(small).resize((w, h), Image.BICUBIC),
                          dtype=np.float32) / 255.0

    def load(p):
        return np.asarray(Image.open(p).convert("RGBA"), dtype=np.float32) / 255.0

    def to_img(a):
        return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGBA")

    def warp(a, amp, seed):
        """§1-9 손으로 그은 선 — 저주파 노이즈로 화면 전체를 미세하게 뒤튼다."""
        h, w = a.shape[:2]
        zz = max(1, h // CELL)
        dx = (noise(h, w, 22 * zz, seed) - 0.5) * 2 * amp
        dy = (noise(h, w, 22 * zz, seed + 1) - 0.5) * 2 * amp
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        sy = np.clip(yy + dy, 0, h - 1.001); sx = np.clip(xx + dx, 0, w - 1.001)
        y0 = sy.astype(np.int32); x0 = sx.astype(np.int32)
        fy = (sy - y0)[..., None]; fx = (sx - x0)[..., None]
        y1 = np.minimum(y0 + 1, h - 1); x1 = np.minimum(x0 + 1, w - 1)
        return ((a[y0, x0] * (1 - fx) + a[y0, x1] * fx) * (1 - fy) +
                (a[y1, x0] * (1 - fx) + a[y1, x1] * fx) * fy)

    def two_tone(rgb, T):
        """§1-3 음영 2단. 색상(hue)은 렌더가 이미 팔레트라 그대로 두고 명도만 두 값으로."""
        v = rgb.max(-1); mn = rgb.min(-1)
        sat = np.where(v > 1e-5, (v - mn) / np.maximum(v, 1e-5), 0.0)
        ratio = rgb / np.maximum(v[..., None], 1e-5)
        s2 = np.clip(sat * SAT, 0, 1)
        k = np.where(sat > 1e-4, s2 / np.maximum(sat, 1e-4), 0.0)
        ratio = np.clip(1.0 - (1.0 - ratio) * k[..., None], 0, 1)
        v2 = np.where(v >= T, V_LIGHT, V_SHADOW)
        out = np.clip(v2[..., None] * ratio, 0, 1)
        return np.where((v < LINE_V)[..., None], LINEC, out)

    def motif_mask(kind, tx, ty, H, jit):
        t = ty + jit
        if kind == "hatch":   return ((tx + t).astype(np.int32) % 7) < 2
        if kind == "dots":    return ((tx.astype(np.int32) % 7) < 2) & (np.abs(t - H / 2) < 1.6)
        if kind == "cross":   return (((tx.astype(np.int32) % 9) < 2) & (np.abs(t - H / 2) < 3.4)) | \
                                     ((np.abs(t - H / 2) < 1.2) & ((tx.astype(np.int32) % 9) < 6))
        if kind == "zig":
            tri = np.abs(((tx / 5.0) % 2) - 1) * 2 - 1
            return np.abs(t - (H / 2 + 2.6 * tri)) < 1.4
        if kind == "saw":     return (t - H / 2 + 2.6) > np.abs(((tx % 8) - 4)) * 0.85
        if kind == "bars":    return ((tx.astype(np.int32) % 8) < 2) & (np.abs(t - H / 2) < 4.0)
        if kind == "diamond": return (np.abs((tx % 10) - 5) + np.abs(t - H / 2)) < 3.2
        if kind == "rings":
            rr = np.sqrt(((tx % 10) - 5) ** 2 + (t - H / 2) ** 2)
            return (rr > 1.5) & (rr < 3.0)
        if kind == "wave":    return np.abs(t - (H / 2 + 2.2 * np.sin(tx * 0.72))) < 1.5
        return np.zeros_like(tx, dtype=bool)

    def bands(arr, role, norm_h, T, seed, land=None):
        """§1-5 장식 무늬 — 목 실링의 물결 + 역할마다 다른 옷단 무늬.
        비율 보정판(c)은 목·허리 높이가 달라지므로 렌더가 실측해 넘겨준 land 를 쓴다."""
        h, w = arr.shape[:2]
        z = h / float(CELL)          # 쇼케이스 512px 도 같은 코드로
        u = norm_h / 1.60
        jitfield = (noise(h, w, int(14 * z), seed + 7) - 0.5) * 2.2 * z
        out = arr.copy()
        v = out[..., :3].max(-1)
        if role not in MOTIF:
            return arr
        wave_z = (land or {}).get("wave", 1.030 * u)
        hem_z = (land or {}).get("hem", 0.345 * u)
        for z_m, kind, bh0 in ((wave_z, "wave", 13), (hem_z, MOTIF[role], 16)):
            bh = int(round(bh0 * z))
            r0 = int(round((BASE_Y - z_m * PPM) * z - bh / 2))
            r1 = r0 + bh
            if r0 < 0 or r1 > h:
                continue
            sub = slice(r0, r1)
            yy, xx = np.mgrid[0:bh, 0:w].astype(np.float32)
            mk = motif_mask(kind, xx / z, yy / z, bh / z, jitfield[sub] / z)
            solid = out[sub, :, 3] > 0.6
            mk = mk & solid
            light = v[sub] >= (V_LIGHT + V_SHADOW) / 2   # 밝은 면엔 검정, 그림자엔 크림
            col_dark = LINEC
            col_light = CREAM
            for ch in range(3):
                out[sub, :, ch] = np.where(mk, np.where(light, col_dark[ch], col_light[ch]),
                                           out[sub, :, ch])
        return out

    def outline(arr, seed):
        """두께가 자리마다 달라지는 어두운 외곽선 (§1-9)."""
        z = max(1, int(round(arr.shape[0] / float(CELL))))
        a8 = (arr[..., 3] * 255).astype(np.uint8)
        im = Image.fromarray(a8)
        gA = np.asarray(im.filter(ImageFilter.MaxFilter(RING_MIN * 2 * z + 1))
                          .filter(ImageFilter.GaussianBlur(1.0 * z)), dtype=np.float32) / 255.0
        gB = np.asarray(im.filter(ImageFilter.MaxFilter(RING_MAX * 2 * z + 1))
                          .filter(ImageFilter.GaussianBlur(1.0 * z)), dtype=np.float32) / 255.0
        wgt = np.clip((noise(arr.shape[0], arr.shape[1], 30 * z, seed + 3) - 0.28) * 1.9, 0, 1)
        grown = gA * (1 - wgt) + gB * wgt
        ring = (grown > 0.5) & (arr[..., 3] < 0.5)
        out = arr.copy()
        for ch in range(3):
            out[ring, ch] = LINEC[ch]
        out[ring, 3] = 1.0
        return out

    def folk(a, role, norm_h, T, seed, land=None):
        # 팔레트와 2단 음영은 렌더에서 이미 끝났다. 여기서는 §1-9(흔들리는 선),
        # §1-5(반복 무늬), §1-4(종이 결), 그리고 외곽선만 얹는다.
        # ★ 비율 보정판(c)도 **이 함수를 그대로** 통과한다 — 화풍을 바꾸지 않는다는 보증.
        a = warp(a, WOBBLE * max(1, a.shape[0] // CELL), seed)
        rgb = a[..., :3]
        v = rgb.max(-1)
        rgb = np.where((v < LINE_V)[..., None], LINEC, rgb)   # Freestyle 선을 더 눌러 또렷하게
        out = np.dstack([rgb, a[..., 3]])
        out = bands(out, role, norm_h, T, seed, land)
        g = 1.0 + (noise(a.shape[0], a.shape[1], 3 * max(1, a.shape[0] // CELL),
                         seed + 11) - 0.5) * 2 * GRAIN
        out[..., :3] = np.clip(out[..., :3] * g[..., None], 0, 1)
        return outline(out, seed)

    def threshold(p):
        a = load(p)
        m = (a[..., 3] > 0.5)
        v = a[..., :3].max(-1)[m]
        v = v[v >= LINE_V]
        return float(np.clip(np.percentile(v, 52) if v.size else 0.55, 0.42, 0.72))

    # ── 실행 ─────────────────────────────────────────────────────
    meta = json.load(open(os.path.join(RAW, "render_meta.json"), encoding="utf-8"))
    metaf_p = os.path.join(RAWF, "render_meta.json")
    metaf = json.load(open(metaf_p, encoding="utf-8")) if os.path.exists(metaf_p) else {"roles": {}}
    metac_p = os.path.join(RAWC, "render_meta.json")
    metac = json.load(open(metac_p, encoding="utf-8")) if os.path.exists(metac_p) else {"roles": {}}
    # --cute : 비율 보정판(c)만 다시 만든다. a/b 는 손대지 않는다(화풍 확정분 보호).
    CUTE_ONLY = "--cute" in argv
    roles = ONLY or ([r for r in ROLE_ORDER if r in metac.get("roles", {})] if CUTE_ONLY
                     else [r for r in ROLE_ORDER if r in meta["roles"]])
    for sub in ("a", "b", "c"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    def cute_assets(role, seed):
        """비율 보정판 — **a/b 와 완전히 같은 folk() 후처리**를 통과시킨다."""
        rc = os.path.join(RAWC, role)
        rmeta = metac.get("roles", {}).get(role) or {}
        if not os.path.exists(os.path.join(rc, "Idle_0.png")):
            return None
        nh = rmeta.get("norm_h", 1.60)
        land = rmeta.get("land")
        T = threshold(os.path.join(rc, "Idle_0.png"))
        sheet = Image.new("RGBA", (CELL * NFRAME, CELL * len(CLIPS)), (0, 0, 0, 0))
        for r, clip in enumerate(CLIPS):
            for i in range(NFRAME):
                fp = os.path.join(rc, "%s_%d.png" % (clip, i))
                if os.path.exists(fp):
                    sheet.paste(to_img(folk(load(fp), role, nh, T, seed, land)),
                                (i * CELL, r * CELL))
        sheet.save(os.path.join(OUT, "c", role + ".png"))
        hp = os.path.join(rc, "hero_0.png")
        if os.path.exists(hp):
            to_img(folk(load(hp), role, nh, T, seed, land)).save(
                os.path.join(OUT, "c", role + "_hero.png"))
        ip = os.path.join(rc, "imp3_0.png")
        if os.path.exists(ip):
            to_img(folk(load(ip), role, nh, T, seed, land)).save(
                os.path.join(OUT, "c", role + "_imp3.png"))
        print("CUTE", role, "T=%.3f" % T, "land", land, flush=True)
        return {"threshold_c": round(T, 3), "land_c": land, "h_c": rmeta.get("h")}

    info = {}
    for role in roles:
        if CUTE_ONLY:
            ci = cute_assets(role, 1000 + 7 * ROLE_ORDER.index(role))
            if ci:
                info[role] = ci
            continue
        ra = os.path.join(RAW, role)
        rb = os.path.join(RAWF, role) if role in metaf.get("roles", {}) else ra
        nh = (metaf.get("roles", {}).get(role) or meta["roles"][role]).get("norm_h", 1.60)
        T = threshold(os.path.join(rb, "Idle_0.png"))
        seed = 1000 + 7 * ROLE_ORDER.index(role)
        sa = Image.new("RGBA", (CELL * NFRAME, CELL * len(CLIPS)), (0, 0, 0, 0))
        sb = Image.new("RGBA", (CELL * NFRAME, CELL * len(CLIPS)), (0, 0, 0, 0))
        for r, clip in enumerate(CLIPS):
            for i in range(NFRAME):
                pa = os.path.join(ra, "%s_%d.png" % (clip, i))
                pb = os.path.join(rb, "%s_%d.png" % (clip, i))
                if os.path.exists(pa):
                    sa.paste(to_img(load(pa)), (i * CELL, r * CELL))
                if os.path.exists(pb):
                    sb.paste(to_img(folk(load(pb), role, nh, T, seed)), (i * CELL, r * CELL))
        sa.save(os.path.join(OUT, "a", role + ".png"))
        sb.save(os.path.join(OUT, "b", role + ".png"))
        info[role] = {"threshold": round(T, 3), "motif": MOTIF[role],
                      "motif_ko": MOTIF_KO[MOTIF[role]], "norm_h": nh,
                      "folk_render": rb != ra}
        print("SHEET", role, "T=%.3f" % T, MOTIF[role], flush=True)

        hp_ = os.path.join(rb, "hero_0.png")
        if os.path.exists(hp_):
            to_img(folk(load(hp_), role, nh, T, seed)).save(
                os.path.join(OUT, "b", role + "_hero.png"))
            print("HERO", role, flush=True)

        for tag, src in (("imp3", rb), ):
            fp = os.path.join(src, tag + "_0.png")
            if os.path.exists(fp):
                to_img(load(os.path.join(ra, tag + "_0.png"))).save(
                    os.path.join(OUT, "a", role + "_" + tag + ".png")) \
                    if os.path.exists(os.path.join(ra, tag + "_0.png")) else None
                to_img(folk(load(fp), role, nh, T, seed)).save(
                    os.path.join(OUT, "b", role + "_" + tag + ".png"))
                print("IMP3", role, flush=True)

        bp = os.path.join(ra, "blob_0.png")
        if os.path.exists(bp):
            os.makedirs(os.path.join(OUT, "blob"), exist_ok=True)
            st = Image.new("RGBA", (CELL * NFRAME, CELL), (0, 0, 0, 0))
            for i in range(NFRAME):
                fp = os.path.join(ra, "blob_%d.png" % i)
                if os.path.exists(fp):
                    st.paste(to_img(load(fp)), (i * CELL, 0))
            st.save(os.path.join(OUT, "blob", role + "_pickup_full.png"))
            print("BLOB", role, flush=True)

    # 동거 문어 — 클립 없이 낱장 두 장
    for src_root, sub, key in ((RAWF, "b", "b"), (RAWC, "c", "c")):
        od = os.path.join(src_root, "octopus")
        if not os.path.exists(os.path.join(od, "Idle_0.png")):
            continue
        if CUTE_ONLY and sub != "c":
            continue
        seed = 9001
        T = threshold(os.path.join(od, "Idle_0.png"))
        for s_, d_ in (("Idle_0.png", "octopus_idle.png"), ("hero_0.png", "octopus_hero.png")):
            fp = os.path.join(od, s_)
            if os.path.exists(fp):
                to_img(folk(load(fp), "octopus", 1.60, T, seed)).save(os.path.join(OUT, sub, d_))
        oi = info.setdefault("octopus", {})
        oi.update({"motif": None, "motif_ko": "-", "norm_h": 1.60, "folk_render": True})
        oi["threshold" if sub == "b" else "threshold_c"] = round(T, 3)
        if sub == "c":
            oi["h_c"] = (metac.get("roles", {}).get("octopus") or {}).get("h")
        print("OCTOPUS", sub, flush=True)

    fm_p = os.path.join(OUT, "front_meta.json")
    prev = json.load(open(fm_p, encoding="utf-8")) if os.path.exists(fm_p) else {}
    out_meta = dict(prev)
    out_meta.update({
        "cell": CELL, "ppm": PPM, "baseline": BASE_Y, "ortho": meta.get("ortho"),
        "view": "front_ortho",
        "note": "cell 좌상단 기준. 발 기준선은 셀 위에서 baseline px.",
        "clips": CLIPS, "rows": {c: i for i, c in enumerate(CLIPS)}, "frames": NFRAME,
        "clip_range": meta.get("clip_range"),
        "variants": {"a": "렌더 그대로(부드러운 음영·옅은 선) — 비교용 한 벌",
                     "b": "평면 민속화풍 — 팔레트 강제·음영 2단·역할별 반복 무늬·흔들리는 선",
                     "c": "b 와 같은 화풍 + 비율 보정(3등신·큰 눈·둥근 아래·과장된 동작). "
                          "팔레트·음영·무늬·선은 b 와 한 줄도 다르지 않다"},
        "palette": {k: list(v) for k, v in FOLK_PALETTE.items()},
        "line_color": FOLK_LINE,
        "sheet": "static/art/chars/front/<a|b|c>/<role>.png",
        "hero": HERO,
        "cute": CUTE, "exag": EXAG,
        "cute_roles": [r for r in ROLE_ORDER + ["octopus"] if r in metac.get("roles", {})],
        "anim_seconds": {"Idle": 2.8, "Walk": 0.8, "PickUp": 1.4},
        "imprint_example": {"ids": IMP_TRIPLE, "roles": [r for r in IMP_ROLES if r in roles]},
    })
    prev_roles = dict(prev.get("roles") or {})
    for r in list(roles) + (["octopus"] if "octopus" in info else []):
        base = dict(prev_roles.get(r) or {})
        base.update(meta["roles"].get(r) or metaf.get("roles", {}).get(r) or {})
        base.update(info.get(r, {}))
        prev_roles[r] = base
    out_meta["roles"] = prev_roles
    json.dump(out_meta, open(fm_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ALL DONE", fm_p, flush=True)


if __name__ == "__main__":
    if MODE == "post":
        run_post()
    else:
        run_render()
