"""S14-A 서버 검증 — 능력치가 생산을 바꾼다 (docs/API_S13.md §S14).

실행:  python tests/test_s14_server.py   (임시 DB + TestClient, 실제 relic_ark.db 를 건드리지 않는다)
수치는 전부 data/balance/stakes.json 에서 읽는다. 스탯은 테스트가 직접 정해 넣는다(굴림에 기대지 않는다).
"""
from __future__ import annotations

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
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t14.db"
S.DEV_MODE = True
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []


def ok(cond, msg):
    RESULTS.append((bool(cond), msg))
    print(("OK   " if cond else "FAIL ") + msg)


P = S.stat_production_params()
RS = S.stk("stat_production.room_stat")
SM = S.stk("staffing.staff_mult")


def clamp(x):
    return max(float(P["min_mult"]), min(float(P["max_mult"]), x))


def setup(uid, stats_by_role: dict, rooms=(("greenhouse", 3), ("workshop", 4))) -> dict:
    """시작 3인 + 방 몇 개. 스탯을 정해 넣는다(나머지 스탯은 5)."""
    C.get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    for rid, slot in rooms:
        st["rooms"].append({"id": rid, "slot": slot, "built": time.time(), "level": 1})
    for r in st["residents_list"]:
        base = {"hand": 5, "eye": 5, "breath": 5, "nerve": 5}
        base.update(stats_by_role.get(r["role"], {}))
        r["stats"] = base
        r["imprints"] = []
        r["injured"] = False
    st["stations"] = {}
    S.save_state(uid, st)
    return st


def who(st, role):
    return next(r for r in st["residents_list"] if r["role"] == role)


def place(uid, rid, slot):
    r = C.post("/api/ark/station", json={"uid": uid, "resident_id": rid, "slot": slot})
    assert r.status_code == 200, r.text
    return r.json()


def t_room_stat_canon():
    """방→능력치 정본이 /api/ark stats_meta 에 온다(화면 ROOM_STAT 사본을 대신)."""
    a = C.get("/api/ark?uid=dev_s14_meta").json()
    rs = a["stats_meta"]["room_stat"]
    want = {k: v for k, v in RS.items() if not k.startswith("_") and k in S.ROOMS}
    ok(rs == want, f"stats_meta.room_stat = stakes 표 ({len(rs)}방)")
    ok(set(a["stats_meta"]["stat_production"]) >= {"center", "per_point", "min_mult", "max_mult", "aggregate"},
       f"stats_meta.stat_production {a['stats_meta']['stat_production']}")


def t_favoured_vs_wrong():
    """같은 사람이 맞는 방 vs 틀린 방 — 기대 배율."""
    uid = "dev_s14_fav"
    # 기술자: 손 9, 숨 2. 공방(hand) vs 온실(breath)
    st = setup(uid, {"engineer": {"hand": 9, "breath": 2}})
    eng = who(st, "engineer")
    ok(RS.get("workshop") == "hand" and RS.get("greenhouse") == "breath", "전제: 공방=손, 온실=숨")
    a = place(uid, eng["id"], 4)["production"]["4"]
    exp_good = clamp(1 + float(P["per_point"]) * (9 - float(P["center"])))
    ok(abs(a["stat_mult"] - round(exp_good, 4)) < 1e-9 and abs(a["mult"] - round(SM[1] * exp_good, 3)) < 1e-9,
       f"공방(손 9): stat_mult {a['stat_mult']} (기대 {exp_good:.4f}), mult {a['mult']}")
    ok(a["per_person"][0]["id"] == eng["id"] and a["per_person"][0]["value"] == 9, f"per_person {a['per_person']}")
    b = place(uid, eng["id"], 3)["production"]["3"]
    exp_bad = clamp(1 + float(P["per_point"]) * (2 - float(P["center"])))
    ok(abs(b["stat_mult"] - round(exp_bad, 4)) < 1e-9, f"온실(숨 2): stat_mult {b['stat_mult']} (기대 {exp_bad:.4f})")
    ok(a["stat_mult"] > 1.0 > b["stat_mult"], "맞는 방 > 1 > 틀린 방")
    # 상한·하한
    st = S.load_state(uid)
    for r in st["residents_list"]:
        r["stats"]["hand"] = 10
    st["stations"] = {r["id"]: 4 for r in st["residents_list"]}
    S.save_state(uid, st)
    c = C.get(f"/api/ark?uid={uid}").json()["production"]["4"]
    ok(c["stat_mult"] == min(float(P["max_mult"]), round(1 + float(P["per_point"]) * 5, 4)),
       f"상한: 손 10 셋 → {c['stat_mult']} (max {P['max_mult']})")
    # 실제 정산도 같은 배율을 쓴다
    st = S.load_state(uid)
    st["stations"] = {eng["id"]: 4}
    st["last_tick"] = time.time() - S.PRODUCTION_TICK_SEC - 5
    room = S.room_at(st, 4)
    before = dict(st["resources"])
    S.tick_production(st)
    got = {k: st["resources"][k] - before.get(k, 0) for k in st["resources"] if st["resources"][k] != before.get(k, 0)}
    m = S.room_mult(st, room)[0]
    exp = {k: int(round(v * m)) for k, v in S.room_produces(room).items()
           if isinstance(v, (int, float)) and k not in ("power_supply", "craft_slots", "heal", "blueprint_progress")}
    exp = {k: v for k, v in exp.items() if v}
    ok(all(got.get(k, 0) >= v for k, v in exp.items()), f"정산 1틱 공방 산출 {got} (방 단독 기대 {exp}, 다른 방 산출 포함)")


def t_role_bonus_moves():
    """역할 보정(요리사 → 식량창고 food +1)은 요리사가 그 방에 서 있을 때만."""
    uid = "dev_s14_role"
    st = setup(uid, {})
    cook = who(st, "cook")
    rb = S.resident_room_bonus(cook)
    ok(rb.get("pantry"), f"요리사의 방 보정 {rb}")
    room = S.room_at(st, 2)
    if P["role_bonus_in_room_only"]:
        ok(S.room_bonus_for(st, room) == {}, "요리사가 홀에 있으면 식량창고 보정 없음")
        a = place(uid, cook["id"], 2)["production"]["2"]
        ok(a["role_bonus"] == rb["pantry"], f"요리사를 식량창고에 → role_bonus {a['role_bonus']}")
        a = place(uid, cook["id"], 3)["production"]
        ok(a["2"]["role_bonus"] == {} and a["3"]["role_bonus"] == {}, "온실로 옮기면 식량창고 보정이 사라진다(온실엔 요리사 보정 없음)")
        # 정산: 요리사가 식량창고에 있을 때와 없을 때 food 차이 = 보정 × 배율
        def food_after(stations):
            s2 = S.load_state(uid)
            s2["stations"] = stations
            s2["last_tick"] = time.time() - S.PRODUCTION_TICK_SEC - 5
            f0 = s2["resources"]["food"]
            S.tick_production(s2)
            return s2["resources"]["food"] - f0
        with_cook = food_after({cook["id"]: 2})
        st2 = S.load_state(uid)
        st2["stations"] = {cook["id"]: 2}
        m = S.room_mult(st2, S.room_at(st2, 2))[0]
        base_food = S.room_produces(S.room_at(st2, 2)).get("food", 0)
        ok(with_cook == int(round((base_food + rb["pantry"]["food"]) * m)) or with_cook >= int(round((base_food + rb["pantry"]["food"]) * m)),
           f"정산: 요리사 식량창고 → food {with_cook} (= ({base_food}+{rb['pantry']['food']})×{m:.3f}, 다른 방 food 포함 가능)")
    else:
        ok(True, "role_bonus_in_room_only=false — 예전처럼 어디서든 적용(건너뜀)")


def t_injured_rule():
    """injured_counts 규칙: 거짓이면 부상자는 머릿수·능력치·보정 어디에도 안 센다."""
    uid = "dev_s14_inj"
    st = setup(uid, {"engineer": {"hand": 9}})
    eng = who(st, "engineer")
    place(uid, eng["id"], 4)
    st = S.load_state(uid)
    who(st, "engineer")["injured"] = True
    S.save_state(uid, st)
    a = C.get(f"/api/ark?uid={uid}").json()["production"]["4"]
    if not P["injured_counts"]:
        ok(a["staff"] == 0 and a["stat_mult"] == 1.0 and a["mult"] == SM[0], f"부상 기술자 → 머릿수 0, mult {a['mult']}")
    else:
        ok(a["staff"] == 1, "injured_counts=true → 부상자도 센다")


def t_snapshot_people():
    """접촉 스냅숏은 머릿수가 아니라 사람 id 를 남긴다 — 능력치·보정도 그 순간 사람으로 센다."""
    if S.stk("staffing.measure") != "contact_snapshot":
        ok(True, "measure 가 contact_snapshot 이 아니다 — 건너뜀")
        return
    uid = "dev_s14_snap"
    st = setup(uid, {"engineer": {"hand": 9, "breath": 2}, "cook": {"hand": 3}})
    eng, cook = who(st, "engineer"), who(st, "cook")
    place(uid, eng["id"], 4)                         # 평소: 기술자 공방
    j = C.get(f"/api/raid/today?uid={uid}&debug_raid=swarm&debug_reset=1&debug_grade=1").json()
    tgt = S.load_state(uid)["raid"]["target_slot"]
    C.post("/api/raid/advance", json={"uid": uid})
    # 접촉 직전: 기술자를 공방에서 빼고 요리사(손 3)를 공방에
    place(uid, eng["id"], None)
    place(uid, cook["id"], 4)
    C.post("/api/raid/advance", json={"uid": uid})  # 접촉 → 스냅숏
    snap = S.load_state(uid).get("staff_snapshot")
    ok(snap and snap.get("ids", {}).get("4") == [cook["id"]], f"스냅숏 ids['4'] = 요리사 {snap and snap.get('ids')}")
    # 되돌린다: 기술자 공방, 요리사 홀
    place(uid, cook["id"], None)
    a = place(uid, eng["id"], 4)["production"]["4"]
    exp_snap = clamp(1 + float(P["per_point"]) * (3 - float(P["center"])))
    exp_now = clamp(1 + float(P["per_point"]) * (9 - float(P["center"])))
    ok(a["snapshot"] and abs(a["stat_mult"] - round(exp_snap, 4)) < 1e-9 and abs(a["now_stat_mult"] - round(exp_now, 4)) < 1e-9,
       f"이번 틱 stat_mult {a['stat_mult']}(요리사 손 3) / 다음 틱 {a['now_stat_mult']}(기술자 손 9)")
    # 정산: 스냅숏 1틱 + 지금 1틱
    st = S.load_state(uid)
    T = S.PRODUCTION_TICK_SEC
    st["last_tick"] -= 2 * T
    st["staff_snapshot"]["tick_start"] = st["last_tick"]
    room = S.room_at(st, 4)
    segs = S.room_segments(st, room, S.staff_snapshot_active(st), 2)
    ok(len(segs) == 2 and segs[0][1] < segs[1][1], f"정산 구간 {[(w, round(m, 3)) for w, m, _ in segs]} — 스냅숏 틱이 더 낮다")
    S.tick_production(st)
    ok("staff_snapshot" not in st, "정산 뒤 스냅숏 소멸")


def t_move_preview():
    """서버가 미리 계산하는 드래그 미리보기(PM 결정). 실제로 옮겼을 때의 변화와 같아야 한다."""
    uid = "dev_s14_prev"
    st = setup(uid, {"engineer": {"hand": 9, "breath": 2}})
    eng = who(st, "engineer")
    a0 = C.get(f"/api/ark?uid={uid}").json()
    mp = a0["move_preview"]
    ok(set(mp) == {r["id"] for r in st["residents_list"]}, f"주민 {len(mp)}명 모두")
    ok(mp[eng["id"]]["4"]["room_delta_pct"] is None, "공방은 쌓이는 산출이 없다(craft_slots) → room_delta null")
    cell = mp[eng["id"]]["3"]                      # 온실(숨) — 기술자 숨 2
    st0 = S.load_state(uid)
    old = S.room_output(st0, S.room_at(st0, 3), S.staff_people(st0, 3))
    a1 = place(uid, eng["id"], 3)
    st1 = S.load_state(uid)
    real = S.room_output(st1, S.room_at(st1, 3), S.staff_people(st1, 3))
    want = round((real - old) / old * 100, 1)
    exp_mult = SM[1] * clamp(1 + float(P["per_point"]) * (2 - float(P["center"])))
    ok(cell["room_delta_pct"] == want and abs(real / old - exp_mult / SM[0]) < 1e-6,
       f"홀→온실 미리보기 room_delta {cell['room_delta_pct']}% = 실제 {want}% (배율 {SM[0]}→{exp_mult:.3f})")
    ok(cell["from_delta_pct"] is None, "홀에서 떠나는 것은 from_delta 없음(null)")
    mp = a1["move_preview"][eng["id"]]
    ok("3" not in mp and "hall" in mp and mp["hall"]["from_delta_pct"] < 0 and mp["hall"]["room_delta_pct"] is None,
       f"온실에서 홀로: from_delta {mp['hall']['from_delta_pct']}%")
    ok(mp["2"]["room_delta_pct"] is not None and mp["2"]["from_delta_pct"] == mp["hall"]["from_delta_pct"],
       f"온실→식량창고: room {mp['2']['room_delta_pct']}% · from {mp['2']['from_delta_pct']}%")
    place(uid, eng["id"], None)
    # 정원 찬 방은 can:false
    st = S.load_state(uid)
    cap = S.room_cap_of(S.room_at(st, 3))
    others = [r for r in st["residents_list"] if r["id"] != eng["id"]][:cap]
    for r in others:
        place(uid, r["id"], 3)
    mp = C.get(f"/api/ark?uid={uid}").json()["move_preview"][eng["id"]]
    ok(mp["3"]["can"] is (len(others) < cap), f"온실 정원 {cap} / 이미 {len(others)}명 → can={mp['3']['can']}")


TESTS = [t_room_stat_canon, t_favoured_vs_wrong, t_role_bonus_moves, t_injured_rule, t_snapshot_people, t_move_preview]

if __name__ == "__main__":
    print("stat_production:", P)
    for t in TESTS:
        print(f"\n## {t.__name__} — {(t.__doc__ or '').strip().splitlines()[0]}")
        try:
            t()
        except Exception:
            RESULTS.append((False, t.__name__ + " 예외"))
            traceback.print_exc()
    bad = [m for c, m in RESULTS if not c]
    print(f"\n합계 {len(RESULTS)} · 통과 {len(RESULTS) - len(bad)} · 실패 {len(bad)}")
    for m in bad:
        print("  FAIL", m)
    sys.exit(1 if bad else 0)
