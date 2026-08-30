# -*- coding: utf-8 -*-
"""촬영 전 임시 화면(스토리보드 카드)을 그린다.

clips/ 에 실제 영상이 없는 컷에 들어간다. 검은 화면보다 훨씬 낫다 -
어느 컷에 어떤 그림이 필요한지 보면서 대사 리듬과 이야기 흐름을 판단할 수 있다.
대각선 줄무늬는 "이건 아직 임시"라는 표시. 실제 클립이 들어오면 자동으로 사라진다.
"""

import hashlib

from PIL import Image, ImageDraw

import config
import subtitles

# 화자별 배경색. 까뮈는 검은 개, 바위는 회색 개라 톤을 맞춰둠
BG = {
    "까뮈": (27, 31, 42),
    "바위": (58, 63, 69),
    "":     (16, 16, 16),
}
STRIPE = (255, 255, 255, 8)
LABEL = (255, 255, 255, 90)


def render_card(cut):
    """컷 하나의 스토리보드 카드 PNG 경로."""
    key = f"card|{cut.no}|{cut.clip}|{cut.speaker}|{config.WIDTH}x{config.HEIGHT}"
    out = config.CACHE_DIR / f"card_{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}.png"
    if out.exists():
        return out

    config.CACHE_DIR.mkdir(exist_ok=True)
    img = Image.new("RGB", (config.WIDTH, config.HEIGHT), BG.get(cut.speaker, BG[""]))

    # 임시 표시용 대각선 줄무늬
    stripes = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(stripes)
    for x in range(-config.HEIGHT, config.WIDTH, 90):
        sd.line([(x, 0), (x + config.HEIGHT, config.HEIGHT)], fill=STRIPE, width=34)
    img = Image.alpha_composite(img.convert("RGBA"), stripes).convert("RGB")

    d = ImageDraw.Draw(img)
    cx, mid = config.WIDTH // 2, config.HEIGHT // 2

    d.text((cx, mid - 210), f"CUT {cut.no:02d}", font=subtitles._font(46),
           fill=LABEL[:3], anchor="mm")

    # 클립 파일명 - 이 컷에 무슨 그림이 필요한지
    name = cut.clip or "(화면 없음)"
    lines = subtitles.wrap(name.replace("_", " "), 15)
    for i, ln in enumerate(lines):
        d.text((cx, mid - 40 + i * 76), ln, font=subtitles._font(62),
               fill=(235, 235, 235), anchor="mm")

    if cut.speaker:
        y = mid + 130 + (len(lines) - 1) * 76
        color = config.CHARACTERS.get(cut.speaker, {}).get("color", (255, 255, 255))
        d.text((cx, y), cut.speaker, font=subtitles._font(50), fill=color, anchor="mm")

    d.text((cx, config.HEIGHT - 90), "촬영 전 임시 화면", font=subtitles._font(34),
           fill=LABEL[:3], anchor="mm")

    img.save(out)
    return out
