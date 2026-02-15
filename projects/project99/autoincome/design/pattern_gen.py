"""Seamless Pattern Generator - Creates tileable patterns for digital products."""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw

from autoincome.config import PALETTES, SIZES


def generate_polka_dot_pattern(palette_name, size=600, seed=None):
    """Generate a seamless polka dot pattern."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    colors = palette["colors"]
    bg = random.choice([palette["bg_light"], palette["bg_dark"]])

    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)

    dot_r = random.randint(size // 30, size // 12)
    spacing = dot_r * random.uniform(3, 5)
    offset = random.random() > 0.5  # Offset alternate rows

    rows = int(size / spacing) + 2
    cols = int(size / spacing) + 2

    dot_colors = random.sample(colors, min(random.randint(1, 3), len(colors)))

    for row in range(rows):
        for col in range(cols):
            x = int(col * spacing)
            y = int(row * spacing)
            if offset and row % 2:
                x += int(spacing / 2)

            # Draw on all edges for seamless tiling
            for dx in [0, -size, size]:
                for dy in [0, -size, size]:
                    cx, cy = x + dx, y + dy
                    color = random.choice(dot_colors)
                    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=color)

    return img


def generate_geometric_pattern(palette_name, size=600, seed=None):
    """Generate a geometric pattern with triangles and shapes."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    colors = palette["colors"]
    bg = random.choice([palette["bg_light"], palette["bg_dark"]])

    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)

    cell_size = random.randint(size // 10, size // 5)
    rows = size // cell_size + 2
    cols = size // cell_size + 2

    shape = random.choice(["triangle", "diamond", "hexagon", "cross"])

    for row in range(rows):
        for col in range(cols):
            x = col * cell_size
            y = row * cell_size
            color = colors[(row + col) % len(colors)]

            if (row + col) % random.randint(2, 4) == 0:
                continue  # Skip some for visual interest

            for dx in [0, -size, size]:
                for dy in [0, -size, size]:
                    cx, cy = x + dx + cell_size // 2, y + dy + cell_size // 2
                    r = cell_size // 3

                    if shape == "triangle":
                        points = [
                            (cx, cy - r),
                            (cx - r, cy + r),
                            (cx + r, cy + r),
                        ]
                        if (row + col) % 2:
                            points = [(cx, cy + r), (cx - r, cy - r), (cx + r, cy - r)]
                        draw.polygon(points, fill=color)

                    elif shape == "diamond":
                        points = [
                            (cx, cy - r), (cx + r, cy),
                            (cx, cy + r), (cx - r, cy),
                        ]
                        draw.polygon(points, fill=color)

                    elif shape == "hexagon":
                        points = []
                        for angle in range(6):
                            a = math.radians(60 * angle - 30)
                            px = cx + int(r * math.cos(a))
                            py = cy + int(r * math.sin(a))
                            points.append((px, py))
                        draw.polygon(points, fill=color)

                    elif shape == "cross":
                        arm = r // 3
                        draw.rectangle([cx - arm, cy - r, cx + arm, cy + r], fill=color)
                        draw.rectangle([cx - r, cy - arm, cx + r, cy + arm], fill=color)

    return img


def generate_stripe_pattern(palette_name, size=600, seed=None):
    """Generate a stripe pattern (vertical, horizontal, or diagonal)."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    colors = palette["colors"]
    bg = random.choice([palette["bg_light"], palette["bg_dark"]])

    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)

    direction = random.choice(["vertical", "horizontal", "diagonal"])
    n_stripes = random.randint(6, 20)
    stripe_colors = random.sample(colors, min(random.randint(2, 4), len(colors)))

    stripe_w = size // n_stripes

    if direction == "vertical":
        for i in range(n_stripes):
            color = stripe_colors[i % len(stripe_colors)]
            if i % 2 == 0:
                draw.rectangle([i * stripe_w, 0, (i + 1) * stripe_w, size], fill=color)
    elif direction == "horizontal":
        for i in range(n_stripes):
            color = stripe_colors[i % len(stripe_colors)]
            if i % 2 == 0:
                draw.rectangle([0, i * stripe_w, size, (i + 1) * stripe_w], fill=color)
    elif direction == "diagonal":
        for i in range(-n_stripes, n_stripes * 2):
            if i % 2 == 0:
                color = stripe_colors[i % len(stripe_colors)]
                x_start = i * stripe_w
                points = [
                    (x_start, 0),
                    (x_start + stripe_w, 0),
                    (x_start + stripe_w - size, size),
                    (x_start - size, size),
                ]
                draw.polygon(points, fill=color)

    return img


def generate_wave_pattern(palette_name, size=600, seed=None):
    """Generate a wavy line pattern."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    colors = palette["colors"]
    bg = random.choice([palette["bg_light"], palette["bg_dark"]])

    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)

    n_waves = random.randint(5, 12)
    amplitude = random.randint(size // 30, size // 10)
    frequency = random.uniform(1.5, 4)
    line_w = random.randint(2, max(3, size // 80))

    spacing = size // n_waves

    for i in range(n_waves + 1):
        color = colors[i % len(colors)]
        y_base = i * spacing

        points = []
        for x in range(0, size + 1, 3):
            y = y_base + int(amplitude * math.sin(2 * math.pi * frequency * x / size))
            points.append((x, y))

        if len(points) > 1:
            # Draw on all y-offsets for seamless tiling
            for dy in [0, -size, size]:
                shifted = [(px, py + dy) for px, py in points]
                draw.line(shifted, fill=color, width=line_w)

    return img


def generate_scatter_pattern(palette_name, size=600, seed=None):
    """Generate a scattered elements pattern (stars, dots, mini shapes)."""
    if seed is not None:
        random.seed(seed)

    palette = PALETTES[palette_name]
    colors = palette["colors"]
    bg = random.choice([palette["bg_light"], palette["bg_dark"]])

    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)

    element = random.choice(["star", "plus", "circle_ring", "tiny_diamond"])
    n_elements = random.randint(20, 60)

    for _ in range(n_elements):
        x = random.randint(0, size)
        y = random.randint(0, size)
        r = random.randint(size // 80, size // 30)
        color = random.choice(colors)

        for dx in [0, -size, size]:
            for dy in [0, -size, size]:
                cx, cy = x + dx, y + dy

                if element == "star":
                    points = []
                    for i in range(5):
                        outer_a = math.radians(72 * i - 90)
                        inner_a = math.radians(72 * i - 90 + 36)
                        points.append((cx + int(r * math.cos(outer_a)),
                                       cy + int(r * math.sin(outer_a))))
                        points.append((cx + int(r * 0.4 * math.cos(inner_a)),
                                       cy + int(r * 0.4 * math.sin(inner_a))))
                    draw.polygon(points, fill=color)

                elif element == "plus":
                    arm = max(1, r // 3)
                    draw.rectangle([cx - arm, cy - r, cx + arm, cy + r], fill=color)
                    draw.rectangle([cx - r, cy - arm, cx + r, cy + arm], fill=color)

                elif element == "circle_ring":
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color,
                                 width=max(1, r // 4))

                elif element == "tiny_diamond":
                    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
                    draw.polygon(points, fill=color)

    return img


def _scale_pattern_to_size(tile_img, target_w, target_h):
    """Tile a small pattern image to fill target size."""
    tw, th = tile_img.size
    result = Image.new("RGB", (target_w, target_h))
    for y in range(0, target_h, th):
        for x in range(0, target_w, tw):
            result.paste(tile_img, (x, y))
    return result


def generate_patterns(palette_name, output_dir, count=2, seed_base=None):
    """Generate a batch of seamless patterns."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    generators = [
        ("polka_dot", generate_polka_dot_pattern),
        ("geometric", generate_geometric_pattern),
        ("stripe", generate_stripe_pattern),
        ("wave", generate_wave_pattern),
        ("scatter", generate_scatter_pattern),
    ]

    tile_size = 600  # Base tile size

    for i in range(count):
        gen_name, gen_func = generators[i % len(generators)]
        seed = (seed_base or 0) + i if seed_base is not None else None

        tile = gen_func(palette_name, tile_size, seed=seed)

        # Save tile version
        fname_tile = f"pattern_{palette_name}_{gen_name}_{i:03d}_tile.png"
        fpath_tile = output_dir / fname_tile
        tile.save(fpath_tile, "PNG", optimize=True)

        # Save full-size version (3600x3600)
        full_w, full_h = SIZES["pattern_tile"]
        full_img = _scale_pattern_to_size(tile, full_w, full_h)
        fname_full = f"pattern_{palette_name}_{gen_name}_{i:03d}_full.png"
        fpath_full = output_dir / fname_full
        full_img.save(fpath_full, "PNG", optimize=True)

        generated.append({
            "file_tile": str(fpath_tile),
            "file_full": str(fpath_full),
            "type": "seamless_pattern",
            "style": gen_name,
            "palette": palette_name,
            "tile_size": tile_size,
            "full_size": (full_w, full_h),
        })

    return generated
