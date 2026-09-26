# -*- coding: utf-8 -*-
"""
잔해 방주 — 1막 「정면 평면 단면」용 2D 캐릭터 스프라이트 시험 (S4-C)

  1) 렌더 (Blender 안에서)
     "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --python tools/render_sprites.py -- render
     "...blender.exe" -b --python tools/render_sprites.py -- render scout cook      # 일부 역할만

  2) 후처리 (맨 파이썬, Pillow + numpy)
     python tools/render_sprites.py post

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
if FOLK: MODE = "render"
ONLY = [a for a in argv[1:] if not a.startswith("-")]

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "art_raw", "chars_front")
RAWF = os.path.join(ROOT, "art_raw", "chars_folk")
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
    return "oxblood"


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
    def folk_extras(arm, role):
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
        for o in list(bpy.data.objects):
            if o.type != 'MESH' or not o.data.materials:
                continue
            mn = (o.data.materials[0].name or "").split('.')[0]
            if mn == "eye_white":
                o.scale = tuple(c * 0.44 for c in o.scale)
            elif mn == "eye":
                o.scale = tuple(c * 0.86 for c in o.scale)
        nk = m.bone_pos(arm, "Neck")
        hp = m.bone_pos(arm, "Hips")
        # (2) §3 번역: 털 목도리 → 잠수복 목 실링 고무테. 같은 물결의 반복 3겹
        rub = m.mat("folk_seal", "#43302A", 0.95)
        for dz, r, t in ((-0.030, 0.150, 0.020), (0.012, 0.172, 0.024), (0.054, 0.146, 0.018)):
            m.ring(arm, "Neck", rub, (nk.x, nk.y + 0.010 * u, nk.z + dz * u), r * u, t * u)
        # (3) §1-6 덩어리진 실루엣 — 아래가 넓은 잠수복 자락 + 무게추 벨트
        #     "주민은 헤엄치지 않고 무게추로 해저를 걷는다"(CONCEPT_DEEP_SEA §7) 를 형상으로
        sk = m.mat("folk_skirt", v["body"], 0.92)
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
            hm = m.mat("folk_helm", "#8A7A5E", 0.45, 0.35)
            dk = m.mat("folk_helmdk", "#3B3025", 0.7)
            m.ball(arm, "Head", hm, (hd.x, hd.y + 0.010 * u, hd.z + 0.345 * u),
                   (0.530 * u, 0.520 * u, 0.440 * u))
            m.box(arm, "Head", hm, (hd.x, hd.y - 0.205 * u, hd.z + 0.500 * u),
                  (0.385 * u, 0.150 * u, 0.030 * u), rot=(math.radians(-52), 0, 0))
            m.box(arm, "Head", dk, (hd.x, hd.y - 0.165 * u, hd.z + 0.450 * u),
                  (0.400 * u, 0.030 * u, 0.030 * u))
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
            e0.position = 0.0; e0.color = (*m.hexcol(shadowc), 1)
            e1.position = 0.42; e1.color = (*m.hexcol(lightc), 1)
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
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)

    roles = ONLY or ROLE_ORDER
    folk = "--folk" in argv or FOLK
    out_root = RAWF if folk else RAW
    meta = {"cell": CELL, "ppm": PPM, "baseline": BASE_Y, "ortho": round(ORTHO, 4),
            "view": "front_ortho", "clips": CLIPS, "frames": NFRAME, "roles": {}}

    for role in roles:
        rdir = os.path.join(out_root, role)
        os.makedirs(rdir, exist_ok=True)
        # 한 번만 짓고 클립을 갈아 끼운다 (역할당 blend 로드 1회)
        arm, mesh, props, _ = m.build(role, "Idle", 0.0)
        if folk:
            folk_extras(arm, role); folk_materials()
        base_loc = tuple(arm.location)
        front_camera(); front_lights()
        lo, hi = m.evaluated_bounds([mesh])
        for clip, t0, t1, cyclic in CLIP_SPEC:
            act = next((a for a in bpy.data.actions if a.name == clip), None)
            if act is None:
                print("MISSING CLIP", role, clip, flush=True); continue
            for i in range(NFRAME):
                f = i / float(NFRAME) if cyclic else i / float(NFRAME - 1)
                m.assign_action(arm, act, t0 + (t1 - t0) * f)
                arm.location = base_loc          # 기준선은 Idle 로 고정
                bpy.context.view_layer.update()
                (folk_render if folk else m.render)(os.path.join(rdir, "%s_%d.png" % (clip, i)))
        meta["roles"][role] = {"h": round(hi - lo, 4), "px": round((hi - lo) * PPM, 1),
                               "norm_h": m.ROLE_DEF[role]["h"],
                               "blend": m.ROLE_DEF[role]["blend"]}
        print("RENDERED", role, "h=%.4f" % (hi - lo), flush=True)

        # 각인 3개 겹침 변형 (Idle 0프레임 한 장)
        if role in IMP_ROLES:
            arm, mesh, props, imps = m.build(role, "Idle", 0.0, imprints=True)
            if folk:
                folk_extras(arm, role); folk_materials()
            for iid, e, parts in imps:
                vis = iid in IMP_TRIPLE
                for o in [e] + parts:
                    o.hide_viewport = not vis; o.hide_render = not vis
            front_camera(); front_lights()
            arm.location = base_loc
            bpy.context.view_layer.update()
            (folk_render if folk else m.render)(os.path.join(rdir, "imp3_0.png"))
            print("RENDERED", role, "imp3", flush=True)

        # 실패 컷 — PickUp 전 구간(0~100%). 비교 페이지 §5 에 "쓰지 않는 이유"로 붙인다.
        if role in IMP_ROLES and not folk:
            arm, mesh, props, _ = m.build(role, "Idle", 0.0)
            front_camera(); front_lights()
            act = next((a for a in bpy.data.actions if a.name == "PickUp"), None)
            if act:
                for i in range(NFRAME):
                    m.assign_action(arm, act, i / float(NFRAME - 1))
                    arm.location = base_loc
                    bpy.context.view_layer.update()
                    m.render(os.path.join(rdir, "blob_%d.png" % i))
                print("RENDERED", role, "blob", flush=True)

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
    GRAIN = 0.085                  # §1-4 종이 결

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
        dx = (noise(h, w, 22, seed) - 0.5) * 2 * amp
        dy = (noise(h, w, 22, seed + 1) - 0.5) * 2 * amp
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

    def bands(arr, role, norm_h, T, seed):
        """§1-5 장식 무늬 — 목 실링의 물결 + 역할마다 다른 옷단 무늬."""
        h, w = arr.shape[:2]
        u = norm_h / 1.60
        jitfield = (noise(h, w, 14, seed + 7) - 0.5) * 2.2
        out = arr.copy()
        v = out[..., :3].max(-1)
        for z_m, kind, bh in ((1.030 * u, "wave", 13), (0.345 * u, MOTIF[role], 16)):
            r0 = int(round(BASE_Y - z_m * PPM - bh / 2))
            r1 = r0 + bh
            if r0 < 0 or r1 > h:
                continue
            sub = slice(r0, r1)
            yy, xx = np.mgrid[0:bh, 0:w].astype(np.float32)
            mk = motif_mask(kind, xx, yy, bh, jitfield[sub])
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
        a8 = (arr[..., 3] * 255).astype(np.uint8)
        im = Image.fromarray(a8)
        gA = np.asarray(im.filter(ImageFilter.MaxFilter(RING_MIN * 2 + 1))
                          .filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255.0
        gB = np.asarray(im.filter(ImageFilter.MaxFilter(RING_MAX * 2 + 1))
                          .filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255.0
        wgt = np.clip((noise(arr.shape[0], arr.shape[1], 30, seed + 3) - 0.28) * 1.9, 0, 1)
        grown = gA * (1 - wgt) + gB * wgt
        ring = (grown > 0.5) & (arr[..., 3] < 0.5)
        out = arr.copy()
        for ch in range(3):
            out[ring, ch] = LINEC[ch]
        out[ring, 3] = 1.0
        return out

    def folk(a, role, norm_h, T, seed):
        # 팔레트와 2단 음영은 렌더에서 이미 끝났다. 여기서는 §1-9(흔들리는 선),
        # §1-5(반복 무늬), §1-4(종이 결), 그리고 외곽선만 얹는다.
        a = warp(a, WOBBLE, seed)
        rgb = a[..., :3]
        v = rgb.max(-1)
        rgb = np.where((v < LINE_V)[..., None], LINEC, rgb)   # Freestyle 선을 더 눌러 또렷하게
        out = np.dstack([rgb, a[..., 3]])
        out = bands(out, role, norm_h, T, seed)
        g = 1.0 + (noise(a.shape[0], a.shape[1], 3, seed + 11) - 0.5) * 2 * GRAIN
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
    roles = ONLY or [r for r in ROLE_ORDER if r in meta["roles"]]
    for sub in ("a", "b"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    info = {}
    for role in roles:
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

    out_meta = {
        "cell": CELL, "ppm": PPM, "baseline": BASE_Y, "ortho": meta.get("ortho"),
        "view": "front_ortho",
        "note": "cell 좌상단 기준. 발 기준선은 셀 위에서 baseline px.",
        "clips": CLIPS, "rows": {c: i for i, c in enumerate(CLIPS)}, "frames": NFRAME,
        "clip_range": meta.get("clip_range"),
        "variants": {"a": "렌더 그대로(부드러운 음영·옅은 선) — 비교용 한 벌",
                     "b": "평면 민속화풍 — 팔레트 강제·음영 2단·역할별 반복 무늬·흔들리는 선"},
        "palette": {k: list(v) for k, v in FOLK_PALETTE.items()},
        "line_color": FOLK_LINE,
        "sheet": "static/art/chars/front/<a|b>/<role>.png",
        "hero": HERO,
        "imprint_example": {"ids": IMP_TRIPLE, "roles": [r for r in IMP_ROLES if r in roles]},
        "roles": {r: dict(meta["roles"][r], **info.get(r, {})) for r in roles},
    }
    json.dump(out_meta, open(os.path.join(OUT, "front_meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("ALL DONE", os.path.join(OUT, "front_meta.json"), flush=True)


if __name__ == "__main__":
    if MODE == "post":
        run_post()
    else:
        run_render()
