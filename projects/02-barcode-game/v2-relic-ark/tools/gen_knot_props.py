# -*- coding: utf-8 -*-
"""S22 1단계 「흔적」 — 매듭 소품 4종 + 손님 흔적 덧씌움 5종 + 하위 종류 소품 12종(by_subtype 표).

  python tools/gen_knot_props.py

1) 매듭 소품(chair_1 · sprout_on_sill · warm_basin · name_tag_worn)
   tools/gen_props.py 의 Sprite·snap·brushed 를 그대로 가져다 쓴다 → 선반 소품 34종과 같은 화풍·같은 팔레트.
   34×30 1배 + x4. props_meta.json 의 "knots" 블록에 덧붙인다(기존 "props" 는 건드리지 않는다).
2) 손님 흔적(trace_*) — 방 칸(564×317) 구석에 놓는 반투명 덧씌움. static/art/decor/ + decor_meta.json "traces".
따뜻한 쪽(차가운 발광 없음, 사용자 피드백 "괴기스럽다"). 생성 AI 없음.
"""
import json, math, os, random, sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_props as G  # noqa: E402  (main() 은 부르지 않는다)

DECOR = os.path.join(ROOT, "static", "art", "decor")


# ══════ 1. 매듭 소품 ══════
def d_chair_1(s):            # 식량창고 앞에 내놓은 의자 하나 — 방석을 얹어 "누가 앉아도 된다"
    s.part(G.rect(9, 20, 11.5, 27), "umber", dark=True)          # 뒷다리(안쪽)
    s.part(G.rect(22, 20, 24.5, 27), "umber", dark=True)
    s.part(G.rect(8, 3, 11, 19), "umber")                         # 등받이 기둥
    s.part(G.rect(22.5, 3, 25.5, 19), "umber")
    s.part(G.cut(7.5, 4, 26, 7.5, 0.8), "umber")                  # 등받이 살 둘
    s.part(G.cut(8.5, 10, 25, 12.5, 0.6), "umber")
    s.part(G.trap(7, 27, 17, 5, 28.5, 20.5), "ochre")             # 앉는 판
    s.part(G.rect(5.5, 20.5, 8.5, 30), "umber")                   # 앞다리
    s.part(G.rect(25.5, 20.5, 28.5, 30), "umber")
    s.part(G.trap(10, 24, 14.5, 8.5, 25.5, 17.6), "oxblood")      # 방석
    s.mark([(11, 16.2), (23, 16.2)], "oxblood", 0.6, False)
    s.mark([(9.5, 5.6), (24, 5.6)], "umber", 0.5)                 # 나뭇결


def d_sprout_on_sill(s):     # 창턱의 싹 — 손톱만 한 초록 하나, 흙 그릇
    s.part(G.rect(0.5, 23.5, 33.5, 27.5), "umber")                # 창턱
    s.part(G.rect(2, 27.5, 32, 30), "umber", dark=True)
    s.part(G.trap(10.5, 23.5, 14.5, 12.5, 21.5, 23.5), "burnt")   # 흙 그릇
    s.flat(G.ell(17, 14.6, 6.3, 1.3), "umber", dark=True)        # 흙
    s.mark([(17, 14.5), (17.3, 11), (16.6, 7.5)], "olive", 0.9)   # 줄기
    s.part(G.ell(13.6, 8.2, 3.2, 1.8), "olive")                   # 떡잎 둘
    s.part(G.ell(20.2, 7.0, 3.4, 1.9), "olive")
    s.part(G.ell(27, 22, 2.2, 1.4), "cream")                      # 젖은 천 끝(창가에 함께)
    s.part(G.trap(24, 30, 18.5, 24.5, 29.5, 23.4), "cream")


def d_warm_basin(s):         # 공방의 따뜻한 대야 — 김 세 줄, 가장자리에 수건
    s.part(G.trap(4, 30, 17.5, 7.5, 26.5, 29), "bone")            # 대야 몸
    s.flat(G.rect(5.5, 20, 28.5, 22), "oxblood")                  # 칠한 띠
    s.part(G.ell(17, 17.5, 13.5, 2.8), "bone")                    # 테
    s.flat(G.ell(17, 17.6, 11.2, 1.8), "cream")                   # 따뜻한 물(밝은 크림 — 물빛 청록을 쓰지 않는다)
    s.part(G.trap(24.5, 30.5, 15.5, 25, 30, 25), "ochre")         # 걸친 수건
    for k, x in enumerate((11.5, 17, 22)):                        # 김(따뜻한 크림색 흔들림)
        s.mark([(x + (0.9 if i % 2 else -0.9), 14 - i * 2.6) for i in range(5)], "cream", 0.75, False)


def d_name_tag_worn(s):      # 닳은 이름표 — 끈 고리, 바느질 테, 글자 대신 긁힌 두 줄
    s.part(G.ell(17, 3.4, 1.4, 1.4), "char")                      # 못
    s.mark([(17, 3.6), (11.5, 11), (22.8, 11), (17, 3.6)], "umber", 0.7, True)   # 끈
    tag = [(8.5, 11), (25.8, 11.6), (26.6, 26.5), (23.6, 27.3), (22.3, 25.8), (9.6, 26.2)]   # 아래 귀퉁이 해짐
    s.part(tag, "cream")
    s.flat([(19, 20), (25.2, 20.4), (25.8, 26.2), (19.6, 25.8)], "cream", dark=True)          # 손때 자국
    for a, b in (((10.5, 13.2), (24.2, 13.6)), ((24.4, 13.8), (25, 24.4)), ((10.8, 24), (11, 13.4))):
        s.mark([a, b], "umber", 0.45)                              # 바느질
    s.mark([(12.5, 17.5), (15, 16.8), (17.2, 18), (20.5, 17)], None, 0.8)       # 이름(읽히지 않는 손글씨 두 줄)
    s.mark([(12.5, 21.4), (16, 20.9), (18.6, 21.6)], None, 0.7)


KNOTS = [("chair_1", "식량창고 앞 의자", d_chair_1, "arcs.json arc 1 step 1 set_prop — 「앉아서 먹는 저녁」. 아직 아무도 앉지 않은 의자"),
         ("sprout_on_sill", "창가의 싹", d_sprout_on_sill, "arcs.json after.prop — 온실 젖은 천 사이 손톱만 한 싹"),
         ("warm_basin", "따뜻한 대야", d_warm_basin, "arcs.json after.prop — 공방 대야에 찬 따뜻한 물, 손이 펴진다"),
         ("name_tag_worn", "닳은 이름표", d_name_tag_worn, "arcs2.json after.prop — 남이 먼저 이름을 써 준 이름표")]


def make_knots():
    meta_p = os.path.join(G.OUT_1X, "props_meta.json")
    meta = json.load(open(meta_p, encoding="utf-8"))
    knots = {}
    made = []
    for pid, name, fn, ctx in KNOTS:
        sp = G.Sprite(1, seed=sum(map(ord, pid)) * 7)
        fn(sp)
        big = G.snap(sp.finish())
        small = G.snap(big.resize((G.CELL_W, G.CELL_H), Image.LANCZOS))
        big = G.brushed(big, seed=sum(map(ord, pid)))
        big.save(os.path.join(G.OUT_4X, pid + ".png")); small.save(os.path.join(G.OUT_1X, pid + ".png"))
        knots[pid] = {"name": name, "kind": "knot", "slots": 1, "w": G.CELL_W, "h": G.CELL_H,
                      "file": "static/art/props/%s.png" % pid, "file4x": "static/art/props/x4/%s.png" % pid, "context": ctx}
        made.append((pid, name, small, big))
    meta["knots"] = knots
    meta["_knots_note"] = "S22 매듭 소품. tools/gen_knot_props.py 가 이 블록만 쓴다(gen_props.py 를 다시 돌리면 지워지니 그 뒤에 이것도 다시 돌릴 것)"
    json.dump(meta, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return made


# ══════ 2. 손님 흔적 덧씌움(방 칸 축척, 반투명) ══════
SS = 3


def canvas(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def down(im, alpha=1.0):
    im = im.resize((im.width // SS, im.height // SS), Image.LANCZOS)
    if alpha < 1:
        a = im.getchannel("A").point(lambda v: int(v * alpha)); im.putalpha(a)
    return im


WET = (40, 30, 22)          # 젖은 자국(따뜻한 진갈색)
SHEEN = (246, 222, 170)     # 등불을 받은 물기 반짝


def trace_footprints():      # 맨발 젖은 발자국 넷 — 손님·신인류
    w, h = 180, 48; im = canvas(w, h); d = ImageDraw.Draw(im)
    for i in range(4):
        x = 20 + i * 42; y = 30 if i % 2 else 16
        d.ellipse([(x - 7.5) * SS, (y - 4) * SS, (x + 7.5) * SS, (y + 11) * SS], fill=(*WET, 170))     # 발바닥
        d.ellipse([(x - 5) * SS, (y + 9) * SS, (x + 5) * SS, (y + 15) * SS], fill=(*WET, 170))       # 뒤꿈치
        for k in range(4):
            tx = x - 6 + k * 4.0; ty = y - 7.5 + abs(k - 1.5) * 1.0
            d.ellipse([(tx - 1.8) * SS, (ty - 1.8) * SS, (tx + 1.8) * SS, (ty + 1.8) * SS], fill=(*WET, 170))
        d.ellipse([(x - 3) * SS, (y - 1) * SS, (x - 1) * SS, (y + 1) * SS], fill=(*SHEEN, 150))
    return down(im.filter(ImageFilter.GaussianBlur(0.7 * SS)), 0.95)


def trace_tentacle():        # 문어가 끌고 지나간 젖은 자국 + 빨판 점
    w, h = 150, 46; im = canvas(w, h); d = ImageDraw.Draw(im)
    pts = [(10 + t * 130, 26 + 10 * math.sin(t * 7.5) * (1 - t * 0.4)) for t in [i / 60 for i in range(61)]]
    d.line([(x * SS, y * SS) for x, y in pts], fill=(*WET, 160), width=8 * SS, joint="curve")
    tip = pts[-1]; d.arc([(tip[0] - 8) * SS, (tip[1] - 12) * SS, (tip[0] + 6) * SS, (tip[1] + 2) * SS], 90, 400, fill=(*WET, 130), width=4 * SS)
    for i in range(3, 58, 5):
        x, y = pts[i]
        d.ellipse([(x - 1.6) * SS, (y + 4) * SS, (x + 1.6) * SS, (y + 7) * SS], fill=(*WET, 160))
    for i in (8, 30, 50):
        x, y = pts[i]; d.line([((x - 3) * SS, (y - 1.5) * SS), ((x + 3) * SS, (y - 1.5) * SS)], fill=(*SHEEN, 150), width=2 * SS)
    return down(im.filter(ImageFilter.GaussianBlur(0.6 * SS)), 0.8)


def trace_scales():          # 작은 비늘 조각 — 등불을 받아 따뜻하게 반짝(작은 물고기 떼). S22 후속: 발자국·문어 자국과 같은 밀도로 키움
    w, h = 150, 46; im = canvas(w, h); d = ImageDraw.Draw(im); r = random.Random(4)
    d.ellipse([14 * SS, 24 * SS, 136 * SS, 42 * SS], fill=(*WET, 80))                 # 젖은 자리(떼가 지나간 물기)
    for i in range(14):
        x, y, s_ = 18 + r.uniform(0, 114), 14 + r.uniform(0, 22), r.uniform(5.5, 8.5)
        a0 = r.uniform(0, 360)
        d.pieslice([(x - s_) * SS, (y - s_ * 0.8) * SS, (x + s_) * SS, (y + s_ * 0.8) * SS], a0, a0 + 200,
                   fill=(226, 204, 150, 245), outline=(98, 74, 44, 255), width=int(1.4 * SS))
        d.arc([(x - s_ * 0.6) * SS, (y - s_ * 0.5) * SS, (x + s_ * 0.6) * SS, (y + s_ * 0.5) * SS], a0 + 30, a0 + 170,
              fill=(150, 120, 80, 220), width=SS)                                     # 비늘 결
        d.ellipse([(x - 1.6) * SS, (y - 1.6) * SS, (x + 1.6) * SS, (y + 1.6) * SS], fill=(255, 240, 200, 255))
    return down(im.filter(ImageFilter.GaussianBlur(0.3 * SS)), 0.95)


def trace_seaweed():         # 바닥에 떨어진 해초 한 가닥(정원사의 떼가 다녀감)
    w, h = 120, 40; im = canvas(w, h); d = ImageDraw.Draw(im)
    pts = [(8 + t * 104, 28 - 8 * math.sin(t * 5.2)) for t in [i / 40 for i in range(41)]]
    for i in range(len(pts) - 1):
        wid = (5.5 - 3.5 * i / len(pts)) * SS
        d.line([(pts[i][0] * SS, pts[i][1] * SS), (pts[i + 1][0] * SS, pts[i + 1][1] * SS)], fill=(110, 112, 58, 220), width=int(wid))
    for i in (10, 22, 32):
        x, y = pts[i]; s_ = 1 if i % 2 else -1
        d.polygon([(x * SS, y * SS), ((x + 9) * SS, (y + s_ * 6) * SS), ((x + 15) * SS, (y + s_ * 4) * SS)], fill=(141, 143, 74, 220))
    d.line([(p[0] * SS, (p[1] - 1.5) * SS) for p in pts[4:20]], fill=(*SHEEN, 120), width=SS)
    d.ellipse([18 * SS, 30 * SS, 60 * SS, 38 * SS], fill=(*WET, 70))                        # 젖은 자리
    return down(im.filter(ImageFilter.GaussianBlur(0.4 * SS)), 0.85)


def trace_ripples():         # 작은 물웅덩이 + 번지는 동심원 + 떨어진 물방울(누군지 모를 손님)
    w, h = 120, 40; im = canvas(w, h); d = ImageDraw.Draw(im)
    d.ellipse([20 * SS, 16 * SS, 100 * SS, 36 * SS], fill=(*WET, 90))
    for k, (rx, ry) in enumerate(((14, 4), (24, 6.5), (34, 8.5))):
        d.ellipse([(60 - rx) * SS, (26 - ry) * SS, (60 + rx) * SS, (26 + ry) * SS], outline=(*SHEEN, 150 - k * 40), width=int(1.6 * SS))
    for x, y in ((104, 30), (110, 34), (12, 32)):
        d.ellipse([(x - 2) * SS, (y - 1.4) * SS, (x + 2) * SS, (y + 1.4) * SS], fill=(*WET, 120))
    return down(im.filter(ImageFilter.GaussianBlur(0.5 * SS)), 0.85)


TRACES = [("trace_footprints", "젖은 맨발 발자국", trace_footprints, ["guest", "newhuman"]),
          ("trace_tentacle", "문어가 끌고 간 자국", trace_tentacle, ["octopus"]),
          ("trace_scales", "작은 비늘 조각", trace_scales, ["small_fish"]),
          ("trace_seaweed", "떨어진 해초 한 가닥", trace_seaweed, ["gardener"]),
          ("trace_ripples", "물웅덩이와 물무늬", trace_ripples, ["residents", "any"])]


def make_traces():
    meta_p = os.path.join(DECOR, "decor_meta.json")
    meta = json.load(open(meta_p, encoding="utf-8"))
    out = {"_note": "S22 손님 흔적. 자리를 비운 사이 손님이 다녀갔다는 힌트. 칸(564×317) 좌표에 anchor(아래 가운데)를 맞춘다. 플레이트 위·사람 아래. 반투명(이미 알파가 들어 있다). 몇 시간 뒤 서서히 지워도 좋다",
           "corner_spots_in_cell": [[200, 272], [370, 272], [300, 276]],
           "corner_note": "방 바닥 면(발선 282 바로 위) 가운데 기둥. 두 서는 자리(84·480) 사이라 사람에 가려도 일부는 보인다", "items": []}
    made = []
    for tid, ko, fn, visitors in TRACES:
        im = fn(); im.save(os.path.join(DECOR, tid + ".png"), optimize=True)
        out["items"].append(dict(id=tid, ko=ko, file=tid + ".png", w=im.width, h=im.height, anchor=[im.width // 2, im.height - 6], visitors=visitors))
        made.append((tid, ko, im, visitors))
    meta["traces"] = out
    json.dump(meta, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return made


def sheet(knots, traces):
    from PIL import ImageFont
    f = lambda s, b=False: ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf" if b else "C:/Windows/Fonts/malgun.ttf", s)
    W = 1400; H = 760
    S = Image.new("RGBA", (W, H), (26, 22, 18, 255)); d = ImageDraw.Draw(S)
    d.text((16, 12), "S22 「흔적」 — 매듭 소품 4종(1배 실제 크기 / 6배) · 손님 흔적 5종(방 플레이트 위) · 생성 AI 없음", font=f(20, True), fill=(232, 220, 191))
    for i, (pid, name, small, big) in enumerate(knots):
        x = 20 + i * 340; y = 50
        S.alpha_composite(small, (x, y + 150))
        up = small.resize((small.width * 6, small.height * 6), Image.NEAREST); S.alpha_composite(up, (x + 60, y))
        S.alpha_composite(big.resize((68, 60), Image.NEAREST), (x, y + 60))
        d.text((x, y + 196), f"{pid}  ·  {name}", font=f(16, True), fill=(240, 200, 120))
    plate = Image.open(os.path.join(ROOT, "static", "art", "plates", "room_plate_quarters_lit.png")).convert("RGBA").crop((54, 33, 618, 350))
    plate2 = Image.open(os.path.join(ROOT, "static", "art", "plates", "room_plate_storage_lit.png")).convert("RGBA").crop((54, 33, 618, 350))
    pos = [(200, 272), (370, 272), (300, 276), (200, 272), (370, 272)]
    for j, (tid, ko, im, vis) in enumerate(traces):
        base = (plate if j % 2 == 0 else plate2).copy()
        ax, ay = pos[j]; base.alpha_composite(im, (ax - im.width // 2, ay - (im.height - 6)))
        crop = base.crop((ax - 150, ay - 110, ax + 150, ay + 40))
        x = 20 + (j % 4) * 340; y = 290 + (j // 4) * 230
        S.alpha_composite(crop, (x, y))
        d.text((x, y + 156), f"{tid} · {ko} · {'/'.join(vis)}", font=f(14, True), fill=(240, 200, 120))
    out = os.path.join(ROOT, "docs", "reports", "bg_S22_sheet.png"); S.convert("RGB").save(out, optimize=True)
    return out




# ══════ 3. 하위 종류 소품 12종(S22 후속) — 맞는 소품이 없던 하위 종류 ══════
def d_hand_lamp(s):          # light — 손등불: 고리 손잡이, 철 바구니, 따뜻한 유리
    s.mark([(12, 7), (13, 2.5), (21, 2.5), (22, 7)], "char", 1.0)            # 손잡이 고리
    s.part(G.cut(11, 6.5, 23, 9, 0.6), "char")                                # 뚜껑
    s.part(G.cut(12, 9, 22, 24, 1.2), "ochre")                                # 따뜻한 유리
    s.flat(G.ell(17, 16.5, 3.2, 4.2), "cream")                                # 불꽃 빛
    for x in (12.5, 17, 21.5):
        s.mark([(x, 9.2), (x, 23.8)], "char", 0.7)                            # 바구니 살
    s.part(G.cut(10, 24, 24, 29.6, 0.8), "char")                              # 받침


def d_bean_tin(s):           # coffee — 검은 콩 깡통 + 막대 봉지 하나
    s.part(G.rect(8, 9, 23, 29.5), "char")
    s.part(G.ell(15.5, 9, 7.5, 1.8), "char")
    s.flat(G.rect(8, 15, 23, 21.5), "burnt")                                  # 띠
    s.part(G.ell(13.6, 18.2, 1.7, 2.3), "umber", dark=True)                   # 콩 둘
    s.part(G.ell(17.6, 18.2, 1.7, 2.3), "umber", dark=True)
    s.mark([(13.6, 16.4), (13.6, 20)], "umber", 0.4)
    s.part(G.trap(25, 29, 14, 24.5, 29.5, 29.6), "umber")                     # 쓴 가루 막대 봉지


def d_white_carton(s):       # milk — 흰 물 상자(뾰족 지붕 종이갑)
    s.part([(10, 12), (17, 6), (24, 12), (24, 29.6), (10, 29.6)], "cream")
    s.part([(10, 12), (17, 6), (17, 3.5), (10, 9.5)], "cream", dark=True)    # 접힌 꼭대기
    s.flat(G.rect(10, 17, 24, 22), "ochre")                                   # 띠
    s.part(G.ell(17, 25.5, 2.0, 2.6), "bone")                                 # 물방울 표식(흰 쪽)


def d_fruit_box(s):          # juice — 과일 단물 상자 + 빨대
    s.mark([(20, 9), (22.5, 2.5), (25.5, 2.5)], "oxblood", 0.9)              # 빨대
    s.part(G.cut(10, 9, 24, 29.6, 0.8), "burnt")
    s.part(G.ell(17, 19.5, 4.2, 4.2), "ochre")                                # 과일
    s.part(G.ell(18.5, 14.6, 2.0, 1.1), "olive")                              # 잎


def d_candy_jar(s):          # sweet — 단 알갱이 병
    s.part(G.cut(9, 10, 25, 29.6, 2.0), "bone")
    s.part(G.cut(11, 6.5, 23, 10.5, 0.8), "oxblood")                          # 뚜껑
    r = random.Random(3)
    for k in range(9):
        x = 12 + (k % 3) * 4.6 + r.uniform(-0.6, 0.6); y = 15 + (k // 3) * 4.6 + r.uniform(-0.6, 0.6)
        s.part(G.ell(x, y, 1.9, 1.9, 10), ["oxblood", "ochre", "olive", "burnt"][k % 4], line=False)
    s.mark([(11, 12.5), (11, 27)], "cream", 0.6, False)                        # 유리 반짝


def d_cloth_bag(s):          # bag — 어깨에 메는 천 가방
    s.mark([(9, 15), (12, 3.5), (22, 3.5), (25, 15)], "umber", 1.4)           # 끈
    s.part(G.cut(6, 13, 28, 29.6, 2.0), "olive")
    s.part([(6, 13), (28, 13), (27, 21), (17, 23), (7, 21)], "olive", dark=True)   # 덮개
    s.part(G.ell(17, 21.5, 1.6, 1.6), "ochre")                                # 단추


def d_knit_hat_glove(s):     # small — 털모자와 장갑 한 짝
    s.part(G.ell(12.5, 22, 9.0, 8.5, 22, 0, 180), "oxblood")                  # 모자 몸
    s.part(G.cut(3.5, 22, 21.5, 27, 0.8), "cream")                            # 접은 테
    s.part(G.ell(12.5, 11.8, 2.4, 2.4), "cream")                              # 방울
    for x in (8, 12.5, 17):
        s.mark([(x, 15), (x, 21.5)], "oxblood", 0.5)
    s.part([(22, 29.6), (22, 17), (24, 14), (25.5, 17), (27, 13.5), (29, 17), (31, 18.5), (31, 29.6)], "umber")   # 장갑
    s.flat(G.rect(22, 26, 31, 29.6), "cream")


def d_rolled_map(s):         # map — 반쯤 펼친 수심 그림(실제 지형 아님)
    s.part(G.cut(3, 14, 26, 28, 0.6), "cream")                                # 펼친 장
    for k in range(3):                                                        # 수심 등고선(추상 물결)
        y = 17.5 + k * 3.4
        s.mark([(5 + i * 3, y + (0.9 if i % 2 else -0.9)) for i in range(8)], "umber", 0.55, False)
    s.part(G.ell(13, 23.5, 1.4, 1.4), "oxblood", line=False)                  # 표시 점
    s.part(G.ell(28, 21, 3.4, 7.6), "cream", dark=True)                        # 말린 쪽
    s.part(G.ell(28.4, 21, 1.4, 4.4), "umber", line=False)


def d_soap_bottle(s):        # hygiene — 거품 내는 병 + 비누
    s.part(G.cut(7, 10, 17, 29.6, 1.2), "bone")
    s.part(G.rect(10.5, 6, 13.5, 10), "char")                                 # 펌프
    s.part(G.rect(10.5, 5, 18, 7), "char")
    s.flat(G.rect(7, 16, 17, 21), "olive")
    s.part(G.cut(19, 23.5, 30, 29.6, 1.2), "cream")                           # 비누
    for cx, cy, rr in ((22.5, 19.5, 2.6), (27, 17.5, 2.0), (24, 13.5, 1.6)):  # 거품(외곽선 없이 밝게 — 작게 그리면 선이 때로 보인다)
        s.part(G.ell(cx, cy, rr, rr, 12), "cream", line=False)
        s.mark([(cx - rr * 0.4, cy - rr * 0.3), (cx - rr * 0.1, cy - rr * 0.6)], "cream", 0.5, True)


def d_sound_shell(s):        # audio — 귀에 거는 소리 조개(머리띠 소리통)
    s.mark([(8.5, 18), (9, 9), (17, 4.5), (25, 9), (25.5, 18)], "char", 1.6)  # 머리띠
    s.part(G.cut(5, 16, 12, 27, 1.6), "oxblood")                              # 귀 조개 둘
    s.part(G.cut(22, 16, 29, 27, 1.6), "oxblood")
    s.part(G.cut(6.5, 18, 10.5, 25, 1.0), "char", line=False)
    s.part(G.cut(23.5, 18, 27.5, 25, 1.0), "char", line=False)
    s.mark([(25.5, 27), (27, 29.4), (31, 29.4)], "char", 0.6)                 # 줄


def d_eraser_ruler(s):       # tool — 지우개와 자
    s.part([(3, 24), (27, 10), (29.5, 14), (5.5, 28)], "ochre")              # 자(비스듬히)
    for i in range(7):
        x = 6 + i * 3.3; y = 25 - i * 1.95
        s.mark([(x, y), (x + 0.9, y + (1.6 if i % 2 else 0.9))], "umber", 0.5)
    s.part(G.cut(18, 21.5, 31, 29.6, 1.0), "cream")                           # 지우개
    s.part(G.rect(22, 21.5, 31, 29.6), "oxblood")                             # 종이 띠


def d_match_box(s):          # fire — 긋는 불 상자 + 성냥 둘
    s.part(G.cut(5, 18, 29, 29.6, 0.8), "cream")                              # 속상자
    s.part(G.cut(9, 17, 29, 29.6, 0.8), "oxblood")                            # 겉갑(반쯤 밀림)
    s.flat(G.rect(9, 21, 29, 23.5), "char")                                   # 긋는 띠
    for k, (x0, y0, x1, y1) in enumerate(((6, 15, 18, 6), (12, 15, 24, 8))):
        s.mark([(x0, y0), (x1, y1)], "bone", 1.0, False)
        s.part(G.ell(x1, y1, 1.6, 1.6, 10), "oxblood")


SUBTYPE_PROPS = [
    ("light", "electronics", "prop_hand_lamp", "손등불", d_hand_lamp),
    ("coffee", "drink", "prop_bean_tin", "검은 콩 깡통", d_bean_tin),
    ("milk", "drink", "prop_white_carton", "흰 물 상자", d_white_carton),
    ("juice", "drink", "prop_fruit_box", "과일 단물 상자", d_fruit_box),
    ("sweet", "food", "prop_candy_jar", "단 알갱이 병", d_candy_jar),
    ("bag", "apparel", "prop_cloth_bag", "천 가방", d_cloth_bag),
    ("small", "apparel", "prop_knit_hat_glove", "털모자와 장갑", d_knit_hat_glove),
    ("map", "book", "prop_rolled_map", "말린 물 깊이 그림", d_rolled_map),
    ("hygiene", "medical", "prop_soap_bottle", "거품 병과 비누", d_soap_bottle),
    ("audio", "electronics", "prop_sound_shell", "소리 조개", d_sound_shell),
    ("tool", "stationery", "prop_eraser_ruler", "지우개와 자", d_eraser_ruler),
    ("fire", "tobacco", "prop_match_box", "긋는 불 상자", d_match_box),
]

# 하위 종류 49개 → 소품(정본). match: good 잘 맞음 · weak 비슷함(나중에 다시 볼 것) · new S22 후속으로 새로 그림
BY_SUBTYPE = {
    "food": {"noodle": ("prop_noodle_box", "good"), "snack": ("prop_crisp_bundle", "good"), "canned": ("prop_dry_jar", "weak"),
             "grain": ("prop_seed_sack", "good"), "sweet": ("prop_candy_jar", "new"), "sauce": ("prop_long_neck_bottle", "weak")},
    "drink": {"water": ("prop_flat_canteen", "good"), "soda": ("prop_cap_heap", "good"), "coffee": ("prop_bean_tin", "new"),
              "tea": ("prop_dry_leaf_box", "weak"), "milk": ("prop_white_carton", "new"), "juice": ("prop_fruit_box", "new"),
              "alcohol": ("prop_long_neck_bottle", "good")},
    "medical": {"pill": ("prop_twelve_cell_box", "good"), "ointment": ("prop_white_crock", "good"), "disinfect": ("prop_brown_vial", "weak"),
                "bandage": ("prop_rolled_strips", "good"), "cosmetic": ("prop_white_crock", "weak"), "hygiene": ("prop_soap_bottle", "new"),
                "tonic": ("prop_brown_vial", "good")},
    "electronics": {"battery": ("prop_cell_tin", "good"), "cable": ("prop_tangled_light_thread", "good"), "device": ("prop_black_panel", "good"),
                    "light": ("prop_hand_lamp", "new"), "audio": ("prop_sound_shell", "new"), "part": ("prop_gauge_piece", "good")},
    "stationery": {"pen": ("prop_stick_bundle", "good"), "paper": ("prop_pressed_paper_stack", "good"), "sticky": ("prop_color_chip_pile", "good"),
                   "toy": ("prop_little_person_doll", "good"), "tape": ("prop_rolled_strips", "weak"), "tool": ("prop_eraser_ruler", "new"),
                   "document": ("prop_loose_leaf_box", "weak")},
    "book": {"manual": ("prop_stacked_books", "good"), "field_guide": ("prop_standing_books", "weak"), "map": ("prop_rolled_map", "new"),
             "story": ("prop_standing_books", "good"), "ledger": ("prop_stacked_books", "weak"), "index": ("prop_fused_block", "weak")},
    "apparel": {"shirt": ("prop_folded_cloth", "good"), "shoes": ("prop_single_boot", "good"), "label": ("prop_name_patch_box", "good"),
                "coat": ("prop_hung_coat", "good"), "small": ("prop_knit_hat_glove", "new"), "bag": ("prop_cloth_bag", "new")},
    "tobacco": {"smoke": ("prop_thin_paper_box", "good"), "liquor": ("prop_sealed_flask", "good"), "beer": ("prop_empty_bottle_row", "weak"),
                "fire": ("prop_match_box", "new")},
    "unknown": {"any": ("prop_nameless_box", "good")},
}


def make_subtype_props():
    meta_p = os.path.join(G.OUT_1X, "props_meta.json")
    meta = json.load(open(meta_p, encoding="utf-8"))
    sub = {}; made = []
    for st, cat, pid, name, fn in SUBTYPE_PROPS:
        sp = G.Sprite(1, seed=sum(map(ord, pid)) * 7)
        fn(sp)
        big = G.snap(sp.finish())
        small = G.snap(big.resize((G.CELL_W, G.CELL_H), Image.LANCZOS))
        big = G.brushed(big, seed=sum(map(ord, pid)))
        big.save(os.path.join(G.OUT_4X, pid + ".png")); small.save(os.path.join(G.OUT_1X, pid + ".png"))
        sub[pid] = {"name": name, "category": cat, "subtype": st, "slots": 1, "w": G.CELL_W, "h": G.CELL_H,
                    "file": "static/art/props/%s.png" % pid, "file4x": "static/art/props/x4/%s.png" % pid}
        made.append((pid, name, small, big, st))
    meta["subtype_props"] = sub
    # by_subtype: 서버·클라이언트가 바로 읽는 표. 파일 경로를 함께 넣어 다른 블록을 뒤질 필요가 없게 한다
    all_files = {}
    for blk in ("props", "subtype_props"):
        for pid, v in meta.get(blk, {}).items():
            all_files[pid] = (v["file"], v["file4x"])
    by = {}
    for cat, m in BY_SUBTYPE.items():
        by[cat] = {}
        for st, (pid, match) in m.items():
            f1, f4 = all_files[pid]
            by[cat][st] = {"prop": pid, "match": match, "file": f1, "file4x": f4}
    meta["by_subtype"] = by
    meta["_by_subtype_note"] = ("S22 정본: relic_templates.json 의 category → subtype → 선반 소품. "
                                "match = good/weak/new. 모르는 subtype 이면 by_subtype[category] 의 첫 good 항목, 그것도 없으면 unknown.any. "
                                "생성 tools/gen_knot_props.py (gen_props.py 를 다시 돌려도 이 블록은 남는다)")
    json.dump(meta, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return made


def subtype_sheet(made):
    from PIL import ImageFont
    f = lambda s_, b=False: ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf" if b else "C:/Windows/Fonts/malgun.ttf", s_)
    cols = 4; cw, ch = 330, 230
    S_ = Image.new("RGBA", (cols * cw + 20, 50 + 3 * ch), (26, 22, 18, 255)); d = ImageDraw.Draw(S_)
    d.text((16, 12), "S22 후속 — 맞는 소품이 없던 하위 종류 12개 (왼쪽 1배 실제 크기 · 오른쪽 6배) · 생성 AI 없음", font=f(19, True), fill=(232, 220, 191))
    for i, (pid, name, small, big, st) in enumerate(made):
        x = 20 + (i % cols) * cw; y = 50 + (i // cols) * ch
        S_.alpha_composite(small, (x, y + 150))
        S_.alpha_composite(small.resize((small.width * 6, small.height * 6), Image.NEAREST), (x + 60, y))
        d.text((x, y + 190), f"{st} → {pid.replace('prop_', '')}", font=f(15, True), fill=(240, 200, 120))
        d.text((x, y + 208), name, font=f(14), fill=(200, 190, 160))
    out = os.path.join(ROOT, "docs", "reports", "bg_S22_subtype_sheet.png"); S_.convert("RGB").save(out, optimize=True)
    return out


# ══════ 4. 보관 자리(잠자리·앉는 자리) — 방 플레이트 위 칸 좌표(564×317) ══════
#   유물(by_subtype 소품, 34×30 1배 → 화면 배율에 맞춰)을 그 사람 잠자리·자리 옆에 둘 때의 바닥점(아래 가운데)
KEEPSAKE_SPOTS = {
    "quarters":   [dict(kind="bed", x=128, y=216, note="아래 칸 침대 왼쪽"), dict(kind="bed", x=272, y=216, note="아래 칸 침대 오른쪽"),
                   dict(kind="bed", x=128, y=127, note="위 칸 침대 왼쪽"), dict(kind="bed", x=272, y=127, note="위 칸 침대 오른쪽")],
    "infirmary":  [dict(kind="bed", x=150, y=244, note="왼쪽 침상 끝"), dict(kind="bed", x=322, y=244, note="오른쪽 침상 끝")],
    "workshop":   [dict(kind="table", x=300, y=205, note="작업대 위 오른쪽"), dict(kind="table", x=190, y=205, note="작업대 위 왼쪽")],
    "greenhouse": [dict(kind="ledge", x=175, y=229, note="왼쪽 화단 턱"), dict(kind="ledge", x=400, y=229, note="오른쪽 화단 턱")],
    "storage":    [dict(kind="shelf", x=350, y=87, note="벽 선반 맨 위 칸 — 머리 위라 사람에 안 가린다"), dict(kind="floor", x=250, y=272, note="바닥 가운데")],
    "power":      [dict(kind="ledge", x=430, y=196, note="오른쪽 장 위 턱"), dict(kind="floor", x=250, y=274, note="바닥 가운데")],
}


def make_keepsake_spots():
    meta_p = os.path.join(DECOR, "decor_meta.json")
    meta = json.load(open(meta_p, encoding="utf-8"))
    meta["keepsake_spots"] = {
        "_note": "S22: 사람의 보관 유물을 놓는 자리. 칸 좌표(564×317, 칸 좌상단 0,0)의 바닥점 = 소품 아래 가운데. "
                 "그 방 사람 수만큼 앞에서부터 쓴다. 침대는 quarters·infirmary 에만 있다. 플레이트가 없는 방은 plate_name_map 을 따른다",
        "by_plate": KEEPSAKE_SPOTS,
        "plate_canvas_offset": [54, 33],
        "plate_canvas_note": "plates_meta(672×378 캔버스) 좌표로 바꾸려면 +54, +33",
    }
    json.dump(meta, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ══════ 5. 「자리 받침」(끝 매듭 공통, 제안 A 승인 2026-10-13) ══════
def d_seat_stand(s):         # 손때 묻은 낮은 나무 받침 + 둥근 방석 + 앞에 이름 천 고리. 등불색 테 한 줄
    s.part(G.rect(6, 27.5, 9, 30), "umber", dark=True)                        # 발 둘
    s.part(G.rect(25, 27.5, 28, 30), "umber", dark=True)
    s.part(G.cut(4.5, 21.5, 29.5, 27.8, 0.8), "umber")                        # 받침 몸
    s.part(G.cut(3, 19, 31, 22.2, 0.6), "ochre")                              # 윗판(등불색 테)
    s.mark([(5, 25), (29, 25)], "umber", 0.45)                                # 나뭇결
    s.part(G.ell(17, 18.6, 11.5, 2.6), "oxblood")                             # 방석
    s.mark([(8, 18.4), (26, 18.4)], "oxblood", 0.5, False)
    s.mark([(14, 22.2), (15, 24.2)], "cream", 0.5); s.mark([(20, 22.2), (19, 24.2)], "cream", 0.5)   # 이름 천 끈
    s.part([(13.2, 24), (20.8, 24), (20.4, 29.2), (17, 28.4), (13.6, 29.2)], "cream")             # 이름 천
    s.mark([(14.6, 26.2), (16.4, 25.8), (18.8, 26.4)], None, 0.5)             # 읽히지 않는 이름


def make_seat_stand():
    pid = "seat_stand"
    sp = G.Sprite(1, seed=sum(map(ord, pid)) * 7); d_seat_stand(sp)
    big = G.snap(sp.finish()); small = G.snap(big.resize((G.CELL_W, G.CELL_H), Image.LANCZOS))
    big = G.brushed(big, seed=sum(map(ord, pid)))
    big.save(os.path.join(G.OUT_4X, pid + ".png")); small.save(os.path.join(G.OUT_1X, pid + ".png"))
    meta_p = os.path.join(G.OUT_1X, "props_meta.json"); meta = json.load(open(meta_p, encoding="utf-8"))
    meta["seat_stand"] = {
        "name": "자리 받침", "slots": 1, "w": G.CELL_W, "h": G.CELL_H,
        "file": "static/art/props/seat_stand.png", "file4x": "static/art/props/x4/seat_stand.png",
        "item_floor_y": 18, "item_floor_y_note": "그 사람의 물건(by_subtype 소품, 같은 배율)의 아래 가장자리를 받침 y=18(방석 윗면)에 맞춘다. 물건이 받침 앞에 그려진다(받침 → 물건 순)",
        "use": "끝 매듭(seat) 공통. 서버 cres.seat.item → 그 물건의 갈래·하위 종류 → by_subtype 소품을 받침 위에. 자리는 decor_meta keepsake_spots",
        "own_prop_arcs": {"arc_cook_seat": "chair_1", "arc_farmer_color": "sprout_on_sill", "arc_engineer_warm": "warm_basin", "arc_trader_unpack": "name_tag_worn"},
        "own_prop_note": "이 넷은 받침 대신 그 매듭 소품(props_meta knots)을 쓴다",
    }
    json.dump(meta, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 미리보기: 받침 / 받침+물건 셋 / 매듭 소품
    from PIL import ImageFont
    f = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 15)
    S_ = Image.new("RGBA", (5 * 230 + 20, 330), (26, 22, 18, 255)); dd = ImageDraw.Draw(S_)
    dd.text((14, 8), "자리 받침(제안 A) — 1배 실제 크기 + 6배 · 받침 위에 그 사람의 물건", font=f, fill=(232, 220, 191))
    items = [None, "prop_white_carton", "prop_hand_lamp", "prop_little_person_doll", "prop_candy_jar"]
    for i, it in enumerate(items):
        c = Image.new("RGBA", (34, 48), (0, 0, 0, 0)); c.alpha_composite(small, (0, 18))
        if it:
            pr = Image.open(os.path.join(G.OUT_1X, it + ".png")).convert("RGBA"); c.alpha_composite(pr, (0, 18 + 18 - 30))
        x = 20 + i * 230
        S_.alpha_composite(c, (x, 250)); S_.alpha_composite(c.resize((34 * 5, 48 * 5), Image.NEAREST), (x + 40, 40))
        dd.text((x, 300), it.replace("prop_", "") if it else "seat_stand", font=f, fill=(240, 200, 120))
    out = os.path.join(ROOT, "docs", "reports", "bg_S22_seat_stand.png"); S_.convert("RGB").save(out, optimize=True)
    return out


if __name__ == "__main__":
    # python tools/gen_knot_props.py            → 전부(매듭·흔적·하위 종류 소품)
    # python tools/gen_knot_props.py subtypes   → 하위 종류 소품 12종 + by_subtype 만
    if sys.argv[1:] == ["seat"]:                   # 자리 받침만
        print("seat stand", make_seat_stand()); sys.exit(0)
    if sys.argv[1:] == ["scales"]:                 # S22 후속: 비늘 흔적 + 보관 자리만
        im = trace_scales(); im.save(os.path.join(DECOR, "trace_scales.png"), optimize=True)
        m = json.load(open(os.path.join(DECOR, "decor_meta.json"), encoding="utf-8"))
        for it in m["traces"]["items"]:
            if it["id"] == "trace_scales":
                it.update(w=im.width, h=im.height, anchor=[im.width // 2, im.height - 6])
        json.dump(m, open(os.path.join(DECOR, "decor_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        make_keepsake_spots(); print("scales + keepsake_spots"); sys.exit(0)
    if sys.argv[1:] != ["subtypes"]:
        k = make_knots(); t = make_traces(); make_keepsake_spots(); print("sheet", sheet(k, t))
    print("subtype sheet", subtype_sheet(make_subtype_props()))
