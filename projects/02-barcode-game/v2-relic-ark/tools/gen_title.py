"""타이틀·로딩 그림 — 기존 M5 레이어만 조립(생성 AI 없음).

python tools/gen_title.py   → static/art/title/* + meta.json + docs/reports/bg_title_sheet.png

「검은 물속에 불 켜진 집」: 절벽에 기댄 탑, 불 켜진 칸들, 돔의 온기, 오른쪽 열린 심연.
시차 레이어 넷(먼 물·빛 / 절벽 / 탑 / 가까운 해초·기포)을 따로 낸다. 크롭 둘: 1280×800, 844×390.
도시 스카이라인(parallax/skyline.png)은 쓰지 않는다(3막 가드). 리바이어던·먹 얼룩 생물도 넣지 않는다(무섭지 않게).
"""
import os, json, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
M5 = os.path.join(ROOT, "static", "art", "maps", "m5")
ART = os.path.join(ROOT, "static", "art")
DST = os.path.join(ART, "title"); os.makedirs(DST, exist_ok=True)
J = json.load(open(os.path.join(M5, "layout.json"), encoding="utf-8"))
WW, WH = J["world"]["w"], J["world"]["h"]
L = J["layers"]; F = {f["id"]: f for f in L["files"]}

CROPS = {  # 세계 영역(x0, y0, w) — 높이는 화면비로
    "landscape": dict(size=(1280, 800), x0=380, y0=180, w=5000),     # 탑은 왼쪽~가운데, 오른쪽 위 열린 물 = 로고 자리
    "phone": dict(size=(844, 390), x0=560, y0=330, w=4900),
}
MARGIN = 0.06   # 시차로 움직일 여유(각 변 6%)
PARALLAX = {"far": 0.15, "cliff": 0.45, "tower": 0.7, "near": 1.0}


def img(name):
    return Image.open(os.path.join(M5, name)).convert("RGBA")


def world_layers():
    """세계 좌표(5600×3400) 레이어 넷"""
    # 먼 물·빛
    b = F["back"]; far = img(b["file"]).resize((b["w"] * 2, b["h"] * 2), Image.BILINEAR)
    atlas = img(L["creatures"]["file"]); fr = L["creatures"]["frames"]
    for s in L["creatures"]["spawn"]:
        if s["s"] in ("leviathan", "ink_a", "ink_b", "ink_c", "eyes"):
            continue                                    # 무섭지 않게: 큰 그림자·먹 생물·눈은 빼고 물고기·해파리만
        f = fr[s["s"]]; sp = atlas.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]))
        if s.get("flip"): sp = sp.transpose(Image.FLIP_LEFT_RIGHT)
        far.alpha_composite(sp, (int(s["x"] - f["w"] / 2), int(s["y"] - f["h"] / 2)))
    # 절벽
    cliff = Image.new("RGBA", (WW, WH), (0, 0, 0, 0)); c = F["cliff"]; cliff.alpha_composite(img(c["file"]), (c["x"], c["y"]))
    # 탑: 껍데기 + 승강로 + 입구 + 불 켜진 칸들 + 승강기 칸
    tower = Image.new("RGBA", (WW, WH), (0, 0, 0, 0))
    t = F["tower_shell"]; tower.alpha_composite(img(t["file"]), (t["x"], t["y"]))
    sh = F["elevator_shaft"]; shi = img(sh["file"])
    for p in sh["place"]:
        tower.alpha_composite(shi, (p["x"], p["y"]))
    e = F["entrance"]; tower.alpha_composite(img(e["file"]), (e["x"], e["y"]))
    hz = L["hatch"]; tower.alpha_composite(img(hz["files"]["closed"]), (hz["x"], hz["y"]))
    PL = os.path.join(ART, "plates"); src = J["plates"]["src_rect"]; crop = (src[0], src[1], src[0] + src[2], src[1] + src[3])
    lit = ["quarters", "infirmary", "workshop", "storage", "quarters", "power", "greenhouse", None, "quarters"]
    warm = Image.new("RGBA", (WW, WH), (0, 0, 0, 0)); dw = ImageDraw.Draw(warm)
    for cobj, k in zip(J["cells"], lit):
        if not k:
            continue
        pl = Image.open(os.path.join(PL, f"room_plate_{k}_lit.png")).convert("RGBA").crop(crop)
        tower.alpha_composite(pl, (cobj["x"], cobj["y"]))
        dw.ellipse([cobj["x"] - 60, cobj["y"] - 50, cobj["x"] + cobj["w"] + 60, cobj["y"] + cobj["h"] + 50], fill=(255, 176, 90, 70))
    rc = J["rock_cells"][1]
    pl = Image.open(os.path.join(PL, "room_plate_greenhouse_lit.png")).convert("RGBA").crop(crop)
    cliff.alpha_composite(pl, (rc["x"], rc["y"]))           # 바위 굴 방은 절벽 레이어에(절벽과 함께 움직인다)
    car = L["car"]; ci = img(car["file"])
    tower.alpha_composite(ci, (int(J["shafts"][0]["x_center"] - car["anchor"][0]), int(J["tower"]["storeys"][1]["floor_y"] - car["anchor"][1])))
    # 칸 불빛이 바다로 번진다(탑 뒤 먼 레이어에 가산)
    g = warm.filter(ImageFilter.GaussianBlur(70))
    fa = np.asarray(far).astype(np.float32) / 255; ga = np.asarray(g).astype(np.float32) / 255
    a = ga[..., 3:4]; out = 1 - (1 - fa[..., :3]) * (1 - ga[..., :3] * a)
    far = Image.fromarray((np.concatenate([out, fa[..., 3:4]], -1) * 255).astype("uint8"), "RGBA")
    # 가까운 해초·기포
    near = Image.new("RGBA", (WW, WH), (0, 0, 0, 0)); fz = F["front"]; near.alpha_composite(img(fz["file"]), (fz["x"], fz["y"]))
    r = random.Random(9); dn = ImageDraw.Draw(near)
    for _ in range(90):                                   # 위로 오르는 기포(가까운 것)
        x, y, s = r.uniform(0, WW), r.uniform(200, WH), r.uniform(4, 13)
        dn.ellipse([x - s, y - s, x + s, y + s], outline=(190, 230, 225, 150), width=3)
        dn.ellipse([x - s * 0.45, y - s * 0.55, x - s * 0.15, y - s * 0.25], fill=(235, 250, 245, 170))
    return {"far": far, "cliff": cliff, "tower": tower, "near": near}


def logo_spot(name, size):
    """로고 자리 = 오른쪽 아래의 어두운 열린 물(유인 등불 아래, 입구 포드·철골과 겹치지 않게)"""
    W, H = size
    if name == "landscape":
        w = int(W * 0.38); return dict(file="lockup_horizontal_dark.png", x=W - w - int(W * 0.04), y=int(H * 0.56), w=w, align="bottom-right")
    w = int(W * 0.36); return dict(file="lockup_horizontal_dark.png", x=W - w - int(W * 0.025), y=140, w=w, align="top-right")   # 아래에 문구·버튼 130px 이상(클라이언트 규칙)


def main():
    WL = world_layers()
    meta = {"_note": "타이틀 화면. 레이어를 order 순으로 겹친다. 각 레이어는 화면보다 margin 만큼 크다(가운데 정렬로 놓고 parallax 배율로 천천히 움직인다: 오프셋 = 카메라 이동 × parallax). 생성 tools/gen_title.py, 기존 M5 레이어 조립, 생성 AI 없음",
           "order": ["far", "cliff", "tower", "near"], "parallax": PARALLAX, "margin_ratio": MARGIN,
           "logo_note": "로고는 기존 static/art/brand/zealandia/(로고 A 「가라앉은 대륙의 창」) 그대로. far 레이어에 로고 자리를 미리 어둡게 해 두었다",
           "motion_hint": "카메라를 6~10초 주기로 아주 천천히(가로 ±1.5%, 세로 ±1%) 흔든다. near 의 기포는 따로 위로 흘려도 좋다",
           "logo_dir": "static/art/brand/zealandia/", "crops": {}, "loading": {}}
    previews = {}
    for name, cfg in CROPS.items():
        W, H = cfg["size"]; sc = W / cfg["w"]; wh = H / sc
        mw, mh = int(W * MARGIN), int(H * MARGIN)
        box = (cfg["x0"] - mw / sc, cfg["y0"] - mh / sc, cfg["x0"] + cfg["w"] + mw / sc, cfg["y0"] + wh + mh / sc)
        files = {}
        comp = Image.new("RGBA", (W + 2 * mw, H + 2 * mh), (0, 0, 0, 255))
        for lid in meta["order"]:
            im = WL[lid].crop(tuple(int(v) for v in box)).resize((W + 2 * mw, H + 2 * mh), Image.LANCZOS)
            if lid == "far":                                   # 로고 자리를 살짝 어둡게(읽히게) — 가장자리는 부드럽게
                lg0 = logo_spot(name, (W, H)); lh = int(lg0["w"] * 300 / 860)
                cx, cy = lg0["x"] + lg0["w"] / 2 + mw, lg0["y"] + lh / 2 + mh
                yy, xx = np.mgrid[0:im.height, 0:im.width].astype(np.float32)
                k = np.exp(-(((xx - cx) / (lg0["w"] * 0.75)) ** 2 + ((yy - cy) / (lh * 1.1)) ** 2)) * 0.42
                a = np.asarray(im).astype(np.float32); a[..., :3] *= (1 - k)[..., None]
                im = Image.fromarray(a.astype("uint8"), "RGBA")
                fn = f"{name}_far.jpg"; im.convert("RGB").save(os.path.join(DST, fn), quality=86, optimize=True, progressive=True)
            else:
                fn = f"{name}_{lid}.png"; im.save(os.path.join(DST, fn), optimize=True)
            files[lid] = fn; comp.alpha_composite(im)
        lg = logo_spot(name, (W, H))
        meta["crops"][name] = dict(size=[W, H], layer_size=[W + 2 * mw, H + 2 * mh], layer_offset=[-mw, -mh], files=files,
                                   world_rect=[round(v) for v in box], logo=lg)
        # 미리보기(로고 포함)
        view = comp.crop((mw, mh, mw + W, mh + H))
        lo = Image.open(os.path.join(ART, "brand", "zealandia", lg["file"])).convert("RGBA")
        lo = lo.resize((lg["w"], int(lo.height * lg["w"] / lo.width)), Image.LANCZOS); lg["h"] = lo.height
        view.alpha_composite(lo, (lg["x"], lg["y"]))
        view.convert("RGB").save(os.path.join(ROOT, "art_raw", "maps", "m5", f"_title_{name}.png"))
        previews[name] = view
    # 로딩: 손등불이 천천히 켜지는 8프레임(소품 hand_lamp x4 + 번지는 빛)
    lamp = Image.open(os.path.join(ART, "props", "x4", "prop_hand_lamp.png")).convert("RGBA")
    N, FW, FH = 8, 192, 192
    sheet = Image.new("RGBA", (FW * N, FH), (0, 0, 0, 0))
    la = np.asarray(lamp).astype(np.float32)
    glass = (la[..., 0] > 200) & (la[..., 1] > 150) & (la[..., 3] > 0)        # 따뜻한 유리·불꽃 화소
    for i in range(N):
        t = i / (N - 1)
        fr = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
        g = Image.new("RGBA", (FW, FH), (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse([FW / 2 - 70, 30, FW / 2 + 70, 170], fill=(255, 190, 100, int(150 * t)))
        fr.alpha_composite(g.filter(ImageFilter.GaussianBlur(26)))
        a = la.copy(); k = 0.35 + 0.65 * t
        a[glass, :3] = a[glass, :3] * k + np.array([40, 30, 20]) * (1 - k)
        fr.alpha_composite(Image.fromarray(a.clip(0, 255).astype("uint8"), "RGBA"), ((FW - lamp.width) // 2, FH - lamp.height - 20))
        sheet.alpha_composite(fr, (i * FW, 0))
    sheet.save(os.path.join(DST, "loading_lantern.png"), optimize=True)
    meta["loading"] = dict(file="loading_lantern.png", frame_w=FW, frame_h=FH, frames=N,
                           use="진행률 p(0~1) → 프레임 round(p×7). 다 켜지면 마지막 프레임에서 빛만 살짝 숨쉬게(알파 0.9↔1, 2초)",
                           note="소품 손등불(prop_hand_lamp x4)이 꺼진 유리 → 따뜻하게 켜진다. 배경 투명, 어두운 바탕 위에")
    json.dump(meta, open(os.path.join(DST, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 접촉 시트
    from PIL import ImageFont
    f = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 18)
    land, ph = previews["landscape"], previews["phone"]
    S = Image.new("RGBA", (1280 + 40, 30 + 800 + 20 + 390 + 30 + 220), (16, 20, 22, 255)); d = ImageDraw.Draw(S)
    d.text((20, 6), "타이틀 — 가로 1280×800 · 폰 844×390 · 로딩 등불 8프레임 (기존 M5 레이어 조립, 생성 AI 없음)", font=f, fill=(232, 220, 191))
    S.alpha_composite(land, (20, 30)); S.alpha_composite(ph, (20, 30 + 800 + 20))
    lw = img2 = None
    ls = Image.open(os.path.join(DST, "loading_lantern.png")).convert("RGBA")
    bg = Image.new("RGBA", (ls.width, ls.height), (10, 30, 36, 255)); bg.alpha_composite(ls)
    bg = bg.resize((ls.width * 2 // 3, ls.height * 2 // 3), Image.LANCZOS)
    S.alpha_composite(bg, (20, 30 + 800 + 20 + 390 + 20))
    # 레이어 분해(폰 옆)
    x = 20 + 844 + 20; y = 30 + 800 + 20
    for lid in ("far", "cliff", "tower", "near"):
        fn = meta["crops"]["landscape"]["files"][lid]
        im = Image.open(os.path.join(DST, fn)).convert("RGBA").resize((100, 62), Image.LANCZOS)
        b2 = Image.new("RGBA", im.size, (60, 60, 60, 255)); b2.alpha_composite(im); S.alpha_composite(b2, (x, y)); d.text((x, y + 64), lid, font=f, fill=(240, 200, 120))
        x += 106
    out = os.path.join(ROOT, "docs", "reports", "bg_title_sheet.png"); S.convert("RGB").save(out, optimize=True)
    tot = sum(os.path.getsize(os.path.join(DST, x_)) for x_ in os.listdir(DST))
    print("title done", out, "KB", tot // 1024)


if __name__ == "__main__":
    main()
