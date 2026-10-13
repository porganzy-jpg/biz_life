"""S21 서버 검증 — 3차 플레이테스트(docs/reports/playtest_7day_r3_20261006.md §4~7) 서버 원인 고침.

실행:  python tests/test_s21.py
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
S.CALENDAR_ENFORCE = False   # S25: 이 스위트는 해금 달력 전 기능 자체를 시험한다(달력은 test_s25)
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t21.db"
S.DEV_MODE = True
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []
S.now_hour = lambda: 10
DIM = S.CORE_A["give_place"]["diminish"]


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


def item(cat, sub=None, name=None, code=None):
    return {"name": name or f"{cat}-{sub}", "category": cat, "subtype": sub, "family": None, "rarity": "common",
            "barcode": code or f"x{cat}{sub}{name}", "card_id": None}


def resident(st, role):
    return next(r for r in st["residents_list"] if r["role"] == role)


# ─────────────────────────────────────────────────────────────
def t_diminish():
    """1. 감쇠: 같은 세션 ×0.8(세션이 바뀌면 초기화), 같은 물건 ×0.6, 겹치면 작은 쪽만, 숫자는 core_a."""
    ok(S.DIM_SAME_DAY == DIM["same_person_session"] == 0.8 and S.DIM_SAME_ITEM == DIM["same_item_days"] == 0.6,
       f"core_a 감쇠 {S.DIM_SAME_DAY}/{S.DIM_SAME_ITEM}")
    uid = "dev_s21_dim"
    ark(uid)
    st = S.load_state(uid)
    sc = resident(st, "scout")
    lk = S.TASTES["roles"]["scout"]["likes"][0]
    it1, it2 = item(lk["category"], lk["subtype"][0], "등1", "w1"), item("food", "grain", "쌀", "g1")
    S.give_apply(st, uid, it1, {"resident_id": sc["id"]}, "copy")
    m, why = S.give_diminish(st, sc, it2)
    ok(m == 0.8 and why[0]["kind"] == "same_person_today", f"같은 세션 둘째 ×{m}")
    m, why = S.give_diminish(st, sc, it1)
    ok(m == 0.6 and len(why) == 1 and why[0]["kind"] == "same_item_3days", f"같은 세션·같은 물건 → 작은 쪽 하나만 ×{m} {why}")
    S.save_state(uid, st)
    post("/api/dev/advance", {"uid": uid, "minutes": 5 * 60})    # 저녁 세션(같은 날)
    ark(uid)
    st = S.load_state(uid)
    sc = resident(st, "scout")
    m, why = S.give_diminish(st, sc, it2)
    ok(m == 1.0 and not why, f"세션이 바뀌면 같은 사람 감쇠 초기화 ×{m}")
    m, _ = S.give_diminish(st, sc, it1)
    ok(m == 0.6, f"같은 물건 사흘은 세션과 무관 ×{m}")
    # 세션을 모를 때: 4시간 간격
    st2 = S.new_state("dev_s21_nos")
    r = st2["residents_list"][0]
    S.cres(st2, r["id"])["given"] = [dict(item("food", "x", "a", "a"), day=1, at=time.time() - 3 * 3600)]
    ok(S.give_diminish(st2, r, item("drink", "y", "b", "b"))[0] == 0.8, "세션 없음 + 3시간 전 → 같은 세션")
    S.cres(st2, r["id"])["given"] = [dict(item("food", "x", "a", "a"), day=1, at=time.time() - 5 * 3600)]
    ok(S.give_diminish(st2, r, item("drink", "y", "b", "b"))[0] == 1.0, "세션 없음 + 5시간 전 → 새 세션")


def t_decor_loop():
    """2. Lv1 칸 3 · 앞선 꼬리표만 권함 · 첫 꼬리표 다음 날 방문 확정 · 반응 tag_ko 는 제안한 꼬리표."""
    uid = "dev_s21_decor"
    ark(uid)
    st = S.load_state(uid)
    pantry = S.room_at(st, 2)
    ok(S.decor_cap(pantry) == 3, f"Lv1 꾸밈 칸 {S.decor_cap(pantry)}")
    S.give_apply(st, uid, item("food", "noodle", "면", "n1"), {"slot": 2}, "copy")        # 따뜻한 부엌 1/2
    tier, info = S.room_decor_tier(st, uid, pantry, item("book", "story", "책", "b1"))       # 책 냄새를 먹이는 물건
    ok(tier == "plain", f"앞선 꼬리표(따뜻한 부엌)가 아니면 꾸밈 제안 안 함 → {tier}")
    tier, info = S.room_decor_tier(st, uid, pantry, item("drink", "tea", "차", "t1"))
    ok(tier == "decor" and info["tag"] == "warm_kitchen", f"앞선 꼬리표만 권함 {info.get('tag')}")
    # 반응 tag_ko(버그 2): 책 냄새 1개·따뜻한 부엌 1개인 방에 책 냄새 물건 — 반응은 「책 냄새」
    uid2 = "dev_s21_tagko"
    ark(uid2)
    st2 = S.load_state(uid2)
    st2["rooms"].append({"id": "decoder", "slot": 3, "built": time.time(), "level": 1})
    S.give_apply(st2, uid2, item("book", "story", "책1", "bb1"), {"slot": 3}, "copy")
    out = S.give_apply(st2, uid2, item("food", "noodle", "면", "nn1"), {"slot": 3}, "copy")
    tier, info = S.room_decor_tier(st2, uid2, S.room_at(st2, 3), item("stationery", "paper", "종이", "pp1"))
    out = S.give_apply(st2, uid2, item("stationery", "paper", "종이", "pp1"), {"slot": 3}, "copy")
    ann = out["reaction"]["announce"]
    ok(info.get("tag") == "book_smell" and ("책 냄새" in ann or (out["effects"]["decor"]["tag_added"] or {}).get("id") == "book_smell"),
       f"반응 꼬리표 = 제안 꼬리표(책 냄새): {ann}")
    # 첫 꼬리표 → 다음 날 방문 확정
    out = S.give_apply(st, uid, item("drink", "tea", "차", "t1"), {"slot": 2}, "copy")
    vg_ = S.core_of(st)["flags"].get("visit_guarantee", {})
    ok(out["effects"]["decor"]["tag_added"] and vg_.get("day") == S.day_of(st) and vg_.get("at") and not vg_.get("done"),
       "첫 꼬리표 → 손님 확정 표시(S22: 다음 세션, 못 오면 다음 날)")
    vis = [v for v in S.visit_rows_for(st, uid, S.day_of(st) + 1) if v["kind"] == "visitor"]
    ok(vis and vis[0]["visitor_id"] == "steam_eel", f"다음 날 꼬마 장어 확정 {[v['visitor_id'] for v in vis]}")
    nv = S.next_visit_candidates(st, uid)
    ok(any(x["kind"] == "visitor_expected" for x in nv), "떠날 때 약속에 내일 손님(지킬 수 있음)")


def t_warm_not_first():
    """3. warm 이 아닌 제안이 있으면 warm 은 1순위가 아니다."""
    uid = "dev_s21_warm"
    ark(uid)
    post("/api/prefs", {"uid": uid, "labels_always": True})   # S23: 라벨 모드에서의 순서 규칙
    bad = 0
    n = 0
    for i in range(30):
        cat = ("medical", "stationery", "drink", "apparel", "food", "electronics", "tobacco", "book")[i % 8]
        if i % 10 == 9:
            post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
        j = post("/api/scan", {"uid": uid, "barcode": ean(f"88011{i:07d}"), "user_category": cat})
        sg = j["where"]["suggest"]
        if sg and any(x["tier"] != "warm" for x in sg):
            n += 1
            bad += sg[0]["tier"] == "warm"
    ok(n and bad == 0, f"warm 이 첫자리인 스캔 {bad}/{n}")


def t_promises():
    """4. 비트 3일째 물음 없으면 star_no_ask · 5일째 색 조각은 건넬 수 있는 물건 · arc_beat_ready 는 물건·물음이 있을 때만."""
    uid = "dev_s21_beat"
    ark(uid)
    st = S.load_state(uid)
    for r in st["residents_list"]:
        for s_ in S.cres(st, r["id"])["arcs"].values():
            s_.pop("ask_pending", None)
    b3 = S.beat_compose(st, uid, 3)
    want = S.BEATS["3"].get("star_no_ask")
    ok(b3["star"] == want and want, f"3일째 물음 없음 → star_no_ask: {b3['star'][:30]}")
    cook = resident(st, "cook")
    sa = S.arc_state(st, cook["id"], "arc_cook_seat")
    sa.update({"step": 2, "ask_pending": 2, "last_day": S.day_of(st)})
    ok(S.beat_compose(st, uid, 3)["star"] == S.BEATS["3"]["star"], "열린 물음이 있으면 원래 star")
    # 5일째 색 조각
    st = S.load_state(uid)
    st["created"] -= 86400 * 4
    st["octopus"] = {"arrived_day": 1, "name": "먹물", "finds": {}, "gift_day": None, "arrival_shown": True}
    S.core_of(st)["beats"]["play_day"] = 5
    S.octopus_tick(st, uid)
    g = st["octopus"].get("gift_relic")
    ok(g and any(x.get("card_id") == g["card_id"] for x in (st.get("shelf") or []) + (st.get("stored") or [])),
       f"색 조각이 선반/창고 상자에 {g}")
    w = S.octopus_gift_where(st, uid)
    ok(w and w["relic_id"] == g["card_id"] and len(w["suggest"]) >= 2, f"색 조각 「어디로」 {[x['name'] for x in w['suggest']]}")
    S.save_state(uid, st)
    j = post("/api/give", {"uid": uid, "relic_id": g["card_id"], "target": w["suggest"][0]["target"]})
    ok(j["ok"], f"색 조각을 건넴 → {j['tier']}")
    ok(S.BEATS["5"]["star"] and "골라 주세요" not in S.BEATS["5"]["star"], "5일째 문장에 고르라는 약속 없음")
    # arc_beat_ready
    uid2 = "dev_s21_nv"
    ark(uid2)
    st = S.load_state(uid2)
    st["shelf"], st["stored"] = [], []
    eng = resident(st, "engineer")
    b = S.ARC_BY_ID["arc_engineer_warm"]["beats"][0]
    ok(not S.arc_item_at_home(st, uid2, eng, b), "집에 전자 물건 없음 → 약속 안 함")
    ok(not any(x["kind"] == "arc_beat_ready" and x["data"].get("arc_id") == "arc_engineer_warm"
               for x in S.next_visit_candidates(st, uid2)), "arc_beat_ready 후보 없음(기술자)")
    S.save_state(uid2, st)
    post("/api/scan", {"uid": uid2, "barcode": ean("490123477001"), "user_category": "electronics"})
    st = S.load_state(uid2)
    ok(S.arc_item_at_home(st, uid2, resident(st, "engineer"), b), "전자 물건을 찍어 선반에 → 약속 가능")
    ok(S.rule_ko(b["trigger"]["give"]) == "전자", f"기술자 1매듭 힌트 「{S.rule_ko(b['trigger']['give'])}」")


def t_bug1_stored():
    """5. 창고 상자로 간 스캔을 「어디로」로 준다(기록이 없어도 card_id 로 찾는다)."""
    uid = "dev_s21_bug1"
    ark(uid)
    st = S.load_state(uid)
    cap = S.shelf_capacity(st)
    last = None
    for i in range(cap + 4):
        last = post("/api/scan", {"uid": uid, "barcode": ean(f"8801062{i:05d}")})
    ok(last.get("stored"), "선반이 차서 창고 상자로")
    sid = last["where"]["scan_id"]
    st = S.load_state(uid)
    S.core_of(st)["scans"].pop(sid, None)            # 기록을 잃은 상황
    S.save_state(uid, st)
    tgt = {"resident_id": st["residents_list"][0]["id"]}
    j = post("/api/give", {"uid": uid, "scan_id": sid, "target": tgt})
    st = S.load_state(uid)
    ok(j["ok"] and not any(x.get("card_id") == sid or x.get("id") == sid for x in st.get("stored") or []) or j["tier"] == "not_for_me",
       f"창고 상자 스캔 주기 200 ({j['tier']})")
    r = C.post("/api/give", json={"uid": uid, "scan_id": sid, "target": tgt})
    ok(r.status_code == 400, "두 번째는 400(이미 정함)")


def t_novelty():
    """6. 켠 날 4부터 세션마다 새것·모르는 결과 하나(없으면 만든다), 같은 실마리 반복 없음."""
    uid = "dev_s21_nov"
    ark(uid)
    st = S.load_state(uid)
    S.core_of(st)["beats"]["play_day"] = 5
    st["overnight"] = {"items": []}
    S.save_state(uid, st)
    keys = []
    for i in range(3):
        post("/api/dev/advance", {"uid": uid, "minutes": 60})
        st = S.load_state(uid)
        S.core_of(st)["beats"]["last_day"] = S.day_of(st)
        S.core_of(st)["beats"]["play_day"] = 5
        st["overnight"] = {"items": []}
        st["clues_extra"] = ["spot_jelly_bloom"]          # 단서 보장(진짜 새것)이 끼지 않게
        S.save_state(uid, st)
        a = ark(uid)
        nv = a.get("novelty")
        ok(nv and nv["line"], f"세션 {i + 1} 새것: {nv and nv['kind']} — {nv and nv['line'][:40]}")
        keys.append((nv or {}).get("line"))
    ok(len(set(keys)) == len(keys), "같은 실마리를 다시 쓰지 않는다")
    nlines = S.moments().get("novelty") or {}
    k_ = (nv or {}).get("line_key") or ""
    ok(k_.startswith("novelty.") and "{" not in nv["line"] and nv["kind"] in k_,
       f"novelty 문장 = ui_moments {k_}")
    st = S.load_state(uid)
    a_ = S.novelty_line(st, "octopus_hint", "기본", {"oct_name": "문어"})
    b_ = S.novelty_line(st, "octopus_hint", "기본", {"oct_name": "문어"})
    ok(a_[0] != b_[0] and a_[0] in [l.replace("{oct_name}", "문어") for l in nlines.get("octopus_hint", [])] and "문어 문어" not in a_[0] + b_[0],
       f"문어 줄 돌려 쓰기·「문어 문어」 없음: {a_[1]} → {b_[1]}")
    a2 = ark(uid)
    ok(a2["novelty"] == a["novelty"], "같은 세션 안에서는 같은 것")


def t_after_ask():
    """7. 버튼 물음의 답 뒤 after_ask_ko 는 null 이 아니다(답별 뒷말 → _default → 기본 줄)."""
    uid = "dev_s21_aa"
    ark(uid)
    for aid, step in (("arc_engineer_warm", 2), ("arc_scout_window", 2)):
        a = S.ARC_BY_ID[aid]
        beat = next(b for b in a["beats"] if b["step"] == step)
        opts = beat["ask"]["options"]
        for opt in opts:
            st = S.load_state(uid)
            r = resident(st, a["role"])
            S.arc_state(st, r["id"], aid).update({"step": step, "ask_pending": step, "asks": {}, "last_day": S.day_of(st)})
            S.save_state(uid, st)
            j = post("/api/arc/ask", {"uid": uid, "arc_id": aid, "step": step, "choice": opt})
            aa = beat.get("after_ask")
            want = (aa.get(opt) or aa.get("_default")) if isinstance(aa, dict) else aa
            ok(j["after_ask_ko"] and "{" not in j["after_ask_ko"] and (not want or j["after_ask_ko"].startswith(S.fill_text(want, st, r)[:6])),
               f"{aid} 「{opt}」 → {j['after_ask_ko'][:40]}")
    # skip 답
    st = S.load_state(uid)
    cook = resident(st, "cook")
    S.arc_state(st, cook["id"], "arc_cook_seat").update({"step": 2, "ask_pending": 2, "asks": {}, "last_day": S.day_of(st)})
    S.save_state(uid, st)
    j = post("/api/arc/ask", {"uid": uid, "arc_id": "arc_cook_seat", "step": 2, "skip": True})
    ok(j["answer"] == "skip" and j["after_ask_ko"], f"넘김 → skip 뒷말: {j['after_ask_ko'][:40]}")


def t_warm_lines():
    """(a) warm 반응: 관리실 줄 = give.soft_thanks, 주민 줄 = warm_lines, 둘이 같지 않고, 사람마다 7일 안에 같은 줄 없음."""
    uid = "dev_s21_wl"
    ark(uid)
    st = S.load_state(uid)
    r = resident(st, "scout")
    wl = S.TASTES["roles"]["scout"].get("warm_lines") or []
    ok(len(wl) >= 8, f"정찰병 warm_lines {len(wl)}줄")
    got = []
    for d in range(7):
        st["created"] -= 86400
        out = S.give_apply(st, uid, item("tobacco", "smoke", f"담배{d}", f"tb{d}"), {"resident_id": r["id"]}, "copy",
                           warm_ids=[r["id"]])
        rc = out["reaction"]
        ok(out["tier"] == "warm" and rc["announce"] != rc["line"] and rc["announce_key"].startswith("give.soft_thanks")
           and (rc["line_key"] or "").startswith("resident_tastes.roles.scout.warm_lines"), f"{d + 1}일째 warm: {rc['line'][:24]}")
        got.append(rc["line"])
    ok(len(set(got)) == 7, f"7일 동안 서로 다른 줄 {len(set(got))}/7")


def t_need_met():
    """후속: /api/ark core.residents[rid].given_need_today(화면 「받음」) · needs_today[].met."""
    uid = "dev_s21_need"
    a0 = ark(uid)
    st = S.load_state(uid)
    sc = resident(st, "scout")
    ok(a0["core"]["residents"][sc["id"]]["given_need_today"] is False, "받기 전 given_need_today false")
    nd = S.need_today(uid, sc, S.day_of(st))
    S.give_apply(st, uid, item(nd["category"], (nd["subtype"] or [None])[0], "필요한 것", "nd1"), {"resident_id": sc["id"]}, "copy")
    S.save_state(uid, st)
    a1 = ark(uid)
    row = next(x for x in a1["needs_today"] if x["resident_id"] == sc["id"])
    ok(a1["core"]["residents"][sc["id"]]["given_need_today"] is True and row["met"] is True,
       f"필요({nd['ko']})를 받은 뒤 given_need_today true · needs_today.met true")
    others = [r for r in a1["residents_list"] if r["id"] != sc["id"]]
    ok(all(a1["core"]["residents"][r["id"]]["given_need_today"] is False for r in others), "다른 사람은 그대로 false")


TESTS = [t_need_met, t_diminish, t_decor_loop, t_warm_not_first, t_promises, t_bug1_stored, t_novelty, t_after_ask, t_warm_lines]

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
