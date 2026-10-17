"""S33 서버 검증 — 오늘의 목표 셋(data/balance/goals.json) · 방 생산 숫자.

실행:  python tests/test_s33.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

os.environ["RELIC_DEV"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import server as S  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t33.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.NEW_STATE_SEED = "s33"
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []
S.now_hour = lambda: 10


def ok(cond, msg):
    RESULTS.append((bool(cond), msg))
    print(("OK   " if cond else "FAIL ") + msg)


def get(path, code=200):
    r = C.get(path)
    assert r.status_code == code, (path, r.status_code, r.text)
    return r.json()


def post(path, body, code=200):
    r = C.post(path, json=body)
    assert r.status_code == code, (path, r.status_code, r.text)
    return r.json()


def ark(uid):
    return get(f"/api/ark?uid={uid}")


def next_day(uid):
    post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
    return ark(uid)


def ean(d12: str) -> str:
    s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d12))
    return d12 + str((10 - s % 10) % 10)


def gmap(a):
    return {g["id"]: g for g in a["goals"]}


# ─────────────────────────────────────────────────────────────
def t_day1_goals_and_clear():
    """1일째 셋 → 판정 · 진행 · 끝낸 순간 한 번 알림 · 셋 다 → 내일 부탁 또렷."""
    uid = "dev_s33_d1"
    a = ark(uid)
    g = gmap(a)
    ok(list(g) == ["w1_staff_pantry", "w1_first_give", "w1_scan3"] and [x["kind"] for x in a["goals"]] == ["manage", "core", "new"],
       f"1일째 목표 {list(g)}")
    ok(all(x["text_key"] and x["progress"] == [0, x["progress"][1]] and not x["done"] for x in a["goals"]), "처음엔 모두 0")
    st = S.load_state(uid)
    S.set_station(st, st["residents_list"][0]["id"], 2)
    S.save_state(uid, st)
    a = ark(uid)
    ok(gmap(a)["w1_staff_pantry"]["done"] and any(x["id"] == "w1_staff_pantry" for x in a["goals_done_now"]), "식량창고에 한 사람 → 끝 + 알림")
    ok(not ark(uid)["goals_done_now"], "알림은 한 번")
    js = [post("/api/scan", {"uid": uid, "barcode": ean(f"88010430150{i}")}) for i in range(3)]
    a = ark(uid)
    ok(gmap(a)["w1_scan3"]["done"] and gmap(a)["w1_scan3"]["progress"] == [3, 3], "서로 다른 물건 셋")
    tgt = next(x["target"] for x in js[0]["where"]["suggest"] if x["kind"] == "resident")   # 「어디로」가 권한 사람(돌려받지 않는다)
    out = post("/api/give", {"uid": uid, "scan_id": js[0]["where"]["scan_id"], "target": tgt})
    ok("goals" in (out.get("state") or {}) and any(x["id"] == "w1_first_give" and x["done"] for x in out["state"]["goals"]),
       "건네기 응답 state 에 목표(바로 체크)")
    a = ark(uid)
    ok(a["tomorrow_need_clear"] is True and a["all_done_ko"], f"셋 다 → tomorrow_need_clear · {a['all_done_ko']}")
    ok(all(x["title_ko"] and x["done_ko"] for x in a["goals"]), "목표 문장(goals_text.json) title_ko·done_ko")
    lv = get(f"/api/leaving?uid={uid}")
    ta = lv["tomorrow_ask"] or ((lv["next_visit"] or {}).get("kind") == "tomorrow_ask" and S.leave_lines(S.load_state(uid), uid)[1])
    ta = ta or S.tomorrow_ask(S.load_state(uid), uid)
    tk = lv["tomorrow_ask"] or (lv["next_visit"] if lv["next_visit"].get("kind") == "tomorrow_ask" else None)
    ok(tk and tk.get("clear"), f"떠날 때 내일 부탁 또렷 {tk and (tk.get('subtype_ko') or (tk.get('data') or {}).get('subtype_ko'))}")


def t_carry_over():
    """못 끝낸 목표는 다음 켠 날 남고(carried), 빈 칸만 그날 목표로."""
    uid = "dev_s33_carry"
    a = ark(uid)
    st = S.load_state(uid)
    S.set_station(st, st["residents_list"][0]["id"], 2)   # 관리만 끝냄
    S.save_state(uid, st)
    ark(uid)
    a = next_day(uid)
    g = gmap(a)
    ok("w2_build_one" in g and "w1_first_give" in g and "w1_scan3" in g, f"2일째: 관리 칸만 새 목표 {list(g)}")
    ok(g["w1_first_give"]["carried"] and not g["w2_build_one"]["carried"], "남은 것은 carried")
    st = S.load_state(uid)
    G = S.core_of(st)["goals"]
    ok({"w2_need_met", "w2_decor"} <= {x["id"] for x in G["queue"]}, "그날 못 넣은 목표는 대기열로")


def t_quiet_day_alt():
    """습격이 없는 날, 3일째 습격 목표는 대체 목표(alt_if_quiet)로 바뀐다."""
    uid = "dev_s33_quiet"
    ark(uid)
    st = S.load_state(uid)
    G = S.goals_tick(st, uid)
    G["slots"]["new"] = {"id": "w3_raid", "kind": "new", "cond": {"raid_handled_today": True}, "text": "goal.w3_raid",
                         "from_pd": 3, "done": False, "alt_if_quiet": (S.GOALS["week1"]["3"][2]).get("alt_if_quiet")}
    st["raid"] = {"day": S.day_of(st), "none": True}
    S.goals_tick(st, uid)
    sl = S.core_of(st)["goals"]["slots"]["new"]
    alt_id = S.GOALS["week1"]["3"][2].get("alt_if_quiet")
    ok(sl["id"] == alt_id and sl.get("alt_of") == "w3_raid" and sl["id"] in S.GOALS["week1"]["_alt"], f"조용한 날 → {sl['id']}")


def t_pool_day8():
    """8번째 켠 날부터 pool 에서 갈래마다 하나, n = 지금 + 한 걸음."""
    uid = "dev_s33_pool"
    a = ark(uid)
    st = S.load_state(uid)
    S.core_of(st)["beats"]["play_day"] = 8
    S.core_of(st)["goals"] = {"slots": {}, "queue": [], "pd": None, "recent": {}, "announced": []}
    G = S.goals_tick(st, uid)
    ids = [ (G["slots"].get(k) or {}).get("id") for k in S.GOAL_KINDS]
    ok(all(ids) and all(i.startswith("p_") for i in ids), f"8일째 pool {ids}")
    core = G["slots"]["core"]
    if core["id"] == "p_knot":
        ok(core["cond"]["chain_beats_total"] == S.goal_metric(st, uid, "chain_beats_total") + 1, "n = 지금 + 1")
    ok(S.goal_metric(st, uid, "rooms_built") == 0, "rooms_built 는 시작 방을 세지 않는다")


def t_production():
    """방 생산 숫자: 옛 값(staff·per_person…)에 하루·시간당·사람 수별 하루가 더해진다 · 드래그 미리보기 하루 값 · 짓기 produces."""
    uid = "dev_s33_prod"
    a = ark(uid)
    pr = a["production"]["2"]
    ok(pr["output_per_day"] == 3.0 and pr["by_people"] == [3.0, 6.0, 8.1, 9.6] and pr["half_without_people"], f"식량창고 0명 하루 {pr['output_per_day']} · {pr['by_people']}")
    ok(abs(pr["output_per_hour"] - round(pr["output_per_tick"] / 8, 2)) < 1e-9, "시간당 = 틱 ÷ 8")
    ok("staff" in pr or "per_person" in pr or "label" in pr, f"옛 방 카드 값 남음 {sorted(pr)[:6]}")
    mp = a["move_preview"]
    rid = next(iter(mp))
    cell = mp[rid].get("2")
    st = S.load_state(uid)
    p_ = next(r for r in st["residents_list"] if r["id"] == rid)
    rm = S.room_at(st, 2)
    exp = round(S.room_output(st, rm, S.staff_people(st, 2) + [p_]) * 3, 1)
    ok(cell and cell.get("room_per_day_after") == exp and exp > pr["output_per_day"], f"드래그 → 하루 {cell and cell.get('room_per_day_after')} (= 식 {exp})")
    bo = a["build_options"]
    ok(any("water" in (v.get("produces") or []) for v in bo.values()), "짓기 produces(정수실 → 물)")


TESTS = [t_day1_goals_and_clear, t_carry_over, t_quiet_day_alt, t_pool_day8, t_production]

if __name__ == "__main__":
    for t in TESTS:
        print(f"\n## {t.__name__} — {(t.__doc__ or '').strip().splitlines()[0] if t.__doc__ else ''}")
        try:
            t()
        except Exception:
            traceback.print_exc()
            RESULTS.append((False, f"{t.__name__} 예외"))
        S.now_hour = lambda: 10
    n = len(RESULTS)
    f = [m for c, m in RESULTS if not c]
    print(f"\n합계 {n} · 통과 {n - len(f)} · 실패 {len(f)}")
    for m in f:
        print("  FAIL", m)
    sys.exit(1 if f else 0)
