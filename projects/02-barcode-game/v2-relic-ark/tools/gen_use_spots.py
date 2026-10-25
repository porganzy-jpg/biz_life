"""S36 「건넨 물건을 방에서 쓴다」 — 방 플레이트마다 쓰는 자리 2개 + 서서 쓰는 자리 2개.

python tools/gen_use_spots.py   → decor_meta.json "use_spots" + docs/reports/bg_S36_sheet.png

좌표는 칸 좌표(564×317). item = 소품 아래 가운데(34×30 1배 소품 기준), stand = 사람 발 가운데(발선 282). 물건이 사람에 가리지 않게 물건 옆 52px(몸 반폭 ≈32 + 여유).
겹치지 않게: keepsake_spots(잠자리 물건) · 장식 자리 소품(slot_positions_in_cell) 영역과 겹치면 실패로 센다.
"""
import os, json
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DECOR = os.path.join(ROOT, "static", "art", "decor"); PLATES = os.path.join(ROOT, "static", "art", "plates")
PROPS = os.path.join(ROOT, "static", "art", "props")
FLOOR = 282
IW, IH = 34, 30          # 소품 1배 크기(아래 가운데 기준)

USE = {   # 플레이트 → [ {kind, x, y, stand_x, note} ×2 ]
    "quarters":   [dict(kind="shelf", x=448, y=203, stand_x=498, note="오른쪽 책장 가운데 칸"),
                   dict(kind="crate", x=381, y=246, stand_x=316, note="책상 아래 낮은 궤짝 위")],
    "storage":    [dict(kind="shelf", x=200, y=189, stand_x=252, note="벽 선반 아래 칸 왼쪽"),
                   dict(kind="stack", x=462, y=147, stand_x=410, note="오른쪽 높은 짐 더미 꼭대기")],
    "workshop":   [dict(kind="crate", x=130, y=209, stand_x=182, note="작업대 왼쪽 흰 상자 위"),
                   dict(kind="floor", x=400, y=276, stand_x=348, note="작업대 오른쪽 끝 바닥 — 의자 옆 자리")],
    "infirmary":  [dict(kind="shelf", x=432, y=177, stand_x=372, note="약 선반 아래 칸"),
                   dict(kind="crate", x=442, y=253, stand_x=494, note="선반 밑 낮은 상자 위")],
    "power":      [dict(kind="ledge", x=380, y=146, stand_x=328, note="오른쪽 장 윗면"),
                   dict(kind="ledge", x=200, y=174, stand_x=252, note="왼쪽 기계 윗면")],
    "greenhouse": [dict(kind="shelf", x=300, y=146, stand_x=248, note="가운데 화분 선반"),
                   dict(kind="shelf", x=440, y=206, stand_x=388, note="아래 화분 선반 오른쪽")],
}
ROOM_TO_PLATE = {"quarters": "quarters", "decoder": "quarters", "pantry": "storage", "storage": "storage", "lounge": "storage",
                 "infirmary": "infirmary", "bath": "infirmary", "workshop": "workshop", "greenhouse": "greenhouse", "well": "greenhouse",
                 "generator": "power", "power": "power"}


def boxes_keep(meta, plate):
    return [(s["x"] - IW / 2, s["y"] - IH, s["x"] + IW / 2, s["y"]) for s in meta["keepsake_spots"]["by_plate"][plate]]


def boxes_slots(meta):
    sz = {s["id"]: s["size"] for s in meta["slots"]}
    out = []
    for sid, lst in meta["slot_positions_in_cell"].items():
        if sid == "note":
            continue
        for x, y in lst:
            w, h = sz[sid]; out.append((x, y, x + w, y + h))
    return out


def hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def main():
    mp = os.path.join(DECOR, "decor_meta.json"); meta = json.load(open(mp, encoding="utf-8"))
    report = {}
    for plate, lst in USE.items():
        ks, sl = boxes_keep(meta, plate), boxes_slots(meta)
        bad = []
        for i, u in enumerate(lst):
            b = (u["x"] - IW / 2, u["y"] - IH, u["x"] + IW / 2, u["y"])
            bad += [f"use{i}×keepsake" for k in ks if hit(b, k)] + [f"use{i}×slot" for s in sl if hit(b, s)]
        b0 = (lst[0]["x"] - IW / 2, lst[0]["y"] - IH, lst[0]["x"] + IW / 2, lst[0]["y"]); b1 = (lst[1]["x"] - IW / 2, lst[1]["y"] - IH, lst[1]["x"] + IW / 2, lst[1]["y"])
        if hit(b0, b1): bad.append("use0×use1")
        report[plate] = bad
    print("겹침:", report)
    meta["use_spots"] = {
        "_note": "S36: 건넨 물건을 주인이 하루 한 번 쓰는 자리. 칸 좌표(564×317). item = 물건(by_subtype 소품 34×30 1배) 아래 가운데, "
                 "stand = 쓰는 사람이 서는 발 가운데(y = 282). keepsake_spots·장식 자리 소품과 겹치지 않음(생성기가 셈)",
        "by_plate": {p: [dict(kind=u["kind"], item=[u["x"], u["y"]], stand=[u["stand_x"], FLOOR], note=u["note"]) for u in lst] for p, lst in USE.items()},
        "room_to_plate": ROOM_TO_PLATE,
        "room_to_plate_note": "base_core.js PLATE_OF 와 같은 대응. 플레이트를 함께 쓰는 방(decoder=quarters 등)은 같은 자리를 쓴다",
        "overlap_check": report,
    }
    json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 접촉 시트: 플레이트 위에 keepsake(분홍 테)·장식 자리(하늘 테)·쓰는 자리(실제 소품) + 서는 사람
    f = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 15)
    demo = ["prop_white_carton", "prop_hand_lamp", "prop_candy_jar", "prop_bean_tin", "prop_rolled_map", "prop_cloth_bag"]
    roles = ["cook", "scholar", "engineer", "medic", "farmer", "trader"]
    S = Image.new("RGBA", (2 * (564 + 20) + 20, 3 * (317 + 40) + 50), (20, 18, 16, 255)); d = ImageDraw.Draw(S)
    d.text((16, 12), "S36 쓰는 자리 — 노란 = 쓰는 자리(소품) · 초록 발 = 서는 자리 · 분홍 = 잠자리 물건(keepsake) · 하늘 = 장식 자리 소품", font=f, fill=(232, 220, 191))
    for i, (plate, lst) in enumerate(USE.items()):
        p = Image.open(os.path.join(PLATES, f"room_plate_{plate}_lit.png")).convert("RGBA").crop((54, 33, 618, 350))
        dp = ImageDraw.Draw(p)
        for b in boxes_slots(meta):
            dp.rectangle(b, outline=(120, 210, 230, 255), width=2)
        for b in boxes_keep(meta, plate):
            dp.rectangle(b, outline=(240, 90, 200, 255), width=2)
        for j, u in enumerate(lst):
            pr = Image.open(os.path.join(PROPS, demo[(i + j) % len(demo)] + ".png")).convert("RGBA")
            p.alpha_composite(pr, (int(u["x"] - IW / 2), int(u["y"] - IH)))
            dp.rectangle((u["x"] - IW / 2, u["y"] - IH, u["x"] + IW / 2, u["y"]), outline=(255, 210, 80, 255), width=2)
            sh = Image.open(os.path.join(ROOT, "static", "art", "chars", "front", "p2", "src", roles[(i + j) % 6] + ".png")).convert("RGBA")
            ce = sh.crop((0, 0, 64, 64)).resize((192, 192), Image.NEAREST)
            p.alpha_composite(ce, (u["stand_x"] - 96, FLOOR - 180))
            dp.ellipse((u["stand_x"] - 7, FLOOR - 4, u["stand_x"] + 7, FLOOR + 4), fill=(90, 220, 110, 255))
            dp.text((u["x"] - 6, u["y"] - IH - 16), str(j + 1), fill=(255, 230, 120, 255))
        x = 20 + (i % 2) * (564 + 20); y = 46 + (i // 2) * (317 + 40)
        S.alpha_composite(p, (x, y))
        d.text((x, y + 320), f"{plate} — 겹침 {len(report[plate])}건", font=f, fill=(240, 200, 120))
    out = os.path.join(ROOT, "docs", "reports", "bg_S36_sheet.png"); S.convert("RGB").save(out, optimize=True)
    print("sheet", out)


if __name__ == "__main__":
    main()
