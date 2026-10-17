"""S27 서버 검증 — 5차 플레이테스트 원인 고침 + PM 첫 세션 큐.

① 기색: 지금 물건 칸 → 이 집에 있는 하위 종류 칸(home) → 역할×갈래 → 공통
② 「어디로」 줄 고정(필요·좋아함이 맞는 사람, 오늘 부탁한 사람 — 첫 칸 아님)
③ 라벨 4일째에 꺼짐 ④ 첫 매듭 1일째 · 낮 한 상 · 7일째 기억 벽(첫 칸 채움)
⑤ 가보: 돌려줄 사람 제외 · 새면 한 줄 · 후보마다 단서 ⑥ 이름 다시 붙이기(하루 한 번)
⑦ r5-1 놓친 이야기 · r5-3 떠날 때 겹침 · r5-4 개발 시계 판정 · r5-5 _alt · 선반 꽉 참 세션 1회
⑧ 「관리실이 대신 막을까요?」
큐: 첫 진입판 · 첫 비트는 첫 스캔 뒤 · 가보 3일째 · 간직 메모 · 한 번에 고르기(quick_pick)

실행:  python tests/test_s27.py
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

S.DB = Path(tempfile.mkdtemp()) / "t27.db"
S.DEV_MODE = True
S.CALENDAR_ENFORCE = True
S.VOTES_EXCLUDE_TEST = False
S.init_db()
C = TestClient(S.app)
S.LOW_KNOWN = 0                  # S31 아는 칸 적은 방주 첫 칸 규칙은 test_s31
S.NEW_STATE_SEED = "s27"         # 시작 주민 고정(흔들림 방지)
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


def next_day(uid, n=1):
    for _ in range(n):
        post("/api/dev/advance", {"uid": uid, "minutes": 60 * 24})
        a = ark(uid)
    return a


def item(cat, sub, name, code, rarity="common"):
    return {"name": name, "category": cat, "subtype": sub, "family": None, "rarity": rarity, "barcode": code, "card_id": f"c-{code}"}


def resident(st, role):
    return next((r for r in st["residents_list"] if r["role"] == role), None)


ALL_ITEMS = [(c, s_) for c, subs in S.SUBTYPE_KO.items() for s_ in subs if S.quick_ok(c, s_)]


# ─────────────────────────────────────────────────────────────
def t_alt_rule():
    """r5-5: line 만 line_alt, announce 는 announce_alt 없으면 그대로(입말을 되풀이하지 않는다)."""
    st = {"residents_list": [{"role": "cook"}]}
    b = {"line": "L", "announce": "A", "requires_role": "zz"}
    ok(S.role_text(b, "line", st) is None and S.role_text(b, "announce", st) == "A", "역할이 없으면 line 없음, announce 그대로")
    b2 = dict(b, line_alt="L2", announce_alt="A2")
    ok(S.role_text(b2, "line", st) == "L2" and S.role_text(b2, "announce", st) == "A2", "_alt 가 있으면 그것")
    ok(S.role_text(dict(b, requires_role="cook"), "line", st) == "L", "역할이 있으면 원래 줄")


def t_calendar_and_first_entry():
    """③④ + 큐①②: 1일째 첫 매듭, 라벨 1~3일째·4일째 꺼짐, 첫 진입판, 첫 비트는 첫 스캔 뒤, 가보 3일째부터."""
    uid = "dev_s27_cal"
    a = ark(uid)
    st = S.load_state(uid)
    ok(S.is_unlocked(st, "first_chain_knot") and S.labels_shown(st), "1일째: 첫 매듭 열림 + 라벨")
    ok(a["beat_today"] is None, "첫 진입: 아무것도 찍기 전에는 첫 비트(바깥 물건이 들어왔다) 없음")
    ov = a.get("overnight")
    ok(ov is None or (ov.get("first_entry") and ov["title"] != (S.moment("morning.title") or "자리 비우신 사이")),
       f"첫 진입판: {ov and ov.get('title')}")
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
    ok(j.get("beat_today") and j["beat_today"].get("new"), f"첫 스캔 뒤 첫 비트 {j.get('beat_today') and j['beat_today'].get('id')}")
    a = ark(uid)
    ok(not (a["beat_today"] or {}).get("new"), "같은 비트를 두 번 열지 않는다")
    st = S.load_state(uid)
    S.core_of(st)["flags"]["first_rare_day"] = 1
    S.save_state(uid, st)
    ok(not S.is_unlocked(S.load_state(uid), "heirloom"), "1일째 귀함이 있어도 가보 칸 닫힘")
    kn = S.keep_note_tick(S.load_state(uid), {"barcode": "k1", "name": "귀한 것", "rarity": "rare"})
    ok(kn and kn["ko"] and "{" not in kn["ko"], f"간직 메모: {kn and kn['ko']}")
    a = next_day(uid, 2)
    st = S.load_state(uid)
    ok(not S.is_unlocked(st, "heirloom"), "S30: 3일째라도 그날 귀함 카드 전에는 닫힘")
    S.heir_open_tick(st, {"rarity": "rare"})
    ok(S.labels_shown(st) and S.is_unlocked(st, "heirloom"), "3일째: 라벨 그대로, 귀함 카드와 함께 가보 칸 열림")
    ok(S.keep_note_tick(st, {"barcode": "k2", "name": "x", "rarity": "rare"}) is None, "열린 뒤엔 간직 메모 없음")
    a = next_day(uid)
    st = S.load_state(uid)
    ok(not S.labels_shown(st) and "notebook" in a["unlocked"]["features"], "4일째: 기색·수첩")


def to_play_day(uid, d):
    a = ark(uid)
    while a["unlocked"]["play_day"] < d:
        a = next_day(uid)
    return a


def t_hint_home():
    """① 기색은 이 집에 있는 하위 종류 칸을 먼저 가리킨다(지금 물건 칸이 있으면 그것이 먼저)."""
    uid = "dev_s27_hint"
    to_play_day(uid, 4)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    likes = [x for x in S.likes_of(uid, cook) if isinstance(x, dict) and S.item_rule_safe(x)]
    signs = S.role_taste("cook").get("signs") or {}
    k = next((i for i, x in enumerate(S.likes_of(uid, cook)) if x in likes and i < len(signs.get("likes") or [])), None)
    ok(k is not None, "요리사 좋아함 칸 + 기색 줄 있음")
    rl = S.likes_of(uid, cook)[k]
    sub = rl.get("subtype")
    sub = sub[0] if isinstance(sub, list) else sub
    S.core_of(st)["seen_subtypes"] = {rl["category"]: [sub] if sub else ["x"]}
    other = next((c, s_) for c, s_ in ALL_ITEMS if S.resident_tier(st, uid, cook, item(c, s_, "딴것", "o1"))[0] in ("warm", "not_for_me"))
    it = item(other[0], other[1], "딴것", "o1")
    cands = S.sign_candidates(st, cook, it, None, uid)
    home = [t for t, src in cands if src == "home"]
    ok(home, f"집에 있는 칸 기색 후보 {len(home)}줄")
    h = S.sign_hint(st, uid, cook, it, "warm", None, set())
    ok(any(S.fill_text(t, st, cook, it) == h for t in home), f"기색이 집에 있는 칸을 가리킴: {h}")
    S.core_of(st)["seen_subtypes"] = {}
    st["shelf"], st["stored"] = [], []
    ok(not [t for t, src in S.sign_candidates(st, cook, it, None, uid) if src == "home"], "집에 없으면 home 후보 없음")


def t_pin_rows():
    """② 필요·좋아함이 맞는 사람과 오늘 부탁한 사람은 줄에서 빠지지 않는다(첫 칸 아님)."""
    uid = "dev_s27_pin"
    to_play_day(uid, 4)
    st = S.load_state(uid)
    hits = 0
    for c, s_ in ALL_ITEMS:
        it = item(c, s_, "물건", f"p-{c}-{s_}")
        fit = [r["id"] for r in st["residents_list"] if S.resident_tier(st, uid, r, it)[0] in ("need", "like", "memory", "chain_beat")]
        w = S.where_for(st, uid, it)
        ppl = [x for x in w["suggest"] if x["kind"] == "resident"]
        ids = [x["target"]["resident_id"] for x in ppl]
        if fit:
            hits += 1
            ok(all(f in ids for f in fit[:3]), f"{c}/{s_}: 맞는 사람 {len(fit)}명 모두 줄에")
            if len(ppl) > 1 and not all(x.get("pinned") for x in ppl):
                ok(not ppl[0].get("pinned"), f"{c}/{s_}: 고정한 사람은 첫 칸이 아님")
        ak = S.asked_today(st, uid)
        if ak:
            ok(ak["id"] in ids, f"{c}/{s_}: 오늘 부탁한 {ak['name']} 님이 줄에")
        if hits >= 4:
            break


def t_heirloom():
    """⑤ 돌려줄 사람에게는 「가보로」 없음, 새면 결과 한 줄, 후보마다 단서 한 줄."""
    uid = "dev_s27_heir"
    to_play_day(uid, 3)
    st = S.load_state(uid)
    S.core_of(st)["flags"]["first_rare_day"] = 1
    S.core_of(st)["flags"]["heir_open_day"] = 1
    S.save_state(uid, st)
    st = S.load_state(uid)
    for c, s_ in ALL_ITEMS:
        it = item(c, s_, "귀한 것", f"h-{c}-{s_}", "rare")
        nfm = [r for r in st["residents_list"] if S.resident_tier(st, uid, r, it)[0] == "not_for_me"]
        if nfm and len(nfm) < len(st["residents_list"]):
            break
    opts = S.heirloom_options(st, uid, it)
    ids = {o["target"]["resident_id"] for o in opts if not o.get("near")}
    sec = {o["target"]["resident_id"] for o in opts if o.get("near")}
    ok(nfm and not ids & {r["id"] for r in nfm}, f"돌려줄 사람 {len(nfm)}명은 가보 후보 아님(후보 {len(opts)}, 「다른 분도」 {len(sec)})")
    nfm = [r for r in nfm if r["id"] not in sec]
    ok(opts and all(o.get("hint_ko") and "{" not in o["hint_ko"] for o in opts), f"후보 단서: {opts and opts[0]['hint_ko']}")
    S.core_of(st)["scans"]["hx"] = {"item": it, "day": S.day_of(st), "given": False, "placed": "copy", "at": time.time(), "warm": []}
    S.save_state(uid, st)
    g = post("/api/give", {"uid": uid, "scan_id": "hx", "target": {"resident_id": nfm[0]["id"], "heirloom": True}})
    st = S.load_state(uid)
    ok(g.get("heirloom_refused") and g.get("heirloom") is None and not next(r for r in st["residents_list"] if r["id"] == nfm[0]["id"]).get("heirloom"),
       f"새도 가보 안 됨, 결과 한 줄: {g['reaction'].get('announce')}")


def t_rename():
    """⑥ 이름 다시 붙이기: 하루 한 번, 이미 정한 바코드만."""
    uid = "dev_s27_ren"
    ark(uid)
    code = ean("490123488001")
    j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
    sp = j["where"].get("subtype_pick")
    ok(sp, "하위 종류 물음")
    post("/api/scan/subtype", {"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": "water"})
    r = C.post("/api/scan/subtype", json={"uid": uid, "scan_id": j["where"]["scan_id"], "subtype": "milk"})
    ok(r.status_code == 400, "rename 없이는 못 바꾼다")
    r = post("/api/scan/subtype", {"uid": uid, "barcode": code, "subtype": "milk", "rename": True})
    ok(r["ok"] and r["subtype"] == "milk" and r["renamed_from"] and r["done_ko"], f"다시 붙임: {r['done_ko']}")
    ok(r["first_meet"]["line_ko"] in (S.moments()["subtype_first"]["drink"]["milk"]) and r["first_meet"]["replaces"] == "category",
       f"고른 하위 종류에 맞춘 첫 만남 줄: {r['first_meet']['line_ko']}")
    st = S.load_state(uid)
    ok(st["barcodes"][S.GEN.normalize(code)]["subtype"] == "milk", "이 방주 기록이 바뀜")
    r = C.post("/api/scan/subtype", json={"uid": uid, "barcode": code, "subtype": "tea", "rename": True})
    ok(r.status_code == 400, "하루 한 번")
    j2 = post("/api/scan", {"uid": uid, "barcode": code})
    rn = j2["where"].get("rename")
    ok(rn and rn["current"]["id"] == "milk" and any(o["current"] for o in rn["options"]) and rn["can_today"] is False and rn["label_ko"],
       f"다시 찍으면 where.rename(선택지 {len(rn['options']) if rn else 0}, 오늘 가능 {rn and rn['can_today']})")
    with S.db() as con:
        v = con.execute("SELECT subtype FROM subtype_votes WHERE uid=? AND barcode=?", (uid, S.GEN.normalize(code))).fetchone()
    ok(v and v["subtype"] == "milk", "전역 표도 새 이름(한 표)")


def t_missed_and_leaving():
    """r5-1 오늘 이미 푼 사람에게 놓친 이야기 없음 · r5-3 떠날 때 겹침 없음."""
    uid = "dev_s27_miss"
    ark(uid)
    st = S.load_state(uid)
    cook = resident(st, "cook")
    ok(not S.solved_today(st, cook["id"]), "처음엔 안 풂")
    S.cres(st, cook["id"])["memory_day"] = S.day_of(st)
    ok(S.solved_today(st, cook["id"]), "기억을 연 날 = 푼 날")
    S.core_of(st)["scans"]["m1"] = {"item": item("food", "noodle", "면", "m1"), "day": S.day_of(st), "given": True,
                                    "to": {"room": 1}, "chain": [{"rid": cook["id"], "tier": "memory"}], "at": time.time()}
    ok(S.missed_chain_of(st, uid) is None, "오늘 푼 사람에게 「놓친 이야기」 없음")
    lv = get(f"/api/leaving?uid={uid}")
    ok(not (lv["next_visit"]["kind"] == "need_tomorrow" and lv["tomorrow_ask"]), "필요 약속과 내일의 부탁이 둘 다 나오지 않는다")
    ok(lv["order"] and lv["order"][0] == "next_visit", f"보여 줄 순서 {lv['order']}")
    if lv["next_visit"]["kind"] == "tomorrow_ask":
        ok(lv["tomorrow_ask"] is None and lv["next_visit"]["line"], f"합침: {lv['next_visit']['line']}")
    a = ark(uid)
    ok("leave_order" in a and not (a["next_visit"]["kind"] in ("need_tomorrow", "nothing") and a["tomorrow_ask"]), "/api/ark 도 같은 규칙")


def t_dev_clock_judge():
    """r5-4: 개발 시계가 있으면 실제 시계 마감을 보지 않는다."""
    uid = "dev_s27_clock"
    to_play_day(uid, 4)
    get(f"/api/raid/today?uid={uid}&debug_raid=longneck")
    st = S.load_state(uid)
    st["raid"]["started"] = time.time() - 86400 * 3        # 실제 시계로는 마감이 지났다
    st["dev_clock_hour"] = 10
    S.save_state(uid, st)
    S.now_hour = S._now_hour_impl
    a = ark(uid)
    st = S.load_state(uid)
    ok(not st["raid"].get("resolved"), "개발 시계 10시: 실제 마감이 지나도 판정 안 함")
    post("/api/dev/clock", {"uid": uid, "hour": 22})
    a = ark(uid)
    st = S.load_state(uid)
    ok(st["raid"].get("resolved") and st["raid"].get("auto"), f"개발 시계 22시: 판정 {st['raid'].get('result')}")
    post("/api/dev/clock", {"uid": uid, "hour": None})
    S.now_hour = lambda: 10


def t_shelf_full_once():
    """선반이 꽉 찼다는 물음은 세션에 한 번."""
    uid = "dev_s27_shelf"
    ark(uid)
    keep = S.shelf_place
    S.shelf_place = lambda st, card: None
    try:
        j1 = post("/api/scan", {"uid": uid, "barcode": ean("880104301509")})
        j2 = post("/api/scan", {"uid": uid, "barcode": ean("880104301516")})
    finally:
        S.shelf_place = keep
    ok(j1["swap_offer"] and j1["swap_offer"]["ko"], "첫 번째는 묻는다")
    ok(j2["swap_offer"] is None and j2["stored"] and j2["stored"].get("quiet_ko"), f"두 번째는 조용히 창고: {j2['stored'] and j2['stored'].get('quiet_ko')}")


def t_daytime_table():
    """④ 낮 한 상: 6일째 낮 세션에도 하루 한 번."""
    uid = "dev_s27_table"
    to_play_day(uid, 6)
    a = ark(uid)
    et = a["evening_table"]
    ok(et and et["open"] and et["daytime"] and et["open_ko"] and et["table_prompt"], f"낮 상: {et and et['open_ko']}")
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301523")})
    st = S.load_state(uid)
    st["resources"]["food"] = 30
    S.save_state(uid, st)
    ppl = [r["id"] for r in st["residents_list"]][:2]
    r = post("/api/table", {"uid": uid, "relic_id": j["card"]["id"], "seats": [ppl]})
    ok(r["daytime"] and r["talk"] and r["promise"] and all("{" not in x["line"] for x in r["talk"]), f"낮 상 대화 {[x['line'] for x in r['talk']]} / {r['promise']}")
    S.now_hour = lambda: 19
    ok(ark(uid)["evening_table"]["done"], "저녁에는 이미 차림(하루 한 상)")
    S.now_hour = lambda: 10


def t_memory_wall():
    """④ 7일째 기억 벽: 식량창고 4칸, 첫 칸은 처음 건넨 물건으로 채워 연다. 빈 고리에 걸 수 있다."""
    uid = "dev_s27_wall"
    ark(uid)
    j = post("/api/scan", {"uid": uid, "barcode": ean("880104301530")})
    st = S.load_state(uid)
    cook = resident(st, "cook")
    post("/api/give", {"uid": uid, "scan_id": j["where"]["scan_id"], "target": {"resident_id": cook["id"]}})
    a = ark(uid)
    ok(a["memory_wall"] is None, "1일째 벽 없음")
    a = to_play_day(uid, 7)
    mw = a["memory_wall"]
    ok(mw and mw["room"] == "pantry" and len(mw["slots"]) == 4 and mw["slots"][0] and mw["filled"] == 1,
       f"7일째 벽: 첫 칸 {mw and mw['slots'][0] and mw['slots'][0]['name']} ({mw and mw['slots'][0] and mw['slots'][0]['from']})")
    j2 = post("/api/scan", {"uid": uid, "barcode": ean("880104301547")})
    h = post("/api/memory_wall/hang", {"uid": uid, "relic_id": j2["card"]["id"]})
    ok(h["memory_wall"]["filled"] == 2, "빈 고리에 걸기")
    ok(h["line"] and "{" not in h["line"] and "2/4" in h["line"], f"걸기 한 줄(memory_wall.hung): {h['line']}")
    for i, k in enumerate(("880104301554", "880104301561")):
        jj = post("/api/scan", {"uid": uid, "barcode": ean(k)})
        h = post("/api/memory_wall/hang", {"uid": uid, "relic_id": jj["card"]["id"]})
    ok(h["complete"] and h["story"] and h["complete_ko"] and "{" not in h["complete_ko"], f"다 차면 완성 방송 + 뒷이야기 {len(h['story'] or [])}줄")
    ok(mw.get("prefilled_ko") and "{" not in mw["prefilled_ko"], f"미리 찬 칸 설명: {mw.get('prefilled_ko')}")
    ok(mw.get("open_ko") and "{" not in mw["open_ko"] and ark(uid)["memory_wall"]["open_ko"] is None, f"처음 열릴 때 방송은 한 번: {mw.get('open_ko')}")


def t_office():
    """⑧ 낮 세션 습격: 관리실이 대신 막는다(가장 나은 배치, 끝나면 원래대로, 방은 잃지 않는다)."""
    uid = "dev_s27_office"
    to_play_day(uid, 4)
    rt = get(f"/api/raid/today?uid={uid}&debug_raid=longneck")
    ok(rt["raid"] and rt["raid"]["office"] and rt["raid"]["office"]["ask"], f"관리실 단추: {rt['raid'] and rt['raid']['office'] and rt['raid']['office']['ask']}")
    st = S.load_state(uid)
    before = dict(st.get("stations") or {})
    o = post("/api/raid/auto_defend", {"uid": uid})
    st = S.load_state(uid)
    ok(o["result"] in ("held", "passed", "scarred") and o["office"]["line"] and "{" not in o["office"]["line"],
       f"관리실 결과 {o['result']}: {o['office']['line']}")
    ok(dict(st.get("stations") or {}) == before, "배치는 원래대로")
    ok(o["raid"]["office"] is None, "끝난 습격엔 단추 없음")
    r = C.post("/api/raid/auto_defend", json={"uid": uid})
    ok(r.status_code == 400, "두 번은 안 됨")
    uid2 = "dev_s27_office2"
    to_play_day(uid2, 4)
    get(f"/api/raid/today?uid={uid2}&debug_raid=longneck")
    S.now_hour = lambda: 20
    ok(C.post("/api/raid/auto_defend", json={"uid": uid2}).status_code == 400, "저녁에는 직접")
    S.now_hour = lambda: 10


def t_quick_pick():
    """큐 ③ 한 번에 고르기: 8 + 기타, 개인화 없음(기본 순서), 고르면 갈래·하위 종류가 한 번에 정해진다."""
    uid = "dev_s27_qp"
    ark(uid)
    code = ean("490123499001")
    pk = get(f"/api/peek?barcode={code}&uid={uid}")
    qp = pk["quick_pick"]
    ok(pk["needs_category"] and qp and len(qp["options"]) == 8 and qp["other"] and qp["prompt_ko"], f"8 + 기타: {[o['ko'] for o in qp['options']]}")
    ok([o["ko"] for o in qp["options"]] == ["면", "과자", "물", "우유", "옷", "건전지", "이야기책", "씻는 것"] or any(o["src"] != "default" for o in qp["options"]),
       "표가 없으면 기본 순서")
    ok(all(o["prop"] for o in qp["options"]), "모두 그림 있음")
    ok(not any(o["category"] == "tobacco" or o["subtype"] == "alcohol" for o in qp["options"]), "안전 목록 밖 없음")
    j = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink", "user_subtype": "milk"})
    ok(j["card"]["category"] == "drink" and j["card"]["subtype"] == "milk" and not j["where"].get("subtype_pick"), "한 번에 정해짐(하위 종류 물음 없음)")
    fm = [m for m in j["first_meet"] if m["kind"] in ("category", "subtype")]
    ok(fm and fm[0]["kind"] == "subtype" and fm[0]["line_ko"] in S.moments()["subtype_first"]["drink"]["milk"], f"첫 만남 줄이 고른 것에 맞춤: {fm and fm[0]['line_ko']}")
    st = S.load_state(uid)
    ok(st["barcodes"][S.GEN.normalize(code)]["subtype"] == "milk" and "milk" in S.core_of(st)["seen_subtypes"].get("drink", []), "방주 기록")
    pk2 = get(f"/api/peek?barcode={ean('490123499002')}&uid={uid}")
    ok(pk2["quick_pick"]["options"][0]["src"] == "ark" and pk2["quick_pick"]["options"][0]["subtype"] == "milk", "이 방주가 고른 것이 앞")
    r = C.post("/api/scan", json={"uid": uid, "barcode": ean("490123499003"), "user_category": "drink", "user_subtype": "alcohol"})
    ok(r.status_code == 400, "안전 목록 밖은 거절")


TESTS = [t_alt_rule, t_calendar_and_first_entry, t_hint_home, t_pin_rows, t_heirloom, t_rename, t_missed_and_leaving,
         t_dev_clock_judge, t_shelf_full_once, t_daytime_table, t_memory_wall, t_office, t_quick_pick]

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
