"""S24 서버 검증 — 안전 목록(담배·술·약을 찾으러 보내지 않음), 손으로 친 스캔은 전역 집계 제외, 도감 완성·보상에서 담배 제외.

실행:  python tests/test_s24.py
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
S.CALENDAR_ENFORCE = False   # S25: 이 스위트는 해금 달력 전 기능 자체를 시험한다(달력은 test_s25)
S.VOTES_EXCLUDE_TEST = False   # 전역 투표 장치를 시험한다(시험 방주 제외는 test_s25b)
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t24.db"
S.DEV_MODE = True
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


def get(path, code=200):
    r = C.get(path)
    assert r.status_code == code, (path, r.status_code, r.text)
    return r.json()


def post(path, body, code=200):
    r = C.post(path, json=body)
    assert r.status_code == code, (path, r.status_code, r.text)
    return r.json()


def t_data_safe():
    """지금 데이터: 필요·사슬 건네기 조건에 안전 목록 밖이 없다."""
    ok(S.safety_audit() == [], f"안전 점검 {S.safety_audit()}")
    ok(S.safe_rule({"category": "tobacco", "subtype": ["smoke"]}) is None, "담배 → 없음")
    ok(S.safe_rule({"category": "medical", "subtype": ["pill", "bandage"]}) == {"category": "medical", "subtype": ["bandage"]},
       "약·붕대 → 붕대만")
    ok(S.safe_rule({"category": "medical"}) == {"category": "medical", "subtype": ["bandage"]}, "의약 아무거나 → 붕대로 좁힘")
    ok(S.safe_rule({"category": "medical", "subtype": ["disinfect"]}) is None, "소독 → 없음(의약은 붕대만)")
    ok(S.safe_rule({"category": "drink", "subtype": ["alcohol"]}) is None, "술 → 없음")


def t_guard_needs_and_tomorrow():
    """데이터 실수 가드: 필요 목록에 담배가 있어도 필요·내일의 부탁에 안 나온다."""
    uid = "dev_s24_needs"
    get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    sc = next(r for r in st["residents_list"] if r["role"] == "scout")
    rt = S.TASTES["roles"]["scout"]
    old = rt["needs"]
    rt["needs"] = [{"category": "tobacco", "subtype": ["smoke"]}, {"category": "medical", "subtype": ["pill"]}, old[0]]
    try:
        days = [S.need_today(uid, sc, d) for d in range(1, 40)]
        ok(all(d and d["category"] not in S.SAFE_EXCLUDE_CATS and not set(d.get("subtype") or []) & {"pill", "tonic", "alcohol"} for d in days),
           f"39일 필요가 모두 안전 {sorted({d['ko'] for d in days})}")
        ok(all(d["idx"] == 2 for d in days), "칸 번호는 원래 목록의 번호(기색·내일 줄과 짝)")
        ta = S.tomorrow_ask(st, uid)
        ok(ta and ta["need"]["category"] not in S.SAFE_EXCLUDE_CATS, f"내일의 부탁 안전 {ta and ta['need']['ko']}")
        slots = [x for x in S.notebook_slots(st, uid, sc) if x["kind"] == "need"]
        ok(all(x["rule"]["category"] not in S.SAFE_EXCLUDE_CATS for x in slots), "수첩 필요 칸도 안전만")
        ok(S.safety_audit(), f"점검이 잡는다 {S.safety_audit()}")
    finally:
        rt["needs"] = old


def t_guard_arc_and_memory():
    uid = "dev_s24_arc"
    get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    r = st["residents_list"][0]
    s_ = {"step": 0}
    ok(not S.trig_one(st, uid, r, s_, "give", {"category": "tobacco", "to": "self"},
                      {"item": {"category": "tobacco", "subtype": "smoke"}, "to": r["id"]}), "담배 건네기 조건은 풀리지 않는다")
    ok(S.trig_one(st, uid, r, s_, "give", {"category": "medical", "subtype": ["pill", "bandage"], "to": "self"},
                  {"item": {"category": "medical", "subtype": "bandage"}, "to": r["id"]}), "섞인 조건은 안전한 쪽(붕대)으로")
    ok(not S.trig_one(st, uid, r, s_, "give", {"category": "medical", "subtype": ["pill", "bandage"], "to": "self"},
                      {"item": {"category": "medical", "subtype": "pill"}, "to": r["id"]}), "약으로는 안 풀린다")
    tr = next(x for x in S.TASTES["roles"]["trader"].get("memories") or [] if (x.get("trigger") or {}).get("category") == "tobacco") \
        if any((x.get("trigger") or {}).get("category") == "tobacco" for x in S.TASTES["roles"]["trader"].get("memories") or []) else None
    trader = S.make_resident("trader", __import__("random").Random(3), set(), uid)
    keys = [x["key"] for x in S.notebook_slots(st, uid, trader)]
    if tr:
        ok(f"memory:{tr['id']}" not in keys, f"담배 기억은 수첩 칸에 없다 {keys}")
    ok(not S.safe_rule({"category": "tobacco"}, strict=True), "기억 실마리도 담배는 없다")


def t_codex_tobacco():
    uid = "dev_s24_codex"
    get(f"/api/ark?uid={uid}")
    cx = get(f"/api/codex?uid={uid}")
    tob = next(x for x in cx if x["category"] == "tobacco")
    ok(tob["in_completion"] is False and all(x["in_completion"] for x in cx if x["category"] != "tobacco"), "도감 완성에서 담배 제외(목록에는 있음)")
    col = get(f"/api/collection?uid={uid}")
    tf = [f for f in col["families"] if f["category"] == "tobacco"]
    ok(tf and all(not f["in_completion"] for f in tf) and col["families_total"] == len(col["families"]) - len(tf),
       f"가문 세트 합계에서 담배 {len(tf)}곳 제외 → {col['families_total']}")
    st = S.load_state(uid)
    code = next(c for c in S.FAMILY_NAMES if S._KNOWN_FAM_CAT.get(c) == "tobacco")
    m0 = st["resources"]["morale"]
    total = int(S.stk("family_sets.pieces_required"))
    with S.db() as con:
        for i in range(total):
            con.execute("INSERT INTO scans(uid,barcode,category,rarity,mult,ts,day) VALUES(?,?,?,?,?,?,?)",
                        (uid, ean(code + f"{i:05d}"), "tobacco", "common", 1.0, 1.0, 1))
    fs = S.family_set_check(st, uid, code)
    ok(fs and fs["just_completed"] and not (fs["reward"] or {}).get("morale") and st["resources"]["morale"] == m0,
       f"담배 가문 한 벌 → 보상 없음 {fs and fs['reward']}")


def t_manual_scan():
    """손으로 친 스캔: 개인 놀이는 그대로, 전역 이름 투표·미리 고름에는 들어가지 않는다."""
    code = ean("490123422001")
    for i in range(3):
        uid = f"dev_s24_m{i}"
        get(f"/api/ark?uid={uid}")
        j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink", "source": "manual"})
        ok(j["card"] and j["where"]["subtype_pick"], "손 입력도 카드·고르기는 그대로")
        post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": "milk"})
    with S.db() as con:
        n = con.execute("SELECT COUNT(*) c FROM subtype_votes WHERE barcode=?", (code,)).fetchone()["c"]
        src = {r["source"] for r in con.execute("SELECT source FROM scans WHERE barcode=?", (code,)).fetchall()}
    ok(n == 0 and src == {"manual"}, f"손 입력 투표 0표, 스캔 출처 {src}")
    ok(S.subtype_vote_suggest(code, "drink") is None, "미리 고름 없음")
    for i in range(3):
        uid = f"dev_s24_c{i}"
        get(f"/api/ark?uid={uid}")
        j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
        post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": "milk"})
    uid = "dev_s24_m_new"
    get(f"/api/ark?uid={uid}")
    jm = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink", "source": "manual"})
    ok(jm["where"]["subtype_pick"]["suggest"] is None, "손 입력 스캔에는 다른 방주 이름을 보여 주지 않는다")
    jc = post("/api/scan", {"uid": "dev_s24_c_new", "barcode": code, "user_category": "drink"}) if get("/api/ark?uid=dev_s24_c_new") else None
    ok(jc["where"]["subtype_pick"]["suggest"] and jc["where"]["subtype_pick"]["suggest"]["arks"] == 3, "카메라 스캔은 카메라 표만 센다(3곳)")


def t_like_safety():
    """좋아함 쪽: 담배·술·약은 「어디로」에서 '좋아함'으로 권하지 않고, 수첩 찾을 것·기색에도 쓰지 않는다(우연히 주면 괜찮다)."""
    import random as _r
    uid = "dev_s24_like"
    get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    tr = S.make_resident("trader", _r.Random(7), {r["name"] for r in st["residents_list"]}, uid)
    tr["joined"] = st["created"]
    S.ensure_stats(uid, tr)
    st["residents_list"].append(tr)
    S.save_state(uid, st)
    st = S.load_state(uid)
    tr = next(r for r in st["residents_list"] if r["role"] == "trader")
    likes = S.likes_of(uid, tr)
    tob = [i for i, x in enumerate(likes) if x.get("category") == "tobacco"]
    ok(tob, f"교섭가 좋아함에 담배가 있다(데이터) {[x.get('category') for x in likes]}")
    keys = [x["key"] for x in S.notebook_slots(st, uid, tr)]
    ok(all(f"like:{i}" not in keys for i in tob), f"수첩 찾을 것에 담배 좋아함 없음 {keys}")
    it = {"name": "연기 막대", "category": "tobacco", "subtype": "smoke", "family": None, "rarity": "common", "barcode": "xtob", "card_id": None}
    w = S.where_for(st, uid, it)
    row = next((x for x in w.get("_internal") or w["suggest"] if x["target"].get("resident_id") == tr["id"]), None)
    ok(not row or row["tier"] != "like", f"담배를 '좋아함'으로 권하지 않는다 {row and row['tier']}")
    out = S.give_apply(st, uid, it, {"resident_id": tr["id"]}, "copy")
    ok(out["tier"] == "like", "우연히 주면 반응은 그대로(좋아함)")
    S.core_of(st)["beats"]["play_day"] = 5
    st["created"] -= 86400 * 4
    h = S.sign_hint(st, uid, tr, it, "like", f"like:{tob[0]}", set())
    sl = (S.role_taste("trader").get("signs") or {}).get("likes") or []
    banned = sl[tob[0]] if tob[0] < len(sl) else []
    ok(h and all(S.fill_text(b, st, tr, it) != h for b in banned), f"담배 칸 기색 줄은 쓰지 않는다: {h}")
    ok(S.item_safe({"category": "medical", "subtype": "bandage"}) and not S.item_safe({"category": "medical", "subtype": "pill"})
       and not S.item_safe({"category": "drink", "subtype": "alcohol"}), "item_safe: 붕대만 의약")


TESTS = [t_like_safety, t_data_safe, t_guard_needs_and_tomorrow, t_guard_arc_and_memory, t_codex_tobacco, t_manual_scan]

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
