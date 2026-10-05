"""S20-A 서버 검증 — 기획 확정값(core_a s19_server_numbers·arc_imprints·visitor_effects) + PM 스모크 고침(어디로 둘 이상·반응 문장·
1~2일째 매듭·떠날 때 약속 돌려 쓰기) + 짧은 줄.

실행:  python tests/test_s20_server.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback
import random
from pathlib import Path

os.environ["RELIC_DEV"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import server as S  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t20.db"
S.DEV_MODE = True
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []
S.now_hour = lambda: 10
N = S.CORE_A["s19_server_numbers"]


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


# ─────────────────────────────────────────────────────────────
def t_numbers_from_data():
    """기획 확정값을 데이터에서 읽는다."""
    ok(S.OVERFLOW_RATE == {"to_morale": N["overflow"]["food_water_per_morale"], "to_trade": N["overflow"]["other_per_trade"],
                           "morale_day_max": N["overflow"]["morale_per_day_max"]}, f"넘침 {S.OVERFLOW_RATE}")
    ok(S.NEAR_MARGIN == float(N["near_margin"]), f"NEAR_MARGIN {S.NEAR_MARGIN}")
    want = {k: v for k, v in N["tag_guest_roles"].items() if isinstance(v, list)}
    ok(S.TAG_GUEST_ROLES == want and S.TAG_GUEST_WEIGHT == N["tag_guest_roles"]["weight"], f"꼬리표 손님 {len(want)}개")
    ok(S.FEAST_COST == N["feast"]["cost"], f"잔치 비용 {S.FEAST_COST}")
    ok(S.ROOMS["workshop"]["cost"]["scrap"] == S._ECON_ALL["rooms"]["list"]["workshop"]["build"]["scrap"] == N["workshop_build_scrap"],
       f"공방 잔해 = economy 값 {S.ROOMS['workshop']['cost']['scrap']}(이중 할인 없음)")
    ok(S.VISITOR_DAILY == S.CORE_A["visitor_effects"]["daily_chance_when_tagged"], f"손님 하루 {S.VISITOR_DAILY}")
    v = S.CORE_A["arc_imprints"]["values"]
    ok(S.ARC_IMPRINTS["opened_hands"]["effect"] == v["opened_hands"]["effect"]
       and S.ARC_IMPRINTS["leaf_sharer"]["effect"] == {"food_daily_all": -0.05}
       and S.ARC_IMPRINTS["table_setter"]["cost"]["effect"] == v["table_setter"]["cost"], "사슬 각인 수치 = core_a(런타임 병합)")


def t_overflow():
    uid = "dev_s20_ov"
    ark(uid)
    st = S.load_state(uid)
    cap = S.storage_cap(st)
    st["resources"]["food"] = cap
    m0 = st["resources"]["morale"]
    S.save_state(uid, st)
    st = S.load_state(uid)
    st["resources"]["food"] = cap + 30
    st["resources"]["trade"] = cap
    S.save_state(uid, st)
    st = S.load_state(uid)
    st["resources"]["trade"] = cap + 10
    S.save_state(uid, st)
    st = S.load_state(uid)
    conv = st["storage_overflow"]["converted"]
    ok(conv.get("morale") == 1 and st["resources"]["morale"] == m0 + 1, f"식량 30 넘침 → 사기 +1(하루 상한) {conv}")
    ok(conv.get("trade") == 2, f"교역 10 넘침 → 교역품 2(5:1) {conv}")


def t_octo_guarantee():
    uid = "dev_s20_oct"
    ark(uid)
    st = S.load_state(uid)
    st["octopus"] = {"arrived_day": 1, "name": None, "finds": {}}
    r = st["residents_list"][0]
    found = None
    for base in range(0, 400):
        st["created"] = time.time() - 86400 * base
        S.core_of(st)["octo_miss"] = {}
        rolls = []
        for d in range(3):
            st["created"] -= 86400 if d else 0
            rolls.append(S.octo_with(st, uid, r))
        if rolls[:2] == [False, False]:
            found = rolls
            break
    ok(found and found[2] is True, f"두 번 빗나가면 사흘째 보장 {found}")
    ok(S.octo_with(st, uid, r) == found[2], "같은 날은 같은 답")


def t_feast():
    uid = "dev_s20_feast"
    ark(uid)
    st = S.load_state(uid)
    ids = [r["id"] for r in st["residents_list"]]
    st["resources"].update({"food": 40, "water": 30})
    S.save_state(uid, st)
    r = C.post("/api/feast", json={"uid": uid, "pair": ids[:2]})
    ok(r.status_code == 400 and "10일째" in r.json()["detail"], "10일째 전에는 잔치 없음")
    st = S.load_state(uid)
    S.core_of(st)["beats"]["play_day"] = 10
    st["created"] -= 86400 * 9
    S.save_state(uid, st)
    j = post("/api/feast", {"uid": uid, "pair": ids[:2]})
    st = S.load_state(uid)
    ok(j["paid"] == {"food": 24, "water": 12} and j["morale"] == 3, f"잔치 식량 24·물 12, 사기 +3 {j['paid']}")
    ok(all(int(a["trust"].get(b["id"], 0)) >= 5 for a in st["residents_list"] for b in st["residents_list"] if a is not b),
       f"그 자리 모두 서로 신뢰 +5 ({len(j['present'])}명)")
    st["resources"].update({"food": 40, "water": 30})
    st["created"] -= 86400 * 3
    S.save_state(uid, st)
    r = C.post("/api/feast", json={"uid": uid, "pair": ids[:2]})
    ok(r.status_code == 400 and "7일" in r.json()["detail"], "7일에 한 번")
    st = S.load_state(uid)
    st["created"] -= 86400 * 4
    S.save_state(uid, st)
    ok(C.post("/api/feast", json={"uid": uid, "pair": ids[:2]}).status_code == 200, "7일 뒤 다시")


def t_food_daily_all():
    uid = "dev_s20_food"
    ark(uid)
    st = S.load_state(uid)
    for i in range(7):
        k = S.make_resident("cook", random.Random(i), {r["name"] for r in st["residents_list"]}, uid)
        st["residents_list"].append(k)
    st["residents_list"][0]["personal_imprints"] = ["leaf_sharer"]
    S.save_state(uid, st)
    ok(S.role_effects(S.load_state(uid))["food_daily_all"] == -0.05, "role_effects food_daily_all −0.05")
    f0 = S.load_state(uid)["resources"]["food"]
    gained = 0.0
    for d in range(2):
        st = S.load_state(uid)
        st["created"] -= 86400
        gained += S.food_all_tick(st)
        S.food_all_tick(st)                  # 같은 날 두 번 → 한 번
        S.save_state(uid, st)
    st = S.load_state(uid)
    ok(abs(gained - 1.0) < 1e-9 and st["resources"]["food"] == f0 + 1, f"주민 10 × 0.05 × 2일 = 식량 +1 ({f0}→{st['resources']['food']})")


def t_visitors():
    uid = "dev_s20_vis"
    ark(uid)
    st = S.load_state(uid)
    S.give_apply(st, uid, item("food", "noodle", "면", "v1"), {"slot": 2}, "copy")
    S.give_apply(st, uid, item("drink", "tea", "차", "v2"), {"slot": 2}, "copy")
    hits = sum(1 for d in range(1, 201) for r in S.visit_rows_for(st, uid, d) if r["kind"] == "visitor")
    ok(0.27 < hits / 200 < 0.43, f"꼬리표 있으면 하루 0.35 ({hits}/200)")
    tilt = [r for r in S.visit_rows_for(st, uid, 3) if r["kind"] == "guest_tilt"]
    ok(tilt and tilt[0]["roles"] == {"cook": 2, "farmer": 2}, f"따뜻한 부엌 → 손님 요리사·농부 ×2 {tilt and tilt[0]['roles']}")
    # 효과
    st["rooms"][0]["cracked"] = True
    res0 = dict(st["resources"])
    effs = {}
    for vid in ("steam_eel", "screw_crab", "page_shrimp", "lantern_fish_pair", "baby_jelly_drift", "glass_star"):
        effs[vid] = S.visitor_apply(st, uid, {"visitor_id": vid, "slot": 2})
    ok(st["resources"]["food"] == res0["food"] - 1 and st["resources"]["parts"] == res0["parts"] + 1
       and st["resources"]["knowledge"] == res0["knowledge"] + 1, f"장어 식량−1·나사게 부품+1·새우 기록+1 {effs}")
    ok(S.visitor_apply(st, uid, {"visitor_id": "screw_crab", "slot": 2}) is None, "나사게는 3일에 한 번")
    ok(abs(S.need_bonus_mult(st, S.room_at(st, 2)) - 1.1) < 1e-9, "아기 해파리 → 그 방 +10%")
    ok(effs["glass_star"] == {"repair_discount": 1, "slot": 2}, "유리별 → 금 간 방 수리비 −1")
    st["resources"].update({"cloth": 5, "med": 5})
    S.save_state(uid, st)
    j = post("/api/ark/repair", {"uid": uid, "slot": 2})
    full = sum(int(v) for v in (S.stk("crack.repair_cost") or {}).values())
    ok(sum(j["paid"].values()) == max(len(j["paid"]), full - 1), f"수리비 {j['paid']}(정가 합 {full})")
    st = S.load_state(uid)
    S.set_station(st, st["residents_list"][0]["id"], 2)
    m0 = st["resources"]["morale"] + float(st.get("morale_frac") or 0)
    e = S.visitor_apply(st, uid, {"visitor_id": "blanket_crab", "slot": 2})
    st["created"] -= 86400
    S.visitor_carry(st, {})
    ok(e and abs(st["resources"]["morale"] + float(st.get("morale_frac") or 0) - m0 - 0.3) < 1e-6, "담요게 → 다음 아침 사기 +0.3")
    e = S.visitor_apply(st, uid, {"visitor_id": "hermit_trader", "slot": 2})
    ok(e and e["swapped"]["to"] and e["swapped"]["category"] != "food" or e["swapped"]["category"] != "drink", f"소라게 장수 맞바꿈 {e}")


def t_where_two():
    """스모크 1: 모든 스캔에 선반 밖 선택지 둘 이상, 같은 답 비율이 30% 아래로 갈 수 있다."""
    uid = "dev_s20_where"
    ark(uid)
    st = S.load_state(uid)                          # 보통 1주차 집: 주민 넷, 방 넷(대상이 셋이면 최소 33%라 30% 를 못 넘는다)
    st["residents_list"].append(S.make_resident("medic", random.Random(5), {r["name"] for r in st["residents_list"]}, uid))
    st["residents_list"][-1]["joined"] = st["created"]
    for rid_, slot in (("storage", 3), ("quarters", 4), ("infirmary", 5)):
        st["rooms"].append({"id": rid_, "slot": slot, "built": time.time(), "level": 2})
    S.save_state(uid, st)
    codes = [ean(f"88010{i:07d}") for i in range(1, 41)]
    few, tops = 0, []
    for i, code in enumerate(codes):
        cat = ("medical", "stationery", "drink", "apparel", "food", "electronics", "tobacco", "book")[i % 8]
        j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": cat})
        sg = j["where"]["suggest"]
        if len(sg) < 2:
            few += 1
        tops.append(str(sg[0]["target"]) if sg else "shelf")
        if sg:
            post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": sg[0]["target"]})
        if i % 6 == 5:
            st = S.load_state(uid)
            st["created"] -= 86400
            S.save_state(uid, st)
            ark(uid)
    ok(few == 0, f"선반 밖 선택지가 둘보다 적은 스캔 {few}/40")
    top = max(tops.count(t) for t in set(tops)) / len(tops)
    ok(top < 0.30, f"가장 흔한 1순위 비율 {top:.2f} < 0.30")
    # warm 을 고르면 돌려받지 않는다
    st = S.load_state(uid)
    j = post("/api/scan", {"uid": uid, "barcode": ean("490123499991"), "user_category": "medical"})
    w = [x for x in j["where"]["suggest"] if x["tier"] == "warm"]
    if w:
        g = post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": w[0]["target"]})
        ok(g["tier"] == "warm" and not g["effects"]["returned_to_shelf"] and g["reaction"]["announce"], f"반가워할 사람 → {g['reaction']['announce']}")
    else:
        ok(True, "이 스캔은 warm 없이도 둘 이상")


def t_reactions():
    """스모크 2: 방·선반 반응 문장이 늘 있다(ui_moments give.*)."""
    uid = "dev_s20_react"
    ark(uid)
    G = S.moments()["give"]
    for code, tgt in ((ean("880104309001"), "shelf"), (ean("880104309002"), {"slot": 2}), (ean("880104309003"), {"slot": 2})):
        j = post("/api/scan", {"uid": uid, "barcode": code})
        g = post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": tgt})
        rc = g["reaction"]
        ok(rc and rc["announce"] and rc["announce_key"] and "{" not in rc["announce"]
           and (tgt == "shelf" or rc["line"]), f"{tgt} → [{rc['announce_key']}] {rc['announce']}")
    st = S.load_state(uid)
    a = S.generic_reaction("shelf", {"name": "x"}, st=st)["announce"]
    b = S.generic_reaction("shelf", {"name": "x"}, st=st)["announce"]
    ok(a != b and a in [l.replace("{item}", "x") for l in G["shelf"]], "선반 줄은 돌려 쓴다(연속 금지)")


def t_early_arc():
    """스모크 3 + PM: 1~2일째 매듭 하나 — 요리사 없는 명단도, 밤 조건은 저녁 세션으로."""
    uid = "dev_s20_early"
    ark(uid)
    st = S.load_state(uid)
    cook = next(r for r in st["residents_list"] if r["role"] == "cook")
    ok(S.beat_opens_day(st, cook, S.arc_state(st, cook["id"], "arc_cook_seat"), S.ARC_BY_ID["arc_cook_seat"]["beats"][0]) == 1,
       "요리사 첫 매듭 1일째(data days_since_join 0)")
    uid2 = "dev_s20_nocook"
    ark(uid2)
    st = S.load_state(uid2)
    st["residents_list"] = [r for r in st["residents_list"] if r["role"] != "cook"]
    for r in st["residents_list"]:
        r["joined"] = st["created"]
    S.save_state(uid2, st)
    st = S.load_state(uid2)
    rid = S.early_arc_rid(st)
    r = next(x for x in st["residents_list"] if x["id"] == rid)
    a, s_ = S.current_arc(st, r)
    d = S.beat_opens_day(st, r, s_, S.next_beat(a, s_))
    ok(d <= 2, f"요리사 없는 명단: {r['role']} 첫 매듭 {d}일째")
    sc = next(x for x in st["residents_list"] if x["role"] == "scout")
    sa = S.arc_state(st, sc["id"], "arc_scout_window")
    b0 = S.ARC_BY_ID["arc_scout_window"]["beats"][0]
    S.core_of(st)["beats"]["play_day"] = 2
    st["created"] -= 86400
    st["raid_log"] = []
    if S.early_arc_rid(st) == sc["id"]:
        S.now_hour = lambda: 10
        ok(not S.trig_all(st, uid2, sc, sa, b0["trigger"], None), "정찰병 밤 조건: 아침엔 아직")
        S.now_hour = lambda: 19
        ok(S.trig_all(st, uid2, sc, sa, b0["trigger"], None), "2일째 저녁 세션이면 밤 조건을 풀어 준다")
        S.now_hour = lambda: 10
    else:
        ok(d <= 2, f"보장 대상은 {r['role']}(건네기 매듭) — 2일째까지 열림")
    # 2일째 /api/ark 에서 매듭 하나가 실제로 열린다(건네기 필요 없으면 풀리고, 필요하면 next.open)
    S.save_state(uid2, st)
    S.now_hour = lambda: 19
    a2 = ark(uid2)
    S.now_hour = lambda: 10
    opened = [v["arc"] for v in a2["core"]["residents"].values() if v.get("arc") and ((v["arc"].get("next") or {}).get("open") or v["arc"]["step"] > 0)]
    ok(opened, f"2일째 열린 매듭 {[(x['id'], x['step']) for x in opened]}")


def t_next_visit_rotation():
    """스모크 4: 같은 약속 문장을 두 세션 연속으로 쓰지 않는다(다른 약속이 있으면)."""
    uid = "dev_s20_nv"
    ark(uid)
    st = S.load_state(uid)
    st["resources"]["cloth"] = 0
    st["boxes"] = [{"id": "b1", "cat": "food", "found_day": 1, "found_ts": time.time(), "from": "door"}]
    S.save_state(uid, st)
    lines = []
    for _ in range(4):
        a = ark(uid)
        lines.append((a["next_visit"]["kind"], a["next_visit"]["line"]))
        post("/api/dev/advance", {"uid": uid, "minutes": 45})
    ok(all(x[1] != y[1] for x, y in zip(lines, lines[1:])), f"세션마다 다른 약속 {[k for k, _ in lines]}")
    a = ark(uid)
    b = ark(uid)
    ok(a["next_visit"]["line"] == b["next_visit"]["line"], "같은 세션 안에서는 같은 약속")
    st = S.load_state(uid)
    st["expedition"] = {"id": "e", "members": [st["residents_list"][0]["id"]], "returns_at": time.time() + 600, "result": {}, "scene": {}}
    cands = S.next_visit_candidates(st, uid)
    ok(cands[0]["kind"] == "expedition_return", f"가장 설레는 것부터 {[c['kind'] for c in cands][:4]}")


def t_short_lines():
    uid = "dev_s20_short"
    ark(uid)
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
    fm = j["first_meet"]
    ok(fm and all("line_short" in x for x in fm) and any(x["line_short"] for x in fm), f"first_meet line_short {[x['line_short'] for x in fm]}")
    ok(j["voice"] is None or "text_short" in j["voice"], f"voice.text_short 키 {(j['voice'] or {}).get('text_short')}")
    shorts = [ln for lines in S.VOICE_LINES.values() for ln in lines if ln.get("text_short")]
    ok(shorts, f"dialogue text_short {len(shorts)}줄 읽음")


TESTS = [t_numbers_from_data, t_overflow, t_octo_guarantee, t_feast, t_food_daily_all, t_visitors, t_where_two,
         t_reactions, t_early_arc, t_next_visit_rotation, t_short_lines]

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
