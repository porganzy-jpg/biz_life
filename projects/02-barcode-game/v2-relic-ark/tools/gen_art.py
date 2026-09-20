# -*- coding: utf-8 -*-
"""
잔해 방주 아트 파이프라인 — "생성은 웹, 통일은 로컬 후처리"
  1) Pollinations(flux)로 원본 생성 → art_raw/
  2) Pillow 후처리(채도 감소·종이 톤·종이 텍스처·비네트) → static/art/

사용:
  python tools/gen_art.py               # 전체 (우선순위 순)
  python tools/gen_art.py rooms cards   # 이름에 포함된 것만
  python tools/gen_art.py --post-only   # 생성 없이 후처리만 다시
"""
import json
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "art_raw"
OUT = ROOT / "static" / "art"
RAW.mkdir(exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

# ── 스타일 토큰 (모든 프롬프트에 고정) ─────────────────────────
# 주제를 먼저, 스타일은 뒤에. (flux는 프롬프트 앞부분을 우선한다)
STYLE = (", storybook watercolor and gouache illustration, soft ink outlines, painterly, "
         "muted dusty palette of grey concrete and faded beige with warm lantern-orange highlights, "
         "full-bleed edge-to-edge composition, no frame, no border, no text, no letters, no watermark, highly detailed")
ROOM = ("Fallout Shelter style side-view cutaway of one cozy inhabited underground bunker room, "
        "seen straight from the side like a dollhouse, bright warm key light, clear readable silhouettes, "
        "lived-in and tidy, wide 3:2 game room asset: ")
CARD = ("close-up product illustration of exactly one object, filling most of the frame, centered, "
        "isolated on a plain dark grey textured background, nothing else in the scene, "
        "soft dramatic top light, slight dust and wear, vertical 3:4: ")

JOBS = {}  # rel path -> (prompt, w, h, seed)

# 1) 배경: 지상 스카이라인(와이드) + 지하 흙 텍스처
JOBS["surface.jpg"] = ("wide panorama of overgrown ruined Korean apartment blocks and a collapsed convenience store "
                        "with a dead neon sign, weeds, rusted cars, birds, hazy warm dusk sky with soft light" + STYLE, 1024, 576, 8801)


def make_earth(dst: Path, size=(768, 768), seed=880):
    """지하 흙 텍스처(세로 타일링). AI는 터널을 그리므로 절차 생성한다."""
    w, h = size
    rnd = random.Random(seed)
    img = Image.new("RGB", size, (30, 27, 23))
    d = ImageDraw.Draw(img)
    y = 0
    while y < h:                                   # 지층
        band = rnd.randint(40, 110)
        c = rnd.choice([(34, 30, 26), (28, 25, 21), (38, 33, 27), (26, 24, 22)])
        d.rectangle((0, y, w, y + band), fill=c)
        d.line((0, y, w, y), fill=(18, 16, 14), width=2)
        y += band
    for _ in range(140):                           # 콘크리트 조각·돌
        x, yy = rnd.randint(0, w), rnd.randint(0, h)
        rw, rh = rnd.randint(6, 40), rnd.randint(4, 18)
        d.rectangle((x, yy, x + rw, yy + rh), fill=rnd.choice([(58, 56, 51), (70, 66, 60), (46, 44, 40)]), outline=(20, 18, 16))
    for _ in range(25):                            # 뿌리
        x = rnd.randint(0, w); yy = rnd.randint(0, h)
        for k in range(rnd.randint(4, 12)):
            nx, ny = x + rnd.randint(-14, 14), yy + rnd.randint(6, 22)
            d.line((x, yy, nx, ny), fill=(52, 42, 30), width=rnd.randint(1, 3)); x, yy = nx, ny
    noise = Image.effect_noise(size, 22).convert("RGB")
    img = Image.blend(img, ImageChops.multiply(img, noise), 0.5)
    # 상하 이음새 완화
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(dst, "JPEG", quality=85)
    print("procedural", dst.name, flush=True)

# 2) 방 4종 + 빈 칸 2종
ROOMS = {
    "room_pantry.jpg": "a food storage room with wooden shelves packed full of colorful salvaged instant noodle packets, tin cans, glass jars and sacks of grain, a warm orange hanging lantern, a small table",
    "room_well.jpg": "a water purification room with two big metal tanks, copper pipes, a dripping tap filling a basin, rows of clear glass water jars glowing pale blue, one small lantern",
    "room_infirmary.jpg": "a small infirmary with two neat cots with white sheets, a medicine cabinet full of boxes and bandages, a soft green glowing lamp, clean white tiles",
    "room_library.jpg": "a cozy library room with salvaged books stacked to the ceiling, a wooden desk covered in blueprints and candles, a ladder, warm golden candlelight",
    "room_rock.jpg": "an unexcavated dark cavity of packed earth and concrete rubble, roots hanging, a pickaxe leaning against the wall, very dim",
    "room_lot.jpg": "an empty rubble lot on the surface between ruined buildings, weeds, a rusted shopping cart, hazy warm daylight, waiting to be rebuilt",
}
for i, (f, p) in enumerate(ROOMS.items()):
    JOBS[f] = (ROOM + p + STYLE, 768, 512, 8810 + i)

# 3) 주민 초상 3종
PORTRAITS = {
    "res_1.jpg": "half-body portrait of a weathered Korean woman survivor in her 40s, patched jacket, kind tired eyes, scarf, lantern light",
    "res_2.jpg": "half-body portrait of a young Korean man survivor with goggles on his forehead, tool belt, hopeful expression",
    "res_3.jpg": "half-body portrait of an old Korean man survivor with a grey beard, reading glasses, holding a salvaged book",
}
for i, (f, p) in enumerate(PORTRAITS.items()):
    JOBS[f] = (p + ", plain dusty background, centered, game character portrait" + STYLE, 512, 512, 8820 + i)

# 4) 유물 카드 아트 — 템플릿 31개 (data/relic_templates.json 이름 순)
TEMPLATE_PROMPTS = {
    # food
    "말린 실의 부적": "a faded red instant ramen packet",
    "바삭 조각의 봉헌": "a crumpled snack chip bag, faded colors",
    "철 항아리": "a dented rusty tin can with a torn label",
    "겨울 씨앗 주머니": "a small burlap pouch spilling seeds and grain",
    # drink
    "투명한 강": "a clear plastic water bottle catching light",
    "거품 우는 병": "a glass soda bottle with foam at the neck",
    "갈색 각성의 물": "a canned coffee drink, dark brown label",
    "불타는 투명수": "a bottle of clear liquor (soju) with a green tint",
    # medical
    "하얀 잠의 알": "a blister pack of white pills",
    "정화의 물": "a spray bottle of disinfectant with a faded blue label",
    "전쟁 물감": "a red lipstick tube, cap off",
    "상처 봉인 띠": "a box of adhesive bandages with a childlike cartoon print",
    # electronics
    "번개 알": "a pair of AA batteries",
    "빛 실": "a coiled charging cable with a glowing tip",
    "검은 거울판": "a cracked smartphone showing a green circuit board",
    "리더의 조각": "an ancient handheld barcode scanner device glowing faint gold, sacred",
    # stationery
    "생각 새기는 막대": "a worn ballpoint pen",
    "웃는 작은 사람": "a small plush toy doll, one button eye",
    "붙는 색 조각": "a stack of colorful sticky notes",
    "보험 증서": "an old folded insurance document with a red seal stamp",
    # book
    "기술자의 노트": "an open engineering notebook with hand-drawn machine diagrams",
    "약초 도감": "an open botanical field guide with pressed dried leaves between pages",
    "별 지도": "an open star atlas with constellations connected by lines",
    "마지막 서고의 열쇠책": "a massive ancient tome with a golden key embedded in its cover, glowing",
    # apparel
    "두 번째 피부": "a folded thermal undershirt, grey fabric",
    "발 갑옷": "a pair of worn hiking boots with deep tread",
    "이름표 천": "a work uniform shirt with a faded embroidered name patch",
    "지휘관의 외투": "a long military-style coat with brass buttons on a hook",
    # tobacco
    "연기 막대 묶음": "a soft pack of cigarettes, crumpled",
    "취하는 물 상자": "a cardboard case of canned beer, dented",
    "봉인된 황금 액체": "a sealed bottle of aged whiskey with amber liquid, dusty",
    # unknown
    "정체불명의 잔해": "an unidentifiable melted plastic object with a visible barcode label",
    "이름 없는 상자": "a sealed unmarked cardboard box with a barcode sticker, mysterious",
}
for i, (stem, p) in enumerate(TEMPLATE_PROMPTS.items()):
    JOBS[f"card_{i:02d}.jpg"] = (CARD + p + STYLE, 768, 1024, 8900 + i)
(OUT / "cards_index.json").write_text(json.dumps({stem: f"card_{i:02d}.jpg" for i, stem in enumerate(TEMPLATE_PROMPTS)}, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 지형 스플랫 텍스처 (절차 생성, 이음새 없는 타일링) ──────────
# S2-D ①. 연속 지형(SCREEN_VISION §6)의 스플랫 4장. 전부 Pillow+numpy 절차 생성이라
# AI 생성물이 아니며(07 §6 공개 대상 아님), 시드 고정으로 재현된다.
# 팔레트 규칙 B2: 초록=생명, 무채=콘크리트/아스팔트, 청록=정원사의 물.
TEX = ROOT / "static" / "textures"
TEXRAW = RAW / "textures"
TEXSIZE = 512


def _tnoise(size, freq, seed):
    """주기적 value noise (좌우·상하가 정확히 이어진다). 격자 인덱스를 freq로 모듈로."""
    import numpy as np
    rng = np.random.default_rng(seed)
    g = rng.random((freq, freq)).astype("float32")
    t = np.linspace(0, freq, size, endpoint=False).astype("float32")
    i0 = np.floor(t).astype(int) % freq
    i1 = (i0 + 1) % freq
    f = t - np.floor(t)
    f = f * f * (3 - 2 * f)                       # smoothstep
    a = g[np.ix_(i0, i0)]; b = g[np.ix_(i0, i1)]
    c = g[np.ix_(i1, i0)]; d = g[np.ix_(i1, i1)]
    top = a + (b - a) * f[None, :]
    bot = c + (d - c) * f[None, :]
    return top + (bot - top) * f[:, None]


def _fbm(size, freq, octaves, seed, gain=0.5):
    import numpy as np
    out = np.zeros((size, size), "float32"); amp = 1.0; tot = 0.0
    for o in range(octaves):
        out += amp * _tnoise(size, freq * (2 ** o), seed + o * 101)
        tot += amp; amp *= gain
    out /= tot
    return (out - out.min()) / max(float(out.max() - out.min()), 1e-6)


def _ramp(n, stops):
    """noise(0~1) → RGB. stops = [(t, '#rrggbb'), ...]"""
    import numpy as np
    ts = np.array([s[0] for s in stops], "float32")
    cs = np.array([[int(s[1][i:i + 2], 16) for i in (1, 3, 5)] for s in stops], "float32")
    out = np.zeros((*n.shape, 3), "float32")
    for ch in range(3):
        out[..., ch] = np.interp(n, ts, cs[:, ch])
    return out


def _wrap(im, fn):
    """타일 경계를 넘는 도형을 9번 그려 이음새를 없앤다."""
    d = ImageDraw.Draw(im, "RGBA")
    s = im.size[0]
    for oy in (-s, 0, s):
        for ox in (-s, 0, s):
            fn(d, ox, oy)


def _save_tex(arr_or_im, name):
    import numpy as np
    im = arr_or_im if isinstance(arr_or_im, Image.Image) else Image.fromarray(np.clip(arr_or_im, 0, 255).astype("uint8"), "RGB")
    TEX.mkdir(parents=True, exist_ok=True); TEXRAW.mkdir(parents=True, exist_ok=True)
    im.save(TEX / name, "PNG", optimize=True)
    # 2×2 타일링 확인 이미지(이음새 육안 검증용)
    chk = Image.new("RGB", (im.size[0] * 2, im.size[1] * 2))
    for gy in (0, 1):
        for gx in (0, 1):
            chk.paste(im, (gx * im.size[0], gy * im.size[1]))
    chk.save(TEXRAW / ("tilecheck_" + name), "PNG", optimize=True)
    print(f"tex  {name} {(TEX / name).stat().st_size // 1024}KB", flush=True)
    return im


def tex_grass(seed=8810):
    """풀: 초록(생명). 채도는 중간 — 네온 초록 금지(B2). 잎날이 보여야 '풀'로 읽힌다."""
    import numpy as np
    n = _fbm(TEXSIZE, 5, 5, seed)
    patch = _fbm(TEXSIZE, 2, 3, seed + 55)
    base = _ramp(n * 0.8 + patch * 0.2, [(0.0, "#3a5230"), (0.4, "#4a663a"), (0.72, "#5b8143"), (1.0, "#6b9550")])
    im = Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB")
    rnd = random.Random(seed)
    # 흙이 비치는 자리 먼저(잎날 아래로)
    dirt = [(rnd.random() * TEXSIZE, rnd.random() * TEXSIZE, rnd.uniform(10, 30)) for _ in range(22)]

    def draw_dirt(d, ox, oy):
        for x, y, r in dirt:
            d.ellipse((x + ox - r, y + oy - r * 0.7, x + ox + r, y + oy + r * 0.7), fill=(88, 80, 58, 70))
    _wrap(im, draw_dirt)
    im = im.filter(ImageFilter.GaussianBlur(1.2))       # 바탕만 부드럽게, 잎날은 이 뒤에
    # 잎날: 굽은 2점 선. 밝은 것 → 어두운 것 순으로 겹쳐 깊이를 만든다.
    blades = []
    for _ in range(5200):
        x, y = rnd.random() * TEXSIZE, rnd.random() * TEXSIZE
        h = rnd.uniform(7, 18); dx = rnd.uniform(-5, 5)
        c = rnd.choice([(138, 172, 92, 210), (102, 138, 68, 220), (72, 102, 52, 225),
                        (160, 182, 102, 170), (52, 78, 42, 230), (118, 150, 74, 215)])
        blades.append((x, y, dx, h, c))

    def draw_blades(d, ox, oy):
        for x, y, dx, h, c in blades:
            d.line((x + ox, y + oy, x + ox + dx * 0.35, y + oy - h * 0.6), fill=c, width=1)
            d.line((x + ox + dx * 0.35, y + oy - h * 0.6, x + ox + dx, y + oy - h), fill=c, width=1)
    _wrap(im, draw_blades)
    return _save_tex(im, "grass.png")


def tex_asphalt(seed=8820):
    """갈라진 아스팔트: 완전 무채색. 색은 뜻이 있을 때만 쓴다(B2)."""
    import numpy as np
    n = _fbm(TEXSIZE, 6, 5, seed)
    grain = _fbm(TEXSIZE, 64, 2, seed + 7)
    v = np.clip(n * 0.72 + grain * 0.28, 0, 1)
    g = 52 + v * 40                                   # 무채: R=G=B
    base = np.stack([g, g, g * 0.985], -1)            # 아주 미세한 한기만
    im = Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB")
    rnd = random.Random(seed)
    # 균열: 분기하는 폴리라인 (타일 경계를 넘어가도 9회 그리기로 이어진다)
    cracks = []
    for _ in range(14):
        x, y = rnd.random() * TEXSIZE, rnd.random() * TEXSIZE
        a = rnd.random() * 6.283
        for seg in range(rnd.randint(8, 22)):
            L = rnd.uniform(8, 26); a += rnd.uniform(-0.6, 0.6)
            nx, ny = x + math.cos(a) * L, y + math.sin(a) * L
            cracks.append((x, y, nx, ny, max(1, 3 - seg // 7)))
            x, y = nx, ny
            if rnd.random() < 0.12:
                a += rnd.choice([-1.1, 1.1])

    def draw_cracks(d, ox, oy):
        for x0, y0, x1, y1, w in cracks:
            d.line((x0 + ox, y0 + oy, x1 + ox, y1 + oy), fill=(24, 23, 22, 210), width=w + 1)
            d.line((x0 + ox, y0 + oy, x1 + ox, y1 + oy), fill=(16, 15, 14, 235), width=w)
    _wrap(im, draw_cracks)
    # 자갈·패임
    peb = [(rnd.random() * TEXSIZE, rnd.random() * TEXSIZE, rnd.uniform(1, 3.4), rnd.randint(-22, 26)) for _ in range(900)]

    def draw_peb(d, ox, oy):
        for x, y, r, dv in peb:
            c = 76 + dv
            d.ellipse((x + ox - r, y + oy - r, x + ox + r, y + oy + r), fill=(c, c, c, 120))
    _wrap(im, draw_peb)
    return _save_tex(im, "asphalt.png")


def tex_moss(seed=8830):
    """이끼: 어두운 초록. 그늘·물가에 깔린다(B9). 벨벳처럼 뭉치고 가장자리가 불규칙."""
    import numpy as np
    n = _fbm(TEXSIZE, 4, 5, seed)
    clump = _fbm(TEXSIZE, 9, 4, seed + 31)
    base = _ramp(n * 0.55 + clump * 0.45, [(0.0, "#1a2916"), (0.38, "#26391f"), (0.7, "#334c28"), (1.0, "#44623a")])
    im = Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB")
    rnd = random.Random(seed)
    # 뭉치: 원 하나가 아니라 작은 원 6~10개를 겹쳐 가장자리를 들쭉날쭉하게
    clumps = []
    for _ in range(140):
        cx, cy = rnd.random() * TEXSIZE, rnd.random() * TEXSIZE
        R = rnd.uniform(9, 26)
        light = rnd.random() < 0.45
        col = (62, 92, 48, 90) if light else (24, 38, 20, 105)
        lobes = [(cx + rnd.uniform(-R, R) * 0.6, cy + rnd.uniform(-R, R) * 0.6, rnd.uniform(R * 0.35, R * 0.7)) for _ in range(rnd.randint(6, 11))]
        clumps.append((lobes, col))

    def draw_clumps(d, ox, oy):
        for lobes, col in clumps:
            for x, y, r in lobes:
                d.ellipse((x + ox - r, y + oy - r, x + ox + r, y + oy + r), fill=col)
    _wrap(im, draw_clumps)
    im = im.filter(ImageFilter.GaussianBlur(1.0))
    # 짧은 이끼 솜털(잔디보다 훨씬 짧고 촘촘)
    fuzz = [(rnd.random() * TEXSIZE, rnd.random() * TEXSIZE, rnd.uniform(-2, 2), rnd.uniform(2, 5),
             rnd.choice([(74, 104, 54, 150), (52, 78, 40, 160), (92, 118, 60, 120)])) for _ in range(6000)]

    def draw_fuzz(d, ox, oy):
        for x, y, dx, h, c in fuzz:
            d.line((x + ox, y + oy, x + ox + dx, y + oy - h), fill=c, width=1)
    _wrap(im, draw_fuzz)
    return _save_tex(im, "moss.png")


def tex_water(seed=8840):
    """물: 청록 = 정원사의 색. 맑고 잔잔하다(B2·B10). 무늬가 세면 돌처럼 보이므로 약하게."""
    import numpy as np
    deep = _fbm(TEXSIZE, 2, 3, seed + 77)
    swell = _fbm(TEXSIZE, 4, 3, seed)
    fine = _fbm(TEXSIZE, 10, 3, seed + 13)
    base = _ramp(deep * 0.6 + swell * 0.4, [(0.0, "#1f6572"), (0.4, "#2b8391"), (0.75, "#3aa3a6"), (1.0, "#4dbcb4")])
    # 코스틱: 얇은 밝은 선 몇 겹만. 지수를 높여 선을 가늘게.
    caustic = np.abs(np.sin((swell * 0.85 + fine * 0.40) * 3.14159 * 2)) ** 9.0
    base += caustic[..., None] * np.array([44, 68, 66], "float32")
    im = Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB")
    return _save_tex(im.filter(ImageFilter.GaussianBlur(0.6)), "water.png")


def make_terrain_textures():
    tex_grass(); tex_asphalt(); tex_moss(); tex_water()
    print("TEXTURES DONE", flush=True)


# ── 후처리 ─────────────────────────────────────────────────────
def paper_texture(size, seed=7):
    """절차적 종이 텍스처: 저주파 얼룩 + 섬유 노이즈."""
    w, h = size
    rnd = random.Random(seed)
    base = Image.effect_noise((w // 2, h // 2), 28).resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))
    fib = Image.effect_noise((w, h), 14)
    tex = ImageChops.add(base, fib, scale=2.0)
    tex = ImageEnhance.Contrast(tex).enhance(0.35)
    return ImageOps.autocontrast(tex).convert("RGB")


def vignette(size, strength=0.55):
    w, h = size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((-w * 0.25, -h * 0.25, w * 1.25, h * 1.25), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(min(w, h) // 5))
    return Image.eval(m, lambda v: int(255 - (255 - v) * strength))


def post(src: Path, dst: Path, size):
    img = Image.open(src).convert("RGB")
    W, H = img.size
    img = img.crop((0, 0, W, int(H * 0.92)))                          # 하단 워터마크 제거
    img = ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.45))
    img = ImageEnhance.Color(img).enhance(0.72)                       # 채도 -28%
    img = ImageOps.autocontrast(img, cutoff=1)
    img = Image.blend(img, Image.new("RGB", size, (232, 223, 203)), 0.08)  # 종이색으로 살짝
    tex = paper_texture(size)
    img = Image.blend(img, ImageChops.multiply(img, tex), 0.22)        # 종이 텍스처 멀티플라이 (약하게)
    dark = ImageChops.multiply(img, Image.new("RGB", size, (60, 56, 50)))
    img = Image.composite(img, dark, vignette(size))                   # 비네트
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=3))
    img.save(dst, "JPEG", quality=86, optimize=True)


# ── 생성 ─────────────────────────────────────────────────────
def fetch(prompt, w, h, seed, dst: Path):
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
           + f"?width={w}&height={h}&seed={seed}&nologo=true&model=flux")
    for attempt in range(3):
        try:
            t = time.time()
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=200).read()
            if len(data) < 15000:
                raise RuntimeError(f"too small {len(data)}")
            dst.write_bytes(data)
            print(f"ok   {dst.name} {len(data)//1024}KB {time.time()-t:.0f}s", flush=True)
            return True
        except Exception as e:
            print(f"retry {dst.name} #{attempt+1}: {e}", flush=True)
            time.sleep(8)
    return False


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    post_only = "--post-only" in sys.argv
    if "--textures" in sys.argv:
        make_terrain_textures(); sys.exit(0)
    if not args or any(a in "earth" for a in args):
        make_earth(OUT / "earth.jpg")
    for rel, (prompt, w, h, seed) in JOBS.items():
        if args and not any(a in rel for a in args):
            continue
        raw, out = RAW / rel, OUT / rel
        if not raw.exists() or raw.stat().st_size < 15000:
            if post_only:
                continue
            if not fetch(prompt, w, h, seed, raw):
                continue
            time.sleep(2)
        post(raw, out, (w, h))
        print(f"post {out.relative_to(ROOT)}", flush=True)
    print("ALL DONE", flush=True)
