# -*- coding: utf-8 -*-
"""
gen_chars_newhumans_proto.py — 「심해 계승자」 신인류 시제품 (스프린트 17-C2)

두 계보만 완성도까지: 등불눈(보는 사람) · 물결팔(물살을 타는 사람). **생성 AI 없음** — 도형 원시함수로 좌표를 찍는다.
한 디자인을 「설계 단위(u)」로 한 번 그리고 세 밀도로 래스터한다:
  · 초상(카드)   160×224, s≈3.6, 몸을 1.3배 길게 — 인물 카드 공개·주민 카드
  · HI 스프라이트 셀 96 · 발 기준선 90 (= P2 64·60 의 1.5배). 방 배율 ×3 화면에서는 ×2 로 그린다(같은 화면 크기, 정수)
  · STD 대체     셀 64 · 발 기준선 60 (P2 와 같다). 카메라를 멀리 뺐을 때(×1·×2) 쓴다
밀도가 높을수록 디테일(속눈썹·머리 결·옷 장식·후광 점묘)이 켜진다 — 같은 디자인이 각 밀도의 픽셀을 제값으로 쓴다.
발광·빛 입자·뒤늦게 따라오는 움직임(머리·옷자락·리본)은 외곽선 뒤에 얹어 선명하게 둔다.
실행: PYTHONIOENCODING=utf-8 python tools/gen_chars_newhumans_proto.py
"""
import os, sys, io, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_chars_p2 as G
from PIL import Image, ImageDraw

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'static', 'art', 'chars', 'newhumans', 'proto')
REP = os.path.join(ROOT, 'docs', 'reports')
Cv = G.Cv
TAU = math.pi * 2

PAL = {
    # 공통 — 창백한 살구빛(성경 C2), 큰 눈
    'pSkin': (248, 228, 214), 'pSkinM': (232, 200, 186), 'pSkinD': (198, 160, 152), 'pBlush': (242, 150, 150),
    'pMouth': (148, 66, 78), 'pEyeD': (24, 18, 40), 'pWhite': (255, 255, 255), 'pLine': (20, 14, 34), 'pLash': (36, 22, 46),
    # 등불눈 — 남빛 · 진주 · 금(발광 하나)
    'lHair': (30, 34, 70), 'lHairM': (50, 60, 112), 'lHairL': (88, 108, 176), 'lBrow': (40, 40, 80),
    'lCoatD': (20, 26, 66), 'lCoat': (34, 48, 114), 'lCoatL': (62, 86, 164),
    'lPearl': (234, 230, 246), 'lPearlD': (176, 170, 208), 'lGold': (216, 172, 80), 'lGoldD': (140, 104, 46),
    'lIris': (76, 66, 156), 'lG1': (178, 128, 52), 'lG2': (255, 212, 108), 'lG3': (255, 246, 200),
    # 물결팔 — 청록 · 물거품 흰빛 · 물빛(발광 하나)
    'wHair': (234, 248, 246), 'wHairM': (176, 224, 220), 'wHairD': (84, 160, 162), 'wBrow': (60, 120, 126),
    'wSuitD': (12, 54, 64), 'wSuit': (24, 108, 116), 'wSuitL': (66, 170, 166), 'wTrim': (232, 246, 248),
    'wRib': (198, 246, 242), 'wRibM': (124, 214, 212), 'wRibD': (54, 142, 150), 'wIris': (24, 124, 136),
    'wG1': (42, 150, 172), 'wG2': (132, 240, 255), 'wG3': (224, 255, 255),
}
GLOW_KEYS = {'lG1', 'lG2', 'lG3', 'wG1', 'wG2', 'wG3', 'pWhite', 'pEyeD', 'pLine'}

LIN = {
    'lampeye': dict(ko='등불눈', role='보는 사람', g=('lG1', 'lG2', 'lG3'), iris='lIris', brow='lBrow',
                    sig='등불 왕관(가운데 등 + 양쪽 빛살) · 눈동자 금빛 고리', base='남빛 · 진주', accent='금빛'),
    'wavearm': dict(ko='물결팔', role='물살을 타는 사람', g=('wG1', 'wG2', 'wG3'), iris='wIris', brow='wBrow',
                    sig='팔뚝에서 흘러나와 뒤로 끌리는 물결 리본 · 물마루 앞머리', base='청록 · 물거품 흰빛', accent='물빛'),
}


class R:
    """설계 단위 → 픽셀. 발 원점(0,0), y 는 위로. T = 목 아래 세로 늘림(초상만 1.3)."""

    def __init__(self, w, h, base, s, T=1.0, cx=None):
        self.c = Cv(w, h)
        self.g = Cv(w, h)                 # 발광·입자(외곽선 뒤)
        self.s, self.T = s, T
        self.cx = (w / 2.0) if cx is None else cx
        self.fy = base - 1
        self.D = s >= 1.4                 # 중간 디테일(HI)
        self.DD = s >= 3.0                # 높은 디테일(초상)

    def V(self, v):
        return v * self.T if v <= 27 else v + 27 * (self.T - 1)

    def X(self, u):
        return self.cx + u * self.s

    def Y(self, v):
        return self.fy - self.V(v) * self.s

    def P(self, u, v):
        return (self.X(u), self.Y(v))

    def ell(self, u, v, ru, rv, t, cv=None, only=None):
        cv = cv or self.c
        rx, ry = max(.5, ru * self.s), max(.5, rv * self.s * (self.T if v <= 27 else 1.0))
        if only:
            cv.ell_in(self.X(u), self.Y(v), rx, ry, t, only=only)
        else:
            cv.ell(self.X(u), self.Y(v), rx, ry, t)

    def poly(self, pts, t, cv=None, only=None):
        cv = cv or self.c
        P = [self.P(u, v) for u, v in pts]
        ys = [p[1] for p in P]
        for y in range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1):
            xs = []
            for i in range(len(P)):
                (x0, y0), (x1, y1) = P[i], P[(i + 1) % len(P)]
                if (y0 <= y + .5 < y1) or (y1 <= y + .5 < y0):
                    xs.append(x0 + (y + .5 - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for x in range(int(round(xs[k])), int(round(xs[k + 1]))):
                    if only is None or cv.get(x, y) in only:
                        cv.set(x, y, t)

    def line(self, pts, t, w=1.0, cv=None):
        cv = cv or self.c
        ww = max(1, int(round(w * self.s))) if w > 0 else 1
        for a, b in zip(pts, pts[1:]):
            G.seg(cv, self.P(*a), self.P(*b), t, ww)

    def dot(self, u, v, t, cv=None, r=0.0):
        cv = cv or self.g
        if r * self.s >= 1.0:
            cv.ell(self.X(u), self.Y(v), r * self.s, r * self.s, t)
        else:
            cv.set(self.X(u), self.Y(v), t)


# ── 얼굴 ────────────────────────────────────────────────────────────────
def eye(r, u, v, lid, w=1.0, glance=0.0):
    L = LIN[lid]
    rx, ry = 1.75 * w, 2.15
    r.ell(u, v, rx, ry, 'pEyeD')
    r.ell(u + glance * .4, v - .25, rx * .78, ry * .76, L['iris'])
    if lid == 'lampeye':                                   # 눈동자 둘레 금빛 고리(발광)
        ring_r = rx * .62 * r.s
        if ring_r >= 1.6:
            G.ring(r.g, r.X(u + glance * .4), r.Y(v - .25), ring_r, max(1.0, .3 * r.s), 'lG2')
        else:
            r.g.set(r.X(u + glance * .4), r.Y(v - 1.4), 'lG2')
    r.ell(u + glance * .5, v - .35, rx * .38, ry * .42, 'pEyeD')
    r.line([(u - rx, v + ry * .55), (u + rx, v + ry * .7)], 'pLash', .55)           # 윗 눈꺼풀 선
    if r.D:
        r.line([(u + rx * .8, v + ry * .7), (u + rx * 1.25, v + ry * 1.05)], 'pLash', .4)   # 바깥 속눈썹 한 올
    hx, hy = u - rx * .38, v + ry * .32
    r.ell(hx, hy, max(.45, .5 * w), .55, 'pWhite', cv=r.g) if r.D else r.g.set(r.X(hx), r.Y(hy), 'pWhite')
    if r.D:
        r.g.set(r.X(u + rx * .35), r.Y(v - ry * .45), 'pWhite')                    # 둘째 반짝임
    if r.DD:
        r.line([(u - rx * .7, v - ry * .95), (u + rx * .6, v - ry * 1.0)], 'pSkinD', .25)  # 아래 눈꺼풀


def face_front(r, lid, glance=0.0, q34=0.0):
    """정면(q34=0) 또는 3/4 왼쪽(q34=1). 눈·눈썹·입·홍조는 언제나."""
    L = LIN[lid]
    sh = -1.8 * q34
    ex = (-3.3 + sh, 3.3 + sh * 0.6)
    ew = (1.0 - .32 * q34, 1.0)
    for x_, w_ in zip(ex, ew):
        eye(r, x_, 34.0, lid, w_, glance)
    bw = .55
    if lid == 'lampeye':                                   # 부드럽게 올라간 눈썹(보는 사람)
        for x_ in ex:
            r.line([(x_ - 1.5, 37.0), (x_, 37.7), (x_ + 1.4, 37.5)], L['brow'], bw)
    else:                                                  # 자신 있게 곧은 눈썹(물살 타는 사람)
        for k, x_ in enumerate(ex):
            d = .5 if k == 0 else -.5
            r.line([(x_ - 1.5, 37.2 + d * .4), (x_ + 1.5, 37.6 - d * .4)], L['brow'], bw)
    mx = sh * .7
    r.line([(mx - 1.1, 30.7), (mx, 30.2), (mx + 1.1, 30.7)], 'pMouth', .45)
    if r.DD:
        r.line([(mx - .5, 30.0), (mx + .5, 30.0)], 'pBlush', .25)
    if r.D:
        r.c.set(r.X(mx + .4), r.Y(32.1), 'pSkinD')                                 # 코끝
    for x_ in ex:
        r.ell(x_ + (-1.3 if x_ < mx else 1.3), 31.6, 1.2, .55, 'pBlush', only=('pSkin', 'pSkinM'))


def face_side(r, lid):
    L = LIN[lid]
    eye(r, 3.6, 34.0, lid, .82, glance=.6)
    r.line([(2.3, 37.3), (3.6, 37.8), (4.9, 37.5)], L['brow'], .55)
    r.c.set(r.X(8.9), r.Y(32.6), 'pSkin'); r.c.set(r.X(8.9), r.Y(32.0), 'pSkinM')
    if r.s >= 1.4:
        r.ell(8.85, 32.4, .45, .6, 'pSkin')
    r.line([(5.3, 30.9), (6.4, 30.4), (7.2, 30.6)], 'pMouth', .45)
    r.ell(2.4, 31.6, 1.1, .55, 'pBlush', only=('pSkin', 'pSkinM'))


# ── 머리·몸 ─────────────────────────────────────────────────────────────
def head(r, lid, view, sway, glow):
    """sway: 머리카락·장식이 한 박자 늦게 따라오는 양(−1~1)."""
    hcx = .6 if view == 'side' else (-.6 if view == 'q34' else 0.0)
    # 뒷머리(몸보다 먼저 그려지는 부분은 body() 앞에서 따로) — 여기선 머리통 위
    r.ell(hcx, 35.5, 8.5, 8.5, 'pSkin')
    r.ell(hcx + 1.6, 33.8, 7.2, 6.6, 'pSkinM', only=('pSkin',))
    r.ell(hcx - .6, 35.0, 7.4, 7.6, 'pSkin', only=('pSkinM',))
    if lid == 'lampeye':
        H, HM, HL = 'lHair', 'lHairM', 'lHairL'
        if view == 'side':
            r.poly([(-8.6, 36), (-6, 43.6), (2, 44.3), (7.6, 40.5), (8.2, 37.6), (4.5, 39.6), (1.5, 38.8), (-1.2, 36.0), (-3.0, 30.6), (-8.3, 31.0)], H)
        else:
            r.poly([(-8.9, 34), (-7.6, 41.6), (-3, 44.4), (3, 44.4), (7.6, 41.6), (8.9, 34), (7.9, 30.8),
                    (6.4, 37.6), (2.2, 38.4), (0, 37.0) if view == 'front' else (-1.2, 37.4), (-2.2, 38.4), (-6.4, 37.6), (-7.9, 30.8)], H)
        r.poly([(-6.5, 41.4), (-2.5, 43.6), (2.5, 43.6), (5.5, 42), (1.5, 42.4), (-3.5, 42.2)], HM)
        if r.D:
            for k in range(-3, 4):
                r.line([(k * 1.8, 43.5), (k * 2.2 + .6, 39.4)], HL if k % 2 else HM, .3)
        # 왕관: 이마 테 + 가운데 등 + 양쪽 빛살(실루엣 서명)
        r.line([(-6.8, 41.0), (-3.0, 42.6), (0, 43.0), (3.0, 42.6), (6.8, 41.0)], 'lGold', .7)
        r.line([(-6.8, 40.6), (6.8, 40.6)], 'lGoldD', .3) if r.D else None
        stem_top = 49.2 + .25 * sway
        r.line([(0, 43.0), (0, stem_top)], 'lGoldD', .55)
        r.poly([(-1.3, 43.4), (0, 45.6), (1.3, 43.4)], 'lGold')
        for sgn in (-1, 1):
            if view == 'side' and sgn < 0:
                continue
            r.line([(sgn * 3.0, 42.6), (sgn * 4.6, 45.8), (sgn * 5.6, 48.0 + .2 * sway)], 'lGold', .45)
            r.dot(sgn * 5.6, 48.6 + .2 * sway, glow[1], r=.55)
        r.dot(0, stem_top + 1.6, glow[2], r=1.65)                                   # 등 — 숨 박자로 밝아진다
        r.dot(0, stem_top + 1.6, glow[1], r=.9)
        if r.D:                                            # 후광 점묘
            hr_ = 3.4 * r.s
            for a in range(0, 360, 30 if r.DD else 45):
                x = r.X(0) + hr_ * math.cos(math.radians(a))
                y = r.Y(stem_top + 1.6) + hr_ * math.sin(math.radians(a))
                if r.g.own(x, y) is None:
                    r.g.set(x, y, glow[0])
        # 광대 점 셋(별자리)
        for (u, v) in ((-5.4, 32.6), (-6.2, 31.4), (-4.6, 31.0)):
            if view != 'side':
                r.dot(u - (1.2 if view == 'q34' else 0), v, glow[1])
        if view == 'side':
            for (u, v) in ((1.4, 32.4), (.6, 31.2)):
                r.dot(u, v, glow[1])
    else:
        H, HM, HD = 'wHair', 'wHairM', 'wHairD'
        if view == 'side':
            r.poly([(-8.6, 33), (-7.6, 41), (-2, 44.8), (5, 44.2), (8.6, 40.6), (6.4, 38.2), (3, 39.2), (0, 37.6), (-2.6, 31), (-6, 29.6)], H)
        else:
            r.poly([(-9.0, 33), (-8.2, 40.6), (-3.6, 44.6), (3.4, 44.8), (8.4, 41.0), (9.0, 33.6), (7.6, 31.6),
                    (6.6, 37.0), (3.6, 38.6), (1.6, 37.4), (-1.6, 38.6), (-4.6, 37.2), (-6.8, 37.6), (-7.8, 31.4)], H)
        r.poly([(-7.8, 38), (-6, 42.6), (-2, 44), (-4.4, 40.2)], HM)
        # 물마루 앞머리 — 오른쪽 위로 말려 올라간다(실루엣 서명). sway 로 끝이 늦게 따라온다
        cx_ = 1.0 if view != 'q34' else -1.0
        tip = (cx_ + 7.2 + .7 * sway, 48.8 + .4 * sway)
        r.poly([(cx_ + .5, 43.6), (cx_ + 4.5, 46.6), tip, (cx_ + 8.6 + .6 * sway, 46.0), (cx_ + 6.8, 43.0), (cx_ + 3.8, 42.2)], H)
        r.line([(cx_ + 1.5, 43.8), (cx_ + 5, 46.2), (tip[0] - .6, tip[1] - .7)], HM, .35)
        if r.D:
            for k in range(-3, 3):
                r.line([(k * 2.2 - .5, 43.0), (k * 2.0 + .6, 38.8)], HD if k % 2 else HM, .3)
        r.ell(tip[0] + .2, tip[1] + .1, .5, .5, HD)
    return hcx


def legs_front(r, lid, body):
    D_, M_ = ('lCoatD', 'lCoat') if lid == 'lampeye' else ('wSuitD', 'wSuit')
    for sgn in (-1, 1):
        r.poly([(sgn * 1.0, 13), (sgn * 4.4, 13), (sgn * 4.0, 2.4), (sgn * 1.4, 2.4)], D_)
        r.poly([(sgn * 1.0, 3.2), (sgn * 4.6, 3.2), (sgn * 5.0, 0), (sgn * .8, 0)], M_)
        if lid == 'lampeye':
            r.line([(sgn * 1.2, .3), (sgn * 4.6, .3)], 'lGold', .45)
        else:                                              # 장화 깃(지느러미 모양 장식 — 옷이다)
            r.poly([(sgn * 4.0, 3.4), (sgn * 6.2, 5.2), (sgn * 4.6, 2.0)], 'wTrim')


def torso_front(r, lid, body, q34=0.0):
    nb = -0.9 if body == 'b' else 0.0
    wz = -0.9 if body == 'b' else 0.0
    if lid == 'lampeye':
        # 진주 속옷 + 남빛 긴 외투(A라인, 밑단이 퍼진다) + 금 테 + 높은 깃
        r.poly([(-6.6 - nb * 0, 27), (6.6, 27), (7.2 + nb, 21), (6.0 + wz, 15), (8.6, 4.2), (-8.6, 4.2), (-6.0 - wz, 15), (-7.2 - nb, 21)], 'lCoat')
        r.poly([(-6.6, 27), (-1.6, 27), (-1.0, 4.2), (-8.6, 4.2), (-6.0 - wz, 15), (-7.2 - nb, 21)], 'lCoatL', only=('lCoat',))
        r.poly([(3.0, 27), (6.6, 27), (7.2 + nb, 21), (6.0 + wz, 15), (8.6, 4.2), (4.6, 4.2)], 'lCoatD', only=('lCoat', 'lCoatL'))
        r.poly([(-1.4, 26.6), (1.4, 26.6), (1.8, 4.4), (-1.8, 4.4)], 'lPearl')
        r.poly([(.4, 26.6), (1.4, 26.6), (1.8, 4.4), (.6, 4.4)], 'lPearlD', only=('lPearl',))
        r.line([(-1.6, 26.6), (-2.0, 4.4)], 'lGold', .4); r.line([(1.6, 26.6), (2.0, 4.4)], 'lGold', .4)
        r.line([(-8.6, 4.4), (8.6, 4.4)], 'lGold', .55)
        r.line([(-6.0 - wz, 15.0), (6.0 + wz, 15.0)], 'lGoldD', .5)
        r.poly([(-4.2, 26.4), (-3.4, 29.4), (3.4, 29.4), (4.2, 26.4)], 'lCoatD')      # 높은 깃
        r.line([(-3.4, 29.3), (3.4, 29.3)], 'lGold', .4)
        if r.D:
            for (u, v) in ((-6.0, 7.2), (-4.4, 9.4), (5.0, 8.0), (6.6, 10.6), (-7.0, 11.8)):
                r.c.set(r.X(u), r.Y(v), 'lG1')             # 외투 아래 별 점(발광은 아님 — 금실)
    else:
        # 몸에 붙는 청록 잠수 재킷 + 흰 이음선 + 짧은 깃
        r.poly([(-6.0, 27), (6.0, 27), (6.8 + nb, 21), (5.2 + wz, 15), (5.8, 11.6), (-5.8, 11.6), (-5.2 - wz, 15), (-6.8 - nb, 21)], 'wSuit')
        r.poly([(-6.0, 27), (-1.0, 27), (-1.4, 11.6), (-5.8, 11.6), (-5.2 - wz, 15), (-6.8 - nb, 21)], 'wSuitL', only=('wSuit',))
        r.poly([(3.2, 27), (6.0, 27), (6.8 + nb, 21), (5.2 + wz, 15), (5.8, 11.6), (3.6, 11.6)], 'wSuitD', only=('wSuit', 'wSuitL'))
        r.line([(0, 27), (.4, 12.0)], 'wTrim', .4)
        r.line([(-5.6, 22.6), (-1.8, 19.4)], 'wTrim', .35); r.line([(5.6, 22.6), (1.8, 19.4)], 'wTrim', .35)
        r.poly([(-5.8, 12.8), (5.8, 12.8), (5.6, 11.0), (-5.6, 11.0)], 'wSuitD')
        r.poly([(-3.8, 26.4), (-3.2, 28.6), (3.2, 28.6), (3.8, 26.4)], 'wTrim')
    r.poly([(-1.2, 26.4), (1.2, 26.4), (1.0, 28.8), (-1.0, 28.8)], 'pSkinM')         # 목


def arm(r, lid, sh, hand, near=True):
    """어깨 → 손. 등불눈은 넓은 소매, 물결팔은 몸에 붙는 소매 + 팔찌."""
    if lid == 'lampeye':
        t, tl = ('lCoat', 'lCoatL') if near else ('lCoatD', 'lCoatD')
        mid = ((sh[0] + hand[0]) / 2.0, (sh[1] + hand[1]) / 2.0)
        r.line([sh, mid], t, 2.6)
        cuff = (hand[0] + (sh[0] - hand[0]) * .22, hand[1] + (sh[1] - hand[1]) * .22)
        r.line([mid, cuff], t, 2.8)
        r.poly([(cuff[0] - 2.0, cuff[1] + .6), (cuff[0] + 2.0, cuff[1] + .6), (cuff[0] + 2.4, cuff[1] - 1.4), (cuff[0] - 2.4, cuff[1] - 1.4)], t)
        r.line([(cuff[0] - 2.4, cuff[1] - 1.4), (cuff[0] + 2.4, cuff[1] - 1.4)], 'lGold', .4)
    else:
        t = 'wSuit' if near else 'wSuitD'
        r.line([sh, hand], t, 2.4)
        cuff = (hand[0] + (sh[0] - hand[0]) * .3, hand[1] + (sh[1] - hand[1]) * .3)
        r.line([(cuff[0] - 1.2, cuff[1]), (cuff[0] + 1.2, cuff[1])], 'wTrim', .9)   # 팔찌
    r.ell(hand[0], hand[1], 1.35, 1.35, 'pSkin')
    if r.D:
        r.ell(hand[0] + .4, hand[1] - .3, .8, .8, 'pSkinM', only=('pSkin',))
    return cuff


def ribbon(r, start, f, n_frames, trail_dir, lag=1, length=17, amp=1.5, phase0=0.0, lift=0.0):
    """물결 리본 — 팔찌에서 시작해 뒤로 끌린다. 한 박자 늦게(lag) 같은 물결을 따라 그린다.
    빛(발광)이 리본을 따라 바깥으로 흘러간다."""
    pts = []
    ph = TAU * ((f - lag) % n_frames) / n_frames + phase0
    for k in range(0, length + 1):
        u = start[0] + trail_dir * k * 1.0
        v = start[1] - k * .42 + lift * k / length + amp * math.sin(ph + k * .55) * (k / float(length)) ** .8
        pts.append((u, v))
    w_ = [1.6 - .9 * k / length for k in range(len(pts))]
    for i in range(len(pts) - 1):
        r.line([pts[i], pts[i + 1]], 'wRibM', max(.6, w_[i]))
    for i in range(len(pts) - 1):
        r.line([(pts[i][0], pts[i][1] + .45), (pts[i + 1][0], pts[i + 1][1] + .45)], 'wRib', max(.35, w_[i] * .45))
    flow = int((f % n_frames) * (length / float(n_frames))) % length       # 빛이 흐른다
    for i, (u, v) in enumerate(pts):
        if (i - flow) % 6 == 0:
            r.dot(u, v + .2, 'wG3' if i > 2 else 'wG2')
        elif (i - flow) % 6 == 1 and r.D:
            r.dot(u, v + .2, 'wG2')
    return pts


def wave_marks(r, sh, hand, f, n):
    """물결팔 계보 서명 — 팔뚝 물결 빛이 손목에서 어깨로 흐른다."""
    for k in range(5):
        t = ((k + f * 5.0 / n) % 5) / 5.0
        u = hand[0] + (sh[0] - hand[0]) * (.15 + .5 * t) + .5 * math.sin(k * 1.7)
        v = hand[1] + (sh[1] - hand[1]) * (.15 + .5 * t)
        r.dot(u, v, 'wG2' if k % 2 == 0 else 'wG1')


# ── 동작 ────────────────────────────────────────────────────────────────
def glow_level(lid, f, n):
    """숨 박자 — 0 어둠 → 2 밝음 → 0. 세 단."""
    g1, g2, g3 = LIN[lid]['g']
    lv = [0, 1, 2, 1][int(4 * f / n) % 4]
    return [(g1, g1, g2), (g1, g2, g3), (g2, g3, g3)][lv]


def draw_front(r, lid, body, f, n, clip='idle'):
    breath = [0, .25, .5, .25][int(4 * f / n) % 4] if clip == 'idle' else 0
    glow = glow_level(lid, f, n)
    sway = math.sin(TAU * (f - 1) / n) * (.6 if clip == 'idle' else .3)
    q = 1.0 if clip == 'work_34' else 0.0
    # 뒷머리(등불눈 긴 머리) — 몸 뒤
    if lid == 'lampeye':
        r.poly([(-8.6, 36), (8.6, 36), (8.0 + .4 * sway, 17.4), (5.0, 15.6 + .3 * sway), (-5.0, 15.6 - .3 * sway), (-8.0 + .4 * sway, 17.4)], 'lHair')
        if r.D:
            r.line([(-6.4, 33), (-6.6 + .4 * sway, 18.4)], 'lHairM', .35)
            r.line([(6.4, 33), (6.6 + .4 * sway, 18.4)], 'lHairM', .35)
    legs_front(r, lid, body)
    torso_front(r, lid, body, q)
    shy = 25.6 - breath
    shl, shr = (-6.4, shy), (6.4, shy)
    if clip == 'work_34':
        wk = [0, 1, 2][f % 3]
        if lid == 'lampeye':                               # 손바닥 위 작은 등을 들여다본다
            hl = (-3.6, 19.6 + wk * .6)
            hr = (5.2, 14.6)
        else:                                              # 두 손으로 물살을 빚는다
            hl = (-6.0 - wk * .8, 18.4 + wk * .5)
            hr = (1.2 - wk * .5, 19.6 - wk * .4)
    else:
        hl, hr = (-7.6, 13.4 + breath * .5), (7.6, 13.4 + breath * .5)
    if lid == 'wavearm':                                   # 리본은 팔 뒤에서 시작해 위로 말려 오른다(1차: 활처럼 보였다)
        for sh, hd in ((shl, hl), (shr, hr)):
            sgn = -1 if hd[0] < 0 else 1
            cuff0 = (hd[0] + (sh[0] - hd[0]) * .3, hd[1] + (sh[1] - hd[1]) * .3)
            ph_ = TAU * ((f - 1) % n) / n + (0 if sgn < 0 else 1.7)
            pts = bez(cuff0, (cuff0[0] + sgn * 5.0, cuff0[1] + 1.0), (cuff0[0] + sgn * 7.5 + .8 * math.sin(ph_), cuff0[1] + 9.0),
                      (cuff0[0] + sgn * 4.0 + 1.2 * math.sin(ph_), cuff0[1] + 15.0 + .8 * math.cos(ph_)), 16)
            band(r, pts, 1.4, .6, 'wRibM')
            band(r, [(u, v + .45) for u, v in pts], .5, .3, 'wRib')
            r.rib_pts = getattr(r, 'rib_pts', []) + [pts]
    cuffs = []
    for sh, hd, near in ((shr, hr, False), (shl, hl, True)):
        cuffs.append((sh, hd, arm(r, lid, sh, hd, near)))
    hcx = head(r, lid, 'q34' if q else 'front', sway, glow)
    face_front(r, lid, glance=(-.8 if q else 0.0), q34=q)
    # 발광·입자(외곽선 뒤)
    if lid == 'wavearm':
        for sh, hd, cuff in cuffs:
            wave_marks(r, sh, hd, f, n)
            sgn = -1 if hd[0] < 0 else 1
        flow = f * 4
        for pts in getattr(r, 'rib_pts', []):              # 리본을 따라 바깥으로 흐르는 빛
            for i, (u, v) in enumerate(pts):
                if (i - flow) % 6 == 0 and i > 1:
                    r.dot(u, v + .2, 'wG3')
                elif (i - flow) % 6 == 1 and r.D and i > 1:
                    r.dot(u, v + .2, 'wG2')
    if lid == 'lampeye' and clip == 'work_34':
        wk = f % 3
        r.dot(hl[0], hl[1] + 2.2, glow[2], r=1.4)
        r.dot(hl[0], hl[1] + 2.2, glow[1], r=.7)
        for k in range(3):                                 # 등에서 오르는 빛 알갱이
            r.dot(hl[0] + (k - 1) * 1.6, hl[1] + 4.2 + ((wk + k) % 3) * 1.5, glow[(k + wk) % 2])
    return r


def draw_side(r, lid, body, f, n):
    th = TAU * f / n
    thl = TAU * (f - 1) / n                                # 한 박자 늦은 위상(옷자락·머리·리본)
    bob = .7 * abs(math.cos(th))
    glow = glow_level(lid, f, n)
    nx, fx = 4.0 * math.sin(th), -4.0 * math.sin(th)
    nl, fl = 1.6 * max(0, math.cos(th)), 1.6 * max(0, -math.cos(th))
    D_, M_, L_ = ('lCoatD', 'lCoat', 'lCoatL') if lid == 'lampeye' else ('wSuitD', 'wSuit', 'wSuitL')
    # 뒤로 날리는 것 먼저: 등불눈 긴 머리 · 외투 자락
    if lid == 'lampeye':
        sw = math.sin(thl)
        r.poly([(-7.6, 37 + bob), (-1.0, 38 + bob), (-3.0, 24 + bob), (-6.4 - 1.2 * sw, 16.0 + bob), (-9.6 - 1.6 * sw, 17.6 + bob), (-9.0, 28 + bob)], 'lHair')
        if r.D:
            r.line([(-6.0, 34 + bob), (-8.2 - 1.4 * sw, 18.6 + bob)], 'lHairM', .35)
    # 먼 팔 · 먼 다리
    sha = (-.3, 25.6 + bob)
    a_far = math.radians(22 * math.sin(th))
    hfar = (sha[0] + 11.2 * math.sin(a_far), sha[1] - 11.2 * math.cos(a_far))
    cfar = arm(r, lid, sha, hfar, near=False)
    for dx, lift, far in ((fx, fl, True), (nx, nl, False)):
        hip = (-.4 if far else .4, 13 + bob)
        ank = (dx, 2.4 + lift)
        r.line([hip, ((hip[0] + ank[0]) / 2 + .6, (hip[1] + ank[1]) / 2), ank], D_ if far else M_, 3.0)
        r.poly([(dx - 2.0, 3.0 + lift), (dx + 2.6, 3.0 + lift), (dx + 3.4, lift), (dx - 2.0, lift)], D_ if far else M_)
        if lid == 'lampeye':
            r.line([(dx - 2.0, lift + .3), (dx + 3.4, lift + .3)], 'lGoldD' if far else 'lGold', .4)
        else:
            r.poly([(dx - 1.6, 3.2 + lift), (dx - 4.0 - .8 * math.sin(thl), 4.6 + lift), (dx - 1.4, 1.8 + lift)], 'wTrim' if not far else 'wRibD')
    # 몸통(옆) + 외투 자락 뒤로
    if lid == 'lampeye':
        sw = math.sin(thl)
        r.poly([(-4.0, 27 + bob), (4.2, 27 + bob), (4.6, 18 + bob), (4.0, 15 + bob), (6.4, 4.6 + bob), (-6.6 - 1.8 * sw, 4.0 + bob), (-8.4 - 2.4 * sw, 5.8 + bob), (-4.6, 15 + bob)], M_)
        r.poly([(-4.0, 27 + bob), (-.6, 27 + bob), (-1.4, 4.6 + bob), (-6.6 - 1.8 * sw, 4.0 + bob), (-8.4 - 2.4 * sw, 5.8 + bob), (-4.6, 15 + bob)], L_, only=(M_,))
        r.line([(3.8, 26.4 + bob), (5.6, 4.8 + bob)], 'lGold', .4)
        r.line([(-8.4 - 2.4 * sw, 5.6 + bob), (6.4, 4.8 + bob)], 'lGold', .5)
        r.line([(-4.4, 15 + bob), (4.0, 15 + bob)], 'lGoldD', .5)
        r.poly([(-2.8, 26.4 + bob), (-2.2, 29.4 + bob), (2.6, 29.4 + bob), (3.2, 26.4 + bob)], D_)
        r.line([(-2.2, 29.3 + bob), (2.6, 29.3 + bob)], 'lGold', .4)
    else:
        r.poly([(-4.0, 27 + bob), (4.0, 27 + bob), (4.6, 20 + bob), (3.6, 15 + bob), (4.0, 11.4 + bob), (-4.2, 11.4 + bob), (-3.8, 15 + bob), (-4.4, 21 + bob)], M_)
        r.poly([(-4.0, 27 + bob), (-1.0, 27 + bob), (-1.6, 11.4 + bob), (-4.2, 11.4 + bob), (-3.8, 15 + bob), (-4.4, 21 + bob)], L_, only=(M_,))
        r.line([(3.4, 26.6 + bob), (3.6, 12 + bob)], 'wTrim', .35)
        r.poly([(-2.8, 26.4 + bob), (-2.4, 28.6 + bob), (2.8, 28.6 + bob), (3.2, 26.4 + bob)], 'wTrim')
    r.poly([(-.8, 26.4 + bob), (1.4, 26.4 + bob), (1.2, 28.8 + bob), (-.8, 28.8 + bob)], 'pSkinM')
    # 머리
    r_bob = bob
    r.cx_save = r.cx
    r.fy_save = r.fy
    r.fy = r.fy - r_bob * r.s
    head(r, lid, 'side', math.sin(thl), glow)
    face_side(r, lid)
    r.fy = r.fy_save
    # 가까운 팔
    a_near = math.radians(-22 * math.sin(th) + 4)
    hnear = (sha[0] + .6 + 11.2 * math.sin(a_near), sha[1] - 11.2 * math.cos(a_near))
    cnear = arm(r, lid, (sha[0] + .6, sha[1]), hnear, near=True)
    # 발광·입자
    if lid == 'wavearm':
        wave_marks(r, (sha[0] + .6, sha[1]), hnear, f, n)
        ribbon(r, cnear, f, n, -1, lag=1, length=17, amp=1.8, lift=2.0)
        ribbon(r, cfar, f, n, -1, lag=1, length=15, amp=1.6, phase0=1.4, lift=2.4)
    for k in range(4):                                     # 걸을 때 남는 빛 알갱이
        age = (f + k * (n // 4 if n >= 4 else 1)) % n
        u = -2.0 - age * 1.5 - k * .8
        v = 1.0 + age * 1.0 + (k % 2) * .8
        g1, g2, g3 = LIN[lid]['g']
        r.dot(u, v, g3 if age < n / 3 else (g2 if age < 2 * n / 3 else g1))
    return r


def render(lid, body, clip, f, cell, base, s, T=1.0):
    n = {'idle': 4, 'walk_side': 6, 'work_34': 3}[clip]
    r = R(cell[0], cell[1], base, s, T)
    if clip == 'walk_side':
        draw_side(r, lid, body, f, n)
    else:
        draw_front(r, lid, body, f, n, clip)
    r.c.outline('pLine')
    im = r.c.img()
    im.alpha_composite(r.g.img())
    return im, r




# ══ 초상 전용 그림(S17-C2 2차) — 스프라이트를 키운 것이 아니라 따로 그린 일러스트 ══════════════
#   비율 약 4등신(머리 16u / 키 61u), 움직임 있는 자세, 재질마다 3단 음영, 발광원에서 오는 테두리 빛(림 라이트).
def bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / float(n)
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def band(r, pts, w0, w1, t, cv=None):
    """굵기가 변하는 띠(옷자락·머리 갈래·리본)."""
    n = len(pts) - 1
    for i in range(n):
        w = w0 + (w1 - w0) * i / float(max(1, n))
        r.line([pts[i], pts[i + 1]], t, w, cv=cv)


def rim_light(cv, light_xy, radius, col, only):
    """발광원 쪽으로 빈 칸을 마주한 가장자리 픽셀에 빛을 얹는다(외곽선 전에)."""
    lx, ly = light_xy
    add = []
    for (x, y) in cv.pixels():
        if cv.own(x, y) not in only:
            continue
        d = math.hypot(x - lx, y - ly)
        if d > radius:
            continue
        sx = 1 if lx > x else -1
        sy = 1 if ly > y else -1
        if cv.own(x + sx, y) is None or cv.own(x, y + sy) is None:
            add.append((x, y))
    for (x, y) in add:
        cv.set(x, y, col)


def p_eye(r, u, v, lid, glow, w=1.0, look=0.0):
    """초상 눈 — 큰 눈, 홍채 그라데이션, (등불눈) 금빛 고리, 반짝임 둘, 속눈썹."""
    L = LIN[lid]
    rx, ry = 2.25 * w, 2.75
    r.ell(u, v, rx + .25, ry + .2, 'pLash')
    r.ell(u, v - .15, rx, ry, 'pWhite')
    iu = u + look
    r.ell(iu, v - .3, rx * .86, ry * .9, 'pEyeD')
    r.ell(iu, v - .5, rx * .72, ry * .74, L['iris'])
    r.ell(iu, v - 1.2, rx * .6, ry * .42, 'lCoatL' if lid == 'lampeye' else 'wSuitL', only=(L['iris'],))
    if lid == 'lampeye':
        G.ring(r.g, r.X(iu), r.Y(v - .5), rx * .62 * r.s, 1.6, glow[2])
        G.ring(r.g, r.X(iu), r.Y(v - .5), rx * .62 * r.s - 1.4, 1.0, glow[1])
    else:
        r.ell(iu, v - 1.4, rx * .5, ry * .22, 'wG2', cv=r.g)
    r.ell(iu, v - .4, rx * .3, ry * .36, 'pEyeD')
    r.line([(u - rx - .3, v + ry * .55), (u, v + ry * 1.0), (u + rx + .5, v + ry * .75)], 'pLash', .7)    # 윗 속눈썹 선
    r.line([(u + rx + .2, v + ry * .7), (u + rx + 1.2, v + ry * 1.15)], 'pLash', .45)                      # 바깥 꼬리
    r.line([(u + rx + .1, v + ry * .2), (u + rx + .9, v + ry * .35)], 'pLash', .35)
    r.ell(iu - rx * .32, v + ry * .2, .75, .85, 'pWhite', cv=r.g)                                          # 큰 반짝임
    r.ell(iu + rx * .34, v - ry * .55, .4, .4, 'pWhite', cv=r.g)                                           # 작은 반짝임
    r.line([(u - rx * .6, v - ry * 1.05), (u + rx * .5, v - ry * 1.1)], 'pSkinD', .3)                       # 아래 눈꺼풀


def p_face(r, lid, glow, hc, look=0.0):
    hx, hy = hc
    L = LIN[lid]
    for sgn in (-1, 1):
        p_eye(r, hx + sgn * 3.6, hy - 1.6, lid, glow, 1.0, look)
    if lid == 'lampeye':                                   # 부드러운 눈썹 · 다문 미소
        for sgn in (-1, 1):
            band(r, bez((hx + sgn * 1.9, hy + 3.3), (hx + sgn * 3.0, hy + 4.0), (hx + sgn * 4.6, hy + 4.0), (hx + sgn * 5.8, hy + 3.3), 8), .38, .3, L['brow'])   # 2차: 화나 보여 안쪽을 올리고 가늘게
        r.line([(hx - 1.2, hy - 6.4), (hx, hy - 6.9), (hx + 1.2, hy - 6.4)], 'pMouth', .45)
        for (u, v) in ((hx - 6.2, hy - 4.4), (hx - 6.9, hy - 3.2), (hx - 5.6, hy - 5.4)):                   # 광대 별자리
            r.dot(u, v, glow[1], r=.4)
    else:                                                  # 자신 있는 눈썹 · 송곳니 하나 보이는 웃음
        for sgn in (-1, 1):
            band(r, bez((hx + sgn * 1.8, hy + 4.2), (hx + sgn * 3.0, hy + 4.6), (hx + sgn * 4.4, hy + 4.4), (hx + sgn * 5.8, hy + 3.7), 8), .4, .28, L['brow'])   # 3차: 안쪽을 올려 웃는 자신감으로
        r.poly([(hx - 1.6, hy - 6.0), (hx + 1.8, hy - 5.8), (hx + .6, hy - 7.4), (hx - .8, hy - 7.3)], 'pMouth')
        r.poly([(hx - .9, hy - 7.0), (hx + .7, hy - 7.0), (hx + .3, hy - 7.4), (hx - .5, hy - 7.4)], 'pBlush')
        r.c.set(r.X(hx + 1.1), r.Y(hy - 6.1), 'pWhite')
    r.c.set(r.X(hx + .5), r.Y(hy - 4.4), 'pSkinD')
    for sgn in (-1, 1):
        r.ell(hx + sgn * 4.4, hy - 4.6, 1.5, .55, 'pBlush', only=('pSkin', 'pSkinM'))
        if r.DD:
            for k in (-1, 0, 1):
                r.c.set(r.X(hx + sgn * 4.4 + k * .8), r.Y(hy - 4.2), 'pSkin') if k else None


def portrait_lampeye(r, f, body):
    ph = TAU * f / 4.0
    phl = TAU * (f - 1) / 4.0
    glow = glow_level('lampeye', f, 4)
    b = .35 * math.sin(ph)                                 # 숨
    sw = math.sin(phl)                                     # 한 박자 늦은 흔들림
    nb = -.8 if body == 'b' else 0.0
    hc = (.4, 46.0 + b)
    # 1. 흐르는 긴 머리(뒤) — 물살에 왼쪽으로
    r.poly([(-8.2, 49 + b), (8.4, 49 + b), (9.2, 40), (8.0, 30), (5.4, 20 + .5 * sw), (1.0, 15 + sw), (-6.0, 13 + sw),
            (-13.4 - 1.2 * sw, 15.6 + sw), (-11.6 - .8 * sw, 22), (-10.8, 34), (-9.6, 42)], 'lHair')
    for k in range(6):
        x0 = -7.5 + k * 2.6
        band(r, bez((x0, 44 + b), (x0 - 1.5, 34), (x0 - 4 - 1.0 * sw, 24), (x0 - 7 - 1.4 * sw, 16 + sw)), .4, .25, 'lHairM' if k % 2 else 'lHairL')
    # 2. 외투 뒷자락 — 왼쪽으로 크게 날린다(실루엣)
    r.poly([(-6.5, 31), (6.5, 31), (9.4, 14), (10.4, 3.2), (4.0, 1.6), (-4.0, 1.4), (-12.0 - 1.6 * sw, 2.6 + .6 * sw),
            (-16.0 - 2.2 * sw, 5.6 + sw), (-11.4, 13), (-8.0, 22)], 'lCoat')
    band(r, bez((-4.0, 1.6), (-9.0, 1.8), (-13.0 - 1.6 * sw, 3.0 + .6 * sw), (-16.0 - 2.2 * sw, 5.6 + sw), 12), .9, .5, 'lPearl')   # 안감 — 밑단 가는 띠
    r.poly([(-6.5, 31), (-1.6, 31), (-2.4, 1.5), (-12.0 - 1.6 * sw, 2.6 + .6 * sw), (-16.0 - 2.2 * sw, 5.6 + sw), (-11.4, 13), (-8.0, 22)],
           'lCoatL', only=('lCoat',))
    r.poly([(3.6, 31), (6.5, 31), (9.4, 14), (10.4, 3.2), (6.0, 2.0)], 'lCoatD', only=('lCoat', 'lCoatL'))
    # 3. 장화
    for (x0, t) in ((-3.0, 'lCoatD'), (3.2, 'lCoat')):
        r.poly([(x0 - 1.8, 5.2), (x0 + 1.8, 5.2), (x0 + 2.6, 0), (x0 - 2.0, 0)], t)
        r.line([(x0 - 2.0, .4), (x0 + 2.6, .4)], 'lGold', .45)
    # 4. 몸통 — 진주 속옷, 금 테 앞섶, 금 띠
    r.poly([(-6.2 - nb, 35), (6.2 + nb, 35), (5.8 + nb * .5, 27), (5.2, 22), (7.6, 2.0), (-7.2, 2.0), (-5.2, 22), (-5.8 - nb * .5, 27)], 'lCoat')
    r.poly([(-6.2, 35), (-2.0, 35), (-2.6, 2.0), (-7.2, 2.0), (-5.2, 22), (-5.8, 27)], 'lCoatL', only=('lCoat',))
    r.poly([(-1.8, 34.6), (1.8, 34.6), (2.4, 2.2), (-2.4, 2.2)], 'lPearl')
    r.poly([(.6, 34.6), (1.8, 34.6), (2.4, 2.2), (.9, 2.2)], 'lPearlD', only=('lPearl',))
    for sgn in (-1, 1):
        r.line([(sgn * 1.9, 34.6), (sgn * 2.5, 2.2)], 'lGold', .5)
    r.poly([(-5.3, 23.4), (5.3, 23.4), (5.1, 21.2), (-5.1, 21.2)], 'lGold')
    r.poly([(-5.3, 21.6), (5.3, 21.6), (5.1, 21.2), (-5.1, 21.2)], 'lGoldD')
    r.line([(-7.2, 2.2), (7.6, 2.2)], 'lGold', .6)
    for k, (u, v) in enumerate(((-5.6, 6), (-4.0, 9.2), (5.0, 5.4), (6.0, 9.8), (-6.4, 13.2), (4.4, 14.4))):   # 금실 별(반짝임은 프레임마다 다르다)
        r.c.set(r.X(u), r.Y(v), 'lGold')
        if (k + f) % 3 == 0:
            r.dot(u, v, glow[2])
    r.poly([(-3.8, 34.4), (-3.2, 38.0), (3.2, 38.0), (3.8, 34.4)], 'lCoatD')                                       # 높은 깃
    r.line([(-3.3, 37.9), (3.3, 37.9)], 'lGold', .45)
    r.poly([(-1.3, 37.0), (1.3, 37.0), (1.1, 39.2), (-1.1, 39.2)], 'pSkinM')
    # 5. 왼팔(화면 왼쪽) — 외투 자락을 쥔다
    band(r, [(-6.0, 34.0), (-8.6, 27.0), (-8.4, 22.4)], 2.9, 3.4, 'lCoat')
    r.poly([(-10.6, 24.0), (-6.4, 24.0), (-6.0, 20.6), (-10.8, 20.6)], 'lCoat')
    r.line([(-10.8, 20.8), (-6.0, 20.8)], 'lGold', .4)
    r.ell(-8.2, 19.6, 1.4, 1.5, 'pSkin')
    # 6. 오른팔 — 가슴 앞에서 손바닥 위에 등을 띄운다
    band(r, [(6.0, 34.0), (9.2, 28.0), (6.4, 26.6)], 2.9, 3.0, 'lCoatD')
    r.poly([(8.4, 29.6), (4.6, 27.4), (4.4, 25.0), (9.4, 26.4)], 'lCoat')
    r.line([(4.4, 25.2), (9.4, 26.6)], 'lGold', .4)
    r.ell(4.2, 27.0, 1.6, 1.1, 'pSkin')
    orb = (4.0, 31.2 + .5 * math.sin(ph))
    # 7. 머리(앞)
    r.ell(hc[0], hc[1], 8.0, 8.4, 'pSkin')
    r.ell(hc[0] + 1.8, hc[1] - 1.6, 6.8, 6.8, 'pSkinM', only=('pSkin',))
    r.ell(hc[0] - .8, hc[1] - .4, 7.0, 7.6, 'pSkin', only=('pSkinM',))
    r.poly([(-8.4, 47 + b), (-7.0, 53 + b), (-2.0, 55 + b), (3.4, 55 + b), (8.0, 52 + b), (8.8, 46 + b), (8.2, 40 + b), (6.8, 46.4 + b),
            (3.6, 49.2 + b), (1.0, 47.4 + b), (-2.0, 49.6 + b), (-5.6, 48.0 + b), (-7.4, 41 + b)], 'lHair')
    r.poly([(-6.0, 52.6 + b), (-2.0, 54.4 + b), (2.4, 54.4 + b), (5.6, 52.6 + b), (1.0, 52.2 + b), (-3.6, 51.6 + b)], 'lHairM')
    for k in range(5):
        band(r, bez((-5 + k * 2.4, 54 + b), (-5.4 + k * 2.4, 51 + b), (-4.8 + k * 2.2, 49.5 + b), (-4.4 + k * 2.2, 48 + b), 6), .3, .25, 'lHairL' if k % 2 else 'lHairM')
    for sgn in (-1, 1):                                    # 어깨 앞으로 내린 옆머리
        band(r, bez((sgn * 7.4, 44 + b), (sgn * 8.6, 38), (sgn * 8.0 - .6 * sw, 32), (sgn * 7.2 - 1.0 * sw, 26 + .5 * sw)), 2.0, .9, 'lHair')
        band(r, bez((sgn * 7.2, 43 + b), (sgn * 8.2, 38), (sgn * 7.6 - .6 * sw, 32), (sgn * 6.9 - 1.0 * sw, 27 + .5 * sw)), .4, .25, 'lHairL')
    # 왕관 — 이마 테 + 가운데 등 + 양쪽 빛살
    band(r, bez((-7.4, 50.2 + b), (-3.6, 52.6 + b), (3.6, 52.6 + b), (7.4, 50.2 + b), 16), .75, .75, 'lGold')
    r.poly([(-1.4, 52.4 + b), (0, 55.6 + b), (1.4, 52.4 + b)], 'lGold')
    r.line([(0, 55.4 + b), (0, 58.4 + b + .3 * sw)], 'lGoldD', .5)
    for sgn in (-1, 1):
        band(r, bez((sgn * 3.6, 52.4 + b), (sgn * 4.6, 55.0 + b), (sgn * 6.4, 57.0 + b), (sgn * 7.6 + .2 * sw, 58.4 + b)), .45, .3, 'lGold')
        r.dot(sgn * 7.8 + .2 * sw, 58.8 + b, glow[1], r=.55)
    crown_lamp = (0, 60.2 + b + .3 * sw)
    p_face(r, 'lampeye', glow, (hc[0], hc[1]), look=.15)
    # 8. 림 라이트(손바닥 등에서) + 발광
    rim_light(r.c, (r.X(orb[0]), r.Y(orb[1])), 18 * r.s, 'lGold', only=('lCoat', 'lCoatD', 'lCoatL', 'pSkin', 'pSkinM', 'lHair', 'lPearlD'))
    for (c_, rad) in ((crown_lamp, 1.7), (orb, 2.1)):
        hr_ = rad * 2.3 * r.s
        for a in range(0, 360, 15):
            x = r.X(c_[0]) + hr_ * math.cos(math.radians(a))
            y = r.Y(c_[1]) + hr_ * math.sin(math.radians(a))
            if (a // 15 + f) % 2 == 0:
                r.g.set(x, y, glow[0])
        r.dot(c_[0], c_[1], glow[2], r=rad)
        r.dot(c_[0], c_[1], 'pWhite', r=rad * .45)
    for k in range(7):                                     # 등에서 떠오르는 빛 알갱이
        a = TAU * k / 7 + ph * .5
        rr = 3.2 + 1.4 * ((k + f) % 3)
        r.dot(orb[0] + rr * math.cos(a), orb[1] + 1.2 + rr * .7 * math.sin(a) + ((k + f) % 4) * .6, glow[(k + f) % 3])


def portrait_wavearm(r, f, body):
    ph = TAU * f / 4.0
    phl = TAU * (f - 1) / 4.0
    glow = glow_level('wavearm', f, 4)
    b = .35 * math.sin(ph)
    sw = math.sin(phl)
    nb = -.8 if body == 'b' else 0.0
    hc = (.6, 46.2 + b)
    hand_up = (14.4, 44.0 + .4 * math.sin(ph))
    # 1. 리본(뒤) — 올린 팔에서 나선으로 감기며 머리 뒤로 크게 S 를 그리고 반대쪽 아래로
    # 2차: 머리 옆으로 늘어지면 양갈래 머리로 읽혔다 → 손에서 위로 솟아 머리 위를 감싸는 물살 고리로
    rib1 = bez(hand_up, (21.0, 49.0 + sw), (21.0, 62.0 + .6 * sw), (10.0, 63.5 + .6 * sw), 26) + \
        bez((10.0, 63.5 + .6 * sw), (2.0, 64.5), (-12.0 - sw, 62.0), (-18.0 - 1.2 * sw, 54.0 + sw), 26)[1:]
    rib2 = bez((-6.4, 24.6), (-12.0, 22.0 + sw), (-8.0, 12.0), (-14.0 - 1.2 * sw, 5.0 + .8 * sw), 26)
    for pts, w0, w1 in ((rib1, 2.2, .8), (rib2, 1.8, .7)):
        n_ = len(pts) - 1
        for i in range(n_):                                # 꼬임 — 띠가 좁아졌다 넓어지며 앞뒷면 색이 바뀐다
            tw = abs(math.cos(i * .32 + ph * .5))
            w = (w0 + (w1 - w0) * i / float(n_)) * (.45 + .55 * tw)
            r.line([pts[i], pts[i + 1]], 'wRibM' if tw > .4 else 'wRibD', w)
            if tw > .6:
                r.line([(pts[i][0], pts[i][1] + w * .35), (pts[i + 1][0], pts[i + 1][1] + w * .35)], 'wRib', max(.3, w * .3))
    # 2. 다리 — 한쪽에 무게, 한쪽은 살짝 내딛음
    for (x0, x1, t) in ((-2.8, -3.2, 'wSuitD'), (2.8, 5.0, 'wSuit')):
        r.poly([(x0 - 2.2, 21.5), (x0 + 2.2, 21.5), (x1 + 1.8, 4.5), (x1 - 1.8, 4.5)], t)
        r.poly([(x1 - 2.2, 5.6), (x1 + 2.2, 5.6), (x1 + 3.0, 0), (x1 - 2.4, 0)], 'wSuitD')
        r.ell(x1 + 2.4, 6.0 + .2 * sw, 1.3, .8, 'wSuitL')    # 장화 깃 — 둥근 지느러미 장식(2차: 흰 가시가 발톱처럼 보였다)
        r.ell(x1 - 2.2, 6.0 + .2 * sw, 1.2, .8, 'wSuitL')
        r.line([(x1 - 2.2, 5.6), (x1 + 2.4, 5.6)], 'wTrim', .4)
        r.line([(x0 - 1.4, 16), (x1 - 1.2, 8)], 'wSuitL' if t == 'wSuit' else 'wSuit', .35)
    r.poly([(-5.4, 23.4), (5.6, 23.4), (6.2, 17.4), (-6.0, 17.4)], 'wSuitD')                       # 짧은 바지
    r.line([(-6.0, 17.6), (6.2, 17.6)], 'wTrim', .4)
    # 3. 몸 — 몸에 붙는 수트 + 가슴의 물결 빛 줄 + 열린 짧은 재킷
    r.poly([(-5.6 - nb, 35), (5.6 + nb, 35), (5.0, 28), (4.6 + nb * .4, 24), (5.4, 22), (-5.4, 22), (-4.6 - nb * .4, 24), (-5.0, 28)], 'wSuit')
    r.poly([(1.2, 35), (5.6 + nb, 35), (5.0, 28), (4.6, 24), (5.4, 22), (1.6, 22)], 'wSuitD', only=('wSuit',))
    wave = [(-4.0 + k * .4, 29.0 + .7 * math.sin(k * .9 + ph)) for k in range(21)]
    for (u, v) in wave[::1]:
        r.dot(u, v, glow[1])
    for sgn in (-1, 1):                                    # 재킷 앞판
        pts = [(sgn * 2.4, 35), (sgn * 6.6, 35), (sgn * (6.8 + nb), 29), (sgn * 6.0, 24.0), (sgn * 3.2, 25.2), (sgn * 2.8, 31)]
        r.poly([(sgn * 3.4, 35), (sgn * 7.0, 35), (sgn * (7.2 + nb), 29), (sgn * 6.4, 24.0), (sgn * 4.4, 25.2), (sgn * 3.8, 31)], 'wSuitL' if sgn < 0 else 'wSuitD')
        r.line([(sgn * 3.4, 35), (sgn * 3.8, 31), (sgn * 4.4, 25.2)], 'wTrim', .45)
    r.poly([(-4.0, 34.6), (-3.2, 38.6), (3.2, 38.6), (4.0, 34.6), (2.4, 35.6), (-2.4, 35.6)], 'wTrim')    # 세운 깃
    r.poly([(-1.3, 36.6), (1.3, 36.6), (1.1, 39.4), (-1.1, 39.4)], 'pSkinM')
    # 4. 팔 — 오른팔은 위로 펼치고, 왼손은 허리에
    band(r, [(-6.0, 34.0), (-10.0, 28.4), (-6.6, 24.8)], 2.6, 2.4, 'wSuit')
    r.ell(-6.4, 24.6, 1.4, 1.4, 'pSkin')
    r.line([(-9.4, 27.2), (-7.6, 25.6)], 'wTrim', .9)
    band(r, [(6.0, 34.0), (10.4, 38.4), (hand_up[0] - .6, hand_up[1] - 1.0)], 2.6, 2.3, 'wSuit')
    r.ell(hand_up[0], hand_up[1], 1.5, 1.6, 'pSkin')
    for k in range(3):                                     # 펼친 손가락
        r.line([(hand_up[0] + .4, hand_up[1] + .6), (hand_up[0] + 1.2 + k * .2, hand_up[1] + 1.8 - k * .9)], 'pSkin', .45)
    r.line([(11.0, 39.0), (12.6, 41.2)], 'wTrim', .9)
    # 팔뚝 물결 빛(계보 서명) — 손목에서 어깨로 흐른다
    for k in range(6):
        t = ((k + f * 1.5) % 6) / 6.0
        r.dot(hand_up[0] - 1.0 - 4.0 * t, hand_up[1] - 1.4 - 4.0 * t + .5 * math.sin(k * 1.9), glow[2] if k % 2 else glow[1])
        r.dot(-6.8 - 3.0 * t, 25.0 + 3.0 * t + .4 * math.sin(k * 1.7), glow[1])
    # 리본의 나선 고리 — 손목에 감긴 부분(팔 앞)
    for k in range(2):
        r.ell(hand_up[0] - 1.8 - k * 2.0, hand_up[1] - 2.2 - k * 2.0, 1.6, .7, 'wRibM', cv=r.c)
    # 5. 머리
    r.ell(hc[0], hc[1], 8.0, 8.4, 'pSkin')
    r.ell(hc[0] + 1.8, hc[1] - 1.6, 6.8, 6.8, 'pSkinM', only=('pSkin',))
    r.ell(hc[0] - .8, hc[1] - .4, 7.0, 7.6, 'pSkin', only=('pSkinM',))
    r.poly([(-8.8, 44 + b), (-8.2, 51 + b), (-3.0, 55.4 + b), (3.0, 55.6 + b), (8.4, 52 + b), (9.0, 45 + b), (7.8, 41.6 + b),
            (6.6, 47.6 + b), (3.4, 49.6 + b), (1.4, 48.0 + b), (-1.8, 49.8 + b), (-4.4, 48.0 + b), (-7.0, 48.6 + b), (-7.8, 42 + b)], 'wHair')
    tip = (12.6 + .8 * sw, 61.4 + .5 * sw)                 # 물마루 앞머리 — 위로 크게 말린다(실루엣 서명)
    r.poly([(-1.0, 53.6 + b), (3.0, 57.8 + b), (7.6, 60.6), tip, (11.0 + .6 * sw, 58.2), (9.2, 55.0 + b), (6.4, 52.6 + b), (3.0, 52.2 + b)], 'wHair')
    band(r, bez((0.4, 53.8 + b), (4.0, 57.0 + b), (8.2, 59.4), (tip[0] - .8, tip[1] - .9), 14), .5, .3, 'wHairM')
    G.ring(r.c, r.X(tip[0] - .6), r.Y(tip[1] - 1.2), 1.4 * r.s, max(1.0, .5 * r.s), 'wHairD')   # 물마루 끝이 말린다
    for k in range(3):
        r.dot(tip[0] + 1.6 + k * .9, tip[1] - .4 - k * 1.1, glow[1])                                  # 물보라
    r.poly([(-7.4, 50.8 + b), (-4.4, 54.4 + b), (-1.0, 54.6 + b), (-4.0, 52.0 + b)], 'wHairM')
    for k in range(5):
        band(r, bez((-6.0 + k * 2.6, 54.0 + b), (-6.2 + k * 2.6, 51.4 + b), (-5.6 + k * 2.4, 50.0 + b), (-5.2 + k * 2.4, 48.6 + b), 6), .3, .25, 'wHairD' if k % 2 else 'wHairM')
    p_face(r, 'wavearm', glow, (hc[0], hc[1]), look=-.1)
    # 6. 림 라이트(리본 빛) + 발광 + 물방울 빛 알갱이
    rim_light(r.c, (r.X(hand_up[0]), r.Y(hand_up[1] + 4)), 22 * r.s, 'wSuitL', only=('wSuit', 'wSuitD', 'pSkin', 'pSkinM', 'wHairM'))
    flow = f * 8
    for i, (u, v) in enumerate(rib1):
        if (i - flow) % 9 == 0:
            r.dot(u, v + .3, glow[2], r=.5)
        elif (i - flow) % 9 == 1:
            r.dot(u, v + .3, glow[1])
    for i, (u, v) in enumerate(rib2):
        if (i - flow) % 9 == 4:
            r.dot(u, v + .3, glow[2])
    for k in range(8):
        a = TAU * k / 8 + ph * .5
        r.dot(hand_up[0] + 3.6 * math.cos(a), hand_up[1] + 3.0 + 2.6 * math.sin(a) + ((k + f) % 3) * .5, glow[(k + f) % 3])


def render_portrait(lid, body, f, P):
    r = R(P['cell'][0], P['cell'][1], P['base'], P['s'], 1.0)
    (portrait_lampeye if lid == 'lampeye' else portrait_wavearm)(r, f, body)
    r.c.outline('pLine')
    im = r.c.img()
    im.alpha_composite(r.g.img())
    return im, r


# ── 카드 틀 「계승자」 ───────────────────────────────────────────────────
def card_frame(W, H, f, nfr=4):
    """전설 위의 등급. 진주 → 청록 → 금으로 도는 테, 모서리 장식, 테를 따라 도는 빛 넷(4프레임에 한 칸씩)."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    px = im.load()
    def put(x, y, c):
        if 0 <= x < W and 0 <= y < H:
            px[x, y] = c + (255,)
    dark, mid = (14, 12, 30), (40, 34, 74)
    for y in range(H):
        for x in range(W):
            e = min(x, y, W - 1 - x, H - 1 - y)
            if e < 3:
                put(x, y, dark)
            elif e < 5:
                t = ((x + y) / float(W + H))
                cols = [(236, 232, 248), (126, 222, 220), (238, 200, 110), (236, 232, 248)]
                k = int(t * 3) % 3
                a = cols[k]; b = cols[k + 1]; w = t * 3 - int(t * 3)
                put(x, y, tuple(int(a[i] + (b[i] - a[i]) * w) for i in range(3)))
            elif e < 7:
                put(x, y, mid)
            elif e == 7:
                put(x, y, (120, 100, 170))
    for (cx, cy) in ((10, 10), (W - 11, 10), (10, H - 11), (W - 11, H - 11)):   # 모서리 마름모 + 반달
        for d in range(-6, 7):
            for e in range(-6, 7):
                if abs(d) + abs(e) <= 6:
                    put(cx + d, cy + e, (238, 200, 110) if abs(d) + abs(e) >= 5 else ((18, 16, 40) if abs(d) + abs(e) >= 3 else (255, 244, 200)))
    cx = W // 2                                            # 위 가운데 문장 — 등불 + 물결
    for d in range(-10, 11):
        for e in range(-6, 7):
            if (d * d) / 100.0 + (e * e) / 36.0 <= 1.0:
                put(cx + d, 4 + e, (18, 16, 40))
    for d in range(-3, 4):
        for e in range(-3, 4):
            if d * d + e * e <= 9:
                put(cx + d, 4 + e, (255, 232, 150) if d * d + e * e <= 3 else (238, 200, 110))
    per = []                                               # 테를 도는 빛
    for x in range(4, W - 4): per.append((x, 4))
    for y in range(4, H - 4): per.append((W - 5, y))
    for x in range(W - 5, 3, -1): per.append((x, H - 5))
    for y in range(H - 5, 3, -1): per.append((4, y))
    L = len(per)
    for k in range(4):
        head_i = int((k * L / 4.0) + f * L / 16.0) % L
        for t in range(14):
            x, y = per[(head_i - t) % L]
            a = max(0.0, 1.0 - t / 14.0)
            c = (int(255 * a + 120 * (1 - a)), int(255 * a + 220 * (1 - a)), int(255 * a + 230 * (1 - a)))
            for dx, dy in ((0, 0), (0, 1), (1, 0)) if t < 4 else ((0, 0),):
                put(x + dx, y + dy, c)
    return im


def backdrop(W, H, lid, f):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    px = im.load()
    top, bot = ((10, 12, 34), (26, 30, 74)) if lid == 'lampeye' else ((6, 22, 32), (16, 64, 74))
    glowc = (255, 212, 108) if lid == 'lampeye' else (132, 240, 255)
    k = [0.0, .5, 1.0, .5][f % 4]
    for y in range(H):
        for x in range(W):
            t = y / float(H)
            c = [top[i] + (bot[i] - top[i]) * t for i in range(3)]
            d = math.hypot((x - W / 2.0) / (W * .42), (y - H * .42) / (H * .4))
            g = max(0.0, 1.0 - d) ** 2 * (.30 + .10 * k)
            c = [c[i] + (glowc[i] - c[i]) * g for i in range(3)]
            if ((x // 2 + y // 2) % 2 == 0) and g > .12:   # 점묘 후광(도트답게)
                c = [c[i] + 8 for i in range(3)]
            px[x, y] = tuple(int(min(255, v)) for v in c) + (255,)
    for i in range(16):                                    # 떠오르는 빛 알갱이
        x = (i * 37 + 11) % W
        y = (H - ((i * 53 + f * 6) % H))
        c = glowc if i % 3 else (255, 255, 255)
        px[x % W, y % H] = c + (255,)
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    G.PAL.update(PAL)
    G.NO_TINT.update(GLOW_KEYS)
    G.harmonize()
    for k, v in PAL.items():
        G.PAL[k] = v
    f12, f14, f16, f20 = G.font(12), G.font(14), G.font(16), G.font(22)
    CLIPS = [('idle', 4, 2.6), ('walk_side', 6, 0.9), ('work_34', 3, 1.4)]
    HI = dict(cell=(96, 96), base=90, s=1.5)
    STD = dict(cell=(64, 64), base=60, s=1.0)
    PORT = dict(cell=(160, 224), base=218, s=3.3)
    meta = {'_comment': '심해 계승자 시제품 — 등불눈·물결팔. 손으로 찍은 도트(생성 AI 없음), 정수 배율만',
            'hi': {'cell': 96, 'baseline': 90, 'note': 'P2 64·60 의 1.5배 밀도. 방 배율 ×3 화면에서는 ×2 로 그린다(= 같은 화면 크기)'},
            'std': {'cell': 64, 'baseline': 60, 'note': '카메라를 멀리 뺐을 때(×1·×2) 같은 디자인의 표준 셀'},
            'portrait': {'size': [160, 224], 'frames': 4, 'seconds': 2.6, 'note': '카드 공개·주민 카드. 4프레임 숨 반짝임'},
            'clips': {c: {'row': i, 'frames': n, 'seconds': sec} for i, (c, n, sec) in enumerate(CLIPS)},
            'facing': {'idle': 'front', 'walk_side': 'right(원본) · 왼쪽 = 반전', 'work_34': 'q34_left(원본)'},
            'lineages': {k: {kk: v[kk] for kk in ('ko', 'role', 'sig', 'base', 'accent')} for k, v in LIN.items()},
            'card_tier': {'id': 'heir', 'ko': '계승자', 'above': 'legendary', 'frame': 'frame_heir_f0~3.png (200×280, 4프레임 빛 순환)'}}
    face_check = {}
    sheets = {}
    for lid in LIN:
        for body in ('a', 'b'):
            for tag, P in (('hi', HI), ('std', STD)):
                cw = P['cell'][0]
                sh = Image.new('RGBA', (cw * 6, cw * 3), (0, 0, 0, 0))
                for row, (clip, n, sec) in enumerate(CLIPS):
                    for f in range(n):
                        im, r = render(lid, body, clip, f, P['cell'], P['base'], P['s'])
                        sh.paste(im, (cw * f, cw * row))
                        keys = set(r.c.own(*p) for p in r.c.pixels()) | set(r.g.own(*p) for p in r.g.pixels())
                        face_check['%s/%s/%s/%s/f%d' % (lid, body, tag, clip, f)] = {
                            'eyes': 'pEyeD' in keys, 'brow': LIN[lid]['brow'] in keys, 'mouth': 'pMouth' in keys}
                nm = 'proto_%s_%s_%s.png' % (lid, body, tag)
                sh.save(os.path.join(OUT, nm))
                sheets[(lid, body, tag)] = sh
        # 초상 4프레임(체형: 등불눈 A · 물결팔 B 를 대표로, 둘 다 낸다)
        for body in ('a', 'b'):
            frames = []
            for f in range(4):
                im, r = render_portrait(lid, body, f, PORT)
                im.save(os.path.join(OUT, 'portrait_%s_%s_f%d.png' % (lid, body, f)))
                frames.append(im)
                keys = set(r.c.own(*p) for p in r.c.pixels())
                face_check['%s/%s/portrait/f%d' % (lid, body, f)] = {
                    'eyes': 'pEyeD' in keys, 'brow': LIN[lid]['brow'] in keys, 'mouth': 'pMouth' in keys}
            pal = set()
            for fr in frames:
                pal |= set(c for c in fr.getdata() if c[3] > 0)
            meta['lineages'][lid]['portrait_colors_%s' % body] = len(pal)
    bad_faces = [k for k, v in face_check.items() if not all(v.values())]
    meta['face_check'] = {'cells': len(face_check), 'missing': bad_faces}
    print('[검사] 얼굴(눈·눈썹·입) %d칸 중 빠진 칸 %d' % (len(face_check), len(bad_faces)))

    # 카드 틀 + 공개 목업
    for f in range(4):
        card_frame(200, 280, f).save(os.path.join(OUT, 'frame_heir_f%d.png' % f))
    def card(lid, body, f):
        bg = backdrop(200, 280, lid, f)
        por = Image.open(os.path.join(OUT, 'portrait_%s_%s_f%d.png' % (lid, body, f)))
        bg.alpha_composite(por, (20, 18))
        bg.alpha_composite(card_frame(200, 280, f))
        d = ImageDraw.Draw(bg)
        d.rectangle([12, 236, 187, 266], fill=(14, 12, 30, 230))
        d.text((22, 239), '%s' % LIN[lid]['ko'], font=f16, fill=(255, 238, 190) if lid == 'lampeye' else (200, 250, 255))
        d.text((22, 256), '계승자 · %s' % LIN[lid]['role'], font=f12, fill=(200, 196, 230))
        return bg
    gif_frames = {}
    for lid, body in (('lampeye', 'a'), ('wavearm', 'b')):
        cf = [card(lid, body, f) for f in range(4)]
        cf[0].save(os.path.join(OUT, 'card_reveal_%s.png' % lid))
        G.up(cf[0], 2).save(os.path.join(OUT, 'card_reveal_%s_x2.png' % lid))
        big = [G.up(c_, 2).convert('RGB') for c_ in cf]
        big[0].save(os.path.join(OUT, 'card_reveal_%s.gif' % lid), save_all=True, append_images=big[1:], duration=650, loop=0)
        gif_frames[lid] = cf
    # 움직이는 그림 — walk_side(HI ×3) GIF
    for lid, body in (('lampeye', 'a'), ('wavearm', 'b')):
        fr = []
        for f in range(6):
            im = Image.new('RGBA', (96 * 3, 96 * 3), (14, 16, 30, 255))
            one, _ = render(lid, body, 'walk_side', f, HI['cell'], HI['base'], HI['s'])
            im.alpha_composite(G.up(one, 3))
            fr.append(im.convert('RGB'))
        fr[0].save(os.path.join(OUT, 'walk_side_%s.gif' % lid), save_all=True, append_images=fr[1:], duration=150, loop=0)

    # ── 접촉 시트 ──
    secs = []
    # ① 초상 1× / 2× + 4프레임
    W1 = 20 + 2 * (160 * 2 + 160 + 20) + 40
    im1 = Image.new('RGB', (W1 + 520, 224 * 2 + 70), (12, 10, 24))
    d = ImageDraw.Draw(im1)
    x = 14
    for lid, body in (('lampeye', 'a'), ('wavearm', 'b')):
        p0 = Image.open(os.path.join(OUT, 'portrait_%s_%s_f0.png' % (lid, body)))
        im1.paste(G.up(p0, 2), (x, 40), G.up(p0, 2))
        im1.paste(p0, (x + 330, 40 + 224), p0)
        d.text((x, 10), '%s (%s) — 초상 2× / 1×' % (LIN[lid]['ko'], LIN[lid]['role']), font=f14, fill=(236, 220, 255))
        x += 520
    x0 = x
    for j, lid in enumerate(('lampeye', 'wavearm')):
        for f in range(4):
            p = Image.open(os.path.join(OUT, 'portrait_%s_%s_f%d.png' % (lid, 'a' if lid == 'lampeye' else 'b', f)))
            pc = p.crop((40, 0, 120, 112))
            im1.paste(G.up(pc, 1), (x0 + f * 84, 40 + j * 120), pc)
        d.text((x0, 10), '숨 반짝임 4프레임(머리 부분 1×)', font=f12, fill=(200, 196, 230))
    secs.append(im1)
    # ② 카드 공개 목업 + 계승자 틀 4프레임
    im2 = Image.new('RGB', (20 + 2 * 420 + 4 * 210, 600), (12, 10, 24))
    d = ImageDraw.Draw(im2)
    for j, lid in enumerate(('lampeye', 'wavearm')):
        c2 = G.up(gif_frames[lid][0], 2)
        im2.paste(c2, (14 + j * 420, 30), c2)
    for f in range(4):
        fr_ = card_frame(200, 280, f)
        bgf = Image.new('RGBA', (200, 280), (24, 20, 44, 255)); bgf.alpha_composite(fr_)
        im2.paste(bgf, (14 + 2 * 420 + f * 210, 30))
        d.text((14 + 2 * 420 + f * 210, 316), 'f%d — 테를 도는 빛' % f, font=f12, fill=(200, 196, 230))
    d.text((14, 6), '카드 공개 목업(2×) — 「계승자」 등급(전설 위): 진주→청록→금으로 도는 테, 빛 넷이 4프레임에 한 칸씩 돈다',
           font=f14, fill=(236, 220, 255))
    secs.append(im2)
    # ③ 방 안 — 기본 배율(방 ×3): 기본 주민 둘(×3) + HI(×2) / 멀리 뺀 배율(×1): STD
    pm = json.load(io.open(os.path.join(ROOT, 'static', 'art', 'plates', 'plates_meta.json'), encoding='utf-8'))
    flY = pm['floor_y']
    plate = Image.open(os.path.join(ROOT, 'static', 'art', 'plates', 'room_plate_quarters_lit.png')).convert('RGBA')
    pl = plate.copy()
    cast = [('b', 'scout', 'a', 130), ('nh', 'lampeye', 'a', 250), ('nh', 'wavearm', 'b', 380), ('b', 'cook', 'b', 500)]
    for typ, who, body, xc in cast:
        if typ == 'b':
            one = G.room_light(G.up(G.build(who, 'idle', 0, body, 'short', 'f0')[0].img(), 3))
            top = flY - 60 * 3
            left = xc - 96
        else:
            one = G.up(render(who, body, 'idle', 0, HI['cell'], HI['base'], HI['s'])[0], 2)
            top = flY - 90 * 2
            left = xc - 96
        bb = one.getbbox()
        pl = G.ground_shadow(pl, (left + bb[0], top + bb[1]), one.crop(bb))
        pl.alpha_composite(one, (left, top))
    d = ImageDraw.Draw(pl)
    d.rectangle([0, 0, pl.width, 24], fill=(16, 11, 9, 230))
    d.text((8, 4), '기본 배율(방 ×3): 기본 주민 ×3 · 계승자 HI(96셀) ×2 — 같은 화면 크기, 정수 배율', font=f12, fill=(244, 216, 160))
    small = Image.new('RGBA', (300, 120), (30, 22, 16, 255))
    ds = ImageDraw.Draw(small)
    ds.rectangle([0, 96, 300, 120], fill=(70, 50, 34, 255))
    for j, (typ, who, body) in enumerate((('b', 'scout', 'a'), ('nh', 'lampeye', 'a'), ('nh', 'wavearm', 'b'), ('b', 'cook', 'b'))):
        one = (G.build(who, 'idle', 0, body)[0].img() if typ == 'b'
               else render(who, body, 'idle', 0, STD['cell'], STD['base'], STD['s'])[0])
        small.alpha_composite(one, (10 + j * 70, 96 - 60))
    ds.text((6, 4), '멀리 뺀 배율 ×1 — STD(64셀)', font=f12, fill=(244, 216, 160))
    im3 = Image.new('RGB', (pl.width + small.width + 30, pl.height + 10), (12, 10, 24))
    im3.paste(pl.convert('RGB'), (10, 5))
    im3.paste(small.convert('RGB'), (pl.width + 20, 5))
    secs.append(im3)
    # ④ walk_side 6프레임(HI ×2) — 한 박자 늦게 따라오는 머리·옷자락·리본 · 빛 알갱이 / STD ×3 / idle·work_34
    im4 = Image.new('RGB', (20 + 6 * 200 + 20, 2 * 230 + 2 * 230 + 60), (14, 16, 30))
    d = ImageDraw.Draw(im4)
    y = 30
    for lid, body in (('lampeye', 'a'), ('wavearm', 'b')):
        d.text((14, y - 22), '%s walk_side 6프레임 — HI ×2 (머리·옷자락·리본이 한 박자 늦게, 발밑 빛 알갱이)' % LIN[lid]['ko'],
               font=f14, fill=(236, 220, 255))
        for f in range(6):
            one, _ = render(lid, body, 'walk_side', f, HI['cell'], HI['base'], HI['s'])
            z = G.up(one, 2)
            im4.paste(z, (14 + f * 200, y), z)
        y += 200
        for f in range(6):
            one, _ = render(lid, body, 'walk_side', f, STD['cell'], STD['base'], STD['s'])
            im4.paste(one, (60 + f * 200, y), one)
        d.text((14, y + 4), 'STD', font=f12, fill=(170, 160, 200))
        y += 76
    d.text((14, y - 4), 'idle 4 · work_34 3 (HI ×2)', font=f14, fill=(236, 220, 255))
    y += 16
    x = 14
    for lid, body in (('lampeye', 'a'), ('wavearm', 'b')):
        for clip, n in (('idle', 4), ('work_34', 3)):
            for f in range(n):
                one, _ = render(lid, body, clip, f, HI['cell'], HI['base'], HI['s'])
                z = G.up(one, 2)
                if x + 192 > im4.width:
                    x = 14; y += 196
                im4.paste(z, (x, y), z)
                x += 170
    secs.append(im4.crop((0, 0, im4.width, min(im4.height, y + 200))))
    Wc = max(s_.width for s_ in secs) + 20
    Hc = 60 + sum(s_.height + 14 for s_ in secs)
    sheet = Image.new('RGB', (Wc, Hc), (8, 6, 16))
    d = ImageDraw.Draw(sheet)
    d.text((12, 10), '심해 계승자 시제품 (S17-C2) — 등불눈 · 물결팔. 손으로 찍은 도트, 생성 AI 없음, 정수 배율', font=f20, fill=(240, 228, 255))
    d.text((12, 38), '초상 160×224 · HI 96셀(방 ×3 화면에서 ×2) · STD 64셀(멀리 뺀 배율). 움직이는 그림: proto/*.gif', font=f12, fill=(190, 184, 220))
    y = 60
    for s_ in secs:
        sheet.paste(s_, (10, y))
        y += s_.height + 14
    sheet.save(os.path.join(REP, 'char_S17_proto.png'))
    with io.open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(meta, ensure_ascii=False, indent=1))
    print('[ok] proto →', OUT)


if __name__ == '__main__':
    main()
