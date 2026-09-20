# -*- coding: utf-8 -*-
"""
잔해 방주 — 바깥(연속 지형) 씬 에셋. S2-D ②③④⑤
blender -b --python tools/blender_scenes.py -- facade
blender -b --python tools/blender_scenes.py -- spot
blender -b --python tools/blender_scenes.py -- dino
blender -b --python tools/blender_scenes.py -- skyline
blender -b --python tools/blender_scenes.py -- all

산출물
  static/models/scenes/mall_facade.glb        몰 정면 파사드 (폭 30m×높이 8m, 원점 = 입구 바닥 중심, 정면 -Y)
  static/models/scenes/spot_flooded_train.glb 힐링 스팟 「물에 잠긴 전철」 (18×12m, 재질 "Water", 마커 koi_1~5)
  static/art/parallax/dino_far.png            트리케라톱스·스테고 실루엣 열 (1600×300 RGBA)
  static/art/parallax/dino_near.png           랩터 2 (1200×300 RGBA)
  static/art/parallax/skyline.png             부족 방향 랜드마크 6 + 초록 덮인 아파트 (2400×400 RGBA)
  art_raw/world/*.png                         검수용 45°/45° 프리뷰 렌더

원칙: B1 한 색 한 등불 / B2 초록·주황·청록 / B3 안은 어둡고 밖은 밝다 / B6 45°45° 직교
      / B8 GLB ≤1.5MB(join) / B9 자연은 흩어서 / B10 힐링 스팟에 거주 요소 0
"""
import bpy, sys, os, math, importlib.util, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT_SCENES = os.path.join(ROOT, "static", "models", "scenes")
OUT_PARA = os.path.join(ROOT, "static", "art", "parallax")
OUT_RAW = os.path.join(ROOT, "art_raw", "world")
DINO_FBX = os.path.join(ROOT, "assets3d", "quaternius_dinos", "Dinosaur Animated Pack - Dec 2018", "FBX")
for d in (OUT_SCENES, OUT_PARA, OUT_RAW):
    os.makedirs(d, exist_ok=True)


def load_iso():
    """blender_iso.py의 재질·원시도형·CC0 소품 헬퍼를 그대로 재사용(정의 중복 금지)."""
    spec = importlib.util.spec_from_file_location("blender_iso", os.path.join(HERE, "blender_iso.py"))
    m = importlib.util.module_from_spec(spec)
    saved = list(sys.argv)
    sys.argv = [saved[0], "--", os.path.join(ROOT, "art_raw", "iso"), "__none__"]
    spec.loader.exec_module(m)
    sys.argv = saved
    return m


iso = load_iso()


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    iso.sc = bpy.context.scene
    iso.make_materials()
    return iso.M


def alpha_mat(name, hexc, alpha=0.3, rough=0.12):
    m = iso.mat(name, hexc, rough)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Alpha"].default_value = alpha
    for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
        try:
            setattr(m, attr, val)
        except Exception:
            pass
    return m


# ── 내보내기 ────────────────────────────────────────────────
def _has_tex(m):
    return bool(m and m.use_nodes and any(n.type == 'TEX_IMAGE' for n in m.node_tree.nodes))


def join_scene(name="scene", keep_prefix=("koi_", "keep_", "marker_")):
    """정적 메시를 둘로 합친다(텍스처 소품 / 단색 원시도형). keep_prefix 노드와 빈 오브젝트는 보존."""
    for o in list(bpy.data.objects):          # 프리뷰 전용 오브젝트(지면·조명)는 합치기 전에 버린다
        if o.name.startswith("PRV_"):
            bpy.data.objects.remove(o, do_unlink=True)
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name in bpy.context.view_layer.objects]
    objs = [o for o in objs if not o.name.startswith(keep_prefix)]
    tex = [o for o in objs if any(_has_tex(m) for m in o.data.materials)]
    flat = [o for o in objs if o not in tex]
    for group, strip in ((flat, True), (tex, False)):
        if len(group) < 1:
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
    # 노드 트랜스폼을 구워 로컬좌표 = 월드좌표로 만든다(개발이 bbox·원점을 그대로 신뢰할 수 있게).
    bpy.ops.object.select_all(action='DESELECT')
    bake = [o for o in bpy.data.objects if o.type == 'MESH' and o.name in bpy.context.view_layer.objects]
    for o in bake:
        o.select_set(True)
    if bake:
        bpy.context.view_layer.objects.active = bake[0]
        try:
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        except Exception as e:
            print("BAKE SKIPPED", e, flush=True)
    for o in list(bpy.data.objects):     # 빈 부모 empty 정리(마커는 이름으로 보존)
        if o.type == 'EMPTY' and not o.children and not o.name.startswith(keep_prefix):
            bpy.data.objects.remove(o, do_unlink=True)
    # 합쳐진 두 메시에 읽을 수 있는 이름을 준다
    rest = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith(keep_prefix)]
    for o in rest:
        o.name = f"{name}_tex" if any(_has_tex(m) for m in o.data.materials) else f"{name}_body"
    print("JOINED", len(flat), "flat +", len(tex), "textured ->", [o.name for o in rest], flush=True)


def export(path):
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA' or o.name.startswith("PRV_"):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_lights=True, export_cameras=False,
                              export_apply=True, use_selection=False, export_animations=False, export_yup=True)
    print("EXPORTED", path, os.path.getsize(path) // 1024, "KB", flush=True)


# ── 프리뷰 렌더(45°/45° 직교, B6) ───────────────────────────
def preview(path, ortho, target=(0, 0, 2.0), res=(1280, 800), az=45, el=45, freestyle=True, exposure=0.4):
    sc = bpy.context.scene
    a, e = math.radians(az), math.radians(el)
    d = 60.0
    loc = Vector((-math.cos(e) * math.sin(a) * d, -math.cos(e) * math.cos(a) * d, math.sin(e) * d)) + Vector(target)
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    cam.rotation_euler = (Vector(target) - loc).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    sc.render.use_freestyle = freestyle; sc.render.line_thickness = 1.1
    if freestyle:
        fs = sc.view_layers[0].freestyle_settings
        ls = fs.linesets[0] if fs.linesets else fs.linesets.new("relic")
        ls.select_silhouette = ls.select_crease = ls.select_border = True
        if ls.linestyle is None:
            ls.linestyle = bpy.data.linestyles.new("relic_ls")
        ls.linestyle.color = iso.hexcol("#1a1714"); ls.linestyle.thickness = 1.1
    names = [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items]
    sc.view_settings.view_transform = 'AgX' if 'AgX' in names else 'Filmic'
    sc.view_settings.exposure = exposure
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("PREVIEW", path, flush=True)
    bpy.data.objects.remove(cam, do_unlink=True)


def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def sky(top="#9fb6bd", bot="#6d7d78", strength=1.0):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*iso.hexcol(top), 1); bg.inputs[1].default_value = strength


# ══════════════════════════════════════════════════════════════
# ② 몰 정면 파사드 — 폭 30m × 높이 8m, 원점 = 입구 바닥 중심, 정면 -Y
# ══════════════════════════════════════════════════════════════
FW, FH, FT = 30.0, 8.0, 0.55           # 폭 / 높이 / 벽 두께(+Y 쪽이 실내)
DOOR_W, DOOR_H = 6.0, 3.9              # 뚫린 입구(문턱)
PIERS = [-15.0, -11.5, -7.5, -3.0, 3.0, 7.5, 11.5, 15.0]
Z_SILL, Z_SPAN0, Z_SPAN1, Z_PARA = 0.35, 3.9, 4.7, 7.25


def _glazing(M, x0, x1, z0, z1, seed, glass, backdrop=True):
    """멀리언 격자 + 깨진 유리(일부 온전한 반투명 판, 일부 조각, 일부 비어 있음)."""
    r = random.Random(seed)
    cube, cyl = iso.cube, iso.cyl
    span = x1 - x0
    nv = max(1, int(round(span / 1.35)))
    nh = max(1, int(round((z1 - z0) / 1.3)))
    xs = [x0 + span * i / nv for i in range(nv + 1)]
    zs = [z0 + (z1 - z0) * j / nh for j in range(nh + 1)]
    if backdrop:                                   # 어두운 실내(B3) — 개발이 실제 내부를 넣으면 지울 수 있게 별도 오브젝트
        b = cube("keep_interior", ((x0 + x1) / 2, 1.15, (z0 + z1) / 2), (span - 0.1, 0.05, z1 - z0), M["_dark"])
        b.name = "keep_interior_backdrop"
    for x in xs:                                   # 세로 멀리언
        cube("mull", (x, 0.10, (z0 + z1) / 2), (0.09, 0.22, z1 - z0), M["metal_lt"])
    for z in zs:                                   # 가로 트랜섬
        cube("tran", ((x0 + x1) / 2, 0.10, z), (span, 0.20, 0.10), M["metal_lt"])
    for i in range(nv):
        for j in range(nh):
            cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            w, h = xs[i + 1] - xs[i] - 0.11, zs[j + 1] - zs[j] - 0.11
            k = r.random()
            if k < 0.42:                            # 온전한 유리 (반투명)
                cube("pane", (cx, 0.13, cz), (w, 0.02, h), glass)
            elif k < 0.76:                          # 깨진 유리: 프레임에 붙은 조각 2~3개
                for _ in range(r.randint(2, 3)):
                    sx = r.choice([-1, 1]); sz = r.choice([-1, 1])
                    pw, ph = w * r.uniform(0.2, 0.42), h * r.uniform(0.2, 0.45)
                    cube("shardp", (cx + sx * (w / 2 - pw / 2), 0.13, cz + sz * (h / 2 - ph / 2)),
                         (pw, 0.02, ph), glass, rot=(0, r.uniform(-0.12, 0.12), 0))
            # else: 완전히 비어 있음


def scene_mall_facade():
    M = fresh()
    cube, cyl, sphere, prop = iso.cube, iso.cyl, iso.sphere, iso.prop
    M["_dark"] = iso.mat("InteriorDark", "#141513", 1.0)
    M["rust"] = iso.mat("rust", "#7a4a2e", 0.9)
    M["sign"] = iso.mat("signpanel", "#5c5f56", 0.85)
    glass = alpha_mat("FacadeGlass", "#7d9ba0", 0.20)
    r = random.Random(4041)

    # ── 구조: 기둥 · 기초 · 스팬드럴 · 파라펫
    for x in PIERS:
        cube("pier", (x, FT / 2, FH / 2), (0.7, FT, FH), M["concrete"])
    for x0, x1 in ((-15.0, -3.0), (3.0, 15.0)):     # 입구를 뺀 기초 turf
        cube("plinth", ((x0 + x1) / 2, 0.3, Z_SILL / 2), (x1 - x0, 0.9, Z_SILL), M["concrete_dk"])
    cube("spandrel", (0, FT / 2 - 0.05, (Z_SPAN0 + Z_SPAN1) / 2), (FW, FT + 0.1, Z_SPAN1 - Z_SPAN0), M["concrete"])
    cube("spanlip", (0, -0.12, Z_SPAN0 + 0.10), (FW, 0.22, 0.14), M["concrete_dk"])
    cube("parapet", (0, FT / 2 - 0.05, (Z_PARA + FH) / 2), (FW, FT + 0.12, FH - Z_PARA), M["concrete"])
    cube("coping", (0, FT / 2 - 0.10, FH + 0.05), (FW + 0.3, FT + 0.3, 0.16), M["concrete_dk"])
    cube("floorslab", (0, FT + 0.6, 0.06), (FW, 1.2, 0.12), M["concrete_dk"])   # 실내 바닥 시작선
    for sx in (-1, 1):                              # 양 끝 리턴 벽 — 평면이 아니라 '건물 모서리'로 읽히게
        cube("return", (sx * (FW / 2 - 0.35), 1.7, FH / 2), (0.7, 2.9, FH), M["concrete_dk"])
        cube("retcop", (sx * (FW / 2 - 0.35), 1.7, FH + 0.05), (0.9, 3.1, 0.16), M["concrete_dk"])

    # ── 유리 파사드: 1층(입구 제외) + 2층(전폭)
    bays = list(zip(PIERS[:-1], PIERS[1:]))
    for i, (x0, x1) in enumerate(bays):
        if abs(x0 + 3.0) < 0.01 and abs(x1 - 3.0) < 0.01:
            continue                                  # 입구 칸: 1층은 뚫린다
        _glazing(M, x0 + 0.35, x1 - 0.35, Z_SILL, Z_SPAN0, 700 + i, glass)
    for i, (x0, x1) in enumerate(bays):
        _glazing(M, x0 + 0.35, x1 - 0.35, Z_SPAN1, Z_PARA, 800 + i, glass)

    # ── 입구(문턱): 폭 6m, 뒤판 없음 → 안쪽 어둠이 그대로 보인다
    cube("thresh", (0, -0.25, 0.07), (DOOR_W + 0.6, 1.3, 0.14), M["concrete_dk"])
    cube("threshtop", (0, -0.25, 0.145), (DOOR_W + 0.2, 1.1, 0.03), M["tile"])
    for sx in (-1, 1):                                 # 문설주
        cube("jamb", (sx * (DOOR_W / 2 + 0.12), 0.25, DOOR_H / 2), (0.24, FT * 0.9, DOOR_H), M["metal_lt"])
    cube("lintel", (0, 0.25, DOOR_H + 0.12), (DOOR_W + 0.7, FT * 0.9, 0.24), M["metal_lt"])
    for sx in (-1, 1):                                 # 입구 리빌: 안쪽으로 이어지는 옆벽 (뒤판은 없음)
        cube("reveal", (sx * (DOOR_W / 2 + 0.3), 2.3, 2.1), (0.42, 4.0, 4.2), M["_dark"])
    cube("soffit", (0, 2.3, DOOR_H + 0.35), (DOOR_W + 1.0, 4.0, 0.5), M["_dark"])
    cube("infloor", (0, 2.3, 0.02), (DOOR_W, 4.0, 0.06), M["_dark"])
    for k in range(7):                                 # 반쯤 말려 올라간 셔터
        cube("shut", (0, 0.42, DOOR_H - 0.06 - k * 0.11), (DOOR_W - 0.1, 0.07, 0.09), M["rust"])
    cyl("shutroll", (0, 0.42, DOOR_H + 0.30), 0.26, DOOR_W - 0.2, M["rust"], rot=(0, math.radians(90), 0), verts=12)
    cube("doorleaf", (-DOOR_W / 2 + 0.55, -0.55, 1.15), (0.9, 0.06, 2.3), glass,
         rot=(math.radians(-72), 0, math.radians(14)))  # 떨어져 기대어 선 문짝 한 장

    # ── 무너진 캐노피: 오른쪽은 남고 왼쪽은 내려앉았다
    cube("canR", (3.4, -1.55, 4.25), (4.4, 3.2, 0.22), M["concrete"])
    cube("canRlip", (3.4, -3.12, 4.18), (4.4, 0.18, 0.34), M["concrete_dk"])
    cyl("canpost", (4.9, -2.95, 2.12), 0.13, 4.25, M["metal_lt"], verts=10)
    cube("canL", (-6.4, -1.75, 2.85), (5.0, 3.4, 0.2), M["concrete"], rot=(math.radians(-31), 0, math.radians(-6)))
    cyl("canpostb", (-7.6, -2.55, 0.9), 0.13, 2.4, M["metal_lt"], rot=(math.radians(34), 0, 0), verts=10)
    cyl("canpostc", (-7.4, -1.35, 0.14), 0.13, 1.9, M["metal_lt"], rot=(math.radians(88), 0, math.radians(20)), verts=10)
    for k in range(5):                                 # 늘어진 철근
        cyl("rebar", (-4.2 + k * 0.5, -3.0 + (k % 2) * 0.3, 2.1 - k * 0.12), 0.02, 1.3 + r.random(),
            M["rust"], rot=(math.radians(60 + k * 6), 0, r.uniform(-0.5, 0.5)), verts=6)
    cube("candeb", (-8.8, -3.3, 0.16), (2.4, 1.7, 0.3), M["concrete_dk"], rot=(0, math.radians(6), math.radians(-18)))

    # ── 간판 잔해 (글자 없음): 프레임만 남고 패널 일부 탈락, 한쪽만 매달림
    cube("signframe", (-8.0, -0.85, 5.95), (8.6, 0.22, 1.9), M["metal_lt"], rot=(0, math.radians(15), 0))
    cube("signrail", (-8.0, -0.90, 6.85), (8.8, 0.26, 0.18), M["rust"], rot=(0, math.radians(15), 0))
    for k in range(7):                                 # 패널 일부 탈락 (글자 없음 — 형태만)
        if k in (1, 5):
            continue
        cube("signpanel", (-11.6 + k * 1.2, -0.96, 5.95 + (k - 3.0) * 0.32), (1.06, 0.08, 1.5), M["sign"], rot=(0, math.radians(15), 0))
    for hx, hz in ((-11.9, 7.6), (-4.2, 7.0)):         # 매단 고리(왼쪽 하나는 끊겨 짧다)
        cyl("signhang", (hx, -0.5, hz), 0.025, 1.4 if hx < -8 else 0.5, M["rust"], verts=6)
    cube("signfall", (9.6, -2.2, 0.18), (3.1, 1.15, 0.12), M["sign"], rot=(math.radians(4), 0, math.radians(27)))
    cube("signfall2", (11.4, -1.1, 0.5), (1.6, 0.9, 0.1), M["sign"], rot=(math.radians(58), 0, math.radians(-12)))
    cube("signbox", (8.2, -0.38, 5.4), (3.4, 0.5, 1.1), M["metal_lt"])     # 남은 간판 상자(면 없음)
    cube("signboxin", (8.2, -0.20, 5.4), (3.1, 0.2, 0.86), M["_dark"])

    # ── 덩굴·이끼·어린 나무 (B9: 흩되 입구 앞 길은 비운다)
    vine_x = [-14.2, -11.4, -8.3, -5.0, 4.6, 7.6, 10.4, 12.9, 14.4]
    for i, vx in enumerate(vine_x):
        iso.vine(vx + r.uniform(-0.3, 0.3), -0.30, FH - 0.1, r.uniform(1.6, 4.4), 'y', 300 + i, lod=True)
    for i in range(11):                                 # 벽을 타는 담쟁이 뭉치
        vx = r.uniform(-14.5, 14.5)
        if abs(vx) < 3.6:
            continue
        vz = r.uniform(0.5, 6.4)
        for k in range(r.randint(3, 6)):
            sphere("ivy", (vx + r.uniform(-0.6, 0.6), -0.22, vz + r.uniform(-0.5, 0.5)),
                   0.19 + r.random() * 0.16, M["leaf"] if k % 2 else M["leaf_dk"], 10, 6)
    for i in range(11):
        x = r.uniform(-14, 14) if i < 7 else r.uniform(5.5, 14)
        if abs(x) < 4.2:
            continue
        iso.sapling(x, -1.3 - r.random() * 1.9, 0.9 + r.random() * 1.4, seed=i)
    # 바닥 이끼·잔디 데칼은 넣지 않는다 — 지형 스플랫(moss.png·grass.png)의 몫이고, 여기 넣으면 z-파이팅이 난다.
    for i in range(14):                                 # 입체 잔해 (CC0)
        x = r.uniform(-14.5, 14.5)
        if abs(x) < 3.8:
            continue
        prop(r.choice(["k:rock-a", "k:rock-c", "k:resource-planks", "k:metal-panel-narrow"]),
             x, -1.1 - r.random() * 2.3, 0, h=0.25 + r.random() * 0.5, rot_z=r.random() * 6)
    iso.shards(-2.0, -1.5, n=9, spread=1.2, seed=3)
    iso.shards(3.2, -1.9, n=8, spread=1.4, seed=5)
    iso.shards(-8.4, -1.2, n=7, spread=1.5, seed=7)

    # ── 프리뷰 조명(밖은 밝고 차갑다 · B3) — 내보내기 전에 제거
    sky("#8ba4ab", strength=0.9)
    bpy.ops.object.light_add(type='SUN', location=(-10, -16, 20), rotation=(math.radians(52), math.radians(6), math.radians(-38)))
    s = bpy.context.object; s.name = "PRV_sun"; s.data.energy = 2.6; s.data.color = (1.0, 0.94, 0.84)
    bpy.ops.object.light_add(type='AREA', location=(0, -14, 10), rotation=(math.radians(62), 0, 0))
    f = bpy.context.object; f.name = "PRV_fill"; f.data.energy = 260; f.data.size = 26; f.data.color = (0.76, 0.85, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, -8, -0.02))     # 프리뷰용 지면(내보내지 않음)
    g = bpy.context.object; g.name = "PRV_ground"
    g.data.materials.append(iso.mat("prvground", "#4a5240", 1.0))

    preview(os.path.join(OUT_RAW, "mall_facade.png"), ortho=33.0, target=(0, -1.0, 2.6), res=(1400, 900), exposure=-0.15)
    preview(os.path.join(OUT_RAW, "mall_facade_front.png"), ortho=32.0, target=(0, 0, 4.0), res=(1400, 480),
            az=0, el=8, exposure=-0.15)      # 정면 입면 — 폭·높이·입구 6m 검증용
    join_scene("mall_facade")
    export(os.path.join(OUT_SCENES, "mall_facade.glb"))


# ══════════════════════════════════════════════════════════════
# ③ 힐링 스팟 「물에 잠긴 전철」 — 18×12m. 거주 요소 0 (B10)
# ══════════════════════════════════════════════════════════════
SX, SY = 18.0, 12.0
WATER_Z = 0.14            # 물 표면. 승강장 상면 z=0, 선로 바닥 z=-1.05
TRENCH_Y0, TRENCH_Y1 = -1.8, 2.5
# 개발이 금붕어를 인스턴스로 뿌릴 빈 수면(소품·수초 금지 구역). 6.0 × 4.0 m
KOI_ZONE = (-3.0, 3.0, -5.9, -1.9)      # x0, x1, y0, y1
# 사람이 서는 문간 하나(B10). 6m 격자선 x=-6.0 위, 스팟 바깥 가장자리(y=-6)에서 들어온다.
THRESH_X, THRESH_Y, THRESH_W = -6.0, -5.2, 1.5


def _in_koi(x, y, pad=0.3):
    x0, x1, y0, y1 = KOI_ZONE
    return (x0 - pad) < x < (x1 + pad) and (y0 - pad) < y < (y1 + pad)


def scene_spot_flooded_train():
    M = fresh()
    cube, cyl, sphere, prop = iso.cube, iso.cyl, iso.sphere, iso.prop
    r = random.Random(5150)
    # 개발이 셰이더로 교체할 물 — 재질 이름은 정확히 "Water"
    water = alpha_mat("Water", "#39a8a4", 0.38, rough=0.04)
    water.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (*iso.hexcol("#4bc4bd"), 1)
    water.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.18
    M["flower"] = iso.mat("flower", "#e2879f", 0.75)
    M["flower2"] = iso.mat("flower2", "#f0b7c6", 0.75)
    M["seat"] = iso.mat("seat", "#b06a34", 0.9)
    M["carbody"] = iso.mat("carbody", "#9aa3a6", 0.55, metallic=0.35)
    M["carband"] = iso.mat("carband", "#3f7f4f", 0.7)      # 노선색 띠(초록 노선)
    M["cardark"] = iso.mat("cardark", "#1b2124", 1.0)
    glass = alpha_mat("TrainGlass", "#9fc2c4", 0.22)

    # ── 승강장(-Y) · 선로 트렌치 · 뒷벽(+Y, +X)
    cube("platform", (0, -3.9, -0.25), (SX, 4.2, 0.5), M["tile"])
    for i in range(-8, 9):                                  # 타일 줄눈
        cube("pg", (i * 1.0, -3.9, 0.004), (0.035, 4.2, 0.008), M["tile2"])
    for k in range(5):
        cube("pgh", (0, -5.7 + k * 1.0, 0.004), (SX, 0.035, 0.008), M["tile2"])
    cube("edgeband", (0, -1.95, 0.02), (SX, 0.34, 0.05), M["line"])        # 노선색 승강장 띠(B5)
    cube("tactile", (0, -2.28, 0.018), (SX, 0.32, 0.04), M["yellow"])      # 점자블록 자리
    cube("edgelip", (0, -1.75, -0.3), (SX, 0.12, 0.6), M["concrete_dk"])
    cube("trench", (0, 0, -1.3), (SX, TRENCH_Y1 - TRENCH_Y0, 0.5), M["concrete_dk"])
    for ry in (-0.72, 0.72):                                 # 레일
        cube("rail", (0, ry, -0.99), (SX, 0.09, 0.12), M["rail"])
    for k in range(13):                                      # 침목
        cube("tie", (-8.4 + k * 1.4, 0, -1.03), (0.28, 2.1, 0.1), M["wood_dk"])
    cube("backwall", (0, 5.0, 2.1), (SX, 0.5, 4.2), M["concrete"])
    cube("backtile", (0, 4.72, 1.0), (SX, 0.04, 2.0), M["tile"])
    cube("backline", (0, 4.69, 1.95), (SX, 0.04, 0.16), M["line"])
    cube("endwall", (8.75, 1.2, 2.1), (0.5, 7.9, 4.2), M["concrete"])
    # 터널 입구 아치(+X 끝, 어둠 — B3의 경계)
    cube("arch", (8.55, 0, 1.35), (0.16, 3.3, 2.9), M["_dark"] if "_dark" in M else M["concrete_dk"])
    for k in range(9):
        a = math.radians(180 * k / 8)
        cube("archrim", (8.5, math.cos(a) * 1.75, 1.75 + math.sin(a) * 1.5), (0.26, 0.34, 0.34), M["concrete_dk"])

    # ── 천장 + 빛기둥용 구멍 2개 (A: x 0.4~3.6 · y 0.5~3.0 / B: x -5.2~-3.4 · y 1.0~2.4)
    HOLE_A = (0.4, 3.6, 2.6, 4.6)
    HOLE_B = (-5.2, -3.4, 3.0, 4.4)
    for x0, x1, y0, y1 in ((-9.0, 9.0, 2.2, 2.6),
                           (-9.0, 0.4, 2.6, 3.0), (3.6, 9.0, 2.6, 3.0),
                           (-9.0, -5.2, 3.0, 4.4), (-3.4, 0.4, 3.0, 4.4), (3.6, 9.0, 3.0, 4.4),
                           (-9.0, 0.4, 4.4, 4.6), (3.6, 9.0, 4.4, 4.6),
                           (-9.0, 9.0, 4.6, 6.0)):
        cube("ceil", ((x0 + x1) / 2, (y0 + y1) / 2, 4.3), (x1 - x0, y1 - y0, 0.4), M["concrete"])
    for bx in (-7.2, -0.8, 5.6):                     # 승강장 위는 가는 보만 — 지하는 읽히되 내부는 보인다
        cube("ceilbeam", (bx, -1.8, 4.28), (0.20, 7.2, 0.34), M["tile"])
    for bx in (-7.2, 5.6):                           # 기둥은 양 끝에만
        cyl("col", (bx, -5.4, 2.1), 0.20, 4.2, M["tile"], verts=12)
    for (hx0, hx1, hy0, hy1), nseg in ((HOLE_A, 16), (HOLE_B, 11)):    # 구멍 가장자리 파편
        cx, cy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
        rx, ry2 = (hx1 - hx0) / 2, (hy1 - hy0) / 2
        for k in range(nseg):
            a = math.radians(360 * k / nseg)
            cube("holerim", (cx + math.cos(a) * rx * 1.06, cy + math.sin(a) * ry2 * 1.06, 4.12 - r.random() * 0.25),
                 (0.5 + r.random() * 0.4, 0.5 + r.random() * 0.4, 0.22), M["concrete_dk"],
                 rot=(r.uniform(-.3, .3), r.uniform(-.3, .3), a))
    for k in range(5):
        cyl("hrebar", (1.2 + k * 0.5, 1.2 + (k % 2) * 1.0, 3.75), 0.02, 1.2 + r.random(), M["rail"],
            rot=(math.radians(70 + k * 8), 0, r.uniform(0, 3)), verts=6)
    for k in range(4):                                       # 큰 구멍에서 쏟아지는 덩굴
        iso.vine(0.9 + k * 0.85, 2.9 + (k % 2) * 1.3, 4.05, 1.6 + r.random() * 1.8, 'x', 60 + k, lod=True)
    for k in range(2):                                       # 작은 구멍에서
        iso.vine(-4.8 + k * 0.9, 3.3 + k * 0.7, 4.05, 1.2 + r.random() * 1.3, 'x', 70 + k, lod=True)

    # ── 멈춘 객차 1량 (x -5.6 ~ 5.6, 선로 위). 문 열림.
    CX0, CX1, CY, CZ0, CZ1 = -5.6, 5.6, 1.35, -0.55, 2.45
    cube("carfloor", (0, 0, CZ0), (CX1 - CX0, CY * 2, 0.18), M["cardark"])
    for sy in (-1, 1):                                       # 측벽: 문 두 곳을 비운다(x -3.6~-2.2, 1.4~2.8)
        segs = [(-5.6, -3.6), (-2.2, 1.4), (2.8, 5.6)] if sy < 0 else [(-5.6, 5.6)]
        for x0, x1 in segs:
            cube("carw", ((x0 + x1) / 2, sy * CY, (CZ0 + CZ1) / 2 + 0.1), (x1 - x0, 0.1, CZ1 - CZ0), M["carbody"])
            cube("carwin", ((x0 + x1) / 2, sy * CY - sy * 0.04, 1.55), (max(0.2, x1 - x0 - 0.9), 0.04, 0.85), glass)
            cube("carband", ((x0 + x1) / 2, sy * CY - sy * 0.06, 0.62), (x1 - x0, 0.03, 0.3), M["carband"])
    for x0, x1 in ((-3.6, -2.2), (1.4, 2.8)):                # 열린 문틀 + 한쪽으로 밀린 문짝
        for x in (x0, x1):
            cube("doorjamb", (x, -CY, (CZ0 + CZ1) / 2 + 0.1), (0.12, 0.14, CZ1 - CZ0), M["metal_lt"])
        cube("doorleaf", (x0 - 0.5, -CY - 0.06, 1.15), (0.85, 0.05, 2.2), glass)
    for sx in (CX0, CX1):                                    # 앞뒤 마구리
        cube("carend", (sx, 0, (CZ0 + CZ1) / 2 + 0.1), (0.12, CY * 2, CZ1 - CZ0), M["carbody"])
        cube("carendw", (sx - math.copysign(0.05, sx), 0, 1.6), (0.04, 1.6, 0.9), glass)
    for rx0, rx1 in ((CX0, -1.6), (2.6, CX1)):               # 지붕 — 가운데는 내려앉아 열려 있다
        cube("carroof", ((rx0 + rx1) / 2, 0, CZ1 + 0.12), (rx1 - rx0, CY * 2 + 0.1, 0.24), M["carbody"])
        k = rx0
        while k < rx1 - 0.4:
            cube("roofrib", (k + 0.6, 0, CZ1 + 0.26), (0.1, CY * 2 - 0.2, 0.05), M["metal_lt"])
            k += 1.2
    for sy in (-1, 1):                                       # 열린 구간 가장자리 찢긴 테두리
        cube("roofedge", (0.5, sy * CY, CZ1 + 0.12), (4.2, 0.12, 0.24), M["carbody"])
    cube("rooffall", (1.2, -2.2, 0.55), (3.4, 2.0, 0.16), M["carbody"], rot=(math.radians(52), 0, math.radians(7)))
    for k in range(4):
        cyl("roofbar", (-1.0 + k * 1.2, 0.2 + (k % 2) * 0.5, 2.35), 0.035, 1.6 + r.random() * 0.8, M["metal_lt"],
            rot=(math.radians(74 + k * 5), 0, r.uniform(0, 3)), verts=6)
    for k in range(4):                                        # 대차
        cyl("wheel", (-4.2 + (k // 2) * 8.4, (-1 if k % 2 else 1) * 0.72, -0.85), 0.34, 0.14, M["rail"],
            rot=(0, math.radians(90), 0), verts=12)

    # ── 객차 안: 손잡이에 꽃 (스팟의 심장), 좌석, 수면 아래 바닥
    cyl("handbar", (0, -0.55, 2.02), 0.035, CX1 - CX0 - 0.6, M["metal_lt"], rot=(0, math.radians(90), 0), verts=10)
    cyl("handbar2", (0, 0.55, 2.02), 0.035, CX1 - CX0 - 0.6, M["metal_lt"], rot=(0, math.radians(90), 0), verts=10)
    for k in range(14):
        hx = -4.8 + k * 0.74; hy = -0.55 if k % 2 else 0.55
        cyl("strap", (hx, hy, 1.80), 0.012, 0.42, M["rubber"] if "rubber" in M else M["beam"], verts=6)
        cyl("ring", (hx, hy, 1.58), 0.075, 0.03, M["metal_lt"], rot=(math.radians(90), 0, 0), verts=10)
        for p in range(4):                                     # 손잡이에 핀 꽃
            a = math.radians(90 * p + k * 23)
            sphere("petal", (hx + math.cos(a) * 0.075, hy + 0.02, 1.58 + math.sin(a) * 0.075),
                   0.055, M["flower"] if (k + p) % 2 else M["flower2"], 8, 5)
        sphere("fcore", (hx, hy, 1.58), 0.05, M["yellow"], 8, 5)
        if k % 3 == 0:
            iso.vine(hx, hy, 1.52, 0.7, 'x', 90 + k, lod=True)
    for dx in (-2.9, 2.1):                                   # 열린 문틀에 걸린 덩굴·꽃 (밖에서 보이는 신호)
        iso.vine(dx, -CY - 0.1, 2.3, 1.5, 'y', 200 + int(dx * 10), lod=True)
        for q in range(5):
            a = math.radians(72 * q)
            sphere("dpetal", (dx + math.cos(a) * 0.12, -CY - 0.12, 1.95 + math.sin(a) * 0.12), 0.07,
                   M["flower"] if q % 2 else M["flower2"], 8, 5)
    for sy in (-1, 1):
        for x0, x1 in (((-5.2, -3.9), (-1.9, 1.1), (3.1, 5.2)) if sy > 0 else ((-1.9, 1.1),))[0:3]:
            cube("seat", ((x0 + x1) / 2, sy * 1.02, -0.05), (x1 - x0, 0.55, 0.36), M["seat"])
            cube("seatback", ((x0 + x1) / 2, sy * 1.28, 0.42), (x1 - x0, 0.1, 0.64), M["seat"])

    # ── 물: 전 면적 한 장 + 트렌치·객차 안까지 (재질 "Water")
    wp = cube("keep_water_plane", (0, 0, WATER_Z), (SX, SY, 0.02), water)
    wp.name = "keep_water_surface"
    cube("keep_water_deep", (0, 0, -0.55), (SX - 0.2, TRENCH_Y1 - TRENCH_Y0 - 0.2, 0.9), water)

    # ── 사람이 서는 문간 하나 (B10). 6m 격자선 x=-6.0 위, 스팟 바깥 가장자리에서 들어온다.
    #    상면 z=+0.45 (수면 0.14보다 높은 '마른 자리'), 폭 1.5m 평탄 — 정찰병이 여기 서서 들어가지 않는다.
    cube("landing", (THRESH_X, THRESH_Y - 0.15, 0.22), (THRESH_W + 0.3, 1.9, 0.44), M["concrete_dk"])
    cube("landtop", (THRESH_X, THRESH_Y - 0.15, 0.45), (THRESH_W, 1.7, 0.05), M["tile2"])
    for sx in (-1, 1):                                       # 문설주 — '문간'임을 실루엣으로
        cube("threshjamb", (THRESH_X + sx * (THRESH_W / 2 + 0.16), THRESH_Y - 0.9, 1.35), (0.26, 0.3, 2.7), M["concrete"])
    cube("threshlintel", (THRESH_X, THRESH_Y - 0.9, 2.80), (THRESH_W + 0.9, 0.34, 0.32), M["concrete"])
    for k in range(2):                                       # 문간에서 물로 내려가는 계단 두 단
        cube("step", (THRESH_X, THRESH_Y + 0.95 + k * 0.32, 0.32 - k * 0.15), (THRESH_W, 0.34, 0.14), M["concrete"])
    bpy.ops.object.empty_add(type='ARROWS', location=(THRESH_X, THRESH_Y, 0.48), radius=0.5)
    bpy.context.object.name = "marker_threshold"

    # ── 초록: 이끼는 물가와 그늘에, 수생식물은 얕은 쪽에 (B9)
    def scatter(n, fn, xr, yr, tries=6):
        """금붕어 자리(빈 수면 6×4m)를 피해 흩는다 — B9."""
        for i in range(n):
            for _ in range(tries):
                x, y = r.uniform(*xr), r.uniform(*yr)
                if not _in_koi(x, y):
                    fn(i, x, y); break

    def _reed(i, x, y):
        for k in range(r.randint(3, 6)):
            cyl("reed", (x + r.uniform(-0.25, 0.25), y + r.uniform(-0.2, 0.2), 0.45 + r.random() * 0.3),
                0.02, 0.9 + r.random() * 0.6, M["leaf_dk"], rot=(r.uniform(-.15, .15), r.uniform(-.15, .15), 0), verts=6)

    scatter(18, lambda i, x, y: iso.moss(x, y, 0.6 + r.random() * 1.3, 0.4 + r.random() * 0.8, r.random() * 3),
            (-8.5, 8.5), (-5.9, -2.1))
    scatter(10, _reed, (-8.4, 8.4), (-5.9, -2.2))
    scatter(12, lambda i, x, y: cyl("pad", (x, y, WATER_Z + 0.02), 0.18 + r.random() * 0.22, 0.02,
                                    M["leaf"] if i % 2 else M["leaf_dk"], verts=10), (-8.2, 8.2), (-5.6, 4.4))
    scatter(9, lambda i, x, y: sphere("petalfloat", (x, y, WATER_Z + 0.03), 0.07, M["flower2"], 8, 5),
            (-6, 6), (-5.4, 2.2))
    for i in range(6):
        iso.vine(r.uniform(-8.2, 8.2), 4.55, 3.9, 1.2 + r.random() * 1.8, 'y', 120 + i, lod=True)
    scatter(7, lambda i, x, y: prop(r.choice(["k:rock-a", "k:rock-b", "k:patch-grass-large"]), x, y, 0,
                                    h=0.22 + r.random() * 0.35, rot_z=r.random() * 6,
                                    recolor=M["moss"] if i % 2 else None), (-8, 8), (-5.8, -2.4))

    # ── 금붕어 자리 마커 koi_1~5 (개발이 물고기 인스턴스를 붙인다)
    for i, (kx, ky) in enumerate([(-2.3, -4.9), (-0.6, -3.4), (1.2, -5.2), (2.4, -2.6), (0.2, -2.2)], 1):
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(kx, ky, WATER_Z - 0.18), radius=0.25)
        bpy.context.object.name = f"koi_{i}"
    bpy.ops.object.empty_add(type='SINGLE_ARROW', location=(2.0, 1.75, 4.1), radius=0.6)
    bpy.context.object.name = "marker_light_shaft"

    # ── 빛기둥 형상: 구멍 → 열린 지붕 → 손잡이의 꽃. 반투명 원뿔(개발이 셰이더로 교체 가능)
    shaftm = alpha_mat("LightShaft", "#f2e6c4", 0.07, rough=1.0)
    shaftm.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1.0, 0.95, 0.80, 1)
    shaftm.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.9
    for tag, (hx, hy), (tx, ty, tz), rtop, rbot in (
            ("a", (2.0, 3.6), (0.6, 0.1, 0.15), 0.85, 1.45),
            ("b", (-4.3, 3.7), (-5.2, -0.6, 0.15), 0.45, 0.85)):
        top = Vector((hx, hy, 4.35)); bot = Vector((tx, ty, tz))
        d = top - bot
        bpy.ops.mesh.primitive_cone_add(radius1=rbot, radius2=rtop, depth=d.length,
                                        location=(bot + top) / 2, vertices=18)
        c = bpy.context.object; c.name = "keep_lightshaft_" + tag
        c.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        c.data.materials.append(shaftm)
        c.visible_shadow = False

    # ── 빛기둥 조명 (B1 등불 하나 = 이 스팟의 주광)
    bpy.ops.object.light_add(type='SPOT', location=(2.4, 4.4, 7.0))
    sp = bpy.context.object; sp.name = "shaft_light"
    sp.data.energy = 120; sp.data.spot_size = math.radians(40); sp.data.spot_blend = 0.5   # ≈6.5k cd
    sp.data.color = (1.0, 0.95, 0.82); sp.data.shadow_soft_size = 0.6
    aim(sp, (0.6, 0.1, 1.2))                                 # 열린 지붕 → 손잡이의 꽃
    bpy.ops.object.light_add(type='SPOT', location=(-4.3, 3.7, 6.6))
    sp2 = bpy.context.object; sp2.name = "shaft_light_b"
    sp2.data.energy = 45; sp2.data.spot_size = math.radians(30); sp2.data.spot_blend = 0.55  # ≈2.4k cd
    sp2.data.color = (1.0, 0.95, 0.84); sp2.data.shadow_soft_size = 0.5
    aim(sp2, (-5.2, -0.6, 0.2))

    # ── 프리뷰 조명(내보내기 전 제거)
    sky("#6d8f96", strength=0.85)
    bpy.ops.object.light_add(type='AREA', location=(2.2, 4.0, 6.6), rotation=(math.radians(22), 0, 0))
    a = bpy.context.object; a.name = "PRV_shaft"; a.data.energy = 2600; a.data.size = 2.4; a.data.color = (1.0, 0.94, 0.79)
    bpy.ops.object.light_add(type='AREA', location=(-11, -13, 8), rotation=(math.radians(56), 0, math.radians(-40)))
    f = bpy.context.object; f.name = "PRV_fill"; f.data.energy = 240; f.data.size = 22; f.data.color = (0.72, 0.89, 0.96)
    bpy.ops.object.light_add(type='POINT', location=(-1.0, -3.2, 0.5))
    w = bpy.context.object; w.name = "PRV_water"; w.data.energy = 700; w.data.color = (0.35, 0.92, 0.88); w.data.shadow_soft_size = 4
    bpy.ops.object.light_add(type='POINT', location=(0.6, 0.0, 1.9))
    fl = bpy.context.object; fl.name = "PRV_flower"; fl.data.energy = 260; fl.data.color = (1.0, 0.9, 0.8); fl.data.shadow_soft_size = 1.2

    preview(os.path.join(OUT_RAW, "spot_flooded_train.png"), ortho=23.0, target=(0, -1.4, 1.2), res=(1400, 900), exposure=0.12)
    join_scene("spot_flooded_train")
    export(os.path.join(OUT_SCENES, "spot_flooded_train.glb"))


# ══════════════════════════════════════════════════════════════
# ④⑤ 실루엣 패럴랙스 렌더 (단색 이미션, Freestyle 없음, 알파 PNG)
# ══════════════════════════════════════════════════════════════
def _srgb_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def sil_mat(name, hexc):
    """이미션 단색. Blender는 선형색을 받으므로 sRGB → 선형 변환해야 PNG에 그 색이 그대로 나온다."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*[_srgb_lin(c) for c in iso.hexcol(hexc)], 1); e.inputs[1].default_value = 1.0
    nt.links.new(e.outputs[0], nt.nodes["Material Output"].inputs[0])
    return m


def paint_all(m):
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.data.materials.clear(); o.data.materials.append(m)


def render_silhouette(path, w, h, ortho, target, front=True, res_scale=1):
    """정면 직교(기울기 0) 실루엣. 배경 투명, Freestyle 없음, 색은 이미션 그대로."""
    sc = bpy.context.scene
    d = 140.0
    loc = Vector(target) + Vector((0, -d, 0))
    bpy.ops.object.camera_add(location=loc, rotation=(math.radians(90), 0, 0))
    cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    sc.camera = cam
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = True
    sc.render.use_freestyle = False
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    names = [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items]
    sc.view_settings.view_transform = 'Standard' if 'Standard' in names else 'Filmic'
    sc.view_settings.exposure = 0.0
    wd = bpy.data.worlds.new("w"); sc.world = wd; wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs[1].default_value = 0.0
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("SILHOUETTE", path, flush=True)


def load_fbx(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(DINO_FBX, name + ".fbx"))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    return new, meshes


def place_fbx(name, x, target_h, rot_z=0.0, flip=False):
    """FBX를 불러 높이 target_h로 정규화하고 x에 세운다(발바닥 z=0). rot_z로 옆모습을 만든다."""
    new, meshes = load_fbx(name)
    if not meshes:
        return None
    bpy.ops.object.empty_add(location=(0, 0, 0)); root = bpy.context.object; root.name = "dino_" + name
    for o in new:
        if o.parent is None and o is not root:
            o.parent = root
    bpy.context.view_layer.update()
    lo, hi = iso._bbox(meshes)
    s = target_h / max(hi.z - lo.z, 1e-4)
    root.scale = (s, s, s)
    root.rotation_euler = (0, 0, rot_z + (math.pi if flip else 0))
    bpy.context.view_layer.update()
    lo, hi = iso._bbox(meshes)
    root.location = (x - (lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)
    return root


def scene_dino_parallax():
    # far: 트리케라톱스·스테고사우루스 실루엣 열 (1600×300)
    fresh()
    sil = sil_mat("sil_far", "#66786a")             # 먼 층은 대기 원근으로 옅게
    L, Rt = math.radians(90), math.radians(-90)     # FBX는 몸통이 Y축 → 옆모습은 Z 90° 회전
    row = [("Triceratops", -9.0, 2.9, L), ("Stegosaurus", -5.0, 3.5, L), ("Triceratops", -1.0, 2.5, Rt),
           ("Stegosaurus", 3.1, 3.2, L), ("Triceratops", 7.4, 3.3, L), ("Stegosaurus", 9.9, 2.5, Rt)]
    for nm, x, h, rz in row:
        place_fbx(nm, x, h, rot_z=rz)
    paint_all(sil)
    render_silhouette(os.path.join(OUT_PARA, "dino_far.png"), 1600, 300, ortho=25.6, target=(0.6, 0, 2.1))

    # near: 랩터 2 (1200×300)
    fresh()
    sil = sil_mat("sil_near", "#232b26")            # 가까운 층은 짙게
    place_fbx("Velociraptor", -3.8, 2.5, rot_z=math.radians(90))
    place_fbx("Velociraptor", 3.7, 2.2, rot_z=math.radians(-90))
    paint_all(sil)
    render_silhouette(os.path.join(OUT_PARA, "dino_near.png"), 1200, 300, ortho=15.0, target=(0, 0, 1.7))


# ── ⑤ 스카이라인: 부족 방향 랜드마크 6 + 초록 덮인 아파트 ──────
def scene_skyline():
    """부족 방향 랜드마크 6 + 초록 덮인 아파트. 프레임 150m×25m(2400×400)에 맞춘 비례."""
    fresh()
    B = sil_mat("sil_bldg", "#424f52")     # 구조물 — 무채에 가까운 청회색
    G = sil_mat("sil_green", "#3d5b3e")    # 자연 — 덮은 초록(B2)
    r = random.Random(6060)
    cube, cyl, sphere = iso.cube, iso.cyl, iso.sphere

    def blk(x, w, h, d=6.0, m=None, z0=0.0):
        cube("b", (x, 0, z0 + h / 2), (w, d, h), m or B)

    def crown(x, z, rr, m=None):
        sphere("c", (x, r.uniform(-1.6, -0.4), z), rr, m or G, 12, 7)

    def treeline(x0, x1, zbase, n, rr=(0.8, 1.5)):
        for _ in range(n):
            crown(r.uniform(x0, x1), zbase + r.uniform(-0.4, 1.2), r.uniform(*rr))

    # ── 1. 불꽃 부족: 굴뚝 두 개 + 냉각탑 (x ≈ -60)
    blk(-64, 9, 5); blk(-58.5, 6, 7); blk(-52.5, 5, 4)
    for cx, ch, cr in ((-65.5, 21.0, 0.85), (-62.6, 17.5, 0.68)):
        cyl("chim", (cx, 0, ch / 2), cr, ch, B, verts=14)
        cyl("chimcap", (cx, 0, ch), cr * 1.35, 0.7, B, verts=14)
    for k in range(6):                                    # 끊긴 연기
        sphere("smoke", (-65.5 + k * 0.55, -0.8, 21.8 + k * 0.85), 0.55 + k * 0.16, B, 10, 6)
    for k in range(6):                                    # 허리 잘록한 냉각탑
        z = 0.4 + k * 1.75
        rr = 3.4 - (2.6 - abs(k - 2.6)) * 0.45
        cyl("cool", (-55.5, 0, z + 0.9), rr, 1.85, B, verts=18)
    treeline(-67, -50, 4.5, 9)

    # ── 2. 하얀 부족: 매끈한 병원 슬래브 + 헬리패드 + 마스트 (x ≈ -42)
    blk(-43, 9.5, 17.5); blk(-37.5, 5.0, 12.0); blk(-47.8, 4.2, 8.5)
    cyl("heli", (-43, -0.4, 17.9), 2.8, 0.55, B, verts=20)
    cyl("mast", (-46.4, 0, 21.5), 0.16, 8.0, B, verts=8)
    for k in range(5):
        cube("band", (-43, -3.05, 2.6 + k * 3.1), (8.6, 0.25, 0.55), B)
    treeline(-49, -36, 3.2, 6, (0.7, 1.2))

    # ── 3. 서고 부족: 내려앉은 학교 지붕 + 시계탑 (x ≈ -24)
    blk(-26.5, 13.0, 7.8); blk(-19.0, 4.6, 9.4)
    cube("roofL", (-30.6, 0, 9.4), (6.6, 6.2, 0.6), B, rot=(0, math.radians(16), 0))
    cube("roofR", (-24.2, 0, 7.6), (7.4, 6.2, 0.6), B, rot=(0, math.radians(-19), 0))
    cube("sag", (-27.0, 0, 7.0), (3.2, 6.0, 0.55), B, rot=(0, math.radians(4), 0))
    cube("clock", (-19.0, 0, 11.6), (3.4, 4.8, 4.4), B)
    cyl("clockface", (-19.0, -2.5, 12.4), 1.0, 0.25, B, verts=16)
    cube("clockroof", (-19.0, 0, 14.1), (4.6, 5.6, 0.6), B)
    cube("clockspire", (-19.0, 0, 15.4), (0.5, 0.5, 2.0), B)
    treeline(-32, -16, 7.0, 10, (0.9, 1.6))

    # ── 4. 온실 부족: 유리 온실 배럴 볼트를 뚫고 나온 나무 (x ≈ -5)
    blk(-5, 18.0, 5.0)
    for k in range(22):                                    # 아치 외곽선(배럴 볼트) — 접선 방향 판으로 이어 붙인다
        a = math.radians(180 * (k + 0.5) / 22)
        cube("vault", (-5 + math.cos(a) * 8.8, 0, 5.0 + math.sin(a) * 8.4), (1.45, 6.6, 0.55), B,
             rot=(0, math.pi / 2 - a, 0))
    for vx in (-12.6, -8.8, -1.2, 2.6):                    # 유리 격간 기둥
        cube("vrib", (vx, 0, 6.4), (0.4, 6.4, 3.0), B)
    cyl("gtrunk", (-3.0, 0, 9.0), 0.5, 18.0, G, verts=10)
    for k in range(8):                                     # 지붕을 뚫고 나온 수관
        crown(-8.4 + k * 2.2, 13.6 + r.uniform(-1.0, 2.6), 1.6 + r.random() * 1.2)
    treeline(-13, 3, 5.4, 7)

    # ── 5. 탑 부족: 가장 높은 탑 + 안테나 + 거울 신호대 (x ≈ 18)
    blk(18, 7.0, 22.0); blk(23.5, 4.6, 14.0); blk(13.2, 4.0, 10.0)
    cyl("spire", (18, 0, 24.6), 0.20, 5.6, B, verts=10)
    for k in range(3):
        cube("ant", (18, 0, 23.3 + k * 1.1), (1.7 - k * 0.42, 0.22, 0.16), B)
    for k in range(9):
        cube("fl", (18, -3.05, 2.0 + k * 2.3), (6.4, 0.25, 0.38), B)
    cube("mirror", (21.6, -2.6, 13.6), (1.2, 0.3, 1.2), B, rot=(0, 0, math.radians(20)))
    cyl("mirrorpost", (21.6, -2.6, 12.4), 0.11, 1.6, B, verts=8)
    treeline(11, 27, 3.0, 6, (0.7, 1.2))

    # ── 6. 길손 부족: 둑에 뚫린 터널 입구 아치 + 전신주 (x ≈ 44)
    for x0, x1, h in ((33.0, 40.2, 7.2), (47.8, 56.0, 7.2)):
        blk((x0 + x1) / 2, x1 - x0, h, d=7.0)
    cube("bankTop", (44, 0, 7.6), (23, 7.0, 1.2), B)
    for k in range(11):                                    # 아치 테두리
        a = math.radians(180 * k / 10)
        cube("arch", (44 + math.cos(a) * 3.9, 0, 1.0 + math.sin(a) * 3.7), (1.35, 7.2, 1.35), B,
             rot=(0, math.pi / 2 - a, 0))
    cube("spandrel", (44, 0, 5.95), (8.4, 7.0, 3.5), B)   # 아치 위 둑(구멍은 비운다 = 터널 입구)
    cube("track", (44, -3.6, 0.12), (11.0, 0.6, 0.24), B)
    for k in range(5):                                     # 둑 위 전신주
        cyl("pole", (35 + k * 4.6, -1.0, 10.4), 0.16, 4.4, B, verts=8)
        cube("cross", (35 + k * 4.6, -1.0, 12.1), (1.7, 0.16, 0.16), B)
    treeline(31, 58, 7.9, 12, (0.8, 1.5))

    # ── 7. 초록 덮인 아파트 — 랜드마크 아래를 지나가는 낮은 띠 (B2: 초록은 생명)
    # 랜드마크가 읽히도록 그 앞은 비운다(학교 지붕·온실 아치·터널 입구는 낮은 구조물이다)
    SKIP = [(-33.5, -15.0), (-15.0, 4.5), (31.0, 58.0)]
    ax = -76
    while ax < 76:
        w = r.uniform(3.4, 6.0); h = r.uniform(2.6, 5.4)
        cx = ax + w / 2
        if not any(a < cx < b for a, b in SKIP):
            blk(cx, w, h, d=3.6)
            for k in range(int(w // 1.7) + 1):             # 옥상을 덮은 나무
                crown(ax + 0.8 + k * 1.7 + r.uniform(-.3, .3), h + r.uniform(-0.4, 1.1), 0.8 + r.random() * 0.7)
            for k in range(r.randint(0, 2)):               # 벽을 타는 덩굴 뭉치
                crown(ax + r.uniform(0, w), r.uniform(1.0, max(1.2, h * 0.7)), 0.6 + r.random() * 0.5)
        ax += w + r.uniform(1.0, 3.0)
    for k in range(90):                                    # 지평선 수풀(바닥 선을 덮되 터널 입구는 비운다)
        hx = r.uniform(-77, 77)
        if 40.5 < hx < 47.5:
            continue
        crown(hx, r.uniform(0.2, 1.4), 0.6 + r.random() * 0.7)

    render_silhouette(os.path.join(OUT_PARA, "skyline.png"), 2400, 400, ortho=150.0, target=(-3.0, 0, 12.0))


if __name__ == "__main__":
    jobs = {"facade": scene_mall_facade, "spot": scene_spot_flooded_train,
            "dino": scene_dino_parallax, "skyline": scene_skyline}
    for k in (jobs if MODE == "all" else [MODE]):
        jobs[k]()
    print("ALL DONE", flush=True)
