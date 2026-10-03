"""M5 「절벽 끝에 기댄 가라앉은 탑」 — 게임 화면 배치 계약(layout.json)의 정본 숫자.

python tools/m5_layout.py   → static/art/maps/m5/layout.json
렌더 스크립트(tools/blender_m5_layers.py)도 이 파일을 import 해서 같은 숫자로 그린다.

축척: 82.5 px/m (도트 원화 27.5 px/m × 3). 주민 = front/p2 src 64px 셀을 NEAREST ×3 = 192 셀, 발선 180.
방 칸 = 방 플레이트(672×378)의 outer_rect(54,33)-(618,350) 을 **1:1 그대로** 잘라 쓴 564×317.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "static", "art", "maps", "m5", "layout.json")

PPM = 82.5
W, H = 5600, 3400                    # 세계 px (= 67.9 m × 41.2 m)

# 칸(플레이트 outer_rect 크롭)
CELL_W, CELL_H = 564, 317
PLATE_SRC = (54, 33, 564, 317)       # drawImage(plate, sx, sy, sw, sh, cell.x, cell.y, 564, 317)
FLOOR_IN_CELL = 315 - 33             # 282: 플레이트 floor_y(315) 를 칸 좌표로
STAND_IN_CELL = (138 - 54, 534 - 54) # 84, 480
LAMP_IN_CELL = (336 - 54, 110 - 33)  # 282, 77

# 가로 구성(왼→오): 절벽 | 바위 칸 | 바위 통로 | 왼 외벽 | 칸0 | 벽 | 승강로A | 벽 | 칸1 | 벽 | 승강로B | 벽 | 칸2 | 오른 외벽 | 심연
SHAFT_W, WALL, FACADE = 150, 16, 200
TOWER_X0 = 1064
SEC_X0 = TOWER_X0 + FACADE                                   # 1264 단면 시작
COL_X = [SEC_X0, SEC_X0 + CELL_W + 2 * WALL + SHAFT_W]
COL_X.append(COL_X[1] + CELL_W + 2 * WALL + SHAFT_W)         # 1264, 2010, 2756
SHAFT_X = [COL_X[0] + CELL_W + WALL, COL_X[1] + CELL_W + WALL]   # 1844, 2590 (왼쪽 끝)
SEC_X1 = COL_X[2] + CELL_W                                   # 3320
TOWER_X1 = SEC_X1 + FACADE                                   # 3520
ROCK_X = 380                                                 # 바위 칸 x (380..944)

# 세로: 돔(홀) 아래로 층 0..4
SLAB = 46
PITCH = CELL_H + SLAB                                        # 363 px = 층 하나
ROOF_Y = 1160                                                # 지붕 윗면 = 홀 바닥(발선)
STOREY0_Y = ROOF_Y + SLAB                                    # 1206 = 깊이 0 m
N_STOREYS = 5
STOREY_Y = [STOREY0_Y + k * PITCH for k in range(N_STOREYS)]
FLOOR_Y = [y + FLOOR_IN_CELL for y in STOREY_Y]
ROCK_STOREYS = (0, 1, 2)

# 돔(꼭대기 유리 아트리움)
DOME = dict(x=SEC_X0, y=760, w=SEC_X1 - SEC_X0, h=ROOF_Y - 760)
DOME_GLASS = dict(cx=(SEC_X0 + SEC_X1) // 2, base_y=ROOF_Y, rx=1080, ry=560)   # 반타원 유리 껍질

# 깊이 규약(base.js 와 같은 식): 층 하나 = 60 m. 깊이 0 m = 층 0 칸의 윗변
DEPTH_PER_FLOOR = 60
M2PX = PITCH / DEPTH_PER_FLOOR                               # 6.05 px/m(게임 깊이 m, 그림 축척 아님)
def depth_y(m): return round(STOREY0_Y + m * M2PX, 1)
TRENCH_Y = depth_y(180)                                      # 2295 = 층 3 윗변
DARK_FULL_Y = 3060                                           # 이 아래로 탑 몸통이 검게 잠긴다

CLIFF_TOP_Y = 560                                            # 절벽 꼭대기 턱(왼쪽 끝 기준, 탑 쪽으로 내려간다)
CLIFF_BOTTOM_Y = 2440                                        # 절벽 밑동 — 해구 문턱 바로 아래에서 끊긴다
ABYSS = dict(x=TOWER_X1 + 40, y=380, w=W - (TOWER_X1 + 40), h=H - 380)
LURE = dict(x=4820, y=1520)                                  # 유인 등불(철골 끝에 매달림)
GIRDER = [(TOWER_X1 - 40, 1120), (4280, 860), (4820, 900)]

# S12-F 입구(에어락 포드) — 돔 오른쪽 끝에 덧붙인 가압 포드. 서버 칸이 아니라 홀의 일부다.
# 철골 뿌리(3480,1120)는 포드 뒤로 숨고, 포드 오른벽(y≈945)에서 심연으로 뻗어 나간다(포드에 박힌 크레인 팔).
POD = dict(x0=3372, x1=4020, y0=820, floor_y=ROOF_Y, y1=ROOF_Y + 26, wall=24)
POD_IN = dict(x=POD["x0"] + POD["wall"], y=POD["y0"] + 32, w=(POD["x1"] - POD["wall"]) - (POD["x0"] + POD["wall"]),
              h=ROOF_Y - (POD["y0"] + 32))                     # 대기 공간 안쪽 = (3396, 852, 600, 308)
INNER_DOOR = dict(x=POD["x0"] + POD["wall"] // 2, y0=1004, y1=ROOF_Y)   # 홀 ↔ 포드 문(돔 유리 밑단)
HATCH = dict(x=POD["x1"] - POD["wall"] // 2, y0=1004, y1=ROOF_Y)        # 바깥 해치(오른벽)
PLATFORM = dict(x0=POD["x1"], x1=4210, y=ROOF_Y)               # 해치 밖 격자 발판
LADDER = dict(x=4160, y0=ROOF_Y + 14, y1=1480)                 # 발판에서 물속으로 내려가는 사다리


def build():
    cells = []
    n = 0
    for s in range(N_STOREYS):
        for c in range(3):
            x, y = COL_X[c], STOREY_Y[s]
            cells.append(dict(id=n, kind="tower", storey=s, col=c, x=x, y=y, w=CELL_W, h=CELL_H,
                              floor_y=y + FLOOR_IN_CELL, depth_m=s * DEPTH_PER_FLOOR,
                              stand_x=[x + STAND_IN_CELL[0], x + STAND_IN_CELL[1]],
                              lamp=[x + LAMP_IN_CELL[0], y + LAMP_IN_CELL[1]],
                              shaft=("A" if c <= 1 else "B") if c != 1 else "AB"))
            n += 1
    rock = []
    for i, s in enumerate(ROCK_STOREYS):
        x, y = ROCK_X, STOREY_Y[s]
        fy = y + FLOOR_IN_CELL
        rock.append(dict(id=f"r{i}", kind="rock", storey=s, x=x, y=y, w=CELL_W, h=CELL_H, floor_y=fy,
                         depth_m=s * DEPTH_PER_FLOOR,
                         stand_x=[x + STAND_IN_CELL[0], x + STAND_IN_CELL[1]],
                         lamp=[x + LAMP_IN_CELL[0], y + LAMP_IN_CELL[1]],
                         tunnel=dict(x=x + CELL_W, y=fy - 196, w=SEC_X0 - (x + CELL_W), h=206, floor_y=fy,
                                     connects_to=s * 3,
                                     note="같은 층 발선 위를 걸어서 칸 0(왼쪽 열)을 지나 승강로 A 로 간다")))
    shafts = []
    for sid, sx in zip("AB", SHAFT_X):
        stops = [dict(floor="hall", door_y=ROOF_Y)] + [dict(floor=s, door_y=FLOOR_Y[s]) for s in range(N_STOREYS)]
        shafts.append(dict(id=sid, x_center=sx + SHAFT_W // 2, x=sx, w=SHAFT_W,
                           top_y=DOME["y"] + 40, bottom_y=STOREY_Y[-1] + CELL_H,
                           stops=stops, serves_cols=[0, 1] if sid == "A" else [1, 2]))
    return {
        "_note": "S12-A M5 게임 화면 배치 계약. 좌표는 전부 세계 px(좌상단 0,0), 82.5 px/m. 정본 생성기 tools/m5_layout.py",
        "scale": {"px_per_m": PPM, "src_px_per_m": 27.5, "char_scale": 3,
                  "char": {"set": "static/art/chars/front/p2", "room_scale": 3, "room_cell": 192, "room_baseline": 180,
                           "draw": "src 64 셀을 NEAREST ×3. 셀 좌상단 = (발 x − 96, floor_y − 180)"}},
        "world": {"w": W, "h": H, "w_m": round(W / PPM, 2), "h_m": round(H / PPM, 2)},
        "plates": {"dir": "static/art/plates", "src_rect": list(PLATE_SRC), "scale": 1,
                   "rule": "플레이트를 키우거나 줄이지 않는다. outer_rect(54,33,564,317)를 잘라 칸에 1:1로 놓는다. room_flood.png·damage_crack*.png 도 같은 src_rect 로 자른다",
                   "floor_in_cell": FLOOR_IN_CELL, "stand_in_cell": list(STAND_IN_CELL), "lamp_in_cell": list(LAMP_IN_CELL)},
        "tower": {"x0": TOWER_X0, "x1": TOWER_X1, "section_x0": SEC_X0, "section_x1": SEC_X1,
                  "facade_w": FACADE, "wall_w": WALL,
                  "columns": [{"col": c, "x0": COL_X[c], "x1": COL_X[c] + CELL_W} for c in range(3)],
                  "storeys": [{"storey": s, "top_y": STOREY_Y[s], "floor_y": FLOOR_Y[s], "bottom_y": STOREY_Y[s] + CELL_H,
                               "depth_m": s * DEPTH_PER_FLOOR} for s in range(N_STOREYS)],
                  "slab_h": SLAB, "pitch_y": PITCH, "roof_y": ROOF_Y},
        "cells": cells,
        "cell_numbering": "id = storey*3 + col (위→아래, 왼→오). 바위 칸은 별도 id r0..r2",
        "rock_cells": rock,
        "shafts": shafts,
        "shaft_car": {"w": 138, "h": 190, "anchor": "아래 가운데 = 정류장 door_y", "sprite": "elevator_car.png",
                      "cap_hint": 3},
        "shaft_recommendation": "승강로 둘(A: 칸0·칸1 사이, B: 칸1·칸2 사이). 모든 칸이 승강로에 바로 붙는다. 주민 10명 이상이면 하나로는 줄이 길다. 둘 다 홀~층4 전 정류장. 갈아타기는 필요 없다(같은 층에서 걸어서 옮겨도 된다)",
        "dome": dict(DOME, floor_y=ROOF_Y, note="홀 = 배치되지 않은 주민이 서는 곳. 발선 = floor_y"),
        "dome_glass": DOME_GLASS,
        "abyss": dict(ABYSS, note="열린 심연. 위협은 오른쪽 끝(x=W)에서 들어와 탑 오른 외벽(x=tower.x1) 쪽으로 다가온다"),
        "lure_lamp": dict(LURE, girder=[list(p) for p in GIRDER]),
        "entrance": {
            "_note": "S12-F 입구 = 에어락 포드. 서버 칸이 아니다(홀의 일부). 바깥 사람이 들어오고, 탐사대가 나가고 돌아오고, 배치 안 된 주민이 여기서 기다리며 소소한 일을 한다",
            "pod": POD,
            "waiting_area": dict(POD_IN, floor_y=ROOF_Y),
            "spots": [
                {"id": "e0", "x": 3436, "floor_y": ROOF_Y, "pose": "lean_wall", "face": 1, "note": "안쪽 문 옆 벽 쪽지 앞"},
                {"id": "e1", "x": 3524, "floor_y": ROOF_Y, "pose": "sit_bench", "face": 1, "seat_y": 1118},
                {"id": "e2", "x": 3616, "floor_y": ROOF_Y, "pose": "sit_bench", "face": -1, "seat_y": 1118},
                {"id": "e3", "x": 3708, "floor_y": ROOF_Y, "pose": "window", "face": 1, "note": "둥근 창(3708, 960)으로 바깥을 본다(등을 보여도 된다)"},
                {"id": "e4", "x": 3800, "floor_y": ROOF_Y, "pose": "gear_rack", "face": 1, "note": "오른쪽 장비 걸이(3830~3930)의 잠수복 손질"},
                {"id": "e5", "x": 3952, "floor_y": ROOF_Y, "pose": "lean_wall", "face": 1, "note": "해치 옆 공기통 앞 — 탐사대를 기다린다"},
            ],
            "inner_door": INNER_DOOR,
            "hatch": HATCH,
            "platform": PLATFORM,
            "ladder": LADDER,
            "swim_out": [[HATCH["x"], ROOF_Y], [4110, ROOF_Y], [LADDER["x"], 1200], [LADDER["x"], 1460], [4300, 1600], [4700, 1780], [5300, 1900], [5650, 1950]],
            "swim_back": [[5650, 1300], [5200, 1260], [4600, 1250], [4300, 1320], [LADDER["x"], 1420], [LADDER["x"], 1200], [4110, ROOF_Y], [HATCH["x"], ROOF_Y]],
            "arrival": [[5650, 1380], [4900, 1400], [4450, 1330], [LADDER["x"], 1400], [LADDER["x"], 1200], [4110, ROOF_Y], [HATCH["x"], ROOF_Y], [3800, ROOF_Y]],
            "path_note": "x 가 POD x1(4020)보다 크면 물속 = 헤엄(잠수복). 사다리 구간(x=4160, y 1200~1460)은 오르내림. 해치 통과 때 해치 열림 → 물방울 스프라이트",
            "hall_link": {"floor_y": ROOF_Y, "nodes": [[2665, ROOF_Y], [3130, ROOF_Y], [INNER_DOOR["x"], ROOF_Y], [3436, ROOF_Y]],
                          "elevator_stops": [{"shaft": "A", "x": 1919, "door_y": ROOF_Y}, {"shaft": "B", "x": 2665, "door_y": ROOF_Y}],
                          "note": "홀 발선(1160) 그대로 걸어서 이어진다. 승강로 B 홀 정류장에서 안쪽 문까지 727px(8.8 m). A 에서는 1473px"},
        },
        "cliff": {"top_y": CLIFF_TOP_Y, "bottom_y": CLIFF_BOTTOM_Y, "x1_at_tower": TOWER_X0,
                  "note": "절벽 꼭대기 턱은 왼쪽 위에 보인다. 절벽은 해구 문턱 바로 아래에서 끝나고 탑만 더 내려간다"},
        "depth": {"depth_per_floor_m": DEPTH_PER_FLOOR, "px_per_depth_m": round(M2PX, 4),
                  "y_of_0m": STOREY0_Y, "formula": "y = 1206 + depth_m * 6.05  (base.js: M2PX = FLOOR_PITCH / DEPTH_PER_FLOOR, FLOOR_PITCH 를 363 으로)",
                  "zones_m": [0, 180, 210], "zones_y": [depth_y(0), depth_y(180), depth_y(210)],
                  "trench_y": TRENCH_Y, "dark_full_y": DARK_FULL_Y,
                  "base_js_mapping": "base.js 26~32행 ZONES 는 '깊이 m × M2PX' 이고 y=0 이 돔 층 윗변이었다. 여기서는 y_of_0m(1206)을 더하면 같은 식이다. ROOM_H→317, FLOOR_GAP→46, FLOOR_PITCH→363, floorSlots→3, DOME_FLOOR 층 = storey 0"},
        "layers": {"_note": "S12-A 2단계 산출물. 모두 세계 좌표 (x,y)에 놓는다. scale 이 2 면 2배로 키워 놓는다(매끈 보간)", "files": []},
        "phone": {
            "viewport_css": [844, 390],
            "default_view": {"zoom": 0.45, "cx": 3350, "cy": 1290,
                             "shows_world": [2412, 857, 4288, 1724],
                             "why": "안팎 경계가 화면 가운데: 왼쪽에 칸1·승강로B·칸2(사람과 등불), 오른쪽에 돔 오른쪽 끝·외벽 창·철골 뿌리·열린 심연. 주민 키 132px × 0.45 ≈ 59 CSS px(역할 판독 하한 근처)"},
            "zoom_min": 0.115, "zoom_min_why": "390 / 3400 — 세계 높이 전체",
            "zoom_max": 1.0, "zoom_max_why": "세계 1px = CSS 1px. 그 이상은 플레이트가 흐려진다",
            "integer_note": "주민은 세계에서 이미 ×3 이다. 화면 배율은 소수여도 되지만 도트를 선명하게 하려면 사람만 따로 (×3×zoom×DPR 을 정수로 반올림) 그리는 것을 권한다",
            "first_open": "처음 열 때는 홀(돔)과 층 0 이 같이 보이게: zoom 0.45, cx 2292, cy 1180 도 후보. 습격 때는 cx 를 4000 쪽으로 옮겨 심연을 넓게"},
    }


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    d = build()
    if os.path.exists(OUT):          # 2단계가 채운 layers·phone 은 보존
        old = json.load(open(OUT, encoding="utf-8"))
        for k in ("layers",):
            if old.get(k):
                d[k] = old[k]
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", OUT, len(d["cells"]), "cells")
