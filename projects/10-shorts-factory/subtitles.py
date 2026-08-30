# -*- coding: utf-8 -*-
"""PIL로 자막 PNG(투명 배경, 1080x1920)를 그린다. ffmpeg overlay 필터로 합성된다."""

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        try:
            _font_cache[size] = ImageFont.truetype(config.FONT_PATH, size)
        except OSError as e:
            raise RuntimeError(
                f"폰트를 열 수 없습니다: {config.FONT_PATH}\n"
                "config.py 의 FONT_PATH 를 설치된 한글 폰트로 바꾸세요."
            ) from e
    return _font_cache[size]


def wrap(text: str, max_chars: int) -> list[str]:
    """공백 우선 줄바꿈, 한 덩어리가 너무 길면 강제 분할."""
    lines, cur = [], ""
    for word in text.split(" "):
        cand = f"{cur} {word}".strip()
        if len(cand) <= max_chars or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)

    out: list[str] = []
    for ln in lines:
        while len(ln) > max_chars:
            out.append(ln[:max_chars])
            ln = ln[max_chars:]
        out.append(ln)
    return out


def _draw_block(draw, text, style, color):
    lines = wrap(text, style["max_chars"])
    line_h = int(style["size"] * 1.22)
    # 여러 줄이면 지정 y를 블록의 중심으로 삼는다
    top = style["y"] - (len(lines) - 1) * line_h // 2
    font = _font(style["size"])
    for i, ln in enumerate(lines):
        draw.text(
            (config.WIDTH // 2, top + i * line_h), ln,
            font=font, fill=color, anchor="mm",
            stroke_width=style["stroke"], stroke_fill=style["stroke_color"],
        )


def render_overlay(cut) -> Path | None:
    """컷의 대사/자막을 그린 PNG 경로. 그릴 게 없으면 None."""
    if not cut.line and not cut.caption:
        return None

    color = config.CHARACTERS.get(cut.speaker, {}).get("color", (255, 255, 255))
    key = f"{cut.line}|{cut.caption}|{cut.speaker}|{color}|{config.WIDTH}x{config.HEIGHT}"
    out = config.CACHE_DIR / f"sub_{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}.png"
    if out.exists():
        return out

    config.CACHE_DIR.mkdir(exist_ok=True)
    img = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if cut.caption:
        _draw_block(draw, cut.caption, config.CAPTION, config.CAPTION["color"])
    if cut.line:
        _draw_block(draw, cut.line, config.DIALOG, color)

    img.save(out)
    return out
