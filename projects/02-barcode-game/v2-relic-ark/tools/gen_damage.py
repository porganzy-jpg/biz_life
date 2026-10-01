# -*- coding: utf-8 -*-
"""
창의 피해 단계와 물 찬 방 — 방 플레이트 위에 얹는 투명 PNG (S8-C ④)

  python tools/gen_damage.py

왜 Blender 가 아니라 PIL 인가: 금은 **선**이다. 두께 1~2px 의 흔들리는 선 수십 개를
3D 로 만들 이유가 없고, 플레이트와 같은 672×378 격자에 정확히 찍어야 하므로
2D 로 그리는 쪽이 정확하고 1초 만에 다시 뽑을 수 있다(소품 34종과 같은 판단 — gen_props.py).

설계 규칙 셋
  D-1 **금은 차갑다.** 방 안에서 유일하게 청록이 허락되는 것이 피해다(B2 의 "청록은 바다에만"을
      어기지 않는다 — 금 너머는 바다다). 금이 보이면 바다가 들어오고 있다는 뜻이다.
  D-2 **세 단계는 누적이다.** 1 의 선은 2 에도 있고, 2 의 선은 3 에도 있다.
      플레이어가 "같은 자리가 더 심해졌다"로 읽어야 한다(COMBAT §3-6 흔적).
  D-3 **물 찬 방은 조용하다.** 등불이 죽고, 난색이 전부 한색으로 덮이고, 소품이 뜬다.
      이것이 이 게임의 죽음이고, 되돌릴 수 없는 대신 화면에 남는다.

좌표는 plates_meta.json 의 캔버스/inner_rect 를 그대로 읽는다. 플레이트 규격이 바뀌면
여기도 저절로 따라간다.
"""
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "art_raw", "plates")

# 바다 색 — PAL 의 물 전용 색과 같은 값(blender_section.PAL)
SEA_TOP = (0x2E, 0x7E, 0x90)
SEA_MID = (0x0B, 0x25, 0x30)
SEA_LOW = (0x04, 0x10, 0x16)
GLINT = (0x9C, 0xC6, 0xD2)        # 금에 비치는 물빛
DARK = (0x02, 0x0B, 0x12)


def meta():
    with open(os.path.join(RAW, "plates_meta.json"), encoding="utf-8") as f:
        return json.load(f)


def jitter_line(d, p0, p1, col, w, seed, amp=2.4, segs=7):
    """흔들리는 선 하나. 자로 그은 선은 금이 아니라 금속이다(F6 과 같은 이유)."""
    rnd = random.Random(seed)
    pts = []
    for k in range(segs + 1):
        t = k / segs
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t
        if 0 < k < segs:
            x += rnd.uniform(-amp, amp)
            y += rnd.uniform(-amp, amp)
        pts.append((x, y))
    d.line(pts, fill=col, width=w, joint="curve")
    return pts


def radial(d, origin, ang, length, w, seed, col, kinks=2):
    """유리의 금은 **곧게 간다.** 나뭇가지처럼 휘면 번개나 나무로 읽힌다(1차 시안이 그랬다).
    마디에서 각도만 조금 꺾고, 그 사이는 직선이다."""
    rnd = random.Random(seed)
    pts = [origin]
    a, p = ang, origin
    for k in range(kinks + 1):
        seg = length / (kinks + 1) * rnd.uniform(0.75, 1.25)
        a += rnd.uniform(-0.17, 0.17)
        p = (p[0] + math.cos(a) * seg, p[1] + math.sin(a) * seg)
        pts.append(p)
    d.line(pts, fill=col, width=w)
    if w > 1:                                        # 굵은 금은 가는 짝을 하나 달고 간다
        d.line([(x + 1.5, y + 1.5) for x, y in pts], fill=col[:3] + (col[3] // 3,), width=1)
    return pts


def web_ring(d, origin, angs, rads, w, col, seed):
    """금과 금을 잇는 고리. 거미줄 모양이 '유리'를 결정한다."""
    rnd = random.Random(seed)
    pts = []
    for a, r in zip(angs, rads):
        rr = r * rnd.uniform(0.86, 1.14)
        pts.append((origin[0] + math.cos(a) * rr, origin[1] + math.sin(a) * rr))
    for p0, p1 in zip(pts, pts[1:]):
        d.line([p0, p1], fill=col, width=w)


def chips(d, cx, cy, n, r, seed, col):
    """금이 만나는 자리에서 떨어져 나간 작은 조각."""
    rnd = random.Random(seed)
    for i in range(n):
        a = rnd.uniform(0, 6.2832)
        rr = r * rnd.uniform(0.3, 1.0)
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        s = rnd.uniform(2.5, 6.0)
        poly = []
        for k in range(rnd.randint(3, 5)):
            aa = 6.2832 * k / 4 + rnd.uniform(-0.4, 0.4)
            poly.append((x + math.cos(aa) * s * rnd.uniform(0.6, 1.3),
                         y + math.sin(aa) * s * rnd.uniform(0.6, 1.3)))
        d.polygon(poly, fill=col)


def clip_inner(im, M, pad=2):
    """**유리는 방 앞에만 있다.** 금이 방 밖 물로 뻗으면 그건 금이 아니라 그냥 선이다.
    1차 시안이 캔버스 밖까지 뻗어 나갔다 — 그래서 안쪽 사각형으로 잘라 둔다."""
    x0, y0, x1, y1 = M["inner_rect"]
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rectangle([x0 + pad, y0 + pad, x1 - pad, y1 - pad], fill=255)
    a = im.getchannel("A")
    im.putalpha(Image.composite(a, Image.new("L", im.size, 0), mask))
    return im


def hole_poly(cx, cy, r, seed, n=11):
    rnd = random.Random(seed)
    return [(cx + math.cos(6.2832 * k / n) * r * rnd.uniform(0.62, 1.40) * 1.1,
             cy + math.sin(6.2832 * k / n) * r * rnd.uniform(0.62, 1.40))
            for k in range(n)]


def make_crack(stage, M):
    w, h = M["canvas"]
    x0, y0, x1, y1 = M["inner_rect"]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # 충격점 — 방 **안쪽** 오른쪽 벽 가까이. 생물은 옆에서 온다(threats_meta.approach = right)
    cx, cy = x1 - 62, (y0 + y1) // 2 - 10
    n, (lmin, lmax), wmax, col = {
        1: (5, (38, 62), 1, GLINT + (122,)),
        2: (9, (74, 132), 2, GLINT + (170,)),
        3: (14, (130, 236), 2, GLINT + (208,)),
    }[stage]
    rnd = random.Random(900 + stage)

    if stage >= 2:                                   # 충격점 둘레의 찬 기운
        bloom = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(bloom).ellipse([cx - 110, cy - 110, cx + 110, cy + 110],
                                      fill=SEA_TOP + (30 if stage == 2 else 56,))
        im.alpha_composite(bloom.filter(ImageFilter.GaussianBlur(36)))

    # D-2 누적: 각도 수열이 황금비라 1 의 금이 2·3 에도 그 자리에 그대로 있다
    angs, rads = [], []
    for i in range(n):
        a = 6.2832 * ((i * 0.618) % 1.0) + 0.21
        ln = rnd.uniform(lmin, lmax)
        radial(d, (cx, cy), a, ln, wmax, 1000 + i * 31, col, kinks=2)
        angs.append(a)
        rads.append(ln)
    order = sorted(range(n), key=lambda i: angs[i])
    if stage >= 2:
        web_ring(d, (cx, cy), [angs[i] for i in order] + [angs[order[0]] + 6.2832],
                 [rads[i] * 0.42 for i in order] + [rads[order[0]] * 0.42], 1,
                 col[:3] + (col[3] * 2 // 3,), 5)
    if stage == 3:
        web_ring(d, (cx, cy), [angs[i] for i in order] + [angs[order[0]] + 6.2832],
                 [rads[i] * 0.74 for i in order] + [rads[order[0]] * 0.74], 1,
                 col[:3] + (col[3] // 2,), 9)
    chips(d, cx, cy, {1: 2, 2: 7, 3: 15}[stage], {1: 14, 2: 30, 3: 54}[stage],
          77 + stage, GLINT + (150,))

    if stage == 3:                                   # 깨짐 — 뚫린 자리로 바다가 보인다
        hole = hole_poly(cx, cy, 26, 7)
        d.polygon(hole, fill=SEA_LOW + (252,))
        d.line(hole + [hole[0]], fill=GLINT + (200,), width=2)

    soft = im.filter(ImageFilter.GaussianBlur(0.6))   # 정정 ②: 매끈한 벡터 선 금지
    return clip_inner(Image.blend(im, soft, 0.45), M)


def make_flood(M):
    """물 찬 방. 등불이 죽고 난색이 전부 한색으로 덮인다."""
    w, h = M["canvas"]
    x0, y0, x1, y1 = M["inner_rect"]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rnd = random.Random(31)
    surf = y0 + int((y1 - y0) * 0.34)                # 수면 — 방의 2/3 가 잠겼다

    # 1) 잠긴 부분 — 아래로 갈수록 검어진다
    for y in range(surf, y1 + 1):
        t = (y - surf) / max(1, y1 - surf)
        c = tuple(int(a + (b - a) * t) for a, b in zip(SEA_MID, SEA_LOW))
        d.line([(x0, y), (x1, y)], fill=c + (232,))
    # 2) 수면 — 한 줄의 밝은 물빛. 화면에서 가장 차가운 선
    pts = [(x, surf + math.sin(x * 0.055) * 2.4 + math.sin(x * 0.017) * 1.6)
           for x in range(x0, x1 + 1, 4)]
    d.line(pts, fill=SEA_TOP + (150,), width=3, joint="curve")
    d.line([(p[0], p[1] + 5) for p in pts], fill=SEA_TOP + (60,), width=2, joint="curve")
    # 3) 공기 방울 — 아직 빠져나가는 중이다
    for _ in range(46):
        bx = rnd.uniform(x0 + 6, x1 - 6)
        by = rnd.uniform(surf + 8, y1 - 4)
        r = rnd.uniform(1.2, 3.6)
        d.ellipse([bx - r, by - r, bx + r, by + r], outline=SEA_TOP + (110,))
    # 4) 떠다니는 살림 — 담요·널빤지·통. 사람이 살던 자리라는 증거
    for i in range(6):
        fx = rnd.uniform(x0 + 40, x1 - 90)
        fy = surf + rnd.uniform(-9, 4)
        fw, fh = rnd.uniform(26, 58), rnd.uniform(7, 13)
        d.rectangle([fx, fy, fx + fw, fy + fh], fill=(0x17, 0x1E, 0x22, 225))
        d.line([(fx, fy), (fx + fw, fy)], fill=SEA_TOP + (90,), width=1)
    # 5) 깨진 자리 — 물이 들어온 구멍. crack3 와 **같은 좌표**여야 이야기가 이어진다
    cx, cy = x1 - 62, (y0 + y1) // 2 - 10
    hole = hole_poly(cx, cy, 28, 7)
    d.polygon(hole, fill=SEA_LOW + (255,))
    d.line(hole + [hole[0]], fill=GLINT + (110,), width=1)

    im = im.filter(ImageFilter.GaussianBlur(0.5))
    # 6) 방 전체를 식힌다 — **등불이 죽었다.** 물 위쪽도 난색이 남으면 안 된다.
    #    위(공기)보다 아래(물)가 더 식는 것이 아니라, 방 전체가 바다 색이 된다.
    chill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(chill).rectangle([x0, y0, x1, y1], fill=SEA_MID + (198,))
    # 등불을 끈다. 잃은 방에는 불이 없다 — 소리도 없다(COMBAT 3-6).
    lx, ly = M["rooms"][0]["lamp"]
    douse = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(douse).ellipse([lx - 110, ly - 70, lx + 110, ly + 120],
                                  fill=DARK + (170,))
    chill.alpha_composite(douse.filter(ImageFilter.GaussianBlur(26)))
    out = Image.alpha_composite(chill, im)
    return clip_inner(out, M, pad=0)


def main():
    M = meta()
    made = []
    for st in (1, 2, 3):
        p = os.path.join(RAW, "damage_crack%d.png" % st)
        make_crack(st, M).save(p)
        made.append(p)
    p = os.path.join(RAW, "room_flood.png")
    make_flood(M).save(p)
    made.append(p)
    for p in made:
        print("  %-26s %6.1f KB" % (os.path.basename(p), os.path.getsize(p) / 1024))

    # 검수용 합성 — 실제 플레이트 위에 네 장을 차례로 얹는다
    base = os.path.join(RAW, M["rooms"][0]["files"]["lit"])
    if os.path.exists(base):
        bg = Image.open(base).convert("RGBA")
        w, h = bg.size
        names = ["damage_crack1.png", "damage_crack2.png", "damage_crack3.png", "room_flood.png"]
        labels = ["1 실금", "2 금", "3 깨짐", "물 찬 방"]
        sheet = Image.new("RGB", (w, (h + 16) * len(names)), (10, 9, 8))
        sd = ImageDraw.Draw(sheet)
        for i, (n, lb) in enumerate(zip(names, labels)):
            cur = bg.copy()
            cur.alpha_composite(Image.open(os.path.join(RAW, n)).convert("RGBA"))
            sd.text((4, i * (h + 16) + 3), lb, fill=(214, 186, 142))
            sheet.paste(cur.convert("RGB"), (0, i * (h + 16) + 16))
        sp = os.path.join(RAW, "damage_sheet.png")
        sheet.save(sp)
        print("DAMAGE SHEET", sp, sheet.size)


if __name__ == "__main__":
    main()
