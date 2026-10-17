"""S25 서버 검증 — 첫 주 해금 달력(켠 날 차례), 가보 칸(귀함 이상·한 사람 한 칸·바꾸기 물음·닦아 오르기·세 번째 기억·진열 드문 손님).

실행:  python tests/test_s25.py
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

S.DB = Path(tempfile.mkdtemp()) / "t25.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False   # 전역 투표 장치를 시험한다(시험 방주 제외는 test_s25b)
S.init_db()
C = TestClient(S.app)
S.UNLOCK_CAL["conditional"]["heirloom"]["min_play_day"] = 1   # S27 가보 3일째는 test_s27
RESULTS: list[tuple[bool, str]] = []
S.now_hour = lambda: 10
S.DAYTIME_TABLE = False          # S27 낮 한 상은 test_s27 이 본다
S.NEW_STATE_SEED = "t25"         # 시작 주민을 uid 로 고정(시각 시드면 성향이 매번 달라 흔들렸다)


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


def ark(uid):
    return get(f"/api/ark?uid={uid}")


def next_day(uid):
    post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
    return ark(uid)


def item(cat, sub, name, code, rarity="rare"):
    return {"name": name, "category": cat, "subtype": sub, "family": None, "rarity": rarity, "barcode": code, "card_id": f"c-{code}"}


def resident(st, role):
    return next((r for r in st["residents_list"] if r["role"] == role), None)


# ─────────────────────────────────────────────────────────────
def t_calendar():
    """해금 달력: 켠 날 차례로 기능이 열리고, 열리기 전엔 서버가 받지 않는다."""
    uid = "dev_s25_cal"
    a = ark(uid)
    f = set(a["unlocked"]["features"])
    ok({"scan", "give_where_labels"} <= f and "decor_place" not in f and "raids" not in f and "expedition" not in f,
       f"1일째 열린 것 {sorted(f)}")
    ok(not [x for x in S.where_for(S.load_state(uid), uid, item("food", "noodle", "면", "n1", "common"))["suggest"] if x["kind"] == "room"],
       "1일째 「어디로」에 방(꾸밈) 없음")
    r = C.post("/api/give", json={"uid": uid, "relic_id": "zzz", "target": {"slot": 2}})
    ok(r.status_code in (400, 403), "꾸밈은 열리기 전 거절")
    ok(C.get(f"/api/expedition/options?uid={uid}").status_code == 403, "원정 1일째 403")
    rt = get(f"/api/raid/today?uid={uid}")
    ok(not rt.get("raid"), "습격 1일째 없음")
    lv = get(f"/api/leaving?uid={uid}")
    ok(lv["unlock_teaser"] and lv["unlock_teaser"]["line"] == S.BEATS["1"]["teaser"] and "decor_place" in lv["unlock_teaser"]["unlocks"],
       f"떠날 때 내일 예고(beats.json teaser): {lv['unlock_teaser'] and lv['unlock_teaser']['line']}")
    a = next_day(uid)
    ok("decor_place" in a["unlocked"]["features"] and any(n["feature"] == "decor_place" for n in a["unlocked"]["new"]),
       f"2일째 꾸밈 열림 + 방송 {[n['feature'] for n in a['unlocked']['new']]}")
    ok(S.labels_shown(S.load_state(uid)), "2일째까지 라벨")
    lv = get(f"/api/leaving?uid={uid}")
    ok(lv["unlock_teaser"] and lv["unlock_teaser"]["required"] == bool(S.BEATS["2"].get("teaser_required")), "2일째 예고(필수 표시)")
    a = next_day(uid)
    ok(S.labels_shown(S.load_state(uid)) and "notebook" not in a["unlocked"]["features"], "3일째까지 라벨(S27: 4일째에 꺼짐)")
    # 사흘을 쉬어도 켠 날 차례: 실제 7일째, 켠 날 4
    post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24 * 3})
    a = ark(uid)
    ok(not S.labels_shown(S.load_state(uid)) and "notebook" in a["unlocked"]["features"], "4일째 기색·수첩(S27)")
    ok(a["unlocked"]["play_day"] == 4 and "raids" in a["unlocked"]["features"] and "expedition" not in a["unlocked"]["features"],
       "켠 날 4: 습격 열림, 원정은 아직(실제 날짜와 무관)")
    a = next_day(uid)
    ok("expedition" in a["unlocked"]["features"] and C.get(f"/api/expedition/options?uid={uid}").status_code == 200, "켠 날 5: 원정")
    a = next_day(uid)
    S.now_hour = lambda: 19
    a2 = ark(uid)
    S.now_hour = lambda: 10
    ok("evening_table" in a2["unlocked"]["features"] and a2["evening_table"], "켠 날 6: 한 상")


def t_calendar_early_locks():
    uid = "dev_s25_cal2"
    ark(uid)
    st = S.load_state(uid)
    S.now_hour = lambda: 19
    ok(S.evening_table_public(st, uid) is None, "1일째 저녁에도 한 상 없음")
    S.now_hour = lambda: 10
    cook = resident(st, "cook")
    ok(S.is_unlocked(st, "first_chain_knot"), "S27: 첫 매듭은 1일째부터(요리사 의자)")
    r = C.post("/api/octopus/name", json={"uid": uid, "name": "먹물"})
    ok(r.status_code in (400, 403), "문어 이름 짓기 2일째 전 거절")


def t_subtype_wanted():
    uid = "dev_s25_sub"
    ark(uid)
    st = S.load_state(uid)
    j = post("/api/scan", {"uid": uid, "barcode": ean("490123411001"), "user_category": "drink"})
    sp = j["where"]["subtype_pick"]
    ok(sp and sp["needed"] is True and sp["later_ok"], "누군가 바라는 갈래(음료) → 묻는다")
    st = S.load_state(uid)
    wants = {x.get("category") for r in st["residents_list"] for x in list(S.role_taste(r["role"]).get("needs") or []) + S.likes_of(uid, r)}
    cat = next(c for c in ("book", "tobacco", "medical", "apparel", "stationery", "electronics") if c not in wants and c != "book") \
        if any(c not in wants for c in ("tobacco", "medical", "apparel", "stationery", "electronics")) else None
    if cat:
        j2 = post("/api/scan", {"uid": uid, "barcode": ean("490123411018"), "user_category": cat})
        sp2 = j2["where"]["subtype_pick"]
        ok(sp2 is None or sp2["needed"] is False, f"아무도 안 바라는 갈래({cat}) → 묻지 않음(나중에 이름 붙이기)")


def t_heirloom():
    uid = "dev_s25_heir"
    ark(uid)
    st = S.load_state(uid)
    ok(not S.heirloom_options(st, uid, item("food", "noodle", "귀한 면", "h1")), "첫 귀함 카드 전에는 가보 칸 없음")
    S.core_of(st)["flags"]["first_rare_day"] = 1
    sc, cook = resident(st, "scout"), resident(st, "cook")
    it = item("food", "noodle", "귀한 면", "h1")
    opts = S.heirloom_options(st, uid, it)
    nfm = sum(1 for r in st["residents_list"] if S.resident_tier(st, uid, r, it)[0] == "not_for_me")
    ok(len([o for o in opts if not o.get("second")]) == len(st["residents_list"]) - nfm and all(o["target"]["heirloom"] and o["value"] == S.HEIR_V for o in opts),
       f"귀함 → 가보 선택지 {[o['label'] for o in opts]}")
    ok(not S.heirloom_options(st, uid, item("food", "noodle", "보통 면", "h0", "uncommon")), "쓸만함 이하는 가보 아님")
    ok(not S.heirloom_options(st, uid, item("tobacco", "smoke", "연기", "ht")), "안전 목록 밖은 가보 아님")
    S.save_state(uid, st)
    # 스캔 기록을 만들어 API 로 건넨다
    st = S.load_state(uid)
    S.core_of(st)["scans"]["sh1"] = {"item": it, "day": S.day_of(st), "given": False, "placed": "copy", "at": time.time()}
    S.save_state(uid, st)
    g = post("/api/give", {"uid": uid, "scan_id": "sh1", "target": {"resident_id": cook["id"], "heirloom": True}})
    ok(g["ok"] and g["heirloom"]["tier"] == "rare" and g["value"] == S.HEIR_V and g["heirloom"]["lines"]["placed"] and g["heirloom"]["lines"]["use"],
       f"가보 → {g['heirloom']['lines']['placed']}")
    ok(g["tier"] in ("like", "need", "warm", "chain_beat", "memory", "not_for_me"), f"보통 건네기도 판정 {g['tier']}")
    st = S.load_state(uid)
    ok(resident(st, "cook")["heirloom"]["barcode"] == "h1", "칸에 놓임")
    # 같은 바코드는 한 사람의 가보만
    S.core_of(st)["scans"]["sh2"] = {"item": dict(it, card_id="c-h1b"), "day": S.day_of(st), "given": False, "placed": "copy", "at": time.time()}
    S.save_state(uid, st)
    r = C.post("/api/give", json={"uid": uid, "scan_id": "sh2", "target": {"resident_id": sc["id"], "heirloom": True}})
    ok(r.status_code == 400 and "가보" in r.json()["detail"], "같은 바코드는 다른 사람 가보가 못 된다")
    # 바꿀까요?
    it2 = item("drink", "tea", "진귀한 차", "h2", "epic")
    st = S.load_state(uid)
    S.core_of(st)["scans"]["sh3"] = {"item": it2, "day": S.day_of(st), "given": False, "placed": "copy", "at": time.time()}
    S.save_state(uid, st)
    q = post("/api/give", {"uid": uid, "scan_id": "sh3", "target": {"resident_id": cook["id"], "heirloom": True}})
    ok(q["ok"] is False and q["ask_swap"]["default"] == "keep" and "{" not in q["ask_swap"]["line"], f"바꿀까요? {q['ask_swap']['line']}")
    st = S.load_state(uid)
    ok(resident(st, "cook")["heirloom"]["barcode"] == "h1" and not S.core_of(st)["scans"]["sh3"]["given"], "묻기만 하면 그대로")
    g = post("/api/give", {"uid": uid, "scan_id": "sh3", "target": {"resident_id": cook["id"], "heirloom": True, "swap": True}})
    st = S.load_state(uid)
    ck = resident(st, "cook")
    ok(g["heirloom"]["swapped"] and ck["heirloom"]["barcode"] == "h2" and ck["heirloom_history"][0]["name"] == "귀한 면"
       and g["heirloom"]["lines"].get("speak"), f"바꿈 → 이력·진귀함 대사 {g['heirloom']['lines'].get('speak')}")
    # 전설 → 세 번째 기억(한 번, 바꿔도 닫히지 않음)
    # S27: 돌려줄 물건은 가보가 못 된다 → 정찰병이 받는(not_for_me 아님) 안전한 전설 물건을 결정적으로 고른다
    # (예전 목록에 없는 갈래 tool·clothing 이 섞여 있어, 주민 성향이 시각 시드로 바뀌면 StopIteration 이 났다)
    it3 = next(item(c, s_, "전설의 물건", "h3", "legendary") for c, subs in sorted(S.SUBTYPE_KO.items()) for s_ in sorted(subs)
               if S.item_safe({"category": c, "subtype": s_})
               and S.resident_tier(st, uid, resident(st, "scout"), item(c, s_, "전설의 물건", "h3", "legendary"))[0] != "not_for_me")
    S.core_of(st)["scans"]["sh4"] = {"item": it3, "day": S.day_of(st), "given": False, "placed": "copy", "at": time.time()}
    S.save_state(uid, st)
    g = post("/api/give", {"uid": uid, "scan_id": "sh4", "target": {"resident_id": sc["id"], "heirloom": True}})
    st = S.load_state(uid)
    ok(g["heirloom"]["third_memory"] and resident(st, "scout")["third_memory_open"], f"전설 → 세 번째 기억 {g['heirloom']['third_memory']['announce'][:30]}")
    a = ark(uid)
    ok(a["core"]["residents"][sc["id"]]["heirloom"]["tier"] == "legendary" and a["core"]["residents"][sc["id"]]["third_memory_open"],
       "/api/ark core.residents.heirloom·third_memory_open")


def t_heirloom_polish():
    """닦아 오르기: 가보 바코드를 서로 다른 날 6번 → 한 등급 위."""
    uid = "dev_s25_pol"
    ark(uid)
    st = S.load_state(uid)
    eng = resident(st, "engineer")
    eng["heirloom"] = {"card_id": "c-p", "barcode": "pcode", "name": "귀한 줄", "category": "electronics", "rarity": "rare",
                       "tier": "rare", "since_day": 1, "seen_days": [1]}
    ups = []
    for d in range(2, 8):
        st["created"] -= 86400
        ups.append(S.heirloom_polish_tick(st, uid, "pcode"))
        S.heirloom_polish_tick(st, uid, "pcode")
    up = next((u for u in ups if u), None)
    ok(up and up["tier"] == "epic" and eng["heirloom"]["tier"] == "epic" and up["line"], f"6일째 닦아 오름 → {up and up['line']}")
    ok(sum(1 for u in ups if u) == 1, "한 번만 오른다")
    ok(S.heir_tier("rare", 3) == "epic" and S.heir_tier("epic", 3) == "legendary" and S.heir_tier("legendary", 3) == "legendary"
       and S.heir_tier("uncommon", 3) == "uncommon", "닦기 3단계 귀함 이상만 한 등급 위")


def t_display_rare():
    """진귀함 이상을 꼬리표 방 꾸밈 칸에 걸면 드문 손님(0.2/0.35)."""
    uid = "dev_s25_disp"
    ark(uid)
    st = S.load_state(uid)
    S.core_of(st)["rooms"]["2"] = {"items": [dict(item("food", "noodle", "면", "d1", "common"), id="a"),
                                             dict(item("drink", "tea", "차", "d2", "epic"), id="b")]}
    ok(abs(S.display_rare_chance(st, 2) - S.HEIR_RARE_P["epic"]) < 1e-9, "진귀함 → 0.2")
    hits = sum(1 for d in range(1, 301) for v in S.visit_rows_for(st, uid, d) if v.get("form") == "rare")
    ok(abs(hits / 300 - S.HEIR_RARE_P["epic"]) < 0.08, f"드문 손님 {hits}/300일")
    row = next(v for d in range(1, 300) for v in S.visit_rows_for(st, uid, d) if v.get("form") == "rare")
    S.apply_visit_row(st, uid, row)
    book = {b["id"]: b for b in S.visitors_book(st)}
    ok(book[row["visitor_id"]]["rare"]["count"] == 1 and row["line"] and "{room}" not in row["line"], f"도감 드문 칸 {row['ko']}")


def t_raid_heirloom_weight():
    uid = "dev_s25_raid"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    S.set_station(st, cook["id"], 2)
    cook["heirloom"] = {"barcode": "q", "tier": "rare"}
    ok((S.raid_target_weights(st) or {}).get(2) == S.RAID_CHERISHED_MULT, "가보 가진 사람의 방 ×1.5")


def t_seed_guard():
    """흔들림 가드: 시드를 고정하면 같은 uid 의 시작 주민(id·이름)이 매번 같다."""
    a1, a2 = S.new_state("dev_s25_seed"), S.new_state("dev_s25_seed")
    ok([(r["id"], r["name"]) for r in a1["residents_list"]] == [(r["id"], r["name"]) for r in a2["residents_list"]], "시작 주민 고정")


TESTS = [t_seed_guard, t_calendar, t_calendar_early_locks, t_subtype_wanted, t_heirloom, t_heirloom_polish, t_display_rare, t_raid_heirloom_weight]

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
