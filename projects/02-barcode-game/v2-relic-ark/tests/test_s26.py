"""S26 서버 검증 — 물 빼기(깊이별 펌프 비용, 되찾기 절반, 모자라면 400+목록, 잃는 것 없음) · 하루 소비(1인당 식량·물 0.6, 굶으면 사기 −1/일).

실행:  python tests/test_s26.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

os.environ["RELIC_DEV"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import server as S  # noqa: E402
S.CALENDAR_ENFORCE = False
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t26.db"
S.DEV_MODE = True
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []
S.now_hour = lambda: 10
D = S._ECON_ALL["drain"]["by_depth_m"]


def ok(cond, msg):
    RESULTS.append((bool(cond), msg))
    print(("OK   " if cond else "FAIL ") + msg)


def get(path, code=200):
    r = C.get(path)
    assert r.status_code == code, (path, r.status_code, r.text)
    return r.json()


def set_res(uid, **kw):
    st = S.load_state(uid)
    st["resources"].update(kw)
    S.save_state(uid, st)


def t_drain_costs():
    ok([S.slot_depth_m(i) for i in range(10)] == [0, 0, 0, 0, 60, 60, 120, 120, 180, 180], "칸 깊이 0/60/120/180")
    st = S.new_state("x")
    ok(S.drain_cost(st, 3) == {} and S.drain_cost(st, 5) == D["60"] and S.drain_cost(st, 9) == D["180"], "돔 층 없음, 60·180m 데이터 그대로")
    rc = S.drain_cost(st, 9, reclaim=True)
    ok(rc == {k: max(1, math.ceil(v * 0.5)) for k, v in D["180"].items() if v}, f"되찾기 절반 올림 {rc}")
    ok(S.drain_cost(st, -1) == {}, "문간 증설(-1)은 물 빼기 없음")


def t_build():
    uid = "dev_s26_build"
    a = get(f"/api/ark?uid={uid}")
    ok(a["drain_cells"]["5"]["drain_cost"] == D["60"] and "2" not in a["drain_cells"], "drain_cells: 빈 칸만, 방 있는 칸 없음")
    bo = a["build_options"]["quarters"]
    ok(bo["by_slot"]["5"]["drain_cost"] == D["60"] and bo["cost"] != bo["by_slot"]["5"]["drain_cost"], "build_options 칸마다 drain_cost 따로")
    # 모자라면 400 + 목록, 아무것도 잃지 않는다
    set_res(uid, food=50, water=50, parts=50, scrap=50, cloth=50, knowledge=50, power=0)
    before = dict(S.load_state(uid)["resources"])
    r = C.post("/api/ark/build", json={"uid": uid, "room_id": "quarters", "slot": 5})
    j = r.json()
    ok(r.status_code == 400 and j["missing"] == {"power": D["60"]["power"]} and j["drain_cost"] == D["60"] and "전력" in j["detail"],
       f"전력 모자람 → 400 {j.get('missing')}")
    ok(S.load_state(uid)["resources"] == before, "모자라면 아무것도 잃지 않는다")
    # 돔 층(0m)은 방 비용만
    cost = S.priced(S.load_state(uid), S.ROOMS["quarters"]["cost"])[0]
    C.post("/api/ark/build", json={"uid": uid, "room_id": "quarters", "slot": 3})
    st = S.load_state(uid)
    ok(all(st["resources"][k] == before[k] - cost.get(k, 0) for k in before if k in cost), "0m 칸: 방 건설비만")
    # 60m: 방 + 물 빼기
    set_res(uid, power=10)
    b2 = dict(S.load_state(uid)["resources"])
    cost2 = S.priced(S.load_state(uid), S.ROOMS["storage"]["cost"])[0]
    r = C.post("/api/ark/build", json={"uid": uid, "room_id": "storage", "slot": 5})
    st = S.load_state(uid)
    want = {k: b2.get(k, 0) - cost2.get(k, 0) - D["60"].get(k, 0) for k in set(cost2) | set(D["60"])}
    ok(r.status_code == 200 and all(st["resources"][k] == v for k, v in want.items()), f"60m 칸: 방 {cost2} + 물 빼기 {D['60']}")
    # 되찾기: 물 찬 칸은 절반
    room = next(x for x in st["rooms"] if x["slot"] == 5)
    room.update({"flooded": True, "flooded_from": {"id": "storage", "level": 1}})
    S.save_state(uid, st)
    a = get(f"/api/ark?uid={uid}")
    ok(a["drain_cells"]["5"]["reclaim"] and a["drain_cells"]["5"]["drain_cost"] == S.drain_cost(st, 5, reclaim=True), "물 찬 칸 = 되찾기 절반")
    set_res(uid, power=10, food=50, parts=50)
    b3 = dict(S.load_state(uid)["resources"])
    C.post("/api/ark/build", json={"uid": uid, "room_id": "storage", "slot": 5})
    st = S.load_state(uid)
    hd = S.drain_cost(st, 5, reclaim=True)
    ok(st["resources"]["power"] == b3["power"] - hd["power"], f"되찾기 펌프 {hd}")
    # 문간 에어락은 물 빼기 없음
    set_res(uid, parts=50, cloth=50, power=0)
    r = C.post("/api/ark/build", json={"uid": uid, "room_id": "airlock", "slot": -1})
    ok(r.status_code == 200, "문간 에어락(-1)은 전력 없이도")


def t_consumption():
    uid = "dev_s26_eat"
    get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    n = len(st["residents_list"])
    st["rooms"] = []                                   # 생산 없이 소비만 본다
    st["resources"].update({"food": 20, "water": 20})
    st["last_tick"] -= 3 * S.PRODUCTION_TICK_SEC
    S.tick_production(st)
    ok(st["resources"]["food"] == 20 - int(0.6 * n) and st["resources"]["water"] == 20 - int(0.6 * n),
       f"하루(3틱) 주민 {n}명 → 식량·물 −{int(0.6 * n)}(소수는 쌓인다)")
    st["last_tick"] -= 3 * S.PRODUCTION_TICK_SEC * 2
    for _ in range(2):
        st["last_tick"] = time.time() - 3 * S.PRODUCTION_TICK_SEC
        S.tick_production(st)
    ok(st["resources"]["food"] == 20 - int(round(0.6 * n * 3)), f"사흘 → −{int(round(0.6 * n * 3))}(0.6×{n}×3)")
    st["resources"].update({"food": 0, "water": 0})
    m0 = st["resources"]["morale"] + float(st.get("morale_frac") or 0)
    nres = len(st["residents_list"])
    st["last_tick"] = time.time() - 3 * S.PRODUCTION_TICK_SEC
    S.tick_production(st)
    ok(st["resources"]["food"] == 0 and len(st["residents_list"]) == nres and
       abs(st["resources"]["morale"] + float(st.get("morale_frac") or 0) - (m0 - 1)) < 1e-6, "굶어도 0에서 멈추고 아무도 안 떠난다, 사기 −1/일")
    a = get(f"/api/ark?uid={uid}")
    ok(a["consumption"]["on"] and a["consumption"]["food_per_day"] == round(0.6 * n, 2), f"/api/ark.consumption {a['consumption']}")


TESTS = [t_drain_costs, t_build, t_consumption]

if __name__ == "__main__":
    for t in TESTS:
        print(f"\n## {t.__name__}")
        try:
            t()
        except Exception:
            traceback.print_exc()
            RESULTS.append((False, f"{t.__name__} 예외"))
    n = len(RESULTS)
    f = [m for c, m in RESULTS if not c]
    print(f"\n합계 {n} · 통과 {n - len(f)} · 실패 {len(f)}")
    for m in f:
        print("  FAIL", m)
    sys.exit(1 if f else 0)
