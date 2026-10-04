"""S16-A — 유물 카드 아트(수집 카드 느낌). 생성 AI 없음, PIL+numpy 절차 생성.

python tools/gen_cards.py          → static/art/cards/*.png + cards_meta.json + docs/reports/s16a_cards_sheet.png

카드 400×560(5:7, 폰 2배 설계). 그리는 순서: art_bg → 유물 그림(props, 정수 배율·최근접) → frame_<rarity> → (foil 마스크로 움직이는 그라데이션) → 글자.
희귀도 id 는 engine/relic_generator.Rarity: common · uncommon · rare · epic · legendary.
화풍: M5 — 깊은 청록 위의 따뜻한 등불, 손그림 진한 외곽선(#1C1712), 2~3단 평면 음영 + 베벨.
"""
import os, math, json, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DST = os.path.join(ROOT, "static", "art", "cards"); os.makedirs(DST, exist_ok=True)
PROPS = os.path.join(ROOT, "static", "art", "props")
CW, CH, RAD = 400, 560, 22
RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]
# 카드 칸(전부 카드 px)
WIN = (36, 70, 364, 334)          # 그림 창 328×264
TOPB = (36, 22, 364, 60)          # 번호 띠(왼쪽 번호, 오른쪽 갈래 자리)
CAT_SLOT = (326, 24, 360, 58)     # 갈래 무늬 자리 34×34
NAMEB = (36, 344, 364, 392)       # 이름 띠
INFOB = (36, 400, 364, 512)       # 갈래·설명 띠
PIPS_Y = 536                      # 희귀도 등(점) 줄 중심
INK = (28, 23, 18)
FONT = "C:/Windows/Fonts/malgun.ttf"; FONTB = "C:/Windows/Fonts/malgunbd.ttf"


def hexrgb(h):
    h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def noise(w, h, scale, seed, octaves=3):
    rng = np.random.default_rng(seed); out = np.zeros((h, w), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        s = max(1, int(scale / (2 ** o)))
        sm = rng.random((h // s + 2, w // s + 2)).astype(np.float32)
        im = Image.fromarray((sm * 255).astype("uint8")).resize((w + 2 * s, h + 2 * s), Image.BICUBIC)
        out += np.asarray(im, np.float32)[s:s + h, s:s + w] / 255 * amp; tot += amp; amp *= 0.5
    return out / tot


def rrect_mask(w, h, box, r):
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle(box, r, fill=255); return m


def bevel(mask_img, blur=5, strength=0.9, light=(-1, -1)):
    """마스크 높이 → 엠보스 음영(-1..1)"""
    hgt = np.asarray(mask_img.filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255
    gy, gx = np.gradient(hgt)
    lx, ly = light; n = math.hypot(lx, ly)
    return np.clip(-(gx * lx + gy * ly) / n * 18 * strength, -1, 1)


def shade(rgb, sh, k=0.35):
    return np.clip(rgb * (1 + k * sh[..., None]), 0, 255)


def outline(mask_img, w=3):
    m = mask_img.point(lambda v: 255 if v > 127 else 0)
    dil = m.filter(ImageFilter.MaxFilter(w * 2 + 1)); ero = m.filter(ImageFilter.MinFilter(3))
    return ImageChops.subtract(dil, ero)


def lamp(img, cx, cy, r=7, glow=34, col=(255, 200, 112), a=230):
    g = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(g)
    d.ellipse([cx - glow, cy - glow, cx + glow, cy + glow], fill=(*col, a))
    g = g.filter(ImageFilter.GaussianBlur(glow * 0.45))
    img.alpha_composite(g)
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], fill=(70, 50, 30, 255), outline=INK + (255,), width=2)   # 받침
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 214, 140, 255))
    d.ellipse([cx - r * 0.45 - 1, cy - r * 0.55 - 1, cx - r * 0.45 + 2, cy - r * 0.55 + 2], fill=(255, 250, 230, 255))


# ── 재질 ────────────────────────────────────────────────────────────────
def mat_wood(polish, seed):
    yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
    nv = np.asarray(Image.fromarray((noise(CW, CH // 8 + 1, 6, seed) * 255).astype("uint8")).resize((CW, CH), Image.BICUBIC), np.float32) / 255
    grain = np.sin(xx * 0.21 + nv * 7.0) * 0.7 + np.sin(xx * 0.07 + nv * 3.0) * 0.3     # 세로 결(위아래로 길게 늘인 노이즈)
    base = hexrgb("#6A4A2A") if not polish else hexrgb("#7E5430")
    dark = hexrgb("#4A321C") if not polish else hexrgb("#5A3820")
    t = (grain * 0.5 + 0.5)[..., None]
    rgb = dark * (1 - t) + base * t
    if not polish:                                    # 닳은 나무: 바랜 얼룩 + 긁힘
        wear = noise(CW, CH, 24, seed + 5)
        rgb = rgb * (0.9 + 0.14 * wear[..., None])
        rgb = rgb + np.array([22, 18, 12]) * np.clip((wear[..., None] - 0.6) * 4, 0, 1)
    else:                                             # 윤낸 나무: 사선 광택 띠
        hl = np.exp(-((xx + yy * 0.6 - 260) / 70) ** 2)
        rgb = rgb + 60 * hl[..., None]
    return rgb


def mat_metal(stops, seed, freq=0.012):
    yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
    n = noise(CW, CH, 30, seed)
    t = (np.sin((xx + yy) * freq + n * 2.2) * 0.5 + 0.5)
    cols = [hexrgb(c) for c in stops]
    idx = t * (len(cols) - 1); i0 = np.floor(idx).astype(int).clip(0, len(cols) - 2); f = (idx - i0)[..., None]
    c0 = np.stack([cols[i] for i in range(len(cols))])
    return c0[i0] * (1 - f) + c0[i0 + 1] * f


def mat_nacre(seed):
    """자개: 진주빛 바탕에 분홍·연두·연보라·복숭아 결이 일렁인다(채도 낮게)"""
    yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
    n = noise(CW, CH, 60, seed); n2 = noise(CW, CH, 14, seed + 1)
    t = (np.sin(xx * 0.035 + yy * 0.021 + n * 7) + np.sin(yy * 0.05 - xx * 0.01 + n2 * 4)) * 0.25 + 0.5
    pal = [hexrgb(c) for c in ["#E9E3D3", "#D9CCE0", "#CBE3DC", "#EED9C6", "#E4E9D0", "#E9E3D3"]]
    idx = t * (len(pal) - 1); i0 = np.floor(idx).astype(int).clip(0, len(pal) - 2); f = (idx - i0)[..., None]
    P = np.stack(pal); rgb = P[i0] * (1 - f) + P[i0 + 1] * f
    sparkle = (n2 > 0.78) * 25
    return rgb + sparkle[..., None]


# ── 프레임 ──────────────────────────────────────────────────────────────
def frame(rarity):
    seed = RARITIES.index(rarity) * 11 + 3
    card = rrect_mask(CW, CH, (0, 0, CW - 1, CH - 1), RAD)
    holes = Image.new("L", (CW, CH), 0); dh = ImageDraw.Draw(holes)
    for b, r in ((WIN, 10), (TOPB, 8), (NAMEB, 8), (INFOB, 8)):
        dh.rounded_rectangle(b, r, fill=255)
    body = ImageChops.subtract(card, holes)
    if rarity == "common":
        rgb = mat_wood(False, seed)
    elif rarity == "uncommon":
        rgb = mat_wood(True, seed)
    elif rarity in ("rare", "epic"):
        rgb = mat_metal(["#7A5A1E", "#C9A040", "#F2D27A", "#B08A30", "#7A5A1E"], seed, 0.016)
    else:
        rgb = mat_nacre(seed)
    sh = bevel(body, 5, 1.0)
    rgb = shade(rgb, sh, 0.45 if rarity != "legendary" else 0.25)
    out = np.zeros((CH, CW, 4), np.float32); out[..., :3] = rgb; out[..., 3] = np.asarray(body, np.float32)
    img = Image.fromarray(out.astype("uint8"), "RGBA")
    d = ImageDraw.Draw(img)

    # 안쪽 테(희귀도마다 다른 금속 띠)
    trim = {"common": "#7A6A54", "uncommon": "#B89A5A", "rare": "#FFF0B0", "epic": "#FFF0B0", "legendary": "#F6F2EA"}[rarity]
    for b, r in ((WIN, 10), (NAMEB, 8), (INFOB, 8), (TOPB, 8)):
        x0, y0, x1, y1 = b
        d.rounded_rectangle((x0 - 5, y0 - 5, x1 + 5, y1 + 5), r + 5, outline=trim, width=3 if rarity != "common" else 2)
    # 판(글자 바탕): 종이 — 글자가 폰에서 읽히게 밝은 바탕 + 진한 글자
    paper = {"common": ("#CDBE9C", "#BBAA86"), "uncommon": ("#DDCDA8", "#C9B890"), "rare": ("#E8DCBF", "#D6C8A4"),
             "epic": ("#E8DCBF", "#D6C8A4"), "legendary": ("#F1ECE0", "#E2DACA")}[rarity]
    for b, r, k in ((TOPB, 8, 1), (NAMEB, 8, 0), (INFOB, 8, 1)):
        pm = rrect_mask(CW, CH, b, r)
        pn = noise(CW, CH, 8, seed + k)
        prgb = np.ones((CH, CW, 3), np.float32) * hexrgb(paper[k]) * (0.94 + 0.08 * pn[..., None])
        psh = bevel(ImageChops.invert(pm), 3, 0.6)                    # 판은 파인 쪽(안쪽 그늘)
        prgb = shade(prgb, -psh, 0.25)
        pa = np.zeros((CH, CW, 4), np.float32); pa[..., :3] = prgb; pa[..., 3] = np.asarray(pm, np.float32)
        img.alpha_composite(Image.fromarray(pa.astype("uint8"), "RGBA"))
    d = ImageDraw.Draw(img)
    # 갈래 무늬 자리(원 홈)
    x0, y0, x1, y1 = CAT_SLOT
    d.ellipse(CAT_SLOT, fill=(40, 34, 26, 255), outline=trim, width=2)

    # 희귀도별 장식
    if rarity == "common":       # 귀퉁이 놋쇠 덮개(바램) + 못
        for (cx, cy, sx, sy) in ((0, 0, 1, 1), (CW, 0, -1, 1), (0, CH, 1, -1), (CW, CH, -1, -1)):
            pts = [(cx, cy + sy * 46), (cx, cy), (cx + sx * 46, cy), (cx + sx * 30, cy + sy * 12), (cx + sx * 12, cy + sy * 30)]
            d.polygon(pts, fill=(122, 106, 84, 255), outline=INK, width=2)
            d.ellipse([cx + sx * 14 - 3, cy + sy * 14 - 3, cx + sx * 14 + 3, cy + sy * 14 + 3], fill=(60, 50, 40, 255))
        r_ = random.Random(1)
        for _ in range(6):            # 긁힘
            x = r_.uniform(8, CW - 8); y = r_.uniform(8, CH - 8)
            if not (WIN[0] - 8 < x < WIN[2] + 8 and WIN[1] - 8 < y < INFOB[3] + 8):
                d.line([(x, y), (x + r_.uniform(-14, 14), y + r_.uniform(-6, 6))], fill=(150, 120, 80, 200), width=1)
    if rarity == "uncommon":     # 놋쇠 귀퉁이(윤기) + 리벳 줄
        for (cx, cy, sx, sy) in ((0, 0, 1, 1), (CW, 0, -1, 1), (0, CH, 1, -1), (CW, CH, -1, -1)):
            pts = [(cx, cy + sy * 54), (cx, cy), (cx + sx * 54, cy), (cx + sx * 36, cy + sy * 14), (cx + sx * 14, cy + sy * 36)]
            d.polygon(pts, fill=(196, 160, 90, 255), outline=INK, width=2)
            d.line([(cx + sx * 6, cy + sy * 40), (cx + sx * 40, cy + sy * 6)], fill=(250, 226, 160, 255), width=2)
        for y in range(90, CH - 60, 44):
            for x in (18, CW - 18):
                d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(210, 180, 110, 255), outline=INK, width=1)
    if rarity == "epic":         # 청록 에나멜 상감(옆 띠) — 바다 빛, 등 사이
        for x0_, x1_ in ((7, 27), (CW - 27, CW - 7)):
            for k in range(4):
                y0_ = 92 + k * 110
                d.rounded_rectangle((x0_, y0_, x1_, y0_ + 74), 6, fill=(30, 90, 100, 255), outline=(255, 240, 176, 255), width=2)
                d.line([(x0_ + 5, y0_ + 8), (x0_ + 5, y0_ + 30)], fill=(120, 200, 200, 255), width=2)
    if rarity == "legendary":    # 은빛 테 + 진주 + 자개 귀퉁이 소용돌이
        d.rounded_rectangle((3, 3, CW - 4, CH - 4), RAD - 3, outline=(246, 242, 234, 255), width=3)
        for (cx, cy) in ((24, 24), (CW - 24, 24), (24, CH - 24), (CW - 24, CH - 24)):
            for rr_ in (14, 9, 4):
                d.arc([cx - rr_, cy - rr_, cx + rr_, cy + rr_], 0, 300, fill=(180, 160, 190, 255), width=2)
    # 등불(희귀도 사다리: 희귀 4 → 영웅 6 → 전설 6 + 진주)
    lamps = {"rare": [(22, 22), (CW - 22, 22), (22, CH - 22), (CW - 22, CH - 22)],
             "epic": [(22, 22), (CW - 22, 22), (22, CH - 22), (CW - 22, CH - 22), (CW // 2, 10), (CW // 2, CH - 10)],
             "legendary": [(CW // 2, 10), (CW // 2, CH - 10), (10, CH // 2), (CW - 10, CH // 2)]}.get(rarity, [])
    for (x, y) in lamps:
        lamp(img, x, y, r=8)
    if rarity == "legendary":
        d = ImageDraw.Draw(img)
        for (cx, cy) in ((24, 24), (CW - 24, 24), (24, CH - 24), (CW - 24, CH - 24)):
            g = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=(255, 250, 240, 120))
            img.alpha_composite(g.filter(ImageFilter.GaussianBlur(6)))
            d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(244, 238, 232, 255), outline=INK, width=2)
            d.ellipse([cx - 4, cy - 5, cx, cy - 1], fill=(255, 255, 255, 255))
    # 희귀도 점(등 모양) — 색이 아니라 개수로도 읽힌다
    n = RARITIES.index(rarity) + 1
    d = ImageDraw.Draw(img)
    for i in range(n):
        x = CW // 2 + (i - (n - 1) / 2) * 22
        d.ellipse([x - 7, PIPS_Y - 7, x + 7, PIPS_Y + 7], fill=(255, 210, 128, 255) if rarity != "common" else (200, 170, 110, 255), outline=INK, width=2)
    # 외곽선(손그림 진한 선): 카드 바깥 + 구멍 둘레
    ol = Image.new("RGBA", img.size, INK + (0,)); ol.putalpha(outline(body, 2))
    img.alpha_composite(ol)
    return img


def art_bg():
    """그림 창 바탕: 깊은 청록 + 위쪽 등불 온기 + 바다눈. 모든 희귀도 공통"""
    w, h = WIN[2] - WIN[0], WIN[3] - WIN[1]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    top, bot = hexrgb("#1E5A68"), hexrgb("#0A2630")
    t = (yy / h)[..., None]; rgb = top * (1 - t) + bot * t
    warm = np.exp(-(((xx - w / 2) / (w * 0.45)) ** 2 + ((yy - h * 0.35) / (h * 0.5)) ** 2))
    rgb = rgb + np.array([90, 55, 20]) * warm[..., None] * 0.55
    vig = np.clip(1 - (((xx - w / 2) / w) ** 2 + ((yy - h / 2) / h) ** 2) * 0.9, 0.55, 1)
    rgb = rgb * vig[..., None]
    img = Image.fromarray(np.clip(rgb, 0, 255).astype("uint8"), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img); r = random.Random(4)
    for _ in range(70):
        x, y = r.uniform(0, w), r.uniform(0, h); s = r.choice([0.8, 1.0, 1.4])
        d.ellipse([x - s, y - s, x + s, y + s], fill=(200, 230, 225, r.randint(50, 120)))
    # 바닥 그림자 띠(유물이 놓이는 선반)
    d.ellipse([w * 0.2, h * 0.78, w * 0.8, h * 0.9], fill=(4, 14, 18, 110))
    return img.filter(ImageFilter.GaussianBlur(0.3))


def card_back():
    yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
    c = hexrgb("#1B5A68"); e = hexrgb("#08202A")
    rr = np.sqrt(((xx - CW / 2) / CW) ** 2 + ((yy - CH / 2) / CH) ** 2) * 1.8
    rgb = c * (1 - rr[..., None].clip(0, 1)) + e * rr[..., None].clip(0, 1)
    for k in range(14):                       # 물결 줄
        y0 = 40 + k * 38
        wave = np.abs(yy - (y0 + 6 * np.sin(xx * 0.045 + k * 1.3)))
        rgb = rgb + np.array([30, 60, 60]) * (wave < 1.2)[..., None] * 0.6
    card = rrect_mask(CW, CH, (0, 0, CW - 1, CH - 1), RAD)
    out = np.zeros((CH, CW, 4), np.float32); out[..., :3] = rgb; out[..., 3] = np.asarray(card, np.float32)
    img = Image.fromarray(np.clip(out, 0, 255).astype("uint8"), "RGBA")
    # 놋쇠 테
    ring = ImageChops.subtract(card, rrect_mask(CW, CH, (18, 18, CW - 19, CH - 19), RAD - 8))
    brass = shade(mat_metal(["#6A5030", "#A08050", "#D8B878", "#A08050"], 9, 0.02), bevel(ring, 4), 0.5)
    ba = np.zeros((CH, CW, 4), np.float32); ba[..., :3] = brass; ba[..., 3] = np.asarray(ring, np.float32)
    img.alpha_composite(Image.fromarray(ba.astype("uint8"), "RGBA"))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((28, 28, CW - 29, CH - 29), RAD - 12, outline=(232, 200, 130, 255), width=2)
    # 표장(방주·관리실): 원 메달 안에 탑 위 유리 돔 + 꼭대기 등불 + 아래 물결 둘
    cx, cy, R = CW // 2, CH // 2 - 10, 92
    med = rrect_mask(CW, CH, (cx - R, cy - R, cx + R, cy + R), R)
    mrgb = shade(mat_metal(["#7A5A30", "#C8A060", "#F0D28C", "#B08A48"], 12, 0.03), bevel(med, 5), 0.5)
    ma = np.zeros((CH, CW, 4), np.float32); ma[..., :3] = mrgb; ma[..., 3] = np.asarray(med, np.float32)
    img.alpha_composite(Image.fromarray(ma.astype("uint8"), "RGBA"))
    d = ImageDraw.Draw(img)
    r2 = R - 14
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=(14, 52, 62, 255), outline=INK, width=3)
    cream = (232, 220, 191, 255)
    # 탑(창 격자) + 돔
    tw, tt = 70, cy - 4
    d.rectangle([cx - tw // 2, tt, cx + tw // 2, cy + 46], fill=cream, outline=INK, width=2)
    for i in range(3):
        for j in range(2):
            x = cx - 26 + i * 20; y = tt + 10 + j * 18
            d.rectangle([x, y, x + 12, y + 11], fill=(255, 200, 112, 255) if (i + j) % 2 == 0 else (40, 60, 64, 255), outline=INK, width=1)
    d.pieslice([cx - 44, tt - 44, cx + 44, tt + 44], 180, 360, fill=(120, 180, 176, 255), outline=INK, width=2)
    for a in (220, 270, 320):
        d.line([(cx, tt), (cx + 44 * math.cos(math.radians(a)), tt + 44 * math.sin(math.radians(a)))], fill=INK, width=2)
    d.arc([cx - 26, tt - 26, cx + 26, tt + 26], 180, 360, fill=INK, width=2)
    # 물결 둘(탑 밑동이 물에)
    for k, yy_ in enumerate((cy + 50, cy + 62)):
        pts = [(cx - 60 + t, yy_ + 4 * math.sin(t * 0.18 + k)) for t in range(0, 121, 4)]
        d.line(pts, fill=(150, 210, 205, 255), width=3)
    lamp(img, cx, tt - 52, r=8, glow=40, a=200)
    # 귀퉁이 등
    for (x, y) in ((40, 40), (CW - 40, 40), (40, CH - 40), (CW - 40, CH - 40)):
        lamp(img, x, y, r=5, glow=18, a=150)
    ol = Image.new("RGBA", img.size, INK + (0,)); ol.putalpha(outline(card, 2)); img.alpha_composite(ol)
    return img


def foil(kind):
    """L 마스크(흰 = 반짝이 셈). 클라이언트가 움직이는 무지개/빛 그라데이션을 이 마스크로 곱해 얹는다"""
    yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
    card = np.asarray(rrect_mask(CW, CH, (0, 0, CW - 1, CH - 1), RAD), np.float32) / 255
    win = np.asarray(rrect_mask(CW, CH, WIN, 10), np.float32) / 255
    bands = np.zeros_like(card)
    for b in (TOPB, NAMEB, INFOB):
        bands = np.maximum(bands, np.asarray(rrect_mask(CW, CH, b, 8), np.float32) / 255)
    rng = np.random.default_rng({"rare": 1, "legendary": 2, "sea": 3}[kind])
    if kind == "rare":          # 사선 가는 줄 + 반짝 점 — 테에 강하게, 그림 창에 약하게
        lines = (np.sin((xx + yy) * 0.55) > 0.82).astype(np.float32) * 0.7
        m = lines
        sp = np.zeros_like(m)
        for _ in range(260):
            x, y = rng.integers(0, CW), rng.integers(0, CH); sp[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = 1
        m = np.maximum(m, sp)
        weight = (1 - win) * (1 - bands) * 1.0 + win * 0.35
    elif kind == "legendary":   # 자개 결(동심 물결) + 별 반짝 — 창 전체에도 깔린다
        n = noise(CW, CH, 50, 7)
        rip = (np.sin(np.sqrt((xx - CW / 2) ** 2 + (yy - CH * 0.4) ** 2) * 0.16 + n * 6) * 0.5 + 0.5) ** 3
        m = rip
        for _ in range(60):
            x, y = int(rng.integers(10, CW - 10)), int(rng.integers(10, CH - 10)); s = int(rng.integers(3, 7))
            m[y, max(0, x - s):x + s + 1] = 1; m[max(0, y - s):y + s + 1, x] = 1
        weight = (1 - bands) * 1.0 + bands * 0.15
        weight = np.where(win > 0.5, 0.3, weight)
    else:                       # 바다 무늬: 가로 물결선(겹친 두 주기)
        w1 = np.abs(((yy + 9 * np.sin(xx * 0.04)) % 22) - 11) < 1.6
        w2 = np.abs(((yy + 14 + 6 * np.sin(xx * 0.07 + 1.3)) % 34) - 17) < 1.1
        m = np.maximum(w1 * 0.9, w2 * 0.6).astype(np.float32)
        weight = (1 - bands) * 1.0 + bands * 0.1
    out = np.clip(m * weight * card, 0, 1)
    img = Image.fromarray((out * 255).astype("uint8"), "L").filter(ImageFilter.GaussianBlur(0.6))
    return img


def charge_glow(size=512):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) - size / 2
    r = np.sqrt(xx ** 2 + yy ** 2) / (size / 2); a = np.arctan2(yy, xx)
    core = np.exp(-(r / 0.28) ** 2)
    halo = np.exp(-(r / 0.62) ** 2) * 0.55
    rays = (np.cos(a * 12) * 0.5 + 0.5) ** 6 * np.exp(-(r / 0.85) ** 2) * 0.6
    v = np.clip(core + halo + rays, 0, 1) * (r < 1)
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0)); img.putalpha(Image.fromarray((v * 255).astype("uint8"), "L"))
    return img


def main():
    meta = {"_note": "S16-A 유물 카드. 좌표는 카드 px(2배 설계, 폰에서 200×280 CSS). 생성 tools/gen_cards.py. 생성 AI 없음",
            "card": {"w": CW, "h": CH, "radius": RAD, "ratio": "5:7"},
            "draw_order": ["art_bg.png → art_window 위치", "유물 그림(static/art/props, 정수 배율·NEAREST, 창 가운데·바닥 선반선 정렬)",
                           "frame_<rarity>.png", "foil(희귀 이상): 마스크로 움직이는 그라데이션을 곱해 얹기(screen/lighter)", "글자"],
            "art_window": dict(x=WIN[0], y=WIN[1], w=WIN[2] - WIN[0], h=WIN[3] - WIN[1], radius=10, shelf_y=WIN[1] + int((WIN[3] - WIN[1]) * 0.84),
                               prop_scale_rule="scale = floor(min(280 / w, 200 / h)), 1 이상 정수. 그림 바닥을 shelf_y 에 맞춘다"),
            "text": {"number": dict(x=TOPB[0] + 12, y=TOPB[1], w=CAT_SLOT[0] - TOPB[0] - 20, h=TOPB[3] - TOPB[1], align="left", size=20, color="#1C1712", note="No. 0123"),
                     "category_slot": dict(x=CAT_SLOT[0], y=CAT_SLOT[1], w=34, h=34, note="갈래 무늬(상자 무늬와 같은 그림)를 원 홈에"),
                     "name": dict(x=NAMEB[0] + 12, y=NAMEB[1], w=NAMEB[2] - NAMEB[0] - 24, h=NAMEB[3] - NAMEB[1], align="center", size=26, weight="bold", color="#1C1712"),
                     "info": dict(x=INFOB[0] + 14, y=INFOB[1] + 8, w=INFOB[2] - INFOB[0] - 28, h=INFOB[3] - INFOB[1] - 16, align="left", size=17, color="#2E261E",
                                  note="첫 줄 갈래·희귀도, 그 아래 설명 2~3줄"),
                     "pips": dict(y=PIPS_Y, note="희귀도 점은 프레임에 그려져 있다(1~5개)")},
            "nine_patch": None, "nine_patch_note": "쓰지 않는다. 카드는 고정 크기 한 장 그림이다(작게 쓸 땐 통째로 줄인다)",
            "rarities": {}, "files": {}}
    tint = {"common": "#C8A878", "uncommon": "#F0C070", "rare": "#FFD27A", "epic": "#7FE0D8", "legendary": "#F4EEFF"}
    desc = {"common": "닳은 나무·바랜 놋쇠", "uncommon": "윤낸 나무·놋쇠 귀퉁이·리벳", "rare": "금박 테·작은 등 넷",
            "epic": "금박 테·청록 에나멜 상감·등 여섯", "legendary": "자개 테·은빛 줄·진주 넷·등 넷"}
    for r in RARITIES:
        im = frame(r)
        im.save(os.path.join(DST, f"frame_{r}.png"), optimize=True)
        meta["rarities"][r] = dict(frame=f"frame_{r}.png", pips=RARITIES.index(r) + 1, look=desc[r], charge_tint=tint[r],
                                   foil={"rare": "foil_rare.png", "epic": "foil_rare.png", "legendary": "foil_legendary.png"}.get(r),
                                   foil_sea_ok=r in ("uncommon", "rare", "epic", "legendary"))
    art_bg().save(os.path.join(DST, "art_bg.png"), optimize=True)
    card_back().save(os.path.join(DST, "card_back.png"), optimize=True)
    for k in ("rare", "legendary", "sea"):
        foil(k).save(os.path.join(DST, f"foil_{k}.png"), optimize=True)
    charge_glow().save(os.path.join(DST, "charge_glow.png"), optimize=True)
    meta["files"] = {"card_back": "card_back.png", "art_bg": "art_bg.png",
                     "foil": {"rare": "foil_rare.png", "legendary": "foil_legendary.png", "sea": "foil_sea.png",
                              "note": "L(회색조) 마스크. 흰 곳만 빛이 지나간다. 바다 무늬(foil_sea)는 특별판·이벤트용 덧씌움"},
                     "charge_glow": {"file": "charge_glow.png", "size": 512, "note": "흰 빛(알파). charge_tint 로 물들여 카드 뒤에서 0→1.3배로 키우며 뒤집기 직전에 터뜨린다"}}
    json.dump(meta, open(os.path.join(DST, "cards_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sheet(meta)


def sheet(meta):
    f = lambda s, b=False: ImageFont.truetype(FONTB if b else FONT, s)
    props = sorted(p for p in os.listdir(PROPS) if p.endswith(".png"))
    pick = ["prop_brown_vial.png", "prop_cell_tin.png", "prop_dry_jar.png", "prop_black_panel.png", "prop_flat_canteen.png"]
    pick = [p for p in pick if p in props] or props[:5]
    names = ["갈색 약병", "전지 깡통", "마른 단지", "검은 판", "납작 수통"]
    cats = ["의약", "전자", "식품", "전자", "음료"]
    S = Image.new("RGBA", (6 * 420 + 20, 60 + CH + 50 + CH // 2 + 44), (10, 30, 38, 255)); d = ImageDraw.Draw(S)
    d.text((20, 14), "S16-A 유물 카드 — 희귀도 다섯 · 뒷면 · 반짝이 마스크 · 등장 빛 (생성 AI 없음)", font=f(26, True), fill=(232, 220, 191))
    bg = Image.open(os.path.join(DST, "art_bg.png")).convert("RGBA")
    for i, r in enumerate(RARITIES):
        c = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        c.alpha_composite(bg, (WIN[0], WIN[1]))
        pr = Image.open(os.path.join(PROPS, pick[i % len(pick)])).convert("RGBA")
        sc = max(1, int(min(280 / pr.width, 200 / pr.height)))
        pr = pr.resize((pr.width * sc, pr.height * sc), Image.NEAREST)
        aw = meta["art_window"]
        c.alpha_composite(pr, (aw["x"] + (aw["w"] - pr.width) // 2, aw["shelf_y"] - pr.height))
        fr = Image.open(os.path.join(DST, f"frame_{r}.png")).convert("RGBA"); c.alpha_composite(fr)
        if r in ("rare", "epic", "legendary"):          # 반짝이 시연: 무지개 사선 그라데이션 × 마스크
            m = Image.open(os.path.join(DST, meta["rarities"][r]["foil"])).convert("L")
            yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32); t = (xx + yy) / (CW + CH) * 6.28
            rb = np.stack([np.sin(t) * 0.5 + 0.5, np.sin(t + 2.1) * 0.5 + 0.5, np.sin(t + 4.2) * 0.5 + 0.5], -1) * 255
            fo = Image.fromarray(rb.astype("uint8"), "RGB").convert("RGBA"); fo.putalpha(m.point(lambda v: int(v * 0.32)))
            c.alpha_composite(fo)
        dc = ImageDraw.Draw(c); T = meta["text"]
        dc.text((T["number"]["x"], T["number"]["y"] + 8), f"No. {37 + i * 41:04d}", font=f(20, True), fill=INK)
        nm = names[i % len(names)]; tw = dc.textlength(nm, font=f(26, True))
        dc.text((NAMEB[0] + (NAMEB[2] - NAMEB[0] - tw) / 2, NAMEB[1] + 7), nm, font=f(26, True), fill=INK)
        dc.text((T["info"]["x"], T["info"]["y"]), f"{cats[i % 5]} · {r}", font=f(17, True), fill=(46, 38, 30))
        dc.text((T["info"]["x"], T["info"]["y"] + 28), "200년 전 누군가의 선반에 있던 것.\n흔들면 안에서 소리가 난다.", font=f(16), fill=(46, 38, 30))
        S.alpha_composite(c, (20 + i * 420, 60))
        d.text((24 + i * 420, 60 + CH + 6), r, font=f(20, True), fill=(240, 200, 120))
    S.alpha_composite(Image.open(os.path.join(DST, "card_back.png")).convert("RGBA"), (20 + 5 * 420, 60))
    d.text((24 + 5 * 420, 60 + CH + 6), "card_back", font=f(20, True), fill=(240, 200, 120))
    # 둘째 줄: 폰 크기(절반) 다섯 + 마스크 셋 + 등장 빛
    y2 = 60 + CH + 50
    for i, r in enumerate(RARITIES):
        fr = Image.open(os.path.join(DST, f"frame_{r}.png")).convert("RGBA").resize((CW // 2, CH // 2), Image.LANCZOS)
        S.alpha_composite(fr, (20 + i * 215, y2))
    d.text((20, y2 + CH // 2 + 6), "↑ 폰 실제 크기(200×280 CSS)", font=f(18), fill=(200, 220, 214))
    for i, k in enumerate(("rare", "legendary", "sea")):
        m = Image.open(os.path.join(DST, f"foil_{k}.png")).convert("L").resize((CW // 2, CH // 2), Image.LANCZOS)
        S.paste(Image.merge("RGBA", (m, m, m, Image.new("L", m.size, 255))), (20 + 5 * 215 + i * 215, y2))
        d.text((24 + 5 * 215 + i * 215, y2 + CH // 2 + 6), f"foil_{k}", font=f(18), fill=(200, 220, 214))
    g = Image.open(os.path.join(DST, "charge_glow.png")).convert("RGBA").resize((280, 280))
    for i, r in enumerate(["rare", "epic", "legendary"]):
        tint = hexrgb(meta["rarities"][r]["charge_tint"]).astype(int)
        gg = Image.new("RGBA", g.size, (*tint, 0)); gg.putalpha(g.getchannel("A"))
        S.alpha_composite(gg, (20 + 8 * 215 + i * 150 - 60, y2 - 10))
    d.text((20 + 8 * 215, y2 + CH // 2 + 6), "charge_glow (희귀·영웅·전설 색)", font=f(18), fill=(200, 220, 214))
    out = os.path.join(ROOT, "docs", "reports", "s16a_cards_sheet.png")
    S.convert("RGB").save(out, optimize=True)
    tot = sum(os.path.getsize(os.path.join(DST, x)) for x in os.listdir(DST))
    print("sheet", out, "cards total KB", tot // 1024)


if __name__ == "__main__":
    main()
