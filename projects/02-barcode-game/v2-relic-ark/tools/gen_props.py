# -*- coding: utf-8 -*-
"""
잔해 방주 — E1 선반 소품 스프라이트 34종 (S6-B)
  python tools/gen_props.py

무엇
  data/relic_props.json 의 이름 34개를 그대로 그림으로 옮긴다.
  "내가 어제 편의점에서 찍은 그 라면이 저 선반에 있다" — PLAYER_JOURNEY §2 E1.

규격 (개발과의 계약)
  격자 한 칸 = 34 × 30 px.  slots=2 인 소품은 68 × 30 px.
  파일:  static/art/props/<id>.png      1배 (격자 그대로. 배치용 정본)
         static/art/props/x4/<id>.png   4배 (고해상 화면용. 같은 그림)
  메타:  static/art/props/props_meta.json
  바닥선 = 캔버스 맨 아래. 소품은 선반 위에 '놓여' 있다(공중부양 금지).

화풍 (REF_ART_FLAT_FOLK §1 원리, §7 교정)
  · 평면 2단 음영. 그라데이션 없음. 그림자는 바탕색의 어두운 한 단계뿐(§1-3)
  · 고정 광선 = 왼쪽 위. 그림자는 항상 오른쪽 아래 테두리로만 생긴다
  · 손으로 그은 흔들리는 외곽선(§1-9). 시드 고정이라 다시 돌려도 같은 그림
  · 흙 팔레트만. 청록~남색은 물 전용이라 한 번도 쓰지 않는다(§5)
  · 34px 에서 읽혀야 하므로 묘사가 아니라 **실루엣**으로 구분한다(§1-6)

생성 AI 0장. 전량 절차 생성(07 §6 공개표 갱신 불필요).
"""
import json
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_1X = os.path.join(ROOT, "static", "art", "props")
OUT_4X = os.path.join(OUT_1X, "x4")
OUT_RAW = os.path.join(ROOT, "art_raw", "world")
SRC = os.path.join(ROOT, "data", "relic_props.json")

CELL_W, CELL_H = 34, 30
S = 4                      # 내부 작업 배율
MARGIN = 8                 # ImageChops.offset 이 감기지 않도록 두는 여백(4배 좌표)

# ── 팔레트 — static/art/chars/front/front_meta.json 과 같은 값을 쓴다 ──
P = {
    "cream":   ("#F2E7CE", "#B39A70"),
    "bone":    ("#D9C9A3", "#9E8A62"),
    "ochre":   ("#E4B453", "#8E5F1B"),
    "umber":   ("#96703F", "#49331D"),
    "burnt":   ("#DC7728", "#84360F"),
    "oxblood": ("#B03A24", "#5C170F"),
    "olive":   ("#8D8F4A", "#464821"),
    "char":    ("#39312A", "#15110E"),
}
LINE = "#12100D"
SNAP = [LINE] + [c for pair in P.values() for c in pair]


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


SNAP_RGB = [rgb(h) for h in SNAP]


# ══════════════════════════════════════════════════════════════
# 도형 — 전부 1배 좌표(칸 기준)로 쓰고, 그릴 때 4배로 올린다
# ══════════════════════════════════════════════════════════════
def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def trap(x0, x1, y0, x2, x3, y1):
    """윗변(x0..x1,y0) 아랫변(x2..x3,y1)"""
    return [(x0, y0), (x1, y0), (x3, y1), (x2, y1)]


def ell(cx, cy, rx, ry, n=22, a0=0.0, a1=360.0):
    pts = []
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        pts.append((cx + rx * math.cos(a), cy - ry * math.sin(a)))
    return pts


def cut(x0, y0, x1, y1, c=0.7):
    """모서리를 깎은 사각 — 손으로 그린 상자의 느낌"""
    return [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c),
            (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]


def shift(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


# ══════════════════════════════════════════════════════════════
# 캔버스 — 2단 음영 + 흔들리는 외곽선
# ══════════════════════════════════════════════════════════════
class Sprite:
    def __init__(self, slots, seed):
        self.w = CELL_W * slots
        self.h = CELL_H
        self.W = self.w * S + MARGIN * 2
        self.H = self.h * S + MARGIN * 2
        self.img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        self.rng = random.Random(seed)
        self.strokes = []

    def _xy(self, pts):
        return [(x * S + MARGIN, y * S + MARGIN) for x, y in pts]

    def part(self, pts, key, dark=False, line=True, shade_px=1.0, closed=True):
        """한 덩어리. 바탕색으로 채우고 오른쪽 아래에 그림자 한 단만 붙인다."""
        base, sh = P[key]
        if dark:
            base, sh = sh, P[key][1]
        d = int(round(shade_px * S))
        xy = self._xy(pts)
        mask = Image.new("L", (self.W, self.H), 0)
        ImageDraw.Draw(mask).polygon(xy, fill=255)
        # 그림자 = 제 모양에서 (왼위로 민 제 모양)을 뺀 나머지 → 오른아래 테두리
        shadow = ImageChops.subtract(mask, ImageChops.offset(mask, -d, -d))
        self.img.paste(Image.new("RGBA", (self.W, self.H), rgb(base) + (255,)), (0, 0), mask)
        self.img.paste(Image.new("RGBA", (self.W, self.H), rgb(sh) + (255,)), (0, 0), shadow)
        if line:
            self.strokes.append((xy, closed, 1.0))
        return self

    def flat(self, pts, key, dark=False, line=False):
        """음영 없는 무늬 면(띠·자국·글씨 대신의 표식)."""
        base, sh = P[key]
        col = sh if dark else base
        mask = Image.new("L", (self.W, self.H), 0)
        ImageDraw.Draw(mask).polygon(self._xy(pts), fill=255)
        self.img.paste(Image.new("RGBA", (self.W, self.H), rgb(col) + (255,)), (0, 0), mask)
        if line:
            self.strokes.append((self._xy(pts), True, 0.8))
        return self

    def mark(self, pts, key=None, w=0.85, dark=True, closed=False):
        """선 하나 — 결·이음매·묶은 자리. 팔레트 색이면 그 색, 아니면 숯검정."""
        col = LINE if key is None else (P[key][1] if dark else P[key][0])
        self.strokes.append((self._xy(pts), closed, w, col))
        return self

    def _wobble(self, xy, closed, amp):
        """손으로 그은 흔들림(§1-9). 점 사이를 나눠 미세하게 흔든다."""
        pts = list(xy) + ([xy[0]] if closed else [])
        out = []
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            seg = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(seg / (2.4 * S / 3)))
            for k in range(n):
                t = k / n
                out.append((x0 + (x1 - x0) * t + self.rng.uniform(-amp, amp),
                            y0 + (y1 - y0) * t + self.rng.uniform(-amp, amp)))
        out.append(pts[-1])
        return out

    def finish(self):
        d = ImageDraw.Draw(self.img)
        for st in self.strokes:
            xy, closed, w = st[0], st[1], st[2]
            col = st[3] if len(st) > 3 else LINE
            wob = self._wobble(xy, closed, 0.34 * S / 3)
            d.line(wob, fill=rgb(col) + (255,), width=max(1, int(round(w * S * 0.9))),
                   joint="curve")
        return self.img.crop((MARGIN, MARGIN, self.W - MARGIN, self.H - MARGIN))


def brushed(im, seed):
    """§1-3 정정판: 매끈한 벡터 면 금지. 손으로 칠한 거친 결을 남긴다.
    팔레트 밖 색을 만들지 않으려고, 바탕색 화소 일부를 **그 색의 그림자 단계**로 바꾼다.
    (4배 그림에만 건다. 34px 에서는 결이 잡티로 보인다)"""
    pair = {}
    for base, sh in P.values():
        pair[rgb(base)] = rgb(sh)
    rng = random.Random(seed)
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 200:
                continue
            tgt = pair.get((r, g, b))
            if tgt is None:
                continue
            # 붓이 지나간 결 — 사선으로 성기게. 값이 아니라 무늬로 읽히게 한다
            v = math.sin((x * 0.42 + y * 0.78)) * 0.5 + rng.random() * 0.62
            if v > 0.86:
                px[x, y] = tgt + (a,)
    return im


def snap(im):
    """색을 팔레트로 되돌린다 — 축소하면서 생긴 중간색을 지워 평면을 유지한다."""
    px = im.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            if a < 42:
                px[x, y] = (0, 0, 0, 0)
                continue
            best, bd = SNAP_RGB[0], 1e9
            for c in SNAP_RGB:
                dd = (r - c[0]) ** 2 + (g - c[1]) ** 2 + (b - c[2]) ** 2
                if dd < bd:
                    bd, best = dd, c
            px[x, y] = best + (255 if a >= 132 else a,)
    return im


# ══════════════════════════════════════════════════════════════
# 소품 34종 — 이름이 곧 주문서다(relic_props.json _for_art)
#   좌표계: 한 칸 34×30, y 아래로, 바닥 y=30
# ══════════════════════════════════════════════════════════════
def d_noodle_box(s):                      # 면 상자 (2칸)
    s.part(cut(5, 9, 63, 29, 1.2), "oxblood")
    s.flat(rect(5, 13, 63, 17.5), "cream")
    for k in range(2):                    # 굵은 물결 두 줄 = 면. 잘아지면 레이스로 읽힌다
        y = 21.5 + k * 4.0
        s.mark([(9 + i * 6.0, y + (1.8 if i % 2 else -1.8)) for i in range(10)], "cream", 1.15, False)
    s.mark([(5, 10.6), (63, 10.6)], "oxblood", 0.6)


def d_dry_jar(s):                         # 마른 항아리
    s.part(ell(17, 20, 9.5, 9.0), "umber")
    s.part(rect(13, 7, 21, 12), "umber", dark=True)
    s.part(trap(11.5, 22.5, 5.5, 12.5, 21.5, 8.0), "cream")     # 덮은 천
    s.mark([(11.5, 7.0), (22.5, 7.0)], "umber", 0.7)
    s.mark(ell(17, 21, 6.4, 5.6, 12, 200, 340), None, 0.55)


def d_seed_sack(s):                       # 씨앗 자루
    s.part([(9, 30), (25, 30), (24, 17), (21, 11), (13, 11), (10, 17)], "bone")
    s.part(rect(13.5, 7, 20.5, 12), "bone", dark=True)
    s.mark([(12.6, 11.6), (21.4, 11.6)], "umber", 0.9)
    s.mark([(14, 6.6), (17, 4.6), (20, 6.6)], "bone", 0.7)      # 묶은 목
    for k in range(3):
        s.mark([(12 + k * 4.2, 21 + k % 2), (13.4 + k * 4.2, 26)], "bone", 0.55)


def d_crisp_bundle(s):                    # 바삭 봉지 묶음 (2칸) — 부푼 봉지, 양 끝은 눌러 봉한 자리
    def bag(cx, top, w, h, key, dark=False):
        # 부푼 가운데 + 눌러 봉한 위아래 = 과자 봉지의 실루엣
        s.part([(cx - w * 0.42, top), (cx + w * 0.42, top), (cx + w * 0.44, top + 3.2),
                (cx + w, top + h * 0.5), (cx + w * 0.44, top + h - 3.2), (cx + w * 0.42, top + h),
                (cx - w * 0.42, top + h), (cx - w * 0.44, top + h - 3.2),
                (cx - w, top + h * 0.5), (cx - w * 0.44, top + 3.2)], key, dark=dark)
        for k in range(4):                                       # 눌러 봉한 주름
            dx = -w * 0.3 + k * w * 0.2
            s.mark([(cx + dx, top + 0.4), (cx + dx, top + 2.8)], key, 0.45)
            s.mark([(cx + dx, top + h - 2.8), (cx + dx, top + h - 0.4)], key, 0.45)
        s.flat(rect(cx - w * 0.62, top + h * 0.42, cx + w * 0.62, top + h * 0.58), "cream")
    bag(13, 6, 9.0, 24, "ochre")
    bag(34, 3, 9.5, 27, "burnt")
    bag(55, 8, 8.5, 22, "ochre", dark=True)
    s.mark([(6, 13), (22, 10), (44, 9), (63, 14)], "olive", 0.8, dark=False)   # 묶은 끈


def d_long_neck_bottle(s):                # 목 긴 병
    s.part([(11, 30), (23, 30), (23, 17), (20, 12), (20, 6), (14, 6), (14, 12), (11, 17)], "olive")
    s.part(rect(13.2, 3.5, 20.8, 6.5), "oxblood")
    s.flat(rect(11.5, 20, 22.5, 25), "cream")                     # 표 딱지
    s.mark([(11.5, 20), (22.5, 20)], "olive", 0.55)
    s.mark([(15.5, 22.5), (18.5, 22.5)], "umber", 0.5)


def d_flat_canteen(s):                    # 납작 물통 — 숯색은 어둠에 묻힌다. 몸통을 올리브로
    s.part(cut(8, 10, 26, 29, 2.4), "olive")
    s.part(rect(14.5, 6, 19.5, 11), "char")
    s.flat(ell(17, 20, 5.6, 6.2, 14), "bone")
    s.mark(ell(17, 20, 5.6, 6.2, 14), "bone", 0.55, dark=True, closed=True)
    s.part([(5, 12), (9, 12), (9, 14), (7.4, 14), (7.4, 24), (9, 24), (9, 26), (5, 26)], "umber")


def d_cap_heap(s):                        # 마개 무더기 — 또렷한 3-2-1 더미. 톱니 테두리로 '마개'
    spots = [(9.5, 26.5, "oxblood"), (17, 27, "ochre"), (24.5, 26.5, "olive"),
             (13.5, 20.5, "cream"), (20.5, 20.5, "oxblood"), (17, 14.5, "ochre")]
    for cx, cy, key in spots:
        s.part(ell(cx, cy, 5.0, 3.4, 16), key)
        s.flat(ell(cx, cy - 0.4, 2.8, 1.9, 12), key, dark=True)
        for k in range(5):                                  # 마개 주름 다섯
            dx = -3.4 + k * 1.7
            s.mark([(cx + dx, cy - 2.2), (cx + dx, cy + 2.2)], key, 0.45)


def d_empty_bottle_row(s):                # 빈 병 줄 (2칸)
    for k, (cx, top) in enumerate(((11, 11), (24, 8), (37, 12), (50, 9), (61, 13))):
        s.part([(cx - 5, 30), (cx + 5, 30), (cx + 5, top + 6), (cx + 2, top + 2),
                (cx + 2, top), (cx - 2, top), (cx - 2, top + 2), (cx - 5, top + 6)],
               "bone", dark=(k % 2 == 1))
        s.mark([(cx - 3.4, top + 10), (cx - 3.4, 27)], "bone", 0.5)


def d_twelve_cell_box(s):                 # 열두 칸 상자
    s.part(cut(4, 12, 30, 28, 1.0), "cream")
    for r in range(3):
        for c in range(4):
            s.flat(ell(7.4 + c * 5.2, 15.6 + r * 4.6, 1.9, 1.7, 10), "oxblood")
    s.mark([(4, 12.0), (30, 12.0)], "cream", 0.6)


def d_rolled_strips(s):                   # 감은 띠 뭉치
    s.part(ell(15, 19, 10, 10, 20), "cream")
    s.flat(ell(15, 19, 3.4, 3.4, 14), "umber")
    s.mark(ell(15, 19, 6.8, 6.8, 18), "cream", 0.55, closed=True)
    s.part([(24, 14), (30, 18), (30, 24), (26, 30), (21, 30), (24, 24)], "cream", dark=True)


def d_brown_vial(s):                      # 갈색 작은 병
    s.part([(12, 30), (22, 30), (22, 16), (20, 13), (20, 9), (14, 9), (14, 13), (12, 16)], "umber", dark=True)
    s.part(rect(13.4, 6, 20.6, 9.5), "burnt")
    s.flat(rect(13, 19, 21, 24), "bone")
    s.mark([(15, 21.5), (19, 21.5)], "umber", 0.5)


def d_white_crock(s):                     # 하얀 단지
    s.part(ell(17, 21, 10, 8.6, 20), "cream")
    s.part(rect(12, 11, 22, 15), "cream", dark=True)
    s.part(trap(10, 24, 8, 11.5, 22.5, 11.8), "bone")
    s.mark([(12.4, 24), (21.6, 24)], "cream", 0.5)


def d_cell_tin(s):                        # 번개 알 통
    s.part(rect(10, 9, 24, 30), "oxblood")
    s.part(ell(17, 9, 7, 2.6, 16), "oxblood", dark=True)
    s.flat([(18.4, 13), (14.2, 20), (16.8, 20), (15.2, 26), (20, 18.4), (17.2, 18.4)], "ochre")
    s.mark([(10, 27), (24, 27)], "oxblood", 0.55)


def d_black_panel(s):                     # 검은 판 (2칸) — 검은 화면 + 밝은 테두리라야 어둠에서 읽힌다
    s.part(cut(4, 4, 64, 27, 1.4), "bone")                              # 테두리
    s.flat(cut(8, 7.5, 60, 23.5, 1.0), "char", dark=True)
    s.mark(cut(8, 7.5, 60, 23.5, 1.0), "char", 0.55, dark=False, closed=True)
    s.mark([(50, 7.5), (43, 14), (50, 16), (42, 23.5)], "bone", 0.6, dark=True)   # 금 간 자리
    s.part(rect(20, 27, 48, 30), "bone", dark=True)                     # 받침
    s.flat(rect(11, 10, 25, 11.4), "olive")


def d_tangled_light_thread(s):            # 엉킨 빛 실 — 덩어리가 아니라 겹친 고리로 읽혀야 한다
    for cx, cy, rx, ry in ((13, 22, 7.0, 5.4), (21, 20, 6.4, 5.0), (16.5, 15, 6.8, 4.6)):
        s.mark(ell(cx, cy, rx, ry, 16), "ochre", 1.15, dark=False, closed=True)
        s.mark(ell(cx, cy, rx, ry, 16), "umber", 0.45, dark=True, closed=True)
    s.mark([(23, 12), (27, 9), (26.5, 6)], "ochre", 1.1, dark=False)
    s.part(rect(24.5, 3, 29.5, 7), "char")                              # 꽂는 머리
    s.mark([(25.6, 3), (25.6, 1.2)], "bone", 0.55, dark=True)
    s.mark([(28.4, 3), (28.4, 1.2)], "bone", 0.55, dark=True)


def d_gauge_piece(s):                     # 계기 조각
    s.part(ell(17, 17, 10.5, 10.5, 22), "bone")
    s.flat(ell(17, 17, 7.4, 7.4, 18), "cream")
    s.mark([(17, 17), (22, 12.6)], None, 0.75)
    s.mark(ell(17, 17, 5.2, 5.2, 14), "bone", 0.5, closed=True)
    s.part(rect(12, 26, 22, 30), "char")
    s.part(rect(5, 20, 8.5, 24), "char", dark=True)


def d_stick_bundle(s):                    # 막대 다발
    for k, (cx, top, key) in enumerate(((10.5, 6, "oxblood"), (14, 3.5, "ochre"), (17.5, 5, "olive"),
                                        (21, 3, "burnt"), (24.5, 6.5, "umber"))):
        s.part(rect(cx - 1.5, top, cx + 1.5, 22), key)
        s.flat(rect(cx - 1.5, top, cx + 1.5, top + 2.2), "cream")
    s.part(trap(8, 27, 18, 10, 25, 30), "umber")
    s.mark([(8.6, 23.5), (26.4, 23.5)], "umber", 0.6)


def d_pressed_paper_stack(s):             # 눌린 종이 묶음 (2칸) — 얇고 하얗고 가장자리가 들쭉날쭉
    s.part([(5, 14), (64, 12.5), (63, 29.5), (6, 30)], "cream")
    for k in range(7):                                          # 낱장 결
        y = 15.5 + k * 2.0
        s.mark([(6 + (k % 2) * 1.6, y), (63 - (k % 3) * 2.2, y - 0.5)], "cream", 0.5)
    s.part(rect(29, 10, 37, 30), "oxblood")                     # 묶은 띠
    s.mark([(29, 20), (37, 20)], "oxblood", 0.5)


def d_color_chip_pile(s):                 # 붙는 색 조각 더미 — 작은 정사각이 어긋나게 쌓인다(책과 구분)
    for k, (dx, dy, rot, key) in enumerate(((0, 0, 0, "ochre"), (2.4, -3.4, -4, "olive"),
                                            (-2.0, -6.6, 5, "oxblood"), (1.4, -9.8, -7, "cream"),
                                            (-0.6, -13.0, 3, "ochre"))):
        cx, cy = 17 + dx, 27 + dy
        a = math.radians(rot)
        pts = [(cx + (x * math.cos(a) - y * math.sin(a)), cy + (x * math.sin(a) + y * math.cos(a)))
               for x, y in ((-6.5, -1.8), (6.5, -1.8), (6.5, 1.8), (-6.5, 1.8))]
        s.part(pts, key, dark=(k % 2 == 1))


def d_little_person_doll(s):              # 작은 사람 인형
    s.part(ell(17, 9.5, 5.4, 5.4, 18), "cream")
    s.part(trap(12.5, 21.5, 14, 10, 24, 28), "oxblood")
    s.part(rect(7.5, 15.5, 12.5, 19), "cream")
    s.part(rect(21.5, 15.5, 26.5, 19), "cream")
    s.part(rect(13, 28, 16, 30), "umber")
    s.part(rect(18, 28, 21, 30), "umber")
    s.flat(ell(15.2, 9.4, 0.9, 1.1, 8), "char")
    s.flat(ell(18.8, 9.4, 0.9, 1.1, 8), "char")
    s.mark([(15.6, 12.2), (18.4, 12.2)], "char", 0.5)          # 입 — §7-3 교정 1


def d_standing_books(s):                  # 세운 책 줄 (2칸)
    x = 5
    for k, (w, top, key) in enumerate(((5, 7, "oxblood"), (4, 9, "ochre"), (6, 6, "olive"),
                                       (4, 10, "umber"), (5, 8, "cream"), (4.5, 7, "burnt"),
                                       (6, 11, "olive"), (5, 9, "oxblood"), (4.5, 6, "ochre"),
                                       (5.5, 10, "umber"), (5, 8, "cream"))):
        if x + w > 64:
            break
        s.part(rect(x, top, x + w, 30), key, dark=(k % 3 == 2))
        s.mark([(x + 1.1, top + 2.4), (x + w - 1.1, top + 2.4)], key, 0.5)
        x += w + 0.4


def d_stacked_books(s):                   # 눕힌 책 더미
    for k, (x0, x1, key) in enumerate(((4, 30, "umber"), (6, 29, "oxblood"),
                                       (4.5, 27, "olive"), (7, 28, "cream"))):
        y = 29 - k * 5.4
        s.part(rect(x0, y - 5.0, x1, y), key)
        s.mark([(x0 + 0.8, y - 1.4), (x1 - 0.8, y - 1.4)], key, 0.5)


def d_loose_leaf_box(s):                  # 낱장 상자
    for k, (x0, top, rot) in enumerate(((9, 6, -1.6), (15, 3.5, 0.6), (21, 7, 1.8))):
        s.part([(x0 + rot, top), (x0 + 7 + rot, top + 1.2), (x0 + 7, 20), (x0, 20)], "cream", dark=(k == 1))
    s.part(cut(4, 17, 30, 29, 1.0), "umber")
    s.flat(rect(4, 17, 30, 19.5), "umber", dark=True)


def d_fused_block(s):                     # 붙어 버린 뭉치 — 책이 물에 불어 한 덩어리가 됐다. 결이 보여야 한다
    s.part([(5, 30), (30, 30), (29, 14), (24, 9), (13, 8), (6, 13)], "umber")
    for k in range(6):                                          # 불어 버린 낱장 결
        y = 12.5 + k * 3.0
        s.flat([(6.2, y), (28.6, y - 0.8), (28.6, y + 1.2), (6.2, y + 2.0)], "umber", dark=True)
    s.flat(ell(10.5, 11.5, 2.4, 2.0, 10), "olive")              # 붙어 자란 것
    s.flat(ell(22, 10.5, 1.8, 1.5, 10), "olive")


def d_folded_cloth(s):                    # 갠 천 더미 (2칸) — 책과 달리 모서리가 둥글고 앞면이 늘어진다
    def fold(x0, x1, y, key, dark=False):
        """갠 수건의 앞면 = 둥글게 말린 두 개의 접힌 끝. 이 곡선이 책과 천을 가른다."""
        h = 6.0
        pts = [(x0 + 2.0, y - h)]
        pts += [(x1 - 1.2, y - h + 0.4), (x1 - 0.2, y - h * 0.5), (x1 - 1.4, y - 0.2)]
        for k in range(5):                                       # 앞쪽 말린 결
            t = 1.0 - k / 4.0
            pts.append((x0 + 2.0 + (x1 - x0 - 3.4) * t, y - (0.0 if k % 2 else 1.1)))
        pts += [(x0 + 0.4, y - h * 0.5)]
        s.part(pts, key, dark=dark)
        s.mark([(x0 + 2.6, y - h * 0.55), (x1 - 2.6, y - h * 0.62)], key, 0.5)
    for k, (x0, x1, key) in enumerate(((4, 31, "olive"), (5, 30, "cream"), (4, 32, "oxblood"))):
        fold(x0, x1, 30 - k * 6.4, key, dark=(k == 1))
    for k, (x0, x1, key) in enumerate(((36, 63, "ochre"), (37, 62, "bone"))):
        fold(x0, x1, 30 - k * 6.8, key, dark=(k == 1))


def d_hung_coat(s):                       # 걸린 겉옷
    s.part(rect(11, 2, 23, 4), "char", dark=True)              # 벽에 박은 걸이못
    s.part([(14, 4), (17, 6.5), (20, 4), (20, 5.6), (17, 8.2), (14, 5.6)], "umber")   # 옷걸이
    s.part([(17, 7), (23, 11), (25, 26), (20, 27), (17, 22), (14, 27), (9, 26), (11, 11)], "olive")
    s.part([(9, 11), (11.5, 11.5), (10, 22), (7, 21)], "olive", dark=True)
    s.part([(25, 11), (22.5, 11.5), (24, 22), (27, 21)], "olive", dark=True)
    s.mark([(17, 9), (17, 24)], "olive", 0.55)


def d_single_boot(s):                     # 신발 한 짝
    s.part([(10, 8), (19, 8), (20, 22), (29, 24), (29, 29), (8, 29), (8, 22)], "umber")
    s.flat(rect(8, 27, 29, 29.6), "char")
    s.mark([(10.5, 12), (18.5, 12)], "umber", 0.55)
    s.mark([(10.5, 16), (18.5, 16)], "umber", 0.55)
    s.part(trap(9.5, 19.5, 6, 10, 19, 8.6), "bone")


def d_name_patch_box(s):                  # 이름표 천 상자
    s.part(cut(5, 14, 29, 29, 1.0), "bone")
    for k, (x0, top, key) in enumerate(((7.5, 9, "oxblood"), (14, 6.5, "ochre"), (20.5, 10, "olive"))):
        s.part(rect(x0, top, x0 + 6, 16), key)
        s.mark([(x0 + 1, top + 2.6), (x0 + 5, top + 2.6)], key, 0.5)
    s.flat(rect(5, 20, 29, 22.5), "bone", dark=True)


def d_foil_bundle(s):                     # 은박 묶음 — 구겨진 은박은 모난다. 둥글면 공으로 읽힌다
    s.part([(6, 24), (9, 15), (15, 11), (23, 12), (28, 18), (29, 25), (24, 30), (11, 30)], "bone")
    for pts in (((9.5, 16.5), (15, 13), (14, 20), (9, 22)),
                ((16.5, 13.5), (23, 14), (25, 21), (17, 20.5)),
                ((11, 24), (18, 23), (19, 29), (12.5, 29.5))):
        s.flat(list(pts), "cream")
        s.mark(list(pts), "bone", 0.5, closed=True)
    s.part(rect(14, 4, 20, 12), "oxblood")                       # 묶은 자리
    s.mark([(14, 7.5), (20, 7.5)], "oxblood", 0.5)


def d_thin_paper_box(s):                  # 얇은 종이 상자
    s.part(rect(11, 5, 24, 30), "ochre")
    s.flat(rect(11, 13, 24, 17), "oxblood")
    s.mark([(11, 8.6), (24, 8.6)], "ochre", 0.55)
    s.part([(24, 5), (28, 7), (28, 29), (24, 30)], "ochre", dark=True)


def d_sealed_flask(s):                    # 봉인된 병
    s.part([(11, 30), (24, 30), (24, 18), (21, 13), (21, 8), (14, 8), (14, 13), (11, 18)], "oxblood")
    s.part([(13, 8), (22, 8), (23, 4), (20, 2.5), (15, 2.5), (12, 4)], "burnt")   # 밀랍
    s.mark([(12.6, 6), (22.4, 6)], "burnt", 0.6)
    s.flat(ell(17.5, 22, 4.2, 4.2, 14), "cream")
    s.mark(ell(17.5, 22, 2.2, 2.2, 10), "oxblood", 0.5, closed=True)


def d_dry_leaf_box(s):                    # 마른 잎 상자 (2칸)
    for k, (cx, cy, rot) in enumerate(((16, 11, -22), (30, 8, 6), (44, 12, 20), (54, 10, -8))):
        a = math.radians(rot)
        pts = [(cx - 5, cy + 7), (cx - 2, cy - 6), (cx + 3, cy - 7), (cx + 5, cy + 6)]
        pts = [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a),
                cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in pts]
        s.part(pts, "olive", dark=(k % 2 == 1))
    s.part(cut(4, 16, 64, 29, 1.2), "umber")
    s.flat(rect(4, 16, 64, 19), "umber", dark=True)
    s.mark([(4, 24), (64, 24)], "umber", 0.55)


def d_nameless_box(s):                    # 이름 없는 상자
    s.part(cut(4, 10, 30, 29, 1.2), "umber")
    s.flat(rect(15.4, 10, 18.6, 29), "bone")
    s.flat(rect(4, 18.4, 30, 21.6), "bone")
    s.mark([(4, 13.4), (30, 13.4)], "umber", 0.55)


def d_unread_lump(s):                     # 정체 모를 덩어리 — 따개비가 덮어 성문을 못 읽는다
    s.part([(6, 30), (29, 30), (30, 19), (25, 11), (17, 8), (9, 12), (5, 20)], "umber", dark=True)
    for cx, cy, r in ((12, 17, 2.8), (20.5, 13.5, 2.2), (24, 22, 2.6), (13.5, 25, 2.0), (21, 25.5, 1.7)):
        s.part(ell(cx, cy, r, r * 0.84, 12), "bone")
        s.flat(ell(cx, cy, r * 0.42, r * 0.36, 8), "char")


DRAW = {
    "prop_noodle_box": d_noodle_box, "prop_dry_jar": d_dry_jar, "prop_seed_sack": d_seed_sack,
    "prop_crisp_bundle": d_crisp_bundle, "prop_long_neck_bottle": d_long_neck_bottle,
    "prop_flat_canteen": d_flat_canteen, "prop_cap_heap": d_cap_heap,
    "prop_empty_bottle_row": d_empty_bottle_row, "prop_twelve_cell_box": d_twelve_cell_box,
    "prop_rolled_strips": d_rolled_strips, "prop_brown_vial": d_brown_vial,
    "prop_white_crock": d_white_crock, "prop_cell_tin": d_cell_tin, "prop_black_panel": d_black_panel,
    "prop_tangled_light_thread": d_tangled_light_thread, "prop_gauge_piece": d_gauge_piece,
    "prop_stick_bundle": d_stick_bundle, "prop_pressed_paper_stack": d_pressed_paper_stack,
    "prop_color_chip_pile": d_color_chip_pile, "prop_little_person_doll": d_little_person_doll,
    "prop_standing_books": d_standing_books, "prop_stacked_books": d_stacked_books,
    "prop_loose_leaf_box": d_loose_leaf_box, "prop_fused_block": d_fused_block,
    "prop_folded_cloth": d_folded_cloth, "prop_hung_coat": d_hung_coat,
    "prop_single_boot": d_single_boot, "prop_name_patch_box": d_name_patch_box,
    "prop_foil_bundle": d_foil_bundle, "prop_thin_paper_box": d_thin_paper_box,
    "prop_sealed_flask": d_sealed_flask, "prop_dry_leaf_box": d_dry_leaf_box,
    "prop_nameless_box": d_nameless_box, "prop_unread_lump": d_unread_lump,
}


# ══════════════════════════════════════════════════════════════
def main():
    os.makedirs(OUT_4X, exist_ok=True)
    os.makedirs(OUT_RAW, exist_ok=True)
    src = json.load(open(SRC, encoding="utf-8"))
    meta = {
        "_comment": "E1 선반 소품 스프라이트. 격자 한 칸 34×30px, slots=2 는 68×30px. "
                    "바닥선 = 이미지 맨 아래(소품은 선반 위에 놓인다). "
                    "1배가 배치 정본, x4/ 는 같은 그림의 4배(고해상 화면용).",
        "_source": "data/relic_props.json (이름·카테고리 = 시나리오 소유)",
        "_style": "docs/refs/REF_ART_FLAT_FOLK.md §1·§5 — 평면 2단 음영, 흙 팔레트, 손그림 외곽선",
        "cell": {"w": CELL_W, "h": CELL_H},
        "scale4x_dir": "x4",
        "line_color": LINE,
        "palette": {k: list(v) for k, v in P.items()},
        "props": {},
    }
    made = []
    for cat, items in src["props"].items():
        for it in items:
            pid, slots = it["id"], int(it.get("slots", 1))
            fn = DRAW.get(pid)
            if fn is None:
                raise SystemExit("그림이 없는 소품: " + pid)
            sp = Sprite(slots, seed=abs(hash(pid)) % 99991)
            fn(sp)
            big = snap(sp.finish())
            small = snap(big.resize((CELL_W * slots, CELL_H), Image.LANCZOS))
            big = brushed(big, seed=abs(hash(pid)) % 7919)
            big.save(os.path.join(OUT_4X, pid + ".png"))
            small.save(os.path.join(OUT_1X, pid + ".png"))
            meta["props"][pid] = {
                "name": it["name"], "category": cat, "slots": slots,
                "w": CELL_W * slots, "h": CELL_H,
                "file": "static/art/props/%s.png" % pid,
                "file4x": "static/art/props/x4/%s.png" % pid,
            }
            made.append((pid, it["name"], slots, small, big))
    json.dump(meta, open(os.path.join(OUT_1X, "props_meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    contact(made)
    print("PROPS", len(made))


def contact(made):
    """검수용 접촉 인화 — 왼쪽은 실제 1배 크기(판독 시험), 오른쪽은 6배."""
    cols, pad, z = 5, 14, 6
    cw = CELL_W * 2 * z + CELL_W * 2 + pad * 3
    ch = CELL_H * z + pad + 12
    rows = (len(made) + cols - 1) // cols
    sheet = Image.new("RGBA", (cw * cols, ch * rows + 26), (26, 22, 18, 255))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), "RELIC ARK  E1 shelf props  x34   left=1x (34x30 grid)  right=6x", fill=(200, 180, 140))
    for i, (pid, name, slots, small, big) in enumerate(made):
        ox = (i % cols) * cw + pad
        oy = (i // cols) * ch + 26
        sheet.alpha_composite(small, (ox, oy + CELL_H * z - CELL_H))
        up = small.resize((small.size[0] * z, small.size[1] * z), Image.NEAREST)
        sheet.alpha_composite(up, (ox + CELL_W * 2 + pad, oy))
        d.text((ox, oy + CELL_H * z + 2), pid.replace("prop_", "") + ("  [2]" if slots == 2 else ""),
               fill=(168, 150, 116))
    sheet.convert("RGB").save(os.path.join(OUT_RAW, "props_sheet.png"))
    print("SHEET", os.path.join(OUT_RAW, "props_sheet.png"))


if __name__ == "__main__":
    main()
