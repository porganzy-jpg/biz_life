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
SERVE = ["section_warm.png", "section_room_zoom.png", "section_before_after.png",
         # S8-C: 사람 없는 판(캐릭터 담당 합성 판정용)
         "section_warm_noppl.png", "section_room_zoom_noppl.png"]


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


# ══════════════════════════════════════════════════════════════
# S8-C 후처리 — 플레이트 / 생물 실루엣
#   투명 PNG 는 그대로 보면 판정이 안 된다. **물 위에 얹어서** 본다.
# ══════════════════════════════════════════════════════════════
RAW_PLATE = os.path.join(ROOT, "art_raw", "plates")
RAW_THREAT = os.path.join(ROOT, "art_raw", "threats")
DST_PLATE = os.path.join(ROOT, "static", "art", "plates")
DST_THREAT = os.path.join(ROOT, "static", "art", "threats")

# 돔이 사는 깊이의 물 — ZONE_STOPS 에서 그 구간만 뽑은 값
WATER_TOP, WATER_BOT = (0x12, 0x44, 0x55), (0x04, 0x10, 0x16)


def water_bg(w, h, top=WATER_TOP, bot=WATER_BOT):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)))
    return im


def _label(d, x, y, s, col=(214, 186, 142)):
    d.text((x, y), s, fill=col)


def threats_sheet():
    """생물 넷 × 두 단계. 같은 물 위에 같은 크기로 — 서로 구분되는지 보는 유일한 방법."""
    import json
    meta = json.load(open(os.path.join(RAW_THREAT, "threats_meta.json"), encoding="utf-8"))
    w, h = meta["canvas"]
    sw, sh = w // 2, h // 2                      # 접촉 인화는 절반 크기
    bar, gap = 22, 8
    cols, rows = 2, len(meta["threats"])
    out = Image.new("RGB", (cols * sw + gap, rows * (sh + bar)), (10, 9, 8))
    d = ImageDraw.Draw(out)
    for r, t in enumerate(meta["threats"]):
        y = r * (sh + bar)
        _label(d, 4, y + 6, "%s (%s)  — %s" % (t["name"], t["id"], t["counter"]))
        for c, stage in enumerate(("far", "near")):
            p = os.path.join(RAW_THREAT, t["files"][stage])
            fg = Image.open(p).convert("RGBA").resize((sw, sh), Image.LANCZOS)
            bg = water_bg(sw, sh).convert("RGBA")
            bg.alpha_composite(fg)
            out.paste(bg.convert("RGB"), (c * (sw + gap), y + bar))
    p = os.path.join(RAW_THREAT, "threats_sheet.png")
    out.save(p)
    print("THREAT SHEET", p, out.size)


def plates_sheet():
    """방 여섯 × 두 상태. 같은 크기로 늘어놓고 ①사람이 없는가 ②바닥선이 맞는가를 본다.
    바닥선·설 수 있는 x 범위를 **메타 값 그대로** 그려 넣는다 — 눈이 아니라 숫자를 검사한다."""
    import json
    meta = json.load(open(os.path.join(RAW_PLATE, "plates_meta.json"), encoding="utf-8"))
    w, h = meta["canvas"]
    sw, sh = w // 2, h // 2
    bar, gap = 20, 6
    out = Image.new("RGB", (2 * sw + gap, len(meta["rooms"]) * (sh + bar)), (10, 9, 8))
    d = ImageDraw.Draw(out)
    for r, rm in enumerate(meta["rooms"]):
        y = r * (sh + bar)
        _label(d, 4, y + 5, "%s (%s)  floor_y=%d  stand_x=%s  lamp=%s"
               % (rm["name"], rm["id"], rm["floor_y"], rm["stand_x"], rm["lamp"]))
        for c, st in enumerate(("dark", "lit")):
            im = Image.open(os.path.join(RAW_PLATE, rm["files"][st])).convert("RGB")
            im = im.resize((sw, sh), Image.LANCZOS)
            dd = ImageDraw.Draw(im)
            fy = rm["floor_y"] // 2
            dd.line([(0, fy), (sw, fy)], fill=(255, 90, 60), width=1)         # 바닥선
            for sx in rm["stand_x"]:
                dd.line([(sx // 2, fy - 10), (sx // 2, fy + 6)], fill=(255, 90, 60), width=1)
            lx, ly = rm["lamp"][0] // 2, rm["lamp"][1] // 2
            dd.ellipse([lx - 4, ly - 4, lx + 4, ly + 4], outline=(120, 220, 255))
            out.paste(im, (c * (sw + gap), y + bar))
    p = os.path.join(RAW_PLATE, "plates_sheet.png")
    out.save(p)
    print("PLATE SHEET", p, out.size)


def plate_char_test():
    """2.5D 접지 시험 — 캐릭터 ×1 원화를 room_scale(×3)로 키워 바닥선에 세워 본다.
    캐릭터 폴더는 **읽기만** 한다. 플레이트가 틀렸는지 도트가 틀렸는지 눈으로 가린다."""
    import json
    meta = json.load(open(os.path.join(RAW_PLATE, "plates_meta.json"), encoding="utf-8"))
    croot = os.path.join(ROOT, "static", "art", "chars", "front", "p2")
    cm = os.path.join(croot, "meta.json")
    if not os.path.exists(cm):
        print("skip char test (front/p2 없음)")
        return
    c = json.load(open(cm, encoding="utf-8"))
    sc = int(c.get("room_scale", 3))
    cell = int(c.get("src_cell", 64))
    base = int(c.get("src_baseline", 60))
    rows = c.get("rows", {})
    cols = int(c.get("cols", 3))
    roles = ["medic", "engineer", "trader", "scholar", "cook", "farmer", "kid", "scout"]
    cut = {}
    for r in roles:
        p = os.path.join(croot, "src", r + ".png")
        if not os.path.exists(p):
            continue
        sh = Image.open(p).convert("RGBA")
        row = int(rows.get("idle", 0))
        frame = sh.crop((0, row * cell, cell, row * cell + cell))
        cut[r] = frame.resize((cell * sc, cell * sc), Image.NEAREST)
    if not cut:
        print("skip char test (src 없음)")
        return
    names = list(cut)
    out_rows = []
    for ri, rm in enumerate(meta["rooms"][:3]):
        im = Image.open(os.path.join(RAW_PLATE, rm["files"]["lit"])).convert("RGBA")
        x0, x1 = rm["stand_x"]
        for k in range(3):
            spr = cut[names[(ri * 3 + k) % len(names)]]
            x = x0 + (x1 - x0) * (k + 0.5) / 3
            # 셀 안의 발 기준선(base*sc)을 플레이트 바닥선에 맞춘다
            im.alpha_composite(spr, (int(x - spr.size[0] / 2),
                                     int(rm["floor_y"] - base * sc)))
        d2 = ImageDraw.Draw(im)
        d2.line([(0, rm["floor_y"]), (im.size[0], rm["floor_y"])], fill=(255, 90, 60, 150))
        out_rows.append((rm["name"], im.convert("RGB")))
    w, h = out_rows[0][1].size
    out = Image.new("RGB", (w, len(out_rows) * (h + 18)), (10, 9, 8))
    d = ImageDraw.Draw(out)
    for i, (nm, im) in enumerate(out_rows):
        _label(d, 4, i * (h + 18) + 4,
               "%s  + front/p2 src x%d  (1.6m = %dpx, %.1f px/m)"
               % (nm, sc, int(c.get("room_h_1m6", 132)), meta["grid"]["px_per_m"]))
        out.paste(im, (0, i * (h + 18) + 18))
    p = os.path.join(RAW_PLATE, "plate_char_test.png")
    out.save(p)
    print("CHAR TEST", p, out.size)


def serve_dir(src, dst, exts=(".png", ".json")):
    os.makedirs(dst, exist_ok=True)
    tot = 0
    for n in sorted(os.listdir(src)):
        if not n.endswith(exts) or n.startswith("_") or n.endswith("_sheet.png"):
            continue
        if n.endswith("_test.png") or n.startswith("example_"):
            continue
        s, t = os.path.join(src, n), os.path.join(dst, n)
        if n.endswith(".json"):
            open(t, "w", encoding="utf-8").write(open(s, encoding="utf-8").read())
        else:
            im = Image.open(s)
            if im.mode == "RGBA":
                # 투명한 자리에도 종이 결 노이즈가 **색으로** 남아 있어서 파일이 두 배가 된다.
                # 안 보이는 화소의 RGB 를 0 으로 눌러 압축이 먹게 한다(화면은 한 화소도 안 바뀐다).
                a = im.getchannel("A")
                im = Image.composite(im, Image.new("RGBA", im.size, (0, 0, 0, 0)),
                                     a.point(lambda v: 255 if v else 0))
            im.save(t, optimize=True)
        kb = os.path.getsize(t) / 1024
        tot += kb
        print("  serve %-34s %7.1f KB" % (n, kb))
    print("  합계 %.1f KB" % tot)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "measure":
        measure(sys.argv[2:] or None)
        raise SystemExit(0)
    if mode == "threats":
        threats_sheet()
        print("serve → static/art/threats")
        serve_dir(RAW_THREAT, DST_THREAT)
        raise SystemExit(0)
    if mode == "plates":
        plates_sheet()
        plate_char_test()
        print("serve → static/art/plates")
        serve_dir(RAW_PLATE, DST_PLATE)
        raise SystemExit(0)
    if mode == "sheets":
        threats_sheet(); plates_sheet(); plate_char_test()
        raise SystemExit(0)
    if mode in ("compare", "all"):
        compare()
    if mode in ("serve", "all"):
        serve()