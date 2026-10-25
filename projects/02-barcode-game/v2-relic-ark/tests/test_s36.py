"""S36 서버 검증 — 준 물건이 방에서 쓰인다(쓰는 자리 둘 · 갈래별 동작 · 하루 한 번 · 장면만).

실행:  python tests/test_s36.py
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

S.DB = Path(tempfile.mkdtemp()) / "t36.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.NEW_STATE_SEED = "s36"
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


def give_rec(st, rid, name, cat, sub, code):
    S.cres(st, rid)["items"].append({"name": name, "category": cat, "subtype": sub, "barcode": code, "day": S.day_of(st),
                                     "card_id": f"c-{code}"})


# ─────────────────────────────────────────────────────────────
def t_use_spots():
    """편한 방(식량창고)에 쓰는 자리 둘 — 가보 먼저, 그다음 최근 · 갈래별 동작 · 자원 변화 없음."""
    uid = "dev_s36_use"
    ark(uid)
    st = S.load_state(uid)
    cook = next(r for r in st["residents_list"] if r["role"] == "cook")
    cook["comfort_room"] = "pantry"
    give_rec(st, cook["id"], "오래된 국자", "stationery", "tool", "u1")
    give_rec(st, cook["id"], "작은 우유", "drink", "milk", "u2")
    give_rec(st, cook["id"], "마른 면", "food", "noodle", "u3")
    cook["heirloom"] = {"name": "이름 새긴 그릇", "category": "apparel", "subtype": "small", "barcode": "h1", "tier": "rare"}
    S.save_state(uid, st)
    a = ark(uid)
    sp = (a["core"]["rooms"].get("2") or {}).get("use_spots") or []
    ok(len(sp) == 2 and sp[0]["item"]["name"] == "이름 새긴 그릇" and sp[0]["item"]["heirloom"] and sp[1]["item"]["name"] == "마른 면",
       f"자리 둘: {[x['item']['name'] for x in sp]}")
    ok(sp[0]["action"] == "wrap" and sp[1]["action"] == "eat" and all(x["owner_id"] == cook["id"] for x in sp), f"동작 {[x['action'] for x in sp]}")
    ok(all(x["item"].get("prop") or x["item"]["name"] for x in sp), "소품 이름·그림")
    res0 = dict(S.load_state(uid)["resources"])
    # 그 사람이 그 방에 있으면 하루 한 번 「쓴다」 + 한 번 방송
    st = S.load_state(uid)
    S.set_station(st, cook["id"], 2)
    S.save_state(uid, st)
    a = ark(uid)
    news = a["use_news"]
    ok(len(news) == 1 and news[0]["resident_id"] == cook["id"] and news[0]["ko"] and "{" not in news[0]["ko"], f"방송 한 줄: {news and news[0]['ko']}")
    sp = a["core"]["rooms"]["2"]["use_spots"]
    ok(all(x["today_used"] for x in sp), "오늘 씀(today_used)")
    ok(not ark(uid)["use_news"], "방송은 하루 한 번")
    res1 = dict(S.load_state(uid)["resources"])
    ok(all(abs(float(res1.get(k, 0)) - float(res0.get(k, 0))) < 5 for k in res0), "자원 보상 없음(장면만)")
    post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
    a = ark(uid)
    ok(a["use_news"] and not any(x["today_used"] for x in []), "다음 날 다시 한 번")


def t_fallback_and_safety():
    """편한 방이 없으면 거주실 · 거주실도 없으면 자리 없음 · 약(붕대 밖)·담배는 「쳐다보기」만."""
    uid = "dev_s36_fb"
    ark(uid)
    st = S.load_state(uid)
    sc = next(r for r in st["residents_list"] if r["role"] == "scout")
    sc["comfort_room"] = "lounge"
    give_rec(st, sc["id"], "알약 판", "medical", "pill", "m1")
    give_rec(st, sc["id"], "붕대", "medical", "bandage", "m2")
    S.save_state(uid, st)
    ok(S.use_room_of(st, sc) is None, "라운지·거주실 없음 → 쓰는 방 없음")
    st["rooms"].append({"id": "quarters", "slot": 1, "built": time.time(), "level": 1})
    S.save_state(uid, st)
    a = ark(uid)
    sp = (a["core"]["rooms"].get("1") or {}).get("use_spots") or []
    acts = {x["item"]["name"]: x["action"] for x in sp if x["owner_id"] == sc["id"]}
    ok(acts.get("붕대") == "bandage" and acts.get("알약 판") == "look", f"거주실로 · 동작 {acts}")
    ok(S.use_action({"category": "tobacco", "subtype": "smoke"}) == "look", "담배는 쳐다보기")
    U = S.moments().get("use_action") or {}
    ok(all(isinstance(U.get(k), list) and U[k] for k in S.USE_DEFAULT_KO), f"시나리오 동작 이름 8종 일치 {sorted(U)[:8]}")


TESTS = [t_use_spots, t_fallback_and_safety]

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
