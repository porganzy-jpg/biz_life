"""AutoIncome Main Pipeline - Orchestrates the entire product generation process."""
import json
import random
import time
from datetime import datetime
from pathlib import Path

from autoincome.config import PALETTES, DAILY_CONFIG, OUTPUT_DIR
from autoincome.design.wallpaper_gen import generate_wallpapers
from autoincome.design.quote_gen import generate_quotes
from autoincome.design.pattern_gen import generate_patterns
from autoincome.design.pod_gen import generate_pod_designs, POD_PHRASES
from autoincome.listing.seo_optimizer import generate_listings


def run_daily_generation(output_base=None, seed=None):
    """Run the complete daily product generation pipeline."""
    start_time = time.time()
    today = datetime.now().strftime("%Y-%m-%d")

    if output_base is None:
        output_base = OUTPUT_DIR

    day_dir = Path(output_base) / today
    day_dir.mkdir(parents=True, exist_ok=True)

    if seed is None:
        seed = int(datetime.now().strftime("%Y%m%d"))

    random.seed(seed)

    config = DAILY_CONFIG
    active_niches = config["active_niches"]

    # Map niches to best palettes
    niche_palettes = {
        "motivational": ["midnight_gold", "sunset_glow", "minimal_bw"],
        "minimalist": ["minimal_bw", "earth_tone", "mocha_mousse"],
        "aesthetic": ["lavender_dream", "pastel_spring", "rose_gold"],
        "nature": ["forest_calm", "ocean_breeze", "earth_tone"],
        "geometric": ["cyber_neon", "minimal_bw", "midnight_gold"],
        "luxury": ["midnight_gold", "rose_gold", "dark_academia"],
        "dark_academia": ["dark_academia", "earth_tone", "mocha_mousse"],
        "boho": ["earth_tone", "mocha_mousse", "sunset_glow"],
    }

    all_products = []
    stats = {
        "wallpapers": 0,
        "quotes": 0,
        "patterns": 0,
        "pod_designs": 0,
        "total": 0,
    }

    print(f"\n{'='*60}")
    print(f"  AutoIncome Daily Generation - {today}")
    print(f"{'='*60}\n")

    for niche in active_niches:
        palettes = niche_palettes.get(niche, ["minimal_bw"])
        palette = random.choice(palettes)
        niche_dir = day_dir / niche

        print(f"[{niche.upper()}] Palette: {palette}")

        # Generate wallpapers
        n_wallpapers = config["wallpapers_per_niche"]
        if n_wallpapers > 0:
            wp_dir = niche_dir / "wallpapers"
            products = generate_wallpapers(
                palette, wp_dir, count=n_wallpapers,
                size_names=["phone", "desktop"],
                seed_base=seed + hash(niche) % 10000
            )
            all_products.extend(products)
            stats["wallpapers"] += len(products)
            print(f"  Wallpapers: {len(products)} generated")

        # Generate quotes
        n_quotes = config["quotes_per_niche"]
        if n_quotes > 0:
            q_dir = niche_dir / "quotes"
            products = generate_quotes(
                palette, q_dir, count=n_quotes,
                size_names=["print_8x10"],
                seed_base=seed + hash(niche) % 10000 + 1000
            )
            all_products.extend(products)
            stats["quotes"] += len(products)
            print(f"  Quotes: {len(products)} generated")

        # Generate patterns
        n_patterns = config["patterns_per_niche"]
        if n_patterns > 0:
            p_dir = niche_dir / "patterns"
            products = generate_patterns(
                palette, p_dir, count=n_patterns,
                seed_base=seed + hash(niche) % 10000 + 2000
            )
            all_products.extend(products)
            stats["patterns"] += len(products)
            print(f"  Patterns: {len(products)} generated")

        # Generate POD designs
        n_pod = config["pod_designs_per_niche"]
        if n_pod > 0:
            pod_dir = niche_dir / "pod"
            pod_cat = random.choice(list(POD_PHRASES.keys()))
            products = generate_pod_designs(
                palette, pod_dir, count=n_pod, category=pod_cat,
                seed_base=seed + hash(niche) % 10000 + 3000
            )
            all_products.extend(products)
            stats["pod_designs"] += len(products)
            print(f"  POD Designs: {len(products)} generated")

        print()

    stats["total"] = sum(v for v in stats.values())

    # Generate listings
    print("Generating SEO listings...")
    listings, json_path, csv_path = generate_listings(all_products, day_dir)
    print(f"  Listings saved: {json_path}")
    print(f"  CSV export: {csv_path}")

    # Save generation report
    elapsed = time.time() - start_time
    report = {
        "date": today,
        "seed": seed,
        "stats": stats,
        "niches": active_niches,
        "total_products": len(all_products),
        "total_listings": len(listings),
        "elapsed_seconds": round(elapsed, 1),
        "output_directory": str(day_dir),
    }

    report_path = day_dir / "generation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  Generation Complete!")
    print(f"{'='*60}")
    print(f"  Wallpapers:   {stats['wallpapers']}")
    print(f"  Quotes:       {stats['quotes']}")
    print(f"  Patterns:     {stats['patterns']}")
    print(f"  POD Designs:  {stats['pod_designs']}")
    print(f"  Total:        {stats['total']} files")
    print(f"  Listings:     {len(listings)}")
    print(f"  Time:         {elapsed:.1f}s")
    print(f"  Output:       {day_dir}")
    print(f"{'='*60}\n")

    return report


def run_custom_generation(palette_name, niche, output_dir,
                          n_wallpapers=5, n_quotes=3, n_patterns=3, n_pod=2,
                          seed=None):
    """Run a custom generation batch with specific parameters."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if seed is None:
        seed = random.randint(0, 99999)

    all_products = []

    if n_wallpapers > 0:
        products = generate_wallpapers(palette_name, output_dir / "wallpapers",
                                       count=n_wallpapers, seed_base=seed)
        all_products.extend(products)

    if n_quotes > 0:
        products = generate_quotes(palette_name, output_dir / "quotes",
                                   count=n_quotes, seed_base=seed + 1000)
        all_products.extend(products)

    if n_patterns > 0:
        products = generate_patterns(palette_name, output_dir / "patterns",
                                     count=n_patterns, seed_base=seed + 2000)
        all_products.extend(products)

    if n_pod > 0:
        products = generate_pod_designs(palette_name, output_dir / "pod",
                                        count=n_pod, seed_base=seed + 3000)
        all_products.extend(products)

    listings, json_path, csv_path = generate_listings(all_products, output_dir)

    return all_products, listings


if __name__ == "__main__":
    run_daily_generation()
