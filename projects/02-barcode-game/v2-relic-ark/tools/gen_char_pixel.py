# -*- coding: utf-8 -*-
"""
gen_char_pixel.py — 도트 캐릭터 샘플 여섯 (스프린트 7-A)

같은 인물(정찰병)을 여섯 가지 도트 어법으로 직접 찍는다.
생성 AI를 쓰지 않는다. 모든 픽셀은 이 파일 안의 좌표 지정과 작은 도형
원시함수로만 만들어진다. 특정 게임의 캐릭터를 베끼지 않고
해상도·비율·외곽선·팔레트 운용 방식의 원리만 가져온다.

출력: static/art/chars/pixel/p1..p6/{full,full4x,face,room,walk}.png
      static/art/chars/pixel/contact.png

실행: python tools/gen_char_pixel.py
"""
import os, math, io, json
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'static', 'art', 'chars', 'pixel')

# ─────────────────────────────────────────────────────────────
# 팔레트 — 흙 계열 따뜻한 색이 바탕. 차가운 색은 G/g(헬멧 유리·물)뿐.
# ─────────────────────────────────────────────────────────────
PAL = {
    'K': (42, 29, 22),      # 외곽선 (검정이 아니라 따뜻한 숯갈색)
    'J': (26, 18, 14),      # 더 어두운 선 / 실루엣
    'o': (68, 42, 26),      # 잠수복 그늘
    'm': (108, 68, 38),     # 잠수복 중간
    'l': (144, 95, 52),     # 잠수복 밝은
    'h': (186, 134, 76),    # 잠수복 하이라이트
    'c': (232, 210, 168),   # 크림(캔버스 천·끈)
    'C': (198, 174, 132),   # 크림 그늘
    'v': (104, 100, 58),    # 탁한 올리브
    'V': (70, 66, 38),      # 올리브 그늘
    's': (240, 207, 174),   # 피부
    'd': (206, 162, 128),   # 피부 그늘
    'b': (216, 134, 118),   # 볼 홍조
    'e': (58, 36, 24),      # 눈·눈썹·입
    'w': (255, 246, 230),   # 눈 하이라이트
    'r': (78, 48, 32),      # 머리카락
    'u': (88, 55, 32),      # 잠수복 중간단 (P4 전용 램프)
    'n': (126, 82, 45),
    'q': (165, 115, 64),
    'R': (150, 62, 48),     # 적갈 (수선 자국·강조)
    'B': (110, 76, 30),     # 놋쇠 그늘
    'N': (158, 116, 42),    # 놋쇠 중간
    'P': (183, 139, 53),    # 놋쇠 중간단 (P4 전용 램프)
    'M': (208, 162, 64),    # 놋쇠 밝은
    'H': (242, 216, 144),   # 놋쇠 하이라이트
    'G': (48, 96, 104),     # 유리 그늘   ← 차가운 색
    'g': (126, 190, 194),   # 유리 반사   ← 차가운 색
    'T': (122, 106, 78),    # 공기통
    't': (160, 142, 106),   # 공기통 밝은
    'L': (255, 212, 130),   # 랜턴 심지
    'y': (236, 160, 70),    # 랜턴 테두리
    'Z': (38, 28, 22),      # 실루엣 본체
    'z': (72, 54, 40),      # 실루엣 내부 약한 단
    'X': (236, 206, 150),   # 가장자리 빛 (따뜻)
    'x': (112, 146, 150),   # 가장자리 빛 (물빛, P4/P5 한정)
}


# ─────────────────────────────────────────────────────────────
# 실제 렌더 방 (2.5D 판정의 기준) — 배경 담당의 section_room_zoom.png
#   방 깊이 1.7m: 캐릭터는 벽에 가깝게 서고 앞뒤 겹침이 없다.
#   배경 주민 실측 키 133px = 1.6m. 우리 목표도 같은 키.
# ─────────────────────────────────────────────────────────────
SCENE_SRC = os.path.join(ROOT, 'static', 'art', 'deep', 'section_room_zoom.png')
SCENE_BOX = (1115, 330, 1420, 600)   # 사람이 없는 깨끗한 바닥이 있는 칸
SCENE_FLOOR = 248                    # 크롭 기준 바닥선 y
SCENE_CX = 138                       # 세울 x
SCENE_LAMP = (133, 40)               # 천장 등불 위치 (크롭 기준)
SCENE_TARGET_H = 132                 # 1.6m에 해당하는 픽셀 키

_scene_cache = {}


def scene_crop():
    if 'im' not in _scene_cache:
        _scene_cache['im'] = Image.open(SCENE_SRC).convert('RGB').crop(SCENE_BOX)
    return _scene_cache['im'].copy()


def lamp_tint():
    """등불이 비춘 벽색에서 틴트를 뽑는다 (평균 1.0으로 정규화)."""
    if 'tint' not in _scene_cache:
        lx, ly = SCENE_LAMP
        box = scene_crop().crop((max(0, lx - 45), ly + 14, lx + 45, ly + 64))
        c = box.resize((1, 1), Image.BOX).getpixel((0, 0))
        m = max(1.0, sum(c) / 3.0)
        _scene_cache['tint'] = tuple(ci / m for ci in c)
    return _scene_cache['tint']


def clamp8(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def harmonize(strength=0.20, contrast=1.26):
    """팔레트를 배경 렌더에서 실제로 뽑아 당긴다 — 한 화면에 사는 색으로.
    다만 당기기만 하면 벽에 묻히므로, 배경 평균색을 기준으로 대비를 다시 벌린다.
    가독성 앵커(눈·외곽선·랜턴·가장자리 빛)와 차가운 색(유리)은 건드리지 않는다."""
    crop = scene_crop()
    q = crop.quantize(colors=16, method=Image.MEDIANCUT)
    raw = q.getpalette()[:48]
    cols = [tuple(raw[i * 3:i * 3 + 3]) for i in range(16)]
    base = crop.resize((1, 1), Image.BOX).getpixel((0, 0))   # 방의 평균색

    def lum(c):
        return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

    keep = set('ewLGgxKJXZz')
    for k, c in list(PAL.items()):
        if k in keep:
            continue
        near = min(cols, key=lambda b: abs(lum(b) - lum(c)))
        mixed = [c[i] * (1 - strength) + near[i] * strength for i in range(3)]
        PAL[k] = tuple(clamp8(base[i] + (mixed[i] - base[i]) * contrast) for i in range(3))


def room_light(spr, strength=1.0):
    """방의 빛을 받게 한다 (HD-2D의 생명): 등불색 틴트 + 위에서 내려오는 광 + 아래 감쇠."""
    t = lamp_tint()
    spr = spr.convert('RGBA')
    w, h = spr.size
    px = spr.load()
    for y in range(h):
        f = 1.0 + strength * (0.13 - 0.32 * (y / max(1, h - 1)))
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            fx = 1.0 + strength * 0.07 * (1 - 2 * x / max(1, w - 1))
            k = f * fx
            px[x, y] = (clamp8(r * k * (1 + 0.30 * strength * (t[0] - 1))),
                        clamp8(g * k * (1 + 0.30 * strength * (t[1] - 1))),
                        clamp8(b * k * (1 + 0.30 * strength * (t[2] - 1))), a)
    return spr


def soften(spr, mix=0.5):
    """P4 전용: 가장자리를 아주 조금 풀어 배경 질감에 붙인다."""
    bl = spr.filter(ImageFilter.GaussianBlur(0.8))
    return Image.blend(spr, bl, mix)


def ground_shadow(base, pos, spr, k=1.0):
    """발밑 접지 그림자 — 없으면 캐릭터가 공중에 뜬다."""
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    ww = int(spr.width * 0.78 * k)
    hh = max(5, int(spr.height * 0.085))
    cx = pos[0] + spr.width // 2
    cy = pos[1] + spr.height - hh // 3
    d.ellipse([cx - ww // 2, cy - hh // 2, cx + ww // 2, cy + hh // 2],
              fill=(10, 6, 4, 165))
    sh = sh.filter(ImageFilter.GaussianBlur(max(2, hh // 2)))
    return Image.alpha_composite(base, sh)


class Px:
    """작은 픽셀 캔버스. 글자 하나 = 픽셀 하나."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.g = [[' '] * w for _ in range(h)]
        self.off = 0  # y 오프셋 (걷기 프레임 바운스용)

    def set(self, x, y, ch):
        if ch in ' .':
            return
        x = int(round(x)); y = int(round(y)) + self.off
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = ch

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.g[y][x]
        return ' '

    def rect(self, x0, y0, x1, y1, ch):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.set(x, y, ch)

    def ell(self, cx, cy, rx, ry, ch):
        for y in range(int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1):
            for x in range(int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1):
                dx = (x - cx) / max(rx, 0.001)
                dy = (y - cy) / max(ry, 0.001)
                if dx * dx + dy * dy <= 1.0:
                    self.set(x, y, ch)

    def ell_in(self, cx, cy, rx, ry, ch, only=None):
        """기존에 칠해진 곳에만 (only 색 위에만) 겹쳐 칠한다 — 음영용."""
        for y in range(int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1):
            for x in range(int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1):
                dx = (x - cx) / max(rx, 0.001)
                dy = (y - cy) / max(ry, 0.001)
                if dx * dx + dy * dy <= 1.0:
                    cur = self.get(x, int(y) + self.off)
                    if cur == ' ':
                        continue
                    if only and cur not in only:
                        continue
                    self.set(x, y, ch)

    def stamp(self, x0, y0, rows):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                self.set(x0 + i, y0 + j, ch)

    def outline(self, ch='K', rounds=1):
        tmps = []
        for r in range(rounds):
            tmp = '\x01' if r == 0 else '\x02'
            tmps.append(tmp)
            add = []
            for y in range(self.h):
                for x in range(self.w):
                    if self.g[y][x] != ' ':
                        continue
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.w and 0 <= ny < self.h and self.g[ny][nx] != ' ':
                            add.append((x, y)); break
            for x, y in add:
                self.g[y][x] = tmp
        for y in range(self.h):
            for x in range(self.w):
                if self.g[y][x] in tmps:
                    self.g[y][x] = ch

    def recolor(self, mapping):
        for y in range(self.h):
            for x in range(self.w):
                c = self.g[y][x]
                if c in mapping:
                    self.g[y][x] = mapping[c]

    def rim(self, ch, side='left', width=1):
        """실루엣의 한쪽 바깥 가장자리 width픽셀을 ch로 바꾼다 (가장자리 빛)."""
        for y in range(self.h):
            xs = [x for x in range(self.w) if self.g[y][x] != ' ']
            if not xs:
                continue
            seq = xs[:width] if side == 'left' else xs[-width:]
            for x in seq:
                self.g[y][x] = ch

    def rim_top(self, ch, width=1):
        for x in range(self.w):
            ys = [y for y in range(self.h) if self.g[y][x] != ' ']
            for y in ys[:width]:
                self.g[y][x] = ch

    def img(self):
        im = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))
        px = im.load()
        for y in range(self.h):
            for x in range(self.w):
                ch = self.g[y][x]
                if ch != ' ':
                    px[x, y] = PAL[ch] + (255,)
        return im


# ─────────────────────────────────────────────────────────────
# 공통 부품
# ─────────────────────────────────────────────────────────────


def eye(p, x, y, w, h, skin='s', hl=True):
    """둥근 눈 + 왼쪽 위 반짝임. 새까만 네모를 피한다 (C10)."""
    p.rect(x, y, x + w - 1, y + h - 1, 'e')
    if w >= 3 and h >= 3:                     # 아래 모서리를 깎아 둥글게
        p.set(x, y + h - 1, skin)
        p.set(x + w - 1, y + h - 1, skin)
    if hl:
        p.set(x, y, 'w')                      # 빛은 왼쪽 위에서 온다
        if w >= 4:
            p.set(x + 1, y, 'w')
        if h >= 4:
            p.set(x, y + 1, 'w')


def brow(p, x, y, w, side, drop=True, ch='e'):
    """바깥쪽 끝이 1px 내려간 편안한 눈썹. 머리카락과 1px 이상 떨어뜨린다."""
    for i in range(w):
        dy = 1 if (drop and ((side == 'l' and i == 0) or (side == 'r' and i == w - 1))) else 0
        p.set(x + i, y + dy, ch)


def smile(p, cx, y, w, open_mouth=False):
    """양 끝이 올라간 웃는 입. 선 하나가 인형을 사람으로 바꾼다 (DECISIONS 2026-09-27)."""
    for i in range(-w, w + 1):
        p.set(cx + i, y - (1 if abs(i) == w else 0), 'e')
    if open_mouth:
        p.set(cx, y + 1, 'R')


def blush(p, x0, x1, y):
    for x in range(x0, x1 + 1):
        if p.get(x, y + p.off) in 'sd':
            p.set(x, y, 'b')


def legs_pairs(f, lx, rx):
    """3프레임 걷기. f0=디딤, f1=왼발 앞, f2=오른발 앞."""
    if f == 0:
        return [(lx, 0, 0), (rx, 0, 0)]
    if f == 1:
        return [(lx - 1, 1, -1), (rx + 1, -1, 1)]
    return [(lx + 1, -1, 1), (rx - 1, 1, -1)]


def wave(p, x0, x1, y, ch, step=2):
    """목 실링·옷단의 물결 반복 무늬 (REF_ART_FLAT_FOLK §1-5)."""
    for x in range(x0, x1 + 1, step):
        p.set(x, y, ch)


# ─────────────────────────────────────────────────────────────
# P1 — 32px 초간결
#   원리: 아주 작은 해상도, 한 색당 면을 크게, 고대비.
#   수십 명이 한 화면에 있어도 각자 읽히게 실루엣 덩어리를 셋으로 분리
#   (둥근 헬멧 / 두툼한 몸통 / 넓은 장화).
# ─────────────────────────────────────────────────────────────

def build_p1(f=0):
    p = Px(22, 32)
    bob = [0, -1, -1][f]

    p.off = bob
    # 공기통
    p.rect(16, 11, 19, 21, 'T')
    p.rect(16, 11, 16, 21, 't')
    p.rect(17, 9, 18, 11, 'B')
    # 목 실링
    p.rect(6, 15, 15, 16, 'c')
    wave(p, 6, 15, 16, 'C')
    # 몸통
    p.rect(5, 16, 16, 25, 'm')
    p.rect(5, 16, 7, 25, 'l')
    p.rect(14, 16, 16, 25, 'o')
    p.rect(5, 23, 16, 24, 'V')          # 허리띠
    p.rect(10, 23, 11, 24, 'M')         # 버클
    p.rect(9, 17, 12, 22, 'c')          # 가슴 끈
    # 팔
    p.rect(3, 17, 4, 23, 'm')
    p.rect(17, 17, 18, 23, 'o')
    p.rect(3, 23, 4, 25, 'c')
    p.rect(17, 23, 18, 25, 'C')
    # 랜턴
    p.rect(2, 21, 3, 23, 'y')
    p.set(2, 22, 'L'); p.set(3, 22, 'L')
    # 헬멧
    p.ell(10.5, 7, 7, 7, 'B')
    p.ell(10.5, 6.4, 6.2, 6.2, 'N')
    p.ell(10.5, 5.6, 5.2, 5.0, 'M')
    p.ell(8, 3.6, 2.4, 1.4, 'H')
    # 얼굴 구멍 (어깨 링보다 확실히 위)
    p.ell(10.5, 8.0, 5.5, 5.6, 'B')
    p.ell(10.5, 8.0, 4.8, 5.0, 'd')
    p.ell_in(9.2, 7.2, 4.0, 3.8, 's', only='d')    # 왼쪽 위만 밝게 — 뼈처럼 하얘지지 않게
    p.ell_in(10.5, 3.9, 4.0, 1.1, 'r', only='sd')  # 앞머리: 사람으로 읽히게 하는 한 줄
    p.rect(4, 13, 17, 13, 'B')           # 돔 밑 테
    p.set(5, 10, 'H'); p.set(16, 10, 'H')  # 볼트
    p.rect(3, 14, 18, 15, 'B')           # 어깨 링
    p.set(4, 14, 'M'); p.set(17, 14, 'M')
    # 얼굴 (아주 단순, 고대비)
    brow(p, 8, 7, 2, 'l', drop=False); brow(p, 12, 7, 2, 'r', drop=False)
    eye(p, 8, 9, 2, 2, hl=False); eye(p, 12, 9, 2, 2, hl=False)
    # 입은 5픽셀 호 하나 — 점 세 개는 '이빨'처럼 보인다
    p.rect(9, 12, 11, 12, 'e'); p.set(10, 12, 'R')   # 입꼬리를 눈 바로 아래에 두면 세로 막대가 된다
    blush(p, 6, 7, 11); blush(p, 14, 15, 11)
    # 배기관
    p.rect(2, 5, 4, 6, 'N'); p.rect(2, 3, 3, 6, 'N'); p.set(2, 2, 'M')

    p.off = 0
    for lx, dxf, _dz in legs_pairs(f, 7, 13):
        p.rect(lx, 25 + bob, lx + 2, 28, 'o')
        p.rect(lx + dxf, 29, lx + 2 + dxf, 30, 'K')
        p.rect(lx + dxf, 30, lx + 2 + dxf, 31, 'N')   # 무게추 장화 코
    p.outline('K')
    return p


# ─────────────────────────────────────────────────────────────
# P2 — 48px 생활형 (가장 유력)
#   원리: 농장·생활 시뮬 계열. 둥글고 따뜻하고 선이 부드럽다.
#   머리 ~2.4등신, 면갑을 올려 얼굴을 완전히 노출, 볼 홍조.
# ─────────────────────────────────────────────────────────────

def build_p2(f=0):
    p = Px(32, 48)
    bob = [0, -1, -1][f]
    p.off = bob

    # 공기통 (오른쪽 어깨 뒤)
    p.ell(26, 29, 3.4, 8.5, 'T')
    p.ell(25, 29, 1.6, 8, 't')
    p.ell(26, 20.5, 3.4, 2, 't')
    p.rect(25, 17, 27, 20, 'B')
    p.rect(22, 16, 25, 17, 'o')          # 호스
    p.rect(21, 14, 22, 17, 'o')

    # 목 실링 (두툼한 고무테, 물결 반복)
    p.ell(14, 24, 9, 3.6, 'c')
    p.ell(14, 23, 8.4, 2.6, 'C')
    wave(p, 6, 22, 23, 'o')
    wave(p, 7, 21, 25, 'o')

    # 몸통
    p.ell(14, 33, 9.2, 8.4, 'm')
    p.ell_in(11.5, 30, 6.5, 6, 'l', only='m')
    p.ell_in(10, 28, 3.5, 3, 'h', only='ml')
    p.rect(5, 37, 23, 41, 'o')
    p.ell_in(14, 40, 9.2, 4, 'o', only='mlh')
    # 가슴 끈 두 줄
    p.rect(10, 26, 11, 35, 'c'); p.rect(17, 26, 18, 35, 'c')
    p.set(10, 35, 'C'); p.set(18, 35, 'C')
    # 허리띠
    p.rect(5, 35, 23, 36, 'V')
    p.rect(13, 34, 15, 37, 'M'); p.set(14, 35, 'H')
    # 기운 자국 (200년 쓴 장비의 이력)
    p.rect(7, 29, 9, 31, 'v')
    p.set(7, 29, 'R'); p.set(9, 30, 'R'); p.set(8, 31, 'R')

    # 팔 + 벙어리 장갑
    p.rect(3, 27, 6, 36, 'm'); p.rect(3, 27, 4, 36, 'l')
    p.rect(22, 27, 25, 36, 'o')
    p.ell(4.5, 38, 2.8, 2.6, 'c')
    p.ell(23.5, 38, 2.8, 2.6, 'C')

    # 허리 랜턴
    p.ell(3, 34, 2.2, 2.8, 'y')
    p.rect(2, 33, 4, 35, 'L')
    p.set(3, 31, 'B')

    # 헬멧 (놋쇠 돔)
    p.ell(14, 12, 10.5, 9.5, 'B')
    p.ell(14, 11.2, 9.6, 8.6, 'N')
    p.ell(14, 10.2, 8.2, 7.2, 'M')
    p.ell(10.5, 7.5, 3.2, 2.2, 'H')
    p.rect(4, 17, 24, 18, 'B')           # 어깨 링
    p.set(6, 17, 'M'); p.set(22, 17, 'M')
    # 배기관 (왼쪽 위)
    p.rect(1, 10, 4, 11, 'N'); p.rect(1, 7, 2, 11, 'N')
    p.rect(1, 6, 2, 6, 'M')
    # 얼굴 구멍 (면갑을 올린 상태 — 유리 없음)
    p.ell(14, 14, 7.4, 7.4, 'B')
    p.ell(14, 14.2, 6.4, 6.4, 's')
    p.ell_in(16, 16, 5, 5, 'd', only='s')
    # 볼트
    p.set(6, 13, 'H'); p.set(22, 13, 'H')
    p.set(6, 14, 'B'); p.set(22, 14, 'B')

    # 얼굴
    p.ell_in(14, 8.6, 5.8, 1.9, 'r', only='sd')    # 앞머리(살 위에만)
    p.ell_in(11.5, 7.8, 3.6, 1.4, 'o', only='r')
    brow(p, 10, 12, 3, 'l'); brow(p, 16, 12, 3, 'r')
    eye(p, 10, 14, 3, 3); eye(p, 16, 14, 3, 3)
    p.set(14, 17, 'd')                   # 코
    smile(p, 14, 19, 2)
    blush(p, 8, 9, 17); blush(p, 19, 20, 17)

    p.off = 0
    for lx, dxf, _d in legs_pairs(f, 8, 16):
        p.rect(lx, 40 + bob, lx + 5, 44, 'o')
        p.rect(lx, 40 + bob, lx + 1, 44, 'm')
        p.rect(lx + dxf, 44, lx + 5 + dxf, 45, 'K')
        p.rect(lx + dxf, 45, lx + 5 + dxf, 47, 'N')   # 무게추 장화
        p.set(lx + dxf, 45, 'M')
    p.outline('K')
    return p


# ─────────────────────────────────────────────────────────────
# P3 — 64px 디테일
#   원리: 장비와 주름이 보이는 해상도. 교체 가능한 장비가 눈에 띈다.
#   유리 면갑을 내린 상태 + 사선 반사 한 줄(차가운 색은 여기만).
# ─────────────────────────────────────────────────────────────

def build_p3(f=0):
    p = Px(42, 64)
    bob = [0, -1, -1][f]
    p.off = bob

    # 공기통 두 통
    for cx in (34, 37.5):
        p.ell(cx, 36, 2.6, 11, 'T')
        p.ell(cx - 1, 36, 1, 10.5, 't')
        p.ell(cx, 25.5, 2.6, 1.6, 't')
    p.rect(34, 21, 38, 25, 'B')
    p.rect(30, 20, 34, 21, 'o')
    p.rect(29, 17, 30, 21, 'o')

    # 목 실링
    p.ell(19, 30, 11, 4.2, 'c')
    p.ell(19, 29, 10.2, 3.2, 'C')
    for x in range(9, 30, 2):
        p.set(x, 28, 'o'); p.set(x + 1, 31, 'o')

    # 몸통
    p.ell(19, 42, 11.5, 11.5, 'm')
    p.ell_in(16, 38, 8.5, 8.5, 'l', only='m')
    p.ell_in(14, 35, 4.5, 4, 'h', only='ml')
    p.ell_in(19, 50, 11.5, 5, 'o', only='mlh')
    # 세로 주름 3줄
    for x in (12, 19, 26):
        for y in range(34, 50):
            if p.get(x, y + bob) in 'mlh':
                p.set(x, y, 'o')
            if p.get(x + 1, y + bob) in 'ml':
                p.set(x + 1, y, 'h')
    # 가슴 하네스
    p.rect(13, 32, 15, 46, 'c'); p.rect(23, 32, 25, 46, 'c')
    p.rect(13, 38, 25, 40, 'C')
    p.rect(17, 37, 21, 41, 'N'); p.rect(18, 38, 20, 40, 'M')   # 가슴 금구
    # 허리띠 + 주머니
    p.rect(8, 46, 30, 49, 'V')
    p.rect(17, 45, 21, 50, 'M'); p.rect(18, 46, 20, 49, 'H')
    p.rect(9, 44, 13, 48, 'v'); p.rect(9, 44, 13, 44, 'V')      # 주머니
    p.rect(25, 44, 29, 48, 'v'); p.rect(25, 44, 29, 44, 'V')
    # 수선 자국
    p.rect(24, 34, 28, 37, 'v')
    for i in range(4):
        p.set(24 + i, 34 + (i % 2), 'R')

    # 팔 (관절 띠가 보인다)
    p.rect(4, 34, 9, 47, 'm'); p.rect(4, 34, 5, 47, 'l')
    p.rect(29, 34, 34, 47, 'o')
    for y in (37, 41, 45):
        p.rect(4, y, 9, y, 'o'); p.rect(29, y, 34, y, 'K')
    p.ell(6.5, 50, 4, 3.6, 'c'); p.ell(6.5, 50, 3, 2.6, 'C')
    p.ell(31.5, 50, 4, 3.6, 'C')

    # 허리 랜턴 (유물 등불)
    p.rect(1, 43, 5, 49, 'N')
    p.rect(2, 44, 4, 48, 'y')
    p.rect(2, 45, 4, 47, 'L')
    p.rect(2, 41, 4, 43, 'B')

    # 헬멧
    p.ell(19, 16, 13.5, 13, 'B')
    p.ell(19, 15, 12.6, 12, 'N')
    p.ell(19, 13.5, 11, 10, 'M')
    p.ell(14.5, 9, 4, 2.8, 'H')
    p.rect(6, 23, 32, 26, 'B')            # 어깨 링
    for x in range(7, 32, 3):
        p.set(x, 24, 'M')
    # 배기관
    p.rect(1, 13, 6, 15, 'N'); p.rect(1, 9, 3, 15, 'N')
    p.rect(1, 8, 3, 8, 'M'); p.set(2, 7, 'B')
    # 유리 면갑 (차가운 색은 여기만)
    p.ell(19, 18, 9.8, 9.8, 'B')
    p.ell(19, 18, 9.0, 9.0, 'G')
    p.ell(19, 19.0, 7.3, 7.3, 's')
    p.ell_in(22, 21.5, 5.6, 5.6, 'd', only='s')
    # 볼트 여섯
    for ang in (200, 250, 290, 340, 20, 160):
        bx = 19 + 11.2 * math.cos(math.radians(ang))
        by = 16 + 10.8 * math.sin(math.radians(ang))
        p.set(bx, by, 'H'); p.set(bx, by + 1, 'B')

    # 얼굴
    p.ell_in(19, 12.8, 7.0, 1.8, 'r', only='sd')   # 앞머리
    p.ell_in(16, 12.0, 4.6, 1.4, 'o', only='r')
    brow(p, 13, 16, 4, 'l'); brow(p, 22, 16, 4, 'r')
    eye(p, 13, 18, 4, 4); eye(p, 22, 18, 4, 4)
    p.set(19, 21, 'd'); p.set(19, 22, 'd')         # 코
    smile(p, 19, 24, 3, open_mouth=True)
    blush(p, 11, 13, 22); blush(p, 25, 27, 22)
    p.set(14, 23, 'd'); p.set(24, 23, 'd')         # 주근깨
    # 유리 반사 — 얼굴을 덮지 않고 유리 테두리 위에만
    for gx, gy in ((13, 12), (14, 11), (15, 10), (16, 10)):
        p.set(gx, gy, 'g')

    p.off = 0
    for lx, dxf, _d in legs_pairs(f, 11, 23):
        p.rect(lx, 52 + bob, lx + 7, 57, 'o')
        p.rect(lx, 52 + bob, lx + 2, 57, 'm')
        p.rect(lx, 55, lx + 7, 55, 'K')
        p.rect(lx + dxf, 57, lx + 7 + dxf, 59, 'K')
        p.rect(lx + dxf, 59, lx + 7 + dxf, 63, 'N')   # 무게추 장화
        p.rect(lx + dxf, 60, lx + 2 + dxf, 62, 'M')
        p.rect(lx + dxf, 62, lx + 7 + dxf, 63, 'B')
    p.outline('K')
    return p


# ─────────────────────────────────────────────────────────────
# P4 — HD-2D (도트 캐릭터 + 렌더 배경)
#   원리: 스프라이트 자체는 도트, 빛은 장면에서 온다.
#   스프라이트에 따뜻한 왼쪽 림라이트를 굽고, 표현 단계에서
#   부드러운 그림자·랜턴 블룸·접지 그림자를 올린다.
# ─────────────────────────────────────────────────────────────

def build_p4(f=0):
    p = Px(36, 64)
    bob = [0, -1, -1][f]
    p.off = bob

    p.ell(29, 32, 3, 9.5, 'T')
    p.ell(28, 32, 1.2, 9, 't')
    p.ell(29, 22.5, 3, 1.8, 't')
    p.rect(28, 19, 30, 22, 'B')
    p.rect(25, 18, 28, 19, 'o')

    p.ell(16, 27, 9.6, 3.8, 'c')
    p.ell(16, 26, 9, 2.8, 'C')
    wave(p, 8, 24, 26, 'o')

    # 음영 6단 — 배경 렌더의 부드러운 계조에 가장 가깝게 (P4의 성격)
    p.ell(16, 38, 10, 10, 'u')
    p.ell_in(15.2, 37.2, 9.3, 9.3, 'm', only='u')
    p.ell_in(13.8, 35.4, 8.0, 8.0, 'n', only='mu')
    p.ell_in(12.6, 33.6, 6.4, 6.4, 'l', only='mnu')
    p.ell_in(11.6, 32.0, 4.4, 3.8, 'q', only='lnm')
    p.ell_in(11.0, 31.0, 2.6, 2.2, 'h', only='ql')
    p.ell_in(16, 45.5, 10, 4.2, 'o', only='umnlqh')
    p.rect(11, 29, 13, 41, 'c'); p.rect(19, 29, 21, 41, 'c')
    p.rect(6, 41, 26, 43, 'V')
    p.rect(15, 40, 17, 44, 'M'); p.set(16, 42, 'H')
    p.rect(8, 33, 10, 36, 'v'); p.set(8, 33, 'R'); p.set(10, 35, 'R')

    p.rect(3, 31, 6, 42, 'm'); p.rect(3, 31, 4, 42, 'l')
    p.rect(25, 31, 28, 42, 'o')
    p.ell(4.8, 44, 3, 2.8, 'c')
    p.ell(26.5, 44, 3, 2.8, 'C')

    p.ell(3, 39, 2.2, 2.8, 'y')
    p.rect(2, 38, 4, 40, 'L')

    p.ell(16, 14, 11.5, 11, 'B')
    p.ell(16, 13.2, 10.6, 10, 'N')
    p.ell(16, 12.6, 9.9, 9.2, 'P')
    p.ell(16, 11.8, 9.0, 8.1, 'M')
    p.ell(13.4, 9.6, 5.4, 3.8, 'H')
    p.ell_in(12.2, 8.6, 3.0, 2.0, 'w', only='H')
    p.rect(5, 20, 27, 21, 'B')
    p.rect(1, 11, 4, 12, 'N'); p.rect(1, 8, 2, 12, 'N'); p.rect(1, 7, 2, 7, 'M')

    p.ell(16, 16, 8.4, 8.4, 'B')
    p.ell(16, 16, 7.7, 7.7, 'G')
    p.ell(16, 16.6, 6.4, 6.4, 's')
    p.ell_in(18.5, 19, 5.2, 5.2, 'd', only='s')
    p.set(7, 15, 'H'); p.set(25, 15, 'H')

    p.ell_in(16, 11.2, 5.8, 1.6, 'r', only='sd')
    p.ell_in(13.5, 10.6, 3.6, 1.2, 'o', only='r')
    brow(p, 11, 14, 3, 'l'); brow(p, 19, 14, 3, 'r')
    eye(p, 11, 16, 3, 3); eye(p, 19, 16, 3, 3)
    p.set(16, 19, 'd')
    smile(p, 16, 21, 2)
    blush(p, 9, 10, 19); blush(p, 22, 23, 19)
    for gx, gy in ((11, 10), (12, 9), (13, 9)):
        p.set(gx, gy, 'g')

    p.off = 0
    for lx, dxf, _d in legs_pairs(f, 9, 19):
        p.rect(lx, 46 + bob, lx + 6, 57, 'o')
        p.rect(lx, 46 + bob, lx + 1, 57, 'n')
        p.rect(lx, 51, lx + 6, 51, 'u')              # 무릎 띠
        p.rect(lx + dxf, 57, lx + 6 + dxf, 58, 'K')
        p.rect(lx + dxf, 58, lx + 6 + dxf, 63, 'N')
        p.rect(lx + dxf, 58, lx + 1 + dxf, 62, 'M')
    p.outline('K')
    # 림라이트: 왼쪽은 따뜻한 등불빛, 오른쪽은 물빛(유일한 예외)
    p.rim('X', 'left')
    p.rim('x', 'right')
    return p


# ─────────────────────────────────────────────────────────────
# P5 — 실루엣 중심
#   원리: 형태만으로 읽힌다. 내부는 두 단, 가장자리 빛 한 줄,
#   랜턴과 유리만 색을 가진다. 물속 분위기에 가장 잘 맞는다.
# ─────────────────────────────────────────────────────────────

def build_p5(f=0):
    """둥근 머리 + 각진 몸. 유기적 곡선만 쓰면 짐승 덩어리로 읽힌다.
    각진 어깨판(가장 넓다)과 둥근 헬멧의 대비가 '잠수부'를 만든다."""
    p = Px(34, 48)
    bob = [0, -1, -1][f]
    p.off = bob

    # 공기통 — 오른쪽 어깨 위로 머리만 내민다 (좌우 비대칭)
    p.rect(25, 8, 29, 17, 'Z')
    p.rect(22, 6, 25, 7, 'Z')

    # 몸통 — 각진 사다리꼴
    p.rect(8, 22, 26, 33, 'Z')
    p.rect(9, 33, 25, 38, 'Z')
    # 팔 — 각진 기둥
    p.rect(4, 23, 8, 34, 'Z')
    p.rect(26, 23, 30, 34, 'Z')
    p.rect(3, 34, 8, 38, 'Z')          # 장갑
    p.rect(26, 34, 31, 38, 'Z')

    # 어깨판 (코르슬릿) — 가장 넓은 수평 요소. 이 한 줄이 잠수부를 만든다
    p.rect(3, 18, 31, 22, 'z')
    p.rect(3, 18, 31, 18, 'J')
    # 목 실링
    p.rect(10, 15, 24, 18, 'Z')
    # 헬멧 — 유일한 곡선
    p.ell(17, 9, 7.2, 7.4, 'Z')
    p.ell_in(14.6, 6.4, 4.6, 4.2, 'z', only='Z')     # 왼쪽 위에서 빛을 받는다
    # 배기관
    p.rect(9, 12, 11, 13, 'Z'); p.rect(9, 10, 10, 13, 'Z')

    # 면갑 — 가운데 둥근 창. 작고 어둡게
    p.ell(17, 9.6, 4.4, 4.4, 'x')      # 창 테두리만 물빛
    p.ell(17, 9.8, 3.6, 3.6, 'J')
    p.ell_in(19.5, 12, 3.0, 2.6, 'z', only='Z')

    # 구조선 — 가슴 끈·허리띠 (덩어리를 가른다)
    p.rect(8, 30, 26, 30, 'J')
    p.rect(13, 22, 14, 30, 'J')
    p.rect(20, 22, 21, 30, 'J')

    # 허리 랜턴 — 화면에서 가장 밝은 점
    p.rect(2, 28, 5, 32, 'y')
    p.rect(3, 29, 4, 31, 'L')

    p.off = 0
    for lx, dxf, _d in legs_pairs(f, 11, 19):
        p.rect(lx, 38 + bob, lx + 4, 43, 'Z')
        p.rect(lx + dxf - 1, 43, lx + 5 + dxf, 47, 'z')
        p.rect(lx + dxf - 1, 43, lx + 5 + dxf, 43, 'J')
    p.outline('J')
    p.rim('X', 'left', 2)      # 등불 쪽 가장자리 빛 두 줄
    p.rim('x', 'right', 1)     # 물빛 쪽
    p.rim_top('X', 1)
    return p


# ─────────────────────────────────────────────────────────────
# P6 — 굵은 외곽선 치비 도트
#   원리: 머리를 크게, 외곽선을 2px로. 작은 모바일 화면에서
#   덩어리가 먼저 읽히고 얼굴이 크다.
# ─────────────────────────────────────────────────────────────

def build_p6(f=0):
    p = Px(38, 42)
    bob = [0, -1, -1][f]
    p.off = bob

    p.ell(30, 26, 3.2, 6.4, 'T')
    p.ell(29, 26, 1.2, 6, 't')
    p.rect(29, 17, 31, 20, 'B')

    p.ell(18, 27, 8.6, 3, 'c')
    wave(p, 11, 25, 27, 'o')

    p.ell(18, 33, 9.6, 7, 'm')
    p.ell_in(15, 31, 7, 5.4, 'l', only='m')
    p.ell_in(13.5, 30, 3.6, 2.6, 'h', only='ml')
    p.rect(9, 35, 27, 37, 'V')
    p.rect(17, 34, 19, 38, 'M')
    p.rect(14, 29, 15, 34, 'c'); p.rect(21, 29, 22, 34, 'c')

    p.rect(7, 30, 9, 36, 'm'); p.rect(27, 30, 29, 36, 'o')
    p.ell(8, 38, 2.8, 2.4, 'c'); p.ell(28, 38, 2.8, 2.4, 'C')

    p.ell(6, 33, 2, 2.6, 'y'); p.rect(5, 32, 7, 34, 'L')

    # 큰 머리
    p.ell(18, 13, 12.5, 11.5, 'B')
    p.ell(18, 12, 11.6, 10.6, 'N')
    p.ell(18, 10.6, 10, 8.8, 'M')
    p.ell(13, 6.6, 4, 2.6, 'H')
    p.rect(7, 21, 29, 22, 'B')
    p.rect(2, 10, 6, 11, 'N'); p.rect(2, 7, 3, 11, 'N'); p.rect(2, 6, 3, 6, 'M')

    p.ell(18, 15, 8.8, 8.6, 'B')
    p.ell(18, 15.2, 7.8, 7.6, 's')
    p.ell_in(21, 18, 6, 6, 'd', only='s')
    p.set(8, 14, 'H'); p.set(28, 14, 'H')

    p.ell_in(18, 9.6, 7.2, 1.8, 'r', only='sd')
    p.ell_in(14.8, 8.8, 4.6, 1.4, 'o', only='r')
    # 큰 눈
    brow(p, 12, 13, 4, 'l'); brow(p, 21, 13, 4, 'r')
    eye(p, 12, 15, 4, 4); eye(p, 21, 15, 4, 4)
    p.set(18, 19, 'd')
    smile(p, 18, 21, 2, open_mouth=True)
    blush(p, 10, 12, 19); blush(p, 24, 26, 19)

    p.off = 0
    for lx, dxf, _d in legs_pairs(f, 12, 20):
        p.rect(lx, 37 + bob, lx + 5, 39, 'o')
        p.rect(lx + dxf, 39, lx + 5 + dxf, 41, 'N')
    p.outline('K', rounds=2)   # 굵은 외곽선
    return p


BUILDERS = {
    'p1': (build_p1, '32px 초간결 — 가장 또렷한 끝'),
    'p2': (build_p2, '48px 생활형'),
    'p3': (build_p3, '64px 디테일'),
    'p4': (build_p4, 'HD-2D 밀착 — 가장 부드러운 끝'),
    'p5': (build_p5, '실루엣 중심'),
    'p6': (build_p6, '굵은 외곽선 치비'),
}
# 실사용 정수 배율 — 배경 주민 키 133px에 맞춘다. 소수 배율 금지.
SCALE = {'p1': 4, 'p2': 3, 'p3': 2, 'p4': 2, 'p5': 3, 'p6': 3}
# 얼굴 확대용 크롭 비율 (가로, 세로) — 머리 비중이 방향마다 다르다
FACE_CROP = {'p1': (0.95, 0.56), 'p2': (0.88, 0.56), 'p3': (0.86, 0.54),
             'p4': (0.88, 0.42), 'p5': (0.88, 0.52), 'p6': (0.94, 0.66)}


# ─────────────────────────────────────────────────────────────
# 표현 (배경·조명·확대)
# ─────────────────────────────────────────────────────────────

def room_bg(w, h, floor=0.86, window=True):
    """어두운 방 배경: 따뜻한 갈색 광원 + 바닥선 + 차가운 물 창 한 곳."""
    im = Image.new('RGB', (w, h), (18, 12, 9))
    px = im.load()
    cx, cy = w * 0.46, h * 0.42
    mr = math.hypot(w, h) * 0.62
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy) / mr
            k = max(0.0, 1.0 - d) ** 1.7
            px[x, y] = (int(16 + 44 * k), int(11 + 28 * k), int(9 + 18 * k))
    d = ImageDraw.Draw(im)
    fy = int(h * floor)
    d.rectangle([0, fy, w, h], fill=(27, 18, 13))
    d.line([0, fy, w, fy], fill=(74, 50, 32))
    # 물 창 (유일한 차가운 면)
    if window:
        ww = max(10, w // 11)
        d.ellipse([w - ww * 2, int(h * 0.10), w - ww // 2, int(h * 0.10) + ww + ww // 2],
                  fill=(14, 34, 40), outline=(70, 54, 30))
    return im


def up(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def to_h(im, hh):
    k = hh / im.height
    return im.resize((max(1, int(round(im.width * k))), hh), Image.NEAREST)


def soft_light(base, sprite_rgba, pos, lantern_xy=None, shadow=True):
    """HD-2D 표현: 접지 그림자 + 랜턴 블룸 + 전체 부드러운 광."""
    out = base.convert('RGBA')
    sx, sy = pos
    if shadow:
        sh = Image.new('RGBA', out.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(sh)
        w = int(sprite_rgba.width * 0.9)
        hgt = max(4, int(sprite_rgba.height * 0.11))
        cxp = sx + sprite_rgba.width // 2
        cyp = sy + sprite_rgba.height - hgt // 2
        dd.ellipse([cxp - w // 2, cyp - hgt // 2, cxp + w // 2, cyp + hgt // 2],
                   fill=(6, 4, 3, 170))
        sh = sh.filter(ImageFilter.GaussianBlur(max(2, hgt // 2)))
        out = Image.alpha_composite(out, sh)
    out.alpha_composite(sprite_rgba, (sx, sy))
    if lantern_xy:
        glow = Image.new('RGBA', out.size, (0, 0, 0, 0))
        dg = ImageDraw.Draw(glow)
        gx, gy = lantern_xy
        for r, a in ((int(sprite_rgba.height * 0.55), 42),
                     (int(sprite_rgba.height * 0.30), 60),
                     (int(sprite_rgba.height * 0.14), 90)):
            dg.ellipse([gx - r, gy - r, gx + r, gy + r], fill=(255, 176, 86, a))
        glow = glow.filter(ImageFilter.GaussianBlur(max(3, sprite_rgba.height // 12)))
        out = Image.alpha_composite(out, glow)
    return out.convert('RGB')


def font(sz=12):
    for name in ('malgun.ttf', 'malgunsl.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(name, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def label(d, xy, text, f, col=(214, 186, 150)):
    d.text(xy, text, font=f, fill=col)


# ─────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT, exist_ok=True)
    harmonize()                      # 팔레트를 배경 렌더에서 뽑는다
    f12, f14 = font(12), font(15)
    contact, scenes = [], []

    for key, (fn, title) in BUILDERS.items():
        dd = os.path.join(OUT, key)
        os.makedirs(dd, exist_ok=True)
        frames = [fn(i) for i in range(3)]
        sp = frames[0].img()
        k = SCALE[key]

        # 1) 원본 해상도
        sp.save(os.path.join(dd, 'full.png'))

        # 2) 4배 확대 (형태 확인용)
        big = up(sp, 4)
        bgw, bgh = big.width + 72, big.height + 56
        im = room_bg(bgw, bgh)
        px0, py0 = (bgw - big.width) // 2, bgh - big.height - int(bgh * 0.14)
        im.paste(big, (px0, py0), big)
        d = ImageDraw.Draw(im)
        label(d, (8, 6), '%s  %s   %dx%d (x4)' % (key.upper(), title, sp.width, sp.height), f12)
        im.save(os.path.join(dd, 'full4x.png'))

        # 3) 얼굴 확대
        cwf, chf = FACE_CROP[key]
        fw, fh = int(sp.width * cwf), int(sp.height * chf)
        fx = (sp.width - fw) // 2
        kf = max(4, int(430 / max(fw, fh)))
        fc = up(sp.crop((fx, 0, fx + fw, fh)), kf)
        fim = room_bg(fc.width + 24, fc.height + 36)
        fim.paste(fc, (12, 24), fc)
        label(ImageDraw.Draw(fim), (8, 5), '%s 얼굴 확대 (x%d)' % (key.upper(), kf), f12)
        fim.save(os.path.join(dd, 'face.png'))

        # 4) 정수 배율별 실제 크기 (소수 배율 금지)
        rw, rh = 340, 180
        rim_ = room_bg(rw, rh)
        d = ImageDraw.Draw(rim_)
        for j, kk in enumerate((1, 2, 3)):
            s2 = up(sp, kk)
            xc = 58 + j * 100
            rim_.paste(s2, (xc - s2.width // 2, int(rh * 0.84) - s2.height), s2)
            mark = ' <= 실사용' if kk == k else ''
            label(d, (xc - 30, int(rh * 0.86)), 'x%d %dpx%s' % (kk, s2.height, mark), f12,
                  (236, 198, 140) if kk == k else (168, 142, 112))
        label(d, (8, 5), '%s  정수 배율별 크기 (방 주민 키 = %dpx)' % (key.upper(), SCENE_TARGET_H), f14)
        rim_.save(os.path.join(dd, 'room.png'))

        # 5) 걷기 3프레임 — 실제 방 바닥 위, 실사용 배율
        strip = []
        for i2, fr in enumerate(frames):
            sc = up(fr.img(), k)
            if key == 'p4':
                sc = soften(sc, 0.5)
            sc = room_light(sc)
            sh = scene_crop().convert('RGBA')
            fx2 = SCENE_CX - sc.width // 2
            fy2 = SCENE_FLOOR - sc.height
            sh = ground_shadow(sh, (fx2, fy2), sc)
            sh.alpha_composite(sc, (fx2, fy2))
            strip.append(sh.convert('RGB'))
        wW = sum(x.width for x in strip) + 8 * 4
        wH = strip[0].height + 26
        wim = Image.new('RGB', (wW, wH), (16, 11, 9))
        xx = 8
        for i2, fi in enumerate(strip):
            wim.paste(fi, (xx, 20))
            label(ImageDraw.Draw(wim), (xx + 6, 3), 'f%d' % i2, f12)
            xx += fi.width + 8
        label(ImageDraw.Draw(wim), (wW - 170, 3), '걷기 3프레임 x%d 실제 크기' % k, f12)
        wim.save(os.path.join(dd, 'walk.png'))

        # 5-b) 걷기 스프라이트 시트 (1배, 투명) — 비교 페이지에서 CSS로 돌린다
        sheet = Image.new('RGBA', (sp.width * 3, sp.height), (0, 0, 0, 0))
        for i2, fr in enumerate(frames):
            sheet.paste(fr.img(), (sp.width * i2, 0))
        sheet.save(os.path.join(dd, 'walk_sheet.png'))
        # 방 빛을 받은 판 — 비교 페이지의 살아 있는 무대가 scene.png와 같은 빛을 쓰게
        lit = Image.new('RGBA', (sp.width * k * 3, sp.height * k), (0, 0, 0, 0))
        for i2, fr in enumerate(frames):
            one = up(fr.img(), k)
            if key == 'p4':
                one = soften(one, 0.5)
            lit.paste(room_light(one), (sp.width * k * i2, 0))
        lit.save(os.path.join(dd, 'walk_sheet_lit.png'))

        # 6) ★ 판정 컷 — 실제 렌더 방 위 1배 실제 크기
        sc = up(sp, k)
        if key == 'p4':
            sc = soften(sc, 0.5)
        sc = room_light(sc)
        sh = scene_crop().convert('RGBA')
        fx2 = SCENE_CX - sc.width // 2
        fy2 = SCENE_FLOOR - sc.height
        sh = ground_shadow(sh, (fx2, fy2), sc)
        sh.alpha_composite(sc, (fx2, fy2))
        # 허리 랜턴 블룸
        gl = Image.new('RGBA', sh.size, (0, 0, 0, 0))
        dg = ImageDraw.Draw(gl)
        gx = fx2 + int(sc.width * 0.11)
        gy = fy2 + int(sc.height * 0.72)
        for r, a in ((26, 30), (15, 44), (7, 70)):
            dg.ellipse([gx - r, gy - r, gx + r, gy + r], fill=(255, 178, 90, a))
        sh = Image.alpha_composite(sh, gl.filter(ImageFilter.GaussianBlur(7)))
        sh = sh.convert('RGB')
        sh.save(os.path.join(dd, 'scene.png'))
        scenes.append((key, title, sh, k))

        contact.append((key, title, sp))
        print('[ok] %s  %dx%d  x%d = %dpx' % (key, sp.width, sp.height, k, sp.height * k))

    scene_crop().save(os.path.join(OUT, 'room_plate.png'))   # 비교 페이지용 배경판

    # 여섯 장면 비교 (2x3)
    sw, shh = scenes[0][2].size
    gim = Image.new('RGB', (sw * 3 + 16, (shh + 24) * 2 + 8), (16, 11, 9))
    dg = ImageDraw.Draw(gim)
    for i2, (key, title, simg, kk) in enumerate(scenes):
        cx = (i2 % 3) * (sw + 8) + 4
        cy = (i2 // 3) * (shh + 24) + 22
        gim.paste(simg, (cx, cy))
        label(dg, (cx + 4, cy - 17), '%s %s (x%d)' % (key.upper(), title, kk), f12)
    gim.save(os.path.join(OUT, 'scene_all.png'))

    # 70px / 110px 판독 비교
    cw, ch = 960, 300
    cim = room_bg(cw, ch, window=False)
    d = ImageDraw.Draw(cim)
    step = cw // 6
    for i2, (key, title, sp) in enumerate(contact):
        for j, hh in enumerate((110, 70)):
            s2 = to_h(sp, hh)
            xc = step * i2 + step // 2 + (-24 if j == 0 else 30)
            cim.paste(s2, (xc - s2.width // 2, 210 - s2.height), s2)
        label(d, (step * i2 + 8, 228), key.upper(), f14)
        label(d, (step * i2 + 8, 248), title[:14], f12)
    label(d, (10, 8), '판독 시험 — 왼쪽 110px / 오른쪽 70px', f14)
    cim.save(os.path.join(OUT, 'contact.png'))
    meta = {'floor': SCENE_FLOOR, 'cx': SCENE_CX, 'target_h': SCENE_TARGET_H,
            'plate': list(scene_crop().size),
            'dirs': {k: {'title': BUILDERS[k][1], 'scale': SCALE[k],
                         'w': BUILDERS[k][0](0).w, 'h': BUILDERS[k][0](0).h}
                     for k in BUILDERS}}
    with io.open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(meta, ensure_ascii=False, indent=1))
    print('[ok] scene_all.png / contact.png / meta.json')


if __name__ == '__main__':
    main()
