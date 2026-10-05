# -*- coding: utf-8 -*-
"""
gen_chars_visitors.py — 꾸밈 손님(작은 짐승) 여덟 (스프린트 19-C)

data/draft/visitors.json 의 손님 여덟을 P2 도트 세계 그대로 그린다. **생성 AI 없음** — gen_chars_p2 의 원시함수로 좌표를 찍는다.
사용자 피드백(신인류 시제품 「괴기스럽다」)을 규칙으로: 따뜻하고 둥근 실루엣, 점 눈 + 작은 웃음 + 홍조, 부드러운 색.
차가운 발광·큰 반사 눈 금지. 빛은 등불고기 턱 밑 작은 「불씨」(따뜻한 등불색)뿐이다.
  · 방 안 손님(담요게·소라게 장수·나사집게): 원화 배율(P2 src, 셀 64 = 사람 44px) 기준으로 그려 방 ×3 에 사람 옆에 선다. 앵커 = 발(바닥) 가운데
  · 창밖 손님(등불고기 한 쌍·책장새우·꼬마 장어·아기 해파리 떼·유리닦이 불가사리): 방 유리 바깥에 보이는 크기. 앵커 = 가운데
출력: static/art/visitors/<id>.png (x1) · <id>_x3.png · visitors_meta.json · docs/reports/char_S19_visitors.png
실행: PYTHONIOENCODING=utf-8 python tools/gen_chars_visitors.py
"""
import os, sys, io, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_chars_p2 as G
from PIL import Image, ImageDraw

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'static', 'art', 'visitors')
REP = os.path.join(ROOT, 'docs', 'reports')
Cv = G.Cv
TAU = math.pi * 2

VPAL = {
    'vCrab': (228, 124, 98), 'vCrabD': (178, 84, 66), 'vCrabL': (246, 170, 136),
    'vFish': (238, 172, 100), 'vFishD': (196, 122, 64), 'vFishL': (250, 210, 146),
    'vCap': (198, 70, 56), 'vCapD': (142, 44, 36), 'vCapL': (232, 116, 94),
    'vShr': (246, 196, 180), 'vShrD': (212, 150, 140), 'vShrL': (252, 228, 214),
    'vEel': (212, 164, 112), 'vEelD': (160, 112, 72), 'vEelL': (238, 204, 152),
    'vJel': (226, 196, 234), 'vJelD': (186, 152, 206), 'vJelL': (248, 232, 250), 'vJelP': (246, 196, 210), 'vJelPD': (214, 150, 172),
    'vStar': (238, 140, 74), 'vStarD': (192, 98, 48), 'vStarL': (252, 188, 124),
    'vMus': (216, 172, 84), 'vMusD': (162, 122, 50), 'vMusL': (240, 208, 132),
    'vMetal': (176, 172, 160), 'vMetalD': (116, 112, 104),
    'vMoss': (126, 150, 96), 'vClear': (196, 226, 222),
}


def eye_dot(c, x, y, sleepy=False):
    if sleepy:                                             # 자는 눈 — 아래로 둥근 한 획
        c.set(x - 1, y, 'ink'); c.set(x, y + 1, 'ink'); c.set(x + 1, y, 'ink')
    else:
        c.set(x, y, 'ink')


def smile(c, x, y):
    c.set(x - 1, y, 'ink'); c.set(x, y + 1, 'ink'); c.set(x + 1, y, 'ink')


def crab_body(c, cx, by, M, D, L, w=6.5, h=4.2, sleepy=False, legs_ph=0):
    """둥근 등딱지 게. by = 발이 닿는 줄."""
    for k, dx in enumerate((-5, -3, 3, 5)):                # 다리
        lift = 1 if (k + legs_ph) % 2 == 0 and legs_ph >= 0 else 0
        c.rect(cx + dx, by - 2 - lift, cx + dx, by - lift, D)
    c.ell(cx, by - 4, w, h, M)
    c.ell_in(cx - 1.5, by - 5.4, w - 2.5, h - 2.2, L, only=(M,))
    c.rect(cx - int(w) + 1, by - 2, cx + int(w) - 1, by - 2, D) if False else None
    for sx in (-2, 2):                                     # 눈자루 + 점 눈
        c.rect(cx + sx, by - 9, cx + sx, by - 8, D)
        c.ell(cx + sx, by - 10, 1.2, 1.2, 'cream')
        eye_dot(c, cx + sx, by - 10, sleepy)
    smile(c, cx, by - 4)
    c.set(cx - 4, by - 4, 'blush'); c.set(cx + 4, by - 4, 'blush')


def quilt_pile(c, x0, y0, x1, y1):
    G.quilt(c, x0, y0, x1, y1)


# ── 손님 여덟 ───────────────────────────────────────────────────────────
def blanket_crab(clip, f):
    c = Cv(28, 20)
    by = 18
    if clip == 'idle':                                     # 담요에 반쯤 파묻혀 잔다 — 숨 쉴 때 등딱지가 1px 오르내린다
        quilt_pile(c, 2, 13, 25, 18)
        crab_body(c, 14, by - [0, 1][f], 'vCrab', 'vCrabD', 'vCrabL', sleepy=True, legs_ph=-1)
        quilt_pile(c, 3, 15, 24, 18)
        c.set(3 + 4 * (f % 2), 14, 'cream')
        z = [(20, 4), (22, 2)][f]                          # z
        c.rect(z[0], z[1], z[0] + 2, z[1], 'creamD'); c.set(z[0] + 1, z[1] + 1, 'creamD'); c.rect(z[0], z[1] + 2, z[0] + 2, z[1] + 2, 'creamD')
        c.set(17, 6, 'cream')                              # 등딱지의 실밥 한 가닥
        c.set(18, 5, 'cream')
    else:                                                  # tuck_in — 담요를 끌어 덮고 눈만 빼꼼
        cover = [16, 13, 10, 9][f]
        quilt_pile(c, 2, 14, 25, 18)
        crab_body(c, 14, by, 'vCrab', 'vCrabD', 'vCrabL', sleepy=(f == 3), legs_ph=-1)
        quilt_pile(c, 3 + f, cover, 24 - f, 18)
        if f >= 2:
            c.rect(6, cover - 1, 21, cover - 1, 'cream')
        if f == 3:
            c.set(21, 4, 'creamD'); c.set(23, 2, 'creamD')
    c.outline('line')
    return c


def lantern_fish_pair(clip, f):
    c = Cv(36, 24)
    def fish(cx, cy, face, lit):
        s = 1 if face > 0 else -1
        c.ell(cx, cy, 4.2, 3.2, 'vFish')
        c.ell_in(cx - s * 1, cy - 1.2, 2.6, 1.6, 'vFishL', only=('vFish',))
        c.rect(cx - s * 5, cy - 2, cx - s * 4, cy + 2, 'vFishD')        # 꼬리
        c.set(cx - s * 6, cy - 2, 'vFishD'); c.set(cx - s * 6, cy + 2, 'vFishD')
        eye_dot(c, cx + s * 2, cy - 1)
        c.set(cx + s * 3, cy + 1, 'ink')                  # 작은 입
        c.set(cx + s * 1, cy + 1, 'blush')
        c.set(cx + s * 2, cy + 4, 'brassD')               # 턱 밑 불씨 줄기
        c.set(cx + s * 2, cy + 5, 'flame' if lit else 'flameR')
        if lit:
            c.set(cx + s * 3, cy + 5, 'flameR')
    if clip == 'idle':                                     # 같은 박자로 깜빡인다
        b = [0, 1, 0, -1][f]
        fish(10, 11 + b, 1, f % 2 == 0)
        fish(25, 12 - b, -1, f % 2 == 0)
    else:                                                  # circle — 서로를 돈다
        a = TAU * f / 4.0
        for k in (0, 1):
            ang = a + k * math.pi
            fish(int(round(18 + 7 * math.cos(ang))), int(round(12 + 3.5 * math.sin(ang))),
                 -1 if math.sin(ang) > 0 else 1, True)
    c.outline('line')
    return c


def hermit_trader(clip, f):
    c = Cv(36, 22)
    by = 20
    cx = 12 if clip == 'idle' else 10
    if clip == 'show_stall' and f >= 1:                    # 작은 천을 깔고 물건 셋을 늘어놓는다
        c.rect(16, by - 1, 33, by, 'creamD'); c.rect(16, by - 1, 33, by - 1, 'cream')
        for k, (t, h) in enumerate((('brass', 2), ('glass', 3), ('ox', 2))):
            if f >= 2 + (k > 0):
                x = 19 + k * 5
                c.rect(x, by - 1 - h, x + 2, by - 2, t)
    # 다리 · 몸
    for dx in (-3, -1, 2):
        c.rect(cx + dx, by - 2, cx + dx, by, 'vCrabD')
    c.ell(cx + 1, by - 4, 3.6, 2.8, 'vCrab')
    # 병뚜껑 집 — 톱니 테
    c.ell(cx - 2, by - 8, 5.6, 4.6, 'vCap')
    c.ell_in(cx - 3.4, by - 9.6, 3.4, 2.4, 'vCapL', only=('vCap',))
    for k in range(-5, 6, 2):
        c.set(cx - 2 + k, by - 4, 'vCapD')
    c.rect(cx - 7, by - 8, cx - 7, by - 6, 'vCapD')
    # 눈자루 · 얼굴
    for sx in (2, 4):
        c.rect(cx + sx, by - 8, cx + sx, by - 7, 'vCrabD')
        c.ell(cx + sx, by - 9, 1.1, 1.1, 'cream')
        eye_dot(c, cx + sx, by - 9)
    smile(c, cx + 3, by - 4)
    c.set(cx + 5, by - 4, 'blush')
    # 집게 — 무언가(단추) 하나
    wave = [0, -1, 0, -2][f] if clip == 'show_stall' else [0, -1][f]
    c.ell(cx + 6, by - 4 + wave, 1.6, 1.4, 'vCrabL')
    c.ell(cx + 8, by - 5 + wave, 1.2, 1.2, 'brassM'); c.set(cx + 8, by - 5 + wave, 'brassH')
    c.outline('line')
    return c


def page_shrimp(clip, f):
    c = Cv(48, 16)
    def shrimp(x, y, ph):
        c.ell(x, y, 3.4, 2.0, 'vShr')
        c.ell_in(x - .6, y - .8, 2.0, 1.0, 'vShrL', only=('vShr',))
        for k in (-1, 1):
            c.set(x + k, y - 1, 'vShrD'); c.set(x + k, y, 'vShrD')            # 가는 줄무늬
        c.rect(x - 5, y - 1, x - 4, y + 1, 'vShrD')                           # 꼬리 부채
        c.set(x + 3, y - 3 - ph, 'vShrD'); c.set(x + 4, y - 4 - ph, 'vShrD')   # 더듬이
        c.set(x + 3, y - 2, 'vShrD')
        eye_dot(c, x + 2, y - 1)
        c.set(x + 1, y + 1, 'blush')
        c.set(x - 1, y + 2, 'vShrD'); c.set(x + 1, y + 2, 'vShrD')
    off = 0 if clip == 'idle' else [0, 1, 2, 3][f]
    for k in range(4):                                      # 한 줄로 선다(왼쪽 → 오른쪽)
        shrimp(6 + k * 10 + off, 8 + (1 if (k + f) % 2 else 0), (k + f) % 2)
    c.outline('line')
    return c


def steam_eel(clip, f):
    c = Cv(36, 16)
    nose = 30 if clip == 'nose_press' else 28
    push = [0, 1, 2][f] if clip == 'nose_press' else 0
    pts = [(nose + push - k, 8 + int(round(1.6 * math.sin((k + f * 2) * .55)))) for k in range(0, 24)]
    for k, (x, y) in enumerate(pts):                       # 손가락 굵기 몸 — 머리에서 꼬리로 가늘어진다
        r = 2 if k < 16 else 1
        c.rect(x, y - r + 1, x, y + r - 1 + (1 if k < 10 else 0), 'vEel')
        c.set(x, y - r + 1, 'vEelD')
        if k < 14:
            c.set(x, y + r - (0 if k < 10 else 1), 'vEelL')
    hx, hy = pts[0]
    c.ell(hx - 1, hy, 2.6, 2.2, 'vEel')
    c.ell_in(hx - 1, hy + 1, 1.8, 1, 'vEelL', only=('vEel',))
    eye_dot(c, hx - 1, hy - 1)
    c.set(hx + 1, hy + 1, 'ink')
    c.set(hx - 2, hy + 1, 'blush')
    c.outline('line')
    if clip == 'nose_press' and f == 2:                   # 김 서린 유리에 남은 동그란 코 자국
        G.ring(c, hx + 2.5, hy + .5, 2.2, 1.0, 'cream')
    return c


def baby_jelly_drift(clip, f):
    c = Cv(40, 26)
    spots = [(7, 9, 'vJel'), (17, 15, 'vJelP'), (26, 8, 'vJel'), (33, 16, 'vJelP'), (13, 21, 'vJel')]
    for k, (x, y, t) in enumerate(spots):
        if clip == 'idle':
            y += [0, -1, 0][(f + k) % 3]
        else:                                              # bump — 둘이 부딪치면 잠깐 밝아진다(따뜻한 빛)
            if k in (1, 2):
                x += [0, 2, 3][f] * (1 if k == 1 else -1)
                y += [0, -2, -3][f] * (1 if k == 1 else -.5)
        x, y = int(round(x)), int(round(y))
        D, L = t + 'D', ('vJelL' if t == 'vJel' else 'vShrL')
        lit = clip == 'bump' and f == 2 and k in (1, 2)
        c.ell(x, y, 3.2, 2.6, L if lit else t)
        c.rect(x - 3, y + 1, x + 3, y + 1, D)
        c.ell_in(x - 1, y - 1, 1.4, .9, 'white' if lit else L, only=(t, L))
        for dx in (-2, 0, 2):                              # 짧은 다리
            c.set(x + dx, y + 2 + ((dx + f) % 2), D)
        eye_dot(c, x - 1, y); eye_dot(c, x + 1, y)
        c.set(x, y + 1 if False else y, t if not lit else L) if False else None
        if lit:
            c.set(x - 4, y - 2, 'flame'); c.set(x + 4, y - 3, 'flame')
    c.outline('line')
    return c


def glass_star(clip, f):
    c = Cv(28, 28)
    cx, cy = 14, 14
    rot = 0 if clip == 'idle' else f * 18
    if clip == 'wipe':                                     # 이끼 낀 유리 위로 맑은 동그라미가 늘어난다
        for (x, y) in [(xx, yy) for yy in range(0, 28) for xx in range(0, 28)]:
            if (x * 7 + y * 13) % 11 == 0 and math.hypot(x - cx, y - cy) > 6 + f * 1.5:
                c.set(x, y, 'vMoss')
        G.ring(c, cx, cy, 7 + f * 1.5, 1.0, 'vClear')
    pts = []
    for k in range(10):
        a = math.radians(rot + k * 36 - 90)
        rr = 9.5 if k % 2 == 0 else 4.2
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    ys = [p[1] for p in pts]
    for y in range(int(min(ys)), int(max(ys)) + 1):        # 별 모양 채우기
        xs = []
        for i in range(10):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 10]
            if (y0 <= y + .5 < y1) or (y1 <= y + .5 < y0):
                xs.append(x0 + (y + .5 - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for x in range(int(round(xs[k])), int(round(xs[k + 1]))):
                c.set(x, y, 'vStar')
    c.ell_in(cx - 1.5, cy - 1.5, 4, 3, 'vStarL', only=('vStar',))
    for k in range(5):                                     # 팔마다 점 무늬
        a = math.radians(rot + k * 72 - 90)
        c.set(cx + 6 * math.cos(a), cy + 6 * math.sin(a), 'vStarD')
    bob = [0, 1][f % 2] if clip == 'idle' else 0
    eye_dot(c, cx - 2, cy - 1 + bob); eye_dot(c, cx + 2, cy - 1 + bob)
    smile(c, cx, cy + 1 + bob)
    c.set(cx - 3, cy + 1 + bob, 'blush'); c.set(cx + 3, cy + 1 + bob, 'blush')
    c.outline('line')
    return c


def screw_crab(clip, f):
    c = Cv(30, 18)
    by = 16
    cx = 12 + ([0, 1, 2, 3][f] if clip == 'carry' else 0)
    crab_body(c, cx, by, 'vMus', 'vMusD', 'vMusL', w=5.4, h=3.6, legs_ph=(f if clip == 'carry' else -1))
    big = (cx + 8, by - 6 + ([0, -1][f % 2] if clip == 'idle' else 0))      # 유난히 큰 집게
    c.ell(big[0], big[1], 3.2, 2.6, 'vMus')
    c.ell_in(big[0] - 1, big[1] - 1, 1.8, 1.2, 'vMusL', only=('vMus',))
    c.rect(big[0] + 1, big[1] - 1, big[0] + 3, big[1] - 1, 'vMusD')
    c.set(cx - 6, by - 5, 'vMusD'); c.set(cx - 7, by - 6, 'vMusD')          # 작은 집게
    holding = not (clip == 'carry' and f == 3)
    if holding:                                            # 나사 하나
        c.rect(big[0] + 3, big[1] - 4, big[0] + 3, big[1] - 1, 'vMetal')
        c.rect(big[0] + 2, big[1] - 5, big[0] + 4, big[1] - 5, 'vMetalD')
    else:                                                  # 바닥에 두고 간 나사
        c.rect(cx - 9, by - 1, cx - 6, by - 1, 'vMetal'); c.set(cx - 10, by - 1, 'vMetalD')
    c.outline('line')
    return c


VISITORS = [
    # id, 그림 함수, 어디, (idle 프레임, fps), (특기 클립, 프레임, fps), 방(대비 그림용)
    ('blanket_crab', blanket_crab, 'inside', (2, 1.5), ('tuck_in', 4, 3), 'quarters'),
    ('lantern_fish_pair', lantern_fish_pair, 'window', (4, 4), ('circle', 4, 5), 'greenhouse'),
    ('hermit_trader', hermit_trader, 'inside', (2, 2), ('show_stall', 4, 3), 'storage'),
    ('page_shrimp', page_shrimp, 'window', (2, 3), ('march', 4, 4), 'quarters'),
    ('steam_eel', steam_eel, 'window', (2, 3), ('nose_press', 3, 3), 'infirmary'),
    ('baby_jelly_drift', baby_jelly_drift, 'window', (3, 3), ('bump', 3, 4), 'greenhouse'),
    ('glass_star', glass_star, 'window', (2, 2), ('wipe', 4, 2), 'power'),
    ('screw_crab', screw_crab, 'inside', (2, 2), ('carry', 4, 4), 'workshop'),
]


def frames_of(fn, idle_n, sig, sig_n):
    rows = [('idle', [fn('idle', f) for f in range(idle_n)]), (sig, [fn(sig, f) for f in range(sig_n)])]
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    G.PAL.update(VPAL)
    G.harmonize()
    for k, v in VPAL.items():
        G.PAL[k] = v
    f12, f14, f16 = G.font(12), G.font(14), G.font(18)
    data = json.load(io.open(os.path.join(ROOT, 'data', 'draft', 'visitors.json'), encoding='utf-8'))
    KO = {v['id']: v['ko'] for v in data['visitors']}
    LOOK = {v['id']: v['look'] for v in data['visitors']}
    meta = {'_comment': '꾸밈 손님 여덟(S19-C). 손으로 찍은 도트(생성 AI 없음), P2 원화 배율. 정수 배율 + image-rendering:pixelated',
            'scale_rule': '원화(x1) 셀은 P2 사람 셀(64, 맨머리 44px)과 같은 배율이다. 방 화면 ×3 이면 손님도 ×3 으로 그린다(_x3.png 가 그 판).',
            'anchor_rule': 'inside = 발(바닥 줄) 가운데 [x, y] — 방 바닥 floor_y 에 이 점을 맞춘다. window = 몸 가운데 — 방 유리 바깥 자리에 맞춘다.',
            'visitors': []}
    sheets = {}
    for vid, fn, where, (idle_n, idle_fps), (sig, sig_n, sig_fps), room in VISITORS:
        rows = frames_of(fn, idle_n, sig, sig_n)
        w, h = rows[0][1][0].w, rows[0][1][0].h
        cols = max(len(fr) for _, fr in rows)
        sh = Image.new('RGBA', (w * cols, h * len(rows)), (0, 0, 0, 0))
        for r_, (_c, frs) in enumerate(rows):
            for i, cv in enumerate(frs):
                sh.paste(cv.img(), (w * i, h * r_))
        sh.save(os.path.join(OUT, vid + '.png'))
        G.up(sh, 3).save(os.path.join(OUT, vid + '_x3.png'))
        sheets[vid] = (sh, w, h)
        if where == 'inside':
            anchor = [w // 2, h - 1]
        else:
            anchor = [w // 2, h // 2]
        meta['visitors'].append({
            'id': vid, 'ko': KO.get(vid, vid), 'file': 'static/art/visitors/%s.png' % vid,
            'file_x3': 'static/art/visitors/%s_x3.png' % vid, 'where': where,
            'indoor': where == 'inside', 'size': [w, h], 'cols': cols,
            'clips': {'idle': {'row': 0, 'frames': idle_n, 'fps': idle_fps},
                      sig: {'row': 1, 'frames': sig_n, 'fps': sig_fps}},
            'anchor': anchor, 'look': LOOK.get(vid, '')})
    with io.open(os.path.join(OUT, 'visitors_meta.json'), 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(meta, ensure_ascii=False, indent=1))

    # ── 접촉 시트: 방마다 주민 둘 + 손님(방 ×3, 플레이트 floor_y 그대로) ──
    pm = json.load(io.open(os.path.join(ROOT, 'static', 'art', 'plates', 'plates_meta.json'), encoding='utf-8'))
    flY, kk = pm['floor_y'], pm['grid']['char_scale']
    cast = [('scout', 'a', 'braid', 'f0'), ('cook', 'b', 'short', 'f1'), ('medic', 'b', 'long', 'f2'),
            ('engineer', 'a', 'tied', 'f0'), ('farmer', 'a', 'curly', 'f1'), ('kid', 'b', 'short', 'f0'),
            ('trader', 'a', 'scarf', 'f2'), ('scholar', 'b', 'short', 'f0')]
    panels = []
    for i, (vid, fn, where, (idle_n, _f), (sig, sig_n, _sf), room) in enumerate(VISITORS):
        pl = Image.open(os.path.join(ROOT, 'static', 'art', 'plates', 'room_plate_%s_lit.png' % room)).convert('RGBA')
        d = ImageDraw.Draw(pl)
        if where == 'window':                              # 방 유리 — 둥근 창, 바깥은 어두운 물
            wx, wy, wr = 470, 120, 70
            d.ellipse([wx - wr - 6, wy - wr - 6, wx + wr + 6, wy + wr + 6], fill=(110, 82, 40))
            d.ellipse([wx - wr, wy - wr, wx + wr, wy + wr], fill=(18, 44, 56))
            d.ellipse([wx - wr + 10, wy - wr + 8, wx - wr + 30, wy - wr + 22], fill=(40, 74, 84))
        for k, xc in enumerate((170, 300)):                # 주민 둘
            role, body, hair, face = cast[(i * 2 + k) % len(cast)]
            one = G.room_light(G.up(G.build(role, 'idle', k % 2, body, hair, face)[0].img(), kk))
            bb = one.getbbox()
            pl = G.ground_shadow(pl, (xc - 96 + bb[0], flY - G.BASE_Y * kk + bb[1]), one.crop(bb))
            pl.alpha_composite(one, (xc - 96, flY - G.BASE_Y * kk))
        sh, w, h = sheets[vid]
        cell_idle = sh.crop((0, 0, w, h))
        cell_sig = sh.crop((w * (sig_n - 1), h, w * sig_n, 2 * h))
        if where == 'inside':
            for j, (cell, xc) in enumerate(((cell_idle, 410), (cell_sig, 540))):
                z = G.room_light(G.up(cell, kk))
                bb = z.getbbox()
                pl = G.ground_shadow(pl, (xc - z.width // 2 + bb[0], flY - h * kk + bb[1]), z.crop(bb), .9)
                pl.alpha_composite(z, (xc - z.width // 2, flY - h * kk + kk))
        else:
            z = G.up(cell_idle, kk)
            pl.alpha_composite(z, (470 - z.width // 2, 120 - z.height // 2))
            z2 = G.up(cell_sig, 2)
            pl.alpha_composite(z2, (560 - z2.width // 2, 250 - z2.height // 2)) if False else None
        d = ImageDraw.Draw(pl)
        d.rectangle([0, 0, pl.width, 26], fill=(16, 11, 9, 230))
        d.text((8, 5), '%s (%s) — %s · ×%d' % (KO.get(vid, vid), vid, '방 안' if where == 'inside' else '창밖', kk),
               font=f14, fill=(244, 216, 160))
        # 아래 띠: 프레임 전부(×3)
        strip_h = h * 3 + 30
        panel = Image.new('RGBA', (pl.width, pl.height + strip_h), (22, 16, 12, 255))
        panel.alpha_composite(pl, (0, 0))
        dp = ImageDraw.Draw(panel)
        x = 8
        for r_, (cname, nfr) in enumerate((('idle', idle_n), (sig, sig_n))):
            dp.text((x, pl.height + 4), cname, font=f12, fill=(220, 196, 150))
            for fi in range(nfr):
                cell = sh.crop((w * fi, h * r_, w * (fi + 1), h * (r_ + 1)))
                bgc = Image.new('RGBA', (w * 3, h * 3), (18, 44, 56, 255) if where == 'window' else (60, 44, 32, 255))
                bgc.alpha_composite(G.up(cell, 3))
                if x + w * 3 > panel.width:
                    break
                panel.alpha_composite(bgc, (x, pl.height + 22))
                x += w * 3 + 4
            x += 14
        panels.append(panel)
    pw, ph_ = panels[0].width, max(p.height for p in panels)
    sheet = Image.new('RGB', (pw * 2 + 30, 60 + 4 * (ph_ + 12)), (14, 10, 8))
    d = ImageDraw.Draw(sheet)
    d.text((12, 10), '꾸밈 손님 여덟 (S19-C) — 방 ×3 · 주민 둘 옆. 손으로 찍은 도트, 생성 AI 없음. 따뜻하고 둥글게, 점 눈 + 웃음 + 홍조',
           font=f16, fill=(244, 222, 170))
    d.text((12, 34), '방 안 손님은 왼쪽 = idle, 오른쪽 = 특기 마지막 칸. 창밖 손님은 둥근 창 안. 아래 띠 = 프레임 전부(×3)',
           font=f12, fill=(200, 176, 140))
    for i, p in enumerate(panels):
        sheet.paste(p.convert('RGB'), (10 + (i % 2) * (pw + 10), 60 + (i // 2) * (ph_ + 12)))
    sheet.save(os.path.join(REP, 'char_S19_visitors.png'))
    print('[ok] visitors →', OUT, '· sheet →', os.path.join(REP, 'char_S19_visitors.png'))


if __name__ == '__main__':
    main()
