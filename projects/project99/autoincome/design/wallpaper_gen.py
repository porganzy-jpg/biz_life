"""Wallpaper Generator - Creates gradient, abstract, and minimalist wallpapers."""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

from autoincome.config import PALETTES, SIZES


def _lerp_color(c1, c2, t):
    """Linear interpolation between two RGB colors."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _multi_gradient(draw, width, height, colors, angle=0):
    """Draw a smooth multi-stop gradient."""
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    # Project corners onto gradient axis to find range
    corners = [(0, 0), (width, 0), (0, height), (width, height)]
    projections = [x * cos_a + y * sin_a for x, y in corners]
    min_proj, max_proj = min(projections), max(projections)
    total = max_proj - min_proj if max_proj != min_proj else 1

    n_stops = len(colors)
    for y in range(height):
        for x in range(0, width, 2):  # Step by 2 for speed
            proj = (x * cos_a + y * sin_a - min_proj) / total
            proj = max(0, min(1, proj))

            seg = proj * (n_stops - 1)
            idx = min(int(seg), n_stops - 2)
            local_t = seg - idx
            color = _lerp_color(colors[idx], colors[idx + 1], local_t)
            draw.rectangle([x, y, x + 1, y], fill=color)


def _fast_gradient(img, colors, direction="vertical"):
    """Fast gradient using line-by-line drawing."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    n = len(colors)

    if direction == "vertical":
        for y in range(h):
            t = y / max(h - 1, 1)
            seg = t * (n - 1)
            idx = min(int(seg), n - 2)
            lt = seg - idx
            c = _lerp_color(colors[idx], colors[idx + 1], lt)
            draw.line([(0, y), (w, y)], fill=c)
    elif direction == "horizontal":
        for x in range(w):
            t = x / max(w - 1, 1)
            seg = t * (n - 1)
            idx = min(int(seg), n - 2)
            lt = seg - idx
            c = _lerp_color(colors[idx], colors[idx + 1], lt)
            draw.line([(x, 0), (x, h)], fill=c)
    elif direction == "diagonal":
        _multi_gradient(draw, w, h, colors, angle=45)
    elif direction == "radial":
        cx, cy = w // 2, h // 2
        max_dist = math.sqrt(cx * cx + cy * cy)
        for y in range(h):
            for x in range(0, w, 3):
                dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_dist
                dist = min(dist, 1.0)
                seg = dist * (n - 1)
                idx = min(int(seg), n - 2)
                lt = seg - idx
                c = _lerp_color(colors[idx], colors[idx + 1], lt)
                draw.rectangle([x, y, x + 2, y], fill=c)

    return img


def generate_gradient_wallpaper(palette_name, size_name="phone", direction=None, seed=None):
    """Generate a smooth gradient wallpaper."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    w, h = SIZES[size_name]
    colors = palette["colors"]

    # Pick 2-4 colors from palette
    n_colors = random.randint(2, min(4, len(colors)))
    selected = random.sample(colors, n_colors)

    if direction is None:
        direction = random.choice(["vertical", "horizontal", "diagonal"])

    img = Image.new("RGB", (w, h))
    img = _fast_gradient(img, selected, direction)

    # Optional: slight blur for smoothness
    img = img.filter(ImageFilter.GaussianBlur(radius=2))

    return img


def generate_abstract_wallpaper(palette_name, size_name="phone", seed=None):
    """Generate abstract wallpaper with geometric shapes on gradient."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    w, h = SIZES[size_name]
    colors = palette["colors"]

    # Base gradient
    bg_colors = random.sample(colors, min(3, len(colors)))
    img = Image.new("RGB", (w, h))
    img = _fast_gradient(img, bg_colors, random.choice(["vertical", "diagonal"]))

    draw = ImageDraw.Draw(img)

    # Add abstract shapes
    n_shapes = random.randint(5, 15)
    for _ in range(n_shapes):
        shape_type = random.choice(["circle", "line", "rect"])
        color = random.choice(colors)
        alpha_color = color + (random.randint(30, 120),)

        # Create overlay for transparency
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)

        if shape_type == "circle":
            r = random.randint(w // 20, w // 3)
            cx = random.randint(-r, w + r)
            cy = random.randint(-r, h + r)
            odraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=alpha_color)
        elif shape_type == "line":
            x1 = random.randint(0, w)
            y1 = random.randint(0, h)
            x2 = random.randint(0, w)
            y2 = random.randint(0, h)
            line_w = random.randint(2, max(3, w // 50))
            odraw.line([(x1, y1), (x2, y2)], fill=alpha_color, width=line_w)
        elif shape_type == "rect":
            x1 = random.randint(0, w)
            y1 = random.randint(0, h)
            rw = random.randint(w // 15, w // 3)
            rh = random.randint(h // 15, h // 3)
            odraw.rectangle([x1, y1, x1 + rw, y1 + rh], fill=alpha_color)

        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    img = img.filter(ImageFilter.GaussianBlur(radius=3))
    return img


def generate_minimalist_wallpaper(palette_name, size_name="phone", seed=None):
    """Generate minimalist wallpaper with clean geometric elements."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    w, h = SIZES[size_name]
    colors = palette["colors"]

    style = random.choice(["split", "circle_center", "stripe", "corner_arc"])

    bg = random.choice([palette["bg_dark"], palette["bg_light"]])
    accent = random.choice(colors)

    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    if style == "split":
        # Clean horizontal or vertical split
        if random.random() > 0.5:
            split_y = int(h * random.uniform(0.3, 0.7))
            draw.rectangle([0, split_y, w, h], fill=accent)
        else:
            split_x = int(w * random.uniform(0.3, 0.7))
            draw.rectangle([split_x, 0, w, h], fill=accent)

    elif style == "circle_center":
        r = min(w, h) // random.randint(3, 6)
        cx, cy = w // 2, h // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent)

    elif style == "stripe":
        n_stripes = random.randint(3, 8)
        stripe_w = w // n_stripes
        for i in range(0, n_stripes, 2):
            c = random.choice(colors)
            draw.rectangle([i * stripe_w, 0, (i + 1) * stripe_w, h], fill=c)

    elif style == "corner_arc":
        r = min(w, h) * random.uniform(0.5, 1.2)
        corner = random.choice(["tl", "tr", "bl", "br"])
        if corner == "tl":
            draw.ellipse([-r, -r, r, r], fill=accent)
        elif corner == "tr":
            draw.ellipse([w - r, -r, w + r, r], fill=accent)
        elif corner == "bl":
            draw.ellipse([-r, h - r, r, h + r], fill=accent)
        elif corner == "br":
            draw.ellipse([w - r, h - r, w + r, h + r], fill=accent)

    return img


def generate_wallpapers(palette_name, output_dir, count=3, size_names=None, seed_base=None):
    """Generate a batch of wallpapers in multiple sizes."""
    if size_names is None:
        size_names = ["phone", "desktop"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    generators = [
        ("gradient", generate_gradient_wallpaper),
        ("abstract", generate_abstract_wallpaper),
        ("minimalist", generate_minimalist_wallpaper),
    ]

    for i in range(count):
        gen_name, gen_func = generators[i % len(generators)]
        seed = (seed_base or 0) + i if seed_base is not None else None

        for size_name in size_names:
            img = gen_func(palette_name, size_name, seed=seed)
            fname = f"wallpaper_{palette_name}_{gen_name}_{i:03d}_{size_name}.png"
            fpath = output_dir / fname
            img.save(fpath, "PNG", optimize=True)
            generated.append({
                "file": str(fpath),
                "type": "wallpaper",
                "style": gen_name,
                "palette": palette_name,
                "size": size_name,
                "dimensions": SIZES[size_name],
            })

    return generated
