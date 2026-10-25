"""S34 서버 검증 — C안: 마음(점수·감쇠·5단계·겹침 금지) · 편한 방(배정·덤·혼잣말) · 결과 칩.

실행:  python tests/test_s34.py
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

S.DB = Path(tempfile.mkdtemp()) / "t34.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.NEW_STATE_SEED = "s34"
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


def item(cat, sub, name, code, rarity="common"):
    return {"name": name, "category": cat, "subtype": sub, "family": None, "rarity": rarity, "barcode": code, "card_id": f"c-{code}"}


def give_item(uid, it, rid):
    st = S.load_state(uid)
    sid = f"g-{it['barcode']}-{time.time()}"
    S.core_of(st)["scans"][sid] = {"item": it, "day": S.day_of(st), "given": False, "placed": "copy", "at": time.time(), "warm": [rid]}
    S.save_state(uid, st)
    return post("/api/give", {"uid": uid, "scan_id": sid, "target": {"resident_id": rid}})


ITEMS = [(c, s_) for c, subs in S.SUBTYPE_KO.items() for s_ in subs if S.item_safe({"category": c, "subtype": s_})]


# ─────────────────────────────────────────────────────────────
def t_heart_points():
    """점수: 반가움 1·좋아함 2·필요 3, 돌려줌 0, 감쇠 곱(0.5 단위) · 결과 칩에 「마음 +n」."""
    uid = "dev_s34_pts"
    ark(uid)
    st = S.load_state(uid)
    r = st["residents_list"][0]
    by_tier = {}
    for c, s_ in ITEMS:
        t_ = S.resident_tier(st, uid, r, item(c, s_, "x", f"t-{c}-{s_}"))[0]
        by_tier.setdefault(t_, (c, s_))
    res = []
    for t_, (c, s_) in sorted(by_tier.items()):
        if t_ in ("chain_beat", "memory"):
            continue
        g = give_item(uid, item(c, s_, "물건", f"p-{c}-{s_}"), r["id"])
        h = g["effects"]["heart"]
        res.append((g["tier"], h["gain"], g["mult"]))
        exp = round(S.HEART_POINTS.get(g["tier"], 0) * (g["mult"] or 1) * 2) / 2
        ok(h["gain"] == exp, f"{g['tier']} → 마음 +{h['gain']} (감쇠 {g['mult']}, 기대 {exp})")
        if h["gain"]:
            ok(any(cp["kind"] == "heart" and "마음" in cp["ko"] for cp in g["effects"]["chips"]), f"칩 {[cp['ko'] for cp in g['effects']['chips']]}")
    a = ark(uid)
    hp = a["core"]["residents"][r["id"]]["heart"]
    ok(hp["points"] == S.heart_state(S.load_state(uid), r["id"])["points"] and hp["levels"] == [3, 8, 18, 32, 52], f"/api/ark heart {hp}")


def t_heart_levels():
    """단계 1~5: 인사 한 줄 · 수첩 좋아함 한 칸 · 답례 소품 · 한 상 초대(신뢰 ×1.5) · 덧매듭+머리맡."""
    uid = "dev_s34_lv"
    ark(uid)
    st = S.load_state(uid)
    r = st["residents_list"][0]
    # 반가움만 주는 물건 찾기(장면 겹침 없이)
    warm = next(item(c, s_, "따뜻한 것", f"w-{c}-{s_}") for c, s_ in ITEMS
                if S.resident_tier(st, uid, r, item(c, s_, "x", "x"))[0] == "warm")
    S.heart_state(st, r["id"])["points"] = 2.5
    S.save_state(uid, st)
    g = give_item(uid, dict(warm, barcode="lv1"), r["id"])
    up = g["effects"]["heart"].get("level_up")
    ok(up and up["level"] == 1 and up["scenes"] and up["scenes"][0]["kind"] == "line" and up["scenes"][0]["announce"],
       f"L1 인사: {up and up['scenes'] and up['scenes'][0]['announce']}")
    st = S.load_state(uid)
    known_before = set(S.nb_known(st, r["id"]))
    S.heart_state(st, r["id"])["points"] = 7.5
    S.save_state(uid, st)
    g = give_item(uid, dict(warm, barcode="lv2"), r["id"])
    sc = (g["effects"]["heart"].get("level_up") or {}).get("scenes") or []
    st = S.load_state(uid)
    new = set(S.nb_known(st, r["id"])) - known_before
    ok(sc and sc[0]["kind"] == "notebook" and any(k.startswith("like:") for k in new), f"L2 수첩 저절로 {new} · {sc and sc[0]['announce']}")
    S.heart_state(st, r["id"])["points"] = 17.5
    S.save_state(uid, st)
    g = give_item(uid, dict(warm, barcode="lv3"), r["id"])
    sc = (g["effects"]["heart"].get("level_up") or {}).get("scenes") or []
    st = S.load_state(uid)
    ok(sc and sc[0]["kind"] == "return_gift" and any(x.get("card_id") == f"heart-{r['id']}" for x in (st.get("shelf") or []) + (st.get("stored") or [])),
       f"L3 답례 소품 선반에 · {sc and sc[0].get('gift_ko')}")
    S.heart_state(st, r["id"])["points"] = 31.5
    S.save_state(uid, st)
    g = give_item(uid, dict(warm, barcode="lv4"), r["id"])
    sc = (g["effects"]["heart"].get("level_up") or {}).get("scenes") or []
    st = S.load_state(uid)
    inv = S.core_of(st).get("table_invite")
    ok(sc and sc[0]["kind"] == "table_invite" and inv and inv["rid"] == r["id"] and "{" not in (sc[0]["announce"] or "{"), f"L4 한 상 초대: {sc and sc[0]['announce']}")
    S.heart_state(st, r["id"])["points"] = 51.5
    S.save_state(uid, st)
    g = give_item(uid, dict(warm, barcode="lv5"), r["id"])
    sc = (g["effects"]["heart"].get("level_up") or {}).get("scenes") or []
    ok(sc and sc[0]["kind"] == "story_knot" and len(sc[0]["scene"]) == 3 and sc[0]["keepsake"], f"L5 덧매듭 {len(sc[0]['scene']) if sc else 0}줄 · {sc and sc[0]['keepsake']}")


def t_table_invite():
    """L4 초대한 짝으로 한 상을 차리면 신뢰 ×1.5."""
    uid = "dev_s34_inv"
    a = ark(uid)
    while a["unlocked"]["play_day"] < 6:
        post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
        a = ark(uid)
    S.now_hour = lambda: 19
    st = S.load_state(uid)
    a_, b_ = st["residents_list"][0], st["residents_list"][1]
    S.core_of(st)["table_invite"] = {"rid": a_["id"], "other": b_["id"], "day": S.day_of(st)}
    st["resources"]["food"] = 30
    S.save_state(uid, st)
    j = post("/api/scan", {"uid": uid, "barcode": "8801043015097"})
    r1 = post("/api/table", {"uid": uid, "relic_id": j["card"]["id"], "seats": [[a_["id"], b_["id"]]]})
    base = S.ET_TRUST[2] if len(r1["liked_by"]) == 2 else S.ET_TRUST[1] if r1["liked_by"] else S.ET_TRUST[0]
    ok(r1["invited"] and r1["trust_delta"] == int(round(base * 1.5)), f"초대 짝 신뢰 +{r1['trust_delta']} (기본 {base})")
    S.now_hour = lambda: 10


def t_no_double():
    """같은 건네기에 매듭·기억·필요 장면이 있으면 단계 장면은 미뤄서 떠날 때 카드에."""
    uid = "dev_s34_dbl"
    ark(uid)
    st = S.load_state(uid)
    r = st["residents_list"][0]
    nd = S.need_today(uid, r, S.day_of(st))
    if not nd or not S.item_rule_safe(nd):
        ok(True, "오늘 안전한 필요 없음(건너뜀)")
        return
    sub = nd.get("subtype")
    sub = sub[0] if isinstance(sub, list) else sub
    S.heart_state(st, r["id"])["points"] = 2.0
    S.save_state(uid, st)
    g = give_item(uid, item(nd["category"], sub, "필요한 것", "need1"), r["id"])
    up = g["effects"]["heart"].get("level_up") or {}
    ok(g["tier"] in ("need", "chain_beat", "memory") and up.get("deferred") and not up.get("scenes"), f"필요 장면과 겹침 → 미룸 ({g['tier']})")
    lv = get(f"/api/leaving?uid={uid}")
    ok(lv["heart_scenes"] and lv["heart_scenes"][0]["level"] == 1, "떠날 때 카드에 마음 장면")
    ok(not get(f"/api/leaving?uid={uid}")["heart_scenes"], "한 번만")


def t_comfort():
    """편한 방: 역할 표(특이점 30% 덧붙임) · 거기 두면 배율 +0.12(상한 1.30) · 혼잣말 하루 1 · 드래그 comfort."""
    uid = "dev_s34_cf"
    a = ark(uid)
    st = S.load_state(uid)
    cook = next(r for r in st["residents_list"] if r["role"] == "cook")
    cr = S.comfort_room_of(st, cook)
    ok(cr in S.ROOMS, f"요리사 편한 방 {cr}")
    cook["comfort_room"] = "pantry"
    S.set_station(st, cook["id"], 2)
    S.save_state(uid, st)
    st = S.load_state(uid)
    rm = S.room_at(st, 2)
    S.COMFORT_ENFORCE = False
    m0 = S.room_mult(st, rm)[1]["stat_mult"]
    S.COMFORT_ENFORCE = True
    m1 = S.room_mult(st, rm)[1]["stat_mult"]
    ok(abs(m1 - min(1.3, m0 + 0.12)) < 1e-6, f"편한 방 덤 {m0} → {m1}")
    a = ark(uid)
    rv = a["core"]["residents"][cook["id"]]
    ok(rv["comfort_room"] == "pantry" and rv["comfort_now"], "core.residents comfort_now")
    mut = a["comfort_mutters"]
    ok(any(x["resident_id"] == cook["id"] and x["line"] for x in mut), f"혼잣말 {[x['line'] for x in mut]}")
    ok(not any(x["resident_id"] == cook["id"] for x in ark(uid)["comfort_mutters"]), "하루 한 번")
    other = next(r for r in st["residents_list"] if r["id"] != cook["id"])
    S.set_station(st, cook["id"], None)
    S.save_state(uid, st)
    mp = ark(uid)["move_preview"][cook["id"]]
    ok(mp["2"]["comfort"] is True, "드래그: 편한 방 위에 comfort")
    # 특이점 덧붙임 비율(역할 표에서 바뀌는 사람 ≈ 30% × 특이점 + 인 사람)
    n, moved = 0, 0
    for i in range(200):
        rr = S.make_resident("cook", __import__("random").Random(i), set(), "u")
        S.ensure_stats("u", rr)
        q = rr.get("quirk") or {}
        if q.get("stat") and int(q.get("sign") or 0) > 0:
            n += 1
            if S.comfort_room_of({}, rr) != "pantry":
                moved += 1
    ok(n and 0.15 <= moved / n <= 0.45, f"특이점 + 인 요리사 {n}명 중 {moved}명 편한 방이 다름({moved / max(1, n):.2f})")


TESTS = [t_heart_points, t_heart_levels, t_table_invite, t_no_double, t_comfort]

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
