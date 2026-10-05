"""S18-A 서버 검증 — 7일 플레이테스트 버그·추천(docs/reports/playtest_7day_20261004.md §5·§6) + 기획 S18-D 수치 + raid_card.

실행:  python tests/test_s18_server.py   (임시 DB + TestClient)
수치·문장은 전부 데이터에서 읽어 비교한다.
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
import storyteller as STY  # noqa: E402
import combat as CB  # noqa: E402
import relic_generator as RG  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t18.db"
S.DEV_MODE = True
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []


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


def new_ark(uid, rooms=()):
    get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    for rid, slot, lv in rooms:
        st["rooms"].append({"id": rid, "slot": slot, "built": time.time(), "level": lv})
    S.save_state(uid, st)
    return S.load_state(uid)


ECON = S._ECON_ALL


# ─────────────────────────────────────────────────────────────
def t_event_gates():
    """버그 2·5: 깊이 문(180m 카드가 0m 에 안 나온다) · 같은 쪽지 반복 금지 창."""
    deep = {e["id"]: STY.min_depth_of(e) for e in S.EVENTS.values() if STY.min_depth_of(e) > 0}
    ok(deep.get("deep_followed_home") == 180, f"깊이 문 있는 카드 {deep}")
    evs = list(S.EVENTS.values())
    bad = 0
    for k in range(300):
        a = STY.ArkState(day=5, act=1, rooms=["pantry"], depth_m=0)
        e = STY.pick_event(a, evs, rng=__import__("random").Random(k))
        bad += STY.min_depth_of(e) > 0
    ok(bad == 0, f"깊이 0m 에서 300번 뽑아 깊이 카드 {bad}번")
    hits = sum(1 for k in range(600) if STY.pick_event(STY.ArkState(day=9, act=1, rooms=["pantry"], depth_m=180), evs,
                                                       rng=__import__("random").Random(k))["id"] == "deep_followed_home")
    ok(hits > 0, f"깊이 180m 에서는 나온다({hits}/600)")
    uid = "dev_s18_ev"
    new_ark(uid)
    win = int(S.stk("events.no_repeat_days"))
    seen = []
    for d in range(12):
        e = get(f"/api/event/today?uid={uid}")["event"]["id"]
        seen.append(e)
        post("/api/event/resolve", {"uid": uid, "card_id": None})
        adv(uid, 60 * 24)
    rep = [i for i in range(1, len(seen)) if seen[i] in seen[max(0, i - win + 1):i] and seen[i] not in S.ALL_OPENERS]
    ok(not rep and not any(STY.min_depth_of(S.EVENTS[e]) > 0 for e in seen),
       f"12일 쪽지: {win}일 안 반복 없음, 깊이 카드 없음 ({len(set(seen))}종)")


def t_voice_claims():
    """버그 3: 「상자 하나 열어 두었습니다」는 상자를 실제로 열었을 때만."""
    lines = [S.voice_for("event_counter", f"s{k}", act=1) for k in range(200)]
    ok(all("상자 하나 열어" not in (v or {}).get("text", "") for v in lines), "상자 없이 막은 날 200번 — 상자 약속 줄 0")
    any_box = any("상자 하나 열어" in (S.voice_for("event_counter", f"s{k}", act=1, facts={"box_opened"}) or {}).get("text", "")
                  for k in range(200))
    ok(any_box, "상자를 열었다는 사실이 있으면 그 줄을 쓸 수 있다")
    uid = "dev_s18_voice"
    new_ark(uid)
    for d in range(7):
        e = get(f"/api/event/today?uid={uid}")
        st = S.load_state(uid)
        tags = e["event"]["counter_tags"]
        st["hand"] = [{"id": f"c{d}", "tags": tags, "name": "x"}]
        S.save_state(uid, st)
        r = post("/api/event/resolve", {"uid": uid, "card_id": f"c{d}"})
        ok("상자 하나 열어" not in ((r.get("voice") or {}).get("text") or ""), f"{d + 1}일째 맞는 카드로 막음 — 상자 약속 없음")
        adv(uid, 60 * 24)


def t_day_end_facts():
    """버그 4: 하루 마감 문장은 실제 상태에서만(돌아옴·되찾은 층·울음 초·아이)."""
    uid = "dev_s18_de"
    new_ark(uid)
    st = S.load_state(uid)
    r = st["residents_list"][0]
    S.day_note(st, "imprint", {"name": r["name"], "src": "event", "imprint": "warden"})
    S.day_note(st, "octopus", "병의 목")
    st["octopus"] = {"arrived_day": 1, "name": "먹물", "finds": {}}
    st["rooms"].append({"id": "quarters", "slot": 4, "built": time.time(), "level": 1})
    S.save_state(uid, st)
    lines_seen = []
    for k in range(20):
        S.DAY_END.setdefault("_seed_salt", 0)
        de = get(f"/api/day_end?uid={uid}")
        lines_seen += [x["text"] for x in de["lines"]]
        # 날을 바꾸지 않고 시드만 다르게 보려면 uid 를 바꾼다
    texts = " ".join(lines_seen)
    ok("돌아온 뒤" not in texts and "아이 손목" not in texts, "쪽지에서 생긴 각인 → 「돌아온 뒤」 줄 없음, 아이 없는 방주 → 「아이 손목」 줄 없음")
    for k in range(30):
        u = f"dev_s18_de{k}"
        new_ark(u)
        st = S.load_state(u)
        S.day_note(st, "imprint", {"name": "가", "src": "event", "imprint": "warden"})
        S.day_note(st, "octopus", "병의 목")
        st["octopus"] = {"arrived_day": 1, "name": "먹물", "finds": {}}
        S.save_state(u, st)
        lines_seen += [x["text"] for x in get(f"/api/day_end?uid={u}")["lines"]]
    texts = " ".join(lines_seen)
    ok("돌아온 뒤" not in texts and "아이 손목" not in texts and "아이만" not in texts,
       f"방주 30개 마감 {len(lines_seen)}줄 — 전제가 틀린 줄 0")
    de = get(f"/api/day_end?uid={uid}")
    ok(de["facts"]["floors"] == 0 and not any("되찾은 층" in x for x in de["facts_ko"]), "되찾은 적 없으면 「되찾은 층」 없음(지은 층을 세지 않는다)")
    st = S.load_state(uid)
    st["rooms"].append({"id": "well", "slot": 5, "built": time.time(), "level": 1, "flooded": True,
                        "flooded_from": {"id": "well", "level": 1}})
    st["resources"].update({"water": 50, "parts": 50})
    S.save_state(uid, st)
    post("/api/ark/build", {"uid": uid, "room_id": "well", "slot": 5})
    de = get(f"/api/day_end?uid={uid}")
    ok(de["facts"]["floors"] == 1 and any("1" in x for x in de["facts_ko"]), f"되찾기 1번 → {de['facts_ko']}")
    # 울음 간격: 오늘 값 = 지금 게이지
    st = S.load_state(uid)
    st["far_call_log"] = {str(S.day_of(st) - 1): 95}
    S.save_state(uid, st)
    sec = S.gauges_of(S.load_state(uid))["far_call_sec"]
    de = get(f"/api/day_end?uid={uid}")
    cry = [x["text"] for x in de["lines"] if x["id"] == "cry_shorter"]
    ok(not cry or any(str(sec) in t or str(95 - sec) in t for t in cry), f"울음 줄 = 지금 간격 {sec}초: {cry}")


def t_imprint_merge_and_parts():
    """버그 6·12: 같은 각인 두 사람 → 아침 한 줄 · ready.parts 에 날 각인 id 없음."""
    rows = [{"day": 2, "resident": "가", "resident_id": "a", "imprint_id": "knock_heard", "imprint_name": "x", "line": "l1"},
            {"day": 2, "resident": "나", "resident_id": "b", "imprint_id": "knock_heard", "imprint_name": "x", "line": "l2"},
            {"day": 2, "resident": "다", "resident_id": "c", "imprint_id": "warden", "imprint_name": "y", "line": "l3"}]
    m = S.merge_morning(rows)
    ok(len(m) == 2 and m[0]["residents"] == ["가", "나"] and "가·나" in m[0]["line"], f"같은 각인 둘 → 한 줄: {m[0]['line']}")
    uid = "dev_s18_parts"
    new_ark(uid)
    get(f"/api/raid/today?uid={uid}&debug_raid=big_maw&debug_reset=1&debug_grade=4")
    post("/api/raid/verb", {"uid": uid, "verb": "station"})
    st = S.load_state(uid)
    tgt = st["raid"]["target_slot"]
    for r in st["residents_list"]:
        r["imprints"] = ["knock_heard"]
    S.save_state(uid, st)
    for r in S.load_state(uid)["residents_list"]:
        post("/api/ark/station", {"uid": uid, "resident_id": r["id"], "slot": tgt})
    adv_ = post("/api/raid/advance", {"uid": uid})
    parts = (adv_["raid"]["ready"] or {}).get("parts") or []
    ok(parts and not any("刻 " in p["ko"] for p in parts) and any("각인 「" in p["ko"] for p in parts),
       f"ready.parts 표시 문장: {[p['ko'] for p in parts if '각인' in p['ko']][:1]}")


def t_rumor_act():
    """버그 8: 1막에 지상 스팟 소문·발견이 새지 않는다."""
    uid = "dev_s18_rumor"
    new_ark(uid)
    cats = ("food", "drink", "tobacco", "apparel", "medical", "electronics", "stationery")
    for i in range(3):
        for c, cat in enumerate(cats):
            post("/api/scan", {"uid": uid, "barcode": ean(f"4901{c:02d}{i:06d}"), "user_category": cat})
        adv(uid, 60 * 24)                              # 하루 20회 상한
    ru = get(f"/api/rumors?uid={uid}")
    land = [x["spot_id"] for x in ru if x["spot_id"] not in S.DEEP_SPOT_IDS]
    ok(not land, f"1막 소문에 지상 스팟 {land}")
    sp = get(f"/api/spots?uid={uid}")
    bad = [x["id"] for x in sp if x["act"] == 3 and (x["unlocked"] or x["state"] != "other_act")]
    ok(not bad, f"/api/spots 지상 스팟은 other_act, 열림 없음 {bad}")


def t_shelf_growth():
    """추천 1: 선반이 자란다(economy.json shelf) · 넘치면 창고 상자 · 바꾸기."""
    sh = ECON["shelf"]
    uid = "dev_s18_shelf"
    new_ark(uid)
    st = S.load_state(uid)
    ok(S.shelf_capacity(st) == sh["base_pantry"], f"식량창고만 → {S.shelf_capacity(st)}")
    st["rooms"].append({"id": "storage", "slot": 3, "built": time.time(), "level": 1})
    ok(S.shelf_capacity(st) == sh["base_pantry"] + sh["per_storage_level"]["1"], f"창고 Lv1 → {S.shelf_capacity(st)}")
    st["rooms"][-1]["level"] = 2
    st["rooms"].append({"id": "storage", "slot": 4, "built": time.time(), "level": 1})
    st["rooms"].append({"id": "storage", "slot": 5, "built": time.time(), "level": 1})
    exp = sh["base_pantry"] + sh["per_storage_level"]["2"] + sh["per_storage_level"]["1"]
    ok(S.shelf_capacity(st) == exp, f"창고 Lv2+Lv1+Lv1 → 둘까지만 합산 {S.shelf_capacity(st)} = {exp}")
    st["reclaimed_total"] = 2
    ok(S.shelf_capacity(st) == exp + 2 * sh["per_floor_reclaimed"], "되찾은 층마다 +4")
    # 넘침
    uid2 = "dev_s18_full"
    new_ark(uid2)
    got = []
    for i in range(sh["base_pantry"] + 3):
        got.append(post("/api/scan", {"uid": uid2, "barcode": ean(f"49012377{i:04d}"), "user_category": "food"}))
    over = [g for g in got if g["shelf_slot"] is None]
    a = get(f"/api/ark?uid={uid2}")
    ok(over and over[0]["stored"] and over[0]["swap_offer"]["candidates"] and over[0]["swap_offer"]["ko"]
       and len(a["stored"]) == len(over), f"꽉 찬 뒤 {len(over)}개 → 창고 상자 {len(a['stored'])}, 바꾸기 제안")
    sid = over[0]["stored"]["id"]
    slot = over[0]["swap_offer"]["candidates"][0]["slot"]
    r = post("/api/shelf/swap", {"uid": uid2, "stored_id": sid, "slot": slot})
    a2 = get(f"/api/ark?uid={uid2}")
    ok(r["ok"] and len(a2["stored"]) == len(a["stored"]) and sid not in [x["id"] for x in a2["stored"]] and r["ko"],
       f"바꾸기 → 선반 칸 {r['slot']}, 내린 것 창고 상자로: {r['down']}")
    code = over[-1]["card"]["barcode"]
    adv(uid2, 60 * 24)
    again = post("/api/scan", {"uid": uid2, "barcode": code, "user_category": "food"})
    ok(again["polish"] and not again["stored"] and len(get(f"/api/ark?uid={uid2}")["stored"]) == len(a2["stored"]),
       "창고 상자에 있는 바코드 재스캔 → 닦기(중복 없음)")


def t_first_week():
    """추천 3: 4일째까지 위협이 없으면 긴목·세기 0, 사람이 선 방."""
    fg = S.first_week_guarantee()
    uid = "dev_s18_fw"
    new_ark(uid, rooms=(("greenhouse", 3, 1),))
    st = S.load_state(uid)
    st["threat_raids"] = 0
    rid = st["residents_list"][0]["id"]
    st["stations"] = {rid: 3}
    S.save_state(uid, st)
    adv(uid, 60 * 24 * (fg["by_day"] - 1))
    j = get(f"/api/raid/today?uid={uid}")
    rd = S.load_state(uid)["raid"]
    ok(j["day"] == fg["by_day"] and rd.get("creature") == fg["creature"] and rd.get("severity") == fg["severity"]
       and rd.get("target_slot") == 3 and rd.get("guaranteed"),
       f"{j['day']}일째 보장 습격 {rd.get('creature')} 세기 {rd.get('severity')} → 사람이 선 방 {rd.get('target_slot')}")
    uid2 = "dev_s18_fw2"
    new_ark(uid2)
    st = S.load_state(uid2)
    st["threat_raids"] = 1
    S.save_state(uid2, st)
    adv(uid2, 60 * 24 * (fg["by_day"] - 1))
    get(f"/api/raid/today?uid={uid2}")
    ok(not S.load_state(uid2)["raid"].get("guaranteed"), "이미 위협이 왔으면 보장하지 않는다")


def t_rescan_zero_trade_cap():
    """추천 5·S18-D: 재스캔 감쇠 표 · 값 0 반응 · 공방 바꾸기 · 저장 상한 · 재료 출처."""
    vals = ECON["scan"]["rescan_decay"]["values"]
    ok([S.rescan_mult(i) for i in range(6)] == vals + [vals[-1]] * (6 - len(vals)), f"감쇠 {[S.rescan_mult(i) for i in range(6)]}")
    uid = "dev_s18_zero"
    new_ark(uid)
    code = ean("490123500001")
    rs = [post("/api/scan", {"uid": uid, "barcode": code, "user_category": "food"}) for _ in range(5)]
    ok([r["rescan_multiplier"] for r in rs] == [S.rescan_mult(i) for i in range(5)], "스캔 응답 배율 = 표")
    ok(rs[0]["zero_reaction"] is None and all(r["zero_reaction"] for r in rs[3:]),
       f"값 낮은 재스캔 반응: {[ (r['zero_reaction'] or {}).get('kind') for r in rs]}")
    a = get(f"/api/ark?uid={uid}")
    ok(set(a["material_sources"]) >= {"cloth", "parts", "scrap"}, "material_sources 가 /api/ark 에")
    # 공방 바꾸기
    T = ECON["workshop_trade"]
    r = C.post("/api/workshop/trade", json={"uid": uid, "give": "food", "get": "cloth"})
    ok(r.status_code == 400 and "공방" in r.json()["detail"], "공방 없으면 바꿀 수 없다")
    st = S.load_state(uid)
    st["rooms"].append({"id": "workshop", "slot": 3, "built": time.time(), "level": 1})
    st["resources"]["food"] = T["keep_reserve"] + T["rate"] * 3
    S.save_state(uid, st)
    j = post("/api/workshop/trade", {"uid": uid, "give": "food", "get": "cloth", "n": T["daily_out_cap"]})
    ok(j["got"] == {"cloth": T["daily_out_cap"]} and j["paid"] == {"food": T["rate"] * T["daily_out_cap"]}, f"식량 {T['rate']}→직물 1 × {T['daily_out_cap']}")
    r = C.post("/api/workshop/trade", json={"uid": uid, "give": "food", "get": "cloth"})
    ok(r.status_code == 400, "하루 상한")
    adv(uid, 60 * 24)
    st = S.load_state(uid)
    st["resources"]["water"] = T["keep_reserve"] + T["rate"] - 1
    S.save_state(uid, st)
    r = C.post("/api/workshop/trade", json={"uid": uid, "give": "water", "get": "parts"})
    ok(r.status_code == 400 and "남겨야" in r.json()["detail"], "남길 재고를 지킨다")
    # 저장 상한
    cap = S.storage_cap(S.load_state(uid))
    st = S.load_state(uid)
    st["resources"]["food"] = cap - 1
    S.save_state(uid, st)
    for i in range(3):
        post("/api/scan", {"uid": uid, "barcode": ean(f"49012388{i:04d}"), "user_category": "food"})
    st = S.load_state(uid)
    ok(st["resources"]["food"] == cap and get(f"/api/ark?uid={uid}")["storage"]["full"] == ["food"] or "food" in get(f"/api/ark?uid={uid}")["storage"]["full"],
       f"식량 상한 {cap}(창고 없음) — 넘친 분은 들어오지 않는다")
    st = S.load_state(uid)
    st["resources"]["water"] = cap + 50
    st.pop("_loaded_res", None)
    S.save_state(uid, st)
    get(f"/api/ark?uid={uid}")
    ok(S.load_state(uid)["resources"]["water"] >= cap + 50, "이미 넘쳐 있던 재고는 깎지 않는다(늘지만 않게)")


def t_relic_names():
    """추천 3(이름): 알려진 커피 가문에는 술 줄기가 없다 · 모르는 가문 음료에 술 없음 · 이름 다양성."""
    g = S.GEN
    sub = {t.get("subtype") for t in g.pool_for(RG.Category.DRINK, "8801037")}
    ok(sub and "alcohol" not in sub and sub <= {"coffee", "tea"}, f"커피 가문 줄기 subtype {sub}")
    unk = {t.get("subtype") for t in g.pool_for(RG.Category.DRINK, "4901234")}
    ok("alcohol" not in unk, f"모르는 음료 가문 subtype {sorted(x for x in unk if x)}")
    names = {g.generate(ean(f"49012340{i:04d}"), user_category="food").name.split(" ", 1)[1] for i in range(60)}
    ok(len(names) >= 8, f"모르는 식품 60개 → 줄기 {len(names)}종")
    a = g.generate(ean("880103701234"))
    b = g.generate(ean("880103701234"))
    ok(a.name == b.name and a.flavor == b.flavor, "같은 바코드 = 같은 이름·문장(결정적)")


def t_depth_announce_overnight():
    """추천 6·밤사이: 깊이 문턱 방송 한 번 · 아침 「밤사이」 한 장."""
    uid = "dev_s18_depth"
    new_ark(uid)
    st = S.load_state(uid)
    st["resources"].update({k: 99 for k in ("food", "water", "scrap", "parts", "cloth")})
    S.save_state(uid, st)
    r = post("/api/ark/build", {"uid": uid, "room_id": "quarters", "slot": 4})
    ok(r["depth_crossed"] and r["depth_crossed"][0]["m"] == 60 and r["depth_crossed"][0]["ko"],
       f"60m 처음 → 방송: {r['depth_crossed'][0]['ko'][:30]}…")
    r2 = post("/api/ark/build", {"uid": uid, "room_id": "well", "slot": 5})
    ok(not r2["depth_crossed"], "같은 문턱은 한 번만")
    get(f"/api/raid/today?uid={uid}&debug_raid=swarm&debug_reset=1&debug_grade=1")
    a = get(f"/api/ark?uid={uid}&debug_night=1")
    ov = a["overnight"]
    kinds = [it["kind"] for it in (ov or {}).get("items", [])]
    ok(ov and "night_judge" in kinds and "depth" in kinds and ov["title"], f"밤사이 한 장: {kinds}")
    post("/api/overnight/seen", {"uid": uid})
    ok(get(f"/api/ark?uid={uid}")["overnight"] is None, "본 뒤에는 비어 있다")
    # 이전 저장: 이미 넘은 깊이는 방송하지 않는다
    uid2 = "dev_s18_depth_old"
    st = S.new_state(uid2)
    st["rooms"].append({"id": "quarters", "slot": 6, "built": 1, "level": 1})
    st.pop("depth_marks", None)
    S.save_state(uid2, st)
    a = get(f"/api/ark?uid={uid2}")
    ok(not a["depth_crossed"], "이전 저장의 이미 넘은 깊이는 조용히")


def t_raid_card():
    """사용자 승인: 습격 카드는 답 대신 버릇 한 줄 + 동사. 동사를 골라야 미리보기, 같은 생물 두 번 만나면 답."""
    rc = S.stk("raid_card")
    uid = "dev_s18_card"
    new_ark(uid)
    j = get(f"/api/raid/today?uid={uid}&debug_raid=longneck&debug_reset=1&debug_grade=1")
    post("/api/raid/advance", {"uid": uid})
    rd = get(f"/api/raid/today?uid={uid}")["raid"]
    ok(rd["card_mode"] == "clue" and rd["habit"] and rd["ready"] is None and rd["action"] is None and rd["verbs"]
       and rd["encounters"] == 0, f"처음 만난 긴목: 버릇 「{rd['habit'][:20]}…」, 동사 {[v['id'] for v in rd['verbs']]}, 미리보기 닫힘")
    acts = next(v for v in rd["verbs"] if v["id"] == "act")["options"]
    ok(len(acts) == len(CB.GATE_ACTIONS), "행동 동사는 모든 관문 행동을 늘어놓는다(답을 콕 집지 않는다)")
    v = post("/api/raid/verb", {"uid": uid, "verb": "light"})["raid"]
    ok(v["ready"] and v["ready"]["gate"]["ko"] is None and v["ready"]["would_ko"] == S.moment(f"raid_preview.{v['ready']['would']}"),
       f"동사 고르면 미리보기(관문 문장 숨김, 미래형 「{v['ready']['would_ko']}」)")
    v = post("/api/raid/verb", {"uid": uid, "verb": "power"})["raid"]
    ok(v["verb"] == "power", "접촉 전까지 몇 번이든 바꾼다")
    ok(C.post("/api/raid/verb", json={"uid": uid, "verb": "dance"}).status_code == 400, "없는 동사 → 400")
    # 두 번 만나면 답
    st = S.load_state(uid)
    st["raid_log"] = [{"creature": "longneck", "result": "held"}] * int(rc["answer_after_encounters"])
    S.save_state(uid, st)
    rd = get(f"/api/raid/today?uid={uid}")["raid"]
    ok(rd["card_mode"] == "answer" and rd["ready"] and rd["ready"]["gate"]["ko"] and rd["encounters"] == rc["answer_after_encounters"],
       f"{rc['answer_after_encounters']}번 만난 뒤 → 답 공개: {rd['ready']['gate']['ko'][:24]}…")
    enc = get(f"/api/ark?uid={uid}")["combat"]["encounters"]
    ok(enc.get("longneck") == rc["answer_after_encounters"], f"생물별 만난 수 {enc}")
    # 문어(위협 아님)는 단서 모드가 아니다
    get(f"/api/raid/today?uid={uid}&debug_raid=octopus&debug_reset=1&debug_grade=1")
    ok(get(f"/api/raid/today?uid={uid}")["raid"] in (None,) or get(f"/api/raid/today?uid={uid}")["raid"]["card_mode"] == "answer",
       "위협 아닌 손님은 답 모드")


def t_small():
    """버그 13: 튜토리얼 미리보기 줍기 3 · 잠수복 수리 응답 문장."""
    uid = "dev_s18_small"
    new_ark(uid)
    sc = next(r for r in S.load_state(uid)["residents_list"] if r["role"] == "scout")
    pv = post("/api/expedition/preview", {"uid": uid, "members": [sc["id"]], "dest": {"kind": "door"}, "length": "short"})
    ok(pv["actions"] == 3, f"튜토리얼 미리보기 줍기 {pv['actions']}")
    st = S.load_state(uid)
    st["suits"] = {"shared_wear": [5]}
    st["resources"].update({"cloth": 5, "parts": 5})
    S.save_state(uid, st)
    r = post("/api/entrance/suit_repair", {"uid": uid})
    ok(r["ko"], f"수리 응답 문장: {r['ko']}")


TESTS = [t_event_gates, t_voice_claims, t_day_end_facts, t_imprint_merge_and_parts, t_rumor_act, t_shelf_growth,
         t_first_week, t_rescan_zero_trade_cap, t_relic_names, t_depth_announce_overnight, t_raid_card, t_small]

if __name__ == "__main__":
    for t in TESTS:
        print(f"\n## {t.__name__} — {(t.__doc__ or '').strip().splitlines()[0]}")
        try:
            t()
        except Exception:
            RESULTS.append((False, t.__name__ + " 예외"))
            traceback.print_exc()
    bad = [m for c, m in RESULTS if not c]
    print(f"\n합계 {len(RESULTS)} · 통과 {len(RESULTS) - len(bad)} · 실패 {len(bad)}")
    for m in bad:
        print("  FAIL", m)
    sys.exit(1 if bad else 0)
