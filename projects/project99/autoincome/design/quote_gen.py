"""Quote Art Print Generator - Creates typography-based quote designs."""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from autoincome.config import PALETTES, SIZES, FONTS, QUOTES


def _wrap_text(text, font, max_width, draw):
    """Word-wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def _get_text_height(lines, font, draw, line_spacing=1.4):
    """Calculate total height of wrapped text."""
    total = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        total += int((bbox[3] - bbox[1]) * line_spacing)
    return total


def generate_classic_quote(quote_text, author, palette_name, size_name="print_8x10", seed=None):
    """Classic centered quote with elegant typography."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    w, h = SIZES[size_name]

    # Choose dark or light background
    use_dark = random.random() > 0.4
    bg = palette["bg_dark"] if use_dark else palette["bg_light"]
    text_color = palette["bg_light"] if use_dark else palette["bg_dark"]
    accent = random.choice(palette["colors"])

    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    # Font selection
    quote_font_key = random.choice(["serif_bold", "book_bold", "classic_bold"])
    author_font_key = random.choice(["sans_regular", "modern_regular", "modern_light"])

    margin = int(w * 0.12)
    max_text_width = w - 2 * margin

    # Try different font sizes
    for font_size in range(int(w * 0.06), int(w * 0.025), -2):
        try:
            quote_font = ImageFont.truetype(str(FONTS[quote_font_key]), font_size)
        except (IOError, OSError):
            quote_font = ImageFont.truetype(str(FONTS["arial_bold"]), font_size)

        lines = _wrap_text(quote_text, quote_font, max_text_width, draw)
        text_h = _get_text_height(lines, quote_font, draw)
        if text_h < h * 0.5:
            break

    author_size = max(int(font_size * 0.5), 16)
    try:
        author_font = ImageFont.truetype(str(FONTS[author_font_key]), author_size)
    except (IOError, OSError):
        author_font = ImageFont.truetype(str(FONTS["arial"]), author_size)

    # Draw decorative elements
    deco_style = random.choice(["line", "quotes", "border", "none"])
    if deco_style == "line":
        line_y = int(h * 0.35)
        line_w = int(w * 0.15)
        draw.line([(w // 2 - line_w, line_y), (w // 2 + line_w, line_y)],
                  fill=accent, width=max(2, w // 400))
    elif deco_style == "border":
        bw = max(3, w // 200)
        inset = int(w * 0.06)
        draw.rectangle([inset, inset, w - inset, h - inset], outline=accent, width=bw)
    elif deco_style == "quotes":
        big_font_size = int(font_size * 3)
        try:
            big_font = ImageFont.truetype(str(FONTS["serif_bold"]), big_font_size)
        except (IOError, OSError):
            big_font = ImageFont.truetype(str(FONTS["arial_bold"]), big_font_size)
        # Draw large quotation mark
        q_color = accent + (60,) if len(accent) == 3 else accent
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.text((margin, int(h * 0.2)), "\u201C", font=big_font,
                    fill=(*accent, 50))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Calculate vertical centering
    total_content_h = text_h + int(h * 0.08) + author_size
    start_y = (h - total_content_h) // 2

    # Draw quote text
    line_spacing = 1.4
    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        draw.text((x, y), line, font=quote_font, fill=text_color)
        y += int((bbox[3] - bbox[1]) * line_spacing)

    # Draw author
    y += int(h * 0.04)
    author_text = f"- {author}" if author != "Unknown" else ""
    if author_text:
        bbox = draw.textbbox((0, 0), author_text, font=author_font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        draw.text((x, y), author_text, font=author_font, fill=accent)

    return img


def generate_modern_quote(quote_text, author, palette_name, size_name="print_8x10", seed=None):
    """Modern/minimal quote with bold typography and accent elements."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    w, h = SIZES[size_name]
    colors = palette["colors"]

    bg = palette["bg_light"]
    text_color = palette["bg_dark"]
    accent = random.choice(colors)

    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    # Add accent block
    block_style = random.choice(["top_bar", "side_bar", "corner_square", "circle_bg"])

    if block_style == "top_bar":
        bar_h = int(h * random.uniform(0.02, 0.05))
        draw.rectangle([0, 0, w, bar_h], fill=accent)
    elif block_style == "side_bar":
        bar_w = int(w * random.uniform(0.015, 0.03))
        bar_start = int(h * 0.2)
        bar_end = int(h * 0.8)
        draw.rectangle([int(w * 0.08), bar_start, int(w * 0.08) + bar_w, bar_end], fill=accent)
    elif block_style == "corner_square":
        sq = int(min(w, h) * 0.15)
        draw.rectangle([w - sq - int(w * 0.05), int(h * 0.05),
                         w - int(w * 0.05), int(h * 0.05) + sq], fill=accent)
    elif block_style == "circle_bg":
        r = int(min(w, h) * 0.3)
        cx = int(w * random.uniform(0.6, 0.85))
        cy = int(h * random.uniform(0.3, 0.7))
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*accent, 30))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Text
    margin = int(w * 0.12)
    max_text_width = w - 2 * margin

    font_key = random.choice(["sans_bold", "modern_bold", "verdana_bold"])
    for font_size in range(int(w * 0.055), int(w * 0.02), -2):
        try:
            quote_font = ImageFont.truetype(str(FONTS[font_key]), font_size)
        except (IOError, OSError):
            quote_font = ImageFont.truetype(str(FONTS["arial_bold"]), font_size)
        lines = _wrap_text(quote_text, quote_font, max_text_width, draw)
        text_h = _get_text_height(lines, quote_font, draw)
        if text_h < h * 0.45:
            break

    author_size = max(int(font_size * 0.45), 14)
    try:
        author_font = ImageFont.truetype(str(FONTS["modern_light"]), author_size)
    except (IOError, OSError):
        author_font = ImageFont.truetype(str(FONTS["arial"]), author_size)

    # Left-aligned text
    total_h = text_h + int(h * 0.06) + author_size
    y = (h - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        draw.text((margin, y), line, font=quote_font, fill=text_color)
        y += int((bbox[3] - bbox[1]) * 1.35)

    y += int(h * 0.03)
    if author != "Unknown":
        author_text = author.upper()
        draw.text((margin, y), author_text, font=author_font, fill=accent)

    return img


def generate_gradient_quote(quote_text, author, palette_name, size_name="print_8x10", seed=None):
    """Quote on a gradient background with white text."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    w, h = SIZES[size_name]
    colors = palette["colors"]

    # Create gradient background
    from autoincome.design.wallpaper_gen import _fast_gradient
    selected = random.sample(colors, min(3, len(colors)))
    img = Image.new("RGB", (w, h))
    direction = random.choice(["vertical", "diagonal"])
    img = _fast_gradient(img, selected, direction)

    # Darken slightly for text readability
    dark_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 80))
    img = Image.alpha_composite(img.convert("RGBA"), dark_overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    text_color = (255, 255, 255)

    margin = int(w * 0.12)
    max_text_width = w - 2 * margin

    font_key = random.choice(["serif_bold", "book_bold", "sans_bold"])
    for font_size in range(int(w * 0.06), int(w * 0.025), -2):
        try:
            quote_font = ImageFont.truetype(str(FONTS[font_key]), font_size)
        except (IOError, OSError):
            quote_font = ImageFont.truetype(str(FONTS["arial_bold"]), font_size)
        lines = _wrap_text(quote_text, quote_font, max_text_width, draw)
        text_h = _get_text_height(lines, quote_font, draw)
        if text_h < h * 0.45:
            break

    author_size = max(int(font_size * 0.5), 14)
    try:
        author_font = ImageFont.truetype(str(FONTS["modern_light"]), author_size)
    except (IOError, OSError):
        author_font = ImageFont.truetype(str(FONTS["arial"]), author_size)

    # Center text
    total_h = text_h + int(h * 0.06) + author_size
    y = (h - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        draw.text((x, y), line, font=quote_font, fill=text_color)
        y += int((bbox[3] - bbox[1]) * 1.4)

    y += int(h * 0.03)
    if author != "Unknown":
        author_text = f"- {author}"
        bbox = draw.textbbox((0, 0), author_text, font=author_font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        draw.text((x, y), author_text, font=author_font, fill=(255, 255, 255, 200))

    return img


def generate_quotes(palette_name, output_dir, count=2, size_names=None, seed_base=None):
    """Generate a batch of quote art prints."""
    if size_names is None:
        size_names = ["print_8x10"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    generators = [
        ("classic", generate_classic_quote),
        ("modern", generate_modern_quote),
        ("gradient", generate_gradient_quote),
    ]

    quotes_pool = list(QUOTES)
    random.shuffle(quotes_pool)

    for i in range(count):
        quote_text, author = quotes_pool[i % len(quotes_pool)]
        gen_name, gen_func = generators[i % len(generators)]
        seed = (seed_base or 0) + i if seed_base is not None else None

        for size_name in size_names:
            img = gen_func(quote_text, author, palette_name, size_name, seed=seed)
            safe_quote = quote_text[:30].replace(" ", "_").replace(".", "").replace(",", "")
            fname = f"quote_{palette_name}_{gen_name}_{i:03d}_{size_name}.png"
            fpath = output_dir / fname
            img.save(fpath, "PNG", optimize=True)
            generated.append({
                "file": str(fpath),
                "type": "quote_print",
                "style": gen_name,
                "palette": palette_name,
                "size": size_name,
                "quote": quote_text,
                "author": author,
                "dimensions": SIZES[size_name],
            })

    return generated
