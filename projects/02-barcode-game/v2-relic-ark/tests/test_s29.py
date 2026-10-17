"""S29 서버 검증 — 6차 플레이테스트 §4.

① 이름 다시 붙이기: 바코드마다 하루 한 번 + 선반·창고 행 갱신(r6-1)
② 라벨 없는 날 「어디로」 첫 칸 = 수첩에 아는 칸이 맞는 사람
③ 저녁 귀띔: 수첩 빈칸이 남는 동안 매일
④ 가보: 후보 하나면 가까운 사람 하나 더 · 오늘 들어온 사람은 내일부터
⑤ 밤 손님 돌려 쓰기(이틀 연속 같은 손님 없음)
⑥ r6-3 원정 귀환 소식은 한 세션만
⑦ 한 번에 고르기 기본 8(6차 로그 재집계)
⑧ 습격 3일째 · 첫 주 긴목 보장 3일째 · 해금 방송과 습격 카드가 겹치지 않음

실행:  python tests/test_s29.py
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

S.DB = Path(tempfile.mkdtemp()) / "t29.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.init_db()
C = TestClient(S.app)
S.LOW_KNOWN = 0                  # S31 아는 칸 적은 방주 첫 칸 규칙은 test_s31
S.NEW_STATE_SEED = "s29"         # 시작 주민 고정(흔들림 방지)
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
def t_rename_per_barcode():
    """① 바코드마다 하루 한 번, 선반·창고의 그 물건도 새 하위 종류(r6-1)."""
    uid = "dev_s29_ren"
    ark(uid)
    codes = [ean("490123488101"), ean("490123488102")]
    for c in codes:
        j = post("/api/scan", {"uid": uid, "barcode": c, "user_category": "apparel", "user_subtype": "shirt"})
        ok(j["card"]["subtype"] == "shirt", f"{c}: 옷으로 정함")
    r1 = post("/api/scan/subtype", {"uid": uid, "barcode": codes[0], "subtype": "small", "rename": True})
    r2 = post("/api/scan/subtype", {"uid": uid, "barcode": codes[1], "subtype": "small", "rename": True})
    ok(r1["ok"] and r2["ok"], "서로 다른 바코드는 같은 날 둘 다 다시 붙일 수 있다")
    bad = C.post("/api/scan/subtype", json={"uid": uid, "barcode": codes[0], "subtype": "coat", "rename": True})
    ok(bad.status_code == 400, "같은 바코드는 하루 한 번")
    st = S.load_state(uid)
    rows = [x for x in (st.get("shelf") or []) + (st.get("stored") or []) if x.get("barcode") == S.GEN.normalize(codes[0])]
    ok(rows and all(x.get("subtype") == "small" for x in rows), "선반·창고 행 하위 종류가 small")
    it = S.item_from_row(rows[0])
    ok(it["subtype"] == "small", f"판정용 물건도 small(이름 {it['name']})")
    j = post("/api/scan", {"uid": uid, "barcode": codes[0]})
    ok(j["where"]["rename"] and j["where"]["rename"]["can_today"] is False, "다시 찍으면 이 바코드는 오늘 못 바꿈")
    next_day(uid)
    j = post("/api/scan", {"uid": uid, "barcode": codes[0]})
    ok(j["where"]["rename"]["can_today"] is True, "다음 날은 다시 됨")


def t_known_first():
    """② 라벨이 꺼진 날, 수첩에 아는 칸이 이 물건과 맞는 사람이 첫 칸."""
    uid = "dev_s29_known"
    to_play_day(uid, 4)
    st = S.load_state(uid)
    ok(not S.labels_shown(st), "4일째 라벨 꺼짐")
    hit = None
    for r in st["residents_list"]:
        for sl in S.notebook_slots(st, uid, r):
            if sl["kind"] != "like" or not isinstance(sl["rule"], dict):
                continue
            sub = sl["rule"].get("subtype")
            sub = sub[0] if isinstance(sub, list) else sub
            it = item(sl["rule"]["category"], sub, "아는 것", "k1")
            if S.resident_tier(st, uid, r, it)[0] == "like":
                hit = (r, sl, it)
                break
        if hit:
            break
    ok(hit, "좋아함 칸 하나 찾음")
    r, sl, it = hit
    S.nb_known(st, r["id"])[sl["key"]] = {"day": 1, "how": "test"}
    w = S.where_for(st, uid, it)
    ppl = [x for x in w["suggest"] if x["kind"] == "resident"]
    ok(ppl and ppl[0]["target"]["resident_id"] == r["id"] and ppl[0].get("first_reason") == "known" and ppl[0]["known"],
       f"첫 칸 = 아는 칸이 맞는 {r['name']} 님")
    S.cres(st, r["id"])["notebook"] = {}
    w2 = S.where_for(st, uid, it)
    ppl2 = [x for x in w2["suggest"] if x["kind"] == "resident"]
    ok(any(x["target"]["resident_id"] == r["id"] for x in ppl2) and not any(x.get("first_reason") for x in ppl2),
       "모르면 첫 칸 고정 없음, 맞는 사람은 줄에 있음")


def t_gossip_daily():
    """③ 가장 많이 받은 사람의 수첩이 다 차도, 빈칸 있는 사람이 있으면 저녁 귀띔이 나온다."""
    uid = "dev_s29_gossip"
    to_play_day(uid, 5)
    st = S.load_state(uid)
    top = max(st["residents_list"], key=lambda r: (len(S.cres(st, r["id"])["given"]), r["id"]))
    for sl in S.notebook_slots(st, uid, top):
        S.nb_known(st, top["id"])[sl["key"]] = {"day": 1, "how": "test"}
    S.now_hour = lambda: 19
    g = S.gossip_tick(st, uid, {"new": True})
    S.now_hour = lambda: 10
    ok(g and g.get("resident_id") != top["id"] and g["line"] and "{" not in g["line"], f"다른 사람 귀띔: {g and g['line']}")


def t_heirloom_second():
    """④ 후보가 하나면 가까운 사람 하나 더(건네면 돌려주지 않는다) · 오늘 들어온 사람은 후보 아님."""
    uid = "dev_s29_heir"
    to_play_day(uid, 3)
    st = S.load_state(uid)
    S.core_of(st)["flags"]["first_rare_day"] = 1
    S.core_of(st)["flags"]["heir_open_day"] = 1
    found = None
    for c, subs in S.SUBTYPE_KO.items():
        for s_ in subs:
            if not S.quick_ok(c, s_):
                continue
            it = item(c, s_, "귀한 것", f"h2-{c}-{s_}", "rare")
            tiers = {r["id"]: S.resident_tier(st, uid, r, it)[0] for r in st["residents_list"]}
            fit = [r for r in st["residents_list"] if tiers[r["id"]] != "not_for_me"]
            nfm = [r for r in st["residents_list"] if tiers[r["id"]] == "not_for_me"
                   and not ((S.twist_of(uid, r).get("dislike") or {}) and S.match({"category": S.twist_of(uid, r)["dislike"]["category"],
                                                                                 "subtype": S.twist_of(uid, r)["dislike"].get("subtype")}, it))]
            if fit and nfm:
                found = (it, fit[0], nfm)
                break
        if found:
            break
    ok(found, "맞는 사람 하나 + 안 맞는 사람이 있는 물건 찾음")
    it, keep, nfm = found
    for r in st["residents_list"]:                       # 나머지는 이미 전설 가보가 있어 후보가 아니게
        if r["id"] != keep["id"] and r["id"] not in {x["id"] for x in nfm}:
            r["heirloom"] = {"tier": "legendary", "name": "x", "barcode": "zz"}
    opts = S.heirloom_options(st, uid, it)
    sec = next(o for o in opts if o.get("second"))
    ok(len(opts) == 2 and sec["more_ko"] and sec["hint_ko"], f"두 번째 후보 {sec['name']} — {sec['more_ko']}")
    S.core_of(st)["scans"]["hs"] = {"item": it, "day": S.day_of(st), "given": False, "placed": "copy", "at": time.time(), "warm": []}
    S.save_state(uid, st)
    g = post("/api/give", {"uid": uid, "scan_id": "hs", "target": {"resident_id": sec["target"]["resident_id"], "heirloom": True}})
    ok(g.get("heirloom") and not g.get("heirloom_refused"), f"두 번째 후보에게 가보 놓임 ({g['tier']})")
    # 오늘 들어온 사람
    st = S.load_state(uid)
    newbie = S.make_resident("kid", __import__("random").Random(7), {r["name"] for r in st["residents_list"]}, uid)
    newbie["joined"] = time.time()
    S.ensure_stats(uid, newbie)
    st["residents_list"].append(newbie)
    for c, subs in S.SUBTYPE_KO.items():
        for s_ in subs:
            if S.quick_ok(c, s_):
                o = S.heirloom_options(st, uid, item(c, s_, "귀한 것", f"h3-{c}-{s_}", "rare"))
                if any(x["target"]["resident_id"] == newbie["id"] for x in o):
                    ok(False, f"오늘 들어온 아이가 후보에 있음 ({c}/{s_})")
                    return
    ok(True, "오늘 들어온 사람은 어떤 물건에도 가보 후보 아님")


def t_night_rotation():
    """⑤ 밤 손님: 이틀 연속 같은 손님 없음, 열흘에 셋 이상."""
    uid = "dev_s29_night"
    ark(uid)
    S.now_hour = lambda: 22
    seen = []
    for _ in range(10):
        st = S.load_state(uid)
        row = S.night_visitor_tick(st, uid)
        S.save_state(uid, st)
        seen.append(row["visitor_id"] if row else None)
        post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
    S.now_hour = lambda: 10
    ok(all(seen) and all(a != b for a, b in zip(seen, seen[1:])), f"연속 같은 손님 없음 {seen}")
    ok(len(set(seen)) >= 3 and len(S.NIGHT_VISITORS) >= 3, f"서로 다른 손님 {len(set(seen))}종 / 데이터 {len(S.NIGHT_VISITORS)}종")


def t_exp_return_once():
    """⑥ r6-3: 원정 귀환 소식은 한 세션만(화면이 seen 을 못 불러도 다음 세션엔 없음)."""
    uid = "dev_s29_exp"
    ark(uid)
    st = S.load_state(uid)
    st["exp_unseen"] = {"id": "exp-x", "line": "돌아왔다."}
    S.save_state(uid, st)
    a = ark(uid)
    ok(a["expedition_return"] and a["expedition_return"]["id"] == "exp-x", "이번 세션엔 보인다")
    ok(ark(uid)["expedition_return"], "같은 세션 안에선 그대로")
    post("/api/dev/advance", {"uid": uid, "minutes": 120})
    a = ark(uid)
    ok(a["expedition_return"] is None and S.load_state(uid).get("exp_unseen") is None, "다음 세션엔 없음")


def t_quick_defaults():
    """⑦ 기본 8 = 6차 로그에서 「기타」로 간 것 위주."""
    qp = S.quick_pick_for(None, "", ean("490123499101"))
    kos = [o["ko"] for o in qp["options"]]
    ok(len(kos) == 8 and {(o["category"], o["subtype"]) for o in qp["options"]} == set(S.QUICK_DEFAULTS) and "이야기책" not in kos, f"기본 8: {kos}")
    ok(all(o["prop"] for o in qp["options"]), "모두 그림 있음")


def t_raids_day3():
    """⑧ 3일째 습격 해금 + 첫 주 긴목 보장. 해금 방송은 /api/ark(아침), 긴목은 습격 카드(소리 단계) — 따로 온다."""
    uid = "dev_s29_raid"
    a = to_play_day(uid, 3)
    f = set(a["unlocked"]["features"])
    ok("raids" in f and "notebook" not in f and "mood_hints" not in f, f"3일째: 습격 열림, 수첩은 아직 {sorted(f)}")
    new = [n["feature"] for n in a["unlocked"]["new"]]
    ok("raids" in new, f"3일째 해금 방송 {new}")
    rt = get(f"/api/raid/today?uid={uid}")
    r = rt["raid"]
    ok(r and r["creature"]["id"] == "longneck" and r["stage"] == "sound" and not r["resolved"], f"3일째 첫 습격 = 긴목, 소리 단계 {r and r['creature']['id']}")
    a2 = ark(uid)
    ok(not a2["unlocked"]["new"], "해금 방송은 한 번(습격 카드와 같이 다시 나오지 않음)")
    a = next_day(uid)
    ok("notebook" in a["unlocked"]["features"] and not S.labels_shown(S.load_state(uid)), "4일째 기색·수첩")


TESTS = [t_rename_per_barcode, t_known_first, t_gossip_daily, t_heirloom_second, t_night_rotation, t_exp_return_once,
         t_quick_defaults, t_raids_day3]

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
