#!/usr/bin/env python3
"""
BarcodeQuest Local Art Generator
=================================
Pillow로 수채화풍 몬스터/캐릭터 이미지를 로컬 생성합니다.
pollinations.ai가 불가할 때 사용하는 대체 스크립트.

사용법:
  python generate_local_art.py              # 전체 110장
  python generate_local_art.py --characters # 캐릭터 10장만
  python generate_local_art.py --monsters   # 몬스터 100장만
"""

import math
import random
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
MONSTERS_DIR = BASE_DIR / "artwork" / "monsters"
CHARACTERS_DIR = BASE_DIR / "artwork" / "named_characters"
SIZE = 512

# ── Color palettes ──
ELEM_COLORS = {
    "fire":    {"bg": (255,240,230), "main": (230,80,40),  "acc": (255,160,50),  "glow": (255,120,30)},
    "water":   {"bg": (230,245,255), "main": (40,120,200), "acc": (80,180,230),  "glow": (60,150,220)},
    "nature":  {"bg": (235,250,235), "main": (50,160,60),  "acc": (120,200,80),  "glow": (80,180,70)},
    "wind":    {"bg": (240,248,255), "main": (140,180,210),"acc": (180,210,240), "glow": (160,200,230)},
    "spirit":  {"bg": (245,235,255), "main": (140,60,200), "acc": (180,120,230), "glow": (160,90,215)},
    "light":   {"bg": (255,252,235), "main": (230,190,50), "acc": (255,220,100), "glow": (245,210,70)},
    "dark":    {"bg": (235,230,245), "main": (60,40,80),   "acc": (100,70,140),  "glow": (80,55,110)},
    "earth":   {"bg": (245,238,230), "main": (140,100,60), "acc": (180,140,90),  "glow": (160,120,75)},
    "mech":    {"bg": (240,240,245), "main": (120,130,140),"acc": (190,160,110), "glow": (155,145,125)},
    "food":    {"bg": (255,240,245), "main": (220,100,130),"acc": (255,180,150), "glow": (240,140,140)},
}

BODY_SHAPES = {
    "dragon":  {"shape": "dragon",  "emoji": "dragon"},
    "slime":   {"shape": "blob",    "emoji": "slime"},
    "goblin":  {"shape": "humanoid","emoji": "goblin"},
    "fairy":   {"shape": "winged",  "emoji": "fairy"},
    "golem":   {"shape": "blocky",  "emoji": "golem"},
    "unicorn": {"shape": "horse",   "emoji": "unicorn"},
    "phoenix": {"shape": "bird",    "emoji": "phoenix"},
    "sprite":  {"shape": "tiny",    "emoji": "sprite"},
    "chimera": {"shape": "beast",   "emoji": "chimera"},
    "wisp":    {"shape": "orb",     "emoji": "wisp"},
}

CHAR_INFO = {
    "nabi":    {"emoji": "\U0001F98B", "color": (180,220,160), "accent": (120,200,80),  "shape": "winged"},
    "haru":    {"emoji": "\U0001F415", "color": (210,180,130), "accent": (180,140,80),  "shape": "dog"},
    "pori":    {"emoji": "\U0001F99C", "color": (80,200,160),  "accent": (255,120,80),  "shape": "bird"},
    "miru":    {"emoji": "\U0001F431", "color": (160,180,200), "accent": (120,150,180), "shape": "cat"},
    "ggomi":   {"emoji": "\U0001F430", "color": (240,230,220), "accent": (255,180,190), "shape": "rabbit"},
    "rang":    {"emoji": "\U0001F98A", "color": (220,140,60),  "accent": (180,100,40),  "shape": "fox"},
    "byeori":  {"emoji": "\U0001F439", "color": (240,210,140), "accent": (220,180,100), "shape": "hamster"},
    "gureum":  {"emoji": "\U0001F408", "color": (230,230,240), "accent": (200,200,220), "shape": "cat"},
    "dari":    {"emoji": "\U0001F989", "color": (140,130,160), "accent": (100,90,130),  "shape": "owl"},
    "sori":    {"emoji": "\U0001F994", "color": (180,160,130), "accent": (140,120,90),  "shape": "hedgehog"},
}

CHAR_NAMES = {"nabi":"나비","haru":"하루","pori":"포리","miru":"미루","ggomi":"꼬미",
              "rang":"랑이","byeori":"별이","gureum":"구름","dari":"달이","sori":"솔이"}
BODY_NAMES = {"dragon":"드래곤","slime":"슬라임","goblin":"고블린","fairy":"페어리","golem":"골렘",
              "unicorn":"유니콘","phoenix":"피닉스","sprite":"스프라이트","chimera":"키메라","wisp":"위스프"}
ELEM_NAMES = {"fire":"불","water":"물","nature":"자연","wind":"바람","spirit":"영혼",
              "light":"빛","dark":"어둠","earth":"대지","mech":"기계","food":"음식"}


def lerp_color(c1, c2, t):
    return tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))


def draw_watercolor_circle(draw, cx, cy, r, color, alpha=180, seed=0):
    """수채화 느낌의 원형 그리기"""
    rng = random.Random(seed)
    for i in range(8):
        offset_x = rng.randint(-r//6, r//6)
        offset_y = rng.randint(-r//6, r//6)
        r_var = r + rng.randint(-r//5, r//5)
        a = max(30, alpha - i*15)
        c = tuple(min(255, max(0, v + rng.randint(-20, 20))) for v in color)
        fill = c + (a,)
        draw.ellipse([cx-r_var+offset_x, cy-r_var+offset_y, cx+r_var+offset_x, cy+r_var+offset_y], fill=fill)


def draw_sparkles(draw, cx, cy, r, color, seed=0):
    """반짝이 효과"""
    rng = random.Random(seed+999)
    for _ in range(12):
        sx = cx + rng.randint(-r, r)
        sy = cy + rng.randint(-r, r)
        sz = rng.randint(2, 6)
        a = rng.randint(100, 220)
        c = tuple(min(255, v+60) for v in color) + (a,)
        draw.ellipse([sx-sz, sy-sz, sx+sz, sy+sz], fill=c)


def draw_eyes(draw, cx, cy, size, seed=0):
    """귀여운 눈 그리기"""
    eye_gap = size * 0.3
    eye_r = size * 0.12
    pupil_r = eye_r * 0.55
    # White
    for ex in [cx - eye_gap, cx + eye_gap]:
        draw.ellipse([ex-eye_r, cy-eye_r, ex+eye_r, cy+eye_r], fill=(255,255,255,230))
        draw.ellipse([ex-pupil_r, cy-pupil_r+1, ex+pupil_r, cy+pupil_r+1], fill=(30,30,40,240))
        # Highlight
        hl = pupil_r * 0.4
        draw.ellipse([ex-hl-1, cy-hl-1, ex+hl-1, cy+hl-1], fill=(255,255,255,200))


def draw_mouth(draw, cx, cy, size, happy=True):
    """작은 입"""
    w = size * 0.15
    if happy:
        bbox = [cx-w, cy-w*0.3, cx+w, cy+w*0.7]
        draw.arc(bbox, 0, 180, fill=(80,50,50,200), width=2)
    else:
        draw.line([cx-w*0.5, cy, cx+w*0.5, cy], fill=(80,50,50,180), width=2)


def draw_body_shape(draw, cx, cy, body_type, size, color, acc_color, seed):
    """몸체 타입별 형태 그리기"""
    rng = random.Random(seed)
    r = size * 0.28

    if body_type in ("blob", "slime"):
        # 슬라임: 큰 방울 모양
        draw_watercolor_circle(draw, cx, cy+10, int(r*1.2), color, 200, seed)
        draw_watercolor_circle(draw, cx, cy-5, int(r*0.8), lerp_color(color, (255,255,255), 0.3), 140, seed+1)
        draw_eyes(draw, cx, cy-5, r*2, seed)
        draw_mouth(draw, cx, cy+15, r*2)

    elif body_type == "dragon":
        # 드래곤: 몸+작은 날개+꼬리
        draw_watercolor_circle(draw, cx, cy, int(r), color, 200, seed)
        # Wings
        draw_watercolor_circle(draw, cx-r*1.1, cy-r*0.5, int(r*0.5), acc_color, 150, seed+10)
        draw_watercolor_circle(draw, cx+r*1.1, cy-r*0.5, int(r*0.5), acc_color, 150, seed+11)
        # Tail
        for i in range(5):
            tx = cx + r*0.8 + i*8
            ty = cy + r*0.5 + i*5
            draw_watercolor_circle(draw, int(tx), int(ty), int(r*0.2-i*2), color, 160, seed+20+i)
        # Horns
        draw.polygon([(cx-15, cy-r*0.9), (cx-10, cy-r*1.4), (cx-5, cy-r*0.9)], fill=acc_color+(180,))
        draw.polygon([(cx+5, cy-r*0.9), (cx+10, cy-r*1.4), (cx+15, cy-r*0.9)], fill=acc_color+(180,))
        draw_eyes(draw, cx, cy-8, r*2, seed)
        draw_mouth(draw, cx, cy+12, r*2)

    elif body_type in ("humanoid", "goblin"):
        # 고블린: 몸+큰 귀
        draw_watercolor_circle(draw, cx, cy+15, int(r*0.8), color, 200, seed)  # body
        draw_watercolor_circle(draw, cx, cy-15, int(r*0.7), color, 210, seed+1)  # head
        # Ears
        draw_watercolor_circle(draw, cx-r*0.8, cy-25, int(r*0.3), acc_color, 170, seed+10)
        draw_watercolor_circle(draw, cx+r*0.8, cy-25, int(r*0.3), acc_color, 170, seed+11)
        draw_eyes(draw, cx, cy-20, r*1.6, seed)
        draw_mouth(draw, cx, cy-5, r*1.6, happy=False)

    elif body_type in ("winged", "fairy"):
        # 페어리: 작은 몸+큰 날개
        draw_watercolor_circle(draw, cx, cy, int(r*0.6), color, 210, seed)
        # Big wings
        draw_watercolor_circle(draw, cx-r*1.2, cy-r*0.2, int(r*0.7), acc_color, 120, seed+10)
        draw_watercolor_circle(draw, cx+r*1.2, cy-r*0.2, int(r*0.7), acc_color, 120, seed+11)
        draw_watercolor_circle(draw, cx-r*0.9, cy+r*0.3, int(r*0.5), acc_color, 100, seed+12)
        draw_watercolor_circle(draw, cx+r*0.9, cy+r*0.3, int(r*0.5), acc_color, 100, seed+13)
        draw_eyes(draw, cx, cy-5, r*1.4, seed)
        draw_mouth(draw, cx, cy+10, r*1.4)

    elif body_type in ("blocky", "golem"):
        # 골렘: 네모난 몸
        bw, bh = int(r*1.6), int(r*1.8)
        draw.rounded_rectangle([cx-bw//2, cy-bh//2, cx+bw//2, cy+bh//2], radius=15, fill=color+(190,))
        draw.rounded_rectangle([cx-bw//2+8, cy-bh//2+8, cx+bw//2-8, cy+bh//2-8], radius=10, fill=lerp_color(color,(200,200,200),0.3)+(140,))
        # Glowing rune eyes
        for ex in [cx-18, cx+18]:
            draw.ellipse([ex-8, cy-15, ex+8, cy+1], fill=acc_color+(220,))
            draw.ellipse([ex-4, cy-11, ex+4, cy-3], fill=(255,255,200,240))

    elif body_type in ("horse", "unicorn"):
        # 유니콘: 말 형태+뿔
        draw_watercolor_circle(draw, cx, cy+10, int(r*0.9), color, 200, seed)
        draw_watercolor_circle(draw, cx-r*0.3, cy-r*0.5, int(r*0.6), color, 210, seed+1)
        # Horn
        pts = [(cx-r*0.3, cy-r*1.1), (cx-r*0.3-5, cy-r*1.6), (cx-r*0.3+5, cy-r*1.1)]
        draw.polygon(pts, fill=acc_color+(200,))
        # Mane
        for i in range(5):
            mx = cx - r*0.1 + i*6
            my = cy - r*0.3 - rng.randint(0, 15)
            draw_watercolor_circle(draw, int(mx), int(my), int(r*0.15), acc_color, 140, seed+20+i)
        draw_eyes(draw, cx-r*0.35, cy-r*0.5, r*1.2, seed)

    elif body_type in ("bird", "phoenix"):
        # 피닉스: 새 형태+불꽃 날개
        draw_watercolor_circle(draw, cx, cy, int(r*0.7), color, 200, seed)
        # Flame wings
        for i in range(6):
            ang = -30 + i*12
            wx = cx - r*1.0 + math.cos(math.radians(ang))*r*0.3
            wy = cy - r*0.2 + math.sin(math.radians(ang))*r*0.5
            draw_watercolor_circle(draw, int(wx), int(wy), int(r*0.35-i*3), acc_color, 130, seed+10+i)
            wx2 = cx + r*1.0 - math.cos(math.radians(ang))*r*0.3
            draw_watercolor_circle(draw, int(wx2), int(wy), int(r*0.35-i*3), acc_color, 130, seed+20+i)
        # Tail feathers
        for i in range(3):
            draw_watercolor_circle(draw, cx+i*8, int(cy+r*0.7+i*6), int(r*0.2), acc_color, 120, seed+30+i)
        draw_eyes(draw, cx, cy-8, r*1.5, seed)
        draw.polygon([(cx-5,cy+5),(cx,cy+15),(cx+5,cy+5)], fill=(220,180,50,200))  # beak

    elif body_type in ("tiny", "sprite"):
        # 스프라이트: 아주 작은 자연 정령
        draw_watercolor_circle(draw, cx, cy, int(r*0.5), color, 220, seed)
        # Leaf antenna
        draw.polygon([(cx-5,cy-r*0.5),(cx-15,cy-r*1.0),(cx,cy-r*0.6)], fill=(80,180,60,180))
        draw.polygon([(cx+5,cy-r*0.5),(cx+15,cy-r*1.0),(cx,cy-r*0.6)], fill=(80,180,60,180))
        # Leaf clothing
        draw_watercolor_circle(draw, cx, cy+r*0.4, int(r*0.35), (80,180,60), 140, seed+10)
        draw_eyes(draw, cx, cy-5, r*1.2, seed)
        draw_mouth(draw, cx, cy+8, r*1.2)

    elif body_type in ("beast", "chimera"):
        # 키메라: 여러 동물 합체
        draw_watercolor_circle(draw, cx, cy+5, int(r*0.9), color, 200, seed)
        # Different colored patches
        draw_watercolor_circle(draw, cx-20, cy-10, int(r*0.4), acc_color, 140, seed+10)
        draw_watercolor_circle(draw, cx+20, cy+10, int(r*0.4), lerp_color(color,acc_color,0.5), 140, seed+11)
        # Horns + ears mixed
        draw.polygon([(cx-20,cy-r*0.7),(cx-15,cy-r*1.2),(cx-10,cy-r*0.7)], fill=acc_color+(180,))
        draw_watercolor_circle(draw, cx+18, cy-r*0.7, int(r*0.2), color, 170, seed+12)  # ear
        # Tail
        draw_watercolor_circle(draw, cx+r*0.8, cy+r*0.3, int(r*0.25), acc_color, 150, seed+13)
        draw_eyes(draw, cx, cy-8, r*2, seed)
        draw_mouth(draw, cx, cy+12, r*2)

    elif body_type in ("orb", "wisp"):
        # 위스프: 빛나는 구체
        draw_watercolor_circle(draw, cx, cy, int(r*1.0), acc_color, 100, seed)
        draw_watercolor_circle(draw, cx, cy, int(r*0.6), color, 180, seed+1)
        draw_watercolor_circle(draw, cx, cy, int(r*0.35), lerp_color(color,(255,255,255),0.5), 200, seed+2)
        # Trailing sparkle tail
        for i in range(6):
            tx = cx + rng.randint(-30, 30)
            ty = cy + r*0.5 + i*10
            draw_watercolor_circle(draw, tx, int(ty), int(r*0.1+rng.randint(0,5)), acc_color, 80+rng.randint(0,60), seed+20+i)
        draw_eyes(draw, cx, cy-5, r*1.3, seed)

    else:
        # Default circle
        draw_watercolor_circle(draw, cx, cy, int(r), color, 200, seed)
        draw_eyes(draw, cx, cy-5, r*2, seed)
        draw_mouth(draw, cx, cy+12, r*2)


def draw_char_shape(draw, cx, cy, char_id, info, size, seed):
    """캐릭터별 특화 형태"""
    color = info["color"]
    acc = info["accent"]
    r = size * 0.25
    rng = random.Random(seed)
    shape = info["shape"]

    if shape == "dog":
        draw_watercolor_circle(draw, cx, cy+10, int(r*0.9), color, 200, seed)
        draw_watercolor_circle(draw, cx, cy-20, int(r*0.7), color, 210, seed+1)
        # Floppy ears
        draw_watercolor_circle(draw, cx-r*0.7, cy-15, int(r*0.35), lerp_color(color,(150,100,50),0.3), 170, seed+10)
        draw_watercolor_circle(draw, cx+r*0.7, cy-15, int(r*0.35), lerp_color(color,(150,100,50),0.3), 170, seed+11)
        # Tail
        draw_watercolor_circle(draw, cx+r*0.9, cy+5, int(r*0.2), color, 160, seed+12)
        draw_eyes(draw, cx, cy-22, r*1.5, seed)
        draw_mouth(draw, cx, cy-10, r*1.5)
        # Nose
        draw.ellipse([cx-4, cy-14, cx+4, cy-10], fill=(50,30,30,200))

    elif shape == "cat":
        draw_watercolor_circle(draw, cx, cy+5, int(r*0.8), color, 200, seed)
        draw_watercolor_circle(draw, cx, cy-20, int(r*0.65), color, 210, seed+1)
        # Pointy ears
        draw.polygon([(cx-25,cy-25),(cx-15,cy-50),(cx-5,cy-25)], fill=color+(190,))
        draw.polygon([(cx+5,cy-25),(cx+15,cy-50),(cx+25,cy-25)], fill=color+(190,))
        # Inner ear
        draw.polygon([(cx-22,cy-27),(cx-15,cy-44),(cx-8,cy-27)], fill=lerp_color(color,(255,180,180),0.5)+(150,))
        draw.polygon([(cx+8,cy-27),(cx+15,cy-44),(cx+22,cy-27)], fill=lerp_color(color,(255,180,180),0.5)+(150,))
        draw_eyes(draw, cx, cy-22, r*1.5, seed)
        # Whiskers
        for dy in [-18, -14]:
            draw.line([cx-35, cy+dy, cx-10, cy+dy-2], fill=(100,80,80,120), width=1)
            draw.line([cx+10, cy+dy-2, cx+35, cy+dy], fill=(100,80,80,120), width=1)
        draw.ellipse([cx-3, cy-14, cx+3, cy-10], fill=(200,120,120,200))  # nose

    elif shape == "rabbit":
        draw_watercolor_circle(draw, cx, cy+10, int(r*0.7), color, 200, seed)
        draw_watercolor_circle(draw, cx, cy-15, int(r*0.6), color, 210, seed+1)
        # Long ears
        draw_watercolor_circle(draw, cx-12, cy-55, int(r*0.2), color, 190, seed+10)
        draw_watercolor_circle(draw, cx-12, cy-40, int(r*0.2), color, 190, seed+11)
        draw_watercolor_circle(draw, cx+12, cy-55, int(r*0.2), color, 190, seed+12)
        draw_watercolor_circle(draw, cx+12, cy-40, int(r*0.2), color, 190, seed+13)
        draw_eyes(draw, cx, cy-18, r*1.3, seed)
        draw.ellipse([cx-3, cy-10, cx+3, cy-6], fill=(220,160,160,200))

    elif shape == "fox":
        draw_watercolor_circle(draw, cx, cy+5, int(r*0.85), color, 200, seed)
        draw_watercolor_circle(draw, cx, cy-20, int(r*0.6), color, 210, seed+1)
        # Pointy ears
        draw.polygon([(cx-28,cy-22),(cx-18,cy-52),(cx-8,cy-22)], fill=color+(190,))
        draw.polygon([(cx+8,cy-22),(cx+18,cy-52),(cx+28,cy-22)], fill=color+(190,))
        # White belly
        draw_watercolor_circle(draw, cx, cy+15, int(r*0.5), (240,230,220), 150, seed+10)
        # Bushy tail
        draw_watercolor_circle(draw, cx+r*0.8, cy+10, int(r*0.4), color, 170, seed+11)
        draw_watercolor_circle(draw, cx+r*1.0, cy+5, int(r*0.25), (240,230,220), 140, seed+12)
        draw_eyes(draw, cx, cy-22, r*1.4, seed)
        draw.ellipse([cx-3, cy-13, cx+3, cy-9], fill=(30,30,30,200))
        # Bandage on leg
        draw.rectangle([cx-r*0.6, cy+r*0.5, cx-r*0.4, cy+r*0.7], fill=(240,240,240,200))

    elif shape == "hamster":
        draw_watercolor_circle(draw, cx, cy, int(r*0.7), color, 210, seed)
        # Puffy cheeks
        draw_watercolor_circle(draw, cx-r*0.5, cy+5, int(r*0.35), lerp_color(color,(255,200,180),0.4), 170, seed+10)
        draw_watercolor_circle(draw, cx+r*0.5, cy+5, int(r*0.35), lerp_color(color,(255,200,180),0.4), 170, seed+11)
        # Small ears
        draw_watercolor_circle(draw, cx-20, cy-r*0.6, int(r*0.15), acc, 180, seed+12)
        draw_watercolor_circle(draw, cx+20, cy-r*0.6, int(r*0.15), acc, 180, seed+13)
        draw_eyes(draw, cx, cy-8, r*1.4, seed)
        draw_mouth(draw, cx, cy+8, r*1.4)

    elif shape == "owl":
        draw_watercolor_circle(draw, cx, cy, int(r*0.8), color, 200, seed)
        # Big eye circles
        for ex in [cx-20, cx+20]:
            draw.ellipse([ex-14, cy-18, ex+14, cy+10], fill=lerp_color(color,(240,230,210),0.5)+(180,))
        # One eye open, one closed
        draw.ellipse([cx-30, cy-10, cx-14, cy+2], fill=(255,255,255,230))
        draw.ellipse([cx-26, cy-7, cx-18, cy-1], fill=(30,30,40,240))
        draw.ellipse([cx-24, cy-6, cx-22, cy-4], fill=(255,255,255,200))
        # Closed eye
        draw.arc([cx+10, cy-6, cx+30, cy+2], 0, 180, fill=(60,50,60,200), width=2)
        # Beak
        draw.polygon([(cx-4,cy+5),(cx,cy+14),(cx+4,cy+5)], fill=(200,170,60,200))
        # Ear tufts
        draw.polygon([(cx-25,cy-r*0.7),(cx-20,cy-r*1.1),(cx-15,cy-r*0.7)], fill=color+(170,))
        draw.polygon([(cx+15,cy-r*0.7),(cx+20,cy-r*1.1),(cx+25,cy-r*0.7)], fill=color+(170,))

    elif shape == "hedgehog":
        # Spines
        for i in range(16):
            ang = 180 + i * (180/15)
            sx = cx + math.cos(math.radians(ang)) * r * 0.9
            sy = cy + math.sin(math.radians(ang)) * r * 0.7 - 10
            ex = cx + math.cos(math.radians(ang)) * r * 1.3
            ey = cy + math.sin(math.radians(ang)) * r * 1.1 - 10
            draw.line([sx, sy, ex, ey], fill=acc+(180,), width=3)
        draw_watercolor_circle(draw, cx, cy, int(r*0.65), color, 210, seed)
        draw_eyes(draw, cx, cy-8, r*1.3, seed)
        draw.ellipse([cx-3, cy-2, cx+3, cy+2], fill=(30,30,30,200))

    else:  # winged (nabi)
        draw_watercolor_circle(draw, cx, cy, int(r*0.5), color, 200, seed)
        # Big butterfly wings
        wing_colors = [(180,220,160), (140,200,120), (200,240,180), (160,210,140)]
        for i, (wx, wy, wr) in enumerate([(-r*1.0, -r*0.3, r*0.6), (r*1.0, -r*0.3, r*0.6),
                                            (-r*0.7, r*0.3, r*0.4), (r*0.7, r*0.3, r*0.4)]):
            draw_watercolor_circle(draw, int(cx+wx), int(cy+wy), int(wr), wing_colors[i%4], 140, seed+10+i)
        draw_eyes(draw, cx, cy-5, r*1.2, seed)
        draw_mouth(draw, cx, cy+8, r*1.2)
        # Bandage on wing
        draw.rectangle([int(cx+r*0.7), int(cy-r*0.4), int(cx+r*0.9), int(cy-r*0.2)], fill=(240,240,240,180))


def generate_image(body_type, elem_id, seed):
    """몬스터 이미지 한 장 생성"""
    colors = ELEM_COLORS[elem_id]
    img = Image.new("RGBA", (SIZE, SIZE), colors["bg"] + (255,))
    draw = ImageDraw.Draw(img, "RGBA")

    cx, cy = SIZE//2, SIZE//2 + 10

    # Background glow
    draw_watercolor_circle(draw, cx, cy, 180, colors["glow"], 40, seed+100)
    draw_sparkles(draw, cx, cy, 160, colors["acc"], seed+200)

    # Body
    shape = BODY_SHAPES[body_type]["shape"]
    draw_body_shape(draw, cx, cy, shape, SIZE, colors["main"], colors["acc"], seed)

    # Element particles
    draw_sparkles(draw, cx, cy, 120, colors["glow"], seed+300)

    # Soften
    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    return img.convert("RGB")


def generate_char_image(char_id, seed):
    """캐릭터 이미지 한 장 생성"""
    info = CHAR_INFO[char_id]
    bg = lerp_color(info["color"], (255,255,255), 0.7)
    img = Image.new("RGBA", (SIZE, SIZE), bg + (255,))
    draw = ImageDraw.Draw(img, "RGBA")

    cx, cy = SIZE//2, SIZE//2 + 10

    # Background glow
    draw_watercolor_circle(draw, cx, cy, 180, lerp_color(info["color"],(255,255,255),0.5), 50, seed+100)
    draw_sparkles(draw, cx, cy, 150, info["accent"], seed+200)

    # Character
    draw_char_shape(draw, cx, cy, char_id, info, SIZE, seed)

    # Sparkles
    draw_sparkles(draw, cx, cy, 100, info["color"], seed+300)

    # Soften
    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    return img.convert("RGB")


def main():
    parser = argparse.ArgumentParser(description="BarcodeQuest Local Art Generator")
    parser.add_argument("--characters", action="store_true")
    parser.add_argument("--monsters", action="store_true")
    args = parser.parse_args()

    do_chars = args.characters or (not args.characters and not args.monsters)
    do_monsters = args.monsters or (not args.characters and not args.monsters)

    MONSTERS_DIR.mkdir(parents=True, exist_ok=True)
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)

    if do_chars:
        print("=== Characters (10) ===")
        for i, (cid, info) in enumerate(CHAR_INFO.items()):
            fp = CHARACTERS_DIR / f"{cid}.png"
            seed = 77000 + i
            img = generate_char_image(cid, seed)
            img.save(fp, "PNG")
            print(f"  [OK] {cid}.png ({CHAR_NAMES[cid]})")
        print(f"  Saved to: {CHARACTERS_DIR}")

    if do_monsters:
        print("=== Monsters (100) ===")
        bodies = list(BODY_SHAPES.keys())
        elems = list(ELEM_COLORS.keys())
        count = 0
        for bi, body in enumerate(bodies):
            for ei, elem in enumerate(elems):
                fp = MONSTERS_DIR / f"{body}_{elem}.png"
                seed = bi * 100 + ei + 42000
                img = generate_image(body, elem, seed)
                img.save(fp, "PNG")
                count += 1
                if count % 10 == 0:
                    print(f"  [{count}/100] {body}_{elem}.png")
        print(f"  Saved to: {MONSTERS_DIR}")

    nc = len(list(CHARACTERS_DIR.glob("*.png")))
    nm = len(list(MONSTERS_DIR.glob("*.png")))
    print(f"\nTotal: {nc} characters + {nm} monsters = {nc+nm} images")


if __name__ == "__main__":
    main()
