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
    W, H = 580, 780
    p = Pen(W, H, ss=3)
    cx = 290.0

    # -- 등 공기통 --
    p.poly(spline(ell(cx + 100, 356, 40, 88)[::6]), fill=(80, 62, 40))
    p.poly(spline(ell(cx + 96, 348, 30, 74)[::6]), fill=(104, 84, 52))
    p.line(spline([(cx + 88, 288), (cx + 122, 250), (cx + 86, 212), (cx + 40, 204)],
                  closed=False), fill=(64, 48, 32), width=12)

    # -- 다리 · 무게추 부츠 (사이를 벌려 실루엣에 구멍을 낸다) --
    for sgn in (-1, 1):
        bx = cx + sgn * 44
        col = SUIT if sgn < 0 else SUIT_SH
        p.poly(spline([(bx - 28, 498), (bx + 28, 498), (bx + 32, 600), (bx + 28, 672),
                       (bx - 28, 672), (bx - 32, 600)]), fill=col)
        if sgn < 0:
            p.poly(spline([(bx - 26, 506), (bx - 2, 502), (bx - 6, 656), (bx - 24, 660)]),
                   fill=SUIT_LT)
        p.poly(spline([(bx - 40, 658), (bx + 40, 658), (bx + 46, 706), (bx + 38, 736),
                       (bx - 38, 736), (bx - 46, 706)]), fill=(52, 40, 28))
        p.poly([(bx - 42, 686), (bx + 42, 686), (bx + 43, 700), (bx - 43, 700)], fill=BRASS_SH)
    # 두 다리 사이의 어두운 틈 — 70px 에서 다리가 한 기둥으로 뭉치는 것을 막는다
    p.poly([(cx - 17, 500), (cx + 17, 500), (cx + 13, 668), (cx - 13, 668)], fill=(38, 28, 19))

    # -- 몸통 --
    body = spline([(cx - 84, 304), (cx - 66, 258), (cx, 244), (cx + 66, 258), (cx + 84, 304),
                   (cx + 94, 406), (cx + 90, 506), (cx, 528), (cx - 90, 506), (cx - 94, 406)])
    p.poly(wobble(body, 1.6, 4), fill=SUIT)
    p.poly(spline([(cx - 78, 300), (cx - 38, 254), (cx + 4, 250), (cx + 14, 320),
                   (cx - 2, 430), (cx - 42, 498), (cx - 84, 470), (cx - 90, 358)]), fill=SUIT_LT)
    p.poly(spline([(cx + 38, 266), (cx + 84, 304), (cx + 94, 406), (cx + 90, 506),
                   (cx + 38, 516), (cx + 50, 398)]), fill=SUIT_SH)
    # 앞치마 — 올리브 캔버스. 갈색 일색을 끊는 색 하나
    p.poly(wobble(spline([(cx - 58, 364), (cx + 58, 364), (cx + 68, 462), (cx + 54, 510),
                          (cx - 54, 510), (cx - 68, 462)]), 1.6, 9), fill=MOSS)
    p.poly(spline([(cx - 54, 368), (cx - 6, 366), (cx - 14, 506), (cx - 50, 506)]), fill=OLIVE)
    for i, yy in enumerate((394, 432, 470)):
        p.line(wobble([(cx - 62, yy), (cx, yy + 5), (cx + 64, yy - 2)], 1.2, 10 + i),
               fill=(58, 60, 34), width=3)
    # 적갈 멜빵
    p.poly(wobble([(cx - 62, 266), (cx - 30, 260), (cx + 54, 478), (cx + 24, 488)], 1.6, 13),
           fill=OXBLOOD)
    for i, yy in enumerate((316, 342)):
        p.line(wobble([(cx - 84, yy), (cx, yy + 7), (cx + 86, yy - 2)], 1.2, 16 + i),
               fill=SUIT_SH, width=3)

    # -- 왼 어깨 기운 자국(빗금) --
    for i in range(5):
        x0 = cx - 80 + i * 11
        p.line([(x0, 304 + i * 3), (x0 + 8, 330 + i * 3)], fill=(112, 44, 34), width=4)

    # -- 팔: 몸통 바깥으로. 왼팔은 내리고 오른팔은 갈고리를 들었다 --
    p.poly(wobble(spline([(cx - 80, 286), (cx - 118, 314), (cx - 132, 396),
                          (cx - 124, 452), (cx - 92, 450), (cx - 88, 380),
                          (cx - 78, 320)]), 1.4, 21), fill=(142, 98, 50))
    p.line(wobble([(cx - 82, 296), (cx - 90, 372), (cx - 96, 444)], 1.2, 24),
           fill=(54, 38, 24), width=6)
    p.poly([(cx - 130, 432), (cx - 92, 430), (cx - 90, 450), (cx - 128, 452)], fill=BONE)
    p.poly(spline(wobble(ell(cx - 118, 478, 40, 38)[::6], 1.6, 26)), fill=CANVASC)
    p.poly(spline(ell(cx - 124, 468, 25, 23)[::6]), fill=BONE)
    p.poly(wobble(spline([(cx + 78, 286), (cx + 122, 300), (cx + 148, 364),
                          (cx + 138, 400), (cx + 108, 386), (cx + 92, 336),
                          (cx + 74, 314)]), 1.4, 22), fill=(142, 98, 50))
    p.line(wobble([(cx + 80, 294), (cx + 104, 336), (cx + 128, 384)], 1.2, 25),
           fill=(54, 38, 24), width=6)
    p.poly([(cx + 112, 372), (cx + 142, 384), (cx + 134, 402), (cx + 106, 390)], fill=BONE)
    p.poly(spline(wobble(ell(cx + 150, 400, 40, 38)[::6], 1.6, 27)), fill=CANVASC)
    p.poly(spline(ell(cx + 144, 392, 25, 23)[::6]), fill=BONE)
    p.line([(cx + 156, 416), (cx + 170, 320)], fill=BRASS_SH, width=9)
    p.line(ell(cx + 160, 312, 17, 17, a0=2.2, a1=5.6)[::2], fill=BRASS, width=9)

    # -- 벨트 + 랜턴 --
    p.poly([(cx - 94, 470), (cx + 94, 470), (cx + 92, 500), (cx - 92, 500)], fill=(58, 44, 30))
    p.poly([(cx - 22, 464), (cx + 18, 464), (cx + 18, 506), (cx - 22, 506)], fill=BRASS)
    p.poly(spline(ell(cx - 84, 520, 25, 31)[::6]), fill=BRASS_SH)
    p.poly(spline(ell(cx - 84, 520, 16, 21)[::6]), fill=LAMP)

    # -- 목 실링: 솜 덩어리 4겹 --
    for i, (ry, col) in enumerate(((30, (132, 92, 48)), (25, CANVASC), (21, SUIT_LT), (15, BONE))):
        p.poly(spline(wobble(ell(cx, 260 - i * 12, 90 - i * 8, ry)[::5], 1.8, 30 + i)), fill=col)

    # -- 머리 --
    hx, hy = cx - 2, 164
    p.poly(spline(ell(hx - 72, hy + 18, 12, 17)[::6]), fill=SKIN_SH)
    p.poly(spline(ell(hx + 72, hy + 18, 12, 17)[::6]), fill=SKIN_SH)
    p.poly(spline(wobble(ell(hx, hy, 72, 86)[::5], 2.0, 41)), fill=SKIN)
    p.poly(spline(ell(hx + 30, hy + 12, 44, 72)[::6]), fill=SKIN_SH)
    p.poly(spline(ell(hx - 24, hy - 16, 40, 46)[::6]), fill=SKIN_LT)
    p.poly(spline([(hx - 70, hy - 20), (hx - 64, hy - 58), (hx - 12, hy - 74),
                   (hx + 52, hy - 64), (hx + 70, hy - 24), (hx + 50, hy - 16),
                   (hx + 24, hy - 44), (hx - 6, hy - 34), (hx - 34, hy - 46),
                   (hx - 52, hy - 10)]), fill=(58, 42, 30))

    # -- 얼굴을 전부 그린다 --
    for sgn in (-1, 1):
        ex = hx + sgn * 29
        p.poly(spline(ell(ex, hy + 16, 19, 21)[::6]), fill=CREAM)
        p.poly(spline(ell(ex + sgn * 2, hy + 19, 12, 14)[::6]), fill=(42, 30, 22))
        p.dot(ex - sgn * 3, hy + 12, 4.5, CREAM)
        p.line([(ex - 18, hy - 22), (ex - 2, hy - 30), (ex + 16, hy - 26)] if sgn < 0
               else [(ex - 16, hy - 26), (ex + 2, hy - 30), (ex + 18, hy - 22)],
               fill=(78, 56, 38), width=5)
    p.line([(hx - 3, hy + 32), (hx + 3, hy + 43), (hx - 6, hy + 45)], fill=SKIN_SH, width=4)
    p.line(ell(hx, hy + 48, 19, 15, a0=0.35, a1=2.79)[::2], fill=(128, 60, 48), width=5)
    for sgn in (-1, 1):
        lay = Pen(W, H, ss=3)
        lay.poly(spline(ell(hx + sgn * 50, hy + 42, 22, 14)[::6]), fill=BLUSH + (135,))
        p.img.alpha_composite(lay.img)
    rng = random.Random(9)
    for _ in range(11):
        a = rng.uniform(0, math.tau); r = rng.uniform(18, 52)
        p.dot(hx + math.cos(a) * r, hy + 34 + math.sin(a) * 8, 2.6, (188, 128, 90))

    # -- 헬멧: 얼굴을 덮지 않고 정수리에 얹혀 있다 --
    g = helmet_geo(hx + 6, hy - 106, 66)
    p.poly(spline(wobble(g["rim"][::6], 1.4, 60)), fill=(128, 94, 28))
    p.poly(spline(wobble(g["shell"][::5], 1.6, 61)), fill=BRASS)
    p.poly(spline(g["crest"][::6]), fill=BRASS_LT)
    p.poly(spline(g["port_ring"][::6]), fill=BRASS_SH)
    p.poly(spline(g["port"][::6]), fill=TEAL)
    p.poly(spline(ell(hx + 18, hy - 114, 10, 7)[::6]), fill=(118, 166, 164))
    p.line(g["pipe"], fill=(128, 94, 28), width=13)
    p.poly(spline(ell(g["pipe"][-1][0], g["pipe"][-1][1], 11, 11)[::8]), fill=(70, 52, 34))
    for bx_, by_ in g["bolts"]:
        p.dot(bx_, by_, 4.5, BRASS_LT)

    fig = p.resolve()
    ol = outline_alpha(fig, (48, 33, 22), 2, blur=1.2)
    out = Image.alpha_composite(ol, fig)
    out = rim_and_core(out, (255, 224, 176), 0.42, 4, 0.62, 10, 2.4)
    out = grain(out, 0.18, 2.0, 5)
    out = out.filter(ImageFilter.SMOOTH)
    glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - 240, 20, cx + 240, 560], fill=(222, 154, 66, 62))
    glow = glow.filter(ImageFilter.GaussianBlur(64))
    out = Image.alpha_composite(glow, out)
    return out, (hx, hy, 148)


def concept_c2():
    """2.4등신. 평면 채색 + 굵은 외곽선. 질감 없음 — 이것이 C1/C6 과 갈리는 지점."""
    W, H = 560, 700
    p = Pen(W, H, ss=3)
    cx = 280.0
    hy = 236.0
    HR = 142.0

    # 공기통 (어깨 위로 살짝)
    p.poly(spline(ell(cx + 92, 452, 40, 56)[::6]), fill=MOSS)

    # 다리 — 짧고 뭉툭, 사이를 벌린다
    for sgn in (-1, 1):
        bx = cx + sgn * 46
        p.poly(spline(ell(bx, 578, 34, 48)[::6]), fill=SUIT if sgn < 0 else SUIT_SH)
        p.poly(spline(ell(bx, 626, 44, 28)[::6]), fill=(52, 40, 28))
        p.poly([(bx - 42, 620), (bx + 42, 620), (bx + 42, 630), (bx - 42, 630)], fill=BRASS)

    # 몸통
    p.poly(spline([(cx - 88, 428), (cx - 72, 386), (cx, 372), (cx + 72, 386), (cx + 88, 428),
                   (cx + 94, 516), (cx, 556), (cx - 94, 516)]), fill=SUIT)
    p.poly(spline([(cx - 88, 470), (cx, 452), (cx + 92, 470), (cx + 94, 516),
                   (cx, 556), (cx - 94, 516)]), fill=SUIT_SH)
    # 올리브 앞치마 조각 — 색 하나 더
    p.poly(spline([(cx - 46, 430), (cx + 46, 430), (cx + 52, 520), (cx - 52, 520)]), fill=MOSS)
    # 어깨 기운 자국
    for i in range(4):
        x0 = cx - 78 + i * 12
        p.line([(x0, 402 + i * 2), (x0 + 8, 424 + i * 2)], fill=OXBLOOD, width=5)
    # 벨트 + 랜턴
    p.poly([(cx - 92, 496), (cx + 94, 496), (cx + 92, 524), (cx - 90, 524)], fill=(48, 36, 24))
    p.poly(spline(ell(cx - 72, 542, 21, 26)[::6]), fill=BRASS)
    p.poly(spline(ell(cx - 72, 542, 13, 17)[::6]), fill=LAMP)

    # 팔 + 큰 벙어리 장갑 — 몸통 바깥으로
    for sgn in (-1, 1):
        sx = cx + sgn * 92
        p.poly(spline(ell(sx + sgn * 12, 452, 27, 46, rot=sgn * 0.22)[::6]),
               fill=SUIT_LT if sgn < 0 else (150, 104, 54))
        p.poly(spline(ell(sx + sgn * 24, 504, 37, 35)[::6]), fill=CANVASC)

    # 목 실링
    p.poly(spline(ell(cx, 374, 86, 30)[::6]), fill=SUIT_LT)
    p.poly(spline(ell(cx, 382, 80, 22)[::6]), fill=CANVASC)

    # 머리
    p.poly(spline(ell(cx, hy, HR, HR * 0.96)[::5]), fill=SKIN)
    p.poly(spline(ell(cx, hy + 50, HR * 0.93, HR * 0.52)[::6]), fill=SKIN_SH)
    p.poly(spline(ell(cx, hy - 4, HR * 0.95, HR * 0.80)[::6]), fill=SKIN)
    # 앞머리
    p.poly(spline([(cx - 134, hy - 34), (cx - 102, hy - 118), (cx - 10, hy - 144),
                   (cx + 104, hy - 114), (cx + 132, hy - 30), (cx + 92, hy - 58),
                   (cx + 36, hy - 88), (cx - 32, hy - 68), (cx - 88, hy - 44)]),
           fill=(58, 42, 30))
    # 볼 홍조 (눈보다 먼저 — 눈을 덮지 않게)
    for sgn in (-1, 1):
        lay = Pen(W, H, ss=3)
        lay.poly(spline(ell(cx + sgn * 94, hy + 58, 28, 18)[::6]), fill=BLUSH + (165,))
        p.img.alpha_composite(lay.img)
    # 큰 눈 + 하이라이트 둘
    for sgn in (-1, 1):
        ex = cx + sgn * 52
        p.poly(spline(ell(ex, hy + 18, 32, 40)[::6]), fill=(30, 22, 16))
        p.poly(spline(ell(ex, hy + 26, 23, 27)[::6]), fill=(84, 54, 36))
        p.dot(ex - sgn * 10, hy + 2, 12, CREAM)
        p.dot(ex + sgn * 12, hy + 34, 5.5, CREAM)
        p.line([(ex - 28, hy - 36), (ex + 28, hy - 44)] if sgn < 0
               else [(ex - 28, hy - 44), (ex + 28, hy - 36)], fill=(58, 42, 30), width=9)
    # 작은 입
    p.line(ell(cx, hy + 72, 15, 12, a0=0.4, a1=2.74)[::2], fill=(124, 58, 46), width=7)

    # 헬멧 — 뒤로 젖혀 정수리에 얹음
    g = helmet_geo(cx + 6, hy - 138, 96)
    p.poly(spline(g["rim"][::6]), fill=(128, 94, 28))
    p.poly(spline(g["shell"][::5]), fill=BRASS)
    p.poly(spline(g["crest"][::6]), fill=BRASS_LT)
    p.poly(spline(g["port_ring"][::6]), fill=BRASS_SH)
    p.poly(spline(g["port"][::6]), fill=TEAL)
    p.poly(spline(ell(cx + 22, hy - 150, 15, 10)[::6]), fill=(118, 166, 164))
    p.line(g["pipe"], fill=(128, 94, 28), width=18)
    p.poly(spline(ell(g["pipe"][-1][0], g["pipe"][-1][1], 15, 15)[::8]), fill=(70, 52, 34))
    for bx_, by_ in g["bolts"]:
        p.dot(bx_, by_, 6, BRASS_LT)

    fig = p.resolve()
    ol = outline_alpha(fig, (28, 20, 14), 4, blur=0.3)      # 굵고 또렷한 외곽선
    out = Image.alpha_composite(ol, fig)
    return out, (cx, hy, 200)


# ══════════════════════════════════════════════════════════════════════
# C3. 잠수복이 캐릭터다 — 체형 없음, 헬멧 창 불빛이 표정
# ══════════════════════════════════════════════════════════════════════
def _c3_helmet(p, cx, cy, R, mood="calm"):
    """헬멧 하나. mood 가 창 불빛의 밝기·색·기울기를 정한다 — 이것이 이 컨셉의 표정이다."""
    tilt = {"calm": 0.0, "alarm": -0.20, "tired": 0.24}[mood]
    glow = {"calm": (244, 188, 96), "alarm": (255, 246, 214), "tired": (176, 108, 44)}[mood]
    core = {"calm": (255, 236, 190), "alarm": (255, 255, 250), "tired": (214, 150, 70)}[mood]
    gr = {"calm": 0.94, "alarm": 1.00, "tired": 0.62}[mood]
    c, s_ = math.cos(tilt), math.sin(tilt)

    def T(x, y):
        return (cx + x * c - y * s_, cy + x * s_ + y * c)

    def TT(pts):
        return [T(x - cx, y - cy) for x, y in pts]

    g = helmet_geo(cx, cy, R)
    p.poly(TT(g["rim"]), fill=(112, 82, 24))
    p.poly(TT(g["shell"]), fill=BRASS)
    p.poly(TT(g["crest"]), fill=BRASS_LT)
    p.poly(TT(ell(cx + R * 0.52, cy + R * 0.30, R * 0.42, R * 0.52)), fill=(146, 108, 34))
    # 창 — 정면에 크게 (이 컨셉에서는 창이 얼굴이다)
    pr = R * 0.52
    p.poly(TT(ell(cx, cy + R * 0.04, pr + R * 0.10, pr + R * 0.10)), fill=(100, 72, 20))
    p.poly(TT(ell(cx, cy + R * 0.04, pr, pr)), fill=(34, 26, 18))
    p.poly(TT(ell(cx, cy + R * 0.06, pr * 0.94, pr * 0.94)), fill=glow + (int(252 * gr),))
    p.poly(TT(ell(cx - pr * 0.22, cy - pr * 0.12, pr * 0.52, pr * 0.46)), fill=core + (int(250 * gr),))
    # 불빛 속에 잠긴 사람의 흐릿한 그림자 — 안에 사람이 있다는 유일한 단서
    p.poly(TT(ell(cx + pr * 0.18, cy + pr * 0.34, pr * 0.46, pr * 0.34)),
           fill=(150, 96, 40, int(150 * gr)))
    # 유리의 반사 두 줄 (D4)
    p.line([T(-pr * 0.70, -pr * 0.30), T(-pr * 0.18, -pr * 0.70)],
           fill=(236, 244, 240), width=R * 0.085)
    p.line([T(-pr * 0.34, 0.0), T(-pr * 0.06, -pr * 0.32)], fill=(212, 226, 224), width=R * 0.05)
    # 옆 작은 창 · 리벳 · 배기관(부리)
    p.poly(TT(ell(cx - R * 0.86, cy + R * 0.06, R * 0.14, R * 0.17)), fill=TEAL)
    for i in range(14):
        ang = i * math.tau / 14
        p.dot(*T(math.cos(ang) * R * 0.86, math.sin(ang) * R * 0.80), R * 0.055, (112, 82, 24))
    p.line([T(R * 0.66, R * 0.36), T(R * 1.26, R * 0.58), T(R * 1.44, R * 0.92)],
           fill=(112, 82, 24), width=R * 0.20)
    p.poly(TT(ell(cx + R * 1.42, cy + R * 0.94, R * 0.16, R * 0.16)), fill=(56, 42, 28))


def concept_c3():
    """체형이 없다. 누빈 자루 하나 + 둥근 헬멧. 실루엣만으로 존재한다."""
    W, H = 560, 740
    p = Pen(W, H, ss=3)
    cx = 280.0

    # 등 공기통 + 호스
    p.poly(spline(ell(cx + 108, 340, 44, 88)[::6]), fill=(74, 58, 38))
    p.line(spline([(cx + 100, 268), (cx + 136, 240), (cx + 116, 206), (cx + 82, 200)],
                  closed=False), fill=(56, 42, 28), width=15)

    # 한 덩어리 자루 — 어깨에서 밑단으로 넓어진다
    sack = spline([(cx - 88, 258), (cx - 62, 222), (cx + 62, 222), (cx + 88, 258),
                   (cx + 122, 398), (cx + 150, 572), (cx + 144, 618),
                   (cx - 144, 618), (cx - 150, 572), (cx - 122, 398)])
    p.poly(wobble(sack, 1.4, 7), fill=SUIT)
    p.poly(spline([(cx + 28, 230), (cx + 88, 258), (cx + 122, 398), (cx + 150, 572),
                   (cx + 144, 618), (cx + 42, 620), (cx + 58, 418)]), fill=SUIT_SH)
    p.poly(spline([(cx - 80, 258), (cx - 38, 226), (cx - 8, 240), (cx - 20, 418),
                   (cx - 56, 598), (cx - 116, 594), (cx - 114, 398)]), fill=SUIT_LT)
    # 누빔 가로줄
    for i in range(9):
        yy = 282 + i * 38
        wdt = 94 + i * 7
        p.line(wobble([(cx - wdt, yy), (cx, yy + 8), (cx + wdt, yy - 2)], 1.4, 40 + i),
               fill=(96, 64, 30), width=4)
    # 밑단 테 + 무게추 부츠
    p.poly(spline([(cx - 148, 598), (cx + 148, 598), (cx + 144, 634), (cx - 144, 634)]),
           fill=(54, 40, 26))
    for sgn in (-1, 1):
        p.poly(spline(ell(cx + sgn * 68, 660, 58, 32)[::6]), fill=(44, 33, 22))
        p.poly([(cx + sgn * 68 - 56, 650), (cx + sgn * 68 + 56, 650),
                (cx + sgn * 68 + 54, 664), (cx + sgn * 68 - 54, 664)], fill=BRASS)

    # 어깨 기운 자국
    for i in range(5):
        x0 = cx - 100 + i * 13
        p.line([(x0, 292 + i * 3), (x0 + 9, 320 + i * 3)], fill=(120, 48, 36), width=5)

    # 팔 — 자루에서 자란 두 뭉치. 손은 큰 장갑 하나
    for sgn in (-1, 1):
        p.poly(spline([(cx + sgn * 88, 262), (cx + sgn * 134, 300), (cx + sgn * 142, 390),
                       (cx + sgn * 118, 440), (cx + sgn * 90, 414), (cx + sgn * 84, 324)]),
               fill=SUIT_LT if sgn < 0 else (146, 100, 50))
        p.line([(cx + sgn * 92, 276), (cx + sgn * 98, 348), (cx + sgn * 104, 420)],
               fill=(54, 38, 24), width=6)
    # 왼손의 그물 자루 (장갑보다 뒤)
    p.poly(spline([(cx - 172, 462), (cx - 132, 470), (cx - 124, 552), (cx - 162, 574),
                   (cx - 194, 540)]), fill=MOSS)
    for i in range(4):
        p.line([(cx - 188 + i * 17, 476), (cx - 176 + i * 17, 566)], fill=OLIVE, width=3)
    for sgn in (-1, 1):
        p.poly(spline(ell(cx + sgn * 124, 458, 43, 41)[::6]), fill=CANVASC)
        p.poly(spline(ell(cx + sgn * 130, 448, 27, 25)[::6]), fill=BONE)

    # 벨트 랜턴
    p.poly(spline(ell(cx - 128, 386, 27, 33)[::6]), fill=(112, 82, 24))
    p.poly(spline(ell(cx - 128, 386, 18, 23)[::6]), fill=LAMP)

    # 헬멧
    _c3_helmet(p, cx, 168, 106, "calm")

    fig = p.resolve()
    ol = outline_alpha(fig, (26, 19, 13), 3, blur=0.5)
    out = Image.alpha_composite(ol, fig)
    out = rim_and_core(out, (255, 222, 172), 0.30, 4, 0.66, 11, 2.6)
    out = grain(out, 0.09, 2.8, 12)
    # 헬멧 불빛이 어깨와 물에 번진다 (D3 빛은 전부 근거가 있다)
    sp = Image.new("RGBA", out.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(sp)
    dd.ellipse([cx - 170, 60, cx + 170, 400], fill=(248, 184, 92, 58))
    dd.ellipse([cx - 92, 104, cx + 92, 246], fill=(255, 214, 138, 92))
    sp = sp.filter(ImageFilter.GaussianBlur(30))
    out = Image.alpha_composite(out, sp)
    return out, (cx, 168, 158)


def c3_moods():
    """헬멧 세 표정 — 이 컨셉이 표정을 무엇으로 말하는지 보여주는 판."""
    W, H = 540, 210
    img = room_bg(W, H, lamp_at=(W * 0.5, H * 0.4), lamp_r=W * 0.8)
    for i, m in enumerate(("calm", "alarm", "tired")):
        p = Pen(W, H, ss=3)
        _c3_helmet(p, 96 + i * 176, 100, 64, m)
        f = p.resolve()
        img = Image.alpha_composite(img, Image.alpha_composite(outline_alpha(f, (26, 19, 13), 2), f))
        sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        al = {"calm": 70, "alarm": 110, "tired": 34}[m]
        ImageDraw.Draw(sp).ellipse([96 + i * 176 - 96, 4, 96 + i * 176 + 96, 196],
                                   fill=(250, 196, 110, al))
        img = Image.alpha_composite(img, sp.filter(ImageFilter.GaussianBlur(22)))
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
    """38x56 그리드에 직접 찍는다. 팔레트 14색. 게임 크기에서 1:1 로 쓰인다."""
    g = PixGrid(38, 56)
    cx = 19

    # 머리
    g.ell(cx - 1, 24, 8, 9, "k")
    g.rect(cx + 4, 18, cx + 6, 31, "K")
    # 머리카락 — 헬멧 밑으로 삐져나온 앞머리
    g.rect(cx - 8, 16, cx + 6, 18, "d")
    g.px(cx - 8, 19, "d"); g.px(cx - 7, 19, "d"); g.px(cx + 5, 19, "d"); g.px(cx + 6, 19, "d")
    g.px(cx - 4, 19, "d"); g.px(cx + 1, 19, "d")
    # 얼굴 — 이 크기에서 읽히는 최소 단위
    for sgn in (-1, 1):
        ex = cx - 1 + sgn * 4
        g.rect(ex - 1, 23, ex, 24, "#")
        g.px(ex - 1, 23, "c")
        g.rect(ex - 2, 21, ex + 1, 21, "d")
    g.px(cx - 1, 26, "K")
    g.rect(cx - 2, 28, cx, 28, "o")
    g.px(cx - 7, 27, "o"); g.px(cx + 5, 27, "o")

    # 헬멧 — 머리 위에 얹혀 있다. 머리를 그린 뒤에 얹어야 떠 보이지 않는다
    g.ell(cx, 11, 7, 6, "b")
    g.rect(cx - 7, 11, cx + 7, 16, "b")           # 돔 아랫부분(정수리에 닿는 면)
    g.rect(cx - 7, 15, cx + 7, 16, "s")           # 아래 테
    g.ell(cx - 3, 8, 3, 2, "B")                   # 정수리 하이라이트
    g.ell(cx + 3, 11, 2, 2, "t")                  # 창
    g.px(cx + 2, 10, "c")
    g.rect(cx - 12, 13, cx - 7, 14, "b")          # 배기관(부리)
    g.rect(cx - 14, 14, cx - 13, 15, "d")
    for x in range(cx - 5, cx + 6, 4):
        g.px(x, 14, "s")

    # 목 실링 3겹
    g.rect(cx - 9, 32, cx + 8, 32, "S")
    g.rect(cx - 10, 33, cx + 9, 33, "L")
    g.rect(cx - 9, 34, cx + 8, 34, "s")

    # 공기통 (오른 어깨 뒤로 삐죽)
    g.rect(cx + 9, 33, cx + 11, 40, "v")

    # 몸통
    g.rect(cx - 9, 35, cx + 8, 48, "S")
    g.rect(cx - 9, 35, cx - 3, 48, "L")
    g.rect(cx + 5, 35, cx + 8, 48, "s")
    g.rect(cx - 5, 40, cx + 4, 47, "v")           # 올리브 앞치마
    for y in (38, 43):
        g.rect(cx - 9, y, cx + 8, y, "s")
    # 어깨 기운 자국
    for i in range(3):
        g.px(cx - 8 + i * 2, 37 + i, "o"); g.px(cx - 7 + i * 2, 38 + i, "o")
    # 벨트 + 랜턴
    g.rect(cx - 9, 45, cx + 8, 46, "d")
    g.rect(cx - 1, 45, cx + 1, 46, "b")
    g.rect(cx - 12, 47, cx - 10, 50, "b")
    g.rect(cx - 11, 48, cx - 11, 49, "l")

    # 팔 + 큰 장갑
    g.rect(cx - 12, 36, cx - 10, 43, "L")
    g.rect(cx + 9, 36, cx + 11, 43, "s")
    g.rect(cx - 13, 44, cx - 9, 47, "c")
    g.rect(cx + 8, 44, cx + 12, 47, "c")

    # 다리 (가운데를 비운다)
    g.rect(cx - 7, 49, cx - 2, 52, "S")
    g.rect(cx + 1, 49, cx + 6, 52, "s")
    # 무게추 부츠
    g.rect(cx - 9, 53, cx - 1, 55, "d")
    g.rect(cx + 0, 53, cx + 8, 55, "d")
    g.rect(cx - 9, 54, cx - 1, 54, "b")
    g.rect(cx + 0, 54, cx + 8, 54, "b")

    g.outline("#")
    im = g.image()
    return im.crop(im.getbbox()), None


# ══════════════════════════════════════════════════════════════════════
# C5. 종이 오림 — 납작한 색 면 + 종이 결 + 얕은 그림자 + 놋쇠 핀
# ══════════════════════════════════════════════════════════════════════
def concept_c5():
    """판지를 오려 겹친다. 납작한 면 + 종이 결 + 얕은 그림자 + 놋쇠 핀."""
    W, H = 540, 740
    cx = 270.0
    layers = []

    def L(fn, depth):
        pp = Pen(W, H, ss=3)
        fn(pp)
        layers.append((pp.resolve(), depth))

    # 공기통
    L(lambda p: [
        p.poly(wobble([(cx + 66, 274), (cx + 128, 288), (cx + 134, 400), (cx + 70, 392)], 2.2, 1),
               fill=MOSS),
        p.poly([(cx + 80, 296), (cx + 122, 304), (cx + 124, 324), (cx + 82, 316)], fill=OLIVE),
    ], 1)
    # 다리
    L(lambda p: [
        p.poly(wobble([(cx - 72, 476), (cx - 16, 476), (cx - 18, 640), (cx - 70, 640)], 2.0, 2),
               fill=CANVASC),
        p.poly(wobble([(cx + 16, 476), (cx + 72, 476), (cx + 74, 640), (cx + 20, 640)], 2.0, 3),
               fill=SUIT_SH),
    ], 1)
    # 부츠
    L(lambda p: [
        p.poly(wobble([(cx - 84, 630), (cx - 8, 630), (cx - 6, 686), (cx - 90, 686)], 2.0, 4),
               fill=(52, 40, 28)),
        p.poly(wobble([(cx + 10, 630), (cx + 86, 630), (cx + 92, 686), (cx + 8, 686)], 2.0, 5),
               fill=(52, 40, 28)),
        p.poly([(cx - 90, 660), (cx - 6, 660), (cx - 6, 672), (cx - 90, 672)], fill=BRASS),
        p.poly([(cx + 8, 660), (cx + 92, 660), (cx + 92, 672), (cx + 8, 672)], fill=BRASS),
    ], 2)
    # 몸통
    L(lambda p: [
        p.poly(wobble([(cx - 82, 266), (cx + 82, 266), (cx + 104, 486), (cx - 104, 486)], 2.4, 6),
               fill=SUIT),
        p.poly(wobble([(cx - 82, 266), (cx - 14, 266), (cx - 28, 486), (cx - 104, 486)], 2.2, 7),
               fill=SUIT_LT),
        p.poly(wobble([(cx - 54, 372), (cx + 54, 372), (cx + 62, 480), (cx - 62, 480)], 2.0, 70),
               fill=MOSS),
        p.poly(wobble([(cx - 76, 300), (cx - 22, 306), (cx - 28, 360), (cx - 80, 354)], 1.8, 8),
               fill=RUST),
        *[p.line([(cx - 72 + i * 12, 306), (cx - 64 + i * 12, 356)], fill=OXBLOOD, width=4)
          for i in range(5)],
    ], 3)
    # 벨트 + 랜턴
    L(lambda p: [
        p.poly([(cx - 102, 446), (cx + 102, 446), (cx + 102, 476), (cx - 102, 476)],
               fill=(52, 40, 28)),
        p.poly([(cx - 20, 440), (cx + 18, 440), (cx + 18, 482), (cx - 20, 482)], fill=BRASS),
        p.poly([(cx - 112, 482), (cx - 66, 482), (cx - 70, 534), (cx - 108, 534)], fill=(112, 82, 24)),
        p.poly([(cx - 104, 492), (cx - 74, 492), (cx - 77, 524), (cx - 101, 524)], fill=LAMP),
    ], 4)
    # 팔 (핀으로 연결된 세 마디) — 몸통 바깥으로
    for sgn in (-1, 1):
        L(lambda p, s=sgn: [
            p.poly(wobble([(cx + s * 72, 272), (cx + s * 130, 288), (cx + s * 140, 374),
                           (cx + s * 86, 366)], 2.0, 10 + s),
                   fill=(150, 104, 54) if s > 0 else SUIT),
            p.poly(wobble([(cx + s * 88, 360), (cx + s * 140, 368), (cx + s * 144, 446),
                           (cx + s * 94, 442)], 2.0, 12 + s), fill=CANVASC),
            p.poly(wobble([(cx + s * 86, 440), (cx + s * 150, 444), (cx + s * 146, 500),
                           (cx + s * 88, 496)], 2.0, 14 + s), fill=BONE),
        ], 5)
    # 목 실링 (오려 겹친 띠 3장)
    L(lambda p: [
        p.poly(wobble([(cx - 94, 242), (cx + 94, 242), (cx + 86, 272), (cx - 86, 272)], 2.2, 20),
               fill=SUIT_LT),
        p.poly(wobble([(cx - 84, 226), (cx + 84, 226), (cx + 80, 248), (cx - 80, 248)], 2.0, 21),
               fill=CANVASC),
        p.poly(wobble([(cx - 74, 212), (cx + 74, 212), (cx + 72, 230), (cx - 72, 230)], 1.8, 22),
               fill=BONE),
    ], 6)
    # 머리
    L(lambda p: [
        p.poly(wobble([(cx - 70, 104), (cx - 52, 62), (cx - 10, 50), (cx + 40, 56),
                       (cx + 70, 96), (cx + 64, 182), (cx + 30, 214), (cx - 26, 214),
                       (cx - 64, 184)], 2.4, 30), fill=SKIN),
        p.poly(wobble([(cx + 20, 56), (cx + 40, 56), (cx + 70, 96), (cx + 64, 182),
                       (cx + 30, 214), (cx + 14, 202)], 2.0, 31), fill=SKIN_SH),
        p.poly(wobble([(cx - 72, 100), (cx - 54, 52), (cx + 44, 48), (cx + 72, 92),
                       (cx + 44, 82), (cx + 6, 96), (cx - 26, 78), (cx - 50, 98)], 2.2, 32),
               fill=(58, 42, 30)),
    ], 7)
    # 얼굴 조각들 — 따로 오려 붙인 것처럼. 순한 인상으로
    L(lambda p: [
        *[q for sgn in (-1, 1) for q in (
            p.poly(wobble(ell(cx + sgn * 27, 130, 18, 16)[::6], 1.4, 40 + sgn), fill=CREAM),
            p.poly(wobble(ell(cx + sgn * 28, 132, 11, 12)[::6], 1.0, 42 + sgn), fill=(44, 32, 24)),
            p.dot(cx + sgn * 28 - sgn * 3, 127, 3.4, CREAM),
            p.poly(wobble([(cx + sgn * 42, 111), (cx + sgn * 15, 106),
                           (cx + sgn * 15, 111), (cx + sgn * 42, 116)], 1.2, 44 + sgn),
                   fill=(78, 56, 38)),
        )],
        p.poly(wobble([(cx - 16, 172), (cx + 16, 172), (cx + 12, 180), (cx - 12, 180)], 1.4, 46),
               fill=(132, 62, 50)),
        p.poly(wobble(ell(cx - 50, 160, 15, 9)[::6], 1.2, 47), fill=BLUSH),
        p.poly(wobble(ell(cx + 50, 160, 15, 9)[::6], 1.2, 48), fill=BLUSH),
    ], 8)
    # 헬멧 — 정수리에 얹은 오린 돔
    L(lambda p: [
        p.poly(wobble([(cx - 78, 52), (cx - 66, 20), (cx - 30, 2), (cx + 22, 2),
                       (cx + 60, 20), (cx + 76, 52), (cx + 70, 68), (cx - 72, 68)], 2.4, 50),
               fill=BRASS),
        p.poly(wobble([(cx - 74, 48), (cx - 60, 18), (cx - 22, 4), (cx - 10, 40),
                       (cx - 30, 56)], 1.8, 51), fill=BRASS_LT),
        p.poly(wobble(ell(cx + 28, 38, 21, 19)[::6], 1.4, 52), fill=TEAL),
        p.poly(wobble([(cx - 78, 44), (cx - 126, 56), (cx - 132, 76), (cx - 76, 62)], 1.8, 53),
               fill=(128, 94, 28)),
    ], 9)

    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for lay, depth in layers:
        off = 3 + depth // 3
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        al = lay.split()[3].filter(ImageFilter.GaussianBlur(2.2))
        sol = Image.new("RGBA", (W, H), (26, 16, 9, 0))
        sol.putalpha(al.point(lambda v: int(v * 0.66)))
        sh.alpha_composite(sol, (off, off + 2))
        base = Image.alpha_composite(base, sh)
        edge = outline_alpha(lay, (248, 240, 220), 1)
        em = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        em.alpha_composite(edge, (-1, -1))
        base = Image.alpha_composite(base, em)
        base = Image.alpha_composite(base, lay)
    # 놋쇠 핀 (관절)
    pn = Pen(W, H, ss=3)
    for (qx, qy) in ((cx - 76, 278), (cx + 76, 278), (cx - 92, 366), (cx + 92, 366),
                     (cx - 44, 480), (cx + 46, 480), (cx - 90, 448), (cx + 90, 448)):
        pn.dot(qx, qy, 9, (112, 82, 24)); pn.dot(qx, qy, 6, BRASS_LT)
        pn.dot(qx + 1.5, qy + 1.5, 2.5, (112, 82, 24))
    base = Image.alpha_composite(base, pn.resolve())
    base = apply_mul(base, paper((W, H), 7, 0.17))
    return base, (cx, 132, 132)


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
    """양모를 뭉쳐 만든 인형. 보풀 · 실밥 · 바느질 자국. 좌우가 조금씩 어긋난다(손으로 만든 것)."""
    W, H = 540, 720
    cx = 270.0
    WOOL = (178, 132, 76); WOOL_L = (206, 166, 108); WOOL_D = (128, 92, 50)
    parts = []

    def part(fn, seed, amt=4.5):
        pp = Pen(W, H, ss=3)
        fn(pp)
        parts.append(fuzz(pp.resolve(), amt, seed, 0.72))

    # 공기통
    part(lambda p: p.poly(spline(ell(cx + 98, 356, 42, 80)[::6]), fill=MOSS), 1, 5.0)
    # 다리 — 둘로 확실히 갈라 놓는다
    part(lambda p: [p.poly(spline(ell(cx - 46, 566, 38, 74)[::6]), fill=WOOL_L),
                    p.poly(spline(ell(cx + 48, 570, 38, 74)[::6]), fill=WOOL_D)], 2, 4.6)
    # 부츠
    part(lambda p: [p.poly(spline(ell(cx - 50, 648, 50, 32)[::6]), fill=(58, 44, 30)),
                    p.poly(spline(ell(cx + 52, 652, 50, 32)[::6]), fill=(58, 44, 30))], 3, 3.4)
    # 몸통 — 뭉친 양모 덩어리(살짝 기울어져 있다)
    part(lambda p: [
        p.poly(spline([(cx - 92, 302), (cx - 70, 252), (cx + 4, 238), (cx + 76, 254),
                       (cx + 94, 304), (cx + 106, 410), (cx + 86, 508), (cx - 4, 530),
                       (cx - 94, 506), (cx - 108, 408)]), fill=WOOL),
        p.poly(spline([(cx - 84, 306), (cx - 38, 256), (cx + 6, 252), (cx + 12, 380),
                       (cx - 18, 496), (cx - 84, 482), (cx - 100, 388)]), fill=WOOL_L),
        p.poly(spline([(cx + 44, 262), (cx + 94, 304), (cx + 106, 410), (cx + 86, 508),
                       (cx + 36, 516), (cx + 52, 396)]), fill=WOOL_D),
        p.poly(spline([(cx - 52, 366), (cx + 52, 366), (cx + 62, 466), (cx - 60, 470)]),
               fill=MOSS),
    ], 4, 5.2)
    # 팔 + 벙어리장갑
    part(lambda p: [
        *[q for s_ in (-1, 1) for q in (
            p.poly(spline(ell(cx + s_ * 108, 372, 33, 76, rot=s_ * 0.16)[::6]),
                   fill=WOOL_D if s_ > 0 else WOOL_L),
            p.poly(spline(ell(cx + s_ * 118, 452, 41, 39)[::6]), fill=CANVASC))],
    ], 5, 4.8)
    # 목 실링 — 굵은 양모 도넛(따뜻한 크림, 흰색이 아니다)
    part(lambda p: [p.poly(spline(ell(cx, 252, 104, 38)[::6]), fill=(198, 168, 118)),
                    p.poly(spline(ell(cx + 2, 244, 92, 28)[::6]), fill=BONE)], 6, 5.4)
    # 머리
    part(lambda p: [
        p.poly(spline(ell(cx, 152, 96, 94)[::5]), fill=SKIN),
        p.poly(spline(ell(cx - 28, 126, 50, 52)[::6]), fill=SKIN_LT),
        p.poly(spline(ell(cx + 40, 168, 50, 62)[::6]), fill=SKIN_SH),
        p.poly(spline([(cx - 88, 110), (cx - 54, 58), (cx + 34, 50), (cx + 86, 94),
                       (cx + 66, 114), (cx + 12, 90), (cx - 40, 106)]), fill=(64, 46, 32)),
    ], 7, 5.6)
    # 헬멧 — 펠트 돔
    part(lambda p: [
        (lambda g: [
            p.poly(spline(g["rim"][::6]), fill=(150, 112, 44)),
            p.poly(spline(g["shell"][::5]), fill=OCHRE),
            p.poly(spline(g["crest"][::6]), fill=AMBER),
            p.poly(spline(g["port_ring"][::6]), fill=(150, 112, 44)),
            p.poly(spline(g["port"][::6]), fill=TEAL),
            p.line(g["pipe"], fill=RUST, width=16),
        ])(helmet_geo(cx + 6, 58, 76)),
    ], 8, 4.4)

    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for im in parts:
        base = Image.alpha_composite(base, im)

    # 실 눈 · 바느질 · 볼 — 보풀 없이 또렷하게 (실은 보풀지 않는다)
    p = Pen(W, H, ss=3)
    for s_ in (-1, 1):
        p.poly(spline(ell(cx + s_ * 60, 180, 25, 16)[::6]), fill=(208, 134, 122))
    for s_ in (-1, 1):
        ex = cx + s_ * 35 + (2 if s_ > 0 else 0)
        p.dot(ex, 150, 15, (32, 24, 18))
        p.dot(ex - s_ * 4, 145, 4.5, CREAM)
        _stitch(p, [(ex - 22, 114), (ex + 22, 108)] if s_ < 0 else [(ex - 22, 108), (ex + 22, 114)],
                (52, 38, 26), n=3, w=5, ln=12)
    _stitch(p, [(cx - 16, 204), (cx - 4, 213), (cx + 8, 213), (cx + 18, 202)],
            (146, 72, 56), n=4, w=5, ln=9)
    # 머리와 몸을 잇는 솔기
    _stitch(p, [(cx - 82, 236), (cx, 226), (cx + 82, 238)], (120, 96, 62), n=7, w=4, ln=9)
    # 몸통 솔기
    _stitch(p, [(cx - 94, 300), (cx - 104, 410), (cx - 90, 500)], (96, 72, 46), n=7, w=4, ln=10)
    _stitch(p, [(cx + 96, 302), (cx + 104, 410), (cx + 84, 502)], (96, 72, 46), n=7, w=4, ln=10)
    _stitch(p, [(cx - 50, 366), (cx + 52, 366)], (150, 124, 82), n=7, w=3, ln=9)
    # 어깨 기운 자국
    for i in range(4):
        x0 = cx - 80 + i * 13
        p.line([(x0, 306 + i * 3), (x0 + 10, 336 + i * 3)], fill=OXBLOOD, width=5)
    # 벨트 + 단추 + 랜턴
    p.poly([(cx - 100, 456), (cx + 98, 458), (cx + 96, 488), (cx - 98, 486)], fill=(58, 44, 30))
    _stitch(p, [(cx - 96, 472), (cx + 94, 474)], (172, 144, 98), n=12, w=3, ln=9)
    p.dot(cx - 2, 472, 15, BRASS); p.dot(cx - 6, 468, 3, (58, 44, 30)); p.dot(cx + 2, 476, 3, (58, 44, 30))
    p.poly(spline(ell(cx - 84, 510, 24, 29)[::6]), fill=(112, 82, 24))
    p.poly(spline(ell(cx - 84, 510, 15, 19)[::6]), fill=LAMP)
    # 헬멧 리벳 = 작은 단추
    for i in range(6):
        ang = math.pi + i * math.pi / 5
        p.dot(cx + 6 + math.cos(ang) * 68, 58 + math.sin(ang) * 60, 7, BRASS)
    base = Image.alpha_composite(base, p.resolve())

    base = grain(base, 0.15, 1.0, 21)
    base = base.filter(ImageFilter.GaussianBlur(0.4))
    base = shade_lin(base, 1.06, 0.86)
    return base, (cx, 152, 158)


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
        head = fig.crop((0, 2, fig.size[0], 33))
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
