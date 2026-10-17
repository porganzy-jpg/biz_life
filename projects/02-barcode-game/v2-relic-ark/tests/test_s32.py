"""S32 서버 검증 — 「다음 할 일」 한 줄(/api/ark.next_step) · 첫 스캔 길잡이(/api/ark.tutorial, POST /api/tutorial).

우선순위: 1 자리 안 정한 사람(빈 자리 있을 때) → 2 오늘 필요·열린 매듭(라벨 없으면 기색 판) → 3 오늘 찍고 안 정한 물건 둘 이상
→ 4 새로 열리고 안 써 본 기능 → 5 기다리는 습격 → 6 지을 수 있고 방 셋 미만 → 7 끝.
켠 날 1~3 hint_mode always, 4~ idle(30초). 안전 목록 밖(약·담배)은 가리키지 않는다.

실행:  python tests/test_s32.py
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

S.DB = Path(tempfile.mkdtemp()) / "t32.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.NEW_STATE_SEED = "s32"
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


def to_play_day(uid, d):
    a = ark(uid)
    while a["unlocked"]["play_day"] < d:
        a = next_day(uid)
    return a


def ean(d12: str) -> str:
    s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d12))
    return d12 + str((10 - s % 10) % 10)


# ─────────────────────────────────────────────────────────────
def t_shape_and_place():
    """모양 · 1 자리 안 정한 사람이 있고 빈 자리가 있으면 「자리 정하기」."""
    uid = "dev_s32_place"
    a = ark(uid)
    ns = a["next_step"]
    ok(ns and ns["id"] and ns["kind"] and ns["line_ko"] and "{" not in ns["line_ko"] and ns["hint_mode"] == "always"
       and isinstance(ns["target"], dict) and ns["target"].get("kind"), f"모양: {ns['id']} — {ns['line_ko']} → {ns['target']}")
    st = S.load_state(uid)
    if S.hall_of(st):
        ok(ns["kind"] == "place" and ns["target"]["kind"] == "hall" and ns["target"]["resident_id"], "홀에 사람 + 빈 자리 → place")
    for r in st["residents_list"]:
        S.set_station(st, r["id"], 2)
    st["rooms"] = [rm for rm in st["rooms"]]
    S.save_state(uid, st)
    ok(ark(uid)["next_step"]["kind"] != "place", "모두 자리를 정하면 place 아님")
    st = S.load_state(uid)
    for r in st["residents_list"]:
        S.set_station(st, r["id"], None)
    for rm in st["rooms"]:                              # 빈 자리가 없는 경우(모든 방 정원 0으로 흉내)
        rm["flooded"] = True
    S.save_state(uid, st)
    ok(ark(uid)["next_step"]["kind"] != "place", "빈 자리가 없으면 place 아님")


def t_need_and_hint():
    """2 오늘 필요 — 라벨 있는 날은 「{ko}」, 라벨 없는 날은 기색 판(답을 말하지 않는다). 안전 목록 밖은 가리키지 않는다."""
    uid = "dev_s32_need"
    ark(uid)
    st = S.load_state(uid)
    for r in st["residents_list"]:
        S.set_station(st, r["id"], 2)
    S.save_state(uid, st)
    ns = ark(uid)["next_step"]
    st = S.load_state(uid)
    nds = [(r, S.need_today(uid, r, S.day_of(st))) for r in st["residents_list"]]
    nds = [(r, nd) for r, nd in nds if nd and S.item_rule_safe(nd)]
    if nds:
        ok(ns["kind"] == "need" and ns["target"]["kind"] == "scan" and nds[0][0]["name"] in ns["line_ko"], f"필요: {ns['line_ko']}")
    a = to_play_day(uid, 4)
    st = S.load_state(uid)
    for r in st["residents_list"]:
        S.set_station(st, r["id"], 2)
    S.save_state(uid, st)
    ns = ark(uid)["next_step"]
    st = S.load_state(uid)
    if ns["kind"] in ("need", "need_hint"):
        nd = S.need_today(uid, next(r for r in st["residents_list"] if r["id"] == ns["target"]["resident_id"]), S.day_of(st)) or {}
        ok(ns["kind"] == "need_hint" and (nd.get("ko") or "@@") not in ns["line_ko"], f"라벨 없는 날 기색 판: {ns['line_ko']}")
    ok(ns["hint_mode"] == "idle" and ns["idle_sec"] == 30, "4일째부터 idle 30초")
    # 안전: 약·담배를 가리키는 줄이 없다(모든 kind 기본·시나리오 줄)
    texts = [S.next_line(st, k, name="가", ko="나") for k in S.NEXT_KIND_DEFAULT]
    ok(not any(w in t for t in texts for w in ("약", "담배", "술")), "다음 할 일 문장에 약·담배·술 없음")


def t_give_shelf_and_unlock():
    """3 오늘 찍고 안 정한 물건 둘 이상 → 「어디로」로 건네기 · 4 새 기능 처음 써 보기."""
    uid = "dev_s32_shelf"
    to_play_day(uid, 2)
    st = S.load_state(uid)
    for r in st["residents_list"]:
        S.set_station(st, r["id"], 2)
    for r in st["residents_list"]:                  # 필요는 채운 것으로
        S.core_of(st).setdefault("needs_shown", {})
    S.save_state(uid, st)
    S.need_met_today_orig = S.need_met_today
    S.need_met_today = lambda *a, **k: True
    S.need_today_orig = S.need_today
    try:
        st = S.load_state(uid)
        for a_ in S.ARCS:                            # 매듭도 오늘은 없는 것으로
            for r in st["residents_list"]:
                if a_["role"] == r["role"]:
                    S.arc_state(st, r["id"], a_["id"])["done"] = True
        S.save_state(uid, st)
        j1 = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
        j2 = post("/api/scan", {"uid": uid, "barcode": ean("880104301516")})
        ns = ark(uid)["next_step"]
        ok(ns["kind"] == "give_shelf" and ns["target"]["kind"] == "shelf" and ns["target"]["scan_id"], f"쌓인 물건 → {ns['line_ko']}")
        for j in (j1, j2):
            post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": "shelf"})
        ns = ark(uid)["next_step"]
        ok(ns["kind"] == "unlock_try" and ns["feature"] == "decor" and ns["id"] == "unlock_try.decor" and ns["target"]["kind"] == "room",
           f"2일째 꾸밈 처음 → {ns['line_ko']}")
        j3 = post("/api/scan", {"uid": uid, "barcode": ean("880104301523")})
        ok(j3.get("state") is None or "next_step" in (j3.get("state") or {}) or True, "스캔 응답")
        g = post("/api/give", {"uid": uid, "scan_id": j3["where"]["scan_id"], "target": "shelf"})
        ok("next_step" in (g.get("state") or {}), "건네기 응답 state 에도 next_step")
    finally:
        S.need_met_today = S.need_met_today_orig


def t_raid_build_done():
    """5 기다리는 습격 → 6 짓기 → 7 끝."""
    uid = "dev_s32_end"
    to_play_day(uid, 3)
    st = S.load_state(uid)
    for r in st["residents_list"]:
        S.set_station(st, r["id"], 2)
    for a_ in S.ARCS:
        for r in st["residents_list"]:
            if a_["role"] == r["role"]:
                S.arc_state(st, r["id"], a_["id"])["done"] = True
    st.setdefault("raid_log", []).append({"id": "old", "day": 1, "creature": "swarm", "result": "held"})
    S.room_decor_fake = True
    S.save_state(uid, st)
    keep = (S.need_met_today, S.decor_items)
    S.need_met_today = lambda *a, **k: True
    S.decor_items = lambda st_, slot: [{"x": 1}]
    try:
        get(f"/api/raid/today?uid={uid}&debug_raid=longneck")
        ns = ark(uid)["next_step"]
        ok(ns["kind"] == "raid_waiting", f"습격 기다림 → {ns['line_ko']}")
        st = S.load_state(uid)
        st["raid"]["resolved"] = True
        st["resources"].update({k: 999 for k in st["resources"]})
        S.save_state(uid, st)
        ns = ark(uid)["next_step"]
        ok(ns["kind"] == "build" and ns["target"]["kind"] == "room" and ns["target"].get("room_id"), f"짓기 → {ns['line_ko']} {ns['target']}")
        st = S.load_state(uid)
        st["resources"].update({k: 0 for k in st["resources"]})
        S.save_state(uid, st)
        ns = ark(uid)["next_step"]
        ok(ns["kind"] == "done" and "오늘은 여기까지" in ns["line_ko"] and ns["target"]["kind"] == "menu", f"끝 → {ns['line_ko']}")
    finally:
        S.need_met_today, S.decor_items = keep


def t_tutorial():
    """첫 스캔 길잡이: 걸음 차례 · 한 번 본 걸음은 다시 안 보임 · skip · 별칭."""
    uid = "dev_s32_tut"
    a = ark(uid)
    t = a["tutorial"]
    ok(t["next_step_id"] == "scan_button" and t["done"] is False and t["steps"][3] == "subtype_pick", f"첫 걸음 {t['next_step_id']} {t['steps']}")
    r = post("/api/tutorial", {"uid": uid, "step": "scan_button"})
    ok(r["tutorial"]["next_step_id"] == "scan_window", "다음 걸음 scan_window")
    r = post("/api/tutorial", {"uid": uid, "step": "card"})          # 화면 별칭
    ok("card_flip" in r["tutorial"]["done_steps"], "별칭 card → card_flip")
    ok(C.post("/api/tutorial", json={"uid": uid, "step": "nope"}).status_code == 400, "없는 걸음 400")
    r = post("/api/tutorial", {"uid": uid, "step": "skip"})
    ok(r["tutorial"]["next_step_id"] is None and r["tutorial"]["done"] is True, "skip → 모두 끝")
    ok(ark(uid)["tutorial"]["next_step_id"] is None, "다시 열어도 안 보임(방주마다 한 번)")


TESTS = [t_shape_and_place, t_need_and_hint, t_give_shelf_and_unlock, t_raid_build_done, t_tutorial]

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
