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


TESTS = [t_options_follow_card, t_test_arks_excluded, t_reset_script]

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
