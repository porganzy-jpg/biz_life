# -*- coding: utf-8 -*-
"""
gen_chars_indoor_proto.py — 실내복 시제품 하나: 요리사 · 체형 A (사용자 요청 2026-10-17)

"밖에서는 잠수복을 입는다는 건 알지만, 들어오면 옷이 바뀌어야 하지 않나?"
지금 P2 주민은 늘 투구 테와 두건을 쓰고 있어 집 안에서도 잠수부처럼 보인다.
→ 투구·두건·공기통·무게추 장화를 벗은 요리사. 머리카락과 얼굴이 다 보이고, 편한 일옷(크림 셔츠 + 번트오렌지 앞치마 + 갈색 바지 + 실내화).
  역할 판독축은 그대로 둔다: 머리 위 = 키 큰 천 모자(요리사 서명), 몸 = 앞치마(역할 색), 손 = 국자.
규약은 P2 그대로: 셀 64 · 발 기준선 60 · 맨머리 44px(머리카락 꼭대기) · 정수 배율 · 손으로 찍은 도트(생성 AI 없음).
행 셋: idle(2) · walk_side(3, 오른쪽 원본) · work(3, 국자를 든다). 기존 시트는 건드리지 않는다.
출력: static/art/chars/indoor_proto/cook_a.png(x1) · cook_a_x4.png · docs/reports/char_indoor_proto.png(비교)
"""
import os, sys, io, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_chars_p2 as G
from PIL import Image, ImageDraw

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'static', 'art', 'chars', 'indoor_proto')
REP = os.path.join(ROOT, 'docs', 'reports')
Cv, FOOT, CELL = G.Cv, G.FOOT, G.CELL

IPAL = {
    'iShirt': (240, 226, 196), 'iShirtD': (206, 186, 150), 'iShirtL': (252, 244, 224),
    'iTr': (104, 76, 58), 'iTrD': (74, 52, 40), 'iTrL': (136, 102, 78),
    'iShoe': (150, 86, 60), 'iShoeD': (104, 56, 40),
    'iHair': (92, 56, 36), 'iHairD': (62, 36, 24), 'iHairL': (128, 82, 52),
    'iCap': (250, 244, 230), 'iCapD': (214, 204, 184),
}
CLIPS = [('idle', 2, 2.8), ('walk_side', 3, 0.8), ('work', 3, 1.4)]
ROLE = 'cook'


def face_front(c, hx, ey):
    """P2 얼굴 ① 과 같은 자리·같은 모양(둥근 눈 · 곧은 눈썹 · 넓은 미소 · 홍조)."""
    exl, exr = int(round(hx - 4.5)), int(round(hx + 1.5))
    G.brow(c, exl, ey - 3, 3, 'l'); G.brow(c, exr, ey - 3, 3, 'r')
    G.eye(c, exl, ey, 3, 3); G.eye(c, exr, ey, 3, 3)
    c.set(hx, ey + 3, 'skinD')
    G.smile(c, hx, ey + 4, 2)
    G.blush(c, int(hx - 6), int(hx - 5), ey + 2); G.blush(c, int(hx + 5), int(hx + 6), ey + 2)


def toque(c, hx, top, side=False):
    """요리사 서명 — 키 큰 천 모자. 맨머리 위에 얹는다(머리카락 꼭대기 = 맨머리 44px 기준선은 그대로)."""
    w = 6.0 if not side else 5.4
    cx_ = hx + (-.6 if side else 0)
    c.ell(cx_, top - 3.2, w + .6, 4.6, 'iCap')               # 부푼 윗부분
    c.ell_in(cx_ + 2.0, top - 2.4, w - 2.0, 3.2, 'iCapD', only=('iCap',))
    c.ell_in(cx_ - 2.0, top - 4.6, 2.4, 1.6, 'white', only=('iCap', 'iCapD'))
    c.rect(cx_ - w + 1, top, cx_ + w - 1, top + 2, 'r_cook')  # 머리띠 — 역할 색(번트오렌지)으로 지금 모자와 이어진다
    c.rect(cx_ - w + 1, top, cx_ + w - 1, top, 'rL_cook')
    c.rect(cx_ - w + 1, top + 2, cx_ + w - 1, top + 2, 'rD_cook')
    G.wave(c, cx_ - w + 2, cx_ + w - 2, top - 1.2, 'iCapD', 2)


def head_front(c, hx, hy, head_top):
    # 뒷머리 → 얼굴 → 앞머리 → 모자
    c.ell(hx, hy + .3, 8.4, 8.8, 'iHair')                # 머리카락 꼭대기 = 원화 y 16(맨머리 44px)
    c.ell_in(hx + 2, hy + 2, 6.4, 6.0, 'iHairD', only=('iHair',))
    c.rect(hx - 8, hy + 2, hx - 7, hy + 7, 'iHair'); c.rect(hx + 7, hy + 2, hx + 8, hy + 6, 'iHairD')   # 귀 옆 머리
    c.ell(hx, hy + 1.6, 6.8, 6.9, 'skin')
    c.ell_in(hx + 1.6, hy + 3.2, 5.6, 5.4, 'skinD', only=('skin',))
    c.ell_in(hx - .4, hy + 1.2, 6.0, 6.2, 'skin', only=('skinD',))
    c.set(hx - 7, hy + 3, 'skin'); c.set(hx + 7, hy + 3, 'skinD')                  # 귀
    for dx, dy in ((-5, -3.8), (-2, -4.6), (1, -4.4), (4, -3.6), (5.6, -2.4), (-6.2, -2.2)):   # 앞머리 술
        c.ell(hx + dx, hy + dy, 1.8, 1.6, 'iHair')
    c.ell_in(hx - 3, hy - 4.6, 2.2, 1.0, 'iHairL', only=('iHair',))
    toque(c, hx, int(round(head_top)) + 2)


def head_side(c, hx, hy, head_top):
    c.ell(hx - 1.4, hy + .5, 8.0, 8.2, 'iHair')
    c.ell_in(hx - 3, hy + 2, 5.0, 5.6, 'iHairD', only=('iHair',))
    c.ell(hx + 1.4, hy + 1.8, 6.4, 6.8, 'skin')
    c.ell_in(hx + 2.6, hy + 3.4, 5.0, 5.0, 'skinD', only=('skin',))
    c.ell_in(hx + 1.0, hy + 1.4, 5.4, 6.0, 'skin', only=('skinD',))
    for dx, dy in ((-3, -4.2), (0, -4.8), (3, -4.2), (5.4, -3.0)):
        c.ell(hx + dx, hy + dy, 1.8, 1.6, 'iHair')
    c.rect(hx - 4, hy - 1, hx - 2, hy + 5, 'iHair')                                # 귀밑머리
    c.ell(hx - 1.2, hy + 2.4, 1.3, 1.7, 'skin'); c.set(hx - 1, hy + 2, 'skinD')    # 귀
    ey = G.ey_of(hy + 1.5)
    ex = int(round(hx + 4))
    c.rect(ex, ey, ex + 1, ey + 2, 'ink'); c.set(ex + 1, ey, 'white')              # 큰 눈 하나
    c.set(ex, ey - 3, 'ink'); c.set(ex + 1, ey - 3, 'ink')                          # 눈썹
    nx = int(round(hx + 8))
    c.set(nx, ey + 2, 'skin'); c.set(nx, ey + 3, 'skinD')                          # 코
    c.set(nx - 2, ey + 5, 'ink'); c.set(nx - 1, ey + 5, 'ink'); c.set(nx - 3, ey + 4, 'ink')   # 입
    c.set(ex - 1, ey + 3, 'blush'); c.set(ex - 2, ey + 3, 'blush')
    toque(c, hx, int(round(head_top)) + 2, side=True)


def front(clip, f):
    c = Cv()
    rM, rD, rL = 'r_cook', 'rD_cook', 'rL_cook'
    bob = {'idle': [0, 1], 'work': [0, -1, 0]}[clip][f]
    head_top = FOOT - 43 + bob
    hy = head_top + 8.5
    hx = 32 + (1 if clip == 'work' else 0)
    cx = 32
    neck_y = head_top + 17
    trx, try_ = 8.6, 7.2                                  # 어깨 폭은 지금 몸과 같다(잠수복을 벗어도 사람 크기는 같다)
    tcy = neck_y + 9
    belt = int(round(tcy + try_ * .45))
    leg_y0 = int(round(tcy + try_ - 1))
    # 다리 · 실내화
    for sx in (cx - 6, cx + 2):
        c.rect(sx, leg_y0, sx + 4, FOOT - 3, 'iTr'); c.rect(sx, leg_y0, sx + 1, FOOT - 3, 'iTrL')
        c.rect(sx - 1, FOOT - 2, sx + 5, FOOT, 'iShoe'); c.rect(sx - 1, FOOT, sx + 5, FOOT, 'iShoeD')
        c.set(sx, FOOT - 2, 'iShirt')                                             # 실내화 털 테
    # 몸 — 크림 셔츠
    c.ell(cx, tcy, trx, try_, 'iShirt')
    c.ell_in(cx - 2, tcy - 2.2, trx - 2, try_ - 1.2, 'iShirtL', only=('iShirt',))
    c.ell_in(cx, tcy + try_ - 1, trx, 3.0, 'iShirtD', only=('iShirt', 'iShirtL'))
    # 앞치마 — 역할 색(번트오렌지). 가슴받이 + 허리 아래로 넓게, 주머니
    c.rect(cx - 4, neck_y + 3, cx + 4, belt, rM); c.rect(cx - 4, neck_y + 3, cx + 4, neck_y + 3, rL)
    c.rect(cx - 7, belt, cx + 7, leg_y0 + 5, rM)
    c.rect(cx - 7, belt, cx - 6, leg_y0 + 5, rL)
    c.rect(cx + 5, belt, cx + 7, leg_y0 + 5, rD)
    c.rect(cx - 7, leg_y0 + 5, cx + 7, leg_y0 + 5, rD)
    c.rect(cx - 3, belt + 3, cx + 2, belt + 5, rD); c.rect(cx - 3, belt + 3, cx + 2, belt + 3, rL)   # 주머니
    c.set(cx - 5, neck_y + 2, rD); c.set(cx + 5, neck_y + 2, rD)                  # 목끈
    c.rect(cx - trx + 1, belt, cx + trx - 1, belt, rD)                            # 허리끈
    c.set(cx + 8, belt + 1, rD); c.set(cx + 9, belt + 2, rD)                      # 뒤로 맨 매듭 끝
    c.rect(cx - 1, belt - 7, cx + 1, belt - 7, 'iShirtL')                         # 앞치마에 묻은 밀가루
    # 팔 — 걷은 소매(크림) + 맨팔뚝
    sw = 0
    lift = [0, -4, -2][f] if clip == 'work' else 0
    ax_l, ax_r = int(cx - trx - 2), int(cx + trx - 1)
    arm_y0, arm_y1 = neck_y + 1, belt + 2
    mid = belt - 3
    c.rect(ax_l, arm_y0 + 1, ax_l + 3, mid, 'iShirt'); c.rect(ax_l, arm_y0 + 1, ax_l + 1, mid, 'iShirtL')
    c.rect(ax_l, mid, ax_l + 3, mid, 'iShirtD')
    c.rect(ax_l + 1, mid + 1, ax_l + 3, arm_y1 + 1, 'skin')
    c.rect(ax_r, arm_y0 + 1, ax_r + 3, mid + lift, 'iShirtD')
    c.rect(ax_r, mid + lift, ax_r + 3, mid + lift, 'iShirtD')
    c.rect(ax_r, mid + lift + 1, ax_r + 2, arm_y1 + 1 + lift, 'skinD')
    wl, wr = (ax_l + 2, arm_y1 + 2), (ax_r + 1, arm_y1 + 2 + lift)
    c.ell(wl[0], wl[1], 1.6, 1.6, 'skin'); c.ell(wr[0], wr[1], 1.6, 1.6, 'skinD')
    G.hand_prop(c, ROLE, wr[0], wr[1])                                            # 국자
    if clip == 'work' and f == 1:                                                 # 김 한 줄(일하는 티)
        c.set(wr[0] + 4, wr[1] - 9, 'iCap'); c.set(wr[0] + 5, wr[1] - 11, 'iCapD')
    # 목
    c.rect(hx - 2, neck_y - 2, hx + 2, neck_y + 1, 'skinD'); c.rect(hx - 2, neck_y - 2, hx - 1, neck_y + 1, 'skin')
    head_front(c, hx, hy, head_top)
    face_front(c, hx, G.ey_of(hy + 1.5))
    c.outline('line')
    return c


def side(f):
    c = Cv()
    rM, rD, rL = 'r_cook', 'rD_cook', 'rL_cook'
    bob = [0, -1, 0][f]
    head_top = FOOT - 43 + bob
    hy = head_top + 8.5
    cx = 31
    hx = cx + 1
    neck_y = head_top + 17
    trx, try_ = 5.6, 7.2
    tcy = neck_y + 9
    belt = int(round(tcy + try_ * .45))
    leg_y0 = int(round(tcy + try_ - 1))
    st = 4
    near_dx, far_dx = [st, 0, -st][f], [-st, -1, st][f]
    far_lift = [0, 2, 0][f]
    near_deg, far_deg = [2, 12, 26][f], [20, 6, -10][f]
    SF, SN = (cx - .5, neck_y + 3.0), (cx + .5, neck_y + 3.0)
    R = 12.0
    a = math.radians(far_deg)                                                     # 먼 팔
    hf = (int(round(SF[0] + R * .9 * math.sin(a))), int(round(SF[1] + R * .9 * math.cos(a))))
    G.seg(c, SF, ((SF[0] + hf[0]) / 2, (SF[1] + hf[1]) / 2), 'iShirtD', 3)
    G.seg(c, ((SF[0] + hf[0]) / 2, (SF[1] + hf[1]) / 2), hf, 'skinD', 2)
    for dx, lift, far in ((far_dx, far_lift, True), (near_dx, 0, False)):         # 다리
        hip = (cx - (1 if far else 0), leg_y0)
        ank = (cx + dx, FOOT - 3 - lift)
        G.seg(c, hip, ank, 'iTrD' if far else 'iTr', 4)
        fx = int(round(cx + dx))
        c.rect(fx - 2, FOOT - 2 - lift, fx + 3, FOOT - lift, 'iShoeD' if far else 'iShoe')
    c.ell(cx, tcy, trx, try_, 'iShirt')                                           # 몸
    c.ell_in(cx - 1.5, tcy - 2.2, trx - 1.5, try_ - 1.2, 'iShirtL', only=('iShirt',))
    c.ell_in(cx, tcy + try_ - 1, trx, 3.0, 'iShirtD', only=('iShirt', 'iShirtL'))
    # 앞치마 — 옆에서는 몸 앞판 + 허리 아래로 넓게 퍼지고 끈이 뒤로 매어진다
    for y in range(neck_y + 3, leg_y0 + 6):
        xr = int(cx + trx - (0 if y > belt else 1))
        x0 = int(cx + 1) if y <= belt else int(cx - 4)
        c.rect(x0, y, xr + (1 if y > belt else 0), y, rM)
    c.rect(int(cx + 1), neck_y + 3, int(cx + trx - 1), neck_y + 3, rL)
    c.rect(int(cx - 4), leg_y0 + 5, int(cx + trx + 1), leg_y0 + 5, rD)
    c.rect(int(cx - trx), belt, int(cx + trx), belt, rD)
    c.rect(int(cx - trx - 2), belt - 1, int(cx - trx - 1), belt + 1, rD)          # 등 뒤 매듭
    c.set(int(cx - trx - 2), belt + 2, rD)
    c.rect(int(cx + 2), belt + 3, int(cx + 4), belt + 4, rD)                      # 주머니
    c.rect(hx - 1, neck_y - 2, hx + 2, neck_y + 1, 'skinD')                        # 목
    head_side(c, hx, hy, head_top)
    a = math.radians(near_deg)                                                    # 가까운 팔 + 국자
    hn = (int(round(SN[0] + R * .9 * math.sin(a))), int(round(SN[1] + R * .9 * math.cos(a))))
    el = ((SN[0] + hn[0]) / 2.0, (SN[1] + hn[1]) / 2.0)
    G.seg(c, SN, el, 'iShirt', 3)
    G.seg(c, el, hn, 'skin', 2)
    c.ell(hn[0], hn[1], 1.5, 1.5, 'skin')
    G.hand_prop(c, ROLE, hn[0], hn[1])
    c.outline('line')
    return c


def build(clip, f):
    return side(f) if clip == 'walk_side' else front(clip, f)


def main():
    os.makedirs(OUT, exist_ok=True)
    G.PAL.update(IPAL)
    G.harmonize()
    for k, v in IPAL.items():
        G.PAL[k] = v
    f12, f14, f16 = G.font(12), G.font(14), G.font(18)
    # 시트(행 셋)
    sh = Image.new('RGBA', (CELL * 3, CELL * len(CLIPS)), (0, 0, 0, 0))
    cells = {}
    for r, (clip, n, _s) in enumerate(CLIPS):
        for i in range(n):
            im = build(clip, i).img()
            cells[(clip, i)] = im
            sh.paste(im, (CELL * i, CELL * r))
    sh.save(os.path.join(OUT, 'cook_a.png'))
    G.up(sh, 4).save(os.path.join(OUT, 'cook_a_x4.png'))
    # 키 확인: 맨머리 꼭대기 = 원화 y 16 (44px) — 머리카락 맨 윗줄
    c0 = build('idle', 0)
    hair_top = min(y for (x, y) in c0.pixels() if c0.own(x, y) in ('iHair', 'iHairD', 'iHairL'))
    skin_rows = set(y for (x, y) in c0.pixels() if c0.own(x, y) in ('ink',))
    meta = {'_comment': '실내복 시제품 — 요리사 · 체형 A. 손으로 찍은 도트(생성 AI 없음). 기존 P2 시트와 같은 셀·기준선',
            'cell': CELL, 'baseline': G.BASE_Y, 'cols': 3,
            'rows': {c: i for i, (c, n, s) in enumerate(CLIPS)}, 'frames': {c: n for c, n, s in CLIPS},
            'anim_seconds': {c: s for c, n, s in CLIPS}, 'facing': {'walk_side': 'right(원본) · 왼쪽 = 반전'},
            'hair_top_y': hair_top}
    with io.open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(meta, ensure_ascii=False, indent=1))

    # ── 비교 그림 ──
    P2 = os.path.join(ROOT, 'static', 'art', 'chars', 'front', 'p2')
    pm = json.load(open(os.path.join(P2, 'meta.json'), encoding='utf-8'))
    rows = {c: i for i, c in enumerate(pm['clips'])}
    cur = Image.open(os.path.join(P2, 'src', 'cook.png')).convert('RGBA')
    suit = Image.open(os.path.join(P2, 'suit', 'cook_a.png')).convert('RGBA')
    suited = cur.copy(); suited.alpha_composite(suit)
    work_row = {'idle': 'idle', 'walk_side': 'walk_side', 'work': 'work'}
    K = 4
    colw = CELL * K
    CW = 3 * (48 * 3 + 4) + 30                            # 한 갈래 폭(세 칸)
    W = 170 + 3 * CW
    H = 70 + len(CLIPS) * (CELL * K // 1 + 20) + 470
    im = Image.new('RGB', (W, H), (40, 30, 24))
    d = ImageDraw.Draw(im)
    heads = ['지금 (집 안에서도 투구 테·두건)', '시제품 실내복', '원정 (잠수복 겹)']
    for j, hd in enumerate(heads):
        d.text((170 + j * CW, 10), hd, font=f16, fill=(244, 222, 170))
    for r, (clip, n, _s) in enumerate(CLIPS):
        y0 = 44 + r * (colw + 20)
        d.text((10, y0 + colw // 2 - 10), clip, font=f14, fill=(220, 196, 150))
        for j in range(3):
            x0 = 170 + j * CW
            for i in range(n):
                if j == 1:
                    cell = cells[(clip, i)]
                else:
                    src = cur if j == 0 else suited
                    rr = rows[work_row[clip]]
                    cell = src.crop((CELL * i, CELL * rr, CELL * (i + 1), CELL * (rr + 1)))
                z = G.up(cell.crop((8, 6, 56, 62)), K * 3 // 4 if False else 3)
                bg = Image.new('RGBA', (z.width, z.height), (60, 46, 34, 255) if (i + j) % 2 else (68, 52, 38, 255))
                bg.alpha_composite(z)
                im.paste(bg.convert('RGB'), (x0 + i * (z.width + 4), y0))
    # 방 안 합성(거주실, 방 ×3) — 다른 주민 둘 사이
    pmeta = json.load(open(os.path.join(ROOT, 'static', 'art', 'plates', 'plates_meta.json'), encoding='utf-8'))
    flY, kk = pmeta['floor_y'], pmeta['grid']['char_scale']
    pl = Image.open(os.path.join(ROOT, 'static', 'art', 'plates', 'room_plate_pantry_lit.png' if os.path.exists(
        os.path.join(ROOT, 'static', 'art', 'plates', 'room_plate_pantry_lit.png')) else 'room_plate_quarters_lit.png')).convert('RGBA')
    for who, xc in ((('scout', 'a', 'idle', 0), 150), ('indoor', 290), (('farmer', 'b', 'idle', 1), 430), ('cur', 540)):
        if who == 'indoor':
            one = G.room_light(G.up(cells[('idle', 0)], kk))
        elif who == 'cur':
            one = G.room_light(G.up(cur.crop((0, 0, CELL, CELL)), kk))
        else:
            one = G.room_light(G.up(G.build(who[0], who[2], who[3], who[1])[0].img(), kk))
        bb = one.getbbox()
        pl = G.ground_shadow(pl, (xc - 96 + bb[0], flY - G.BASE_Y * kk + bb[1]), one.crop(bb))
        pl.alpha_composite(one, (xc - 96, flY - G.BASE_Y * kk))
    dd = ImageDraw.Draw(pl)
    dd.rectangle([0, 0, pl.width, 26], fill=(16, 11, 9, 230))
    dd.text((8, 5), '방 ×3 — 정찰병 · [실내복 요리사] · 농부 · 지금 요리사(맨 오른쪽)', font=f14, fill=(244, 216, 160))
    ry = 44 + len(CLIPS) * (colw + 20)
    im.paste(pl.convert('RGB'), (170, ry))
    # 70px
    sc70 = 70.0 / 49.0
    x7 = 170 + pl.width + 30
    d.text((x7, ry), '70px — 모자로 역할이 읽히는가', font=f14, fill=(244, 222, 170))
    for j, cell in enumerate((cur.crop((0, 0, CELL, CELL)), cells[('idle', 0)], suited.crop((0, 0, CELL, CELL)))):
        for k_, sil in enumerate((False, True)):
            one = cell.copy()
            if sil:
                px = one.load()
                for yy in range(one.height):
                    for xx in range(one.width):
                        if px[xx, yy][3]:
                            px[xx, yy] = (14, 10, 8, 255)
            z = one.resize((int(CELL * sc70), int(CELL * sc70)), Image.NEAREST)
            bg = Image.new('RGBA', z.size, (150, 120, 88, 255)); bg.alpha_composite(z)
            im.paste(bg.convert('RGB'), (x7 + j * 100, ry + 30 + k_ * 100))
    im = im.crop((0, 0, max(W, x7 + 320), ry + max(pl.height, 240) + 10))
    im.save(os.path.join(REP, 'char_indoor_proto.png'))
    print('[ok] indoor proto · hair_top', hair_top)


if __name__ == '__main__':
    main()
