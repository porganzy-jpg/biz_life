# -*- coding: utf-8 -*-
"""
잔해 방주 — 맵 컨셉 넷 (S11-A, 가로 16:9 블록아웃)

두 단계로 돈다. 같은 파일이 Blender 안에서는 구조물을, 일반 파이썬에서는 합성을 맡는다.
  1) "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --python tools/blender_maps.py -- m1
       → art_raw/maps/_m1_mid.png   (구조물 3D 렌더, 투명 배경, 3200×1800, 손그림 선)
  2) python tools/blender_maps.py post m1
       → art_raw/maps/m1_hero.png (1600×900) · m1_phone.png (844×390) · m1_phone2x.png (1688×780)
  3) python tools/blender_maps.py serve      → static/art/maps/
  (m1 대신 all 이면 넷 전부)

컨셉 (docs/MAP_CONCEPTS.md)
  M1 가라앉은 배 속의 집 · M2 절벽에 뿌리내린 돔 · M3 고래 낙하 위의 마을 · M4 가라앉은 탑

규칙
  - 축척: 합성 캔버스 3200×1800 = 55px/m(캐릭터 ×2). 대표 컷은 정확히 1/2(=27.5px/m, 캐릭터 ×1).
    캐릭터는 원화 셀을 정수 배율·최근접 보간으로만 키운다(DECISIONS 2026-10-01 ①).
    방 플레이트(82.5px/m)는 축척을 맞추려 2/3로 줄인다 — 넓은 장소 컷이라서다(보고서에 이탈 사유).
  - 색: 안 = 황토 등불, 밖 = 청록→검정. 청록은 물에만(REF_ART_FLAT_FOLK §5).
  - 화면에서 가장 밝은 것은 방 안 등불(B3·F7). 빛기둥은 그보다 어둡게.
  - 생성 AI 없음. 구조물 = Blender 절차 모델, 나머지 = 기존 자산(플레이트·도트·생물 실루엣) + 절차 합성.
  - blender_section.py / blender_iso.py 는 수정하지 않는다(동시 작업 중). 이 파일은 독립 실행.
"""
import os, sys, math, random, json

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "art_raw", "maps")
DST = os.path.join(ROOT, "static", "art", "maps")
ART = os.path.join(ROOT, "static", "art")
os.makedirs(RAW, exist_ok=True)

W2, H2 = 3200, 1800          # 합성 캔버스
PPM = 55.0                   # px/m (캔버스)
ORTHO = W2 / PPM             # 58.18 m

# 플레이트 규격 (plates_meta.json)
PLATE_CROP = (54, 33, 618, 350)          # outer_rect
PLATE_PPM = 82.5
SLOT_W = (PLATE_CROP[2] - PLATE_CROP[0]) / PLATE_PPM      # 6.836 m
SLOT_H = (PLATE_CROP[3] - PLATE_CROP[1]) / PLATE_PPM      # 3.842 m
FLOOR_FROM_BOTTOM = (PLATE_CROP[3] - 315) / PLATE_PPM     # 0.424 m

PAL = {
    "cream": "#E8DCBF", "bone": "#C9B896", "ochre": "#F4AE43", "ochre_d": "#C4924D",
    "burnt": "#954515", "oxblood": "#642E26", "char": "#1C1712", "char_lt": "#3A312A",
    "olive": "#79804F", "olive_d": "#464E26",
    "sea_top": "#2E7E90", "sea_mid": "#0B2530", "sea_low": "#041016", "abyss": "#000000",
}


# ══════════════════════════════════════════════════════════════
# 장면 데이터 — 두 단계가 같이 읽는다
#   rooms: (x중심, 바닥z, 종류, 상태)  상태 = lit | dark | flood | plan | pump
#   people: 방마다 [(역할, 방 안 x 오프셋, 자세)]
# ══════════════════════════════════════════════════════════════
KINDS = ["quarters", "greenhouse", "workshop", "storage", "infirmary", "power"]


M1_L, M1_H = 50.0, 10.6        # 선체 길이·높이(용골→갑판)


def m1_hull():
    """M1 선체 좌표계: u = 선미→선수, v = 용골→갑판. 10° 선수 숙임 — 뱃머리가 해구 쪽 어둠으로."""
    th = math.radians(-10.0)
    x0, z0 = -26.5, -2.6

    def T(u, v):
        return (x0 + u * math.cos(th) - v * math.sin(th), z0 + u * math.sin(th) + v * math.cos(th))
    return T


def scene_m1():
    T = m1_hull()
    rooms = []
    plan = [  # (u중심, 줄, 종류, 상태) — 선미(왼쪽)부터 되찾았다
        (5.0, 0, "storage", "lit"), (5.0, 1, "quarters", "lit"),
        (12.4, 0, "power", "lit"), (12.4, 1, "greenhouse", "lit"),
        (19.8, 0, "workshop", "lit"), (19.8, 1, "infirmary", "lit"),
        (27.2, 0, "storage", "pump"), (27.2, 1, "quarters", "dark"),
        (34.6, 0, "storage", "flood"), (34.6, 1, "workshop", "flood"),
    ]
    rowv = [1.75, 6.05]
    for u, r, k, s in plan:
        x, z = T(u, rowv[r])
        rooms.append((round(x, 2), round(z, 2), k, s))
    bx, bz = T(8.6, M1_H + 1.3)      # 선교(브리지) — 갑판 위 집
    rooms.append((round(bx, 2), round(bz, 2), "quarters", "lit"))
    people = {
        0: [("trader", -1.6, "carry"), ("kid", 0.9, "sit")],
        1: [("cook", -1.9, "idle"), ("kid", 0.2, "sit"), ("medic", 1.9, "sit")],
        2: [("engineer", 0.4, "work")],
        3: [("farmer", -0.8, "work"), ("kid", 1.6, "idle")],
        4: [("engineer", -1.8, "work"), ("scout", 1.2, "idle")],
        5: [("medic", -1.0, "work"), ("scholar", 1.4, "sit")],
        6: [("engineer", -1.6, "work"), ("scout", 0.9, "carry")],
        10: [("scholar", -1.4, "idle"), ("scout", 1.3, "sit")],
    }
    return dict(key="m1", cx=0.0, cz=0.0, rooms=rooms, people=people)


def scene_m2():
    C = [-24.0, -16.8, -9.6]          # 바위 속 격자 세 칸
    R = [2.2, -2.25, -6.7, -11.15]    # 층 바닥
    st = [
        ["quarters:lit", "quarters:lit", "greenhouse:lit"],
        ["storage:lit", "workshop:lit", "infirmary:lit"],
        ["power:lit", "storage:dark", "plan"],
        ["plan", "plan", "plan"],
    ]
    rooms = []
    for ri, row in enumerate(st):
        for ci, cell in enumerate(row):
            k, s = (cell.split(":") + ["plan"])[:2] if ":" in cell else ("storage", "plan")
            # 같은 방이 옆에 붙으면 합쳐진다(폴아웃 셸터) — 첫 줄 거주 둘은 틈 없이 붙인다
            x = C[ci] + (0.17 if (ri == 0 and ci == 0) else (-0.17 if (ri == 0 and ci == 1) else 0))
            rooms.append((x, R[ri], k, s))
    # 돔(절벽 턱 위) 안의 온실
    rooms.append((-8.6, 8.6, "greenhouse", "lit"))
    people = {
        0: [("cook", -1.2, "idle"), ("kid", 1.4, "sit")],
        1: [("medic", -1.6, "sit"), ("scholar", 0.8, "idle")],
        2: [("farmer", -1.0, "work"), ("scout", 1.7, "idle")],
        3: [("trader", -1.2, "carry")],
        4: [("engineer", -0.8, "work"), ("engineer", 1.6, "idle")],
        5: [("medic", 0.4, "work"), ("kid", -1.8, "sit")],
        6: [("engineer", 0.6, "work")],
        12: [("farmer", -1.6, "work"), ("scholar", 0.4, "sit"), ("kid", 1.9, "idle")],
    }
    return dict(key="m2", cx=0.0, cz=-0.5, rooms=rooms, people=people)


RIBS_M3 = [-26.0, -17.0, -8.0, 1.0]


def scene_m3():
    """갈비뼈 아치 사이 칸. 위로 갈수록 갈비뼈가 오른쪽으로 휘므로 방도 따라 옮긴다."""
    rooms = [
        (-21.5, -9.9, "storage", "lit"), (-12.5, -9.9, "power", "lit"), (-3.5, -9.9, "workshop", "lit"),
        (-21.15, -5.3, "storage", "plan"), (-12.15, -5.3, "quarters", "lit"), (-3.15, -5.3, "greenhouse", "lit"),
        (-11.4, -0.7, "workshop", "dark"), (-2.4, -0.7, "infirmary", "lit"),
        (-30.0, -9.9, "storage", "plan"),           # 꼬리 쪽 — 아직 아무도 안 사는 뼈
        (13.4, -3.7, "quarters", "lit"),            # 머리뼈 위 돔
    ]
    people = {
        0: [("trader", -1.4, "carry"), ("kid", 1.4, "idle")],
        1: [("engineer", 0.5, "work")],
        2: [("engineer", -1.2, "work"), ("scout", 1.5, "idle")],
        4: [("cook", -1.7, "idle"), ("kid", 0.0, "sit"), ("medic", 1.8, "sit")],
        5: [("farmer", -0.5, "work")],
        7: [("medic", -1.0, "work"), ("scholar", 1.4, "sit")],
        9: [("scholar", -1.2, "idle"), ("farmer", 1.2, "work")],
    }
    return dict(key="m3", cx=0.0, cz=0.0, rooms=rooms, people=people)


def scene_m4():
    C = [-7.3, 0.0, 7.3]
    F = [2.4, -2.0, -6.4, -10.8, -15.2]
    st = [
        ["quarters:lit", "infirmary:lit", "workshop:lit"],
        ["storage:lit", "quarters:lit", "power:lit"],
        ["workshop:lit", "storage:pump", "quarters:flood"],
        ["storage:flood", "workshop:flood", "storage:flood"],
        ["plan", "storage:dark", "plan"],
    ]
    rooms = []
    for fi, row in enumerate(st):
        for ci, cell in enumerate(row):
            if cell == "plan":
                rooms.append((C[ci], F[fi], "storage", "plan"))
            else:
                k, s = cell.split(":")
                rooms.append((C[ci], F[fi], k, s))
    rooms.append((0.0, 7.6, "greenhouse", "lit"))      # 꼭대기 아트리움
    people = {
        0: [("cook", -1.4, "idle"), ("kid", 1.2, "sit")],
        1: [("medic", 0.2, "work")],
        2: [("engineer", -0.4, "work"), ("trader", 1.8, "idle")],
        3: [("trader", -1.0, "carry")],
        4: [("scholar", -1.6, "sit"), ("scout", 1.0, "idle")],
        5: [("engineer", 0.2, "work")],
        6: [("engineer", -1.5, "work"), ("kid", 1.4, "idle")],
        7: [("scout", -1.8, "work")],
        15: [("farmer", -2.2, "work"), ("scholar", -0.2, "sit"), ("kid", 1.6, "idle"), ("cook", 2.6, "idle")],
    }
    return dict(key="m4", cx=0.0, cz=0.0, rooms=rooms, people=people)


M5_X0, M5_HW, M5_IN = -4.6, 14.0, 10.8     # M5 탑: 중심 x, 바깥 반폭, 잘라 낸 단면 반폭


def scene_m5():
    """M2+M4 혼합 — 절벽 끝에 기대 선 수몰 탑. 왼쪽 바위, 가운데 탑, 오른쪽 열린 심연."""
    C = [M5_X0 - 7.3, M5_X0, M5_X0 + 7.3]
    F = [2.4, -2.0, -6.4, -10.8, -15.2]
    st = [
        ["quarters:lit", "infirmary:lit", "workshop:lit"],
        ["storage:lit", "quarters:lit", "power:lit"],
        ["workshop:lit", "storage:pump", "quarters:flood"],
        ["storage:flood", "plan", "workshop:flood"],
        ["plan", "storage:dark", "plan"],
    ]
    rooms = []
    for fi, row in enumerate(st):
        for ci, cell in enumerate(row):
            if cell == "plan":
                rooms.append((C[ci], F[fi], "storage", "plan"))
            else:
                k, s_ = cell.split(":")
                rooms.append((C[ci], F[fi], k, s_))
    rooms.append((-24.2, -2.0, "greenhouse", "lit"))    # 15 바위를 판 굴 방(탑과 절벽이 만나는 곳)
    rooms.append((-24.2, -6.4, "storage", "plan"))      # 16 더 팔 자리
    rooms.append((M5_X0, 7.6, "greenhouse", "lit"))     # 17 꼭대기 아트리움(돔)
    people = {
        0: [("cook", -1.4, "idle"), ("kid", 1.2, "sit")],
        1: [("medic", 0.2, "work")],
        2: [("engineer", -0.4, "work"), ("trader", 1.8, "idle")],
        3: [("trader", -1.0, "carry")],
        4: [("scholar", -1.6, "sit"), ("scout", 1.0, "idle")],
        5: [("engineer", 0.2, "work")],
        6: [("engineer", -1.5, "work"), ("kid", 1.4, "idle")],
        7: [("scout", -1.8, "work")],
        15: [("farmer", -0.8, "work"), ("kid", 1.6, "idle")],
        17: [("farmer", -2.2, "work"), ("scholar", -0.2, "sit"), ("kid", 1.6, "idle"), ("cook", 2.6, "idle")],
    }
    return dict(key="m5", cx=0.0, cz=0.0, rooms=rooms, people=people)


SCENES = {"m1": scene_m1, "m2": scene_m2, "m3": scene_m3, "m4": scene_m4, "m5": scene_m5}

META = {
    "m1": dict(name="가라앉은 배 속의 집", ref="Spiritfarer + Barotrauma",
               line="옆으로 기운 화물선의 선체가 집이다. 물을 빼고 한 칸씩 되찾는다. 뱃머리는 해구 쪽 어둠으로."),
    "m2": dict(name="절벽에 뿌리내린 돔", ref="Dome Keeper + Fallout Shelter",
               line="왼쪽은 바위를 깎은 굴 같은 방들, 오른쪽은 해구로 떨어지는 심연. 위협은 열린 쪽에서 온다."),
    "m3": dict(name="고래 낙하 위의 마을", ref="Spiritfarer + 심해 고래 낙하 생태",
               line="쓰러진 거대 생물의 갈비뼈가 기둥이다. 죽음 위에 사는 삶, 뼈 주위로 작은 생물이 모인다."),
    "m5": dict(name="절벽 끝에 기댄 가라앉은 탑", ref="M2+M4 혼합 — Dome Keeper + Fallout Shelter",
               line="절벽 끝에 기대 선 수몰 탑. 꼭대기 아트리움이 돔, 층을 따라 해구 위 어둠으로 내려간다. 오른쪽은 열린 심연, 위협은 그쪽에서 온다."),
    "m4": dict(name="가라앉은 탑", ref="Fallout Shelter + 3막 지상 도시 복선",
               line="수몰 고층 건물의 꼭대기 유리 아트리움이 돔이다. 거점은 층을 따라 해구의 어둠으로 내려간다."),
}


def slot_rect(x, zf):
    """방 슬롯 바깥 사각형(월드 m): 좌, 아래, 우, 위"""
    b = zf - FLOOR_FROM_BOTTOM
    return (x - SLOT_W / 2, b, x + SLOT_W / 2, b + SLOT_H)


# ══════════════════════════════════════════════════════════════════════════════
#  1단계 — Blender
# ══════════════════════════════════════════════════════════════════════════════
def _blender_main(key):
    import bpy, bmesh
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    noline = bpy.data.collections.new("NOLINE"); sc.collection.children.link(noline)
    rng = random.Random(hash(key) & 0xffff)

    def s2l(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lin(h):
        h = h.lstrip("#")
        return tuple(s2l(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))

    MATS = {}

    def mat(name, cols, stops=None, noise=0.06, axis="Z", nscale=3.0):
        """2~3단 평면 음영. 아래(어두움)→위(밝음). 노이즈로 경계를 손으로 칠한 듯 흔든다."""
        k = (name,)
        if k in MATS:
            return MATS[k]
        m = bpy.data.materials.new(name); m.use_nodes = True
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        if len(cols) == 1:
            em.inputs["Color"].default_value = (*lin(cols[0]), 1)
        else:
            tc = nt.nodes.new("ShaderNodeTexCoord")
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(tc.outputs["Generated"], sep.inputs[0])
            nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = nscale
            nz.inputs["Detail"].default_value = 3.0
            nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
            mr = nt.nodes.new("ShaderNodeMapRange")
            mr.inputs["To Min"].default_value = -noise; mr.inputs["To Max"].default_value = noise
            nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
            add = nt.nodes.new("ShaderNodeMath"); add.operation = 'ADD'
            nt.links.new(sep.outputs[axis], add.inputs[0]); nt.links.new(mr.outputs[0], add.inputs[1])
            ramp = nt.nodes.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
            cr.interpolation = 'CONSTANT'
            n = len(cols)
            stops = stops or [i / n for i in range(n)]
            cr.elements[0].position = 0.0; cr.elements[0].color = (*lin(cols[0]), 1)
            cr.elements[1].position = stops[1]; cr.elements[1].color = (*lin(cols[1]), 1)
            for i in range(2, n):
                e = cr.elements.new(stops[i]); e.color = (*lin(cols[i]), 1)
            nt.links.new(add.outputs[0], ramp.inputs["Fac"])
            nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
        MATS[k] = m
        return m

    def _obj(name, bm, m, line=True):
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(name, me)
        (sc.collection if line else noline).objects.link(o)
        me.materials.append(m)
        return o

    def jag(pts, amp=0.12, step=0.7, closed=True, seed=1):
        """가장자리를 손으로 자른 듯 — 변을 쪼개고 법선 방향으로 흔든다."""
        r = random.Random(seed); outp = []
        n = len(pts); rng_n = n if closed else n - 1
        for i in range(rng_n):
            a = pts[i]; b = pts[(i + 1) % n]
            d = math.dist(a, b); k = max(1, int(d / step))
            nx, nz = (-(b[1] - a[1]) / (d or 1), (b[0] - a[0]) / (d or 1))
            for j in range(k):
                t = j / k; o = r.uniform(-amp, amp) if j else 0.0
                outp.append((a[0] + (b[0] - a[0]) * t + nx * o, a[1] + (b[1] - a[1]) * t + nz * o))
        if not closed:
            outp.append(pts[-1])
        return outp

    def poly(name, pts, y, m, line=True, j=0.0, seed=1):
        if j:
            pts = jag(pts, amp=j, seed=seed)
        bm = bmesh.new()
        vs = [bm.verts.new((p[0], y, p[1])) for p in pts]
        try:
            bm.faces.new(vs)
        except Exception:
            pass
        return _obj(name, bm, m, line)

    def ribbon(name, pts, w, y, m, line=True, w1=None):
        """폴리라인을 두께 있는 띠로. w → w1 로 가늘어진다."""
        w1 = w if w1 is None else w1
        bm = bmesh.new(); L, R = [], []
        n = len(pts)
        for i, p in enumerate(pts):
            a = pts[max(0, i - 1)]; b = pts[min(n - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]; d = math.hypot(dx, dz) or 1
            nx, nz = -dz / d, dx / d
            ww = (w + (w1 - w) * i / max(1, n - 1)) / 2
            L.append(bm.verts.new((p[0] + nx * ww, y, p[1] + nz * ww)))
            R.append(bm.verts.new((p[0] - nx * ww, y, p[1] - nz * ww)))
        for i in range(n - 1):
            bm.faces.new((L[i], L[i + 1], R[i + 1], R[i]))
        return _obj(name, bm, m, line)

    def ellipse(cx, cz, rx, rz, n=28, a0=0.0, a1=2 * math.pi):
        return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cz + rz * math.sin(a0 + (a1 - a0) * i / n))
                for i in range(n + (0 if a1 - a0 >= 2 * math.pi - 1e-6 else 1))]

    def rect(x0, z0, x1, z1):
        return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]

    def kelp(name, x, z, h, y, m, seed, lean=0.0, w=0.32):
        r = random.Random(seed); pts = []
        ph = r.uniform(0, 6.28); n = 14
        for i in range(n + 1):
            t = i / n
            pts.append((x + math.sin(ph + t * 4.2) * 0.55 * t + lean * t * h, z + t * h))
        ribbon(name, pts, w, y, m, w1=w * 0.35)
        # 잎 몇 장
        for i in range(3, n, 3):
            px, pz = pts[i]; s = 1 if i % 2 else -1
            ribbon(name + f"_l{i}", [(px, pz), (px + s * 0.5, pz + 0.35), (px + s * 0.95, pz + 0.55)],
                   0.22, y - 0.01, m, w1=0.05)

    def win(name, x, z, w, h, y, col="#F4AE43"):
        poly(name, rect(x - w / 2, z - h / 2, x + w / 2, z + h / 2), y, mat("win_" + col, [col]), line=True)

    sc_data = SCENES[key]()
    ROOMS = sc_data["rooms"]

    # 방 뒤판: 구조물 안에 박힌 '굴'의 어두운 테 — 플레이트가 위에 얹힌다
    def room_backs(y=0.2):
        mb = mat("roomback", ["#120E0B"])
        for i, (x, zf, k, s) in enumerate(ROOMS):
            if s == "plan":
                continue
            l, b, r_, t = slot_rect(x, zf)
            poly(f"rb{i}", rect(l - 0.25, b - 0.25, r_ + 0.25, t + 0.25), y, mb, j=0.06, seed=i)

    # ───────────────────────── M1 ─────────────────────────
    if key == "m1":
        T = m1_hull()
        L, H = M1_L, M1_H
        # 해저 비탈: 왼쪽 위 → 오른쪽 아래, x≈17 에서 해구로 꺾여 떨어진다
        bedm = mat("bed", ["#0C171A", "#1C3436", "#2E4E4C", "#4A6A62"], [0, 0.5, 0.78, 0.93], nscale=1.5)
        bed = [(-31, -3.0), (-25, -4.6), (-16, -6.4), (-6, -8.4), (4, -10.4), (12, -11.8), (16.5, -12.6),
               (18.0, -15.0), (17.0, -19.0), (18.5, -24.0), (-31, -24.0)]
        poly("bed", bed, 3.0, bedm, j=0.3, seed=3)
        poly("bed_b", [(-31, 0.5), (-22, -1.0), (-10, -3.5), (2, -6.4), (12, -8.6), (16.0, -9.6), (17.5, -20),
                       (-31, -20)], 6.0, mat("bed_b", ["#0C1C22", "#173238", "#244A4C"], [0, 0.55, 0.88]), j=0.35, seed=4)
        # 선체 바깥판(뒤판) — 녹슨 적갈을 찬물이 식힌 색
        hull = [T(-1.4, 3.0), T(0.4, 0.6), T(2.0, 0), T(L - 7, 0), T(L - 2.5, 2.2), T(L + 1.2, 6.0),
                T(L + 3.0, H + 1.6), T(-0.6, H), T(-1.6, 6.0)]
        poly("hull_back", hull, 1.0, mat("hull_back", ["#1A1311", "#2A1E19", "#3A2A22"], [0, 0.5, 0.86]),
             j=0.08, seed=5)
        # 아직 덮인 선수 강판(되찾지 못한 칸) — 둥근 창, 하나만 희미하게 불빛
        cov = [T(38.3, 0.1), T(L - 7, 0.1), T(L - 2.5, 2.2), T(L + 1.2, 6.0), T(L + 3.0, H + 1.6), T(38.3, H + 0.1)]
        poly("bow_plate", cov, 0.4, mat("bowp", ["#24130F", "#3A2A22", "#4E3A2E"], [0, 0.3, 0.8]), j=0.06, seed=6)
        # 흘수선 아래 적갈 방오 도료 띠(배의 문법 — 한눈에 '배')
        poly("antifoul", [T(-1.4, 3.0), T(0.4, 0.6), T(2.0, 0), T(L - 7, 0), T(L - 2.5, 2.2), T(L - 0.6, 3.6),
                          T(-1.2, 3.6)], 0.35, mat("antif", ["#3A1A14", "#5A2A20"], [0, 0.55]), j=0.05, seed=16)
        for i, u in enumerate([40.5, 43.5, 46.5]):
            for v in (5.6, 8.6):
                px, pz = T(u + (v - 5.6) * 0.1, v)
                col = "#2E3E3E" if (i, v) != (1, 8.6) else "#9A7A40"
                poly(f"port{i}_{v}", ellipse(px, pz, 0.55, 0.55, 14), 0.3, mat("port" + col, [col]))
        # 닻(뱃머리에 매달려 해구 쪽으로)
        ax, az = T(L - 1.0, 7.4)
        ribbon("anchor_chain", [(ax, az), (ax + 1.0, az - 3.0), (ax + 1.6, az - 6.4)], 0.22, 0.25, mat("chain", ["#2A2420"]))
        poly("anchor", [(ax + 0.6, az - 6.4), (ax + 2.6, az - 6.4), (ax + 2.2, az - 7.6), (ax + 1.6, az - 8.4),
                        (ax + 1.0, az - 7.6)], 0.25, mat("anc", ["#2A2420", "#4A3E34"], [0, 0.6]))
        # 단면 둘레 강판(두꺼운 테) + 갑판
        rim = [T(-1.6, 6.0), T(-1.4, 3.0), T(0.4, 0.6), T(2.0, 0), T(L - 7, 0), T(L - 2.5, 2.2), T(L + 1.2, 6.0),
               T(L + 3.0, H + 1.6)]
        ribbon("hull_rim", rim, 0.9, 0.3, mat("rim", ["#3E2C22", "#5A3E2C", "#6E5A4A"], [0, 0.5, 0.9]))
        ribbon("deck", [T(-0.8, H), T(L + 3.0, H + 1.6)], 0.7, 0.3, mat("deck", ["#4A3628", "#6E5A4A"], [0, 0.6]))
        for u in range(0, int(L), 2):    # 난간 기둥
            ribbon(f"rail{u}", [T(u, H + 0.3), T(u, H + 1.3)], 0.12, 0.32, mat("rail", ["#4A3628"]))
        ribbon("railtop", [T(-0.4, H + 1.3), T(L + 1, H + 2.4)], 0.14, 0.32, mat("rail", []))
        # 늑골(칸막이) — 방 사이
        for u in (1.3, 8.7, 16.1, 23.5, 30.9, 38.3):
            ribbon(f"frame{u}", [T(u, 0.4), T(u, H - 0.2)], 0.6, 0.25, mat("frame", ["#2C201A", "#4A3628"], [0, 0.7]))
        ribbon("midfloor", [T(0.5, 5.65), T(38.3, 5.65)], 0.35, 0.28, mat("frame", []))
        # 선교(브리지) 집 + 지붕 + 지붕 위 유리돔(사람이 올린 전망등)
        br = [T(2.6, H - 0.2), T(14.6, H - 0.2), T(14.0, H + 6.0), T(3.2, H + 6.0)]
        poly("bridge", br, 0.6, mat("bridge", ["#2E221C", "#4A3628", "#6A5244"], [0, 0.5, 0.85]), j=0.06, seed=7)
        rf = [T(2.0, H + 5.8), T(15.2, H + 5.8), T(15.0, H + 6.6), T(2.2, H + 6.6)]
        poly("bridge_roof", rf, 0.5, mat("roof", ["#5A4436", "#7C6450"], [0, 0.5]))
        dx, dz = T(8.6, H + 6.6)
        poly("bdome", ellipse(dx, dz, 2.8, 2.3, 22, 0, math.pi), 0.45, mat("bdome", ["#1E4A50", "#2E6A70", "#4A8A90"], [0, 0.5, 0.85]))
        win("bdlamp", dx, dz + 0.9, 0.6, 0.6, 0.4, "#FFE2A0")
        # 굴뚝(적갈 + 크림 띠)
        poly("funnel", [T(16.6, H - 0.2), T(20.0, H - 0.2), T(20.6, H + 5.4), T(17.2, H + 5.4)], 0.7,
             mat("funnel", ["#3A1E18", "#642E26", "#7A4030"], [0, 0.45, 0.85]), j=0.05, seed=8)
        ribbon("funnel_band", [T(16.9, H + 3.8), T(20.3, H + 3.8)], 0.6, 0.65, mat("fband", ["#A89878"]))
        # 쓰러진 돛대 + 늘어진 밧줄
        ribbon("mast", [T(30, H), T(35, H + 10)], 0.45, 0.9, mat("mast", ["#3A2A22", "#5A4436"], [0, 0.6]))
        ribbon("mast_x", [T(32.4, H + 6.6), T(35.6, H + 5.0)], 0.3, 0.9, mat("mast", []))
        p1, p2 = T(35, H + 10), T(L + 1, H + 2.4)
        ribbon("stay", [p1, ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 - 1.2), p2], 0.08, 0.9, mat("rope", ["#6A5A48"]))
        # 선미 키·추진기
        poly("rudder", [T(-1.0, 4.4), T(-3.8, 3.8), T(-4.2, 0.2), T(-0.8, 1.0)], 1.1,
             mat("rud", ["#2A1E19", "#4A3628"], [0, 0.6]), j=0.05, seed=9)
        px, pz = T(-0.4, 2.0)
        for a in range(3):
            ang = a * 2.09 + 0.4
            poly(f"prop{a}", ellipse(px + 1.0 * math.cos(ang), pz + 1.0 * math.sin(ang), 0.95, 0.42, 12), 1.15,
                 mat("prop", ["#5A4436", "#7C6450"], [0, 0.5]))
        # 용골을 묻은 퇴적(박혀 있다) — 선체 앞쪽
        sed = [(-31, -6.0), (-28, -3.6), (-24, -3.8), (-18, -5.6), (-10, -7.0), (-2, -8.6), (6, -10.0),
               (12, -11.6), (16, -12.4), (16.5, -14), (-31, -14)]
        ribbon("bed_skin", jag(bed[:7], amp=0.2, closed=False, seed=31), 0.7, 2.95, mat("skin", ["#3E5A54", "#5A766A"], [0, 0.5]))
        ribbon("sed_skin", jag(sed[:10], amp=0.2, closed=False, seed=32), 1.0, 0.0, mat("skin2", ["#34483F", "#4E6254"], [0, 0.5]))
        poly("sediment", sed, 0.05, mat("sed", ["#10181A", "#2A3A36", "#4A5C50", "#6A7A64"], [0, 0.45, 0.8, 0.94], nscale=2.0), j=0.3, seed=17)
        # 쏟아진 컨테이너(200년 전 상품 — 바코드 유물의 근원)
        cols = ["#6A2E22", "#4E5A2A", "#8A6A34", "#3E4450", "#7A4020"]
        boxes = [(-27.6, -5.2, 5.6, 2.4, -6, 2.0), (-22.6, -5.6, 5.6, 2.4, 3, 2.2), (-24.6, -3.2, 5.6, 2.4, -2, 2.4),
                 (-12.0, -8.2, 5.6, 2.4, -12, -0.2), (-5.0, -9.3, 5.6, 2.4, 20, -0.25), (9.0, -12.2, 5.6, 2.4, -24, -0.3)]
        for i, (bx, bz, bw, bh, rot, by) in enumerate(boxes):
            r = math.radians(rot); c, s_ = math.cos(r), math.sin(r)
            pts = [(bx + (px_ * c - pz_ * s_), bz + (px_ * s_ + pz_ * c)) for px_, pz_ in
                   ((-bw / 2, -bh / 2), (bw / 2, -bh / 2), (bw / 2, bh / 2), (-bw / 2, bh / 2))]
            col = cols[i % len(cols)]
            poly(f"box{i}", pts, by, mat("box" + col, ["#1A1210", col], [0, 0.22]), j=0.04, seed=20 + i)
            for k in range(1, 7):
                t = k / 7
                a_ = (pts[0][0] + (pts[1][0] - pts[0][0]) * t, pts[0][1] + (pts[1][1] - pts[0][1]) * t)
                b_ = (pts[3][0] + (pts[2][0] - pts[3][0]) * t, pts[3][1] + (pts[2][1] - pts[3][1]) * t)
                ribbon(f"box{i}_r{k}", [a_, b_], 0.1, by - 0.02, mat("boxrib", ["#140E0C"]), line=False)
        # 비탈의 해초 숲 + 갑판에 자란 해초
        km = mat("kelp", ["#1E2A16", "#2E3A1E", "#46502A"], [0, 0.5, 0.85])
        for i, (x, z, h) in enumerate([(-30, -4.0, 8), (-28.8, -4.2, 5.5), (-17.5, -6.0, 6.5), (-15.0, -6.6, 4.5),
                                       (-1.0, -9.0, 8.0), (2.2, -9.6, 5.5), (13.0, -11.8, 6.0), (15.0, -12.4, 9.0)]):
            kelp(f"k{i}", x, z, h, -0.1, km, 100 + i, lean=0.06)
        for i, u in enumerate([22, 26, 29, 41, 45]):
            x, z = T(u, H + 0.4)
            kelp(f"kh{i}", x, z, 2.2 + (i % 3), 0.2, km, 200 + i, w=0.22)
        # 펌프 호스(되찾는 중인 칸 → 수면 쪽 위로) — 성장의 증거
        hx, hz = T(27.2, 3.0)
        ribbon("hose", [(hx + 2.4, hz), (hx + 3.6, hz + 3.0), (hx + 3.0, hz + 8.0), (hx + 4.4, hz + 13.4),
                        (hx + 6.4, hz + 18.0), (hx + 7.0, hz + 22.0)], 0.32, 0.15, mat("hose", ["#5A3A20", "#8A6030"], [0, 0.5]))
        room_backs()

    elif key == "m2":
        # 절벽 앞면: 왼쪽 바위. 턱(z≈9) 위에 돔, 가장자리는 x≈0~2, 해구 바로 위(z≈-13)에서 끝난다.
        edge = [(-14.6, 16.6), (-14.0, 12.0), (-13.0, 8.6), (-0.6, 7.8), (1.2, 6.4), (0.4, 4.4),
                (1.8, 2.4), (1.0, 0.0), (2.4, -2.2), (1.4, -4.8), (2.6, -7.4), (1.6, -9.4), (2.2, -10.6),
                (0.4, -12.2), (-1.8, -13.2), (-3.4, -12.5), (-5.0, -13.6), (-7.4, -12.7), (-9.4, -13.8),
                (-11.6, -12.6), (-14.2, -13.9), (-17.2, -12.7), (-20.2, -14.0), (-23.2, -12.8), (-26.2, -14.2),
                (-29.5, -13.2), (-29.5, 16.6)]
        rock = mat("rock", ["#120F0D", "#1C1815", "#262220", "#33302A"], [0, 0.3, 0.62, 0.86], noise=0.08, nscale=1.6)
        poly("cliff", edge, 1.0, rock, j=0.22, seed=11)
        # 지층 띠(바위의 결) — 가로로 기운 어두운/밝은 줄
        r = random.Random(8)
        for i, z in enumerate([12.6, 6.2, 0.9, -3.6, -8.2, -12.2]):
            pts = [(-29.5, z + r.uniform(-0.4, 0.4))]
            for x in range(-26, 2, 3):
                pts.append((x, z + r.uniform(-0.5, 0.5) + (x + 29) * 0.03))
            ribbon(f"strata{i}", pts, 0.5 + r.uniform(0, 0.4), 0.8, mat("strata", ["#2E2A24", "#3A362E"], [0, 0.5]))
        # 심연 쪽 가장자리 테: 물빛을 받은 차가운 모서리(B3 경계 강조)
        ribbon("edge_rim", jag(edge[3:14], amp=0.15, closed=False, seed=12), 0.7, 0.85,
               mat("erim", ["#3A4644", "#56625C"], [0, 0.5]))
        ribbon("ledge_top", [(-13.0, 8.6), (-0.6, 7.8), (1.2, 6.4)], 0.6, 0.8, mat("ledge", ["#4E5A4A", "#62705A"], [0, 0.5]))
        # 균열
        cm = mat("crack", ["#0A0806"])
        for i in range(18):
            x = r.uniform(-28, -2); z = r.uniform(-13, 14); pts = [(x, z)]
            for _ in range(4):
                x += r.uniform(-1.4, 1.4); z += r.uniform(-1.6, -0.4); pts.append((x, z))
            ribbon(f"crk{i}", pts, 0.18, 0.7, cm, w1=0.04)
        # 돔: 턱 위
        DX, DZ = -8.6, 8.0
        poly("dome_base", rect(DX - 6.6, DZ - 0.8, DX + 6.6, DZ + 0.2), 0.5, mat("dbase", ["#3A2E26", "#5A4A3A"], [0, 0.5]))
        poly("dome_glass", ellipse(DX, DZ + 0.2, 6.2, 5.6, 30, 0, math.pi), 0.55,
             mat("dglass", ["#1C3E44", "#2A5A60", "#3E7A80"], [0, 0.5, 0.85]))
        for i in range(1, 6):
            a = math.pi * i / 6
            ribbon(f"drib{i}", [(DX + 6.2 * math.cos(a), DZ + 0.2 + 5.6 * math.sin(a)), (DX, DZ + 0.2)],
                   0.12, 0.5, mat("drib", ["#5A4A3A"]))
        poly("dome_cap", ellipse(DX, DZ + 5.8, 0.8, 0.5, 12), 0.5, mat("dcap", ["#7C6450"]))
        # 승강 척추(돔 → 아래)
        ribbon("spine", [(-4.4, 7.2), (-4.4, -11.8)], 1.2, 0.5, mat("spine", ["#2A2420", "#4A3E34"], [0, 0.7]))
        for z in range(-12, 7, 1):
            ribbon(f"rung{z}", [(-4.9, z + 0.5), (-3.9, z + 0.5)], 0.1, 0.45, mat("rung", ["#6E5A4A"]))
        # 심연으로 내민 크레인(밖으로 뻗은 손)
        ribbon("crane", [(1.8, 3.8), (6.4, 6.2), (10.6, 5.8)], 0.38, 0.6, mat("crane", ["#4A3628", "#6E5A4A"], [0, 0.5]))
        ribbon("crane_rope", [(10.6, 5.8), (10.7, -3.0)], 0.07, 0.6, mat("rope", ["#8A7A60"]))
        poly("crane_hook", ellipse(10.7, -3.4, 0.5, 0.5, 10), 0.6, mat("hook", ["#C4924D"]))
        # 맨 아래 칸에서 해구로 늘어뜨린 줄(닿지 못하는 깊이 — 180m)
        ribbon("deep_rope", [(-9.6, -13.4), (-9.3, -14.8), (-9.5, -15.9)], 0.07, 0.6, mat("rope", []))
        # 턱 위·절벽 틈의 해초
        km = mat("kelp", ["#1E2A16", "#2E3A1E", "#46502A"], [0, 0.5, 0.85])
        for i, (x, z, h, ln) in enumerate([(-1.6, 7.9, 4.5, 0.15), (0.6, 6.8, 3.0, 0.3), (-14.0, 9.0, 3.5, -0.1),
                                           (1.8, 1.0, 2.6, 0.4), (2.2, -6.6, 2.2, 0.5), (1.6, -11.2, 2.0, 0.45),
                                           (-20.0, 13.6, 2.6, 0.1), (-26.0, 12.8, 3.4, -0.1)]):
            kelp(f"k{i}", x, z, h, 0.3, km, 300 + i, lean=ln, w=0.26)
        # 절벽 밑동에서 늘어진 덩굴 — 밑은 허공
        for i, x in enumerate([-2.0, -6.0, -12.0, -18.5, -24.0]):
            z0 = -12.6 - (i % 2) * 0.8
            pts = [(x + math.sin(t * 2.5 + i) * 0.4, z0 - t * (1.8 + i % 3)) for t in [k / 8 for k in range(9)]]
            ribbon(f"hang{i}", pts, 0.22, 0.3, km, w1=0.05)
        room_backs()

    # ───────────────────────── M3 ─────────────────────────
    elif key == "m3":
        bed = [(-31, -11.6), (-20, -11.2), (-10, -11.8), (0, -11.2), (10, -11.6), (20, -11.0), (31, -11.8),
               (31, -20), (-31, -20)]
        poly("bed", bed, 3.0, mat("bed", ["#0B1418", "#14262C", "#24383C"], [0, 0.8, 0.94]), j=0.22, seed=3)
        ribbon("bed_skin", jag(bed[:7], amp=0.15, closed=False, seed=31), 0.6, 2.95, mat("skin", ["#2E4A48", "#40605A"], [0, 0.5]))
        for i, (x, rx) in enumerate([(-22, 8), (-6, 9), (10, 10), (24, 6)]):
            poly(f"mound{i}", ellipse(x, -11.4, rx, 1.6, 20, 0, math.pi), 2.6,
                 mat("mound", ["#1A2A2C", "#2A3E3E"], [0, 0.7]), j=0.12, seed=40 + i)
        bone = mat("bone", ["#5E5444", "#8E8068", "#B8A888", "#D8CCAE"], [0, 0.3, 0.62, 0.86], noise=0.05)
        bone_d = mat("bone_d", ["#2E2A24", "#423C32", "#5A5244"], [0, 0.5, 0.85])
        # 등뼈 — 꼬리(왼쪽, 화면 밖) → 두개골(오른쪽)
        spine = [(-36, -10.6), (-26, -10.0), (-16, -9.6), (-6, -9.4), (2, -9.2), (8, -8.8)]
        ribbon("spine", spine, 1.3, 0.8, bone)
        for i in range(-35, 8, 2):
            zz = -10.4 + (i + 34) * 0.03
            poly(f"vert{i}", ellipse(i, zz + 0.55, 0.75, 0.9, 12), 0.75, bone, j=0.04, seed=60 + i)
        # 갈비뼈 — 성당 아치처럼 높이 솟아 오른쪽으로 휜다. 뒤편 갈비뼈는 어둡게 비켜서.
        for i, x in enumerate(RIBS_M3):
            # 사분 타원 호: 등뼈에서 곧게 솟아 위에서 오른쪽으로 크게 휘어 넘어간다
            Rz = 17.5 - abs(x + 10) * 0.12; Rx = 5.4
            pts = [(x + Rx * (1 - math.cos(ph)), -9.6 + Rz * math.sin(ph))
                   for ph in [math.radians(118) * k / 20 for k in range(21)]]
            pts2 = [(p[0] - 2.2 + 1.2 * k / 20, p[1] + 0.8) for k, p in enumerate(pts)]
            ribbon(f"ribB{i}", pts2, 1.0, 1.6, bone_d, w1=0.35)
            ribbon(f"rib{i}", pts, 1.5, 0.9, bone, w1=0.45)
        # 꼬리 쪽 작은 갈비뼈(아직 아무도 안 사는 뼈 — 자랄 자리)
        for i, x in enumerate([-34.5, -31.5]):
            pts = [(x + math.sin(k / 12 * 1.6) * 2.0 * k / 12, -10.0 + k / 12 * 11.0) for k in range(13)]
            ribbon(f"ribT{i}", pts, 1.0, 0.9, bone, w1=0.4)
        # 두개골: 둥근 머리뼈(왼쪽) → 길고 납작한 주둥이(오른쪽 끝으로)
        sk = [(7.0, -9.6), (8.0, -6.6), (10.4, -4.6), (14.0, -3.8), (17.6, -4.4), (21.0, -6.0), (25.0, -7.4),
              (29.0, -8.4), (31.5, -9.2), (29.5, -9.9), (22.0, -10.0), (14.0, -10.3)]
        poly("skull", sk, 1.0, bone, j=0.08, seed=70)
        ribbon("jaw", [(8.6, -11.0), (16.0, -11.6), (24.0, -11.2), (31.0, -10.4)], 0.9, 0.95, bone_d)
        poly("eye", ellipse(12.8, -7.4, 1.4, 1.1, 14), 0.9, mat("eye", ["#0E0C0A"]))
        ribbon("snout_line", [(15.0, -8.0), (22.0, -8.4), (29.0, -9.0)], 0.18, 0.95, mat("crack", ["#3A342A"]))
        # 머리뼈 위 유리돔
        poly("sdome", ellipse(13.4, -4.3, 5.0, 4.6, 28, 0, math.pi), 0.6,
             mat("dglass", ["#1C3E44", "#2A5A60", "#3E7A80"], [0, 0.5, 0.85]))
        poly("sdome_base", rect(8.0, -5.0, 18.8, -4.1), 0.55, mat("dbase", ["#3A2E26", "#5A4A3A"], [0, 0.5]))
        # 뼈 사이 받침 발판·밧줄·등불 줄(사람이 묶은 것)
        wood = mat("wood", ["#3A2A1E", "#5A4430", "#7A5E40"], [0, 0.5, 0.85])
        for i, (cx_, z) in enumerate([(-12.15, -5.3), (-3.15, -5.3), (-11.4, -0.7), (-2.4, -0.7)]):
            poly(f"plank{i}", rect(cx_ - 4.2, z - 0.85, cx_ + 4.2, z - 0.42), 0.4, wood)
        rope = mat("rope", ["#8A7A60"])
        # 갈비뼈 꼭대기 사이에 걸친 등불 줄(사람이 사는 뼈라는 표시)
        for i, (x0, x1) in enumerate([(-22.9, -14.0), (-13.9, -5.0), (-4.9, 4.0)]):
            pts = [(x0 + (x1 - x0) * t, 6.6 - math.sin(math.pi * t) * 1.6) for t in [k / 10 for k in range(11)]]
            ribbon(f"rope{i}", pts, 0.08, 0.85, rope)
            for k in (2, 4, 6, 8):
                win(f"lamp{i}{k}", pts[k][0], pts[k][1] - 0.35, 0.36, 0.42, 0.84, "#FFC870")
        # 관벌레·해초(뼈를 먹고 사는 것들)
        km = mat("kelp", ["#1E2A16", "#2E3A1E", "#46502A"], [0, 0.5, 0.85])
        for i, (x, h) in enumerate([(-30, 6.5), (-28.4, 4.5), (5.0, 4.0), (21.5, 3.6), (29, 7.0), (-18.0, 3.0)]):
            kelp(f"k{i}", x, -11.4, h, 2.0, km, 400 + i, lean=0.05)
        worm = mat("worm", ["#6A2A22", "#A8483A"], [0, 0.6])
        r = random.Random(9)
        for i in range(30):
            x = r.choice([r.uniform(-31, -26), r.uniform(5, 12), r.uniform(18, 30), r.uniform(-26, 2)])
            z = -10.3 + r.uniform(-0.6, 0.4)
            hh = r.uniform(0.6, 1.4)
            ribbon(f"worm{i}", [(x, z), (x + r.uniform(-0.2, 0.2), z + hh)], 0.12, 0.7, worm)
            poly(f"wormh{i}", ellipse(x, z + hh, 0.22, 0.16, 8), 0.68, mat("wormh", ["#E0704A"]), line=False)
        # 머리뼈 아래 꺼진 구멍 → 더 깊은 굴(아래로 갈 곳)
        poly("sink", ellipse(19.0, -13.4, 4.4, 1.5, 22), 2.4, mat("sink", ["#000000"]), j=0.15, seed=88)
        ribbon("sink_rope", [(17.0, -10.6), (18.2, -12.4), (18.6, -14.4)], 0.08, 2.3, rope)
        room_backs()

    # ───────────────────────── M4 ─────────────────────────
    elif key == "m4":
        conc = mat("conc", ["#16191A", "#22282A", "#30383A", "#424A4A"], [0, 0.3, 0.65, 0.9], noise=0.04)
        conc_d = mat("conc_d", ["#101314", "#1A2022", "#262E30"], [0, 0.5, 0.85])
        TW = 15.6                      # 탑 반폭 — 가운데 ±11 은 잘라 낸 단면(거점), 양옆은 남은 외벽
        poly("tower", rect(-TW, -30, TW, 5.6), 1.2, conc_d, j=0.05, seed=2)
        # 남은 외벽: 층마다 창 두 줄. 사는 층은 창 몇 개에 불, 깨진 창은 검게.
        r = random.Random(14)
        floors = [5.6, 1.6, -2.8, -7.2, -11.6, -16.0, -20.4]
        for side in (-1, 1):
            xa, xb = side * 11.2, side * TW
            x0, x1 = min(xa, xb), max(xa, xb)
            poly(f"facade{side}", rect(x0, -30, x1, 5.6), 1.0, mat("facade", ["#1A2022", "#262E30", "#343E40"], [0, 0.5, 0.85]),
                 j=0.04, seed=3 + side)
            for fi in range(len(floors) - 1):
                ztop, zbot = floors[fi], floors[fi + 1]
                for wx in (x0 + 0.5, x0 + 2.4):
                    for half in (0, 1):
                        zz = zbot + 0.5 + half * 2.0
                        roll = r.random()
                        if fi <= 1 and roll < 0.30:
                            col = "#7A5430"            # 사람이 사는 층 — 창에 희미한 불(방 안보다 어둡게)
                        elif roll < 0.25:
                            col = "#06090A"            # 깨진 창
                        else:
                            col = "#16303A" if fi < 3 else "#0C1A20"
                        poly(f"w{side}{fi}{wx}{half}", rect(wx, zz, wx + 1.4, zz + 1.6), 0.9, mat("win" + col, [col]))
        # 기둥·층 슬래브(단면)
        for x in (-TW, -11.2, -3.65, 3.65, 11.2, TW):
            ribbon(f"col{x}", [(x, -30), (x, 5.6)], 0.7, 0.4, conc)
        for f in floors:
            ribbon(f"slab{f}", [(-TW - 0.6, f), (TW + 0.6, f)], 0.6, 0.4, conc)
        # 지붕 테라스 + 아트리움 유리돔(꼭대기 = 돔)
        poly("roof", rect(-TW - 1.0, 5.6, TW + 1.0, 6.8), 0.5, mat("roofc", ["#3A4242", "#5A6262"], [0, 0.6]))
        ribbon("parapet", [(-TW - 1.0, 7.4), (TW + 1.0, 7.4)], 0.35, 0.5, mat("roofc", []))
        poly("atrium", ellipse(0.0, 6.8, 10.6, 8.0, 34, 0, math.pi), 0.6,
             mat("dglass", ["#1C3E44", "#2A5A60", "#3E7A80"], [0, 0.45, 0.85]))
        for i in range(1, 8):
            a = math.pi * i / 8
            ribbon(f"arib{i}", [(10.6 * math.cos(a), 6.8 + 8.0 * math.sin(a)), (0.0, 6.8)], 0.14, 0.55,
                   mat("drib", ["#6A5A48"]))
        for k in (0.45, 0.75):
            ribbon(f"aring{k}", ellipse(0.0, 6.8, 10.6 * k, 8.0 * k, 20, 0, math.pi), 0.12, 0.55, mat("drib", []))
        # 옥상 물탱크·부러진 안테나 — 고층 건물의 문법
        poly("tank", rect(-TW + 0.2, 6.8, -TW + 3.0, 9.6), 0.5, mat("tank", ["#3A3028", "#5A4A3A"], [0, 0.5]))
        ribbon("tank_leg", [(-TW + 0.6, 6.8), (-TW + 0.6, 7.4)], 0.2, 0.5, mat("tank", []))
        ribbon("antenna", [(TW - 2.0, 6.8), (TW - 1.6, 12.6), (TW + 0.6, 14.4)], 0.3, 0.5, mat("ant", ["#4A3E34"]))
        # 무너진 옆 건물(왼쪽) — 우리 탑에 기대어 있다, 판자 다리가 놓였다
        lean = [(-31, -24), (-24.0, -24), (-15.8, 1.0), (-18.4, 2.8), (-31, -6.0)]
        poly("lean_bldg", lean, 2.4, mat("leanb", ["#121618", "#1C2224", "#283032"], [0, 0.55, 0.88]), j=0.1, seed=12)
        for i in range(1, 7):
            t = i / 7
            p0 = (-24.0 + (-15.8 + 24.0) * t, -24 + 25.0 * t)
            ribbon(f"lean_fl{i}", [p0, (p0[0] - 7.0, p0[1] - 2.0 + 0.5 * i)], 0.3, 2.35, mat("leanfl", ["#2C3436"]))
        ribbon("bridge_plank", [(-18.0, 2.6), (-TW, 2.2)], 0.35, 0.3, mat("wood", ["#3A2A1E", "#6A5038"], [0, 0.5]))
        # 오른쪽: 부러진 철골과 늘어진 케이블
        ribbon("girder", [(TW + 0.6, -4.0), (21.0, 3.0), (25.0, 4.6)], 0.5, 1.0, mat("gird", ["#3A2420", "#5A3428"], [0, 0.5]))
        for i in range(4):
            x = TW + 1.8 + i * 1.6
            ribbon(f"gird_x{i}", [(x, -2.6 + i * 1.4), (x + 1.0, -1.6 + i * 1.4)], 0.18, 1.0, mat("gird", []))
        ribbon("cable", [(25.0, 4.6), (25.6, -2.0), (24.2, -9.0), (26.0, -18.0)], 0.1, 1.1, mat("rope", ["#5A4A3A"]))
        # 외벽 해초(창턱에서 자란다)
        km = mat("kelp", ["#1E2A16", "#2E3A1E", "#46502A"], [0, 0.5, 0.85])
        for i, (x, z, h) in enumerate([(-TW - 0.3, -11.6, 6.0), (-TW - 0.4, -2.8, 4.0), (TW + 0.3, -7.2, 5.5),
                                       (TW + 0.4, 1.6, 3.4), (-TW - 0.6, 7.0, 3.0), (TW + 0.2, -16.0, 7.0),
                                       (-TW - 0.2, -20.4, 7.5), (TW - 1.0, 7.4, 2.4)]):
            kelp(f"k{i}", x, z, h, 0.2, km, 500 + i, lean=0.1 if x > 0 else -0.1, w=0.28)
        room_backs()

    # ───────────────────────── M5 (M2+M4 혼합) ─────────────────────────
    elif key == "m5":
        X0, HW, IN = M5_X0, M5_HW, M5_IN          # 탑 중심·반폭·단면 반폭
        L_, R_ = X0 - HW, X0 + HW
        conc = mat("conc", ["#16191A", "#22282A", "#30383A", "#424A4A"], [0, 0.3, 0.65, 0.9], noise=0.04)
        conc_d = mat("conc_d", ["#101314", "#1A2022", "#262E30"], [0, 0.5, 0.85])
        # 절벽(왼쪽) — 탑이 그 끝에 기대 섰다. 절벽은 해구 바로 위에서 끝나고, 탑만 더 아래로 내려간다.
        # 절벽이 탑의 왼쪽 외벽을 감싸 쥔다(탑이 절벽 끝 홈에 기대 섰다)
        edge = [(-29.5, 16.6), (-26.4, 16.6), (-25.0, 12.4), (-22.6, 8.8), (-19.8, 6.6), (-17.4, 4.4),
                (-15.9, 1.6), (-15.6, -3.0), (-16.0, -7.6), (-15.7, -10.4), (-17.0, -12.4), (-19.2, -13.2),
                (-21.0, -12.4), (-22.8, -13.6), (-24.8, -12.6), (-26.8, -13.8), (-29.5, -12.8)]
        rock = mat("rock", ["#18130F", "#241E19", "#302922", "#3E352C"], [0, 0.3, 0.62, 0.86], noise=0.08, nscale=1.6)
        poly("cliff", edge, 0.85, rock, j=0.22, seed=11)
        r = random.Random(8)
        for i, z in enumerate([2.4, -1.8, -5.6, -9.4]):
            pts = [(-29.5, z + r.uniform(-0.4, 0.4))]
            for x in range(-27, -16, 3):
                pts.append((x, z + r.uniform(-0.5, 0.5) + (x + 29) * 0.04))
            ribbon(f"strata{i}", pts, 0.5 + r.uniform(0, 0.4), 0.8, mat("strata", ["#2E2A24", "#3A362E"], [0, 0.5]))
        cm = mat("crack", ["#0A0806"])
        for i in range(10):
            x = r.uniform(-28.5, -19.5); z = r.uniform(-10, 4); pts = [(x, z)]
            for _ in range(4):
                x += r.uniform(-1.0, 1.0); z += r.uniform(-1.6, -0.4); pts.append((x, z))
            ribbon(f"crk{i}", pts, 0.18, 0.78, cm, w1=0.04)
        ribbon("edge_rim", jag(edge[1:], amp=0.15, closed=False, seed=12), 0.6, 0.75, mat("erim", ["#3A4644", "#56625C"], [0, 0.5]))
        # 절벽 밑동에서 늘어진 덩굴 — 밑은 허공
        km = mat("kelp", ["#1E2A16", "#2E3A1E", "#46502A"], [0, 0.5, 0.85])
        for i, x in enumerate([-19.6, -22.4, -25.6, -28.4]):
            z0 = -12.6 - (i % 2) * 0.7
            pts = [(x + math.sin(t * 2.5 + i) * 0.4, z0 - t * (1.8 + i % 3)) for t in [k / 8 for k in range(9)]]
            ribbon(f"hang{i}", pts, 0.22, 0.8, km, w1=0.05)
        for i, (x, z, h, ln) in enumerate([(-21.5, 7.6, 3.6, 0.1), (-24.8, 11.8, 3.0, 0.0), (-18.6, 5.0, 2.4, 0.3)]):
            kelp(f"kc{i}", x, z, h, 0.8, km, 600 + i, lean=ln, w=0.26)
        # 바위를 판 굴 방과 탑을 잇는 짧은 통로
        poly("tunnel", rect(-21.0, -2.5, L_ + 0.2, 0.9), 0.3, mat("tunnel", ["#2A1E16", "#3A2A1E"], [0, 0.5]))
        win("tunlamp", -19.6, 0.4, 0.4, 0.4, 0.28, "#FFC870")
        # 탑 몸통 — 화면 아래로 끝없이(해구 위 어둠 속으로)
        poly("tower", rect(L_, -30, R_, 5.6), 1.2, conc_d, j=0.05, seed=2)
        floors = [5.6, 1.6, -2.8, -7.2, -11.6, -16.0, -20.4]
        for side in (-1, 1):
            xa, xb = X0 + side * IN, X0 + side * HW
            x0, x1 = min(xa, xb), max(xa, xb)
            poly(f"facade{side}", rect(x0, -30, x1, 5.6), 1.0, mat("facade", ["#1A2022", "#262E30", "#343E40"], [0, 0.5, 0.85]),
                 j=0.04, seed=3 + side)
            for fi in range(len(floors) - 1):
                zbot = floors[fi + 1]
                for wx in (x0 + 0.3, x0 + 1.75):
                    for half in (0, 1):
                        zz = zbot + 0.5 + half * 2.0
                        roll = r.random()
                        if fi <= 1 and roll < 0.30:
                            col = "#5A4026"
                        elif roll < 0.25:
                            col = "#06090A"
                        else:
                            col = "#16303A" if fi < 3 else "#0C1A20"
                        poly(f"w{side}{fi}{wx}{half}", rect(wx, zz, wx + 1.2, zz + 1.6), 0.9, mat("win" + col, [col]))
        for x in (L_, X0 - IN, X0 - 3.65, X0 + 3.65, X0 + IN, R_):
            ribbon(f"col{x}", [(x, -30), (x, 5.6)], 0.7, 0.4, conc)
        for f in floors:
            ribbon(f"slab{f}", [(L_ - 0.6, f), (R_ + 0.6, f)], 0.6, 0.4, conc)
        # 지붕 + 아트리움 유리돔
        poly("roof", rect(L_ - 1.0, 5.6, R_ + 1.0, 6.8), 0.5, mat("roofc", ["#3A4242", "#5A6262"], [0, 0.6]))
        ribbon("parapet", [(L_ - 1.0, 7.4), (R_ + 1.0, 7.4)], 0.35, 0.5, mat("roofc", []))
        poly("atrium", ellipse(X0, 6.8, 10.2, 7.8, 34, 0, math.pi), 0.6,
             mat("dglass", ["#1C3E44", "#2A5A60", "#3E7A80"], [0, 0.45, 0.85]))
        for i in range(1, 8):
            a = math.pi * i / 8
            ribbon(f"arib{i}", [(X0 + 10.2 * math.cos(a), 6.8 + 7.8 * math.sin(a)), (X0, 6.8)], 0.14, 0.55,
                   mat("drib", ["#6A5A48"]))
        for k in (0.45, 0.75):
            ribbon(f"aring{k}", ellipse(X0, 6.8, 10.2 * k, 7.8 * k, 20, 0, math.pi), 0.12, 0.55, mat("drib", []))
        # 지붕 오른쪽 끝에서 심연으로 내민 부러진 철골 + 유인 등불(위협이 오는 쪽으로 빛을 건다)
        ribbon("girder", [(R_ - 0.6, 6.6), (14.0, 10.0), (20.4, 9.4)], 0.5, 0.45, mat("gird", ["#3A2420", "#5A3428"], [0, 0.5]))
        for i in range(5):
            x = R_ + 0.8 + i * 1.9
            zt = 6.8 + min(3.2, (x - R_) * 0.7)
            ribbon(f"gird_x{i}", [(x, zt - 0.4), (x + 1.0, zt + 0.5)], 0.16, 0.45, mat("gird", []))
        ribbon("lure_rope", [(20.4, 9.4), (20.5, 4.0), (20.4, -0.6)], 0.07, 0.45, mat("rope", ["#8A7A60"]))
        poly("lure_cage", ellipse(20.4, -1.0, 0.38, 0.46, 12), 0.44, mat("lure", ["#E8B060"]))
        ribbon("antenna", [(L_ + 2.0, 6.8), (L_ + 1.6, 12.4), (L_ + 3.0, 13.8)], 0.3, 0.5, mat("ant", ["#4A3E34"]))
        # 외벽 해초(심연 쪽 창턱에서 자란다)
        for i, (x, z, h) in enumerate([(R_ + 0.3, -7.2, 5.5), (R_ + 0.4, 1.6, 3.4), (R_ + 0.2, -16.0, 7.0),
                                       (R_ - 1.0, 7.4, 2.4)]):
            kelp(f"k{i}", x, z, h, 0.2, km, 500 + i, lean=0.12, w=0.28)
        room_backs()

    # ── 손그림 선 (blender_section F6 와 같은 처방, 독립 구현) ──
    sc.render.use_freestyle = True
    sc.render.line_thickness = 1.0
    vl = sc.view_layers[0]; vl.use_freestyle = True
    fs = vl.freestyle_settings
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("relic")
    ls.select_silhouette = ls.select_crease = ls.select_border = True
    fs.crease_angle = math.radians(152.0)
    ls.select_by_collection = True; ls.collection = noline; ls.collection_negation = 'EXCLUSIVE'
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("relic_ls")
    st = ls.linestyle
    st.color = lin(PAL["char"]); st.thickness = 3.4
    mo = st.thickness_modifiers.new(name="th_noise", type='NOISE')
    mo.amplitude, mo.period, mo.seed = 2.0, 22, 3
    g1 = st.geometry_modifiers.new(name="g_perlin", type='PERLIN_NOISE_2D')
    g1.amplitude, g1.frequency, g1.octaves, g1.seed = 2.2, 2.0, 3, 7
    g2 = st.geometry_modifiers.new(name="g_sin", type='SINUS_DISPLACEMENT')
    g2.wavelength, g2.amplitude, g2.phase = 40.0, 1.1, 0.4

    # ── 카메라·렌더 ──
    cx, cz = sc_data["cx"], sc_data["cz"]
    bpy.ops.object.camera_add(location=(cx, -100.0, cz))
    cam = bpy.context.object; cam.data.type = 'ORTHO'; cam.data.ortho_scale = ORTHO
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.clip_start, cam.data.clip_end = 0.1, 300.0
    sc.camera = cam
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = W2, H2
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    try:
        sc.eevee.taa_render_samples = 16
    except Exception:
        pass
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = 0.0
    sc.render.filepath = os.path.join(RAW, f"_{key}_mid.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", sc.render.filepath, flush=True)


# ══════════════════════════════════════════════════════════════════════════════
#  2단계 — 합성 (일반 파이썬 + PIL)
# ══════════════════════════════════════════════════════════════════════════════
def _post(key):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageChops

    S = SCENES[key]()
    CX, CZ = S["cx"], S["cz"]
    rng = random.Random(1000 + int(key[1]))

    def P(x, z):
        return (W2 / 2 + (x - CX) * PPM, H2 / 2 - (z - CZ) * PPM)

    def hexrgb(h):
        h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def lerp(a, b, t):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    # ── 1. 물 그라데이션 (청록 → 검정) ──
    stops = {
        "m1": [(0.0, "#2C7484"), (0.22, "#16505E"), (0.5, "#0B2A34"), (0.78, "#041218"), (1.0, "#010406")],
        "m2": [(0.0, "#2A7080"), (0.25, "#154A58"), (0.5, "#0A2630"), (0.75, "#030E13"), (1.0, "#000000")],
        "m3": [(0.0, "#1E5A68"), (0.3, "#103C48"), (0.6, "#08222A"), (1.0, "#02080B")],
        "m4": [(0.0, "#2E7888"), (0.25, "#185262"), (0.55, "#0A2A34"), (0.8, "#03111A"), (1.0, "#000203")],
        "m5": [(0.0, "#2A7080"), (0.25, "#154A58"), (0.5, "#0A2630"), (0.75, "#030E13"), (1.0, "#000000")],
    }[key]
    ys = np.linspace(0, 1, H2)
    col = np.zeros((H2, 3))
    for c in range(3):
        col[:, c] = np.interp(ys, [s[0] for s in stops], [hexrgb(s[1])[c] for s in stops])
    bg = np.repeat(col[:, None, :], W2, axis=1)
    if key in ("m2", "m5"):   # 오른쪽 아래 = 해구: 더 빨리 검어진다
        xx = np.linspace(0, 1, W2)[None, :]; yy = ys[:, None]
        dark = np.clip((xx - 0.45) * 1.6, 0, 1) * np.clip((yy - 0.35) * 1.8, 0, 1)
        bg *= (1 - 0.85 * dark)[..., None]
    if key == "m1":   # 오른쪽 아래(뱃머리 방향)가 해구
        xx = np.linspace(0, 1, W2)[None, :]; yy = ys[:, None]
        dark = np.clip((xx - 0.55) * 1.8, 0, 1) * np.clip((yy - 0.45) * 2.0, 0, 1)
        bg *= (1 - 0.8 * dark)[..., None]
    img = Image.fromarray(bg.astype("uint8"), "RGB").convert("RGBA")

    def layer():
        return Image.new("RGBA", (W2, H2), (0, 0, 0, 0))

    def over(base, top):
        return Image.alpha_composite(base, top)

    def screen(base, top_rgb_layer, strength=1.0):
        """가산(screen) 합성 — 빛기둥·등불 번짐"""
        b = np.asarray(base).astype(np.float32) / 255
        t = np.asarray(top_rgb_layer).astype(np.float32) / 255
        a = t[..., 3:4] * strength
        c = t[..., :3] * a
        out = 1 - (1 - b[..., :3]) * (1 - c)
        res = np.concatenate([out, b[..., 3:4]], axis=-1)
        return Image.fromarray((np.clip(res, 0, 1) * 255).astype("uint8"), "RGBA")

    def water_at(px, py):
        return tuple(int(v) for v in bg[int(min(H2 - 1, max(0, py))), int(min(W2 - 1, max(0, px)))])

    # ── 2. 먼 실루엣(안개 속) — 장소가 '어디'인지 ──
    def far(polys_world, rgb, blur, alpha=255):
        L = layer(); d = ImageDraw.Draw(L)
        for pts in polys_world:
            d.polygon([P(*p) for p in pts], fill=(*rgb, alpha))
        return L.filter(ImageFilter.GaussianBlur(blur))

    def jag_line(x0, x1, base_z, amp, step, seed, bottom=-40):
        r = random.Random(seed); pts = []
        x = x0
        while x <= x1:
            pts.append((x, base_z + r.uniform(-amp, amp))); x += step * r.uniform(0.6, 1.4)
        return pts + [(x1, bottom), (x0, bottom)]

    if key == "m1":
        img = over(img, far([jag_line(-40, 40, -4.0, 1.4, 3.0, 1)], (16, 46, 54), 6))
        # 멀리 가라앉은 다른 배(쌍둥이 실루엣) — 이 바다는 배 무덤이다
        img = over(img, far([[(14, 2.0), (30, -0.5), (31, 1.2), (29, 3.4), (15, 4.4)],
                             [(18, 4.4), (21, 4.4), (21, 7.4), (18.6, 7.4)]], (18, 52, 62), 4))
        img = over(img, far([jag_line(-40, 40, -9.0, 1.0, 2.2, 2)], (12, 34, 40), 3))
    elif key == "m2":
        # 해구 건너편 절벽(아주 먼)과 심연 바닥 없는 어둠
        img = over(img, far([[(18, 20), (31, 20), (31, -30), (22, -30), (24, -10), (20, -2), (23, 6), (19, 12)]],
                            (14, 42, 50), 8))
        img = over(img, far([[(26, 20), (31, 20), (31, -30), (28, -30), (29, -6), (26.5, 6)]], (10, 30, 36), 4))
        img = over(img, far([jag_line(-40, 0, 13.0, 1.6, 2.8, 3)], (20, 60, 70), 6))
    elif key == "m3":
        img = over(img, far([jag_line(-40, 40, -6.5, 2.2, 4.0, 4)], (14, 40, 48), 7))
        # 먼 데의 또 다른 뼈(다른 고래) — 아치 둘
        L = layer(); d = ImageDraw.Draw(L)
        for i, x in enumerate([18, 21, 24]):
            pts = [P(x + math.sin(t * 1.4) * 1.5 * t, -6 + t * 7) for t in [k / 10 for k in range(11)]]
            d.line(pts, fill=(30, 66, 72, 255), width=14)
        img = over(img, L.filter(ImageFilter.GaussianBlur(4)))
        img = over(img, far([jag_line(-40, 40, -9.5, 1.0, 2.0, 5)], (11, 30, 36), 3))
    elif key == "m5":
        # 3막 스포일러 방지: 도시 스카이라인 없음. 아주 먼 데 무언가 서 있던 흔적 둘만, 물빛에 거의 녹아서.
        img = over(img, far([[(22, -30), (24.6, -30), (24.6, 3.0), (23.6, 4.2), (22, 2.6)],
                             [(27.0, -30), (29.5, -30), (29.5, -2.0), (27.0, -1.0)]], (18, 50, 60), 12, alpha=150))
        img = over(img, far([[(25, 20), (31, 20), (31, -30), (27, -30), (28.5, -8), (26.0, 4)]], (12, 34, 40), 9, alpha=170))
    elif key == "m4":
        # 수몰 도시 스카이라인 — 세 겹(먼 것일수록 물빛에 녹는다)
        r = random.Random(7)
        for depth, (rgb, blur, base, hmax) in enumerate([((22, 64, 76), 9, -6, 18), ((16, 46, 56), 5, -10, 13),
                                                         ((11, 32, 40), 2.5, -14, 9)]):
            polys = []
            x = -34
            while x < 34:
                w = r.uniform(3, 7); h = r.uniform(4, hmax)
                if abs(x + w / 2) < 14 and depth == 2:
                    x += w + 1; continue
                top = base + h
                if r.random() < 0.35:   # 부러진 꼭대기
                    polys.append([(x, base - 30), (x + w, base - 30), (x + w, top - r.uniform(1, 3)), (x + w * 0.4, top),
                                  (x, top - 1)])
                else:
                    polys.append([(x, base - 30), (x + w, base - 30), (x + w, top), (x, top)])
                x += w + r.uniform(0.6, 3.0)
            img = over(img, far(polys, rgb, blur))

    # ── 3. 위에서 내려오는 희미한 빛기둥 ──
    L = layer(); d = ImageDraw.Draw(L)
    for i in range(6):
        x0 = rng.uniform(0.05, 0.95) * W2; w0 = rng.uniform(60, 160); dx = rng.uniform(-260, 120)
        h = rng.uniform(0.5, 0.85) * H2
        d.polygon([(x0 - w0, -10), (x0 + w0, -10), (x0 + dx + w0 * 1.9, h), (x0 + dx - w0 * 1.9, h)],
                  fill=(120, 200, 205, int(rng.uniform(22, 40))))
    L = L.filter(ImageFilter.GaussianBlur(40))
    fade = Image.linear_gradient("L").resize((W2, H2)).point(lambda v: 255 - v)
    L.putalpha(ImageChops.multiply(L.getchannel("A"), fade))
    img = screen(img, L, 1.0)

    # ── 4. 멀리 지나가는 큰 것의 실루엣 (static/art/threats 재사용) ──
    def threat(name, cx_, cy_, width, alpha=0.55, flip=False, tint=None):
        im = Image.open(os.path.join(ART, "threats", name)).convert("RGBA")
        bb = im.getchannel("A").point(lambda v: 255 if v > 18 else 0).getbbox()
        if bb:
            im = im.crop(bb)
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        hgt = int(im.height * width / im.width)
        im = im.resize((int(width), max(1, hgt)), Image.LANCZOS)
        wr = tint or tuple(int(v * 0.32) for v in water_at(cx_, cy_))
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        sil = Image.new("RGBA", im.size, (*wr, 0)); sil.putalpha(a)
        L = layer(); L.paste(sil, (int(cx_ - im.width / 2), int(cy_ - hgt / 2)), sil)
        return L.filter(ImageFilter.GaussianBlur(2))

    def leviathan(cx_, cy_, length, facing=1, alpha=0.75, tint=None):
        """먼 데를 지나가는 큰 것 — 방추형 몸 + 꼬리 + 가슴지느러미. 몸만, 얼굴 없음."""
        L = layer(); d = ImageDraw.Draw(L)
        wr = tint or tuple(int(v * 0.32) for v in water_at(cx_, cy_))
        top, bot = [], []
        n = 40
        for i in range(n + 1):
            t = i / n
            x = cx_ + facing * (t - 0.5) * length
            th = math.sin(math.pi * min(1, t * 1.15) ** 0.8) * length * 0.075 * (1 - 0.6 * t)
            yc = cy_ + math.sin(t * 3.0) * length * 0.02
            top.append((x, yc - th)); bot.append((x, yc + th * 0.85))
        tail_x = cx_ - facing * 0.5 * length
        body = top + bot[::-1]
        d.polygon(body, fill=(*wr, int(255 * alpha)))
        tx = cx_ - facing * (0.5 * length)
        tyc = cy_ + math.sin(3.0) * length * 0.02
        d.polygon([(tx + facing * length * 0.04, tyc), (tx - facing * length * 0.09, tyc - length * 0.09),
                   (tx - facing * length * 0.05, tyc), (tx - facing * length * 0.09, tyc + length * 0.07)],
                  fill=(*wr, int(255 * alpha)))
        fx_ = cx_ + facing * length * 0.12
        d.polygon([(fx_, cy_ + length * 0.03), (fx_ - facing * length * 0.14, cy_ + length * 0.13),
                   (fx_ - facing * length * 0.04, cy_ + length * 0.04)], fill=(*wr, int(255 * alpha)))
        return L.filter(ImageFilter.GaussianBlur(3))

    def eyes(pts, r=9):
        """어둠 속 큰 것: 몸은 안 보이고 눈만 — 먼 위협의 첫 신호"""
        L = layer(); d = ImageDraw.Draw(L)
        for x_, y_ in pts:
            d.ellipse([x_ - r, y_ - r, x_ + r, y_ + r], fill=(200, 240, 220, 230))
        return L

    big = {
        "m1": [("LEVIATHAN", 2500, 520, 1300, 0.7, True), ("threat_longneck_near.png", 2950, 1620, 900, 0.6, False)],
        "m2": [("LEVIATHAN", 2500, 820, 1600, 0.75, True), ("threat_longneck_near.png", 2700, 1560, 1100, 0.65, False),
               ("threat_needle_far.png", 2050, 1560, 420, 0.5, False)],
        "m3": [("LEVIATHAN", 900, 300, 1200, 0.55, False), ("threat_longneck_near.png", 3000, 820, 700, 0.4, False)],
        "m5": [("LEVIATHAN", 2750, 820, 1150, 0.72, True), ("threat_longneck_near.png", 2900, 1560, 950, 0.6, False)],
        "m4": [("LEVIATHAN", 2650, 470, 1300, 0.6, True), ("threat_longneck_near.png", 380, 1350, 800, 0.45, True)],
    }[key]
    for nm, x_, y_, w_, a_, fl in big:
        if nm == "LEVIATHAN":
            img = over(img, leviathan(x_, y_, w_, -1 if fl else 1, a_))
        else:
            img = over(img, threat(nm, x_, y_, w_, a_, fl))
    eye_pts = {"m1": [(3010, 1560), (3040, 1566), (2350, 1680)], "m2": [(2600, 1420), (2632, 1428), (2950, 1700), (2200, 1740)],
               "m3": [(3080, 1640), (3104, 1646)], "m4": [(2900, 1640), (2930, 1646), (420, 1700)],
               "m5": [(2600, 1430), (2632, 1438), (3000, 1700), (2300, 1740)]}[key]
    E = eyes(eye_pts)
    img = screen(img, E.filter(ImageFilter.GaussianBlur(9)), 1.0); img = over(img, E)

    # 해파리(희미하게 빛나는 우산) — 깊은 쪽
    def jelly(L, x, y, r, rgb, a):
        d = ImageDraw.Draw(L)
        d.pieslice([x - r, y - r, x + r, y + r], 180, 360, fill=(*rgb, a))
        for k in range(5):
            tx = x - r * 0.7 + k * r * 0.35
            d.line([(tx, y), (tx + math.sin(k) * 6, y + r * 1.4), (tx - 4, y + r * 2.4)], fill=(*rgb, a // 2), width=3)
    L = layer()
    jel = {"m1": [(2300, 1150, 26), (2700, 1300, 18), (1800, 1350, 14)],
           "m2": [(2200, 1100, 30), (2550, 1250, 20), (2850, 1050, 16), (2400, 1500, 22), (1900, 1650, 14)],
           "m3": [(600, 900, 22), (2900, 600, 18), (2700, 900, 26), (1400, 380, 14)],
           "m4": [(2700, 1200, 26), (450, 900, 20), (2950, 1500, 16), (300, 1550, 18)],
           "m5": [(2450, 1180, 28), (2800, 1300, 20), (3050, 1060, 16), (2600, 1520, 22), (2250, 1650, 14)]}[key]
    for x, y, r in jel:
        jelly(L, x, y, r, (140, 230, 225), 120)
    glow = L.filter(ImageFilter.GaussianBlur(14))
    img = screen(img, glow, 1.0); img = over(img, L)

    # ── 5. 중간 물고기 떼(먼 것은 어둡게, 빛 받는 것은 은빛) ──
    def fish(d, x, y, ang, s, rgb, a):
        c, sn = math.cos(ang), math.sin(ang)
        def R(px, py):
            return (x + px * c - py * sn, y + px * sn + py * c)
        body = [R(s, 0), R(s * 0.3, -s * 0.38), R(-s * 0.6, -s * 0.2), R(-s, -s * 0.45), R(-s * 0.85, 0),
                R(-s, s * 0.45), R(-s * 0.6, s * 0.2), R(s * 0.3, s * 0.38)]
        d.polygon(body, fill=(*rgb, a))

    def shoal(L, path, n, spread, size, rgb, a, seed):
        d = ImageDraw.Draw(L); r = random.Random(seed)
        for i in range(n):
            t = r.random()
            # 2차 베지에
            (x0, y0), (x1, y1), (x2, y2) = path
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t * t * x2
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t * t * y2
            tx = 2 * (1 - t) * (x1 - x0) + 2 * t * (x2 - x1); ty = 2 * (1 - t) * (y1 - y0) + 2 * t * (y2 - y1)
            ang = math.atan2(ty, tx)
            ox, oy = r.gauss(0, spread), r.gauss(0, spread * 0.45)
            fish(d, x + ox, y + oy, ang + r.uniform(-0.15, 0.15), size * r.uniform(0.7, 1.2), rgb, a)

    SHOALS = {
        "m1": [(((1700, 260), (2300, 120), (3100, 300)), 90, 70, 16, (150, 200, 200), 150),
               (((1250, 120), (1650, 40), (2000, 200)), 50, 50, 12, (120, 175, 180), 120),
               (((2550, 1250), (2850, 1120), (3200, 1300)), 60, 45, 13, (16, 30, 34), 200)],
        "m2": [(((1900, 380), (2600, 160), (3200, 520)), 140, 90, 16, (150, 205, 205), 160),
               (((1850, 1200), (2300, 980), (2950, 1300)), 80, 60, 13, (12, 22, 26), 210),
               (((2200, 650), (2500, 760), (2900, 600)), 40, 40, 10, (120, 180, 185), 120)],
        "m3": [(((900, 300), (1600, 80), (2400, 260)), 160, 110, 15, (150, 200, 200), 150),
               (((1150, 520), (1650, 420), (2050, 620)), 70, 70, 11, (190, 170, 120), 150),
               (((2600, 300), (2900, 420), (3200, 300)), 40, 50, 12, (120, 170, 175), 120)],
        "m5": [(((2200, 300), (2700, 120), (3200, 380)), 140, 90, 16, (150, 205, 205), 160),
               (((2250, 1150), (2600, 980), (3150, 1250)), 80, 60, 13, (12, 22, 26), 210),
               (((2350, 600), (2650, 700), (3050, 560)), 45, 40, 10, (120, 180, 185), 120)],
        "m4": [(((300, 200), (1200, 0), (2200, 220)), 140, 100, 15, (150, 205, 205), 150),
               (((2300, 650), (2800, 520), (3200, 760)), 70, 60, 13, (130, 185, 188), 140),
               (((200, 700), (500, 820), (900, 760)), 50, 45, 12, (14, 26, 30), 200)],
    }[key]
    L = layer()
    for path, n, sp, sz, rgb, a in SHOALS:
        shoal(L, path, n, sp, sz, rgb, a, n + sz)
    img = over(img, L.filter(ImageFilter.GaussianBlur(0.8)))

    # ── 6. Blender 구조물 ──
    mid_p = os.path.join(RAW, f"_{key}_mid.png")
    mid = Image.open(mid_p).convert("RGBA")
    # 찬물이 구조물에 내려앉는다: 위쪽 가장자리만 청록을 아주 얇게 섞는다
    img = over(img, mid)

    # ── 7. 등불 번짐 → 플레이트 ──
    rooms = S["rooms"]
    halo = layer(); d = ImageDraw.Draw(halo)
    hk = {"m1": 1.0, "m2": 0.55, "m3": 0.85, "m4": 0.7, "m5": 0.65}[key]
    for i, (x, zf, k, s) in enumerate(rooms):
        l, b, r_, t = slot_rect(x, zf)
        (pl, pt), (pr, pb) = P(l, t), P(r_, b)
        if s in ("lit", "pump"):
            pad = 200 if i == len(rooms) - 1 else 130     # 돔(맨 끝 방)은 더 넓게 — 화면의 주인공
            a8 = int((150 if i == len(rooms) - 1 else 120) * (hk if i != len(rooms) - 1 else 1.0) * (1 if s == "lit" else 0.6))
            d.ellipse([pl - pad, pt - pad * 0.9, pr + pad, pb + pad], fill=(255, 170, 70, a8))
    img = screen(img, halo.filter(ImageFilter.GaussianBlur(70)), 1.0)

    plate_cache = {}

    def plate(kind, state):
        kk = (kind, state)
        if kk in plate_cache:
            return plate_cache[kk]
        sfx = "lit" if state in ("lit",) else "dark"
        im = Image.open(os.path.join(ART, "plates", f"room_plate_{kind}_{sfx}.png")).convert("RGBA").crop(PLATE_CROP)
        if state in ("flood", "pump"):
            fl = Image.open(os.path.join(ART, "plates", "room_flood.png")).convert("RGBA").crop(PLATE_CROP)
            if state == "pump":    # 물을 빼는 중: 수면이 아래쪽 1/3 로 내려갔다
                fl = fl.crop((0, 0, fl.width, fl.height)).transform(fl.size, Image.AFFINE, (1, 0, 0, 0, 1, -int(fl.height * 0.32)))
                base = Image.open(os.path.join(ART, "plates", f"room_plate_{kind}_lit.png")).convert("RGBA").crop(PLATE_CROP)
                base = Image.blend(base, im, 0.45)
                im = Image.alpha_composite(base, fl)
            else:
                arr = np.asarray(im).astype(np.float32)
                arr[..., :3] *= np.array([0.35, 0.55, 0.62])     # 물에 잠긴 칸: 청록으로 식는다
                im = Image.alpha_composite(Image.fromarray(arr.astype("uint8"), "RGBA"), fl)
                fl2 = np.asarray(im).astype(np.float32)
                ys_ = np.linspace(0, 1, im.height)[:, None]
                fl2[..., :3] *= (0.55 + 0.25 * (1 - ys_))[..., None]
                im = Image.fromarray(np.clip(fl2, 0, 255).astype("uint8"), "RGBA")
        elif state == "dark":
            arr = np.asarray(im).astype(np.float32); arr[..., :3] *= 0.7
            im = Image.fromarray(arr.astype("uint8"), "RGBA")
        w = round(im.width * PPM / PLATE_PPM); h = round(im.height * PPM / PLATE_PPM)
        im = im.resize((w, h), Image.LANCZOS)
        plate_cache[kk] = im
        return im

    L = layer(); d = ImageDraw.Draw(L)
    for i, (x, zf, k, s) in enumerate(rooms):
        l, b, r_, t = slot_rect(x, zf)
        pl, pt = P(l, t); pr, pb = P(r_, b)
        if s == "plan":
            # 아직 안 지은 자리: 분필 점선 + 가운데 '+'
            dash, gap = 26, 18
            for (ax, ay), (bx_, by_) in (((pl, pt), (pr, pt)), ((pr, pt), (pr, pb)), ((pr, pb), (pl, pb)), ((pl, pb), (pl, pt))):
                ln = math.hypot(bx_ - ax, by_ - ay); n = int(ln / (dash + gap))
                for j in range(n + 1):
                    t0 = j * (dash + gap) / ln; t1 = min(1, t0 + dash / ln)
                    d.line([(ax + (bx_ - ax) * t0, ay + (by_ - ay) * t0), (ax + (bx_ - ax) * t1, ay + (by_ - ay) * t1)],
                           fill=(232, 220, 191, 120), width=5)
            cxp, cyp = (pl + pr) / 2, (pt + pb) / 2
            d.line([(cxp - 26, cyp), (cxp + 26, cyp)], fill=(232, 220, 191, 150), width=7)
            d.line([(cxp, cyp - 26), (cxp, cyp + 26)], fill=(232, 220, 191, 150), width=7)
            continue
        im = plate(k, s)
        img.paste(im, (int(round(pl)), int(round(pt))), im)
    img = over(img, L)

    # ── 7.5 아래로 갈수록 어둠이 구조물까지 삼킨다(더 깊은 곳 = 아직 못 간 곳) ──
    fade = {"m5": (-5.0, -16.4, 0.8), "m2": (-9.0, -17.0, 0.55), "m4": (-6.0, -16.4, 0.72)}.get(key)
    if fade:
        z0, z1, st_ = fade
        arr = np.asarray(img).astype(np.float32)
        zs = CZ + (H2 / 2 - np.arange(H2)) / PPM
        f = 1 - st_ * np.clip((z0 - zs) / (z0 - z1), 0, 1)
        arr[..., :3] *= f[:, None, None]
        img = Image.fromarray(arr.astype("uint8"), "RGBA")

    # ── 8. 바위 속 광맥·유물 반짝임(M2: 땅이 지도다) / 기포 / 부유물 / 바다눈 ──
    L = layer(); d = ImageDraw.Draw(L)
    if key == "m2":
        r = random.Random(3)
        for _ in range(9):
            x = r.uniform(-27, -6); z = r.uniform(-12.3, -11.9)
            px, py = P(x, z)
            d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(244, 190, 100, 190))
        for x, z in [(-23.2, -12.2), (-25.0, 6.0), (-21.4, 11.0)]:
            px, py = P(x, z); d.ellipse([px - 12, py - 12, px + 12, py + 12], fill=(250, 210, 130, 230))
    # 가장 깊은 곳의 희미한 불빛 하나 — "저 아래 뭔가 있다"
    deep_pts = {"m1": [(26.0, -15.8)], "m2": [(-9.5, -16.0)], "m3": [(18.6, -14.4)], "m4": [(3.5, -15.0)], "m5": [(12.0, -15.2)]}[key]
    for x, z in deep_pts:
        px, py = P(x, z); d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(255, 200, 120, 255))
    if key == "m5":     # 유인 등불 — 심연 쪽에 건 빛. 방 다음으로 밝다
        G = layer(); dg = ImageDraw.Draw(G)
        px, py = P(20.4, -1.1)
        dg.ellipse([px - 120, py - 120, px + 120, py + 120], fill=(255, 190, 100, 85))
        img = screen(img, G.filter(ImageFilter.GaussianBlur(60)), 1.0)
    glow = L.filter(ImageFilter.GaussianBlur(10))
    img = screen(img, glow, 1.0); img = over(img, L)

    # 바다눈 + 기포 + 부유 잔해
    L = layer(); d = ImageDraw.Draw(L)
    r = random.Random(11)
    for _ in range(900):
        x = r.uniform(0, W2); y = r.uniform(0, H2); s = r.choice([2, 2, 3, 4])
        d.ellipse([x, y, x + s, y + s], fill=(200, 225, 220, r.randint(40, 120)))
    for _ in range(18):    # 떠다니는 쓰레기 조각(병, 판자, 비닐)
        x = r.uniform(0, W2); y = r.uniform(80, H2 * 0.75); s = r.uniform(10, 26); a = r.uniform(0, 3.14)
        pts = [(x + math.cos(a + k * 1.57) * s * (1 if k % 2 else 0.45), y + math.sin(a + k * 1.57) * s * (1 if k % 2 else 0.45)) for k in range(4)]
        d.polygon(pts, fill=(*lerp(water_at(x, y), (0, 0, 0), 0.5), 210))
    bub_src = {"m1": [(-15.0, 15.4), (5.2, 9.0), (21.0, 0.6)], "m2": [(-8.6, 14.2), (-4.4, 7.4)],
               "m3": [(13.4, 0.6), (-1.5, 3.4)], "m4": [(0.0, 14.8), (-7.3, 6.0), (7.3, 6.0)], "m5": [(-4.6, 14.6), (20.4, -0.4)]}[key]
    for bx, bz in bub_src:
        px, py = P(bx, bz)
        for j in range(16):
            yy = py - j * r.uniform(22, 38); xx = px + math.sin(j * 0.9) * 14 + r.uniform(-6, 6); s = r.uniform(4, 10)
            d.ellipse([xx - s, yy - s, xx + s, yy + s], outline=(190, 235, 230, 150), width=2)
    img = over(img, L)

    # ── 9. M3: 뼈 위 작은 생물(게·불가사리) + 우리 문어 ──
    if key == "m3":
        L = layer(); d = ImageDraw.Draw(L); r = random.Random(4)
        for _ in range(40):
            x = r.choice([r.uniform(-29, -20), r.uniform(5, 29), r.uniform(-19, 4)])
            z = r.choice([-10.6, -9.0, -8.3, -4.0, -3.2, -6.2])
            px, py = P(x, z)
            if r.random() < 0.6:   # 게
                d.ellipse([px - 9, py - 6, px + 9, py + 6], fill=(170, 70, 50, 255))
                for k in (-1, 1):
                    for j in range(3):
                        d.line([(px + k * 6, py + 2), (px + k * (12 + j * 3), py + 6 + j * 2)], fill=(140, 55, 40, 255), width=2)
            else:                  # 흰 박테리아 매트·조개
                d.ellipse([px - 14, py - 5, px + 14, py + 5], fill=(220, 214, 190, 170))
        img = over(img, L)

    # ── 10. 앞쪽 해초(화면 가장자리, 어둡고 흐릿하게 — 깊이) ──
    L = layer(); d = ImageDraw.Draw(L); r = random.Random(21 + int(key[1]))
    fg = {"m5": [(3140, 4)], "m1": [(80, 6), (3120, 3)], "m2": [(60, 5), (1500, 2)], "m3": [(70, 4), (3150, 5)], "m4": [(90, 4), (3100, 4)]}[key]
    for bx, n in fg:
        for i in range(n):
            x = bx + r.uniform(-90, 90); h = r.uniform(380, 820); ph = r.uniform(0, 6)
            pts = [(x + math.sin(ph + t * 4) * 40 * t, H2 + 20 - t * h) for t in [k / 20 for k in range(21)]]
            for j in range(len(pts) - 1):
                w = int(30 * (1 - j / 20) + 6)
                d.line([pts[j], pts[j + 1]], fill=(6, 14, 12, 235), width=w)
    img = over(img, L.filter(ImageFilter.GaussianBlur(5)))

    # ── 11. 종이 결 + 비네트 ──
    arr = np.asarray(img).astype(np.float32)
    nrng = np.random.default_rng(7)
    small = nrng.normal(0, 1, (H2 // 8, W2 // 8)).astype(np.float32)
    grain = np.asarray(Image.fromarray(((small * 18) + 128).clip(0, 255).astype("uint8")).resize((W2, H2), Image.BICUBIC)).astype(np.float32)
    grain = (grain - 128) / 128 * 0.06
    fine = nrng.normal(0, 0.025, (H2, W2)).astype(np.float32)
    arr[..., :3] *= (1 + grain + fine)[..., None]
    yy, xx = np.mgrid[0:H2, 0:W2].astype(np.float32)
    v = ((xx / W2 - 0.5) ** 2 * 1.2 + (yy / H2 - 0.5) ** 2) ** 0.5
    arr[..., :3] *= (1 - np.clip(v - 0.32, 0, 1) * 0.85)[..., None]
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGBA").convert("RGB")

    # ── 12. 사람(도트 — 정수 배율, 최근접) ──
    rows = {"idle": 0, "walk": 1, "work": 2, "sit": 3, "carry": 4}
    sheets = {}

    def cell(role, pose, frame=0):
        if role not in sheets:
            sheets[role] = Image.open(os.path.join(ART, "chars", "front", "p2", "src", f"{role}.png")).convert("RGBA")
        sh = sheets[role]
        c = sh.crop((frame * 64, rows[pose] * 64, frame * 64 + 64, rows[pose] * 64 + 64))
        # 등불색을 받는다(2.5D 조건 ②): 따뜻하게 살짝 곱한다
        a = np.asarray(c).astype(np.float32)
        a[..., :3] *= np.array([1.0, 0.93, 0.80]) * 0.96 + 0.04
        return Image.fromarray(np.clip(a, 0, 255).astype("uint8"), "RGBA")

    actors = []   # (x세계, z바닥, role, pose, frame)
    for ri, lst in S["people"].items():
        x, zf, k, s = rooms[ri]
        for j, (role, off, pose) in enumerate(lst):
            actors.append((x + off, zf, role, pose, (ri + j) % 2))
    if key == "m3":
        actors.append(("octo", None, None, None, None))

    def paste_actors(im, scale, origin=(0, 0), canvas_scale=1.0):
        d = ImageDraw.Draw(im, "RGBA")
        for a in actors:
            if a[0] == "octo":
                oc = Image.open(os.path.join(ART, "chars", "front", "p2", "src", "octopus.png")).convert("RGBA").crop((0, 0, 64, 64))
                px, py = P(-5.0, 3.3)
            else:
                x, zf, role, pose, fr = a
                oc = cell(role, pose, fr)
                px, py = P(x, zf)
            px = px * canvas_scale - origin[0]; py = py * canvas_scale - origin[1]
            if not (-80 < px < im.width + 80 and -80 < py < im.height + 80):
                continue
            sp = oc.resize((64 * scale, 64 * scale), Image.NEAREST)
            d.ellipse([px - 11 * scale, py - 2 * scale, px + 11 * scale, py + 2 * scale], fill=(20, 12, 6, 120))
            im.paste(sp, (int(round(px - 32 * scale)), int(round(py - 60 * scale))), sp)

    hero = canvas.reduce(2)
    paste_actors(hero, 1, canvas_scale=0.5)
    hero.save(os.path.join(RAW, f"{key}_hero.png"))
    # 폰 가로(844×390) — 거점 중심 크롭. 2x 판은 캔버스에서 바로(캐릭터 ×2)
    crop_c = {"m1": (-4.0, 3.5), "m2": (3.0, 1.0), "m3": (-1.0, -2.0), "m4": (4.0, 4.0), "m5": (9.0, 3.4)}[key]   # 안팎 경계가 들어가게
    pcx, pcy = P(*crop_c)
    x0 = int(min(W2 - 1688, max(0, pcx - 844))) // 2 * 2; y0 = int(min(H2 - 780, max(0, pcy - 390))) // 2 * 2
    ph2 = canvas.crop((x0, y0, x0 + 1688, y0 + 780))
    paste_actors(ph2, 2, origin=(x0, y0))
    ph2.save(os.path.join(RAW, f"{key}_phone2x.png"))
    ph = hero.crop((x0 // 2, y0 // 2, x0 // 2 + 844, y0 // 2 + 390))
    ph.save(os.path.join(RAW, f"{key}_phone.png"))
    print("POST", key, "→", os.path.join(RAW, f"{key}_hero.png"), flush=True)


def _serve():
    import shutil
    os.makedirs(DST, exist_ok=True)
    from PIL import Image
    for k in SCENES:
        for suf in ("hero", "phone", "phone2x"):
            src = os.path.join(RAW, f"{k}_{suf}.png")
            if os.path.exists(src):
                im = Image.open(src).convert("RGB")
                out = os.path.join(DST, f"{k}_{suf}.jpg")
                im.save(out, quality=88, optimize=True)
                print("SERVE", out, os.path.getsize(out) // 1024, "KB")
    with open(os.path.join(DST, "maps_meta.json"), "w", encoding="utf-8") as f:
        json.dump({k: dict(META[k], hero=f"{k}_hero.jpg", phone=f"{k}_phone.jpg", phone2x=f"{k}_phone2x.jpg")
                   for k in SCENES}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    try:
        import bpy  # noqa
        IN_BLENDER = True
    except ImportError:
        IN_BLENDER = False
    if IN_BLENDER:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["all"]
        keys = list(SCENES) if argv[0] == "all" else argv
        for k in keys:
            _blender_main(k)
        print("ALL DONE", flush=True)
    else:
        cmd = sys.argv[1] if len(sys.argv) > 1 else "post"
        if cmd == "serve":
            _serve()
        else:
            arg = sys.argv[2] if len(sys.argv) > 2 else "all"
            for k in (list(SCENES) if arg == "all" else [arg]):
                _post(k)
