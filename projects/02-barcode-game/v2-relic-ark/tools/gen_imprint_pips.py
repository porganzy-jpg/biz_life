# -*- coding: utf-8 -*-
"""
gen_imprint_pips.py — 각인 머리 위 표식(pip) 12종 (S22 2차, 손으로 찍은 도트 · 생성 AI 없음)

화면 배율이 작을 때(방 ×3 보다 멀리, z < 1) 몸 위 각인 픽셀은 1~3 화면 픽셀이 되어 읽히지 않는다.
그때는 머리 위에 이 표식을 **화면 픽셀 기준**(배율 무관, ×2 고정 권장)으로 1~3개 띄운다.
각 표식 = 9×9: 어두운 테 + 그 각인 색 + 부위를 가리키는 작은 모양(얼굴 점·팔 띠·목걸이·물방울…).
가까이(z ≥ 1)에서는 몸 위 각인 레이어가 보이므로 표식을 끈다.
출력: static/art/chars/front/p2/imprints/pips.png(12칸 가로, x1) · pips_x2.png · pips.json
"""
import os, sys, json, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_chars_p2 as G
from PIL import Image

OUT = os.path.join(G.ROOT, 'static', 'art', 'chars', 'front', 'p2', 'imprints')
N = 9
RIM, BG = (34, 24, 18), (250, 238, 214)

# id → (바탕색, 모양색, 모양) — 색은 각인 레이어의 그 각인 색을 한 단 밝힌 것
PIPS = {
    'spore_mark':    ((150, 196, 104), (60, 96, 40), 'dots'),       # 목덜미 녹색 반점
    'empty_stomach': ((206, 168, 80), (92, 84, 44), 'knot'),        # 허리 매듭
    'warden':        ((214, 110, 92), (255, 236, 220), 'scar'),     # 광대 흉터
    'sun_memory':    ((244, 236, 214), (196, 160, 90), 'veil'),     # 베일
    'empty_seat':    ((96, 84, 80), (230, 222, 210), 'band'),       # 팔띠
    'footprint':     ((236, 230, 214), (120, 96, 70), 'tooth'),     # 이빨 목걸이
    'debt_paid':     ((236, 196, 92), (120, 84, 30), 'ring'),       # 손목 팔찌
    'water_memory':  ((126, 196, 214), (255, 255, 255), 'drop'),    # 젖은 머리
    'saved_breath':  ((222, 146, 84), (255, 230, 200), 'ring'),     # 구릿빛 고리
    'crack_seen':    ((150, 214, 220), (40, 90, 104), 'crack'),     # 유리빛 금
    'depth_mark':    ((166, 122, 166), (250, 230, 250), 'dots'),    # 자줏빛 자국
    'knock_heard':   ((226, 188, 96), (255, 255, 255), 'wave'),     # 울림쇠
}
SHAPES = {   # 9×9 안 가운데 5×5 에 찍는 모양(# = 모양색)
    'dots':  ['.....', '.#.#.', '.....', '..#..', '.....'],
    'knot':  ['.....', '#...#', '.###.', '#...#', '.....'],
    'scar':  ['#....', '.#...', '..#..', '...#.', '....#'],
    'veil':  ['.###.', '#...#', '#...#', '#...#', '#.#.#'],
    'band':  ['.....', '#####', '.....', '#####', '.....'],
    'tooth': ['#...#', '.#.#.', '..#..', '..#..', '.....'],
    'ring':  ['.###.', '#...#', '#...#', '#...#', '.###.'],
    'drop':  ['..#..', '.###.', '#####', '#####', '.###.'],
    'crack': ['..#..', '..#..', '.#...', '..##.', '...#.'],
    'wave':  ['.....', '#.#.#', '.#.#.', '.....', '.....'],
}


def pip(bg, fg, shape):
    im = Image.new('RGBA', (N, N), (0, 0, 0, 0))
    px = im.load()
    for y in range(N):
        for x in range(N):
            d = ((x - 4) ** 2 + (y - 4) ** 2) ** .5
            if d <= 4.3:
                px[x, y] = RIM + (255,)
            if d <= 3.4:
                px[x, y] = bg + (255,)
    for j, row in enumerate(SHAPES[shape]):
        for i, ch in enumerate(row):
            if ch == '#':
                px[2 + i, 2 + j] = fg + (255,)
    px[3, 2] = (255, 255, 255, 255) if px[3, 2][:3] == bg else px[3, 2]   # 작은 반짝임
    return im


def main():
    ids = list(PIPS)
    sheet = Image.new('RGBA', (N * len(ids), N), (0, 0, 0, 0))
    for k, iid in enumerate(ids):
        bg, fg, sh = PIPS[iid]
        sheet.paste(pip(bg, fg, sh), (N * k, 0))
    sheet.save(os.path.join(OUT, 'pips.png'))
    G.up(sheet, 2).save(os.path.join(OUT, 'pips_x2.png'))
    meta = {'_comment': '각인 머리 위 표식(S22 2차). 손으로 찍은 도트. 화면 배율이 방 ×3 보다 작을 때(z < 1)만 쓴다',
            'cell': N, 'order': ids,
            'rule': '사람 머리 위(맨머리 꼭대기에서 화면 4px 위)에 가진 각인 1~3개를 가로로 1px 띄워 늘어놓는다. '
                    '화면 픽셀 기준 ×2(18px) 고정 — 카메라 배율을 곱하지 않는다. z ≥ 1 에서는 끈다(몸 위 각인 레이어가 보인다). '
                    '방 불빛 틴트를 곱하지 않는다. 뒷모습·잠수복이어도 표식은 같다.'}
    with io.open(os.path.join(OUT, 'pips.json'), 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(meta, ensure_ascii=False, indent=1))
    print('[ok] pips', len(ids))


if __name__ == '__main__':
    main()
