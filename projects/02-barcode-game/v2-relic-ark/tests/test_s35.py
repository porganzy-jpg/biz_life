"""S35 서버 검증 — 살림 게이지 · 방은 사람 때문에 열린다.

실행:  python tests/test_s35.py
"""
from __future__ import annotations

import os
import random
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

S.DB = Path(tempfile.mkdtemp()) / "t35.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.NEW_STATE_SEED = "s35"
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


# ─────────────────────────────────────────────────────────────
def t_household():
    """살림 띠: 며칠치 · 3일치 이상 가득 · 바닥이면 새 부탁 쉼(매듭은 그대로) · 한 줄."""
    uid = "dev_s35_house"
    ark(uid)
    st = S.load_state(uid)
    n = len(st["residents_list"])
    st["resources"].update({"food": int(n * 0.6 * 3) + 2, "water": 1, "power": 0})
    S.save_state(uid, st)
    a = ark(uid)
    hh = {x["res"]: x for x in a["household"]}
    ok(list(hh) == ["food", "water"] and hh["food"]["level"] == "full" and hh["water"]["level"] == "low",
       f"띠 {[(x['res'], x['days'], x['level'], x['ko']) for x in a['household']]}")
    ok(not a["household_dim"] and a["needs_today"] is not None, "식량·물이 있으면 부탁 그대로")
    st = S.load_state(uid)
    st["resources"]["water"] = 0
    S.save_state(uid, st)
    a = ark(uid)
    ok(a["household_dim"] and a["household_note"] and a["needs_today"] == [], f"물 바닥 → 새 부탁 쉼 · {a['household_note']}")
    st = S.load_state(uid)
    r = st["residents_list"][0]
    nd = S.need_today(uid, r, S.day_of(st))
    if nd:
        sub = nd.get("subtype")
        sub = sub[0] if isinstance(sub, list) else sub
        t_, _ = S.resident_tier(st, uid, r, {"name": "x", "category": nd["category"], "subtype": sub, "barcode": "x"})
        ok(t_ != "need", f"쉬는 동안 필요 판정 없음({t_})")
    ok(a["next_step"]["kind"] not in ("need", "need_hint"), "다음 할 일도 부탁을 가리키지 않음")
    st = S.load_state(uid)
    st["resources"]["water"] = 10
    S.save_state(uid, st)
    ok(not ark(uid)["household_dim"], "물이 돌아오면 다시")


def t_room_types():
    """방 종류: 편한 방 주인이 처음 들어오면 열린다(시작 주민은 조용히) · 열리기 전엔 짓기 거절."""
    uid = "dev_s35_rooms"
    a = ark(uid)
    rto = a["room_types_open"]
    ok(not rto["greenhouse"]["open"] and a["build_options"]["greenhouse"]["people_locked"], "온실은 처음엔 닫힘")
    bo = a["build_options"]["greenhouse"]
    ok(bo["locked_by_role"] == "farmer" and bo["locked_ko"] == "농부가 오면 열립니다", f"잠금 역할 {bo['locked_by_role']} · {bo['locked_ko']}")
    ok("locked_by_role" not in a["build_options"]["quarters"], "열린 방엔 잠금 역할 없음")
    ok(not a["room_news"], "시작 주민의 방 종류는 방송 없음")
    st = S.load_state(uid)
    st["resources"].update({k: 999 for k in st["resources"]})
    S.save_state(uid, st)
    r = C.post("/api/ark/build", json={"uid": uid, "room_id": "greenhouse", "slot": 3})
    ok(r.status_code == 400 and "편해할" in r.json()["detail"], f"닫힌 방 짓기 거절: {r.json().get('detail')}")
    st = S.load_state(uid)
    farmer = S.make_resident("farmer", random.Random(5), {x["name"] for x in st["residents_list"]}, uid)
    S.ensure_stats(uid, farmer)
    farmer["joined"] = time.time() + 120
    farmer["comfort_room"] = "greenhouse"
    st["residents_list"].append(farmer)
    S.save_state(uid, st)
    a = ark(uid)
    ok(a["room_types_open"]["greenhouse"]["open"] and any(n["kind"] == "room_open" and farmer["name"] in n["ko"] for n in a["room_news"]),
       f"농부가 오니 온실 열림 · {[n['ko'] for n in a['room_news']]}")
    ok(not ark(uid)["room_news"], "방송은 한 번")
    ok(not a["build_options"]["greenhouse"]["people_locked"] and a["build_options"]["greenhouse"]["opened_by"]["name"] == farmer["name"], "짓기 목록에 열림 + 누구 덕분")


def t_no_room_guest():
    """잠자리 없는 손님: 「머물 칸이 없습니다」 한 번 + 관리 칸 목표(하던 관리 목표는 대기열 맨 앞)."""
    uid = "dev_s35_guest"
    a = ark(uid)
    st = S.load_state(uid)
    cur = (S.core_of(st)["goals"]["slots"] or {}).get("manage")
    while S.beds_state(st)["free"] > 0:
        x = S.make_resident("kid", random.Random(len(st["residents_list"])), {y["name"] for y in st["residents_list"]}, uid)
        S.ensure_stats(uid, x)
        st["residents_list"].append(x)
    g = S.make_guest(st, uid, f"{uid}|g", "knock")
    S.save_state(uid, st)
    a = ark(uid)
    news = [n for n in a["room_news"] if n["kind"] == "no_room"]
    ok(news and g["name"] in news[0]["ko"], f"머물 칸 없음 방송: {news and news[0]['ko']}")
    mg = next(x for x in a["goals"] if x["kind"] == "manage")
    ok(mg["id"].startswith("room_for_") and g["name"] in mg["title_ko"] and mg["person"] == g["name"], f"관리 칸 목표: {mg['title_ko']}")
    st = S.load_state(uid)
    if cur and not cur.get("done"):
        ok(S.core_of(st)["goals"]["queue"][0]["id"] == cur["id"], "하던 관리 목표는 대기열 맨 앞")
    ok(not [n for n in ark(uid)["room_news"] if n["kind"] == "no_room"], "방송은 한 번")


def t_comfort_goal():
    """편한 방이 없는 사람 → 「○○ 님 편한 방 짓기」 목표 후보(그 방 종류가 열려 있을 때)."""
    uid = "dev_s35_cg"
    ark(uid)
    st = S.load_state(uid)
    cands = S.comfort_goal_candidates(st, uid, 1)
    ok(cands and "편한 방" in cands[0]["title_ko"] and cands[0]["cond"]["room_built"] in S.ROOMS, f"후보 {cands and cands[0]['title_ko']}")
    rid = cands[0]["cond"]["room_built"]
    st["rooms"].append({"id": rid, "slot": 3, "built": time.time(), "level": 1})
    ok(not any(c_["cond"]["room_built"] == rid for c_ in S.comfort_goal_candidates(st, uid, 1)), "지으면 후보에서 빠짐")


TESTS = [t_household, t_room_types, t_no_room_guest, t_comfort_goal]

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
