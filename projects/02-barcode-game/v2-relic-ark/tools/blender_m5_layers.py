"""S12-A — M5 「절벽 끝에 기댄 가라앉은 탑」 게임 화면용 레이어 (82.5 px/m, 세계 5600×3400).

숫자의 정본은 tools/m5_layout.py(→ static/art/maps/m5/layout.json). 이 스크립트는 그 숫자로만 그린다.

  1) Blender 단계 — 구조물 패스 6개(절벽·탑·유리·승강로·승강기 칸·앞 해초)를 세계 전체 캔버스로 렌더
     "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --python tools/blender_m5_layers.py -- render
  2) 합성 단계 — 뒤 바다(JPG)·생물 아틀라스·칸 오버레이·잘라 내기·용량 줄이기·미리보기
     python tools/blender_m5_layers.py post

화풍: S11 블록아웃과 같은 처방(2~3단 평면 음영 + Freestyle 손그림 선, 청록은 물에만, 가장 밝은 것은 방 안 등불).
생성 AI 없음. 수채·flux 아님(DECISIONS 2026-10-03, PM 권고 ①).
"""
import os, sys, math, random, json

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import m5_layout as LY  # noqa: E402

RAW = os.path.join(ROOT, "art_raw", "maps", "m5")
DST = os.path.join(ROOT, "static", "art", "maps", "m5")
ART = os.path.join(ROOT, "static", "art")
os.makedirs(RAW, exist_ok=True); os.makedirs(DST, exist_ok=True)

W, H, PPM = LY.W, LY.H, LY.PPM
PASSES = ["cliff", "tower", "glass", "shaft", "car", "front", "ent_back", "hatch_closed", "hatch_open"]
CAR_RECT = (200, 3000, 338, 3190)             # 승강기 칸을 렌더하는 빈 자리(세계 px). 렌더 뒤 잘라 낸다
SHAFT_SPR_PAD = 10


# ══════════════════════════════════════════════════════════════════════════════
#  1단계 — Blender
# ══════════════════════════════════════════════════════════════════════════════
def _blender():
    import bpy, bmesh

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    noline = bpy.data.collections.new("NOLINE"); sc.collection.children.link(noline)
    REG = {p: [] for p in PASSES}
    cur = {"pass": "tower"}

    def s2l(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lin(h):
        h = h.lstrip("#"); return tuple(s2l(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))

    MATS = {}

    def mat(name, cols=None, stops=None, noise=0.06, nscale=3.0):
        if name in MATS:
            return MATS[name]
        m = bpy.data.materials.new(name); m.use_nodes = True
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        if len(cols) == 1:
            em.inputs["Color"].default_value = (*lin(cols[0]), 1)
        else:
            tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(tc.outputs["Generated"], sep.inputs[0])
            nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = nscale
            nz.inputs["Detail"].default_value = 3.0
            nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
            mr = nt.nodes.new("ShaderNodeMapRange")
            mr.inputs["To Min"].default_value = -noise; mr.inputs["To Max"].default_value = noise
            nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
            add = nt.nodes.new("ShaderNodeMath"); add.operation = 'ADD'
            nt.links.new(sep.outputs["Z"], add.inputs[0]); nt.links.new(mr.outputs[0], add.inputs[1])
            ramp = nt.nodes.new("ShaderNodeValToRGB"); cr = ramp.color_ramp; cr.interpolation = 'CONSTANT'
            n = len(cols); stops = stops or [i / n for i in range(n)]
            cr.elements[0].position = 0.0; cr.elements[0].color = (*lin(cols[0]), 1)
            cr.elements[1].position = stops[1]; cr.elements[1].color = (*lin(cols[1]), 1)
            for i in range(2, n):
                e = cr.elements.new(stops[i]); e.color = (*lin(cols[i]), 1)
            nt.links.new(add.outputs[0], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
        MATS[name] = m
        return m

    def P(px, py):                     # 세계 px → Blender (x, z) m
        return (px / PPM, -py / PPM)

    def _obj(name, bm, m, line=True):
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(name, me)
        (sc.collection if line else noline).objects.link(o)
        me.materials.append(m); REG[cur["pass"]].append(o)
        return o

    def jag(pts, amp=8, step=40, closed=True, seed=1):
        r = random.Random(seed); outp = []
        n = len(pts); rn = n if closed else n - 1
        for i in range(rn):
            a = pts[i]; b = pts[(i + 1) % n]
            d = math.dist(a, b); k = max(1, int(d / step))
            nx, ny = (-(b[1] - a[1]) / (d or 1), (b[0] - a[0]) / (d or 1))
            for j in range(k):
                t = j / k; o = r.uniform(-amp, amp) if j else 0.0
                outp.append((a[0] + (b[0] - a[0]) * t + nx * o, a[1] + (b[1] - a[1]) * t + ny * o))
        if not closed:
            outp.append(pts[-1])
        return outp

    def poly(name, pts, y, m, line=True, j=0.0, seed=1, step=40):
        """pts: 세계 px. y: 깊이(작을수록 앞)"""
        if j:
            pts = jag(pts, amp=j, seed=seed, step=step)
        bm = bmesh.new()
        vs = [bm.verts.new((p[0] / PPM, y, -p[1] / PPM)) for p in pts]
        try:
            bm.faces.new(vs)
        except Exception:
            pass
        return _obj(name, bm, m, line)

    def ribbon(name, pts, w, y, m, line=True, w1=None):
        w1 = w if w1 is None else w1
        bm = bmesh.new(); Lv, Rv = [], []; n = len(pts)
        for i, p in enumerate(pts):
            a = pts[max(0, i - 1)]; b = pts[min(n - 1, i + 1)]
            dx, dy = b[0] - a[0], b[1] - a[1]; d = math.hypot(dx, dy) or 1
            nx, ny = -dy / d, dx / d
            ww = (w + (w1 - w) * i / max(1, n - 1)) / 2
            Lv.append(bm.verts.new(((p[0] + nx * ww) / PPM, y, -(p[1] + ny * ww) / PPM)))
            Rv.append(bm.verts.new(((p[0] - nx * ww) / PPM, y, -(p[1] - ny * ww) / PPM)))
        for i in range(n - 1):
            bm.faces.new((Lv[i], Lv[i + 1], Rv[i + 1], Rv[i]))
        return _obj(name, bm, m, line)

    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def ellipse(cx, cy, rx, ry, n=28, a0=0.0, a1=2 * math.pi):
        full = a1 - a0 >= 2 * math.pi - 1e-6
        return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy - ry * math.sin(a0 + (a1 - a0) * i / n))
                for i in range(n + (0 if full else 1))]

    def kelp(name, x, y, h, dep, m, seed, lean=0.0, w=24, up=True):
        """해초: (x,y) 뿌리에서 위(up) 또는 아래로. 길이 h px"""
        r = random.Random(seed); pts = []; ph = r.uniform(0, 6.28); n = 14
        sgn = -1 if up else 1
        for i in range(n + 1):
            t = i / n
            pts.append((x + math.sin(ph + t * 4.2) * 40 * t + lean * t * h, y + sgn * t * h))
        ribbon(name, pts, w, dep, m, w1=w * 0.35)
        for i in range(3, n, 3):
            px, py = pts[i]; s = 1 if i % 2 else -1
            ribbon(name + f"_l{i}", [(px, py), (px + s * 40, py + sgn * 28), (px + s * 76, py + sgn * 44)], 17, dep - 0.01, m, w1=4)

    rr = random.Random(512)

    # ─────────────── 절벽 (cliff) ───────────────
    cur["pass"] = "cliff"
    rock = mat("rock", ["#2C241B", "#3C3227", "#4E4233", "#62543F"], [0, 0.28, 0.58, 0.84], noise=0.05, nscale=1.4)
    edge = [(-20, 470), (200, 452), (420, 480), (640, 468), (860, 498), (1000, 524), (1056, 560),
            (1062, 640), (1040, 720), (1078, 820), (1104, 1000), (1128, 1200), (1118, 1450), (1136, 1700), (1120, 1950), (1132, 2200), (1100, 2350),
            (1020, 2440), (880, 2400), (760, 2475), (600, 2430), (450, 2492), (300, 2440), (150, 2505), (-20, 2462)]
    poly("cliff", edge, 0.85, rock, j=10, seed=11, step=36)
    # 지층 띠 — 밝은 결이 위에서 아래로 반복되어 높이가 읽힌다
    strata_cols = [("#6E5E48", "#7E6C52"), ("#625440", "#72624A"), ("#5A4C3A", "#685842")]
    for i, y0 in enumerate([640, 900, 1160, 1420, 1680, 1940, 2200]):
        pts = []; x = -10
        left = -10; right = 1050 if y0 < 800 else 1110
        while x <= right:
            pts.append((x, y0 + rr.uniform(-12, 12) + x * 0.035)); x += 90
        c = strata_cols[i % 3]
        ribbon(f"strata{i}", pts, 26 + rr.uniform(0, 16), 0.80, mat(f"strata{i%3}", list(c), [0, 0.5]), line=(i % 2 == 0))
        # 결 아래 그늘 한 줄
        ribbon(f"strata_sh{i}", [(p[0], p[1] + 24) for p in pts], 10, 0.81, mat("strata_sh", ["#221B14"]), line=False)
    cm = mat("crack", ["#120D09"])
    for i in range(16):
        x = rr.uniform(40, 1040); y = rr.uniform(640, 2300); pts = [(x, y)]
        for _ in range(4):
            x += rr.uniform(-50, 50); y += rr.uniform(40, 120); pts.append((x, y))
        ribbon(f"crk{i}", pts, 12, 0.78, cm, w1=3)
    # 꼭대기 턱의 차가운 테(위에서 오는 빛) + 오른쪽 끝(심연 쪽) 모서리 테
    top_edge = edge[:8]
    ribbon("rim_top", jag(top_edge, amp=6, closed=False, seed=12), 30, 0.74, mat("rim", ["#5E716C", "#82968C"], [0, 0.5]))
    ribbon("rim_side", jag(edge[7:16], amp=5, closed=False, seed=13), 18, 0.75, mat("rim2", ["#4A5A56", "#627470"], [0, 0.5]))
    # 꼭대기 턱 위: 바위 몇 개와 해초 무리(초록은 생명 — B2·B9)
    for i, (x, y, rx, ry) in enumerate([(120, 456, 70, 34), (430, 474, 50, 26), (760, 482, 40, 22)]):
        poly(f"boulder{i}", ellipse(x, y, rx, ry, 18, 0, math.pi), 0.72, mat("boulder", ["#3E352A", "#5C4F3D", "#7A6A52"], [0, 0.4, 0.8]),
             j=4, seed=40 + i, step=20)
    km = mat("kelp", ["#24361A", "#34481F", "#4E6228"], [0, 0.5, 0.85])
    for i, (x, y, h, ln) in enumerate([(70, 464, 230, 0.05), (210, 450, 300, -0.08), (330, 470, 180, 0.1),
                                       (560, 474, 260, 0.04), (820, 492, 200, 0.15), (1030, 546, 150, 0.25)]):
        kelp(f"kc{i}", x, y, h, 0.70, km, 600 + i, lean=ln, w=22)
    # 절벽 틈의 이끼 띠(옆면)
    for i, (x, y) in enumerate([(1100, 1300), (1110, 1820), (1095, 2280), (400, 2470)]):
        kelp(f"km{i}", x, y, 120, 0.70, km, 700 + i, lean=0.3, w=16)
    # 바위를 판 굴 방(뒤판)과 탑으로 가는 통로
    holl = mat("hollow", ["#120D0A", "#1C1510"], [0, 0.6])
    tun = mat("tunnel", ["#2A1E16", "#3A2A1E", "#4A3626"], [0, 0.45, 0.85])
    plank = mat("plank", ["#5A3E26", "#6E4C2E"], [0, 0.5])
    for rc in LY.build()["rock_cells"]:
        x, y, w_, h_ = rc["x"], rc["y"], rc["w"], rc["h"]
        poly(f"hollow_{rc['id']}", rect(x - 16, y - 16, x + w_ + 16, y + h_ + 14), 0.6, holl, j=6, seed=hash(rc["id"]) & 255, step=30)
        t = rc["tunnel"]
        poly(f"tun_{rc['id']}", rect(t["x"] - 10, t["y"], t["x"] + t["w"], t["y"] + t["h"]), 0.58, tun, j=5, seed=7, step=30)
        ribbon(f"tunfloor_{rc['id']}", [(t["x"] - 10, t["floor_y"] + 4), (t["x"] + t["w"], t["floor_y"] + 4)], 16, 0.55, plank)
        for k in range(3):        # 버팀목
            bx = t["x"] + 30 + k * 110
            ribbon(f"tunpost_{rc['id']}{k}", [(bx, t["floor_y"]), (bx, t["y"] + 8)], 12, 0.56, plank)
            ribbon(f"tunbeam_{rc['id']}{k}", [(bx - 30, t["y"] + 14), (bx + 30, t["y"] + 14)], 10, 0.56, plank)
        lx = t["x"] + t["w"] * 0.5
        poly(f"tunlamp_{rc['id']}", rect(lx - 9, t["y"] + 26, lx + 9, t["y"] + 50), 0.54, mat("lampw", ["#FFC870"]))
        ribbon(f"tunlampw_{rc['id']}", [(lx, t["y"] + 14), (lx, t["y"] + 26)], 3, 0.545, mat("wire", ["#2A2420"]), line=False)
    # 절벽 밑동에서 늘어진 덩굴 — 그 아래는 허공(해구)
    for i, x in enumerate([1040, 900, 760, 610, 470, 300, 140]):
        y0 = 2420 + (i % 3) * 25; ln = 220 + (i * 97) % 260
        pts = [(x + math.sin(t * 2.5 + i) * 26, y0 + t * ln) for t in [k / 8 for k in range(9)]]
        ribbon(f"hang{i}", pts, 16, 0.80, km, w1=4)

    # ─────────────── 탑 껍데기 (tower) ───────────────
    cur["pass"] = "tower"
    D = LY.build()
    conc = mat("conc", ["#1E2426", "#2A3234", "#384244", "#4A5454"], [0, 0.3, 0.65, 0.9], noise=0.04)
    conc_d = mat("conc_d", ["#101415", "#192022", "#232C2E"], [0, 0.5, 0.85])
    facade_m = mat("facade", ["#1C2426", "#283234", "#36403F"], [0, 0.5, 0.85])
    ruin = mat("ruin", ["#0D1214", "#141C1F", "#1B2629"], [0, 0.55, 0.9], noise=0.05)
    ruin_fl = mat("ruin_fl", ["#1C1A16", "#26231D"], [0, 0.6])
    deb = mat("debris", ["#1E2020", "#2C2E2C", "#3A3A36"], [0, 0.5, 0.85])
    X0, X1, SX0, SX1 = LY.TOWER_X0, LY.TOWER_X1, LY.SEC_X0, LY.SEC_X1
    bottom = H + 60
    poly("body", rect(X0, LY.ROOF_Y, X1, bottom), 1.5, conc_d, j=2, seed=2)
    # 층 목록: 칸 층 0..4 + 그 아래 이어지는 유령 층(어둠에 잠김)
    tops = list(LY.STOREY_Y)
    while tops[-1] + LY.PITCH < bottom:
        tops.append(tops[-1] + LY.PITCH)
    # 빈 칸의 속(지어지지 않은 폐허): 뒷벽 + 옛 창틀 + 바닥 잔해 + 늘어진 전선
    for si, ty in enumerate(tops):
        for c in range(3):
            x = LY.COL_X[c]; key = f"{si}_{c}"; r = random.Random(si * 7 + c)
            poly(f"rb_{key}", rect(x, ty, x + LY.CELL_W, ty + LY.CELL_H), 1.2, ruin, line=False)
            fy = ty + LY.FLOOR_IN_CELL
            poly(f"rf_{key}", rect(x, fy, x + LY.CELL_W, ty + LY.CELL_H), 1.15, ruin_fl, line=False)
            # 뒷벽의 옛 창(문명의 잔해 — 바깥이 비친다)
            for k in range(r.choice([2, 3])):
                wx = x + 70 + k * 170 + r.uniform(-14, 14)
                poly(f"rw_{key}{k}", rect(wx, ty + 70, wx + 100, ty + 210), 1.1,
                     mat("rwin", ["#0A1A20", "#0F242C"], [0, 0.6]), line=True)
                ribbon(f"rwm_{key}{k}", [(wx + 50, ty + 70), (wx + 50, ty + 210)], 5, 1.09, mat("rwm", ["#2A3234"]), line=False)
            # 바닥 잔해 더미
            dx = x + r.uniform(60, LY.CELL_W - 200)
            poly(f"rd_{key}", [(dx, fy + 4), (dx + 30, fy - 30), (dx + 80, fy - 46), (dx + 140, fy - 22), (dx + 180, fy + 4)],
                 1.05, deb, j=5, seed=si * 11 + c, step=18)
            if r.random() < 0.6:                       # 늘어진 전선
                cx_ = x + r.uniform(80, LY.CELL_W - 80)
                ribbon(f"rcab_{key}", [(cx_, ty), (cx_ + 20, ty + 60), (cx_ + 8, ty + 120 + r.uniform(0, 50))], 5, 1.04,
                       mat("cable", ["#0A0C0C"]), line=False)
            if r.random() < 0.5:                       # 바닥 틈에서 자란 해초
                kelp(f"rk_{key}", x + r.uniform(40, LY.CELL_W - 40), fy, r.uniform(90, 170), 1.03,
                     mat("kelp_in", ["#1A2814", "#26361A"], [0, 0.6]), 900 + si * 3 + c, w=14)
    # 기둥(칸 사이 벽·승강로 벽·단면 끝)
    def colm(name, x0, x1):
        poly(name, rect(x0, LY.ROOF_Y - 2, x1, bottom), 0.9, conc, j=1.5, seed=len(name))
    colm("col_L", SX0 - 22, SX0)
    colm("col_R", SX1, SX1 + 22)
    for i, sx in enumerate(LY.SHAFT_X):
        colm(f"col_s{i}a", sx - LY.WALL, sx)
        colm(f"col_s{i}b", sx + LY.SHAFT_W, sx + LY.SHAFT_W + LY.WALL)
    poly("outer_L", rect(X0 - 14, LY.ROOF_Y - 60, X0 + 22, bottom), 0.88, conc, j=2, seed=31)
    poly("outer_R", rect(X1 - 22, LY.ROOF_Y - 60, X1 + 14, bottom), 0.88, conc, j=2, seed=32)
    # 외벽(창 격자) — 단면 양옆으로 남은 건물
    for side, (fx0, fx1) in enumerate([(X0 + 22, SX0 - 22), (SX1 + 22, X1 - 22)]):
        poly(f"facade{side}", rect(fx0, LY.ROOF_Y, fx1, bottom), 1.0, facade_m, j=2, seed=3 + side)
        for si, ty in enumerate(tops):
            for wxk in range(2):
                for row in range(2):
                    wx = fx0 + 14 + wxk * 74; wy = ty + 34 + row * 160
                    roll = rr.random()
                    if si <= 1 and roll < 0.28:
                        col = "#6A4A2A"                 # 희미하게 불 비친 창(방 안보다 어둡게)
                    elif roll < 0.25:
                        col = "#05080A"                 # 깨진 창
                    else:
                        col = "#1A3A44" if si < 3 else "#0E1E24"
                    poly(f"w{side}_{si}_{wxk}{row}", rect(wx, wy, wx + 58, wy + 124), 0.95, mat("win" + col, [col]))
                    ribbon(f"wm{side}_{si}_{wxk}{row}", [(wx, wy + 62), (wx + 58, wy + 62)], 4, 0.94, mat("wmull", ["#3A4444"]), line=False)
    # 바닥 슬래브: 각 층 위·맨 아래 칸 아래, 그리고 유령 층들
    for si, ty in enumerate(tops):
        poly(f"slab{si}", rect(X0 - 24, ty - LY.SLAB, X1 + 24, ty), 0.6, conc, j=2, seed=50 + si)
        ribbon(f"slabl{si}", [(X0 - 24, ty - LY.SLAB + 5), (X1 + 24, ty - LY.SLAB + 5)], 8, 0.59, mat("slablit", ["#56605E"]), line=False)
    # 지붕(= 홀 바닥) 윗면 + 양 끝 난간
    ribbon("roofdeck", [(X0 - 40, LY.ROOF_Y - 6), (X1 + 40, LY.ROOF_Y - 6)], 14, 0.55, mat("roofc", ["#4A5454", "#66706C"], [0, 0.6]))
    dg = LY.DOME_GLASS
    for i, (a, b) in enumerate([(X0 - 40, dg["cx"] - dg["rx"]), (dg["cx"] + dg["rx"], X1 + 40)]):
        poly(f"parapet{i}", rect(a, LY.ROOF_Y - 70, b, LY.ROOF_Y - 12), 0.56, conc, j=3, seed=60 + i)
    # 지붕 위: 왼쪽 부러진 안테나, 오른쪽 물탱크
    ribbon("antenna", [(X0 + 120, LY.ROOF_Y - 70), (X0 + 96, 640), (X0 + 210, 520)], 20, 0.5, mat("ant", ["#4A3E34", "#5E4E40"], [0, 0.5]))
    ribbon("antenna_x", [(X0 + 70, 860), (X0 + 150, 830)], 8, 0.5, mat("ant", []))
    poly("tank", rect(X1 - 150, LY.ROOF_Y - 210, X1 - 30, LY.ROOF_Y - 70), 0.52, mat("tank", ["#3A2A22", "#54382A", "#6A4630"], [0, 0.5, 0.85]), j=3, seed=71)
    for k in range(2):
        ribbon(f"tank_leg{k}", [(X1 - 140 + k * 100, LY.ROOF_Y - 70), (X1 - 140 + k * 100, LY.ROOF_Y - 12)], 10, 0.53, mat("ant", []))
    # 돔 골조(유리는 glass 패스)
    rib = mat("drib", ["#6A5A48", "#86735A"], [0, 0.6])
    cx_, by_, rx_, ry_ = dg["cx"], dg["base_y"], dg["rx"], dg["ry"]
    ribbon("dome_arc", ellipse(cx_, by_ - 10, rx_, ry_, 48, 0, math.pi), 22, 0.45, rib)
    # 경선(옆에서 본 반구의 세로 골조 = 폭이 줄어드는 반타원) + 위선(가로 띠)
    for k in (0.36, 0.7):
        ribbon(f"dmer{k}", ellipse(cx_, by_ - 10, rx_ * k, ry_, 36, 0, math.pi), 12, 0.46, rib)
    ribbon("dmer0", [(cx_, by_ - 10), (cx_, by_ - 10 - ry_)], 12, 0.46, rib)
    for a in (0.42, 0.8, 1.12):
        yy = by_ - 10 - ry_ * math.sin(a); xx = rx_ * math.cos(a)
        ribbon(f"dpar{a}", [(cx_ - xx, yy), (cx_ + xx, yy)], 10, 0.46, rib)
    # 홀 안: 양 끝 화분 상자(초록) + 꼭대기에 매단 홀 등(따뜻한 하나)
    for i, x in enumerate([SX0 + 20, SX1 - 170]):
        poly(f"planter{i}", rect(x, LY.ROOF_Y - 64, x + 150, LY.ROOF_Y - 8), 0.44, mat("planter", ["#4A3020", "#6A4428"], [0, 0.6]), j=2, seed=80 + i)
        for k in range(4):
            kelp(f"hplant{i}{k}", x + 20 + k * 36, LY.ROOF_Y - 60, 70 + (k * 37) % 60, 0.43, km, 800 + i * 5 + k, lean=0.1 * (k - 1.5), w=14)
    ribbon("hall_chain", [(cx_, by_ - ry_ + 20), (cx_, LY.DOME["y"] + 60)], 5, 0.47, mat("wire", []), line=False)
    poly("hall_lamp", ellipse(cx_, LY.DOME["y"] + 78, 26, 20, 16), 0.46, mat("hlamp", ["#FFC870"]))
    poly("hall_lamp_hood", [(cx_ - 34, LY.DOME["y"] + 70), (cx_ + 34, LY.DOME["y"] + 70), (cx_ + 16, LY.DOME["y"] + 52), (cx_ - 16, LY.DOME["y"] + 52)],
         0.455, mat("hood", ["#3A2E24"]))
    # 지붕 오른쪽 끝에서 심연으로 내민 부러진 철골 + 유인 등불
    g = [tuple(p) for p in LY.GIRDER]
    gm = mat("gird", ["#3A2420", "#5A3428", "#704030"], [0, 0.5, 0.85])
    ribbon("girder", g, 40, 0.45, gm)
    ribbon("girder_lo", [(g[0][0], g[0][1] + 40), (g[1][0] - 40, g[1][1] + 60)], 16, 0.46, gm)
    for i in range(7):
        t = (i + 0.5) / 7; x = g[0][0] + (g[1][0] - g[0][0]) * t; y = g[0][1] + (g[1][1] - g[0][1]) * t
        ribbon(f"gird_x{i}", [(x - 30, y + 46), (x + 30, y - 4)], 10, 0.455, gm)
    lx, ly = LY.LURE["x"], LY.LURE["y"]
    ribbon("lure_rope", [(g[2][0], g[2][1]), (lx + 8, (g[2][1] + ly) / 2), (lx, ly - 40)], 6, 0.45, mat("rope", ["#8A7A60"]), line=False)
    poly("lure_cage", ellipse(lx, ly, 30, 36, 14), 0.44, mat("lure", ["#E8B060"]))
    ribbon("lure_bar", [(lx - 30, ly), (lx + 30, ly)], 4, 0.435, mat("lurebar", ["#5A3A24"]), line=False)
    # 외벽 해초(심연 쪽 창턱에서) — 시드 난수로 흩는다(B9)
    for i, (x, y, h) in enumerate([(X1 + 4, 1490, 300), (X1 + 8, 2200, 420), (X1 - 6, 1060, 170), (X1 + 2, 2600, 380),
                                   (X0 + 6, 2560, 340), (X1 - 120, LY.ROOF_Y - 70, 150)]):
        kelp(f"fk{i}", x, y, h, 0.4, km, 500 + i, lean=0.15 if x > 2000 else -0.15, w=22)

    # ─────────────── 유리(glass) ───────────────
    cur["pass"] = "glass"
    poly("glass", ellipse(cx_, by_ - 10, rx_, ry_, 48, 0, math.pi), 0.6,
         mat("dglass", ["#1E4248", "#2C5E64", "#427E84"], [0, 0.45, 0.85]), line=False)

    # ─────────────── 승강로(shaft) — A 하나만 그리고 B 에도 같은 그림을 쓴다 ───────────────
    cur["pass"] = "shaft"
    sh = D["shafts"][0]; sx, sw = sh["x"], sh["w"]
    iron = mat("iron", ["#3A332C", "#4E443A", "#625646"], [0, 0.5, 0.85])
    poly("sh_back", rect(sx, LY.ROOF_Y, sx + sw, sh["bottom_y"]), 0.9, mat("shback", ["#080B0C", "#0E1314"], [0, 0.6]), line=False)
    for k, x in enumerate([sx + 14, sx + sw - 14]):
        ribbon(f"rail{k}", [(x, sh["top_y"]), (x, sh["bottom_y"])], 10, 0.8, iron)
    ribbon("cable", [(sx + sw / 2, sh["top_y"]), (sx + sw / 2, sh["bottom_y"])], 4, 0.82, mat("cable2", ["#6A6050"]), line=False)
    yb = sh["top_y"] + 40; k = 0
    while yb < sh["bottom_y"] - 60:          # 엇갈린 가새
        a, b = (sx + 14, yb), (sx + sw - 14, yb + 110)
        if k % 2:
            a, b = (sx + sw - 14, yb), (sx + 14, yb + 110)
        ribbon(f"brace{k}", [a, b], 5, 0.83, iron, line=False)
        yb += 120; k += 1
    for st in sh["stops"]:
        dy = st["door_y"]
        ribbon(f"door_{st['floor']}", [(sx - 2, dy), (sx - 2, dy - 214), (sx + sw + 2, dy - 214), (sx + sw + 2, dy)], 12, 0.7, iron)
        ribbon(f"sill_{st['floor']}", [(sx - 8, dy + 4), (sx + sw + 8, dy + 4)], 10, 0.69, mat("sill", ["#6A5A48"]))
        poly(f"stoplamp_{st['floor']}", ellipse(sx + sw / 2, dy - 232, 9, 7, 12), 0.68, mat("lampw", []))
    poly("sh_head", rect(sx - 14, sh["top_y"] - 56, sx + sw + 14, sh["top_y"]), 0.66, iron, j=2, seed=90)
    poly("sh_wheel", ellipse(sx + sw / 2, sh["top_y"] - 28, 22, 22, 16), 0.65, mat("wheel", ["#7A6A54"]))

    # ─────────────── 승강기 칸(car) ───────────────
    cur["pass"] = "car"
    cx0, cy0, cx1, cy1 = CAR_RECT
    poly("car_back", rect(cx0 + 6, cy0 + 22, cx1 - 6, cy1 - 10), 0.9, mat("carback", ["#2A2018", "#3A2C20"], [0, 0.6]), line=False)
    ribbon("car_frame", [(cx0 + 4, cy1), (cx0 + 4, cy0 + 16), (cx1 - 4, cy0 + 16), (cx1 - 4, cy1)], 10, 0.8, iron)
    poly("car_floor", rect(cx0, cy1 - 14, cx1, cy1), 0.79, mat("carfloor", ["#5A4632", "#6E5638"], [0, 0.6]))
    poly("car_roof", rect(cx0, cy0 + 4, cx1, cy0 + 22), 0.79, iron)
    poly("car_hook", rect((cx0 + cx1) / 2 - 8, cy0 - 8, (cx0 + cx1) / 2 + 8, cy0 + 6), 0.78, iron)
    poly("car_lamp", ellipse((cx0 + cx1) / 2, cy0 + 34, 12, 8, 12), 0.75, mat("lampw", []))
    for k in range(5):                         # 옆 격자문(앞쪽은 비워 사람을 가리지 않는다)
        x = cx0 + 6 + k * 3
        ribbon(f"car_gateL{k}", [(cx0 + 10, cy0 + 26 + k * 32), (cx0 + 22, cy0 + 26 + k * 32)], 3, 0.7, iron, line=False)
        ribbon(f"car_gateR{k}", [(cx1 - 22, cy0 + 26 + k * 32), (cx1 - 10, cy0 + 26 + k * 32)], 3, 0.7, iron, line=False)

    # ─────────────── 앞 해초(front) ───────────────
    cur["pass"] = "front"
    fkm = mat("fkelp", ["#0C130A", "#142010", "#1C2C14"], [0, 0.55, 0.9])
    for i, (x, h, ln) in enumerate([(30, 820, 0.05), (110, 640, -0.04), (200, 900, 0.08), (300, 520, 0.1), (420, 380, 0.12),
                                    (5230, 560, -0.1), (5330, 760, -0.05), (5440, 980, -0.08), (5540, 700, 0.02)]):
        kelp(f"ffk{i}", x, H + 20, h, 0.2, fkm, 1000 + i, lean=ln, w=40)
    for i, (x, y) in enumerate([(0, H - 120), (5380, H - 140)]):
        poly(f"frock{i}", ellipse(x + 110, y + 160, 260, 170, 20, 0, math.pi), 0.25, mat("frock", ["#06090A", "#0C1012"], [0, 0.7]), j=12, seed=1100 + i, step=30)

    # ─────────────── S12-F 입구(에어락 포드) ───────────────
    cur["pass"] = "ent_back"
    PO, PI, ID, HT, PF, LD = LY.POD, LY.POD_IN, LY.INNER_DOOR, LY.HATCH, LY.PLATFORM, LY.LADDER
    hull = mat("hull", ["#3A2A20", "#56382A", "#6E4A34", "#86603F"], [0, 0.3, 0.62, 0.88], noise=0.04)
    x0p, x1p, y0p, y1p = PO["x0"], PO["x1"], PO["y0"], PO["y1"]
    rad = 70
    outer = [(x0p, y1p), (x0p, y0p)]
    outer += [(x1p - rad + rad * math.sin(a * math.pi / 16), y0p + rad - rad * math.cos(a * math.pi / 16)) for a in range(9)]
    outer += [(x1p, y1p - 30), (x1p - 30, y1p)]
    poly("pod_hull", outer, 0.42, hull, j=2, seed=301, step=24)
    for k in range(9):                                            # 리벳 띠
        rx = x0p + 40 + k * 52
        poly(f"rivet{k}", ellipse(rx, y0p + 14, 4, 4, 8), 0.41, mat("rivet", ["#A08060"]), line=False)
    inner_m = mat("podin", ["#2A1E16", "#36281C", "#423020"], [0, 0.5, 0.85], noise=0.05)
    poly("pod_in", rect(PI["x"], PI["y"], PI["x"] + PI["w"], LY.ROOF_Y), 0.40, inner_m, line=False)
    for k in range(4):                                            # 벽 판 이음매
        xx = PI["x"] + 92 + k * 92
        ribbon(f"seam{k}", [(xx, PI["y"]), (xx, LY.ROOF_Y)], 4, 0.395, mat("seam", ["#1E150F"]), line=False)
    # 안쪽 문(홀 쪽)·해치 자리(바깥 쪽): 벽 띠에 낸 구멍
    poly("idoor_gap", rect(x0p - 2, ID["y0"], PI["x"] + 2, ID["y1"]), 0.39, mat("gap", ["#2E2218", "#3A2A1E"], [0, 0.6]), line=False)
    ribbon("idoor_frame", [(x0p - 4, ID["y1"]), (x0p - 4, ID["y0"] - 8), (PI["x"] + 4, ID["y0"] - 8), (PI["x"] + 4, ID["y1"])], 10, 0.385, iron)
    poly("hatch_gap", rect(PI["x"] + PI["w"] - 2, HT["y0"], x1p + 2, HT["y1"]), 0.39, mat("hgap", ["#0A2028", "#0E2A32"], [0, 0.6]), line=False)
    ribbon("hatch_frame", [(PI["x"] + PI["w"] - 4, HT["y1"]), (PI["x"] + PI["w"] - 4, HT["y0"] - 10), (x1p + 6, HT["y0"] - 10), (x1p + 6, HT["y1"])], 12, 0.385, iron)
    # 바닥(격자판) — 홀 지붕 윗면과 같은 높이
    poly("pod_floor", rect(x0p - 30, LY.ROOF_Y, x1p, y1p), 0.38, mat("pfloor", ["#3A3228", "#56483A"], [0, 0.5]))
    for k in range(10):
        xx = x0p + 20 + k * 48
        ribbon(f"grate{k}", [(xx, LY.ROOF_Y + 3), (xx + 20, LY.ROOF_Y + 3)], 3, 0.375, mat("grate", ["#1C1610"]), line=False)
    # 둥근 창(바깥 바다가 비친다) — 'window' 자리
    poly("port_rim", ellipse(3708, 960, 38, 38, 20), 0.39, mat("brass", ["#7A5A30", "#A07A40"], [0, 0.6]))
    poly("port_glass", ellipse(3708, 960, 28, 28, 20), 0.385, mat("pglass", ["#174450", "#24606A"], [0, 0.6]), line=False)
    ribbon("port_glint", [(3696, 947), (3712, 939)], 4, 0.38, mat("glint", ["#8AC4C4"]), line=False)
    # 벽 쪽지(B4) · 안쪽 문 옆
    for k, (nx, ny, rot) in enumerate([(3436, 950, 0.1), (3468, 968, -0.08), (3446, 992, 0.05)]):
        c, sn = math.cos(rot), math.sin(rot)
        pts = [(nx + px * c - py * sn, ny + px * sn + py * c) for px, py in [(-12, -14), (12, -14), (12, 14), (-12, 14)]]
        poly(f"note{k}", pts, 0.38, mat("paper", ["#C9B896"]), line=False)
    # 등불 하나(B1)
    ribbon("plamp_w", [(3650, PI["y"]), (3650, 900)], 4, 0.385, mat("wire", []), line=False)
    poly("plamp_hood", [(3628, 906), (3672, 906), (3660, 894), (3640, 894)], 0.38, mat("hood", []))
    poly("plamp", ellipse(3650, 914, 14, 10, 12), 0.375, mat("lampw", []))
    # 긴 의자 + 그 밑 상자
    wood = mat("bench", ["#5A3E26", "#7A5434"], [0, 0.55])
    poly("bench_seat", rect(3480, 1112, 3660, 1124), 0.37, wood)
    poly("bench_back", rect(3480, 1060, 3490, 1112), 0.372, wood)
    for xx in (3486, 3652):
        ribbon(f"bench_leg{xx}", [(xx, 1124), (xx, LY.ROOF_Y)], 8, 0.371, wood)
    crate = mat("crate", ["#6A4A2A", "#86603A"], [0, 0.6])
    poly("crate_a", rect(3556, 1128, 3616, LY.ROOF_Y), 0.373, crate)
    ribbon("crate_a_x", [(3556, 1128), (3616, LY.ROOF_Y)], 4, 0.372, mat("crx", ["#4A3220"]), line=False)
    # 창 아래 상자 + 화분(초록 — B2)
    poly("crate_b", rect(3742, 1104, 3786, LY.ROOF_Y), 0.373, crate)
    poly("pot", rect(3750, 1084, 3778, 1104), 0.372, mat("pot", ["#8A4A2A"]))
    for k in range(3):
        kelp(f"potplant{k}", 3756 + k * 9, 1086, 34 + k * 8, 0.371, km, 1200 + k, lean=0.2 * (k - 1), w=8)
    # 장비 걸이: 잠수복 둘 + 공기통 둘
    ribbon("rack_bar", [(3830, 934), (3934, 934)], 8, 0.38, iron)
    for xx in (3830, 3934):
        ribbon(f"rack_post{xx}", [(xx, 930), (xx, LY.ROOF_Y)], 8, 0.381, iron)
    suit = mat("suit", ["#4A4A2A", "#5E5E34", "#727040"], [0, 0.5, 0.85])
    brass = mat("brass", [])
    for k, sx_ in enumerate((3856, 3908)):
        ribbon(f"suit_hook{k}", [(sx_, 934), (sx_, 950)], 3, 0.378, mat("wire", []), line=False)
        poly(f"helmet{k}", ellipse(sx_, 972, 22, 22, 18), 0.376, brass)
        poly(f"visor{k}", ellipse(sx_ + 4, 974, 11, 10, 14), 0.374, mat("visor", ["#0E2A30"]), line=False)
        poly(f"suit{k}", [(sx_ - 20, 994), (sx_ + 20, 994), (sx_ + 24, 1060), (sx_ + 14, 1100), (sx_ - 14, 1100), (sx_ - 24, 1060)],
             0.377, suit, j=2, seed=1300 + k, step=14)
    tank = mat("tank2", ["#5A2E22", "#7A4030", "#94523A"], [0, 0.5, 0.85])
    for k, tx in enumerate((3958, 3982)):
        poly(f"airtank{k}", rect(tx - 11, 1090, tx + 11, LY.ROOF_Y - 2), 0.369, tank)
        poly(f"airtank_v{k}", rect(tx - 4, 1080, tx + 4, 1090), 0.368, brass)
    # 철골이 포드 오른벽을 뚫고 나가는 자리의 조임 고리
    poly("girder_collar", rect(x1p - 10, 912, x1p + 22, 976), 0.36, iron, j=2, seed=1400)
    # 바깥 발판 + 난간 + 사다리 + 받침 기둥(외벽에서)
    poly("platform", rect(PF["x0"], PF["y"], PF["x1"], PF["y"] + 14), 0.4, mat("pfloor", []))
    for xx in (PF["x0"] + 40, PF["x1"] - 10):
        ribbon(f"rail_post{xx}", [(xx, PF["y"]), (xx, PF["y"] - 70)], 6, 0.405, iron)
    ribbon("rail_top", [(PF["x0"] + 40, PF["y"] - 70), (PF["x1"] - 10, PF["y"] - 70)], 6, 0.405, iron)
    for xx in (LD["x"] - 18, LD["x"] + 18):
        ribbon(f"lad_side{xx}", [(xx, LD["y0"]), (xx, LD["y1"])], 6, 0.4, iron)
    yy = LD["y0"] + 20
    while yy < LD["y1"]:
        ribbon(f"lad_rung{yy}", [(LD["x"] - 18, yy), (LD["x"] + 18, yy)], 4, 0.401, iron, line=False); yy += 30
    for a, b in [((LY.TOWER_X1, 1330), (3760, y1p)), ((LY.TOWER_X1, 1520), (3990, y1p)), ((LY.TOWER_X1, 1330), (3990, y1p))]:
        ribbon(f"strut{a[1]}{b[0]}", [a, b], 14, 0.43, gm)
    for i, (x, h) in enumerate([(3470, 120), (3880, 170)]):     # 포드 밑 해초(B9)
        kelp(f"podkelp{i}", x, y1p, h, 0.41, km, 1500 + i, w=12, up=False)

    # 해치 두 상태(같은 자리, 같은 잘라 내기)
    cur["pass"] = "hatch_closed"
    door_m = mat("hdoor", ["#56382A", "#704A34", "#8A6040"], [0, 0.5, 0.85])
    hx0, hx1 = PI["x"] + PI["w"] - 2, x1p + 2
    poly("hd_c", rect(hx0, HT["y0"], hx1, HT["y1"]), 0.37, door_m)
    poly("hd_c_wheel", ellipse((hx0 + hx1) / 2, (HT["y0"] + HT["y1"]) / 2, 11, 11, 12), 0.36, brass)
    poly("hd_c_lamp", ellipse(x1p + 18, HT["y0"] - 26, 7, 7, 10), 0.36, mat("lampw", []))
    cur["pass"] = "hatch_open"
    poly("hd_o", [(hx1 - 2, HT["y1"] - 14), (hx1 + 152, HT["y1"] - 4), (hx1 + 152, HT["y1"] + 8), (hx1 - 2, HT["y1"])], 0.37, door_m)
    poly("hd_o_wheel", ellipse(hx1 + 76, HT["y1"] - 14, 9, 6, 12), 0.36, brass)
    ribbon("hd_o_chain", [(hx1 + 6, HT["y0"] - 4), (hx1 + 150, HT["y1"] - 8)], 3, 0.365, mat("cable2", []), line=False)
    poly("hd_o_lamp", ellipse(x1p + 18, HT["y0"] - 26, 7, 7, 10), 0.36, mat("lamp_g", ["#B8D890"]))

    # ── 손그림 선 ──
    sc.render.use_freestyle = True; sc.render.line_thickness = 1.0
    vl = sc.view_layers[0]; vl.use_freestyle = True
    fs = vl.freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("relic")
    ls.select_silhouette = ls.select_crease = ls.select_border = True
    fs.crease_angle = math.radians(152.0)
    ls.select_by_collection = True; ls.collection = noline; ls.collection_negation = 'EXCLUSIVE'
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("relic_ls")
    st_ = ls.linestyle
    st_.color = lin("#1C1712"); st_.thickness = 4.6
    mo = st_.thickness_modifiers.new(name="th_noise", type='NOISE'); mo.amplitude, mo.period, mo.seed = 2.6, 30, 3
    g1 = st_.geometry_modifiers.new(name="g_perlin", type='PERLIN_NOISE_2D'); g1.amplitude, g1.frequency, g1.octaves, g1.seed = 3.0, 2.0, 3, 7
    g2 = st_.geometry_modifiers.new(name="g_sin", type='SINUS_DISPLACEMENT'); g2.wavelength, g2.amplitude, g2.phase = 56.0, 1.5, 0.4

    # ── 카메라: 세계 전체 = 렌더 캔버스(1px = 세계 1px) ──
    bpy.ops.object.camera_add(location=(W / 2 / PPM, -100.0, -H / 2 / PPM))
    cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = W / PPM
    cam.rotation_euler = (math.radians(90), 0, 0); cam.data.clip_start, cam.data.clip_end = 0.1, 300.0
    sc.camera = cam
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    try:
        sc.eevee.taa_render_samples = 16
    except Exception:
        pass
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = 0.0

    only = [a for a in sys.argv[sys.argv.index("--") + 1:] if a in PASSES] if "--" in sys.argv else []
    for p in (only or PASSES):
        for q, objs in REG.items():
            for o in objs:
                o.hide_render = (q != p)
        sc.render.filepath = os.path.join(RAW, f"_pass_{p}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDER", p, sc.render.filepath, flush=True)


# ══════════════════════════════════════════════════════════════════════════════
#  2단계 — 합성(PIL)
# ══════════════════════════════════════════════════════════════════════════════
def _post():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageChops

    D = LY.build()
    rng = random.Random(1205)

    def hexrgb(h):
        h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def screen(base, top, strength=1.0):
        b = np.asarray(base).astype(np.float32) / 255; t = np.asarray(top).astype(np.float32) / 255
        a = t[..., 3:4] * strength; c = t[..., :3] * a
        out = 1 - (1 - b[..., :3]) * (1 - c)
        return Image.fromarray((np.clip(np.concatenate([out, b[..., 3:4]], -1), 0, 1) * 255).astype("uint8"), "RGBA")

    def depth_factor(y):
        """탑·절벽의 깊이 어둠(세계 y → 밝기 배수). 해구 문턱(2295) 아래로 급히 잠긴다"""
        return np.interp(y, [0, 1500, LY.TRENCH_Y, LY.DARK_FULL_Y, H], [1.0, 1.0, 0.62, 0.14, 0.06])

    def darken_by_depth(im, y0=0, strength=1.0):
        a = np.asarray(im).astype(np.float32)
        ys = np.arange(a.shape[0]) + y0
        f = 1 - (1 - depth_factor(ys)) * strength
        a[..., :3] *= f[:, None, None]
        return Image.fromarray(np.clip(a, 0, 255).astype("uint8"), "RGBA")

    def crop_save(im, name, pad=2, quant=True, colors=256):
        bb = im.getchannel("A").point(lambda v: 255 if v > 3 else 0).getbbox()
        x0, y0, x1, y1 = bb
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad); x1, y1 = min(im.width, x1 + pad), min(im.height, y1 + pad)
        c = im.crop((x0, y0, x1, y1))
        c.save(os.path.join(RAW, name.replace(".png", "_rgba.png")))
        out = c.quantize(colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE) if quant else c
        out.save(os.path.join(DST, name), optimize=True)
        return dict(file=name, x=x0, y=y0, w=x1 - x0, h=y1 - y0)

    def load(p):
        return Image.open(os.path.join(RAW, f"_pass_{p}.png")).convert("RGBA")

    layers = []

    # ── 1. 뒤 바다(불투명, JPG, 절반 해상도 → 화면에서 ×2) ──
    HW_, HH_ = W // 2, H // 2
    stops = [(0, "#2E7E90"), (700, "#1B5A68"), (1300, "#0F3843"), (1900, "#0A2630"), (2400, "#05141A"),
             (3000, "#010608"), (H, "#000204")]
    ys = np.arange(HH_) * 2.0
    col = np.stack([np.interp(ys, [s[0] for s in stops], [hexrgb(s[1])[c] for s in stops]) for c in range(3)], -1)
    bg = np.repeat(col[:, None, :], HW_, axis=1)
    xx = (np.arange(HW_) * 2.0)[None, :]; yy = ys[:, None]
    dark = np.clip((xx - 3400) / 1800, 0, 1) * np.clip((yy - 1300) / 1300, 0, 1)      # 오른쪽 아래 = 해구
    bg *= (1 - 0.7 * dark)[..., None]
    back = Image.fromarray(bg.astype("uint8"), "RGB").convert("RGBA")

    def lay():
        return Image.new("RGBA", (HW_, HH_), (0, 0, 0, 0))

    def far(polys, rgb, blur, alpha=255):
        L = lay(); d = ImageDraw.Draw(L)
        for pts in polys:
            d.polygon([(x / 2, y / 2) for x, y in pts], fill=(*rgb, alpha))
        return L.filter(ImageFilter.GaussianBlur(blur))

    # 먼 실루엣: 절벽 뒤로 더 높이 솟은 먼 바위(절벽이 큰 산의 끝자락임을 말한다), 해구 건너편의 먼 벽.
    # 3막 가드 — 사람이 지은 실루엣(스카이라인·사각 기둥) 없음. 바위만.
    def jagpts(pts, amp, step, seed):
        r = random.Random(seed); out = []
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]; n = max(1, int(math.dist(pts[i], pts[i + 1]) / step))
            for k in range(n):
                t = k / n; out.append((x0 + (x1 - x0) * t + r.uniform(-amp, amp), y0 + (y1 - y0) * t + r.uniform(-amp, amp)))
        return out + [pts[-1]]
    # 절벽 뒤로 더 높이 솟은 먼 산줄기(절벽이 큰 바위산의 끝자락) — 바닥까지 이어져 물빛에 녹는다
    back = Image.alpha_composite(back, far([jagpts([(-20, 180), (260, 90), (520, 170), (760, 300), (980, 420), (1250, 640),
                                                    (1450, 1000), (1560, 1500), (1620, 2300), (1700, H + 20), (-20, H + 20)], 40, 70, 5)],
                                           (22, 62, 70), 18, 150))
    # 해구 건너편의 먼 벽(오른쪽 끝) — 바위 결, 아주 흐리게
    back = Image.alpha_composite(back, far([jagpts([(5640, 1050), (5450, 1200), (5300, 1420), (5220, 1800), (5150, 2300), (5080, 2900),
                                                    (5040, H + 20), (5640, H + 20)], 50, 60, 6)], (12, 34, 40), 22, 150))
    # 깊이 어둠: 먼 실루엣까지 해구 쪽으로 잠근다(바닥이 가장 어둡다)
    ba = np.asarray(back).astype(np.float32)
    ba[..., :3] *= np.interp(ys, [0, 1900, LY.TRENCH_Y, LY.DARK_FULL_Y, H], [1, 1, 0.8, 0.38, 0.22])[:, None, None]
    back = Image.fromarray(ba.astype("uint8"), "RGBA")
    # 빛기둥
    L = lay(); d = ImageDraw.Draw(L)
    for i in range(8):
        x0 = rng.uniform(0.04, 0.96) * HW_; w0 = rng.uniform(30, 90); dx = rng.uniform(-200, 80); h = rng.uniform(0.45, 0.8) * HH_
        d.polygon([(x0 - w0, -10), (x0 + w0, -10), (x0 + dx + w0 * 1.9, h), (x0 + dx - w0 * 1.9, h)], fill=(120, 200, 205, int(rng.uniform(22, 42))))
    L = L.filter(ImageFilter.GaussianBlur(26))
    fade = Image.linear_gradient("L").resize((HW_, HH_)).point(lambda v: 255 - v)
    L.putalpha(ImageChops.multiply(L.getchannel("A"), fade))
    back = screen(back, L)
    # 등불 번짐(돔·유인 등불) — 빛은 바다에 번진다(가우스 감쇠). 등불 자체는 탑 레이어에 있다
    dg = LY.DOME_GLASS
    yy2, xx2 = np.mgrid[0:HH_, 0:HW_] * 2.0
    def glow(cx, cy, rx, ry, a):
        g = np.exp(-(((xx2 - cx) / rx) ** 2 + ((yy2 - cy) / ry) ** 2)) * a
        return Image.fromarray(np.dstack([np.full_like(g, 255), np.full_like(g, 170), np.full_like(g, 80), g * 255]).astype("uint8"), "RGBA")
    back = screen(back, glow(dg["cx"], dg["base_y"] - 300, 1100, 600, 0.30))
    back = screen(back, glow(LY.LURE["x"], LY.LURE["y"], 200, 200, 0.32))
    # 바다눈(아주 작은 흰 점) — 위쪽이 많고 아래로 갈수록 드물다
    L = lay(); d = ImageDraw.Draw(L)
    for i in range(1400):
        x = rng.uniform(0, HW_); y = HH_ * rng.random() ** 1.6; r = rng.choice([0.6, 0.8, 1.0, 1.3])
        d.ellipse([x - r, y - r, x + r, y + r], fill=(190, 225, 220, int(rng.uniform(40, 110) * (1 - y / HH_ * 0.7))))
    back = Image.alpha_composite(back, L)
    back = back.convert("RGB")
    back.save(os.path.join(DST, "back.jpg"), quality=86, optimize=True, progressive=True)
    layers.append(dict(id="back", file="back.jpg", x=0, y=0, w=HW_, h=HH_, scale=2, smooth=True, z=0,
                       note="불투명 바다. 절반 해상도 — ×2 로 매끈 확대. 돔·유인 등불 번짐이 구워져 있다"))

    # ── 2. 절벽(mid) ──
    cliff = darken_by_depth(load("cliff"), strength=0.75)
    info = crop_save(cliff, "cliff.png"); info.update(id="cliff", scale=1, z=30,
                                                     note="절벽 바위. 탑 껍데기 **위**에 그린다(절벽이 탑의 왼쪽 외벽을 감싼다). 바위 칸 홈·통로·통로 등 포함")
    # ── 3. 탑 껍데기 = 유리(반투명, 안쪽 따뜻함) + 탑 ──
    glass = load("glass"); ga = np.asarray(glass).astype(np.float32)
    # 유리 안쪽에 홀 등불 온기
    h_, w_ = ga.shape[:2]
    yy_, xx_ = np.mgrid[0:h_, 0:w_]
    hl = np.exp(-(((xx_ - dg["cx"]) / 900.0) ** 2 + ((yy_ - (LY.DOME["y"] + 120)) / 420.0) ** 2))
    ga[..., 0] = ga[..., 0] * (1 - 0.5 * hl) + 230 * 0.5 * hl
    ga[..., 1] = ga[..., 1] * (1 - 0.45 * hl) + 170 * 0.45 * hl
    ga[..., 2] = ga[..., 2] * (1 - 0.4 * hl) + 90 * 0.4 * hl
    ga[..., 3] *= 0.42
    glass = Image.fromarray(ga.astype("uint8"), "RGBA")
    tower = Image.alpha_composite(glass, load("tower"))
    tower = darken_by_depth(tower)
    # 맨 아래는 어둠 속으로 녹는다(알파도 줄여 배경 검정과 이어지게)
    ta = np.asarray(tower).astype(np.float32)
    ys_ = np.arange(H)
    ta[..., 3] *= np.interp(ys_, [0, LY.DARK_FULL_Y, H], [1, 1, 0.35])[:, None]
    tower = Image.fromarray(ta.astype("uint8"), "RGBA")
    tinfo = crop_save(tower, "tower_shell.png"); tinfo.update(id="tower_shell", scale=1, z=20,
                                                              note="탑 껍데기: 외벽 창 격자·기둥·슬래브·빈 칸 속(폐허)·지붕·돔 골조와 유리·홀 등·안테나·물탱크·철골·유인 등불. 방 안은 없다(플레이트가 덮는다)")
    # ── 4. 승강로 + 승강기 칸 ──
    sh = D["shafts"][0]
    shaft = darken_by_depth(load("shaft"), strength=0.8)
    sinfo = crop_save(shaft, "elevator_shaft.png", pad=SHAFT_SPR_PAD)
    sinfo.update(id="elevator_shaft", scale=1, z=25, place=[dict(shaft=s["id"], x=sinfo["x"] + (s["x"] - sh["x"]), y=sinfo["y"]) for s in D["shafts"]],
                 note="승강로 하나의 그림. A·B 두 자리에 같은 그림을 놓는다(place). 정류장 문틀·등 포함")
    car = load("car"); cx0, cy0, cx1, cy1 = CAR_RECT
    cbox = (cx0 - 6, cy0 - 12, cx1 + 6, cy1 + 6)
    carimg = car.crop(cbox)
    carimg.save(os.path.join(DST, "elevator_car.png"), optimize=True)
    car_info = dict(id="elevator_car", file="elevator_car.png", w=carimg.width, h=carimg.height,
                    anchor=[(cx0 + cx1) / 2 - cbox[0], cy1 - cbox[1]],
                    note="anchor(아래 가운데) 를 (승강로 x_center, 현재 바닥 y) 에 맞춘다. 사람은 칸 뒤판 위·앞 격자 아래에 그린다(칸 안 앞쪽은 비어 있다)")
    # ── 5. 앞 해초 ──
    front = load("front")
    finfo = crop_save(front, "front.png"); finfo.update(id="front", scale=1, z=90, parallax=1.12,
                                                       note="맨 앞 해초·바위 실루엣. 사람·방 위에 그린다. 카메라보다 조금 빨리 움직이면(1.1~1.15) 깊이가 산다")

    # ── 6. 칸 오버레이 ──
    CW, CH = LY.CELL_W, LY.CELL_H
    plan = Image.new("RGBA", (CW, CH), (0, 0, 0, 0)); d = ImageDraw.Draw(plan)
    d.rectangle([0, 0, CW - 1, CH - 1], fill=(4, 10, 12, 70))
    chalk = (206, 218, 206, 175)
    def dashed(x0, y0, x1, y1, dash=22, gap=14, w=4):
        L_ = math.dist((x0, y0), (x1, y1)); n = int(L_ // (dash + gap)) + 1
        for i in range(n):
            t0 = i * (dash + gap) / L_; t1 = min(1, (i * (dash + gap) + dash) / L_)
            if t0 >= 1: break
            jx = random.uniform(-1.2, 1.2)
            d.line([(x0 + (x1 - x0) * t0 + jx, y0 + (y1 - y0) * t0 + jx), (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)], fill=chalk, width=w)
    random.seed(3)
    m_ = 16
    dashed(m_, m_, CW - m_, m_); dashed(CW - m_, m_, CW - m_, CH - m_); dashed(CW - m_, CH - m_, m_, CH - m_); dashed(m_, CH - m_, m_, m_)
    cxp, cyp = CW // 2, CH // 2 - 6
    d.line([(cxp - 34, cyp), (cxp + 34, cyp)], fill=chalk, width=6); d.line([(cxp, cyp - 34), (cxp, cyp + 34)], fill=chalk, width=6)
    plan.save(os.path.join(DST, "cell_plan.png"), optimize=True)
    fl = Image.open(os.path.join(ART, "plates", "room_flood.png")).convert("RGBA").crop((54, 33, 618, 350))
    fa = np.asarray(fl).astype(np.float32)
    frame = fa[..., 3] < 10                         # 플레이트 테 부분: 물빛으로 식힌다
    fa[frame] = [8, 34, 40, 120]
    flood = Image.fromarray(fa.astype("uint8"), "RGBA")
    flood.save(os.path.join(DST, "cell_flood.png"), optimize=True)
    overlays = [dict(id="cell_plan", file="cell_plan.png", w=CW, h=CH,
                     note="아직 안 지은 칸: 칸 사각형에 그대로. 뒤의 폐허(탑 껍데기)가 비친다"),
                dict(id="cell_flood", file="cell_flood.png", w=CW, h=CH, water_top_in_cell=[118, 128],
                     note="물 찬 칸: 플레이트(어두운 판 권장) 위에. 물 빼는 중이면 아래쪽 일부만 그린다(수면을 y 로 내리며 clip). 테 부분은 물빛으로 식힌다")]


    # ── 6.5 S12-F 입구(에어락 포드) ──
    ent = darken_by_depth(load("ent_back"), strength=0.6)
    ea = np.asarray(ent).astype(np.float32); hh, ww = ea.shape[:2]
    gy, gx = np.mgrid[0:hh, 0:ww]
    inside = (gx > LY.POD_IN["x"]) & (gx < LY.POD_IN["x"] + LY.POD_IN["w"]) & (gy > LY.POD_IN["y"]) & (gy < LY.ROOF_Y + 4)
    gl = np.exp(-(((gx - 3650) / 330.0) ** 2 + ((gy - 960) / 220.0) ** 2)) * inside      # 포드 등불 온기(방 안 등불보다 약하게)
    for c, v in enumerate((255, 176, 92)):
        ea[..., c] = ea[..., c] + (v - ea[..., c]) * gl * 0.32
    ent = Image.fromarray(np.clip(ea, 0, 255).astype("uint8"), "RGBA")
    einfo = crop_save(ent, "entrance.png"); einfo.update(id="entrance", scale=1, z=26,
        note="에어락 포드(대기 공간·장비 걸이·긴 의자·등·둥근 창·바깥 발판·사다리·받침). 탑 껍데기 위, 사람 아래")
    hc, ho = load("hatch_closed"), load("hatch_open")
    bb1 = hc.getchannel("A").getbbox(); bb2 = ho.getchannel("A").getbbox()
    hb = (min(bb1[0], bb2[0]) - 2, min(bb1[1], bb2[1]) - 2, max(bb1[2], bb2[2]) + 2, max(bb1[3], bb2[3]) + 2)
    hc.crop(hb).save(os.path.join(DST, "hatch_closed.png"), optimize=True)
    ho.crop(hb).save(os.path.join(DST, "hatch_open.png"), optimize=True)
    hatch_info = dict(id="hatch", files={"closed": "hatch_closed.png", "open": "hatch_open.png"}, x=hb[0], y=hb[1],
                      w=hb[2] - hb[0], h=hb[3] - hb[1], z=27,
                      note="같은 자리(x,y)에 둘 중 하나. 사람이 해치를 지날 때 open 으로 바꾸고 물방울을 띄운다. 닫힘 = 따뜻한 등, 열림 = 옅은 초록 등")
    # 물방울 기둥(3프레임, 해치 앞에서 위로)
    BW, BH, NF = 90, 300, 3
    bub = Image.new("RGBA", (BW * NF, BH), (0, 0, 0, 0)); db = ImageDraw.Draw(bub); rb = random.Random(77)
    seeds = [(rb.uniform(20, 70), rb.uniform(0, BH), rb.uniform(3, 9)) for _ in range(26)]
    for f in range(NF):
        for (bx, by, br) in seeds:
            y = (by - f * BH / NF) % BH; x = bx + math.sin(y * 0.05 + br) * 8
            a = int(200 * min(1, y / 60) * min(1, (BH - y) / 40 + 0.2))
            db.ellipse([f * BW + x - br, y - br, f * BW + x + br, y + br], outline=(170, 225, 225, a), width=2)
            db.ellipse([f * BW + x - br * 0.4 - 1, y - br * 0.5 - 1, f * BW + x - br * 0.4 + 1, y - br * 0.5 + 1], fill=(220, 245, 240, a))
    bub.save(os.path.join(DST, "bubbles.png"), optimize=True)
    bubbles_info = dict(id="bubbles", file="bubbles.png", frame_w=BW, frame_h=BH, frames=NF, fps=6,
                        anchor=[BW // 2, BH], place=[LY.HATCH["x"] + 30, LY.ROOF_Y - 20],
                        note="anchor(아래 가운데)를 place 에. 해치가 열릴 때 1.5~2초 돌리고 끈다. 사다리 아래(4010,1460)에서 헤엄쳐 나갈 때도 쓸 수 있다")

    # ── 7. 생물 아틀라스 ──
    sprites = {}

    def blank(w, h):
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def fish_poly(d, x, y, ang, s, rgb, a):
        c, sn = math.cos(ang), math.sin(ang)
        R = lambda px, py: (x + px * c - py * sn, y + px * sn + py * c)
        d.polygon([R(s, 0), R(s * 0.3, -s * 0.38), R(-s * 0.6, -s * 0.2), R(-s, -s * 0.45), R(-s * 0.85, 0),
                   R(-s, s * 0.45), R(-s * 0.6, s * 0.2), R(s * 0.3, s * 0.38)], fill=(*rgb, a))

    def shoal(w, h, n, size, rgb, a, seed):
        im = blank(w, h); d = ImageDraw.Draw(im); r = random.Random(seed)
        for i in range(n):
            t = r.random(); x = 30 + t * (w - 60); y = h / 2 + math.sin(t * 3.1) * h * 0.18 + r.gauss(0, h * 0.14)
            fish_poly(d, x, y, r.uniform(-0.12, 0.12), size * r.uniform(0.7, 1.2), rgb, a)
        return im.filter(ImageFilter.GaussianBlur(0.6))

    sprites["shoal_silver"] = (shoal(760, 260, 120, 18, (160, 212, 210), 175, 1), "오른쪽으로 헤엄(좌우 반전하면 왼쪽). 위쪽 밝은 물")
    sprites["shoal_far"] = (shoal(520, 180, 60, 12, (110, 168, 172), 120, 2), "멀리 흐린 떼. 0.3~0.5배 시차")
    sprites["shoal_dark"] = (shoal(560, 210, 70, 15, (14, 26, 30), 215, 3), "깊은 물의 검은 떼(빛이 아니라 그림자)")
    for i, (s, rgb) in enumerate([(18, (170, 220, 214)), (24, (150, 200, 196)), (14, (200, 190, 140))]):
        im = blank(int(s * 2.4), int(s * 1.4)); fish_poly(ImageDraw.Draw(im), s * 1.2, s * 0.7, 0, s, rgb, 230)
        sprites[f"fish_{i}"] = (im, "낱마리. 떼에서 빠져나와 따로 움직이는 몇 마리용")

    def jelly(r, rgb=(140, 230, 225)):
        w_, h_ = int(r * 4), int(r * 5.2); im = blank(w_, h_); d = ImageDraw.Draw(im)
        x, y = w_ / 2, r * 1.6
        d.pieslice([x - r, y - r, x + r, y + r], 180, 360, fill=(*rgb, 130))
        d.arc([x - r, y - r, x + r, y + r], 180, 360, fill=(*rgb, 210), width=2)
        for k in range(5):
            tx = x - r * 0.7 + k * r * 0.35
            d.line([(tx, y), (tx + math.sin(k) * r * 0.25, y + r * 1.4), (tx - r * 0.15, y + r * 2.6)], fill=(*rgb, 80), width=2)
        glow = im.filter(ImageFilter.GaussianBlur(r * 0.5))
        out = screen(Image.new("RGBA", im.size, (0, 0, 0, 0)), glow)
        out = Image.alpha_composite(glow, im)
        return out

    sprites["jelly_a"] = (jelly(34), "천천히 위아래로(주기 4~6초). 깊은 쪽에 2~4개")
    sprites["jelly_b"] = (jelly(22), "작은 해파리")

    def leviathan(length=2000, alpha=0.78):
        hgt = int(length * 0.32); im = blank(length + 40, hgt); d = ImageDraw.Draw(im)
        cx_, cy_ = im.width / 2, hgt / 2; wr = (5, 16, 20); facing = -1
        top, bot = [], []
        for i in range(41):
            t = i / 40; x = cx_ + facing * (t - 0.5) * length
            th = math.sin(math.pi * min(1, t * 1.15) ** 0.8) * length * 0.075 * (1 - 0.6 * t)
            yc = cy_ + math.sin(t * 3.0) * length * 0.02
            top.append((x, yc - th)); bot.append((x, yc + th * 0.85))
        A = int(255 * alpha)
        d.polygon(top + bot[::-1], fill=(*wr, A))
        tx = cx_ - facing * 0.5 * length; tyc = cy_ + math.sin(3.0) * length * 0.02
        d.polygon([(tx + facing * length * 0.04, tyc), (tx - facing * length * 0.09, tyc - length * 0.09),
                   (tx - facing * length * 0.05, tyc), (tx - facing * length * 0.09, tyc + length * 0.07)], fill=(*wr, A))
        fx_ = cx_ + facing * length * 0.12
        d.polygon([(fx_, cy_ + length * 0.03), (fx_ - facing * length * 0.14, cy_ + length * 0.13),
                   (fx_ - facing * length * 0.04, cy_ + length * 0.04)], fill=(*wr, A))
        return im.filter(ImageFilter.GaussianBlur(3))

    lev = leviathan(1800)
    sprites["leviathan"] = (lev, "왼쪽을 보고 있다. 아주 천천히(초당 10~20px) 심연 위쪽을 가로지른다. 얼굴 없음")

    def inkblot(w, h, seed, eye_gap, eye_r, body):
        """먹 얼룩 생물: 검은 실루엣 + 튀긴 가장자리 + 창백한 눈 두 점 (S11-C 에서 옮겨 온 것)"""
        r = random.Random(seed)
        m = Image.new("L", (w, h), 0); d = ImageDraw.Draw(m)
        for (cx_, cy_, rx, ry) in body(w, h):
            d.ellipse([cx_ - rx, cy_ - ry, cx_ + rx, cy_ + ry], fill=255)
        # 늘어진 촉수/다리 몇 가닥
        for k in range(r.randint(4, 7)):
            x = w * r.uniform(0.25, 0.75); y = h * 0.55; pts = [(x, y)]
            for j in range(6):
                x += r.uniform(-w * 0.04, w * 0.04); y += h * r.uniform(0.04, 0.07); pts.append((x, y))
            d.line(pts, fill=255, width=max(3, int(w * 0.022 * (1 - k * 0.08))))
        # 가장자리를 번지게: 블러 + 노이즈 임계
        mb = m.filter(ImageFilter.GaussianBlur(w * 0.012))
        a = np.asarray(mb).astype(np.float32) / 255
        noise = np.asarray(Image.effect_noise((w, h), 80).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
        a = np.clip((a + (noise - 0.5) * 0.55 - 0.42) * 5.0, 0, 1)
        # 튀긴 점(가장자리 밖으로)
        sp = Image.new("L", (w, h), 0); ds = ImageDraw.Draw(sp)
        edge = np.argwhere((a > 0.4) & (a < 0.9))
        for _ in range(int(w * 0.35)):
            if len(edge) == 0: break
            yy0, xx0 = edge[r.randrange(len(edge))]
            ang = r.uniform(0, 6.28); dist = r.uniform(w * 0.01, w * 0.07); rad = r.uniform(1, w * 0.012)
            px, py = xx0 + math.cos(ang) * dist, yy0 + math.sin(ang) * dist
            ds.ellipse([px - rad, py - rad, px + rad, py + rad], fill=255)
        a = np.maximum(a, np.asarray(sp).astype(np.float32) / 255 * 0.9)
        rgba = np.zeros((h, w, 4), np.float32); rgba[..., :3] = (4, 7, 9); rgba[..., 3] = a * 245
        im = Image.fromarray(rgba.astype("uint8"), "RGBA"); d2 = ImageDraw.Draw(im)
        ex, ey = w * 0.5 + r.uniform(-w * 0.06, w * 0.06), h * 0.36
        for sx_ in (-eye_gap / 2, eye_gap / 2):
            d2.ellipse([ex + sx_ - eye_r, ey - eye_r, ex + sx_ + eye_r, ey + eye_r], fill=(222, 236, 220, 255))
        return im

    sprites["ink_a"] = (inkblot(460, 380, 11, 46, 8, lambda w, h: [(w * .5, h * .38, w * .28, h * .26), (w * .36, h * .48, w * .16, h * .14), (w * .64, h * .46, w * .17, h * .15)]),
                        "먹 얼룩 생물(중간). 심연에서 천천히 떠오르고 가라앉는다. 눈만 깜빡이게(알파 0↔1) 해도 산다")
    sprites["ink_b"] = (inkblot(300, 240, 12, 30, 6, lambda w, h: [(w * .5, h * .4, w * .3, h * .25), (w * .42, h * .32, w * .14, h * .18)]),
                        "먹 얼룩 생물(작은)")
    sprites["ink_c"] = (inkblot(720, 520, 13, 70, 11, lambda w, h: [(w * .5, h * .36, w * .33, h * .24), (w * .28, h * .44, w * .16, h * .16), (w * .72, h * .42, w * .18, h * .17), (w * .5, h * .5, w * .22, h * .14)]),
                        "먹 얼룩 생물(큰) — 해구 문턱 아래 어둠에서. 몸 절반은 화면 밖이어도 좋다")
    ey = blank(64, 24); de = ImageDraw.Draw(ey)
    for x in (18, 46):
        de.ellipse([x - 7, 5, x + 7, 19], fill=(200, 240, 220, 235))
    eglow = ey.filter(ImageFilter.GaussianBlur(5)); sprites["eyes"] = (Image.alpha_composite(eglow, ey), "어둠 속 눈 두 점 — 몸은 안 보인다. 먼 위협의 첫 신호")

    # 선반 채우기로 아틀라스
    order = sorted(sprites.items(), key=lambda kv: -kv[1][0].height)
    AW = 2048; x = y = rowh = 0; frames = {}
    for name, (im, note) in order:
        if x + im.width > AW:
            x = 0; y += rowh + 4; rowh = 0
        frames[name] = dict(x=x, y=y, w=im.width, h=im.height, note=note); x += im.width + 4; rowh = max(rowh, im.height)
    atlas = Image.new("RGBA", (AW, y + rowh), (0, 0, 0, 0))
    for name, (im, note) in sprites.items():
        f = frames[name]; atlas.paste(im, (f["x"], f["y"]))
    atlas.save(os.path.join(RAW, "creatures_rgba.png"))
    atlas.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(os.path.join(DST, "creatures.png"), optimize=True)
    # 처음 놓을 자리(세계 px, 스프라이트 가운데) — 개발이 여기서부터 떠다니게 한다
    spawn = [
        dict(s="shoal_silver", x=4300, y=560, drift=[1, 0], speed=22, z=10),
        dict(s="shoal_far", x=2400, y=420, drift=[-1, 0], speed=10, z=5, alpha=0.7),
        dict(s="shoal_silver", x=5000, y=1050, drift=[-1, 0], speed=18, z=10, flip=True, alpha=0.8),
        dict(s="shoal_dark", x=4150, y=1700, drift=[1, 0], speed=14, z=10),
        dict(s="leviathan", x=4500, y=1780, drift=[-1, 0], speed=12, z=8, alpha=0.9),
        dict(s="jelly_a", x=4050, y=1700, bob=[0, 30], period=5, z=12),
        dict(s="jelly_b", x=4700, y=2050, bob=[0, 24], period=4.2, z=12),
        dict(s="jelly_a", x=5250, y=1500, bob=[0, 30], period=6, z=12),
        dict(s="jelly_b", x=3800, y=2350, bob=[0, 20], period=4.8, z=12),
        dict(s="ink_a", x=4950, y=2300, bob=[0, 40], period=9, z=14),
        dict(s="ink_c", x=4100, y=2950, bob=[0, 50], period=12, z=14),
        dict(s="ink_b", x=1500, y=2900, bob=[0, 30], period=8, z=14, note="절벽 밑 허공(왼쪽 아래)"),
        dict(s="eyes", x=5300, y=2700, blink=True, z=15),
        dict(s="eyes", x=3900, y=3150, blink=True, z=15),
        dict(s="fish_0", x=3700, y=900, drift=[1, 0], speed=40, z=16),
        dict(s="fish_1", x=1200, y=470, drift=[-1, 0], speed=30, z=16),
        dict(s="fish_2", x=2100, y=650, drift=[1, 0], speed=35, z=16),
    ]
    creatures = dict(file="creatures.png", frames=frames, spawn=spawn,
                     note="생물은 정지 그림이 아니라 개발이 띄운다. z: 탑 껍데기(20)보다 작으면 탑 뒤, 크면 앞. 위협 실루엣(threats/)은 따로")

    # ── 8. layout.json 갱신 ──
    layers_all = [layers[0], info, tinfo, sinfo, einfo, finfo]
    lay_path = LY.OUT
    J = json.load(open(lay_path, encoding="utf-8"))
    J["layers"] = {"_note": "x,y = 세계 px 좌상단. scale 2 는 ×2 매끈 확대. draw_order 순서대로 그린다",
                   "draw_order": ["back", "creatures(z<20)", "tower_shell", "elevator_shaft(A,B)", "entrance", "hatch", "cliff",
                                  "plates(cells, rock_cells)", "overlays(cell_plan/cell_flood)", "elevator_car", "residents",
                                  "bubbles", "creatures(z>20)", "front"],
                   "files": layers_all, "car": car_info, "overlays": overlays, "creatures": creatures,
                   "hatch": hatch_info, "bubbles": bubbles_info}
    json.dump(J, open(lay_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("layers written")
    tot = 0
    for f in sorted(os.listdir(DST)):
        s = os.path.getsize(os.path.join(DST, f)); tot += s; print(f"{f:28s} {s/1024:8.1f} KB")
    print("TOTAL", round(tot / 1024 / 1024, 2), "MB")


# ══════════════════════════════════════════════════════════════════════════════
#  3단계 — 미리보기: layout.json + 레이어 + 플레이트만으로 다시 짠다(계약 증명)
# ══════════════════════════════════════════════════════════════════════════════
def _preview():
    import numpy as np
    from PIL import Image, ImageDraw
    J = json.load(open(LY.OUT, encoding="utf-8"))
    Ls = J["layers"]; files = {f["id"]: f for f in Ls["files"]}

    def img(name):
        return Image.open(os.path.join(DST, name)).convert("RGBA")

    canvas = Image.new("RGBA", (J["world"]["w"], J["world"]["h"]), (0, 0, 0, 255))
    b = files["back"]; bi = img(b["file"]).resize((b["w"] * b["scale"], b["h"] * b["scale"]), Image.BILINEAR)
    canvas.alpha_composite(bi, (b["x"], b["y"]))
    atlas = img(Ls["creatures"]["file"]); fr = Ls["creatures"]["frames"]

    def put_creatures(zmin, zmax):
        for s in Ls["creatures"]["spawn"]:
            if not (zmin <= s["z"] < zmax):
                continue
            f = fr[s["s"]]; sp = atlas.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]))
            if s.get("flip"):
                sp = sp.transpose(Image.FLIP_LEFT_RIGHT)
            if s.get("alpha"):
                a = sp.getchannel("A").point(lambda v, k=s["alpha"]: int(v * k)); sp.putalpha(a)
            canvas.alpha_composite(sp, (int(s["x"] - f["w"] / 2), int(s["y"] - f["h"] / 2)))

    def put(id_):
        f = files[id_]; canvas.alpha_composite(img(f["file"]), (f["x"], f["y"]))

    put_creatures(0, 20)
    put("tower_shell")
    sh = files["elevator_shaft"]; shi = img(sh["file"])
    for p in sh["place"]:
        canvas.alpha_composite(shi, (p["x"], p["y"]))
    put("entrance")
    hz = Ls["hatch"]; canvas.alpha_composite(img(hz["files"]["open"]), (hz["x"], hz["y"]))
    put("cliff")
    # 칸: 예시 상태
    PL = os.path.join(ART, "plates"); src = tuple(J["plates"]["src_rect"])
    crop = (src[0], src[1], src[0] + src[2], src[1] + src[3])

    def plate(kind, st):
        return Image.open(os.path.join(PL, f"room_plate_{kind}_{'lit' if st == 'lit' else 'dark'}.png")).convert("RGBA").crop(crop)
    plan = img("cell_plan.png"); flood = img("cell_flood.png")
    states = ["quarters:lit", "infirmary:lit", "workshop:lit",
              "storage:lit", "quarters:lit", "power:lit",
              "workshop:lit", "storage:pump", "quarters:flood",
              "storage:flood", "plan", "workshop:flood",
              "plan", "storage:dark", "plan"]
    rock_states = ["plan", "greenhouse:lit", "plan"]
    cells = J["cells"] + J["rock_cells"]
    allst = states + rock_states
    dfac = lambda y: float(np.interp(y, [0, 1500, J["depth"]["trench_y"], J["depth"]["dark_full_y"]], [1, 1, 0.8, 0.5]))
    for c, st in zip(cells, allst):
        if st == "plan":
            canvas.alpha_composite(plan, (c["x"], c["y"])); continue
        k, s = st.split(":")
        im = plate(k, "lit" if s in ("lit", "pump") else "dark")
        if s in ("flood", "dark", "pump") or c["y"] > 2000:
            a = np.asarray(im).astype(np.float32); f = dfac(c["y"]) * (0.8 if s == "dark" else 1.0)
            a[..., :3] *= f; im = Image.fromarray(a.astype("uint8"), "RGBA")
        canvas.alpha_composite(im, (c["x"], c["y"]))
        if s == "flood":
            canvas.alpha_composite(flood, (c["x"], c["y"]))
        if s == "pump":                    # 수면을 내려 아래 1/3 만 그린다
            top = Ls["overlays"][1]["water_top_in_cell"][0] - 8          # 수면 줄부터 잘라
            new_top = int(c["h"] * 0.62)                                   # 칸 아래 1/3 높이로 내린다
            part = flood.crop((0, top, flood.width, top + (c["h"] - new_top)))
            canvas.alpha_composite(part, (c["x"], c["y"] + new_top))
    # 승강기 칸 둘(A 는 층 1 정류장, B 는 이동 중)
    car = Ls["car"]; ci = img(car["file"])
    for shaft, y in [(J["shafts"][0], J["tower"]["storeys"][1]["floor_y"]), (J["shafts"][1], J["tower"]["storeys"][0]["floor_y"] + 170)]:
        canvas.alpha_composite(ci, (int(shaft["x_center"] - car["anchor"][0]), int(y - car["anchor"][1])))
    # 주민(P2 ×3, NEAREST, 발 = floor_y)
    rows = {"idle": 0, "walk": 1, "work": 2, "sit": 3, "carry": 4}
    sheets = {}

    def person(role, pose, fx, fy, fr=0):
        if role not in sheets:
            sheets[role] = Image.open(os.path.join(ART, "chars", "front", "p2", "src", f"{role}.png")).convert("RGBA")
        cimg = sheets[role].crop((fr * 64, rows[pose] * 64, fr * 64 + 64, rows[pose] * 64 + 64)).resize((192, 192), Image.NEAREST)
        d = ImageDraw.Draw(canvas, "RGBA"); d.ellipse([fx - 33, fy - 6, fx + 33, fy + 6], fill=(20, 12, 6, 120))
        canvas.alpha_composite(cimg, (int(fx - 96), int(fy - 180)))
    people = {0: [("cook", 0, "idle"), ("kid", 1, "sit")], 1: [("medic", 0, "work")], 2: [("engineer", 0, "work"), ("trader", 1, "idle")],
              3: [("trader", 0, "carry")], 4: [("scholar", 0, "sit"), ("scout", 1, "idle")], 5: [("engineer", 1, "work")],
              6: [("engineer", 0, "work"), ("kid", 1, "idle")], 7: [("scout", 0, "work")]}
    for ci_, lst in people.items():
        c = J["cells"][ci_]
        for role, si, pose in lst:
            person(role, pose, c["stand_x"][si], c["floor_y"], (ci_ + si) % 2)
    rc = J["rock_cells"][1]
    person("farmer", "work", rc["stand_x"][0], rc["floor_y"]); person("kid", "idle", rc["stand_x"][1], rc["floor_y"], 1)
    hall = J["dome"]
    for i, (role, pose) in enumerate([("farmer", "idle"), ("cook", "walk")]):
        person(role, pose, hall["x"] + 900 + i * 600, hall["floor_y"], i % 2)
    E = J["entrance"]; sp = {s_["id"]: s_ for s_ in E["spots"]}
    for sid, role, pose in [("e1", "scholar", "sit"), ("e2", "kid", "sit"), ("e3", "trader", "idle"), ("e4", "scout", "work"), ("e5", "engineer", "idle")]:
        person(role, pose, sp[sid]["x"], sp[sid]["floor_y"], 1 if sid in ("e2", "e4") else 0)
    bz = Ls["bubbles"]; bi = img(bz["file"]).crop((bz["frame_w"], 0, 2 * bz["frame_w"], bz["frame_h"]))
    canvas.alpha_composite(bi, (bz["place"][0] - bz["anchor"][0], bz["place"][1] - bz["anchor"][1]))
    sA = J["shafts"][0]; person("medic", "idle", sA["x_center"], J["tower"]["storeys"][1]["floor_y"])
    put_creatures(20, 100)
    put("front")
    canvas = canvas.convert("RGB")
    canvas.save(os.path.join(RAW, "preview_full.png"))
    canvas.resize((canvas.width // 4, canvas.height // 4), Image.LANCZOS).save(os.path.join(DST, "preview.png"), optimize=True)
    canvas.resize((canvas.width // 2, canvas.height // 2), Image.LANCZOS).save(os.path.join(RAW, "preview_half.jpg"), quality=88)
    # 폰 가로 기본 화면(844×390 CSS, 기본 배율) — layout.json phone 항목 그대로
    ph = J.get("phone") or {}
    if ph.get("default_view"):
        v = ph["default_view"]; z = v["zoom"]
        vw, vh = 844 / z, 390 / z
        box = (int(v["cx"] - vw / 2), int(v["cy"] - vh / 2), int(v["cx"] + vw / 2), int(v["cy"] + vh / 2))
        cr = canvas.crop(box)
        cr.resize((844, 390), Image.LANCZOS).save(os.path.join(DST, "preview_phone.png"), optimize=True)
        cr.resize((844 * 2, 390 * 2), Image.LANCZOS).save(os.path.join(RAW, "preview_phone2x.png"))
    E = J["entrance"]["pod"]
    canvas.crop((E["x0"] - 500, E["y0"] - 160, E["x0"] + 1300, E["y1"] + 420)).save(os.path.join(DST, "preview_entrance.png"), optimize=True)
    print("preview done")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    mode = argv[0] if argv else "post"
    if mode == "render":
        _blender()
    elif mode == "post":
        _post()
    elif mode == "preview":
        _preview()
