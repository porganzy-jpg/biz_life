"""S15-E — 원정 3D 화면(물속판)용 아이소 에셋 키트.

  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --python tools/blender_iso_sea.py -- [id ...]
  python tools/blender_iso_sea.py sheet        → docs/reports/s15e_iso_sea_sheet.png + manifest 마무리

- 출력: static/art/iso_sea/<id>.glb (+ manifest.json), 썸네일은 art_raw/iso_sea/<id>.png
- 단위 m, Z-up(Blender) → GLB 는 Y-up. 원점 = 바닥 면 가운데(발이 닿는 높이 0). 땅 타일은 6 m 격자(아이소 육상판과 같은 격자).
- 팔레트 = M5: 청록은 물에만(배경), 바닥은 무채색 모래·진흙·바위, 따뜻한 등불 강조, 초록은 해초.
- 저폴리(폰): 타일 ≤ 200 tri, 소품 ≤ 600 tri 목표. 생성 AI 없음. 3막 가드: 도시 실루엣 없음.
- blender_iso.py 는 건드리지 않는다(독립 스크립트).
"""
import os, sys, math, random, json

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DST = os.path.join(ROOT, "static", "art", "iso_sea")
RAW = os.path.join(ROOT, "art_raw", "iso_sea")
os.makedirs(DST, exist_ok=True); os.makedirs(RAW, exist_ok=True)
GRID = 6.0
CATS = ["food", "drink", "medical", "electronics", "stationery", "book", "apparel", "tobacco"]   # engine/relic_generator.Category

# ══════════════════════════════════════════════════════════════════════════════
def _blender(only):
    import bpy, bmesh
    from mathutils import Vector, Matrix

    def s2l(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lin(h):
        h = h.lstrip("#"); return tuple(s2l(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))

    MATS = {}

    def mat(hexc, emit=0.0, alpha=1.0, name=None):
        k = (hexc, emit, alpha)
        if k in MATS and MATS[k].name in bpy.data.materials:
            return MATS[k]
        m = bpy.data.materials.new(name or f"m_{hexc.strip('#')}_{int(emit*10)}_{int(alpha*100)}")
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (*lin(hexc), 1)
        b.inputs["Roughness"].default_value = 0.95
        try:
            b.inputs["Specular IOR Level"].default_value = 0.1
        except Exception:
            pass
        if emit:
            b.inputs["Emission Color"].default_value = (*lin(hexc), 1)
            b.inputs["Emission Strength"].default_value = emit
        if alpha < 1:
            b.inputs["Alpha"].default_value = alpha
            try:
                m.surface_render_method = 'BLENDED'
            except Exception:
                m.blend_method = 'BLEND'
        m.use_backface_culling = False
        MATS[k] = m
        return m

    PARTS = []

    def obj_from_bm(name, bm, m):
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
        me.materials.append(m); PARTS.append(o)
        for p in me.polygons:
            p.use_smooth = False
        return o

    def box(name, size, loc, m, rot=(0, 0, 0), taper=None):
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
            if taper and v.co.z > 0:
                v.co.x *= taper; v.co.y *= taper
        o = obj_from_bm(name, bm, m)
        o.location = loc; o.rotation_euler = rot
        return o

    def cyl(name, r, h, loc, m, seg=8, rot=(0, 0, 0), r2=None):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
        o = obj_from_bm(name, bm, m); o.location = loc; o.rotation_euler = rot
        return o

    def rockmesh(name, r, loc, m, seed, squash=0.7, sub=1):
        rr = random.Random(seed)
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
        for v in bm.verts:
            k = rr.uniform(0.75, 1.15)
            v.co *= k; v.co.z *= squash
            if v.co.z < -r * 0.15:
                v.co.z = -r * 0.15
        o = obj_from_bm(name, bm, m); o.location = (loc[0], loc[1], loc[2] + r * 0.15 * squash)
        return o

    def poly_flat(name, pts, m, z=0.0, thick=0.0, rot=(0, 0, 0), loc=(0, 0, 0)):
        """xz 평면(세로판) 다각형 — 두께가 있으면 y 로 밀어낸다"""
        bm = bmesh.new()
        vs = [bm.verts.new((x, 0, y)) for x, y in pts]
        f = bm.faces.new(vs)
        if thick:
            r = bmesh.ops.extrude_face_region(bm, geom=[f])
            for v in [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]:
                v.co.y += thick
        o = obj_from_bm(name, bm, m); o.location = loc; o.rotation_euler = rot
        return o

    def ribbon(name, pts, w, m, w1=None, loc=(0, 0, 0), rot=(0, 0, 0)):
        """xz 평면 띠(해초 잎) — 두께 없는 양면"""
        w1 = w if w1 is None else w1
        bm = bmesh.new(); L, R = [], []; n = len(pts)
        for i, p in enumerate(pts):
            a = pts[max(0, i - 1)]; b = pts[min(n - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]; d = math.hypot(dx, dz) or 1
            nx, nz = -dz / d, dx / d; ww = (w + (w1 - w) * i / max(1, n - 1)) / 2
            L.append(bm.verts.new((p[0] + nx * ww, 0, p[1] + nz * ww))); R.append(bm.verts.new((p[0] - nx * ww, 0, p[1] - nz * ww)))
        for i in range(n - 1):
            bm.faces.new((L[i], L[i + 1], R[i + 1], R[i]))
        o = obj_from_bm(name, bm, m); o.location = loc; o.rotation_euler = rot
        return o

    def ground(name, m, seed, amp=0.18, n=8, size=GRID, drop=None, wall=None, extra=None):
        """6 m 땅 타일. 위 면 높이 0 근처에서 출렁인다. drop: 'E' 면 +x 쪽이 심연으로 꺼진다. 'NE' 는 모서리"""
        rr = random.Random(seed)
        bm = bmesh.new()
        h = size / 2; verts = {}
        for i in range(n + 1):
            for j in range(n + 1):
                x = -h + size * i / n; y = -h + size * j / n
                edge = i in (0, n) or j in (0, n)
                z = 0 if edge else rr.uniform(-amp, amp)
                if extra:
                    z += extra(x, y)
                if drop:
                    t = 0.0
                    if "E" in drop: t = max(t, (x - 0.6) / (h - 0.6))
                    if "N" in drop: t = max(t, (y - 0.6) / (h - 0.6))
                    if t > 0:
                        z -= (t ** 1.6) * 3.2 + (0 if edge else rr.uniform(0, 0.25))
                verts[(i, j)] = bm.verts.new((x, y, z))
        for i in range(n):
            for j in range(n):
                bm.faces.new((verts[(i, j)], verts[(i + 1, j)], verts[(i + 1, j + 1)], verts[(i, j + 1)]))
        # 두께(옆면) — 아이소에서 타일 단면이 보인다
        ring = [verts[(i, 0)] for i in range(n + 1)] + [verts[(n, j)] for j in range(1, n + 1)] + \
               [verts[(i, n)] for i in range(n - 1, -1, -1)] + [verts[(0, j)] for j in range(n - 1, 0, -1)]
        bot = [bm.verts.new((v.co.x, v.co.y, min(v.co.z, 0) - 0.6)) for v in ring]
        for k in range(len(ring)):
            a, b = ring[k], ring[(k + 1) % len(ring)]; c, d = bot[(k + 1) % len(ring)], bot[k]
            try:
                bm.faces.new((a, b, c, d))
            except Exception:
                pass
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        return obj_from_bm(name, bm, m)

    def kelp(name, x, y, hgt, m, seed, n=6, w=0.34):
        rr = random.Random(seed); ph = rr.uniform(0, 6); lean = rr.uniform(-0.3, 0.3)
        pts = [(math.sin(ph + t * 3.2) * 0.25 * t + lean * t, t * hgt) for t in [k / n for k in range(n + 1)]]
        return ribbon(name, pts, w, m, w1=w * 0.3, loc=(x, y, 0), rot=(0, 0, rr.uniform(0, 3.14)))

    # ── 팔레트(M5) ──
    P = dict(sand="#7C7A62", sand_b="#8A8468", silt="#4E5654", silt_d="#3C4442", rock="#4A4E48", rock_l="#646A60",
             rock_d="#2E3230", kelp="#46582A", kelp_l="#5E7034", fan="#B0784A", fan_b="#C9B896",
             wood="#6A4A2A", wood_l="#86603A", iron="#4E443A", rust="#7A4A30", cream="#C9B896",
             conc="#3E4646", conc_l="#56605E", lamp="#FFC870", brass="#8A6A3A", husk="#7A3A2A", glass="#0E2A30",
             dark="#06090A", eye="#D8ECDC", suit="#5E5E34")

    def m_(k, **kw):
        return mat(P[k], **kw)

    A = {}   # id -> (builder, meta)

    def asset(id_, footprint, tags, note=""):
        def deco(fn):
            A[id_] = (fn, dict(id=id_, footprint_m=footprint, tags=tags, note=note))
            return fn
        return deco

    # ── 땅 타일 ──
    @asset("ground_sand_a", [6, 6], ["ground", "sand"], "모래 바닥(기본)")
    def _():
        ground("g", m_("sand"), 1, amp=0.12)
        for i in range(5):
            rr = random.Random(10 + i); rockmesh(f"peb{i}", rr.uniform(0.08, 0.16), (rr.uniform(-2.5, 2.5), rr.uniform(-2.5, 2.5), 0), m_("rock_l"), 20 + i)

    @asset("ground_sand_b", [6, 6], ["ground", "sand"], "물결 무늬 모래(물살 자국)")
    def _():
        ground("g", m_("sand_b"), 2, amp=0.06, n=10, extra=lambda x, y: 0.09 * math.sin((x + 0.4 * y) * 2.2))

    @asset("ground_silt", [6, 6], ["ground", "silt"], "진흙(더 깊은 쪽). 발자국이 안 남는 고운 바닥")
    def _():
        ground("g", m_("silt"), 3, amp=0.08)
        for i in range(3):
            rr = random.Random(30 + i)
            cyl(f"vent{i}", 0.12, 0.05, (rr.uniform(-2, 2), rr.uniform(-2, 2), 0.02), m_("silt_d"), seg=6)

    @asset("ground_rock", [6, 6], ["ground", "rock"], "바위 바닥(울퉁불퉁)")
    def _():
        ground("g", m_("rock"), 4, amp=0.3)
        for i in range(4):
            rr = random.Random(40 + i); rockmesh(f"r{i}", rr.uniform(0.3, 0.6), (rr.uniform(-2.2, 2.2), rr.uniform(-2.2, 2.2), 0), m_("rock_l"), 41 + i, squash=0.5)

    @asset("ground_edge_drop", [6, 6], ["ground", "edge", "drop"], "+x 쪽이 심연으로 꺼지는 가장자리. 회전해서 네 방향으로 쓴다")
    def _():
        ground("g", m_("silt"), 5, amp=0.1, drop="E")
        for i in range(3):
            rockmesh(f"lip{i}", 0.35, (1.2, -2 + i * 2, -0.1), m_("rock"), 50 + i, squash=0.6)

    @asset("ground_edge_corner", [6, 6], ["ground", "edge", "corner"], "+x·+y 두 쪽이 꺼지는 바깥 모서리")
    def _():
        ground("g", m_("silt"), 6, amp=0.1, drop="EN")

    @asset("ground_edge_wall", [6, 6], ["ground", "edge", "wall"], "-y 쪽에 바위 벽이 솟는 가장자리(절벽 밑). 회전해서 쓴다")
    def _():
        ground("g", m_("sand"), 7, amp=0.1)
        rr = random.Random(70)
        for i in range(5):
            x = -2.6 + i * 1.3
            box(f"w{i}", (1.4, 1.0, rr.uniform(2.4, 3.6)), (x, -2.6, 1.2), m_("rock"), rot=(rr.uniform(-.08, .08), 0, rr.uniform(-.2, .2)), taper=0.8)
        for i in range(4):
            box(f"strata{i}", (1.45, 1.05, 0.12), (-2.0 + i * 1.3, -2.55, 1.6 + 0.3 * (i % 2)), m_("rock_l"))
        kelp("k0", 1.6, -1.8, 1.4, m_("kelp"), 71)

    # ── 바위 ──
    @asset("rock_small", [1, 1], ["rock", "prop"])
    def _():
        rockmesh("r", 0.45, (0, 0, 0), m_("rock"), 101, squash=0.6)
        rockmesh("r2", 0.22, (0.4, 0.25, 0), m_("rock_l"), 102, squash=0.6)

    @asset("rock_boulder", [2, 2], ["rock", "prop", "blocker"])
    def _():
        rockmesh("r", 1.0, (0, 0, 0), m_("rock"), 111, squash=0.75)
        rockmesh("cap", 0.55, (0.15, -0.1, 0.75), m_("rock_l"), 112, squash=0.6)

    @asset("rock_stack", [2, 2], ["rock", "prop", "tall", "landmark"], "길잡이가 되는 높은 바위 기둥")
    def _():
        z = 0
        for i, r in enumerate((0.8, 0.62, 0.5, 0.36)):
            rockmesh(f"s{i}", r, (0.08 * i, -0.05 * i, z), m_("rock" if i % 2 else "rock_l"), 120 + i, squash=0.8)
            z += r * 1.05
        kelp("k", 0.6, 0.3, 1.2, m_("kelp"), 125)

    # ── 해초 ──
    @asset("kelp_clump_a", [1, 1], ["kelp", "plant", "green"])
    def _():
        rockmesh("base", 0.25, (0, 0, 0), m_("rock"), 201, squash=0.5)
        for i in range(7):
            rr = random.Random(210 + i)
            kelp(f"k{i}", rr.uniform(-0.3, 0.3), rr.uniform(-0.3, 0.3), rr.uniform(1.6, 2.8), m_("kelp" if i % 2 else "kelp_l"), 210 + i)

    @asset("kelp_clump_b", [2, 2], ["kelp", "plant", "green", "tall"], "키 큰 해초 숲 한 무리")
    def _():
        for i in range(9):
            rr = random.Random(220 + i)
            kelp(f"k{i}", rr.uniform(-0.8, 0.8), rr.uniform(-0.8, 0.8), rr.uniform(2.4, 4.2), m_("kelp" if i % 3 else "kelp_l"), 220 + i, w=0.3)

    # ── 부채 산호 비슷한 것(실제 종 이름 없음) ──
    def fan(name, col, seed, h=1.4, wd=1.6):
        rr = random.Random(seed); pts = [(0, 0)]
        for k in range(9):
            a = math.pi * (0.15 + 0.7 * k / 8); r = h * rr.uniform(0.85, 1.05)
            pts.append((math.cos(a) * wd / 2 * r / h * 1.0, math.sin(a) * r))
        rz = math.pi / 4 + rr.uniform(-0.35, 0.35)                     # 넓은 면이 아이소 카메라를 본다
        poly_flat(name, pts, mat(col), thick=0.04, rot=(0, 0, rz))
        for k in range(5):                                              # 부채 살(어두운 결)
            a = math.pi * (0.2 + 0.6 * k / 4)
            ribbon(name + f"_v{k}", [(0, 0.02), (math.cos(a) * wd * 0.42, math.sin(a) * h * 0.85)], 0.045, m_("rock_d"),
                   w1=0.015, loc=(-0.025 * math.sin(rz), 0.025 * math.cos(rz) * -1, 0), rot=(0, 0, rz))
        cyl(name + "_st", 0.06, 0.3, (0, 0, 0.15), m_("rock_d"), seg=6)

    @asset("fan_a", [1, 1], ["fan", "plant", "warm"], "부채꼴 판 — 흐린 주황")
    def _():
        rockmesh("base", 0.3, (0, 0, 0), m_("rock"), 301, squash=0.5)
        fan("f", P["fan"], 302)

    @asset("fan_b", [1, 1], ["fan", "plant", "pale"], "부채 셋 무리 — 뼈색")
    def _():
        rockmesh("base", 0.35, (0, 0, 0), m_("rock"), 311, squash=0.5)
        for i in range(3):
            fan(f"f{i}", P["fan_b"] if i != 1 else P["fan"], 312 + i, h=0.8 + 0.25 * i, wd=0.9)
        for o in PARTS[-6:]:
            if o.name.startswith("f") and not o.name.endswith("_st"):
                o.location.x += random.Random(o.name).uniform(-0.3, 0.3)

    # ── 바코드 잔해(상표 없음) ──
    @asset("relic_crate", [1, 1], ["relic", "pickup", "debris"], "나무 궤짝 — 반쯤 묻힘")
    def _():
        box("c", (0.9, 0.7, 0.6), (0, 0, 0.22), m_("wood"), rot=(0.12, 0.05, 0.4))
        for k in (-0.3, 0.3):
            box(f"band{k}", (0.06, 0.72, 0.62), (k, 0, 0.22), m_("iron"), rot=(0.12, 0.05, 0.4))
        ground_sil = cyl("sand", 0.7, 0.12, (0, 0, 0.0), m_("sand"), seg=8, r2=0.4)

    @asset("relic_cans", [1, 1], ["relic", "pickup", "debris"], "깡통 무더기 — 상표 없는 바랜 띠")
    def _():
        rr = random.Random(401)
        for i in range(6):
            lying = i % 2
            x, y = rr.uniform(-0.35, 0.35), rr.uniform(-0.35, 0.35)
            col = "cream" if i % 3 else "rust"
            if lying:
                cyl(f"can{i}", 0.08, 0.2, (x, y, 0.08), m_(col), seg=8, rot=(math.pi / 2, 0, rr.uniform(0, 3)))
            else:
                cyl(f"can{i}", 0.08, 0.2, (x, y, 0.1), m_(col), seg=8)
                cyl(f"band{i}", 0.082, 0.06, (x, y, 0.1), m_("husk"), seg=8)

    @asset("relic_cart", [2, 1], ["relic", "pickup", "debris", "landmark"], "넘어진 손수레(장바구니 수레) — 철망 바구니")
    def _():
        rot = (0, 0.35, 0.3)
        ir = m_("iron")
        # 바구니 테두리 + 철망 기둥
        for (sx, sy, sz, x, y, z) in [(1.0, 0.04, 0.04, 0, -0.3, 0.5), (1.0, 0.04, 0.04, 0, 0.3, 0.5), (0.04, 0.64, 0.04, -0.5, 0, 0.5),
                                      (0.04, 0.64, 0.04, 0.5, 0, 0.5), (0.9, 0.6, 0.03, 0, 0, 0.12)]:
            box(f"b{x}{y}{z}{sx}", (sx, sy, sz), (x, y, z), ir)
        for k in range(6):
            box(f"wire{k}", (0.02, 0.62, 0.4), (-0.45 + k * 0.18, 0, 0.3), ir)
        box("handle", (0.04, 0.7, 0.04), (0.62, 0, 0.72), ir)
        for k in (-0.3, 0.3):
            box(f"hpost{k}", (0.15, 0.03, 0.03), (0.56, k, 0.62), ir)
            for x in (-0.45, 0.45):
                cyl(f"wheel{k}{x}", 0.07, 0.04, (x, k, 0.03), m_("rock_d"), seg=8, rot=(math.pi / 2, 0, 0))
        # 통째로 기울여 넘어뜨린다
        for o in PARTS:
            o.location = Matrix.Rotation(0.5, 4, 'Y') @ o.location
            o.rotation_euler.y += 0.5
        kelp("k", 0.2, 0.1, 0.9, m_("kelp"), 402, w=0.14)

    @asset("relic_vending_husk", [2, 1], ["relic", "pickup", "debris", "landmark"], "자판기 껍데기 — 상표 없음, 단추 줄과 꺼진 유리")
    def _():
        rot = (0, -0.22, 0.2)
        box("body", (1.0, 0.8, 1.9), (0, 0, 0.95), m_("husk"), rot=rot)
        box("glass", (0.7, 0.04, 1.1), (-0.06, -0.41, 1.25), m_("glass"), rot=rot)
        for r in range(3):
            for c in range(4):
                box(f"btn{r}{c}", (0.08, 0.03, 0.05), (0.36, -0.42, 1.5 - r * 0.18 + 0 * c), m_("cream"), rot=rot) if c == 0 else None
        box("slot", (0.5, 0.05, 0.12), (-0.05, -0.42, 0.3), m_("dark"), rot=rot)
        for i in range(3):
            kelp(f"k{i}", 0.5 - i * 0.4, 0.45, 1.2 + i * 0.4, m_("kelp"), 410 + i, w=0.16)
        rockmesh("sand", 0.5, (0, 0, -0.2), m_("sand"), 415, squash=0.4)

    # ── 봉인 상자 + 갈래 무늬 여덟 + 빈 원 ──
    def glyph(cat, top_z, m):
        """상자 윗면·앞면의 갈래 무늬(볼록한 판). 실제 상표·기호 아님 — 간단한 그림 글자"""
        def flat(name, pts, z=top_z, s=1.0):
            bm = bmesh.new(); vs = [bm.verts.new((x * s, y * s, z)) for x, y in pts]; bm.faces.new(vs)
            r = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
            for v in [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]:
                v.co.z += 0.02
            obj_from_bm(name, bm, m)
        def circle(cx, cy, r, n=10):
            return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        def ring(name, r0, r1, n=14):
            bm = bmesh.new(); o = [bm.verts.new((r1 * math.cos(2 * math.pi * k / n), r1 * math.sin(2 * math.pi * k / n), top_z)) for k in range(n)]
            i_ = [bm.verts.new((r0 * math.cos(2 * math.pi * k / n), r0 * math.sin(2 * math.pi * k / n), top_z)) for k in range(n)]
            for k in range(n):
                bm.faces.new((o[k], o[(k + 1) % n], i_[(k + 1) % n], i_[k]))
            r = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
            for v in [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]:
                v.co.z += 0.02
            obj_from_bm(name, bm, m)
        def rot(pts, ang, ox=0.0, oy=0.0):
            c, sn = math.cos(ang), math.sin(ang)
            return [(ox + x * c - y * sn, oy + x * sn + y * c) for x, y in pts]
        def band(line, w, w1=None):
            """폴리라인 → 두께 있는 띠 다각형(왼쪽 + 뒤집은 오른쪽)"""
            w1 = w if w1 is None else w1; Lp, Rp = [], []; n = len(line)
            for i, (x, y) in enumerate(line):
                ax, ay = line[max(0, i - 1)]; bx, by = line[min(n - 1, i + 1)]
                dx, dy = bx - ax, by - ay; d = math.hypot(dx, dy) or 1; nx, ny = -dy / d, dx / d
                ww = (w + (w1 - w) * i / max(1, n - 1)) / 2
                Lp.append((x + nx * ww, y + ny * ww)); Rp.append((x - nx * ww, y - ny * ww))
            return Lp + Rp[::-1]
        def drop(cx, cy, r):
            """물방울: 아래는 둥글고 위는 뾰족"""
            pts = [(cx + r * math.cos(a_), cy + r * math.sin(a_)) for a_ in [math.pi * (1.15 + 0.7 * k / 8) for k in range(9)]]
            return pts + [(cx + r * 0.5, cy + r * 0.9), (cx, cy + r * 2.0), (cx - r * 0.5, cy + r * 0.9)]
        if cat == "food":          # 이삭 세 줄(부채꼴로 벌어진 줄기 + 낟알 잎)
            for k, ang in enumerate((0.38, 0.0, -0.38)):
                flat(f"stem{k}", rot([(-0.012, -0.17), (0.012, -0.17), (0.012, -0.01), (-0.012, -0.01)], ang, 0, -0.0))
                for j in range(3):          # 낟알 셋(위로 갈수록 작다)
                    yy = 0.0 + j * 0.058; r_ = 0.03 - j * 0.005
                    flat(f"grain{k}{j}", rot([(0, yy - r_ * 1.6), (r_, yy), (0, yy + r_ * 1.6), (-r_, yy)], ang, 0, -0.0))
        elif cat == "drink":       # 물방울 셋
            for k, (cx, cy, r_) in enumerate([(-0.07, -0.08, 0.045), (0.07, -0.06, 0.04), (0.0, 0.03, 0.05)]):
                flat(f"drop{k}", drop(cx, cy, r_))
        elif cat == "medical":     # 엇갈린 띠 둘(X자, 십자가 아님)
            bar = [(-0.03, -0.16), (0.03, -0.16), (0.03, 0.16), (-0.03, 0.16)]
            flat("g1", rot(bar, 0.6)); flat("g2", rot(bar, -0.6), z=top_z + 0.012)
        elif cat == "electronics": # 번개
            flat("g", [(0.02, 0.15), (-0.09, -0.01), (-0.01, -0.01), (-0.04, -0.15), (0.09, 0.03), (0.01, 0.03)])
        elif cat == "stationery":  # 깃 하나(비스듬한 깃펜)
            vane = [(0.0, -0.06), (0.03, -0.02), (0.042, 0.06), (0.018, 0.075), (0.04, 0.1), (0.03, 0.17), (0.0, 0.23),
                    (-0.018, 0.15), (-0.03, 0.08), (-0.012, 0.06), (-0.028, 0.02)]                  # 길고 좁은 깃 + 갈라진 홈 둘
            flat("vane", rot(vane, -0.6))
            flat("shaft", rot(band([(0, -0.2), (0, 0.0), (0.002, 0.2)], 0.014, 0.006), -0.6), z=top_z + 0.012)
        elif cat == "book":        # 겹친 장 — 얇은 판 넷이 조금씩 어긋나 포개짐
            for k in range(4):
                ox, oy = -0.03 + k * 0.02, -0.09 + k * 0.05
                flat(f"sheet{k}", [(ox - 0.12, oy - 0.012), (ox + 0.12, oy - 0.012), (ox + 0.12, oy + 0.012), (ox - 0.12, oy + 0.012)])
        elif cat == "apparel":     # 실타래 — 둥근 테 + 안쪽에 같은 방향으로 감긴 곡선 실 셋 + 풀린 꼬리
            ring("ball", 0.115, 0.14)
            for k, R_ in enumerate((0.16, 0.21, 0.26)):
                arc = [(-0.19 + R_ * math.cos(t), 0.19 + R_ * math.sin(t)) for t in [-math.pi / 2 + (math.pi / 2) * i / 24 for i in range(25)]]
                arc = [q for q in arc if math.hypot(*q) < 0.1]
                if len(arc) > 2:
                    flat(f"wrap{k}", band(arc, 0.018))
            flat("tail", band([(0.12, -0.07), (0.17, -0.1), (0.15, -0.15), (0.2, -0.17)], 0.018))
        elif cat == "tobacco":     # 연기 세 가닥(위로 피어오른다)
            for k, ox in enumerate((-0.07, 0.0, 0.07)):
                line = [(ox + 0.025 * math.sin(t * 5.5 + k), -0.15 + t * 0.3) for t in [i / 8 for i in range(9)]]
                flat(f"wisp{k}", band(line, 0.024, 0.008))
        else:                      # 빈 원(튜토리얼)
            ring("g", 0.09, 0.14)

    def sealed_box(cat):
        body = m_("iron"); glyph_m = mat("#E8DCBF", emit=0.6)
        box("body", (0.7, 0.5, 0.42), (0, 0, 0.21), body)
        box("lid", (0.74, 0.54, 0.08), (0, 0, 0.45), m_("brass"))
        for k in (-0.22, 0.22):
            box(f"strap{k}", (0.06, 0.56, 0.5), (k, 0, 0.25), m_("rust"))
        box("lock", (0.12, 0.05, 0.12), (0, -0.28, 0.3), m_("brass"))
        glyph(cat, 0.49, glyph_m)

    PAT = dict(food="이삭", drink="물방울", medical="엇갈린 띠", electronics="번개", stationery="깃", book="겹친 장",
               apparel="실타래", tobacco="연기", blank="빈 원(튜토리얼)")
    for c in CATS + ["blank"]:
        def mk(c=c):
            sealed_box(c)
        A[f"sealed_box_{c}"] = (mk, dict(id=f"sealed_box_{c}", footprint_m=[1, 1], tags=["sealed_box", "pickup", c],
                                          note="봉인 상자 — 뚜껑에 갈래 무늬(살짝 빛남). 무늬 이름 정본 = data/expedition_text.json. " + PAT[c]))

    # ── 표지들 ──
    @asset("beacon_spot", [1, 1], ["marker", "spot", "light"], "스팟 표지 등대: 말뚝 + 따뜻한 등(점광원 포함)")
    def _():
        rockmesh("base", 0.4, (0, 0, 0), m_("rock"), 501, squash=0.5)
        cyl("post", 0.07, 2.2, (0, 0, 1.1), m_("iron"), seg=6)
        for k in range(4):                                   # 등 바구니 = 가는 살 넷(등이 가려지지 않게)
            a = k * math.pi / 2 + math.pi / 4
            box(f"cage{k}", (0.03, 0.03, 0.36), (0.2 * math.cos(a), 0.2 * math.sin(a), 2.3), m_("brass"))
        rockmesh("lamp", 0.17, (0, 0, 2.14), mat(P["lamp"], emit=8.0), 503, squash=1.2, sub=1)
        cyl("cap", 0.24, 0.06, (0, 0, 2.49), m_("iron"), seg=8, r2=0.05)
        kelp("k", 0.3, 0.2, 1.0, m_("kelp"), 502, w=0.14)
        bpy.ops.object.light_add(type='POINT', location=(0, 0, 2.3)); L = bpy.context.object
        L.data.energy = 120; L.data.color = lin(P["lamp"]); L.data.shadow_soft_size = 0.3; PARTS.append(L)

    @asset("danger_shadow", [6, 4], ["marker", "danger", "silhouette"], "위험 표지: 바닥의 큰 그림자 + 떠 있는 검은 몸과 창백한 눈 둘(먹 얼룩 생물 계열). 몸은 반투명")
    def _():
        bm = bmesh.new(); n = 18
        vs = [bm.verts.new((2.8 * math.cos(2 * math.pi * k / n) * (1 + 0.12 * math.sin(k * 2.3)), 1.6 * math.sin(2 * math.pi * k / n), 0.03)) for k in range(n)]
        bm.faces.new(vs); obj_from_bm("shadow", bm, mat("#000000", alpha=0.45))
        rockmesh("body", 1.3, (0.2, 0.3, 2.2), mat(P["dark"], alpha=0.85), 601, squash=0.55, sub=2)
        for i in range(4):
            box(f"tend{i}", (0.12, 0.12, 1.4), (-0.6 + i * 0.45, 0.1 * (i % 2), 1.3), mat(P["dark"], alpha=0.75), rot=(0.1 * (i - 1.5), 0.15 * (i - 1.5), 0), taper=0.3)
        for x in (-0.25, 0.25):
            rockmesh(f"eye{x}", 0.13, (0.55 + x, -1.25, 2.3), mat(P["eye"], emit=4.0), 610, squash=1.0, sub=1)

    @asset("fork_marker", [1, 1], ["marker", "fork"], "갈림길 표지: 닳은 화살표 판 둘(끝이 위로 들림). 왼쪽 판에 작은 등불 = 「불빛 쪽」, 오른쪽 판은 검은 돌 = 「어둠 쪽」")
    def _():
        rockmesh("base", 0.35, (0, 0, 0), m_("rock"), 701, squash=0.5)
        cyl("post", 0.06, 1.8, (0, 0, 0.9), m_("wood"), seg=6)
        arrow = [(0, -0.09), (0.55, -0.09), (0.55, -0.16), (0.78, 0.0), (0.55, 0.16), (0.55, 0.09), (0, 0.09)]
        poly_flat("arrowL", [(-x, y) for x, y in arrow], m_("wood_l"), thick=0.04, rot=(0, -0.35, 0), loc=(-0.05, -0.02, 1.55))
        poly_flat("arrowR", arrow, m_("wood"), thick=0.04, rot=(0, 0.35, 0), loc=(0.05, -0.02, 1.2))
        rockmesh("lampL", 0.1, (-0.62, -0.08, 1.8), mat(P["lamp"], emit=8.0), 703, squash=1.2, sub=1)
        rockmesh("stoneR", 0.08, (0.66, -0.05, 1.38), m_("dark"), 702, squash=1.0)
        bpy.ops.object.light_add(type='POINT', location=(-0.62, -0.2, 1.85)); L = bpy.context.object
        L.data.energy = 25; L.data.color = lin(P["lamp"]); PARTS.append(L)

    @asset("base_hatch_landmark", [12, 6], ["landmark", "start", "base"], "출발 표지: 탑 외벽 아랫동(창 격자) + 위에서 내려온 사다리 + 사다리 발치의 등. 해치·포드는 화면 위(사다리 꼭대기 너머)에 있다는 약속. 외벽은 +y(뒤, glTF 로는 -Z)에, 사다리는 -x 쪽")
    def _():
        ground("g", m_("sand"), 801, amp=0.08, n=6, size=12.0)
        # 외벽(뒤쪽 벽) — 9 m 높이에서 잘림. 창 격자 2단
        box("wall", (11.0, 0.8, 9.0), (-0.2, -2.6, 4.5), m_("conc"))
        for c in range(5):
            for r in range(2):
                box(f"win{c}{r}", (1.1, 0.1, 1.6), (-4.2 + c * 2.0, -2.2, 2.6 + r * 3.4), mat("#6A4A2A" if (c + r) % 4 == 1 else "#0E1E24"))
        for k in range(3):
            box(f"slab{k}", (11.4, 1.0, 0.3), (-0.2, -2.55, 1.0 + k * 3.4), m_("conc_l"))
        # 받침 기둥(포드를 받치는 사선)
        box("strut", (0.25, 0.25, 7.0), (3.6, -1.6, 5.8), m_("rust"), rot=(0, 0.5, 0))
        # 사다리(위로 화면 밖까지)
        for x in (4.4, 4.9):
            box(f"rail{x}", (0.08, 0.08, 10.0), (x, 0.0, 5.0), m_("iron"))
        for k in range(30):
            box(f"rung{k}", (0.55, 0.05, 0.05), (4.65, 0.0, 0.3 + k * 0.33), m_("iron"))
        # 발치: 등 하나 + 상자 둘 + 해초
        cyl("lpost", 0.06, 1.6, (3.4, 1.0, 0.8), m_("iron"), seg=6)
        rockmesh("lamp", 0.26, (3.4, 1.0, 1.5), mat(P["lamp"], emit=8.0), 805, squash=1.2, sub=1)
        cyl("lcap", 0.32, 0.08, (3.4, 1.0, 1.95), m_("iron"), seg=8, r2=0.08)
        box("crate1", (0.8, 0.6, 0.5), (2.2, 0.6, 0.25), m_("wood"), rot=(0, 0, 0.2))
        box("crate2", (0.5, 0.5, 0.4), (2.4, 1.3, 0.2), m_("wood_l"), rot=(0, 0, -0.3))
        for i in range(4):
            kelp(f"k{i}", -4.5 + i * 1.6, -1.8, 1.5 + (i % 2), m_("kelp"), 810 + i)
        bpy.ops.object.light_add(type='POINT', location=(3.4, 1.0, 1.7)); L = bpy.context.object
        L.data.energy = 150; L.data.color = lin(P["lamp"]); PARTS.append(L)
        for o in PARTS:                       # 창이 난 면·사다리·등이 아이소 카메라(-y 쪽)를 보게 180° 돌린다 → 벽은 +y(뒤)
            o.location = Matrix.Rotation(math.pi, 4, 'Z') @ o.location
            o.rotation_euler.z += math.pi

    # ══════ 빌드·내보내기·썸네일 ══════
    report = {}
    ids = only or list(A.keys())
    for id_ in ids:
        fn, meta = A[id_]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        MATS.clear(); PARTS.clear()
        sc = bpy.context.scene
        fn()
        meshes = [o for o in PARTS if o.type == 'MESH']
        # 메시 합치기(재질별 프리미티브만 남게) — 노드 수 줄이기(B8)
        bpy.ops.object.select_all(action='DESELECT')
        for o in meshes:
            o.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        if len(meshes) > 1:
            bpy.ops.object.join()
        J = bpy.context.view_layer.objects.active; J.name = id_
        tris = sum(len(p.vertices) - 2 for p in J.data.polygons)
        lo = [min(v.co[i] + J.location[i] for v in J.data.vertices) for i in range(3)]
        hi = [max(v.co[i] + J.location[i] for v in J.data.vertices) for i in range(3)]
        path = os.path.join(DST, f"{id_}.glb")
        bpy.ops.object.select_all(action='SELECT')
        kw = dict(filepath=path, export_format='GLB', export_lights=True, export_cameras=False, export_apply=True,
                  use_selection=True, export_animations=False, export_yup=True)
        bpy.ops.export_scene.gltf(**kw)
        # 썸네일: 45°/45° 직교 + 손그림 선, 물빛 조명
        world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
        bg = world.node_tree.nodes.get("Background"); bg.inputs[0].default_value = (*lin("#2A6A78"), 1); bg.inputs[1].default_value = 0.9
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 10)); sun = bpy.context.object
        sun.rotation_euler = (math.radians(35), math.radians(10), math.radians(30)); sun.data.energy = 2.2; sun.data.color = lin("#CFE8E6")
        cx, cy, cz = [(lo[i] + hi[i]) / 2 for i in range(3)]
        span = max(hi[0] - lo[0], hi[1] - lo[1], (hi[2] - lo[2]) * 1.3, 1.0)
        bpy.ops.object.camera_add(); cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = span * 1.55
        az, el = math.radians(45), math.radians(45)
        d = 40
        cam.location = (cx + d * math.cos(el) * math.sin(az) * -1 * -1, cy - d * math.cos(el) * math.cos(az), cz + d * math.sin(el))
        cam.rotation_euler = (math.radians(90) - el, 0, az)
        cam.data.clip_end = 200
        sc.camera = cam
        sc.render.engine = 'BLENDER_EEVEE'; sc.render.resolution_x = sc.render.resolution_y = 320
        sc.render.film_transparent = True; sc.view_settings.view_transform = 'Standard'
        sc.render.use_freestyle = True; sc.render.line_thickness = 1.0
        vl = sc.view_layers[0]; vl.use_freestyle = True
        fs = vl.freestyle_settings; ls = fs.linesets[0] if fs.linesets else fs.linesets.new("l")
        ls.select_silhouette = ls.select_border = True; ls.select_crease = True; fs.crease_angle = math.radians(140)
        if ls.linestyle is None:
            ls.linestyle = bpy.data.linestyles.new("ls")
        ls.linestyle.color = lin("#1C1712"); ls.linestyle.thickness = 1.6
        sc.render.filepath = os.path.join(RAW, f"{id_}.png")
        bpy.ops.render.render(write_still=True)
        meta.update(file=f"{id_}.glb", tris=tris, size_kb=round(os.path.getsize(path) / 1024, 1),
                    bbox_m=[[round(v, 2) for v in lo], [round(v, 2) for v in hi]], thumb=f"art_raw/iso_sea/{id_}.png")
        report[id_] = meta
        print("ASSET", id_, tris, "tris", meta["size_kb"], "KB", flush=True)
    mp = os.path.join(RAW, "_build.json")
    old = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    old.update(report)
    json.dump(old, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ══════════════════════════════════════════════════════════════════════════════
def _sheet():
    from PIL import Image, ImageDraw, ImageFont
    B = json.load(open(os.path.join(RAW, "_build.json"), encoding="utf-8"))
    order = list(B.keys())
    cols = 7; cw, ch = 300, 340
    rows = (len(order) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch + 60), (10, 32, 40))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 15); big = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 24)
    except Exception:
        font = big = ImageFont.load_default()
    total = sum(v["size_kb"] for v in B.values())
    d.text((16, 14), f"S15-E 물속 아이소 키트 — {len(order)}종 · GLB 합계 {total/1024:.2f} MB · 45°/45° 직교 · 생성 AI 없음", fill=(232, 220, 191), font=big)
    for i, k in enumerate(order):
        x, y = (i % cols) * cw, (i // cols) * ch + 60
        d.rectangle([x + 6, y + 6, x + cw - 6, y + ch - 6], fill=(18, 52, 62))
        t = Image.open(os.path.join(ROOT, B[k]["thumb"])).convert("RGBA").resize((288, 288), Image.LANCZOS)
        sheet.paste(t, (x + 6, y + 8), t)
        d.text((x + 12, y + 296), k, fill=(240, 200, 120), font=font)
        d.text((x + 12, y + 316), f"{B[k]['tris']} tri · {B[k]['size_kb']} KB · {B[k]['footprint_m'][0]}×{B[k]['footprint_m'][1]} m", fill=(170, 200, 196), font=font)
    out = os.path.join(ROOT, "docs", "reports", "s15e_iso_sea_sheet.png")
    sheet.save(out, optimize=True)
    man = {"_note": "S15-E 물속 아이소 키트(원정 3D 화면). 단위 m, GLB Y-up(Blender +y → glTF -Z), 원점 = 바닥 가운데(발 높이 0). 땅 타일 6 m 격자. 썸네일 카메라는 Blender -y 쪽에서 45°/45°로 본다. 생성기 tools/blender_iso_sea.py",
           "palette": "M5 — 청록은 물(배경·안개)에만, 바닥 무채색, 등불 #FFC870, 해초 올리브",
           "scene_hint": {"fog": "#0E3440", "fog_near_m": 8, "fog_far_m": 40, "ambient": "#2A6A78", "sun": "#CFE8E6",
                          "note": "물속은 Three.js 안개(FogExp2 또는 선형)로. 빛나는 것(등·상자 무늬·눈)은 emissive 라 안개 속에서도 보인다"},
           "box_categories": CATS + ["blank"],
           "assets": [{k2: B[k][k2] for k2 in ("id", "file", "footprint_m", "tags", "note", "tris", "size_kb", "bbox_m")} for k in order],
           "total_kb": round(total, 1)}
    json.dump(man, open(os.path.join(DST, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("sheet", out, "total", round(total), "KB")


if __name__ == "__main__":
    try:
        import bpy  # noqa: F401
        IN_BLENDER = True
    except ImportError:
        IN_BLENDER = False
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ([] if IN_BLENDER else sys.argv[1:])
    if argv and argv[0] == "sheet":
        _sheet()
    else:
        _blender(argv)
