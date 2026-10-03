# -*- coding: utf-8 -*-
"""
색맹 점검 (OPEN_GAPS B4) — 2026-10-01 / relic-bg

  python tools/check_colorblind.py            전체(판정표 + 판정 컷)
  python tools/check_colorblind.py table      숫자만 (콘솔)

우리는 **방을 색으로 구분한다**(아트 원리 §1-4). 남성의 약 8%가 적록색약이다.
그래서 묻는다 — 황토·올리브·적갈이 적록색약에게도 서로 다른 색인가.
아니라면 대비책은 이미 있다: 방마다 **고유 무늬**(REF §1-5). 그 무늬가
**색을 완전히 뺐을 때도** 방을 구분시키는지 같은 자리에서 확인한다.

판정 방법
  1. sRGB → 선형 RGB → Machado 2009 severity 1.0 행렬 → 선형 → sRGB
     (protanopia 적색맹 / deuteranopia 녹색맹 / tritanopia 청색맹)
  2. 방 색 6종의 **모든 쌍**에 대해 CIE76 ΔE 를 잰다. 넓은 단색 면끼리의 구분이므로
     ΔE 20 이상 = 넉넉 / 10~20 = 아슬 / 10 미만 = 구분 안 됨 으로 본다.
  3. 같은 일을 **명도만 남긴 판**(완전 흑백)에도 한다. 여기서 살아남는 차이는
     색맹 종류와 무관하게 언제나 작동하는 차이다 — 그게 무늬와 명도다.
  4. 결과를 **변환 전/후를 나란히 놓은 한 장**으로 찍는다. 이게 판정 자료다.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PLATE = os.path.join(ROOT, "art_raw", "plates")
OUT_DIR = os.path.join(ROOT, "art_raw", "accessibility")

# ── 시뮬레이션 행렬 (Machado, Oliveira, Fernandes 2009 — severity 1.0, 선형 RGB) ──
MATS = {
    "protan": ((0.152286, 1.052583, -0.204868),
               (0.114503, 0.786281, 0.099216),
               (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968),
               (0.280085, 0.672501, 0.047413),
               (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779),
               (-0.078411, 0.930809, 0.147602),
               (0.004733, 0.691367, 0.303900)),
}
KIND_KR = {"normal": "정상", "protan": "적색맹(protan)", "deutan": "녹색맹(deutan)",
           "tritan": "청색맹(tritan)", "gray": "명도만(흑백)"}

OK, WARN = 20.0, 10.0          # ΔE 판정 문턱(넓은 단색 면: 20↑ 확실히 다른 색, 10↓ 같은 색)


def _s2l(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _l2s(c):
    c = max(0.0, min(1.0, c))
    c = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return int(round(max(0.0, min(1.0, c)) * 255))


def sim_rgb(rgb, kind):
    """한 색을 색맹 시야로."""
    if kind == "normal":
        return tuple(rgb)
    if kind == "gray":                       # 명도만 — 색이 통째로 없을 때
        y = sum(a * b for a, b in zip((0.2126, 0.7152, 0.0722), map(_s2l, rgb)))
        return (_l2s(y),) * 3
    m = MATS[kind]
    lin = [_s2l(v) for v in rgb]
    return tuple(_l2s(sum(m[i][j] * lin[j] for j in range(3))) for i in range(3))


def sim_image(im, kind):
    """이미지 한 장을 색맹 시야로. 화소별 변환은 느려서 **LUT 로 한 번만** 만든다."""
    im = im.convert("RGB")
    if kind == "normal":
        return im
    if kind == "gray":
        return Image.merge("RGB", [im.convert("L")] * 3)
    # 채널별 1차 결합이라 채널 LUT 로는 못 한다 → 3×3 행렬 변환을 선형 공간에서 수행
    m = MATS[kind]
    lut = [_s2l(v) for v in range(256)]
    inv = [_l2s(v / 4095.0) for v in range(4096)]
    src = im.load()
    out = Image.new("RGB", im.size)
    dst = out.load()
    w, h = im.size
    cache = {}
    for y in range(h):
        for x in range(w):
            p = src[x, y]
            q = cache.get(p)
            if q is None:
                lr, lg, lb = lut[p[0]], lut[p[1]], lut[p[2]]
                q = tuple(inv[max(0, min(4095, int(
                    (m[i][0] * lr + m[i][1] * lg + m[i][2] * lb) * 4095)))] for i in range(3))
                cache[p] = q
            dst[x, y] = q
    return out


# ── CIE Lab / ΔE76 ───────────────────────────────────────────
def lab(rgb):
    r, g, b = (_s2l(v) for v in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def de76(a, b):
    la, lb_ = lab(a), lab(b)
    return sum((p - q) ** 2 for p, q in zip(la, lb_)) ** 0.5


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ── 방 색표 ──────────────────────────────────────────────────
def rooms():
    meta = json.load(open(os.path.join(RAW_PLATE, "plates_meta.json"), encoding="utf-8"))
    return [(r["id"], r["name"], r["hue"], r["files"]) for r in meta["rooms"]]


MOTIF_KR = {"quarters": "물결", "storage": "점", "workshop": "마름모",
            "infirmary": "×(붕대)", "power": "빗금", "greenhouse": "꺾쇠"}


def table(rs):
    """콘솔 판정표. 가장 가까운 쌍이 어디서 무너지는지가 전부다."""
    worst = {}
    for kind in ("normal", "protan", "deutan", "tritan", "gray"):
        cols = [(rid, nm, sim_rgb(hex2rgb(h), kind)) for rid, nm, h, _ in rs]
        print("\n== %s ==" % KIND_KR[kind])
        print("        " + "".join("%9s" % n for _, n, _ in cols))
        pairs = []
        for i, (ida, na, ca) in enumerate(cols):
            line = "%-8s" % na
            for j, (idb, nb, cb) in enumerate(cols):
                if i == j:
                    line += "%9s" % "·"
                    continue
                d = de76(ca, cb)
                line += "%9.1f" % d
                if i < j:
                    pairs.append((d, na, nb))
            print(line)
        pairs.sort()
        worst[kind] = pairs[:3]
        for d, a, b in pairs[:3]:
            mark = "OK  " if d >= OK else ("아슬" if d >= WARN else "실패")
            print("   가까운 쌍: %-5s %-5s ΔE %5.1f  %s" % (a, b, d, mark))
    return worst


# ── 판정 컷 ──────────────────────────────────────────────────
def font(sz):
    for p in ("C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/gulim.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


# 고치기 전 방 색(S8-C). 판정 컷에서 '전/후'를 나란히 놓기 위해 남겨 둔다.
BEFORE = {"quarters": "#C68F3E", "storage": "#8A6531", "workshop": "#B85A24",
          "infirmary": "#E6D8B4", "power": "#6E2A22", "greenhouse": "#6F7A3C"}
MOTIF_BEFORE = {"quarters": "지그재그", "storage": "점", "workshop": "톱니",
                "infirmary": "아치", "power": "빗금", "greenhouse": "꺾쇠"}


def _pairs(cols, kind):
    c = [(n, sim_rgb(v, kind)) for n, v in cols]
    return sorted((de76(a[1], b[1]), a[0], b[0]) for i, a in enumerate(c) for b in c[i + 1:])


def sheet(rs):
    f_h, f_m, f_s = font(22), font(16), font(13)
    W = 1500
    SW, SH = 120, 64
    PW, PH = 252, 142
    out = Image.new("RGB", (W, 3200), (16, 14, 12))
    d = ImageDraw.Draw(out)
    y = 0

    def hdr(t, sub):
        nonlocal y
        d.rectangle([0, y, W, y + 2], fill=(90, 70, 46))
        d.text((10, y + 10), t, font=f_h, fill=(236, 206, 152))
        d.text((10, y + 38), sub, font=f_s, fill=(160, 142, 116))
        y += 64

    def badge(x, yy, dd):
        col = (92, 196, 120) if dd >= 20 else ((224, 176, 64) if dd >= 10 else (226, 84, 70))
        d.text((x, yy), "%.1f" % dd, font=f_m, fill=col)

    # ── A. 방 색: 고치기 전 / 후, 각각 정상·적색맹·녹색맹 ──
    hdr("A. 방 색 6종 — 고치기 전(S8) / 고친 뒤(S10), 각각 세 가지 눈",
        "왼쪽 셋이 문제였다: 창고·공방·온실이 적록색약 눈에 한 색. 오른쪽 넷은 명도 사다리를 적용한 뒤")
    left = 100
    kinds_b = ("normal", "protan", "deutan")
    kinds_a = ("normal", "protan", "deutan", "gray")
    for i, k in enumerate(kinds_b):
        d.text((left + i * (SW + 8), y), "전 · " + KIND_KR[k].split("(")[0], font=f_s, fill=(200, 150, 120))
    ox = left + 3 * (SW + 8) + 40
    for i, k in enumerate(kinds_a):
        d.text((ox + i * (SW + 8), y), "후 · " + KIND_KR[k].split("(")[0], font=f_s, fill=(150, 214, 150))
    y += 22
    for rid, nm, h, _ in rs:
        d.text((8, y + 12), nm, font=f_m, fill=(226, 206, 170))
        d.text((8, y + 36), "%s→%s" % (BEFORE[rid][1:], h[1:]), font=font(10), fill=(140, 124, 104))
        for i, k in enumerate(kinds_b):
            d.rectangle([left + i * (SW + 8), y, left + i * (SW + 8) + SW, y + SH],
                        fill=sim_rgb(hex2rgb(BEFORE[rid]), k))
        for i, k in enumerate(kinds_a):
            d.rectangle([ox + i * (SW + 8), y, ox + i * (SW + 8) + SW, y + SH],
                        fill=sim_rgb(hex2rgb(h), k))
        y += SH + 6
    y += 14

    # ── B. 가장 가까운 쌍 ──
    hdr("B. 가장 가까운 세 쌍의 ΔE(CIE76) — 20↑ 초록 / 10~20 노랑 / 10↓ 빨강",
        "이 숫자가 곧 '플레이어가 방을 헷갈리는 곳'이다. 흑백은 색이 통째로 없을 때(최악)")
    cb = [(nm, hex2rgb(BEFORE[rid])) for rid, nm, h, _ in rs]
    ca = [(nm, hex2rgb(h)) for rid, nm, h, _ in rs]
    for ci, k in enumerate(("protan", "deutan", "gray")):
        x = 20 + ci * 490
        d.text((x, y), KIND_KR[k], font=f_m, fill=(214, 186, 142))
        for j, (pb, pa) in enumerate(zip(_pairs(cb, k)[:3], _pairs(ca, k)[:3])):
            yy = y + 26 + j * 24
            d.text((x, yy), "전 %s–%s" % (pb[1], pb[2]), font=f_s, fill=(190, 170, 150))
            badge(x + 150, yy - 2, pb[0])
            d.text((x + 230, yy), "후 %s–%s" % (pa[1], pa[2]), font=f_s, fill=(190, 170, 150))
            badge(x + 380, yy - 2, pa[0])
    y += 26 + 3 * 24 + 20

    # ── C/D. 플레이트 ──
    def plate_block(title, sub, state, kinds):
        nonlocal y
        hdr(title, sub)
        for i, k in enumerate(kinds):
            d.text((left + i * (PW + 12), y), KIND_KR[k], font=f_m, fill=(214, 186, 142))
        y += 24
        for rid, nm, h, files in rs:
            p = os.path.join(RAW_PLATE, files[state])
            d.text((6, y + 40), nm, font=f_m, fill=(226, 206, 170))
            d.text((6, y + 62), "무늬 " + MOTIF_KR.get(rid, "?"), font=f_s, fill=(150, 134, 112))
            if os.path.exists(p):
                im = Image.open(p).convert("RGB").resize((PW, PH), Image.LANCZOS)
                for i, k in enumerate(kinds):
                    out.paste(sim_image(im, k), (left + i * (PW + 12), y))
            y += PH + 6
        y += 10

    plate_block("C. 빈 방(색 + 무늬만) — 고친 뒤", "무늬: 거주 물결 · 창고 점 · 공방 마름모 · 의무실 × · "
                "발전실 빗금 · 온실 꺾쇠. 무늬와 벽의 명도차를 L* 26 으로 고정", "dark",
                ("normal", "protan", "deutan", "gray"))
    plate_block("D. 등불 켠 방(소품 있음) — 고친 뒤", "실제 플레이 화면. 소품이 무늬를 가리는가 — 위쪽 띠가 남아야 한다",
                "lit", ("normal", "protan", "deutan", "gray"))
    out = out.crop((0, 0, W, y + 10))
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "colorblind_check.png")
    out.save(p, optimize=True)
    print("SHEET", p, out.size, "%.0f KB" % (os.path.getsize(p) / 1024))
    return p


if __name__ == "__main__":
    rs = rooms()
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    table(rs)
    if mode != "table":
        sheet(rs)
