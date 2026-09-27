# -*- coding: utf-8 -*-
"""
단면 렌더 후처리 (S6-B)
  python tools/post_section.py compare   전·후 비교 한 장 (같은 카메라)
  python tools/post_section.py serve     art_raw/deep/*.png → static/art/deep/
  python tools/post_section.py all

비교 컷 규칙: 같은 구도·같은 해상도만 나란히 놓는다. 한쪽만 예쁜 각도로 찍으면
그것은 비교가 아니라 광고다.
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "art_raw", "deep")
DST = os.path.join(ROOT, "static", "art", "deep")

PAIRS = [
    ("_before_room_zoom.png", "section_room_zoom.png", "BEFORE  S4-A", "AFTER  S6-B  cozy"),
]
SERVE = ["section_warm.png", "section_room_zoom.png", "section_before_after.png"]


def compare():
    rows = []
    for b, a, lb, la in PAIRS:
        pb, pa = os.path.join(RAW, b), os.path.join(RAW, a)
        if not (os.path.exists(pb) and os.path.exists(pa)):
            print("skip (없음):", b, a)
            continue
        rows.append((Image.open(pb).convert("RGB"), Image.open(pa).convert("RGB"), lb, la))
    if not rows:
        raise SystemExit("비교할 렌더가 없다. blender_section.py -- before / roomzoom 을 먼저 돌린다.")
    gap, bar = 10, 30
    w = rows[0][0].size[0]
    h = rows[0][0].size[1]
    out = Image.new("RGB", (w * 2 + gap, (h + bar) * len(rows)), (18, 15, 12))
    d = ImageDraw.Draw(out)
    for i, (imb, ima, lb, la) in enumerate(rows):
        y = i * (h + bar)
        d.text((6, y + 9), lb, fill=(196, 172, 132))
        d.text((w + gap + 6, y + 9), la, fill=(240, 208, 150))
        out.paste(imb, (0, y + bar))
        out.paste(ima, (w + gap, y + bar))
    p = os.path.join(RAW, "section_before_after.png")
    out.save(p)
    print("COMPARE", p, out.size)


def serve(colors=None):
    """B8 성능 예산 메모 — **256색 양자화는 시험했고 버렸다.**
    1,062KB → 134KB 로 8배 줄지만, 디더가 **가장 어두운 물**에서 청록·갈색을 섞어
    초록 잡티를 만든다. 그 어둠이 이 게임의 안팎 대비 그 자체라 바꿀 수 없다.
    (`serve(colors=256)` 으로 언제든 재현 가능. 판단만 달라지면 인자 하나다)"""
    os.makedirs(DST, exist_ok=True)
    for n in SERVE:
        s = os.path.join(RAW, n)
        if not os.path.exists(s):
            print("skip (없음):", n)
            continue
        im = Image.open(s).convert("RGB")
        if colors:
            im = im.quantize(colors=colors, method=Image.MAXCOVERAGE,
                             dither=Image.FLOYDSTEINBERG)
        d = os.path.join(DST, n)
        im.save(d, optimize=True)
        print("serve %-28s %6.1f KB  (raw %6.1f KB)"
              % (n, os.path.getsize(d) / 1024, os.path.getsize(s) / 1024))


def measure(names=None):
    """검수 수치. ①바깥 물이 여전히 어두운가 ②방 안이 따뜻해졌는가 ③청록이 방에 샜는가.
    판정 기준: 어두운 화소(휘도<0.115)는 D2 의 '빈 물', 난색 화소는 방 안이다."""
    for n in (names or ["section_hero.png", "section_warm.png",
                        "_before_room_zoom.png", "section_room_zoom.png"]):
        p = os.path.join(RAW, n)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        px = list(im.getdata())
        tot = len(px)
        dark = warm = cool_in = 0
        wsum = 0.0
        for r, g, b in px:
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            if lum < 0.115:
                dark += 1
                continue
            if r > b + 12:                    # 난색(방 안)
                warm += 1
                wsum += lum
            elif b > r + 12:                  # 한색
                if lum > 0.30:                # 밝은 한색 = 물이 아니라 방에 샌 청록
                    cool_in += 1
        print("%-28s dark %5.1f%%  warm %5.1f%%  warm_lum %.3f  cool_leak %5.2f%%"
              % (n, 100.0 * dark / tot, 100.0 * warm / tot,
                 (wsum / warm) if warm else 0.0, 100.0 * cool_in / tot))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "measure":
        measure(sys.argv[2:] or None)
        raise SystemExit(0)
    if mode in ("compare", "all"):
        compare()
    if mode in ("serve", "all"):
        serve()
