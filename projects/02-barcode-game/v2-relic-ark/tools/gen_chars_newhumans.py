# -*- coding: utf-8 -*-
"""
gen_chars_newhumans.py — 「신인류」(깊이에 적응한 드문 주민) 콘셉트 시트 (스프린트 17-C)

P2 48px 생활형 도트 규약 그대로(셀 64 · 발 기준선 60 · 맨머리 44px · 정수 배율). **생성 AI 없음** —
gen_chars_p2.py 의 도형 원시함수(Cv · ell · rect · seg)로 좌표를 찍는다. 기존 시트(행)는 건드리지 않는다.

네 방향(이름은 가제 — 시나리오 LORE_NEWHUMANS.md 가 정하면 바꾼다):
  A 등불결   — 남빛 압력복 + 몸에 붙는 두건, 뒤로 솟은 볏 지느러미. 이음선을 따라 물빛(시안) 발광선
  B 지느러미깃 — 청록 압력복 + 머리 뒤로 펼친 진주빛 부채 깃. 깃살 끝이 호박빛으로 빛난다
  C 진주눈   — 진주빛 압력복 + 머리를 감싼 유리 방울, 어둠에 맞춘 큰 눈(반사 반짝임). 이마 위 아귀 같은 보랏빛 등
  D 해파리 망토 — 자두빛 종 모양 두건이 어깨까지 덮고 뒤로 끈 촉수가 늘어진다. 가장자리 점들이 장밋빛으로 빛난다
공통: 투구도 공기통도 없다(= 적응했다). 창백한 피부 · 큰 눈 · 눈썹 · 입 · 홍조(C2·C10). 체형 A/B 는 역할과 무관(1px 차이).

발광 겹(glow) — 기존 겹치는 순서 끝에 하나를 더한다:
  기본 → 머리 → 얼굴(조합 규칙) → 잠수복 → 각인 → **발광**
  발광 겹은 몸 동작과 따로 2단(밝음/어두움)으로 맥박친다(셀마다 glow_a / glow_b 두 장). 틴트를 받지 않는 색이고,
  얼굴(눈·눈썹·입) 픽셀 위에는 놓지 않는다. 이 콘셉트 시트에서는 몸에 구워 넣지 않고 겹으로만 낸다.
실행: PYTHONIOENCODING=utf-8 python tools/gen_chars_newhumans.py
"""
import os, sys, io, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_chars_p2 as G
from PIL import Image, ImageDraw

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'static', 'art', 'chars', 'newhumans', 'concept')
REP = os.path.join(ROOT, 'docs', 'reports')
Cv, FOOT, CELL = G.Cv, G.FOOT, G.CELL

NH_PAL = {
    'nhSkin': (242, 224, 210), 'nhSkinD': (212, 186, 170), 'nhInk': (40, 28, 52), 'nhBrow': (66, 46, 70),
    'nhBlush': (232, 140, 138), 'nhWhite': (252, 250, 255), 'nhLine': (18, 14, 36),
    'nhInd': (46, 48, 104), 'nhIndD': (28, 28, 66), 'nhIndL': (78, 84, 148),
    'nhTeal': (36, 116, 126), 'nhTealD': (20, 72, 84), 'nhTealL': (72, 162, 166),
    'nhPearl': (222, 218, 232), 'nhPearlD': (170, 164, 190), 'nhPearlL': (248, 246, 254),
    'nhPlum': (96, 54, 110), 'nhPlumD': (60, 32, 74), 'nhPlumL': (138, 90, 152),
    'gCyan': (128, 255, 236), 'gCyanD': (62, 168, 172),
    'gAmber': (255, 216, 122), 'gAmberD': (186, 138, 62),
    'gViolet': (214, 176, 255), 'gVioletD': (136, 108, 192),
    'gRose': (255, 166, 204), 'gRoseD': (178, 100, 142),
    'nhGlass': (150, 210, 226), 'nhGlassD': (80, 130, 150),
    # 계보 무늬(LORE_NEWHUMANS §2) — 집 안 등불색(황토) 위에 차가운 청록·연한 금으로 남는다
    'gGold': (255, 228, 142), 'gGoldD': (196, 164, 84), 'gTeal': (116, 232, 222), 'gTealD': (58, 150, 152),
    'gSalt': (252, 252, 255), 'gSaltD': (196, 204, 218), 'gGreen': (156, 240, 152), 'gGreenD': (88, 158, 98),
}
GLOW_KEYS = {'gCyan', 'gCyanD', 'gAmber', 'gAmberD', 'gViolet', 'gVioletD', 'gRose', 'gRoseD', 'nhWhite', 'nhInk', 'nhLine',
             'gGold', 'gGoldD', 'gTeal', 'gTealD', 'gSalt', 'gSaltD', 'gGreen', 'gGreenD'}
LINEAGES = [   # id, 이름, 무늬 색, 그림 서명(LORE_NEWHUMANS §2)
    ('lampeye', '등불눈', 'gGold', '눈동자 둘레 금빛 고리 + 광대 점 셋'),
    ('wavearm', '물결팔', 'gTeal', '팔뚝의 물결 선, 손목→어깨로 흐른다'),
    ('saltgrain', '소금결', 'gSalt', '손등·목덜미 하얀 결정 점 + 맨발'),
    ('lowsong', '낮은노래', 'gGold', '턱선 빛 줄 + 조개 귀걸이'),
    ('weedhand', '해초손', 'gGreen', '손끝~손목의 「초록」'),
    ('stripehand', '줄무늬손', 'gTeal', '손등의 성문 같은 굵고 가는 빛 줄'),
]
LIN_KO = {k[0]: k[1] for k in LINEAGES}
LIN_COL = {k[0]: k[2] for k in LINEAGES}

CONCEPTS = [
    ('A', '등불결', 'nhInd', 'gCyan', '남빛 압력복 · 뒤로 솟은 볏 지느러미 · 이음선 발광'),
    ('B', '지느러미깃', 'nhTeal', 'gAmber', '청록 압력복 · 머리 뒤 진주빛 부채 깃 · 깃살 끝 발광'),
    ('C', '진주눈', 'nhPearl', 'gViolet', '진주빛 압력복 · 유리 방울 · 큰 반사 눈 · 이마 위 아귀 등'),
    ('D', '해파리 망토', 'nhPlum', 'gRose', '자두빛 종 두건 · 뒤로 끈 촉수 · 가장자리 발광 점'),
]


def tone(base):
    return base, base + 'D', base + 'L'


# ── 얼굴 (정면) ──────────────────────────────────────────────────────────
def face_front(c, hx, ey, big=False):
    """큰 눈(어둠 적응) + 반사 반짝임, 눈썹, 웃는 입, 홍조. 아늑하게 — 무섭지 않게."""
    w, h = (4, 4) if big else (3, 4)
    for ex in (hx - 1 - w, hx + 2):
        c.rect(ex, ey, ex + w - 1, ey + h - 1, 'nhInk')
        c.set(ex, ey, 'nhWhite'); c.set(ex + 1, ey, 'nhWhite') if big else None
        c.set(ex + w - 1, ey + h - 1, 'nhGlass')                   # 반사판 반짝임(아래쪽)
        c.set(ex + w - 1, ey, 'nhSkin'); c.set(ex, ey + h - 1, 'nhSkin')
    c.rect(hx - 1 - w, ey - 2, hx - 2, ey - 2, 'nhBrow')
    c.rect(hx + 2, ey - 2, hx + 1 + w, ey - 2, 'nhBrow')
    my = ey + h + 1
    c.set(hx - 1, my, 'nhInk'); c.set(hx, my + 1, 'nhInk'); c.set(hx + 1, my, 'nhInk')
    for bx in (hx - 1 - w, hx + 1 + w):
        if c.get(bx, my - 1) in ('nhSkin', 'nhSkinD'):
            c.set(bx, my - 1, 'nhBlush')


def face_side(c, hx, ey, hr, big=False):
    """옆얼굴(오른쪽) — 큰 눈 하나 + 반짝임, 눈썹, 코, 입, 홍조."""
    ex = int(round(hx + 3))
    h = 4
    c.rect(ex, ey, ex + 1 + (1 if big else 0), ey + h - 1, 'nhInk')
    c.set(ex + 1, ey, 'nhWhite')
    c.set(ex + (2 if big else 1), ey + h - 1, 'nhGlass')
    c.rect(ex, ey - 2, ex + 1 + (1 if big else 0), ey - 2, 'nhBrow')
    nx = int(round(hx + hr))
    c.set(nx, ey + 2, 'nhSkin'); c.set(nx, ey + 3, 'nhSkinD')
    c.set(nx - 2, ey + 5, 'nhInk'); c.set(nx - 1, ey + 5, 'nhInk'); c.set(nx - 3, ey + 4, 'nhInk')
    c.set(ex - 1, ey + h, 'nhBlush')


# ── 정면 idle ────────────────────────────────────────────────────────────
def style_marks(c, glow, lid, hx, ey, eye_w, eye_h, hands, arms, feet, face_rows):
    """방향 A~D 몸 위에 계보 서명을 얹는다. glow 항목 = (x, y, 색, 얼굴 위 허용, 맥박 단)."""
    col = LIN_COL.get(lid)
    if lid == 'lampeye':
        for ex in (hx - 1 - eye_w, hx + 2):
            for x in range(ex, ex + eye_w):
                glow.append((x, ey + eye_h - 1, col, True, (0, 1)))     # 눈동자 아래 테
            glow.append((ex + eye_w - 1, ey, col, True, (0, 1)))        # 위 바깥 모서리
        for (x, y) in ((hx - 6, ey + eye_h - 1), (hx - 7, ey + eye_h + 1), (hx - 5, ey + eye_h + 1)):
            if c.own(x, y) in ('nhSkin', 'nhSkinD'):
                glow.append((x, y, col, False, (0, 1)))
    elif lid == 'wavearm':
        for (ax, y0, y1) in arms:
            for y in range(y0, y1 + 1):
                for ph in (0, 1):
                    glow.append((ax + [0, 1, 2, 1][(y + ph) % 4], y, col, False, (ph,)))
    elif lid == 'stripehand':
        for (x0, y0, x1, y1) in hands:
            for x in (x0, x1):
                for y in range(y0, y1 + 1):
                    glow.append((x, y, col, False, (0, 1)))
    elif lid == 'weedhand':
        for (x0, y0, x1, y1) in hands:
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    glow.append((x, y, col, False, (0, 1)))
    elif lid == 'saltgrain':
        for (x0, y0, x1, y1) in hands:
            glow.append((x0 + 1, y0, col, False, (0, 1)))
        for (fx0, fy0, fx1, fy1) in feet:                    # 맨발
            c.rect(fx0, fy0, fx1, fy1, 'nhSkin'); c.rect(fx0, fy1, fx1, fy1, 'nhSkinD')
    elif lid == 'lowsong':
        for x in range(hx - 4, hx + 5):
            ys = [y for (y, lo, hi) in face_rows if lo <= x <= hi]
            if ys:
                glow.append((x, max(ys), col, False, (0, 1)))


def nh_front(cid, body, f, lid=None):
    base_col, accent = [(k[2], k[3]) for k in CONCEPTS if k[0] == cid][0]
    M, D, L = tone(base_col)
    c, glow = Cv(), []
    bob = [0, 1][f]
    hr = 8.5
    head_top = FOOT - 43 + bob
    hy = head_top + hr
    hx = cx = 32
    neck_y = head_top + 17
    trx = 7.4 - (1.0 if body == 'b' else 0.0)
    tcy, tr_y = neck_y + 9, 7.2
    belt = int(round(tcy + 3.2))
    leg_y0 = int(round(tcy + tr_y - 1))

    # 뒤에 오는 것
    if cid == 'B':                                         # 부채 깃 — 머리 뒤로 반원
        R0 = 15
        c.ell(hx, neck_y - 2, R0, R0 - 2, 'nhPearl')
        c.ell_in(hx, neck_y - 2, R0 - 2, R0 - 4, 'nhPearlL', only=('nhPearl',))
        for k in range(7):
            a = math.radians(200 + k * 23.3)
            tip = (hx + R0 * math.cos(a), neck_y - 2 + (R0 - 2) * math.sin(a))
            G.seg(c, (hx, neck_y - 2), tip, 'nhTeal', 1)
            glow.append((int(round(tip[0])), int(round(tip[1]))))
        for y in range(neck_y - 1, 64):                     # 아래 반은 지운다(어깨 뒤에서 끝난다)
            for x in range(64):
                if c.own(x, y) in ('nhPearl', 'nhPearlL', 'nhTeal'):
                    c.clear(x, y)
    if cid == 'D':                                         # 촉수 — 몸 뒤로 늘어진다
        for k, x0 in enumerate((cx - 9, cx - 5, cx + 5, cx + 9)):
            for y in range(int(hy), FOOT - 6 + (k % 2) * 2):
                xx = x0 + int(round(math.sin((y + f * 2 + k) * 0.55)))
                c.set(xx, y, 'nhPlumD')
            glow.append((x0 + int(round(math.sin((FOOT - 7 + (k % 2) * 2 + f * 2 + k) * 0.55))), FOOT - 7 + (k % 2) * 2))

    # 다리 — 매끈한 압력복 다리, 지느러미 같은 발끝
    for lx in (cx - 5, cx + 1):
        c.rect(lx, leg_y0, lx + 3, FOOT - 2, D)
        c.rect(lx, leg_y0, lx, FOOT - 2, M)
        c.rect(lx - 1, FOOT - 1, lx + 4, FOOT, D); c.set(lx + 4, FOOT - 1, L)
        if cid == 'A':
            glow.append((lx + 3, leg_y0 + 3)); glow.append((lx + 3, leg_y0 + 6))
    # 몸통
    c.ell(cx, tcy, trx, tr_y, M)
    c.ell_in(cx - 2, tcy - 2.2, trx - 2, tr_y - 1.2, L, only=(M,))
    c.ell_in(cx, tcy + tr_y - 1, trx, 3.0, D, only=(M, L))
    if body == 'b':
        for yy in (belt - 1, belt):
            for xx in range(cx - 12, cx + 13):
                if abs(xx - cx) > trx - 1.2 and c.own(xx, yy) in (M, L, D):
                    c.clear(xx, yy)
    if cid == 'C':                                         # 남빛 가슴 판
        c.rect(cx - 3, neck_y + 2, cx + 3, belt - 1, 'nhInd'); c.rect(cx - 3, neck_y + 2, cx + 3, neck_y + 2, 'nhIndL')
    c.rect(cx - int(trx) + 1, belt, cx + int(trx) - 1, belt, D)
    if cid == 'A':
        for y in range(neck_y + 2, belt + 4, 2):
            glow.append((cx, y))                           # 가슴 가운데 이음선
    # 팔
    ax_l, ax_r = int(cx - trx - 2), int(cx + trx - 1)
    for ax, t in ((ax_l, M), (ax_r, D)):
        c.rect(ax, neck_y + 2, ax + 2, belt + 2, t)
        c.rect(ax, belt + 3, ax + 2, belt + 4, 'nhSkinD')  # 맨손(창백)
        if cid == 'A':
            glow.append((ax + (0 if ax == ax_l else 2), neck_y + 5)); glow.append((ax + (0 if ax == ax_l else 2), neck_y + 8))
    # 목깃
    c.ell(cx, neck_y - 1, trx - 1.2, 2.2, L)
    # 머리
    c.ell(hx, hy, hr, hr, 'nhSkin')
    c.ell_in(hx + 2, hy + 2, hr - 1.5, hr - 1.5, 'nhSkinD', only=('nhSkin',))
    ey = int(round(hy + 0.5))
    if cid == 'A':                                         # 몸에 붙는 두건 + 볏
        c.ell(hx, hy - 0.5, hr + 0.8, hr + 0.6, M)
        c.ell_in(hx - 2, hy - 3, hr - 1, hr - 2, L, only=(M,))
        c.ell(hx, hy + 2.2, hr - 2.2, hr - 2.6, 'nhSkin')
        c.ell_in(hx + 2, hy + 3.6, hr - 3.4, hr - 3.6, 'nhSkinD', only=('nhSkin',))
        for k in range(7):                                 # 볏 — 위로 가늘어진다
            y = int(head_top) - 1 - k
            wv = 1 if k < 5 else 0
            c.rect(hx - wv, y, hx + wv, y, M if k < 6 else L)
        glow += [(hx, int(head_top) - 2 - k) for k in range(0, 6, 2)]
        pass                                               # 얼굴 테 발광은 뺐다(가면처럼 읽혔다 — 1차 확인)
    elif cid == 'B':                                       # 매끈한 수영모 + 귀 지느러미
        c.ell(hx, hy - 3, hr + 0.4, hr - 3.2, M)
        c.ell_in(hx - 2, hy - 4.5, hr - 2, hr - 5, L, only=(M,))
        for s in (-1, 1):
            c.rect(hx + s * (hr + 1) - (1 if s < 0 else 0), ey - 1, hx + s * (hr + 1) + (0 if s < 0 else 1), ey + 2, 'nhTealL')
    elif cid == 'C':                                       # 머리 지느러미 두 덩이 + 유리 방울 + 아귀 등
        for s in (-1, 1):
            c.ell(hx + s * 4, head_top + 1, 2.4, 1.8, 'nhPearlD')
        c.ell_in(hx, hy - 4, hr - 1, 2.0, 'nhPearlD', only=('nhSkin', 'nhSkinD'))
        rr = hr + 3.0
        G.ring(c, hx, hy - 0.5, rr, 1.0, 'nhGlass')
        c.set(int(hx - rr * 0.6), int(hy - rr * 0.6), 'nhWhite'); c.set(int(hx - rr * 0.7), int(hy - rr * 0.45), 'nhWhite')
        top = int(round(hy - 0.5 - rr))
        G.seg(c, (hx, top), (hx + 2, top - 4), 'nhInd', 1)
        G.seg(c, (hx + 2, top - 4), (hx + 5, top - 4), 'nhInd', 1)
        glow += [(hx + 6, top - 4), (hx + 6, top - 3), (hx + 7, top - 4), (hx + 7, top - 3)]
    elif cid == 'D':                                       # 해파리 종 두건
        c.ell(hx, hy - 2, hr + 3.2, hr + 0.6, M)
        c.ell_in(hx - 3, hy - 5, hr, hr - 3, L, only=(M,))
        rim = int(round(hy - 3))                           # 가장자리는 눈썹 위 — 얼굴 전체가 보인다(1차: 눈을 가려 가면처럼 읽혔다)
        for y in range(rim, int(hy + hr) + 1):             # 가장자리 아래는 얼굴이 보이게 걷는다
            for x in range(int(hx - hr + 2), int(hx + hr - 1)):
                if c.own(x, y) in (M, L):
                    c.set(x, y, 'nhSkin' if (x - hx) ** 2 + (y - hy) ** 2 <= hr * hr else None)
        for k, x in enumerate(range(int(hx - hr - 3), int(hx + hr + 4), 3)):   # 물결 가장자리 + 발광 점
            c.set(x, rim, D); c.set(x + 1, rim + 1, D)
            glow.append((x, rim + 1))
    face_front(c, hx, ey, big=(cid == 'C'))
    if lid:
        face_rows = []
        for y in range(ey, ey + 9):
            xs = [x for x in range(int(hx - hr), int(hx + hr) + 1) if c.own(x, y) in ('nhSkin', 'nhSkinD')]
            if xs:
                face_rows.append((y, min(xs), max(xs)))
        hands = [(ax, belt + 3, ax + 2, belt + 4) for ax in (ax_l, ax_r)]
        arms = [(ax, belt - 3, belt + 2) for ax in (ax_l, ax_r)]
        feet = [(lx - 1, FOOT - 1, lx + 4, FOOT) for lx in (cx - 5, cx + 1)]
        if lid == 'lowsong':                               # 조개 귀걸이(본체 쪽 — 빛나지 않는다)
            for x in (int(hx - hr + 0.5), int(hx + hr - 0.5)):
                c.set(x, ey + 4, 'nhPearl'); c.set(x, ey + 5, 'nhPearlL')
        style_marks(c, glow, lid, hx, ey, 4 if cid == 'C' else 3, 4, hands, arms, feet, face_rows)
    c.outline('nhLine')
    if cid == 'C':                                         # 유리 방울은 외곽선 안쪽에서 빛난다(바깥선 위에 다시)
        G.ring(c, hx, hy - 0.5, hr + 3.0, 1.0, 'nhGlass')
    return c, glow, accent


# ── 옆모습 walk_side (오른쪽) ────────────────────────────────────────────
def nh_side(cid, body, f):
    base_col, accent = [(k[2], k[3]) for k in CONCEPTS if k[0] == cid][0]
    M, D, L = tone(base_col)
    c, glow = Cv(), []
    bob = [0, -1, 0][f]
    hr = 8.5
    head_top = FOOT - 43 + bob
    hy = head_top + hr
    cx = 31
    hx = cx + 1
    neck_y = head_top + 17
    trx, tr_y = 5.4 - (0.6 if body == 'b' else 0.0), 7.2
    tcy = neck_y + 9
    belt = int(round(tcy + 3.2))
    leg_y0 = int(round(tcy + tr_y - 1))
    st = 4
    near_dx, far_dx = [st, 0, -st][f], [-st, -1, st][f]
    far_lift = [0, 2, 0][f]
    # 뒤에 오는 것
    if cid == 'B':                                         # 부채 깃 — 옆에서는 머리 뒤 반원판
        c.ell(hx - 4, hy + 1, 9, 11, 'nhPearl')
        c.ell_in(hx - 5, hy, 7, 9, 'nhPearlL', only=('nhPearl',))
        for k in range(5):
            a = math.radians(120 + k * 30)
            tip = (hx - 4 + 9 * math.cos(a), hy + 1 - 11 * math.sin(a))
            G.seg(c, (hx - 2, hy + 3), tip, 'nhTeal', 1)
            glow.append((int(round(tip[0])), int(round(tip[1]))))
    if cid == 'D':                                         # 촉수 — 뒤로 흐른다(걸음마다 물결)
        for k in range(3):
            y0 = int(hy) + 1 + k * 2
            for t in range(15 - k * 2):
                x = hx - 6 - t
                y = y0 + t // 2 + int(round(math.sin((t + f * 2 + k) * 0.7)))
                c.set(x, y, 'nhPlumD')
            glow.append((hx - 6 - (14 - k * 2), y0 + (14 - k * 2) // 2 + int(round(math.sin((14 - k * 2 + f * 2 + k) * 0.7)))))
    # 먼 팔
    sw = [-1, 0, 1][f]
    SF = (cx - 0.5, neck_y + 3.0)
    a = math.radians(20 * sw)
    hf = (int(round(SF[0] + 11 * math.sin(a))), int(round(SF[1] + 11 * math.cos(a))))
    G.seg(c, SF, hf, D, 3)
    # 다리
    for dx, lift, far in ((far_dx, far_lift, True), (near_dx, 0, False)):
        hip = (cx - (1 if far else 0), leg_y0)
        ank = (cx + dx, FOOT - 3 - lift)
        G.seg(c, hip, ank, D if far else M, 4)
        fx = int(round(cx + dx))
        c.rect(fx - 2, FOOT - 2 - lift, fx + 3, FOOT - lift, D if far else M)
        c.set(fx + 4, FOOT - lift, D if far else L)                      # 지느러미 발끝
        if cid == 'A' and not far:
            glow.append((fx, FOOT - 5 - lift))
    # 몸통
    c.ell(cx, tcy, trx, tr_y, M)
    c.ell_in(cx - 1.5, tcy - 2.2, trx - 1.5, tr_y - 1.2, L, only=(M,))
    c.ell_in(cx, tcy + tr_y - 1, trx, 3.0, D, only=(M, L))
    if cid == 'C':
        c.rect(cx + 1, neck_y + 2, cx + int(trx) - 1, belt - 1, 'nhInd')
    if cid == 'A':
        for y in range(neck_y + 2, belt + 4, 2):
            glow.append((int(cx + trx - 1), y))
    c.ell(cx, neck_y - 1, trx - .4, 2.2, L)
    # 가까운 팔
    SN = (cx + 0.5, neck_y + 3.0)
    a = math.radians(-20 * sw + 6)
    hn = (int(round(SN[0] + 11 * math.sin(a))), int(round(SN[1] + 11 * math.cos(a))))
    G.seg(c, SN, hn, M, 3)
    c.ell(hn[0], hn[1], 1.6, 1.6, 'nhSkinD')
    if cid == 'A':
        glow.append((int((SN[0] + hn[0]) / 2) + 1, int((SN[1] + hn[1]) / 2)))
    # 머리(옆)
    c.ell(hx, hy, hr, hr, 'nhSkin')
    c.ell_in(hx + 2, hy + 2, hr - 1.5, hr - 1.5, 'nhSkinD', only=('nhSkin',))
    ey = int(round(hy + 0.5))
    if cid == 'A':                                         # 두건이 뒤 반을 덮고 볏이 뒤로 솟는다
        for y in range(int(hy - hr - 1), int(hy + hr + 1)):
            for x in range(int(hx - hr - 1), int(hx + hr + 2)):
                inside = (x - hx) ** 2 + (y - hy) ** 2 <= (hr + 0.8) ** 2
                face = (x - (hx + 3)) ** 2 / 25.0 + (y - (hy + 2)) ** 2 / 36.0 <= 1.0
                if inside and not face:
                    c.set(x, y, L if (y < hy - 3 and x < hx) else M)
        for k in range(9):                                 # 볏 — 정수리에서 뒤-위로
            x, y = int(hx - k), int(head_top - 1 - (k * 0.7))
            c.rect(x, y, x, y + 2, M)
            if k % 3 == 1:
                glow.append((x, y))
        glow += [(int(hx - 1), int(hy - 4)), (int(hx - 2), int(hy)), (int(hx - 1), int(hy + 4))]
    elif cid == 'B':
        c.ell(hx - 1, hy - 3, hr, hr - 3.2, M)
        c.ell_in(hx - 3, hy - 4.5, hr - 2, hr - 5, L, only=(M,))
        c.rect(hx - 3, ey - 1, hx - 2, ey + 3, 'nhTealL')            # 귀 지느러미
    elif cid == 'C':
        c.ell(hx - 2, head_top + 1, 3, 1.8, 'nhPearlD')
        rr = hr + 3.0
        G.ring(c, hx, hy - 0.5, rr, 1.0, 'nhGlass')
        top = int(round(hy - 0.5 - rr))
        G.seg(c, (hx + 1, top), (hx + 5, top - 3), 'nhInd', 1)       # 아귀 등 — 앞으로 굽는다
        G.seg(c, (hx + 5, top - 3), (hx + 9, top - 1), 'nhInd', 1)
        glow += [(hx + 10, top - 1), (hx + 10, top), (hx + 11, top - 1), (hx + 11, top)]
    elif cid == 'D':
        c.ell(hx - 1, hy - 2, hr + 2.6, hr + 0.4, M)
        c.ell_in(hx - 4, hy - 5, hr - 1, hr - 3, L, only=(M,))
        rim = int(round(hy + 1))
        for y in range(rim - 2, rim + 4):                  # 얼굴 쪽(앞)은 걷는다
            for x in range(int(hx + 1), int(hx + hr + 4)):
                if c.own(x, y) in (M, L):
                    c.set(x, y, 'nhSkin' if (x - hx) ** 2 + (y - hy) ** 2 <= hr * hr else None)
        for x in range(int(hx - hr - 3), int(hx + 2), 3):
            c.set(x, rim + 1, D)
            glow.append((x, rim + 2))
        ey = int(round(hy + 1.0))
    face_side(c, hx, ey, hr, big=(cid == 'C'))
    c.outline('nhLine')
    if cid == 'C':
        G.ring(c, hx, hy - 0.5, hr + 3.0, 1.0, 'nhGlass')
    return c, glow, accent


def glow_layer(glow, accent, phase, body_cv, face_px):
    """발광 겹 한 장. phase 0 = 밝음, 1 = 어두움(맥박). 얼굴 픽셀 위에는 놓지 않는다."""
    g = Cv()
    for it in glow:
        x, y = it[0], it[1]
        col = it[2] if len(it) > 2 else accent
        face_ok = it[3] if len(it) > 3 else False
        phases = it[4] if len(it) > 4 else (0, 1)
        if phase not in phases or ((x, y) in face_px and not face_ok):
            continue
        g.set(x, y, col if phase == 0 else col + 'D')
    return g


FACE_COLS = ('nhInk', 'nhWhite', 'nhBrow', 'nhBlush', 'nhGlass')


def render(cid, body, kind, f, phase, lid=None):
    c, glow, accent = (nh_front(cid, body, f, lid) if kind == 'idle' else nh_side(cid, body, f))
    face_px = set(p for p in c.pixels() if c.own(*p) in ('nhInk', 'nhWhite', 'nhBrow', 'nhBlush'))
    g = glow_layer(glow, accent, phase, c, face_px)
    im = c.img()
    im.alpha_composite(g.img())
    return im, c, g


def main():
    os.makedirs(OUT, exist_ok=True)
    G.PAL.update(NH_PAL)
    G.NO_TINT.update(GLOW_KEYS)
    G.harmonize()
    for k, v in NH_PAL.items():                            # 신인류 팔레트는 당기지 않는다(따로 서야 한다)
        G.PAL[k] = v
    f12, f14, f16 = G.font(12), G.font(15), G.font(18)
    K = 3

    # 1. 콘셉트마다 셀 시트(x4): idle f0·f1 · walk_side f0~2 · 발광 겹 a/b(본체 위)
    sheets = {}
    for cid, ko, *_ in CONCEPTS:
        for body in ('a', 'b'):
            cells = []
            for kind, n in (('idle', 2), ('walk_side', 3)):
                for f in range(n):
                    cells.append(render(cid, body, kind, f, f % 2)[0])
            sh = Image.new('RGBA', (CELL * len(cells), CELL), (0, 0, 0, 0))
            for i, im in enumerate(cells):
                sh.paste(im, (CELL * i, 0))
            sh.save(os.path.join(OUT, 'nh_%s_%s.png' % (cid, body)))
            G.up(sh, 4).save(os.path.join(OUT, 'nh_%s_%s_x4.png' % (cid, body)))
            # 발광 겹만 따로(두 단) — 제안하는 겹 형식
            gl = Image.new('RGBA', (CELL * 4, CELL), (0, 0, 0, 0))
            for i, (kind, f, ph) in enumerate((('idle', 0, 0), ('idle', 0, 1), ('walk_side', 0, 0), ('walk_side', 0, 1))):
                gl.paste(render(cid, body, kind, f, ph)[2].img(), (CELL * i, 0))
            gl.save(os.path.join(OUT, 'glow_%s_%s.png' % (cid, body)))
            sheets[(cid, body)] = sh

    # 2. 대비 — 기본 주민 둘 옆에 (정면 idle / 옆 walk_side), 어두운 방
    basics = [('scout', 'a', 'braid', 'f0'), ('cook', 'b', 'short', 'f1')]
    panels = []
    for cid, ko, base_col, accent, note in CONCEPTS:
        W, H = 10 + 8 * (64 * K // 2 + 6) + 28 + 64 * K // 2, 64 * K + 70
        im = G.room_bg(W, H, (60 + 64 * K - 10) / float(H), False).convert('RGBA')
        d = ImageDraw.Draw(im)
        x = 10
        for kind, fr in (('idle', 0), ('walk_side', 1)):
            for role, body, h, fc in basics:
                one = G.build(role, kind, fr, body, h, fc)[0].img()
                im.alpha_composite(G.up(one, K), (x, 50))
                x += 64 * K // 2 + 6
            for body in ('a', 'b'):
                one = render(cid, body, kind, fr, 0)[0]
                im.alpha_composite(G.up(one, K), (x, 50))
                x += 64 * K // 2 + 6
            x += 14
        d.text((10, 6), '%s %s — %s' % (cid, ko, note), font=f16, fill=(236, 214, 255))
        d.text((10, 28), '왼쪽 둘 = 기본 주민(정찰병 A · 요리사 B) / 오른쪽 둘 = 신인류 A·B 체형   ·   정면 idle  |  옆 walk_side',
               font=f12, fill=(190, 176, 210))
        im.save(os.path.join(OUT, 'contrast_%s.png' % cid))
        panels.append(im)

    # 3. 방 안 — 거주실 플레이트(×3, floor_y 그대로)에 기본 셋 + 신인류 하나
    pm = json.load(io.open(os.path.join(ROOT, 'static', 'art', 'plates', 'plates_meta.json'), encoding='utf-8'))
    flY, kk = pm['floor_y'], pm['grid']['char_scale']
    plate = Image.open(os.path.join(ROOT, 'static', 'art', 'plates', 'room_plate_quarters_lit.png')).convert('RGBA')
    rooms = []
    for cid, ko, *_ in CONCEPTS:
        pl = plate.copy()
        cast = [('b', 'scout', 'idle', 0), ('nh', cid, 'idle', 0), ('b', 'farmer', 'walk_side', 1), ('b', 'kid', 'idle', 1)]
        xs = [150, 270, 390, 500]
        for (typ, who, kind, fr), xc in zip(cast, xs):
            if typ == 'b':
                one = G.build(who, kind, fr, 'a', 'short', 'f0')[0].img()
                one = G.room_light(G.up(one, kk))
            else:
                one = G.up(render(who, 'a', kind, fr, 0)[0], kk)
            bb = one.getbbox()
            pl = G.ground_shadow(pl, (xc - 96 + bb[0], flY - G.BASE_Y * kk + bb[1]), one.crop(bb))
            pl.alpha_composite(one, (xc - 96, flY - G.BASE_Y * kk))
        d = ImageDraw.Draw(pl)
        d.rectangle([0, 0, pl.width, 26], fill=(16, 11, 9, 230))
        d.text((8, 5), '거주실 — 기본 주민 셋 사이의 신인류 %s %s (×%d)' % (cid, ko, kk), font=f14, fill=(244, 216, 160))
        pl.save(os.path.join(OUT, 'room_%s.png' % cid))
        rooms.append(pl)

    # 4. 70px — 기본 8역할 + 신인류 넷(색 / 실루엣)
    sc70 = 70.0 / 49.0
    line = [('b', r) for r in G.ROLES] + [('nh', k[0]) for k in CONCEPTS]
    W7, H7 = 20 + len(line) * 76, 40 + 2 * 112
    im70 = G.room_bg(W7, H7, 0.99, True)
    d = ImageDraw.Draw(im70)
    for rr, sil in enumerate((False, True)):
        y0 = 40 + rr * 112
        for j, (typ, who) in enumerate(line):
            one = (G.build(who, 'idle', 0, 'a')[0].img() if typ == 'b' else render(who, 'a', 'idle', 0, 0)[0])
            if sil:
                px = one.load()
                for yy in range(one.height):
                    for xx in range(one.width):
                        if px[xx, yy][3] > 0:
                            px[xx, yy] = (22, 14, 10, 255)
            z = one.resize((int(round(CELL * sc70)), int(round(CELL * sc70))), Image.NEAREST)
            im70.paste(z, (20 + j * 76 + 38 - z.width // 2, y0 + 106 - int(G.BASE_Y * sc70)), z)
            if rr == 0:
                d.text((20 + j * 76 + 8, 8), (G.ROLE_KO[who][:2] if typ == 'b' else '신' + who), font=f12, fill=(40, 28, 18))
    im70.save(os.path.join(OUT, 'lineup70.png'))

    # 5. 얼굴·발광 확대 — 맥박 두 단
    zoom = Image.new('RGB', (20 + 8 * 190, 230), (12, 10, 22))
    d = ImageDraw.Draw(zoom)
    for j, (cid, ko, *_r) in enumerate(CONCEPTS):
        for ph in (0, 1):
            one = render(cid, 'a', 'idle', 0, ph)[0].crop((10, 2, 54, 40))
            z = G.up(one, 4)
            zoom.paste(z, (20 + (j * 2 + ph) * 190, 40), z)
            d.text((20 + (j * 2 + ph) * 190, 14), '%s %s · 발광 %s' % (cid, ko, '밝음' if ph == 0 else '어두움'),
                   font=f12, fill=(220, 210, 240))
    zoom.save(os.path.join(OUT, 'faces_glow.png'))

    # 7. 트랙 1 — 계보 무늬 겹을 **기존 P2 몸** 위에(LORE_NEWHUMANS §2: 각인처럼 레이어로)
    #    무늬 픽셀은 머리 6·얼굴 18조합·각인 12 픽셀을 비킨다(잠수복 겹과 같은 금지 목록). 예외는 등불눈의 눈동자 금빛 고리
    #    하나 — 정의상 눈 위에 있다. 그래서 등불눈만 얼굴 3종마다 한 장씩(faces 처럼) 낸다.
    lin_check = {}
    def lineage_p2(lid, role, body, f, fid, phase):
        base, ov, a = G.raw_of(role, 'idle', f, body)
        comp = G.build(role, 'idle', f, body, 'short', fid)[0]
        fb = G.suit_forbid(role, 'idle', f, body)
        srole = 'kid' if role == 'kid' else 'scout'
        _b, _o, ai = G.raw_of(srole, 'idle', f, body)
        imp = set()
        for iid, *_r in G.IMPRINTS:
            imp |= G.imprint_layer(iid, ai).pixels()
        col = LIN_COL[lid] + ('' if phase == 0 else 'D')
        L_ = Cv()
        ey = G.ey_of(a['fy'])
        hx, fy, fr = a['hx'], a['fy'], a['fr']
        wr = (a['wrist_r'][0], a['wrist_r'][1] + 2)
        mitts = [a['mitten_l'], wr]
        def mitt_px(cn):
            return [(x, y) for (x, y) in comp.pixels() if comp.own(x, y) in ('cream', 'creamD')
                    and math.hypot(x - cn[0], y - cn[1]) <= 2.6 and (x, y) not in fb]
        if lid == 'lampeye':
            fl = G.face_layer(fid, a, base, G.hair_layer('short', a, base))
            ink = [(x, y) for (x, y) in fl.pixels() if fl.own(x, y) in ('ink', 'skin') and ey <= y <= ey + 2
                   and any(fl.own(x + dx, y + dy) == 'ink' for dx, dy in ((1, 0), (-1, 0), (0, -1)))]
            for side in (lambda x: x < hx, lambda x: x >= hx):
                pts = [q for q in ink if side(q[0])]
                if pts:
                    yb = max(q[1] for q in pts)
                    for q in pts:
                        if q[1] == yb:
                            L_.set(q[0], q[1], col)        # 눈동자 아래 테 — 의도된 얼굴 위 픽셀
            cand = [(x, y) for (x, y) in comp.pixels() if comp.own(x, y) in ('skin', 'skinD') and (x, y) not in fb
                    and ey + 1 <= y <= ey + 3 and x <= hx - 4]
            cand.sort(key=lambda q: (q[0] + q[1]))
            for q in cand[::max(1, len(cand) // 3)][:3]:
                L_.set(q[0], q[1], col)
        elif lid == 'wavearm':
            for (x, y) in comp.pixels():
                t = comp.own(x, y)
                if t in ('suitM', 'suitD', 'suitL') and (x, y) not in fb and a['belt_y'] - 4 <= y <= a['belt_y'] + 2 \
                        and (abs(x - a['ax_l'] - 1.5) <= 2.2 or abs(x - a['ax_r'] - 1.5) <= 2.2) and (x + y + phase) % 3 == 0:
                    L_.set(x, y, LIN_COL[lid])
        elif lid == 'saltgrain':
            for cn in mitts:
                for (x, y) in mitt_px(cn):
                    if (x * 3 + y) % 4 == 0:
                        L_.set(x, y, col)
            for (x, y) in comp.pixels():                   # 목덜미(목 실링 옆)
                if comp.own(x, y) in ('cream', 'creamD') and y in (a['neck_y'] - 2, a['neck_y'] - 1) \
                        and abs(x - a['cx']) in (4, 5) and (x, y) not in fb:
                    L_.set(x, y, col)
            for (x, y) in comp.pixels():                   # 맨발(본체 색 — 빛나지 않는다)
                if y >= FOOT - 4 and comp.own(x, y) in ('bootM', 'bootL', 'brassM', 'brass', 'brassD') and (x, y) not in fb:
                    L_.set(x, y, 'skin' if y < FOOT else 'skinD')
        elif lid == 'lowsong':
            for x in range(int(hx - fr), int(hx + fr) + 1):      # 턱선 = 열마다 가장 아래 살 칸
                ys = [y for y in range(int(fy), int(fy + fr) + 2) if comp.own(x, y) in ('skin', 'skinD')]
                if ys and (x, max(ys)) not in fb and max(ys) > fy + 2:
                    L_.set(x, max(ys), col)
            for x in (int(round(hx - fr - 1)), int(round(hx + fr + 1))):
                for (xx, yy, t) in ((x, ey + 3, 'nhPearl'), (x, ey + 4, 'nhPearlL')):
                    if (xx, yy) not in fb:
                        L_.set(xx, yy, t)
        elif lid == 'weedhand':
            for cn in mitts:
                for (x, y) in mitt_px(cn):
                    if y >= cn[1] - 0.5:
                        L_.set(x, y, col)
        elif lid == 'stripehand':
            for cn in mitts:
                for (x, y) in mitt_px(cn):
                    if x - cn[0] in (-2, -1, 1) and y >= cn[1] - 1:
                        L_.set(x, y, col)
        px = L_.pixels()
        face_hits = px & fb - imp
        lin_check[(lid, role, body, fid)] = {'x_imprint': len(px & imp),
                                             'x_hair_face': len(face_hits) if lid != 'lampeye' else 0,
                                             'lampeye_on_eye': len(face_hits) if lid == 'lampeye' else 0}
        im_ = comp.img()
        im_.alpha_composite(L_.img())
        return im_, L_
    lin_cast = [('lampeye', 'scholar', 'a', 'f0'), ('wavearm', 'cook', 'b', 'f1'), ('saltgrain', 'farmer', 'a', 'f2'),
                ('lowsong', 'medic', 'b', 'f0'), ('weedhand', 'kid', 'a', 'f1'), ('stripehand', 'engineer', 'b', 'f0')]
    WL, HL = 20 + 6 * 330, 64 * 4 + 90
    imL = G.room_bg(WL, HL, 0.99, False).convert('RGBA')
    d = ImageDraw.Draw(imL)
    for j, (lid, role, body, fid) in enumerate(lin_cast):
        x0 = 14 + j * 330
        plain = G.build(role, 'idle', 0, body, 'short', fid)[0].img()
        for k, (im_, lab) in enumerate(((plain, '기본'), (lineage_p2(lid, role, body, 0, fid, 0)[0], '숨 들이쉼'),
                                        (lineage_p2(lid, role, body, 1, fid, 1)[0], '숨 내쉼'))):
            cut = im_.crop((12, 8, 52, 62))
            z = G.up(cut, 3)
            imL.alpha_composite(z, (x0 + k * 106, 60))
            d.text((x0 + k * 106 + 4, 60 + z.height + 2), lab, font=f12, fill=(190, 176, 160))
        d.text((x0, 8), '%s — %s' % (LIN_KO[lid], [k_[3] for k_ in LINEAGES if k_[0] == lid][0]), font=f12, fill=(236, 214, 180))
        d.text((x0, 26), '%s · 체형 %s · 얼굴 %s' % (G.ROLE_KO[role], body.upper(), fid), font=f12, fill=(170, 150, 130))
    d.text((14, HL - 22), '트랙 1(설정 그대로): 기존 몸·머리·얼굴 위에 계보 무늬 겹. 역할(모자)은 그대로 — 신인류도 역할을 하나 갖는다(LORE §2)',
           font=f12, fill=(220, 200, 170))
    imL.save(os.path.join(OUT, 'lineage_on_p2.png'))
    # 따뜻한 방 안 — 차가운 무늬만 남는다(LORE §1-1)
    pl = plate.copy()
    for (lid, role, body, fid), xc in zip(lin_cast[:4], (150, 260, 380, 500)):
        im_ = G.room_light(G.up(lineage_p2(lid, role, body, 0, fid, 0)[0], kk))
        Lp = G.up(lineage_p2(lid, role, body, 0, fid, 0)[1].img(), kk)
        im_.alpha_composite(Lp)                            # 무늬는 등불색 틴트를 받지 않는다
        bb = im_.getbbox()
        pl = G.ground_shadow(pl, (xc - 96 + bb[0], flY - G.BASE_Y * kk + bb[1]), im_.crop(bb))
        pl.alpha_composite(im_, (xc - 96, flY - G.BASE_Y * kk))
    d = ImageDraw.Draw(pl)
    d.rectangle([0, 0, pl.width, 26], fill=(16, 11, 9, 230))
    d.text((8, 5), '거주실 — 계보 무늬(등불눈·물결팔·소금결·낮은노래)는 등불색을 받지 않아 차갑게 남는다', font=f14, fill=(244, 216, 160))
    pl.save(os.path.join(OUT, 'lineage_room.png'))
    lin_tot_imp = sum(v['x_imprint'] for v in lin_check.values())
    lin_tot_hf = sum(v['x_hair_face'] for v in lin_check.values())
    print('[검사] 계보 무늬 × 각인 %d칸 · × 머리·얼굴 %d칸 (등불눈 눈동자 테는 의도 — %d칸)'
          % (lin_tot_imp, lin_tot_hf, sum(v['lampeye_on_eye'] for v in lin_check.values())))

    # 8. 트랙 2 — 방향 A~D × 계보 셋(등불눈·물결팔·줄무늬손)
    grid_l = ['lampeye', 'wavearm', 'stripehand']
    WG, HG = 130 + 4 * 2 * 110, 40 + len(grid_l) * 200
    imG = Image.new('RGB', (WG, HG), (12, 10, 22))
    d = ImageDraw.Draw(imG)
    for r, lid in enumerate(grid_l):
        d.text((8, 40 + r * 200 + 80), LIN_KO[lid], font=f14, fill=(236, 214, 255))
        for j, (cid, ko, *_r) in enumerate(CONCEPTS):
            for ph in (0, 1):
                one = render(cid, 'a' if r % 2 == 0 else 'b', 'idle', ph, ph, lid)[0]
                z = G.up(one, 3)
                imG.paste(z, (130 + (j * 2 + ph) * 110 - 40, 40 + r * 200 - 20), z)
    for j, (cid, ko, *_r) in enumerate(CONCEPTS):
        d.text((130 + j * 220, 8), '%s %s (밝음 · 어두움)' % (cid, ko), font=f12, fill=(220, 210, 240))
    imG.save(os.path.join(OUT, 'style_x_lineage.png'))

    # 6. 접촉 시트(보고서용 한 장)
    parts = [imL, pl, imG] + panels + [im70, zoom]
    Wc = max(p.width for p in parts + rooms[:1]) + 20
    room_row_h = rooms[0].height // 2 + 10
    Hc = 60 + sum(p.height + 12 for p in parts) + room_row_h * 2 + 20
    sheet = Image.new('RGB', (Wc, Hc), (14, 10, 20))
    d = ImageDraw.Draw(sheet)
    d.text((12, 10), '신인류 콘셉트 4방향 (S17-C) — P2 48px · 손으로 찍은 도트 · 정수 배율. 이름은 가제(시나리오 확정 전)',
           font=f16, fill=(236, 214, 255))
    d.text((12, 34), '고르는 법: A 볏+발광선 / B 부채 깃 / C 유리 방울+아귀 등 / D 해파리 망토. 섞어도 된다(예: C의 눈 + B의 깃).',
           font=f12, fill=(190, 176, 210))
    y = 60
    for p in parts:
        sheet.paste(p.convert('RGB'), (10, y))
        y += p.height + 12
    for i, pl in enumerate(rooms):
        half = pl.resize((pl.width // 2, pl.height // 2), Image.NEAREST)
        sheet.paste(half.convert('RGB'), (10 + (i % 2) * (half.width + 10), y + (i // 2) * (half.height + 10)))
    sheet.save(os.path.join(REP, 'char_S17_concept.png'))
    json.dump({'lineage_checks': {'%s/%s/%s/%s' % k: v for k, v in lin_check.items()},
               'lineage_x_imprint_total': lin_tot_imp, 'lineage_x_hair_face_total': lin_tot_hf},
              io.open(os.path.join(OUT, 'concept_checks.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('[ok] newhumans concept →', OUT, '· contact sheet →', os.path.join(REP, 'char_S17_concept.png'))


if __name__ == '__main__':
    main()
