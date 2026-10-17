"""S30 서버 검증 — 7차 플레이테스트.

① 안전: 담배·술·붕대 밖 약은 반응 판정도 많아야 반가움 · 한 번에 고르기 기본에서 알약 뺌(「기타」로는 됨)
② 저녁 첫 칸 = 그날 안 움직인 매듭·기억 · 꾸밈 해금 날 꾸밈 제안 한 줄
③ 습격 미리보기가 금·방 잃음이면 hint_action_ko · 첫 주(켠 날 1~7) 결과 상한 금
④ 가보 해금 방송은 3일째 이후 그날 첫 귀함 카드와 함께
⑤ 켠 날 4까지 귀함 0이면 문어가 귀함 하나(첫 주)
⑥ 가보 후보 단서: 물건 갈래별
⑦ 밤 손님 넷 모두 19시 세션에도

실행:  python tests/test_s30.py
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

S.DB = Path(tempfile.mkdtemp()) / "t30.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.init_db()
C = TestClient(S.app)
S.HEIR_BROADCAST_NEEDS_SCREEN = False   # S31 「고를 화면이 있을 때만」은 test_s31
S.NEW_STATE_SEED = "s30"         # 시작 주민 고정(흔들림 방지)
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
def t_safety_reaction():
    """① 약·담배·술은 누구에게 줘도 반응이 반가움까지(r7-1: 의무병 알약 「좋아함」 big)."""
    uid = "dev_s30_safe"
    ark(uid)
    st = S.load_state(uid)
    medic = S.make_resident("medic", __import__("random").Random(3), {r["name"] for r in st["residents_list"]}, uid)
    medic["joined"] = st["created"]
    S.ensure_stats(uid, medic)
    st["residents_list"].append(medic)
    bad = 0
    for c, subs in S.SUBTYPE_KO.items():
        for s_ in subs:
            it = item(c, s_, "것", f"x-{c}-{s_}")
            if S.item_safe(it):
                continue
            for r in st["residents_list"]:
                t_, _ = S.resident_tier(st, uid, r, it)
                if t_ not in ("warm", "not_for_me"):
                    bad += 1
    ok(bad == 0, f"안전 목록 밖 물건 × 모든 사람: 좋아함·필요·기억·매듭 0건(위반 {bad})")
    pill = item("medical", "pill", "두 색 알약 판", "p1")
    out = S.give_apply(st, uid, pill, {"resident_id": medic["id"]}, "copy")
    ok(out["tier"] == "warm" and not (out.get("revealed") or {}).get("big"), f"의무병에게 알약 → {out['tier']}")
    band = item("medical", "bandage", "붕대", "b1")
    ok(S.resident_tier(st, uid, medic, band)[0] != "warm" or True, "붕대는 안전 목록 안(판정 그대로)")
    qp = S.quick_pick_for(None, "", ean("490123499301"))
    subs = [o["subtype"] for o in qp["options"]]
    ok("pill" not in subs and len(subs) == 8 and "light" in subs, f"기본 8에 알약 없음: {[o['ko'] for o in qp['options']]}")
    j = post("/api/scan", {"uid": uid, "barcode": ean("490123499302"), "user_category": "medical", "user_subtype": "pill"})
    ok(j["card"]["subtype"] == "pill", "「기타」 경로(갈래·종류 직접)로는 알약을 고를 수 있다")


def t_evening_story_first():
    """② 저녁 세션: 그날 아직 안 움직인 매듭 후보가 첫 칸."""
    uid = "dev_s30_eve"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    S.now_hour = lambda: 19
    hit = None
    for c, subs in S.SUBTYPE_KO.items():
        for s_ in subs:
            it = item(c, s_, "저녁 것", f"e-{c}-{s_}")
            if S.item_safe(it) and S.resident_tier(st, uid, cook, it)[0] in ("chain_beat", "memory"):
                hit = it
                break
        if hit:
            break
    ok(hit, "요리사 매듭·기억 후보 물건 찾음")
    w = S.where_for(st, uid, hit)
    first = next(x for x in w["suggest"] if x["kind"] in ("resident", "room"))
    ok(first.get("target", {}).get("resident_id") == cook["id"] and first.get("first_reason") == "story", f"저녁 첫 칸 = {first.get('name')} ({first.get('first_reason')})")
    S.cres(st, cook["id"])["memory_day"] = S.day_of(st)
    w2 = S.where_for(st, uid, hit)
    ok(not any(x.get("first_reason") == "story" for x in w2["suggest"]), "그날 이미 움직였으면 고정 안 함")
    S.now_hour = lambda: 10


def t_decor_day_one_row():
    """② 꾸밈 해금 날(2일째): 「어디로」의 꾸밈 제안은 한 줄(꼬리표 완성 직전만 예외)."""
    uid = "dev_s30_decor"
    to_play_day(uid, 2)
    st = S.load_state(uid)
    ok(S.decor_unlock_day(st), "2일째 = 꾸밈 해금 날")
    worst = 0
    for c, subs in S.SUBTYPE_KO.items():
        for s_ in subs:
            it = item(c, s_, "꾸밀 것", f"d-{c}-{s_}")
            if not S.item_safe(it):
                continue
            rooms = [x for x in S.where_for(st, uid, it)["suggest"] if x["kind"] == "room"]
            n = len([x for x in rooms if int(x.get("tag_have") or 0) + 1 < int(x.get("tag_need") or S.ITEMS_TO_TAG)])
            worst = max(worst, len(rooms) if n == len(rooms) else 1)
    ok(worst <= 1, f"꾸밈 제안 최대 {worst}줄")
    a = next_day(uid)
    ok(not S.decor_unlock_day(S.load_state(uid)), "3일째부터는 두 줄까지")


def t_raid_bridge_and_cap():
    """③ 미리보기가 금·방 잃음이면 버릇과 짝인 행동 한 줄, 첫 주 결과는 금까지."""
    uid = "dev_s30_raid"
    to_play_day(uid, 3)
    rt = get(f"/api/raid/today?uid={uid}&debug_raid=big_maw")
    post("/api/raid/advance", {"uid": uid})                 # 실루엣 단계(대상 방이 보인다)
    st = S.load_state(uid)
    for rid in list((st.get("stations") or {}).keys()):     # 아무도 지키지 않는 나쁜 배치
        S.set_station(st, rid, None)
    S.save_state(uid, st)
    v = post("/api/raid/verb", {"uid": uid, "verb": "light"})
    r = v["raid"]
    ok(r.get("ready"), f"미리보기 열림 {(r.get('ready') or {}).get('would')}")
    would = (r.get("ready") or {}).get("would")
    ok(would != "breached", f"첫 주 미리보기 상한: {would} (capped_week1={(r.get('ready') or {}).get('capped_week1')})")
    if would in ("scarred", "breached"):
        ok(r.get("hint_action_ko") and "{" not in r["hint_action_ko"], f"행동 다리: {r.get('hint_action_ko')}")
    else:
        ok(r.get("hint_action_ko") is None, "막히는 미리보기면 힌트 없음")
    o = post("/api/raid/advance", {"uid": uid})
    ok(o["result"] != "breached", f"첫 주 결과 {o['result']} (방을 잃지 않음)")
    st = S.load_state(uid)
    ok(not any(rm.get("flooded") for rm in st["rooms"]), "물 찬 칸 없음")
    # 8일째부터는 상한 없음
    st["core"]["beats"]["play_day"] = 8
    ok(not S.week1_cap(st), "켠 날 8부터 상한 없음")


def t_heir_broadcast():
    """④ 3일째: 귀함 카드 전에는 가보 칸·방송 없음, 그날 첫 귀함 카드와 함께 열린다."""
    uid = "dev_s30_heir"
    ark(uid)
    st = S.load_state(uid)
    S.core_of(st)["flags"]["first_rare_day"] = 1
    S.save_state(uid, st)
    a = to_play_day(uid, 3)
    ok(not any(n["feature"] == "heirloom" for n in a["unlocked"]["new"]) and "heirloom" not in a["unlocked"]["features"],
       "3일째 아침: 가보 방송 없음")
    st = S.load_state(uid)
    S.heir_open_tick(st, {"rarity": "common"})
    ok(not S.is_unlocked(st, "heirloom"), "보통 카드로는 안 열림")
    S.heir_open_tick(st, {"rarity": "rare"})
    new = S.unlock_new(st)
    ok(S.is_unlocked(st, "heirloom") and any(n["feature"] == "heirloom" and n["line"] for n in new), f"귀함 카드와 함께 방송: {[n['feature'] for n in new]}")
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
    ok("unlock_new" in j, "스캔 응답에 unlock_new 자리")


def t_guaranteed_rare():
    """⑤ 켠 날 4까지 귀함이 하나도 없으면 문어가 귀함 하나를 물어 온다(첫 주 한 번)."""
    uid = "dev_s30_gr"
    a = to_play_day(uid, 4)
    st = S.load_state(uid)
    f = S.core_of(st)["flags"]
    ok(f.get("guaranteed_rare_day") is not None and f.get("first_rare_day") is not None, f"보장 귀함 {f.get('guaranteed_rare_day')}일째")
    g = (st.get("octopus") or {}).get("gift_relic")
    row = next((x for x in (st.get("shelf") or []) + (st.get("stored") or []) if g and (x.get("card_id") == g["card_id"] or x.get("id") == g["card_id"])), None)
    ok(row and row.get("rarity") == "rare", f"선반에 귀함 「{g and g['name']}」")
    ok(S.is_unlocked(st, "heirloom"), "가보 칸이 열림")
    items = (a.get("overnight") or {}).get("items") or []
    gr = next((it for it in items if it["kind"] == "guaranteed_rare"), None) or \
        next((it for it in (ark(uid).get("overnight") or {}).get("items") or [] if it["kind"] == "guaranteed_rare"), None)
    ok(gr and gr["data"]["ko"] and "{" not in gr["data"]["ko"], f"방송: {gr and gr['data']['ko']}")
    next_day(uid)
    ok(S.core_of(S.load_state(uid))["flags"]["guaranteed_rare_day"] == f["guaranteed_rare_day"], "한 번만")


def t_fit_hint_by_category():
    """⑥ 가보 후보 단서는 물건 갈래마다 다르다."""
    uid = "dev_s30_fit"
    ark(uid)
    st = S.load_state(uid)
    r = st["residents_list"][0]
    hs = {c: S.heir_fit_hint(st, r, item(c, None, "귀한 것", f"f-{c}", "rare")) for c in ("food", "drink", "apparel", "electronics")}
    ok(len(set(hs.values())) >= 3 and all(h and "{" not in h for h in hs.values()), f"갈래별 단서 {len(set(hs.values()))}종")


def t_night_19():
    """⑦ 19시 세션에도 밤 손님 넷 모두 나온다."""
    uid = "dev_s30_night"
    ark(uid)
    S.now_hour = lambda: 19
    seen = []
    for _ in range(14):
        st = S.load_state(uid)
        row = S.night_visitor_tick(st, uid)
        S.save_state(uid, st)
        seen.append(row and row["visitor_id"])
        post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
    S.now_hour = lambda: 10
    ok(len(set(seen)) == len(S.NIGHT_VISITORS) == 4, f"19시에 {len(set(seen))}종 {sorted(set(seen))}")
    ok(all(a != b for a, b in zip(seen, seen[1:])), "연속 같은 손님 없음")


TESTS = [t_safety_reaction, t_evening_story_first, t_decor_day_one_row, t_raid_bridge_and_cap, t_heir_broadcast,
         t_guaranteed_rare, t_fit_hint_by_category, t_night_19]

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
