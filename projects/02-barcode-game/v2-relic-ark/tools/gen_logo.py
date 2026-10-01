# -*- coding: utf-8 -*-
"""
gen_logo.py — 「깊은 등불」 로고 시안 생성기 (S8 브랜드)

생성 AI 이미지를 쓰지 않는다. Pillow + numpy로 전부 직접 그린다.

산출: static/art/brand/*.png
  1단계: 로고 컨셉 L1~L4 × 제목 T1 (ko/en)
  2단계: 최우수 컨셉(L1) × 제목 T2~T5 (ko/en)
  각 세트: wide / wide_bw / sq / sq_bw / sq64 / sq64_bw (+ 64px 확대 검수본)

폰트: Noto Sans KR (SIL Open Font License 1.1) — 상업 이용·수정·재배포 가능.
      C:\\Windows\\Fonts\\NotoSansKR-VF.ttf 가변 폰트의 'Black'·'Medium' 인스턴스.

정사각 아이콘 방침: L1~L3은 **글자 없는 마크 단독**이다. 한글 네 글자를 64px에
넣으면 글자당 10px이 되어 반드시 뭉갠다. 언어판 구분은 가로형이 담당한다.
L4는 글자 자체가 마크이므로 정사각도 한/영이 다르다.

실행:  python tools/gen_logo.py            (전체)
       python tools/gen_logo.py stage1     (1단계만)
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "art", "brand")
GAME_SHOT = os.path.join(ROOT, "static", "art", "deep", "section_warm.png")
FONT_PATH = r"C:\Windows\Fonts\NotoSansKR-VF.ttf"
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------------------
# 팔레트 — REF_ART_FLAT_FOLK.md §5 + section_warm.png 실측값
# 청록~남색은 물에만. 글자·마크·실내는 흙 팔레트.
# ----------------------------------------------------------------------------
CREAM = (246, 236, 212)
BONE = (228, 210, 179)
OCHRE = (209, 154, 64)
AMBER = (240, 189, 96)
LAMP = (255, 232, 168)
BURNT = (186, 100, 42)
OX = (136, 54, 38)
OLIVE = (124, 122, 68)
WOOD = (103, 75, 36)
WOOD_D = (54, 39, 20)
CHAR = (18, 15, 12)

WATER_RAMP = [
    (0.00, (29, 96, 112)), (0.18, (22, 79, 96)), (0.38, (13, 49, 62)),
    (0.58, (7, 27, 35)), (0.80, (2, 9, 14)), (1.00, (0, 3, 5)),
]
# L1 막대가 깊이를 따라 가는 색: 뼈 → 황토 → 올리브 → 청록 → 검정
BAR_RAMP = [
    (0.00, (247, 238, 216)), (0.16, (233, 217, 186)), (0.34, (198, 163, 101)),
    (0.52, (124, 123, 80)), (0.70, (44, 90, 100)), (0.86, (18, 50, 64)),
    (1.00, (6, 22, 30)),
]


def ramp_col(rmp, tarr):
    xs = np.array([p[0] for p in rmp], np.float32)
    cs = np.array([p[1] for p in rmp], np.float32)
    out = np.empty(np.shape(tarr) + (3,), np.float32)
    for k in range(3):
        out[..., k] = np.interp(np.clip(tarr, 0, 1), xs, cs[:, k])
    return out


def C(c):
    return np.array(c, np.float32)


# ----------------------------------------------------------------------------
# 손맛 도구 — 블러 / 노이즈 / 워프 / 팽창
# ----------------------------------------------------------------------------
def _box1d(a, r, axis):
    if r < 1:
        return a
    k = 2 * r + 1
    L = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode="edge")
    zs = list(p.shape)
    zs[axis] = 1
    c = np.concatenate([np.zeros(zs, np.float32),
                        np.cumsum(p, axis=axis, dtype=np.float32)], axis=axis)
    hi = [slice(None)] * a.ndim
    lo = [slice(None)] * a.ndim
    hi[axis] = slice(k, k + L)
    lo[axis] = slice(0, L)
    return (c[tuple(hi)] - c[tuple(lo)]) / float(k)


def gblur(a, sx, sy=None):
    if sy is None:
        sy = sx
    a = a.astype(np.float32)
    rx, ry = max(0, int(round(sx * 0.9))), max(0, int(round(sy * 0.9)))
    for _ in range(3):
        if rx:
            a = _box1d(a, rx, 1)
        if ry:
            a = _box1d(a, ry, 0)
    return a


def dilate(m, r):
    """근사 팽창 — 키라인(외곽선)용."""
    if r <= 0:
        return m
    return np.clip(gblur(m, r * 0.62) * 3.2, 0, 1)


def vnoise(h, w, cells, seed, octaves=3):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot, c = 1.0, 0.0, float(cells)
    for _ in range(octaves):
        n = max(2, int(round(c)))
        g = (rng.random((n, n)) * 255).astype(np.uint8)
        out += (np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC),
                           np.float32) / 255.0) * amp
        tot += amp
        amp *= 0.5
        c *= 2.0
    return (out / tot) * 2.0 - 1.0


def warp(img, dx, dy):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    sx = np.clip(xx + dx, 0, w - 1.001)
    sy = np.clip(yy + dy, 0, h - 1.001)
    x0, y0 = sx.astype(np.int32), sy.astype(np.int32)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = sx - x0, sy - y0
    if img.ndim == 3:
        fx, fy = fx[..., None], fy[..., None]
    a, b, c, d = img[y0, x0], img[y0, x1], img[y1, x0], img[y1, x1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def handwobble(mask, amp=2.0, cells=7, seed=0, bite=0.16):
    """매끈한 벡터 가장자리를 손으로 그은 떨림과 거친 결로 바꾼다."""
    h, w = mask.shape
    m = warp(mask, vnoise(h, w, cells, seed) * amp,
             vnoise(h, w, cells, seed + 991) * amp)
    n = vnoise(h, w, cells * 9, seed + 77) * bite
    return np.clip((m + n - bite * 0.5) * 1.22, 0, 1)


def draw_mask(w, h, fn):
    im = Image.new("L", (w, h), 0)
    fn(ImageDraw.Draw(im))
    return np.asarray(im, np.float32) / 255.0


def over(dst, color, mask, alpha=1.0):
    m = (np.clip(mask, 0, 1) * alpha)[..., None]
    col = color if (isinstance(color, np.ndarray) and color.ndim == 3) else C(color)
    return dst * (1 - m) + col * m


def add_glow(dst, cx, cy, radius, color, strength=1.0, falloff=2.2):
    h, w = dst.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / float(radius)
    g = np.clip(1.0 - d, 0, 1) ** falloff * strength
    return np.clip(dst + C(color)[None, None, :] * g[..., None], 0, 255)


# ----------------------------------------------------------------------------
# 배경 — 검은 물
# ----------------------------------------------------------------------------
def water_bg(w, h, t0=0.02, t1=1.0, seed=3):
    t = np.linspace(t0, t1, h, dtype=np.float32)[:, None].repeat(w, 1)
    t = np.clip(t + vnoise(h, w, 3, seed) * 0.035, 0, 1)
    bg = ramp_col(WATER_RAMP, t)
    rng = np.random.default_rng(seed + 12)
    pm = np.zeros((h, w), np.float32)
    for _ in range(int(w * h / 5200)):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        r = int(rng.integers(1, max(2, w // 420) + 2))
        a = float(rng.random()) * 0.5 + 0.12
        pm[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = a
    pm = gblur(pm, 0.9)
    fade = np.clip(1.25 - np.linspace(t0, t1, h, dtype=np.float32), 0.15, 1)[:, None]
    return over(bg, (150, 185, 190), pm * fade * 0.5)


def finish(arr, seed=5, grain=0.055, vignette=0.30):
    h, w = arr.shape[:2]
    g = vnoise(h, w, max(6, w // 14), seed, octaves=4)
    fine = vnoise(h, w, max(24, w // 3), seed + 4, octaves=2)
    arr = arr * (1.0 + (g * 0.6 + fine * 0.4) * grain * 2.0)[..., None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    arr = arr * (1.0 - np.clip((d - 0.55) / 0.9, 0, 1) * vignette)[..., None]
    return np.clip(arr, 0, 255)


def to_img(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


# ----------------------------------------------------------------------------
# 글자 — Noto Sans KR Black (OFL 1.1) + 목판 인쇄 처리
# ----------------------------------------------------------------------------
_FONT_CACHE = {}


def get_font(px, weight="Black"):
    key = (int(px), weight)
    if key not in _FONT_CACHE:
        f = ImageFont.truetype(FONT_PATH, int(px))
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
        _FONT_CACHE[key] = f
    return _FONT_CACHE[key]


def text_mask(text, px, weight="Black", tracking=0.0):
    font = get_font(px, weight)
    tr = tracking * px
    adv = [font.getlength(ch) for ch in text]
    total = sum(adv) + tr * max(0, len(text) - 1)
    pad = int(px * 0.5)
    W, H = int(total) + pad * 2, int(px * 1.75) + pad * 2
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    x, base = float(pad), pad + int(px * 1.22)
    for i, ch in enumerate(text):
        d.text((x, base), ch, font=font, fill=255, anchor="ls")
        x += adv[i] + tr
    return np.asarray(im, np.float32) / 255.0


def crop_mask(m, margin=0):
    ys, xs = np.nonzero(m > 0.25)
    if len(xs) == 0:
        return m
    return m[max(0, ys.min() - margin):min(m.shape[0], ys.max() + 1 + margin),
             max(0, xs.min() - margin):min(m.shape[1], xs.max() + 1 + margin)]


def make_wordmark(text, px, tracking=0.0, seed=1, weight="Black"):
    m = crop_mask(text_mask(text, px, weight=weight, tracking=tracking),
                  margin=max(3, px // 12))
    return handwobble(m, amp=max(0.8, px * 0.010), cells=max(5, int(px / 30)),
                      seed=seed, bite=0.13)


def paste_mask(shape, m, x, y):
    H, W = shape
    out = np.zeros((H, W), np.float32)
    h, w = m.shape
    x, y = int(x), int(y)
    sx0, sy0 = max(0, -x), max(0, -y)
    dx0, dy0 = max(0, x), max(0, y)
    cw, ch = min(w - sx0, W - dx0), min(h - sy0, H - dy0)
    if cw > 0 and ch > 0:
        out[dy0:dy0 + ch, dx0:dx0 + cw] = m[sy0:sy0 + ch, sx0:sx0 + cw]
    return out


def ink_text(arr, m, light=CREAM, dark=OCHRE, split=0.58, seed=2, keyline=True):
    """목판 인쇄 느낌: 어두운 후광 → 숯검정 키라인 → 숯검정 그림자 →
    크림/황토 2단 평면 + 인쇄 결."""
    H, W = arr.shape[:2]
    ys, xs = np.nonzero(m > 0.3)
    if len(ys) == 0:
        return arr
    y0, y1 = ys.min(), ys.max()
    h = max(1, y1 - y0)

    arr = over(arr, (0, 4, 7), gblur(m, h * 0.10) * 0.60)          # 물에서 떼어 놓는 후광
    if keyline:
        arr = over(arr, CHAR, dilate(m, h * 0.030), 0.95)          # 키라인
    off = max(2.0, h * 0.030)
    arr = over(arr, CHAR, warp(m, -off, -off * 1.15) * 0.92)       # 그림자

    yy = np.mgrid[0:H, 0:W][0].astype(np.float32)
    line = y0 + h * split + vnoise(H, W, 8, seed) * (h * 0.035)
    lower = np.clip((yy - line) / max(1.0, h * 0.012), 0, 1)       # 단단한 2단 경계
    col = C(light)[None, None, :] * (1 - lower[..., None]) + \
        C(dark)[None, None, :] * lower[..., None]
    speck = 1.0 + vnoise(H, W, max(30, W // 6), seed + 5, octaves=2) * 0.085
    arr = over(arr, np.clip(col * speck[..., None], 0, 255), m)
    seam = np.clip(1.0 - np.abs(yy - line) / max(1.0, h * 0.011), 0, 1)
    arr = over(arr, BURNT, seam * m, 0.55)                          # 2단 경계의 잉크 이음매
    return arr


# ============================================================================
# L1 — 성문이 수심선이 된다  ★ 주력
#   바코드 막대가 아래로 내려갈수록 길어지고(바깥으로 벌어지고) 흐려져
#   수심의 지층이 된다. 맨 아래 막대들 사이에 아주 작은 등불 하나.
# ============================================================================
def mark_L1(S, bg=None, seed=11):
    H = W = S
    arr = water_bg(W, H, t0=0.08, t1=1.0, seed=seed) if bg is None else bg.copy()
    rng = np.random.default_rng(seed)

    pad_x = S * 0.088
    y_top = S * 0.080
    y_bot = S * 0.995
    span = y_bot - y_top
    cx = W * 0.5
    T_CODE = 0.335          # 여기까지는 칼같은 바코드, 그 아래부터 물에 번진다

    # --- 1차원 바코드 프로필: 진짜 바코드다운 모듈 폭(1x~4x), 좁은 간격
    prof = np.zeros(W, np.float32)
    extl = np.zeros(W, np.float32)   # 막대마다 "얼마나 깊이 내려가는가"
    inner = W - pad_x * 2
    pattern = []
    tot = 0
    while tot < 96:
        bw = int(rng.choice([1, 1, 1, 1, 2, 2, 3, 4]))
        gp = int(rng.choice([1, 1, 1, 1, 2, 2, 3]))
        pattern.append((bw, gp))
        tot += bw + gp
    u = inner / float(tot)
    x = pad_x
    for bw, gp in pattern:
        x0, x1 = int(round(x)), int(round(x + bw * u))
        prof[max(0, x0):min(W, x1)] = 1.0
        # 가운데 막대일수록 깊이 내려간다 + 불규칙
        c = abs((x0 + x1) * 0.5 - cx) / (inner * 0.5)
        extl[max(0, x0):min(W, x1)] = float(
            np.clip(1.05 - 0.30 * (c ** 1.8) - rng.random() * 0.26, T_CODE + 0.20, 1.0))
        x += (bw + gp) * u
    # 가드 바 — 바코드의 그 양끝 두 줄
    gw = max(1, int(round(u)))
    for gx in (int(pad_x), int(pad_x) + int(u * 2),
               int(W - pad_x) - gw, int(W - pad_x) - int(u * 2) - gw):
        prof[gx:gx + gw] = 1.0
        extl[gx:gx + gw] = 0.995

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = np.clip((yy - y_top) / span, 0, 1)
    xs_idx = np.arange(W, dtype=np.float32)

    # (a) 성문 — 번지지 않는 바코드 블록
    block = np.interp(xx.ravel(), xs_idx, prof).reshape(H, W).astype(np.float32)
    block *= np.clip((yy - y_top) / (S * 0.005), 0, 1) * np.clip((y_top + span * T_CODE - yy) / (S * 0.004), 0, 1)
    block = handwobble(block, amp=S * 0.0013, cells=18, seed=seed + 3, bite=0.08)

    # (b) 수심선 — 블록 아래로 뻗으며 벌어지고 흐려지고 어두워진다
    dt = np.clip((t - T_CODE) / (1 - T_CODE), 0, 1)
    scale = 1.0 + 0.40 * (dt ** 1.35)
    sxs = cx + (xx - cx) / scale + vnoise(H, W, 4, seed + 2) * (S * 0.012) * dt
    ext = np.interp(sxs.ravel(), xs_idx, prof).reshape(H, W).astype(np.float32)
    extd = np.interp(sxs.ravel(), xs_idx, extl).reshape(H, W).astype(np.float32)
    ext *= np.clip((extd - t) / 0.09, 0, 1)                    # 막대마다 다른 끝
    ext *= np.clip((yy - (y_top + span * T_CODE)) / (S * 0.004), 0, 1)

    sigmas = [S * 0.004, S * 0.020, S * 0.055, S * 0.125, S * 0.255]
    centers = [0.0, 0.22, 0.45, 0.72, 1.0]
    acc = np.zeros((H, W), np.float32)
    wsum = np.zeros((H, W), np.float32)
    for tc, sig in zip(centers, sigmas):
        wgt = np.clip(1.0 - np.abs(dt - tc) / 0.30, 0, 1) ** 1.2
        acc += gblur(ext, sig, sig * 0.08) * wgt
        wsum += wgt
    ext = acc / np.maximum(wsum, 1e-5)

    # --- 색·불투명도
    arr = over(arr, ramp_col(BAR_RAMP, t), ext * np.clip(1.0 - dt * 0.34, 0.44, 1.0))
    arr = over(arr, ramp_col(BAR_RAMP, t * 0.55), block)
    field2 = np.maximum(block, ext)

    # --- 수심선(지층) — 아래로 갈수록 촘촘해지는 가로 띠
    for k, ty in enumerate([0.455, 0.575, 0.675, 0.760, 0.832, 0.892]):
        yl = y_top + span * ty
        th = S * (0.0050 + 0.0014 * k)
        wob = vnoise(H, W, 4, seed + 40 + k) * (S * 0.011)
        dy = (yy + wob) - yl
        arr = over(arr, (4, 18, 25), np.clip(1 - np.abs(dy) / th, 0, 1) * (0.34 + 0.06 * k))
        arr = over(arr, (72, 136, 146),
                   np.clip(1 - np.abs(dy + th * 1.9) / (th * 0.55), 0, 1) * 0.30)

    # --- 맨 아래, 아주 작은 등불 하나
    lx = pad_x + inner * 0.385
    ly = y_top + span * 0.845
    gr = S * 0.175
    arr = add_glow(arr, lx, ly, gr * 2.3, (30, 21, 7), 1.0, 2.6)
    arr = add_glow(arr, lx, ly, gr * 1.15, (142, 97, 30), 1.0, 2.0)
    arr = add_glow(arr, lx, ly, gr * 0.50, (196, 146, 58), 1.0, 1.6)

    lw, lh = S * 0.021, S * 0.029

    def _lamp(d):
        d.polygon([(lx - lw * .85, ly + lh * .52), (lx + lw * .85, ly + lh * .52),
                   (lx + lw * .55, ly - lh * .50), (lx - lw * .55, ly - lh * .50)], fill=255)
        d.rectangle([lx - lw * 1.0, ly - lh * .76, lx + lw * 1.0, ly - lh * .46], fill=255)
        d.line([lx, ly - lh * .76, lx, ly - lh * 1.7], fill=255, width=max(1, int(S * .0042)))
    arr = over(arr, CHAR, handwobble(draw_mask(W, H, _lamp), amp=S * .0014,
                                     cells=14, seed=seed + 9, bite=.08))

    def _core(d):
        d.rectangle([lx - lw * .48, ly - lh * .34, lx + lw * .48, ly + lh * .34], fill=255)
    arr = over(arr, LAMP, gblur(draw_mask(W, H, _core), S * 0.0024))
    arr = add_glow(arr, lx, ly, gr * 0.19, (255, 243, 210), 1.0, 1.1)

    # 등불이 주변 지층을 데운다 (D3)
    dd = np.sqrt((xx - lx) ** 2 + (yy - ly) ** 2) / (gr * 2.1)
    arr = np.clip(arr + C((126, 80, 26))[None, None, :] *
                  ((np.clip(1 - dd, 0, 1) ** 2.0) * field2 * 1.25)[..., None], 0, 255)
    return arr


# ============================================================================
# L2 — 등불이 곧 돔
# ============================================================================
def mark_L2(S, bg=None, seed=21):
    H = W = S
    arr = water_bg(W, H, t0=0.24, t1=1.0, seed=seed) if bg is None else bg.copy()
    cx, cy = W * 0.5, H * 0.545
    R = S * 0.315
    ring = S * 0.032

    arr = add_glow(arr, cx, cy, R * 2.7, (30, 22, 8), 1.0, 2.4)
    arr = add_glow(arr, cx, cy, R * 1.6, (96, 60, 17), 1.0, 2.2)

    def _disc(d):
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    disc = handwobble(draw_mask(W, H, _disc), amp=S * .004, cells=7, seed=seed + 1, bite=.10)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / R
    arr = over(arr, ramp_col([(0, AMBER), (.55, OCHRE), (1, (146, 88, 32))],
                             np.clip(rr, 0, 1)), disc)

    # 방 세 칸 — 각 방이 고유 색을 갖는다 (CONCEPT §6 D1)
    rooms = [(-0.62, -0.20, (240, 188, 101)),    # 호박 — 거실
             (-0.20, 0.22, (178, 168, 94)),      # 탁한 올리브 — 온실
             (0.22, 0.64, (178, 106, 58))]       # 적동 — 작업실
    fh = S * 0.024
    rng = np.random.default_rng(seed + 5)
    for fi, (ya, yb, rc) in enumerate(rooms):
        y0, y1 = cy + R * ya, cy + R * yb

        def _room(d, y0=y0, y1=y1):
            d.rectangle([cx - R, y0, cx + R, y1], fill=255)
        rm = draw_mask(W, H, _room) * disc
        arr = over(arr, rc, rm, 0.95)
        arr = add_glow(arr, cx, y0 + (y1 - y0) * 0.30, R * 0.62,
                       (74, 48, 14), 1.0, 1.9)                       # 천장 등 빛 웅덩이

        def _fl(d, y1=y1):
            d.rectangle([cx - R, y1 - fh * 0.5, cx + R, y1 + fh * 0.5], fill=255)
        arr = over(arr, WOOD_D, handwobble(draw_mask(W, H, _fl), amp=S * .0024,
                                           cells=16, seed=seed + 20 + fi, bite=.09) * disc)
        # 사람
        n = 3 if fi == 1 else 2
        pm = np.zeros((H, W), np.float32)
        for p in range(n):
            px = cx + (p - (n - 1) / 2.0) * R * 0.66 + (rng.random() - .5) * S * .012
            ph = S * 0.050

            def _p(d, px=px, ph=ph, y1=y1):
                d.ellipse([px - ph * .30, y1 - fh * .5 - ph, px + ph * .30,
                           y1 - fh * .5 - ph * .42], fill=255)
                d.polygon([(px - ph * .37, y1 - fh * .5), (px + ph * .37, y1 - fh * .5),
                           (px + ph * .26, y1 - fh * .5 - ph * .50),
                           (px - ph * .26, y1 - fh * .5 - ph * .50)], fill=255)
            pm += draw_mask(W, H, _p)
        arr = over(arr, (44, 29, 15), handwobble(np.clip(pm, 0, 1), amp=S * .0016,
                                                 cells=18, seed=seed + 31 + fi, bite=.07) * disc, .92)

    # 유리 세로 살 — 등불의 살이자 돔의 늑재
    ribs = np.zeros((H, W), np.float32)
    for f in (-0.56, 0.56):
        rx = cx + R * f
        rw = S * 0.012

        def _rib(d, rx=rx, rw=rw):
            d.rectangle([rx - rw, cy - R, rx + rw, cy + R], fill=255)
        ribs += draw_mask(W, H, _rib)
    arr = over(arr, CHAR, np.clip(ribs, 0, 1) * disc, 0.55)

    # 테두리
    def _ring(d):
        d.ellipse([cx - R - ring, cy - R - ring, cx + R + ring, cy + R + ring], fill=255)
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=0)
    arr = over(arr, CHAR, handwobble(draw_mask(W, H, _ring), amp=S * .004,
                                     cells=7, seed=seed + 1, bite=.10))

    # D4 유리는 두 번 보인다 — 반사(뼈)와 투과(청록)
    def _hl(d):
        d.arc([cx - R * .80, cy - R * .80, cx + R * .80, cy + R * .80], 198, 248,
              fill=255, width=max(2, int(S * .017)))
    arr = over(arr, CREAM, gblur(handwobble(draw_mask(W, H, _hl), amp=S * .003,
                                            cells=9, seed=seed + 2), S * .002), .60)

    def _tr(d):
        d.arc([cx - R * .90, cy - R * .90, cx + R * .90, cy + R * .90], 28, 82,
              fill=255, width=max(2, int(S * .012)))
    arr = over(arr, (70, 150, 164), gblur(draw_mask(W, H, _tr), S * .004), .38)

    # 등불의 갓(위)과 받침(아래) — 구슬 장식이 아니라 등불로 읽히게 하는 핵심
    def _cap(d):
        top = cy - R - ring
        d.polygon([(cx - S * .175, top + S * .030), (cx + S * .175, top + S * .030),
                   (cx + S * .085, top - S * .060), (cx - S * .085, top - S * .060)], fill=255)
        d.rectangle([cx - S * .040, top - S * .098, cx + S * .040, top - S * .052], fill=255)
        d.arc([cx - S * .052, top - S * .170, cx + S * .052, top - S * .080], 180, 360,
              fill=255, width=max(3, int(S * .018)))
    arr = over(arr, CHAR, handwobble(draw_mask(W, H, _cap), amp=S * .003,
                                     cells=10, seed=seed + 4, bite=.09))

    def _base(d):
        b = cy + R + ring
        d.polygon([(cx - S * .090, b - S * .026), (cx + S * .090, b - S * .026),
                   (cx + S * .176, b + S * .036), (cx - S * .176, b + S * .036)], fill=255)
        d.rectangle([cx - S * .205, b + S * .030, cx + S * .205, b + S * .066], fill=255)
    arr = over(arr, CHAR, handwobble(draw_mask(W, H, _base), amp=S * .003,
                                     cells=10, seed=seed + 6, bite=.09))
    return arr


# ============================================================================
# L3 — 아래로 뻗는 척추  (게임 화면의 영웅 실루엣 그대로)
# ============================================================================
def mark_L3(S, bg=None, seed=31):
    H = W = S
    arr = water_bg(W, H, t0=0.10, t1=1.0, seed=seed) if bg is None else bg.copy()
    cx = W * 0.5
    R = S * 0.125
    cy = S * 0.150

    arr = add_glow(arr, cx, cy, R * 3.2, (26, 19, 7), 1.0, 2.4)
    arr = add_glow(arr, cx, cy, R * 1.8, (104, 66, 20), 1.0, 2.1)

    # 꼭대기 돔 + 바깥 테 고리
    def _ringo(d):
        d.ellipse([cx - R * 1.72, cy - R * 1.72, cx + R * 1.72, cy + R * 1.72],
                  outline=255, width=max(2, int(S * .010)))
        for a in range(0, 360, 45):
            d.line([cx + R * 1.0 * math.cos(math.radians(a)),
                    cy + R * 1.0 * math.sin(math.radians(a)),
                    cx + R * 1.72 * math.cos(math.radians(a)),
                    cy + R * 1.72 * math.sin(math.radians(a))],
                   fill=255, width=max(2, int(S * .007)))
    arr = over(arr, WOOD_D, handwobble(draw_mask(W, H, _ringo), amp=S * .0022,
                                       cells=12, seed=seed + 7, bite=.08), .85)

    def _dome(d):
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    dome = handwobble(draw_mask(W, H, _dome), amp=S * .0035, cells=8, seed=seed + 1, bite=.09)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / R
    arr = over(arr, ramp_col([(0, AMBER), (.6, OCHRE), (1, (142, 86, 32))],
                             np.clip(rr, 0, 1)), dome)

    def _dfl(d):
        d.rectangle([cx - R, cy + R * .22, cx + R, cy + R * .38], fill=255)
        for p in range(3):
            px = cx + (p - 1) * R * .50
            d.ellipse([px - R * .11, cy + R * .22 - R * .34, px + R * .11, cy + R * .22 - R * .12], fill=255)
            d.polygon([(px - R * .14, cy + R * .23), (px + R * .14, cy + R * .23),
                       (px + R * .10, cy + R * .23 - R * .19), (px - R * .10, cy + R * .23 - R * .19)], fill=255)
    arr = over(arr, WOOD_D, handwobble(draw_mask(W, H, _dfl), amp=S * .0018,
                                       cells=16, seed=seed + 2, bite=.07) * dome)

    def _dring(d):
        t = S * .016
        d.ellipse([cx - R - t, cy - R - t, cx + R + t, cy + R + t], fill=255)
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=0)
    arr = over(arr, CHAR, handwobble(draw_mask(W, H, _dring), amp=S * .003,
                                     cells=9, seed=seed + 3, bite=.09))

    # 중앙 기둥
    y0, y1 = cy + R * 0.90, S * 0.975
    col = np.zeros((H, W), np.float32)
    for y in range(int(y0), int(y1)):
        f = (y - y0) / float(y1 - y0)
        hw = (S * .042) * (1 - f) + (S * .011) * f
        col[y, int(cx - hw):int(cx + hw)] = 1.0
    col = handwobble(col, amp=S * .0026, cells=12, seed=seed + 4, bite=.08)
    arr = over(arr, WOOD, col * .95)
    rung = np.zeros((H, W), np.float32)
    yv = int(y0)
    while yv < y1:
        f = (yv - y0) / float(y1 - y0)
        hw = (S * .042) * (1 - f) + (S * .011) * f
        rung[yv:yv + max(1, int(S * .0035)), int(cx - hw):int(cx + hw)] = 1
        yv += max(3, int(S * .017))
    arr = over(arr, WOOD_D, rung * col * .8)

    # 기둥을 가로지르는 방 슬래브 — 아래로 갈수록 좁고 어두워진다
    # (깊이, 밝기, 좌우 쏠림, 폭 배수) — 규칙적인 삼각형이 되지 않게 흐트러뜨린다
    slabs = [(0.085, 1.00, -0.30, 1.00), (0.215, 0.88, 0.26, 0.72),
             (0.340, 0.75, -0.18, 1.02), (0.465, 0.59, 0.30, 0.60),
             (0.580, 0.45, -0.24, 0.84), (0.690, 0.30, 0.16, 0.54),
             (0.790, 0.18, -0.14, 0.68), (0.878, 0.09, 0.10, 0.42)]
    for i, (f, k, shift, wm) in enumerate(slabs):
        y = y0 + (y1 - y0) * f
        wdt = S * (0.44 * (1 - f * 0.70)) * wm
        hgt = S * (0.074 * (1 - f * 0.58))
        x = cx + shift * wdt
        arr = add_glow(arr, x, y, wdt * 0.95, (86 * k, 54 * k, 15 * k), 1.0, 2.0)

        def _cell(d, x=x, y=y, wdt=wdt, hgt=hgt):
            d.rectangle([x - wdt / 2, y - hgt / 2, x + wdt / 2, y + hgt / 2], fill=255)
        cell = handwobble(draw_mask(W, H, _cell), amp=S * .0024, cells=15,
                          seed=seed + 10 + i, bite=.08)
        warm = [(240, 189, 96), (214, 160, 70), (186, 130, 58), (150, 118, 56)][i % 4]
        warm = tuple(int(c * (0.26 + 0.74 * k)) for c in warm)
        arr = over(arr, warm, cell)

        # 바닥과 사람 — 축소해도 "사람이 산다"는 잔상이 남게
        def _cf(d, x=x, y=y, wdt=wdt, hgt=hgt):
            d.rectangle([x - wdt / 2, y + hgt * .30, x + wdt / 2, y + hgt / 2], fill=255)
            n = max(2, int(wdt / (S * .075)))
            for p in range(n):
                px = x + (p - (n - 1) / 2.0) * (wdt / (n + 0.6))
                d.polygon([(px - hgt * .11, y + hgt * .31), (px + hgt * .11, y + hgt * .31),
                           (px + hgt * .075, y - hgt * .16), (px - hgt * .075, y - hgt * .16)], fill=255)
        arr = over(arr, WOOD_D, draw_mask(W, H, _cf) * cell, .88 * (0.45 + 0.55 * k))

        def _co(d, x=x, y=y, wdt=wdt, hgt=hgt):
            d.rectangle([x - wdt / 2, y - hgt / 2, x + wdt / 2, y + hgt / 2],
                        outline=255, width=max(2, int(S * .0085)))
        arr = over(arr, CHAR, handwobble(draw_mask(W, H, _co), amp=S * .002,
                                         cells=15, seed=seed + 50 + i, bite=.08), .92)

    # 맨 아래는 검정에 삼켜진다
    yy2 = np.mgrid[0:H, 0:W][0].astype(np.float32)
    sw = np.clip((yy2 - S * 0.80) / (S * 0.20), 0, 1) ** 1.25
    arr = arr * (1 - sw[..., None] * .96) + C((0, 3, 5))[None, None, :] * (sw[..., None] * .96)
    return arr


# ============================================================================
# L4 — 물에 잠긴 글자
# ============================================================================
def submerged_text(arr, m, waterline_y, seed=41, amp=None):
    H, W = arr.shape[:2]
    ys, xs = np.nonzero(m > 0.3)
    if len(ys) == 0:
        return arr
    y0, y1 = ys.min(), ys.max()
    h = max(1, y1 - y0)
    if amp is None:
        amp = h * 0.052
    yy = np.mgrid[0:H, 0:W][0].astype(np.float32)

    wl = waterline_y + vnoise(H, W, 7, seed) * (h * 0.018)
    under = np.clip((yy - wl) / max(1.0, h * 0.008), 0, 1)

    phase = (yy - wl) / max(1.0, h * 0.14)
    dx = np.sin(phase * 1.7 + 0.6) * amp * np.clip(phase * 0.8, 0, 1.5)
    dx += vnoise(H, W, 5, seed + 3) * amp * 0.6
    m_under = warp(m, dx, np.zeros_like(dx)) * under
    m_over = m * (1 - under)

    arr = over(arr, (0, 4, 7), gblur(m, h * 0.09) * 0.55)
    arr = over(arr, CHAR, dilate(m_over, h * 0.026), 0.92)
    off = max(2.0, h * 0.030)
    arr = over(arr, CHAR, warp(m_over, -off, -off * 1.1) * 0.90)

    split = y0 + h * 0.34
    lower = np.clip((yy - split) / max(1.0, h * 0.012), 0, 1)
    col_o = C(CREAM)[None, None, :] * (1 - lower[..., None]) + C(OCHRE)[None, None, :] * lower[..., None]
    arr = over(arr, col_o, m_over)

    # 물속 — 청록에서 남색으로. 읽히게 유지한다(흐리게만 하지 않는다)
    depth = np.clip((yy - wl) / max(1.0, (y1 - waterline_y) * 1.02), 0, 1)
    col_u = ramp_col([(0, (92, 150, 160)), (.28, (52, 112, 128)),
                      (.62, (26, 76, 96)), (1, (14, 46, 64))], depth)
    arr = over(arr, (2, 16, 24), dilate(m_under, h * 0.022) * 0.85)
    blurred = gblur(m_under, max(0.6, h * 0.0035))
    arr = over(arr, col_u, np.clip(blurred, 0, 1) * np.clip(1 - depth * .28, .55, 1))

    # 수면선
    line = np.clip(1.0 - np.abs(yy - wl) / max(1.2, h * 0.012), 0, 1)
    arr = over(arr, (176, 222, 224), line * .60)
    arr = over(arr, CREAM, np.clip(1 - np.abs(yy - (wl - h * .010)) / max(1.0, h * .006), 0, 1) * .34)
    arr = over(arr, (214, 242, 240), np.clip(line * gblur(m, h * .008) * 1.5, 0, 1) * .55)
    return arr


# ============================================================================
# 제목 / 레이아웃
# ============================================================================
TITLES = {
    "T1": {"ko": "깊은 등불", "en": "DEEP LAMP",
           "ko_sq": ["깊은", "등불"], "en_sq": ["DEEP", "LAMP"],
           "sub_ko": "바다가 보관한 것", "sub_en": "WHAT THE SEA KEPT"},
    "T2": {"ko": "바다가 보관한 것", "en": "WHAT THE SEA KEPT",
           "ko_sq": ["바다가", "보관한 것"], "en_sq": ["WHAT THE", "SEA KEPT"],
           "sub_ko": "심해 유리돔 생존기", "sub_en": "A DEEP-SEA DOME"},
    "T3": {"ko": "내려가는 집", "en": "THE HOUSE BELOW",
           "ko_sq": ["내려가는", "집"], "en_sq": ["THE HOUSE", "BELOW"],
           "sub_ko": "바다가 보관한 것", "sub_en": "WHAT THE SEA KEPT"},
    "T4": {"ko": "성문 아래", "en": "BENEATH THE SEALS",
           "ko_sq": ["성문", "아래"], "en_sq": ["BENEATH", "THE SEALS"],
           "sub_ko": "바다가 보관한 것", "sub_en": "WHAT THE SEA KEPT"},
    "T5": {"ko": "무광층", "en": "APHOTIC",
           "ko_sq": ["무광층"], "en_sq": ["APHOTIC"],
           "sub_ko": "바다가 보관한 것", "sub_en": "WHAT THE SEA KEPT"},
}
MARKS = {"L1": mark_L1, "L2": mark_L2, "L3": mark_L3}


def _fit_px(text, target_w, start_px, tracking):
    px = float(start_px)
    for _ in range(40):
        f = get_font(int(px))
        w = sum(f.getlength(c) for c in text) + tracking * px * max(0, len(text) - 1)
        if w <= target_w or px <= 12:
            break
        px *= target_w / max(1.0, w) * 0.985
    return max(12, int(px))


def render_wide(concept, tkey, lang, S=2):
    W, H = 1200 * S, 400 * S
    T = TITLES[tkey]
    title, sub = T[lang], (T["sub_ko"] if lang == "ko" else T["sub_en"])
    trk = 0.0 if lang == "ko" else 0.055

    if concept == "L4":
        arr = water_bg(W, H, t0=0.18, t1=0.94, seed=77)
        px = _fit_px(title, W * 0.82, 200 * S, trk)
        m = make_wordmark(title, px, tracking=trk, seed=7)
        mh, mw = m.shape
        top = H * 0.50 - mh * 0.47
        mm = paste_mask((H, W), m, (W - mw) / 2, top)
        ys = np.nonzero(mm.sum(1) > 0)[0]
        arr = submerged_text(arr, mm, waterline_y=ys.min() + (ys.max() - ys.min()) * 0.52, seed=41)
        spx = max(14, int(px * 0.150))
        sm = make_wordmark(sub, spx, tracking=0.34, seed=8, weight="Medium")
        sh, sw = sm.shape
        arr = over(arr, (142, 176, 178), paste_mask((H, W), sm, (W - sw) / 2, H * 0.885 - sh / 2), .88)
    else:
        arr = water_bg(W, H, t0=0.24, t1=0.92, seed=61)
        ms = int(H * 0.84)
        mx, my = int(H * 0.09), int(H * 0.08)
        # 마크를 배너 배경 **위에 직접** 그리고, 테두리를 배경에 녹인다
        patch = arr[my:my + ms, mx:mx + ms]
        mk = MARKS[concept](ms, bg=patch)
        yy_, xx_ = np.mgrid[0:ms, 0:ms].astype(np.float32)
        edge = np.minimum.reduce([xx_, yy_, ms - 1 - xx_, ms - 1 - yy_])
        f = (np.clip(edge / (ms * 0.07), 0, 1) ** 0.8)[..., None]
        arr[my:my + ms, mx:mx + ms] = patch * (1 - f) + mk * f

        tx = mx + ms + int(H * 0.15)
        avail = W - tx - int(H * 0.10)
        px = _fit_px(title, avail, 160 * S, trk)
        m = make_wordmark(title, px, tracking=trk, seed=7)
        mh, mw = m.shape
        ty = H * 0.435 - mh * 0.5
        arr = ink_text(arr, paste_mask((H, W), m, tx, ty), seed=3)

        rule = np.zeros((H, W), np.float32)
        ry = int(ty + mh + H * 0.030)
        rule[ry:ry + max(2, int(H * 0.007)), int(tx + 4):int(tx + 4 + mw * 0.30)] = 1
        arr = over(arr, OCHRE, handwobble(rule, amp=H * .004, cells=7, seed=12), .80)

        spx = max(13, int(px * 0.185))
        sm = make_wordmark(sub, spx, tracking=0.30, seed=8, weight="Medium")
        sh, sw = sm.shape
        arr = over(arr, (150, 182, 184), paste_mask((H, W), sm, tx + 6, ry + H * 0.055), .90)

    return to_img(finish(arr, seed=9, grain=.05, vignette=.26)).resize((1200, 400), Image.LANCZOS)


def render_square(concept, tkey, lang, S=2):
    N = 512 * S
    T = TITLES[tkey]
    if concept == "L4":
        arr = water_bg(N, N, t0=0.14, t1=0.96, seed=78)
        lines = T[lang + "_sq"]
        trk = 0.0 if lang == "ko" else 0.04
        longest = max(lines, key=lambda s: sum(get_font(100).getlength(c) for c in s))
        px = _fit_px(longest, N * 0.86, 300 * S, trk)
        masks = [make_wordmark(s, px, tracking=trk, seed=7 + i) for i, s in enumerate(lines)]
        gap = int(px * 0.10)
        th = sum(m.shape[0] for m in masks) + gap * (len(masks) - 1)
        y = N * 0.47 - th / 2
        big = np.zeros((N, N), np.float32)
        last = None
        for m in masks:
            mh, mw = m.shape
            lay = paste_mask((N, N), m, (N - mw) / 2, y)
            big = np.maximum(big, lay)
            last = lay
            y += mh + gap
        # 수면이 마지막 줄 글자의 한가운데를 지난다 (잉크 실제 범위 기준)
        lys = np.nonzero(last.sum(1) > 0)[0]
        arr = submerged_text(arr, big, waterline_y=lys.min() + (lys.max() - lys.min()) * 0.50, seed=42)
    else:
        # 아이콘은 마크 단독 — 64px에서 글자는 반드시 뭉갠다
        arr = MARKS[concept](N)
    return to_img(finish(arr, seed=10, grain=.05, vignette=.34)).resize((512, 512), Image.LANCZOS)


def to_bw(im):
    return im.convert("L").convert("RGB")


def emit(concept, tkey, lang):
    tag = f"{concept}_{tkey}_{lang}"
    wide, sq = render_wide(concept, tkey, lang), render_square(concept, tkey, lang)
    sq64 = sq.resize((64, 64), Image.LANCZOS)
    out = {
        f"{tag}_wide.png": wide, f"{tag}_wide_bw.png": to_bw(wide),
        f"{tag}_sq.png": sq, f"{tag}_sq_bw.png": to_bw(sq),
        f"{tag}_sq64.png": sq64, f"{tag}_sq64_bw.png": to_bw(sq64),
        f"{tag}_sq64_zoom.png": sq64.resize((256, 256), Image.NEAREST),
        f"{tag}_sq64_bw_zoom.png": to_bw(sq64).resize((256, 256), Image.NEAREST),
    }
    for n, im in out.items():
        im.save(os.path.join(OUT, n))
    return tag


def emit_beside_game(concept, tkey, lang):
    """합격 기준 ③ — 게임 화면과 같은 세계로 보이는가."""
    if not os.path.exists(GAME_SHOT):
        return
    shot = Image.open(GAME_SHOT).convert("RGB").resize((1200, 675), Image.LANCZOS)
    logo = Image.open(os.path.join(OUT, f"{concept}_{tkey}_{lang}_wide.png")).convert("RGB")
    c = Image.new("RGB", (1200, 1075), (0, 3, 5))
    c.paste(shot, (0, 0))
    c.paste(logo, (0, 675))
    c.save(os.path.join(OUT, f"check_beside_{concept}_{tkey}_{lang}.png"))
    # 타이틀 화면 상정 — 네모 상자가 보이지 않게 가장자리를 녹여 얹는다
    lw, lh, lx, ly = 760, 253, 220, 46
    lg = np.asarray(logo.resize((lw, lh), Image.LANCZOS), np.float32)
    base = np.asarray(shot, np.float32).copy()
    yy_, xx_ = np.mgrid[0:lh, 0:lw].astype(np.float32)
    fx = np.minimum(xx_, lw - 1 - xx_) / (lw * 0.16)
    fy = np.minimum(yy_, lh - 1 - yy_) / (lh * 0.16)
    f = (np.clip(np.minimum(fx, fy), 0, 1) ** 0.9)[..., None]
    # 먼저 그 자리를 어둡게 깔고(실제 타이틀 화면이 하는 일), 그 위에 밝은 쪽만 남긴다
    reg = base[ly:ly + lh, lx:lx + lw]
    reg = reg * (1 - f * 0.80)
    base[ly:ly + lh, lx:lx + lw] = reg * (1 - f) + np.maximum(reg, lg) * f
    Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).save(
        os.path.join(OUT, f"check_title_{concept}_{tkey}_{lang}.png"))


def main():
    args = set(sys.argv[1:])
    n = 0
    for c in ["L1", "L2", "L3", "L4"]:
        for lang in ["ko", "en"]:
            print("  ", emit(c, "T1", lang))
            n += 1
    if "stage1" not in args:
        for t in ["T2", "T3", "T4", "T5"]:
            for lang in ["ko", "en"]:
                print("  ", emit("L1", t, lang))
                n += 1
    for c in ["L1", "L2", "L3", "L4"]:
        emit_beside_game(c, "T1", "ko")
    print(f"done: {n} sets -> {OUT}")


if __name__ == "__main__":
    main()
