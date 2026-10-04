"""S15-A 서버 검증 — 원정·문간 (docs/API_EXPEDITION.md, docs/EXPEDITION.md).

실행:  python tests/test_s15_expedition.py   (임시 DB + TestClient. 실제 relic_ark.db 를 건드리지 않는다)
시간은 개발 훅 POST /api/dev/advance(RELIC_DEV=1) 로 민다. 수치는 data/balance/expedition.json 에서 읽는다.
"""
from __future__ import annotations

import os
import random
import statistics
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
import expedition as EX  # noqa: E402
import combat as CB  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t15.db"
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


def get(path):
    r = C.get(path)
    assert r.status_code == 200, (path, r.status_code, r.text)
    return r.json()


def post(path, body, code=200):
    r = C.post(path, json=body)
    assert r.status_code == code, (path, r.status_code, r.text)
    return r.json()


def adv(uid, minutes):
    return post("/api/dev/advance", {"uid": uid, "minutes": minutes})


def new_ark(uid, rooms=(), stats=None):
    get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    for rid, slot, lv in rooms:
        st["rooms"].append({"id": rid, "slot": slot, "built": time.time(), "level": lv})
    for r in st["residents_list"]:
        r["stats"] = dict({"hand": 5, "eye": 5, "breath": 5, "nerve": 5}, **(stats or {}).get(r["role"], {}))
        r["injured"] = False
    st["resources"].update({k: 20 for k in ("food", "water", "parts", "cloth", "med", "scrap")})
    S.save_state(uid, st)
    return st


def who(uid, role):
    return next(r for r in S.load_state(uid)["residents_list"] if r["role"] == role)


def tutorial(uid, rid):
    """첫 원정(튜토리얼): 줍기 3번 → 끝 → 바로 귀환."""
    post("/api/expedition/start", {"uid": uid, "members": [rid], "dest": {"kind": "door"}, "length": "short"})
    for i in range(3):
        sc = post("/api/expedition/scene", {"uid": uid, "action": "pick", "i": i})
    post("/api/expedition/scene", {"uid": uid, "action": "done"})
    return get(f"/api/ark?uid={uid}")


# ─────────────────────────────────────────────────────────────
def t_full_loop():
    """출발 → 시간 흐름(개발 훅) → 귀환 → 상자 → 스캔으로 열기 → 두드림 → 들이기."""
    uid = "dev_s15_loop"
    new_ark(uid)
    scout = who(uid, "scout")
    a0 = get(f"/api/ark?uid={uid}")
    sup = a0["air"]["supply"]
    ok(a0["air"]["value"] == sup == float(EX.g("air.daily_supply_base")) and a0["gauges"]["air"]["fixed"] is False,
       f"공기 하루 공급 {sup}, 게이지 실값")
    opt = get(f"/api/expedition/options?uid={uid}")
    ok(opt["tutorial"] and opt["lengths"]["long"]["can"] is False, "첫 원정은 튜토리얼, 밤 넘기기는 에어락 필요")
    # 튜토리얼
    post("/api/expedition/start", {"uid": uid, "members": [scout["id"]], "dest": {"kind": "unknown"}, "length": "half"})
    sc = get(f"/api/expedition/scene?uid={uid}")
    ok(sc["tutorial"] and len(sc["head"]["picks"]) == 3 and sc["next"] == "pick:0" and sc["head"]["danger"] is None,
       f"튜토리얼 장면: 줍기 3, 위험 없음, dest={sc['dest']}")
    r = C.post("/api/expedition/scene", json={"uid": uid, "action": "pick", "i": 1})
    ok(r.status_code == 400, "순서 어긴 줍기 → 400(서버 검증)")
    ok(scout["id"] in S.load_state(uid)["outside"], "출발하면 outside = 원정대")
    for i in range(3):
        sc = post("/api/expedition/scene", {"uid": uid, "action": "pick", "i": i})
    ok(sc["head"]["picks"][2]["item"] == {"kind": "box", "cat": "blank", "i": 2}, "셋째 줍기 = 빈 원 상자(아무 갈래)")
    post("/api/expedition/scene", {"uid": uid, "action": "done"})
    a = get(f"/api/ark?uid={uid}")
    ret = a["expedition_return"]
    ok(ret and ret["tutorial"] and len(ret["haul"]["boxes"]) == 1 and a["expedition"] is None and not S.load_state(uid)["outside"],
       f"튜토리얼 귀환: {ret and ret['line']}")
    ok(a["boxes"] and a["boxes"][0]["any"], "상자가 대기(빈 원)")
    post("/api/expedition/seen", {"uid": uid})
    ok(get(f"/api/ark?uid={uid}")["expedition_return"] is None, "seen 뒤에는 귀환 결과가 오지 않는다")
    # 첫 스캔이 상자를 연다
    food0 = S.load_state(uid)["resources"]["food"]
    sc = post("/api/scan", {"uid": uid, "barcode": ean("490123400001"), "user_category": "drink"})
    ok(sc["box_opened"] and sc["box_opened"]["cat"] == "blank", f"첫 스캔이 빈 원 상자를 연다 {sc['box_opened']}")
    # 반나절 문 앞 — 실제 시간
    sup_before = get(f"/api/ark?uid={uid}")["air"]["value"]
    st = post("/api/expedition/start", {"uid": uid, "members": [scout["id"]], "dest": {"kind": "door"}, "length": "half"})
    tank = int(EX.g("lengths.half.tank"))
    ok(abs(st["state"]["air"]["value"] - (sup_before - tank)) < 1e-6, f"공기 {sup_before} → {st['state']['air']['value']} (−{tank})")
    adv(uid, 120)
    p = get(f"/api/expedition?uid={uid}")
    ok(p["expedition"] and 0.4 < p["expedition"]["progress"] < 0.6 and p["expedition_return"] is None, f"2시간 뒤 진행 {p['expedition']['progress']}")
    adv(uid, 121)
    a1 = get(f"/api/ark?uid={uid}")
    a2 = get(f"/api/ark?uid={uid}")
    st_ = S.load_state(uid)
    ok(a1["expedition_return"] and a1["expedition"] is None and len(st_["exp_log"]) == 2 and a2["expedition_return"]["id"] == a1["expedition_return"]["id"],
       f"4시간 뒤 정산 한 번(멱등): exp_log {len(st_['exp_log'])}, {a1['expedition_return']['line']}")
    # 두드림: 3일차 고정
    st_ = S.load_state(uid)
    ok(not st_["guests"], "1일차 손님 없음")
    adv(uid, 60 * 24 * 2)
    a = get(f"/api/ark?uid={uid}")
    ent = get(f"/api/entrance?uid={uid}")
    ok(a["day"] >= 3 and a["knock"] and len(ent["guests"]) == 1, f"{a['day']}일차 첫 두드림: {a['knock']}")
    gid = ent["guests"][0]["id"]
    beds0 = int((EX.g("newcomers.beds_by_quarters_level") or {}).get("0", 3))
    ok(ent["beds"]["total"] == beds0, f"거주실 없음 → 잠자리 {ent['beds']} (데이터 {beds0})")
    st_ = S.load_state(uid)
    keep = list(st_["residents_list"])
    while len(st_["residents_list"]) < beds0:                 # 잠자리를 꽉 채워 '빈 잠자리 없음'을 만든다
        st_["residents_list"].append(dict(keep[0], id=f"filler-{len(st_['residents_list'])}"))
    S.save_state(uid, st_)
    r = C.post("/api/entrance/guest", json={"uid": uid, "guest_id": gid, "accept": True})
    ok(r.status_code == 400, "빈 잠자리가 없으면 들일 수 없다")
    st_ = S.load_state(uid)
    st_["residents_list"] = keep
    st_["rooms"].append({"id": "quarters", "slot": 4, "built": time.time(), "level": 1})
    S.save_state(uid, st_)
    j = post("/api/entrance/guest", {"uid": uid, "guest_id": gid, "accept": True})
    ok(j["accepted"] and len(j["state"]["residents_list"]) == 4 and not j["entrance"]["guests"], "들이기 → 주민 4명")
    adv(uid, 60 * 24 * 10)
    ok(len(S.load_state(uid)["residents_list"]) == 4, "들인 사람은 그대로 있다")


def t_guests_never_leave():
    """손님은 스스로 떠나지 않는다. 자리(2)가 차면 두드림이 오지 않는다."""
    uid = "dev_s15_guests"
    new_ark(uid)
    st = S.load_state(uid)
    S.make_guest(st, uid, "a", "knock")
    S.make_guest(st, uid, "b", "knock")
    st["first_knock_done"] = True
    S.save_state(uid, st)
    for _ in range(12):
        adv(uid, 60 * 24)
        get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    ok(len(st["guests"]) == 2, f"12일 뒤 손님 {len(st['guests'])}명(떠나지 않고, 더 오지도 않는다)")
    g = st["guests"][0]["guest_id"]
    j = post("/api/entrance/guest", {"uid": uid, "guest_id": g, "accept": False})
    ok(not j["accepted"] and len(S.load_state(uid)["guests"]) == 1, "안내(거절) → 벌도 보상도 없이 손님 하나 줄어든다")


def t_overnight():
    """밤 넘기기가 날 경계를 넘는다 — outside 가 날이 바뀌어도 비지 않는다."""
    uid = "dev_s15_night"
    new_ark(uid, rooms=(("airlock", 3, 1),))
    st = S.load_state(uid)
    st["exp_count"] = 2                                   # 튜토리얼·배우는 원정 지난 방주
    S.save_state(uid, st)
    # 1일차 끝자락으로
    t0 = S.load_state(uid)["created"]
    adv(uid, 60 * 20)
    eng = who(uid, "engineer")
    d0 = get(f"/api/ark?uid={uid}")["day"]
    opt = get(f"/api/expedition/options?uid={uid}")
    ok(opt["lengths"]["long"]["can"] and opt["suits"]["total"] == 2, f"에어락 Lv1 → 밤 넘기기·공용 잠수복 {opt['suits']['total']}")
    post("/api/expedition/start", {"uid": uid, "members": [eng["id"]], "dest": {"kind": "unknown"}, "length": "long"})
    adv(uid, 60 * 6)
    j = get(f"/api/raid/today?uid={uid}")
    st = S.load_state(uid)
    ok(j["day"] == d0 + 1 and eng["id"] in st["outside"] and st["expedition"], f"{d0}→{j['day']}일차 습격 확인 뒤에도 원정대는 밖에 있다")
    adv(uid, 60 * 4 + 1)
    a = get(f"/api/ark?uid={uid}")
    ret = a["expedition_return"]
    ok(ret and ret["length"] == "long" and not S.load_state(uid)["outside"], f"밤 넘기기 귀환: {ret and ret['line']}")
    ok(ret and ret["newcomer"], f"첫 '모르는 쪽'은 반드시 누군가를 만난다: {ret and ret['newcomer']}")


def t_raid_absent():
    """밖에 나간 사람은 지키지 못한다: 점수·관문(손톱 무리)·생산·밤 판정에서 없는 사람."""
    uid = "dev_s15_raid"
    new_ark(uid, rooms=(("greenhouse", 3, 1),))
    st = S.load_state(uid)
    st["exp_count"] = 2
    S.save_state(uid, st)
    j = get(f"/api/raid/today?uid={uid}&debug_raid=claws&debug_reset=1&debug_grade=2")
    tgt = S.load_state(uid)["raid"]["target_slot"]
    for r in S.load_state(uid)["residents_list"]:
        post("/api/ark/station", {"uid": uid, "resident_id": r["id"], "slot": tgt})
    st = S.load_state(uid)
    ok(not st["outside"], "손톱 무리 날 — 무작위 차출 없음(outside 빈 채)")
    post("/api/raid/advance", {"uid": uid})
    pre = S.raid_public(S.load_state(uid), S.load_state(uid)["raid"])["ready"]
    ok(pre["gate"]["ok"], f"아무도 안 나가면 관문 통과(score {pre['score']})")
    scout = who(uid, "scout")
    pv = post("/api/expedition/preview", {"uid": uid, "members": [scout["id"]], "dest": {"kind": "door"}, "length": "short"})
    ok(pv["danger"]["lingering_add"] == float(EX.g("raid_link.lingering_add.claws")) and pv["warnings"],
       f"접촉 전 손톱 무리 → 원정 위험 +{pv['danger']['lingering_add']}, 경고")
    post("/api/expedition/start", {"uid": uid, "members": [scout["id"]], "dest": {"kind": "door"}, "length": "half"})
    st = S.load_state(uid)
    ctx = S.raid_ctx(st, st["raid"])
    pub = S.raid_public(st, st["raid"])["ready"]
    ok(scout["id"] not in [p["id"] for p in ctx["people"]] and not pub["gate"]["ok"] and pub["score"] < pre["score"],
       f"원정 나간 정찰병은 방에 없다: 사람 {len(ctx['people'])}, 관문 실패, score {pre['score']}→{pub['score']}")
    ok(all(scout["id"] not in [p['id'] for p in S.staff_people(st, s)] for s in (2, 3, tgt)), "생산에도 없다(staff_people)")
    post("/api/expedition/recall", {"uid": uid})
    st = S.load_state(uid)
    ok(st["expedition"] and scout["id"] in st["outside"], "불러들이는 20분 동안은 아직 밖")
    adv(uid, 21)
    get(f"/api/ark?uid={uid}")
    st = S.load_state(uid)
    pub = S.raid_public(st, st["raid"])["ready"]
    ok(not st["outside"] and pub["gate"]["ok"] and S.station_slot(st, scout["id"]) == tgt,
       "21분 뒤 돌아와 원래 자리로 → 관문 통과")
    ret = st["exp_unseen"]
    ok(ret["recalled"], f"불러들인 원정 — 지난 비율만큼만: {ret['line']}")
    # 밤 판정도 밖에 나간 사람을 없는 사람으로 본다
    uid2 = "dev_s15_raid2"
    new_ark(uid2)
    st = S.load_state(uid2)
    st["exp_count"] = 2
    S.save_state(uid2, st)
    get(f"/api/raid/today?uid={uid2}&debug_raid=swarm&debug_reset=1&debug_grade=1")
    tgt = S.load_state(uid2)["raid"]["target_slot"]
    for r in S.load_state(uid2)["residents_list"]:
        post("/api/ark/station", {"uid": uid2, "resident_id": r["id"], "slot": tgt})
    eng = who(uid2, "engineer")
    post("/api/expedition/start", {"uid": uid2, "members": [eng["id"]], "dest": {"kind": "door"}, "length": "half"})
    rep = get(f"/api/ark?uid={uid2}&debug_night=1")["night_judge"]["report"]
    log = S.load_state(uid2)["raid_log"][-1]
    ok(rep is not None and log["score"] is not None, f"밤 판정 결과 {rep and rep['result']} (원정 중 기술자 제외로 계산)")
    st = S.load_state(uid2)
    ctx_people = [p for p in S.stations_map(st).get(tgt, [])]
    ok(eng["id"] not in [p["id"] for p in ctx_people], "밤 판정 시점 대상 방 명단에 원정대 없음")


def t_ev_equal():
    """따라 나가도 기댓값이 같다(DECISIONS 2026-10-03 ①). 공통 난수라 자동과 같은 선택이면 결과가 같다."""
    members = [{"id": "a", "stats": {"hand": 6, "eye": 6, "breath": 6, "nerve": 5}}]
    same, diffs, v_auto, v_lit, v_dark, v_follow_rand = 0, 0, [], [], [], []
    N = 3000
    for k in range(N):
        res = EX.roll(f"ev|{k}", members=members, dest={"kind": "unknown"}, dest_cat="*", length="half",
                      danger_mul=1.3, lingering=None, learning=False, recent_cats=["food", "drink"],
                      kinds_weights=None, rescue_p=0.1, clue_p=0.06, discover_p=0.0)
        auto_fork = "lit" if k % 2 else "dark"
        a = EX.settle(res, fork=auto_fork, danger_choice=None)
        # 따라 나가기: 줍기를 직접 탭하고(순서·탭은 결과에 영향 없음) 자동과 같은 것을 고른다
        f = EX.settle(res, fork=auto_fork, danger_choice=EX.danger_auto(res.get("danger")))
        same += (a == f)
        v_auto.append(a["value"])
        v_lit.append(EX.settle(res, fork="lit", danger_choice=None)["value"])
        v_dark.append(EX.settle(res, fork="dark", danger_choice=None)["value"])
        rng = random.Random(k)
        v_follow_rand.append(EX.settle(res, fork=rng.choice(["lit", "dark"]), danger_choice=None)["value"])
    ok(same == N, f"따라 나가서 자동과 같은 선택 → {same}/{N} 결과 동일")
    ml, md, ma, mr = (statistics.mean(x) for x in (v_lit, v_dark, v_auto, v_follow_rand))
    ok(abs(ml - md) / ma < 0.05 and abs(mr - ma) / ma < 0.05,
       f"갈림길 기댓값(가치 단위): 불빛 {ml:.3f} / 어둠 {md:.3f} / 자동 {ma:.3f} / 무작위로 고름 {mr:.3f} (차 {abs(ml - md) / ma:.1%})")
    # API 로도: 장면에서 자동과 같은 선택을 하면 결과가 같다
    uid = "dev_s15_ev"
    new_ark(uid)
    st = S.load_state(uid)
    st["exp_count"] = 2
    S.save_state(uid, st)
    sc_ = who(uid, "scout")
    post("/api/expedition/start", {"uid": uid, "members": [sc_["id"]], "dest": {"kind": "door"}, "length": "half"})
    ex = S.load_state(uid)["expedition"]
    expect = EX.settle(ex["result"], fork=ex["auto_fork"], danger_choice=None)
    sc = get(f"/api/expedition/scene?uid={uid}")
    while sc["next"] != "done":
        n = sc["next"]
        if n.startswith("pick:"):
            sc = post("/api/expedition/scene", {"uid": uid, "action": "pick", "i": int(n.split(":")[1])})
        elif n == "danger":
            sc = post("/api/expedition/scene", {"uid": uid, "action": "danger", "choice": sc["head"]["danger"]["auto"]})
        elif n == "fork":
            sc = post("/api/expedition/scene", {"uid": uid, "action": "fork", "choice": sc["head"]["fork"]["auto"]})
        elif n == "drop":
            break
    post("/api/expedition/scene", {"uid": uid, "action": "done"})
    adv(uid, 241)
    ret = get(f"/api/ark?uid={uid}")["expedition_return"]
    ok(ret and abs(ret["value"] - expect["value"]) < 1e-9, f"API 따라 나가기 결과 가치 {ret and ret['value']} = 자동 {expect['value']}")


def t_box_pry_and_scan_rules():
    """상자: 같은 갈래 스캔으로 가장 오래된 것부터, 같은 바코드는 하루 한 상자, 7일 뒤 억지로(절반)."""
    uid = "dev_s15_box"
    new_ark(uid)
    st = S.load_state(uid)
    b1 = S.box_new(st, "drink", "door", "b1")
    b1["found_ts"] -= 10
    b2 = S.box_new(st, "drink", "door", "b2")
    S.box_new(st, "medical", "door", "b3")
    S.save_state(uid, st)
    code = ean("490123499990")
    sc = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
    units = int(EX.g("boxes.value.units"))
    ok(sc["box_opened"] and sc["box_opened"]["id"] == b1["id"] and sc["box_opened"]["gained"] == {"water": units},
       f"음료 스캔 → 가장 오래된 음료 상자, 물 {units}")
    sc = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
    ok(sc["box_opened"] is None and sc["rescan_multiplier"] < 1, "같은 바코드 같은 날 → 상자 안 열림")
    adv(uid, 60 * 24)
    sc = post("/api/scan", {"uid": uid, "barcode": code, "user_category": "drink"})
    ok(sc["box_opened"] and sc["box_opened"]["id"] == b2["id"], "다음 날 같은 바코드(값 감쇠)로 다음 상자가 열린다")
    r = C.post("/api/box/pry", json={"uid": uid, "box_id": "box-b3"})
    ok(r.status_code == 400, f"7일 전 억지로 열기 → 400 ({r.json()['detail']})")
    adv(uid, 60 * 24 * 7)
    j = post("/api/box/pry", {"uid": uid, "box_id": "box-b3"})
    ok(j["box_opened"]["gained"] == {"med": int(round(units * float(EX.g("boxes.pry.value_mul"))))} and j["box_opened"]["by"],
       f"7일 뒤 억지로 → 절반 {j['box_opened']['gained']} by {j['box_opened']['by']['name']}")


def t_air_suits():
    """하루 공기 8, 틱마다 1/3, 상한. 잠수복 한 벌 = 혼자."""
    uid = "dev_s15_air"
    new_ark(uid)
    st = S.load_state(uid)
    st["exp_count"] = 2
    S.save_state(uid, st)
    sc_, ck = who(uid, "scout"), who(uid, "cook")
    r = C.post("/api/expedition/start", json={"uid": uid, "members": [sc_["id"], ck["id"]], "dest": {"kind": "door"}, "length": "short"})
    ok(r.status_code == 400 and "잠수복" in r.json()["detail"], "공용 잠수복 한 벌 → 둘은 못 간다")
    post("/api/expedition/start", {"uid": uid, "members": [sc_["id"]], "dest": {"kind": "door"}, "length": "half"})
    adv(uid, 241)
    get(f"/api/ark?uid={uid}")
    v = S.air_state(S.load_state(uid))
    ok(v["value"] <= v["supply"], f"공기 {v}")
    st = S.load_state(uid)
    st["air"]["value"] = 3.0
    S.save_state(uid, st)
    r = C.post("/api/expedition/start", json={"uid": uid, "members": [ck["id"]], "dest": {"kind": "door"}, "length": "half"})
    if True:
        ok(r.status_code == 400 and "공기" in r.json()["detail"], "공기가 모자라면 출발 불가")
    st = S.load_state(uid)
    st["air"]["value"] = 0
    st["expedition"] = None
    st["outside"] = []
    S.save_state(uid, st)
    adv(uid, 8 * 60 + 1)
    get(f"/api/ark?uid={uid}")
    v = S.air_state(S.load_state(uid))
    ok(abs(v["value"] - v["supply"] / 3) < 0.01, f"8시간(한 틱) → 공급의 1/3 = {v['value']}")
    adv(uid, 8 * 60 * 5)
    get(f"/api/ark?uid={uid}")
    v = S.air_state(S.load_state(uid))
    ok(v["value"] == v["supply"], f"하루치 이상 쌓이지 않는다 {v['value']}/{v['supply']}")


def t_spots_clue_found():
    """스캔 문턱 = 단서, 발견 = 단서 원정. 방 레벨업 조건은 발견만 센다."""
    uid = "dev_s15_spot"
    new_ark(uid, stats={"scout": {"eye": 10}})
    st = S.load_state(uid)
    st["exp_count"] = 2
    S.save_state(uid, st)
    for i in range(3):
        post("/api/scan", {"uid": uid, "barcode": ean(f"49012340{i:04d}"), "user_category": "stationery"})
    sp = {x["id"]: x for x in get(f"/api/spots?uid={uid}")}
    ok(sp["spot_jelly_bloom"]["state"] == "clue", "문구 셋 → 등불 떼 '단서'")
    ok(not S.spot_found(S.load_state(uid), uid, "spot_jelly_bloom"), "단서는 발견이 아니다")
    sc_ = who(uid, "scout")
    found = False
    for k in range(6):
        pv = post("/api/expedition/preview", {"uid": uid, "members": [sc_["id"]], "dest": {"kind": "clue", "id": "spot_jelly_bloom"}, "length": "half"})
        post("/api/expedition/start", {"uid": uid, "members": [sc_["id"]], "dest": {"kind": "clue", "id": "spot_jelly_bloom"}, "length": "half"})
        scn = get(f"/api/expedition/scene?uid={uid}")
        adv(uid, 60 * 13)
        ret = get(f"/api/ark?uid={uid}")["expedition_return"]
        st = S.load_state(uid)
        for r in st["residents_list"]:
            r["injured"] = False
        S.save_state(uid, st)
        if ret and ret["discovered"]:
            found = True
            ok(ret["discovered"].get("pos") == (scn["discovers"] or {}).get("pos")
               and ret["discovered"]["pos"] in scn["waypoints"] and ret["discovered"]["pos"] != {"x": 0.0, "z": 0.0},
               f"discovered.pos {ret['discovered'].get('pos')} = 장면 discovers.pos (같은 좌표계, 경로 위)")
            break
    ok(found and S.spot_found(S.load_state(uid), uid, "spot_jelly_bloom"), f"단서 원정 {k + 1}번째에 발견(발견 확률 {pv['discover_p']})")
    sp = {x["id"]: x for x in get(f"/api/spots?uid={uid}")}
    ok(sp["spot_jelly_bloom"]["state"] == "found", "/api/spots state=found")
    opt = get(f"/api/expedition/options?uid={uid}")
    ok(any(d["dest"] == {"kind": "spot", "id": "spot_jelly_bloom"} for d in opt["dests"]), "이제 '아는 곳'으로 갈 수 있다")
    # 이전 저장: rumors_seen 의 1막 스팟은 발견으로 옮긴다
    uid2 = "dev_s15_spot_old"
    st = S.new_state(uid2)
    st["rumors_seen"] = ["spot_vent_garden"]
    st.pop("s15_spots_migrated", None)
    st["outside"] = ["ghost"]
    S.save_state(uid2, st)
    st = S.load_state(uid2)
    ok("spot_vent_garden" in st["spots_found"] and st["outside"] == [], "이전 저장: 찾은 스팟 유지, 옛 차출 outside 비움")


def t_lid_override():
    """덮개 보류 해제는 데이터(threats.json min_grade_override). 키가 없으면 지금처럼 보류."""
    saved = dict(CB.THR.get("min_grade_override") or {})
    CB.THR["min_grade_override"] = {}
    base = CB.min_grade("lid", residents=10)
    ok(base == CB.min_grade("lid"), f"override 없음 → 주민 수와 무관 (lid {base})")
    CB.THR.setdefault("min_grade_override", {})["lid"] = {"residents_at_least": 5, "min_grade": 4}
    try:
        ok(CB.min_grade("lid", residents=4) == base and CB.min_grade("lid", residents=5) == 4,
           "override 가 있으면 주민 5명부터 등급 4 로 돌아온다")
        hits = sum(1 for d in range(1, 300) if (CB.pick_creature(f"u{d}", d, 4, residents=6) or {}).get("id") == "lid")
        ok(hits > 0, f"주민 6명·등급 4 → 덮개가 나온다({hits}/299)")
    finally:
        CB.THR["min_grade_override"] = saved
    ov = saved.get("lid")
    if ov:
        ok(CB.min_grade("lid", residents=ov["residents_at_least"] - 1) > 5 and
           CB.min_grade("lid", residents=ov["residents_at_least"]) == ov["min_grade"],
           f"threats.json 실제 값: 주민 {ov['residents_at_least']}명부터 덮개 등급 {ov['min_grade']}")


def t_never():
    """죽음·못 돌아옴·장비 소멸·방 상실은 0(규칙). 원정 60번."""
    uid = "dev_s15_never"
    new_ark(uid, rooms=(("airlock", 3, 1),))
    st = S.load_state(uid)
    st["exp_count"] = 2
    S.save_state(uid, st)
    n0 = len(S.load_state(uid)["residents_list"])
    rooms0 = len(S.load_state(uid)["rooms"])
    inj = 0
    for k in range(60):
        st = S.load_state(uid)
        for r in st["residents_list"]:
            r["injured"] = False
        st["air"]["value"] = 99
        st["suits"]["shared_wear"] = [0, 0]
        st["guests"] = []
        S.save_state(uid, st)
        m = st["residents_list"][k % len(st["residents_list"])]["id"]
        post("/api/expedition/start", {"uid": uid, "members": [m], "dest": {"kind": "unknown"}, "length": "long"})
        adv(uid, 11 * 60)
        ret = get(f"/api/ark?uid={uid}")["expedition_return"]
        inj += bool(ret and ret["injured"])
    st = S.load_state(uid)
    ok(len(st["residents_list"]) == n0 and len(st["rooms"]) == rooms0 and not any(r.get("flooded") for r in st["rooms"])
       and st["expedition"] is None and not st["outside"] and len(st["suits"]["shared_wear"]) == 2,
       f"60번: 주민 {n0} 그대로, 방 그대로, 잠수복 둘 그대로, 모두 돌아옴 (부상 {inj})")


def t_a2_fixes():
    """S15-A2: 문장 묶음·recalled·상자 정본 갈래·actions 정수/기댓값·ark.entrance·options 500 회귀."""
    m = get("/api/text/moments")
    groups = [k for k in ("entrance", "guest", "expedition", "sealed_box", "spot") if k in m]
    ok(len(groups) == 5 and "shelf" in m, f"/api/text/moments 에 원정 문장 묶음 {groups} + 기존 ui_moments")
    # options 500(L.get) 회귀: expedition.json 의 '_' 주석 키가 규칙에 섞이지 않는다
    uid = "dev_s15_a2"
    new_ark(uid, rooms=(("airlock", 3, 1),))
    opt = get(f"/api/expedition/options?uid={uid}")
    ok(all(isinstance(v, dict) and v.get("minutes") for v in opt["lengths"].values()) and set(opt["lengths"]) == {"short", "half", "long"},
       f"options 200 · lengths 키 {sorted(opt['lengths'])} (주석 키 없음)")
    ok(all(not str(k).startswith("_") for k in (EX.g("lengths") or {})), "엔진이 읽는 표에 '_' 키 없음")
    a = get(f"/api/ark?uid={uid}")
    ok(isinstance(a.get("entrance"), dict) and a["entrance"].keys() == get(f"/api/entrance?uid={uid}").keys(),
       "/api/ark entrance = /api/entrance 와 같은 모양")
    st = S.load_state(uid)
    st["exp_count"] = 2
    S.save_state(uid, st)
    sc_ = who(uid, "scout")
    pv = post("/api/expedition/preview", {"uid": uid, "members": [sc_["id"]], "dest": {"kind": "door"}, "length": "half"})
    ok(isinstance(pv["actions"], int) and isinstance(pv["actions_expected"], float) and pv["actions"] <= pv["actions_expected"],
       f"preview actions {pv['actions']}(정수, 보장) · actions_expected {pv['actions_expected']}")
    # recalled
    post("/api/expedition/start", {"uid": uid, "members": [sc_["id"]], "dest": {"kind": "door"}, "length": "half"})
    adv(uid, 60)
    post("/api/expedition/recall", {"uid": uid})
    adv(uid, 21)
    ret = get(f"/api/ark?uid={uid}")["expedition_return"]
    ok(ret and ret["recalled"] is True, f"불러들인 원정 결과 recalled: {ret and ret['recalled']}")
    ok(ret and ret["line"] and "{" not in ret["line"] and (S.xt("expedition.log.recall") or "") in ret["line"],
       f"일지 한 줄 = 시나리오 조각: {ret and ret['line']}")
    # 상자 갈래: 정본 여덟 + blank 만(문 앞·모르는 쪽도)
    cats = set()
    for k in range(400):
        res = EX.roll(f"bc|{k}", members=[{"id": "a", "stats": {"hand": 5, "eye": 9, "breath": 9, "nerve": 5}}],
                      dest={"kind": "door"}, dest_cat="unknown", length="half", danger_mul=0.5, lingering=None,
                      learning=True, recent_cats=[], kinds_weights=None, rescue_p=0, clue_p=0, discover_p=0)
        for i in range(res["actions"]):
            it = EX.item_at(res, i, "dark")
            if it["kind"] == "box":
                cats.add(it["cat"])
    ok(cats and cats <= set(S.BOX_CATS), f"문 앞 상자 갈래 {sorted(cats)} ⊂ 정본")
    st = S.load_state(uid)
    st["boxes"] = [{"id": "box-old1", "cat": "any", "found_day": 1, "found_ts": 1, "from": "door"},
                   {"id": "box-old2", "cat": "unknown", "found_day": 1, "found_ts": 2, "from": "door"}]
    S.save_state(uid, st)
    bx = get(f"/api/boxes?uid={uid}")
    ok({b["cat"] for b in bx} <= set(S.BOX_CATS) and any(b["cat"] == "blank" for b in bx) and all(b["pattern"] for b in bx),
       f"옛 저장 상자 any/unknown → {[(b['cat'], b['pattern']) for b in bx]}")


def t_d2_values():
    """S15-D2: 잠자리 기본 4(거주실 없이 3일차 손님을 들인다) · 자동 갈림길 새 규칙 · 덮개 문턱 주민 수."""
    uid = "dev_s15_d2"
    new_ark(uid)
    adv(uid, 60 * 24 * 2)
    a = get(f"/api/ark?uid={uid}")
    ent = get(f"/api/entrance?uid={uid}")
    ok(a["day"] >= 3 and ent["guests"] and ent["beds"]["free"] >= 1, f"3일차 손님 + 거주실 없이 잠자리 {ent['beds']}")
    j = post("/api/entrance/guest", {"uid": uid, "guest_id": ent["guests"][0]["id"], "accept": True})
    ok(j["accepted"] and len(j["state"]["residents_list"]) == 4, "거주실 없이 첫 손님을 들인다 → 주민 4")
    F = EX.g("scene.fork")
    st = S.load_state(uid)
    st["boxes"] = []
    for m in F["auto_low_materials"]:
        st["resources"][m] = F["auto_low_stock"]
    ok(S.auto_fork_for(st) == "dark", "상자 대기 적고 재료 넉넉 → 어둠(상자)")
    st["resources"][F["auto_low_materials"][0]] = F["auto_low_stock"] - 1
    ok(S.auto_fork_for(st) == "lit", f"{F['auto_low_materials'][0]} < {F['auto_low_stock']} → 불빛(재료)")
    st["resources"][F["auto_low_materials"][0]] = 99
    st["boxes"] = [{"id": f"b{i}", "cat": "food", "found_day": 1} for i in range(F["auto_box_backlog"])]
    ok(S.auto_fork_for(st) == "lit", f"상자 대기 {F['auto_box_backlog']} → 불빛")
    # 덮개 문턱: 손님(들이지 않은)은 빼고, 원정 나간 주민은 센다
    ov = (CB.THR.get("min_grade_override") or {}).get("lid") or {}
    need = int(ov.get("residents_at_least", 6))
    st = S.load_state(uid)
    st["guests"] = []
    for k in range(need + 2):
        S.make_guest(st, uid, f"lidg{k}", "knock")
    base_r = st["residents_list"][0]
    while len(st["residents_list"]) < need - 1:
        st["residents_list"].append(dict(base_r, id=f"pad-{len(st['residents_list'])}"))
    st["residents_list"] = st["residents_list"][:need - 1]
    S.save_state(uid, st)
    seen = {}
    orig = CB.pick_creature
    def spy(uid_, day_, grade_, force=None, residents=None):
        seen["r"] = residents
        return orig(uid_, day_, grade_, force=force, residents=residents)
    CB.pick_creature = spy
    try:
        st = S.load_state(uid)
        st["expedition"] = {"members": [st["residents_list"][0]["id"]]}
        st["outside"] = [st["residents_list"][0]["id"]]
        S.ensure_raid(st, uid, reset=True)
    finally:
        CB.pick_creature = orig
    ok(seen.get("r") == need - 1, f"덮개 문턱에 넘긴 주민 수 {seen.get('r')} = 주민 {need - 1}(원정 1명 포함, 손님 {len(st['guests'])} 제외)")


TESTS = [t_full_loop, t_guests_never_leave, t_overnight, t_raid_absent, t_ev_equal, t_box_pry_and_scan_rules,
         t_air_suits, t_spots_clue_found, t_lid_override, t_never, t_a2_fixes, t_d2_values]

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
