"""S13-A 서버 검증 — 이해관계·수집 (docs/API_S13.md).

실행:  python tests/test_s13_server.py
  - 임시 DB 에서 FastAPI TestClient 로 돈다(실제 relic_ark.db 를 건드리지 않는다).
  - 날짜를 넘기는 대목은 방주의 created 를 하루씩 뒤로 미는 방식으로 흉내 낸다(day_of 가 created 기준).
  - 수치는 전부 data/balance/stakes.json 에서 읽어 비교한다(테스트에 숫자를 박지 않는다).
"""
from __future__ import annotations

import json
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

TMP = Path(tempfile.mkdtemp()) / "t13.db"
S.DB = TMP
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


def shift_day(uid: str, n: int = 1):
    st = S.load_state(uid)
    st["created"] -= 86400 * n
    S.save_state(uid, st)


def scan(uid, code, cat=None):
    r = C.post("/api/scan", json={"uid": uid, "barcode": code, "user_category": cat})
    assert r.status_code == 200, r.text
    return r.json()


def ark(uid, **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    r = C.get(f"/api/ark?uid={uid}" + ("&" + qs if qs else ""))
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────
def t_polish_and_dup_fix():
    uid = "dev_s13_polish"
    ark(uid)
    code = ean("880104301509")
    a = scan(uid, code)
    ok(a["shelf_new"] and a["shelf_slot"] is not None, f"첫 스캔 → 선반 새 칸 {a['shelf_slot']}")
    b = scan(uid, code)
    st = S.load_state(uid)
    ok(b["shelf_slot"] == a["shelf_slot"] and not b["shelf_new"] and len(st["shelf"]) == 1,
       f"같은 날 재스캔(감쇠 {b['rescan_multiplier']}) → 같은 칸, 선반 {len(st['shelf'])}칸 (중복 칸 버그 수정)")
    ok(b["polish"] and not b["polish"]["counted_today"] and b["polish"]["level"] == 1, "놓인 날 재스캔은 닦기에 세지 않는다")
    spl = S.stk("polish.scans_per_level")
    mx = int(S.stk("polish.max_level"))
    levels = []
    for i in range(sum(spl) + 1):
        shift_day(uid)
        p = scan(uid, code)["polish"]
        levels.append(p["level"])
        again = scan(uid, code)["polish"]
        if again["counted_today"]:
            ok(False, "하루 두 번째 재스캔이 세졌다")
    exp2, exp3 = spl[0], spl[0] + spl[1]
    ok(levels[exp2 - 1] == 2 and levels[exp2 - 2] == 1, f"다른 날 {exp2}번 → Lv2 (levels={levels})")
    ok(levels[exp3 - 1] == 3 and levels[exp3 - 2] == 2, f"다른 날 {exp3}번 → Lv3")
    ok(levels[-1] == mx, f"최대 {mx} 에서 멈춤")
    st = S.load_state(uid)
    ok(len(st["shelf"]) == 1, f"재스캔 {len(levels) * 2 + 2}번 뒤에도 선반 1칸")
    last = scan(uid, code)
    ok("더 닦을 데가" in (last["polish"]["ko"] or ""), "최대 레벨 재스캔 문장 = shelf.rescan_max")
    sh = ark(uid)["shelf"][0]
    ok(sh["polish"] == mx and sh["barcode"] == code and sh["polish_label"], f"/api/ark shelf 에 polish={sh['polish']} label={sh['polish_label']}")


def t_migration_old_save():
    uid = "dev_s13_mig"
    st = S.new_state(uid)
    code = ean("880104301510")
    st["shelf"] = [
        {"slot": 0, "prop_id": "food_a", "name": "x", "category": "food", "rarity": "common", "family": None,
         "scanned_at": 1, "card_id": f"{code}-111"},
        {"slot": 1, "prop_id": "food_b", "name": "x", "category": "food", "rarity": "common", "family": None,
         "scanned_at": 2, "card_id": f"{code}-222"},
        {"slot": 2, "prop_id": "food_c", "name": "y", "category": "food", "rarity": "common", "family": None,
         "scanned_at": 3, "card_id": "made-heal-1"},
    ]
    st["rooms"][0]["cracked"] = True
    for k in ("barcodes", "seen_categories", "seen_families", "family_sets", "wishes_done", "day_log", "codex_meta"):
        st.pop(k, None)
    S.save_state(uid, st)
    with S.db() as con:
        con.execute("INSERT INTO scans(uid,barcode,category,rarity,mult,ts,day) VALUES(?,?,?,?,?,?,?)",
                    (uid, ean("490123456789"), "drink", "common", 1.0, time.time(), 1))
    st2 = S.load_state(uid)
    bcs = [it.get("barcode") for it in st2["shelf"]]
    ok(len(st2["shelf"]) == 2 and bcs[0] == code, f"옛 중복 칸 정리: 3칸 → {len(st2['shelf'])}칸, 바코드 복원 {bcs}")
    ok(st2["barcodes"].get(ean("490123456789"), {}).get("category") == "drink", "scans 표에서 카테고리 고정 복원")
    a = ark(uid)
    ok(a["production"].get("2", {}).get("cracked") is True, "옛 cracked 플래그가 이제 실제로 금 간 방")
    r = C.get(f"/api/codex?uid={uid}")
    ok(r.status_code == 200, "구버전 방주 도감 OK(codex_meta 재생성)")


def t_category_lock_and_peek():
    uid = "dev_s13_lock"
    ark(uid)
    code = ean("490123456789")          # 모르는 가문
    pk = C.get(f"/api/peek?barcode={code}&uid={uid}").json()
    ok(pk["needs_category"] and pk["locked_category"] is None, "처음에는 카테고리를 묻는다")
    a = scan(uid, code, "food")
    b = scan(uid, code, "drink")
    c = scan(uid, code, "electronics")
    ok(a["card"]["category"] == b["card"]["category"] == c["card"]["category"] == "food"
       and a["card"]["name"] == c["card"]["name"], f"고른 카테고리 무시, 같은 유물: {a['card']['name']}")
    ok(b["category_locked"] == "food", "응답에 category_locked")
    pk = C.get(f"/api/peek?barcode={code}&uid={uid}").json()
    ok(pk["locked_category"] == "food" and not pk["needs_category"], "peek(uid) → 고정 카테고리, 묻지 않는다")
    pk0 = C.get(f"/api/peek?barcode={code}").json()
    ok(pk0["needs_category"] and pk0["locked_category"] is None, "uid 없는 peek 은 예전과 같다")
    code2 = ean("490123456790")
    u = scan(uid, code2)                 # 고르지 않음 → 정체불명, 고정하지 않는다
    v = scan(uid, code2, "book" if False else "apparel")
    ok(u["card"]["category"] == "unknown" and v["card"]["category"] == "apparel", "정체불명은 고정하지 않는다(다음에 고를 수 있다)")


def t_variant():
    week = S.iso_week()
    rate = float(S.stk("variant.rate"))
    shiny = plain = None
    n = 0
    for i in range(4000):
        code = ean(f"4901234{i:05d}")
        v = S.sea_variant(code)
        n += v["shiny"]
        if v["shiny"] and not shiny:
            shiny = code
        if not v["shiny"] and not plain:
            plain = code
    ok(abs(n / 4000 - rate) < rate * 0.5, f"바다 무늬 비율 {n}/4000 = {n / 4000:.4f} (목표 {rate})")
    ok(S.sea_variant(shiny) == S.sea_variant(shiny), "같은 주·같은 바코드 = 같은 결과(결정적)")
    nxt = S.sea_variant(shiny, time.time() + 7 * 86400)
    ok(nxt["week"] != week, f"주가 바뀌면 시드가 바뀐다 ({week} → {nxt['week']})")
    uid = "dev_s13_var"
    ark(uid)
    a = scan(uid, shiny, "food")
    ok(a["variant"]["shiny"] and a["variant"]["id"] == "sea" and a["card"]["sea_variant"] and a["variant"].get("ko"),
       f"스캔 응답 variant={a['variant']['id']} week={a['variant']['week']}")
    ok(ark(uid)["shelf"][0]["variant"] == "sea", "선반 물건에 variant=sea")
    b = scan(uid, plain, "food")
    ok(b["variant"]["id"] is None, "평범한 것은 variant id=None")
    cx = C.get(f"/api/codex?uid={uid}").json()
    seen = [e for c in cx for e in c["entries"] if e.get("variant_seen")]
    ok(len(seen) == 1, "도감 줄기에 변형 칸 기록")


def t_family_set_and_first_meet():
    uid = "dev_s13_fam"
    st0 = ark(uid)
    mor0 = st0["resources"]["morale"]
    total = int(S.stk("family_sets.pieces_required"))
    reward = S.stk("family_sets.reward")
    outs = [scan(uid, ean(f"88010430{i:04d}")) for i in range(total + 1)]
    fm = outs[0]["first_meet"]
    ok([x["kind"] for x in fm] == ["family", "category"], f"첫 만남: 가문 줄 먼저, 카테고리 줄 뒤 {[x['kind'] for x in fm]}")
    ok(outs[1]["first_meet"] == [], "두 번째부터 첫 만남 없음")
    ok(outs[0]["family_set"]["total"] == total and outs[0]["family_set"]["have"] == 1, f"세트 진행 1/{total}")
    ok("{" not in (outs[0]["family_set"]["ko"] or "{"), f"진행 문장 치환: {outs[0]['family_set']['ko']}")
    done = outs[total - 1]["family_set"]
    ok(done["just_completed"] and done["reward"]["story"] and done["reward"]["decor"], f"{total}번째에서 완성 + 이야기·장식")
    ok(done["ko"] == S.moment("family_set.complete.8801043"), "완성 문장 = family_set.complete.<code>")
    after = outs[total]["family_set"]
    ok(after["completed"] and not after["just_completed"], "완성 뒤에는 다시 보상하지 않는다")
    a = ark(uid)
    # 사기는 스캔 산출(식품 → morale)도 있으므로 세트 보상분이 들어갔는지만 본다
    gained_m = sum(o["gained"].get("morale", 0) for o in outs)
    ok(a["resources"]["morale"] == mor0 + gained_m + int(reward["morale"]), f"사기 +{reward['morale']} (세트 보상)")
    ok(a["families_done"] == ["8801043"] and a["decor"], f"/api/ark decor={a['decor']}")
    col = C.get(f"/api/collection?uid={uid}").json()
    f1 = next(f for f in col["families"] if f["code"] == "8801043")
    f2 = next(f for f in col["families"] if f["code"] == "8801062")
    ok(f1["known"] and f1["completed"] and f1["story"], "collection: 완성 가문은 이야기가 열린다")
    ok(not f2["known"] and f2["name"] is None and f2["silhouette"], "collection: 모르는 가문은 실루엣")
    ok(len(col["families"]) == 18 and col["families_done"] == 1, "가문 18칸")


def t_staffing_and_crack():
    uid = "dev_s13_staff"
    ark(uid)
    st = S.load_state(uid)
    sm = S.stk("staffing.staff_mult")
    cm = float(S.stk("crack.prod_mult"))

    def run(st_):
        s2 = json.loads(json.dumps(st_))
        s2["last_tick"] = time.time() - S.PRODUCTION_TICK_SEC * S.MAX_OFFLINE_TICKS - 5
        res0 = dict(s2["resources"])
        S.tick_production(s2)
        return {k: s2["resources"][k] - res0.get(k, 0) for k in s2["resources"] if s2["resources"][k] != res0.get(k, 0)}

    bonus = S.role_effects(st)["room_bonus"].get("pantry", {})      # 역할 보정(요리사)도 같은 배율을 받는다
    base = {k: v + bonus.get(k, 0) for k, v in S.room_produces(S.room_at(st, 2)).items() if isinstance(v, (int, float))}
    p0 = run(st)
    rid = st["residents_list"][0]["id"]
    st["stations"] = {rid: 2}
    p1 = run(st)
    st["stations"] = {r["id"]: 2 for r in st["residents_list"]}
    p3 = run(st)
    print("     base", base, "| 0명", p0, "| 1명", p1, "| 3명", p3)
    k = next(iter(base))
    exp = lambda n: int(round(base[k] * S.MAX_OFFLINE_TICKS * sm[min(n, len(sm) - 1)]))
    ok(p0.get(k, 0) == exp(0) and p1.get(k, 0) == exp(1) and p3.get(k, 0) == exp(3),
       f"식량창고 {k}: 0명 {p0.get(k, 0)} / 1명 {p1.get(k, 0)} / 3명 {p3.get(k, 0)} = staff_mult {sm[0]}/{sm[1]}/{sm[3]}")
    st["stations"] = {rid: 2}
    st["rooms"][0]["cracked"] = True
    pc = run(st)
    ok(pc.get(k, 0) == int(round(base[k] * S.MAX_OFFLINE_TICKS * sm[1] * cm)), f"금 간 방 {k}: {pc.get(k, 0)} (×{cm})")
    # API 로: 배치하면 미리보기 배율이 바뀐다
    S.save_state(uid, S.load_state(uid))
    a = ark(uid)
    ok(a["production"]["2"]["staff"] == 0 and a["production"]["2"]["mult"] == sm[0] and a["production"]["2"]["label"],
       f"/api/ark production: 0명 mult={a['production']['2']['mult']} label={a['production']['2']['label']}")
    r = C.post("/api/ark/station", json={"uid": uid, "resident_id": rid, "slot": 2}).json()
    ok(r["production"]["2"]["mult"] == sm[1] and "label" not in r["production"]["2"], f"배치 1명 → mult={r['production']['2']['mult']}")


def t_repair():
    uid = "dev_s13_repair"
    ark(uid)
    st = S.load_state(uid)
    st["rooms"][0]["cracked"] = True
    cost = S.stk("crack.repair_cost")
    for k in cost:
        st["resources"][k] = 0
    S.save_state(uid, st)
    r = C.post("/api/ark/repair", json={"uid": uid, "slot": 2})
    ok(r.status_code == 400 and "모자랍니다" in r.json()["detail"], f"재료 없으면 400: {r.json()['detail']}")
    st = S.load_state(uid)
    for k, v in cost.items():
        st["resources"][k] = v
    S.save_state(uid, st)
    r = C.post("/api/ark/repair", json={"uid": uid, "slot": 2})
    j = r.json()
    ok(r.status_code == 200 and j["paid"] == cost and all(j["state"]["resources"][k] == 0 for k in cost)
       and not S.room_at(S.load_state(uid), 2).get("cracked"), f"수리 → 재료 {cost} 지불, 금 지움. {j['ko']}")
    r = C.post("/api/ark/repair", json={"uid": uid, "slot": 2})
    ok(r.status_code == 400, "금 없는 방 수리 → 400")
    st = S.load_state(uid)
    st["rooms"][0]["cracked"] = True
    st["tools"] = {"patch": 1}
    S.save_state(uid, st)
    j = C.post("/api/ark/repair", json={"uid": uid, "slot": 2, "use_patch": True}).json()
    ok(j["used_patch"] and j["state"]["combat"]["workshop"]["tools"] is not None
       and S.load_state(uid)["tools"]["patch"] == 0, "봉합 패치로 대신 수리")
    ok(C.post("/api/ark/repair", json={"uid": uid, "slot": 9}).status_code == 400, "방 없는 칸 → 400")


def _raid(uid, cre, grade=None, reset=True):
    q = f"/api/raid/today?uid={uid}&debug_raid={cre}" + ("&debug_reset=1" if reset else "")
    if grade:
        q += f"&debug_grade={grade}"
    r = C.get(q)
    assert r.status_code == 200, r.text
    return r.json()


def t_night_judge():
    uid = "dev_s13_night"
    ark(uid)
    # 상실이 나올 판: 등급 4, 빈 방, 큰 입
    rj = _raid(uid, "big_maw", grade=4)
    adv = C.post("/api/raid/advance", json={"uid": uid}).json()        # 실루엣 — 미리보기를 본다
    would = adv["raid"]["ready"]["would"]
    a = ark(uid, debug_night=1)
    rep = a["night_judge"]["report"]
    worst = S.stk("night_judge.worst_result")
    cap = worst if worst in S._RESULT_RANK else None
    exp = would if (cap is None or S._RESULT_RANK[would] <= S._RESULT_RANK[cap]) else cap
    ok(rep is not None and rep["result"] == exp and rep["capped"] == (exp != would),
       f"밤 판정 = 누른 것과 같은 규칙(상한 {cap}): 미리보기 {would} → 결과 {rep and rep['result']} capped={rep and rep['capped']}")
    ok(rep and rep["ko"] and "{" not in rep["ko"], f"아침 방송({rep and rep['key']}): {rep and rep['ko']}")
    st = S.load_state(uid)
    room = S.room_at(st, st["raid"]["target_slot"])
    if exp == "breached":
        ok(room.get("flooded") and room.get("flooded_from", {}).get("id") == room["id"], f"결과 상실 → 물 찬 칸, 기억 {room.get('flooded_from')}")
    else:
        ok(room.get("cracked") and not room.get("flooded"), "결과 금 → 방이 금 간다(물은 안 찬다)")
    ok(st["raid"]["resolved"] and st["raid"]["auto"], "습격 resolved·auto")
    a2 = ark(uid, debug_night=1)
    ok(a2["night_judge"]["report"] is None and len(S.load_state(uid)["raid_log"]) == 1, "멱등: 두 번째 요청에 판정 없음, raid_log 1건")
    r = C.post("/api/raid/advance", json={"uid": uid})
    ok(r.status_code == 400, "자동 판정 뒤 접촉 버튼 → 400(이미 지나감)")
    # 막을 수 있는 판은 막음 그대로(보상도 그대로)
    uid2 = "dev_s13_night2"
    a = ark(uid2)
    _raid(uid2, "longneck", grade=1)
    st = S.load_state(uid2)
    slot = st["raid"]["target_slot"]
    C.post("/api/ark/light", json={"uid": uid2, "slot": slot, "on": False})
    for r_ in st["residents_list"]:
        C.post("/api/ark/station", json={"uid": uid2, "resident_id": r_["id"], "slot": slot})
    rep = ark(uid2, debug_night=1)["night_judge"]["report"]
    ok(rep and rep["result"] == "held" and not rep["capped"] and rep["gained"], f"서 있는 배치가 좋으면 막음 + 보상 {rep and rep['gained']}")
    # 날이 바뀌어 다음 요청이 오면(디버그 없이) 어제 것을 판정
    uid3 = "dev_s13_night3"
    ark(uid3)
    _raid(uid3, "swarm", grade=1)
    shift_day(uid3)
    j = C.get(f"/api/raid/today?uid={uid3}").json()
    ok(j["night_judge"] is not None and j["night_judge"]["result"] in ("held", "scarred"),
       f"하루가 지난 뒤 raid/today → 어제 습격 판정 {j['night_judge'] and j['night_judge']['result']}")
    # 시각 규칙
    from datetime import datetime
    h = int(S.stk("night_judge.hour"))
    t15 = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0).timestamp()
    t22 = datetime.now().replace(hour=22, minute=0, second=0, microsecond=0).timestamp()
    ok(datetime.fromtimestamp(S.night_deadline(t15)).hour == h and S.night_deadline(t15) - t15 == (h - 15) * 3600,
       f"15시에 본 습격 → 같은 날 {h}시 판정")
    ok(S.night_deadline(t22) - t22 == (24 - 22 + h) * 3600, f"22시에 본 습격 → 다음 날 {h}시(바로 판정하지 않는다)")
    ok(C.get(f"/api/ark?uid={uid}&debug_night=1").status_code == 200, "debug_night 은 개발 모드 전용(여기서는 DEV)")


def t_lid():
    uid = "dev_s13_lid"
    ark(uid)
    st = S.load_state(uid)
    st["rooms"].append({"id": "quarters", "slot": 4, "built": time.time(), "level": 1})
    S.save_state(uid, st)
    j = _raid(uid, "lid", grade=4)
    rid = j["state"]["residents_list"][0]["id"]
    ok(j["raid"]["stage"] == "sound" and not j["raid"]["lid_revealed"], "소리 단계: 덮개 대상 비공개")
    C.post("/api/ark/station", json={"uid": uid, "resident_id": rid, "slot": 2})
    ok(S.load_state(uid)["raid"]["moves"] == 1, "소리 단계 이동은 센다(moves=1)")
    _raid(uid, "lid", grade=4)                    # 다시 처음부터
    adv = C.post("/api/raid/advance", json={"uid": uid}).json()
    rv = adv["raid"]
    ok(rv["lid_revealed"] and rv["target_slot"] is not None and rv["reveal_ko"], f"실루엣: 대상 공개 slot={rv['target_slot']} {rv['reveal_ko']}")
    for r_ in S.load_state(uid)["residents_list"]:
        C.post("/api/ark/station", json={"uid": uid, "resident_id": r_["id"], "slot": rv["target_slot"]})
    st = S.load_state(uid)
    ok(st["raid"]["moves"] == 0, "공개 뒤(실루엣) 이동은 세지 않는다(stakes lid._note)")
    pub = S.raid_public(st, st["raid"])
    ok(pub["ready"]["gate"]["ok"], f"관문 통과 상태로 접촉 준비: score {pub['ready']['score']} / need {pub['ready']['need']}")
    # 다른 생물에는 공개 규칙이 없다(실루엣 이동이 그대로 센다)
    uid2 = "dev_s13_lid2"
    ark(uid2)
    _raid(uid2, "swarm", grade=1)
    C.post("/api/raid/advance", json={"uid": uid2})
    r_ = S.load_state(uid2)["residents_list"][0]
    C.post("/api/ark/station", json={"uid": uid2, "resident_id": r_["id"], "slot": 2})
    ok(S.load_state(uid2)["raid"]["moves"] == 1, "덮개 아닌 생물은 예전처럼 moves 를 센다")


def t_crack_combat():
    """금 간 방의 바탕 감점이 판정 미리보기에 보인다."""
    uid = "dev_s13_crackc"
    ark(uid)
    _raid(uid, "swarm", grade=2)
    C.post("/api/raid/advance", json={"uid": uid})
    st = S.load_state(uid)
    before = S.raid_public(st, st["raid"])["ready"]["score"]
    S.room_at(st, st["raid"]["target_slot"])["cracked"] = True
    after = S.raid_public(st, st["raid"])["ready"]
    pen = float(S.stk("crack.room_base_penalty"))
    ok(round(after["score"] - before, 2) == pen and any(p["v"] == pen for p in after["parts"]),
       f"금 간 방 판정 바탕 {before} → {after['score']} ({pen})")


def t_spot_distinct():
    uid = "dev_s13_spot"
    ark(uid)
    code = ean("490123400001")
    for _ in range(3):
        scan(uid, code, "electronics")
    cnt = S.scan_counts(uid)
    ok(cnt.get("electronics") == 1, f"같은 바코드 3번 → 스팟 카운트 {cnt.get('electronics')} (서로 다른 바코드만)")
    scan(uid, ean("490123400002"), "electronics")
    ru = C.get(f"/api/rumors?uid={uid}").json()
    vent = next((x for x in ru if x["spot_id"] == "spot_vent_garden"), None)
    ok(vent and vent["progress"]["have"] == 2 and vent["unlocked"], f"서로 다른 둘 → 열수구 {vent and vent['progress']}")
    de = C.get(f"/api/day_end?uid={uid}").json()
    ok(any(l_["id"] == "spot_found" for l_ in de["lines"]), "스팟 연 날 → 하루 마감에 spot_found 줄")


def t_codex():
    uid = "dev_s13_codex"
    ark(uid)
    scan(uid, ean("880104301509"))
    cx = C.get(f"/api/codex?uid={uid}").json()
    tot = sum(c["total"] for c in cx)
    ent = sum(len(c["entries"]) for c in cx)
    known = [e for c in cx for e in c["entries"] if e["known"]]
    unknown = [e for c in cx for e in c["entries"] if not e["known"]]
    ok(ent == tot and len(known) == 1, f"도감 전 칸 {ent}/{tot}, 아는 칸 {len(known)}")
    ok(all(e["stem"] is None and e["hint_ko"] for e in unknown), "모르는 칸은 이름 없이 실루엣 문장")
    ok(known[0]["rarity_best"] in S.RARITY_KEYS, f"아는 칸 희귀도 {known[0]['rarity_best']}")
    ok(all(k in cx[0] for k in ("category", "total", "found", "names")), "옛 필드 유지(옛 화면 호환)")


def t_octopus_wishes_dayend():
    uid = "dev_s13_oct"
    a = ark(uid)
    ok(a["octopus"] == {"arrived": False}, "1일차: 문어 없음")
    ok(C.post("/api/octopus/name", json={"uid": uid, "name": "먹물"}).status_code == 400, "오기 전 이름 짓기 → 400")
    for i in range(3):
        scan(uid, ean(f"88010620{i:04d}"))          # 식품 셋 → 요리사 바람(선반 식품 3칸)
    shift_day(uid)
    a = ark(uid)
    oc = a["octopus"]
    ok(oc["arrived"] and oc.get("arrival") and oc["gift_today"] and oc["gift_today"]["ko"], f"2일차: 첫 등장 + 선물 {oc['gift_today'] and oc['gift_today']['name']}")
    a2 = ark(uid)
    ok("arrival" not in a2["octopus"] and a2["octopus"]["gift_today"]["id"] == oc["gift_today"]["id"]
       and a2["octopus"]["finds_count"] == 1, "같은 날 다시 열어도 선물 하나, 등장 연출은 한 번")
    n = C.post("/api/octopus/name", json={"uid": uid, "name": "먹물"}).json()
    ok(n["name"] == "먹물" and "먹물" in n["ko"], f"이름 짓기: {n['ko']}")
    w = C.get(f"/api/wishes?uid={uid}").json()
    roles = sorted({x["role"] for x in w})
    cook = next(x for x in w if x["role"] == "cook")
    ok(roles == sorted({r["role"] for r in a["residents_list"]}), f"바람은 있는 역할만: {roles}")
    ok(cook["done"] and cook["line"] and "{name}" not in cook["line"], f"요리사 바람 이룸 → line_after: {cook['line'][:30]}…")
    de = C.get(f"/api/day_end?uid={uid}").json()
    ids = [x["id"] for x in de["lines"]]
    ok("octopus_brought" in ids and len(ids) <= 3 and all("{" not in x["text"] for x in de["lines"]), f"하루 마감 줄 {ids}")
    ok(de["open"] and de["close"] and de["facts"]["floors"] >= 1, "마감 머리·꼬리 문장")
    col = C.get(f"/api/collection?uid={uid}").json()
    ok(sum(1 for f in col["octopus_finds"] if f["known"]) == 1 and len(col["octopus_finds"]) == 20, "문어 선물 도감 1/20")
    uq = "dev_s13_quiet"
    ark(uq)
    dq = C.get(f"/api/day_end?uid={uq}").json()
    ok([x["id"] for x in dq["lines"]] == ["quiet"], "아무 일 없는 날 → quiet 한 줄")


def t_moments_and_events():
    m = C.get("/api/text/moments").json()
    ok(m.get("shelf") and m.get("night_judge"), f"/api/text/moments 키 {len(m)}개")
    uid = "dev_s13_event"
    ark(uid)
    e = C.get(f"/api/event/today?uid={uid}")
    ok(e.status_code == 200 and e.json().get("event"), f"오늘의 사건 {e.json().get('event', {}).get('id')}")
    r = C.post("/api/event/resolve", json={"uid": uid, "card_id": None})
    ok(r.status_code == 200 and "state" in r.json() and "production" in r.json()["state"], "사건 해결 → /base 상태 모양 그대로")
    r2 = C.post("/api/event/resolve", json={"uid": uid, "card_id": None})
    ok(r2.status_code == 400, "두 번 해결 → 400")


def t_player_loop():
    """플레이어 한 바퀴(규칙 사): 스캔 → 재스캔 닦기 → 가문 진행 → 습격 → 무응답 → 밤 판정(금 상한) → 금 → 수리 → 배치가 생산을 바꾼다."""
    uid = "dev_s13_loop"
    ark(uid)
    a = scan(uid, ean("880103700001"))
    b = scan(uid, ean("880103700002"))
    shift_day(uid)
    c = scan(uid, ean("880103700001"))
    ok(a["shelf_new"] and not c["shelf_new"] and c["polish"]["counted_today"], "① 스캔 → 다른 날 재스캔은 닦기")
    ok(b["family_set"]["have"] == 2, f"② 가문 진행 {b['family_set']['have']}/{b['family_set']['total']}")
    st = S.load_state(uid)
    st["rooms"].append({"id": "greenhouse", "slot": 3, "built": time.time(), "level": 1})
    S.save_state(uid, st)
    j = _raid(uid, "big_maw", grade=4)
    ok(j["raid"]["creature"]["id"] == "big_maw", "③ 습격 옴(접촉 안 누름)")
    rep = ark(uid, debug_night=1)["night_judge"]["report"]
    ok(rep and rep["result"] in ("scarred", "breached"), f"④ 밤 판정 {rep and rep['result']} (상한 {S.stk('night_judge.worst_result')})")
    st = S.load_state(uid)
    slot = st["raid"]["target_slot"]
    room = S.room_at(st, slot)
    if room.get("flooded"):
        ok(True, f"⑤ {room['flooded_from']['id']} 물 찬 칸")
        st["resources"].update({k: 99 for k in ("food", "water", "parts", "scrap", "power", "cloth", "med")})
        S.save_state(uid, st)
        rr = C.post("/api/ark/build", json={"uid": uid, "room_id": room["flooded_from"]["id"], "slot": slot})
        ok(rr.status_code == 200 and rr.json()["reclaimed"], f"⑥ 되찾기(다시 짓기) {rr.status_code}")
        prod = rr.json()["production"]
    else:
        ok(room.get("cracked"), f"⑤ {room['id']} 금")
        st["resources"].update({k: v for k, v in S.stk("crack.repair_cost").items()})
        S.save_state(uid, st)
        rr = C.post("/api/ark/repair", json={"uid": uid, "slot": slot})
        ok(rr.status_code == 200, "⑥ 수리")
        prod = rr.json()["state"]["production"]
    rid = st["residents_list"][0]["id"]
    s2 = C.post("/api/ark/station", json={"uid": uid, "resident_id": rid, "slot": 3}).json()["production"]
    nm = lambda p_: p_.get("now_mult", p_["mult"])          # 접촉한 틱은 스냅숏, 다음 틱부터 지금 배치
    ok(nm(s2["3"]) > nm(prod["3"]), f"⑦ 온실에 1명 → 다음 틱 배율 {nm(prod['3'])} → {nm(s2['3'])}")


def t_contact_snapshot():
    """staffing.measure=contact_snapshot: 접촉 순간 배치가 그 틱 생산을 정한다(옮겨 막고 되돌려도 비용이 남는다)."""
    if S.stk("staffing.measure") != "contact_snapshot":
        ok(True, "measure 가 contact_snapshot 이 아니다 — 건너뜀")
        return
    uid = "dev_s13_snap"
    ark(uid)
    st = S.load_state(uid)
    st["rooms"].append({"id": "greenhouse", "slot": 3, "built": time.time(), "level": 1})
    S.save_state(uid, st)
    sm = S.stk("staffing.staff_mult")
    # 평소: 온실 1명
    rid = st["residents_list"][0]["id"]
    C.post("/api/ark/station", json={"uid": uid, "resident_id": rid, "slot": 3})
    j = _raid(uid, "swarm", grade=1)
    tgt = S.load_state(uid)["raid"]["target_slot"]
    C.post("/api/raid/advance", json={"uid": uid})
    for r_ in S.load_state(uid)["residents_list"]:          # 전원 대상 방으로 몰고
        C.post("/api/ark/station", json={"uid": uid, "resident_id": r_["id"], "slot": tgt})
    C.post("/api/raid/advance", json={"uid": uid})          # 접촉
    for r_ in S.load_state(uid)["residents_list"]:          # 바로 되돌린다
        C.post("/api/ark/station", json={"uid": uid, "resident_id": r_["id"], "slot": None})
    C.post("/api/ark/station", json={"uid": uid, "resident_id": rid, "slot": 3})
    a = ark(uid)
    other = "2" if str(tgt) == "3" else "3"
    p_t, p_o = a["production"][str(tgt)], a["production"][other]
    ok(p_t["snapshot"] and p_t["staff"] == 3 and p_t["mult"] == sm[3], f"접촉한 틱: 대상 방 {tgt} = 3명 배율 {p_t['mult']} (지금 배치 {p_t.get('now_mult')})")
    ok(p_o["staff"] == 0 and p_o["mult"] == sm[0], f"접촉한 틱: 비운 방 {other} = 0명 {p_o['mult']} — 되돌려도 이번 틱 비용이 남는다")
    # 정산: 그 틱이 지나면 스냅숏으로 한 틱, 나머지는 지금 배치
    st = S.load_state(uid)
    T = S.PRODUCTION_TICK_SEC
    st["last_tick"] -= 2 * T
    st["staff_snapshot"]["tick_start"] = st["last_tick"]
    res0 = dict(st["resources"])
    S.tick_production(st)
    ok("staff_snapshot" not in st, "정산 뒤 스냅숏은 사라진다")


def t_flooded_reclaim():
    """사용자 결정: 잃은 방 = 물 찬 칸. 종류·레벨을 기억하고, 보통 짓기(economy 건설비)로 Lv1 부터 되찾는다."""
    uid = "dev_s13_flood"
    ark(uid)
    st = S.load_state(uid)
    st["rooms"].append({"id": "greenhouse", "slot": 3, "built": time.time(), "level": 2})
    S.save_state(uid, st)
    # 엔진 판정으로 상실을 만든다: 등급 4 큰 입, 빈 방 — 대상이 온실이 될 때까지 날을 민다
    for _ in range(30):
        _raid(uid, "big_maw", grade=4)
        if S.load_state(uid)["raid"]["target_slot"] == 3:
            break
        shift_day(uid)
    C.post("/api/raid/advance", json={"uid": uid})
    out = C.post("/api/raid/advance", json={"uid": uid}).json()
    st = S.load_state(uid)
    room = S.room_at(st, 3)
    ok(out["result"] == "breached" and room["flooded"] and room["flooded_from"] == {"id": "greenhouse", "level": 2},
       f"상실 → 물 찬 칸, 기억 {room.get('flooded_from')}")
    a = ark(uid)
    fc = a["flooded_cells"]
    ok(fc and fc[0]["slot"] == 3 and fc[0]["was_id"] == "greenhouse" and fc[0]["was_level"] == 2, f"/api/ark flooded_cells {fc}")
    ok(C.post("/api/ark/station", json={"uid": uid, "resident_id": st["residents_list"][0]["id"], "slot": 3}).status_code == 400,
       "물 찬 칸에는 사람을 둘 수 없다")
    cost = a["build_options"]["greenhouse"]["cost"]
    st = S.load_state(uid)
    for k in cost:
        st["resources"][k] = 0
    S.save_state(uid, st)
    r = C.post("/api/ark/build", json={"uid": uid, "room_id": "greenhouse", "slot": 3})
    ok(r.status_code == 400, "재료 없으면 되찾기 불가(보통 건설비)")
    st = S.load_state(uid)
    st["resources"].update(cost)
    S.save_state(uid, st)
    r = C.post("/api/ark/build", json={"uid": uid, "room_id": "greenhouse", "slot": 3})
    j = r.json()
    room = S.room_at(S.load_state(uid), 3)
    ok(r.status_code == 200 and room["id"] == "greenhouse" and room["level"] == 1 and not room.get("flooded")
       and all(j["resources"][k] == 0 for k in cost), f"다시 짓기 → Lv1, 건설비 {cost} 지불, reclaimed={j['reclaimed']}")
    ok(not j["flooded_cells"] and len(S.load_state(uid)["reclaimed"]) == 1, "물 찬 칸 목록에서 빠지고 기록에 남는다")
    ok(C.post("/api/ark/build", json={"uid": uid, "room_id": "greenhouse", "slot": 3}).status_code == 400, "멀쩡한 칸에는 못 짓는다(예전 규칙)")
    # 옛 저장의 물 찬 방 → flooded_from 보강
    uid2 = "dev_s13_flood_old"
    st = S.new_state(uid2)
    st["rooms"].append({"id": "well", "slot": 3, "built": 1, "level": 2, "flooded": True, "flooded_day": 3})
    S.save_state(uid2, st)
    st = S.load_state(uid2)
    ok(S.room_at(st, 3)["flooded_from"] == {"id": "well", "level": 2}, "옛 물 찬 방 → 기억 보강(migrate_s13)")


def t_lid_deferred():
    """사용자 결정: 덮개 보류 — 1막(등급 1~5) 선택에서 빠진다. 데이터: threats.json min_grade.lid."""
    import combat as CB
    mg = CB.min_grade("lid")
    ok(mg > max(r["grade"] for r in S.THREAT_GRADES), f"threats.json min_grade.lid = {mg} (1막 최고 등급 {max(r['grade'] for r in S.THREAT_GRADES)} 위)")
    ok(all("lid" not in CB.creature_weights(g) for g in range(1, 6)), "등급 1~5 가중치에 덮개 없음")
    hits = sum(1 for d in range(1, 400) for g in (4, 5)
               if (CB.pick_creature(f"u{d}", d, g) or {}).get("id") == "lid")
    ok(hits == 0, f"1~399일 × 등급 4·5 무작위 선택에서 덮개 {hits}회")
    ok(CB.CREATURES.get("lid") is not None, "생물 자체와 디버그 강제(debug_raid=lid)는 남는다")


TESTS = [t_polish_and_dup_fix, t_migration_old_save, t_category_lock_and_peek, t_variant, t_family_set_and_first_meet,
         t_staffing_and_crack, t_repair, t_night_judge, t_lid, t_crack_combat, t_spot_distinct, t_codex,
         t_octopus_wishes_dayend, t_moments_and_events, t_contact_snapshot, t_flooded_reclaim, t_lid_deferred, t_player_loop]

if __name__ == "__main__":
    for t in TESTS:
        print(f"\n## {t.__name__} — {t.__doc__.strip().splitlines()[0] if t.__doc__ else ''}")
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
