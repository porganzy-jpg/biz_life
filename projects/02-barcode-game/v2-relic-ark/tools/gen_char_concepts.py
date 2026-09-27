# -*- coding: utf-8 -*-
"""
잔해 방주 — 캐릭터 컨셉 여섯 (제로베이스 탐색, 스프린트 6-A 재시작)

  python tools/gen_char_concepts.py           # 여섯 전부
  python tools/gen_char_concepts.py c1 c4     # 일부만

왜 3D 렌더를 베이스로 쓰지 않는가 (이번만의 예외)
  a/b/c 세 변형이 전부 같은 Blender 렌더 위에 후처리만 갈아 끼운 것이었고,
  그래서 세 번 모두 같은 얼굴·같은 덩어리를 물려받았다(REF_ART_FLAT_FOLK §0).
  이번 목적은 "고를 수 있는 서로 다른 여섯"이므로 공통 베이스를 의도적으로 버린다.
  여섯이 각자 자기 형태 언어로 처음부터 그려진다. 생성 AI는 한 점도 쓰지 않는다.

같은 인물(정찰병)임을 알아보게 하는 표식 — 여섯 전부에 들어간다
  ① 뒤로 젖혀 머리에 얹은(또는 쓴) 구식 잠수 헬멧 + 부리처럼 튀어나온 배기관
  ② 두툼한 목 실링 고무테
  ③ 등에 공기통 하나, 헬멧으로 이어지는 호스
  ④ 허리 벨트의 랜턴(이 인물의 유일한 광원)
  ⑤ 왼 어깨의 기운 자국(정찰병 고유 무늬 = 빗금)
  ⑥ 큰 장갑과 무게추 부츠
"""
import os, sys, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "static", "art", "chars", "concepts")

# ── 팔레트: 흙 계열 따뜻한 색. 청록은 물·유리에만 (CONCEPT_DEEP_SEA D1) ──
CREAM   = (240, 226, 198); BONE  = (227, 210, 174)
AMBER   = (232, 184,  92); OCHRE = (216, 162,  65); ORANGE = (193, 113,  44)
OXBLOOD = (139,  58,  42); RUST  = (158,  82,  39)
INK     = ( 26,  22,  17); UMBER = ( 59,  46,  34); BROWN  = ( 91,  68,  41)
OLIVE   = (110, 106,  60); MOSS  = ( 78,  82,  48)
SKIN    = (233, 188, 145); SKIN_SH = (197, 143,  99); SKIN_LT = (245, 213, 176)
SUIT    = (169, 121,  63); SUIT_SH = (122,  81,  39); SUIT_LT = (201, 154,  92)
CANVASC = (185, 143,  82)
BRASS   = (198, 154,  60); BRASS_SH = (142, 106,  32); BRASS_LT = (230, 194, 100)
BLUSH   = (216, 116, 106)
TEAL    = ( 42,  90,  94)          # 물·유리 전용
LAMP    = (255, 214, 140)

ROOM_TOP = (49, 36, 26); ROOM_BOT = (20, 14, 8)


# ══════════════════════════════════════════════════════════════════════
# 0. 그리기 도구
# ══════════════════════════════════════════════════════════════════════
class Pen:
    """초과표본(supersample) 캔버스. 좌표는 전부 최종 해상도 기준으로 쓴다."""
    def __init__(self, w, h, ss=3):
        self.w, self.h, self.ss = w, h, ss
        self.img = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pts):
        s = self.ss
        return [(x * s, y * s) for x, y in pts]

    def poly(self, pts, fill=None, outline=None, width=0):
        self.d.polygon(self._p(pts), fill=fill,
                       outline=outline, width=int(width * self.ss) if width else 0)

    def line(self, pts, fill, width, joint="curve"):
        self.d.line(self._p(pts), fill=fill, width=max(1, int(width * self.ss)), joint=joint)

    def dot(self, cx, cy, r, fill):
        self.poly(ell(cx, cy, r, r), fill=fill)

    def resolve(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def ell(cx, cy, rx, ry, rot=0.0, n=72, a0=0.0, a1=math.tau):
    """회전 타원(또는 호)을 다각형 점열로."""
    c, s = math.cos(rot), math.sin(rot)
    out = []
    for i in range(n + 1):
        t = a0 + (a1 - a0) * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def spline(pts, closed=True, samples=14):
    """Catmull-Rom — 유기적인 덩어리 윤곽용."""
    P = list(pts)
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for s in range(samples):
            t = s / samples; t2 = t * t; t3 = t2 * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    return out


def wobble(pts, amp=2.0, seed=0, freq=0.22):
    """손으로 그은 흔들림 (REF §1-9). 저주파 사인 두 개를 겹친다."""
    rng = random.Random(seed)
    p1, p2 = rng.random() * 6.3, rng.random() * 6.3
    f2 = freq * 2.7
    out = []
    for i, (x, y) in enumerate(pts):
        d = amp * (0.7 * math.sin(i * freq + p1) + 0.3 * math.sin(i * f2 + p2))
        # 법선 방향 대신 간단히 대각 흔들림 — 크기가 작아 차이가 없다
        out.append((x + d, y + d * 0.6))
    return out


def outline_alpha(img, color, width, blur=0.0):
    """알파 실루엣을 부풀려 외곽선 레이어를 만든다."""
    a = img.split()[3]
    dil = a
    k = 3
    for _ in range(max(1, int(width))):
        dil = dil.filter(ImageFilter.MaxFilter(k))
    if blur:
        dil = dil.filter(ImageFilter.GaussianBlur(blur))
    lay = Image.new("RGBA", img.size, color + (0,))
    lay.putalpha(dil)
    return lay


def noise(size, scale=1.0, seed=0, octaves=1):
    """부드러운 회색 노이즈 (0..1)."""
    w, h = size
    rng = np.random.RandomState(seed)
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        sw = max(2, int(w / (scale * (2 ** o))))
        sh = max(2, int(h / (scale * (2 ** o))))
        n = rng.rand(sh, sw).astype(np.float32)
        n = np.array(Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
                     np.float32) / 255.0
        acc += n * amp; tot += amp; amp *= 0.5
    return acc / tot


def grain(img, amount=0.16, scale=2.5, seed=1):
    """연필·붓 결. RGB에 곱하기."""
    arr = np.array(img).astype(np.float32)
    n = noise(img.size, scale=scale, seed=seed, octaves=3)
    n = 1.0 + (n - 0.5) * 2.0 * amount
    arr[..., :3] *= n[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def paper(size, seed=7, strength=0.13):
    """종이 결 — 세로로 늘인 섬유 노이즈."""
    w, h = size
    n = noise((w, h), scale=1.4, seed=seed, octaves=3)
    fib = np.array(Image.fromarray((noise((w, h), 1.0, seed + 5, 1) * 255).astype(np.uint8))
                   .filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255.0
    m = 1.0 + ((n * 0.6 + fib * 0.4) - 0.5) * 2 * strength
    return m


def apply_mul(img, m):
    arr = np.array(img).astype(np.float32)
    arr[..., :3] *= m[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def fuzz(img, amount=3.0, seed=3, density=0.55):
    """펠트 보풀 — 알파 가장자리를 노이즈로 흩뜨린다."""
    a = np.array(img.split()[3]).astype(np.float32) / 255.0
    big = np.array(img.split()[3].filter(ImageFilter.MaxFilter(3))
                   .filter(ImageFilter.GaussianBlur(amount)), np.float32) / 255.0
    n = noise(img.size, scale=0.9, seed=seed, octaves=2)
    halo = np.clip((big - a) * 2.4, 0, 1) * (n > (1 - density)) * n
    newa = np.clip(a + halo, 0, 1)
    out = img.copy()
    out.putalpha(Image.fromarray((newa * 255).astype(np.uint8)))
    return out


def shade_lin(img, top=1.06, bot=0.80):
    """세로 그러데이션 곱하기 — 위가 밝고 아래가 어둡다."""
    w, h = img.size
    g = np.linspace(top, bot, h, dtype=np.float32)[:, None].repeat(w, 1)
    return apply_mul(img, g)


def hexs(c):
    return "#%02x%02x%02x" % c


def _shift(a, dx, dy):
    out = Image.new("L", a.size, 0)
    out.paste(a, (dx, dy))
    return out


def edge_band(img, dx, dy):
    """알파에서 한쪽 가장자리 띠만 뽑는다. (dx,dy)>0 이면 좌상단 가장자리."""
    a = img.split()[3]
    return ImageChops.subtract(a, _shift(a, dx, dy))


def rim_and_core(fig, rim_color=(255, 226, 180), rim_a=0.55, rim_w=4,
                 core_dark=0.55, core_w=9, blur=2.0):
    """회화적 부피 — 좌상단 림라이트 + 우하단 코어 그림자. 3D 렌더 없이 덩어리를 만든다."""
    rim = edge_band(fig, rim_w, rim_w).filter(ImageFilter.GaussianBlur(blur))
    core = edge_band(fig, -core_w, -core_w).filter(ImageFilter.GaussianBlur(blur * 1.6))
    arr = np.array(fig).astype(np.float32)
    c = np.array(core, np.float32) / 255.0
    arr[..., :3] *= (1.0 - c * (1.0 - core_dark))[..., None]
    r = np.array(rim, np.float32) / 255.0 * rim_a
    for i in range(3):
        arr[..., i] = arr[..., i] * (1 - r) + rim_color[i] * r
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    out.putalpha(fig.split()[3])
    return out


# ── 공통 소품: 구식 잠수 헬멧 (여섯 전부 같은 형태, 그리는 방식만 다르다) ──
def helmet_geo(cx, cy, R):
    """머리 위에 얹혀 있는 헬멧. 납작한 접시가 아니라 둥근 돔이다.
    반환 키: shell, rim, port_ring, port, crest, pipe(폴리라인), bolts(점열)"""
    return dict(
        shell=ell(cx, cy, R, R * 0.88),
        rim=ell(cx, cy + R * 0.60, R * 0.99, R * 0.26),
        port_ring=ell(cx + R * 0.30, cy + R * 0.02, R * 0.38, R * 0.35),
        port=ell(cx + R * 0.30, cy + R * 0.02, R * 0.28, R * 0.26),
        crest=ell(cx - R * 0.34, cy - R * 0.40, R * 0.42, R * 0.24, rot=-0.35),
        pipe=[(cx - R * 0.80, cy + R * 0.34), (cx - R * 1.34, cy + R * 0.06),
              (cx - R * 1.52, cy - R * 0.40)],
        bolts=[(cx + math.cos(a) * R * 0.90, cy + math.sin(a) * R * 0.80)
               for a in [math.pi + i * math.pi / 6 for i in range(7)]],
    )


# ══════════════════════════════════════════════════════════════════════
# 1. 공통 배경 / 합성
# ══════════════════════════════════════════════════════════════════════
def room_bg(w, h, lamp_at=None, lamp_r=None):
    """어두운 방 배경. 여섯 전부 같은 배경 위에 놓아야 비교가 공정하다."""
    g = np.zeros((h, w, 3), np.float32)
    for i in range(3):
        g[..., i] = np.linspace(ROOM_TOP[i], ROOM_BOT[i], h, dtype=np.float32)[:, None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    lx, ly = lamp_at or (w * 0.5, h * 0.30)
    lr = lamp_r or (w * 0.62)
    d = np.sqrt((xx - lx) ** 2 + (yy - ly) ** 2) / lr
    glow = np.clip(1.0 - d, 0, 1) ** 2.1
    for i, c in enumerate((70, 46, 20)):
        g[..., i] += glow * c
    n = noise((w, h), 1.2, 11, 2)
    g *= (0.97 + n * 0.06)[..., None]
    img = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert("RGBA")
    # 바닥선
    d2 = ImageDraw.Draw(img)
    fy = int(h * 0.90)
    d2.line([(0, fy), (w, fy)], fill=(58, 42, 26, 160), width=max(1, h // 260))
    return img


def floor_shadow(base, cx, cy, rx, ry, a=120):
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(10, 6, 3, a))
    lay = lay.filter(ImageFilter.GaussianBlur(max(2, ry * 0.5)))
    return Image.alpha_composite(base, lay)


def card(fig, w=640, h=820, feet=772, shadow=True, pixel=False):
    """전신 큰 그림 — 어두운 방 배경 위에 인물을 세운다."""
    bg = room_bg(w, h, lamp_at=(w * 0.5, h * 0.26), lamp_r=w * 0.95)
    fw, fh = fig.size
    x = (w - fw) // 2
    y = feet - fh
    if shadow:
        bg = floor_shadow(bg, w * 0.5, feet - 4, fw * 0.40, fw * 0.075, 150)
    bg.alpha_composite(fig, (x, y))
    return bg


def thumb(fig, px, pad_w=1.9, pad_h=1.45, pixel=False):
    """어두운 방 배경 위의 축소 컷. px = 인물의 세로 픽셀 수."""
    fw, fh = fig.size
    s = px / fh
    nw, nh = max(1, int(round(fw * s))), px
    small = fig.resize((nw, nh), Image.NEAREST if pixel else Image.LANCZOS)
    W, H = int(px * pad_w), int(px * pad_h)
    bg = room_bg(W, H, lamp_at=(W * 0.5, H * 0.28), lamp_r=W * 0.9)
    fy = int(H * 0.90)
    bg = floor_shadow(bg, W * 0.5, fy, nw * 0.42, max(1.5, nw * 0.09), 150)
    bg.alpha_composite(small, ((W - nw) // 2, fy - nh))
    return bg


def silhouette(fig, px):
    """검게 칠한 실루엣 — 04 C1 자가 검수용."""
    fw, fh = fig.size
    s = px / fh
    small = fig.resize((max(1, int(fw * s)), px), Image.LANCZOS)
    a = small.split()[3].point(lambda v: 255 if v > 90 else 0)
    W, H = int(px * 1.9), int(px * 1.45)
    bg = Image.new("RGBA", (W, H), (225, 214, 190, 255))
    sil = Image.new("RGBA", small.size, (20, 16, 12, 0)); sil.putalpha(a)
    bg.alpha_composite(sil, ((W - small.size[0]) // 2, int(H * 0.90) - px))
    return bg


def facecrop(fig, cx, cy, half, size=512, pixel=False):
    box = (int(cx - half), int(cy - half), int(cx + half), int(cy + half))
    pad = Image.new("RGBA", (fig.size[0] + 1200, fig.size[1] + 1200), (0, 0, 0, 0))
    pad.alpha_composite(fig, (600, 600))
    crop = pad.crop((box[0] + 600, box[1] + 600, box[2] + 600, box[3] + 600))
    crop = crop.resize((size, size), Image.NEAREST if pixel else Image.LANCZOS)
    bg = room_bg(size, size, lamp_at=(size * 0.5, size * 0.42), lamp_r=size * 0.85)
    bg.alpha_composite(crop)
    return bg


def save(cid, name, img):
    d = os.path.join(OUT, cid)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    img.convert("RGBA").save(p)
    print("  " + os.path.relpath(p, ROOT).replace("\\", "/"))


# ══════════════════════════════════════════════════════════════════════
# C1. 동화 삽화 — 4.5등신, 얼굴을 전부 그린다, 연필 결, 3단 음영
# ══════════════════════════════════════════════════════════════════════
def concept_c1():
    W, H = 540, 780
    p = Pen(W, H, ss=3)
    cx = 268.0
    FEET = 744.0

    # ── 등 공기통 ──
    p.poly(spline(ell(cx + 108, 360, 44, 92)[::6]), fill=(80, 62, 40))
    p.poly(spline(ell(cx + 104, 352, 34, 78)[::6]), fill=(104, 84, 52))
    p.line(spline([(cx + 96, 288), (cx + 128, 252), (cx + 92, 214), (cx + 46, 206)],
                  closed=False), fill=(64, 48, 32), width=12)

    # ── 다리 · 무게추 부츠 (가운데 어두운 틈으로 갈라 놓는다) ──
    for sgn in (-1, 1):
        bx = cx + sgn * 50
        col = SUIT if sgn < 0 else SUIT_SH
        p.poly(spline([(bx - 38, 500), (bx + 38, 500), (bx + 42, 610), (bx + 36, 678),
                       (bx - 36, 678), (bx - 42, 610)]), fill=col)
        if sgn < 0:
            p.poly(spline([(bx - 36, 508), (bx - 4, 502), (bx - 8, 660), (bx - 34, 664)]),
                   fill=SUIT_LT)
        p.poly(spline([(bx - 52, 664), (bx + 52, 664), (bx + 58, 714), (bx + 48, 740),
                       (bx - 48, 740), (bx - 58, 714)]), fill=(52, 40, 28))
        p.poly([(bx - 54, 694), (bx + 54, 694), (bx + 55, 708), (bx - 55, 708)], fill=BRASS_SH)
    p.poly([(cx - 12, 500), (cx + 12, 500), (cx + 10, 672), (cx - 10, 672)], fill=(44, 33, 22))

    # ── 몸통: 아래가 무거운 덩어리 (REF §1-6) ──
    body = spline([(cx - 96, 306), (cx - 74, 258), (cx, 244), (cx + 74, 258), (cx + 96, 306),
                   (cx + 110, 410), (cx + 104, 512), (cx, 532), (cx - 104, 512), (cx - 110, 410)])
    p.poly(wobble(body, 1.6, 4), fill=SUIT)
    p.poly(spline([(cx - 88, 302), (cx - 44, 256), (cx + 4, 250), (cx + 16, 320),
                   (cx - 2, 430), (cx - 46, 500), (cx - 96, 470), (cx - 104, 360)]), fill=SUIT_LT)
    p.poly(spline([(cx + 44, 268), (cx + 96, 306), (cx + 110, 410), (cx + 104, 512),
                   (cx + 42, 522), (cx + 56, 400)]), fill=SUIT_SH)
    # 앞치마 — 올리브 캔버스. 갈색 일색을 끊는 색 하나
    p.poly(wobble(spline([(cx - 66, 368), (cx + 66, 368), (cx + 78, 470), (cx + 62, 516),
                          (cx - 62, 516), (cx - 78, 470)]), 1.6, 9), fill=MOSS)
    p.poly(spline([(cx - 62, 372), (cx - 8, 370), (cx - 16, 512), (cx - 58, 512)]), fill=OLIVE)
    for i, yy in enumerate((398, 438, 478)):
        p.line(wobble([(cx - 72, yy), (cx, yy + 5), (cx + 74, yy - 2)], 1.2, 10 + i),
               fill=(58, 60, 34), width=3)
    # 적갈 멜빵 — 왼어깨에서 오른허리로
    p.poly(wobble([(cx - 70, 268), (cx - 36, 262), (cx + 62, 486), (cx + 30, 496)], 1.6, 13),
           fill=OXBLOOD)
    # 누빔 주름
    for i, yy in enumerate((318, 344)):
        p.line(wobble([(cx - 96, yy), (cx, yy + 7), (cx + 98, yy - 2)], 1.2, 16 + i),
               fill=SUIT_SH, width=3)

    # ── 왼 어깨 기운 자국(빗금) ──
    for i in range(5):
        x0 = cx - 92 + i * 12
        p.line([(x0, 306 + i * 3), (x0 + 9, 334 + i * 3)], fill=(112, 44, 34), width=4)

    # ── 팔 + 너무 큰 장갑 (안쪽에 어두운 선을 그어 몸통과 떼어 놓는다) ──
    for sgn in (-1, 1):
        sx = cx + sgn * 92
        arm = spline([(sx - sgn * 6, 292), (sx + sgn * 34, 320), (sx + sgn * 44, 394),
                      (sx + sgn * 32, 454), (sx + sgn * 2, 452), (sx - sgn * 10, 380),
                      (sx - sgn * 14, 320)])
        p.poly(wobble(arm, 1.4, 20 + sgn), fill=SUIT_LT if sgn < 0 else (150, 104, 54))
        p.line(wobble([(sx - sgn * 4, 300), (sx + sgn * 2, 372), (sx + sgn * 12, 446)], 1.2, 24),
               fill=(70, 48, 30), width=4)
        p.poly(spline(wobble(ell(sx + sgn * 34, 474, 42, 40)[::6], 1.6, 26 + sgn)), fill=CANVASC)
        p.poly(spline(ell(sx + sgn * 40, 464, 26, 24)[::6]), fill=BONE)
    # 오른손의 짧은 갈고리
    p.line([(cx + 128, 456), (cx + 152, 386)], fill=BRASS_SH, width=9)
    p.line(ell(cx + 144, 378, 17, 17, a0=2.2, a1=5.6)[::2], fill=BRASS, width=9)

    # ── 벨트 + 랜턴 ──
    p.poly([(cx - 108, 476), (cx + 108, 476), (cx + 106, 506), (cx - 106, 506)], fill=(58, 44, 30))
    p.poly([(cx - 26, 470), (cx + 18, 470), (cx + 18, 512), (cx - 26, 512)], fill=BRASS)
    p.poly(spline(ell(cx - 96, 524, 26, 32)[::6]), fill=BRASS_SH)
    p.poly(spline(ell(cx - 96, 524, 17, 22)[::6]), fill=LAMP)

    # ── 목 실링: 솜 덩어리 4겹 ──
    for i, (ry, col) in enumerate(((32, (132, 92, 48)), (27, CANVASC), (22, SUIT_LT), (16, BONE))):
        p.poly(spline(wobble(ell(cx, 262 - i * 13, 106 - i * 9, ry)[::5], 1.8, 30 + i)), fill=col)

    # ── 머리 (달걀형. 귀는 작게) ──
    hx, hy = cx - 2, 158
    p.poly(spline(ell(hx - 74, hy + 18, 12, 17)[::6]), fill=SKIN_SH)
    p.poly(spline(ell(hx + 74, hy + 18, 12, 17)[::6]), fill=SKIN_SH)
    p.poly(spline(wobble(ell(hx, hy, 74, 88)[::5], 2.0, 41)), fill=SKIN)
    p.poly(spline(ell(hx + 30, hy + 12, 46, 74)[::6]), fill=SKIN_SH)
    p.poly(spline(ell(hx - 24, hy - 16, 42, 48)[::6]), fill=SKIN_LT)
    # 머리카락 — 헬멧 밑으로 삐져나온 앞머리
    p.poly(spline([(hx - 70, hy - 26), (hx - 62, hy - 66), (hx - 12, hy - 80),
                   (hx + 52, hy - 70), (hx + 70, hy - 30), (hx + 52, hy - 22),
                   (hx + 26, hy - 44), (hx - 6, hy - 26), (hx - 34, hy - 46),
                   (hx - 52, hy - 16)]), fill=(58, 42, 30))

    # ── 얼굴을 전부 그린다 (DECISIONS 2026-09-27) ──
    for sgn in (-1, 1):
        ex = hx + sgn * 30
        p.poly(spline(ell(ex, hy + 14, 19, 21)[::6]), fill=CREAM)
        p.poly(spline(ell(ex + sgn * 2, hy + 17, 12, 14)[::6]), fill=(42, 30, 22))
        p.dot(ex - sgn * 3, hy + 10, 4.5, CREAM)
        p.line([(ex - 19, hy - 18), (ex - 3, hy - 26), (ex + 17, hy - 20)] if sgn < 0
               else [(ex - 17, hy - 20), (ex + 3, hy - 26), (ex + 19, hy - 18)],
               fill=(64, 46, 32), width=6)
    p.line([(hx - 3, hy + 30), (hx + 3, hy + 41), (hx - 6, hy + 43)], fill=SKIN_SH, width=4)
    p.line(ell(hx, hy + 46, 19, 15, a0=0.35, a1=2.79)[::2], fill=(128, 60, 48), width=5)
    p.poly(spline(ell(hx, hy + 53, 12, 6)[::6]), fill=(176, 90, 74))
    for sgn in (-1, 1):
        lay = Pen(W, H, ss=3)
        lay.poly(spline(ell(hx + sgn * 52, hy + 40, 23, 14)[::6]), fill=BLUSH + (135,))
        p.img.alpha_composite(lay.img)
    rng = random.Random(9)
    for _ in range(11):
        a = rng.uniform(0, math.tau); r = rng.uniform(18, 54)
        p.dot(hx + math.cos(a) * r, hy + 32 + math.sin(a) * 8, 2.6, (188, 128, 90))

    # ── 헬멧: 얼굴을 덮지 않고 정수리에 얹혀 있다 (REF §1-8 번역) ──
    g = helmet_geo(hx + 6, hy - 82, 78)
    p.poly(spline(wobble(g["rim"][::6], 1.4, 60)), fill=(128, 94, 28))
    p.poly(spline(wobble(g["shell"][::5], 1.6, 61)), fill=BRASS)
    p.poly(spline(g["crest"][::6]), fill=BRASS_LT)
    p.poly(spline(g["port_ring"][::6]), fill=BRASS_SH)
    p.poly(spline(g["port"][::6]), fill=TEAL)
    p.poly(spline(ell(hx + 20, hy - 92, 12, 8)[::6]), fill=(118, 166, 164))
    p.line(g["pipe"], fill=(128, 94, 28), width=15)
    p.poly(spline(ell(*g["pipe"][-1], 12, 12)[::8]), fill=(70, 52, 34))
    for bx_, by_ in g["bolts"]:
        p.dot(bx_, by_, 5, BRASS_LT)

    fig = p.resolve()
    ol = outline_alpha(fig, (48, 33, 22), 2, blur=1.2)
    out = Image.alpha_composite(ol, fig)
    out = rim_and_core(out, (255, 224, 176), 0.42, 4, 0.62, 10, 2.4)   # 회화적 부피
    out = grain(out, 0.18, 2.0, 5)
    out = out.filter(ImageFilter.SMOOTH)
    glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - 240, 20, cx + 240, 560], fill=(222, 154, 66, 62))
    glow = glow.filter(ImageFilter.GaussianBlur(64))
    out = Image.alpha_composite(glow, out)
    return out, (hx, hy, 148)


def _concept_c1_old():
    W, H = 520, 720
    p = Pen(W, H, ss=3)
    cx = 262.0
    # --- 등 공기통 (인물 뒤) ---
    p.poly(spline([(cx + 96, 268), (cx + 132, 300), (cx + 134, 392), (cx + 100, 424),
                   (cx + 72, 392), (cx + 70, 300)]), fill=SUIT_SH)
    p.poly(spline([(cx + 100, 272), (cx + 126, 300), (cx + 128, 388), (cx + 104, 414),
                   (cx + 88, 386), (cx + 88, 300)]), fill=BROWN)
    p.line([(cx + 96, 274), (cx + 76, 236), (cx + 40, 214)], fill=UMBER, width=9)

    # --- 다리 / 무게추 부츠 ---
    for sgn in (-1, 1):
        bx = cx + sgn * 44
        p.poly(spline([(bx - 34, 486), (bx + 34, 486), (bx + 38, 610), (bx + 30, 650),
                       (bx - 30, 650), (bx - 38, 610)]), fill=SUIT)
        p.poly(spline([(bx - 46, 640), (bx + 46, 640), (bx + 52, 676), (bx + 44, 692),
                       (bx - 44, 692), (bx - 52, 676)]), fill=UMBER)
        p.poly([(bx - 46, 660), (bx + 46, 660), (bx + 47, 670), (bx - 47, 670)], fill=BRASS_SH)

    # --- 몸통: 아래가 넓은 덩어리 (REF §1-6) ---
    body = spline([(cx - 96, 300), (cx - 78, 250), (cx, 236), (cx + 78, 250), (cx + 96, 300),
                   (cx + 108, 400), (cx + 96, 486), (cx, 506), (cx - 96, 486), (cx - 108, 400)])
    p.poly(wobble(body, 1.6, 4), fill=SUIT)
    # 누빔 3단 음영 (밝은 면 / 중간 / 그림자)
    p.poly(spline([(cx - 84, 296), (cx - 46, 250), (cx + 6, 244), (cx + 20, 300),
                   (cx + 4, 420), (cx - 40, 470), (cx - 92, 440), (cx - 100, 350)]), fill=SUIT_LT)
    p.poly(spline([(cx + 40, 270), (cx + 96, 300), (cx + 108, 400), (cx + 96, 486),
                   (cx + 40, 496), (cx + 52, 390)]), fill=SUIT_SH)
    for i, yy in enumerate((330, 372, 414, 456)):
        p.line(wobble([(cx - 100 + i * 2, yy), (cx - 40, yy + 6), (cx + 40, yy + 4),
                       (cx + 104 - i * 2, yy - 2)], 1.2, 10 + i), fill=SUIT_SH, width=3)

    # --- 왼 어깨 기운 자국(빗금) ---
    for i in range(5):
        x0 = cx - 92 + i * 13
        p.line([(x0, 300 + i * 3), (x0 + 9, 326 + i * 3)], fill=OXBLOOD, width=3)

    # --- 팔 + 너무 큰 장갑 ---
    for sgn in (-1, 1):
        sx = cx + sgn * 96
        arm = spline([(sx, 296), (sx + sgn * 34, 330), (sx + sgn * 40, 400),
                      (sx + sgn * 26, 448), (sx - sgn * 4, 444), (sx - sgn * 14, 380),
                      (sx - sgn * 16, 320)])
        p.poly(wobble(arm, 1.4, 20 + sgn), fill=SUIT if sgn < 0 else SUIT_SH)
        p.poly(spline(ell(sx + sgn * 30, 464, 40, 40)[::6]), fill=CANVASC)
        p.poly(spline(ell(sx + sgn * 34, 456, 26, 26)[::6]), fill=SUIT_LT)
    # 오른손의 짧은 갈고리
    p.line([(cx + 126, 446), (cx + 146, 380)], fill=BRASS_SH, width=8)
    p.line(ell(cx + 138, 372, 16, 16, a0=2.2, a1=5.6)[::2], fill=BRASS, width=8)

    # --- 목 실링: 솜 덩어리 4겹 ---
    for i, (ry, col) in enumerate(((30, SUIT_SH), (26, CANVASC), (22, SUIT_LT), (16, BONE))):
        p.poly(spline(wobble(ell(cx, 254 - i * 12, 104 - i * 9, ry)[::5], 1.6, 30 + i)),
               fill=col)

    # --- 머리 ---
    hx, hy = cx - 2, 150
    head = spline(wobble(ell(hx, hy, 84, 92)[::5], 2.0, 41))
    p.poly(head, fill=SKIN)
    p.poly(spline(ell(hx + 34, hy + 10, 52, 78)[::6]), fill=SKIN_SH)   # 그림자쪽
    p.poly(spline(ell(hx - 28, hy - 18, 46, 52)[::6]), fill=SKIN_LT)   # 밝은 면
    # 귀
    p.poly(spline(ell(hx - 84, hy + 12, 14, 20)[::6]), fill=SKIN_SH)
    p.poly(spline(ell(hx + 84, hy + 12, 14, 20)[::6]), fill=SKIN_SH)
    # 머리카락 (이마 앞머리 몇 갈래)
    p.poly(spline([(hx - 76, hy - 40), (hx - 40, hy - 86), (hx + 24, hy - 92),
                   (hx + 72, hy - 58), (hx + 60, hy - 30), (hx + 20, hy - 52),
                   (hx - 16, hy - 34), (hx - 48, hy - 24)]), fill=UMBER)

    # --- 얼굴을 전부 그린다 (DECISIONS 2026-09-27) ---
    for sgn in (-1, 1):
        ex = hx + sgn * 32
        p.poly(spline(ell(ex, hy + 12, 20, 22)[::6]), fill=CREAM)        # 흰자
        p.poly(spline(ell(ex + sgn * 2, hy + 15, 12, 14)[::6]), fill=(40, 30, 22))  # 동공
        p.dot(ex - sgn * 3, hy + 8, 4.5, CREAM)                           # 하이라이트
        p.line([(ex - 20, hy - 20), (ex - 4, hy - 28), (ex + 18, hy - 22)]
               if sgn < 0 else
               [(ex - 18, hy - 22), (ex + 4, hy - 28), (ex + 20, hy - 20)],
               fill=UMBER, width=6)                                       # 눈썹
    p.line([(hx - 4, hy + 30), (hx + 2, hy + 40), (hx - 6, hy + 42)], fill=SKIN_SH, width=4)  # 코
    p.line(ell(hx, hy + 44, 20, 16, a0=0.35, a1=2.79)[::2], fill=(122, 58, 48), width=5)      # 입
    p.poly(spline(ell(hx, hy + 52, 13, 6)[::6]), fill=(168, 84, 70))                          # 아랫입술 안쪽
    for sgn in (-1, 1):                                                                       # 볼 홍조
        lay = Pen(W, H, ss=3)
        lay.poly(spline(ell(hx + sgn * 58, hy + 40, 24, 15)[::6]), fill=BLUSH + (140,))
        p.img.alpha_composite(lay.img)
    rng = random.Random(9)                                                                    # 주근깨
    for _ in range(11):
        a = rng.uniform(0, math.tau); r = rng.uniform(20, 62)
        p.dot(hx + math.cos(a) * r, hy + 32 + math.sin(a) * 9, 2.6, (186, 126, 88))

    # --- 헬멧: 얼굴을 덮지 않고 머리 위에 얹혀 있다 (REF §1-8 번역) ---
    p.poly(spline(ell(hx + 4, hy - 74, 92, 62)[::5]), fill=BRASS_SH)
    p.poly(spline(ell(hx + 2, hy - 82, 84, 56)[::5]), fill=BRASS)
    p.poly(spline(ell(hx - 22, hy - 96, 44, 26)[::6]), fill=BRASS_LT)
    p.poly(spline(ell(hx + 10, hy - 78, 34, 26)[::6]), fill=TEAL)            # 창(물색은 여기만)
    p.poly(spline(ell(hx + 2, hy - 86, 18, 11)[::6]), fill=(96, 148, 148))
    p.line([(hx - 86, hy - 66), (hx - 122, hy - 48), (hx - 130, hy - 30)], fill=BRASS_SH, width=13)  # 배기관(부리)
    for i in range(8):                                                       # 놋쇠 리벳
        a = math.pi + i * math.pi / 7
        p.dot(hx + 4 + math.cos(a) * 88, hy - 74 + math.sin(a) * 58, 5, BRASS_LT)

    # --- 허리 벨트 + 랜턴 ---
    p.poly([(cx - 104, 452), (cx + 106, 452), (cx + 104, 480), (cx - 102, 480)], fill=UMBER)
    p.poly([(cx - 40, 448), (cx + 4, 448), (cx + 4, 484), (cx - 40, 484)], fill=BRASS)
    p.poly(spline(ell(cx - 84, 498, 24, 30)[::6]), fill=BRASS_SH)
    p.poly(spline(ell(cx - 84, 498, 16, 21)[::6]), fill=LAMP)

    fig = p.resolve()
    # 외곽선: 검정이 아니라 따뜻한 갈색, 부드러운 가장자리 (REF §0 정정)
    ol = outline_alpha(fig, (46, 32, 22), 2, blur=1.1)
    out = Image.alpha_composite(ol, fig)
    out = grain(out, 0.17, 2.2, 5)
    out = out.filter(ImageFilter.SMOOTH)
    # 황토 후광 — 인물이 따뜻한 빛에 잠긴다
    glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - 230, 20, cx + 230, 520], fill=(214, 148, 64, 58))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    out = Image.alpha_composite(glow, out)
    return out, (cx - 2, 150, 150)


# ══════════════════════════════════════════════════════════════════════
# C2. 통통 치비 — 2.6등신, 굵고 부드러운 외곽선, 평면 채색 + 1단 음영
# ══════════════════════════════════════════════════════════════════════
def concept_c2():
    W, H = 520, 700
    p = Pen(W, H, ss=3)
    cx = 260.0
    hy = 232.0; HR = 132.0      # 머리 반지름 — 2.6등신

    # 공기통
    p.poly(spline(ell(cx + 96, 470, 46, 64)[::6]), fill=SUIT_SH)
    p.poly(spline(ell(cx + 96, 462, 36, 52)[::6]), fill=BROWN)

    # 다리 (짧고 뭉툭)
    for sgn in (-1, 1):
        bx = cx + sgn * 42
        p.poly(spline(ell(bx, 586, 36, 52)[::6]), fill=SUIT)
        p.poly(spline(ell(bx, 632, 46, 30)[::6]), fill=UMBER)

    # 몸통 — 작고 둥글다
    p.poly(spline([(cx - 86, 430), (cx - 72, 386), (cx, 372), (cx + 72, 386), (cx + 86, 430),
                   (cx + 92, 520), (cx, 560), (cx - 92, 520)]), fill=SUIT)
    p.poly(spline([(cx - 86, 470), (cx, 450), (cx + 90, 470), (cx + 92, 520),
                   (cx, 560), (cx - 92, 520)]), fill=SUIT_SH)     # 음영 1단
    # 어깨 기운 자국
    for i in range(4):
        x0 = cx - 78 + i * 12
        p.line([(x0, 404 + i * 2), (x0 + 8, 424 + i * 2)], fill=OXBLOOD, width=4)
    # 벨트 + 랜턴
    p.poly([(cx - 90, 500), (cx + 92, 500), (cx + 90, 524), (cx - 88, 524)], fill=UMBER)
    p.poly(spline(ell(cx - 72, 542, 20, 25)[::6]), fill=BRASS)
    p.poly(spline(ell(cx - 72, 542, 12, 16)[::6]), fill=LAMP)

    # 팔 + 큰 벙어리 장갑
    for sgn in (-1, 1):
        sx = cx + sgn * 84
        p.poly(spline(ell(sx + sgn * 14, 452, 28, 46, rot=sgn * 0.25)[::6]), fill=SUIT)
        p.poly(spline(ell(sx + sgn * 26, 504, 36, 34)[::6]), fill=CANVASC)

    # 목 실링 (머리와 몸 사이 도넛)
    p.poly(spline(ell(cx, 372, 84, 30)[::6]), fill=SUIT_LT)
    p.poly(spline(ell(cx, 380, 78, 22)[::6]), fill=CANVASC)

    # 머리 — 아주 크고 둥글다
    p.poly(spline(ell(cx, hy, HR, HR * 0.96)[::5]), fill=SKIN)
    p.poly(spline(ell(cx, hy + 44, HR * 0.92, HR * 0.54)[::6]), fill=SKIN_SH)   # 턱 그림자 1단
    p.poly(spline(ell(cx, hy - 10, HR * 0.94, HR * 0.78)[::6]), fill=SKIN)
    # 앞머리
    p.poly(spline([(cx - 124, hy - 34), (cx - 96, hy - 112), (cx - 10, hy - 134),
                   (cx + 96, hy - 106), (cx + 122, hy - 30), (cx + 86, hy - 56),
                   (cx + 34, hy - 84), (cx - 30, hy - 66), (cx - 82, hy - 44)]), fill=UMBER)

    # 큰 눈 + 하이라이트 둘 (C2 원칙)
    for sgn in (-1, 1):
        ex = cx + sgn * 50
        p.poly(spline(ell(ex, hy + 16, 30, 38)[::6]), fill=(32, 24, 18))
        p.poly(spline(ell(ex, hy + 22, 22, 26)[::6]), fill=(76, 50, 34))
        p.dot(ex - sgn * 9, hy + 2, 11, CREAM)
        p.dot(ex + sgn * 11, hy + 30, 5, CREAM)
        p.line([(ex - 26, hy - 34), (ex + 26, hy - 42)] if sgn < 0
               else [(ex - 26, hy - 42), (ex + 26, hy - 34)], fill=UMBER, width=8)
    # 작은 입 + 볼 홍조
    p.line(ell(cx, hy + 66, 14, 11, a0=0.4, a1=2.74)[::2], fill=(122, 58, 48), width=6)
    for sgn in (-1, 1):
        lay = Pen(W, H, ss=3)
        lay.poly(spline(ell(cx + sgn * 88, hy + 50, 26, 17)[::6]), fill=BLUSH + (150,))
        p.img.alpha_composite(lay.img)

    # 헬멧 — 뒤로 젖혀 정수리에 얹음
    p.poly(spline(ell(cx + 4, hy - 108, 112, 66)[::5]), fill=BRASS)
    p.poly(spline(ell(cx - 24, hy - 124, 54, 28)[::6]), fill=BRASS_LT)
    p.poly(spline(ell(cx + 22, hy - 104, 40, 30)[::6]), fill=TEAL)
    p.line([(cx - 108, hy - 96), (cx - 150, hy - 74), (cx - 158, hy - 52)], fill=BRASS_SH, width=15)
    for i in range(7):
        a = math.pi + i * math.pi / 6
        p.dot(cx + 4 + math.cos(a) * 112, hy - 108 + math.sin(a) * 66, 6, BRASS_SH)

    fig = p.resolve()
    ol = outline_alpha(fig, (36, 26, 18), 3, blur=0.5)      # 굵고 부드러운 외곽선
    out = Image.alpha_composite(ol, fig)
    return out, (cx, hy, 190)


# ══════════════════════════════════════════════════════════════════════
# C3. 잠수복이 캐릭터다 — 체형 없음, 헬멧 창 불빛이 표정
# ══════════════════════════════════════════════════════════════════════
def _c3_helmet(p, cx, cy, R, mood="calm"):
    """헬멧 하나. mood 가 창 불빛의 밝기·색·기울기를 정한다."""
    tilt = {"calm": 0.0, "alarm": -0.16, "tired": 0.20}[mood]
    glow = {"calm": (232, 176, 92), "alarm": (255, 232, 186), "tired": (150, 98, 44)}[mood]
    gr = {"calm": 0.64, "alarm": 0.86, "tired": 0.44}[mood]
    c, s = math.cos(tilt), math.sin(tilt)

    def T(x, y):
        return (cx + x * c - y * s, cy + x * s + y * c)

    p.poly([T(*q) for q in [(-R * 0.86, R * 0.86), (R * 0.86, R * 0.86),
                            (R * 1.02, R * 1.16), (-R * 1.02, R * 1.16)]], fill=BRASS_SH)
    p.poly([T(x - cx, y - cy) for x, y in ell(cx, cy, R, R * 1.02)[::5]], fill=BRASS)
    p.poly([T(x - cx, y - cy) for x, y in ell(cx - R * 0.34, cy - R * 0.40, R * 0.44, R * 0.34)[::6]],
           fill=BRASS_LT)
    # 창
    pr = R * 0.56
    p.poly([T(x - cx, y - cy) for x, y in ell(cx, cy + R * 0.06, pr + 9, pr + 9)[::5]], fill=BRASS_SH)
    p.poly([T(x - cx, y - cy) for x, y in ell(cx, cy + R * 0.06, pr, pr)[::5]], fill=(38, 28, 20))
    # 창 안의 따뜻한 불빛 (표정)
    lay = Pen(p.w, p.h, ss=p.ss)
    lay.poly([T(x - cx, y - cy) for x, y in ell(cx, cy + R * 0.10, pr * 0.92, pr * 0.92)[::5]],
             fill=glow + (int(255 * gr),))
    lay.poly([T(x - cx, y - cy) for x, y in ell(cx - pr * 0.3, cy - pr * 0.2, pr * 0.42, pr * 0.34)[::6]],
             fill=(255, 240, 210, int(220 * gr)))
    li = lay.resolve().filter(ImageFilter.GaussianBlur(3))
    p.img.alpha_composite(li.resize(p.img.size, Image.LANCZOS))
    # 창 유리의 반사 두 줄 (D4 유리는 두 번 보인다)
    p.line([T(-pr * 0.66, -pr * 0.28), T(-pr * 0.16, -pr * 0.66)], fill=(224, 236, 236), width=R * 0.07)
    p.line([T(-pr * 0.30, -pr * 0.02), T(-pr * 0.06, -pr * 0.30)], fill=(200, 218, 218), width=R * 0.045)
    # 옆 작은 창 + 리벳 + 배기관(부리)
    p.poly([T(x - cx, y - cy) for x, y in ell(cx - R * 0.80, cy + R * 0.10, R * 0.15, R * 0.18)[::6]],
           fill=TEAL)
    for i in range(12):
        a = i * math.tau / 12
        p.dot(*T(math.cos(a) * R * 0.92, math.sin(a) * R * 0.94), R * 0.055, BRASS_SH)
    p.line([T(R * 0.70, R * 0.30), T(R * 1.30, R * 0.52), T(R * 1.48, R * 0.86)],
           fill=BRASS_SH, width=R * 0.20)
    p.poly([T(x - cx, y - cy) for x, y in ell(cx + R * 1.46, cy + R * 0.88, R * 0.16, R * 0.16)[::8]],
           fill=UMBER)


def concept_c3():
    W, H = 540, 720
    p = Pen(W, H, ss=3)
    cx = 270.0

    # 등 공기통 + 호스
    p.poly(spline(ell(cx + 104, 330, 46, 86)[::6]), fill=SUIT_SH)
    p.line(spline([(cx + 96, 268), (cx + 130, 248), (cx + 112, 214), (cx + 78, 208)],
                  closed=False), fill=UMBER, width=14)

    # 한 덩어리 자루 — 어깨에서 밑단으로 넓어진다. 체형이 없다.
    sack = spline([(cx - 92, 262), (cx - 66, 226), (cx + 66, 226), (cx + 92, 262),
                   (cx + 124, 400), (cx + 152, 574), (cx + 146, 622),
                   (cx - 146, 622), (cx - 152, 574), (cx - 124, 400)])
    p.poly(wobble(sack, 1.4, 7), fill=SUIT)
    p.poly(spline([(cx + 30, 234), (cx + 92, 262), (cx + 124, 400), (cx + 152, 574),
                   (cx + 146, 622), (cx + 44, 624), (cx + 60, 420)]), fill=SUIT_SH)
    p.poly(spline([(cx - 84, 262), (cx - 40, 230), (cx - 10, 244), (cx - 22, 420),
                   (cx - 58, 600), (cx - 118, 596), (cx - 116, 400)]), fill=SUIT_LT)
    # 누빔 가로줄 — 자루를 옷으로 만든다
    for i in range(9):
        yy = 286 + i * 38
        wdt = 96 + i * 7
        p.line(wobble([(cx - wdt, yy), (cx, yy + 8), (cx + wdt, yy - 2)], 1.4, 40 + i),
               fill=SUIT_SH, width=4)
    # 밑단 + 무게추 부츠 (자루 아래로 조금만)
    p.poly(spline([(cx - 150, 604), (cx + 150, 604), (cx + 146, 640), (cx - 146, 640)]), fill=UMBER)
    for sgn in (-1, 1):
        p.poly(spline(ell(cx + sgn * 66, 662, 58, 30)[::6]), fill=UMBER)
        p.poly([(cx + sgn * 66 - 56, 656), (cx + sgn * 66 + 56, 656),
                (cx + sgn * 66 + 54, 668), (cx + sgn * 66 - 54, 668)], fill=BRASS_SH)

    # 어깨 기운 자국
    for i in range(5):
        x0 = cx - 104 + i * 13
        p.line([(x0, 300 + i * 3), (x0 + 9, 328 + i * 3)], fill=OXBLOOD, width=4)

    # 팔 — 자루에서 자란 두 뭉치. 손은 큰 장갑 하나
    for sgn in (-1, 1):
        p.poly(spline([(cx + sgn * 92, 268), (cx + sgn * 136, 306), (cx + sgn * 142, 396),
                       (cx + sgn * 118, 444), (cx + sgn * 92, 420), (cx + sgn * 86, 330)]),
               fill=SUIT if sgn < 0 else SUIT_SH)
        p.poly(spline(ell(cx + sgn * 122, 462, 42, 40)[::6]), fill=CANVASC)
    # 왼손의 그물 자루
    p.poly(spline([(cx - 164, 470), (cx - 128, 476), (cx - 120, 552), (cx - 156, 572),
                   (cx - 186, 540)]), fill=MOSS)
    for i in range(4):
        p.line([(cx - 182 + i * 16, 482), (cx - 172 + i * 16, 566)], fill=OLIVE, width=3)

    # 벨트 랜턴
    p.poly(spline(ell(cx - 130, 392, 26, 32)[::6]), fill=BRASS_SH)
    p.poly(spline(ell(cx - 130, 392, 17, 22)[::6]), fill=LAMP)

    # 헬멧
    _c3_helmet(p, cx, 178, 104, "calm")

    fig = p.resolve()
    ol = outline_alpha(fig, (30, 22, 15), 2, blur=0.6)
    out = Image.alpha_composite(ol, fig)
    out = grain(out, 0.10, 2.8, 12)
    # 헬멧 불빛이 어깨에 떨어진다 (D3 빛은 전부 근거가 있다)
    sp = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(sp).ellipse([cx - 150, 190, cx + 150, 350], fill=(240, 180, 96, 46))
    sp = sp.filter(ImageFilter.GaussianBlur(34))
    out = Image.alpha_composite(out, sp)
    return out, (cx, 178, 150)


def c3_moods():
    """헬멧 세 표정 — 이 컨셉이 표정을 무엇으로 말하는지 보여주는 판."""
    W, H = 512, 190
    img = room_bg(W, H, lamp_at=(W * 0.5, H * 0.4), lamp_r=W * 0.8)
    labels = [("calm", "평온"), ("alarm", "놀람"), ("tired", "지침")]
    for i, (m, _) in enumerate(labels):
        p = Pen(W, H, ss=3)
        _c3_helmet(p, 86 + i * 170, 92, 62, m)
        f = p.resolve()
        img = Image.alpha_composite(img, Image.alpha_composite(outline_alpha(f, (30, 22, 15), 2), f))
    return img


# ══════════════════════════════════════════════════════════════════════
# C4. 픽셀 도트 — 그리드 위에서 직접, 제한 팔레트 14색
# ══════════════════════════════════════════════════════════════════════
P4 = {
    ".": None, "#": (26, 22, 17), "d": (59, 46, 34), "s": (122, 81, 39),
    "S": (169, 121, 63), "L": (201, 154, 92), "k": (233, 188, 145), "K": (197, 143, 99),
    "c": (240, 226, 198), "b": (198, 154, 60), "B": (230, 194, 100), "o": (139, 58, 42),
    "v": (110, 106, 60), "l": (255, 214, 140), "t": (42, 90, 94),
}


class PixGrid:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.g = [["." for _ in range(w)] for _ in range(h)]

    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = c

    def rect(self, x0, y0, x1, y1, c):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.px(x, y, c)

    def ell(self, cx, cy, rx, ry, c):
        for y in range(int(cy - ry), int(cy + ry) + 1):
            for x in range(int(cx - rx), int(cx + rx) + 1):
                if ((x - cx) / max(0.5, rx)) ** 2 + ((y - cy) / max(0.5, ry)) ** 2 <= 1.02:
                    self.px(x, y, c)

    def outline(self, c="#"):
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.g[y][x] != ".":
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.w and 0 <= ny < self.h and self.g[ny][nx] not in (".", c):
                        add.append((x, y)); break
        for x, y in add:
            self.px(x, y, c)

    def image(self):
        im = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        pix = im.load()
        for y in range(self.h):
            for x in range(self.w):
                col = P4[self.g[y][x]]
                if col:
                    pix[x, y] = col + (255,)
        return im


def concept_c4():
    g = PixGrid(40, 55)
    cx = 20
    # 공기통(뒤)
    g.rect(cx + 8, 26, cx + 11, 38, "d")
    g.rect(cx + 9, 27, cx + 10, 37, "s")
    # 다리
    for sgn in (-1, 1):
        bx = cx + sgn * 5 - (1 if sgn < 0 else 0)
        g.rect(bx - 2, 41, bx + 2, 48, "S")
        g.rect(bx + (1 if sgn > 0 else -2), 41, bx + (2 if sgn > 0 else -1), 48, "s")
        g.rect(bx - 4, 49, bx + 4, 52, "d")
        g.rect(bx - 4, 50, bx + 4, 50, "b")
    # 몸통
    g.rect(cx - 8, 26, cx + 7, 43, "S")
    g.rect(cx - 8, 26, cx - 2, 43, "L")      # 밝은 면(랜턴 쪽)
    g.rect(cx + 4, 26, cx + 7, 43, "s")      # 그림자 면
    for y in (30, 34, 38):                   # 누빔
        g.rect(cx - 8, y, cx + 7, y, "s")
    # 어깨 기운 자국(빗금) — 정찰병 표식
    for i in range(3):
        g.px(cx - 7 + i * 2, 28 + i, "o"); g.px(cx - 6 + i * 2, 29 + i, "o")
    # 벨트 + 랜턴
    g.rect(cx - 8, 40, cx + 7, 41, "d")
    g.rect(cx - 11, 42, cx - 9, 45, "b")
    g.rect(cx - 10, 43, cx - 10, 44, "l")
    # 팔 + 큰 장갑
    for sgn in (-1, 1):
        ax = cx + (8 if sgn > 0 else -9)
        g.rect(ax, 27, ax + (2 if sgn > 0 else 0) - (0 if sgn > 0 else -2), 37,
               "s" if sgn > 0 else "S")
        g.rect(ax - (0 if sgn > 0 else 1), 38, ax + (3 if sgn > 0 else 2) - (0 if sgn > 0 else 1), 41, "L")
    # 목 실링 (3겹)
    g.rect(cx - 9, 23, cx + 8, 25, "L")
    g.rect(cx - 8, 22, cx + 7, 22, "S")
    g.rect(cx - 9, 24, cx + 8, 24, "s")
    # 머리
    g.ell(cx - 1, 15, 7, 8, "k")
    g.rect(cx + 3, 9, cx + 5, 21, "K")       # 그림자 면
    g.ell(cx - 3, 12, 4, 4, "k")
    # 머리카락
    g.rect(cx - 8, 7, cx + 6, 9, "d")
    g.px(cx - 6, 10, "d"); g.px(cx - 2, 10, "d"); g.px(cx + 3, 10, "d")
    # 얼굴 — 55px 에서도 읽히게 눈 2x2, 입 2x1, 눈썹 3x1
    for sgn in (-1, 1):
        ex = cx - 1 + sgn * 3
        g.rect(ex - 1, 15, ex, 16, "#")
        g.px(ex - 1, 15, "c")
        g.rect(ex - 2, 13, ex + 1, 13, "d")     # 눈썹
    g.rect(cx - 2, 19, cx, 19, "o")             # 입
    g.px(cx - 6, 18, "o"); g.px(cx + 4, 18, "o")   # 볼 홍조
    # 헬멧 — 정수리에 얹음
    g.ell(cx, 4, 9, 5, "b")
    g.ell(cx - 3, 2, 5, 2, "B")
    g.ell(cx + 3, 4, 3, 2, "t")
    g.rect(cx - 13, 5, cx - 9, 6, "b")          # 배기관
    g.px(cx - 14, 6, "d")
    for x in range(cx - 8, cx + 9, 4):
        g.px(x, 8, "s")
    g.outline("#")
    im = g.image()
    # 여백 잘라내기
    bb = im.getbbox()
    return im.crop(bb), None


# ══════════════════════════════════════════════════════════════════════
# C5. 종이 오림 — 납작한 색 면 + 종이 결 + 얕은 그림자 + 놋쇠 핀
# ══════════════════════════════════════════════════════════════════════
def concept_c5():
    W, H = 520, 720
    cx = 260.0
    layers = []   # (그릴 함수, z깊이) — 깊이마다 그림자 오프셋이 다르다

    def L(fn, depth):
        p = Pen(W, H, ss=3)
        fn(p)
        layers.append((p.resolve(), depth))

    # 뒤 → 앞 순서
    L(lambda p: [
        p.poly(wobble([(cx + 70, 268), (cx + 132, 280), (cx + 138, 400), (cx + 74, 392)], 2.2, 1),
               fill=SUIT_SH),
        p.poly([(cx + 84, 288), (cx + 126, 296), (cx + 128, 318), (cx + 86, 310)], fill=BROWN),
    ], 1)
    # 다리
    L(lambda p: [
        p.poly(wobble([(cx - 76, 470), (cx - 12, 470), (cx - 14, 640), (cx - 74, 640)], 2.0, 2),
               fill=CANVASC),
        p.poly(wobble([(cx + 12, 470), (cx + 76, 470), (cx + 78, 640), (cx + 16, 640)], 2.0, 3),
               fill=SUIT),
    ], 1)
    # 부츠
    L(lambda p: [
        p.poly(wobble([(cx - 86, 632), (cx - 6, 632), (cx - 4, 684), (cx - 92, 684)], 2.0, 4),
               fill=UMBER),
        p.poly(wobble([(cx + 8, 632), (cx + 88, 632), (cx + 94, 684), (cx + 6, 684)], 2.0, 5),
               fill=UMBER),
        p.poly([(cx - 92, 662), (cx - 4, 662), (cx - 4, 672), (cx - 92, 672)], fill=BRASS),
        p.poly([(cx + 6, 662), (cx + 94, 662), (cx + 94, 672), (cx + 6, 672)], fill=BRASS),
    ], 2)
    # 몸통 (오린 사다리꼴 + 한쪽에 덧댄 조각)
    L(lambda p: [
        p.poly(wobble([(cx - 84, 262), (cx + 84, 262), (cx + 106, 480), (cx - 106, 480)], 2.4, 6),
               fill=SUIT),
        p.poly(wobble([(cx - 84, 262), (cx - 16, 262), (cx - 30, 480), (cx - 106, 480)], 2.2, 7),
               fill=CANVASC),
        # 덧댄 기움 조각(정찰병 빗금)
        p.poly(wobble([(cx - 78, 300), (cx - 24, 306), (cx - 30, 362), (cx - 82, 356)], 1.8, 8),
               fill=RUST),
        *[p.line([(cx - 74 + i * 12, 306), (cx - 66 + i * 12, 358)], fill=OXBLOOD, width=4)
          for i in range(5)],
    ], 3)
    # 벨트 + 랜턴
    L(lambda p: [
        p.poly([(cx - 104, 440), (cx + 104, 440), (cx + 104, 470), (cx - 104, 470)], fill=UMBER),
        p.poly([(cx - 22, 434), (cx + 18, 434), (cx + 18, 476), (cx - 22, 476)], fill=BRASS),
        p.poly([(cx - 112, 476), (cx - 66, 476), (cx - 70, 528), (cx - 108, 528)], fill=BRASS_SH),
        p.poly([(cx - 104, 486), (cx - 74, 486), (cx - 77, 518), (cx - 101, 518)], fill=LAMP),
    ], 4)
    # 팔 (핀으로 연결된 두 마디)
    for sgn in (-1, 1):
        L(lambda p, s=sgn: [
            p.poly(wobble([(cx + s * 70, 268), (cx + s * 124, 282), (cx + s * 132, 372),
                           (cx + s * 82, 366)], 2.0, 10 + s), fill=SUIT_SH if s > 0 else SUIT),
            p.poly(wobble([(cx + s * 82, 358), (cx + s * 130, 364), (cx + s * 134, 442),
                           (cx + s * 88, 440)], 2.0, 12 + s), fill=CANVASC),
            p.poly(wobble([(cx + s * 78, 438), (cx + s * 142, 442), (cx + s * 138, 496),
                           (cx + s * 80, 492)], 2.0, 14 + s), fill=BONE),
        ], 5)
    # 목 실링 (오려 겹친 띠 3장)
    L(lambda p: [
        p.poly(wobble([(cx - 96, 238), (cx + 96, 238), (cx + 88, 268), (cx - 88, 268)], 2.2, 20),
               fill=SUIT_LT),
        p.poly(wobble([(cx - 86, 222), (cx + 86, 222), (cx + 82, 244), (cx - 82, 244)], 2.0, 21),
               fill=CANVASC),
        p.poly(wobble([(cx - 76, 208), (cx + 76, 208), (cx + 74, 226), (cx - 74, 226)], 1.8, 22),
               fill=BONE),
    ], 6)
    # 머리
    L(lambda p: [
        p.poly(wobble([(cx - 72, 96), (cx - 46, 62), (cx + 46, 62), (cx + 72, 96),
                       (cx + 66, 186), (cx + 28, 212), (cx - 28, 212), (cx - 66, 186)], 2.4, 30),
               fill=SKIN),
        p.poly(wobble([(cx + 18, 66), (cx + 46, 62), (cx + 72, 96), (cx + 66, 186),
                       (cx + 28, 212), (cx + 12, 200)], 2.0, 31), fill=SKIN_SH),
        # 머리카락 조각
        p.poly(wobble([(cx - 74, 92), (cx - 52, 54), (cx + 50, 54), (cx + 74, 92),
                       (cx + 44, 80), (cx + 8, 96), (cx - 26, 78), (cx - 52, 96)], 2.2, 32),
               fill=UMBER),
    ], 7)
    # 얼굴 조각들 (따로 오려 붙인 것처럼)
    L(lambda p: [
        *[q for sgn in (-1, 1) for q in (
            p.poly(wobble(ell(cx + sgn * 28, 126, 19, 15)[::6], 1.4, 40 + sgn), fill=CREAM),
            p.poly(wobble(ell(cx + sgn * 30, 128, 8, 9)[::6], 1.0, 42 + sgn), fill=(38, 28, 20)),
            p.poly(wobble([(cx + sgn * 46, 100), (cx + sgn * 12, 94),
                           (cx + sgn * 12, 102), (cx + sgn * 46, 108)], 1.2, 44 + sgn), fill=UMBER),
        )],
        p.poly(wobble([(cx - 18, 166), (cx + 18, 166), (cx + 14, 180), (cx - 14, 180)], 1.4, 46),
               fill=OXBLOOD),
        p.poly(wobble(ell(cx - 52, 156, 16, 9)[::6], 1.2, 47), fill=BLUSH),
        p.poly(wobble(ell(cx + 52, 156, 16, 9)[::6], 1.2, 48), fill=BLUSH),
    ], 8)
    # 헬멧 (정수리에 얹은 조각)
    L(lambda p: [
        p.poly(wobble([(cx - 84, 44), (cx - 58, 8), (cx + 58, 8), (cx + 84, 44),
                       (cx + 78, 62), (cx - 78, 62)], 2.4, 50), fill=BRASS),
        p.poly(wobble([(cx - 82, 40), (cx - 56, 10), (cx - 6, 8), (cx - 14, 44)], 1.8, 51),
               fill=BRASS_LT),
        p.poly(wobble(ell(cx + 26, 36, 22, 17)[::6], 1.4, 52), fill=TEAL),
        p.poly(wobble([(cx - 84, 40), (cx - 132, 52), (cx - 136, 72), (cx - 82, 60)], 1.8, 53),
               fill=BRASS_SH),
    ], 9)

    # 합성: 레이어마다 얕은 오프셋 그림자
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for lay, depth in layers:
        off = 3 + depth // 3
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        a = lay.split()[3].filter(ImageFilter.GaussianBlur(2.2))
        sol = Image.new("RGBA", (W, H), (28, 18, 10, 0)); sol.putalpha(a.point(lambda v: int(v * 0.62)))
        sh.alpha_composite(sol, (off, off + 2))
        base = Image.alpha_composite(base, sh)
        # 오린 가장자리의 밝은 종이 단면 (위·왼쪽)
        edge = outline_alpha(lay, (246, 236, 214), 1)
        edge_m = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        edge_m.alpha_composite(edge, (-1, -1))
        base = Image.alpha_composite(base, edge_m)
        base = Image.alpha_composite(base, lay)
    # 놋쇠 핀 (관절)
    pn = Pen(W, H, ss=3)
    for (px_, py_) in ((cx - 76, 272), (cx + 76, 272), (cx - 86, 362), (cx + 86, 362),
                       (cx - 44, 474), (cx + 46, 474), (cx - 84, 444), (cx + 84, 444)):
        pn.dot(px_, py_, 9, BRASS_SH); pn.dot(px_, py_, 6, BRASS_LT); pn.dot(px_ + 1.5, py_ + 1.5, 2.5, BRASS_SH)
    base = Image.alpha_composite(base, pn.resolve())
    # 종이 결
    base = apply_mul(base, paper((W, H), 7, 0.16))
    return base, (cx, 130, 130)


# ══════════════════════════════════════════════════════════════════════
# C6. 펠트 인형 — 양모 덩어리, 보풀 가장자리, 바느질 자국
# ══════════════════════════════════════════════════════════════════════
def _stitch(p, pts, color, n=None, w=4, ln=9):
    """바느질 자국 — 점선."""
    total = 0.0
    segs = []
    for i in range(len(pts) - 1):
        d = math.dist(pts[i], pts[i + 1]); segs.append(d); total += d
    n = n or max(4, int(total / (ln * 2.1)))
    for k in range(n):
        t = (k + 0.5) / n * total
        acc = 0.0
        for i, d in enumerate(segs):
            if acc + d >= t:
                u = (t - acc) / d
                x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u
                y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u
                dx = (pts[i + 1][0] - pts[i][0]) / d; dy = (pts[i + 1][1] - pts[i][1]) / d
                p.line([(x - dx * ln / 2, y - dy * ln / 2), (x + dx * ln / 2, y + dy * ln / 2)],
                       fill=color, width=w)
                break
            acc += d


def _wool(pen_fn, W, H, seed, amount=3.0):
    p = Pen(W, H, ss=3)
    pen_fn(p)
    im = p.resolve()
    return fuzz(im, amount, seed)


def concept_c6():
    W, H = 520, 700
    cx = 260.0
    parts = []   # (이미지, 보풀량)

    def part(fn, seed, amt=3.2):
        parts.append(_wool(fn, W, H, seed, amt))

    # 공기통
    part(lambda p: p.poly(spline(ell(cx + 96, 350, 44, 82)[::6]), fill=MOSS), 1, 3.6)
    # 다리
    part(lambda p: [p.poly(spline(ell(cx - 44, 556, 40, 76)[::6]), fill=CANVASC),
                    p.poly(spline(ell(cx + 44, 556, 40, 76)[::6]), fill=SUIT)], 2)
    # 부츠
    part(lambda p: [p.poly(spline(ell(cx - 48, 638, 52, 34)[::6]), fill=UMBER),
                    p.poly(spline(ell(cx + 48, 638, 52, 34)[::6]), fill=UMBER)], 3, 2.6)
    # 몸통 — 뭉친 양모 덩어리
    part(lambda p: [
        p.poly(spline([(cx - 96, 300), (cx - 74, 250), (cx, 236), (cx + 74, 250), (cx + 96, 300),
                       (cx + 112, 410), (cx + 92, 510), (cx, 534), (cx - 92, 510), (cx - 112, 410)]),
               fill=SUIT),
        p.poly(spline([(cx - 88, 306), (cx - 40, 254), (cx + 4, 250), (cx + 10, 380),
                       (cx - 20, 500), (cx - 88, 486), (cx - 104, 390)]), fill=SUIT_LT),
    ], 4, 3.8)
    # 팔 + 벙어리장갑
    part(lambda p: [
        *[q for s in (-1, 1) for q in (
            p.poly(spline(ell(cx + s * 108, 370, 34, 78, rot=s * 0.14)[::6]),
                   fill=SUIT_SH if s > 0 else SUIT),
            p.poly(spline(ell(cx + s * 118, 452, 42, 40)[::6]), fill=CANVASC))],
    ], 5)
    # 목 실링 — 굵은 양모 도넛
    part(lambda p: [p.poly(spline(ell(cx, 252, 108, 40)[::6]), fill=BONE),
                    p.poly(spline(ell(cx, 244, 96, 30)[::6]), fill=CREAM)], 6, 4.2)
    # 머리
    part(lambda p: [
        p.poly(spline(ell(cx, 150, 98, 96)[::5]), fill=SKIN),
        p.poly(spline(ell(cx - 30, 124, 52, 54)[::6]), fill=SKIN_LT),
        p.poly(spline([(cx - 90, 108), (cx - 56, 56), (cx + 34, 48), (cx + 88, 92),
                       (cx + 70, 112), (cx + 14, 88), (cx - 42, 104)]), fill=UMBER),
    ], 7, 4.4)
    # 헬멧
    part(lambda p: [
        p.poly(spline(ell(cx + 4, 52, 100, 56)[::5]), fill=OCHRE),
        p.poly(spline(ell(cx - 26, 36, 46, 24)[::6]), fill=AMBER),
        p.poly(spline(ell(cx + 28, 52, 30, 22)[::6]), fill=TEAL),
        p.poly(spline([(cx - 98, 56), (cx - 146, 72), (cx - 150, 96), (cx - 96, 78)]), fill=RUST),
    ], 8, 3.4)

    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for im in parts:
        base = Image.alpha_composite(base, im)

    # 위에 얹는 것들: 실 눈·바느질·볼·빗금 — 보풀 없이 또렷하게
    p = Pen(W, H, ss=3)
    # 볼
    for s in (-1, 1):
        p.poly(spline(ell(cx + s * 62, 176, 26, 17)[::6]), fill=(212, 140, 128))
    # 실 눈 (매듭) + 눈썹 실 + 입 스티치
    for s in (-1, 1):
        ex = cx + s * 36
        p.dot(ex, 148, 15, (34, 26, 20))
        p.dot(ex - s * 4, 143, 4.5, CREAM)
        _stitch(p, [(ex - 22, 112), (ex + 22, 106)] if s < 0 else [(ex - 22, 106), (ex + 22, 112)],
                (46, 34, 24), n=3, w=5, ln=12)
    _stitch(p, [(cx - 22, 196), (cx - 6, 206), (cx + 10, 206), (cx + 24, 194)],
            (128, 62, 50), n=4, w=5, ln=10)
    # 몸통 솔기 + 어깨 빗금
    _stitch(p, [(cx - 96, 300), (cx - 100, 410), (cx - 88, 500)], (74, 56, 38), n=7, w=4, ln=10)
    _stitch(p, [(cx + 96, 300), (cx + 108, 410), (cx + 90, 500)], (74, 56, 38), n=7, w=4, ln=10)
    for i in range(4):
        x0 = cx - 82 + i * 14
        p.line([(x0, 306 + i * 3), (x0 + 10, 336 + i * 3)], fill=OXBLOOD, width=5)
    # 벨트 + 랜턴 (펠트 띠 + 단추)
    p.poly([(cx - 104, 452), (cx + 104, 452), (cx + 102, 484), (cx - 102, 484)], fill=UMBER)
    _stitch(p, [(cx - 100, 468), (cx + 100, 468)], (168, 140, 96), n=12, w=3, ln=9)
    p.dot(cx - 4, 468, 15, BRASS); p.dot(cx - 8, 464, 3, UMBER); p.dot(cx, 472, 3, UMBER)
    p.poly(spline(ell(cx - 86, 506, 25, 30)[::6]), fill=BRASS_SH)
    p.poly(spline(ell(cx - 86, 506, 16, 20)[::6]), fill=LAMP)
    # 헬멧 리벳 = 작은 단추
    for i in range(6):
        a = math.pi + i * math.pi / 5
        p.dot(cx + 4 + math.cos(a) * 100, 52 + math.sin(a) * 56, 7, BRASS)
    base = Image.alpha_composite(base, p.resolve())

    # 양모 질감: 미세 노이즈 + 아주 약한 부드러움
    base = grain(base, 0.13, 1.1, 21)
    base = base.filter(ImageFilter.GaussianBlur(0.35))
    base = shade_lin(base, 1.05, 0.88)
    return base, (cx, 150, 155)


# ══════════════════════════════════════════════════════════════════════
# 실행
# ══════════════════════════════════════════════════════════════════════
CONCEPTS = {
    "c1": ("동화 삽화", concept_c1, False),
    "c2": ("통통 치비", concept_c2, False),
    "c3": ("잠수복이 캐릭터다", concept_c3, False),
    "c4": ("픽셀 도트", concept_c4, True),
    "c5": ("종이 오림", concept_c5, False),
    "c6": ("펠트 인형", concept_c6, False),
}


def run(cid):
    name, fn, pixel = CONCEPTS[cid]
    print(f"[{cid}] {name}")
    fig, face = fn()
    if pixel:
        big = fig.resize((fig.size[0] * 11, fig.size[1] * 11), Image.NEAREST)
        save(cid, "full.png", card(big, 640, 820, 792))
        # 얼굴 = 머리 영역 1:1 확대
        head = fig.crop((0, 0, fig.size[0], 24))
        hs = 512 // head.size[1] + 1
        hi = head.resize((head.size[0] * hs, head.size[1] * hs), Image.NEAREST)
        bg = room_bg(512, 512, lamp_at=(256, 200), lamp_r=460)
        bg.alpha_composite(hi, ((512 - hi.size[0]) // 2, (512 - hi.size[1]) // 2))
        save(cid, "face.png", bg)
        save(cid, "t70.png", thumb(fig, 70, pixel=True))
        save(cid, "t110.png", thumb(fig, 110, pixel=True))
    else:
        bb = fig.getbbox()
        trimmed = fig.crop(bb)
        save(cid, "full.png", card(trimmed, 640, 820, 786))
        fx, fy, fr = face
        save(cid, "face.png", facecrop(fig, fx, fy, fr))
        save(cid, "t70.png", thumb(trimmed, 70))
        save(cid, "t110.png", thumb(trimmed, 110))
        trimmed_for_sil = trimmed
        save(cid, "sil70.png", silhouette(trimmed_for_sil, 70))
    if cid == "c3":
        save(cid, "moods.png", c3_moods())
    if cid == "c4":
        save(cid, "sil70.png", silhouette(fig, 70))


if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:] if a.lower() in CONCEPTS]
    for cid in (args or list(CONCEPTS)):
        run(cid)
    print("done ->", os.path.relpath(OUT, ROOT).replace("\\", "/"))
