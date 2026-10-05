"""S20-L — 「질랜디아 / ZEALANDIA」 로고. 생성 AI 없음, 글꼴도 쓰지 않는다(글자를 획으로 직접 짓는다 — 글꼴 라이선스 걱정 없음).

python tools/gen_logo_zealandia.py options   → docs/reports/s20_logo_options.png (방향 셋)
python tools/gen_logo_zealandia.py final A   → static/art/brand/zealandia/*

팔레트 M5: 깊은 청록 바탕 + 따뜻한 등불 금색. 손으로 그은 듯 살짝 흔들리는 둥근 획.
금지: 고사리·새 모티프, 실제 뉴질랜드 지도. 대륙은 둥근 추상 덩어리.
"""
import os, sys, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DST = os.path.join(ROOT, "static", "art", "brand", "zealandia")
P = dict(gold="#F4C870", gold_d="#C4924D", cream="#E8DCBF", ink="#1C1712", deep="#0A2630", teal="#1E5A68",
         teal_l="#6FB0AC", sea_top="#2A6E7C", land="#2C4A4C", land_d="#1C3436", light_bg="#EFE6D2", light_ink="#123C46")


def rgb(h, a=255):
    h = h.lstrip("#"); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


# ══════ 글자 획(한글 음절 상자 100×110, 영문 상자 폭 가변×100) ══════
KO = {
    "질": [[(8, 12), (50, 12)], [(30, 12), (24, 30), (8, 50)], [(30, 26), (40, 40), (54, 50)], [(72, 4), (72, 60)],
          [(16, 70), (68, 70), (68, 82), (18, 82), (18, 96), (72, 96)]],
    "랜": [[(8, 10), (44, 10), (44, 24), (10, 24), (10, 40), (48, 40)], [(60, 4), (60, 60)], [(60, 30), (70, 30)], [(80, 2), (80, 62)],
          [(16, 70), (16, 96), (74, 96)]],
    "디": [[(54, 16), (12, 16), (12, 90), (56, 90)], [(76, 4), (76, 104)]],
    "아": [[("O", 32, 54, 22)], [(70, 4), (70, 104)], [(70, 52), (90, 52)]],
}
EN = {  # 폭, 획
    "Z": (58, [[(4, 6), (54, 6), (4, 94), (54, 94)]]),
    "E": (50, [[(46, 6), (6, 6), (6, 94), (46, 94)], [(6, 50), (38, 50)]]),
    "A": (64, [[(4, 94), (32, 6), (60, 94)], [(16, 62), (48, 62)]]),
    "L": (46, [[(6, 4), (6, 94), (44, 94)]]),
    "N": (60, [[(6, 94), (6, 6), (54, 94), (54, 6)]]),
    "D": (60, [[(6, 6), (6, 94), (30, 94), ("ARC", 30, 50, 26, 44), (30, 6), (6, 6)]]),
    "I": (14, [[(7, 6), (7, 94)]]),
}


def wobble(pts, amp, seed, step=6):
    r = random.Random(seed); out = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        n = max(1, int(math.dist(pts[i], pts[i + 1]) / step))
        for k in range(n):
            t = k / n; out.append((x0 + (x1 - x0) * t + r.uniform(-amp, amp), y0 + (y1 - y0) * t + r.uniform(-amp, amp)))
    out.append(pts[-1])
    return out


def expand(stroke):
    """'O'(원)·'ARC'(D 의 둥근 등) 를 점 목록으로"""
    out = []
    for p in stroke:
        if p[0] == "O":
            _, cx, cy, r = p
            out += [(cx + r * math.cos(2 * math.pi * k / 40), cy + r * math.sin(2 * math.pi * k / 40)) for k in range(41)]
        elif p[0] == "ARC":
            _, cx, cy, rx, ry = p
            out += [(cx + rx * math.sin(math.pi * k / 20), cy + ry * math.cos(math.pi * k / 20)) for k in range(21)]
        else:
            out.append(p)
    return out


def word_mask(chars, table, box_w, h_px, weight, gap, seed=1, ko=True):
    """글자 → L 마스크(4배로 그려 줄임)"""
    SS = 4; unit = h_px / (110 if ko else 100) * SS
    widths = [(box_w if ko else table[c][0]) for c in chars]
    W = int((sum(widths) + gap * (len(chars) - 1)) * unit + weight * unit * 2)
    H = int(h_px * SS + weight * unit * 2)
    m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
    x0 = weight * unit
    for i, c in enumerate(chars):
        strokes = table[c] if ko else table[c][1]
        for j, st in enumerate(strokes):
            pts = expand(st)
            pts = wobble(pts, 0.9, seed * 100 + i * 10 + j)
            pp = [(x0 + x * unit, weight * unit + y * unit) for x, y in pts]
            wpx = int(weight * unit)
            d.line(pp, fill=255, width=wpx, joint="curve")
            for q in (pp[0], pp[-1]):
                d.ellipse([q[0] - wpx / 2, q[1] - wpx / 2, q[0] + wpx / 2, q[1] + wpx / 2], fill=255)
        x0 += (widths[i] + gap) * unit
    return m.resize((W // SS, H // SS), Image.LANCZOS)


def paint_word(mask, top, bottom=None, split=None, outline="#1C1712", ow=3, wave_seed=2, shadow=True, hl=True):
    """마스크 → 색 입힌 RGBA. split(0~1): 그 높이 아래는 물에 잠긴 색(bottom), 경계는 물결"""
    w, h = mask.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    col = np.zeros((h, w, 4), np.uint8)
    t = np.array(rgb(top)); col[..., :] = t
    if hl:                                                    # 위쪽 밝은 띠(등불 받은 면)
        yy = np.arange(h)[:, None]
        light = np.clip(1 - yy / (h * 0.55), 0, 1) * 30
        col[..., :3] = np.clip(col[..., :3].astype(int) + light[..., None].astype(int), 0, 255)
    if split is not None and bottom is not None:
        xx = np.arange(w)[None, :]
        line = h * split + 3.5 * np.sin(xx * 0.09 + wave_seed) + 1.5 * np.sin(xx * 0.23)
        under = (np.arange(h)[:, None] > line)
        col[under] = np.array(rgb(bottom))
    fill = Image.fromarray(col, "RGBA"); fill.putalpha(mask)
    if outline:
        ol = mask.filter(ImageFilter.MaxFilter(ow * 2 + 1))
        O = Image.new("RGBA", (w, h), rgb(outline)); O.putalpha(ol)
        if shadow:
            sh = Image.new("RGBA", (w, h), (0, 0, 0, 0)); sh.alpha_composite(O, (0, 0))
            out.alpha_composite(sh.transform(sh.size, Image.AFFINE, (1, 0, -3, 0, 1, -4)))
        out.alpha_composite(O)
    out.alpha_composite(fill)
    return out


def pad(im, p):
    o = Image.new("RGBA", (im.width + 2 * p, im.height + 2 * p), (0, 0, 0, 0)); o.alpha_composite(im, (p, p)); return o


def glow(img, cx, cy, r, col=(255, 196, 110), a=200):
    g = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*col, a))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(r * 0.5)))


def wave_pts(x0, x1, y, amp, freq, phase=0.0, step=4):
    return [(x, y + amp * math.sin(x * freq + phase)) for x in range(int(x0), int(x1) + 1, step)]


# ══════ 상징 셋 ══════
def icon_base(S, light=False):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    m = Image.new("L", (S, S), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, S - 1, S - 1], int(S * 0.22), fill=255)
    yy = np.linspace(0, 1, S)[:, None, None]
    top = np.array(rgb(P["sea_top"]))[:3]; bot = np.array(rgb(P["deep"]))[:3]
    if light:
        top = np.array(rgb("#F3EBD9"))[:3]; bot = np.array(rgb("#E2D6BC"))[:3]
    g = (top * (1 - yy) + bot * yy).repeat(S, axis=1)
    bg = Image.fromarray(g.astype("uint8"), "RGB").convert("RGBA"); bg.putalpha(m)
    im.alpha_composite(bg)
    return im, m


def symbol_A(S=512, light=False):
    """가라앉은 대륙: 둥근 땅 덩어리의 꼭대기만 물 위로, 몸 대부분은 물 아래 — 그 안에 불 켜진 창 하나"""
    im, m = icon_base(S, light); d = ImageDraw.Draw(im)
    k = S / 512; wl = 196 * k
    # 물 위(조금 밝은 물) — 물결선 위
    above = Image.new("RGBA", (S, S), (0, 0, 0, 0)); da = ImageDraw.Draw(above)
    da.polygon([(0, 0), (S, 0)] + [(x, y) for x, y in reversed(wave_pts(0, S, wl, 7 * k, 0.03 / k))], fill=rgb("#3C8A94" if not light else "#F7F1E4"))
    above.putalpha(ImageChops.multiply(above.getchannel("A"), m)); im.alpha_composite(above)
    # 땅 덩어리(추상 — 둥근 비대칭 언덕, 실제 지도 아님)
    # 두 봉우리 단면(추상): 오른쪽 봉우리만 물 위로 조금, 왼쪽 봉우리와 몸 대부분은 물 아래 — 실제 지도 아님
    r = random.Random(5); pts = []
    for i in range(0, 97):
        x = (16 + i * 5) * k
        hgt = 300 * math.exp(-((x / k - 320) / 120) ** 2) + 180 * math.exp(-((x / k - 150) / 100) ** 2)
        y = (470 - hgt) * k + r.uniform(-1.2, 1.2) * k
        pts.append((x, y))
    pts = [(pts[0][0], S), *pts, (pts[-1][0], S)]
    land = Image.new("RGBA", (S, S), (0, 0, 0, 0)); dl = ImageDraw.Draw(land)
    dl.polygon(pts, fill=rgb(P["land"] if not light else "#2F5A5E"))
    # 땅의 결(지층 줄 두 개 — 아래로 자란다)
    for j, yy in enumerate((330, 410)):
        dl.line(wave_pts(70 * k, 450 * k, yy * k, 4 * k, 0.04 / k, j), fill=rgb(P["land_d"] if not light else "#24484C"), width=int(6 * k))
    land.putalpha(ImageChops.multiply(land.getchannel("A"), m)); im.alpha_composite(land)
    d = ImageDraw.Draw(im)
    d.line(pts[1:-1], fill=rgb(P["ink"]), width=int(7 * k), joint="curve")
    # 물결선(꼭대기를 가로지른다)
    d.line(wave_pts(18 * k, S - 18 * k, wl, 7 * k, 0.03 / k), fill=rgb(P["teal_l"] if not light else "#3C8A94"), width=int(9 * k), joint="curve")
    # 불 켜진 창(아치) + 번짐
    cx, cy = 312 * k, 300 * k
    glow(im, cx, cy, 110 * k, a=170)
    d = ImageDraw.Draw(im)
    w, h = 62 * k, 84 * k
    d.rounded_rectangle([cx - w / 2, cy - h / 2 + w / 2, cx + w / 2, cy + h / 2], int(4 * k), fill=rgb(P["gold"]), outline=rgb(P["ink"]), width=int(7 * k))
    d.pieslice([cx - w / 2, cy - h / 2, cx + w / 2, cy - h / 2 + w], 180, 360, fill=rgb(P["gold"]), outline=rgb(P["ink"]), width=int(7 * k))
    d.rectangle([cx - w / 2 + 4 * k, cy - h / 2 + w / 2 - 2 * k, cx + w / 2 - 4 * k, cy - h / 2 + w / 2 + 6 * k], fill=rgb(P["gold"]))
    d.line([(cx, cy - h / 2 + 8 * k), (cx, cy + h / 2 - 4 * k)], fill=rgb(P["gold_d"]), width=int(6 * k))
    d.line([(cx - w / 2 + 6 * k, cy + 4 * k), (cx + w / 2 - 6 * k, cy + 4 * k)], fill=rgb(P["gold_d"]), width=int(6 * k))
    return im


def symbol_B(S=512, light=False):
    """물결 아래 가라앉은 건물(살짝 기운 탑) + 창 하나만 불"""
    im, m = icon_base(S, light); d = ImageDraw.Draw(im); k = S / 512
    d.line(wave_pts(30 * k, S - 30 * k, 110 * k, 8 * k, 0.03 / k), fill=rgb(P["teal_l"]), width=int(10 * k))
    d.line(wave_pts(60 * k, S - 60 * k, 140 * k, 5 * k, 0.04 / k, 1), fill=rgb(P["teal_l"], 140), width=int(6 * k))
    tower = Image.new("RGBA", (S, S), (0, 0, 0, 0)); dt = ImageDraw.Draw(tower)
    dt.rectangle([180 * k, 190 * k, 332 * k, S + 10], fill=rgb(P["land"]), outline=rgb(P["ink"]), width=int(7 * k))
    for i in range(3):
        for j in range(4):
            x = 200 * k + i * 44 * k; y = 214 * k + j * 64 * k
            lit = (i == 1 and j == 1)
            dt.rectangle([x, y, x + 28 * k, y + 40 * k], fill=rgb(P["gold"] if lit else "#14303A"), outline=rgb(P["ink"]), width=int(4 * k))
    tower = tower.rotate(-6, center=(256 * k, 400 * k), resample=Image.BICUBIC)
    tower.putalpha(ImageChops.multiply(tower.getchannel("A"), m))
    glow(im, 262 * k, 300 * k, 90 * k, a=150); im.alpha_composite(tower)
    return im


def symbol_C(S=512, light=False):
    """해저 비탈 위 유리 돔, 그 안에 등불 하나"""
    im, m = icon_base(S, light); d = ImageDraw.Draw(im); k = S / 512
    d.line(wave_pts(30 * k, S - 30 * k, 96 * k, 8 * k, 0.03 / k), fill=rgb(P["teal_l"]), width=int(10 * k))
    ground = Image.new("RGBA", (S, S), (0, 0, 0, 0)); dg = ImageDraw.Draw(ground)
    dg.polygon([(0, 380 * k), (S, 340 * k), (S, S), (0, S)], fill=rgb(P["land"]))
    ground.putalpha(ImageChops.multiply(ground.getchannel("A"), m)); im.alpha_composite(ground)
    glow(im, 256 * k, 300 * k, 120 * k, a=150); d = ImageDraw.Draw(im)
    d.pieslice([126 * k, 220 * k, 386 * k, 480 * k], 180, 360, fill=rgb("#4A8C90"), outline=rgb(P["ink"]), width=int(8 * k))
    for a in (225, 270, 315):
        d.line([(256 * k, 350 * k), (256 * k + 130 * k * math.cos(math.radians(a)), 350 * k + 130 * k * math.sin(math.radians(a)))], fill=rgb("#8A6A44"), width=int(6 * k))
    d.ellipse([232 * k, 270 * k, 280 * k, 318 * k], fill=rgb(P["gold"]), outline=rgb(P["ink"]), width=int(6 * k))
    d.line([(126 * k, 350 * k), (386 * k, 350 * k)], fill=rgb(P["ink"]), width=int(8 * k))
    return im


SYMBOLS = {"A": symbol_A, "B": symbol_B, "C": symbol_C}
SPLIT = {"A": 0.62, "B": None, "C": None}


def wordmarks(direction, light=False, ko_h=120, en_h=30):
    top = P["gold"] if not light else P["light_ink"]
    under = P["teal_l"] if not light else "#3C8A94"
    ko = word_mask(list("질랜디아"), KO, 100, ko_h, 15, 12, seed=3)
    kim = paint_word(ko, top, under if SPLIT[direction] else None, SPLIT[direction], outline=P["ink"] if not light else None, ow=4,
                     shadow=not light, hl=not light)
    en = word_mask(list("ZEALANDIA"), EN, 0, en_h, 9, 26, seed=4, ko=False)
    eim = paint_word(en, P["cream"] if not light else P["light_ink"], outline=None, shadow=False, hl=False)
    return pad(kim, 6), pad(eim, 4)


def lockup(direction, kind="h", light=False):
    sym = SYMBOLS[direction](512, light=False)            # 상징은 항상 어두운 물 바탕(앱 아이콘과 같다)
    kim, eim = wordmarks(direction, light)
    if kind == "h":
        s = sym.resize((220, 220), Image.LANCZOS)
        W = 40 + s.width + 40 + max(kim.width, eim.width) + 40; H = 300
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        im.alpha_composite(s, (40, (H - s.height) // 2))
        tx = 40 + s.width + 40
        im.alpha_composite(kim, (tx, 52)); im.alpha_composite(eim, (tx + 10, 52 + kim.height + 8))
    else:
        s = sym.resize((300, 300), Image.LANCZOS)
        W = max(kim.width, eim.width, s.width) + 80; H = 40 + s.height + 30 + kim.height + 10 + eim.height + 40
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        im.alpha_composite(s, ((W - s.width) // 2, 40))
        y = 40 + s.height + 30
        im.alpha_composite(kim, ((W - kim.width) // 2, y)); im.alpha_composite(eim, ((W - eim.width) // 2, y + kim.height + 10))
    return im


def on_bg(im, light, padpx=0):
    bg = Image.new("RGBA", (im.width + 2 * padpx, im.height + 2 * padpx), rgb(P["light_bg"] if light else P["deep"]))
    if not light:                                         # 어두운 바탕엔 바다눈 몇 점
        d = ImageDraw.Draw(bg); r = random.Random(1)
        for _ in range(int(bg.width * bg.height / 3000)):
            x, y = r.uniform(0, bg.width), r.uniform(0, bg.height); d.ellipse([x, y, x + 1.6, y + 1.6], fill=(160, 210, 205, r.randint(40, 110)))
    bg.alpha_composite(im, (padpx, padpx)); return bg


def options():
    from PIL import ImageFont
    f = lambda s: ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", s)
    rows = []
    for dname, title in (("A", "A · 가라앉은 대륙의 창 — 꼭대기만 물 위, 몸 안에 불빛 하나 / 글자 아랫부분이 물에 잠김"),
                         ("B", "B · 물결 아래 기운 탑 — 창 하나만 불"), ("C", "C · 비탈 위 유리 돔 + 등불")):
        sym = SYMBOLS[dname](512)
        h = on_bg(lockup(dname, "h"), False, 20); l = on_bg(lockup(dname, "h", light=True), True, 20)
        tiny = sym.resize((48, 48), Image.LANCZOS)
        rows.append((title, sym.resize((256, 256), Image.LANCZOS), tiny, h, l))
    W = 40 + 256 + 40 + 100 + max(r[3].width for r in rows) + 40
    H = 70 + sum(max(256, r[3].height + r[4].height + 20) + 70 for r in rows)
    S = Image.new("RGBA", (W, H), (18, 26, 30, 255)); d = ImageDraw.Draw(S)
    d.text((24, 18), "S20-L 「질랜디아」 로고 방향 셋 — 글꼴 없이 획으로 지은 글자 · 생성 AI 없음", font=f(26), fill=(232, 220, 191))
    y = 70
    for title, big, tiny, h, l in rows:
        d.text((24, y), title, font=f(20), fill=(240, 200, 120)); y += 34
        S.alpha_composite(big, (40, y))
        S.alpha_composite(tiny, (40 + 256 + 26, y + 20)); d.text((40 + 256 + 20, y + 74), "48px", font=f(14), fill=(200, 210, 205))
        tiny2 = tiny.resize((96, 96), Image.NEAREST); S.alpha_composite(tiny2, (40 + 256 + 4, y + 110))
        x = 40 + 256 + 40 + 100
        S.alpha_composite(h, (x, y)); S.alpha_composite(l, (x, y + h.height + 20))
        y += max(256, h.height + l.height + 20) + 36
    out = os.path.join(ROOT, "docs", "reports", "s20_logo_options.png")
    S.convert("RGB").save(out, optimize=True); print("options", out)


def final(dname):
    os.makedirs(DST, exist_ok=True)
    sym = SYMBOLS[dname](1024)
    sym.resize((512, 512), Image.LANCZOS).save(os.path.join(DST, "icon_512.png"), optimize=True)
    sym.resize((192, 192), Image.LANCZOS).save(os.path.join(DST, "icon_192.png"), optimize=True)
    sym.resize((48, 48), Image.LANCZOS).save(os.path.join(DST, "icon_48.png"), optimize=True)
    for light in (False, True):
        tag = "light" if light else "dark"
        kim, eim = wordmarks(dname, light, ko_h=200, en_h=46)
        kim.save(os.path.join(DST, f"wordmark_ko_{tag}.png"), optimize=True)
        eim.save(os.path.join(DST, f"wordmark_en_{tag}.png"), optimize=True)
        lockup(dname, "h", light).save(os.path.join(DST, f"lockup_horizontal_{tag}.png"), optimize=True)
        lockup(dname, "v", light).save(os.path.join(DST, f"lockup_stacked_{tag}.png"), optimize=True)
    # 확인용 미리보기(바탕 포함)
    prev = [on_bg(lockup(dname, "h"), False, 30), on_bg(lockup(dname, "h", True), True, 30),
            on_bg(lockup(dname, "v"), False, 30), on_bg(lockup(dname, "v", True), True, 30)]
    W = prev[0].width + prev[2].width + prev[3].width + 80; H = max(prev[0].height + prev[1].height + 20, prev[2].height) + 260
    S = Image.new("RGBA", (W, H), (18, 26, 30, 255))
    S.alpha_composite(prev[0], (20, 20)); S.alpha_composite(prev[1], (20, 40 + prev[0].height))
    S.alpha_composite(prev[2], (40 + prev[0].width, 20)); S.alpha_composite(prev[3], (60 + prev[0].width + prev[2].width, 20))
    y = max(prev[0].height + prev[1].height + 60, prev[2].height + 40); x = 20
    for s in (512, 192, 96, 48, 32):
        ic = Image.open(os.path.join(DST, "icon_512.png")).resize((min(s, 200), min(s, 200)) if s > 200 else (s, s), Image.LANCZOS)
        S.alpha_composite(ic, (x, y)); x += ic.width + 30
    out = os.path.join(ROOT, "docs", "reports", "s20_logo_final.png"); S.convert("RGB").save(out, optimize=True)
    tot = sum(os.path.getsize(os.path.join(DST, f)) for f in os.listdir(DST))
    print("final", dname, "total KB", tot // 1024)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "options":
        options()
    else:
        final(a[1] if len(a) > 1 else "A")
