"""S22 서버 검증 — 1단계 「약속을 지키는 루프」 앞쪽(기획 검수 §3 · 4차 플테 §6~8 · DECISIONS 2026-10-11).

실행:  python tests/test_s22.py
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

S.DB = Path(tempfile.mkdtemp()) / "t22.db"
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


def ark(uid):
    return get(f"/api/ark?uid={uid}")


def item(cat, sub=None, name=None, code=None, rarity="common"):
    return {"name": name or f"{cat}-{sub}", "category": cat, "subtype": sub, "family": None, "rarity": rarity,
            "barcode": code or f"x{cat}{sub}{name}", "card_id": None}


def resident(st, role):
    return next((r for r in st["residents_list"] if r["role"] == role), None)


def add_resident(st, role, uid, seed=1):
    r = S.make_resident(role, random.Random(seed), {x["name"] for x in st["residents_list"]}, uid)
    r["joined"] = st["created"]
    S.ensure_stats(uid, r)
    st["residents_list"].append(r)
    return r


UNKNOWN_MILK = ean("490123499001")      # 모르는 가문 → 하위 종류를 고른다


# ─────────────────────────────────────────────────────────────
def t_subtype_pick():
    """① 「이게 뭐예요?」: 모르는 가문만 묻는다 · 고르면 영구 · 다시 찍어도 그 값 · 카드·「어디로」 다시 계산."""
    uid = "dev_s22_sub"
    ark(uid)
    j = post("/api/scan", {"uid": uid, "barcode": UNKNOWN_MILK, "user_category": "drink"})
    sp = j["where"].get("subtype_pick")
    ids = [o["id"] for o in (sp or {}).get("options") or []]
    ok(sp and sp["needed"] and 4 <= len(ids) <= 6 and "alcohol" not in ids and "milk" in ids and sp["ask_ko"],
       f"모르는 가문 음료 → 고르기 {ids}")
    known = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
    ok(known["where"].get("subtype_pick") is None, "알려진 가문(8801043)은 묻지 않는다")
    book = post("/api/scan", {"uid": uid, "barcode": ean("979116224190")})
    ok(book["where"].get("subtype_pick") is None, "책(979)은 묻지 않는다")
    r = post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": "milk"})
    ok(r["card"]["subtype"] == "milk" and r["subtype_ko"] == S.sub_ko("drink", "milk") and r["where"]["suggest"] is not None,
       f"고름 → 카드 「{r['card']['name']}」 {r['subtype_ko']}, 「어디로」 다시 계산")
    st = S.load_state(uid)
    ok(st["barcodes"][UNKNOWN_MILK]["subtype"] == "milk", "방주에 영구 고정")
    j2 = post("/api/scan", {"uid": uid, "barcode": UNKNOWN_MILK, "user_category": "drink"})
    ok(j2["card"]["subtype"] == "milk" and j2["where"].get("subtype_pick") is None, "다시 찍으면 고른 값, 묻지 않음")
    bad = C.post("/api/scan/subtype", json={"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": "soda"})
    ok(bad.status_code == 400, "이미 정한 것은 바꾸지 않는다")
    bad2 = C.post("/api/scan/subtype", json={"uid": uid, "scan_id": j2["where"]["scan_id"], "subtype": "noodle"})
    ok(bad2.status_code == 400, "다른 갈래의 종류는 400")
    # 같은 바코드가 아니면 결정성: 고르지 않은 스캔은 예전과 같은 카드
    a = S.GEN.generate(ean("490123499018"), user_category="drink").to_dict()
    b = S.GEN.generate(ean("490123499018"), user_category="drink", user_subtype=None).to_dict()
    ok(a == b, "고르지 않으면 카드가 예전과 바이트까지 같다")


def t_subtype_votes():
    """① 다른 방주 이름: 서로 다른 방주 3곳 이상·60% 이상이면 미리 고른다(숫자만)."""
    code = ean("490123499025")
    for i, sub in enumerate(("milk", "milk", "milk", "juice")):
        uid = f"dev_s22_vote{i}"
        ark(uid)
        j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
        post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": sub})
        if i == 1:
            ok(j["where"]["subtype_pick"]["suggest"] is None, "1곳뿐일 때는 미리 고르지 않는다")
    uid = "dev_s22_vote_new"
    ark(uid)
    j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
    sg = j["where"]["subtype_pick"]["suggest"]
    ok(sg and sg["id"] == "milk" and sg["arks"] == 3 and "3" in j["where"]["subtype_pick"]["suggest_ko"],
       f"3/4 방주 milk → 미리 고름 {sg} · {j['where']['subtype_pick']['suggest_ko']}")
    with S.db() as con:
        cols = [r[1] for r in con.execute("PRAGMA table_info(subtype_votes)").fetchall()]
    ok(set(cols) == {"uid", "barcode", "category", "subtype", "ts"}, f"표에는 숫자 셀 것만 {cols}")


def t_intent():
    """① 의도: 그날 필요를 보여 준 뒤 찍어 채우면 intent:true · 전용 문장 · 같은 사람 하루 한 번."""
    uid = "dev_s22_int"
    ark(uid)                                           # 필요를 보여 준다
    st = S.load_state(uid)
    sc = resident(st, "scout")
    nd = S.need_today(uid, sc, S.day_of(st))
    ok(S.core_of(st).get("needs_shown", {}).get("day") == S.day_of(st), "필요를 보여 준 시각 기록")
    for k in [x for x in S.cres(st, sc["id"])["arcs"]]:
        pass
    # 필요한 하위 종류의 모르는 바코드를 찍고 고른 뒤 건넨다
    code = ean("490123488001")
    j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": nd["category"]})
    sub = (nd.get("subtype") or [None])[0]
    if j["where"].get("subtype_pick") and sub in [o["id"] for o in j["where"]["subtype_pick"]["options"]]:
        post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": sub})
    st = S.load_state(uid)
    for a_ in S.cres(st, sc["id"])["arcs"].values():
        a_["done"] = True                              # 사슬과 섞이지 않게
    S.cres(st, sc["id"])["memories_seen"] = [m["id"] for m in S.TASTES["roles"]["scout"]["memories"]]
    for aid in [a["id"] for a in S.ARCS if a["role"] == "scout"]:
        S.arc_state(st, sc["id"], aid)["done"] = True
    S.save_state(uid, st)
    g = post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": {"resident_id": sc["id"]}})
    ok(g["intent"] is True and g["tier"] == "need" and "give_intent" in (g["reaction"]["announce_key"] or "")
       and "intent_lines" in (g["reaction"]["line_key"] or ""), f"의도 채움 → {g['reaction']['announce']}")
    j3 = post("/api/scan", {"uid": uid, "barcode": ean("490123488018"), "user_category": nd["category"]})
    if j3["where"].get("subtype_pick") and sub:
        post("/api/scan/subtype", {"uid": uid, "scan_id": j3["where"]["scan_id"], "subtype": sub})
    g3 = post("/api/give", {"uid": uid, "scan_id": j3["where"]["scan_id"], "target": {"resident_id": sc["id"]}})
    ok(g3["intent"] is False, "같은 사람 같은 날 두 번째는 intent 아님")
    # 필요를 보이기 전 찍은 것 → intent 아님
    st = S.load_state(uid)
    rec = {"day": S.day_of(st), "at": float(S.core_of(st)["needs_shown"]["at"]) - 5}
    eng = resident(st, "engineer")
    nd2 = S.need_today(uid, eng, S.day_of(st))
    out = {"tier": "need"}
    ok(not S.give_intent(st, uid, rec, item(nd2["category"], (nd2.get("subtype") or [None])[0]), {"resident_id": eng["id"]}, out),
       "필요를 보여 주기 전에 찍은 물건은 intent 아님")


def t_soft_fallback():
    """② 좁은 조건 매듭이 2일(켠 날) 안 풀리면 갈래 전체도 받고, 힌트도 넓은 말로."""
    uid = "dev_s22_soft"
    ark(uid)
    st = S.load_state(uid)
    sc = resident(st, "scout")
    a = S.ARC_BY_ID["arc_scout_window"]
    b2 = next(b for b in a["beats"] if b["step"] == 2)
    s = S.arc_state(st, sc["id"], a["id"])
    s.update({"step": 1, "last_day": S.day_of(st)})
    S.save_state(uid, st)
    narrow = (b2["trigger"].get("give") or {}).get("subtype")
    ok(narrow, f"정찰병 2매듭 좁은 조건 {narrow}")
    od = S.beat_opens_day(st, sc, s, b2)
    # 열린 날 + 2 켠 날
    for _ in range(od - S.day_of(st) + 2):
        post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
        ark(uid)
    st = S.load_state(uid)
    sc = resident(st, "scout")
    s = S.arc_state(st, sc["id"], a["id"])
    other_sub = next(x for x in S.SUBTYPE_KO["electronics"] if x not in narrow)
    hit = S.arc_try_give(st, uid, sc, item("electronics", other_sub, "건전지", "e9"), preview=True)
    ok(s.get("soft_step") == 2 and hit, f"켠 날 2일 뒤 → 전자 전체({other_sub})도 매듭 2")
    stt = S.arc_status(st, uid, sc)
    ok(stt["next"]["soft"] and stt["next"]["hint_ko"] == "전자", f"힌트가 넓은 말로 「{stt['next']['hint_ko']}」")
    # 켠 날만 센다: 실제로는 사흘 지났어도 켠 날이 하루면 아직
    uid2 = "dev_s22_soft2"
    ark(uid2)
    st = S.load_state(uid2)
    sc = resident(st, "scout")
    s = S.arc_state(st, sc["id"], a["id"])
    s.update({"step": 1, "last_day": S.day_of(st)})
    S.save_state(uid2, st)
    post("/api/dev/advance", {"uid": uid2, "minutes": 60 * 24 * (od - 1 + 3)})
    ark(uid2)
    st = S.load_state(uid2)
    s = S.arc_state(st, resident(st, "scout")["id"], a["id"])
    if S.SOFT_PLAYED_ONLY:
        ok(s.get("soft_step") != 2, "켠 날만 셈: 열린 뒤 켠 날 1 → 아직 좁은 조건")
    # 의무병 3매듭 희귀도 한 단계 아래
    ok(S.soft_rule({"step": 2, "soft_step": 3}, {"category": "medical", "subtype": ["pill"], "rarity_min": "rare"})
       == {"category": "medical", "rarity_min": "uncommon"}, "희귀도 rare → uncommon, 하위 종류 없앰")


def t_memory_hint_seen():
    """② 기억 실마리는 이 방주가 찍은 적 있는 하위 종류만."""
    uid = "dev_s22_mh"
    ark(uid)
    st = S.load_state(uid)
    ok(not S.memory_hint_ok(st, {"category": "book", "subtype": ["map"]}), "찍은 적 없는 지도 → 실마리 없음")
    S.core_of(st)["seen_subtypes"] = {"book": ["map"]}
    st["seen_categories"] = ["book"]
    ok(S.memory_hint_ok(st, {"category": "book", "subtype": ["map"]}), "지도를 찍었으면 실마리")


def t_decor():
    """③ 꼬리표 방주에 한 번 · 제안 = 붙는 꼬리표 · 하나 남으면 흔적 · 첫 꼬리표 다음 세션 손님 · 같은 이름 방 구분."""
    uid = "dev_s22_dec"
    ark(uid)
    st = S.load_state(uid)
    st["rooms"].append({"id": "quarters", "slot": 3, "built": time.time(), "level": 1})
    st["rooms"].append({"id": "quarters", "slot": 4, "built": time.time(), "level": 1})
    S.give_apply(st, uid, item("food", "noodle", "면", "n1"), {"slot": 2}, "copy")
    tr = S.decor_trace(st, uid)
    ok(tr and tr[0]["tag"] == "warm_kitchen" and tr[0]["visitor_id"] == "steam_eel" and tr[0]["line"] and "{room}" not in tr[0]["line"],
       f"하나 남음 → 흔적 {tr and tr[0]['line']}")
    out = S.give_apply(st, uid, item("drink", "tea", "차", "t1"), {"slot": 2}, "copy")
    ta = out["effects"]["decor"]["tag_added"]
    ok(ta and ta["id"] == "warm_kitchen", "따뜻한 부엌 붙음")
    # 같은 꼬리표를 다른 방에 → 붙지 않고, 제안도 안 함
    tier, info = S.room_decor_tier(st, uid, S.room_at(st, 3), item("food", "noodle", "면2", "n2"))
    ok(info.get("tag") != "warm_kitchen", f"다른 방에는 따뜻한 부엌을 권하지 않음({info.get('tag')})")
    S.core_of(st)["rooms"]["3"] = {"items": [dict(item("food", "noodle", "면3", "n3"), id="x1"), dict(item("drink", "coffee", "커피", "c1"), id="x2")]}
    ok("warm_kitchen" not in S.room_tags_on(st, 3), "같은 꼬리표는 방주에 한 번만 붙는다")
    # 같은 이름 방 구분
    w = S.where_for(st, uid, item("apparel", "small", "양말", "a1"))
    names = [x["name"] for x in w["suggest"] if x["kind"] == "room" and x.get("name_ko") == "거주실"]
    ok(len(set(names)) == len(names), f"같은 이름 방 구분 {names}")
    ok(S.room_display_name(st, S.room_at(st, 3)) != S.room_display_name(st, S.room_at(st, 4)), "거주실 둘 이름이 다르다")
    # 제안 꼬리표 = 붙는 꼬리표(둘을 함께 채우는 물건)
    uid2 = "dev_s22_dec2"
    ark(uid2)
    st2 = S.load_state(uid2)
    S.give_apply(st2, uid2, item("drink", "tea", "차1", "tt1"), {"slot": 2}, "copy")      # 따뜻한 부엌·자라는 창가 1/2 씩
    tier, info = S.room_decor_tier(st2, uid2, S.room_at(st2, 2), item("drink", "tea", "차2", "tt2"))
    out = S.give_apply(st2, uid2, item("drink", "tea", "차2", "tt2"), {"slot": 2}, "copy")
    ok((out["effects"]["decor"]["tag_added"] or {}).get("id") == info.get("tag"), f"제안 {info.get('tag')} = 붙음 {(out['effects']['decor']['tag_added'] or {}).get('id')}")
    # 첫 꼬리표 → 다음 세션(30분 뒤) 손님
    S.save_state(uid, st)
    a = ark(uid)
    ok(not any(v.get("kind") == "visitor" and v.get("forced") for v in a["visits"]), "같은 세션에는 아직")
    post("/api/dev/advance", {"uid": uid, "minutes": 40})
    st = S.load_state(uid)
    st["core"]["flags"]["visit_guarantee"]["at"] -= 40 * 60
    S.save_state(uid, st)
    a = ark(uid)
    fv = [v for v in a["visits"] if v.get("kind") == "visitor" and v.get("visitor_id") == "steam_eel"]
    ok(fv and fv[0]["first"], f"다음 세션에 첫 손님 {[v.get('visitor_id') for v in fv]}")
    book = {b["id"]: b for b in a["visitors_book"]}
    ok(len(book) == 8 and book["steam_eel"]["count"] >= 1, f"손님 도감 8칸, 꼬마 장어 {book['steam_eel']['count']}회")


def t_souvenir():
    uid = "dev_s22_souv"
    ark(uid)
    st = S.load_state(uid)
    for i in range(S.SOUVENIR_VISITS):
        S.apply_visit_row(st, uid, {"visitor_id": "steam_eel", "slot": 2, "room": "식량창고", "tag": "warm_kitchen",
                                    "ko": "꼬마 장어", "line": "x", "first": i == 0})
    b = S.core_of(st)["visitor_book"]["steam_eel"]
    ok(b["count"] == S.SOUVENIR_VISITS and b["souvenir"] and any(x.get("card_id") == b["souvenir"]["relic_id"]
                                                              for x in (st.get("shelf") or []) + (st.get("stored") or [])),
       f"세 번 → 기념품 「{(b['souvenir'] or {}).get('name')}」 선반에")
    ok(any(it["kind"] == "souvenir" for it in st["overnight"]["items"]), "밤사이 기념품 줄")


def t_bugs():
    """④ r4-1 r4-2 r4-3 r4-4 r4-5 r4-6 r4-7."""
    # r4-1: 이미 푼 매듭 기록이 있으면 다시 제안·풀기 없음
    uid = "dev_s22_b1"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    a = S.ARC_BY_ID["arc_cook_seat"]
    s = S.arc_state(st, cook["id"], a["id"])
    s["days"] = {"1": S.day_of(st)}                    # 1매듭을 푼 기록은 있는데 step 이 0(옛 저장·꼬인 상태)
    ok(S.arc_try_give(st, uid, cook, item("food", "noodle", "면", "rr1"), preview=True) is None, "r4-1 푼 매듭 기록 → 다시 제안 안 함")
    # r4-2: 문어 조각은 한 번 건네면 끝
    uid2 = "dev_s22_b2"
    ark(uid2)
    st = S.load_state(uid2)
    st["created"] -= 86400 * 4
    st["octopus"] = {"arrived_day": 1, "name": None, "finds": {}, "gift_day": None, "arrival_shown": True}
    S.core_of(st)["beats"]["play_day"] = 5
    S.octopus_tick(st, uid2)
    S.save_state(uid2, st)
    w = S.octopus_gift_where(S.load_state(uid2), uid2)
    g = post("/api/give", {"uid": uid2, "relic_id": w["relic_id"], "target": w["suggest"][0]["target"]})
    a2 = ark(uid2)
    st = S.load_state(uid2)
    ok(g["tier"] != "not_for_me" and a2["octopus_gift_where"] is None
       and not any(x.get("card_id") == w["relic_id"] for x in (st.get("shelf") or []) + (st.get("stored") or [])),
       f"r4-2 조각 한 번에 옮김({g['tier']}), 다시 제안 없음")
    # r4-3: 첫 방문은 「또」 없이
    uid3 = "dev_s22_b3"
    ark(uid3)
    st = S.load_state(uid3)
    S.give_apply(st, uid3, item("food", "noodle", "면", "q1"), {"slot": 2}, "copy")
    S.give_apply(st, uid3, item("drink", "tea", "차", "q2"), {"slot": 2}, "copy")
    vx = [x for x in S.next_visit_candidates(st, uid3) if x["kind"] == "visitor_expected"]
    ok(vx and "또" not in vx[0]["line"], f"r4-3 첫 손님 약속: {vx and vx[0]['line']}")
    # r4-4: 6일째 구조가 없으면 star_no_rescue
    st = S.load_state(uid3)
    st["exp_log"] = []
    b6 = S.beat_compose(st, uid3, 6)
    ok("모셔 오셨습니다" not in b6["star"] and b6["alt"], f"r4-4 구조 없음 → {b6['star'][:30]}")
    nr = add_resident(st, "medic", uid3, 9)
    nr["joined"] = st["created"] + 3600
    b6 = S.beat_compose(st, uid3, 6)
    ok(nr["name"] in b6["star"], f"r4-4 star_no_rescue 에 새 식구 이름: {b6['star'][:40]}")
    # r4-5: 넘침 문장에 (은)는 꼴 없음
    st = S.load_state(uid3)
    cap = S.storage_cap(st)
    st["resources"]["food"] = cap
    S.save_state(uid3, st)
    st = S.load_state(uid3)
    st["resources"]["food"] = cap + 21
    S.save_state(uid3, st)
    ko = S.load_state(uid3)["storage_overflow"]["ko"]
    ok("(은)" not in ko and "(으)" not in ko, f"r4-5 넘침 문장: {ko}")
    # r4-6: 없는 역할을 말하는 줄
    st = S.load_state(uid3)
    st["residents_list"] = [r for r in st["residents_list"] if r["role"] != "medic"]
    f = next(x for x in S.OCTOPUS["finds"] if x["id"] == "oct_sealed_strip")
    ok(S.role_text(f, "line", st) == f["line_alt"] and "의무병" not in S.role_text(f, "line", st), "r4-6 의무병 없음 → line_alt")
    add_resident(st, "medic", uid3, 11)
    ok(S.role_text(f, "line", st) == f["line"], "의무병 있으면 원래 줄")
    # r4-7: 문어 매듭 announce
    kid_arc = S.ARC_BY_ID["arc_kid_sweet"]
    for aid in ("arc_cook_seat", "arc_engineer_warm", "arc_scout_window", "arc_medic_seal", "arc_farmer_color"):
        for b in S.ARC_BY_ID[aid]["beats"]:
            if "octopus_with" in str(b.get("trigger")):
                r = resident(st, S.ARC_BY_ID[aid]["role"]) or add_resident(st, S.ARC_BY_ID[aid]["role"], uid3, 13)
                row = S.arc_public_beat(st, r, S.ARC_BY_ID[aid], {"step": 0}, b, None, None)
                ok(row["announce"], f"r4-7 {aid} {b['step']} announce: {row['announce'][:30]}")


def t_novelty_morning():
    """⑤ 아침 머리맡 줄·비트는 새것이 아니다 → 실마리가 나온다."""
    uid = "dev_s22_nov"
    ark(uid)
    st = S.load_state(uid)
    S.core_of(st)["beats"]["play_day"] = 6
    S.core_of(st)["seen_subtypes"] = {}
    st["overnight"] = {"items": [{"kind": "keepsake", "day": S.day_of(st), "at": time.time(), "data": {}},
                                 {"kind": "arc_morning", "day": S.day_of(st), "at": time.time(), "data": {}}]}
    S.save_state(uid, st)
    st = S.load_state(uid)
    ss = S.session_tick(st)
    nv = S.novelty_tick(st, uid, [], [])
    ok(nv and nv["kind"] in ("visitor_hint", "keepsake_hint", "octopus_hint", "memory_hint"), f"머리맡 줄만 있는 아침 → 실마리 {nv and nv['kind']}")


def t_missed_chain():
    """⑥ 매듭·기억 제안을 닫은 날 → 떠날 때 한 줄."""
    uid = "dev_s22_mc"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    S.core_of(st)["scans"]["sx"] = {"item": item("food", "noodle", "면", "mc1"), "day": S.day_of(st), "given": True, "to": "shelf",
                                    "chain": [{"rid": cook["id"], "name": cook["name"], "tier": "chain_beat"}]}
    S.save_state(uid, st)
    lv = get(f"/api/leaving?uid={uid}")
    mc = lv["missed_chain"]
    ok(mc and mc["resident_id"] == cook["id"] and cook["name"] in mc["line"], f"놓친 매듭 → {mc and mc['line']}")
    st = S.load_state(uid)
    S.core_of(st)["scans"]["sx"]["to"] = {"resident_id": cook["id"]}
    S.save_state(uid, st)
    ok(get(f"/api/leaving?uid={uid}")["missed_chain"] is None, "그 사람에게 줬으면 없음")


def t_visual_fields():
    """⑦ keepsakes_recent · card.history · visitors_book."""
    uid = "dev_s22_vis"
    ark(uid)
    st = S.load_state(uid)
    sc = resident(st, "scout")
    code = ean("880106200011")
    for i in range(4):
        S.give_apply(st, uid, item("drink", "milk", f"우유{i}", code if i == 0 else f"m{i}"), {"resident_id": sc["id"]}, "copy",
                     warm_ids=[sc["id"]])
    S.save_state(uid, st)
    a = ark(uid)
    kr = a["core"]["residents"][sc["id"]]["keepsakes_recent"]
    ok(len(kr) == 3 and kr[0]["name"] == "우유3" and all(k["prop"] for k in kr), f"최근 받은 셋 {[(k['name'], k['prop']) for k in kr]}")
    j = post("/api/scan", {"uid": uid, "barcode": code})
    h = j["card"]["history"]
    ok(h and h[0]["to_name"] == sc["name"], f"card.history {h}")
    ok(len(a["visitors_book"]) == 8 and all("count" in b and "souvenir" in b for b in a["visitors_book"]), "visitors_book 8칸")


TESTS = [t_subtype_pick, t_subtype_votes, t_intent, t_soft_fallback, t_memory_hint_seen, t_decor, t_souvenir, t_bugs,
         t_novelty_morning, t_missed_chain, t_visual_fields]

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
