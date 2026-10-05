"""S19-A 서버 검증 — 핵심 루프 A(docs/CORE_LOOP_A.md · 계약 docs/API_S19.md) + 2차 플레이테스트 고침 + 각인(PM 추가).

실행:  python tests/test_s19_server.py   (임시 DB + TestClient)
수치·문장은 데이터(core_a.json·resident_tastes·arcs·room_decor·visitors·beats·next_visit·ui_moments)에서 읽어 비교한다.
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
import combat as CB  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t19.db"
S.DEV_MODE = True
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []
S.now_hour = lambda: 10          # 기본은 아침(저녁 조건은 테스트마다 바꾼다)


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


def adv(uid, minutes):
    return post("/api/dev/advance", {"uid": uid, "minutes": minutes})


def ark(uid):
    return get(f"/api/ark?uid={uid}")


def resident(st, role):
    return next(r for r in st["residents_list"] if r["role"] == role)


def item(cat, sub=None, name=None, fam=None, rarity="common", code=None):
    return {"name": name or f"{cat}-{sub}", "category": cat, "subtype": sub, "family": fam, "rarity": rarity,
            "barcode": code or f"x{cat}{sub}{name}", "card_id": None}


TASTES = S.TASTES
V = S.OUTCOME_V


# ─────────────────────────────────────────────────────────────
def t_scan_where():
    """① 스캔 응답 where: 제안 ≤3 + 선반, card.subtype, 재료는 그대로 들어온다."""
    uid = "dev_s19_where"
    ark(uid)
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
    w = j["where"]
    ok(w["scan_id"] == j["card"]["id"] and w["shelf"]["target"] == "shelf" and w["shelf"]["value"] == V["keep"],
       f"where.scan_id·선반 {w['shelf']}")
    ok(len(w["suggest"]) <= 3 and all(x["tier"] in S.TIER_ICON and x["icon"] for x in w["suggest"]),
       f"제안 {[(x['name'], x['tier'], x['value']) for x in w['suggest']]}")
    ok("subtype" in j["card"] and j["card"]["subtype"], f"card.subtype = {j['card']['subtype']} ({j['card'].get('subtype_ko')})")
    vals = [round(x["value"] * x["mult"], 4) for x in w["suggest"]]
    ok(vals == sorted(vals, reverse=True), f"가치 높은 순 {vals}")
    ok(all(0.8 <= x["value"] <= 1.2 for x in w["suggest"]), "결과 가치는 0.8~1.2V")
    res_before = dict(S.load_state(uid)["resources"])
    g = post("/api/give", {"uid": uid, "scan_id": w["scan_id"], "target": "shelf"})
    ok(g["tier"] == "keep" and g["state"]["resources"] == res_before, "선반에 두기 = 재료 그대로")
    r = C.post("/api/give", json={"uid": uid, "scan_id": w["scan_id"], "target": "shelf"})
    ok(r.status_code == 400, "같은 scan_id 는 한 번만")
    j2 = post("/api/scan", {"uid": uid, "barcode": ean("880104301516")})
    ok(j2["where"]["compact"] is True, "같은 세션 둘째 스캔부터 compact")


def t_give_values():
    """① 주기 값 규칙: 필요·좋아함·안 맞음·몰아주기 ×0.5·같은 물건 사흘 ×0.3·재료 대가 없음."""
    uid = "dev_s19_give"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    S.cres(st, cook["id"])["memories_seen"] = [m["id"] for m in TASTES["roles"]["cook"]["memories"]]   # 기억과 겹치지 않게
    nd = S.need_today(uid, cook, S.day_of(st))
    it = item(nd["category"], (nd["subtype"] or [None])[0], "필요한 것")
    tier, _ = S.resident_tier(st, uid, cook, it)
    ok(tier == "need", f"오늘 필요 {nd['ko']} → tier {tier}")
    S.set_station(st, cook["id"], 2)
    m0 = st["resources"]["morale"]
    res0 = {k: v for k, v in st["resources"].items() if k != "morale"}
    out = S.give_apply(st, uid, it, {"resident_id": cook["id"]}, "copy")
    ok(out["tier"] == "need" and out["value"] == V["need"] and st["resources"]["morale"] == m0 + 2,
       f"필요 → 사기 +2, V {out['value']}")
    ok(out["effects"]["room_bonus"] and out["effects"]["room_bonus"]["pct"] == 10, f"그 사람 방 +10% {out['effects']['room_bonus']}")
    rm = S.room_at(st, 2)
    ok(abs(S.need_bonus_mult(st, rm) - 1.1) < 1e-9 and S.room_mult(st, rm)[1].get("need_mult") == 1.1, "room_mult 에 필요 배율 1.1")
    ok({k: v for k, v in st["resources"].items() if k != "morale"} == res0, "주기에 재료가 들지 않는다")
    ok(out["reaction"]["announce"] and "{" not in out["reaction"]["announce"] and out["reaction"]["line"],
       f"반응 문장: {out['reaction']['announce']}")
    # 같은 사람 같은 날 둘째 → ×0.5
    rt = TASTES["roles"]["cook"]
    lk = rt["likes"][0]
    it2 = item(lk["category"], lk["subtype"][0], "좋아하는 것")
    m1 = st["resources"]["morale"]
    f1 = float(st.get("morale_frac") or 0)
    out2 = S.give_apply(st, uid, it2, {"resident_id": cook["id"]}, "copy")
    ok(out2["mult"] == S.DIM_SAME_DAY and abs((st["resources"]["morale"] + float(st.get("morale_frac") or 0)) - (m1 + f1) - 0.5) < 1e-6,
       f"같은 날 둘째 ×{out2['mult']} → 사기 +0.5 ({out2['tier']})")
    # 다음 날 같은 물건 → ×0.3
    st["created"] -= 86400
    out3 = S.give_apply(st, uid, it2, {"resident_id": cook["id"]}, "copy")
    ok(out3["mult"] == S.DIM_SAME_ITEM and out3["diminish"][0]["kind"] == "same_item_3days", f"사흘 안 같은 물건 ×{out3['mult']}")
    # 안 맞음 → 정중하게 돌려준다(선반)
    tw = S.twist_of(uid, cook)["dislike"]
    out4 = S.give_apply(st, uid, item(tw["category"], tw["subtype"], "안 맞는 것"), {"resident_id": cook["id"]}, "copy")
    ok(out4["tier"] == "not_for_me" and out4["effects"]["returned_to_shelf"] and out4["value"] == V["neutral_person"],
       f"안 맞음 → 돌려줌: {out4['reaction']['announce']}")
    # 사슬 선호 순서: 요리사 좋아함 + 필요가 아닌 것을 다른 사람에게
    ok(S.twist_of(uid, cook) == S.twist_of(uid, cook), "덧붙임은 시드 결정적(D6)")


def t_keepsake_needs_morning():
    """②③ 날마다 바뀌는 필요(아침 방송) · 덧붙임 · 머리맡 물건(처음 좋아함)."""
    uid = "dev_s19_need"
    ark(uid)
    st = S.load_state(uid)
    scout = resident(st, "scout")
    days = [S.need_today(uid, scout, d)["ko"] for d in range(1, 15)]
    ok(len(set(days)) >= 2, f"정찰병 필요 14일 {len(set(days))}종: {days[:5]}")
    a = ark(uid)
    nd = a["needs_today"]
    ok(len(nd) == len(a["residents_list"]) and all(x["announce"] and x["need"]["ko"] for x in nd), f"아침 needs_today {nd[0]['announce']}")
    kinds = [it["kind"] for it in (a["overnight"] or {}).get("items") or []]
    ok("needs" in kinds, f"밤사이에 needs 한 장: {kinds}")
    core = a["core"]["residents"][scout["id"]]
    ok(core["twist"]["like"]["ko"] and core["twist"]["dislike"]["ko"] and core["twist"]["like"] != core["twist"]["dislike"],
       f"덧붙임 좋아함 {core['twist']['like']['ko']} / 안 맞음 {core['twist']['dislike']['ko']}")
    # 머리맡: 처음 like
    st = S.load_state(uid)
    scout = resident(st, "scout")
    lk = TASTES["roles"]["scout"]["likes"][0]
    out = S.give_apply(st, uid, item(lk["category"], lk["subtype"][0], "작은 등"), {"resident_id": scout["id"]}, "copy")
    ok(out["effects"]["keepsake"] and "작은 등" in out["effects"]["keepsake"]["line"], f"머리맡 물건: {out['effects']['keepsake']}")
    out2 = S.give_apply(st, uid, item(lk["category"], lk["subtype"][-1], "둘째 등"), {"resident_id": scout["id"]}, "copy")
    ok(not out2["effects"]["keepsake"] and S.cres(st, scout["id"])["keepsake"]["name"] == "작은 등", "머리맡은 하나만(처음 것)")
    S.save_state(uid, st)
    adv(uid, 60 * 24)
    a = ark(uid)
    ks = [it for it in (a["overnight"] or {}).get("items") or [] if it["kind"] == "keepsake"]
    ok(ks and "작은 등" in ks[0]["data"]["line"], f"다음 아침 머리맡 한 줄: {ks and ks[0]['data']['line']}")


def t_memory():
    uid = "dev_s19_mem"
    ark(uid)
    st = S.load_state(uid)
    eng = resident(st, "engineer")
    m = TASTES["roles"]["engineer"]["memories"][0]
    tr = m["trigger"]
    it = item(tr["category"], tr["subtype"][0], "건전지")
    out = S.give_apply(st, uid, it, {"resident_id": eng["id"]}, "copy")
    ok(out["tier"] in ("memory", "chain_beat") and out["effects"]["memory"]["id"] == m["id"], f"기억 {m['id']} → {out['tier']}")
    out2 = S.give_apply(st, uid, item(tr["category"], tr["subtype"][0], "건전지2"), {"resident_id": eng["id"]}, "copy")
    ok(not out2["effects"]["memory"], "기억은 사람×기억마다 한 번")


def t_arcs():
    """④ 사슬: 저절로 안 풀림 · 합류 후 n일 · 건네기 · 엇갈림 · 큰 매듭 하루 하나(미룸) · 저녁 · 묻기 · 바람 이전."""
    uid = "dev_s19_arc"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    a = S.ARC_BY_ID["arc_cook_seat"]
    food = item("food", "noodle", "면 하나", code="f1")
    # 1일째: 합류 3일 전이라 안 풀린다
    out = S.give_apply(st, uid, food, {"resident_id": cook["id"]}, "copy")
    ok(not out["effects"]["arc"] and S.arc_state(st, cook["id"], a["id"])["step"] == 0, "합류 3일 전에는 매듭 안 풀림")
    S.save_state(uid, st)
    adv(uid, 60 * 24 * 3)
    a1 = ark(uid)
    nxt = a1["core"]["residents"][cook["id"]]["arc"]["next"]
    ok(nxt["open"] and nxt["step"] == 1 and nxt["hint_ko"], f"4일째 매듭 1 열림: {nxt}")
    st = S.load_state(uid)
    cook = resident(st, "cook")
    w = S.where_for(st, uid, item("food", "canned", "통조림", code="f2"))
    top = next((x for x in w["suggest"] if x.get("arc_id") == a["id"]), None)
    ok(top and top["tier"] == "chain_beat" and top["icon"] == "chain", f"제안에 사슬 매듭 아이콘: {top}")
    out = S.give_apply(st, uid, item("food", "canned", "통조림", code="f2"), {"resident_id": cook["id"]}, "copy")
    ok(out["tier"] == "chain_beat" and out["effects"]["arc"]["step"] == 1 and out["effects"]["arc"]["announce"],
       f"건네기 → 매듭 1: {out['effects']['arc']['announce'][:30]}…")
    ok("chair_1" in S.core_of(st)["props"] and cook.get("arc_line"), "소품·대사 한 줄 영구 변화")
    # 같은 날 두 번째 매듭 없음 + min_days_after_prev 1
    out = S.give_apply(st, uid, item("food", "sauce", "양념", code="f3"), {"resident_id": cook["id"]}, "copy")
    ok(not out["effects"]["arc"], "같은 날 같은 사람 매듭은 하나")
    S.save_state(uid, st)
    adv(uid, 60 * 24)
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    ok(S.arc_state(st, cook["id"], a["id"])["step"] == 2, f"5일째 give_distinct 2(이미 둘) → 매듭 2 수동 판정")
    pend = S.arc_state(st, cook["id"], a["id"]).get("ask_pending")
    ok(pend == 2, f"매듭 2 묻기 대기 {pend}")
    sh = post("/api/scan", {"uid": uid, "barcode": ean("880104301523")})
    rid_ = sh["card"]["id"]
    j = post("/api/arc/ask", {"uid": uid, "arc_id": a["id"], "step": 2, "relic_id": rid_})
    ok(j["ok"] and j["after_ask_ko"], f"묻기(place) 답 → {j['after_ask_ko'][:30]}")
    # 다른 사슬의 choice 묻기
    st = S.load_state(uid)
    eng = resident(st, "engineer")
    s_e = S.arc_state(st, eng["id"], "arc_engineer_warm")
    s_e.update({"step": 2, "last_day": S.day_of(st), "ask_pending": 2})
    S.save_state(uid, st)
    r = C.post("/api/arc/ask", json={"uid": uid, "arc_id": "arc_engineer_warm", "step": 2, "choice": "아무거나"})
    ok(r.status_code == 400, "없는 선택지 → 400")
    j = post("/api/arc/ask", {"uid": uid, "arc_id": "arc_engineer_warm", "step": 2, "choice": "돌리기"})
    st = S.load_state(uid)
    ok(S.arc_state(st, resident(st, "engineer")["id"], "arc_engineer_warm")["asks"]["2"]["choice"] == "돌리기", "choice 기록")
    # 큰 매듭: 저녁 + give_distinct 3 → 하루 하나, 넘치면 미룸
    st = S.load_state(uid)
    cook = resident(st, "cook")
    s_c = S.arc_state(st, cook["id"], a["id"])
    s_c.update({"step": 3, "last_day": S.day_of(st) - 1})
    S.core_of(st)["big_day"] = S.day_of(st)
    S.now_hour = lambda: 19
    out = S.give_apply(st, uid, item("food", "grain", "곡물", code="f9"), {"resident_id": cook["id"]}, "copy")
    ok(out["effects"]["arc"] and out["effects"]["arc"].get("deferred"), "오늘 큰 매듭이 이미 나왔으면 미룬다")
    S.save_state(uid, st)
    adv(uid, 60 * 24)
    a2 = ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    done = S.arc_state(st, cook["id"], a["id"])
    ok(done["done"] and any(e["arc_id"] == a["id"] and e["done"] for e in a2["arc_events"]), "다음 날 미룬 큰 매듭이 뜬다 → 사슬 끝")
    ok(a["wish_id"] in st["wishes_done"] and any(w["id"] == a["wish_id"] for w in a2["wishes_new"]), "사슬 끝 = 바람 이룸(wishes_new)")
    ok(S.cres(st, cook["id"]).get("seat") and int(S.core_of(st)["flags"].get("arc_guest_due") or 0) >= 0, "자리 + 옛 무리 손님")
    S.now_hour = lambda: 10
    # 저녁 아니면 저녁 매듭은 안 풀린다
    st = S.load_state(uid)
    scholar = S.make_resident("scholar", __import__("random").Random(1), set(), uid)
    scholar["joined"] = st["created"]
    st["residents_list"].append(scholar)
    sa = S.arc_state(st, scholar["id"], "arc_scholar_page")
    sa.update({"step": 3, "last_day": S.day_of(st) - 3})
    for i in range(3):
        S.cres(st, scholar["id"])["given"].append(dict(item("book", "story", f"책{i}", code=f"b{i}"), day=1))
    t = S.next_beat(S.ARC_BY_ID["arc_scholar_page"], sa)["trigger"]
    ok(not S.trig_all(st, uid, scholar, sa, t, None), "저녁 매듭: 아침에는 조건 미충족")
    S.now_hour = lambda: 20
    ok(S.trig_all(st, uid, scholar, sa, t, None), "저녁(20시)에는 충족")
    S.now_hour = lambda: 10


def t_wishes_no_auto():
    """④ 옛 바람 자동 이룸 없음 · 옛 저장의 이룬 바람은 사슬 끝으로 이전."""
    uid = "dev_s19_wish"
    ark(uid)
    for i in range(4):
        post("/api/scan", {"uid": uid, "barcode": ean(f"88010620{i:04d}")})
    w = get(f"/api/wishes?uid={uid}")
    ok(not any(x["done"] for x in w), "식품 넷을 선반에 → 바람 저절로 안 이뤄짐")
    st = S.new_state("dev_s19_wish_old")
    cook = resident(st, "cook")
    st["wishes_done"] = {"wish_cook_seat": {"day": 2, "resident_id": cook["id"]}}
    S.save_state("dev_s19_wish_old", st)
    st2 = S.load_state("dev_s19_wish_old")
    s_ = S.arc_state(st2, cook["id"], "arc_cook_seat")
    ok(s_["done"] and s_["step"] == len(S.ARC_BY_ID["arc_cook_seat"]["beats"]), "옛 이룬 바람 → 사슬 끝으로 이전")
    a, _ = S.current_arc(st2, resident(st2, "cook"))
    ok(a and a["id"] == "arc_cook_feast", f"이전 뒤 다음 사슬 {a and a['id']}")


def t_decor_visitors_raid():
    """⑤ 꾸밈 칸(레벨 2/3/4) · 꼬리표(둘) · 방문자 · 습격 가중 ×1.5 · 금 → 상자 → 수리 · 상실 → 창고 상자 → 되찾기."""
    uid = "dev_s19_decor"
    ark(uid)
    st = S.load_state(uid)
    pantry = S.room_at(st, 2)
    ok(S.decor_cap(pantry) == S.DECOR_SLOTS[1] == 2, f"Lv1 꾸밈 칸 {S.decor_cap(pantry)}")
    a = S.give_apply(st, uid, item("food", "noodle", "면", code="d1"), {"slot": 2}, "copy")
    ok(a["tier"] == "decor" and not a["effects"]["decor"]["tag_added"], f"첫 물건 → decor, 꼬리표 아직 {a['effects']['decor']['tags']}")
    b = S.give_apply(st, uid, item("drink", "tea", "차", code="d2"), {"slot": 2}, "copy")
    ta = b["effects"]["decor"]["tag_added"]
    ok(ta and ta["id"] == "warm_kitchen" and ta["announce"] and "{room}" not in ta["announce"], f"둘 → 꼬리표 붙음: {ta and ta['announce']}")
    try:
        S.give_apply(st, uid, item("food", "grain", "곡물", code="d3"), {"slot": 2}, "copy")
        ok(False, "칸이 차면 400")
    except S.HTTPException as e:
        ok(e.status_code == 400, f"칸이 차면 400 ({e.detail})")
    # 방문자: 시드 고정, 꼬리표 visitors 종류만
    rows = S.visit_rows_for(st, uid, 5)
    kinds = {r["kind"] for r in rows}
    allowed = {"visitor", "residents", "octopus", "gardener", "guest_tilt", "newhuman_tilt"}
    ok(kinds <= allowed and rows == S.visit_rows_for(st, uid, 5), f"방문 굴림 결정적, 종류 {kinds}")
    vis = [r for d in range(1, 30) for r in S.visit_rows_for(st, uid, d) if r["kind"] == "visitor"]
    ok(vis and all(v["visitor_id"] == "steam_eel" for v in vis) and 0.3 < len(vis) / 29 < 0.75,
       f"따뜻한 부엌 → 꼬마 장어 {len(vis)}/29일(≈0.5)")
    meta = __import__("json").loads((ROOT / "static" / "art" / "visitors" / "visitors_meta.json").read_text(encoding="utf-8"))
    ids = set((meta.get("visitors") or {}).keys()) if isinstance(meta.get("visitors"), dict) else {x["id"] for x in meta["visitors"]}
    ok({v["id"] for v in S.VISITORS_BY_TAG.values()} <= ids, "visitors.json id = visitors_meta.json id")
    S.save_state(uid, st)
    a1 = ark(uid)
    ok(a1["room_decor"]["2"]["tags"][0]["on"] and isinstance(a1["visits"], list), f"/api/ark room_decor·visits {len(a1['visits'])}")
    # 습격 가중
    st = S.load_state(uid)
    st["rooms"].append({"id": "storage", "slot": 3, "built": time.time(), "level": 1})
    w = S.raid_target_weights(st)
    ok(w == {2: S.RAID_CHERISHED_MULT}, f"꾸민 방 가중 {w}")
    rooms = S.live_rooms(st)
    hits = sum(1 for d in range(2, 400) if CB.pick_target(uid, d, CB.CREATURES["longneck"], rooms, {}, weights=w) == 2)
    ok(0.52 < hits / 398 < 0.68, f"꾸민 방이 노려지는 비율 {hits / 398:.2f}(1.5:1 → 0.6)")
    same = all(CB.pick_target(uid, d, CB.CREATURES["longneck"], rooms, {}) == CB.pick_target(uid, d, CB.CREATURES["longneck"], rooms, {}, weights=None)
               for d in range(2, 60))
    ok(same, "가중이 없으면 옛 추첨과 같다")
    # 금 → 상자 → 수리
    m0 = st["resources"]["morale"]
    n = S.decor_on_crack(st, 2)
    ok(n == 2 and all(it["boxed"] for it in S.decor_items(st, 2)) and not S.room_tags_on(st, 2) and st["resources"]["morale"] <= m0,
       "금 → 꾸밈 물건이 상자로, 꼬리표 꺼짐, 사기 −1")
    S.decor_on_repair(st, 2)
    ok(not any(it["boxed"] for it in S.decor_items(st, 2)) and S.room_tags_on(st, 2) == ["warm_kitchen"], "수리 → 제자리")
    # 상실 → 창고 상자 → 되찾기
    S.decor_on_breach(st, 2)
    ok(not S.decor_items(st, 2) and sum(1 for x in st["stored"] if x.get("from_slot") == 2) == 2, "상실 → 창고 상자(from_slot)")
    S.decor_on_reclaim(st, 2)
    ok(len(S.decor_items(st, 2)) == 2 and not any(x.get("from_slot") == 2 for x in st["stored"]), "되찾으면 돌아온다")
    # 긴목 ×1.3: 첫 주에는 꺼짐
    st["rooms"].append({"id": "generator", "slot": 5, "built": time.time(), "level": 1})
    S.core_of(st)["rooms"]["5"] = {"items": [dict(item("electronics", "light", "등1"), id="e1"), dict(item("electronics", "light", "등2"), id="e2")]}
    S.core_of(st)["beats"]["play_day"] = 3
    ok(S.creature_mult(st) is None, "첫 주(켠 날 ≤7) 긴목 가중 없음")
    S.core_of(st)["beats"]["play_day"] = 9
    ok(S.creature_mult(st) == {"longneck": S.SHINY_LONGNECK_MULT}, f"8일째 이후 트인 쪽 전자 둘 → {S.creature_mult(st)}")
    # decor remove
    S.save_state(uid, st)
    iid = S.decor_items(S.load_state(uid), 2)[0]["id"]
    j = post("/api/decor/remove", {"uid": uid, "slot": 2, "item_id": iid})
    ok(j["back_to"] in ("shelf", "stored") and len(j["state"]["room_decor"]["2"]["items"]) == 1, f"꾸밈 빼기 → {j['back_to']}")


def t_guest_tilt():
    uid = "dev_s19_tilt"
    ark(uid)
    st = S.load_state(uid)
    S.core_of(st)["visits"] = {"day": S.day_of(st), "rows": [{"kind": "guest_tilt", "roles": {"kid": 2}}]}
    ok(S.guest_role_weights(st) == {"kid": 2}, "꼬리표 손님 가중 kid ×2")
    kids = 0
    for i in range(200):
        st["guests"] = []
        g = S.make_guest(st, uid, f"seed{i}", "knock")
        kids += g["role"] == "kid"
    st2 = S.load_state(uid)
    st2["core"]["visits"] = {}
    base = 0
    for i in range(200):
        st2["guests"] = []
        base += S.make_guest(st2, uid, f"seed{i}", "knock")["role"] == "kid"
    ok(kids > base, f"아이 손님 {base} → {kids}/200 (오는 횟수는 그대로, 누가 오는지만)")


def t_beats_session_leaving():
    """⑥⑦ 켠 날 차례 비트 · 세션당 큰 창 2 · 15일째 규칙 · 떠날 때 카드(지킬 수 있는 약속만)."""
    uid = "dev_s19_beat"
    a = ark(uid)
    b = a["beat_today"]
    ok(b["play_day"] == 1 and b["beat"] == S.BEATS["1"]["beat"] and b["new"] and b["star"] == S.BEATS["1"]["star"], f"1일째 비트 {b['beat']}")
    a = ark(uid)
    ok(not a["beat_today"]["new"], "같은 세션 둘째 /api/ark → new false")
    adv(uid, 60 * 24 * 5)                      # 실제로는 6일째, 켠 날은 둘째
    a = ark(uid)
    ok(a["day"] == 6 and a["beat_today"]["play_day"] == 2 and a["beat_today"]["beat"] == "octopus_arrives",
       f"사흘 넘게 쉬어도 다음 비트(켠 날 2): {a['beat_today']['beat']}")
    ok(a["session"]["new"] and a["session"]["big_left"] <= 2, f"세션 {a['session']}")
    st = S.load_state(uid)
    S.core_of(st)["beats"]["play_day"] = 3
    S.core_of(st)["beats"]["shown"] = {"1": True, "2": True}
    S.core_of(st)["session"]["big"] = 2
    S.core_of(st)["session"].pop("shown_beat_session", None)
    S.save_state(uid, st)
    a = ark(uid)
    ok(not a["beat_today"]["new"] and a["beat_today"]["queued"] >= 0, "큰 창 2개를 다 쓰면 비트는 다음 세션으로")
    adv(uid, 60)
    a = ark(uid)
    ok(a["beat_today"]["new"] and a["beat_today"]["play_day"] == 3, "다음 세션에 밀린 비트")
    # 비트 4: 긴목을 운 대신 차례로
    st = S.load_state(uid)
    S.core_of(st)["beats"]["play_day"] = 4
    st["threat_raids"] = 0
    st["raid"] = None
    st["raid_log"] = []
    S.save_state(uid, st)
    j = get(f"/api/raid/today?uid={uid}")
    ok((j.get("raid") or {}).get("creature", {}).get("id") == "longneck" and j["raid"]["severity"] == 0, f"켠 날 4 → 긴목(세기 0) {(j.get('raid') or {}).get('creature', {}).get('id')}")
    # 15일째부터
    st = S.load_state(uid)
    for p, want in ((21, "weekly_log"), (28, "fortnight_log")):
        ok(S.beat_compose(st, uid, p)["beat"] == want, f"켠 날 {p} → {want}")
    d16 = S.beat_compose(st, uid, 16)
    ok(d16["beat"].startswith("daily_") and d16["star"], f"켠 날 16 → {d16['beat']}")
    ok(S.beat_compose(st, uid, 7)["weekly_log"]["residents"], "7일째 일지 요약")
    # 떠날 때 카드
    lv = get(f"/api/leaving?uid={uid}")
    ok(lv["next_visit"]["line"] and lv["next_visit"]["kind"] in ("expedition_return", "guest_at_door", "arc_beat_ready",
                                                                  "box_key_hint", "visitor_expected", "need_tomorrow", "nothing"),
       f"떠날 때: {lv['next_visit']['kind']} — {lv['next_visit']['line']}")
    st = S.load_state(uid)
    st["expedition"] = {"id": "exp-x", "members": [st["residents_list"][0]["id"]], "returns_at": time.time() + 3600,
                        "result": {}, "scene": {}}
    nv = S.next_visit_public(st, uid)
    ok(nv["kind"] == "expedition_return" and st["residents_list"][0]["name"] in nv["line"] and "{" not in nv["line"],
       f"원정 귀환 약속(실제 시각): {nv['line']}")


def t_round2_fixes():
    """⑧ 2차 플레이테스트 고침."""
    uid = "dev_s19_fix"
    ark(uid)
    # 넘침 → 사기·교역, 밤사이에 말한다
    st = S.load_state(uid)
    cap = S.storage_cap(st)
    st["resources"]["food"] = cap
    m0 = st["resources"]["morale"]
    S.save_state(uid, st)
    st = S.load_state(uid)
    st["resources"]["food"] = cap + 12
    S.save_state(uid, st)
    st = S.load_state(uid)
    ov = st["storage_overflow"]
    ok(st["resources"]["food"] == cap and ov["lost"]["food"] == 12 and ov["converted"].get("morale") == 2
       and st["resources"]["morale"] == m0 + 2 and ov["ko"], f"넘친 식량 12 → 사기 2: {ov['ko']}")
    a = ark(uid)
    ok(any(it["kind"] == "overflow" for it in a["overnight"]["items"]) and a["storage"]["overflow"]["converted"], "밤사이에 넘침 한 줄")
    # 밤사이 제목 = 시각대, 다음 날 저절로 비움
    S.now_hour = lambda: 19
    a = ark(uid)
    bt = S.moments()["morning"]["by_time"]["evening"]
    ok(a["overnight"]["title"] == bt["title"] and a["overnight"]["band"] == "evening", f"저녁에 연 밤사이 제목 「{a['overnight']['title']}」")
    S.now_hour = lambda: 10
    adv(uid, 60 * 24)
    a = ark(uid)
    ok(not any(it["kind"] == "overflow" and it["day"] < a["day"] for it in (a["overnight"] or {}).get("items") or []),
       "한 번 내려간 밤사이 항목은 다음 날 비워진다")
    # 1주차 반나절 단서
    st = S.load_state(uid)
    S.core_of(st)["beats"]["play_day"] = 5
    st["spots_found"] = []
    S.beat_force_tick(st, uid)
    sid = (st.get("clues_extra") or [None])[-1]
    sp = S.dest_spec(st, uid, {"kind": "clue", "id": sid})
    ok(sid and "half" in sp["lengths"] and not sp.get("why"), f"켠 날 5 단서 보장 {sid}: lengths {sp['lengths']}")
    st["clues_extra"] = ["spot_kelp_ceiling"]
    S.core_of(st)["beats"]["play_day"] = 6
    sp = S.dest_spec(st, uid, {"kind": "clue", "id": "spot_kelp_ceiling"})
    ok("half" in sp["lengths"] and sp["week1_half"], f"밤 넘기기 단서도 1주차 첫 단서면 반나절 {sp['lengths']}")
    # 에어락 = 문간 증설
    st["resources"].update({"parts": 50, "cloth": 50, "knowledge": 50, "scrap": 50})
    S.save_state(uid, st)
    n_rooms = len(S.load_state(uid)["rooms"])
    j = post("/api/ark/build", {"uid": uid, "room_id": "airlock", "slot": -1})
    st = S.load_state(uid)
    ok(j["entrance_airlock"]["level"] == 1 and len(st["rooms"]) == n_rooms and S.room_level_of(st, "airlock") == 1
       and S.suits_state(st)["total"] == 2, "에어락을 칸 없이 문간에 → Lv1, 잠수복 2")
    errs, _, _ = S.exp_errors(st, uid, [st["residents_list"][0]["id"]], {"kind": "unknown"}, "long")
    ok(not any("에어락" in e for e in errs), "밤 넘기기 열림")
    j = post("/api/ark/upgrade", {"uid": uid, "room_id": "airlock"})
    ok(j["entrance_airlock"]["level"] == 2, "문간 에어락 올리기 → Lv2")
    # 공방 잔해
    e = S._ECON_ALL["rooms"]["list"]["workshop"]["build"]["scrap"]
    ok(S.ROOMS["workshop"]["cost"]["scrap"] == max(1, round(e * 0.5)), f"공방 잔해 {e} → {S.ROOMS['workshop']['cost']['scrap']}")
    # 선반 자동 채움 · 폭 맞는 후보 · 식량창고를 잃어도 선반
    uid2 = "dev_s19_shelf"
    ark(uid2)
    st = S.load_state(uid2)
    cap = S.shelf_capacity(st)
    for i in range(cap + 3):
        post("/api/scan", {"uid": uid2, "barcode": ean(f"8801062{i:05d}")})
    st = S.load_state(uid2)
    nst = len(st["stored"])
    st["rooms"].append({"id": "storage", "slot": 3, "built": time.time(), "level": 1})
    S.save_state(uid2, st)
    a = ark(uid2)
    st = S.load_state(uid2)
    ok(nst > 0 and len(st["stored"]) < nst and a["shelf_autofill"], f"창고를 지으면 상자에서 저절로 올라옴 {nst} → {len(st['stored'])}")
    c1 = S.swap_candidates(st, n=99, width=2)
    ok(all(S.prop_width(x.get("prop_id") or "") >= 1 for x in c1), "폭 2 후보 계산")
    st["rooms"] = [dict(r, flooded=True, flooded_from={"id": r["id"], "level": 1}) for r in st["rooms"]]
    ok(S.shelf_capacity(st) == int(S._ECON_ALL["shelf"]["base_pantry"]), "선반 방을 다 잃어도 창고 상자 선반(바탕 칸)")
    pub = S.public_state(st, uid2)
    ok(pub["shelf_room"] and pub["shelf_room"]["fallback"] and pub["shelf"], "shelf_room.fallback")
    # 값 낮은 재스캔 줄 돌려 쓰기
    uid3 = "dev_s19_low"
    ark(uid3)
    code = ean("490123500002")
    zs = [post("/api/scan", {"uid": uid3, "barcode": code, "user_category": "food"})["zero_reaction"] for _ in range(6)]
    kos = [z["ko"] for z in zs if z]
    lines = S.moments()["shelf"]["rescan_low"]
    ok(len(set(kos)) >= 3 and sum(1 for k in kos if k in lines) >= 2 and all(a_ != b_ for a_, b_ in zip(kos, kos[1:])),
       f"값 낮은 재스캔 줄 {len(set(kos))}종, 연속 반복 없음(rescan_low 포함)")
    # 문어 선물 줄에 「문어」
    st = S.load_state(uid3)
    st["created"] -= 86400
    S.save_state(uid3, st)
    a = ark(uid3)
    oc = [it for it in a["overnight"]["items"] if it["kind"] == "octopus"]
    ok(oc and "문어" in oc[0]["data"]["label"] and oc[0]["data"]["who"], f"문어 선물 줄: {oc and oc[0]['data']['label']}")
    # 단서 모드 모자란 갈래 한 단어
    st = S.load_state(uid3)
    raid = {"target_slot": 2, "severity": 0}
    w = S.short_of_word(st, raid, CB.CREATURES["longneck"], {"gate": {"ok": True}, "would": "scarred"})
    ok(w in ("손", "눈", "숨", "담", "도구", "불"), f"모자란 갈래 한 단어: {w}")
    ok(S.short_of_word(st, raid, CB.CREATURES["longneck"], {"gate": {"ok": True}, "would": "held"}) is None, "막을 수 있으면 없음")
    # free_pack → 상자, 막 필터
    st = S.load_state(uid3)
    st["resources"]["free_pack"] = 2
    S.save_state(uid3, st)
    st = S.load_state(uid3)
    ok("free_pack" not in st["resources"] and len(st["boxes"]) >= 2, "옛 free_pack → 상자 둘")
    a = ark(uid3)
    ok("free_pack" not in a["resources"], "자원 줄에 free_pack 없음")
    uid4 = "dev_s19_fp"
    ark(uid4)
    get(f"/api/event/today?uid={uid4}&debug_force_event=relic_cache")
    st = S.load_state(uid4)
    st["hand"] = [{"id": "c1", "tags": ["부품"], "category": "electronics"}]
    S.save_state(uid4, st)
    j = post("/api/event/resolve", {"uid": uid4, "card_id": "c1"})
    ok(j["countered"] and "free_pack" not in j["applied"] and j["applied"].get("box") == 1 and "free_pack" not in j["state"]["resources"],
       f"사건 free_pack → 상자: {j['applied']}")
    picks = set()
    import storyteller as STY
    for k in range(200):
        a_ = STY.ArkState(day=5, act=1, rooms=["pantry"], depth_m=0)
        picks.add(STY.pick_event(a_, list(S.EVENTS.values()), rng=__import__("random").Random(k),
                                 exclude=S.ACT_TEXT_DENY[1])["id"])
    ok("relic_cache" not in picks, "1막 사건 풀에 「숨겨진 유물 창고」 없음")


def t_imprints():
    """PM 추가: 사건 쪽지는 각인 없음 · 「빈 자리」는 방을 잃을 때만 · 같은 날 같은 각인 두 사람 금지 · 사슬 끝 개인 각인 · 덕분에 한 줄."""
    uid = "dev_s19_imp"
    ark(uid)
    seen_imp = 0
    for eid in ("deep_hull_crack", "deep_air_leak", "relic_cache"):
        if eid not in S.EVENTS:
            continue
        get(f"/api/event/today?uid={uid}&debug_force_event={eid}")
        j = post("/api/event/resolve", {"uid": uid, "card_id": None})
        seen_imp += len(j["new_imprints"])
    any_ev = next(iter(S.EVENTS))
    get(f"/api/event/today?uid={uid}&debug_force_event={any_ev}")
    j = post("/api/event/resolve", {"uid": uid, "card_id": None})
    seen_imp += len(j["new_imprints"])
    ok(seen_imp == 0 and "imprint_credit" in j, "사건 쪽지 결과로는 각인이 생기지 않는다")
    st = S.load_state(uid)
    ok(not any("empty_seat" in r.get("imprints", []) for r in st["residents_list"]), "가벼운 실패에 「빈 자리」 없음")
    # 같은 날 같은 각인 두 사람 금지
    st = S.load_state(uid)
    ppl = st["residents_list"][:2]
    for p in ppl:
        p["imprints"], p["crises"] = [], []
    got = S.grant_imprints(st, None, ["air_survived"], ppl, src="expedition")
    ok(len(got) == 1, f"같은 각인은 같은 날 한 사람: {[g['resident'] for g in got]}")
    # 원정 각인: 아슬아슬한 것만
    ok(S.close_call_flags(["beast_left", "healing_spot_found"], {"danger": {"ok": True}}, None) == [], "위험을 무사히 넘긴 원정·발견 → 각인 없음")
    ok(S.close_call_flags(["beast_left"], {"danger": {"ok": False}}, None) == ["beast_left"], "위험에 지고 돌아옴 → beast_left")
    ok(S.close_call_flags(["air_survived"], {"danger": {"ok": False}}, None) == ["air_survived"], "숨이 떨어져 겨우 → air_survived")
    # 습격: 여유 있게 막으면 각인 없음, 금 가면 버틴 사람이 변함, 방을 잃으면 지켜본 사람에게 「빈 자리」
    uid2 = "dev_s19_imp2"
    ark(uid2)
    st = S.load_state(uid2)
    for p in st["residents_list"]:
        p["imprints"], p["crises"] = [], []
    S.set_station(st, st["residents_list"][0]["id"], 2)
    raid = {"id": "r1", "day": S.day_of(st), "creature": "swarm", "grade": 1, "target_slot": 2, "severity": 4,
            "stage": "contact", "started": time.time(), "resolved": False, "acts": [], "moves": 0, "outside_sent": []}
    st["raid"] = raid
    out = S.resolve_raid(st, uid2, raid, [])
    if out["result"] == "breached":
        es = [r for r in st["residents_list"] if "empty_seat" in r.get("imprints", [])]
        ok(len(es) == 1 and es[0]["id"] != st["residents_list"][0]["id"], f"방을 잃음 → 지켜본 한 사람에게 「빈 자리」 {[r['name'] for r in es]}")
    else:
        ok(out["result"] in ("scarred", "breached"), f"세기 4 작은 떼 결과 {out['result']}")
    # 각인 덕분에 한 줄(점수에 보탠 각인)
    parts = [{"ko": "누리 · 刻 saved_breath", "v": 1.5}, {"ko": "방이 있다 (Lv1)", "v": 2}]
    cr = S.imprint_credit_parts(st, parts, "seed")
    ok(cr and cr[0]["name"] == "누리" and cr[0]["imprint_id"] == "saved_breath" and "누리" in cr[0]["ko"] and cr[0]["key"].startswith("imprint_credit"),
       f"덕분에: {cr and cr[0]['ko']}")
    # 사슬 끝 → 개인 각인(위기 각인 셈 밖)
    st = S.load_state(uid2)
    kid = S.make_resident("kid", __import__("random").Random(3), set(), uid2)
    kid["joined"] = st["created"]
    st["residents_list"].append(kid)
    a = S.ARC_BY_ID["arc_kid_sweet"]
    s_ = S.arc_state(st, kid["id"], a["id"])
    s_.update({"step": len(a["beats"]) - 1, "last_day": S.day_of(st) - 5})
    row = S.fire_beat(st, uid2, kid, a, s_, S.next_beat(a, s_), force=True)
    iid = (a.get("imprint_on_done") or {}).get("id")
    ok(row["done"] and row["imprint"] and row["imprint"]["id"] == iid and iid in kid["personal_imprints"] and not kid["imprints"],
       f"사슬 끝 개인 각인 {row['imprint'] and row['imprint']['name']} (위기 각인 0)")
    ok(not kid.get("role_evolved"), "개인 각인은 역할 진화 셈에 들지 않는다")
    eff = S.role_effects(st)
    ok(eff["imprint_count"] >= 1, "개인 각인 효과가 role_effects 에 더해진다")


def t_api_roundtrip():
    """한 바퀴: 스캔 → 어디로 → 주기 → /api/ark core 에 보인다."""
    uid = "dev_s19_loop"
    ark(uid)
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301530")})
    sug = j["where"]["suggest"]
    tgt = sug[0]["target"] if sug else {"resident_id": S.load_state(uid)["residents_list"][0]["id"]}
    g = post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": tgt})
    ok(g["ok"] and g["state"]["core"] and g["tier"], f"주기 {g['tier']} → state.core")
    if g["tier"] not in ("not_for_me",) and "resident_id" in tgt:
        rid = tgt["resident_id"]
        ok(g["state"]["core"]["residents"][rid]["given_today"] == 1, "core.given_today 1")
        ok(not any(x.get("card_id") == j["card"]["id"] for x in g["state"]["shelf"]), "준 물건은 선반에서 그 사람에게 갔다")
    a = ark(uid)
    j2 = post("/api/scan", {"uid": uid, "barcode": ean("880104301547")})
    a = ark(uid)
    row = next((x for x in a["shelf"] if x.get("card_id") == j2["card"]["id"]), None)
    ok(row and row["category"] == j2["card"]["category"] and row["subtype"] == j2["card"]["subtype"],
       f"shelf[] 에 card_id·category·subtype {row and (row['card_id'], row['category'], row['subtype'])}")
    g2 = post("/api/give", {"uid": uid, "relic_id": row["card_id"], "target": "shelf"}) if row else {}
    ok(g2.get("ok"), "shelf card_id 로 /api/give relic_id 동작")
    for k in ("core", "needs_today", "room_decor", "visits", "beat_today", "next_visit", "session", "arc_events", "entrance_airlock"):
        ok(k in a, f"/api/ark.{k}")


TESTS = [t_scan_where, t_give_values, t_keepsake_needs_morning, t_memory, t_arcs, t_wishes_no_auto,
         t_decor_visitors_raid, t_guest_tilt, t_beats_session_leaving, t_round2_fixes, t_imprints, t_api_roundtrip]

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
