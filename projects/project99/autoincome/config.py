"""AutoIncome Configuration"""
import os
from pathlib import Path

# === Paths ===
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
FONTS_DIR = Path("C:/Windows/Fonts")

# === Fonts (Windows built-in) ===
FONTS = {
    "serif_regular": FONTS_DIR / "georgia.ttf",
    "serif_bold": FONTS_DIR / "georgiab.ttf",
    "sans_regular": FONTS_DIR / "calibri.ttf",
    "sans_bold": FONTS_DIR / "calibrib.ttf",
    "sans_light": FONTS_DIR / "calibril.ttf",
    "display_bold": FONTS_DIR / "impact.ttf",
    "script": FONTS_DIR / "BRUSHSCI.TTF",
    "mono": FONTS_DIR / "consola.ttf",
    "classic_regular": FONTS_DIR / "times.ttf",
    "classic_bold": FONTS_DIR / "timesbd.ttf",
    "modern_regular": FONTS_DIR / "segoeui.ttf",
    "modern_bold": FONTS_DIR / "segoeuib.ttf",
    "modern_light": FONTS_DIR / "segoeuil.ttf",
    "book": FONTS_DIR / "BOOKOS.TTF",
    "book_bold": FONTS_DIR / "BOOKOSB.TTF",
    "century": FONTS_DIR / "CENTURY.TTF",
    "arial": FONTS_DIR / "arial.ttf",
    "arial_bold": FONTS_DIR / "arialbd.ttf",
    "trebuchet": FONTS_DIR / "trebuc.ttf",
    "verdana": FONTS_DIR / "verdana.ttf",
    "verdana_bold": FONTS_DIR / "verdanab.ttf",
}

# === Image Sizes ===
SIZES = {
    "phone": (1080, 1920),
    "desktop": (2560, 1440),
    "ipad": (2048, 2732),
    "print_a4": (2480, 3508),       # A4 at 300dpi
    "print_8x10": (2400, 3000),     # 8x10 inches at 300dpi
    "print_11x14": (3300, 4200),    # 11x14 inches at 300dpi
    "pattern_tile": (3600, 3600),   # Seamless pattern at 300dpi
    "pod_tshirt": (4500, 5400),     # T-shirt design
    "instagram": (1080, 1080),      # Square format
}

# === Color Palettes (Trending 2025-2026) ===
PALETTES = {
    "mocha_mousse": {
        "name": "Mocha Mousse",
        "colors": [(163, 121, 96), (200, 162, 135), (235, 210, 190), (120, 85, 65), (80, 55, 40)],
        "bg_dark": (45, 30, 22),
        "bg_light": (245, 235, 225),
    },
    "ocean_breeze": {
        "name": "Ocean Breeze",
        "colors": [(0, 119, 182), (0, 180, 216), (144, 224, 239), (202, 240, 248), (3, 4, 94)],
        "bg_dark": (2, 12, 47),
        "bg_light": (230, 245, 252),
    },
    "sunset_glow": {
        "name": "Sunset Glow",
        "colors": [(255, 107, 107), (255, 159, 67), (254, 202, 87), (255, 234, 167), (200, 55, 55)],
        "bg_dark": (50, 20, 20),
        "bg_light": (255, 245, 235),
    },
    "forest_calm": {
        "name": "Forest Calm",
        "colors": [(46, 125, 50), (102, 187, 106), (165, 214, 167), (200, 230, 201), (27, 94, 32)],
        "bg_dark": (15, 40, 18),
        "bg_light": (235, 248, 235),
    },
    "midnight_gold": {
        "name": "Midnight Gold",
        "colors": [(212, 175, 55), (255, 215, 0), (184, 134, 11), (20, 20, 40), (245, 235, 200)],
        "bg_dark": (15, 15, 30),
        "bg_light": (250, 245, 230),
    },
    "lavender_dream": {
        "name": "Lavender Dream",
        "colors": [(147, 112, 219), (186, 152, 241), (216, 191, 251), (238, 224, 255), (100, 60, 180)],
        "bg_dark": (30, 15, 55),
        "bg_light": (245, 238, 255),
    },
    "rose_gold": {
        "name": "Rose Gold",
        "colors": [(183, 110, 121), (222, 161, 168), (244, 194, 194), (250, 218, 221), (140, 70, 85)],
        "bg_dark": (45, 20, 28),
        "bg_light": (252, 240, 242),
    },
    "minimal_bw": {
        "name": "Minimal B&W",
        "colors": [(30, 30, 30), (80, 80, 80), (140, 140, 140), (200, 200, 200), (245, 245, 245)],
        "bg_dark": (20, 20, 20),
        "bg_light": (250, 250, 250),
    },
    "earth_tone": {
        "name": "Earth Tone",
        "colors": [(139, 90, 43), (180, 130, 70), (210, 180, 140), (160, 120, 80), (100, 65, 30)],
        "bg_dark": (40, 28, 15),
        "bg_light": (245, 235, 220),
    },
    "pastel_spring": {
        "name": "Pastel Spring",
        "colors": [(255, 183, 197), (183, 228, 199), (186, 200, 255), (255, 218, 185), (200, 180, 255)],
        "bg_dark": (40, 35, 50),
        "bg_light": (255, 248, 250),
    },
    "dark_academia": {
        "name": "Dark Academia",
        "colors": [(101, 67, 33), (139, 90, 43), (169, 132, 103), (205, 183, 158), (60, 40, 20)],
        "bg_dark": (35, 25, 15),
        "bg_light": (235, 225, 210),
    },
    "cyber_neon": {
        "name": "Cyber Neon",
        "colors": [(0, 255, 255), (255, 0, 255), (0, 255, 128), (255, 255, 0), (128, 0, 255)],
        "bg_dark": (10, 10, 25),
        "bg_light": (240, 240, 255),
    },
}

# === Quotes Database ===
QUOTES = [
    # Motivational
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
    ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
    ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
    ("Success is not final, failure is not fatal: it is the courage to continue that counts.", "Winston Churchill"),
    ("In the middle of difficulty lies opportunity.", "Albert Einstein"),
    ("The best time to plant a tree was 20 years ago. The second best time is now.", "Chinese Proverb"),
    ("Your limitation - it's only your imagination.", "Unknown"),
    ("Push yourself, because no one else is going to do it for you.", "Unknown"),
    ("Great things never come from comfort zones.", "Unknown"),
    ("Dream it. Wish it. Do it.", "Unknown"),
    ("Stay hungry, stay foolish.", "Steve Jobs"),
    ("The way to get started is to quit talking and begin doing.", "Walt Disney"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
    ("Everything you've ever wanted is on the other side of fear.", "George Addair"),
    # Minimal / Aesthetic
    ("Less is more.", "Ludwig Mies van der Rohe"),
    ("Simplicity is the ultimate sophistication.", "Leonardo da Vinci"),
    ("Be yourself; everyone else is already taken.", "Oscar Wilde"),
    ("Still I rise.", "Maya Angelou"),
    ("This too shall pass.", "Persian Proverb"),
    ("Breathe.", "Unknown"),
    ("Be the change.", "Mahatma Gandhi"),
    ("Create your own sunshine.", "Unknown"),
    ("Good vibes only.", "Unknown"),
    ("Inhale courage, exhale fear.", "Unknown"),
    # Life Wisdom
    ("Life is what happens when you're busy making other plans.", "John Lennon"),
    ("The purpose of our lives is to be happy.", "Dalai Lama"),
    ("You only live once, but if you do it right, once is enough.", "Mae West"),
    ("Life is really simple, but we insist on making it complicated.", "Confucius"),
    ("Happiness is not something ready made. It comes from your own actions.", "Dalai Lama"),
    # Hustle / Work
    ("Rise and grind.", "Unknown"),
    ("Hustle in silence, let success make the noise.", "Unknown"),
    ("Work hard in silence, let your success be your noise.", "Frank Ocean"),
    ("The dream is free. The hustle is sold separately.", "Unknown"),
    ("Make today so awesome, yesterday gets jealous.", "Unknown"),
    # Nature / Peace
    ("In every walk with nature, one receives far more than he seeks.", "John Muir"),
    ("The earth has music for those who listen.", "William Shakespeare"),
    ("Adopt the pace of nature: her secret is patience.", "Ralph Waldo Emerson"),
    ("Look deep into nature, and then you will understand everything better.", "Albert Einstein"),
    ("Nature does not hurry, yet everything is accomplished.", "Lao Tzu"),
]

# === Niche Keywords ===
NICHES = {
    "motivational": {
        "tags": ["motivational", "inspirational", "quote", "motivation", "inspire", "positive", "mindset", "success"],
        "audience": "General",
    },
    "minimalist": {
        "tags": ["minimalist", "minimal", "simple", "clean", "modern", "aesthetic", "scandinavian"],
        "audience": "Design lovers",
    },
    "aesthetic": {
        "tags": ["aesthetic", "vsco", "tumblr", "soft", "dreamy", "pastel", "cozy"],
        "audience": "Gen Z / Millennials",
    },
    "dark_academia": {
        "tags": ["dark academia", "academia", "vintage", "classical", "literary", "bookish", "scholarly"],
        "audience": "Students / Book lovers",
    },
    "nature": {
        "tags": ["nature", "earth", "green", "forest", "ocean", "mountain", "botanical", "organic"],
        "audience": "Nature lovers",
    },
    "geometric": {
        "tags": ["geometric", "abstract", "modern", "shapes", "contemporary", "polygon", "architecture"],
        "audience": "Modern art fans",
    },
    "boho": {
        "tags": ["boho", "bohemian", "free spirit", "earthy", "natural", "hippie", "warm"],
        "audience": "Boho lifestyle",
    },
    "luxury": {
        "tags": ["luxury", "elegant", "gold", "premium", "sophisticated", "classy", "upscale"],
        "audience": "Luxury lifestyle",
    },
}

# === Daily Generation Config ===
DAILY_CONFIG = {
    "wallpapers_per_niche": 3,
    "quotes_per_niche": 2,
    "patterns_per_niche": 2,
    "pod_designs_per_niche": 1,
    "active_niches": ["motivational", "minimalist", "aesthetic", "nature", "geometric", "luxury"],
}
