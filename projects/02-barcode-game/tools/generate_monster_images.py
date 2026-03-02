#!/usr/bin/env python3
"""
BarcodeQuest AI Image Generator
================================
pollinations.ai 를 사용하여 수채화 판타지 스타일(지브리풍)
몬스터/캐릭터 이미지 URL 매핑을 생성하고, 선택적으로 다운로드합니다.

사용법:
  python generate_monster_images.py                # URL 매핑 JSON 생성만
  python generate_monster_images.py --download     # JSON 생성 + 이미지 다운로드
  python generate_monster_images.py --characters   # 캐릭터만
  python generate_monster_images.py --monsters     # 몬스터만

생성되는 파일:
  artwork/image_urls.json  — 전체 이미지 URL 매핑 (HTML에서 참조)
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import argparse
from pathlib import Path

# ── 경로 설정 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
ARTWORK_DIR = BASE_DIR / "artwork"
MONSTERS_DIR = ARTWORK_DIR / "monsters"
CHARACTERS_DIR = ARTWORK_DIR / "named_characters"
URL_MAP_FILE = ARTWORK_DIR / "image_urls.json"

# ── pollinations.ai 설정 ──────────────────────────────────
IMAGE_WIDTH = 512
IMAGE_HEIGHT = 512
RATE_LIMIT_SECONDS = 3

# ── 스타일 프리픽스 ─────────────────────────────────────────
STYLE_PREFIX = (
    "Studio Ghibli watercolor fantasy art style, "
    "soft pastel colors, magical atmosphere, "
    "detailed hand-painted illustration, "
    "white background, centered character, full body, "
    "cute and expressive eyes, "
)
STYLE_SUFFIX = ", high quality, detailed, 4k, artstation"

# ── 10 몬스터 몸체 타입 ────────────────────────────────────
MONSTER_BODIES = [
    {"id": "dragon",    "name": "dragon",     "nameKr": "드래곤",     "prompt": "baby dragon creature, small wings, scales, long tail"},
    {"id": "slime",     "name": "slime",      "nameKr": "슬라임",     "prompt": "cute slime creature, translucent jelly body, bouncy, round shape"},
    {"id": "goblin",    "name": "goblin",     "nameKr": "고블린",     "prompt": "small goblin creature, pointy ears, mischievous smile, small horns"},
    {"id": "fairy",     "name": "fairy",      "nameKr": "페어리",     "prompt": "tiny fairy creature, butterfly wings, glowing aura, floating"},
    {"id": "golem",     "name": "golem",      "nameKr": "골렘",       "prompt": "small stone golem creature, mossy rocks, glowing rune eyes, sturdy"},
    {"id": "unicorn",   "name": "unicorn",    "nameKr": "유니콘",     "prompt": "baby unicorn creature, spiral horn, flowing mane, sparkles"},
    {"id": "phoenix",   "name": "phoenix",    "nameKr": "피닉스",     "prompt": "baby phoenix bird creature, flame feathers, glowing warmly"},
    {"id": "sprite",    "name": "sprite",     "nameKr": "스프라이트", "prompt": "tiny nature sprite creature, leaf clothing, twig antennae, playful"},
    {"id": "chimera",   "name": "chimera",    "nameKr": "키메라",     "prompt": "small chimera creature, mixed animal parts, fluffy, whimsical"},
    {"id": "wisp",      "name": "wisp",       "nameKr": "위스프",     "prompt": "glowing wisp creature, ethereal floating orb, trailing sparkles"},
]

# ── 10 속성 타입 ──────────────────────────────────────────
ELEMENTS = [
    {"id": "fire",    "name": "fire",    "nameKr": "불",   "prompt": "fire element, warm red-orange glow, small flames around body, ember particles"},
    {"id": "water",   "name": "water",   "nameKr": "물",   "prompt": "water element, blue aqua tones, water droplets, bubble effects"},
    {"id": "nature",  "name": "nature",  "nameKr": "자연", "prompt": "nature element, green leaves, flowers growing, vine accents"},
    {"id": "wind",    "name": "wind",    "nameKr": "바람", "prompt": "wind element, swirling air currents, feather-light, cloud wisps"},
    {"id": "spirit",  "name": "spirit",  "nameKr": "영혼", "prompt": "spirit element, ethereal purple glow, ghostly aura, mystical mist"},
    {"id": "light",   "name": "light",   "nameKr": "빛",   "prompt": "light element, golden radiance, sun rays, bright halo"},
    {"id": "dark",    "name": "dark",    "nameKr": "어둠", "prompt": "dark element, deep purple-black shadows, starry particles, mysterious"},
    {"id": "earth",   "name": "earth",   "nameKr": "대지", "prompt": "earth element, brown rocky textures, crystal accents, grounded"},
    {"id": "mech",    "name": "mech",    "nameKr": "기계", "prompt": "mechanical element, small gears, copper-bronze accents, steampunk"},
    {"id": "food",    "name": "food",    "nameKr": "음식", "prompt": "food element, candy and pastry accents, sweet frosting details, colorful sprinkles"},
]

# ── 10 네임드 캐릭터 ───────────────────────────────────────
NAMED_CHARACTERS = [
    {"id": "nabi",    "name": "나비",  "emoji": "butterfly", "prompt": "a beautiful butterfly spirit with damaged but healing wings, sitting in a flower garden, gentle and hopeful expression, bandaged wing"},
    {"id": "haru",    "name": "하루",  "emoji": "dog",       "prompt": "a loyal golden puppy with warm brown eyes, wagging tail, sitting faithfully, hopeful expression, slightly thin but happy"},
    {"id": "pori",    "name": "포리",  "emoji": "parrot",    "prompt": "a colorful parrot with vibrant feathers, singing happily, musical notes around, free from cage, joyful expression"},
    {"id": "miru",    "name": "미루",  "emoji": "cat",       "prompt": "a rain-soaked kitten with blue-grey fur, big expressive eyes, sitting near a book, slightly shy but curious"},
    {"id": "ggomi",   "name": "꼬미",  "emoji": "rabbit",    "prompt": "a fluffy white rabbit with long ears, touching grass for the first time, wonder in eyes, standing in a garden"},
    {"id": "rang",    "name": "랑이",  "emoji": "fox",       "prompt": "a wise red fox with an injured leg, gentle eyes looking at stars, bandaged paw, sitting on an observatory deck at night"},
    {"id": "byeori",  "name": "별이",  "emoji": "hamster",   "prompt": "a tiny golden hamster with big round eyes, cheeks full of seeds, sitting on a sunflower, cute and small"},
    {"id": "gureum",  "name": "구름",  "emoji": "cat2",      "prompt": "an elderly white cat with wise gentle eyes, fluffy cloud-like fur, sitting peacefully on a cushion, serene expression"},
    {"id": "dari",    "name": "달이",  "emoji": "owl",       "prompt": "a wise owl with one eye closed, moonlit feathers, perched on a branch under starry sky, dignified pose"},
    {"id": "sori",    "name": "솔이",  "emoji": "hedgehog",  "prompt": "a small hedgehog with cute spines, peeking out from autumn leaves, tiny paws, curious and gentle expression"},
]


def build_url(prompt: str, seed: int) -> str:
    """pollinations.ai 이미지 생성 URL"""
    full_prompt = STYLE_PREFIX + prompt + STYLE_SUFFIX
    encoded = urllib.parse.quote(full_prompt)
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={IMAGE_WIDTH}&height={IMAGE_HEIGHT}"
        f"&seed={seed}&nologo=true"
    )


def generate_url_map(do_chars: bool = True, do_monsters: bool = True) -> dict:
    """전체 이미지 URL 매핑을 생성합니다."""
    url_map = {"characters": {}, "monsters": {}, "meta": {
        "style": STYLE_PREFIX.strip(", "),
        "size": f"{IMAGE_WIDTH}x{IMAGE_HEIGHT}",
        "bodies": [b["id"] for b in MONSTER_BODIES],
        "elements": [e["id"] for e in ELEMENTS],
    }}

    if do_chars:
        for i, char in enumerate(NAMED_CHARACTERS):
            seed = 77000 + i
            url_map["characters"][char["id"]] = {
                "name": char["name"],
                "url": build_url(char["prompt"], seed),
                "seed": seed,
                "local": f"artwork/named_characters/{char['id']}.png",
            }

    if do_monsters:
        for bi, body in enumerate(MONSTER_BODIES):
            for ei, elem in enumerate(ELEMENTS):
                key = f"{body['id']}_{elem['id']}"
                seed = bi * 100 + ei + 42000
                prompt = f"{body['prompt']}, {elem['prompt']}"
                url_map["monsters"][key] = {
                    "body": body["id"],
                    "bodyKr": body["nameKr"],
                    "element": elem["id"],
                    "elementKr": elem["nameKr"],
                    "url": build_url(prompt, seed),
                    "seed": seed,
                    "local": f"artwork/monsters/{body['id']}_{elem['id']}.png",
                }

    return url_map


def download_image(url: str, filepath: Path, retries: int = 3) -> bool:
    """이미지 다운로드 (Cloudflare 530 시 실패할 수 있음)"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                if len(data) < 1024:
                    print(f"  [!] Too small ({len(data)}B), retry {attempt+1}/{retries}")
                    time.sleep(5)
                    continue
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(data)
                print(f"  [OK] {filepath.name} ({len(data)//1024}KB)")
                return True
        except Exception as e:
            print(f"  [FAIL] attempt {attempt+1}/{retries}: {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return False


def download_all(url_map: dict, do_chars: bool, do_monsters: bool):
    """매핑된 URL에서 이미지를 다운로드합니다."""
    success = fail = skip = 0

    if do_chars:
        print("\n--- Characters ---")
        for cid, info in url_map["characters"].items():
            fp = BASE_DIR / info["local"]
            if fp.exists() and fp.stat().st_size > 1024:
                print(f"  [SKIP] {cid}.png")
                skip += 1
                continue
            print(f"  Downloading {cid}.png ...")
            if download_image(info["url"], fp):
                success += 1
            else:
                fail += 1
            time.sleep(RATE_LIMIT_SECONDS)

    if do_monsters:
        print("\n--- Monsters ---")
        for key, info in url_map["monsters"].items():
            fp = BASE_DIR / info["local"]
            if fp.exists() and fp.stat().st_size > 1024:
                print(f"  [SKIP] {key}.png")
                skip += 1
                continue
            print(f"  Downloading {key}.png ...")
            if download_image(info["url"], fp):
                success += 1
            else:
                fail += 1
            time.sleep(RATE_LIMIT_SECONDS)

    print(f"\nDownload: {success} OK, {skip} skipped, {fail} failed")


def main():
    parser = argparse.ArgumentParser(description="BarcodeQuest AI Image Generator")
    parser.add_argument("--download", action="store_true", help="Download images (default: URL map only)")
    parser.add_argument("--characters", action="store_true", help="Characters only")
    parser.add_argument("--monsters", action="store_true", help="Monsters only")
    args = parser.parse_args()

    do_chars = args.characters or (not args.characters and not args.monsters)
    do_monsters = args.monsters or (not args.characters and not args.monsters)

    ARTWORK_DIR.mkdir(parents=True, exist_ok=True)
    MONSTERS_DIR.mkdir(parents=True, exist_ok=True)
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)

    # 항상 URL 매핑 생성
    url_map = generate_url_map(do_chars, do_monsters)
    URL_MAP_FILE.write_text(json.dumps(url_map, ensure_ascii=False, indent=2), encoding="utf-8")
    n_chars = len(url_map["characters"])
    n_mons = len(url_map["monsters"])
    print(f"URL map saved: {URL_MAP_FILE}")
    print(f"  Characters: {n_chars}, Monsters: {n_mons}, Total: {n_chars + n_mons}")

    if args.download:
        download_all(url_map, do_chars, do_monsters)


if __name__ == "__main__":
    main()
