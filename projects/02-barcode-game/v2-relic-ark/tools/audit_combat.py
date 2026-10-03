"""감사(audit) — 배치 방어 전투가 퍼즐인가, 체크리스트인가, 동전 던지기인가.

읽기 전용. 프로젝트 파일·DB 를 건드리지 않는다.
  - engine/combat.py 의 evaluate / pick_creature / pick_target / severity / need_for 를 **직접** 부른다.
  - server.py 를 import 해서 raid_ctx·roll_stats·grant_imprints·room_cap_of 같은 **순수 함수**만 쓴다
    (init_db·load_state·save_state·log 는 부르지 않는다 → relic_ark.db 에 쓰지 않는다).
  - 인자는 코드에서 읽은 이름 그대로(검수 규칙 마). 변수는 하나씩 움직인다(검수 규칙 바).

실행: python tools/audit_combat.py           (전체, 약 30~60초)
      python tools/audit_combat.py --quick   (30일 시뮬 방주 수를 줄인다)
결과는 표준출력.
"""
from __future__ import annotations

import copy
import io
import itertools
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "engine"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

with redirect_stdout(io.StringIO()):          # 기동 로그(1막 풀 장수 등)를 감춘다
    import server as S                         # noqa: E402  순수 함수만 쓴다
import combat as C                             # noqa: E402  (server 가 import 한 것과 같은 모듈 객체)

QUICK = "--quick" in sys.argv
THREATS = [cid for cid, c in C.CREATURES.items() if c["threat"]]
RES_ORDER = [C.HELD, C.PASSED, C.SCARRED, C.BREACHED]
KO = {C.HELD: "막음", C.PASSED: "넘김", C.SCARRED: "금", C.BREACHED: "상실"}


def hr(t):
    print("\n" + "=" * 100 + "\n" + t + "\n" + "=" * 100)


# ─────────────────────────────────────────────────────────────
# 합성 상태 — server.raid_ctx 가 읽는 키만 채운다
# ─────────────────────────────────────────────────────────────
def person(rid, role, nerve, imprints=(), injured=False, eye=5, name=None):
    return {"id": rid, "name": name or rid, "role": role, "injured": injured,
            "imprints": list(imprints), "crises": [],
            "stats": {"hand": 5, "eye": eye, "breath": 5, "nerve": nerve}}


def make_state(rooms, residents, stations=None, lights=None, power_on=True, room_tools=None, outside=None):
    return {"created": time.time() - 86400 * 3, "rooms": rooms, "residents_list": residents,
            "stations": dict(stations or {}), "lights": dict(lights or {}), "power_on": power_on,
            "room_tools": copy.deepcopy(room_tools or {}), "outside": list(outside or []),
            "hand": [{"id": "c1", "name": "카드"}], "resources": {}}


def evaluate_state(cid, st, slot, sev, grade, acts=(), moves=0, consumables=()):
    raid = {"target_slot": slot, "severity": sev, "grade": grade, "acts": list(acts), "moves": moves}
    ctx = S.raid_ctx(st, raid, list(consumables))
    return C.evaluate(C.CREATURES[cid], ctx), ctx


# 판정 표에 들어가는 한 방 — 슬롯 4(지하 2층, 60m)에 방 하나
def one_room_state(room_id, level, people, tools=(), light=True, power=True, gather_all=True,
                   extra_rooms=(), outside=()):
    rooms = [{"id": room_id, "slot": 4, "level": level}] + [
        {"id": rid, "slot": s, "level": 1} for rid, s in extra_rooms]
    st = make_state(rooms, people, stations={p["id"]: 4 for p in people if p["id"] not in outside},
                    lights={"4": light}, power_on=power,
                    room_tools={"4": [{"id": t, "uses": C.TOOLS[t].get("uses")} for t in tools
                                      if C.TOOLS[t]["kind"] in C.INSTALLED_KINDS]},
                    outside=outside)
    return st


# 생물마다 "올바른 관문 행동"을 상태로 옮기는 법(코드의 gate_state 를 읽고 그대로 만든 것)
def apply_gate(cid, st, slot, correct=True):
    """correct=True 면 관문을 맞추는 상태/행동, False 면 아무것도 안 한 기본 상태. (acts, moves) 반환."""
    g = C.CREATURES[cid]["gate"]
    acts, moves = [], 0
    if not correct:
        return acts, moves
    if g == "lights_off":
        st["lights"][str(slot)] = False
    elif g == "quiet":
        st["power_on"] = False                       # + 전원이 모두 한 방에 있어야 한다(호출자가 배치)
    elif g == "all_inside":
        st["outside"] = []
    elif g in ("light_elsewhere", "cloud_water", "make_way", "feed", "return_it", "guide_up"):
        acts = [C.action_for_gate(g)["id"]]
    return acts, moves


# ─────────────────────────────────────────────────────────────
# A0. 공식 상수 — 코드에서 읽은 값
# ─────────────────────────────────────────────────────────────
def section_constants():
    hr("A0. 판정 공식 상수 (engine/combat.py 가 defense.json·threats.json 에서 읽은 실제 값)")
    print(f"room_base={C.ROOM_BASE}  person=({C.W_NERVE_BASE}+{C.W_NERVE_STEP}*담) 부상x{C.HURT_MUL}  "
          f"affinity 강{C.W_AFF_STRONG}/약{C.W_AFF_WEAK}  imprint {C.W_IMPRINT}  tool cap {C.TOOL_CAP}")
    print(f"verdict pass={C.VERDICT_PASS}  fail={C.VERDICT_FAIL}  loss_shield={C.LOSS_SHIELD}")
    print("need_by_grade =", {g: C.need_for(C.CREATURES['longneck'], g, 0) for g in range(1, 6)},
          "(+creature_offset +severity)")
    print("MAX_TOOL_HANDS =", C.MAX_TOOL_HANDS)
    print("\n생물 | 관문 | min_grade | offset | 각인일치 | 친화 강/약(역할)")
    for cid in THREATS:
        c = C.CREATURES[cid]
        aff = C.ROLE_AFFINITY.get(cid, {})
        print(f"  {cid:13s} {c['gate']:15s} g{C.min_grade(cid)}  {C._num(C.THR.get('creature_offset') or {}, cid, 0):+.1f}  "
              f"{','.join(sorted(set(C.IMPRINT_MATCH.get(cid, [])) | set(c.get('imprints') or [])))}  "
              f"강:{','.join(aff.get('strong', {}))} 약:{','.join(aff.get('weak', {}))}")
    # 1막에서 실제로 얻을 수 있는 주민
    print("\n1막 실제 명단: new_state() 의 시작 3인 =", ["cook", "engineer", "scout"],
          "| 1막 사건 카드 중 주민을 늘리는 것:",
          [e["id"] for e in S.EVENTS.values() if 1 in (e.get("acts") or [])
           and "resident" in str(e.get("on_counter")) + str(e.get("on_fail"))] or "없음")
    covered = Counter()
    for cid in THREATS:
        for k in ("strong", "weak"):
            for role in (C.ROLE_AFFINITY.get(cid, {}).get(k) or {}):
                if role in ("cook", "engineer", "scout"):
                    covered[cid] += 1
    print("생물별 시작 3인 중 친화를 받는 사람 수:", dict(covered))


# ─────────────────────────────────────────────────────────────
# A1(a)(b). 생물 × 관문 × 배치 전수
# ─────────────────────────────────────────────────────────────
ACT1 = ("cook", "engineer", "scout")
BASE_NERVE = {r: S.STAT_BASE[r]["nerve"] for r in S.STAT_BASE}


def act1_people(imprint_n=0, nerves=None, roles=ACT1, cid=None):
    imps = sorted(set(C.IMPRINT_MATCH.get(cid, [])) | set(C.CREATURES[cid].get("imprints") or []))[:1] if cid else []
    out = []
    for i, r in enumerate(roles):
        nv = (nerves or {}).get(r, BASE_NERVE[r])
        out.append(person(f"{r}{i}", r, nv, imps if i < imprint_n else []))
    return out


def best_tools_for(cid):
    """그 생물에게 점수가 가장 큰 도구 조합(상한 3.0 안). 관문 도구(덧문·가리개·등불)는 점수가 작다."""
    pool = ["patch", "long_net", "brace", "shutter", "lure_lamp", "hush", "beacon"]
    best, bs = (), -1
    for k in range(0, 4):
        for combo in itertools.combinations(pool, k):
            s = min(sum(C.tool_power(t, cid) for t in combo), C.TOOL_CAP)
            if s > bs:
                best, bs = combo, s
    return best, bs


def fast_ctx(cid, rid, lvl, cap, ppl, tools, sev, grade):
    """server.raid_ctx 와 같은 키·같은 의미를 직접 채운다(전수 열거 속도용). 관문은 '맞춤' 상태.
    동등성은 check_fast_ctx() 가 표본으로 raid_ctx 와 대조한다."""
    g = C.CREATURES[cid]["gate"]
    inst = [t for t in tools if C.TOOLS[t]["kind"] in C.INSTALLED_KINDS]
    cons = [t for t in tools if C.TOOLS[t]["kind"] in C.CARRY_KINDS]
    act = C.action_for_gate(g)
    return {"room_id": rid, "room_level": lvl, "room_cap": cap, "people": ppl,
            "light_on": g != "lights_off", "forced_dark": False, "power_on": g != "quiet",
            "gathered_one_room": True, "hushed": False, "outside": [], "installed": inst,
            "consumables": cons, "hands": sum(int(C.TOOLS[t].get("hands", 0)) for t in tools),
            "severity": sev, "grade": grade, "acts": [act["id"]] if act else [], "moves": 0,
            "lure_elsewhere": False}


def check_fast_ctx():
    """fast_ctx 가 raid_ctx 와 같은 판정을 내는지 표본 대조(측정을 먼저 의심한다 — 규칙 가)."""
    bad = 0; n = 0
    for cid in THREATS:
        for lvl in (1, 3):
            for k in (1, 3):
                ppl = act1_people(1, cid=cid)[:k]
                st = one_room_state("quarters", lvl, copy.deepcopy(ppl), tools=("brace",),
                                    extra_rooms=[("well", 1), ("pantry", 2)])
                acts, mv = apply_gate(cid, st, 4, True)
                a, _ = evaluate_state(cid, st, 4, 1, 3, acts, mv)
                fp = [{"name": p["id"], "role": p["role"], "nerve": p["stats"]["nerve"], "injured": False,
                       "imprints": p["imprints"]} for p in ppl]
                b = C.evaluate(C.CREATURES[cid], fast_ctx(cid, "quarters", lvl, 4, fp, ("brace",), 1, 3))
                n += 1
                bad += (a["result"], a["score"]) != (b["result"], b["score"])
    print(f"  [검증] fast_ctx vs server.raid_ctx 표본 {n}개 중 불일치 {bad}개")


def enumerate_space():
    check_fast_ctx()
    hr("A1(a). 생물 × 등급 × 세기 × 배치 전수 — 이기는 배치가 몇 가지인가")
    print("배치 공간: 대상 방(정원 2/3/4) × 방 레벨 1~3 × 사람(8역할 중복조합, 정원까지, 담=역할 기본값) "
          "× 각인 0..n × 도구(점수 도구 0~3개 조합) — 관문은 '맞춤'으로 고정(관문 실패는 held 불가가 규칙).")
    roles8 = list(S.STAT_BASE.keys())
    tool_pool = ["patch", "long_net", "brace"]
    tool_sets = [c for k in range(0, 4) for c in itertools.combinations(tool_pool, k)]
    rooms = {2: "well", 3: "generator", 4: "quarters"}
    summary = []
    for cid in THREATS:
        for grade in range(max(1, C.min_grade(cid)), 6):
            for sev in (0, 1, 2):
                tot = win = 0
                win_people_n = Counter()
                min_people_win = None
                act1_wins = 0; act1_tot = 0
                for cap, rid in rooms.items():
                    for lvl in (1, 2, 3):
                        for n in range(0, cap + 1):
                            for combo in itertools.combinations_with_replacement(roles8, n):
                                for imp_n in sorted({0, min(1, n), n}):
                                    ppl = [{"name": f"p{i}", "role": r, "nerve": BASE_NERVE[r], "injured": False,
                                            "imprints": (sorted(C.IMPRINT_MATCH.get(cid, []))[:1] if i < imp_n else [])}
                                           for i, r in enumerate(combo)]
                                    for ts in tool_sets:
                                        ctx = fast_ctx(cid, rid, lvl, cap, ppl, ts, sev, grade)
                                        ev = C.evaluate(C.CREATURES[cid], ctx)
                                        tot += 1
                                        ok = ev["result"] in (C.HELD, C.PASSED)
                                        if ok:
                                            win += 1
                                            win_people_n[n] += 1
                                            min_people_win = n if min_people_win is None else min(min_people_win, n)
                                        is_act1 = set(combo) <= set(ACT1) and len(set(combo)) == len(combo)
                                        if is_act1:
                                            act1_tot += 1; act1_wins += ok
                summary.append((cid, grade, sev, tot, win, min_people_win, act1_tot, act1_wins))
    print("\n생물          등급 세기 | 전체 배치  이김   비율 | 이기는 최소 인원 | 1막 명단(요리사·기술자·정찰병 부분집합)만: 배치 이김 비율")
    for cid, g, sev, tot, win, mn, a1t, a1w in summary:
        print(f"  {cid:13s} g{g} s{sev} | {tot:7d} {win:6d} {win / tot:6.1%} | {('-' if mn is None else mn):>3} "
              f"| {a1w:5d}/{a1t:<5d} {a1w / max(1, a1t):6.1%}")
    return summary


def stage_scenarios():
    hr("A1(b). 1일 / 7일 / 30일 자원 수준에서 이길 수 없는 / 공짜로 이기는 생물")
    print("1막 명단은 3인 고정(요리사·기술자·정찰병, 담=역할 기본값 5/4/5). 단계 가정은 threats.json map·economy target_curve 에서:")
    print("  D1 = 등급1·방Lv1·각인0·도구0 | D7 = 등급2·방Lv1·각인1(일치)·보강대 1(대상 방이면) | "
          "D30 = 등급4·방Lv2·각인3·도구 상한3.0 (대상 방에 있을 때) / 등급5 도 함께")
    print("  '최선' = 3인 전원 대상 방 + 관문 맞춤 + 그 방 도구 최대. '게으름' = 전원 홀, 아무 조작 없음.")
    print("  (설계 의도 명단: target_curve 5명@7일·10명@30일 — 비교용으로 정원까지 채운 '설계 명단'도 계산)")
    stages = [
        ("D1", 1, 1, 0, ()),
        ("D7", 2, 1, 1, ("brace",)),
        ("D30-g4", 4, 2, 3, ("brace", "long_net")),
        ("D30-g5", 5, 2, 3, ("brace", "long_net")),
    ]
    rows = []
    for label, grade, lvl, imp_n, tools in stages:
        for cid in THREATS:
            if C.min_grade(cid) > grade:
                continue
            for sev in (0, 1, 2):
                # 최선(1막 명단). 정원 4 방(quarters). 각인은 그 생물에 맞는 것을 imp_n 명이 가진다
                ppl = act1_people(imp_n, cid=cid)
                st = one_room_state("quarters", lvl, ppl, tools=tools, extra_rooms=[("well", 1), ("pantry", 2)])
                acts, mv = apply_gate(cid, st, 4, True)
                cons = ["patch"] if (cid == "swarm" and tools) else []      # 패치는 공방이 있어야 만든다
                if C.CREATURES[cid]["gate"] == "guide_up":      # 등을 켤 사람 하나는 홀에 남아야 한다
                    st["stations"].pop(ppl[-1]["id"], None)
                best, _ = evaluate_state(cid, st, 4, sev, grade, acts, mv, cons)
                # 설계 명단: 정원까지 친화 강 역할로 채움
                strong = list((C.ROLE_AFFINITY.get(cid, {}).get("strong") or {}).keys())
                fill = (strong + ["trader", "farmer", "scout", "cook"])[:4]
                ppl2 = [person(f"d{i}", r, BASE_NERVE[r]) for i, r in enumerate(fill)]
                for i in range(min(imp_n, len(ppl2))):
                    ppl2[i]["imprints"] = sorted(set(C.IMPRINT_MATCH.get(cid, [])))[:1]
                st2 = one_room_state("quarters", lvl, ppl2, tools=tools, extra_rooms=[("well", 1), ("pantry", 2)])
                acts2, mv2 = apply_gate(cid, st2, 4, True)
                design, _ = evaluate_state(cid, st2, 4, sev, grade, acts2, mv2, cons)
                # 게으름: 전원 홀(배치 0), 불 켜짐, 전원 켜짐, 행동 없음. 손톱이면 홀 사람 1~2명이 밖
                ppl3 = act1_people(imp_n, cid=cid)
                st3 = one_room_state("quarters", lvl, ppl3, tools=tools, extra_rooms=[("well", 1), ("pantry", 2)])
                st3["stations"] = {}
                if C.CREATURES[cid]["gate"] == "all_inside":
                    st3["outside"] = [ppl3[0]["id"]]
                lazy, _ = evaluate_state(cid, st3, 4, sev, grade)
                rows.append((label, cid, sev, best, design, lazy))
    print("\n단계   생물          세기 | 최선(1막 3인): 점수/필요 → 결과 | 설계 명단(정원 4): 결과 | 게으름(홀): 점수/필요 → 결과")
    for label, cid, sev, b, d, l in rows:
        print(f"  {label:7s}{cid:13s} s{sev} | {b['score']:5.1f}/{b['need']:<5.1f} → {KO[b['result']]:3s}"
              f"{'(보호)' if b.get('shielded') else '':5s}| {KO[d['result']]:3s} {d['score']:5.1f} "
              f"| {l['score']:4.1f}/{l['need']:<5.1f} → {KO[l['result']]}{'(보호)' if l.get('shielded') else ''}")
    # 요약
    print("\n요약:")
    for label in ("D1", "D7", "D30-g4", "D30-g5"):
        rs = [r for r in rows if r[0] == label]
        unwin = sorted({f"{r[1]}s{r[2]}" for r in rs if r[3]["result"] not in (C.HELD, C.PASSED)})
        free = sorted({f"{r[1]}s{r[2]}" for r in rs if r[5]["result"] in (C.HELD, C.PASSED)})
        lazy_breach = sorted({f"{r[1]}s{r[2]}" for r in rs if r[5]["result"] == C.BREACHED})
        print(f"  {label}: 최선으로도 못 막는 칸 {len(unwin)}/{len(rs)} {unwin}")
        print(f"         게으름이 그냥 막는/넘기는 칸 {len(free)}/{len(rs)} {free}")
        print(f"         게으름이 방을 잃는 칸 {len(lazy_breach)}/{len(rs)}")
    return rows


# ─────────────────────────────────────────────────────────────
# A1(c). 민감도 — 하나만 움직인다
# ─────────────────────────────────────────────────────────────
def sensitivity():
    hr("A1(c). 민감도 — 기준 배치에서 변수 하나만 최소→최대로 (관문 맞춤 고정)")
    print("기준: 정원 4 방(거주실) Lv1, 친화 없는 역할(학자/아이 제외한 '무관' 역할) 3명 담5, 각인0, 도구0, 등급3 세기1")
    neutral = "scholar"     # 학자는 대부분 생물에 강이 없다 → 친화 0 이 나오는 칸만 쓰도록 아래에서 거른다

    def base_people(n=3, nerve=5, aff_role=None, aff_n=0, imp=0, cid=None):
        out = []
        for i in range(n):
            role = aff_role if (aff_role and i < aff_n) else "_none"
            p = person(f"p{i}", role, nerve)
            if i < imp:
                p["imprints"] = sorted(set(C.IMPRINT_MATCH.get(cid, [])) | set(C.CREATURES[cid].get("imprints") or []))[:1]
            out.append(p)
        return out

    variables = {
        "담(전원 1→10)":       lambda cid: (base_people(3, 1, cid=cid), base_people(3, 10, cid=cid), {}, {}),
        "인원(1→4)":           lambda cid: (base_people(1, cid=cid), base_people(4, cid=cid), {}, {}),
        "친화(없음→강 3명)":    lambda cid: (base_people(3, cid=cid),
                                            base_people(3, aff_role=next(iter(C.ROLE_AFFINITY[cid]['strong'])), aff_n=3, cid=cid), {}, {}),
        "친화(없음→약 1명)":    lambda cid: (base_people(3, cid=cid),
                                            base_people(3, aff_role=next(iter(C.ROLE_AFFINITY[cid]['weak'])), aff_n=1, cid=cid), {}, {}),
        "각인(0→3명)":         lambda cid: (base_people(3, cid=cid), base_people(3, imp=3, cid=cid), {}, {}),
        "도구(0→상한)":         lambda cid: (base_people(3, cid=cid), base_people(3, cid=cid), {}, {"tools": ("brace", "long_net")}),
        "방 레벨(1→3)":         lambda cid: (base_people(3, cid=cid), base_people(3, cid=cid), {"lvl": 1}, {"lvl": 3}),
        "부상(0→3명)":          lambda cid: ([dict(p, injured=True) for p in base_people(3, cid=cid)], base_people(3, cid=cid), {}, {}),
    }
    print("\n변수                | Δ점수(평균) | 결과가 바뀐 칸 / 전체 (생물11 × 등급1~5 × 세기0~2, 관문 맞춤)")
    for name, fn in variables.items():
        deltas, flips, cells = [], 0, 0
        for cid in THREATS:
            if C.CREATURES[cid]["gate"] == "quiet":
                continue                      # 문지기는 관문 통과 시 점수와 무관하게 passed
            lo_p, hi_p, lo_o, hi_o = fn(cid)
            for grade in range(1, 6):
                for sev in (0, 1, 2):
                    res = []
                    for ppl, o in ((lo_p, lo_o), (hi_p, hi_o)):
                        st = one_room_state("quarters", o.get("lvl", 1), copy.deepcopy(ppl),
                                            tools=o.get("tools", ()), extra_rooms=[("well", 1), ("pantry", 2)])
                        acts, mv = apply_gate(cid, st, 4, True)
                        ev, _ = evaluate_state(cid, st, 4, sev, grade, acts, mv)
                        res.append(ev)
                    deltas.append(res[1]["score"] - res[0]["score"])
                    cells += 1
                    flips += res[0]["result"] != res[1]["result"]
        print(f"  {name:18s} | {statistics.mean(deltas):+6.2f}     | {flips:3d}/{cells} ({flips / cells:.0%})")
    print("\n참고 — 같은 '+1.5' 가 어디서 오나: 사람 1명(담5)=1.0, 강 친화 1명=+1.5, 각인 1개=+1.5, 도구 1개=+1.5, 방 Lv1→3=+1.0.")
    print("담은 1→10 전체 폭이 사람당 0.9 → 3명이 다 바꿔도 2.7. 한 명의 담 특이점(±2)은 0.2.")


# ─────────────────────────────────────────────────────────────
# A1(d). 역전의 날 — 먼저 배운 정답이 오답이 되는가
# ─────────────────────────────────────────────────────────────
def reversal():
    hr("A1(d). 역전의 날 (거울눈·덮개) — 최적해가 실제로 바뀌는가, 화면이 미리 말하는가")
    ppl = act1_people(0, cid="longneck")
    for grade in (3, 4):
        for sev in (0, 1):
            # 긴목의 정답 상태 = 그 방 불 끄기 + 전원 대상 방
            st = one_room_state("quarters", 1, copy.deepcopy(ppl), extra_rooms=[("well", 1), ("pantry", 2)])
            st["lights"]["4"] = False
            ln, _ = evaluate_state("longneck", st, 4, sev, grade)
            me, ctx = evaluate_state("mirror_eye", st, 4, sev, grade)
            # 거울눈의 정답 = 불 켜고 + 다른 방 등불(행동)
            st2 = one_room_state("quarters", 1, copy.deepcopy(ppl), extra_rooms=[("well", 1), ("pantry", 2)])
            me2, _ = evaluate_state("mirror_eye", st2, 4, sev, grade, acts=["light_elsewhere"])
            ln2, _ = evaluate_state("longneck", st2, 4, sev, grade, acts=["light_elsewhere"])
            print(f"  g{grade} s{sev}: [불 끔] 긴목 {KO[ln['result']]} / 거울눈 {KO[me['result']]}"
                  f"   [불 켬+반대쪽 등불] 거울눈 {KO[me2['result']]} / 긴목 {KO[ln2['result']]}")
    print("  거울눈 관문 문장(불 끈 상태에서 화면 미리보기에 그대로 뜨는 글):", ctx and C.gate_state(C.CREATURES['mirror_eye'], ctx)["ko"])
    # 덮개
    print()
    for grade in (4, 5):
        for sev in (0, 1):
            st = one_room_state("quarters", 1, copy.deepcopy(act1_people(0, cid='lid')),
                                extra_rooms=[("well", 1), ("pantry", 2)])
            still, _ = evaluate_state("lid", st, 4, sev, grade, moves=0)
            moved, ctx = evaluate_state("lid", st, 4, sev, grade, moves=1)
            st_e = one_room_state("quarters", 1, copy.deepcopy(act1_people(0, cid='lid')),
                                  extra_rooms=[("well", 1), ("pantry", 2)])
            st_e["stations"] = {}
            empty, _ = evaluate_state("lid", st_e, 4, sev, grade, moves=0)
            print(f"  덮개 g{grade} s{sev}: 3인이 원래 그 방에 있고 안 움직임 → {KO[still['result']]} "
                  f"({still['score']}/{still['need']}) | 한 번이라도 옮김 → {KO[moved['result']]} "
                  f"| 대상 방이 원래 비어 있고 안 움직임 → {KO[empty['result']]} ({empty['score']}/{empty['need']})")
    print("  덮개 관문 문장:", C.gate_state(C.CREATURES['lid'], {"moves": 1})["ko"])
    # 덮개 = 서 있던 자리 운. 대상 방은 pick_target 이 살아 있는 방 중 균등 추첨
    print("\n  덮개는 '움직이지 않는다'가 관문이므로 결과는 **습격 전 서 있던 배치**가 정한다. 대상 방은 균등 추첨 →")
    for n_rooms in (6, 8, 10):
        for occupied in (1, 2, 3):
            print(f"    살아 있는 방 {n_rooms}칸, 사람이 서 있는 방 {occupied}칸: 대상이 빈 방일 확률 "
                  f"{(n_rooms - occupied) / n_rooms:.0%}")
    print("  (빈 방 + 등급4 이상 = 점수 1.0~2.0 대 필요 7.5~9.5 → 상실. 1막 3인으로 방 10칸 중 3칸 이상을 지킬 수 없다)")


# ─────────────────────────────────────────────────────────────
# A1(e). 미리보기 — 몇 번 만에 정답을 찾는가, 결과가 불확실한 적이 있는가
# ─────────────────────────────────────────────────────────────
def preview_steps():
    hr("A1(e). 미리보기와 '해 보고 → 보고 → 고치기' 횟수")
    print("결과 미리보기 = server.raid_public → ready.{gate.ko, score, need, would, parts}. 판정은 evaluate 하나, 난수 없음.")
    print("정답까지 필요한 최소 조작(API 호출) — 시작: 전원 홀(게으름), 불 켜짐, 전원 켜짐. 1막 3인.")
    rows = []
    for cid in THREATS:
        g = C.CREATURES[cid]["gate"]
        moves = 0 if g == "stand_still" else 3          # 정원 4 방이면 3인 다 옮긴다(station 3회)
        gate_ops = {"people": 0, "lights_off": 1, "quiet": 2, "all_inside": 1, "light_elsewhere": 1,
                    "cloud_water": 1, "stand_still": 0, "make_way": 1, "feed": 1, "return_it": 1,
                    "guide_up": 1}[g]
        restore = {"lights_off": 1, "quiet": 1}.get(g, 0)      # 끝나고 불·전원 되돌리기
        if g == "guide_up":
            moves = 2                                   # 한 사람은 홀에 남아야 한다
        rows.append((cid, g, moves, gate_ops, restore))
        print(f"  {cid:13s} {g:15s} 옮기기 {moves} + 관문 {gate_ops} (+되돌리기 {restore}) = {moves + gate_ops + restore}회")
    print("\n불확실성의 원천(코드에서 찾은 것 전부):")
    eyes = []
    for i in range(2000):
        uid = f"audit{i}"
        best = max(S.roll_stats(uid, f"{r}-{i}", r)[0]["eye"] for r in ACT1)
        eyes.append(best)
    p8 = sum(e >= S.EYE_EARLY for e in eyes) / len(eyes)
    print(f"  ① 소리 단계에는 대상 방이 숨겨진다(눈 {S.EYE_EARLY} 이상인 사람이 있으면 보임). "
          f"1막 3인 중 최고 눈 ≥{S.EYE_EARLY} 인 방주 비율 = {p8:.0%} (roll_stats 2000 방주). "
          "실루엣 단계로 넘기면 누구나 보인다 → 덮개 외에는 비용 없는 정보.")
    print("  ② 미리보기는 소모품(봉합 패치·귀환 신호기)을 넣지 않고 계산한다(raid_public→raid_ctx(st, raid) 소모품 없음) "
          "→ 패치를 쓰면 실제가 미리보기보다 좋다. 나빠지는 쪽은 없다.")
    print("  ③ 그 밖에 판정 뒤에 굴리는 난수 없음(resolve_raid: evaluate → 결과). 대상·세기·생물은 uid|day 시드로 습격 생성 시 고정.")
    print("  → 실루엣 단계 이후 결과는 **한 번도 불확실하지 않다**. 미리보기의 would 가 곧 결과다.")


# ─────────────────────────────────────────────────────────────
# A2. 30일 시뮬레이션 — 성실(greedy) vs 게으름(lazy)
# ─────────────────────────────────────────────────────────────
BUILD_PLAN = [  # (day, room_id, slot) — threats.json map 의 typical day 에 맞춘 보통 플레이어 증축 순서
    (1, "pantry", 2), (1, "quarters", 3), (1, "well", 1),
    (4, "storage", 0),
    (6, "workshop", 4),       # 60m → 등급 2
    (9, "generator", 5),
    (13, "greenhouse", 6),    # 120m → 등급 3
    (17, "infirmary", 7),
    (22, "airlock", 8),       # 180m → 등급 4
    (28, "decoder", 9),       # 방 10칸 → 등급 5
]
LEVEL_PLAN = [(14, "quarters", 2), (18, "storage", 2), (24, "well", 2), (26, "pantry", 2)]
TOOL_PLAN = [(8, "brace"), (12, "long_net"), (15, "shutter"), (18, "hush"), (20, "lure_lamp")]


def sim_one(uid, policy, days=30):
    """policy: greedy / lazy_hall / lazy_spread. 같은 uid 면 같은 생물·대상·세기를 받는다(시드 공유)."""
    rng_res = []
    for i, r in enumerate(ACT1):
        stats, _ = S.roll_stats(uid, f"{r}-{i}", r)
        p = person(f"{r}-{i}", r, stats["nerve"], eye=stats["eye"], name=r)
        p["stats"] = stats
        rng_res.append(p)
    st = make_state([], rng_res)
    st["created"] = time.time() - 86400 * days
    install_room = "pantry"
    tools_owned = Counter()
    log = []
    severity_debt = 0
    spent = Counter()
    for day in range(1, days + 1):
        for d, rid, slot in BUILD_PLAN:
            if d == day and not S.room_at(st, slot):
                st["rooms"].append({"id": rid, "slot": slot, "level": 1})
        for d, rid, lv in LEVEL_PLAN:
            if d == day:
                for r in st["rooms"]:
                    if r["id"] == rid and not r.get("flooded"):
                        r["level"] = lv
        for d, t in TOOL_PLAN:
            if d == day:
                slot = next((r["slot"] for r in S.live_rooms(st) if r["id"] == install_room), None)
                if slot is not None and policy != "lazy_hall_notools":
                    st["room_tools"].setdefault(str(slot), []).append({"id": t, "uses": C.TOOLS[t].get("uses")})
        if day % 4 == 0:
            tools_owned["patch"] += 1
        if day == 10:
            tools_owned["beacon"] += 1
        # 서 있는 자리(습격 전)
        pantry = next((r["slot"] for r in S.live_rooms(st) if r["id"] == "pantry"), None)
        if policy == "greedy":
            home = pantry if pantry is not None else (S.live_rooms(st) or [{"slot": None}])[0]["slot"]
            st["stations"] = {p["id"]: home for p in st["residents_list"]} if home is not None else {}
        elif policy == "lazy_spread":
            if day == 1:
                st["stations"] = {st["residents_list"][0]["id"]: 2, st["residents_list"][1]["id"]: 3,
                                  st["residents_list"][2]["id"]: 1}
            for rid, s in list(st["stations"].items()):        # 물 찬 방에 있던 사람은 홀로(server 와 같다)
                if (S.room_at(st, s) or {}).get("flooded"):
                    st["stations"].pop(rid)
        else:
            st["stations"] = {}
        st["lights"] = {}; st["power_on"] = True; st["outside"] = []
        grade = S.grade_of(st)
        cre = C.pick_creature(uid, day, grade)
        if not cre:
            log.append((day, grade, None, None, None)); continue
        if not cre["threat"]:
            log.append((day, grade, cre["id"], C.PASSED, 0)); continue
        slot = C.pick_target(uid, day, cre, S.live_rooms(st), st.get("room_tools") or {})
        if slot is None:
            log.append((day, grade, cre["id"], "diverted", 0)); continue
        sev = max(0, min(4, C.severity(uid, day, grade) + severity_debt)); severity_debt = 0
        if cre["gate"] == "all_inside":
            st["outside"] = S.send_outside(st, uid, day)
        acts, moves, cons = [], 0, []
        if policy == "greedy":
            g = cre["gate"]
            cap = S.room_cap_of(S.room_at(st, slot))
            if g == "all_inside":
                st["outside"] = []                             # /api/ark/recall (공짜)
            if g == "quiet":
                # 문지기는 '모두 한 방 + 전원 내림'이면 대상과 무관하게 넘긴다 → 가장 넓은 방에 모은다
                big = max(S.live_rooms(st), key=lambda r: S.room_cap_of(r))
                st["stations"] = {p["id"]: big["slot"] for p in st["residents_list"]}
            elif g != "stand_still":
                movers = list(st["residents_list"])
                keep_hall = 1 if g == "guide_up" else 0
                placed = 0
                for p in movers:
                    if placed < cap and len(movers) - placed > keep_hall:
                        if st["stations"].get(p["id"]) != slot:
                            moves += 1
                        st["stations"][p["id"]] = slot; placed += 1
                    else:
                        st["stations"].pop(p["id"], None)
            if g == "lights_off":
                st["lights"][str(slot)] = False
            if g == "quiet":
                st["power_on"] = False
            if g in ("light_elsewhere", "cloud_water", "make_way", "feed", "return_it", "guide_up"):
                a = C.action_for_gate(g)["id"]
                acts = [a]
                for k, v in C.action_cost(a, sev).items():
                    spent[k] += v
                if a == "return_it":
                    spent["relic_card"] += 1
                if a == "make_way":
                    lost = st["room_tools"].pop(str(slot), [])
                    spent["tools_lost"] += len(lost)
                if a == "guide_up":
                    severity_debt += 1
            if cre["id"] == "swarm" and tools_owned["patch"] > 0:
                cons = ["patch"]; tools_owned["patch"] -= 1
            moves = 0 if g != "stand_still" else 0            # 덮개 외에는 이동 수가 관문에 안 쓰인다
        raid = {"target_slot": slot, "severity": sev, "grade": grade, "acts": acts, "moves": moves}
        ctx = S.raid_ctx(st, raid, cons)
        ev = C.evaluate(cre, ctx)
        res = ev["result"]
        room = S.room_at(st, slot)
        if res == C.BREACHED and room:
            room["flooded"] = True
            st["room_tools"].pop(str(slot), None)
            for pid, s in list(st["stations"].items()):
                if s == slot:
                    st["stations"].pop(pid)
        # 각인(서버와 같은 규칙: 대상 방 사람 최대 2, 없으면 홀 1)
        flags = list(cre.get("hold_flags") or []) if res in (C.HELD, C.PASSED) else (
            list(cre.get("breach_flags") or []) if res == C.BREACHED else [])
        if flags:
            here = [p for p in st["residents_list"] if st["stations"].get(p["id"]) == slot][:2] \
                or [p for p in st["residents_list"] if p["id"] not in st["stations"]][:1]
            with redirect_stdout(io.StringIO()):
                S.grant_imprints(st, None, flags, here)
        log.append((day, grade, cre["id"], res, ev["margin"]))
    return log, st, spent


def sim_30():
    hr("A2. 30일 습격 시뮬레이션 — 성실 vs 게으름 (같은 uid = 같은 생물·대상·세기, 정책만 다르다)")
    print("증축 순서(두 정책 동일):", BUILD_PLAN)
    print("레벨업:", LEVEL_PLAN, "| 도구(식량창고에 설치):", TOOL_PLAN, "| 패치 4일에 1개(성실만 사용)")
    print("정책: greedy = 실루엣에서 3인 전원 대상 방 + 관문 행동/토글 + 끝나면 되돌림, 평소엔 전원 식량창고"
          " | lazy_hall = 아무도 배치 안 함, 아무 조작 없음 | lazy_spread = 1일차에 한 명씩 세 방, 그 뒤로 손대지 않음")
    n = 120 if QUICK else 400
    agg = {}
    per_grade = {}
    rooms_lost = {}
    imprints = {}
    spent_tot = {}
    by_creature = {}
    for pol in ("greedy", "lazy_spread", "lazy_hall"):
        cnt = Counter(); pg = defaultdict(Counter); lost = []; imps = []; sp = Counter(); bc = defaultdict(Counter)
        for i in range(n):
            log, st, spent = sim_one(f"sim{i}", pol)
            for day, grade, cid, res, m in log:
                if cid is None:
                    cnt["조용(아무것도 안 옴)"] += 1; continue
                if not C.CREATURES[cid]["threat"]:
                    cnt["조용(문어·그늘·울음)"] += 1; continue
                if res == "diverted":
                    cnt["딴 데로(유인 등불)"] += 1; continue
                cnt[res] += 1; pg[grade][res] += 1; bc[cid][res] += 1
            lost.append(sum(1 for r in st["rooms"] if r.get("flooded")))
            imps.append(sum(len(p.get("imprints") or []) for p in st["residents_list"]))
            sp.update(spent)
        agg[pol] = cnt; per_grade[pol] = pg; rooms_lost[pol] = lost; imprints[pol] = imps
        spent_tot[pol] = {k: v / n for k, v in sp.items()}; by_creature[pol] = bc
    print(f"\n방주 {n}개 × 30일. 습격 결과 분포(위협이 실제로 접촉한 것만):")
    print("정책          | 막음   넘김   금     상실   | 위협 수/방주 | 30일 뒤 잃은 방(평균, 최대) | 각인 수(평균)")
    for pol in agg:
        c = agg[pol]; tot = sum(c[r] for r in RES_ORDER)
        print(f"  {pol:12s}| " + " ".join(f"{c[r] / tot:6.1%}" for r in RES_ORDER) +
              f" | {tot / n:5.2f}      | {statistics.mean(rooms_lost[pol]):.2f}, {max(rooms_lost[pol])}"
              f"                   | {statistics.mean(imprints[pol]):.2f}")
    print("\n그 밖의 날(방주당 30일 중 평균):", {k: round(v / n, 2) for k, v in agg["greedy"].items()
                                          if k not in RES_ORDER})
    print("\n등급별 (막음/넘김/금/상실 %):")
    for pol in agg:
        for g in sorted(per_grade[pol]):
            c = per_grade[pol][g]; tot = sum(c.values())
            print(f"  {pol:12s} g{g} (n={tot:4d}): " + " / ".join(f"{c[r] / tot * 100:4.0f}" for r in RES_ORDER))
    print("\n생물별 — 성실 vs 게으름(lazy_spread) 막음+넘김 비율:")
    for cid in THREATS:
        a = by_creature["greedy"][cid]; b = by_creature["lazy_spread"][cid]; h = by_creature["lazy_hall"][cid]
        ta, tb, th = sum(a.values()), sum(b.values()), sum(h.values())
        if ta == 0:
            print(f"  {cid:13s} (30일 안에 안 옴)"); continue
        f = lambda c, t: (c[C.HELD] + c[C.PASSED]) / t if t else 0
        fl = lambda c, t: c[C.BREACHED] / t if t else 0
        print(f"  {cid:13s} n={ta:4d} | 성실 {f(a, ta):5.0%} 상실 {fl(a, ta):4.0%} | 펼친 게으름 {f(b, tb):5.0%} 상실 {fl(b, tb):4.0%}"
              f" | 홀 게으름 {f(h, th):5.0%} 상실 {fl(h, th):4.0%}")
    print("\n성실한 플레이어가 30일간 관문 행동에 쓴 자원(방주당 평균):", spent_tot["greedy"])
    print("비교: threats.json rewards._scale_check — 보통 플레이어 하루 스캔 수입 ≈ 34 → 30일 ≈ 1,020")


def tradeoff_check():
    hr("A2-추가. 성실한 플레이어에게 '진짜 거래'가 있는가 — 방어가 생산을 깎는가 (server.tick_production 실측)")
    base_rooms = [{"id": "pantry", "slot": 2, "level": 1}, {"id": "well", "slot": 1, "level": 1},
                  {"id": "greenhouse", "slot": 4, "level": 1}]
    ppl = [person("a", "cook", 5), person("b", "engineer", 4), person("c", "scout", 5)]

    def produce(stations, lights=None, power=True, elapsed_h=8.0):
        st = make_state(copy.deepcopy(base_rooms), copy.deepcopy(ppl), stations=stations, lights=lights, power_on=power)
        st["resources"] = {k: 0 for k in ("food", "water", "med", "power", "parts", "morale", "cloth", "trade", "knowledge", "scrap", "chem")}
        st["blueprint_progress"] = 0
        st["last_tick"] = time.time() - elapsed_h * 3600
        with redirect_stdout(io.StringIO()):
            out = S.tick_production(st)
        return out
    print("  8시간 생산 — 전원 홀:", produce({}))
    print("  8시간 생산 — 3인 전원 식량창고:", produce({"a": 2, "b": 2, "c": 2}))
    print("  8시간 생산 — 한 명씩 생산 방:", produce({"a": 2, "b": 1, "c": 4}))
    print("  → 배치는 생산을 바꾸지 않는다(room_produces 는 방 레벨만 본다; role_effects 는 배치와 무관하게 전원 합산).")
    print("  8시간 생산 — 식량창고 불 끔(8시간 내내):", produce({}, lights={"2": False}))
    print("  8시간 생산 — 전원 내림(8시간 내내):", produce({}, power=False))
    print("  7시간 경과 후 전원 내렸다가 바로 켬(틱 경계 안 넘음):", produce({}, power=True, elapsed_h=7.0),
          "← 0 은 '아직 틱이 안 됨'. 다음 틱에 정상 8시간치가 들어온다(전원은 정산 순간에만 읽는다)")
    print("  → 불·전원 대가는 '꺼진 채로 8시간 틱 경계를 넘길 때'만 생긴다. 습격을 넘기고 바로 켜면 대가 0.")


def ignore_check():
    hr("A2-추가. '접촉을 누르지 않는' 플레이어 — server.ensure_raid 로 실측")
    st = make_state([{"id": "pantry", "slot": 2, "level": 1}, {"id": "quarters", "slot": 4, "level": 1}],
                    [person("a", "cook", 5)])
    st["raid"] = None; st["raid_log"] = []
    st["created"] = time.time() - 86400 * 5          # 6일차
    r1 = S.ensure_raid(st, "audit_ignore", force="lid", grade_force=4)
    print(f"  6일차 습격: {r1['creature']} → 대상 {r1['target_slot']}, 세기 {r1['severity']}, resolved={r1['resolved']}")
    st["created"] -= 86400                           # 하루가 지났다(접촉 버튼을 누르지 않음)
    r2 = S.ensure_raid(st, "audit_ignore")
    print(f"  7일차 ensure_raid → 어제 습격은 판정 없이 덮어쓰였다: raid_log {len(st['raid_log'])}건, "
          f"물 찬 방 {sum(1 for r in st['rooms'] if r.get('flooded'))}칸, 오늘 = {(r2 or {}).get('creature', '없음')}")
    print("  → static/base.js 는 #radv 클릭에서만 /api/raid/advance 를 부른다(타이머 없음). 누르지 않으면 상실도 보상도 0.")
    print("    보상이 작아(threats.json rewards: 등급4 막음 = 부품2·직물2·의약1·사기2) '누르지 않기'가 상실 회피의 지배 전략이 된다.")


def main():
    t0 = time.time()
    section_constants()
    stage_scenarios()
    sensitivity()
    reversal()
    preview_steps()
    if "--no-enum" not in sys.argv:
        enumerate_space()
    sim_30()
    tradeoff_check()
    ignore_check()
    print(f"\n(완료 {time.time() - t0:.0f}초)")


if __name__ == "__main__":
    main()
