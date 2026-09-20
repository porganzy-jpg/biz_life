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
