"""POD (Print-on-Demand) Design Generator - T-shirt, mug, phone case designs."""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from autoincome.config import PALETTES, SIZES, FONTS


# POD text phrases by category
POD_PHRASES = {
    "funny": [
        "I'm not lazy\nI'm on energy\nsaving mode",
        "Running on\ncoffee and\nsarcasm",
        "I speak fluent\nsarcasm",
        "Nap Queen",
        "But first,\ncoffee",
        "Weekend\nVibes Only",
        "Zero Fox\nGiven",
        "This is my\n\"I don't care\"\noutfit",
        "Professional\nOverthinking",
        "Powered by\nCaffeine",
    ],
    "motivational": [
        "NEVER\nGIVE UP",
        "DREAM\nBIG",
        "STAY\nHUNGRY\nSTAY\nFOOLISH",
        "JUST\nDO IT\nTODAY",
        "RISE\nAND\nGRIND",
        "HUSTLE",
        "FEARLESS",
        "BE BOLD",
        "LIMITLESS",
        "UNSTOPPABLE",
    ],
    "profession": [
        "TRUST ME\nI'M AN\nENGINEER",
        "World's Okayest\nDeveloper",
        "EAT\nSLEEP\nCODE\nREPEAT",
        "Fueled by\nCode & Coffee",
        "NURSE\nLife",
        "Teacher Mode\nON",
        "CHEF\nat work",
        "Proud to be a\nFIREFIGHTER",
        "DOCTOR\nin progress",
        "ARTIST\nat heart",
    ],
    "minimal": [
        "BREATHE",
        "BE KIND",
        "GRATEFUL",
        "PEACE",
        "LOVE",
        "WANDERLUST",
        "ADVENTURE\nAWAITS",
        "EXPLORE",
        "WILD\n&\nFREE",
        "BLOOM",
    ],
}


def generate_text_pod(phrase, palette_name, style="bold", seed=None):
    """Generate a text-based POD design with transparent background."""
    if seed is not None:
        random.seed(seed)

    w, h = SIZES["pod_tshirt"]
    palette = PALETTES[palette_name]
    colors = palette["colors"]

    # Transparent background for POD
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    lines = phrase.split("\n")
    text_color = random.choice(colors)

    if style == "bold":
        font_key = random.choice(["display_bold", "arial_bold", "verdana_bold"])
    elif style == "elegant":
        font_key = random.choice(["serif_bold", "book_bold", "classic_bold"])
    elif style == "modern":
        font_key = random.choice(["sans_bold", "modern_bold", "trebuchet"])
    else:
        font_key = "arial_bold"

    # Find best font size
    margin = int(w * 0.15)
    max_text_width = w - 2 * margin

    for font_size in range(int(w * 0.08), int(w * 0.02), -4):
        try:
            font = ImageFont.truetype(str(FONTS[font_key]), font_size)
        except (IOError, OSError):
            font = ImageFont.truetype(str(FONTS["arial_bold"]), font_size)

        max_line_w = 0
        total_h = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            max_line_w = max(max_line_w, lw)
            total_h += int(lh * 1.3)

        if max_line_w <= max_text_width and total_h <= h * 0.6:
            break

    # Draw text centered
    total_h = 0
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lh = bbox[3] - bbox[1]
        line_heights.append(lh)
        total_h += int(lh * 1.3)

    y = (h - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (w - lw) // 2
        draw.text((x, y), line, font=font, fill=text_color)
        y += int(line_heights[i] * 1.3)

    return img


def generate_badge_pod(phrase, palette_name, seed=None):
    """Generate a badge/stamp style POD design."""
    if seed is not None:
        random.seed(seed)

    w, h = SIZES["pod_tshirt"]
    palette = PALETTES[palette_name]
    colors = palette["colors"]

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    color = random.choice(colors)
    cx, cy = w // 2, h // 2

    badge_type = random.choice(["circle", "rounded_rect", "shield"])
    r = int(min(w, h) * 0.3)

    if badge_type == "circle":
        # Outer circle
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=max(4, r // 15))
        # Inner circle
        inner_r = int(r * 0.88)
        draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
                     outline=color, width=max(2, r // 30))

    elif badge_type == "rounded_rect":
        rr = r // 5
        x1, y1 = cx - r, cy - int(r * 0.7)
        x2, y2 = cx + r, cy + int(r * 0.7)
        draw.rounded_rectangle([x1, y1, x2, y2], radius=rr, outline=color,
                               width=max(4, r // 15))
        # Inner
        m = int(r * 0.08)
        draw.rounded_rectangle([x1 + m, y1 + m, x2 - m, y2 - m], radius=rr - m,
                               outline=color, width=max(2, r // 30))

    elif badge_type == "shield":
        # Shield shape
        points = [
            (cx - r, cy - r),
            (cx + r, cy - r),
            (cx + r, cy),
            (cx, cy + r),
            (cx - r, cy),
        ]
        draw.polygon(points, outline=color, fill=None)
        draw.line(points + [points[0]], fill=color, width=max(4, r // 15))

    # Add text inside badge
    lines = phrase.split("\n")
    main_text = lines[0] if lines else phrase

    for font_size in range(int(r * 0.5), int(r * 0.1), -4):
        try:
            font = ImageFont.truetype(str(FONTS["arial_bold"]), font_size)
        except (IOError, OSError):
            font = ImageFont.truetype(str(FONTS["arial"]), font_size)

        bbox = draw.textbbox((0, 0), main_text, font=font)
        tw = bbox[2] - bbox[0]
        if tw <= r * 1.4:
            break

    # Draw lines
    total_lines = len(lines)
    small_font_size = max(int(font_size * 0.6), 14)
    try:
        small_font = ImageFont.truetype(str(FONTS["arial"]), small_font_size)
    except (IOError, OSError):
        small_font = ImageFont.truetype(str(FONTS["arial"]), small_font_size)

    line_h = int(font_size * 1.3)
    total_h = line_h * total_lines
    start_y = cy - total_h // 2

    for i, line in enumerate(lines):
        f = font if i == 0 or len(lines) <= 2 else small_font
        bbox = draw.textbbox((0, 0), line, font=f)
        tw = bbox[2] - bbox[0]
        x = cx - tw // 2
        draw.text((x, start_y + i * line_h), line, font=f, fill=color)

    return img


def generate_icon_text_pod(phrase, palette_name, seed=None):
    """Generate a design with a simple icon/shape above text."""
    if seed is not None:
        random.seed(seed)

    w, h = SIZES["pod_tshirt"]
    palette = PALETTES[palette_name]
    colors = palette["colors"]

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    color = random.choice(colors)
    cx = w // 2

    # Draw simple icon
    icon = random.choice(["heart", "star", "lightning", "mountain", "sun"])
    icon_size = int(min(w, h) * 0.12)
    icon_y = int(h * 0.3)

    if icon == "heart":
        # Simple heart
        r = icon_size // 2
        draw.ellipse([cx - r - r // 2, icon_y - r, cx - r // 2, icon_y + r], fill=color)
        draw.ellipse([cx + r // 2 - r, icon_y - r, cx + r // 2, icon_y + r], fill=color)
        draw.polygon([(cx - icon_size // 2 - r // 4, icon_y + r // 3),
                       (cx, icon_y + icon_size),
                       (cx + icon_size // 2 + r // 4, icon_y + r // 3)], fill=color)

    elif icon == "star":
        points = []
        for i in range(5):
            outer_a = math.radians(72 * i - 90)
            inner_a = math.radians(72 * i - 90 + 36)
            points.append((cx + int(icon_size * math.cos(outer_a)),
                           icon_y + int(icon_size * math.sin(outer_a))))
            points.append((cx + int(icon_size * 0.4 * math.cos(inner_a)),
                           icon_y + int(icon_size * 0.4 * math.sin(inner_a))))
        draw.polygon(points, fill=color)

    elif icon == "lightning":
        points = [
            (cx, icon_y - icon_size),
            (cx - icon_size // 3, icon_y),
            (cx + icon_size // 6, icon_y - icon_size // 8),
            (cx, icon_y + icon_size),
            (cx + icon_size // 3, icon_y),
            (cx - icon_size // 6, icon_y + icon_size // 8),
        ]
        draw.polygon(points, fill=color)

    elif icon == "mountain":
        base_y = icon_y + icon_size
        draw.polygon([
            (cx - icon_size, base_y),
            (cx, icon_y - icon_size // 2),
            (cx + icon_size, base_y),
        ], fill=color)

    elif icon == "sun":
        r = icon_size // 2
        draw.ellipse([cx - r, icon_y - r, cx + r, icon_y + r], fill=color)
        for angle in range(0, 360, 45):
            a = math.radians(angle)
            x1 = cx + int(r * 1.4 * math.cos(a))
            y1 = icon_y + int(r * 1.4 * math.sin(a))
            x2 = cx + int(r * 1.8 * math.cos(a))
            y2 = icon_y + int(r * 1.8 * math.sin(a))
            draw.line([(x1, y1), (x2, y2)], fill=color, width=max(3, r // 6))

    # Text below icon
    text_y = icon_y + icon_size + int(h * 0.08)
    lines = phrase.split("\n")

    for font_size in range(int(w * 0.06), int(w * 0.02), -4):
        try:
            font = ImageFont.truetype(str(FONTS["sans_bold"]), font_size)
        except (IOError, OSError):
            font = ImageFont.truetype(str(FONTS["arial_bold"]), font_size)

        max_lw = max(draw.textbbox((0, 0), l, font=font)[2] for l in lines)
        if max_lw <= w * 0.7:
            break

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = cx - tw // 2
        draw.text((x, text_y + i * int(th * 1.3)), line, font=font, fill=color)

    return img


def generate_pod_designs(palette_name, output_dir, count=1, category=None, seed_base=None):
    """Generate a batch of POD designs."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    if category is None:
        category = random.choice(list(POD_PHRASES.keys()))

    phrases = list(POD_PHRASES.get(category, POD_PHRASES["motivational"]))
    random.shuffle(phrases)

    generators = [
        ("text_bold", lambda p, pal, s: generate_text_pod(p, pal, "bold", s)),
        ("text_elegant", lambda p, pal, s: generate_text_pod(p, pal, "elegant", s)),
        ("badge", generate_badge_pod),
        ("icon_text", generate_icon_text_pod),
    ]

    for i in range(count):
        phrase = phrases[i % len(phrases)]
        gen_name, gen_func = generators[i % len(generators)]
        seed = (seed_base or 0) + i if seed_base is not None else None

        img = gen_func(phrase, palette_name, seed)
        safe_phrase = phrase.split("\n")[0][:20].replace(" ", "_").replace("'", "")
        fname = f"pod_{palette_name}_{category}_{gen_name}_{i:03d}.png"
        fpath = output_dir / fname
        img.save(fpath, "PNG", optimize=True)

        generated.append({
            "file": str(fpath),
            "type": "pod_design",
            "style": gen_name,
            "category": category,
            "palette": palette_name,
            "phrase": phrase,
            "dimensions": SIZES["pod_tshirt"],
        })

    return generated
