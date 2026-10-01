# -*- coding: utf-8 -*-
"""
gen_chars_p2.py — P2(48px 생활형 도트) 확정판 · 전체 등장인물 세트 (스프린트 8-A)

사용자가 P2를 골랐다(DECISIONS 2026-10-01). 이 파일 하나가 8역할 · 6자세 ·
각인 12종 · 문어 · 뒷모습을 전부 찍는다. **생성 AI를 쓰지 않는다.**
모든 픽셀은 이 파일 안의 좌표 지정과 도형 원시함수(rect/ell/ell_in/outline)로만 만든다.

── 규약 (한 줄로 외울 것) ───────────────────────────────────────────────
  원화 1m = 27.5px.  맨머리 1.6m = **44 원화 px**.  아이 1.2m = **33 원화 px**.
  원화 셀 64×64, 발 기준선(발바닥 다음 줄) = 원화 y 60.
    ×4 → 셀 256 · 발 기준선 240 · 미터당 110px   ← 기존 front 규약과 **정확히** 일치
    ×3 → 셀 192 · 발 기준선 180 · 1.6m = 132px   ← 단면 렌더 방 안 실제 크기
  두 배율 모두 정수. S7 보고서가 지적한 「방향 간 키 ±12% 오차」가 여기서 사라진다.

출력: static/art/chars/front/p2/…   (상세는 같은 폴더 meta.json)
실행: python tools/gen_chars_p2.py
"""
import os, io, json, math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'static', 'art', 'chars', 'front', 'p2')

# ── 규약 상수 ────────────────────────────────────────────────────────────
CELL = 64          # 원화 셀 (정사각)
BASE_Y = 60        # 원화 발 기준선 (발바닥 픽셀의 마지막 줄 = 59)
FOOT = BASE_Y - 1  # 59
PPM = 27.5         # 원화 미터당 픽셀
SHEET_K = 4        # 시트 배율 → 셀 256 · 기준선 240 · 110px/m
ROOM_K = 3         # 방 합성 배율 → 1.6m = 132px

H_ADULT = 44       # 1.600 m
H_KID = 33         # 1.200 m

CLIPS = [('idle', 2), ('walk', 3), ('work', 3), ('sit', 2), ('carry', 2),
         ('hurt', 2), ('back_walk', 3)]
CLIP_SEC = {'idle': 2.8, 'walk': 0.8, 'work': 1.4, 'sit': 3.2,
            'carry': 1.0, 'hurt': 2.0, 'back_walk': 0.8}
MAXF = 3

# ── 팔레트 ───────────────────────────────────────────────────────────────
# 흙 계열 따뜻한 색이 바탕. 차가운 색은 유리·물에만(고글 렌즈, 각인 '금을 본 자').
PAL = {
    'line':  (42, 29, 22),      # 외곽선 — 검정이 아니라 따뜻한 숯갈색
    'line2': (26, 18, 14),
    'suitD': (68, 42, 26),      # 잠수복 그늘
    'suitM': (108, 68, 38),     # 잠수복 중간
    'suitL': (144, 95, 52),     # 잠수복 밝은
    'suitH': (186, 134, 76),
    'cream': (232, 210, 168),   # 캔버스 천·끈
    'creamD': (198, 174, 132),
    'oliv':  (104, 100, 58),    # 허리띠
    'olivD': (70, 66, 38),
    'skin':  (240, 207, 174),
    'skinD': (206, 162, 128),
    'blush': (216, 134, 118),
    'ink':   (58, 36, 24),      # 눈·눈썹·입
    'white': (255, 246, 230),
    'hair':  (78, 48, 32),
    'hairD': (54, 33, 22),
    'ox':    (150, 62, 48),     # 적갈 — 수선 자국·십자
    'brassD': (110, 76, 30),
    'brassM': (158, 116, 42),
    'brass': (208, 162, 64),
    'brassH': (242, 216, 144),
    'bootM': (80, 56, 38),      # 무게추 장화 — 검정이면 어두운 방에서 발이 사라진다
    'bootL': (112, 82, 54),
    'tank':  (122, 106, 78),
    'tankL': (160, 142, 106),
    'flame': (255, 212, 130),   # 랜턴 심지 (틴트 제외)
    'flameR': (236, 160, 70),
    'glassD': (48, 96, 104),    # 유리 그늘   ← 차가운 색
    'glass': (126, 190, 194),   # 유리 반사   ← 차가운 색
    # 문어 (짐승은 사람보다 따뜻하다 — C5)
    'octM': (182, 96, 78),
    'octD': (124, 56, 46),
    'octL': (222, 142, 110),
    # 각인 전용
    'impGrn': (142, 188, 96),
    'impPlum': (142, 102, 138),
    'impDark': (38, 28, 24),
    'impCop': (204, 128, 66),
    'impPale': (236, 230, 214),
}

# 역할 겉옷 색 — 70px에서 여덟이 갈리는 첫 번째 축. 전부 흙 계열 안에서 색상(hue)을 벌렸다.
ROLE_COLS = {
    'scout':    ((96, 110, 72),  (60, 72, 44),  (132, 148, 100)),   # 올리브 초록
    'cook':     ((206, 122, 56), (138, 72, 28), (238, 166, 94)),    # 번트오렌지
    'medic':    ((228, 216, 188),(166, 150, 118),(250, 242, 220)),  # 크림 흰
    'engineer': ((88, 82, 72),   (52, 48, 42),  (126, 118, 102)),   # 숯회색
    'farmer':   ((152, 128, 66), (98, 80, 36),  (192, 168, 102)),   # 황토
    'scholar':  ((128, 102, 124),(82, 62, 80),  (164, 138, 158)),   # 탁한 자줏빛
    'trader':   ((160, 88, 66),  (104, 52, 36), (198, 126, 94)),    # 적갈
    'kid':      ((226, 183, 76), (156, 118, 38),(248, 216, 126)),   # 노란 황토
}
for _r, (_m, _d, _l) in ROLE_COLS.items():
    PAL['r_' + _r] = _m
    PAL['rD_' + _r] = _d
    PAL['rL_' + _r] = _l

ROLES = ['scout', 'cook', 'medic', 'engineer', 'farmer', 'scholar', 'trader', 'kid']
ROLE_KO = {'scout': '정찰병', 'cook': '요리사', 'medic': '의무병', 'engineer': '기술자',
           'farmer': '농부', 'scholar': '학자', 'trader': '교섭가', 'kid': '아이'}
ROLE_SIG = {   # ①머리 ②겉옷 ③손
    'scout':    ('뾰족 꼭지가 달린 올리브 후드 + 뒤 꼬리', '올리브 조끼', '짧은 망원경'),
    'cook':     ('키 큰 천 모자', '번트오렌지 앞치마', '국자'),
    'medic':    ('머릿수건 + 뒤 꼬리', '크림 가운 + 적갈 완장', '약 가방'),
    'engineer': ('이마 위로 올린 넓은 용접 고글(물빛 렌즈)', '숯회색 작업복', '렌치'),
    'farmer':   ('넓은 밀짚 챙', '황토 작업복', '물뿌리개'),
    'scholar':  ('각진 납작 모자 + 깨진 안경', '자줏빛 긴 외투', '책'),
    'trader':   ('둥근 챙모자 + 목도리', '적갈 코트', '손저울'),
    'kid':      ('작은 우비 후드', '노란 우비', '작은 등불'),
}

# 틴트를 받으면 안 되는 색(스스로 빛나거나, 가독성 앵커)
NO_TINT = {'flame', 'flameR', 'white', 'ink', 'line', 'line2', 'glass', 'glassD'}

# ── 실제 렌더 방 (2.5D 판정 기준) ────────────────────────────────────────
#   사람 없는 플레이트가 아직 없어서(배경 담당 요청 중) 기존 렌더에서
#   주민을 피한 칸만 잘라 쓴다. 보고서 §미완에 적는다.
SCENE_SRC = os.path.join(ROOT, 'static', 'art', 'deep', 'section_room_zoom.png')
SCENE_BOX = (1148, 330, 1364, 600)   # 216×270 — 좌우 주민을 피한 깨끗한 칸
SCENE_FLOOR = 248                    # 크롭 기준 바닥선 y (전체 좌표 578)
SCENE_LAMP = (100, 40)
_cache = {}


def scene_crop():
    if 'im' not in _cache:
        _cache['im'] = Image.open(SCENE_SRC).convert('RGB').crop(SCENE_BOX)
    return _cache['im'].copy()


def lamp_tint():
    if 'tint' not in _cache:
        lx, ly = SCENE_LAMP
        box = scene_crop().crop((max(0, lx - 45), ly + 14, lx + 45, ly + 64))
        c = box.resize((1, 1), Image.BOX).getpixel((0, 0))
        m = max(1.0, sum(c) / 3.0)
        _cache['tint'] = tuple(ci / m for ci in c)
    return _cache['tint']


def clamp8(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def harmonize(strength=0.20, contrast=1.26):
    """2.5D 조건 ④ — 팔레트를 배경 렌더에서 뽑아 20% 당기고, 방 평균색 기준으로
    대비를 1.26배 재확장한다(S7에서 찾은 값. 당기기만 하면 벽에 묻혀 형체가 사라진다)."""
    crop = scene_crop()
    q = crop.quantize(colors=16, method=Image.MEDIANCUT)
    raw = q.getpalette()[:48]
    cols = [tuple(raw[i * 3:i * 3 + 3]) for i in range(16)]
    base = crop.resize((1, 1), Image.BOX).getpixel((0, 0))

    def lum(c):
        return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

    for k, c in list(PAL.items()):
        if k in NO_TINT:
            continue
        near = min(cols, key=lambda b: abs(lum(b) - lum(c)))
        mixed = [c[i] * (1 - strength) + near[i] * strength for i in range(3)]
        PAL[k] = tuple(clamp8(base[i] + (mixed[i] - base[i]) * contrast) for i in range(3))


def room_light(spr, strength=1.0):
    """2.5D 조건 ② — 방의 등불색을 받는다. 이것이 HD-2D의 생명."""
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


def ground_shadow(base, pos, spr, k=1.0):
    """2.5D 조건 ③ — 발밑 접지 그림자. 없으면 캐릭터가 공중에 뜬다."""
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    ww = int(spr.width * 0.70 * k)
    hh = max(5, int(spr.height * 0.075))
    cx = pos[0] + spr.width // 2
    cy = pos[1] + spr.height - hh // 3
    d.ellipse([cx - ww // 2, cy - hh // 2, cx + ww // 2, cy + hh // 2], fill=(10, 6, 4, 165))
    return Image.alpha_composite(base, sh.filter(ImageFilter.GaussianBlur(max(2, hh // 2))))


# ── 캔버스 ───────────────────────────────────────────────────────────────
class Cv:
    """원화 픽셀 캔버스. 칸 하나에 팔레트 키 문자열이 들어간다."""

    def __init__(self, w=CELL, h=CELL):
        self.w, self.h = w, h
        self.g = [[None] * w for _ in range(h)]

    def set(self, x, y, t):
        if t is None:
            return
        x = int(round(x)); y = int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = t

    def get(self, x, y):
        x = int(round(x)); y = int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.g[y][x]
        return None

    def rect(self, x0, y0, x1, y1, t):
        for y in range(int(round(y0)), int(round(y1)) + 1):
            for x in range(int(round(x0)), int(round(x1)) + 1):
                self.set(x, y, t)

    def ell(self, cx, cy, rx, ry, t):
        for y in range(int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1):
            for x in range(int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1):
                dx = (x - cx) / max(rx, .001); dy = (y - cy) / max(ry, .001)
                if dx * dx + dy * dy <= 1.0:
                    self.set(x, y, t)

    def ell_in(self, cx, cy, rx, ry, t, only=None):
        for y in range(int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1):
            for x in range(int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1):
                dx = (x - cx) / max(rx, .001); dy = (y - cy) / max(ry, .001)
                if dx * dx + dy * dy <= 1.0:
                    cur = self.get(x, y)
                    if cur is None:
                        continue
                    if only is not None and cur not in only:
                        continue
                    self.set(x, y, t)

    def outline(self, t='line'):
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.g[y][x] is not None:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.w and 0 <= ny < self.h and self.g[ny][nx] is not None:
                        add.append((x, y)); break
        for x, y in add:
            self.g[y][x] = t

    def bbox(self):
        xs = [x for y in range(self.h) for x in range(self.w) if self.g[y][x] is not None]
        ys = [y for y in range(self.h) for x in range(self.w) if self.g[y][x] is not None]
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def img(self):
        im = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))
        px = im.load()
        for y in range(self.h):
            for x in range(self.w):
                t = self.g[y][x]
                if t is not None:
                    px[x, y] = PAL[t] + (255,)
        return im

    def mask(self):
        """틴트 마스크 — 흰색일수록 방 등불색을 많이 받는다. 0 = 절대 틴트 금지."""
        im = Image.new('L', (self.w, self.h), 0)
        px = im.load()
        for y in range(self.h):
            for x in range(self.w):
                t = self.g[y][x]
                if t is None:
                    continue
                px[x, y] = 40 if t in ('line', 'line2') else (0 if t in NO_TINT else 255)
        return im


# ── 공통 부품 ────────────────────────────────────────────────────────────
def eye(c, x, y, w=3, h=3):
    c.rect(x, y, x + w - 1, y + h - 1, 'ink')
    c.set(x, y + h - 1, 'skin'); c.set(x + w - 1, y + h - 1, 'skin')
    c.set(x, y, 'white')


def brow(c, x, y, w, side):
    for i in range(w):
        dy = 1 if ((side == 'l' and i == 0) or (side == 'r' and i == w - 1)) else 0
        c.set(x + i, y + dy, 'ink')


def smile(c, cx, y, w=2, sad=False):
    for i in range(-w, w + 1):
        dy = (1 if sad else -1) if abs(i) == w else 0
        c.set(cx + i, y + dy, 'ink')


def blush(c, x0, x1, y):
    for x in range(x0, x1 + 1):
        if c.get(x, y) in ('skin', 'skinD'):
            c.set(x, y, 'blush')


def wave(c, x0, x1, y, t, step=2):
    for x in range(int(round(x0)), int(round(x1)) + 1, step):
        c.set(x, y, t)


def mitten(c, cx, cy, t='cream'):
    c.ell(cx, cy, 2.4, 2.2, t)


def boot(c, x0, x1, y0, y1):
    c.rect(x0, y0, x1, y1 - 1, 'bootM')
    c.rect(x0, y0, x0 + 1, y1 - 1, 'bootL')
    c.rect(x0, y1, x1, y1, 'brassM')      # 무게추 밑창
    c.set(x0, y1, 'brass'); c.set(x1, y1 - 1, 'brassD')


def lantern(c, cx, cy):
    c.ell(cx, cy, 1.9, 2.4, 'flameR')
    c.rect(cx - 1, cy - 1, cx + 1, cy + 1, 'flame')
    c.set(cx, cy - 3, 'brassD')


def tank(c, cx, cy, ry=7.0):
    c.ell(cx, cy, 2.7, ry, 'tank')
    c.ell(cx - 1, cy, 1.1, ry - .5, 'tankL')
    c.ell(cx, cy - ry, 2.7, 1.6, 'tankL')
    c.rect(cx - 1, cy - ry - 3, cx + 1, cy - ry, 'brassD')


# ── 머리에 쓴 것 (①) ────────────────────────────────────────────────────
def headwear(c, role, hx, hy, hr, back=False, layer='over'):
    """머리에 쓴 것 (①) — 70px 판독의 첫 번째 축.
    layer='under' 는 얼굴 구멍보다 먼저(두개골을 감싸는 천),
    layer='over'  는 얼굴보다 나중에(챙·밴드·꼬리) 그린다."""
    top = hy - hr
    rM, rD, rL = 'r_' + role, 'rD_' + role, 'rL_' + role
    if role == 'scout':
        # roles.json 의 hood:true 를 그대로 — 끐꼉한 꼬리가 달린 올리브 후드
        if layer == 'under':
            c.ell(hx, hy - .8, hr + .7, hr + .3, rM)
            c.ell_in(hx - 1.6, hy - 2.4, hr - .4, hr - 1.2, rL, only=(rM,))
            c.rect(hx - 2, hy - hr - 3, hx + 1, hy - hr - 2, rD)        # 꼬지
            c.set(hx - 1, hy - hr - 4, rM)
            c.rect(hx + hr - 2, top + 6, hx + hr + 3, top + 10, rD)     # 뒤로 넘긴 꼬리
            c.rect(hx + hr + 1, top + 9, hx + hr + 3, top + 14, rM)
        elif not back:
            c.rect(hx - hr + 2, top + 3, hx + hr - 2, top + 3, rD)      # 후드 알단
    elif role == 'cook':
        if layer == 'under':
            c.ell(hx, top - 2.2, hr - 1.4, 4.4, rL)                     # 키 큰 천 모자
            c.ell_in(hx + 2, top - 1.4, hr - 2.4, 3.4, rM, only=(rL,))
            c.rect(hx - hr + 1, top, hx + hr - 1, top + 2, rM)
            c.rect(hx - hr + 1, top + 2, hx + hr - 1, top + 2, rD)
            wave(c, hx - hr + 2, hx + hr - 2, top + 1, rL)
    elif role == 'medic':
        if layer == 'under':
            c.ell(hx, hy - 1.0, hr + .5, hr - .2, rL)                   # 머릿수건
            c.ell_in(hx + 2, hy + .5, hr - .5, hr - 1.5, rM, only=(rL,))
            c.rect(hx + hr - 2, top + 5, hx + hr + 2, top + 11, rL)     # 뒤 꼬리
            c.rect(hx + hr, top + 9, hx + hr + 2, top + 12, rM)
        elif not back:
            c.rect(hx - 1, top + 1, hx + 1, top + 1, 'ox')              # 이마 십자
            c.set(hx, top, 'ox'); c.set(hx, top + 2, 'ox')
    elif role == 'engineer':
        if layer == 'over':
            c.rect(hx - hr - 1, top - 2, hx + hr + 1, top + 2, rD)      # 이마 위로 올린 용접 고글
            c.rect(hx - hr - 1, top - 2, hx + hr + 1, top - 2, 'tankL')
            c.rect(hx - hr - 1, top - 1, hx - hr, top + 2, 'tankL')
            if not back:
                c.ell(hx - 3.6, top - .2, 2.4, 1.8, 'glassD')
                c.ell(hx + 3.6, top - .2, 2.4, 1.8, 'glassD')
                c.set(hx - 4, top - 1, 'glass'); c.set(hx + 3, top - 1, 'glass')
                c.rect(hx - 1, top - 1, hx + 1, top - 1, 'brassM')
            c.rect(hx + hr - 1, top + 2, hx + hr + 2, top + 5, 'tankL')  # 어깨 공구띄 끔
    elif role == 'farmer':
        if layer == 'over':
            c.rect(hx - hr - 5, top + 2, hx + hr + 5, top + 3, rM)      # 넓은 밀짚 챙
            c.rect(hx - hr - 5, top + 3, hx + hr + 5, top + 3, rD)
            wave(c, hx - hr - 4, hx + hr + 4, top + 2, rL)
        else:
            c.ell(hx, top + 1.0, hr - 1.5, 2.6, rL)                     # 낮은 밀짚 머리통
            c.ell_in(hx + 2, top + 1.5, hr - 2.5, 2.0, rM, only=(rL,))
    elif role == 'scholar':
        if layer == 'under':
            c.rect(hx - hr + 1, top - 2, hx + hr - 1, top + 2, rM)      # 각진 납작 모자
            c.rect(hx - hr + 1, top - 2, hx + hr - 1, top - 2, rL)
            c.rect(hx - hr + 1, top + 2, hx + hr - 1, top + 2, rD)
            c.rect(hx + hr - 1, top - 1, hx + hr + 1, top + 3, 'brass')  # 술
    elif role == 'trader':
        if layer == 'under':
            c.ell(hx, top + .2, hr - 2, 3.2, rM)                        # 둥근 챙모자 머리통
            c.ell(hx - 1, top - 1.4, hr - 3.5, 1.6, rL)
        else:
            c.rect(hx - hr - 3, top + 3, hx + hr + 3, top + 4, rD)      # 챙
            c.rect(hx - hr - 3, top + 3, hx + hr + 3, top + 3, rM)
    elif role == 'kid':
        if layer == 'under':
            c.ell(hx, hy - .6, hr + .8, hr + .4, rM)                    # 작은 우비 후드
            c.ell_in(hx - 1.5, hy - 2.2, hr - .5, hr - 1.2, rL, only=(rM,))
            c.set(hx, hy - hr - 2, rD); c.set(hx, hy - hr - 1, rM)      # 꼭지
            c.rect(hx - hr, hy + hr - 2, hx + hr, hy + hr, rD)          # 후드 아랫단


def hand_prop(c, role, x, y, flip=False):
    """손에 든 것 (③). x,y = 오른손 장갑 중심."""
    s = -1 if flip else 1
    rM, rD, rL = 'r_' + role, 'rD_' + role, 'rL_' + role
    if role == 'scout':                      # 짧은 망원경
        c.rect(x + s * 2, y - 4, x + s * 3, y + 1, 'brassM')
        c.rect(x + s * 2, y - 5, x + s * 3, y - 5, 'brass')
        c.set(x + s * 2, y - 4, 'brassH')
    elif role == 'cook':                     # 국자
        c.rect(x + s * 2, y - 6, x + s * 2, y, 'brassM')
        c.ell(x + s * 2, y + 1.5, 2.2, 1.8, 'brass')
        c.set(x + s * 2, y + 1, 'brassH')
    elif role == 'medic':                    # 약 가방
        c.rect(x + s * 1, y + 1, x + s * 5, y + 5, 'cream')
        c.rect(x + s * 1, y + 1, x + s * 5, y + 1, 'creamD')
        c.rect(x + s * 3, y + 2, x + s * 3, y + 4, 'ox')
        c.rect(x + s * 2, y + 3, x + s * 4, y + 3, 'ox')
    elif role == 'engineer':                 # 렌치
        c.rect(x + s * 2, y - 5, x + s * 3, y + 1, 'tankL')
        c.rect(x + s * 1, y - 7, x + s * 4, y - 6, 'tankL')
        c.set(x + s * 2, y - 7, None); c.set(x + s * 3, y - 7, None)
        c.set(x + s * 1, y - 7, 'tankL'); c.set(x + s * 4, y - 7, 'tankL')
    elif role == 'farmer':                   # 물뿌리개
        c.rect(x + s * 1, y - 2, x + s * 5, y + 3, rM)
        c.rect(x + s * 1, y - 2, x + s * 5, y - 2, rL)
        c.rect(x + s * 5, y - 4, x + s * 7, y - 1, rD)
        c.set(x + s * 7, y - 4, rD)
    elif role == 'scholar':                  # 책
        c.rect(x + s * 1, y - 4, x + s * 5, y + 2, rD)
        c.rect(x + s * 2, y - 3, x + s * 5, y + 1, 'cream')
        c.rect(x + s * 3, y - 3, x + s * 3, y + 1, 'creamD')
    elif role == 'trader':                   # 손저울
        c.rect(x + s * 3, y - 6, x + s * 3, y, 'brassM')
        c.rect(x + s * 1, y - 6, x + s * 5, y - 6, 'brassM')
        c.rect(x + s * 1, y - 4, x + s * 2, y - 4, 'brass')
        c.rect(x + s * 4, y - 3, x + s * 5, y - 3, 'brass')
        c.set(x + s * 1, y - 5, 'brassD'); c.set(x + s * 5, y - 5, 'brassD')
    elif role == 'kid':                      # 작은 등불
        c.rect(x + s * 2, y - 1, x + s * 4, y + 2, 'flameR')
        c.rect(x + s * 3, y, x + s * 3, y + 1, 'flame')
        c.set(x + s * 3, y - 2, 'brassD')


# ── 몸 ───────────────────────────────────────────────────────────────────
def legs_walk(f):
    """3프레임 걷기: f0 디딤 / f1 왼발 앞 / f2 오른발 앞."""
    return [(0, 0), (-1, 1), (1, -1)][f]


POSE = {
    #            머리 내림  몸통 반지름  목→몸통중심  다리     다리를 몸통 앞에
    'idle':      dict(drop=0,  tr=7.2, tdy=9, legs='stand', front=False),
    'walk':      dict(drop=0,  tr=7.2, tdy=9, legs='walk',  front=False),
    'work':      dict(drop=1,  tr=7.2, tdy=9, legs='stand', front=False),
    'sit':       dict(drop=10, tr=5.9, tdy=7, legs='sit',   front=True),
    'carry':     dict(drop=0,  tr=7.2, tdy=9, legs='stand', front=False),
    'hurt':      dict(drop=12, tr=5.9, tdy=7, legs='kneel', front=True),
    'back_walk': dict(drop=0,  tr=7.2, tdy=9, legs='walk',  front=False),
}


def draw_legs(c, mode, cx, leg_y0, kid, f):
    """다리. sit/kneel 은 몸통보다 나중에 그려 앞으로 나온다."""
    if mode == 'sit':
        # 한쪽으로 모아 앉기 — 바닥에 닿는 면이 넓어 '쉰다'가 멀리서도 읽힌다
        c.rect(cx - 6, FOOT - 9, cx + 5, FOOT - 2, 'suitD')          # 엉덩이
        c.rect(cx - 12, FOOT - 7, cx + 3, FOOT - 2, 'suitM')         # 허벅지(가로)
        c.rect(cx - 12, FOOT - 7, cx + 3, FOOT - 7, 'suitL')
        c.rect(cx - 12, FOOT - 2, cx + 3, FOOT - 2, 'suitD')
        c.ell(cx - 11, FOOT - 5, 3.4, 3.0, 'suitL')                  # 무릎
        c.rect(cx - 14, FOOT - 4, cx - 9, FOOT - 1, 'suitM')         # 정강이
        boot(c, cx - 15, cx - 9, FOOT - 3, FOOT)
        c.rect(cx + 1, FOOT - 4, cx + 7, FOOT - 1, 'suitD')
        boot(c, cx + 3, cx + 9, FOOT - 3, FOOT)
        return
    if mode == 'kneel':
        # 한 무릎을 꿇고 주저앉음
        c.rect(cx - 9, FOOT - 4, cx - 1, FOOT - 1, 'suitM')   # 바닥에 닿은 무릎
        c.rect(cx - 9, FOOT - 4, cx - 1, FOOT - 4, 'suitL')
        c.rect(cx - 9, FOOT - 1, cx - 1, FOOT, 'suitD')
        c.rect(cx + 1, FOOT - 10, cx + 6, FOOT - 3, 'suitD')  # 세운 무릎
        c.rect(cx + 1, FOOT - 10, cx + 2, FOOT - 3, 'suitM')
        boot(c, cx, cx + 7, FOOT - 3, FOOT)
        return
    dxL, dxR = (legs_walk(f) if mode == 'walk' else (0, 0))
    lw = 5 if not kid else 4
    for sx, dxf in ((cx - 6 if not kid else cx - 5, dxL),
                    (cx + 2 if not kid else cx + 1, dxR)):
        c.rect(sx, leg_y0, sx + lw - 1, FOOT - 5, 'suitD')
        c.rect(sx, leg_y0, sx + 1, FOOT - 5, 'suitM')
        boot(c, sx + dxf - 1, sx + lw + dxf - 1, FOOT - 4, FOOT)


def build(role, clip='idle', f=0):
    """한 프레임을 그린다. (캔버스, 각인 앵커)를 돌려준다."""
    c = Cv()
    kid = (role == 'kid')
    H = H_KID if kid else H_ADULT
    rM, rD, rL = 'r_' + role, 'rD_' + role, 'rL_' + role
    back = (clip == 'back_walk')
    P = POSE[clip]

    bob = {'walk': [0, -1, -1], 'back_walk': [0, -1, -1], 'idle': [0, 1],
           'sit': [0, 1], 'work': [0, -1, 0], 'carry': [0, 1],
           'hurt': [0, 1]}[clip][f]
    lean = 1 if clip == 'work' else (2 if clip == 'hurt' else 0)

    # ── 기준 좌표 (원화) ──
    hr = 8.5 if not kid else 7.4
    head_top = FOOT - (H - 1) + P['drop'] + bob      # 맨머리 꼭대기
    hy = head_top + hr
    hx = 32 + lean
    neck_y = head_top + (17 if not kid else 15)
    torso_ry = P['tr'] if not kid else P['tr'] - 2.2
    torso_rx = 8.6 if not kid else 6.9
    torso_cy = neck_y + (P['tdy'] if not kid else P['tdy'] - 3)
    belt_y = int(round(torso_cy + torso_ry * .45))
    leg_y0 = int(round(torso_cy + torso_ry - 1))
    cx = 32

    # ── 뒤쪽: 공기통 ──
    if not kid:
        if back:
            pass                 # 뒤에서 보면 공기통이 앞에 온다 — 몸통 뒤에 그린다
        else:
            tank(c, cx + 11, torso_cy - 1, torso_ry - 1.2)
            c.rect(cx + 7, neck_y + 1, cx + 10, neck_y + 2, 'suitD')

    # ── 다리 (뒤) ──
    if not P['front']:
        draw_legs(c, P['legs'], cx, leg_y0, kid, f)

    # ── 몸통 — 역할 겉옷이 가장 큰 색 면이다 (70px 판독의 두 번째 축) ──
    c.ell(cx, torso_cy, torso_rx, torso_ry, rM)
    c.ell_in(cx - 2, torso_cy - 2.2, torso_rx - 2, torso_ry - 1.2, rL, only=(rM,))
    c.ell_in(cx, torso_cy + torso_ry - 1, torso_rx, 3.2, rD, only=(rM, rL))
    c.rect(cx - torso_rx, neck_y + 1, cx - torso_rx + 1, torso_cy + 1, 'suitM')
    c.rect(cx + torso_rx - 1, neck_y + 1, cx + torso_rx, torso_cy + 1, 'suitD')
    if not back:
        c.rect(cx - 4, neck_y + 1, cx - 3, belt_y - 1, 'cream')
        c.rect(cx + 3, neck_y + 1, cx + 4, belt_y - 1, 'cream')
        c.rect(cx - 7, torso_cy - 2, cx - 6, torso_cy, 'ox')      # 기운 자국
    else:
        c.rect(cx - 5, neck_y + 2, cx + 5, neck_y + 3, 'cream')
    c.rect(cx - torso_rx + 1, belt_y, cx + torso_rx - 1, belt_y + 1, 'oliv')
    if not back:
        c.rect(cx - 1, belt_y - 1, cx + 1, belt_y + 2, 'brassM')
        c.set(cx, belt_y, 'brassH')

    # ── 뒷모습의 공기통 — 뒱에 메므로 앞으로 나온다 ──
    if back and not kid:
        tank(c, cx - 5, torso_cy - 1, torso_ry - .6)
        tank(c, cx + 5, torso_cy - 1, torso_ry - .6)
        c.rect(cx - 1, int(torso_cy - torso_ry), cx + 1, int(torso_cy + torso_ry - 2), 'cream')

    # ── 팔 ──
    arm_y0 = neck_y + 1
    arm_y1 = belt_y + (2 if not kid else 1)
    ax_l, ax_r = int(cx - torso_rx - 2), int(cx + torso_rx - 1)
    if clip == 'carry':
        c.rect(ax_l, arm_y0 + 1, ax_l + 3, arm_y1 - 1, 'suitM')
        c.rect(ax_r, arm_y0 + 1, ax_r + 3, arm_y1 - 1, 'suitD')
        bx0, bx1 = cx - 7, cx + 7
        by0, by1 = int(torso_cy - 1), int(torso_cy + 6)
        c.rect(bx0, by0, bx1, by1, 'suitL')
        c.rect(bx0, by0, bx1, by0, 'suitH')
        c.rect(bx0, by0, bx0, by1, 'suitH')
        c.rect(bx0, by1, bx1, by1, 'suitD')
        wave(c, bx0 + 1, bx1 - 1, by0 + 3, 'cream')
        wl, wr = (cx - 9, by0 + 2), (cx + 9, by0 + 2)
        mitten(c, wl[0], wl[1]); mitten(c, wr[0], wr[1], 'creamD')
    elif clip == 'hurt':
        c.rect(ax_l, arm_y0 + 1, ax_l + 3, FOOT - 5, 'suitM')
        wl = (ax_l + 1, FOOT - 3)
        mitten(c, wl[0], wl[1])                                   # 바닥을 짚은 손
        c.rect(ax_r, arm_y0 + 1, ax_r + 3, arm_y1, 'suitD')
        wr = (ax_r + 2, arm_y1 + 2)
        mitten(c, wr[0], wr[1], 'creamD')
    elif clip == 'sit':
        c.rect(ax_l, arm_y0 + 1, ax_l + 3, arm_y1, 'suitM')
        c.rect(ax_r, arm_y0 + 1, ax_r + 3, arm_y1, 'suitD')
        wl, wr = (ax_l + 1, arm_y1 + 2), (ax_r + 2, arm_y1 + 2)
        mitten(c, wl[0], wl[1]); mitten(c, wr[0], wr[1], 'creamD')
    else:
        sw = [0, 1, -1][f] if clip in ('walk', 'back_walk') else 0
        lift = [0, -4, -2][f] if clip == 'work' else 0
        c.rect(ax_l, arm_y0 + 1, ax_l + 3, arm_y1 + sw, 'suitM')
        c.rect(ax_l, arm_y0 + 1, ax_l + 1, arm_y1 + sw, 'suitL')
        c.rect(ax_r, arm_y0 + 1, ax_r + 3, arm_y1 - sw + lift, 'suitD')
        wl = (ax_l + 1, arm_y1 + sw + 2)
        wr = (ax_r + 2, arm_y1 - sw + lift + 2)
        mitten(c, wl[0], wl[1]); mitten(c, wr[0], wr[1], 'creamD')

    # ── 허리 랜턴 (장갑과 겹치지 않게 허리띠 바로 아래 앞쪽) ──
    if not kid:
        lantern(c, int(cx - torso_rx + 1), belt_y + 3)

    # ── 다리 (앞) ──
    if P['front']:
        draw_legs(c, P['legs'], cx, leg_y0, kid, f)

    # ── 손에 든 것 (③) ──
    if not back and clip in ('idle', 'walk', 'work'):
        hand_prop(c, role, wr[0], wr[1])

    # ── 목 실링 + 어깨 링 ──
    c.ell(cx, neck_y - 1, torso_rx - .4, 2.8, 'cream')
    c.ell(cx, neck_y - 2, torso_rx - 1, 2.0, 'creamD')
    wave(c, cx - torso_rx + 2, cx + torso_rx - 2, neck_y - 3, 'suitD')
    c.rect(cx - torso_rx + 1, neck_y, cx + torso_rx - 1, neck_y, 'brassD')
    c.set(cx - torso_rx + 2, neck_y, 'brassM'); c.set(cx + torso_rx - 2, neck_y, 'brassM')

    # ── 머리: 놋쇠 돔 + 완전히 노출된 얼굴 (면갑을 올린 상태) ──
    c.ell(hx, hy, hr, hr, 'brassD')
    c.ell(hx, hy - .5, hr - .9, hr - .9, 'brassM')
    c.ell(hx, hy - 1.1, hr - 1.9, hr - 1.9, 'brass')
    c.ell(hx - hr * .42, hy - hr * .58, hr * .36, hr * .24, 'brassH')
    headwear(c, role, hx, hy, hr, back, 'under')
    for bx in (-1, 1):                                   # 볼트 두 개
        c.set(int(round(hx + bx * (hr - 1.2))), int(round(hy - 1)), 'brassH')
    fy = hy + 1.5
    fr = hr - 2.2
    c.ell(hx, fy, fr + .9, fr + .9, 'brassD')            # 얼굴 구멍 테
    if back:
        c.ell(hx, fy, fr, fr, 'hair')
        c.ell_in(hx - 1.6, fy - 1.8, fr - 1.0, fr - 1.4, 'suitH', only=('hair',))
        c.rect(int(hx), int(fy - fr), int(hx), int(fy + fr - 3), 'hairD')   # 가르마
        c.rect(int(hx - 3), int(fy + fr - 2), int(hx + 3), int(fy + fr), 'hairD')  # 목덜미
    else:
        c.ell(hx, fy, fr, fr, 'skin')
        c.ell_in(hx + 1.6, fy + 1.6, fr - .6, fr - .6, 'skinD', only=('skin',))
        c.ell_in(hx, fy - fr + 1.2, fr - .4, 2.1, 'hair', only=('skin', 'skinD'))
        c.ell_in(hx - 1.8, fy - fr + .6, fr - 2.2, 1.4, 'hairD', only=('hair',))
        # 얼굴 — 눈·눈썹·입을 전부 그린다 (DECISIONS 2026-09-27, C10)
        ey = int(round(fy + .4))
        ew = 3
        exl = int(round(hx - 4.5)); exr = int(round(hx + 1.5))
        sad = (clip == 'hurt')
        brow(c, exl, ey - 3 + (1 if sad else 0), ew, 'l')
        brow(c, exr, ey - 3 + (1 if sad else 0), ew, 'r')
        eye(c, exl, ey, ew, 2 if sad else 3)
        eye(c, exr, ey, ew, 2 if sad else 3)
        c.set(hx, ey + 3, 'skinD')
        smile(c, hx, ey + 4, 2, sad=sad)
        blush(c, int(hx - 6), int(hx - 5), ey + 2)
        blush(c, int(hx + 5), int(hx + 6), ey + 2)
        if role == 'scholar':                            # 깨진 안경
            c.rect(hx - 6, ey - 1, hx - 1, ey - 1, 'brassM')
            c.rect(hx + 1, ey - 1, hx + 6, ey - 1, 'brassM')
            c.set(hx - 6, ey, 'brassM'); c.set(hx + 6, ey, 'brassM')
            c.set(hx - 3, ey + 1, 'brassH')
        if role == 'trader':                             # 목도리
            c.rect(hx - hr + 1, hy + hr - 1, hx + hr - 1, hy + hr + 1, rL)
            c.rect(hx + hr - 3, hy + hr + 1, hx + hr - 1, hy + hr + 4, rM)

    headwear(c, role, hx, hy, hr, back, 'over')

    if clip == 'work' and f == 1 and not back:           # 일하는 티 (C7)
        c.set(wr[0] + 4, wr[1] - 8, 'cream')
        c.set(wr[0] + 5, wr[1] - 10, 'creamD')

    c.outline('line')

    aL = {
        'head_top': (int(hx), int(head_top)),
        'forehead': (int(hx), int(round(fy - fr + 1.2))),
        'temple_l': (int(round(hx - fr - .4)), int(round(fy - 1))),
        'temple_r': (int(round(hx + fr - .6)), int(round(fy - 1))),
        'cheek_r': (int(round(hx + fr - 1.6)), int(round(fy + 2))),
        'neck_l': (int(round(cx - torso_rx + 2)), int(neck_y - 2)),
        'collar_r': (int(round(cx + torso_rx - 4)), int(neck_y + 1)),
        'chest': (int(cx), int(neck_y + 3)),
        'arm_l': (int(ax_l), int(neck_y + 5)),
        'wrist_r': (int(wr[0]), int(wr[1] - 2)),
        'mitten_l': (int(wl[0]), int(wl[1])),
        'belt_c': (int(cx + (4 if not kid else 0)), int(belt_y + 1)),
        'hr': hr, 'face_shown': (not back),
    }
    return c, aL


# ── 각인 12종 (C4 — 부위를 나눠 3개 동시에도 안 겹친다) ────────────────
IMPRINTS = [
    ('spore_mark',  '포자의 표식', '목덜미 왼쪽', '녹색'),
    ('empty_stomach', '빈 위장', '허리띠 오른쪽 매듭', '올리브·놋쇠'),
    ('warden',      '지킨 자', '오른 광대', '적갈'),
    ('sun_memory',  '햇빛의 기억', '머리 뒤로 늘어진 베일', '바랜 크림'),
    ('empty_seat',  '빈 자리', '왼 위팔', '숯검정'),
    ('footprint',   '발자국', '가슴 중앙 목걸이', '흰 이빨'),
    ('debt_paid',   '갚은 자', '오른 손목', '놋쇠'),
    ('water_memory', '물의 기억', '이마 앞머리', '젖은 머리 + 반짝임'),
    ('saved_breath', '아낀 숨', '오른 옷깃 호스 고리', '구릿빛'),
    ('crack_seen',  '금을 본 자', '왼 장갑 끝', '유리빛'),
    ('depth_mark',  '깊이의 자국', '왼 관자놀이', '자줏빛'),
    ('knock_heard', '두드림을 들은 자', '오른 관자놀이 울림쇠', '놋쇠 + 흰 점'),
]


def imprint_layer(iid, a):
    """각인 하나를 투명 레이어로. 본체와 같은 64×64 셀, 같은 자리에 겹치면 된다."""
    c = Cv()
    face = a['face_shown']
    if iid == 'spore_mark':
        x, y = a['neck_l']
        c.rect(x, y, x + 1, y, 'impGrn'); c.set(x + 1, y + 1, 'impGrn')
    elif iid == 'empty_stomach':
        x, y = a['belt_c']
        c.rect(x, y, x + 2, y, 'olivD'); c.set(x + 1, y + 1, 'brassM')
    elif iid == 'warden':
        if not face:
            return c
        x, y = a['cheek_r']
        c.set(x, y, 'ox'); c.set(x, y + 1, 'ox'); c.set(x + 1, y + 2, 'ox')
    elif iid == 'sun_memory':
        x, y = a['head_top']
        hr = int(a['hr'])
        c.rect(x - hr - 2, y + 10, x - hr, y + 16, 'impPale')     # 왼쪽으로 늘어진 베일
        c.rect(x - hr - 3, y + 13, x - hr - 2, y + 17, 'impPale')
        c.set(x - hr, y + 9, 'impPale')
    elif iid == 'empty_seat':
        x, y = a['arm_l']
        c.rect(x, y, x + 2, y + 1, 'impDark')
    elif iid == 'footprint':
        x, y = a['chest']
        c.set(x, y, 'impPale'); c.set(x, y + 1, 'white'); c.set(x, y + 2, 'impPale')
    elif iid == 'debt_paid':
        x, y = a['wrist_r']
        c.rect(x - 1, y, x + 1, y, 'brass'); c.set(x, y + 1, 'brassH')
    elif iid == 'water_memory':
        if not face:
            return c
        x, y = a['forehead']
        c.rect(x - 2, y, x + 2, y, 'hairD'); c.set(x - 1, y - 1, 'white')
    elif iid == 'saved_breath':
        x, y = a['collar_r']
        c.rect(x, y, x + 2, y, 'impCop'); c.set(x + 2, y + 1, 'impCop')
    elif iid == 'crack_seen':
        x, y = a['mitten_l']
        c.set(x - 1, y - 1, 'glass'); c.set(x, y - 2, 'glass'); c.set(x - 2, y, 'glassD')
    elif iid == 'depth_mark':
        x, y = a['temple_l']
        c.rect(x, y, x, y + 1, 'impPlum'); c.set(x + 1, y + 2, 'impPlum')
    elif iid == 'knock_heard':
        x, y = a['temple_r']
        c.rect(x, y, x, y + 1, 'brass'); c.set(x - 1, y + 2, 'white')
    return c


# ── 문어 (식구. 어떤 매체에서도 발화하지 않는다 — DECISIONS 2026-09-27) ──
def build_octopus(pose='idle', f=0):
    """문어 — 식구다. 짐승은 사람보다 가깝고 따뜻하다(C5).
    어떤 매체에서도 발화하지 않는다(DECISIONS 2026-09-27)."""
    c = Cv()
    bob = [0, 1, 0][f % 3]
    body, bodyD, bodyL = 'octM', 'octD', 'octL'
    cx = 30
    cy = FOOT - 13 + bob

    def arm(x0, y0, ang, length, thick, curl, t=None):
        px_, py_ = float(x0), float(y0)
        a = math.radians(ang)
        for k in range(length):
            w = max(0.6, thick * (1.0 - k / float(length)) + .4)
            c.ell(px_, py_, w, w * .85, t or (bodyD if k % 4 == 3 else body))
            if k % 3 == 1 and w > 1.2:                  # 빨판
                c.set(px_, py_ + w * .6, bodyL)
            a += math.radians(curl)
            px_ += math.cos(a); py_ += math.sin(a)

    # 여덟 팔 — 아래로 늘어지고 끝이 말린다
    specs = [(-9, 148, 14, 2.4, 6), (-7, 124, 15, 2.7, 4), (-4, 106, 13, 2.6, 3),
             (-1, 95, 10, 2.2, 2), (1, 85, 10, 2.2, -2), (4, 74, 13, 2.6, -3),
             (7, 56, 15, 2.7, -4), (9, 32, 14, 2.4, -6)]
    for dx, ang, ln, th, cu in specs:
        arm(cx + dx, cy + 6.5, ang + math.sin(f * 1.1 + dx) * 5, ln, th, cu)

    # 외투막(머리처럼 보이는 몸통)
    c.ell(cx, cy, 9.2, 8.4, body)
    c.ell(cx, cy - 5.5, 6.0, 4.4, body)                  # 위로 솟은 부분
    c.ell_in(cx - 2.6, cy - 3.6, 6.4, 5.4, bodyL, only=(body,))
    c.ell_in(cx, cy + 5.6, 9.2, 3.4, bodyD, only=(body, bodyL))
    for dx in (-5, 0, 5, -2, 3):                         # 사마귀 무늬 (반복 무늬)
        c.set(cx + dx, cy + 2 + (dx % 3), bodyD)
    c.rect(cx - 7, cy + 7, cx + 7, cy + 8, bodyD)        # 외투막 아랫단
    c.ell(cx + 7.5, cy - 1.5, 2.2, 2.6, bodyL)           # 숨구멍(사이펀)
    c.set(cx + 8, cy - 2, bodyD)

    # 눈 — 크고 둥글고 사람보다 밝다 (C5). 신뢰의 역전을 눈으로 말한다
    for ex in (cx - 4, cx + 4):
        c.ell(ex, cy + .2, 2.8, 2.6, 'white')
        c.ell(ex, cy + .6, 1.5, 1.5, 'ink')
        c.set(ex - 1, cy - 1, 'white')
    c.ell_in(cx, cy - 2.8, 8.0, 1.4, bodyD, only=(body, bodyL))   # 눈두덩

    if pose == 'wrap':
        # 손목 감기 (J7) — 사람의 손목 하나와, 그 둘레를 세 바퀴 감은 팔
        wx, wy = cx + 20, cy + 1
        c.rect(wx - 2, wy - 9, wx + 4, wy + 4, 'suitM')            # 잠수복 소매
        c.rect(wx - 2, wy - 9, wx, wy + 4, 'suitL')
        mitten(c, wx + 1, wy + 7)                                   # 벙어리 장갑
        for k in range(22):                                         # 뻗어 나간 팔
            t = k / 21.0
            x = cx + 8 + t * 10
            y = cy + 5 - math.sin(t * 2.0) * 5.5
            w = 2.5 - t * 1.1
            c.ell(x, y, w, w * .85, body if k % 4 else bodyD)
        bands = ((wy - 6, 5.2, 0), (wy - 2, 4.6, -1), (wy + 2, 3.8, 1))
        for yy, rw, ox in bands:                                    # 세 바퀴
            c.ell(wx + 1 + ox, yy, rw, 1.5, body)
            c.ell_in(wx + 1 + ox, yy - .6, rw - .6, .9, bodyL, only=(body,))
            c.set(wx + 1 + ox - int(rw), yy + 1, bodyD)
            c.set(wx + 1 + ox + int(rw), yy + 1, bodyD)
        c.set(wx + 6, wy + 3, body); c.set(wx + 7, wy + 2, bodyD)   # 말린 끝
    c.outline('line')
    return c


# ── 출력 ─────────────────────────────────────────────────────────────────
def up(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def to_h(im, hh):
    k = hh / im.height
    return im.resize((max(1, int(round(im.width * k))), hh), Image.NEAREST)


def font(sz=12):
    for name in ('malgun.ttf', 'malgunsl.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(name, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def room_bg(w, h, floor=0.86, light=True):
    im = Image.new('RGB', (w, h), (18, 12, 9))
    px = im.load()
    cx, cy = w * 0.5, h * 0.36
    mr = math.hypot(w, h) * 0.62
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy) / mr
            k = max(0.0, 1.0 - d) ** 1.7
            if light:
                px[x, y] = (int(96 + 86 * k), int(72 + 70 * k), int(50 + 48 * k))
            else:
                px[x, y] = (int(16 + 44 * k), int(11 + 28 * k), int(9 + 18 * k))
    d = ImageDraw.Draw(im)
    fy = int(h * floor)
    d.rectangle([0, fy, w, h], fill=(142, 108, 70) if light else (27, 18, 13))
    d.line([0, fy, w, fy], fill=(96, 70, 44) if light else (74, 50, 32))
    return im


def sheet_of(cells, k):
    """3열 × 7행 시트. 셀 = CELL*k, 발 기준선 = BASE_Y*k."""
    w, h = CELL * k * MAXF, CELL * k * len(CLIPS)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for (clip, n), row in zip(CLIPS, range(len(CLIPS))):
        for i in range(n):
            one = cells[(clip, i)]
            im.paste(up(one, k) if k > 1 else one, (CELL * k * i, CELL * k * row))
    return im


def mask_sheet_of(cells, k):
    w, h = CELL * k * MAXF, CELL * k * len(CLIPS)
    im = Image.new('L', (w, h), 0)
    for (clip, n), row in zip(CLIPS, range(len(CLIPS))):
        for i in range(n):
            one = cells[(clip, i)]
            im.paste(one.resize((one.width * k, one.height * k), Image.NEAREST) if k > 1 else one,
                     (CELL * k * i, CELL * k * row))
    return im


def trim_sprite(c):
    """외곽 여백을 잘라 낸 실제 스프라이트와 발·머리 좌표."""
    bb = c.bbox()
    im = c.img()
    return im.crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), bb


def main():
    os.makedirs(OUT, exist_ok=True)
    for sub in ('src', 'masks', 'imprints', 'check'):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    harmonize()
    f12, f14, f16 = font(12), font(15), font(18)

    meta_roles = {}
    standing = {}        # 70px 비교용 (idle f0)
    sheets1 = {}

    for role in ROLES:
        cells, mcells = {}, {}
        for clip, n in CLIPS:
            for i in range(n):
                c, a = build(role, clip, i)
                cells[(clip, i)] = c.img()
                mcells[(clip, i)] = c.mask()
                if clip == 'idle' and i == 0:
                    anchors0 = a
                    base_cv = c
        s1 = sheet_of(cells, 1)
        s4 = sheet_of(cells, SHEET_K)
        s1.save(os.path.join(OUT, 'src', role + '.png'))
        s4.save(os.path.join(OUT, role + '.png'))
        mask_sheet_of(mcells, 1).save(os.path.join(OUT, 'masks', role + '.png'))
        sheets1[role] = s1

        # 실측 검증 — 맨머리 꼭대기와 발바닥
        H = H_KID if role == 'kid' else H_ADULT
        head_top = anchors0['head_top'][1]
        px_h = FOOT - head_top + 1
        bb = base_cv.bbox()
        meta_roles[role] = {
            'ko': ROLE_KO[role],
            'sig_head': ROLE_SIG[role][0], 'sig_coat': ROLE_SIG[role][1], 'sig_hand': ROLE_SIG[role][2],
            'color': '#%02X%02X%02X' % ROLE_COLS[role][0],
            'bare_head_px': px_h, 'bare_head_m': round(px_h / PPM, 4),
            'head_top_y': head_top, 'foot_y': FOOT,
            'with_hat_top_y': bb[1], 'with_hat_px': FOOT - bb[1] + 1,
        }
        standing[role] = cells[('idle', 0)]
        print('[ok] %-9s 맨머리 %2dpx = %.3fm  (모자 포함 %2dpx)'
              % (role, px_h, px_h / PPM, FOOT - bb[1] + 1))

    # ── 각인 레이어 ──
    #   앵커는 역할이 아니라 **자세와 체격**에 달려 있다. 어른 여덟은 체격이 같으므로 한 벌,
    #   아이는 체격이 달라 따로 한 벌(imprints/kid/).
    os.makedirs(os.path.join(OUT, 'imprints', 'kid'), exist_ok=True)
    for who, sub in (('scout', ''), ('kid', 'kid')):
        for iid, ko, part, col in IMPRINTS:
            cells = {}
            for clip, n in CLIPS:
                for i in range(n):
                    _c, a = build(who, clip, i)
                    cells[(clip, i)] = imprint_layer(iid, a).img()
            d0 = os.path.join(OUT, 'imprints', sub) if sub else os.path.join(OUT, 'imprints')
            sheet_of(cells, 1).save(os.path.join(d0, iid + '.png'))
            sheet_of(cells, SHEET_K).save(os.path.join(d0, iid + '_x4.png'))
    print('[ok] 각인 %d종 × 2벌(어른·아이)' % len(IMPRINTS))

    # ── 문어 ──
    oc = Cv(CELL * 4, CELL)
    for i in range(3):
        o = build_octopus('idle', i).img()
        oc_im = o
        if i == 0:
            octo_idle = o
        oc.g = oc.g  # noop
    oct_sheet = Image.new('RGBA', (CELL * 4, CELL), (0, 0, 0, 0))
    for i in range(3):
        oct_sheet.paste(build_octopus('idle', i).img(), (CELL * i, 0))
    oct_sheet.paste(build_octopus('wrap', 0).img(), (CELL * 3, 0))
    oct_sheet.save(os.path.join(OUT, 'src', 'octopus.png'))
    up(oct_sheet, SHEET_K).save(os.path.join(OUT, 'octopus.png'))
    print('[ok] 문어 idle 3 + wrap 1')

    # ── 검증 1: 70px 8역할 한 줄 (밝은 벽 / 어두운 방) ──
    for name, light in (('check/row70_light.png', True), ('check/row70_dark.png', False)):
        W, Hh = 980, 220
        im = room_bg(W, Hh, 0.80, light)
        d = ImageDraw.Draw(im)
        step = W // 8
        for i, role in enumerate(ROLES):
            sp = standing[role]
            bb = Image.fromarray(__import__('numpy').array(sp)) if False else None
            s = to_h(sp.crop(sp.getbbox()), 70)
            xc = step * i + step // 2
            im.paste(s, (xc - s.width // 2, int(Hh * 0.80) - s.height), s)
            d.text((step * i + 6, int(Hh * 0.80) + 8), ROLE_KO[role], font=f14,
                   fill=(40, 28, 18) if light else (226, 198, 150))
        d.text((8, 6), '70px 판독 — %s' % ('밝은 벽' if light else '어두운 방'), font=f16,
               fill=(40, 28, 18) if light else (236, 206, 150))
        im.save(os.path.join(OUT, name))

    # ── 검증 1-b: 검은 실루엣 70px (자가 검수 1번) ──
    W, Hh = 980, 150
    im = room_bg(W, Hh, 0.84, True)
    d = ImageDraw.Draw(im)
    step = W // 8
    for i, role in enumerate(ROLES):
        sp = standing[role].crop(standing[role].getbbox())
        s = to_h(sp, 70)
        sil = Image.new('RGBA', s.size, (0, 0, 0, 0))
        px, qx = s.load(), sil.load()
        for y in range(s.height):
            for x in range(s.width):
                if px[x, y][3] > 0:
                    qx[x, y] = (22, 14, 10, 255)
        xc = step * i + step // 2
        im.paste(sil, (xc - sil.width // 2, int(Hh * 0.84) - sil.height), sil)
        d.text((step * i + 6, int(Hh * 0.84) + 6), ROLE_KO[role], font=f14, fill=(40, 28, 18))
    d.text((8, 6), '검은 실루엣 70px — 머리에 쓴 것과 손에 든 것만으로 갈리는가', font=f16, fill=(40, 28, 18))
    im.save(os.path.join(OUT, 'check', 'silhouette70.png'))

    # ── 검증 2: 실제 렌더 방 합성 (×3) ──
    #   사람 없는 플레이트가 아직 없다. 넓은 칸을 잘라 주민을 피해 세우고,
    #   동시에 옛 화풍 주민과 **키가 같은지**를 눈으로 확인하는 컷으로 쓴다.
    wide = Image.open(SCENE_SRC).convert('RGB').crop((1000, 320, 1480, 600)).convert('RGBA')
    comp = wide.copy()
    picks = [('scout', 170, 'idle', 0), ('cook', 240, 'work', 1), ('kid', 305, 'idle', 0)]
    for role, px_x, clip, fi in picks:
        c, _a = build(role, clip, fi)
        bb = c.bbox()
        spr = room_light(up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), ROOM_K))
        px0 = px_x - spr.width // 2
        py0 = (578 - 320) - (FOOT - bb[1] + 1) * ROOM_K
        comp = ground_shadow(comp, (px0, py0), spr)
        comp.alpha_composite(spr, (px0, py0))
    big = up(comp.convert('RGB'), 2)
    d = ImageDraw.Draw(big)
    # 실측 눈금 — 바닥선에서 1.6m(=132px ×3) 와 1.2m 를 그어 넣는다
    fl = (578 - 320) * 2
    for m, lab in ((1.6, '1.6m = 132px'), (1.2, '1.2m = 99px')):
        yy = fl - int(m * PPM * ROOM_K) * 2
        d.line([24, yy, big.width - 24, yy], fill=(255, 196, 96))
        d.text((28, yy - 16), lab, font=f12, fill=(255, 212, 130))
    d.line([24, fl, big.width - 24, fl], fill=(255, 196, 96))
    d.rectangle([2, 2, big.width - 3, 26], fill=(16, 11, 9))
    d.text((8, 5), '실제 렌더 방 × P2 도트 — 정수 배율 ×3 · 맨머리 1.6m = 132px', font=f16,
           fill=(236, 206, 150))
    d.text((8, big.height - 24), '※ 좌우 끝의 인물은 배경 렌더에 이미 그려진 옛 화풍 주민이다'
           ' (사람 없는 플레이트를 배경 담당에게 요청해 둠). 키 비교용으로 남겼다.',
           font=f12, fill=(200, 168, 128))
    big.save(os.path.join(OUT, 'check', 'room_composite.png'))
    scene_crop().save(os.path.join(OUT, 'room_plate.png'))

    # ── 각인 겹침 객관 검사 — 12종 레이어가 한 픽셀도 공유하지 않는가 ──
    for who in ('scout', 'kid'):
        _c0, a0 = build(who, 'idle', 0)
        occupied, clash = {}, []
        for iid, ko, part, col in IMPRINTS:
            lay = imprint_layer(iid, a0)
            for y in range(CELL):
                for x in range(CELL):
                    if lay.g[y][x] is None:
                        continue
                    if (x, y) in occupied:
                        clash.append((iid, occupied[(x, y)], x, y))
                    occupied[(x, y)] = iid
        print('[검사] %-5s 각인 12종 픽셀 충돌: %d건 %s' % (who, len(clash), clash[:4]))
    _c0, a0 = build('scout', 'idle', 0)

    def zoom_panel(role, ids, k_fig=4, k_zoom=9):
        """본체 + 각인 위치 상자 + 확대 조각."""
        c, a = build(role, 'idle', 0)
        base = c.img()
        boxes = []
        for iid in ids:
            lay = imprint_layer(iid, a)
            bbl = lay.bbox()
            if bbl:
                boxes.append((iid, bbl))
            base.alpha_composite(lay.img())
        bb = c.bbox()
        fig = up(base.crop((bb[0] - 1, bb[1] - 1, bb[2] + 2, bb[3] + 2)), k_fig)
        df = ImageDraw.Draw(fig)
        for iid, bl in boxes:
            x0 = (bl[0] - (bb[0] - 1)) * k_fig - 2
            y0 = (bl[1] - (bb[1] - 1)) * k_fig - 2
            x1 = (bl[2] + 1 - (bb[0] - 1)) * k_fig + 1
            y1 = (bl[3] + 1 - (bb[1] - 1)) * k_fig + 1
            df.rectangle([x0, y0, x1, y1], outline=(255, 214, 120))
        zooms = []
        for iid, bl in boxes:
            pad = 3
            cut = base.crop((bl[0] - pad, bl[1] - pad, bl[2] + 1 + pad, bl[3] + 1 + pad))
            zooms.append((iid, up(cut, k_zoom)))
        return fig, zooms

    # ── 검증 3: 각인 3개 동시 착용 ──
    sets = [('scout', ['warden', 'empty_seat', 'debt_paid']),
            ('medic', ['spore_mark', 'water_memory', 'footprint']),
            ('engineer', ['crack_seen', 'depth_mark', 'knock_heard']),
            ('farmer', ['sun_memory', 'empty_stomach', 'saved_breath'])]
    PW, W, Hh = 262, 1048, 330
    im = room_bg(W, Hh, 0.99, False)
    d = ImageDraw.Draw(im)
    for i, (role, ids) in enumerate(sets):
        fig, zooms = zoom_panel(role, ids, 4, 5)
        x0 = i * PW + 10
        im.paste(fig, (x0, 36), fig)
        d.text((x0, 36 + fig.height + 4), ROLE_KO[role], font=f14, fill=(236, 206, 150))
        zx = x0 + fig.width + 8
        for j, (iid, z) in enumerate(zooms):
            zy = 40 + j * 92
            im.paste(z, (zx, zy), z)
            nm = [t[1] for t in IMPRINTS if t[0] == iid][0]
            pt = [t[2] for t in IMPRINTS if t[0] == iid][0]
            d.text((zx, zy + z.height + 2), nm, font=f12, fill=(242, 214, 152))
            d.text((zx, zy + z.height + 18), pt, font=f12, fill=(184, 156, 120))
    d.text((8, 6), '각인 3개 동시 착용 — 노란 상자가 각인 자리. 12종 전체가 한 픽셀도 겹치지 않는다(자동 검사 0건)',
           font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'imprint3.png'))

    # ── 검증 3-b: 각인 12종 ──
    W, Hh = 1180, 620
    im = room_bg(W, Hh, 0.99, False)
    d = ImageDraw.Draw(im)
    for i, (iid, ko, part, col) in enumerate(IMPRINTS):
        fig, zooms = zoom_panel('scout', [iid], 3, 8)
        cx0 = (i % 4) * (W // 4) + 10
        cy0 = (i // 4) * 200 + 30
        im.paste(fig, (cx0, cy0), fig)
        if zooms:
            im.paste(zooms[0][1], (cx0 + fig.width + 4, cy0 + 10), zooms[0][1])
        d.text((cx0 + fig.width + 4, cy0 + 100), ko, font=f14, fill=(240, 212, 150))
        d.text((cx0 + fig.width + 4, cy0 + 118), part, font=f12, fill=(190, 162, 124))
        d.text((cx0 + fig.width + 4, cy0 + 134), col, font=f12, fill=(158, 134, 102))
    d.text((8, 6), '각인 12종 — 머리·목·가슴·팔·손목·허리로 부위를 나눴다 (오른쪽은 ×8 확대)',
           font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'imprints12.png'))

    # ── 검증 4: 자세 여섯 + 뒷모습 ──
    rowspec = [[('idle', 2, '느린 호흡'), ('walk', 3, '걷기'), ('work', 3, '일하기'),
                ('carry', 2, '물건 들기')],
               [('sit', 2, '앉기'), ('hurt', 2, '부상·주저앉음'), ('back_walk', 3, '뒷모습 걷기')]]
    W, Hh = 1060, 540
    im = room_bg(W, Hh, 0.99, False)
    d = ImageDraw.Draw(im)
    for r, row in enumerate(rowspec):
        base_y = 160 + r * 250
        x = 12
        for clip, n, ko in row:
            x_start = x
            for i in range(n):
                c, _ = build('scout', clip, i)
                bb = c.bbox()
                s2 = up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), 3)
                im.paste(s2, (x, base_y - (FOOT - bb[1] + 1) * 3), s2)
                x += s2.width + 3
            d.line([x_start - 4, base_y + 1, x - 6, base_y + 1], fill=(120, 92, 58))
            d.text((x_start, base_y + 6), '%s (%d)' % (ko, n), font=f14, fill=(230, 200, 150))
            d.text((x_start, base_y + 24), clip, font=f12, fill=(170, 144, 110))
            x += 26
    d.text((8, 6), '자세 — 발 기준선(가로 선)은 전부 같다. 앉기·주저앉음은 다리를 몸통 앞으로 그린다',
           font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'poses.png'))

    # ── 검증 5: 걷기 애니메이션 시트 (방 빛을 받은 판) ──
    W = 8 * 150
    im = room_bg(W, 210, 0.81, False)
    d = ImageDraw.Draw(im)
    for i, role in enumerate(ROLES):
        for fidx in range(3):
            c, _ = build(role, 'walk', fidx)
            bb = c.bbox()
            s = room_light(up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), 2))
            im.paste(s, (i * 150 + 8 + fidx * 46, 170 - s.height), s)
        d.text((i * 150 + 8, 178), ROLE_KO[role] + ' walk f0~2', font=f12, fill=(214, 186, 150))
    d.text((8, 6), '걷기 3프레임 × 8역할 (×2, 방 빛 적용)', font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'walk_all.png'))

    # 걷기 시트(방 빛) — 비교 페이지가 CSS steps(3)로 돌린다
    for role in ROLES:
        lit = Image.new('RGBA', (CELL * ROOM_K * 3, CELL * ROOM_K), (0, 0, 0, 0))
        for i in range(3):
            c, _ = build(role, 'walk', i)
            lit.paste(room_light(up(c.img(), ROOM_K)), (CELL * ROOM_K * i, 0))
        lit.save(os.path.join(OUT, 'check', 'walklit_%s.png' % role))

    # ── 검증 6: 문어 ──
    W, Hh = 620, 240
    im = room_bg(W, Hh, 0.84, False)
    d = ImageDraw.Draw(im)
    for i, (pose, fi, lab) in enumerate((('idle', 0, 'idle f0'), ('idle', 1, 'idle f1'),
                                         ('wrap', 0, '손목 감기 (J7)'))):
        c = build_octopus(pose, fi)
        bb = c.bbox()
        s = up(c.img().crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1)), 3)
        im.paste(s, (20 + i * 200, int(Hh * 0.84) - s.height), s)
        d.text((20 + i * 200, int(Hh * 0.84) + 8), lab, font=f14, fill=(226, 198, 150))
    d.text((8, 6), '문어 — 식구다. 말하지 않는다 (DECISIONS 2026-09-27)', font=f16, fill=(236, 206, 150))
    im.save(os.path.join(OUT, 'check', 'octopus.png'))

    # ── 메타 ──
    meta = {
        '_comment': 'P2 48px 생활형 도트 — 확정 화풍. 정수 배율 + image-rendering:pixelated 필수.',
        'style': 'p2', 'authored': 'hand-plotted pixels, no generative AI',
        'src_cell': CELL, 'src_baseline': BASE_Y, 'src_ppm': PPM,
        'sheet_scale': SHEET_K, 'cell': CELL * SHEET_K, 'baseline': BASE_Y * SHEET_K,
        'ppm': PPM * SHEET_K,
        'room_scale': ROOM_K, 'room_cell': CELL * ROOM_K, 'room_baseline': BASE_Y * ROOM_K,
        'room_h_1m6': int(H_ADULT * ROOM_K),
        'cols': MAXF,
        'clips': [c for c, _ in CLIPS],
        'frames': {c: n for c, n in CLIPS},
        'rows': {c: i for i, (c, _) in enumerate(CLIPS)},
        'anim_seconds': CLIP_SEC,
        'sheet': 'static/art/chars/front/p2/<role>.png  (x4, 셀 256, 발 기준선 240)',
        'source': 'static/art/chars/front/p2/src/<role>.png  (x1, 셀 64, 발 기준선 60)',
        'tint_mask': 'static/art/chars/front/p2/masks/<role>.png  (x1, L8)',
        'imprint_layer': 'static/art/chars/front/p2/imprints/<id>.png (어른 8역할 공용, x1) · imprints/kid/<id>.png (아이 전용). 같은 셀·같은 자리에 알파 합성. 기본은 전부 꺼짐',
        'octopus': 'static/art/chars/front/p2/octopus.png  (x4, 4칸: idle f0~2 + wrap)',
        'roles': meta_roles,
        'imprints': [{'id': i, 'ko': k, 'part': p, 'color': c} for i, k, p, c in IMPRINTS],
        'rules_2_5d': {
            '1_integer_scale': '정수 배율 + NEAREST(image-rendering: pixelated). 소수 배율 금지',
            '2_lamp_tint': 'masks/<role>.png 가 흰 곳만 방 등불색을 곱한다. 0인 곳(눈·외곽선·랜턴 불꽃·유리)은 건드리지 않는다. 권장식: rgb *= (1 + 0.30*(tint-1)) * (1.13 - 0.32*(y/h))',
            '3_contact_shadow': '발 기준선에 폭 = 스프라이트 70%, 높이 = 7.5%의 흐린 타원 (알파 165)',
            '4_palette': '배경 렌더 16색에서 명도가 가까운 색으로 20% 당기고, 방 평균색 기준 대비를 1.26배 재확장 (이 파일 harmonize()에 구현)',
            '5_depth': '방 깊이 1.7m — 벽 가까이 세우고 앞뒤로 겹치는 소품을 두지 않는다',
        },
    }
    with io.open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(meta, ensure_ascii=False, indent=1))
    print('[ok] meta.json / check/*.png')


if __name__ == '__main__':
    main()
