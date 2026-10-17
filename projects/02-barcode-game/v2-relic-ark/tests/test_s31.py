"""S31 서버 검증 — 8차 플레이테스트.

① r8-1 보장 귀함 → 가보 길(문어 조각 「어디로」 가보 후보, 선반 「가보로 드리기」 /api/relic/where + /api/give relic_id),
   해금 방송은 고를 화면이 있을 때만, r8-2 선반 이름(display_name)
② 아침엔 기억 하나를 저녁 몫으로 · 아침에 걸음 간 작은 매듭은 같은 저녁 한 걸음 더
③ 아는 칸이 적은 방주(B): 라벨 꺼진 날 첫 칸 = 기색이 맞는 사람
④ POST /api/dev/raid (개발 전용)

실행:  python tests/test_s31.py
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

S.DB = Path(tempfile.mkdtemp()) / "t31.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.NEW_STATE_SEED = "s31"
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


def item(cat, sub, name, code, rarity="common"):
    return {"name": name, "category": cat, "subtype": sub, "family": None, "rarity": rarity, "barcode": code, "card_id": f"c-{code}"}


def resident(st, role):
    return next((r for r in st["residents_list"] if r["role"] == role), None)


# ─────────────────────────────────────────────────────────────
def t_guaranteed_to_heirloom():
    """① 보장 귀함(문어) → 문어 조각 「어디로」 가보 후보 맨 앞 → 가보로 놓인다. 선반 이름 = 문어 줄 이름."""
    uid = "dev_s31_gr"
    a = to_play_day(uid, 4)
    st = S.load_state(uid)
    g = st["octopus"]["gift_relic"]
    ok(g and S.item_safe({"category": g["category"], "subtype": None}), f"보장 귀함 갈래 {g and g['category']}(담배·약 아님)")
    ogw = a.get("octopus_gift_where") or ark(uid).get("octopus_gift_where")
    ok(ogw and ogw.get("heirloom") and ogw.get("heirloom_first"), f"문어 조각 「어디로」 가보 후보 {len((ogw or {}).get('heirloom') or [])}")
    row = next(x for x in a["shelf"] + (a.get("stored") or []) if x.get("card_id") == g["card_id"])
    ok(row.get("display_name") == g["name"], f"선반 이름 = 문어 줄 이름 「{row.get('display_name')}」(소품 「{row.get('name')}」)")
    new_all = [n["feature"] for n in a["unlocked"]["new"]]
    ok("heirloom" in new_all or "heirloom" in S.core_of(S.load_state(uid))["flags"].get("unlock_shown", []),
       "고를 화면(문어 조각)이 있으니 가보 방송이 나갔다")
    rid = ogw["heirloom"][0]["target"]["resident_id"]
    out = post("/api/give", {"uid": uid, "relic_id": g["card_id"], "target": {"resident_id": rid, "heirloom": True}})
    ok(out.get("heirloom") and out["heirloom"]["tier"] == "rare", f"가보로 놓임 → {out.get('heirloom') and out['heirloom']['lines']['placed']}")


def t_octo_tobacco_category():
    """① 문어 조각이 담배 갈래 조각이어도 선반 물건은 담배 갈래가 아니다."""
    uid = "dev_s31_tob"
    ark(uid)
    st = S.load_state(uid)
    f = next(x for x in S.OCTOPUS["finds"] if x.get("favor_category") == "tobacco")
    g = S.octopus_gift_relic(st, f, S.day_of(st))
    ok(g["category"] == "stationery", f"담배 조각 → {g['category']}")


def t_shelf_heirloom_path():
    """① 선반의 귀함 → /api/relic/where 가보 후보 → /api/give relic_id 가보. 방송은 고를 화면이 있을 때만."""
    uid = "dev_s31_shelf"
    to_play_day(uid, 3)
    st = S.load_state(uid)
    f = S.core_of(st)["flags"]
    f["first_rare_day"] = 1
    f["heir_open_day"] = S.day_of(st)
    f["guaranteed_rare_day"] = 1                     # 보장 귀함은 이 시험에서 끈다
    st["shelf"] = []
    st["stored"] = []
    S.save_state(uid, st)
    st = S.load_state(uid)
    ok(S.is_unlocked(st, "heirloom") and not S.heir_choosable(st, uid), "가보 칸은 열렸지만 고를 물건이 없다")
    new = S.unlock_new(st, uid)
    ok(not any(n["feature"] == "heirloom" for n in new), "고를 화면이 없으면 가보 방송을 미룬다")
    card = {"category": "food", "rarity": "rare", "id": "rare-1", "name": "귀한 면 상자", "barcode": None, "_day": S.day_of(st), "subtype": "noodle"}
    S.shelf_place(st, card)
    S.save_state(uid, st)
    st = S.load_state(uid)
    ok(S.heir_choosable(st, uid), "선반에 귀함 → 고를 화면 있음")
    w = get(f"/api/relic/where?uid={uid}&relic_id=rare-1")
    ok(w.get("heirloom") and w["heirloom_label"] and any(n["feature"] == "heirloom" for n in w["unlock_new"]),
       f"선반 「어디로」 가보 {len(w.get('heirloom') or [])}명 + 방송 함께")
    rid = w["heirloom"][0]["target"]["resident_id"]
    out = post("/api/give", {"uid": uid, "relic_id": "rare-1", "target": {"resident_id": rid, "heirloom": True}})
    ok(out.get("heirloom"), "선반에서 가보로 드림")


def t_memory_reserve():
    """② 아침: 기억 후보는 줄 끝(저녁 몫, 고르면 줄 수 있다). 저녁엔 그대로·첫 칸."""
    uid = "dev_s31_mem"
    to_play_day(uid, 4)
    st = S.load_state(uid)
    hit = None
    for c, subs in S.SUBTYPE_KO.items():
        for s_ in subs:
            it = item(c, s_, "기억 것", f"m-{c}-{s_}")
            if not S.item_safe(it):
                continue
            tiers = [S.resident_tier(st, uid, r, it)[0] for r in st["residents_list"]]
            if "memory" in tiers and sum(1 for t in tiers if t != "not_for_me") >= 2:
                hit = it
                break
        if hit:
            break
    ok(hit, "기억 후보 + 다른 후보가 있는 물건 찾음")
    w = S.where_for(st, uid, hit)
    ppl = [x for x in w["suggest"] if x["kind"] == "resident"]
    mem_ids = {r["id"] for r in st["residents_list"] if S.resident_tier(st, uid, r, hit)[0] == "memory"}
    mrow = next((x for x in ppl if x["target"]["resident_id"] in mem_ids), None)
    ok(mrow and ppl[-1] is mrow and mrow.get("evening_reserve"), f"아침: 기억 후보는 줄 끝(저녁 몫) {[x['name'] for x in ppl]}")
    S.now_hour = lambda: 19
    w2 = S.where_for(st, uid, hit)
    p2 = [x for x in w2["suggest"] if x["kind"] == "resident"]
    ok(p2 and p2[0]["target"]["resident_id"] in mem_ids and not p2[0].get("evening_reserve"), "저녁: 기억 후보가 첫 칸")
    S.now_hour = lambda: 10


def t_evening_small_step():
    """② 아침에 걸음 간 사슬의 작은 다음 걸음(min_days_after_prev ≤ 1)은 같은 저녁에 한 번 더 열린다."""
    uid = "dev_s31_step"
    ark(uid)
    st = S.load_state(uid)
    d = S.day_of(st)
    s = {"step": 1, "last_day": d, "last_evening": False, "asks": {}, "done": False}
    small = {"step": 2, "size": "small", "trigger": {"min_days_after_prev": 1}}
    big = {"step": 2, "size": "big", "trigger": {"min_days_after_prev": 1}}
    slow = {"step": 2, "size": "small", "trigger": {"min_days_after_prev": 2}}
    ok(not S.evening_step_ok(st, s, small), "아침에는 같은 날 다음 걸음 없음")
    S.now_hour = lambda: 19
    ok(S.evening_step_ok(st, s, small) and not S.arc_today_blocked(st, s, small), "저녁: 작은 걸음(간격 1) 열림")
    ok(not S.evening_step_ok(st, s, big) and not S.evening_step_ok(st, s, slow), "큰 걸음·간격 2는 안 열림")
    ok(not S.evening_step_ok(st, dict(s, last_evening=True), small), "저녁에 이미 걸었으면 안 열림")
    ok(not S.evening_step_ok(st, dict(s, evening_extra_day=d), small), "저녁 덤은 하루 한 번")
    S.now_hour = lambda: 10


def t_low_known_first():
    """③ 라벨 꺼진 날, 방주 전체 아는 칸 < 3 이면 지금 물건과 기색이 맞는 사람이 첫 칸(first_reason fit)."""
    uid = "dev_s31_low"
    to_play_day(uid, 4)
    st = S.load_state(uid)
    ok(not S.labels_shown(st) and S.known_total(st) < S.LOW_KNOWN, f"4일째 아는 칸 {S.known_total(st)}")
    hit = None
    for c, subs in S.SUBTYPE_KO.items():
        for s_ in subs:
            it = item(c, s_, "맞는 것", f"l-{c}-{s_}")
            if S.item_safe(it) and any(S.resident_tier(st, uid, r, it)[0] in ("need", "like") for r in st["residents_list"]):
                hit = it
                break
        if hit:
            break
    w = S.where_for(st, uid, hit)
    ppl = [x for x in w["suggest"] if x["kind"] == "resident"]
    fit = {r["id"] for r in st["residents_list"] if S.resident_tier(st, uid, r, hit)[0] in ("need", "like", "memory", "chain_beat")}
    ok(ppl and ppl[0]["target"]["resident_id"] in fit and ppl[0].get("first_reason") in ("fit", "known"), f"첫 칸 {ppl[0]['name']} ({ppl[0].get('first_reason')})")
    for r in st["residents_list"]:
        for sl in S.notebook_slots(st, uid, r)[:2]:
            S.nb_known(st, r["id"])[sl["key"]] = {"day": 1, "how": "t"}
    ok(S.known_total(st) >= S.LOW_KNOWN, "아는 칸이 넉넉해지면")
    w2 = S.where_for(st, uid, hit)
    ok(not any(x.get("first_reason") == "fit" for x in w2["suggest"]), "기색 첫 칸 규칙은 꺼진다")


def t_dev_raid():
    """④ POST /api/dev/raid: 개발에서는 그 생물로 새 습격, 배포에서는 404."""
    uid = "dev_s31_draid"
    ark(uid)
    r = post("/api/dev/raid", {"uid": uid, "creature": "straight_one"})
    ok(r["raid"] and r["raid"]["creature"]["id"] == "straight_one" and r["raid"]["stage"] == "sound", "곧은치 습격 열림(1일째라도)")
    ok(C.post("/api/dev/raid", json={"uid": uid, "creature": "nope"}).status_code == 400, "없는 생물 400")
    S.DEV_MODE = False
    ok(C.post("/api/dev/raid", json={"uid": uid, "creature": "longneck"}).status_code == 404, "배포에서는 404")
    S.DEV_MODE = True


def t_heir_nobody_fits():
    """① 아무도 맞지 않는 귀함(모두 not_for_me)이어도 가까운 사람 둘이 가보 후보로 나온다(r8-1 라이브 재현)."""
    uid = "dev_s31_nofit"
    to_play_day(uid, 3)
    st = S.load_state(uid)
    S.core_of(st)["flags"].update({"first_rare_day": 1, "heir_open_day": 1})
    hit = None
    for c, subs in S.SUBTYPE_KO.items():
        for s_ in subs:
            it = item(c, s_, "아무도 안 맞는 귀한 것", f"n-{c}-{s_}", "rare")
            if S.item_safe(it) and all(S.resident_tier(st, uid, r, it)[0] == "not_for_me" for r in st["residents_list"]):
                hit = it
                break
        if hit:
            break
    if not hit:
        ok(True, "이 방주엔 모두 안 맞는 물건이 없음(건너뜀)")
        return
    opts = S.heirloom_options(st, uid, hit)
    ok(len(opts) == 2 and all(o["near"] for o in opts) and not opts[0]["second"] and opts[1]["second"],
       f"가까운 사람 둘: {[o['name'] for o in opts]} (첫째는 바로 보임, 둘째는 「다른 분도」)")


def t_guaranteed_many_arks():
    """① 보장 귀함은 어느 방주에서나 가보 후보가 있다(시드 여러 개, r8-1 라이브 재현: 약 조각)."""
    bad = []
    for i in range(6):
        uid = f"dev_s31_many{i}"
        S.NEW_STATE_SEED = f"m{i}"
        a = to_play_day(uid, 4)
        g = (a.get("octopus_gift_where") or {})
        if not g.get("heirloom"):
            bad.append((uid, g.get("name")))
    S.NEW_STATE_SEED = "s31"
    ok(not bad, f"6개 방주 모두 문어 조각에 가보 후보 (없음: {bad})")


TESTS = [t_guaranteed_to_heirloom, t_heir_nobody_fits, t_guaranteed_many_arks, t_octo_tobacco_category, t_shelf_heirloom_path, t_memory_reserve, t_evening_small_step,
         t_low_known_first, t_dev_raid]

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
