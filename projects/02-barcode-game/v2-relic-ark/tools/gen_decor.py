"""S19-E — 방 장식 꼬리표 덧씌움(데코 오버레이) 8종 + 장식 자리 소품 3종.

python tools/gen_decor.py   → static/art/decor/*.png + decor_meta.json + docs/reports/s19e_decor_sheet.png

- 칸 = M5 layout.json 의 칸(564×317) = 방 플레이트 outer_rect 크롭. 덧씌움은 칸 좌상단 (0,0)에 1:1로 놓는다.
- 사람 자리 비움: 바닥 띠(y ≥ 262)와 두 서는 자리 기둥(x 34~150, 414~530 의 y ≥ 95), 방 등불(282,77) 둘레 반경 34.
- 그림은 2배로 그려 반으로 줄인다(손그림 외곽선 #1C1712, 2단 평면 음영, 따뜻한 등불 빛). 생성 AI 없음.
"""
import os, math, json, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DST = os.path.join(ROOT, "static", "art", "decor"); os.makedirs(DST, exist_ok=True)
PLATES = os.path.join(ROOT, "static", "art", "plates")
CW, CH, S = 564, 317, 2
INK = (28, 23, 18, 255)
FLOOR_Y, SPOT_L, SPOT_R, HEAD_Y, LAMP = 262, (34, 150), (414, 530), 95, (282, 77, 34)
OW = 4   # 외곽선(2배 좌표)


def C(h, a=255):
    h = h.lstrip("#"); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def new():
    return Image.new("RGBA", (CW * S, CH * S), (0, 0, 0, 0))


def sc(v):
    return [x * S for x in v]


class Pen:
    def __init__(self, im):
        self.im = im; self.d = ImageDraw.Draw(im)

    def rect(self, b, fill, r=0, ow=OW, outline=INK):
        b = sc(b)
        if r:
            self.d.rounded_rectangle(b, r * S, fill=fill, outline=outline, width=ow)
        else:
            self.d.rectangle(b, fill=fill, outline=outline, width=ow)

    def poly(self, pts, fill, ow=OW, outline=INK):
        p = [(x * S, y * S) for x, y in pts]
        self.d.polygon(p, fill=fill)
        if ow:
            self.d.line(p + [p[0]], fill=outline, width=ow, joint="curve")

    def ell(self, b, fill, ow=OW, outline=INK):
        self.d.ellipse(sc(b), fill=fill, outline=outline if ow else None, width=ow)

    def line(self, pts, fill, w=2):
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(w * S), joint="curve")


def glow(im, cx, cy, r, col=(255, 190, 100), a=110):
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse(sc((cx - r, cy - r, cx + r, cy + r)), fill=(*col, a))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(r * S * 0.45)))


def shelf(p, x0, x1, y, col="#7A5434"):
    p.rect((x0, y, x1, y + 8), C(col))
    for x in (x0 + 12, x1 - 18):                     # 받침쇠
        p.poly([(x, y + 8), (x + 6, y + 8), (x + 6, y + 26), (x, y + 14)], C("#5A4632"), ow=3)


def bottle(p, x, ybot, h, col, w=14, label=None):
    p.rect((x, ybot - h, x + w, ybot), C(col), r=3)
    p.rect((x + w * 0.3, ybot - h - 8, x + w * 0.7, ybot - h + 1), C(col))
    if label:
        p.rect((x + 2, ybot - h * 0.6, x + w - 2, ybot - h * 0.3), C(label), ow=2)


def steam(im, x, y0, y1, seed):
    r = random.Random(seed); L = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    for k in range(3):
        ox = x + (k - 1) * 9
        pts = [(ox + 7 * math.sin(t * 6 + k + r.random()), y0 - (y0 - y1) * t) for t in [i / 14 for i in range(15)]]
        d.line([(a * S, b * S) for a, b in pts], fill=(244, 240, 230, 200 - k * 30), width=3 * S, joint="curve")
    im.alpha_composite(L.filter(ImageFilter.GaussianBlur(2.2 * S)))


def finish(im):
    return im.resize((CW, CH), Image.LANCZOS)


# ══════ 꼬리표 여덟 ══════
def warm_kitchen():
    im = new(); p = Pen(im)
    shelf(p, 160, 300, 104)
    hs = [34, 46, 52, 40, 28, 22]                    # 키 순서(큰 것 → 작은 것)
    cols = ["#8A4A2A", "#C08A33", "#6A7A3A", "#B06A3A", "#D8C9A3", "#8C6222"]
    x = 166
    for h, c in zip(sorted(hs, reverse=True), cols):
        if c == "#D8C9A3":                          # 봉지
            p.poly([(x, 104), (x + 18, 104), (x + 16, 104 - h), (x + 2, 104 - h)], C(c)); x += 22
        else:
            bottle(p, x, 104, h - 8, c, w=15, label="#E8DCBF"); x += 21
    # 매단 냄비 + 김
    p.line([(352, 36), (352, 132)], C("#3A3028"), 1.6)
    glow(im, 352, 168, 44, a=130)
    p.ell((318, 140, 386, 160), C("#4A3E34"))
    p.poly([(320, 150), (384, 150), (378, 192), (326, 192)], C("#6A4A32"))
    p.rect((316, 144, 388, 154), C("#8A6A44"), r=3)
    p.line([(316, 150), (304, 140)], INK, 1.5); p.line([(388, 150), (400, 140)], INK, 1.5)
    steam(im, 352, 142, 70, 1)
    # 마른 고추·마늘 줄(왼쪽 벽 위, 머리 위)
    for i in range(5):
        p.ell((60 + i * 14, 50 + (i % 2) * 6, 72 + i * 14, 66 + (i % 2) * 6), C("#A84A2A" if i % 2 else "#E8DCBF"), ow=3)
    p.line([(56, 50), (134, 52)], C("#5A4632"), 1.2)
    return finish(im)


def book_smell():
    im = new(); p = Pen(im)
    shelf(p, 160, 400, 128); shelf(p, 170, 390, 192)
    r = random.Random(3); cols = ["#6A3A2A", "#3A5A4A", "#8A6A3A", "#4A4A6A", "#7A2E26", "#C9B896", "#5A4632"]
    for row, y, x0, x1 in ((0, 128, 166, 330), (1, 192, 176, 384)):
        x = x0
        while x < x1:
            w = r.randint(9, 15); h = r.randint(30, 46); lean = r.choice([0, 0, 0, 6, -5])
            c = r.choice(cols)
            p.poly([(x, y), (x + w, y), (x + w + lean, y - h), (x + lean, y - h)], C(c), ow=3)
            p.line([(x + 2 + lean * 0.5, y - h * 0.55), (x + w - 2 + lean * 0.5, y - h * 0.55)], C("#E8DCBF", 200), 0.8)
            x += w + (4 if lean else 1)
    # 책상 등(구부러진 목 + 따뜻한 갓) — 위 선반 오른쪽
    glow(im, 364, 112, 30, a=140)
    p.line([(362, 128), (360, 104), (372, 92)], C("#3A3028"), 2)
    p.poly([(362, 86), (388, 92), (384, 104), (364, 100)], C("#C08A33"))
    p.ell((370, 98, 382, 106), C("#FFE0A0"), ow=0)
    # 펼친 채 엎어 둔 책 — 작은 걸상 위(바닥 띠는 비운다)
    p.rect((262, 236, 322, 244), C("#7A5434")); p.rect((268, 244, 274, 258), C("#5A3E26"), ow=3); p.rect((310, 244, 316, 258), C("#5A3E26"), ow=3)
    p.poly([(266, 236), (292, 222), (318, 236)], C("#7A2E26"))
    p.line([(292, 222), (292, 236)], INK, 1)
    # 벽에 기댄 큰 책 둘(머리 위 벽, 왼쪽)
    p.poly([(60, 92), (78, 92), (92, 46), (74, 44)], C("#3A5A4A")); p.poly([(80, 92), (96, 92), (100, 50), (84, 50)], C("#8A6A3A"))
    return finish(im)


def shiny_things():
    im = new(); p = Pen(im)
    # 줄 전구(머리 위, 등불 둘레는 비움)
    for seg in ((40, 250), (316, 526)):
        xs = np.linspace(seg[0], seg[1], 9)
        pts = [(x, 38 + 10 * math.sin((x - seg[0]) / (seg[1] - seg[0]) * math.pi)) for x in xs]
        p.line(pts, C("#3A3028"), 1.2)
        for i, (x, y) in enumerate(pts[1:-1]):
            glow(im, x, y + 8, 10, a=160)
            p.ell((x - 5, y + 3, x + 5, y + 14), C("#FFD27A" if i % 2 else "#FFE9B8"), ow=2)
    # 선반 위 유리병·판 — 빛을 받는다
    shelf(p, 168, 396, 150)
    for i, (h, c) in enumerate([(40, "#5A8A8A"), (30, "#8AB0A0"), (46, "#A06A3A"), (26, "#C8D8D0"), (36, "#6A9A9A"), (42, "#B08A4A")]):
        x = 178 + i * 34
        bottle(p, x, 150, h - 8, c, w=16)
        p.line([(x + 4, 150 - h + 10), (x + 4, 146)], C("#FFFFFF", 170), 1.2)
    p.rect((376, 108, 392, 150), C("#9AB8B0"), ow=3)        # 판(거울 조각)
    # 벽의 빛 조각(따뜻한·하얀 작은 마름모) — 머리 위와 가운데 벽
    r = random.Random(7)
    L = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    n = 0
    while n < 26:
        x, y = r.uniform(40, 524), r.uniform(60, 240)
        if (y > HEAD_Y - 9 and not (166 < x < 398)) or math.hypot(x - LAMP[0], y - LAMP[1]) < LAMP[2] + 6 or 100 < y < 156 and 168 < x < 396:
            continue
        s = r.uniform(3, 6); col = (255, 236, 190, 200) if n % 3 else (210, 240, 236, 190)
        d.polygon([((x) * S, (y - s) * S), ((x + s * 0.6) * S, y * S), (x * S, (y + s) * S), ((x - s * 0.6) * S, y * S)], fill=col); n += 1
    im.alpha_composite(L.filter(ImageFilter.GaussianBlur(0.8))); im.alpha_composite(L)
    return finish(im)


def soft_corner():
    im = new(); p = Pen(im)
    # 가로대에 걸친 담요(끝이 아래로 늘어진다) — 가운데
    p.rect((176, 100, 392, 108), C("#5A3E26"))
    p.poly([(186, 104), (300, 104), (306, 230), (292, 250), (270, 236), (250, 252), (226, 236), (196, 246)], C("#A8584A"))
    for k in range(4):
        p.line([(196 + k * 26, 112), (204 + k * 24, 236)], C("#C9785A"), 1.5)
    p.poly([(300, 104), (382, 104), (378, 170), (360, 182), (340, 168), (306, 176)], C("#D8C9A3"))
    p.line([(312, 128), (372, 128)], C("#A08A60"), 1.2); p.line([(312, 150), (370, 150)], C("#A08A60"), 1.2)
    # 쌓인 천 + 방석 둘 + 인형(낮은 상자 위, 바닥 띠 위)
    p.rect((312, 214, 396, 260), C("#6A4A2A"))
    for i, c in enumerate(["#7A8A5A", "#C08A33", "#8A5A6A"]):
        p.rect((316 + i * 2, 200 - i * 12, 392 - i * 3, 214 - i * 12), C(c), r=4, ow=3)
    p.ell((176, 228, 236, 258), C("#C9785A")); p.ell((226, 234, 284, 260), C("#7A8A5A"))
    # 인형(작은 곰 비슷한 천 인형 — 상표 없음)
    p.ell((342, 152, 366, 176), C("#B08A5A")); p.ell((338, 148, 348, 158), C("#B08A5A"), ow=3); p.ell((360, 148, 370, 158), C("#B08A5A"), ow=3)
    p.ell((340, 170, 368, 192), C("#B08A5A"))
    p.ell((349, 160, 352, 163), INK, ow=0); p.ell((356, 160, 359, 163), INK, ow=0)
    glow(im, 300, 200, 70, a=60)
    return finish(im)


def workbench():
    im = new(); p = Pen(im)
    # 공구판(벽) + 공구 그림자 줄
    p.rect((170, 40, 244, 150), C("#8A6A44")); p.rect((320, 40, 400, 150), C("#8A6A44"))
    r = random.Random(9)
    for bx in (170, 320):
        for i in range(5):
            for j in range(8):
                p.ell((bx + 8 + i * 15, 48 + j * 13, bx + 10 + i * 15, 50 + j * 13), C("#5A4632"), ow=0)
    tools = [  # (x, y, 모양)
        (182, 60, "hammer"), (208, 58, "wrench"), (230, 64, "screw"), (334, 58, "saw"), (370, 60, "pliers"), (392, 64, "screw")]
    for x, y, t in tools:
        sh = C("#2A2018", 230); tc = C("#6A6A64")
        if t == "hammer":
            p.rect((x + 4, y, x + 8, y + 64), C("#7A5434"), ow=3); p.rect((x - 4, y - 4, x + 16, y + 8), tc, ow=3)
        elif t == "wrench":
            p.rect((x + 3, y + 8, x + 9, y + 66), tc, ow=3); p.ell((x - 2, y - 4, x + 14, y + 12), tc, ow=3); p.ell((x + 3, y, x + 9, y + 6), C("#8A6A44"), ow=0)
        elif t == "screw":
            p.rect((x + 2, y, x + 7, y + 30), C("#A84A2A"), ow=3); p.line([(x + 4.5, y + 30), (x + 4.5, y + 56)], tc, 1.6)
        elif t == "saw":
            p.poly([(x, y), (x + 26, y + 6), (x + 26, y + 72), (x, y + 60)], tc); p.rect((x - 6, y - 6, x + 8, y + 14), C("#7A5434"), ow=3)
        else:
            p.line([(x, y), (x + 6, y + 60)], tc, 2); p.line([(x + 12, y), (x + 6, y + 60)], tc, 2)
    # 늘어진 줄 묶음(전선 둘둘)
    for k in range(3):
        p.d.arc(sc((262 + k * 4, 50 + k * 3, 302 - k * 2, 100 - k * 2)), 0, 360, fill=C("#2A2A2A" if k % 2 else "#A84A2A"), width=3 * S)
    p.line([(282, 40), (282, 52)], C("#3A3028"), 1.2)
    # 작업 판(가운데) 위 반쯤 뜯은 기계 + 대팻밥
    p.rect((176, 206, 392, 216), C("#7A5434")); p.rect((186, 216, 194, 260), C("#5A3E26"), ow=3); p.rect((374, 216, 382, 260), C("#5A3E26"), ow=3)
    p.rect((220, 176, 286, 206), C("#4A5050")); p.rect((228, 182, 262, 198), C("#1E2A2A"), ow=2)
    p.poly([(286, 180), (310, 172), (312, 196), (286, 206)], C("#6A6A64"))
    for i in range(6):
        p.ell((240 + i * 6, 188, 244 + i * 6, 192), C("#C08A33"), ow=0)
    for i in range(7):                                 # 대팻밥 말림
        x = 320 + r.uniform(0, 50); y = 196 + r.uniform(0, 8)
        p.d.arc(sc((x, y, x + 10, y + 8)), 180, 520, fill=C("#E0B880"), width=2 * S)
    glow(im, 260, 190, 50, a=50)
    return finish(im)


def growing():
    im = new(); p = Pen(im)
    # 둥근 창(바깥 물빛) + 물방울 줄
    p.rect((190, 56, 376, 168), C("#5A4632"), r=10)
    p.rect((200, 66, 366, 158), C("#1E5A64"), r=6)
    p.line([(283, 66), (283, 158)], C("#5A4632"), 2.4); p.line([(200, 112), (366, 112)], C("#5A4632"), 2.4)
    r = random.Random(5)
    for i in range(9):
        x = r.uniform(206, 360); y0 = r.uniform(70, 120)
        p.line([(x, y0), (x + r.uniform(-1, 1), y0 + r.uniform(16, 36))], C("#9AD8D0", 200), 0.9)
        p.ell((x - 2, y0 + 30, x + 2, y0 + 35), C("#C8ECE6"), ow=0)
    # 창턱 + 줄지은 그릇과 새싹
    p.rect((180, 168, 386, 178), C("#7A5434"))
    for i in range(6):
        x = 190 + i * 32
        p.poly([(x, 152), (x + 24, 152), (x + 20, 168), (x + 4, 168)], C("#A06A3A" if i % 2 else "#D8C9A3"), ow=3)
        for k in range(3):
            p.line([(x + 8 + k * 4, 152), (x + 6 + k * 5, 136 - (k % 2) * 6)], C("#6A8A2A"), 1.4)
            p.ell((x + 2 + k * 5, 130 - (k % 2) * 6, x + 10 + k * 5, 138 - (k % 2) * 6), C("#7AA034"), ow=2)
    # 젖은 천(창턱에 걸침)
    p.poly([(330, 170), (370, 170), (366, 220), (356, 212), (346, 224), (334, 214)], C("#B8C8C0"))
    for k in range(3):
        p.ell((338 + k * 10, 228 + k * 6, 341 + k * 10, 232 + k * 6), C("#9AD8D0"), ow=0)
    # 매단 화분(머리 위 왼쪽)
    p.line([(96, 36), (96, 60)], C("#3A3028"), 1.2)
    p.poly([(82, 60), (110, 60), (104, 78), (88, 78)], C("#A06A3A"))
    for k in range(4):
        p.line([(90 + k * 4, 76), (84 + k * 6, 89 - k)], C("#6A8A2A"), 1.4)
    return finish(im)


def clean_shelf():
    im = new(); p = Pen(im)
    p.rect((184, 50, 384, 236), C("#E0D6C0"), r=4)          # 하얀 약장
    for i in range(1, 3):
        p.line([(184, 50 + i * 62), (384, 50 + i * 62)], C("#8A7A60"), 1.6)
    for j in range(1, 3):
        p.line([(184 + j * 66.7, 50), (184 + j * 66.7, 236)], C("#8A7A60"), 1.6)
    items = ["box", "bottle", "jar", "bottle", "box", "jar", "jar", "box", "bottle"]
    for k, it in enumerate(items):
        cx = 184 + 33 + (k % 3) * 66.7; yb = 50 + 62 * (k // 3 + 1) - 4
        if it == "box":
            p.rect((cx - 18, yb - 30, cx + 18, yb), C("#F4EEE0"), ow=3)
            p.rect((cx - 12, yb - 22, cx + 12, yb - 12), C("#C9B896"), ow=2)
            p.line([(cx - 8, yb - 17), (cx + 6, yb - 17)], INK, 0.8)
        elif it == "bottle":
            bottle(p, cx - 8, yb, 30, "#8A5A3A", w=16, label="#F4EEE0")
        else:
            p.rect((cx - 14, yb - 26, cx + 14, yb), C("#C8D8D0"), r=4, ow=3)
            p.rect((cx - 15, yb - 32, cx + 15, yb - 24), C("#7A6A54"), ow=2)
            p.rect((cx - 10, yb - 18, cx + 10, yb - 8), C("#F4EEE0"), ow=2)
    # 십자가 아닌 "엇갈린 띠" 표지(상자 무늬와 같은 그림) — 약장 위
    for ang in (0.6, -0.6):
        c, s_ = math.cos(ang), math.sin(ang)
        pts = [(283 + x * c - y * s_, 40 + x * s_ + y * c) for x, y in [(-4, -12), (4, -12), (4, 12), (-4, 12)]]
        p.poly(pts, C("#A84A2A"), ow=2)
    return finish(im)


def trade_corner():
    im = new(); p = Pen(im)
    # 벽에 건 흥정 천(물건을 꽂아 둠)
    p.line([(186, 104), (382, 104)], C("#5A3E26"), 2)
    p.poly([(190, 104), (378, 104), (372, 186), (340, 178), (300, 188), (260, 178), (220, 188), (196, 180)], C("#8A5A2A"))
    for k in range(5):
        p.line([(200 + k * 36, 110), (204 + k * 34, 176)], C("#B07A3A"), 1.5)
    for i, c in enumerate(["#C08A33", "#7A8A5A", "#A84A2A", "#D8C9A3"]):
        x = 214 + i * 40
        p.rect((x, 124, x + 22, 152), C(c), r=3, ow=3)
        p.line([(x + 11, 116), (x + 11, 124)], INK, 0.8)
    # 낮은 상 + 이름표 단 물건들 + 마주 보는 방석 둘
    p.rect((214, 222, 354, 232), C("#7A5434"))
    p.rect((222, 232, 230, 256), C("#5A3E26"), ow=3); p.rect((338, 232, 346, 256), C("#5A3E26"), ow=3)
    goods = [(228, "jar"), (262, "bag"), (296, "tin"), (326, "sweet")]
    for x, g in goods:
        if g == "jar":
            p.rect((x, 200, x + 18, 222), C("#C8D8D0"), r=3, ow=3)
        elif g == "bag":
            p.poly([(x, 222), (x + 22, 222), (x + 18, 198), (x + 4, 198)], C("#A06A3A"), ow=3)
        elif g == "tin":
            p.rect((x, 206, x + 20, 222), C("#8A6A44"), ow=3)
        else:
            p.ell((x, 208, x + 18, 222), C("#C9785A"), ow=3)
        p.rect((x + 4, 188, x + 16, 196), C("#F4EEE0"), ow=2)           # 이름표
        p.line([(x + 10, 196), (x + 10, 202)], INK, 0.6)
    p.ell((160, 236, 206, 258), C("#7A2E26")); p.ell((362, 236, 408, 258), C("#3A5A4A"))
    glow(im, 284, 210, 60, a=55)
    return finish(im)


# ══════ 장식 자리 소품 ══════
def slot_bracket():
    im = Image.new("RGBA", (130 * S, 56 * S), (0, 0, 0, 0)); p = Pen(im)
    p.rect((4, 10, 126, 20), C("#7A5434"))
    for x in (16, 106):
        p.poly([(x, 20), (x + 8, 20), (x + 8, 44), (x, 28)], C("#5A4632"), ow=3)
    return im.resize((130, 56), Image.LANCZOS), dict(size=[130, 56], anchor=[65, 10], note="벽 선반. 유물 바닥을 anchor(선반 윗면 가운데)에")


def slot_hook():
    im = Image.new("RGBA", (40 * S, 60 * S), (0, 0, 0, 0)); p = Pen(im)
    p.rect((12, 4, 28, 16), C("#5A4632"), r=3)
    p.d.arc(sc((10, 14, 30, 40)), 0, 200, fill=C("#8A7A60"), width=4 * S)
    p.line([(20, 14), (20, 28)], C("#8A7A60"), 2)
    return im.resize((40, 60), Image.LANCZOS), dict(size=[40, 60], anchor=[20, 40], note="벽 고리. 유물 윗가운데를 anchor 에 매단다(옷·가방·줄)")


def slot_stand():
    im = Image.new("RGBA", (84 * S, 70 * S), (0, 0, 0, 0)); p = Pen(im)
    p.rect((12, 10, 72, 18), C("#86603A"))
    p.poly([(22, 18), (62, 18), (56, 60), (28, 60)], C("#6A4A2A"))
    p.rect((16, 60, 68, 66), C("#5A3E26"), ow=3)
    return im.resize((84, 70), Image.LANCZOS), dict(size=[84, 70], anchor=[42, 10], note="작은 받침대. 바닥에 두지 말고 칸 가운데 기둥(x 150~414)에, 받침 밑면이 바닥 띠(262) 위에 오게")


TAGS = [("warm_kitchen", "따뜻한 부엌", warm_kitchen, ["pantry", "quarters"], "quarters"),
        ("book_smell", "책 냄새", book_smell, ["decoder", "quarters", "lounge"], "quarters"),
        ("shiny_things", "반짝이는 것들", shiny_things, ["lounge", "storage"], "storage"),
        ("soft_corner", "포근한 구석", soft_corner, ["quarters", "bath"], "quarters"),
        ("workbench", "손때 묻은 작업대", workbench, ["workshop", "generator"], "workshop"),
        ("growing", "자라는 창가", growing, ["greenhouse", "well"], "greenhouse"),
        ("clean_shelf", "말끔한 약장", clean_shelf, ["infirmary", "bath"], "infirmary"),
        ("trade_corner", "흥정 자리", trade_corner, ["storage", "lounge"], "storage")]

def window_spots():
    """S19-E 추가: 칸마다 바깥 손님이 유리 너머로 보이는 자리. 탑 칸에는 자기 창이 없으므로(플레이트가 칸을 덮는다)
    가장 가까운 외벽 창(tower_shell 의 창 격자)을 쓴다. 세계 px + 칸 좌표(칸 밖이면 음수·초과값)."""
    import sys
    sys.path.insert(0, HERE); import m5_layout as LY
    D = LY.build()
    # tower_shell 외벽 창: 각 층 윗변 ty 에서 창 위·아래 두 줄(ty+34, ty+194, 높이 124), 한 외벽에 두 열(폭 58)
    L_glass_x = LY.TOWER_X0 + 22 + 14 + 74 + 29          # 왼 외벽 안쪽 열 가운데(바깥 열은 절벽이 덮는다) = 1203
    R_glass_x = LY.SEC_X1 + 22 + 14 + 74 + 29            # 오른 외벽 바깥 열 가운데 = 3459
    out = {"_note": "visitor_world = 손님(물고기·문어·은빛 떼·신인류)이 나타나는 점. glass_world = 그 손님이 비쳐 보이는 외벽 창 가운데. cell_frame 은 칸 좌상단 기준(칸 밖이면 범위를 벗어난다)",
           "cells": {}, "rock_cells": {}, "hall": {}, "entrance": {}}
    for c in D["cells"]:
        ty = c["y"]; gy = ty + 34 + 62                    # 위 줄 창 가운데
        if c["col"] == 0:
            g = (L_glass_x, gy); v = (L_glass_x - 40, gy + 10); via = "facade_left"
            note = "왼 외벽 창. 바깥은 절벽 틈이라 작은 것(물고기·문어)이 어울린다"
        else:
            g = (R_glass_x, gy); v = (LY.TOWER_X1 + 90, gy); via = "facade_right"
            note = "오른 외벽 창 + 바로 밖 열린 물" + (" (가운데 칸은 자기 외벽이 없어 오른 외벽을 같이 쓴다)" if c["col"] == 1 else "")
        out["cells"][str(c["id"])] = dict(via=via, glass_world=list(g), visitor_world=list(v),
                                         cell_frame=[v[0] - c["x"], v[1] - c["y"]], note=note)
    for r in D["rock_cells"]:
        out["rock_cells"][r["id"]] = dict(via=None, note="바위 속 칸 — 유리 없음. 손님 연출을 쓰려면 통로 등불(tunnel 가운데 위) 앞에 작은 것만")
    out["hall"] = dict(via="dome_glass", glass_world=[LY.DOME_GLASS["cx"] + 700, LY.DOME["y"] + 40], visitor_world=[LY.DOME_GLASS["cx"] + 760, LY.DOME["y"] - 20],
                       note="돔 유리 오른쪽 위 바깥")
    out["entrance"] = dict(via="porthole", glass_world=[3708, 960], visitor_world=[3708, 960],
                           note="포드 둥근 창(window 자리 e3) — 손님이 창에 얼굴을 댄다")
    return out


def main():
    meta = {"_note": "S19-E 방 장식 꼬리표 덧씌움. 칸(564×317, M5 layout.json 의 cell) 좌상단에 1:1로 플레이트 위·사람 아래에 그린다. 생성 tools/gen_decor.py, 생성 AI 없음. 꼬리표 정의는 data/draft/room_decor.json",
            "cell": [CW, CH], "anchor": [0, 0], "draw": "plate → decor overlay → 사람 → (방 앞 효과)",
            "clear_zones": {"floor_band_y": FLOOR_Y, "spot_columns_x": [list(SPOT_L), list(SPOT_R)], "spot_columns_below_y": HEAD_Y,
                            "lamp_circle": list(LAMP), "note": "덧씌움은 이 구역을 비운다(사람이 서는 자리 stand_x 84·480, 방 등불)"},
            "plate_name_map": {"generator": "power", "pantry": "(플레이트 없음 → quarters/storage)", "decoder": "(없음 → quarters)",
                               "lounge": "(없음 → storage)", "bath": "(없음 → infirmary)", "well": "(없음 → greenhouse)"},
            "tags": [], "slots": []}
    sheet_items = []
    for tid, ko, fn, rooms, plate in TAGS:
        im = fn()
        # 비움 검사: 바닥 띠·서는 자리 기둥에 그려진 픽셀 수
        a = np.asarray(im.getchannel("A"))
        bad = int((a[FLOOR_Y:, :] > 40).sum() + (a[HEAD_Y:, SPOT_L[0]:SPOT_L[1]] > 40).sum() + (a[HEAD_Y:, SPOT_R[0]:SPOT_R[1]] > 40).sum())
        im.save(os.path.join(DST, f"decor_{tid}.png"), optimize=True)
        meta["tags"].append(dict(id=tid, ko=ko, file=f"decor_{tid}.png", best_rooms=rooms, preview_plate=plate, anchor=[0, 0],
                                 clear_zone_pixels=bad))
        sheet_items.append((tid, ko, im, plate, bad))
        print(tid, "clear-zone px:", bad)
    for name, fn in (("slot_shelf_bracket", slot_bracket), ("slot_hook", slot_hook), ("slot_stand", slot_stand)):
        im, info = fn(); im.save(os.path.join(DST, f"{name}.png"), optimize=True)
        meta["slots"].append(dict(id=name, file=f"{name}.png", **info))
    meta["slot_positions_in_cell"] = {"slot_shelf_bracket": [[150, 60], [280, 160]], "slot_hook": [[100, 40], [440, 40]], "slot_stand": [[240, 192]],
                                      "note": "칸 좌표, 소품 좌상단. 머리 위 벽(y < 95)이나 가운데 기둥에만"}
    meta["window_spot"] = window_spots()
    json.dump(meta, open(os.path.join(DST, "decor_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 접촉 시트: 꼬리표마다 [플레이트만 | 플레이트+덧씌움+주민 둘]
    f = lambda s, b=False: ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf" if b else "C:/Windows/Fonts/malgun.ttf", s)
    roles = ["cook", "scholar", "trader", "kid", "engineer", "farmer", "medic", "scout"]
    pad = 16; colw = CW * 2 + pad * 3
    S_ = Image.new("RGBA", (colw * 2, 60 + 4 * (CH + 44) + 120), (10, 30, 38, 255)); d = ImageDraw.Draw(S_)
    d.text((16, 14), "S19-E 방 장식 꼬리표 — 왼쪽: 플레이트만 / 오른쪽: 덧씌움 + 주민(서는 자리 84·480)  · 생성 AI 없음", font=f(24, True), fill=(232, 220, 191))
    for i, (tid, ko, im, plate, bad) in enumerate(sheet_items):
        cx = (i % 2) * colw + pad; cy = 60 + (i // 2) * (CH + 44)
        pl = Image.open(os.path.join(PLATES, f"room_plate_{plate}_lit.png")).convert("RGBA").crop((54, 33, 618, 350))
        S_.alpha_composite(pl, (cx, cy))
        comp = pl.copy(); comp.alpha_composite(im)
        for k, sx in enumerate((84, 480)):
            sh = Image.open(os.path.join(ROOT, "static", "art", "chars", "front", "p2", "src", f"{roles[(i + k) % 8]}.png")).convert("RGBA")
            ce = sh.crop((0, 2 * 64, 64, 3 * 64)).resize((192, 192), Image.NEAREST)
            comp.alpha_composite(ce, (sx - 96, 282 - 180))
        S_.alpha_composite(comp, (cx + CW + pad, cy))
        d.text((cx, cy + CH + 6), f"{ko}  ({tid}) · 플레이트 {plate} · 비움 구역 침범 {bad}px", font=f(17, True), fill=(240, 200, 120))
    y = 60 + 4 * (CH + 44) + 10; x = 16
    d.text((x, y), "장식 자리 소품:", font=f(18, True), fill=(232, 220, 191)); x += 150
    for s in meta["slots"]:
        im = Image.open(os.path.join(DST, s["file"])).convert("RGBA").resize((s["size"][0] * 2, s["size"][1] * 2), Image.NEAREST)
        bgc = Image.new("RGBA", (im.width + 20, im.height + 20), (60, 48, 36, 255)); bgc.alpha_composite(im, (10, 10))
        S_.alpha_composite(bgc, (x, y)); d.text((x, y + bgc.height + 2), s["id"], font=f(15), fill=(200, 220, 214)); x += bgc.width + 40
    out = os.path.join(ROOT, "docs", "reports", "s19e_decor_sheet.png"); S_.convert("RGB").save(out, optimize=True)
    tot = sum(os.path.getsize(os.path.join(DST, x_)) for x_ in os.listdir(DST))
    print("sheet", out, "decor total KB", tot // 1024)


if __name__ == "__main__":
    main()
