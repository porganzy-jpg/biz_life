"""SEO Listing Generator - Creates optimized titles, descriptions, and tags for marketplaces."""
import random
import json
import csv
from pathlib import Path
from datetime import datetime

from autoincome.config import PALETTES, NICHES


def _get_palette_descriptors(palette_name):
    """Get descriptive words for a color palette."""
    descriptors = {
        "mocha_mousse": ["warm", "cozy", "earthy", "brown", "neutral", "coffee", "mocha"],
        "ocean_breeze": ["blue", "ocean", "calm", "coastal", "nautical", "sea", "serene"],
        "sunset_glow": ["warm", "sunset", "orange", "vibrant", "golden", "sunny", "bright"],
        "forest_calm": ["green", "nature", "forest", "botanical", "organic", "calming", "fresh"],
        "midnight_gold": ["luxury", "gold", "elegant", "dark", "premium", "royal", "sophisticated"],
        "lavender_dream": ["purple", "lavender", "dreamy", "soft", "feminine", "pastel", "gentle"],
        "rose_gold": ["rose", "pink", "romantic", "blush", "feminine", "elegant", "soft"],
        "minimal_bw": ["minimalist", "black and white", "monochrome", "simple", "clean", "modern"],
        "earth_tone": ["earthy", "natural", "warm", "rustic", "vintage", "organic", "brown"],
        "pastel_spring": ["pastel", "spring", "soft", "light", "cute", "kawaii", "gentle"],
        "dark_academia": ["dark academia", "vintage", "scholarly", "classic", "literary", "antique"],
        "cyber_neon": ["neon", "cyber", "futuristic", "vibrant", "electric", "gaming", "tech"],
    }
    return descriptors.get(palette_name, ["beautiful", "colorful", "unique"])


def generate_wallpaper_listing(product_info):
    """Generate SEO-optimized listing for a wallpaper."""
    palette = product_info.get("palette", "minimal_bw")
    style = product_info.get("style", "gradient")
    size = product_info.get("size", "phone")
    descriptors = _get_palette_descriptors(palette)
    palette_data = PALETTES.get(palette, {})
    palette_display = palette_data.get("name", palette.replace("_", " ").title())

    size_labels = {
        "phone": "iPhone Android Phone",
        "desktop": "Desktop Computer Mac PC",
        "ipad": "iPad Tablet",
    }
    size_label = size_labels.get(size, size)

    style_labels = {
        "gradient": "Gradient",
        "abstract": "Abstract Art",
        "minimalist": "Minimalist",
    }
    style_label = style_labels.get(style, style.title())

    d1, d2 = random.sample(descriptors, min(2, len(descriptors)))

    titles = [
        f"{d1.title()} {style_label} Digital Wallpaper | {size_label} Background",
        f"{palette_display} {style_label} Wallpaper | {d2.title()} Digital Download",
        f"{style_label} {size_label} Wallpaper | {d1.title()} {d2.title()} Aesthetic",
    ]

    descriptions = [
        f"Beautiful {d1} {style_label.lower()} digital wallpaper in {palette_display} color palette. "
        f"Perfect for your {size_label.lower()}. Instant digital download - no waiting! "
        f"This {d2} design features a {style_label.lower()} style that will transform your screen. "
        f"High resolution PNG file ready to use immediately.",
        f"Transform your {size_label.lower()} with this stunning {d1} {style_label.lower()} wallpaper. "
        f"Featuring {palette_display} tones, this {d2} design is perfect for anyone who loves "
        f"clean, beautiful aesthetics. Digital download - get it instantly!",
    ]

    base_tags = ["digital wallpaper", "phone wallpaper", "desktop wallpaper", "digital download",
                 "instant download", "aesthetic wallpaper", "background"]
    style_tags = [f"{style_label.lower()} wallpaper", f"{style_label.lower()} background"]
    color_tags = [f"{d} wallpaper" for d in descriptors[:3]]

    tags = list(set(base_tags + style_tags + color_tags))[:13]

    return {
        "title": random.choice(titles),
        "description": random.choice(descriptions),
        "tags": tags,
        "price_suggestion": {"etsy": "$1.99-$3.99", "gumroad": "$1.99"},
        "category": "Digital Wallpaper",
    }


def generate_quote_listing(product_info):
    """Generate SEO-optimized listing for a quote print."""
    palette = product_info.get("palette", "minimal_bw")
    style = product_info.get("style", "classic")
    quote = product_info.get("quote", "")
    author = product_info.get("author", "Unknown")
    descriptors = _get_palette_descriptors(palette)
    palette_data = PALETTES.get(palette, {})
    palette_display = palette_data.get("name", palette.replace("_", " ").title())

    short_quote = quote[:40] + "..." if len(quote) > 40 else quote
    d1 = random.choice(descriptors)

    titles = [
        f"Inspirational Quote Print | {short_quote} | Digital Wall Art",
        f"{d1.title()} Quote Art Print | Motivational Poster | Digital Download",
        f"Printable Quote Wall Art | {author} Quote | {palette_display} Design",
    ]

    descriptions = [
        f'"{quote}" - {author}\n\n'
        f"Beautiful {d1} typography art print featuring this inspiring quote. "
        f"Printed in {palette_display} tones with a {style} design style. "
        f"Perfect for home office, bedroom, or living room decor. "
        f"High resolution digital download - print at home or at any print shop. "
        f"Multiple sizes included.",
    ]

    tags = ["quote print", "inspirational quote", "wall art", "digital print", "printable art",
            "typography print", "motivational poster", "home decor", "office decor",
            f"{d1} art", "instant download", "quote wall art", "digital download"][:13]

    return {
        "title": random.choice(titles),
        "description": random.choice(descriptions),
        "tags": tags,
        "price_suggestion": {"etsy": "$2.99-$5.99", "gumroad": "$2.99"},
        "category": "Quote Art Print",
    }


def generate_pattern_listing(product_info):
    """Generate SEO-optimized listing for a pattern."""
    palette = product_info.get("palette", "minimal_bw")
    style = product_info.get("style", "polka_dot")
    descriptors = _get_palette_descriptors(palette)
    palette_data = PALETTES.get(palette, {})
    palette_display = palette_data.get("name", palette.replace("_", " ").title())

    style_labels = {
        "polka_dot": "Polka Dot",
        "geometric": "Geometric",
        "stripe": "Stripe",
        "wave": "Wave",
        "scatter": "Scattered",
    }
    style_label = style_labels.get(style, style.title())
    d1 = random.choice(descriptors)

    titles = [
        f"{style_label} Seamless Pattern | {palette_display} | Digital Paper",
        f"{d1.title()} {style_label} Digital Pattern | Scrapbook Paper | Commercial Use",
        f"Seamless {style_label} Pattern | {d1.title()} Digital Background",
    ]

    descriptions = [
        f"Beautiful {d1} {style_label.lower()} seamless pattern in {palette_display} colors. "
        f"This versatile digital pattern is perfect for scrapbooking, fabric design, "
        f"web backgrounds, packaging, and more. Includes both tile and full-size versions. "
        f"High resolution 300 DPI PNG file. Tiles seamlessly in all directions.",
    ]

    tags = ["seamless pattern", "digital paper", f"{style_label.lower()} pattern",
            "scrapbook paper", "background pattern", "digital pattern",
            f"{d1} pattern", "commercial use", "fabric design", "surface pattern",
            "instant download", "digital download", "tileable pattern"][:13]

    return {
        "title": random.choice(titles),
        "description": random.choice(descriptions),
        "tags": tags,
        "price_suggestion": {"etsy": "$1.99-$3.99", "gumroad": "$1.99"},
        "category": "Digital Pattern",
    }


def generate_pod_listing(product_info):
    """Generate SEO-optimized listing for a POD design."""
    palette = product_info.get("palette", "minimal_bw")
    category = product_info.get("category", "motivational")
    phrase = product_info.get("phrase", "").replace("\n", " ")
    style = product_info.get("style", "text_bold")
    descriptors = _get_palette_descriptors(palette)
    d1 = random.choice(descriptors)

    cat_labels = {
        "funny": "Funny",
        "motivational": "Motivational",
        "profession": "Profession",
        "minimal": "Minimalist",
    }
    cat_label = cat_labels.get(category, category.title())

    short_phrase = phrase[:30]

    titles = [
        f"{cat_label} T-Shirt Design | {short_phrase} | Unisex Graphic Tee",
        f"{short_phrase} | {cat_label} {d1.title()} Design | T-shirt Mug Hoodie",
    ]

    descriptions = [
        f'"{phrase}" - {cat_label} design perfect for t-shirts, mugs, hoodies, '
        f"phone cases, and more. {d1.title()} color scheme that stands out. "
        f"Available on all Redbubble products. Makes a great gift!",
    ]

    tags = [f"{cat_label.lower()} shirt", f"{cat_label.lower()} design",
            "graphic tee", "funny shirt", f"{d1} design",
            "gift idea", "t-shirt design", "mug design",
            "redbubble", "print on demand", "unisex"][:13]

    return {
        "title": random.choice(titles),
        "description": random.choice(descriptions),
        "tags": tags,
        "price_suggestion": {"redbubble": "Default markup + 20%"},
        "category": "POD Design",
    }


def generate_listings(products, output_dir):
    """Generate listings for all products and save as CSV + JSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    listing_generators = {
        "wallpaper": generate_wallpaper_listing,
        "quote_print": generate_quote_listing,
        "seamless_pattern": generate_pattern_listing,
        "pod_design": generate_pod_listing,
    }

    all_listings = []

    for product in products:
        ptype = product.get("type", "")
        gen = listing_generators.get(ptype)
        if gen:
            listing = gen(product)
            listing["product_file"] = product.get("file", product.get("file_tile", ""))
            listing["product_type"] = ptype
            all_listings.append(listing)

    # Save as JSON
    json_path = output_dir / "listings.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_listings, f, indent=2, ensure_ascii=False)

    # Save as CSV (for easy Etsy bulk upload)
    csv_path = output_dir / "listings.csv"
    if all_listings:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "description", "tags",
                                                     "price_suggestion", "category",
                                                     "product_file", "product_type"])
            writer.writeheader()
            for listing in all_listings:
                row = dict(listing)
                row["tags"] = ", ".join(row["tags"])
                row["price_suggestion"] = str(row["price_suggestion"])
                writer.writerow(row)

    return all_listings, json_path, csv_path
