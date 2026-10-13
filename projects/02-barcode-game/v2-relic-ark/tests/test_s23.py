"""S23 서버 검증 — 1단계 뒤쪽: 사람 수첩(기색·결과 공개·귀띔·늘 이름표), 받는 저녁 한 상, 밤 손님, 내일의 부탁, 이름 투표 어긋남.

실행:  python tests/test_s23.py
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

S.DB = Path(tempfile.mkdtemp()) / "t23.db"
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


def item(cat, sub=None, name=None, code=None):
    return {"name": name or f"{cat}-{sub}", "category": cat, "subtype": sub, "family": None, "rarity": "common",
            "barcode": code or f"x{cat}{sub}{name}", "card_id": None}


def resident(st, role):
    return next((r for r in st["residents_list"] if r["role"] == role), None)


def to_day(uid, d):
    st = S.load_state(uid)
    st["created"] -= 86400 * (d - S.day_of(st))
    S.save_state(uid, st)


# ─────────────────────────────────────────────────────────────
def t_notebook_labels():
    """① 1~2일째는 라벨·값 순서, 3일째부터 사람 → 방 고정 순서, 모르는 칸은 라벨 대신 기색."""
    uid = "dev_s23_nb"
    ark(uid)
    st = S.load_state(uid)
    w = S.where_for(st, uid, item("food", "noodle", "면", "w1"))
    ok(w["labels"] is True and w["order"] == "value" and all("tier" in x for x in w["suggest"]), "1일째 라벨")
    to_day(uid, 3)
    ark(uid)
    st = S.load_state(uid)
    sc = resident(st, "scout")
    for a_ in [a for a in S.ARCS if a["role"] == "scout"]:
        S.arc_state(st, sc["id"], a_["id"])["done"] = True
    S.cres(st, sc["id"])["memories_seen"] = [m["id"] for m in S.TASTES["roles"]["scout"]["memories"]]
    nd = S.need_today(uid, sc, S.day_of(st))
    it = item(nd["category"], (nd.get("subtype") or [None])[0], "필요한 것", "nb1")
    w = S.where_for(st, uid, it)
    row = next((x for x in w["suggest"] if x["target"].get("resident_id") == sc["id"]), None)
    ok(w["labels"] is False and w["order"] == "least_recent", "3일째 오래 못 받은 사람부터")
    ok(row and row["known"] is False and "tier" not in row and "icon" not in row and "value" not in row and row["hint_ko"]
       and "{" not in row["hint_ko"], f"모르는 칸 → 기색: {row and row.get('hint_ko')}")
    kinds = [x["kind"] for x in w["suggest"]]
    ok(kinds == sorted(kinds, key=lambda k: k != "resident"), f"사람 → 방 순서 {kinds}")
    # 건넨 뒤 결과 공개(맞힘) → 수첩 → 다음엔 라벨
    S.save_state(uid, st)
    j = post("/api/scan", {"uid": uid, "barcode": ean("490123477100"), "user_category": nd["category"]})
    if j["where"].get("subtype_pick") and nd.get("subtype"):
        post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": nd["subtype"][0]})
    g = post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": {"resident_id": sc["id"]}})
    rv = g["revealed"]
    ok(rv and rv["kind"] == "need" and rv["big"] and rv["slot"] == f"need:{nd['idx']}" and rv["line_key"].startswith("reveal.discovered"),
       f"맞힘(big) → {rv and rv['line']}")
    st = S.load_state(uid)
    nb = S.notebook_public(st, uid, resident(st, "scout"))
    ok(any(x["key"] == f"need:{nd['idx']}" and x["known"] and x["ko"] for x in nb["slots"]), f"수첩 {nb['known']}/{nb['total']}")
    w2 = S.where_for(st, uid, item(nd["category"], (nd.get("subtype") or [None])[0], "필요2", "nb2"))
    row2 = next((x for x in w2["suggest"] if x["target"].get("resident_id") == sc["id"]), None)
    ok(row2 and row2["known"] and row2.get("tier") == "need", "알게 된 칸은 다시 라벨")
    # 늘 이름표
    pr = post("/api/prefs", {"uid": uid, "labels_always": True})
    st = S.load_state(uid)
    ok(pr["prefs"]["labels_always"] and S.where_for(st, uid, it)["labels"] is True and pr["label_ko"], "늘 이름표 설정")
    ok(ark(uid)["prefs"]["labels_always"] is True, "/api/ark.prefs")


def t_notebook_early_record():
    """① 1~2일째 라벨로 건넨 결과도 수첩에(맞힘 아님)."""
    uid = "dev_s23_early"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    for a_ in [a for a in S.ARCS if a["role"] == "cook"]:
        S.arc_state(st, cook["id"], a_["id"])["done"] = True
    lk = S.TASTES["roles"]["cook"]["likes"][0]
    S.save_state(uid, st)
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
    st = S.load_state(uid)
    it = dict(item(lk["category"], lk["subtype"][0], "면", "e1"))
    before = S.notebook_before(st, uid, it, {"resident_id": cook["id"]})
    out = S.give_apply(st, uid, it, {"resident_id": cook["id"]}, "copy")
    rv = S.notebook_record(st, uid, it, {"resident_id": cook["id"]}, out, before)
    ok(rv["kind"] == "like" and not rv["big"] and rv["slot"] == "like:0" and "like:0" in S.nb_known(st, cook["id"]),
       f"1일째 라벨 건넴도 수첩에, big 아님 {rv}")


def t_repeat_line():
    """① 같은 세션 같은 사람 두 번째 → repeat_lines({other})."""
    uid = "dev_s23_rep"
    ark(uid)
    codes = [ean("490123466001"), ean("490123466018")]
    st = S.load_state(uid)
    cook = resident(st, "cook")
    gs = []
    for cd in codes:
        j = post("/api/scan", {"uid": uid, "barcode": cd, "user_category": "food"})
        gs.append(post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": {"resident_id": cook["id"]}}))
    rp = gs[1].get("repeat")
    ok(gs[0].get("repeat") is None and rp and rp["other_name"] in rp["line"] and rp["other_id"] != cook["id"] and gs[1]["mult"] == S.DIM_SAME_DAY,
       f"두 번째 → {rp and rp['line']} (값 ×{gs[1]['mult']})")


def t_gossip():
    """① 저녁 귀띔: 가장 많이 받은 사람의 모르는 칸 하나가 알려진다(하루 한 번)."""
    uid = "dev_s23_gos"
    ark(uid)
    st = S.load_state(uid)
    sc = resident(st, "scout")
    for i in range(3):
        S.cres(st, sc["id"])["given"].append(dict(item("food", "x", f"g{i}", f"g{i}"), day=1))
    S.save_state(uid, st)
    S.now_hour = lambda: 19
    post("/api/dev/advance", {"uid": uid, "minutes": 45})
    a = ark(uid)
    S.now_hour = lambda: 10
    tip = a["notebook_tip"]
    ok(tip and tip["resident_id"] == sc["id"] and tip["line"] and "{" not in tip["line"], f"귀띔: {tip and tip['line']}")
    st = S.load_state(uid)
    ok(S.nb_known(st, sc["id"]).get(tip["slot"], {}).get("how") == "gossip", "귀띔 칸이 수첩에(how=gossip)")
    S.now_hour = lambda: 20
    post("/api/dev/advance", {"uid": uid, "minutes": 45})
    a2 = ark(uid)
    S.now_hour = lambda: 10
    ok(a2["notebook_tip"]["slot"] == tip["slot"], "하루 한 번")


def t_table():
    """② 저녁 한 상: 첫 저녁 세션에 열림, 식량 4(한 상 몫 먼저), 신뢰 +3/+5/+7, 같은 짝 연달아 ×0.5, 대화·약속."""
    uid = "dev_s23_tab"
    ark(uid)
    ok(ark(uid)["evening_table"] is None, "낮에는 상 없음")
    S.now_hour = lambda: 19
    a = ark(uid)
    et = a["evening_table"]
    ok(et and et["open"] and et["table_prompt"] and et["candidates"]["residents"], f"저녁 상 열림 {et and et['open_ko']}")
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
    st = S.load_state(uid)
    cook, eng = resident(st, "cook"), resident(st, "engineer")
    st["resources"]["food"] = 20
    S.core_of(st)["table_store"] = 2
    S.save_state(uid, st)
    rid = j["card"]["id"]
    r = post("/api/table", {"uid": uid, "relic_id": rid, "seats": [[cook["id"], eng["id"]]]})
    st = S.load_state(uid)
    la = any(S.match(x, S.item_from_row(next(y for y in st["shelf"] if y.get("card_id") == rid))) for x in S.likes_of(uid, cook))
    ok(r["table_store_paid"] == 2 and r["food_paid"] == S.ET_FOOD - 2 and st["resources"]["food"] == 20 - (S.ET_FOOD - 2), "식량: 한 상 몫 먼저")
    ok(r["trust_delta"] in S.ET_TRUST and int(resident(st, "cook")["trust"].get(eng["id"], 0)) >= r["trust_delta"],
       f"신뢰 +{r['trust_delta']}(좋아함 {r['liked_by']})")
    ok(r["talk"] and all(x["line"] and "{" not in x["line"] for x in r["talk"]) and r["promise"], f"대화 {[x['line'] for x in r['talk']]}")
    ok(any(x.get("card_id") == rid for x in st["shelf"] + st.get("stored", [])), "물건은 제자리(없어지지 않음)")
    bad = C.post("/api/table", json={"uid": uid, "relic_id": rid, "seats": [[cook["id"], eng["id"]]]})
    ok(bad.status_code == 400, "하루 한 번")
    ok(ark(uid)["evening_table"]["done"], "차린 뒤 done")
    # 다음 날 같은 짝 ×0.5
    post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
    ark(uid)
    r2 = post("/api/table", {"uid": uid, "relic_id": rid, "seats": [[eng["id"], cook["id"]]]})
    ok(r2["repeat_pair"] and r2["trust_delta"] == max(1, int(round(r["trust_delta"] * S.ET_REPEAT))), f"같은 짝 연달아 → +{r2['trust_delta']}")
    S.now_hour = lambda: 10
    bad = C.post("/api/table", json={"uid": uid, "relic_id": rid, "seats": [[cook["id"], eng["id"]]]})
    ok(bad.status_code == 400, "저녁이 아니면 400")


def t_overflow_table_store():
    uid = "dev_s23_ovt"
    ark(uid)
    st = S.load_state(uid)
    cap = S.storage_cap(st)
    st["resources"]["food"] = cap
    S.save_state(uid, st)
    st = S.load_state(uid)
    st["resources"]["food"] = cap + 20
    S.save_state(uid, st)
    st = S.load_state(uid)
    ok(int(S.core_of(st).get("table_store") or 0) == min(20, S.TABLE_STORE_MAX), f"넘친 식량 → 한 상 몫 {S.core_of(st).get('table_store')}")


def t_night_visitor():
    uid = "dev_s23_night"
    ark(uid)
    S.now_hour = lambda: 20
    post("/api/dev/advance", {"uid": uid, "minutes": 45})
    a = ark(uid)
    S.now_hour = lambda: 10
    nv = [v for v in a["visits"] if v.get("kind") == "night_visitor"]
    ok(nv and nv[0]["visitor_id"] == S.NIGHT_VISITORS[0]["id"] and nv[0]["line"] and "{room}" not in nv[0]["line"], f"밤 손님 {nv and nv[0]['line'][:30]}")
    post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
    a = ark(uid)
    ok(any(it["kind"] == "night_trace" for it in (a["overnight"] or {}).get("items") or []), "다음 날 아침 흔적")


def t_tomorrow_ask():
    """③ 내일의 부탁 = 내일 실제 필요(같은 시드)."""
    uid = "dev_s23_tom"
    ark(uid)
    lv = get(f"/api/leaving?uid={uid}")
    ta = lv["tomorrow_ask"]
    ok(ta and ta["line"] and "{" not in ta["line"], f"내일의 부탁: {ta and ta['line']}")
    post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
    a = ark(uid)
    nd = next(x for x in a["needs_today"] if x["resident_id"] == ta["resident_id"])
    ok(nd["need"]["ko"] == ta["need"]["ko"] and nd["need"]["category"] == ta["need"]["category"], f"다음 날 실제 필요와 같다({nd['need']['ko']})")


def t_vote_mismatch():
    """④ 전역 이름(3곳·60%)과 다르게 고른 바코드는 의도 장면 없음(주기는 그대로)."""
    code = ean("490123455001")
    for i in range(3):
        uid = f"dev_s23_v{i}"
        ark(uid)
        j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
        post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": "milk"})
    uid = "dev_s23_vme"
    ark(uid)
    st = S.load_state(uid)
    st.setdefault("barcodes", {})[code] = {"category": "drink", "subtype": "water"}
    ok(S.vote_mismatch(st, {"barcode": code, "category": "drink"}), "모두 우유인데 나는 물 → 어긋남")
    st["barcodes"][code]["subtype"] = "milk"
    ok(not S.vote_mismatch(st, {"barcode": code, "category": "drink"}), "같게 부르면 어긋남 아님")


def t_order_and_hints():
    """후속: 3일째부터 가장 오래 못 받은 사람부터(첫자리 쏠림 없음) · 한 「어디로」 안에서 같은 기색 문장 없음."""
    uid = "dev_s23_ord"
    ark(uid)
    to_day(uid, 3)
    ark(uid)
    st = S.load_state(uid)
    for i in range(3):
        st["residents_list"].append(S.make_resident(("medic", "farmer", "kid")[i], random.Random(40 + i),
                                                    {r["name"] for r in st["residents_list"]}, uid))
        st["residents_list"][-1]["joined"] = st["created"]
        S.ensure_stats(uid, st["residents_list"][-1])
    S.save_state(uid, st)
    # B 흉내: 첫 제안만 누른다 — 받는 사람이 돌아가야 한다
    firsts = []
    for i in range(8):
        j = post("/api/scan", {"uid": uid, "barcode": ean(f"49012344{i:04d}"), "user_category": "drink"})
        w = j["where"]
        ppl = [x for x in w["suggest"] if x["kind"] == "resident"]
        if not ppl:
            continue
        hints = [x["hint_ko"] for x in ppl if x.get("hint_ko")]
        st = S.load_state(uid)
        names = {r["name"] for r in st["residents_list"]}
        templates = []
        for h in hints:
            t_ = h
            for n in names:
                t_ = t_.replace(n, "{name}")
            for rk in ("요리사", "기술자", "정찰병", "의무병", "농부", "아이", "학자", "교섭가"):
                t_ = t_.replace(rk + " ", "")
            templates.append(t_)
        ok(len(set(templates)) == len(templates), f"스캔 {i + 1}: 기색 문장 겹침 없음 ({len(templates)}줄)")
        firsts.append(ppl[0]["target"]["resident_id"])
        post("/api/give", {"uid": uid, "scan_id": w["scan_id"], "target": ppl[0]["target"]})
        post("/api/dev/advance", {"uid": uid, "minutes": 1})
    top = max(firsts.count(f) for f in set(firsts)) / len(firsts)
    ok(len(set(firsts)) >= 3 and top <= 0.5, f"첫 제안만 눌러도 받는 사람이 돈다: {len(set(firsts))}명, 최다 {top:.2f}")
    st = S.load_state(uid)
    never = [r for r in st["residents_list"] if not S.cres(st, r["id"])["given"]]
    w = S.where_for(st, uid, item("drink", "milk", "우유", "o1"))
    ppl = [x for x in w["suggest"] if x["kind"] == "resident"]
    if never and any(x["target"]["resident_id"] == never[0]["id"] for x in ppl):
        ok(S.cres(st, ppl[0]["target"]["resident_id"])["given"] == [], "받은 적 없는 사람이 맨 앞")


def t_missed_undecided_and_dev_imprint():
    """후속: 아직 고르지 않은 스캔은 missed_chain 이 아니다 · 개발 전용 각인 주기(RELIC_DEV 아니면 404)."""
    uid = "dev_s23_mu"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    S.core_of(st)["scans"]["su"] = {"item": item("food", "noodle", "면", "mu1"), "day": S.day_of(st), "given": False,
                                    "chain": [{"rid": cook["id"], "name": cook["name"], "tier": "chain_beat"}]}
    S.save_state(uid, st)
    ok(ark(uid)["missed_chain"] is None and get(f"/api/leaving?uid={uid}")["missed_chain"] is None, "방금 찍고 아직 안 고른 스캔 → missed_chain 없음")
    st = S.load_state(uid)
    S.core_of(st)["scans"]["su"].update({"given": True, "to": "shelf"})
    S.save_state(uid, st)
    ok((ark(uid)["missed_chain"] or {}).get("resident_id") == cook["id"], "선반으로 닫은 뒤에는 missed_chain")
    ids = [i["id"] for i in S.IMPRINT_LIST[:3]]
    j = post("/api/dev/imprint", {"uid": uid, "resident_id": cook["id"], "ids": ids})
    st = S.load_state(uid)
    ok(j["ok"] and resident(st, "cook")["imprints"] == ids and j["role_evolved"], f"개발 각인 3개 → 역할 진화 {j['evolved_ko']}")
    pid = next(iter(S.ARC_IMPRINTS))
    j = post("/api/dev/imprint", {"uid": uid, "resident_id": cook["id"], "ids": [pid], "personal": True})
    ok(resident(S.load_state(uid), "cook")["personal_imprints"] == [pid], "개인 각인도")
    ok(C.post("/api/dev/imprint", json={"uid": uid, "resident_id": cook["id"], "ids": ["nope"]}).status_code == 400, "없는 각인 400")
    ok(C.post("/api/dev/imprint", json={"uid": uid, "resident_id": cook["id"], "ids": ids + [ids[0]]}).status_code == 400, "4개·중복 400")
    S.DEV_MODE = False
    try:
        ok(C.post("/api/dev/imprint", json={"uid": uid, "resident_id": cook["id"], "ids": ids[:1]}).status_code == 404, "배포(RELIC_DEV 아님) → 404")
    finally:
        S.DEV_MODE = True


TESTS = [t_missed_undecided_and_dev_imprint, t_order_and_hints, t_notebook_labels, t_notebook_early_record, t_repeat_line, t_gossip, t_table, t_overflow_table_store, t_night_visitor,
         t_tomorrow_ask, t_vote_mismatch]

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
