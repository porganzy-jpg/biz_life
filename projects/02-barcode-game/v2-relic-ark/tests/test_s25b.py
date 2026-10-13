"""S25 후속 검증 — 「이게 뭐예요?」 선택지·미리 고름은 카드 갈래 것만, 시험·플레이테스트 방주는 전역 투표에서 빠진다, reset_votes 미리 보기·적용.

실행:  python tests/test_s25b.py
"""
from __future__ import annotations

import os
import shutil
import sqlite3
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

S.DB = Path(tempfile.mkdtemp()) / "t25b.db"
S.DEV_MODE = False                      # 운영처럼(개발 서버 방주 표시 없음)
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []
S.now_hour = lambda: 10


def ok(cond, msg):
    RESULTS.append((bool(cond), msg))
    print(("OK   " if cond else "FAIL ") + msg)


def ean(d12: str) -> str:
    s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d12))
    return d12 + str((10 - s % 10) % 10)


def post(path, body, code=200):
    r = C.post(path, json=body)
    assert r.status_code == code, (path, r.status_code, r.text)
    return r.json()


def t_options_follow_card():
    """회귀: 다른 갈래로 표가 쌓인 바코드를 식품으로 찍어도 선택지·미리 고름은 식품 것만. 알려진 가문은 null."""
    code = "4951234560005"
    with S.db() as con:
        for i in range(10):
            con.execute("INSERT INTO subtype_votes VALUES(?,?,?,?,?)", (f"u{i}real", code, "drink", "water", time.time()))
    C.get("/api/ark?uid=ufood1")
    j = post("/api/scan", {"uid": "ufood1", "barcode": code, "user_category": "food"})
    sp = j["where"]["subtype_pick"]
    ok(j["card"]["category"] == "food" and sp and all(o["id"] in S.SUBTYPE_KO["food"] for o in sp["options"]) and sp["suggest"] is None,
       f"식품 카드 → 식품 선택지 {[o['ko'] for o in sp['options']]}, 미리 고름 없음")
    C.get("/api/ark?uid=udrink1")
    j2 = post("/api/scan", {"uid": "udrink1", "barcode": code, "user_category": "drink"})
    sg = j2["where"]["subtype_pick"]["suggest"]
    ok(sg and sg["id"] == "water" and sg["category"] == "drink" and sg["arks"] == 10, "음료로 찍으면 음료 표(10곳)")
    C.get("/api/ark?uid=uknown1")
    j3 = post("/api/scan", {"uid": "uknown1", "barcode": ean("880104301509")})
    ok(j3["where"]["subtype_pick"] is None, "알려진 가문(붉은 실 8801043)은 묻지 않는다(스크린샷의 음료 선택지는 서버가 낸 것이 아님)")
    with S.db() as con:
        con.execute("INSERT INTO subtype_votes VALUES(?,?,?,?,?)", ("ux", code, "food", "water", time.time()))
    ok(S.subtype_vote_suggest(code, "food") is None, "그 갈래에 없는 종류의 표는 세지 않는다")


def t_test_arks_excluded():
    code = ean("490123400555")
    for uid in ("pt7a_r5", "r5dry_a", "smoke", "dev_x1"):
        C.get(f"/api/ark?uid={uid}")
        j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
        post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": "milk"})
    with S.db() as con:
        n = con.execute("SELECT COUNT(*) FROM subtype_votes WHERE barcode=?", (code,)).fetchone()[0]
    ok(n == 0, f"시험 uid 표는 쌓이지 않는다({n})")
    S.DEV_MODE = True
    C.get("/api/ark?uid=ureal_devsrv")
    S.DEV_MODE = False
    st = S.load_state("ureal_devsrv")
    ok(st.get("test_ark") is True and S.vote_excluded("ureal_devsrv", st), "개발 서버에서 만든 방주는 test_ark")
    j = post("/api/scan", {"uid": "ureal_devsrv", "barcode": code, "user_category": "drink"})
    post("/api/scan/subtype", {"uid": "ureal_devsrv", "scan_id": j["where"]["scan_id"], "subtype": "milk"})
    C.get("/api/ark?uid=ureal9")
    j = post("/api/scan", {"uid": "ureal9", "barcode": code, "user_category": "drink"})
    post("/api/scan/subtype", {"uid": "ureal9", "scan_id": j["where"]["scan_id"], "subtype": "milk"})
    with S.db() as con:
        rows = [r[0] for r in con.execute("SELECT uid FROM subtype_votes WHERE barcode=?", (code,))]
    ok(rows == ["ureal9"], f"실제 사람 꼴(u…) 표만 {rows}")
    # 이미 쌓인 시험 표도 세지 않는다
    with S.db() as con:
        for i in range(5):
            con.execute("INSERT INTO subtype_votes VALUES(?,?,?,?,?)", (f"devS22_{i}", code, "drink", "water", time.time()))
    ok(S.subtype_vote_suggest(code, "drink") is None, "이미 들어간 시험 표는 집계에서 빠진다")


def t_reset_script():
    import importlib
    tmp = Path(tempfile.mkdtemp()) / "copy.db"
    shutil.copy2(S.DB, tmp)
    rv = importlib.import_module("tools.reset_votes") if (ROOT / "tools" / "__init__.py").exists() else None
    if rv is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("reset_votes", ROOT / "tools" / "reset_votes.py")
        rv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rv)
    before = sqlite3.connect(tmp).execute("SELECT COUNT(*) FROM subtype_votes").fetchone()[0]
    rv.main(["--db", str(tmp)])
    mid = sqlite3.connect(tmp).execute("SELECT COUNT(*) FROM subtype_votes").fetchone()[0]
    ok(before == mid, "미리 보기는 지우지 않는다")
    rv.main(["--db", str(tmp), "--apply"])
    uids = {r[0] for r in sqlite3.connect(tmp).execute("SELECT DISTINCT uid FROM subtype_votes")}
    ok(uids and all(u.startswith("u") and u != "ureal_devsrv" for u in uids) and not any(u.startswith("devS") for u in uids),
       f"--apply 뒤 남은 표 {sorted(uids)}")
    ok(any(p.name.startswith("copy.db.bak-") for p in tmp.parent.iterdir()), "지우기 전 사본을 남긴다")


def t_seat_slot():
    """클라이언트 요청: 사슬 끝 자리에 방 칸(slot)."""
    uid = "useat1"
    C.get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    cook = next(r for r in st["residents_list"] if r["role"] == "cook")
    S.set_station(st, cook["id"], 2)
    a = S.ARC_BY_ID["arc_cook_seat"]
    s_ = S.arc_state(st, cook["id"], a["id"])
    s_.update({"step": len(a["beats"]) - 1, "last_day": S.day_of(st) - 3})
    row = S.fire_beat(st, uid, cook, a, s_, S.next_beat(a, s_), force=True)
    seat = S.cres(st, cook["id"])["seat"]
    ok(row["done"] and seat["slot"] == 2, f"자리 = 선 방 칸 {seat}")
    S.cres(st, cook["id"])["seat"] = {"arc": a["id"], "item": "x", "day": 1}       # 옛 저장
    S.set_station(st, cook["id"], None)
    S.save_state(uid, st)
    j = C.get(f"/api/ark?uid={uid}").json()
    sl = j["core"]["residents"][cook["id"]]["seat"]["slot"]
    ok(sl == 2, f"옛 자리는 사슬이 가리킨 방(식량창고 2)으로 {sl}")


def t_dev_clock():
    """★ 개발 시계: RELIC_DEV 에서만, 그 방주의 시각을 고정한다(아침 9시·저녁 19시 세션 플레이테스트용)."""
    S.now_hour = S._now_hour_impl
    try:
        uid = "uclock1"
        C.get(f"/api/ark?uid={uid}")
        ok(C.post("/api/dev/clock", json={"uid": uid, "hour": 19}).status_code == 404, "운영 모드 → 404")
        S.DEV_MODE = True
        j = post("/api/dev/clock", {"uid": uid, "hour": 19})
        ok(j["hour"] == 19 and j["evening"] and not j["is_night"], f"19시 → 저녁 세션 {j}")
        a = C.get(f"/api/ark?uid={uid}").json()
        ok(a["session"]["evening"] is True and a["overnight"] is None or (a["overnight"] or {}).get("band") == "evening", "/api/ark 저녁(밤사이 제목 band evening)")
        j = post("/api/dev/clock", {"uid": uid, "hour": 9})
        a = C.get(f"/api/ark?uid={uid}").json()
        ok(j["now_hour"] == 9 and a["session"]["evening"] is False and a["is_night"] is False, "9시 → 아침")
        post("/api/dev/clock", {"uid": uid, "hour": 22})
        a = C.get(f"/api/ark?uid={uid}").json()
        ok(a["is_night"] is True, "22시 → 밤")
        C.get("/api/ark?uid=uclock_other")
        b = C.get("/api/ark?uid=uclock_other").json()
        ok(b["is_night"] == S.is_night(__import__("datetime").datetime.now().hour), "다른 방주는 실제 시계")
        # 21시 자동 판정: 낮에 연 습격이 개발 시계 21시에 판정된다
        st = S.load_state(uid)
        st["dev_clock_hour"] = 10
        st["raid"] = {"id": "r1", "day": S.day_of(st), "creature": "longneck", "grade": 1, "target_slot": 2, "severity": 0,
                      "stage": "sound", "started": time.time(), "resolved": False, "acts": [], "moves": 0, "outside_sent": []}
        S.save_state(uid, st)
        C.get(f"/api/ark?uid={uid}")
        ok(not S.load_state(uid)["raid"].get("resolved"), "10시: 아직 판정 안 함")
        post("/api/dev/clock", {"uid": uid, "hour": 21})
        a = C.get(f"/api/ark?uid={uid}").json()
        ok(S.load_state(uid)["raid"].get("resolved") and a["night_judge"]["report"], "21시: 자동 판정")
        j = post("/api/dev/clock", {"uid": uid, "hour": None})
        ok(j["hour"] is None, "hour=null → 실제 시계로")
        ok(C.post("/api/dev/clock", json={"uid": uid, "hour": 25}).status_code == 400, "0~23시만")
    finally:
        S.DEV_MODE = False
        S.now_hour = lambda: 10


TESTS = [t_dev_clock, t_seat_slot, t_options_follow_card, t_test_arks_excluded, t_reset_script]

if __name__ == "__main__":
    for t in TESTS:
        print(f"\n## {t.__name__} — {(t.__doc__ or '').strip().splitlines()[0] if t.__doc__ else ''}")
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
